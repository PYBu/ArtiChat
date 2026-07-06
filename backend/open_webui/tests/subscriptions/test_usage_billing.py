import pytest

from open_webui.models.subscriptions import SubscriptionPlans, UserSubscriptions, chatpoint_to_micros
from open_webui.utils.subscriptions import (
    assert_chatpoint_available,
    bill_model_usage,
    ensure_subscription_current,
)


@pytest.mark.asyncio
async def test_metered_usage_debits_plan_before_check(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await ensure_subscription_current('user-1', now=1_720_000_000, db=db_session)
    await UserSubscriptions.adjust_balances(
        'user-1',
        plan_delta_micros=-chatpoint_to_micros(9),
        check_delta_micros=chatpoint_to_micros(2),
        event_type='admin_adjustment',
        created_by='admin',
        db=db_session,
    )

    usage = await bill_model_usage(
        user_id='user-1',
        model_id='metered-model',
        quota_mode='metered',
        usage_multiplier='1',
        usage={'input_tokens': 10_000, 'output_tokens': 10_000, 'total_tokens': 20_000},
        metadata={'chat_id': 'chat-1', 'message_id': 'msg-1'},
        is_admin=False,
        now=1_720_000_010,
        db=db_session,
    )

    assert usage.cost_micros == chatpoint_to_micros(2)
    assert usage.plan_cost_micros == chatpoint_to_micros(1)
    assert usage.check_cost_micros == chatpoint_to_micros(1)
    assert usage.check_balance_after_micros == chatpoint_to_micros(1)


@pytest.mark.asyncio
async def test_request_can_make_balance_negative_then_next_metered_request_is_blocked(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await ensure_subscription_current('user-2', now=1_720_000_000, db=db_session)
    await UserSubscriptions.adjust_balances(
        'user-2',
        plan_delta_micros=-chatpoint_to_micros(9),
        check_delta_micros=0,
        event_type='admin_adjustment',
        created_by='admin',
        db=db_session,
    )

    await bill_model_usage(
        user_id='user-2',
        model_id='metered-model',
        quota_mode='metered',
        usage_multiplier='1',
        usage={'total_tokens': 20_000},
        metadata={},
        is_admin=False,
        now=1_720_000_010,
        db=db_session,
    )

    with pytest.raises(PermissionError, match='CHATPOINT_BALANCE_EXHAUSTED'):
        await assert_chatpoint_available('user-2', quota_mode='metered', is_admin=False, db=db_session)


@pytest.mark.asyncio
async def test_unlimited_usage_records_zero_cost(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    usage = await bill_model_usage(
        user_id='user-3',
        model_id='free-model',
        quota_mode='unlimited',
        usage_multiplier='9',
        usage={'input_tokens': 50_000, 'output_tokens': 50_000, 'total_tokens': 100_000},
        metadata={},
        is_admin=False,
        now=1_720_000_000,
        db=db_session,
    )

    assert usage.status == 'unlimited'
    assert usage.cost_micros == 0


@pytest.mark.asyncio
async def test_admin_usage_records_bypass_without_debit(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    usage = await bill_model_usage(
        user_id='admin-1',
        model_id='power-model',
        quota_mode='metered',
        usage_multiplier='10',
        usage={'total_tokens': 1_000_000},
        metadata={},
        is_admin=True,
        now=1_720_000_000,
        db=db_session,
    )

    assert usage.status == 'admin_bypass'
    assert usage.cost_micros == 0
