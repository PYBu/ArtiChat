from __future__ import annotations

import hashlib
import logging
import time
from decimal import Decimal, InvalidOperation

from open_webui.models.config import Config
from open_webui.models.subscriptions import (
    CHATPOWER_TIER,
    FREE_TIER,
    PLUS_TIER,
    RedemptionCodes,
    RedemptionRecords,
    SubscriptionLedgers,
    SubscriptionReservation,
    SubscriptionPlans,
    SubscriptionReservationModel,
    SubscriptionReservations,
    SubscriptionUsage,
    SubscriptionUsages,
    UserSubscriptionModel,
    UserSubscriptions,
    calculate_token_cost_micros,
    debit_balances,
    get_subscription_db_context,
    json_safe_metadata,
    now_ts,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

SECONDS_PER_DAY = 24 * 60 * 60
log = logging.getLogger(__name__)


class ChatpointReservationRequest(BaseModel):
    request_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    amount_micros: int = Field(ge=0)
    expires_at: int | None = None
    metadata: dict | None = None

    @field_validator('request_id', 'model_id')
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('identifier must not be empty')
        return value


class ChatpointReservationResizeRequest(BaseModel):
    reservation_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    amount_micros: int = Field(ge=0)
    expires_at: int | None = None
    metadata: dict | None = None

    @field_validator('reservation_id', 'request_id', 'model_id')
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('identifier must not be empty')
        return value


class ChatpointReservationInsufficientError(PermissionError):
    def __init__(self, *, requested_micros: int, available_micros: int):
        self.requested_micros = requested_micros
        self.available_micros = available_micros
        super().__init__(
            f'CHATPOINT_RESERVATION_INSUFFICIENT: requested={requested_micros}, available={available_micros}'
        )


class ChatpointReservationCapExceededError(PermissionError):
    def __init__(self, *, requested_micros: int, committed_micros: int, cap_micros: int):
        self.requested_micros = requested_micros
        self.committed_micros = committed_micros
        self.cap_micros = cap_micros
        super().__init__(
            f'CHATPOINT_MEDIA_DAILY_CAP_EXCEEDED: requested={requested_micros}, '
            f'committed={committed_micros}, cap={cap_micros}'
        )


class ChatpointReservationConflictError(ValueError):
    pass


class ChatpointReservationGrant(BaseModel):
    reservation: SubscriptionReservationModel
    acquired: bool


PENDING_SETTLEMENT_KEY = '_artichat_pending_settlement'
PENDING_SETTLEMENT_LEASE_SECONDS = 120
DEFAULT_MAX_PENDING_SETTLEMENTS_PER_USER = 3
# Backward-compatible export for integrations that imported the old default.
MAX_PENDING_SETTLEMENTS_PER_USER = DEFAULT_MAX_PENDING_SETTLEMENTS_PER_USER
MAX_PENDING_SETTLEMENTS_LIMIT = 100
_PENDING_SETTLEMENT_LIMIT_CACHE_TTL_SECONDS = 5
_pending_settlement_limit_cache: tuple[float, int] | None = None


async def get_max_pending_settlements_per_user() -> int:
    """Read the administrator's continuation allowance with a safe bound."""
    global _pending_settlement_limit_cache
    now = time.monotonic()
    if (
        _pending_settlement_limit_cache is not None
        and now - _pending_settlement_limit_cache[0] < _PENDING_SETTLEMENT_LIMIT_CACHE_TTL_SECONDS
    ):
        return _pending_settlement_limit_cache[1]

    configured = await Config.get(
        'billing.max_pending_settlements_per_user',
        DEFAULT_MAX_PENDING_SETTLEMENTS_PER_USER,
    )
    try:
        value = int(configured)
    except (TypeError, ValueError):
        value = DEFAULT_MAX_PENDING_SETTLEMENTS_PER_USER
    value = min(max(value, 0), MAX_PENDING_SETTLEMENTS_LIMIT)
    _pending_settlement_limit_cache = (now, value)
    return value


def cache_max_pending_settlements_per_user(value: int) -> None:
    """Refresh the local setting cache after an administrator update."""
    global _pending_settlement_limit_cache
    _pending_settlement_limit_cache = (time.monotonic(), min(max(int(value), 0), MAX_PENDING_SETTLEMENTS_LIMIT))


def _pending_settlement_metadata(reservation: SubscriptionReservationModel) -> dict | None:
    value = (reservation.metadata or {}).get(PENDING_SETTLEMENT_KEY)
    return value if isinstance(value, dict) else None


async def _reconcile_pending_settlement_count(
    user_id: str,
    subscription: UserSubscriptionModel,
    *,
    now: int,
    db: AsyncSession,
) -> tuple[UserSubscriptionModel, int]:
    """Initialize the counter for rows created before the counter migration."""
    if subscription.pending_settlement_count is not None:
        return subscription, max(int(subscription.pending_settlement_count), 0)

    rows = await SubscriptionReservations.list_active(user_id=user_id, limit=None, db=db)
    count = sum(1 for row in rows if _pending_settlement_metadata(row) is not None)
    subscription = await UserSubscriptions.update_pending_settlement_count(
        user_id,
        count,
        now=now,
        commit=False,
        db=db,
    )
    return subscription, count


async def _decrement_pending_settlement_count(
    user_id: str,
    subscription: UserSubscriptionModel,
    *,
    now: int,
    db: AsyncSession,
) -> UserSubscriptionModel:
    """Release one slot when a pending reservation becomes terminal."""
    if subscription.pending_settlement_count is None:
        return subscription
    return await UserSubscriptions.update_pending_settlement_count(
        user_id,
        max(int(subscription.pending_settlement_count) - 1, 0),
        now=now,
        commit=False,
        db=db,
    )


async def defer_chatpoint_reservation_settlement(
    reservation_id: str,
    payload: dict,
    *,
    max_pending_settlements: int | None = None,
    now: int | None = None,
    db: AsyncSession | None = None,
) -> SubscriptionReservationModel | None:
    """Release the input hold while keeping the reservation for later billing.

    This lets a completed response return immediately and lets the next prompt
    reserve against the restored balance. The settlement worker will charge the
    actual usage later; any overage is intentionally recorded as unpaid.
    """
    current_time = now if now is not None else now_ts()
    if max_pending_settlements is None:
        max_pending_settlements = await get_max_pending_settlements_per_user()
    max_pending_settlements = min(max(int(max_pending_settlements), 0), MAX_PENDING_SETTLEMENTS_LIMIT)
    async with get_subscription_db_context(db) as session:
        try:
            reservation = await SubscriptionReservations.get_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
            if reservation.status != 'active':
                return reservation

            await ensure_subscription_current(
                reservation.user_id,
                now=current_time,
                commit=False,
                db=session,
            )
            subscription = await UserSubscriptions.lock_for_billing(reservation.user_id, db=session)
            _subscription, pending_count = await _reconcile_pending_settlement_count(
                reservation.user_id,
                subscription,
                now=current_time,
                db=session,
            )
            if pending_count >= max_pending_settlements:
                reservation = await SubscriptionReservations.lock_by_id(reservation_id, db=session)
                if reservation is None:
                    raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
                if _pending_settlement_metadata(reservation) is not None:
                    await session.commit()
                    return reservation
                await session.commit()
                return None

            # Serialize the marker write after the per-user slot decision.
            reservation = await SubscriptionReservations.lock_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
            if reservation.status != 'active':
                return reservation
            if _pending_settlement_metadata(reservation) is not None:
                return reservation

            refund_plan = max(reservation.reserved_plan_micros, 0)
            refund_check = max(reservation.reserved_check_micros, 0)
            if refund_plan or refund_check:
                await UserSubscriptions.adjust_balances(
                    reservation.user_id,
                    plan_delta_micros=refund_plan,
                    check_delta_micros=refund_check,
                    event_type='reservation_pending_settlement_release',
                    reference_type='subscription_reservation',
                    reference_id=reservation.id,
                    metadata={'reserved_micros': reservation.reserved_micros},
                    created_by=None,
                    created_at=current_time,
                    commit=False,
                    db=session,
                )

            metadata = dict(reservation.metadata or {})
            metadata[PENDING_SETTLEMENT_KEY] = {
                'state': 'pending',
                'attempts': 0,
                'queued_at': current_time,
                'payload': json_safe_metadata(payload) or {},
            }
            result = await SubscriptionReservations.update_state(
                reservation.id,
                values={
                    'reserved_micros': 0,
                    'reserved_plan_micros': 0,
                    'reserved_check_micros': 0,
                    'expires_at': current_time + 86400,
                    'meta': metadata,
                    'updated_at': current_time,
                },
                commit=False,
                db=session,
            )
            await UserSubscriptions.update_pending_settlement_count(
                reservation.user_id,
                pending_count + 1,
                now=current_time,
                commit=False,
                db=session,
            )
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def list_pending_chatpoint_settlements(
    *,
    limit: int = 20,
    db: AsyncSession | None = None,
) -> list[SubscriptionReservationModel]:
    if limit <= 0:
        return []
    # Scan all active rows so older non-pending reservations cannot starve the
    # durable continuation queue.
    rows = await SubscriptionReservations.list_active(limit=None, db=db)
    pending = []
    now = now_ts()
    for row in rows:
        marker = _pending_settlement_metadata(row)
        if not marker:
            continue
        if marker.get('state') == 'running' and int(marker.get('lease_until') or 0) > now:
            continue
        pending.append(row)
        if len(pending) >= limit:
            break
    return pending


async def count_pending_chatpoint_settlements(
    user_id: str,
    *,
    limit: int = MAX_PENDING_SETTLEMENTS_LIMIT,
    db: AsyncSession | None = None,
) -> int:
    if limit <= 0:
        return 0
    rows = await SubscriptionReservations.list_active(
        user_id=user_id,
        limit=None,
        db=db,
    )
    return sum(1 for row in rows if _pending_settlement_metadata(row) is not None)


async def claim_pending_chatpoint_settlement(
    reservation_id: str,
    *,
    now: int | None = None,
    db: AsyncSession | None = None,
) -> tuple[SubscriptionReservationModel, dict] | None:
    current_time = now if now is not None else now_ts()
    async with get_subscription_db_context(db) as session:
        try:
            reservation = await SubscriptionReservations.lock_by_id(reservation_id, db=session)
            if reservation is None or reservation.status != 'active':
                return None
            marker = _pending_settlement_metadata(reservation)
            if not marker:
                return None
            if marker.get('state') == 'running' and int(marker.get('lease_until') or 0) > current_time:
                return None
            payload = marker.get('payload') if isinstance(marker.get('payload'), dict) else {}
            marker = {
                **marker,
                'state': 'running',
                'lease_until': current_time + PENDING_SETTLEMENT_LEASE_SECONDS,
                'attempts': int(marker.get('attempts') or 0) + 1,
            }
            metadata = dict(reservation.metadata or {})
            metadata[PENDING_SETTLEMENT_KEY] = marker
            claimed = await SubscriptionReservations.update_state(
                reservation.id,
                values={'meta': metadata, 'updated_at': current_time},
                commit=False,
                db=session,
            )
            await session.commit()
            return claimed, payload
        except Exception:
            await session.rollback()
            raise


async def mark_pending_chatpoint_settlement_retry(
    reservation_id: str,
    error: str,
    *,
    now: int | None = None,
    db: AsyncSession | None = None,
) -> None:
    current_time = now if now is not None else now_ts()
    async with get_subscription_db_context(db) as session:
        reservation = await SubscriptionReservations.get_by_id(reservation_id, db=session)
        if reservation is None or reservation.status != 'active':
            return
        marker = _pending_settlement_metadata(reservation)
        if not marker:
            return
        metadata = dict(reservation.metadata or {})
        metadata[PENDING_SETTLEMENT_KEY] = {
            **marker,
            'state': 'pending',
            'last_error': error[:200],
            'lease_until': None,
        }
        await SubscriptionReservations.update_state(
            reservation.id,
            values={'meta': metadata, 'updated_at': current_time},
            db=session,
        )


def period_seconds(period_days: int) -> int:
    return period_days * SECONDS_PER_DAY


class ModelSubscriptionPolicy(BaseModel):
    model_config = ConfigDict(extra='ignore')

    allowed_tiers: list[str] = Field(default_factory=lambda: [FREE_TIER, PLUS_TIER, CHATPOWER_TIER])
    quota_mode: str = 'metered'
    usage_multiplier: str = '1'
    input_chatpoint_per_million: str | None = None
    output_chatpoint_per_million: str | None = None
    cache_creation_chatpoint_per_million: str | None = None
    cache_read_chatpoint_per_million: str | None = None

    @model_validator(mode='before')
    @classmethod
    def normalize_legacy_prices(cls, value):
        data = dict(value or {})
        try:
            multiplier = Decimal(str(data.get('usage_multiplier', '1')))
        except InvalidOperation as exc:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: usage_multiplier must be numeric') from exc
        if not multiplier.is_finite() or multiplier < 0:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: usage_multiplier must be >= 0')

        legacy_price = _canonical_decimal(multiplier * Decimal('100'))
        data.setdefault('input_chatpoint_per_million', legacy_price)
        data.setdefault('output_chatpoint_per_million', legacy_price)
        data.setdefault('cache_creation_chatpoint_per_million', '0')
        data.setdefault('cache_read_chatpoint_per_million', '0')
        return data

    @field_validator('allowed_tiers')
    @classmethod
    def validate_allowed_tiers(cls, value: list[str]) -> list[str]:
        allowed = {FREE_TIER, PLUS_TIER, CHATPOWER_TIER}
        normalized = [tier for tier in value if tier in allowed]
        if not normalized:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: allowed_tiers must include at least one tier')
        return normalized

    @field_validator('quota_mode')
    @classmethod
    def validate_quota_mode(cls, value: str) -> str:
        if value not in {'unlimited', 'metered'}:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: quota_mode must be unlimited or metered')
        return value

    @field_validator('usage_multiplier')
    @classmethod
    def validate_usage_multiplier(cls, value: str) -> str:
        try:
            multiplier = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: usage_multiplier must be numeric') from exc
        if multiplier < 0:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: usage_multiplier must be >= 0')
        return str(value)

    @field_validator(
        'input_chatpoint_per_million',
        'output_chatpoint_per_million',
        'cache_creation_chatpoint_per_million',
        'cache_read_chatpoint_per_million',
        mode='before',
    )
    @classmethod
    def validate_token_price(cls, value) -> str:
        try:
            price = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: token price must be numeric') from exc
        if not price.is_finite() or price < 0:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: token price must be >= 0')
        return _canonical_decimal(price)


def _canonical_decimal(value: Decimal) -> str:
    normalized = format(value.normalize(), 'f')
    return '0' if Decimal(normalized) == 0 else normalized


class NormalizedBillableUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    unclassified_tokens: int = Field(default=0, exclude=True)
    raw_usage: dict = Field(default_factory=dict)
    usage_present: bool = False


def _usage_int(usage: dict, *keys: str) -> int:
    for key in keys:
        if key in usage and usage[key] is not None:
            try:
                return max(int(usage[key]), 0)
            except (TypeError, ValueError):
                return 0
    return 0


def normalize_billable_usage(usage: dict | None) -> NormalizedBillableUsage:
    raw_usage = dict(usage or {})
    input_tokens = _usage_int(raw_usage, 'input_tokens', 'prompt_tokens', 'prompt_eval_count', 'prompt_n')
    output_tokens = _usage_int(raw_usage, 'output_tokens', 'completion_tokens', 'eval_count', 'predicted_n')
    cache_creation_tokens = _usage_int(raw_usage, 'cache_creation_tokens', 'cache_creation_input_tokens')
    cache_read_tokens = _usage_int(raw_usage, 'cache_read_tokens', 'cache_read_input_tokens')

    cache_is_included_in_input = False
    for details_key in ('prompt_tokens_details', 'input_tokens_details'):
        details = raw_usage.get(details_key)
        if isinstance(details, dict) and details.get('cached_tokens') is not None:
            cache_read_tokens = _usage_int(details, 'cached_tokens')
            cache_is_included_in_input = True
            break

    normal_input_tokens = max(input_tokens - cache_read_tokens, 0) if cache_is_included_in_input else input_tokens
    component_tokens = normal_input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens
    reported_total = _usage_int(raw_usage, 'total_tokens')
    total_tokens = max(component_tokens, reported_total)
    return NormalizedBillableUsage(
        input_tokens=normal_input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        total_tokens=total_tokens,
        unclassified_tokens=max(reported_total - component_tokens, 0),
        raw_usage=raw_usage,
        usage_present=total_tokens > 0,
    )


def get_request_client_ip(request) -> str | None:
    client = getattr(request, 'client', None)
    host = getattr(client, 'host', None)
    return str(host) if host else None


def billing_idempotency_key(user_id: str, request_id: str | None) -> str | None:
    if not request_id:
        return None
    payload = f'artichat-billing-v1\0{user_id}\0{request_id}'.encode()
    return hashlib.sha256(payload).hexdigest()


def reservation_billing_idempotency_key(reservation_id: str) -> str:
    payload = f'artichat-reservation-billing-v1\0{reservation_id}'.encode()
    return hashlib.sha256(payload).hexdigest()


def reservation_idempotency_key(user_id: str, request_id: str, model_id: str) -> str:
    payload = f'artichat-reservation-v1\0{user_id}\0{request_id}\0{model_id}'.encode()
    return hashlib.sha256(payload).hexdigest()


def stream_event_has_content(data: dict | None) -> bool:
    if not isinstance(data, dict):
        return False
    event_type = str(data.get('type') or '')
    if event_type.endswith('.delta') and any(
        marker in event_type for marker in ('output_text', 'reasoning', 'function_call_arguments')
    ):
        return bool(data.get('delta'))
    for choice in data.get('choices') or []:
        delta = choice.get('delta') or {}
        if delta.get('content') or delta.get('reasoning_content') or delta.get('reasoning') or delta.get('thinking'):
            return True
        if delta.get('tool_calls'):
            return True
    return False


def get_model_subscription_policy(model: dict) -> ModelSubscriptionPolicy:
    meta = (model.get('info') or {}).get('meta') or model.get('meta') or {}
    raw_policy = meta.get('subscription') or {}
    return ModelSubscriptionPolicy.model_validate(raw_policy)


def assert_model_subscription_access(model: dict, *, tier: str, is_admin: bool) -> ModelSubscriptionPolicy:
    policy = get_model_subscription_policy(model)
    if is_admin:
        return policy
    if tier not in policy.allowed_tiers:
        raise PermissionError('SUBSCRIPTION_TIER_REQUIRED')
    return policy


def ensure_metered_stream_usage_options(payload: dict, metadata: dict | None) -> None:
    policy = (metadata or {}).get('subscription_policy') or {}
    if not policy or policy.get('quota_mode') != 'metered' or not payload.get('stream'):
        return

    stream_options = payload.get('stream_options')
    if not isinstance(stream_options, dict):
        stream_options = {}

    stream_options['include_usage'] = True
    payload['stream_options'] = stream_options


def filter_models_for_subscription(models: list[dict], *, tier: str, is_admin: bool) -> list[dict]:
    if is_admin:
        return models
    filtered = []
    for item in models:
        try:
            assert_model_subscription_access(item, tier=tier, is_admin=False)
            filtered.append(item)
        except PermissionError:
            continue
    return filtered


async def ensure_subscription_current(
    user_id: str,
    *,
    now: int | None = None,
    commit: bool = True,
    db: AsyncSession | None = None,
) -> UserSubscriptionModel:
    current_time = now if now is not None else now_ts()
    async with get_subscription_db_context(db) as session:
        try:
            await SubscriptionPlans.seed_defaults(db=session, commit=False)

            subscription = await UserSubscriptions.get_by_user_id(user_id, db=session)
            if not subscription:
                subscription = await UserSubscriptions.create_from_plan(
                    user_id=user_id,
                    plan_id=FREE_TIER,
                    starts_at=current_time,
                    expires_at=None,
                    source='default',
                    commit=False,
                    db=session,
                )
            elif subscription.expires_at is not None and current_time >= subscription.expires_at:
                previous = subscription
                subscription = await UserSubscriptions.create_from_plan(
                    user_id=user_id,
                    plan_id=FREE_TIER,
                    starts_at=current_time,
                    expires_at=None,
                    source='default',
                    commit=False,
                    db=session,
                )
                await SubscriptionLedgers.insert(
                    user_id=user_id,
                    event_type='auto_downgrade',
                    tier_before=previous.tier,
                    tier_after=subscription.tier,
                    plan_delta_micros=subscription.plan_balance_micros - previous.plan_balance_micros,
                    check_delta_micros=0,
                    plan_balance_after_micros=subscription.plan_balance_micros,
                    check_balance_after_micros=subscription.check_balance_micros,
                    reference_type='subscription',
                    reference_id=previous.id,
                    created_at=current_time,
                    commit=False,
                    db=session,
                )
            elif current_time >= subscription.next_reset_at:
                periods_elapsed = max(
                    1, (current_time - subscription.period_start_at) // period_seconds(subscription.period_days)
                )
                new_period_start = subscription.period_start_at + periods_elapsed * period_seconds(
                    subscription.period_days
                )
                new_period_end = new_period_start + period_seconds(subscription.period_days)
                before_plan = subscription.plan_balance_micros
                subscription.period_start_at = new_period_start
                subscription.period_end_at = new_period_end
                subscription.next_reset_at = new_period_end
                subscription.plan_balance_micros = subscription.plan_chatpoint_allowance_micros
                subscription.updated_at = current_time
                subscription = await UserSubscriptions.save(
                    subscription,
                    allow_balance_change=True,
                    commit=False,
                    db=session,
                )
                await SubscriptionLedgers.insert(
                    user_id=user_id,
                    event_type='period_reset',
                    tier_before=subscription.tier,
                    tier_after=subscription.tier,
                    plan_delta_micros=subscription.plan_balance_micros - before_plan,
                    check_delta_micros=0,
                    plan_balance_after_micros=subscription.plan_balance_micros,
                    check_balance_after_micros=subscription.check_balance_micros,
                    reference_type='subscription',
                    reference_id=subscription.id,
                    created_at=current_time,
                    commit=False,
                    db=session,
                )

            if commit:
                await session.commit()
            return subscription
        except Exception:
            if commit:
                await session.rollback()
            raise


class RedemptionResult(BaseModel):
    subscription: UserSubscriptionModel
    tier_before: str | None
    tier_after: str | None
    plan_delta_micros: int
    check_delta_micros: int


async def redeem_code(
    user_id: str,
    raw_code: str,
    *,
    now: int | None = None,
    db: AsyncSession | None = None,
    commit: bool = True,
) -> RedemptionResult:
    current_time = now if now is not None else now_ts()
    async with get_subscription_db_context(db) as session:
        try:
            code = await RedemptionCodes.get_by_raw_code(raw_code, db=session)
            if not code:
                raise ValueError('REDEMPTION_CODE_INVALID')
            if not code.is_active:
                raise ValueError('REDEMPTION_CODE_DISABLED')
            if code.expires_at is not None and current_time >= code.expires_at:
                raise ValueError('REDEMPTION_CODE_EXPIRED')
            if code.used_count >= code.max_uses:
                raise ValueError('REDEMPTION_CODE_EXHAUSTED')
            if await RedemptionRecords.get_by_code_and_user(code.id, user_id, db=session):
                raise ValueError('REDEMPTION_CODE_ALREADY_USED')

            subscription = await ensure_subscription_current(
                user_id,
                now=current_time,
                commit=False,
                db=session,
            )
            before = subscription
            tier_after = before.tier
            expires_after = before.expires_at
            plan_delta = code.plan_chatpoint_micros
            check_delta = code.check_chatpoint_micros

            if code.tier and code.duration_days:
                plan = await SubscriptionPlans.get_plan_by_id(code.tier, db=session)
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
                        commit=False,
                        db=session,
                    )
                    tier_after = subscription.tier

            subscription = await UserSubscriptions.adjust_balances(
                user_id,
                plan_delta_micros=plan_delta,
                check_delta_micros=check_delta,
                event_type='redemption',
                created_by=None,
                reference_type='redemption',
                reference_id=code.id,
                metadata={'benefit_type': code.benefit_type},
                commit=False,
                db=session,
            )
            await RedemptionCodes.increment_used_count(code.id, db=session, commit=False)
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
                db=session,
                commit=False,
            )
            if commit:
                await session.commit()
            return RedemptionResult(
                subscription=subscription,
                tier_before=before.tier,
                tier_after=tier_after,
                plan_delta_micros=plan_delta,
                check_delta_micros=check_delta,
            )
        except Exception:
            if commit:
                await session.rollback()
            raise


