from __future__ import annotations

import time

from open_webui.models.config import Config
from open_webui.utils.email_security import claim_sensitive_action_grant
from open_webui.utils.session_security import current_session_id
from sqlalchemy.ext.asyncio import AsyncSession


async def authorize_sensitive_action(
    request,
    user,
    *,
    action: str,
    verification_token: str | None,
    expected_email: str | None = None,
    db: AsyncSession | None = None,
) -> None:
    if not await Config.get('registration.sensitive_action_verification_enabled', False):
        return
    if not verification_token:
        raise ValueError('SENSITIVE_ACTION_VERIFICATION_REQUIRED')
    await claim_sensitive_action_grant(
        verification_token,
        action=action,
        user_id=user.id,
        session_id=current_session_id(request),
        expected_email=expected_email,
        now=int(time.time()),
        db=db,
    )
