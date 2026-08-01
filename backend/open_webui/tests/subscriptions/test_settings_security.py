from open_webui.utils.settings_security import sanitize_user_settings


def test_direct_connection_secrets_are_removed_without_mutating_input():
    original = {
        'ui': {
            'theme': 'dark',
            'directConnections': {
                'OPENAI_API_BASE_URLS': ['https://api.example/v1'],
                'OPENAI_API_KEYS': ['provider-secret'],
            },
        },
        'keybindings': {'save': 'ctrl+s'},
    }

    sanitized = sanitize_user_settings(original)

    assert sanitized == {
        'ui': {'theme': 'dark'},
        'keybindings': {'save': 'ctrl+s'},
    }
    assert original['ui']['directConnections']['OPENAI_API_KEYS'] == ['provider-secret']
