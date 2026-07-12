import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from open_webui.models.subscriptions import (
    SubscriptionLedgers,
    SubscriptionPlans,
    SubscriptionUsages,
    UserSubscriptions,
    chatpoint_to_micros,
)
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
        plan_delta_micros=-chatpoint_to_micros(99),
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
        plan_delta_micros=-chatpoint_to_micros(99),
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


@pytest.mark.asyncio
async def test_usage_metadata_filters_runtime_values_before_insert(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    def runtime_callback():
        return None

    class RuntimeObject:
        pass

    usage = await bill_model_usage(
        user_id='user-json',
        model_id='metered-model',
        quota_mode='metered',
        usage_multiplier='1',
        usage={'total_tokens': 10_000},
        metadata={
            'chat_id': 'chat-json',
            'message_id': 'msg-json',
            'callable': runtime_callback,
            'nested': {
                'safe': 'value',
                'callable': runtime_callback,
                'object': RuntimeObject(),
            },
            'items': [1, runtime_callback, {'safe': True, 'object': RuntimeObject()}],
        },
        is_admin=False,
        now=1_720_000_000,
        db=db_session,
    )

    assert usage.status == 'billed'
    assert usage.metadata == {
        'chat_id': 'chat-json',
        'message_id': 'msg-json',
        'nested': {'safe': 'value'},
        'items': [1, {'safe': True}],
    }


@pytest.mark.asyncio
async def test_four_part_prices_charge_cache_tokens_and_snapshot_audit_fields(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await ensure_subscription_current('priced-user', now=1_720_000_000, db=db_session)

    usage = await bill_model_usage(
        user_id='priced-user',
        model_id='priced-model',
        quota_mode='metered',
        usage_multiplier='1',
        pricing={
            'input_chatpoint_per_million': '10',
            'output_chatpoint_per_million': '20',
            'cache_creation_chatpoint_per_million': '4',
            'cache_read_chatpoint_per_million': '1',
        },
        usage={
            'input_tokens': 1_000_000,
            'output_tokens': 500_000,
            'cache_creation_input_tokens': 250_000,
            'cache_read_input_tokens': 100_000,
        },
        metadata={'request_id': 'req-priced', 'client_ip': '10.0.0.4'},
        is_admin=False,
        request_id='req-priced',
        client_ip='10.0.0.4',
        first_token_latency_ms=120,
        total_duration_ms=980,
        now=1_720_000_000,
        db=db_session,
    )

    assert usage.cost_micros == chatpoint_to_micros('21.1')
    assert usage.cache_creation_tokens == 250_000
    assert usage.cache_read_tokens == 100_000
    assert usage.input_chatpoint_per_million == '10'
    assert usage.cache_read_chatpoint_per_million == '1'
    assert usage.request_id == 'req-priced'
    assert usage.client_ip == '10.0.0.4'
    assert usage.first_token_latency_ms == 120
    assert usage.total_duration_ms == 980


@pytest.mark.asyncio
async def test_metered_billing_rolls_back_balance_and_ledger_when_usage_insert_fails(db_session, monkeypatch):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await ensure_subscription_current('rollback-user', now=1_720_000_000, db=db_session)
    before = await UserSubscriptions.get_by_user_id('rollback-user', db=db_session)
    before_ledgers = await SubscriptionLedgers.search(user_id='rollback-user', db=db_session)

    async def fail_insert(*args, **kwargs):
        raise RuntimeError('usage insert failed')

    monkeypatch.setattr(SubscriptionUsages, 'insert', fail_insert)

    with pytest.raises(RuntimeError, match='usage insert failed'):
        await bill_model_usage(
            user_id='rollback-user',
            model_id='rollback-model',
            quota_mode='metered',
            usage_multiplier='1',
            pricing={
                'input_chatpoint_per_million': '100',
                'output_chatpoint_per_million': '100',
                'cache_creation_chatpoint_per_million': '0',
                'cache_read_chatpoint_per_million': '0',
            },
            usage={'input_tokens': 10_000},
            metadata={},
            is_admin=False,
            request_id='req-rollback',
            now=1_720_000_001,
            db=db_session,
        )

    after = await UserSubscriptions.get_by_user_id('rollback-user', db=db_session)
    after_ledgers = await SubscriptionLedgers.search(user_id='rollback-user', db=db_session)
    assert after.plan_balance_micros == before.plan_balance_micros
    assert after.check_balance_micros == before.check_balance_micros
    assert len(after_ledgers) == len(before_ledgers)


@pytest.mark.asyncio
async def test_concurrent_metered_usage_does_not_lose_a_debit(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await ensure_subscription_current('concurrent-billing-user', now=1_720_000_000, db=db_session)
    Session = async_sessionmaker(db_session.bind, expire_on_commit=False)

    async def bill_once(request_id: str):
        async with Session() as session:
            return await bill_model_usage(
                user_id='concurrent-billing-user',
                model_id='metered-model',
                quota_mode='metered',
                usage_multiplier='1',
                pricing={
                    'input_chatpoint_per_million': '100',
                    'output_chatpoint_per_million': '0',
                    'cache_creation_chatpoint_per_million': '0',
                    'cache_read_chatpoint_per_million': '0',
                },
                usage={'input_tokens': 100_000},
                metadata={},
                is_admin=False,
                request_id=request_id,
                now=1_720_000_001,
                db=session,
            )

    await asyncio.gather(bill_once('concurrent-1'), bill_once('concurrent-2'))
    db_session.expire_all()
    subscription = await UserSubscriptions.get_by_user_id('concurrent-billing-user', db=db_session)

    assert subscription.plan_balance_micros == chatpoint_to_micros(80)
