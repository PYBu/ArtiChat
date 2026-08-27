"""Video generation configuration and job endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from open_webui.models.config import Config
from open_webui.models.video_generation import VideoGenerationJob, VideoGenerationJobs
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_permission
from open_webui.utils.video_generation import create_video_job, release_video_job_billing
from open_webui.utils.media_billing import media_cost_chatpoints, parse_media_rate
from open_webui.internal.db import get_async_db_context
from pydantic import BaseModel, Field

router = APIRouter()

VIDEO_CONFIG_KEYS = {
    'ENABLE_VIDEO_GENERATION': 'video_generation.enable',
    'VIDEO_GENERATION_ADMIN_ONLY': 'video_generation.admin_only',
    'VIDEO_GENERATION_PROVIDER': 'video_generation.provider',
    'VIDEO_GENERATION_BASE_URL': 'video_generation.base_url',
    'VIDEO_GENERATION_API_KEY': 'video_generation.api_key',
    'VIDEO_GENERATION_API_VERSION': 'video_generation.api_version',
    'VIDEO_GENERATION_MODEL': 'video_generation.model',
    'VIDEO_GENERATION_REGION': 'video_generation.region',
    'VIDEO_GENERATION_RESOLUTION': 'video_generation.resolution',
    'VIDEO_GENERATION_DURATION': 'video_generation.duration',
    'VIDEO_GENERATION_RATIO': 'video_generation.ratio',
    'VIDEO_GENERATION_POLL_INTERVAL': 'video_generation.poll_interval',
    'VIDEO_GENERATION_MAX_CONCURRENCY': 'video_generation.max_concurrency',
    'VIDEO_GENERATION_MAX_OUTPUT_MB': 'video_generation.max_output_mb',
    'VIDEO_GENERATION_MAX_ATTEMPTS': 'video_generation.max_attempts',
    'VIDEO_GENERATION_WATERMARK': 'video_generation.watermark',
    'VIDEO_GENERATION_PROMPT_ENABLE': 'video_generation.prompt.enable',
    'VIDEO_GENERATION_PROMPT_TEMPLATE': 'video_generation.prompt.template',
    'VIDEO_GENERATION_CHATPOINTS_PER_SECOND': 'billing.media.video_chatpoints_per_second',
    'VIDEO_GENERATION_REQUIRE_CONFIRMATION': 'billing.media.video_require_confirmation',
    'VIDEO_GENERATION_DAILY_MAX_CHATPOINTS': 'billing.media.video_daily_max_chatpoints',
}


def _updates(data: dict) -> dict:
    return {storage_key: data[field] for field, storage_key in VIDEO_CONFIG_KEYS.items() if field in data}


async def _get_values() -> dict:
    values = await Config.get_many(*VIDEO_CONFIG_KEYS.values())
    result = {field: values.get(storage_key) for field, storage_key in VIDEO_CONFIG_KEYS.items()}
    key = result.get('VIDEO_GENERATION_API_KEY') or ''
    result['VIDEO_GENERATION_API_KEY_SET'] = bool(key)
    result['VIDEO_GENERATION_API_KEY'] = '********' if key else ''
    return result


class VideoConfig(BaseModel):
    ENABLE_VIDEO_GENERATION: bool = False
    VIDEO_GENERATION_ADMIN_ONLY: bool = True
    VIDEO_GENERATION_PROVIDER: str = 'minimax'
    VIDEO_GENERATION_BASE_URL: str = ''
    VIDEO_GENERATION_API_KEY: str = ''
    VIDEO_GENERATION_API_VERSION: str = 'v2'
    VIDEO_GENERATION_MODEL: str = ''
    VIDEO_GENERATION_REGION: str = 'cn-beijing'
    VIDEO_GENERATION_RESOLUTION: str = '768P'
    VIDEO_GENERATION_DURATION: int = Field(default=5, ge=4, le=15)
    VIDEO_GENERATION_RATIO: str = '16:9'
    VIDEO_GENERATION_POLL_INTERVAL: float = Field(default=10, ge=1, le=120)
    VIDEO_GENERATION_MAX_CONCURRENCY: int = Field(default=2, ge=1, le=16)
    VIDEO_GENERATION_MAX_OUTPUT_MB: int = Field(default=200, ge=1, le=2048)
    VIDEO_GENERATION_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    VIDEO_GENERATION_WATERMARK: bool = False
    VIDEO_GENERATION_PROMPT_ENABLE: bool = True
    VIDEO_GENERATION_PROMPT_TEMPLATE: str = ''
    VIDEO_GENERATION_CHATPOINTS_PER_SECOND: float = Field(default=1, ge=0, le=1_000_000)
    VIDEO_GENERATION_REQUIRE_CONFIRMATION: bool = True
    VIDEO_GENERATION_DAILY_MAX_CHATPOINTS: float = Field(default=0, ge=0, le=1_000_000)


@router.get('/config', response_model=dict)
async def get_video_config(user=Depends(get_admin_user)):
    return await _get_values()


@router.post('/config/update', response_model=dict)
async def update_video_config(form_data: VideoConfig, user=Depends(get_admin_user)):
    data = form_data.model_dump()
    api_key = data.get('VIDEO_GENERATION_API_KEY', '')
    if api_key in {'', '********'}:
        data.pop('VIDEO_GENERATION_API_KEY', None)
    if data.get('VIDEO_GENERATION_PROVIDER') not in {'minimax', 'seedance', 'modelark', 'volcengine'}:
        raise HTTPException(status_code=400, detail='Unsupported video provider')
    if data.get('VIDEO_GENERATION_PROVIDER') == 'minimax' and data.get('VIDEO_GENERATION_API_VERSION') != 'v2':
        raise HTTPException(status_code=400, detail='MiniMax video integration currently requires API version v2')
    for field in ('VIDEO_GENERATION_CHATPOINTS_PER_SECOND', 'VIDEO_GENERATION_DAILY_MAX_CHATPOINTS'):
        try:
            parse_media_rate(data.get(field))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    await Config.upsert(_updates(data))
    return await _get_values()


@router.get('/estimate', response_model=dict)
async def estimate_video_generation(
    duration: int | None = Query(default=None, ge=4, le=15),
    user=Depends(get_verified_user),
):
    config = await Config.get_many(
        'video_generation.enable',
        'video_generation.admin_only',
        'video_generation.duration',
        'billing.media.video_chatpoints_per_second',
        'billing.media.video_require_confirmation',
        'billing.media.video_daily_max_chatpoints',
    )
    if not config.get('video_generation.enable'):
        raise HTTPException(status_code=403, detail='Video generation is disabled')
    if config.get('video_generation.admin_only') and user.role != 'admin':
        raise HTTPException(status_code=403, detail='Video generation is currently admin-only')
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.video_generation', await Config.get('user.permissions')
    ):
        raise HTTPException(status_code=403, detail='Video generation is not permitted for this user')
    requested_duration = int(duration or config.get('video_generation.duration') or 5)
    rate = parse_media_rate(config.get('billing.media.video_chatpoints_per_second'))
    daily_cap = parse_media_rate(config.get('billing.media.video_daily_max_chatpoints'))
    return {
        'duration_seconds': requested_duration,
        'rate_chatpoints_per_second': str(rate),
        'estimated_chatpoints': str(media_cost_chatpoints(requested_duration, rate)),
        'daily_max_chatpoints': str(daily_cap),
        'requires_confirmation': bool(
            user.role != 'admin' and rate > 0 and config.get('billing.media.video_require_confirmation', True)
        ),
    }


class CreateVideoForm(BaseModel):
    prompt: str = Field(min_length=1, max_length=7000)
    model: str | None = None
    first_frame_url: str | None = None
    duration: int | None = Field(default=None, ge=4, le=15)
    resolution: str | None = None
    ratio: str | None = None
    watermark: bool | None = None
    confirm_cost: bool = False
    chat_id: str | None = None
    message_id: str | None = None


@router.post('/generations', status_code=status.HTTP_202_ACCEPTED)
async def generate_video(request: Request, form_data: CreateVideoForm, user=Depends(get_verified_user)):
    job = await create_video_job(
        request,
        prompt=form_data.prompt,
        first_frame_url=form_data.first_frame_url,
        model=form_data.model,
        options={
            key: value
            for key, value in {
                'duration': form_data.duration,
                'resolution': form_data.resolution,
                'ratio': form_data.ratio,
                'watermark': form_data.watermark,
            }.items()
            if value is not None
        },
        user=user,
        chat_id=form_data.chat_id,
        message_id=form_data.message_id,
        confirm_cost=form_data.confirm_cost,
    )
    return {'status': 'queued', 'job': job.model_dump()}


@router.get('/jobs')
async def list_video_jobs(limit: int = 50, user=Depends(get_verified_user)):
    jobs = await VideoGenerationJobs.list_for_user(user.id, limit=limit)
    return {'items': [job.model_dump() for job in jobs]}


@router.get('/jobs/{job_id}')
async def get_video_job(request: Request, job_id: str, user=Depends(get_verified_user)):
    job = await VideoGenerationJobs.get_for_user(job_id, user.id, is_admin=user.role == 'admin')
    if not job:
        raise HTTPException(status_code=404, detail='Video generation job not found')
    payload = job.model_dump()
    if job.output_file_id:
        payload['file_url'] = str(request.app.url_path_for('get_file_content_by_id', id=job.output_file_id))
        payload['file'] = {'type': 'video', 'id': job.output_file_id, 'url': payload['file_url']}
    return payload


@router.post('/jobs/{job_id}/cancel')
async def cancel_video_job(job_id: str, user=Depends(get_verified_user)):
    async with get_async_db_context() as db:
        row = await db.get(VideoGenerationJob, job_id)
        if not row or (row.user_id != user.id and user.role != 'admin'):
            raise HTTPException(status_code=404, detail='Video generation job not found')
        if row.status in {'succeeded', 'failed', 'cancelled', 'expired'}:
            return {'status': row.status, 'job_id': row.id}
        row.cancel_requested = True
        if not row.provider_task_id:
            await release_video_job_billing(row, '用户取消视频生成')
            row.status = 'cancelled'
            row.completed_at = int(time.time())
        row.updated_at = int(time.time())
        await db.commit()
        return {'status': 'cancel_requested', 'job_id': row.id}
