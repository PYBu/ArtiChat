from types import SimpleNamespace

from open_webui.models.assets import normalize_asset_category, normalize_asset_source
from open_webui.utils.memory import is_sensitive_memory_content, sanitize_memory_operations


def test_asset_category_uses_mime_and_filename_fallbacks():
    assert normalize_asset_category('image/png', 'document.bin') == 'image'
    assert normalize_asset_category(None, 'movie.mp4') == 'video'
    assert normalize_asset_category('application/pdf', 'report.pdf') == 'other'


def test_asset_source_defaults_to_uploaded():
    assert normalize_asset_source('generated') == 'generated'
    assert normalize_asset_source('unknown') == 'uploaded'


def test_automatic_memory_filters_secrets_duplicate_and_unknown_ids():
    existing = [SimpleNamespace(id='memory-1', type='user', path='profile', content='I prefer concise answers')]
    operations = sanitize_memory_operations(
        [
            {'action': 'add', 'type': 'user', 'path': 'profile', 'content': ' I   prefer concise answers '},
            {'action': 'add', 'type': 'user', 'content': 'api_key: sk-test-value-123456789'},
            {'action': 'remove', 'id': 'not-a-real-memory'},
            {'action': 'move', 'id': 'memory-1', 'path': 'preferences'},
        ],
        existing,
    )

    assert operations == [{'action': 'move', 'id': 'memory-1', 'path': 'preferences'}]
    assert is_sensitive_memory_content('password = do-not-store')
    assert is_sensitive_memory_content('Bearer abcdefghijklmnop')
    assert not is_sensitive_memory_content('I prefer concise answers')


def test_automatic_memory_bounds_content_and_operations():
    operations = sanitize_memory_operations(
        [
            {'action': 'add', 'content': 'one'},
            {'action': 'add', 'content': 'two'},
            {'action': 'add', 'content': 'three'},
            {'action': 'add', 'content': 'four'},
            {'action': 'add', 'content': 'five'},
            {'action': 'add', 'content': 'x' * 601},
        ],
        [],
    )

    assert [operation['content'] for operation in operations] == ['one', 'two', 'three', 'four']