def extract_token_usage(usage: dict | None) -> tuple[int, int, int]:
    usage = usage or {}
    input_tokens = int(usage.get('input_tokens') or usage.get('prompt_tokens') or 0)
    output_tokens = int(usage.get('output_tokens') or usage.get('completion_tokens') or 0)
    total_tokens = int(usage.get('total_tokens') or input_tokens + output_tokens)
    return input_tokens, output_tokens, total_tokens


async def assert_chatpoint_available(
    user_id: str, *, quota_mode: str, is_admin: bool, db: AsyncSession | None = None
) -> UserSubscriptionModel | None:
    if is_admin or quota_mode == 'unlimited':
        return None

    subscription = await UserSubscriptions.get_by_user_id(user_id, db=db)
    if subscription is None:
        subscription = await ensure_subscription_current(user_id, db=db)
    if subscription.plan_balance_micros + subscription.check_balance_micros <= 0:
        raise PermissionError('CHATPOINT_BALANCE_EXHAUSTED')
    return subscription


def _reservation_request(value: ChatpointReservationRequest | dict) -> ChatpointReservationRequest:
    return value if isinstance(value, ChatpointReservationRequest) else ChatpointReservationRequest.model_validate(value)


def _reservation_resize_request(
    value: ChatpointReservationResizeRequest | dict,
) -> ChatpointReservationResizeRequest:
    return (
        value
        if isinstance(value, ChatpointReservationResizeRequest)
        else ChatpointReservationResizeRequest.model_validate(value)
    )


