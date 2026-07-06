import pytest

from open_webui.models.subscriptions import (
    CHATPOWER_TIER,
    FREE_TIER,
    PLUS_TIER,
    SubscriptionPlans,
    chatpoint_to_micros,
)


@pytest.mark.asyncio
async def test_seed_default_plans_creates_three_tiers(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    plans = await SubscriptionPlans.get_plans(db=db_session)
    by_id = {plan.id: plan for plan in plans}

    assert set(by_id) == {FREE_TIER, PLUS_TIER, CHATPOWER_TIER}
    assert by_id[FREE_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(10)
    assert by_id[PLUS_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(100)
    assert by_id[CHATPOWER_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(500)
    assert by_id[FREE_TIER].period_days == 30


@pytest.mark.asyncio
async def test_seed_default_plans_is_idempotent(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await SubscriptionPlans.seed_defaults(db=db_session)

    plans = await SubscriptionPlans.get_plans(db=db_session)

    assert len(plans) == 3
