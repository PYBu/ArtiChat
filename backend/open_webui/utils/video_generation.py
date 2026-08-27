"""Provider adapters and durable worker for asynchronous video generation."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import mimetypes
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urljoin

import aiohttp
from fastapi import HTTPException, Request
from fastapi import UploadFile
from open_webui.internal.db import get_async_db_context
from open_webui.config import (
    VIDEO_GENERATION_API_KEY,
    VIDEO_GENERATION_API_VERSION,
    VIDEO_GENERATION_BASE_URL,
    VIDEO_GENERATION_DURATION,
    VIDEO_GENERATION_MAX_ATTEMPTS,
    VIDEO_GENERATION_MAX_CONCURRENCY,
    VIDEO_GENERATION_MAX_OUTPUT_MB,
    VIDEO_GENERATION_MODEL,
    VIDEO_GENERATION_POLL_INTERVAL,
    DEFAULT_VIDEO_GENERATION_PROMPT_TEMPLATE,
    VIDEO_GENERATION_PROVIDER,
    VIDEO_GENERATION_RATIO,
    VIDEO_GENERATION_REGION,
    VIDEO_GENERATION_RESOLUTION,
    VIDEO_GENERATION_WATERMARK,
)
from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL
from open_webui.models.chats import Chats
from open_webui.models.config import Config
from open_webui.models.users import Users
from open_webui.models.video_generation import VideoGenerationJob, VideoGenerationJobs
from open_webui.retrieval.web.utils import get_ssrf_safe_session, validate_url
from open_webui.routers.files import upload_file_handler
from open_webui.socket.main import get_event_emitter
from open_webui.utils.access_control import has_permission
from open_webui.utils.media_billing import (
    MediaBillingContext,
    media_cost_chatpoints,
    media_cost_micros,
    parse_media_rate,
    release_media_generation,
    reserve_media_generation,
    settle_media_generation,
    utc_day_start,
)
from sqlalchemy import select

log = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({'succeeded', 'failed', 'cancelled', 'expired'})
ACTIVE_STATUSES = frozenset({'queued', 'submitting', 'running'})
VIDEO_GENERATION_CHAT_WAIT_TIMEOUT = 15 * 60
VIDEO_MIME_TYPES = frozenset({'video/mp4', 'video/quicktime', 'video/webm', 'video/x-msvideo'})


@dataclass(frozen=True)
class VideoTask:
    task_id: str
    status: str
    progress: int = 0
    output_url: str | None = None
    response: dict | None = None
    error_code: str | None = None
    error_message: str | None = None


class VideoProviderError(RuntimeError):
    """A provider response with an explicit retry policy."""

    def __init__(self, code: str, message: str, *, retryable: bool, status: int | None = None):
        super().__init__(f'{code}: {message}')
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status = status


def _clean_base_url(value: str | None) -> str:
    return (value or '').strip().rstrip('/')


def _provider_config(values: dict | None = None) -> SimpleNamespace:
    values = values or {}
    return SimpleNamespace(
        provider=(values.get('video_generation.provider') or VIDEO_GENERATION_PROVIDER or 'minimax').strip().lower(),
        base_url=_clean_base_url(values.get('video_generation.base_url') or VIDEO_GENERATION_BASE_URL),
        api_key=(values.get('video_generation.api_key') or VIDEO_GENERATION_API_KEY or '').strip(),
        api_version=(values.get('video_generation.api_version') or VIDEO_GENERATION_API_VERSION or 'v2').strip().lower(),
        model=(values.get('video_generation.model') or VIDEO_GENERATION_MODEL or '').strip(),
        region=(values.get('video_generation.region') or VIDEO_GENERATION_REGION or 'cn-beijing').strip(),
        resolution=values.get('video_generation.resolution') or VIDEO_GENERATION_RESOLUTION,
        duration=values.get('video_generation.duration') or VIDEO_GENERATION_DURATION,
        ratio=values.get('video_generation.ratio') or VIDEO_GENERATION_RATIO,
        watermark=(
            values['video_generation.watermark']
            if 'video_generation.watermark' in values and values['video_generation.watermark'] is not None
            else VIDEO_GENERATION_WATERMARK
        ),
        poll_interval=values.get('video_generation.poll_interval') or VIDEO_GENERATION_POLL_INTERVAL,
        max_concurrency=values.get('video_generation.max_concurrency') or VIDEO_GENERATION_MAX_CONCURRENCY,
        max_output_mb=values.get('video_generation.max_output_mb') or VIDEO_GENERATION_MAX_OUTPUT_MB,
        max_attempts=values.get('video_generation.max_attempts') or VIDEO_GENERATION_MAX_ATTEMPTS,
    )


def _validate_video_options(config: SimpleNamespace, options: dict) -> None:
    """Reject provider combinations that are known to fail before reserving work."""

    if config.provider != 'minimax' or config.api_version != 'v2':
        return

    model = str(config.model or '').strip().lower().replace('_', '-')
    if model not in {'minimax-h3', 'minimax-h3-v2'}:
        return

    raw_resolution = options.get('resolution') or config.resolution or '768P'
    resolution = str(raw_resolution).strip().upper()
    if resolution not in {'768P', '2K'}:
        raise HTTPException(
            status_code=400,
            detail=(
                'MiniMax-H3 v2 supports only 768P or 2K. '
                f'Received {raw_resolution!r}; choose 768P or 2K.'
            ),
        )
    if options.get('resolution') is not None:
        options['resolution'] = resolution


async def _load_provider_config() -> SimpleNamespace:
    values = await Config.get_many(
        'video_generation.provider',
        'video_generation.base_url',
        'video_generation.api_key',
        'video_generation.api_version',
        'video_generation.model',
        'video_generation.region',
        'video_generation.resolution',
        'video_generation.duration',
        'video_generation.ratio',
        'video_generation.watermark',
        'video_generation.poll_interval',
        'video_generation.max_concurrency',
        'video_generation.max_output_mb',
        'video_generation.max_attempts',
    )
    return _provider_config(values)


def _provider_error(payload: dict, fallback: str) -> tuple[str, str]:
    error = payload.get('error') if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get('type') or 'provider_error'), str(error.get('message') or fallback)
    return 'provider_error', str(payload.get('message') or fallback) if isinstance(payload, dict) else fallback


def _normalise_video_status(value: str | None) -> str:
    """Map provider-specific progress labels onto the worker state machine."""

    status = str(value or '').strip().lower().replace('-', '_').replace(' ', '_')
    return {
        'pending': 'queued',
        'preparing': 'queued',
        'queue': 'queued',
        'queued': 'queued',
        'queueing': 'queued',
        'submitting': 'submitting',
        'processing': 'running',
        'generating': 'running',
        'running': 'running',
        'success': 'succeeded',
        'succeeded': 'succeeded',
        'complete': 'succeeded',
        'completed': 'succeeded',
        'fail': 'failed',
        'failed': 'failed',
        'error': 'failed',
        'cancel': 'cancelled',
        'canceled': 'cancelled',
        'cancelled': 'cancelled',
        'expire': 'expired',
        'expired': 'expired',
    }.get(status, 'running')


def _job_billing_context(row: VideoGenerationJob) -> MediaBillingContext | None:
    if not row.billing_reservation_id or row.billing_status != 'reserved':
        return None
    rate_micros = int(row.billing_unit_price_micros or 0)
    return MediaBillingContext(
        user_id=row.user_id,
        media_type='video',
        unit='second',
        requested_units=max(1, int(row.billing_unit_count or 1)),
        rate_chatpoints=Decimal(rate_micros) / Decimal(1_000_000),
        rate_micros=rate_micros,
        reservation_id=row.billing_reservation_id,
        model_id=row.model or f'video:{row.provider}',
        chat_id=row.chat_id,
        message_id=row.message_id,
        metadata={'video_generation_job_id': row.id, 'provider': row.provider},
    )


def _video_duration_from_result(result: VideoTask, fallback: int) -> int:
    candidates = []
    payload = result.response if isinstance(result.response, dict) else {}
    candidates.extend([payload.get('duration'), payload.get('duration_seconds')])
    for key in ('task', 'content', 'data'):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.extend([nested.get('duration'), nested.get('duration_seconds')])
    for candidate in candidates:
        try:
            value = int(float(candidate))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return max(1, int(fallback))


async def _release_job_billing(row: VideoGenerationJob, reason: str) -> None:
    context = _job_billing_context(row)
    if context is None:
        return
    await release_media_generation(context, reason=reason)
    row.billing_status = 'released'


async def _settle_job_billing(row: VideoGenerationJob, duration_seconds: int) -> None:
    context = _job_billing_context(row)
    if context is None:
        return
    usage = await settle_media_generation(
        context,
        units=max(1, int(duration_seconds)),
        metadata={'actual_duration_seconds': max(1, int(duration_seconds))},
    )
    row.billing_status = 'settled'
    row.billing_usage_id = getattr(usage, 'id', None)


async def release_video_job_billing(row: VideoGenerationJob, reason: str) -> None:
    await _release_job_billing(row, reason)


class VideoProvider(ABC):
    name: str

    def __init__(self, config: SimpleNamespace):
        self.config = config

    @abstractmethod
    async def submit(self, *, prompt: str, first_frame_url: str | None, model: str | None, options: dict) -> VideoTask:
        raise NotImplementedError

    @abstractmethod
    async def query(self, task_id: str) -> VideoTask:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, task_id: str) -> None:
        raise NotImplementedError


class MiniMaxH3Provider(VideoProvider):
    name = 'minimax'

    def _base_url(self) -> str:
        return _clean_base_url(self.config.base_url or 'https://api.minimaxi.com')

    def _headers(self) -> dict[str, str]:
        if not self.config.api_key:
            raise HTTPException(status_code=503, detail='Video generation API key is not configured')
        return {'Authorization': f'Bearer {self.config.api_key}', 'Content-Type': 'application/json'}

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                urljoin(f'{self._base_url()}/', path.lstrip('/')),
                headers=self._headers(),
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
                timeout=aiohttp.ClientTimeout(total=60),
                **kwargs,
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, json.JSONDecodeError, ValueError):
                    # Do not persist or surface an unbounded HTML/proxy body.
                    raise VideoProviderError(
                        'invalid_provider_response',
                        f'MiniMax returned a non-JSON response ({response.status})',
                        retryable=response.status >= 500,
                        status=response.status,
                    )
                if response.status >= 400:
                    code, message = _provider_error(payload, f'MiniMax request failed ({response.status})')
                    raise VideoProviderError(
                        code,
                        message,
                        retryable=response.status >= 500,
                        status=response.status,
                    )
                return payload

    async def submit(self, *, prompt: str, first_frame_url: str | None, model: str | None, options: dict) -> VideoTask:
        content = [{'type': 'text', 'text': prompt}]
        if first_frame_url:
            content.append({'type': 'image_url', 'image_url': {'url': first_frame_url}, 'role': 'first_frame'})
        input_mode = 'image' if first_frame_url else 'text'
        ratio = 'adaptive' if first_frame_url else options.get('ratio', self.config.ratio)
        payload = {
            'model': model or self.config.model or 'MiniMax-H3',
            'content': content,
            'resolution': options.get('resolution', self.config.resolution),
            'duration': int(options.get('duration', self.config.duration)),
            'ratio': ratio,
            'aigc_watermark': bool(options.get('watermark', self.config.watermark)),
        }
        response = await self._request('POST', '/v2/video_generation', json=payload)
        task_id = str(response.get('task_id') or '')
        if not task_id:
            code, message = _provider_error(response, 'MiniMax did not return a task id')
            raise RuntimeError(f'{code}: {message}')
        return VideoTask(task_id=task_id, status='queued', response=response)

    async def query(self, task_id: str) -> VideoTask:
        response = await self._request('GET', f'/v2/query/video_generation/{task_id}')
        task = response.get('task') or response
        status = _normalise_video_status(task.get('status'))
        content = task.get('content') or {}
        return VideoTask(
            task_id=task_id,
            status=status,
            progress=100 if status == 'succeeded' else 0,
            output_url=content.get('url') if isinstance(content, dict) else None,
            response=response,
            error_code=(task.get('error') or {}).get('code') if isinstance(task.get('error'), dict) else None,
            error_message=(task.get('error') or {}).get('message') if isinstance(task.get('error'), dict) else None,
        )

    async def cancel(self, task_id: str) -> None:
        await self._request('DELETE', f'/v2/video_generation/{task_id}')


class SeedanceProvider(VideoProvider):
    name = 'seedance'

    def _base_url(self) -> str:
        if self.config.base_url:
            return _clean_base_url(self.config.base_url)
        return f'https://ark.{self.config.region}.volces.com'

    def _headers(self) -> dict[str, str]:
        if not self.config.api_key:
            raise HTTPException(status_code=503, detail='Video generation API key is not configured')
        return {'Authorization': f'Bearer {self.config.api_key}', 'Content-Type': 'application/json'}

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                urljoin(f'{self._base_url()}/', path.lstrip('/')),
                headers=self._headers(),
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
                timeout=aiohttp.ClientTimeout(total=60),
                **kwargs,
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, json.JSONDecodeError, ValueError):
                    raise VideoProviderError(
                        'invalid_provider_response',
                        f'Seedance returned a non-JSON response ({response.status})',
                        retryable=response.status >= 500,
                        status=response.status,
                    )
                if response.status >= 400:
                    code, message = _provider_error(payload, f'Seedance request failed ({response.status})')
                    raise VideoProviderError(
                        code,
                        message,
                        retryable=response.status >= 500,
                        status=response.status,
                    )
                return payload

    def _path(self, suffix: str = '') -> str:
        return f'/api/v3/contents/generations/tasks{suffix}'

    async def submit(self, *, prompt: str, first_frame_url: str | None, model: str | None, options: dict) -> VideoTask:
        content: list[dict] = [{'type': 'text', 'text': prompt}]
        if first_frame_url:
            content.append({'type': 'image_url', 'image_url': {'url': first_frame_url}})
        payload = {
            'model': model or self.config.model,
            'content': content,
            'resolution': options.get('resolution', self.config.resolution),
            'duration': int(options.get('duration', self.config.duration)),
            'ratio': options.get('ratio', self.config.ratio),
            'watermark': bool(options.get('watermark', self.config.watermark)),
        }
        response = await self._request('POST', self._path(), json=payload)
        task_id = str(response.get('id') or response.get('task_id') or '')
        if not task_id:
            code, message = _provider_error(response, 'Seedance did not return a task id')
            raise RuntimeError(f'{code}: {message}')
        return VideoTask(task_id=task_id, status='queued', response=response)

    async def query(self, task_id: str) -> VideoTask:
        response = await self._request('GET', self._path(f'/{task_id}'))
        status = _normalise_video_status(response.get('status'))
        content = response.get('content') or {}
        error = response.get('error') or {}
        return VideoTask(
            task_id=task_id,
            status=status,
            progress=100 if status == 'succeeded' else 0,
            output_url=content.get('video_url') if isinstance(content, dict) else None,
            response=response,
            error_code=error.get('code') if isinstance(error, dict) else None,
            error_message=error.get('message') if isinstance(error, dict) else None,
        )

    async def cancel(self, task_id: str) -> None:
        await self._request('DELETE', self._path(f'/{task_id}'))


def get_video_provider(config: SimpleNamespace | None = None) -> VideoProvider:
    config = config or _provider_config()
    if config.provider == 'minimax':
        if config.api_version != 'v2':
            raise HTTPException(status_code=400, detail='Only MiniMax H3 v2 is supported by the video MVP')
        return MiniMaxH3Provider(config)
    if config.provider in {'seedance', 'modelark', 'volcengine'}:
        return SeedanceProvider(config)
    raise HTTPException(status_code=400, detail=f'Unsupported video provider: {config.provider}')


async def _resolve_first_frame_url(reference: str | None, request: Request, user) -> str | None:
    if not reference:
        return None
    if reference.startswith(('http://', 'https://', 'data:')):
        return reference
    from open_webui.utils.image_refs import resolve_image_reference

    resolved = await resolve_image_reference(reference, user)
    if len(resolved.data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='First-frame image exceeds the provider 30 MB limit')
    return resolved.as_data_url()


async def _download_video(
    request: Request, url: str, user, metadata: dict, *, max_output_mb: int
) -> tuple[str, str]:
    await asyncio.to_thread(validate_url, url)
    max_bytes = max(1, int(max_output_mb)) * 1024 * 1024
    async with get_ssrf_safe_session() as session:
        async with session.get(url, ssl=AIOHTTP_CLIENT_SESSION_SSL, allow_redirects=True) as response:
            response.raise_for_status()
            content_type = (response.headers.get('content-type') or '').split(';', 1)[0].lower()
            if content_type not in VIDEO_MIME_TYPES:
                raise RuntimeError(f'Video output has unsupported content type: {content_type or "unknown"}')
            if response.content_length and response.content_length > max_bytes:
                raise RuntimeError('Video output exceeds the configured size limit')
            chunks = bytearray()
            async for chunk in response.content.iter_chunked(256 * 1024):
                chunks.extend(chunk)
                if len(chunks) > max_bytes:
                    raise RuntimeError('Video output exceeds the configured size limit')
    if not chunks:
        raise RuntimeError('Video output is empty')
    extension = mimetypes.guess_extension(content_type) or '.mp4'
    upload = UploadFile(file=io.BytesIO(bytes(chunks)), filename=f'generated-video{extension}', headers={'content-type': content_type})
    item = await upload_file_handler(
        request,
        file=upload,
        metadata={**metadata, 'asset_source': 'generated', 'asset_category': 'video'},
        process=False,
        user=user,
    )
    if not item or not item.id:
        raise RuntimeError('Failed to persist generated video')
    return item.id, str(request.app.url_path_for('get_file_content_by_id', id=item.id))


async def _emit_job_event(job: VideoGenerationJob, payload: dict) -> None:
    if not job.user_id or not job.chat_id or not job.message_id:
        return
    emitter = await get_event_emitter(
        {'user_id': job.user_id, 'chat_id': job.chat_id, 'message_id': job.message_id},
    )
    if emitter:
        await emitter({'type': 'status', 'data': payload})


async def _attach_video(request: Request, job: VideoGenerationJob, file_id: str, url: str) -> None:
    if job.chat_id and job.message_id:
        linked = await Chats.insert_chat_files(job.chat_id, job.message_id, [file_id], user_id=job.user_id)
        if not linked:
            return
        emitter = await get_event_emitter(
            {'user_id': job.user_id, 'chat_id': job.chat_id, 'message_id': job.message_id},
        )
        if emitter:
            await emitter(
                {'type': 'files', 'data': {'files': [{'type': 'video', 'id': file_id, 'url': url}]}}
            )


async def _process_job(request: Request, row: VideoGenerationJob) -> None:
    config = await _load_provider_config()
    # Keep queued jobs on the provider selected when they were created, even if
    # an administrator changes the default provider while they are running.
    config.provider = row.provider
    provider = get_video_provider(config)
    now = int(time.time())
    try:
        if row.cancel_requested:
            if row.provider_task_id:
                await provider.cancel(row.provider_task_id)
            await _release_job_billing(row, '用户取消视频生成')
            row.status = 'cancelled'
            row.completed_at = now
            row.updated_at = now
            return

        if not row.provider_task_id:
            await _emit_job_event(row, {'status_id': 'video.submitting', 'description': '正在提交视频生成任务', 'done': False})
            options = row.request_payload.get('options') or {}
            submitted = await provider.submit(
                prompt=row.prompt,
                first_frame_url=row.request_payload.get('first_frame_url'),
                model=row.model,
                options=options,
            )
            row.provider_task_id = submitted.task_id
            row.provider_response = submitted.response
            row.status = 'running'
            row.progress = 5
            row.next_poll_at = now + max(1, int(config.poll_interval))
            row.updated_at = now
            await _emit_job_event(row, {'status_id': 'video.running', 'description': '视频生成中', 'done': False, 'progress': 5})
            return

        result = await provider.query(row.provider_task_id)
        row.status = result.status
        row.progress = result.progress
        row.provider_response = result.response
        row.updated_at = now
        if result.status in {'queued', 'submitting', 'running'}:
            row.next_poll_at = now + max(1, int(config.poll_interval))
            await _emit_job_event(row, {'status_id': 'video.running', 'description': '视频生成中', 'done': False, 'progress': row.progress})
            return
        if result.status == 'succeeded':
            if not result.output_url:
                raise RuntimeError('Provider reported success without a video URL')
            user = await Users.get_user_by_id(row.user_id)
            if not user:
                raise RuntimeError('Video owner no longer exists')
            if row.output_file_id:
                file_id = row.output_file_id
                file_url = str(request.app.url_path_for('get_file_content_by_id', id=file_id))
            else:
                file_id, file_url = await _download_video(
                    request,
                    result.output_url,
                    user,
                    {'video_generation_job_id': row.id, 'chat_id': row.chat_id, 'message_id': row.message_id},
                    max_output_mb=int(config.max_output_mb),
                )
                row.output_file_id = file_id
            row.progress = 100
            row.completed_at = now
            await _attach_video(request, row, file_id, file_url)
            await _settle_job_billing(row, _video_duration_from_result(result, row.billing_unit_count or int(config.duration)))
            await _emit_job_event(row, {'status_id': 'video.succeeded', 'description': '视频已生成', 'done': True, 'progress': 100})
            return
        row.error_code = result.error_code or result.status
        row.error_message = result.error_message or f'视频生成以“{result.status}”状态结束'
        await _release_job_billing(row, row.error_message)
        row.completed_at = now
        await _emit_job_event(row, {'status_id': 'video.failed', 'description': row.error_message, 'done': True, 'error': row.error_message})
    except asyncio.CancelledError:
        raise
    except VideoProviderError as exc:
        row.attempts = int(row.attempts or 0) + 1
        row.error_code = exc.code
        row.error_message = exc.message
        row.updated_at = now
        if not exc.retryable or row.attempts >= max(1, int(config.max_attempts)):
            await _release_job_billing(row, f'视频生成失败：{exc.message}')
            row.status = 'failed'
            row.completed_at = now
            await _emit_job_event(
                row,
                {'status_id': 'video.failed', 'description': f'视频生成失败：{exc.message}', 'done': True, 'error': exc.message},
            )
        else:
            row.status = 'queued' if not row.provider_task_id else 'running'
            row.next_poll_at = now + min(60, 2 ** min(row.attempts, 5))
            await _emit_job_event(row, {'status_id': 'video.retrying', 'description': '视频生成将重试', 'done': False, 'progress': row.progress})
    except Exception as exc:
        row.attempts = int(row.attempts or 0) + 1
        row.error_code = 'worker_error'
        row.error_message = str(exc)
        row.updated_at = now
        if row.attempts >= max(1, int(config.max_attempts)):
            await _release_job_billing(row, f'视频生成失败：{exc}')
            row.status = 'failed'
            row.completed_at = now
            await _emit_job_event(row, {'status_id': 'video.failed', 'description': f'视频生成失败：{exc}', 'done': True, 'error': str(exc)})
        else:
            row.status = 'queued' if not row.provider_task_id else 'running'
            row.next_poll_at = now + min(60, 2 ** min(row.attempts, 5))
            await _emit_job_event(row, {'status_id': 'video.retrying', 'description': '视频生成将重试', 'done': False, 'progress': row.progress})


def _internal_request(app) -> Request:
    return Request(
        {
            'type': 'http',
            'asgi.version': '3.0',
            'asgi.spec_version': '2.0',
            'method': 'POST',
            'path': '/internal/video-generation',
            'query_string': b'',
            'headers': [],
            'client': ('127.0.0.1', 0),
            'server': ('127.0.0.1', 80),
            'scheme': 'http',
            'app': app,
        }
    )


async def _claim_due_video_jobs(*, now: int, limit: int, db=None) -> list[str]:
    """Claim due or lease-expired jobs in one short transaction."""

    async with get_async_db_context(db) as session:
        result = await session.execute(
            select(VideoGenerationJob)
            .where(
                VideoGenerationJob.status.in_(tuple(ACTIVE_STATUSES)),
                VideoGenerationJob.next_poll_at <= now,
                (VideoGenerationJob.lease_until.is_(None) | (VideoGenerationJob.lease_until < now)),
            )
            .order_by(VideoGenerationJob.next_poll_at.asc())
            .limit(max(1, int(limit)))
        )
        rows = list(result.scalars().all())
        for row in rows:
            row.lease_until = now + 90
            row.updated_at = now
        if rows:
            await session.commit()
        return [row.id for row in rows]


async def video_generation_worker(app) -> None:
    """Claim due jobs in short transactions and process them outside the lock."""
    while True:
        try:
            now = int(time.time())
            runtime = await _load_provider_config()
            concurrency = max(1, int(runtime.max_concurrency))
            job_ids = await _claim_due_video_jobs(now=now, limit=concurrency)
            if job_ids:
                request = _internal_request(app)
                semaphore = asyncio.Semaphore(concurrency)

                async def run(job_id):
                    async with semaphore:
                        async with get_async_db_context() as db:
                            current = await db.get(VideoGenerationJob, job_id)
                            if not current:
                                return
                            await _process_job(request, current)
                            current.lease_until = None
                            await db.commit()

                await asyncio.gather(*(run(job_id) for job_id in job_ids))
            else:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception('Video generation worker iteration failed')
            await asyncio.sleep(2)


async def create_video_job(
    request: Request,
    *,
    prompt: str,
    first_frame_url: str | None,
    model: str | None,
    options: dict | None,
    user,
    chat_id: str | None,
    message_id: str | None,
    confirm_cost: bool = False,
):
    config = await Config.get_many(
        'video_generation.enable',
        'video_generation.admin_only',
        'video_generation.provider',
        'video_generation.api_version',
        'video_generation.base_url',
        'video_generation.api_key',
        'video_generation.model',
        'video_generation.region',
        'video_generation.resolution',
        'video_generation.duration',
        'video_generation.ratio',
        'video_generation.watermark',
        'video_generation.poll_interval',
        'video_generation.max_concurrency',
        'video_generation.max_output_mb',
        'video_generation.max_attempts',
        'billing.media.video_chatpoints_per_second',
        'billing.media.video_require_confirmation',
        'billing.media.video_daily_max_chatpoints',
    )
    if not config.get('video_generation.enable'):
        raise HTTPException(status_code=403, detail='Video generation is disabled')
    if config.get('video_generation.admin_only') and user.role != 'admin':
        raise HTTPException(status_code=403, detail='Video generation is currently admin-only')
    if user.role != 'admin' and not await has_permission(user.id, 'features.video_generation', await Config.get('user.permissions')):
        raise HTTPException(status_code=403, detail='Video generation is not permitted for this user')
    if not prompt.strip():
        raise HTTPException(status_code=400, detail='A video prompt is required')
    prompt = prompt.strip()
    if await Config.get('video_generation.prompt.enable'):
        template = await Config.get('video_generation.prompt.template')
        template = template or DEFAULT_VIDEO_GENERATION_PROMPT_TEMPLATE
        prompt = template.replace('{{PROMPT}}', prompt).strip()
    prompt = prompt[:7000]
    provider_values = {
        key: value
        for key, value in config.items()
        if key.startswith('video_generation.')
    }
    provider_config = _provider_config(provider_values)
    provider_config.model = model or provider_config.model
    get_video_provider(provider_config)
    first_frame_url = await _resolve_first_frame_url(first_frame_url, request, user)
    request_options = dict(options or {})
    _validate_video_options(provider_config, request_options)
    try:
        duration = int(request_options.get('duration') or provider_config.duration)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail='视频时长必须是有效秒数') from exc
    if duration < 4 or duration > 15:
        raise HTTPException(status_code=400, detail='视频时长必须在 4 到 15 秒之间')
    request_options['duration'] = duration
    try:
        rate = parse_media_rate(config.get('billing.media.video_chatpoints_per_second'))
        daily_cap = parse_media_rate(config.get('billing.media.video_daily_max_chatpoints'))
        estimated_cost_micros = media_cost_micros(duration, rate)
        if user.role != 'admin' and rate > 0 and config.get('billing.media.video_require_confirmation', True) and not confirm_cost:
            raise HTTPException(
                status_code=409,
                detail={
                    'code': 'VIDEO_COST_CONFIRMATION_REQUIRED',
                    'message': '请先确认视频生成费用后再提交。',
                    'duration_seconds': duration,
                    'rate_chatpoints_per_second': str(rate),
                    'estimated_chatpoints': str(media_cost_chatpoints(duration, rate)),
                    'estimated_cost_micros': estimated_cost_micros,
                    'confirm_cost': True,
                },
            )
        billing = await reserve_media_generation(
            user,
            media_type='video',
            units=duration,
            rate_chatpoints=rate,
            model_id=provider_config.model or f'video:{provider_config.provider}',
            chat_id=chat_id,
            message_id=message_id,
            metadata={'prompt_length': len(prompt), 'input_mode': 'image' if first_frame_url else 'text'},
            daily_cap_chatpoints=daily_cap if daily_cap > 0 else None,
            daily_cap_since=utc_day_start(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        job = await VideoGenerationJobs.create(
            user_id=user.id,
            chat_id=chat_id,
            message_id=message_id,
            provider=provider_config.provider,
            model=provider_config.model,
            prompt=prompt,
            input_mode='image' if first_frame_url else 'text',
            request_payload={
                'first_frame_url': first_frame_url,
                'options': request_options,
                'billing': {
                    'cost_confirmed': bool(confirm_cost or user.role == 'admin' or rate == 0),
                    'estimated_cost_micros': estimated_cost_micros,
                    'unit_price_micros': billing.rate_micros,
                },
            },
            billing_reservation_id=billing.reservation_id,
            billing_unit_count=duration,
            billing_unit_price_micros=billing.rate_micros,
            billing_status='reserved' if billing.reservation_id else 'none',
        )
    except BaseException as exc:
        await release_media_generation(billing, reason=f'视频任务入队失败：{exc}')
        raise
    return job


async def wait_for_video_job(
    job_id: str,
    user_id: str,
    *,
    timeout: int = VIDEO_GENERATION_CHAT_WAIT_TIMEOUT,
):
    """Wait for a queued job to reach a terminal state for chat tool calls."""
    deadline = time.monotonic() + max(1, int(timeout))
    while time.monotonic() < deadline:
        job = await VideoGenerationJobs.get_for_user(job_id, user_id)
        if job is None:
            raise RuntimeError('Video generation job was not found')
        if job.status in TERMINAL_STATUSES:
            return job
        await asyncio.sleep(1)
    raise TimeoutError('Video generation timed out while waiting for the provider')