def _assert_reservation_retry_matches(
    reservation: SubscriptionReservationModel,
    request: ChatpointReservationRequest,
) -> None:
    if (
        reservation.request_id != request.request_id
        or reservation.model_id != request.model_id
        or reservation.reserved_micros != request.amount_micros
    ):
        raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_CONFLICT')


async def reserve_chatpoint_batch(
    user_id: str,
    requests: list[ChatpointReservationRequest | dict],
    *,
    now: int | None = None,
    cap_micros: int | None = None,
    cap_since: int | None = None,
    cap_media_type: str | None = None,
    cap_model_prefix: str | None = None,
    db: AsyncSession | None = None,
) -> list[ChatpointReservationGrant]:
    """Atomically reserve every fanout item or reject the complete batch."""

    normalized = [_reservation_request(item) for item in requests]
    if not normalized:
        return []

    keys = [reservation_idempotency_key(user_id, item.request_id, item.model_id) for item in normalized]
    if len(set(keys)) != len(keys):
        raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_DUPLICATE_REQUEST')

    current_time = now if now is not None else now_ts()
    if any(item.expires_at is not None and item.expires_at <= current_time for item in normalized):
        raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_ALREADY_EXPIRED')

    async with get_subscription_db_context(db) as session:
        try:
            await ensure_subscription_current(user_id, now=current_time, commit=False, db=session)
            subscription = await UserSubscriptions.lock_for_billing(user_id, db=session)
            if subscription.plan_balance_micros < 0 or subscription.check_balance_micros < 0:
                raise ChatpointReservationConflictError('CHATPOINT_BALANCE_INVALID')

            existing = await SubscriptionReservations.get_by_idempotency_keys(keys, db=session)
            new_items: list[tuple[ChatpointReservationRequest, str]] = []
            for item, key in zip(normalized, keys):
                prior = existing.get(key)
                if prior is not None:
                    _assert_reservation_retry_matches(prior, item)
                    if prior.status != 'active':
                        raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_ALREADY_TERMINAL')
                    if prior.expires_at is not None and prior.expires_at <= current_time:
                        raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_EXPIRED')
                else:
                    new_items.append((item, key))

            if existing and new_items:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_PARTIAL_BATCH_RETRY')

            requested_micros = sum(item.amount_micros for item, _ in new_items)
            if cap_micros is not None and requested_micros:
                if cap_micros < 0 or cap_since is None or not cap_media_type or not cap_model_prefix:
                    raise ValueError(
                        'reservation cap requires a non-negative amount, start, media type, and model prefix'
                    )
                usage_result = await session.execute(
                    select(func.coalesce(func.sum(SubscriptionUsage.cost_micros), 0)).where(
                        SubscriptionUsage.user_id == user_id,
                        SubscriptionUsage.usage_type == cap_media_type,
                        SubscriptionUsage.created_at >= cap_since,
                    )
                )
                active_result = await session.execute(
                    select(func.coalesce(func.sum(SubscriptionReservation.reserved_micros), 0)).where(
                        SubscriptionReservation.user_id == user_id,
                        SubscriptionReservation.status == 'active',
                        or_(
                            SubscriptionReservation.model_id.like(f'{cap_model_prefix}%'),
                            SubscriptionReservation.meta.contains(
                                {'media_billing': True, 'media_type': cap_media_type}
                            ),
                        ),
                    )
                )
                committed_micros = int(usage_result.scalar_one() or 0) + int(active_result.scalar_one() or 0)
                if committed_micros + requested_micros > cap_micros:
                    raise ChatpointReservationCapExceededError(
                        requested_micros=requested_micros,
                        committed_micros=committed_micros,
                        cap_micros=cap_micros,
                    )
            available_micros = subscription.plan_balance_micros + subscription.check_balance_micros
            if requested_micros > available_micros:
                raise ChatpointReservationInsufficientError(
                    requested_micros=requested_micros,
                    available_micros=available_micros,
                )

            results = {
                key: ChatpointReservationGrant(reservation=reservation, acquired=False)
                for key, reservation in existing.items()
            }
            plan_balance = subscription.plan_balance_micros
            check_balance = subscription.check_balance_micros
            for item, key in new_items:
                debit = debit_balances(plan_balance, check_balance, item.amount_micros)
                if debit.unpaid_cost_micros:
                    raise ChatpointReservationInsufficientError(
                        requested_micros=requested_micros,
                        available_micros=available_micros,
                    )
                reservation = await SubscriptionReservations.insert(
                    user_id=user_id,
                    request_id=item.request_id,
                    model_id=item.model_id,
                    idempotency_key=key,
                    period_start_at=subscription.period_start_at,
                    reserved_micros=item.amount_micros,
                    reserved_plan_micros=debit.plan_cost_micros,
                    reserved_check_micros=debit.check_cost_micros,
                    expires_at=item.expires_at,
                    metadata=item.metadata,
                    created_at=current_time,
                    commit=False,
                    db=session,
                )
                await UserSubscriptions.adjust_balances(
                    user_id,
                    plan_delta_micros=-debit.plan_cost_micros,
                    check_delta_micros=-debit.check_cost_micros,
                    event_type='reservation_hold',
                    reference_type='subscription_reservation',
                    reference_id=reservation.id,
                    metadata={'model_id': item.model_id, 'reserved_micros': item.amount_micros},
                    created_by=None,
                    created_at=current_time,
                    commit=False,
                    db=session,
                )
                plan_balance = debit.plan_balance_after_micros
                check_balance = debit.check_balance_after_micros
                results[key] = ChatpointReservationGrant(reservation=reservation, acquired=True)

            await session.commit()
            return [results[key] for key in keys]
        except Exception:
            await session.rollback()
            raise


