from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from open_webui.internal.db import get_async_session
from open_webui.models.announcements import Announcements
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
bearer_security = HTTPBearer(auto_error=False)


async def get_announcement_current_user(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    auth_token: HTTPAuthorizationCredentials = Depends(bearer_security),
):
    from open_webui.utils.auth import get_current_user

    return await get_current_user(request, response, background_tasks, auth_token)


def get_verified_announcement_user(user=Depends(get_announcement_current_user)):
    if user.role not in {'user', 'admin'}:
        raise HTTPException(status_code=401, detail='ACCESS_PROHIBITED')
    return user


def get_admin_announcement_user(user=Depends(get_announcement_current_user)):
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='ACCESS_PROHIBITED')
    return user


class AnnouncementForm(BaseModel):
    title: str
    summary: str | None = None
    body: str
    image_url: str | None = '/assets/images/space.jpg'
    view_button_label: str = '查看公告'
    close_button_label: str | None = None
    display_mode: str = 'once'
    button_label: str = '知道了'
    icon: str | None = None
    is_active: bool = True
    starts_at: int | None = None
    ends_at: int | None = None
    sort_order: int = 0


class AnnouncementUpdateForm(BaseModel):
    title: str | None = None
    summary: str | None = None
    body: str | None = None
    image_url: str | None = None
    view_button_label: str | None = None
    close_button_label: str | None = None
    display_mode: str | None = None
    button_label: str | None = None
    icon: str | None = None
    is_active: bool | None = None
    starts_at: int | None = None
    ends_at: int | None = None
    sort_order: int | None = None


@router.get('/active')
async def get_active_announcements(
    user=Depends(get_verified_announcement_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {
        'items': await Announcements.get_active_for_user(
            user_id=user.id,
            user_created_at=user.created_at,
            db=db,
        )
    }


@router.post('/{announcement_id}/viewed')
async def mark_announcement_viewed(
    announcement_id: str,
    user=Depends(get_verified_announcement_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await Announcements.mark_viewed(announcement_id, user_id=user.id, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/admin')
async def get_admin_announcements(
    limit: int = 100,
    offset: int = 0,
    include_inactive: bool = False,
    user=Depends(get_admin_announcement_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {
        'items': await Announcements.list_all(
            limit=limit,
            offset=offset,
            include_inactive=include_inactive,
            db=db,
        )
    }


@router.post('/admin')
async def create_admin_announcement(
    form_data: AnnouncementForm,
    user=Depends(get_admin_announcement_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await Announcements.create(
            title=form_data.title,
            summary=form_data.summary,
            body=form_data.body,
            image_url=form_data.image_url,
            view_button_label=form_data.view_button_label,
            close_button_label=form_data.close_button_label,
            display_mode=form_data.display_mode,
            button_label=form_data.button_label,
            icon=form_data.icon,
            is_active=form_data.is_active,
            starts_at=form_data.starts_at,
            ends_at=form_data.ends_at,
            sort_order=form_data.sort_order,
            created_by=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch('/admin/{announcement_id}')
async def update_admin_announcement(
    announcement_id: str,
    form_data: AnnouncementUpdateForm,
    user=Depends(get_admin_announcement_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        changed = form_data.model_fields_set
        return await Announcements.update(
            announcement_id,
            title=form_data.title,
            summary=form_data.summary,
            body=form_data.body,
            image_url=form_data.image_url,
            view_button_label=form_data.view_button_label,
            close_button_label=form_data.close_button_label,
            display_mode=form_data.display_mode,
            button_label=form_data.button_label,
            icon=form_data.icon,
            is_active=form_data.is_active,
            starts_at=form_data.starts_at if 'starts_at' in changed else None,
            ends_at=form_data.ends_at if 'ends_at' in changed else None,
            sort_order=form_data.sort_order,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete('/admin/{announcement_id}')
async def delete_admin_announcement(
    announcement_id: str,
    user=Depends(get_admin_announcement_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await Announcements.delete(announcement_id, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
