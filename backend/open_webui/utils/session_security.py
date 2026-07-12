from __future__ import annotations

import hmac
import time
from uuid import uuid4

from open_webui.env import REDIS_KEY_PREFIX
from open_webui.models.oauth_sessions import OAuthSessions
from open_webui.models.users import Users
from sqlalchemy.ext.asyncio import AsyncSession


def new_auth_epoch() -> str:
    return uuid4().hex


def token_auth_epoch_matches(decoded: dict, user) -> bool:
    current_epoch = getattr(user, 'auth_epoch', None)
    if not current_epoch:
        return True
    token_epoch = str(decoded.get('auth_epoch') or '')
    return hmac.compare_digest(token_epoch, str(current_epoch))


async def revoke_user_sessions(
    request,
    user_id: str,
    *,
    db: AsyncSession | None = None,
) -> str:
    auth_epoch = new_auth_epoch()
    updated = await Users.update_user_by_id(user_id, {'auth_epoch': auth_epoch}, db=db)
    if updated is None:
        raise ValueError('USER_SESSION_REVOCATION_FAILED')

    await OAuthSessions.delete_sessions_by_user_id(user_id, db=db)
    app = request.scope.get('app') if request is not None else None
    redis = getattr(getattr(app, 'state', None), 'redis', None)
    if redis is not None:
        await redis.set(
            f'{REDIS_KEY_PREFIX}:auth:user:{user_id}:revoked_at',
            str(int(time.time())),
        )

    from open_webui.socket.main import disconnect_user_sessions

    await disconnect_user_sessions(user_id)
    return auth_epoch