async def reserve_chatpoints(
    user_id: str,
    *,
    request_id: str,
    model_id: str,
    amount_micros: int,
    expires_at: int | None = None,
    metadata: dict | None = None,
    now: int | None = None,
    cap_micros: int | None = None,
    cap_since: int | None = None,
    cap_media_type: str | None = None,
    cap_model_prefix: str | None = None,
    db: AsyncSession | None = None,
) -> ChatpointReservationGrant:
    reservations = await reserve_chatpoint_batch(
        user_id,
        [
            ChatpointReservationRequest(
                request_id=request_id,
                model_id=model_id,
                amount_micros=amount_micros,
                expires_at=expires_at,
                metadata=metadata,
            )
        ],
        now=now,
        cap_micros=cap_micros,
        cap_since=cap_since,
        cap_media_type=cap_media_type,
        cap_model_prefix=cap_model_prefix,
        db=db,
    )
    return reservations[0]


async def resize_chatpoint_reservation_batch(
    user_id: str,
    requests: list[ChatpointReservationResizeRequest | dict],
    *,
    now: int | None = None,
    db: AsyncSession | None = None,
) -> list[SubscriptionReservationModel]:
    """Atomically reconcile a prepared fanout batch to its final payload cost."""

    normalized = [_reservation_resize_request(item) for item in requests]
    if not normalized:
        return []
    reservation_ids = [item.reservation_id for item in normalized]
    if len(set(reservation_ids)) != len(reservation_ids):
        raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_DUPLICATE_RESIZE')

    current_time = now if now is not None else now_ts()
    async with get_subscription_db_context(db) as session:
        try:
            await ensure_subscription_current(user_id, now=current_time, commit=False, db=session)
            subscription = await UserSubscriptions.lock_for_billing(user_id, db=session)
            locked_by_id = {}
            for reservation_id in sorted(reservation_ids):
                reservation = await SubscriptionReservations.lock_by_id(reservation_id, db=session)
                if reservation is None:
                    raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
                locked_by_id[reservation_id] = reservation

            reservations = []
            for item in normalized:
                reservation = locked_by_id[item.reservation_id]
                if (
                    reservation.user_id != user_id
                    or reservation.request_id != item.request_id
                    or reservation.model_id != item.model_id
                ):
                    raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_RESIZE_MISMATCH')
                if reservation.status != 'active':
                    raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_ACTIVE')
                if reservation.expires_at is not None and reservation.expires_at <= current_time:
                    raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_EXPIRED')
                if reservation.period_start_at != subscription.period_start_at:
                    raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_PERIOD_CHANGED')
                reservations.append(reservation)

            old_plan_total = sum(item.reserved_plan_micros for item in reservations)
            old_check_total = sum(item.reserved_check_micros for item in reservations)
            plan_pool = subscription.plan_balance_micros + old_plan_total
            check_pool = subscription.check_balance_micros + old_check_total
            requested_total = sum(item.amount_micros for item in normalized)
            if requested_total > plan_pool + check_pool:
                raise ChatpointReservationInsufficientError(
                    requested_micros=requested_total,
                    available_micros=plan_pool + check_pool,
                )

            allocations = []
            remaining_plan = plan_pool
            remaining_check = check_pool
            for item in normalized:
                plan_amount = min(remaining_plan, item.amount_micros)
                check_amount = item.amount_micros - plan_amount
                if check_amount > remaining_check:
                    raise ChatpointReservationInsufficientError(
                        requested_micros=requested_total,
                        available_micros=plan_pool + check_pool,
                    )
                remaining_plan -= plan_amount
                remaining_check -= check_amount
                allocations.append((plan_amount, check_amount))

            new_plan_total = sum(item[0] for item in allocations)
            new_check_total = sum(item[1] for item in allocations)
            plan_delta = old_plan_total - new_plan_total
            check_delta = old_check_total - new_check_total
            if plan_delta or check_delta:
                await UserSubscriptions.adjust_balances(
                    user_id,
                    plan_delta_micros=plan_delta,
                    check_delta_micros=check_delta,
                    event_type='reservation_resize',
                    reference_type='subscription_reservation_batch',
                    reference_id=reservation_ids[0],
                    metadata={
                        'reservation_ids': reservation_ids,
                        'requested_micros': requested_total,
                    },
                    created_by=None,
                    created_at=current_time,
                    commit=False,
                    db=session,
                )

            updated_items = []
            for item, reservation, (plan_amount, check_amount) in zip(normalized, reservations, allocations):
                reservation_metadata = dict(reservation.metadata or {})
                reservation_metadata.update(item.metadata or {})
                reservation_metadata['reconciled'] = True
                updated_items.append(
                    await SubscriptionReservations.update_state(
                        reservation.id,
                        values={
                            'reserved_micros': item.amount_micros,
                            'reserved_plan_micros': plan_amount,
                            'reserved_check_micros': check_amount,
                            'expires_at': max(reservation.expires_at or 0, item.expires_at or 0) or None,
                            'meta': reservation_metadata,
                            'updated_at': current_time,
                        },
                        commit=False,
                        db=session,
                    )
                )

            await session.commit()
            return updated_items
        except Exception:
            await session.rollback()
            raise


