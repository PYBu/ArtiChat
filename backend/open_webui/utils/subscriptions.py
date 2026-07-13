from __future__ import annotations

from decimal import Decimal, InvalidOperation

from open_webui.models.subscriptions import (
    CHATPOWER_TIER,
    FREE_TIER,
    PLUS_TIER,
    RedemptionCodes,
    RedemptionRecords,
    SubscriptionLedgers,
    SubscriptionPlans,
    SubscriptionUsages,
    UserSubscriptionModel,
    UserSubscriptions,
    calculate_cost_micros,
    calculate_token_cost_micros,
    debit_balances,
    get_subscription_db_context,
    now_ts,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

SECONDS_PER_DAY = 24 * 60 * 60


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
            cache_read_tokens = max(int(details.get('cached_tokens') or 0), 0)
            cache_is_included_in_input = True
            break

    normal_input_tokens = max(input_tokens - cache_read_tokens, 0) if cache_is_included_in_input else input_tokens
    if normal_input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens == 0:
        normal_input_tokens = _usage_int(raw_usage, 'total_tokens')
    total_tokens = normal_input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens
    return NormalizedBillableUsage(
        input_tokens=normal_input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        total_tokens=total_tokens,
        raw_usage=raw_usage,
        usage_present=bool(raw_usage),
    )


def get_request_client_ip(request) -> str | None:
    client = getattr(request, 'client', None)
    host = getattr(client, 'host', None)
    return str(host) if host else None


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
    client_ip: str | None = None,
    first_token_latency_ms: int | None = None,
    total_duration_ms: int | None = None,
    now: int | None = None,
    db: AsyncSession | None = None,
):
    current_time = now if now is not None else now_ts()
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
        subscription = None
        if not is_admin:
            subscription = await ensure_subscription_current(user_id, now=current_time, db=session)
            subscription = await UserSubscriptions.lock_for_billing(user_id, db=session)

        status = 'billed'
        cost_micros = 0
        plan_cost_micros = 0
        check_cost_micros = 0
        plan_balance_after_micros = subscription.plan_balance_micros if subscription else None
        check_balance_after_micros = subscription.check_balance_micros if subscription else None

        if is_admin:
            status = 'admin_bypass'
        elif quota_mode == 'unlimited':
            status = 'unlimited'
        elif not normalized.usage_present:
            status = 'missing_usage'
        else:
            cost_micros = calculate_token_cost_micros(
                input_tokens=normalized.input_tokens,
                output_tokens=normalized.output_tokens,
                cache_creation_tokens=normalized.cache_creation_tokens,
                cache_read_tokens=normalized.cache_read_tokens,
                **prices,
            )
            if cost_micros > 0:
                debit = debit_balances(
                    subscription.plan_balance_micros,
                    subscription.check_balance_micros,
                    cost_micros,
                )
                updated = await UserSubscriptions.adjust_balances(
                    user_id,
                    plan_delta_micros=-debit.plan_cost_micros,
                    check_delta_micros=-debit.check_cost_micros,
                    event_type='usage_debit',
                    created_by=None,
                    commit=False,
                    db=session,
                )
                plan_cost_micros = debit.plan_cost_micros
                check_cost_micros = debit.check_cost_micros
                plan_balance_after_micros = updated.plan_balance_micros
                check_balance_after_micros = updated.check_balance_micros

        try:
            result = await SubscriptionUsages.insert(
                user_id=user_id,
                chat_id=metadata.get('chat_id'),
                message_id=metadata.get('message_id'),
                request_id=request_id or metadata.get('request_id'),
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
        except Exception:
            await session.rollback()
            raise
