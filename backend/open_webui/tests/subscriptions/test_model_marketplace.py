from types import SimpleNamespace

import pytest

pytest.importorskip('chromadb')

from open_webui.models.models import ModelMeta
from open_webui.routers import models


@pytest.mark.asyncio
async def test_marketplace_exposes_only_opted_in_presentation_fields(monkeypatch):
    visible = SimpleNamespace(
        id='market-model',
        name='Market Model',
        is_active=True,
        access_grants=[SimpleNamespace(id='grant-1')],
        meta=ModelMeta(
            description='Short description',
            marketplace={'visible': True, 'long_description': 'Long description'},
            subscription={
                'allowed_tiers': ['plus'],
                'quota_mode': 'metered',
                'input_chatpoint_per_million': '10',
                'output_chatpoint_per_million': '20',
                'cache_creation_chatpoint_per_million': '3',
                'cache_read_chatpoint_per_million': '1',
            },
        ),
    )
    hidden = SimpleNamespace(
        id='hidden-model',
        name='Hidden Model',
        is_active=True,
        access_grants=[],
        meta=ModelMeta(marketplace={'visible': False}),
    )

    async def get_all_models(db=None):
        return [visible, hidden]

    async def get_history(model_ids, *, days, db=None):
        assert model_ids == ['market-model']
        assert days == 30
        return {'market-model': [{'date': '2026-07-17', 'count': 8}]}

    monkeypatch.setattr(models.Models, 'get_all_models', get_all_models)
    monkeypatch.setattr(models.SubscriptionUsages, 'get_daily_request_counts', get_history)

    response = await models.get_model_marketplace(user=SimpleNamespace(id='user-1'), db=object())

    assert len(response) == 1
    item = response[0].model_dump()
    assert item == {
        'id': 'market-model',
        'name': 'Market Model',
        'description': 'Short description',
        'long_description': 'Long description',
        'is_active': True,
        'allowed_tiers': ['plus'],
        'quota_mode': 'metered',
        'pricing': {'input': '10', 'output': '20', 'cache_creation': '3', 'cache_read': '1'},
        'restricted_access': True,
        'history': [{'date': '2026-07-17', 'count': 8}],
    }
    assert {'params', 'access_grants', 'user_id'}.isdisjoint(item)
