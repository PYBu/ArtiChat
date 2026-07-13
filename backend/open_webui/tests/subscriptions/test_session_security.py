from types import SimpleNamespace

import jwt
import pytest
from starlette.requests import Request

from open_webui.env import WEBUI_SECRET_KEY
from open_webui.models.users import User
from open_webui.utils.session_security import current_session_id, new_auth_epoch, token_auth_epoch_matches


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


def test_sensitive_session_id_comes_from_the_authenticated_jwt():
    token = jwt.encode({'id': 'user-1', 'jti': 'session-1'}, WEBUI_SECRET_KEY, algorithm='HS256')
    request = Request({'type': 'http', 'headers': [(b'authorization', f'Bearer {token}'.encode())]})
    assert current_session_id(request) == 'session-1'

    api_key_request = Request({'type': 'http', 'headers': [(b'authorization', b'Bearer sk-test')]})
    with pytest.raises(ValueError, match='SENSITIVE_ACTION_SESSION_REQUIRED'):
        current_session_id(api_key_request)
