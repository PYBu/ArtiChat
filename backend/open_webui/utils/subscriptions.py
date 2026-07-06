from __future__ import annotations

from open_webui.models.subscriptions import (
    FREE_TIER,
    SubscriptionLedgers,
    SubscriptionPlans,
    UserSubscriptionModel,
    UserSubscriptions,
    now_ts,
)
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
