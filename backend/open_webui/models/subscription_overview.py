from __future__ import annotations

import datetime as dt
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from open_webui.models.subscriptions import (
    FREE_TIER,
    GiftCardGrant,
    RedemptionCode,
    SubscriptionLedger,
    SubscriptionLedgerModel,
    SubscriptionUsage,
    UserSubscription,
    get_subscription_db_context,
    now_ts,
    user_summary,
)
from open_webui.models.users import User
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

SUBSCRIPTION_CHANGE_EVENT_TYPES = frozenset(
    {
        'activation',
        'admin_adjustment',
        'admin_update',
        'auto_downgrade',
        'expiry',
        'period_reset',
        'redemption',
        'renewal',
        'subscription_activation',
        'tier_change',
    }
)


def _application_timezone() -> tuple[str, ZoneInfo]:
    timezone_name = os.getenv('WEBUI_TIMEZONE') or os.getenv('TZ') or 'UTC'
    try:
        return timezone_name, ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return 'UTC', dt.UTC


def _period_bounds(current_time: int, timezone_info: ZoneInfo) -> dict[str, int | str]:
    local_now = dt.datetime.fromtimestamp(current_time, tz=timezone_info)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day_start = day_start + dt.timedelta(days=1)
    month_start = day_start.replace(day=1)
    previous_month_start = (month_start - dt.timedelta(days=1)).replace(day=1)
    previous_mtd_end = previous_month_start + (local_now - month_start)
    previous_mtd_end = min(previous_mtd_end, month_start)

    return {
        'day_start': int(day_start.timestamp()),
        'next_day_start': int(next_day_start.timestamp()),
        'month_start': int(month_start.timestamp()),
        'previous_month_start': int(previous_month_start.timestamp()),
        'previous_mtd_end': int(previous_mtd_end.timestamp()),
    }


def _percentage_change(current: int, previous: int) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 1)


