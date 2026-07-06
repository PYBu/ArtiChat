import pytest

from open_webui.utils.subscriptions import (
    ModelSubscriptionPolicy,
    assert_model_subscription_access,
    filter_models_for_subscription,
    get_model_subscription_policy,
)


def model(model_id, subscription=None):
    return {'id': model_id, 'info': {'meta': {'subscription': subscription or {}}}}


def test_missing_policy_allows_all_tiers_and_is_metered():
    policy = get_model_subscription_policy(model('gpt-test'))

    assert policy.allowed_tiers == ['free', 'plus', 'chatpower']
    assert policy.quota_mode == 'metered'
    assert policy.usage_multiplier == '1'


def test_filter_removes_models_not_allowed_for_tier():
    models = [
        model('free-model', {'allowed_tiers': ['free', 'plus', 'chatpower'], 'quota_mode': 'unlimited'}),
        model('plus-model', {'allowed_tiers': ['plus', 'chatpower'], 'quota_mode': 'metered'}),
    ]

    filtered = filter_models_for_subscription(models, tier='free', is_admin=False)

    assert [item['id'] for item in filtered] == ['free-model']


def test_admin_sees_all_models():
    models = [
        model('free-model', {'allowed_tiers': ['free'], 'quota_mode': 'unlimited'}),
        model('power-model', {'allowed_tiers': ['chatpower'], 'quota_mode': 'metered'}),
    ]

    filtered = filter_models_for_subscription(models, tier='free', is_admin=True)

    assert [item['id'] for item in filtered] == ['free-model', 'power-model']


def test_disallowed_tier_raises_stable_error():
    with pytest.raises(PermissionError, match='SUBSCRIPTION_TIER_REQUIRED'):
        assert_model_subscription_access(
            model('plus-model', {'allowed_tiers': ['plus'], 'quota_mode': 'metered'}),
            tier='free',
            is_admin=False,
        )


def test_negative_multiplier_is_invalid():
    with pytest.raises(ValueError, match='MODEL_SUBSCRIPTION_POLICY_INVALID'):
        ModelSubscriptionPolicy.model_validate(
            {'allowed_tiers': ['free'], 'quota_mode': 'metered', 'usage_multiplier': '-1'}
        )
