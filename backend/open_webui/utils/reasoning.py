from __future__ import annotations

from dataclasses import dataclass


REASONING_EFFORT_BY_PROFILE = {
    'gpt': {
        'low': 'low',
        'medium': 'medium',
        'high': 'high',
        'extra': 'xhigh',
        'max': 'max',
    },
    'claude': {
        'low': 'low',
        'medium': 'medium',
        'high': 'high',
        'extra': 'xhigh',
        'max': 'max',
    },
}
REASONING_LEVELS = frozenset(REASONING_EFFORT_BY_PROFILE['gpt'])
REASONING_PROFILES = frozenset(REASONING_EFFORT_BY_PROFILE)


class ReasoningControlError(ValueError):
    pass


@dataclass(frozen=True)
class ReasoningSelection:
    level: str
    profile: str
    effort: str


def move_reasoning_effort_to_responses(payload: dict) -> dict:
    reasoning_effort = payload.pop('reasoning_effort', None)
    if reasoning_effort is None:
        return payload

    reasoning = payload.get('reasoning')
    if not isinstance(reasoning, dict):
        reasoning = {}
    payload['reasoning'] = {**reasoning, 'effort': reasoning_effort}
    return payload


def move_reasoning_effort_to_anthropic(payload: dict) -> dict:
    reasoning_effort = payload.pop('reasoning_effort', None)
    if reasoning_effort is None:
        return payload

    output_config = payload.get('output_config')
    if not isinstance(output_config, dict):
        output_config = {}
    payload['output_config'] = {**output_config, 'effort': reasoning_effort}
    return payload


def apply_reasoning_metadata_to_payload(payload: dict, metadata: dict | None) -> dict:
    level = metadata.get('reasoning_level') if isinstance(metadata, dict) else None
    profile = metadata.get('reasoning_profile') if isinstance(metadata, dict) else None
    effort = REASONING_EFFORT_BY_PROFILE.get(profile, {}).get(level)
    if effort is not None:
        payload['reasoning_effort'] = effort
    return payload


def resolve_reasoning_selection(model_info, requested_level) -> ReasoningSelection | None:
    if requested_level is None:
        return None
    if not isinstance(requested_level, str) or requested_level not in REASONING_LEVELS:
        raise ReasoningControlError('Invalid reasoning level.')

    meta = getattr(model_info, 'meta', None) if model_info is not None else None
    control = getattr(meta, 'reasoning_control', None) if meta is not None else None
    if control is None and isinstance(meta, dict):
        control = meta.get('reasoning_control')

    enabled = getattr(control, 'enabled', None)
    profile = getattr(control, 'profile', None)
    if isinstance(control, dict):
        enabled = control.get('enabled')
        profile = control.get('profile')

    if not enabled or profile not in REASONING_PROFILES:
        raise ReasoningControlError('Reasoning control is not enabled for this model.')

    return ReasoningSelection(
        level=requested_level,
        profile=profile,
        effort=REASONING_EFFORT_BY_PROFILE[profile][requested_level],
    )
