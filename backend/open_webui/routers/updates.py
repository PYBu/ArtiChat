import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from open_webui.env import (
    ARTICHAT_ANNOUNCEMENT_CACHE_TTL_SECONDS,
    ARTICHAT_ANNOUNCEMENT_TIMEOUT_SECONDS,
    ARTICHAT_ANNOUNCEMENT_URL,
    ARTICHAT_UPDATE_CACHE_TTL_SECONDS,
    ARTICHAT_UPDATE_GITHUB_TOKEN,
    ARTICHAT_UPDATE_REF,
    ARTICHAT_UPDATE_REPOSITORY,
    ARTICHAT_UPDATE_STALE_AFTER_SECONDS,
    ARTICHAT_UPDATE_STATE_PATH,
    ARTICHAT_UPDATE_WORKFLOW,
    VERSION,
    WEBUI_BUILD_HASH,
)
from open_webui.utils.announcement_service import (
    AnnouncementError,
    AnnouncementService,
)
from open_webui.utils.auth import get_admin_user
from open_webui.utils.github_updates import GitHubUpdateClient, GitHubUpdateError
from open_webui.utils.update_service import ArtiChatUpdateService
from open_webui.utils.update_state import UpdateInProgressError, UpdateStateStore


router = APIRouter()
log = logging.getLogger(__name__)
_update_service: ArtiChatUpdateService | None = None
_announcement_service: AnnouncementService | None = None


class DeployUpdateForm(BaseModel):
    target_version: str


def get_update_service() -> ArtiChatUpdateService:
    global _update_service
    if _update_service is None:
        github = (
            GitHubUpdateClient(
                ARTICHAT_UPDATE_REPOSITORY,
                token=ARTICHAT_UPDATE_GITHUB_TOKEN,
            )
            if ARTICHAT_UPDATE_REPOSITORY
            else None
        )
        _update_service = ArtiChatUpdateService(
            current_version=VERSION,
            display_version=f"{VERSION} (Artivis Alpha)",
            build_hash=WEBUI_BUILD_HASH,
            state_store=UpdateStateStore(
                ARTICHAT_UPDATE_STATE_PATH,
                stale_after_seconds=ARTICHAT_UPDATE_STALE_AFTER_SECONDS,
            ),
            github=github,
            workflow=ARTICHAT_UPDATE_WORKFLOW,
            ref=ARTICHAT_UPDATE_REF,
            cache_ttl_seconds=ARTICHAT_UPDATE_CACHE_TTL_SECONDS,
        )
    return _update_service


def get_announcement_service() -> AnnouncementService:
    global _announcement_service
    if _announcement_service is None:
        _announcement_service = AnnouncementService(
            ARTICHAT_ANNOUNCEMENT_URL,
            cache_ttl_seconds=ARTICHAT_ANNOUNCEMENT_CACHE_TTL_SECONDS,
            timeout_seconds=ARTICHAT_ANNOUNCEMENT_TIMEOUT_SECONDS,
        )
    return _announcement_service


@router.get("/check")
async def check_for_updates(
    force: bool = False,
    user=Depends(get_admin_user),
    service=Depends(get_update_service),
):
    try:
        return await service.check(force=force)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/status")
async def get_update_status(
    user=Depends(get_admin_user),
    service=Depends(get_update_service),
):
    return service.status()


@router.get('/announcement')
async def get_update_announcement(
    user=Depends(get_admin_user),
    service=Depends(get_announcement_service),
):
    try:
        announcement = await service.get()
    except AnnouncementError as exc:
        log.warning('Unable to load the update announcement: %s', exc)
        announcement = None
    return {'announcement': announcement}


@router.post("/deploy", status_code=202)
async def deploy_update(
    form_data: DeployUpdateForm,
    user=Depends(get_admin_user),
    service=Depends(get_update_service),
):
    try:
        return await service.deploy(form_data.target_version)
    except UpdateInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubUpdateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
