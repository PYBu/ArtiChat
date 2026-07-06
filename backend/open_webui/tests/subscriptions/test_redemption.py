import pytest

from open_webui.models.subscriptions import (
    CHATPOWER_TIER,
    PLUS_TIER,
    RedemptionCodes,
    SubscriptionPlans,
    UserSubscriptions,
    chatpoint_to_micros,
)
from open_webui.utils.subscriptions import redeem_code


@pytest.mark.asyncio
async def test_single_use_code_can_only_be_redeemed_once(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    created = await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=0,
        expires_at=None,
        memo='plus trial',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    result = await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)
    assert result.subscription.tier == PLUS_TIER

    with pytest.raises(ValueError, match='REDEMPTION_CODE_EXHAUSTED'):
        await redeem_code('user-2', created.raw_codes[0], now=1_720_000_010, db=db_session)


@pytest.mark.asyncio
async def test_multi_use_code_prevents_same_user_redeeming_twice(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    created = await RedemptionCodes.create_codes(
        mode='multi_use',
        quantity=1,
        max_uses=5,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=chatpoint_to_micros(25),
        expires_at=None,
        memo='check topup',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)
    with pytest.raises(ValueError, match='REDEMPTION_CODE_ALREADY_USED'):
        await redeem_code('user-1', created.raw_codes[0], now=1_720_000_001, db=db_session)


@pytest.mark.asyncio
async def test_lower_tier_code_does_not_downgrade_higher_subscription(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await UserSubscriptions.create_from_plan(
        user_id='user-1',
        plan_id=CHATPOWER_TIER,
        starts_at=1_720_000_000,
        expires_at=1_720_000_000 + 30 * 24 * 60 * 60,
        source='admin',
        db=db_session,
    )
    created = await RedemptionCodes.create_codes(
        mode='multi_use',
        quantity=1,
        max_uses=10,
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=chatpoint_to_micros(3),
        check_chatpoint_micros=chatpoint_to_micros(4),
        expires_at=None,
        memo='lower tier grant',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    result = await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)

    assert result.subscription.tier == CHATPOWER_TIER
    assert result.subscription.plan_balance_micros == chatpoint_to_micros(503)
    assert result.subscription.check_balance_micros == chatpoint_to_micros(4)
