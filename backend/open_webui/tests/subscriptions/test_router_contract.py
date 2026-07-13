from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from open_webui.routers import subscriptions


def test_router_exposes_user_and_admin_paths():
    paths = {route.path for route in subscriptions.router.routes}

    assert '/me' in paths
    assert '/usage' in paths
    assert '/plans' in paths
    assert '/redeem' in paths
    assert '/gift-cards/pending' in paths
    assert '/gift-cards/{grant_id}/claim' in paths
    assert '/records' in paths
    assert '/billing-address' in paths
    assert '/admin/plans' in paths
    assert '/admin/models' in paths
    assert '/admin/models/bulk' in paths
    assert '/admin/codes' in paths
    assert '/admin/codes/{code_id}' in paths
    assert '/admin/gift-cards' in paths
    assert '/admin/gift-cards/{grant_id}' in paths
    assert '/admin/users' in paths
    assert '/admin/users/{user_id}' in paths
    assert '/admin/usage' in paths
    assert '/admin/ledger' in paths


def test_admin_model_policy_projection_is_consistent_after_updates():
    model = SimpleNamespace(
        id='model-1',
        name='Model One',
        base_model_id='provider-model',
        meta=SimpleNamespace(subscription={'allowed_tiers': ['free']}),
    )

    assert subscriptions._admin_model_policy_response(model) == {
        'id': 'model-1',
        'name': 'Model One',
        'base_model_id': 'provider-model',
        'subscription': {'allowed_tiers': ['free']},
    }


def test_admin_code_batch_size_is_bounded():
    with pytest.raises(ValidationError):
        subscriptions.AdminCodeCreateForm(mode='single_use', quantity=501)
