from __future__ import annotations

from open_webui.models.subscriptions import (
    FREE_TIER,
    RedemptionCodes,
    RedemptionRecords,
    SubscriptionLedgers,
    SubscriptionPlans,
    UserSubscriptionModel,
    UserSubscriptions,
    now_ts,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

SECONDS_PER_DAY = 24 * 60 * 60


def period_seconds(period_days: int) -> int:
    return period_days * SECONDS_PER_DAY


async def ensure_subscription_current(
    user_id: str, *, now: int | None = None, db: AsyncSession | None = None
) -> UserSubscriptionModel:
    current_time = now if now is not None else now_ts()
    await SubscriptionPlans.seed_defaults(db=db)

    subscription = await UserSubscriptions.get_by_user_id(user_id, db=db)
    if not subscription:
        return await UserSubscriptions.create_from_plan(
            user_id=user_id,
            plan_id=FREE_TIER,
            starts_at=current_time,
            expires_at=None,
            source='default',
            db=db,
        )

    if subscription.expires_at is not None and current_time >= subscription.expires_at:
        downgraded = await UserSubscriptions.create_from_plan(
            user_id=user_id,
            plan_id=FREE_TIER,
            starts_at=current_time,
            expires_at=None,
            source='default',
            db=db,
        )
        await SubscriptionLedgers.insert(
            user_id=user_id,
            event_type='auto_downgrade',
            tier_before=subscription.tier,
            tier_after=downgraded.tier,
            plan_delta_micros=downgraded.plan_balance_micros - subscription.plan_balance_micros,
            check_delta_micros=0,
            plan_balance_after_micros=downgraded.plan_balance_micros,
            check_balance_after_micros=downgraded.check_balance_micros,
            reference_type='subscription',
            reference_id=subscription.id,
            created_at=current_time,
            db=db,
        )
        return downgraded

    if current_time >= subscription.next_reset_at:
        periods_elapsed = max(
            1, (current_time - subscription.period_start_at) // period_seconds(subscription.period_days)
        )
        new_period_start = subscription.period_start_at + periods_elapsed * period_seconds(subscription.period_days)
        new_period_end = new_period_start + period_seconds(subscription.period_days)
        before_plan = subscription.plan_balance_micros
        subscription.period_start_at = new_period_start
        subscription.period_end_at = new_period_end
        subscription.next_reset_at = new_period_end
        subscription.plan_balance_micros = subscription.plan_chatpoint_allowance_micros
        subscription.updated_at = current_time
        reset = await UserSubscriptions.save(subscription, db=db)
        await SubscriptionLedgers.insert(
            user_id=user_id,
            event_type='period_reset',
            tier_before=subscription.tier,
            tier_after=subscription.tier,
            plan_delta_micros=reset.plan_balance_micros - before_plan,
            check_delta_micros=0,
            plan_balance_after_micros=reset.plan_balance_micros,
            check_balance_after_micros=reset.check_balance_micros,
            reference_type='subscription',
            reference_id=reset.id,
            created_at=current_time,
            db=db,
        )
        return reset

    return subscription


class RedemptionResult(BaseModel):
    subscription: UserSubscriptionModel
    tier_before: str | None
    tier_after: str | None
    plan_delta_micros: int
    check_delta_micros: int


async def redeem_code(
    user_id: str, raw_code: str, *, now: int | None = None, db: AsyncSession | None = None
) -> RedemptionResult:
    current_time = now if now is not None else now_ts()
    code = await RedemptionCodes.get_by_raw_code(raw_code, db=db)
    if not code:
        raise ValueError('REDEMPTION_CODE_INVALID')
    if not code.is_active:
        raise ValueError('REDEMPTION_CODE_DISABLED')
    if code.expires_at is not None and current_time >= code.expires_at:
        raise ValueError('REDEMPTION_CODE_EXPIRED')
    if code.used_count >= code.max_uses:
        raise ValueError('REDEMPTION_CODE_EXHAUSTED')
    if await RedemptionRecords.get_by_code_and_user(code.id, user_id, db=db):
        raise ValueError('REDEMPTION_CODE_ALREADY_USED')

    subscription = await ensure_subscription_current(user_id, now=current_time, db=db)
    before = subscription
    tier_after = before.tier
    expires_after = before.expires_at
    plan_delta = code.plan_chatpoint_micros
    check_delta = code.check_chatpoint_micros

    if code.tier and code.duration_days:
        plan = await SubscriptionPlans.get_plan_by_id(code.tier, db=db)
        if not plan or not plan.is_active:
            raise ValueError('SUBSCRIPTION_PLAN_INACTIVE')
        if plan.tier_rank >= before.tier_rank:
            base_expiry = max(current_time, before.expires_at or current_time)
            expires_after = base_expiry + period_seconds(code.duration_days)
            subscription = await UserSubscriptions.create_from_plan(
                user_id=user_id,
                plan_id=code.tier,
                starts_at=current_time,
                expires_at=expires_after,
                source='redemption',
                db=db,
            )
            tier_after = subscription.tier

    subscription = await UserSubscriptions.adjust_balances(
        user_id,
        plan_delta_micros=plan_delta,
        check_delta_micros=check_delta,
        event_type='redemption',
        created_by=None,
        db=db,
    )
    await RedemptionCodes.increment_used_count(code.id, db=db)
    await RedemptionRecords.insert(
        redemption_code_id=code.id,
        user_id=user_id,
        tier_before=before.tier,
        tier_after=tier_after,
        plan_delta_micros=plan_delta,
        check_delta_micros=check_delta,
        subscription_expires_at_before=before.expires_at,
        subscription_expires_at_after=expires_after,
        created_at=current_time,
        db=db,
    )

    return RedemptionResult(
        subscription=subscription,
        tier_before=before.tier,
        tier_after=tier_after,
        plan_delta_micros=plan_delta,
        check_delta_micros=check_delta,
    )
