from __future__ import annotations

import hmac
import time
from uuid import uuid4

import jwt
from open_webui.env import REDIS_KEY_PREFIX, WEBUI_SECRET_KEY
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


def current_session_id(request) -> str:
    authorization = request.headers.get('Authorization', '')
    token = authorization[7:] if authorization.lower().startswith('bearer ') else request.cookies.get('token')
    if not token or token.startswith('sk-'):
        raise ValueError('SENSITIVE_ACTION_SESSION_REQUIRED')
    try:
        decoded = jwt.decode(token, WEBUI_SECRET_KEY, algorithms=['HS256'])
    except Exception as exc:
        raise ValueError('SENSITIVE_ACTION_SESSION_REQUIRED') from exc
    session_id = str(decoded.get('jti') or '')
    if not session_id:
        raise ValueError('SENSITIVE_ACTION_SESSION_REQUIRED')
    return session_id


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
