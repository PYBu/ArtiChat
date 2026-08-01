from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from open_webui.utils import arena


def request_with_models(models):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(MODELS=models)))


@pytest.mark.asyncio
async def test_arena_filters_nested_missing_and_inaccessible_models(monkeypatch):
    models = {
        'arena': {
            'id': 'arena',
            'owned_by': 'arena',
            'info': {'meta': {'model_ids': ['nested', 'missing', 'blocked', 'allowed']}},
        },
        'nested': {'id': 'nested', 'owned_by': 'arena'},
        'blocked': {'id': 'blocked', 'owned_by': 'openai'},
        'allowed': {'id': 'allowed', 'owned_by': 'openai'},
    }

    async def check_access(_user, model):
        if model['id'] == 'blocked':
            raise PermissionError('blocked')

    monkeypatch.setattr(arena, '_check_model_access', check_access)
    form_data = {'model': 'arena'}
    metadata = {}

    resolved, selected_id = await arena.resolve_arena_model(
        request_with_models(models),
        form_data,
        SimpleNamespace(role='user'),
        metadata,
        models['arena'],
    )

    assert resolved is models['allowed']
    assert selected_id == 'allowed'
    assert form_data['model'] == 'allowed'
    assert metadata['selected_model_id'] == 'allowed'


@pytest.mark.asyncio
async def test_arena_rejects_when_no_accessible_child_exists():
    models = {
        'arena': {'id': 'arena', 'owned_by': 'arena', 'info': {'meta': {'model_ids': ['nested']}}},
        'nested': {'id': 'nested', 'owned_by': 'arena'},
    }

    with pytest.raises(HTTPException) as exc:
        await arena.resolve_arena_model(
            request_with_models(models),
            {'model': 'arena'},
            SimpleNamespace(role='user'),
            {},
            models['arena'],
        )

    assert exc.value.status_code == 403