async def extend_chatpoint_reservation(
    reservation_id: str,
    *,
    user_id: str,
    request_id: str,
    model_id: str,
    amount_micros: int,
    expires_at: int | None = None,
    metadata: dict | None = None,
    now: int | None = None,
    db: AsyncSession | None = None,
) -> SubscriptionReservationModel:
    """Atomically add budget for one more provider dispatch."""

    if amount_micros < 0:
        raise ValueError('amount_micros must be greater than or equal to 0')
    current_time = now if now is not None else now_ts()

    async with get_subscription_db_context(db) as session:
        try:
            reservation = await SubscriptionReservations.get_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
            if (
                reservation.user_id != user_id
                or reservation.request_id != request_id
                or reservation.model_id != model_id
            ):
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_EXTENSION_MISMATCH')

            await ensure_subscription_current(user_id, now=current_time, commit=False, db=session)
            subscription = await UserSubscriptions.lock_for_billing(user_id, db=session)
            reservation = await SubscriptionReservations.lock_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
            if reservation.status != 'active':
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_ACTIVE')

            if reservation.expires_at is not None and reservation.expires_at <= current_time:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_EXPIRED')

            same_period = reservation.period_start_at == subscription.period_start_at
            debit = debit_balances(
                subscription.plan_balance_micros if same_period else 0,
                subscription.check_balance_micros,
                amount_micros,
            )
            if debit.unpaid_cost_micros:
                raise ChatpointReservationInsufficientError(
                    requested_micros=amount_micros,
                    available_micros=debit.plan_cost_micros + debit.check_cost_micros,
                )

            if amount_micros:
                await UserSubscriptions.adjust_balances(
                    user_id,
                    plan_delta_micros=-debit.plan_cost_micros,
                    check_delta_micros=-debit.check_cost_micros,
                    event_type='reservation_hold',
                    reference_type='subscription_reservation',
                    reference_id=reservation.id,
                    metadata={
                        'model_id': model_id,
                        'reserved_micros': amount_micros,
                        'extension': True,
                        'cross_period': not same_period,
                    },
                    created_by=None,
                    created_at=current_time,
                    commit=False,
                    db=session,
                )

            reservation_metadata = dict(reservation.metadata or {})
            reservation_metadata.update(metadata or {})
            reservation_metadata['provider_call_count'] = int(
                reservation_metadata.get('provider_call_count') or 1
            ) + 1
            updated = await SubscriptionReservations.update_state(
                reservation.id,
                values={
                    'reserved_micros': reservation.reserved_micros + amount_micros,
                    'reserved_plan_micros': reservation.reserved_plan_micros + debit.plan_cost_micros,
                    'reserved_check_micros': reservation.reserved_check_micros + debit.check_cost_micros,
                    'expires_at': max(
                        reservation.expires_at or 0,
                        expires_at or 0,
                    )
                    or None,
                    'meta': reservation_metadata,
                    'updated_at': current_time,
                },
                commit=False,
                db=session,
            )
            await session.commit()
            return updated
        except Exception:
            await session.rollback()
            raise


