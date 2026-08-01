from types import SimpleNamespace

import pytest
from open_webui.utils.reasoning import (
    ReasoningControlError,
    apply_reasoning_metadata_to_payload,
    move_reasoning_effort_to_anthropic,
    move_reasoning_effort_to_responses,
    resolve_reasoning_selection,
)


def model_info(*, enabled=True, profile='gpt'):
    return SimpleNamespace(meta=SimpleNamespace(reasoning_control=SimpleNamespace(enabled=enabled, profile=profile)))


@pytest.mark.parametrize(
    ('profile', 'level', 'effort'),
    [
        ('gpt', 'low', 'low'),
        ('gpt', 'medium', 'medium'),
        ('gpt', 'high', 'high'),
        ('gpt', 'extra', 'xhigh'),
        ('gpt', 'max', 'max'),
        ('claude', 'low', 'low'),
        ('claude', 'medium', 'medium'),
        ('claude', 'high', 'high'),
        ('claude', 'extra', 'xhigh'),
        ('claude', 'max', 'max'),
    ],
)
def test_resolves_five_levels_for_gpt_codex_and_claude(profile, level, effort):
    selection = resolve_reasoning_selection(model_info(profile=profile), level)

    assert selection.level == level
    assert selection.profile == profile
    assert selection.effort == effort


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


def test_maps_canonical_effort_to_responses_and_anthropic_shapes():
    responses = move_reasoning_effort_to_responses(
        {'reasoning_effort': 'max', 'reasoning': {'summary': 'auto'}}
    )
    anthropic = move_reasoning_effort_to_anthropic(
        {'reasoning_effort': 'xhigh', 'output_config': {'format': {'type': 'json_object'}}}
    )

    assert responses == {'reasoning': {'summary': 'auto', 'effort': 'max'}}
    assert anthropic == {
        'output_config': {'format': {'type': 'json_object'}, 'effort': 'xhigh'}
    }


def test_validated_message_snapshot_overrides_legacy_model_effort():
    payload = apply_reasoning_metadata_to_payload(
        {'reasoning_effort': 'low'},
        {'reasoning_level': 'max', 'reasoning_profile': 'gpt'},
    )
    assert payload['reasoning_effort'] == 'max'


def test_invalid_or_incomplete_metadata_does_not_change_payload():
    assert apply_reasoning_metadata_to_payload({'reasoning_effort': 'high'}, None) == {
        'reasoning_effort': 'high'
    }
    assert apply_reasoning_metadata_to_payload({}, {'reasoning_level': 'ultra'}) == {}
    assert apply_reasoning_metadata_to_payload({}, {'reasoning_level': 'max'}) == {}
