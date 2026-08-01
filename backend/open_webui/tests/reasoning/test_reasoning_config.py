import pytest
from open_webui.models.models import ModelMeta
from pydantic import ValidationError


def test_reasoning_control_accepts_supported_profiles():
    gpt = ModelMeta(reasoning_control={'enabled': True, 'profile': 'gpt'})
    claude = ModelMeta(reasoning_control={'enabled': True, 'profile': 'claude'})

    assert gpt.reasoning_control.profile == 'gpt'
    assert claude.reasoning_control.profile == 'claude'


def test_reasoning_control_requires_profile_only_when_enabled():
    disabled = ModelMeta(reasoning_control={'enabled': False, 'profile': None})
    assert disabled.reasoning_control.profile is None

    with pytest.raises(ValidationError, match='reasoning profile is required'):
        ModelMeta(reasoning_control={'enabled': True, 'profile': None})


def test_reasoning_control_rejects_unknown_profile():
    with pytest.raises(ValidationError):
        ModelMeta(reasoning_control={'enabled': True, 'profile': 'custom'})