async def renew_chatpoint_reservation(
    reservation_id: str,
    *,
    expires_at: int,
    now: int | None = None,
    db: AsyncSession | None = None,
) -> SubscriptionReservationModel:
    """Renew the lease for an in-flight provider request."""

    current_time = now if now is not None else now_ts()
    if expires_at <= current_time:
        raise ValueError('expires_at must be in the future')
    async with get_subscription_db_context(db) as session:
        try:
            reservation = await SubscriptionReservations.lock_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
            if reservation.status != 'active':
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_ACTIVE')
            renewed = await SubscriptionReservations.update_state(
                reservation.id,
                values={
                    'expires_at': expires_at,
                    'updated_at': current_time,
                },
                commit=False,
                db=session,
            )
            await session.commit()
            return renewed
        except Exception:
            await session.rollback()
            raise


def get_reservation_id(
    grant: str | ChatpointReservationGrant | SubscriptionReservationModel,
) -> str:
    if isinstance(grant, str):
        return grant
    reservation = getattr(grant, 'reservation', None)
    if reservation is not None:
        return reservation.id
    return grant.id


async def settle_chatpoint_reservation(
    reservation_id: str | ChatpointReservationGrant | SubscriptionReservationModel,
    *,
    actual_cost_micros: int,
    allow_partial: bool = False,
    now: int | None = None,
    commit: bool = True,
    db: AsyncSession | None = None,
) -> SubscriptionReservationModel:
    reservation_id = get_reservation_id(reservation_id)
    if actual_cost_micros < 0:
        raise ValueError('actual_cost_micros must be greater than or equal to 0')

    current_time = now if now is not None else now_ts()
    async with get_subscription_db_context(db) as session:
        try:
            reservation = await SubscriptionReservations.get_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')

            await ensure_subscription_current(
                reservation.user_id,
                now=current_time,
                commit=False,
                db=session,
            )
            subscription = await UserSubscriptions.lock_for_billing(reservation.user_id, db=session)
            reservation = await SubscriptionReservations.lock_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
            if reservation.status in {'settled', 'partially_settled'}:
                if reservation.actual_cost_micros != actual_cost_micros:
                    raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_SETTLEMENT_CONFLICT')
                if commit:
                    await session.commit()
                return reservation
            if reservation.status != 'active':
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_ACTIVE')

            pending_marker = _pending_settlement_metadata(reservation)

            base_paid_micros = min(actual_cost_micros, reservation.reserved_micros)
            base_plan_micros = min(reservation.reserved_plan_micros, base_paid_micros)
            base_check_micros = base_paid_micros - base_plan_micros
            unused_plan_micros = reservation.reserved_plan_micros - base_plan_micros
            unused_check_micros = reservation.reserved_check_micros - base_check_micros
            same_period = reservation.period_start_at == subscription.period_start_at
            refunded_plan_micros = unused_plan_micros if same_period else 0
            forfeited_plan_micros = unused_plan_micros - refunded_plan_micros
            refunded_check_micros = unused_check_micros

            overage_micros = max(actual_cost_micros - reservation.reserved_micros, 0)
            overage = debit_balances(
                subscription.plan_balance_micros,
                subscription.check_balance_micros,
                overage_micros,
            )
            if overage.unpaid_cost_micros and not allow_partial:
                raise ChatpointReservationInsufficientError(
                    requested_micros=overage_micros,
                    available_micros=overage.plan_cost_micros + overage.check_cost_micros,
                )

            settled_plan_micros = base_plan_micros + overage.plan_cost_micros
            settled_check_micros = base_check_micros + overage.check_cost_micros
            status = 'partially_settled' if overage.unpaid_cost_micros else 'settled'
            subscription = await UserSubscriptions.adjust_balances(
                reservation.user_id,
                plan_delta_micros=refunded_plan_micros - overage.plan_cost_micros,
                check_delta_micros=refunded_check_micros - overage.check_cost_micros,
                event_type='reservation_settlement',
                reference_type='subscription_reservation',
                reference_id=reservation.id,
                metadata={
                    'actual_cost_micros': actual_cost_micros,
                    'unpaid_cost_micros': overage.unpaid_cost_micros,
                },
                created_by=None,
                created_at=current_time,
                commit=False,
                db=session,
            )
            settlement_metadata = dict(reservation.metadata or {})
            if pending_marker is not None:
                subscription = await _decrement_pending_settlement_count(
                    reservation.user_id,
                    subscription,
                    now=current_time,
                    db=session,
                )
                settlement_metadata.pop(PENDING_SETTLEMENT_KEY, None)
            settled = await SubscriptionReservations.update_state(
                reservation.id,
                values={
                    'status': status,
                    'actual_cost_micros': actual_cost_micros,
                    'settled_plan_micros': settled_plan_micros,
                    'settled_check_micros': settled_check_micros,
                    'refunded_plan_micros': refunded_plan_micros,
                    'refunded_check_micros': refunded_check_micros,
                    'forfeited_plan_micros': forfeited_plan_micros,
                    'unpaid_cost_micros': overage.unpaid_cost_micros,
                    'meta': settlement_metadata or None,
                    'settled_at': current_time,
                    'updated_at': current_time,
                },
                commit=False,
                db=session,
            )
            if commit:
                await session.commit()
            return settled
        except Exception:
            await session.rollback()
            raise


