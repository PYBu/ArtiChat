"""User-owned asset center and revocable anonymous sharing."""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import secrets
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from open_webui.internal.db import get_async_session
from open_webui.models.assets import (
    ASSET_CATEGORIES,
    ASSET_SOURCES,
    AssetShares,
    normalize_asset_category,
    normalize_asset_source,
)
from open_webui.models.files import Files, FileModel
from open_webui.storage.provider import Storage
from open_webui.utils.auth import get_verified_user
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
public_router = APIRouter()


class AssetShareSummary(BaseModel):
    id: str
    created_at: int
    expires_at: int | None = None


class AssetResponse(BaseModel):
    id: str
    filename: str
    source: str
    category: str
    content_type: str | None = None
    size: int | None = None
    created_at: int | None = None
    updated_at: int | None = None
    preview_url: str
    download_url: str
    active_shares: list['AssetShareSummary'] = Field(default_factory=list)


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int


class AssetShareRequest(BaseModel):
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class AssetShareResponse(BaseModel):
    id: str
    file_id: str
    url: str
    expires_at: int | None = None


def _meta(file: FileModel) -> dict:
    return file.meta if isinstance(file.meta, dict) else {}


def _asset_source(file: FileModel, meta: dict) -> str:
    source = meta.get('asset_source')
    if source in ASSET_SOURCES:
        return source
    data = meta.get('data') if isinstance(meta.get('data'), dict) else {}
    if (
        meta.get('video_generation_job_id')
        or data.get('video_generation_job_id')
        or str(meta.get('name') or file.filename).lower().startswith('generated-')
    ):
        return 'generated'
    return normalize_asset_source(source)


def _asset_response(file: FileModel, active_shares: list[AssetShareSummary] | None = None) -> AssetResponse:
    meta = _meta(file)
    content_type = meta.get('content_type') if isinstance(meta.get('content_type'), str) else None
    filename = str(meta.get('name') or file.filename)
    category = meta.get('asset_category')
    if category not in ASSET_CATEGORIES:
        category = normalize_asset_category(content_type, filename)
    return AssetResponse(
        id=file.id,
        filename=filename,
        source=_asset_source(file, meta),
        category=category,
        content_type=content_type,
        size=meta.get('size') if isinstance(meta.get('size'), int) else None,
        created_at=file.created_at,
        updated_at=file.updated_at,
        preview_url=f'/api/v1/files/{quote(file.id, safe="")}/content',
        download_url=f'/api/v1/files/{quote(file.id, safe="")}/content?attachment=true',
        active_shares=active_shares or [],
    )


def _ensure_owner(file: FileModel | None, user) -> FileModel:
    if not file or file.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Asset not found')
    return file


@router.get('/', response_model=AssetListResponse)
async def list_assets(
    source: str | None = Query(default=None),
    category: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=40, ge=1, le=100),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    if source is not None and source not in ASSET_SOURCES:
        raise HTTPException(status_code=400, detail='Invalid asset source')
    if category is not None and category not in ASSET_CATEGORIES:
        raise HTTPException(status_code=400, detail='Invalid asset category')

    files = await Files.get_files_by_user_id(user.id, db=db)
    normalized_query = (query or '').strip().lower()
    active_shares = await AssetShares.get_active_for_owner_files(user.id, [file.id for file in files], db=db)
    items = []
    for file in files:
        item = _asset_response(
            file,
            [
                AssetShareSummary(
                    id=share.id,
                    created_at=share.created_at,
                    expires_at=share.expires_at,
                )
                for share in active_shares.get(file.id, [])
            ],
        )
        if source and item.source != source:
            continue
        if category and item.category != category:
            continue
        if normalized_query and normalized_query not in item.filename.lower():
            continue
        items.append(item)

    items.sort(key=lambda item: (item.updated_at or item.created_at or 0, item.id), reverse=True)
    total = len(items)
    start = (page - 1) * limit
    return AssetListResponse(items=items[start : start + limit], total=total)


@router.post('/{id}/share', response_model=AssetShareResponse)
async def share_asset(
    id: str,
    form_data: AssetShareRequest,
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    file = _ensure_owner(await Files.get_file_by_id(id, db=db), user)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    expires_at = None
    if form_data.expires_in_days:
        expires_at = int(time.time()) + form_data.expires_in_days * 86400
    share = await AssetShares.create(
        file_id=file.id,
        owner_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        db=db,
    )
    url = str(request.url_for('get_public_asset_share', token=raw_token))
    return AssetShareResponse(id=share.id, file_id=file.id, url=url, expires_at=expires_at)


@router.delete('/share/{share_id}')
async def revoke_asset_share(
    share_id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not await AssetShares.revoke_for_owner(share_id, user.id, db=db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Share not found')
    return {'status': True}


@public_router.get('/{token}', name='get_public_asset_share')
async def get_public_asset_share(
    token: str,
    request: Request,
    download: bool = Query(default=False),
    db: AsyncSession = Depends(get_async_session),
):
    if len(token) < 20 or len(token) > 200:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Share not found')
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    share = await AssetShares.get_active_by_token_hash(token_hash, db=db)
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Share not found')
    file = await Files.get_file_by_id(share.file_id, db=db)
    if not file or file.user_id != share.owner_id or not file.path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Asset not found')

    try:
        file_path = Path(await asyncio.to_thread(Storage.get_file, file.path))
    except Exception as exc:
        raise HTTPException(status_code=404, detail='Asset not found') from exc
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Asset not found')

    await AssetShares.touch(share.id, db=db)
    meta = file.meta if isinstance(file.meta, dict) else {}
    filename = str(meta.get('name') or file.filename)
    content_type = meta.get('content_type') if isinstance(meta.get('content_type'), str) else None
    content_type = content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    inline = not download and (
        content_type.startswith(('image/', 'video/', 'audio/'))
        or content_type in {'application/pdf', 'text/plain', 'text/markdown'}
    )
    disposition = 'inline' if inline else 'attachment'
    encoded_filename = quote(filename)
    return FileResponse(
        file_path,
        media_type=content_type,
        headers={
            'Content-Disposition': f"{disposition}; filename*=UTF-8''{encoded_filename}",
            'Cache-Control': 'private, max-age=0, must-revalidate',
            'X-Content-Type-Options': 'nosniff',
        },
    )