class SubscriptionOverviewTable:
    async def get(
        self,
        *,
        now: int | None = None,
        activity_limit: int = 10,
        db: AsyncSession | None = None,
    ) -> dict:
        current_time = now if now is not None else now_ts()
        timezone_name, timezone_info = _application_timezone()
        bounds = _period_bounds(current_time, timezone_info)

        async with get_subscription_db_context(db) as session:
            active_filters = [
                UserSubscription.tier != FREE_TIER,
                UserSubscription.status == 'active',
                UserSubscription.starts_at <= current_time,
                or_(UserSubscription.expires_at.is_(None), UserSubscription.expires_at > current_time),
            ]
            active_count = int(
                (await session.execute(select(func.count(UserSubscription.id)).where(*active_filters))).scalar_one()
            )

            mtd_filters = [
                UserSubscription.tier != FREE_TIER,
                UserSubscription.status == 'active',
                UserSubscription.starts_at >= bounds['month_start'],
                UserSubscription.starts_at < current_time,
            ]
            mtd_count = int(
                (await session.execute(select(func.count(UserSubscription.id)).where(*mtd_filters))).scalar_one()
            )
            previous_mtd_filters = [
                UserSubscription.tier != FREE_TIER,
                UserSubscription.status == 'active',
                UserSubscription.starts_at >= bounds['previous_month_start'],
                UserSubscription.starts_at < bounds['previous_mtd_end'],
            ]
            previous_mtd_count = int(
                (
                    await session.execute(select(func.count(UserSubscription.id)).where(*previous_mtd_filters))
                ).scalar_one()
            )

            pending_result = await session.execute(
                select(
                    func.count(GiftCardGrant.id),
                    func.count(func.distinct(GiftCardGrant.batch_id)),
                )
                .select_from(GiftCardGrant)
                .join(RedemptionCode, RedemptionCode.id == GiftCardGrant.redemption_code_id)
                .where(
                    GiftCardGrant.status == 'pending',
                    RedemptionCode.is_active.is_(True),
                    RedemptionCode.used_count < RedemptionCode.max_uses,
                    or_(RedemptionCode.expires_at.is_(None), RedemptionCode.expires_at > current_time),
                    ~RedemptionCode.code_hash.like('deleted:%'),
                )
            )
            pending_count, pending_batch_count = pending_result.one()

            deductions_result = await session.execute(
                select(
                    func.coalesce(func.sum(SubscriptionUsage.plan_cost_micros), 0),
                    func.coalesce(func.sum(SubscriptionUsage.check_cost_micros), 0),
                    func.count(SubscriptionUsage.id),
                ).where(
                    SubscriptionUsage.created_at >= bounds['day_start'],
                    SubscriptionUsage.created_at < bounds['next_day_start'],
                )
            )
            plan_deductions, check_deductions, deduction_count = deductions_result.one()

            code_result = await session.execute(
                select(
                    RedemptionCode.tier,
                    RedemptionCode.duration_days,
                    RedemptionCode.plan_chatpoint_micros,
                    RedemptionCode.check_chatpoint_micros,
                ).where(
                    RedemptionCode.is_active.is_(True),
                    RedemptionCode.used_count < RedemptionCode.max_uses,
                    or_(RedemptionCode.expires_at.is_(None), RedemptionCode.expires_at > current_time),
                    ~RedemptionCode.code_hash.like('deleted:%'),
                )
            )
            available_code_counts = {'subscription': 0, 'recharge': 0, 'legacy': 0}
            for tier, duration_days, plan_micros, check_micros in code_result.all():
                has_subscription = tier is not None or duration_days is not None
                has_recharge = (plan_micros or 0) > 0 or (check_micros or 0) > 0
                if has_subscription:
                    available_code_counts['subscription'] += 1
                elif has_recharge:
                    available_code_counts['recharge'] += 1
                else:
                    # Preserve incomplete historical cards as legacy until an explicit
                    # benefit_type migration is approved; redeemability is unchanged.
                    available_code_counts['legacy'] += 1

            activity_result = await session.execute(
                select(SubscriptionLedger, User)
                .outerjoin(User, User.id == SubscriptionLedger.user_id)
                .where(
                    SubscriptionLedger.event_type.in_(SUBSCRIPTION_CHANGE_EVENT_TYPES),
                    or_(
                        SubscriptionLedger.event_type != 'redemption',
                        SubscriptionLedger.tier_before != SubscriptionLedger.tier_after,
                        SubscriptionLedger.meta['benefit_type'].as_string() == 'subscription',
                    ),
                )
                .order_by(SubscriptionLedger.created_at.desc())
                .limit(activity_limit)
            )
            recent_activity = []
            for ledger, activity_user in activity_result.all():
                if ledger.event_type == 'redemption':
                    metadata = ledger.meta if isinstance(ledger.meta, dict) else {}
                    is_subscription_redemption = (
                        ledger.tier_before != ledger.tier_after or metadata.get('benefit_type') == 'subscription'
                    )
                    if not is_subscription_redemption:
                        continue
                ledger_model = SubscriptionLedgerModel.model_validate(ledger)
                recent_activity.append(
                    {
                        **ledger_model.model_dump(by_alias=True),
                        'user': user_summary(activity_user),
                    }
                )

        plan_deductions = int(plan_deductions or 0)
        check_deductions = int(check_deductions or 0)
        return {
            'generated_at': current_time,
            'timezone': timezone_name,
            'metrics': {
                'active_subscriptions': {
                    'count': active_count,
                    'mtd_count': mtd_count,
                    'previous_mtd_count': previous_mtd_count,
                    'mtd_change_percent': _percentage_change(mtd_count, previous_mtd_count),
                },
                'pending_gifts': {
                    'count': int(pending_count or 0),
                    'batch_count': int(pending_batch_count or 0),
                },
                'daily_deductions': {
                    'plan_micros': plan_deductions,
                    'check_micros': check_deductions,
                    'total_micros': plan_deductions + check_deductions,
                    'request_count': int(deduction_count or 0),
                    'day_start': bounds['day_start'],
                    'day_end': bounds['next_day_start'],
                },
                'available_codes': {
                    'total': sum(available_code_counts.values()),
                    **available_code_counts,
                },
            },
            'recent_activity': recent_activity,
        }


SubscriptionOverview = SubscriptionOverviewTable()
