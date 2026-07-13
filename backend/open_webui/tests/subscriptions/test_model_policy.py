import pytest

from open_webui.models.models import Model, Models
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
    assert policy.input_chatpoint_per_million == '100'
    assert policy.output_chatpoint_per_million == '100'
    assert policy.cache_creation_chatpoint_per_million == '0'
    assert policy.cache_read_chatpoint_per_million == '0'


def test_legacy_multiplier_normalizes_to_equivalent_four_part_prices():
    policy = ModelSubscriptionPolicy.model_validate(
        {
            'allowed_tiers': ['free'],
            'quota_mode': 'metered',
            'usage_multiplier': '2.5',
        }
    )

    assert policy.input_chatpoint_per_million == '250'
    assert policy.output_chatpoint_per_million == '250'
    assert policy.cache_creation_chatpoint_per_million == '0'
    assert policy.cache_read_chatpoint_per_million == '0'


def test_explicit_four_part_prices_are_preserved_as_canonical_strings():
    policy = ModelSubscriptionPolicy.model_validate(
        {
            'allowed_tiers': ['plus'],
            'quota_mode': 'metered',
            'usage_multiplier': '9',
            'input_chatpoint_per_million': '1.2500',
            'output_chatpoint_per_million': 3,
            'cache_creation_chatpoint_per_million': '0.50',
            'cache_read_chatpoint_per_million': '0.125',
        }
    )

    assert policy.input_chatpoint_per_million == '1.25'
    assert policy.output_chatpoint_per_million == '3'
    assert policy.cache_creation_chatpoint_per_million == '0.5'
    assert policy.cache_read_chatpoint_per_million == '0.125'


@pytest.mark.parametrize(
    'field,value',
    [
        ('input_chatpoint_per_million', '-1'),
        ('output_chatpoint_per_million', 'invalid'),
        ('cache_creation_chatpoint_per_million', '-0.1'),
        ('cache_read_chatpoint_per_million', 'nan'),
    ],
)
def test_invalid_four_part_prices_are_rejected(field, value):
    with pytest.raises(ValueError, match='MODEL_SUBSCRIPTION_POLICY_INVALID'):
        ModelSubscriptionPolicy.model_validate(
            {
                'allowed_tiers': ['free'],
                'quota_mode': 'metered',
                field: value,
            }
        )


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


@pytest.mark.asyncio
async def test_bulk_model_policy_update_preserves_other_meta(db_session):
    db_session.add_all(
        [
            Model(
                id='model-a',
                user_id='admin',
                base_model_id='provider-a',
                name='Model A',
                params={},
                meta={'description': 'keep-a'},
                is_active=True,
                created_at=1_720_000_000,
                updated_at=1_720_000_000,
            ),
            Model(
                id='model-b',
                user_id='admin',
                base_model_id='provider-b',
                name='Model B',
                params={},
                meta={'description': 'keep-b'},
                is_active=True,
                created_at=1_720_000_000,
                updated_at=1_720_000_000,
            ),
        ]
    )
    await db_session.commit()

    updated = await Models.update_model_subscription_policies(
        {
            'model-a': {'allowed_tiers': ['free'], 'quota_mode': 'metered', 'usage_multiplier': '1'},
            'model-b': {'allowed_tiers': ['plus'], 'quota_mode': 'unlimited', 'usage_multiplier': '0'},
        },
        db=db_session,
    )

    by_id = {model.id: model for model in updated}
    assert by_id['model-a'].meta.description == 'keep-a'
    assert by_id['model-a'].meta.subscription['allowed_tiers'] == ['free']
    assert by_id['model-b'].meta.description == 'keep-b'
    assert by_id['model-b'].meta.subscription['quota_mode'] == 'unlimited'


@pytest.mark.asyncio
async def test_bulk_model_policy_update_rejects_missing_model_without_partial_write(db_session):
    db_session.add(
        Model(
            id='model-a',
            user_id='admin',
            base_model_id='provider-a',
            name='Model A',
            params={},
            meta={'subscription': {'allowed_tiers': ['free'], 'quota_mode': 'metered', 'usage_multiplier': '1'}},
            is_active=True,
            created_at=1_720_000_000,
            updated_at=1_720_000_000,
        )
    )
    await db_session.commit()

    with pytest.raises(ValueError, match='MODEL_NOT_FOUND: missing-model'):
        await Models.update_model_subscription_policies(
            {
                'model-a': {'allowed_tiers': ['plus'], 'quota_mode': 'metered', 'usage_multiplier': '2'},
                'missing-model': {'allowed_tiers': ['free'], 'quota_mode': 'metered', 'usage_multiplier': '1'},
            },
            db=db_session,
        )

    unchanged = await db_session.get(Model, 'model-a')
    assert unchanged.meta['subscription']['allowed_tiers'] == ['free']