async def release_chatpoint_reservation(
    reservation_id: str | ChatpointReservationGrant | SubscriptionReservationModel,
    *,
    reason: str = 'released',
    expired: bool = False,
    now: int | None = None,
    commit: bool = True,
    db: AsyncSession | None = None,
) -> SubscriptionReservationModel:
    reservation_id = get_reservation_id(reservation_id)
    current_time = now if now is not None else now_ts()
    async with get_subscription_db_context(db) as session:
        try:
            reservation = await SubscriptionReservations.get_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')

            await ensure_subscription_current(
                reservation.user_id,
                now=current_time,
                commit=False,
                db=session,
            )
            subscription = await UserSubscriptions.lock_for_billing(reservation.user_id, db=session)
            reservation = await SubscriptionReservations.lock_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
            if reservation.status in {'released', 'expired'}:
                if commit:
                    await session.commit()
                return reservation
            if reservation.status != 'active':
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_ACTIVE')
            if expired and (reservation.expires_at is None or reservation.expires_at > current_time):
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_EXPIRED')

            pending_marker = _pending_settlement_metadata(reservation)
            if expired and pending_marker is not None:
                # Pending rows are owned by the durable settlement worker. A
                # cleanup pass must never turn a recoverable job terminal.
                if commit:
                    await session.commit()
                return reservation

            same_period = reservation.period_start_at == subscription.period_start_at
            refunded_plan_micros = reservation.reserved_plan_micros if same_period else 0
            forfeited_plan_micros = reservation.reserved_plan_micros - refunded_plan_micros
            subscription = await UserSubscriptions.adjust_balances(
                reservation.user_id,
                plan_delta_micros=refunded_plan_micros,
                check_delta_micros=reservation.reserved_check_micros,
                event_type='reservation_expired' if expired else 'reservation_release',
                reference_type='subscription_reservation',
                reference_id=reservation.id,
                metadata={'reason': reason},
                created_by=None,
                created_at=current_time,
                commit=False,
                db=session,
            )
            release_metadata = dict(reservation.metadata or {})
            if pending_marker is not None:
                subscription = await _decrement_pending_settlement_count(
                    reservation.user_id,
                    subscription,
                    now=current_time,
                    db=session,
                )
                release_metadata.pop(PENDING_SETTLEMENT_KEY, None)
            released = await SubscriptionReservations.update_state(
                reservation.id,
                values={
                    'status': 'expired' if expired else 'released',
                    'refunded_plan_micros': refunded_plan_micros,
                    'refunded_check_micros': reservation.reserved_check_micros,
                    'forfeited_plan_micros': forfeited_plan_micros,
                    'release_reason': reason,
                    'meta': release_metadata or None,
                    'released_at': current_time,
                    'updated_at': current_time,
                },
                commit=False,
                db=session,
            )
            if commit:
                await session.commit()
            return released
        except Exception:
            await session.rollback()
            raise


async def release_expired_chatpoint_reservations(
    *,
    now: int | None = None,
    limit: int = 100,
    db: AsyncSession | None = None,
) -> list[SubscriptionReservationModel]:
    current_time = now if now is not None else now_ts()
    reservation_ids = await SubscriptionReservations.list_expired_active_ids(
        now=current_time,
        limit=limit,
        db=db,
    )
    released = []
    for reservation_id in reservation_ids:
        try:
            reservation = await SubscriptionReservations.get_by_id(reservation_id, db=db)
            if reservation is None or _pending_settlement_metadata(reservation) is not None:
                continue
            released.append(
                await release_chatpoint_reservation(
                    reservation_id,
                    reason='reservation expired',
                    expired=True,
                    now=current_time,
                    db=db,
                )
            )
        except ChatpointReservationConflictError:
            continue
    return released


