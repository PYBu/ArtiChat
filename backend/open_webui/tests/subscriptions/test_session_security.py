from types import SimpleNamespace

from open_webui.models.users import User
from open_webui.utils.session_security import new_auth_epoch, token_auth_epoch_matches


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
