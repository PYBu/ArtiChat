"""Chatpoint reservations for image and video generation.

Media providers are asynchronous or return a variable number of files, so the
reservation is made from the requested amount and settled only after the
generated files have been persisted. Provider errors release the hold without
creating a positive charge.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from open_webui.models.subscriptions import (
    SubscriptionReservationModel,
    SubscriptionUsages,
    UserSubscriptions,
    chatpoint_to_micros,
    get_subscription_db_context,
    now_ts,
)
from open_webui.utils.subscriptions import (
    ChatpointReservationCapExceededError,
    ChatpointReservationConflictError,
    assert_chatpoint_available,
    release_chatpoint_reservation,
    reserve_chatpoints,
    reservation_billing_idempotency_key,
    settle_chatpoint_reservation,
)

MEDIA_BILLING_EXPIRY_SECONDS = {
    'image': 60 * 60,
    'video': 2 * 24 * 60 * 60,
}
SECONDS_PER_DAY = 24 * 60 * 60


@dataclass
class MediaBillingContext:
    user_id: str
    media_type: str
    unit: str
    requested_units: int
    rate_chatpoints: Decimal
    rate_micros: int
    reservation_id: str | None = None
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    model_id: str = ''
    chat_id: str | None = None
    message_id: str | None = None
    is_admin: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def billable(self) -> bool:
        return self.reservation_id is not None and self.rate_chatpoints > 0


def parse_media_rate(value: Any) -> Decimal:
    """Normalize a configured Chatpoint price and reject unsafe values."""

    try:
        rate = Decimal(str(value if value is not None else '0')).normalize()
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('media billing rate must be a finite number') from exc
    if not rate.is_finite() or rate < 0:
        raise ValueError('media billing rate must be a finite number greater than or equal to 0')
    if rate > Decimal('1000000'):
        raise ValueError('media billing rate is too large')
    return rate


def media_cost_micros(units: int, rate_chatpoints: Decimal | str | int) -> int:
    units = int(units)
    if units < 0:
        raise ValueError('media units must be greater than or equal to 0')
    rate = parse_media_rate(rate_chatpoints)
    return chatpoint_to_micros(Decimal(units) * rate) if units and rate else 0


def media_cost_chatpoints(units: int, rate_chatpoints: Decimal | str | int) -> Decimal:
    return Decimal(media_cost_micros(units, rate_chatpoints)) / Decimal(1_000_000)


def utc_day_start(timestamp: int | None = None) -> int:
    current = int(timestamp if timestamp is not None else now_ts())
    return current - current % SECONDS_PER_DAY


def _media_unit(media_type: str) -> str:
    if media_type == 'image':
        return 'image'
    if media_type == 'video':
        return 'second'
    raise ValueError(f'unsupported media type: {media_type}')


async def reserve_media_generation(
    user,
    *,
    media_type: str,
    units: int,
    rate_chatpoints: Decimal | str | int,
    model_id: str,
    chat_id: str | None = None,
    message_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
    daily_cap_chatpoints: Decimal | str | int | None = None,
    daily_cap_since: int | None = None,
    db=None,
) -> MediaBillingContext:
    """Reserve the maximum requested media cost before calling a provider."""

    units = int(units)
    if units <= 0:
        raise ValueError('media units must be greater than 0')
    rate = parse_media_rate(rate_chatpoints)
    daily_cap_rate = parse_media_rate(daily_cap_chatpoints) if daily_cap_chatpoints is not None else Decimal('0')
    context = MediaBillingContext(
        user_id=str(user.id),
        media_type=media_type,
        unit=_media_unit(media_type),
        requested_units=units,
        rate_chatpoints=rate,
        rate_micros=chatpoint_to_micros(rate) if rate else 0,
        request_id=request_id or uuid.uuid4().hex,
        model_id=model_id or f'media:{media_type}',
        chat_id=chat_id,
        message_id=message_id,
        is_admin=getattr(user, 'role', None) == 'admin',
        metadata=dict(metadata or {}),
    )
    if context.is_admin or rate == 0:
        return context

    try:
        await assert_chatpoint_available(str(user.id), quota_mode='metered', is_admin=False, db=db)
        grant = await reserve_chatpoints(
            str(user.id),
            request_id=context.request_id,
            model_id=f'__media__:{media_type}:{context.model_id}',
            amount_micros=media_cost_micros(units, rate),
            expires_at=now_ts() + MEDIA_BILLING_EXPIRY_SECONDS[media_type],
            metadata={
                **context.metadata,
                'media_billing': True,
                'media_type': media_type,
                'media_unit': context.unit,
                'media_units_reserved': units,
                'media_rate_chatpoints': str(rate),
                'chat_id': chat_id,
                'message_id': message_id,
            },
            db=db,
            cap_micros=chatpoint_to_micros(daily_cap_rate) if daily_cap_rate else None,
            cap_since=(daily_cap_since if daily_cap_since is not None else utc_day_start())
            if daily_cap_rate
            else None,
            cap_media_type=media_type,
            cap_model_prefix=f'__media__:{media_type}:',
        )
        context.reservation_id = grant.reservation.id
        return context
    except ChatpointReservationCapExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                'code': 'MEDIA_DAILY_CAP_EXCEEDED',
                'message': '已达到今日媒体费用上限。',
                'requested_chatpoints': str(Decimal(exc.requested_micros) / Decimal(1_000_000)),
                'committed_chatpoints': str(Decimal(exc.committed_micros) / Decimal(1_000_000)),
                'cap_chatpoints': str(Decimal(exc.cap_micros) / Decimal(1_000_000)),
            },
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=402, detail='Chatpoint 余额不足，无法生成媒体') from exc


async def settle_media_generation(
    context: MediaBillingContext,
    *,
    units: int,
    metadata: dict[str, Any] | None = None,
    db=None,
):
    """Settle a successful provider result and write one usage row."""

    if not context.billable:
        return None
    units = int(units)
    if units <= 0:
        return await release_media_generation(context, reason='provider returned no media', db=db)

    current_time = now_ts()
    stored_metadata = {**context.metadata, **(metadata or {}), 'media_success': True}
    async with get_subscription_db_context(db) as session:
        existing = await SubscriptionUsages.get_by_reservation_id(context.reservation_id, db=session)
        if existing:
            return existing
        reservation = await _get_reservation(context.reservation_id, session)
        if reservation is None:
            raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
        if reservation.status == 'active':
            reservation = await settle_chatpoint_reservation(
                context.reservation_id,
                actual_cost_micros=media_cost_micros(units, context.rate_chatpoints),
                allow_partial=False,
                now=current_time,
                commit=False,
                db=session,
            )
        elif reservation.status not in {'settled', 'partially_settled'}:
            raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_ACTIVE')

        subscription = await UserSubscriptions.get_by_user_id(context.user_id, db=session)
        if subscription is None:
            raise ValueError(f'user subscription not found: {context.user_id}')
        actual_cost = int(reservation.actual_cost_micros or 0)
        context.request_id = reservation.request_id
        if not context.model_id:
            context.model_id = reservation.model_id
        result = await SubscriptionUsages.insert(
            user_id=context.user_id,
            chat_id=context.chat_id,
            message_id=context.message_id,
            request_id=reservation.request_id,
            idempotency_key=reservation_billing_idempotency_key(context.reservation_id),
            reservation_id=context.reservation_id,
            model_id=context.model_id,
            usage_type=context.media_type,
            media_unit=context.unit,
            media_units=units,
            media_unit_price_micros=context.rate_micros,
            tier=subscription.tier,
            quota_mode='metered',
            usage_multiplier='1',
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            total_tokens=0,
            input_chatpoint_per_million=None,
            output_chatpoint_per_million=None,
            cache_creation_chatpoint_per_million=None,
            cache_read_chatpoint_per_million=None,
            cost_micros=actual_cost,
            plan_cost_micros=int(reservation.settled_plan_micros or 0),
            check_cost_micros=int(reservation.settled_check_micros or 0),
            unpaid_cost_micros=int(reservation.unpaid_cost_micros or 0),
            plan_balance_after_micros=subscription.plan_balance_micros,
            check_balance_after_micros=subscription.check_balance_micros,
            first_token_latency_ms=None,
            total_duration_ms=None,
            client_ip=None,
            status='partially_billed' if reservation.unpaid_cost_micros else 'billed',
            raw_usage=None,
            metadata=stored_metadata,
            created_at=current_time,
            commit=False,
            db=session,
        )
        await session.commit()
        return result


async def release_media_generation(
    context: MediaBillingContext,
    *,
    reason: str,
    metadata: dict[str, Any] | None = None,
    db=None,
):
    """Release a failed/cancelled operation and record a zero-cost audit row."""

    if not context.billable:
        return None
    current_time = now_ts()
    stored_metadata = {**context.metadata, **(metadata or {}), 'media_success': False, 'failure_reason': reason}
    async with get_subscription_db_context(db) as session:
        existing = await SubscriptionUsages.get_by_reservation_id(context.reservation_id, db=session)
        if existing:
            return existing
        reservation = await _get_reservation(context.reservation_id, session)
        if reservation is None:
            return None
        if reservation.status == 'active':
            reservation = await release_chatpoint_reservation(
                context.reservation_id,
                reason=reason,
                now=current_time,
                commit=False,
                db=session,
            )
        elif reservation.status in {'settled', 'partially_settled'}:
            # A provider callback may fail after the monetary settlement has
            # committed. Never write a zero-cost failure row for that charge.
            raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_ALREADY_SETTLED')
        context.request_id = reservation.request_id
        if not context.model_id:
            context.model_id = reservation.model_id
        subscription = await UserSubscriptions.get_by_user_id(context.user_id, db=session)
        if subscription is None:
            await session.commit()
            return None
        result = await SubscriptionUsages.insert(
            user_id=context.user_id,
            chat_id=context.chat_id,
            message_id=context.message_id,
            request_id=reservation.request_id,
            idempotency_key=reservation_billing_idempotency_key(context.reservation_id),
            reservation_id=context.reservation_id,
            model_id=context.model_id,
            usage_type=context.media_type,
            media_unit=context.unit,
            media_units=0,
            media_unit_price_micros=context.rate_micros,
            tier=subscription.tier,
            quota_mode='metered',
            usage_multiplier='1',
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            total_tokens=0,
            input_chatpoint_per_million=None,
            output_chatpoint_per_million=None,
            cache_creation_chatpoint_per_million=None,
            cache_read_chatpoint_per_million=None,
            cost_micros=0,
            plan_cost_micros=0,
            check_cost_micros=0,
            unpaid_cost_micros=0,
            plan_balance_after_micros=subscription.plan_balance_micros,
            check_balance_after_micros=subscription.check_balance_micros,
            first_token_latency_ms=None,
            total_duration_ms=None,
            client_ip=None,
            status='failed',
            raw_usage=None,
            metadata=stored_metadata,
            created_at=current_time,
            commit=False,
            db=session,
        )
        await session.commit()
        return result


async def _get_reservation(reservation_id: str, db) -> SubscriptionReservationModel | None:
    from open_webui.models.subscriptions import SubscriptionReservations

    return await SubscriptionReservations.get_by_id(reservation_id, db=db)
