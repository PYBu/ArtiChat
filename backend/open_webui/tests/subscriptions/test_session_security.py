import ast
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from starlette.requests import Request

from open_webui.env import WEBUI_SECRET_KEY
from open_webui.models.users import User
from open_webui.utils.session_security import (
    current_session_id,
    new_auth_epoch,
    token_auth_epoch_matches,
    user_token_claims,
)


def _async_function_calls(path: Path, name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )
    return {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_user_table_tracks_auth_epoch():
    assert 'auth_epoch' in User.__table__.columns


def test_auth_epoch_keeps_legacy_users_compatible_and_rejects_old_tokens():
    assert token_auth_epoch_matches({'id': 'user-1'}, SimpleNamespace(auth_epoch=None))
    assert token_auth_epoch_matches(
        {'id': 'user-1', 'auth_epoch': 'epoch-current'},
        SimpleNamespace(auth_epoch='epoch-current'),
    )
    assert not token_auth_epoch_matches(
        {'id': 'user-1', 'auth_epoch': 'epoch-old'},
        SimpleNamespace(auth_epoch='epoch-current'),
    )
    assert new_auth_epoch() != new_auth_epoch()


def test_user_token_claims_bind_auth_epoch_and_preserve_token_type():
    user = SimpleNamespace(id='user-1', auth_epoch='epoch-current')

    claims = user_token_claims(user, typ='automation')

    assert claims == {
        'id': 'user-1',
        'auth_epoch': 'epoch-current',
        'typ': 'automation',
    }


def test_sensitive_session_id_comes_from_the_authenticated_jwt():
    token = jwt.encode({'id': 'user-1', 'jti': 'session-1'}, WEBUI_SECRET_KEY, algorithm='HS256')
    request = Request({'type': 'http', 'headers': [(b'authorization', f'Bearer {token}'.encode())]})
    assert current_session_id(request) == 'session-1'

    api_key_request = Request({'type': 'http', 'headers': [(b'authorization', b'Bearer sk-test')]})
    with pytest.raises(ValueError, match='SENSITIVE_ACTION_SESSION_REQUIRED'):
        current_session_id(api_key_request)


def test_every_password_change_route_revokes_existing_sessions():
    backend = Path(__file__).resolve().parents[2]

    assert 'revoke_user_sessions' in _async_function_calls(backend / 'routers' / 'auths.py', 'update_password')
    assert 'revoke_user_sessions' in _async_function_calls(backend / 'routers' / 'users.py', 'update_user_by_id')
    assert 'revoke_user_sessions' in _async_function_calls(backend / 'routers' / 'emails.py', 'reset_password')