async def bill_model_usage(
    *,
    user_id: str,
    model_id: str,
    quota_mode: str,
    usage_multiplier: str,
    usage: dict | None,
    metadata: dict,
    is_admin: bool,
    pricing: dict | None = None,
    request_id: str | None = None,
    reservation_id: str | None = None,
    allow_partial_reservation: bool = False,
    charge_reserved_on_missing_usage: bool = False,
    client_ip: str | None = None,
    first_token_latency_ms: int | None = None,
    total_duration_ms: int | None = None,
    now: int | None = None,
    db: AsyncSession | None = None,
):
    current_time = now if now is not None else now_ts()
    resolved_request_id = request_id or metadata.get('request_id')
    legacy_idempotency_key = billing_idempotency_key(user_id, resolved_request_id)
    idempotency_key = (
        reservation_billing_idempotency_key(reservation_id)
        if reservation_id is not None
        else legacy_idempotency_key
    )
    policy = ModelSubscriptionPolicy.model_validate(
        {'usage_multiplier': usage_multiplier, **(pricing or {})}
    )
    normalized = normalize_billable_usage(usage)
    prices = {
        'input_chatpoint_per_million': policy.input_chatpoint_per_million,
        'output_chatpoint_per_million': policy.output_chatpoint_per_million,
        'cache_creation_chatpoint_per_million': policy.cache_creation_chatpoint_per_million,
        'cache_read_chatpoint_per_million': policy.cache_read_chatpoint_per_million,
    }
    stored_metadata = dict(metadata or {})
    stored_metadata.pop('client_ip', None)

    async with get_subscription_db_context(db) as session:
        reservation = None
        if reservation_id is not None:
            reservation = await SubscriptionReservations.get_by_id(reservation_id, db=session)
            if reservation is None:
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_NOT_FOUND')
            if (
                reservation.user_id != user_id
                or reservation.model_id != model_id
                or (resolved_request_id is not None and reservation.request_id != resolved_request_id)
            ):
                raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_BILLING_MISMATCH')

            existing = await SubscriptionUsages.get_by_reservation_id(reservation_id, db=session)
            if existing:
                return existing

        if idempotency_key:
            existing = await SubscriptionUsages.get_by_idempotency_key(idempotency_key, db=session)
            if existing:
                return existing

        # Compatibility with usage rows created before reservation-scoped
        # billing keys. Only treat the old key as a duplicate for the same model.
        if reservation is not None and legacy_idempotency_key:
            legacy_existing = await SubscriptionUsages.get_by_idempotency_key(
                legacy_idempotency_key,
                db=session,
            )
            if legacy_existing and legacy_existing.model_id == model_id:
                if reservation.status == 'active':
                    await release_chatpoint_reservation(
                        reservation_id,
                        reason='legacy duplicate billing idempotency key',
                        now=current_time,
                        commit=False,
                        db=session,
                    )
                    await session.commit()
                return legacy_existing

        subscription = None
        if not is_admin:
            subscription = await ensure_subscription_current(
                user_id,
                now=current_time,
                commit=False,
                db=session,
            )
            if reservation_id is None:
                subscription = await UserSubscriptions.lock_for_billing(user_id, db=session)

        status = 'billed'
        cost_micros = 0
        plan_cost_micros = 0
        check_cost_micros = 0
        unpaid_cost_micros = 0
        plan_balance_after_micros = subscription.plan_balance_micros if subscription else None
        check_balance_after_micros = subscription.check_balance_micros if subscription else None

        if is_admin:
            status = 'admin_bypass'
        elif quota_mode == 'unlimited':
            status = 'unlimited'
        else:
            if normalized.usage_present:
                cost_micros = calculate_token_cost_micros(
                    input_tokens=normalized.input_tokens,
                    output_tokens=normalized.output_tokens,
                    cache_creation_tokens=normalized.cache_creation_tokens,
                    cache_read_tokens=normalized.cache_read_tokens,
                    **prices,
                )
                if normalized.unclassified_tokens:
                    conservative_price = max(Decimal(str(price)) for price in prices.values())
                    cost_micros += calculate_token_cost_micros(
                        input_tokens=normalized.unclassified_tokens,
                        output_tokens=0,
                        cache_creation_tokens=0,
                        cache_read_tokens=0,
                        input_chatpoint_per_million=conservative_price,
                        output_chatpoint_per_million=0,
                        cache_creation_chatpoint_per_million=0,
                        cache_read_chatpoint_per_million=0,
                    )
            else:
                status = 'missing_usage'
                if reservation is not None and charge_reserved_on_missing_usage:
                    cost_micros = reservation.reserved_micros
                    status = 'reserved_fallback'

            if reservation is not None:
                settlement = await settle_chatpoint_reservation(
                    reservation_id,
                    actual_cost_micros=cost_micros,
                    allow_partial=allow_partial_reservation,
                    now=current_time,
                    commit=False,
                    db=session,
                )
                plan_cost_micros = settlement.settled_plan_micros
                check_cost_micros = settlement.settled_check_micros
                unpaid_cost_micros = settlement.unpaid_cost_micros
                subscription = await UserSubscriptions.get_by_user_id(user_id, db=session)
                plan_balance_after_micros = subscription.plan_balance_micros
                check_balance_after_micros = subscription.check_balance_micros
                if unpaid_cost_micros:
                    status = 'partially_billed'
            elif cost_micros > 0:
                debit = debit_balances(
                    subscription.plan_balance_micros,
                    subscription.check_balance_micros,
                    cost_micros,
                )
                plan_cost_micros = debit.plan_cost_micros
                check_cost_micros = debit.check_cost_micros
                unpaid_cost_micros = debit.unpaid_cost_micros
                if plan_cost_micros or check_cost_micros:
                    updated = await UserSubscriptions.adjust_balances(
                        user_id,
                        plan_delta_micros=-plan_cost_micros,
                        check_delta_micros=-check_cost_micros,
                        event_type='usage_debit',
                        created_by=None,
                        commit=False,
                        db=session,
                    )
                    plan_balance_after_micros = updated.plan_balance_micros
                    check_balance_after_micros = updated.check_balance_micros
                if unpaid_cost_micros:
                    status = 'partially_billed'

        if reservation is not None and (is_admin or quota_mode == 'unlimited'):
            await release_chatpoint_reservation(
                reservation_id,
                reason='reservation not applicable to bypass billing',
                now=current_time,
                commit=False,
                db=session,
            )
            subscription = await UserSubscriptions.get_by_user_id(user_id, db=session)
            plan_balance_after_micros = subscription.plan_balance_micros
            check_balance_after_micros = subscription.check_balance_micros

        try:
            result = await SubscriptionUsages.insert(
                user_id=user_id,
                chat_id=metadata.get('chat_id'),
                message_id=metadata.get('message_id'),
                request_id=resolved_request_id,
                idempotency_key=idempotency_key,
                reservation_id=reservation_id,
                model_id=model_id,
                tier='admin' if is_admin else subscription.tier,
                quota_mode=quota_mode,
                usage_multiplier=usage_multiplier,
                input_tokens=normalized.input_tokens,
                output_tokens=normalized.output_tokens,
                cache_creation_tokens=normalized.cache_creation_tokens,
                cache_read_tokens=normalized.cache_read_tokens,
                total_tokens=normalized.total_tokens,
                **prices,
                cost_micros=cost_micros,
                plan_cost_micros=plan_cost_micros,
                check_cost_micros=check_cost_micros,
                unpaid_cost_micros=unpaid_cost_micros,
                plan_balance_after_micros=plan_balance_after_micros,
                check_balance_after_micros=check_balance_after_micros,
                first_token_latency_ms=first_token_latency_ms,
                total_duration_ms=total_duration_ms,
                client_ip=client_ip,
                status=status,
                raw_usage=normalized.raw_usage,
                metadata=stored_metadata,
                created_at=current_time,
                commit=False,
                db=session,
            )
            await session.commit()
            return result
        except IntegrityError:
            await session.rollback()
            if reservation_id:
                existing = await SubscriptionUsages.get_by_reservation_id(reservation_id, db=session)
                if existing:
                    return existing
            if idempotency_key:
                existing = await SubscriptionUsages.get_by_idempotency_key(idempotency_key, db=session)
                if existing:
                    if reservation_id is not None and existing.reservation_id != reservation_id:
                        raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_BILLING_MISMATCH')
                    return existing
            raise
        except Exception:
            await session.rollback()
            raise


async def process_pending_chatpoint_settlements(
    *,
    limit: int = 10,
    db: AsyncSession | None = None,
) -> int:
    """Settle completed chats from durable reservation metadata."""
    processed = 0
    for reservation in await list_pending_chatpoint_settlements(limit=limit, db=db):
        claimed = await claim_pending_chatpoint_settlement(reservation.id, db=db)
        if claimed is None:
            continue
        _, payload = claimed
        try:
            await bill_model_usage(
                user_id=str(payload.get('user_id') or reservation.user_id),
                model_id=str(payload.get('model_id') or reservation.model_id),
                quota_mode=str(payload.get('quota_mode') or 'metered'),
                usage_multiplier=str(payload.get('usage_multiplier') or '1'),
                usage=payload.get('usage'),
                metadata=payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {},
                is_admin=bool(payload.get('is_admin')),
                pricing=payload.get('pricing') if isinstance(payload.get('pricing'), dict) else None,
                request_id=payload.get('request_id'),
                reservation_id=reservation.id,
                allow_partial_reservation=True,
                charge_reserved_on_missing_usage=True,
                client_ip=payload.get('client_ip'),
                first_token_latency_ms=payload.get('first_token_latency_ms'),
                total_duration_ms=payload.get('total_duration_ms'),
                db=db,
            )
            processed += 1
        except Exception as exc:
            log.exception('Deferred Chatpoint settlement failed for %s', reservation.id)
            await mark_pending_chatpoint_settlement_retry(reservation.id, str(exc), db=db)
    return processed
