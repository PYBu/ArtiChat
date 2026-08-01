from open_webui.utils.anthropic import (
    get_provider_profile,
    is_anthropic_connection,
    is_anthropic_messages_passthrough,
)


def test_explicit_anthropic_profile_supports_custom_gateways():
    url = 'https://models.example/v1'

    assert get_provider_profile(url, {'provider': 'anthropic'}) == 'anthropic'
    assert is_anthropic_connection(url, {'provider': 'anthropic'}) is True


def test_explicit_non_anthropic_profile_beats_hostname_inference():
    url = 'https://api.anthropic.com/v1'

    assert get_provider_profile(url, {'provider': 'openai-compatible'}) == 'openai-compatible'
    assert is_anthropic_connection(url, {'provider': 'openai-compatible'}) is False


def test_legacy_anthropic_url_remains_a_compatibility_fallback():
    assert is_anthropic_connection('https://api.anthropic.com/v1', {}) is True
    assert get_provider_profile('https://gateway.example/v1', {}) == 'openai-compatible'


def test_litellm_messages_passthrough_is_preserved_without_claiming_anthropic_profile():
    config = {'provider': 'litellm'}

    assert is_anthropic_connection('https://litellm.example/v1', config) is False
    assert is_anthropic_messages_passthrough('https://litellm.example/v1', config) is True
