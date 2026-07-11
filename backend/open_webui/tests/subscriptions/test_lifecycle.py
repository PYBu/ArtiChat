import pytest

from open_webui.models.subscriptions import (
    CHATPOWER_TIER,
    FREE_TIER,
    PLUS_TIER,
    SubscriptionPlan,
    SubscriptionLedgers,
    SubscriptionPlans,
    UserSubscriptions,
    chatpoint_to_micros,
)
from open_webui.utils.subscriptions import ensure_subscription_current


@pytest.mark.asyncio
async def test_seed_default_plans_creates_three_tiers(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    plans = await SubscriptionPlans.get_plans(db=db_session)
    by_id = {plan.id: plan for plan in plans}

    assert set(by_id) == {FREE_TIER, PLUS_TIER, CHATPOWER_TIER}
    assert by_id[FREE_TIER].display_name == 'Free'
    assert by_id[FREE_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(100)
    assert by_id[PLUS_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(3000)
    assert by_id[CHATPOWER_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(10000)
    assert by_id[FREE_TIER].period_days == 30


@pytest.mark.asyncio
async def test_seed_default_plans_is_idempotent(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await SubscriptionPlans.seed_defaults(db=db_session)

    plans = await SubscriptionPlans.get_plans(db=db_session)

    assert len(plans) == 3


@pytest.mark.asyncio
async def test_seed_default_plans_updates_legacy_defaults_without_overwriting_custom_values(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    free_plan = await db_session.get(SubscriptionPlan, FREE_TIER)
    plus_plan = await db_session.get(SubscriptionPlan, PLUS_TIER)
    free_plan.display_name = '免费版'
    free_plan.description = '基础模型访问额度。'
    free_plan.plan_chatpoint_allowance_micros = chatpoint_to_micros(10)
    plus_plan.display_name = '自定义 Plus'
    plus_plan.description = '自定义说明'
    plus_plan.plan_chatpoint_allowance_micros = chatpoint_to_micros(888)
    await db_session.commit()

    await SubscriptionPlans.seed_defaults(db=db_session)
    plans = {plan.id: plan for plan in await SubscriptionPlans.get_plans(db=db_session)}

    assert plans[FREE_TIER].display_name == 'Free'
    assert plans[FREE_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(100)
    assert plans[PLUS_TIER].display_name == '自定义 Plus'
    assert plans[PLUS_TIER].description == '自定义说明'
    assert plans[PLUS_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(888)


@pytest.mark.asyncio
async def test_new_user_gets_free_subscription(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    subscription = await ensure_subscription_current('user-1', now=1_720_000_000, db=db_session)

    assert subscription.user_id == 'user-1'
    assert subscription.tier == FREE_TIER
    assert subscription.plan_balance_micros == chatpoint_to_micros(100)
    assert subscription.check_balance_micros == 0
    assert subscription.period_end_at == 1_720_000_000 + 30 * 24 * 60 * 60


@pytest.mark.asyncio
async def test_period_reset_preserves_check_balance(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    subscription = await ensure_subscription_current('user-2', now=1_720_000_000, db=db_session)
    await UserSubscriptions.adjust_balances(
        'user-2',
        plan_delta_micros=-chatpoint_to_micros(7),
        check_delta_micros=chatpoint_to_micros(25),
        event_type='admin_adjustment',
        created_by='admin',
        db=db_session,
    )

    reset = await ensure_subscription_current('user-2', now=subscription.period_end_at + 10, db=db_session)

    assert reset.plan_balance_micros == chatpoint_to_micros(100)
    assert reset.check_balance_micros == chatpoint_to_micros(25)
    assert reset.period_start_at == subscription.period_end_at


@pytest.mark.asyncio
async def test_expired_plus_auto_downgrades_to_free_before_reset(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    start = 1_720_000_000
    await UserSubscriptions.create_from_plan(
        user_id='user-3',
        plan_id=PLUS_TIER,
        starts_at=start,
        expires_at=start + 30 * 24 * 60 * 60,
        source='redemption',
        db=db_session,
    )

    subscription = await ensure_subscription_current('user-3', now=start + 31 * 24 * 60 * 60, db=db_session)

    assert subscription.tier == FREE_TIER
    assert subscription.plan_chatpoint_allowance_micros == chatpoint_to_micros(100)
    assert subscription.plan_balance_micros == chatpoint_to_micros(100)

    ledger = await SubscriptionLedgers.get_recent_for_user('user-3', limit=5, db=db_session)
    assert any(entry.event_type == 'auto_downgrade' for entry in ledger)
