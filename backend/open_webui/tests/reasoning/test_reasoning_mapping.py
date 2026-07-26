from types import SimpleNamespace

import pytest
from open_webui.utils.reasoning import (
    ReasoningControlError,
    apply_reasoning_metadata_to_payload,
    move_reasoning_effort_to_responses,
    resolve_reasoning_selection,
)


def model_info(*, enabled=True, profile='gpt'):
    return SimpleNamespace(meta=SimpleNamespace(reasoning_control=SimpleNamespace(enabled=enabled, profile=profile)))


@pytest.mark.parametrize(
    ('level', 'effort'),
    [
        ('low', 'low'),
        ('medium', 'medium'),
        ('high', 'high'),
        ('extra', 'xhigh'),
        ('max', 'max'),
    ],
)
def test_resolves_five_internal_levels(level, effort):
    selection = resolve_reasoning_selection(model_info(), level)
    assert selection.level == level
    assert selection.profile == 'gpt'
    assert selection.effort == effort


def test_accepts_claude_profile_with_same_responses_literals():
    selection = resolve_reasoning_selection(model_info(profile='claude'), 'extra')
    assert selection.profile == 'claude'
    assert selection.effort == 'xhigh'


@pytest.mark.parametrize('level', ['ultra', '', 4, {'level': 'high'}])
def test_rejects_unknown_or_malformed_levels(level):
    with pytest.raises(ReasoningControlError, match='Invalid reasoning level'):
        resolve_reasoning_selection(model_info(), level)


def test_rejects_models_without_enabled_control():
    with pytest.raises(ReasoningControlError, match='not enabled'):
        resolve_reasoning_selection(model_info(enabled=False), 'high')
    with pytest.raises(ReasoningControlError, match='not enabled'):
        resolve_reasoning_selection(None, 'high')


def test_omitted_level_preserves_legacy_behavior():
    assert resolve_reasoning_selection(None, None) is None


def test_moves_chat_completions_effort_into_responses_shape():
    payload = move_reasoning_effort_to_responses(
        {
            'model': 'gpt-5.6',
            'reasoning_effort': 'max',
            'reasoning': {'summary': 'auto'},
        }
    )

    assert 'reasoning_effort' not in payload
    assert payload['reasoning'] == {'summary': 'auto', 'effort': 'max'}


def test_existing_responses_effort_is_unchanged_without_legacy_field():
    payload = {'reasoning': {'effort': 'high'}}
    assert move_reasoning_effort_to_responses(payload) == {'reasoning': {'effort': 'high'}}


def test_validated_message_level_overrides_legacy_model_effort():
    payload = apply_reasoning_metadata_to_payload(
        {'reasoning_effort': 'low'},
        {'reasoning_level': 'max'},
    )
    assert payload['reasoning_effort'] == 'max'


def test_invalid_or_absent_metadata_does_not_change_payload():
    assert apply_reasoning_metadata_to_payload({'reasoning_effort': 'high'}, None) == {'reasoning_effort': 'high'}
    assert apply_reasoning_metadata_to_payload({}, {'reasoning_level': 'ultra'}) == {}
