from __future__ import annotations

import hashlib
import re
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Any

from open_webui.internal.db import Base, get_async_db_context
from open_webui.models.users import User
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Index,
    Integer,
    String,
    Text,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

CHATPOINT_MICROS = 1_000_000
TOKENS_PER_CHATPOINT = 10_000
TOKENS_PER_MILLION = 1_000_000

FREE_TIER = 'free'
PLUS_TIER = 'plus'
CHATPOWER_TIER = 'chatpower'
TIER_RANKS = {FREE_TIER: 0, PLUS_TIER: 1, CHATPOWER_TIER: 2}
DEFAULT_PLAN_CHATPOINTS = {FREE_TIER: Decimal('100'), PLUS_TIER: Decimal('3000'), CHATPOWER_TIER: Decimal('10000')}
LEGACY_PLAN_CHATPOINTS = {FREE_TIER: [Decimal('10')], PLUS_TIER: [Decimal('100')], CHATPOWER_TIER: [Decimal('500')]}
DEFAULT_PERIOD_DAYS = 30
_SKIP_JSON_VALUE = object()


@dataclass(frozen=True)
class DebitResult:
    plan_cost_micros: int
    check_cost_micros: int
    plan_balance_after_micros: int
    check_balance_after_micros: int
    unpaid_cost_micros: int


def now_ts() -> int:
    return int(time.time())


def chatpoint_to_micros(value: Decimal | int | str) -> int:
    decimal_value = Decimal(str(value))
    return int((decimal_value * CHATPOINT_MICROS).to_integral_value(rounding=ROUND_CEILING))


def micros_to_chatpoint(value: int) -> Decimal:
    return Decimal(value) / Decimal(CHATPOINT_MICROS)


def calculate_cost_micros(total_tokens: int, usage_multiplier: str | Decimal | int = '1') -> int:
    multiplier = Decimal(str(usage_multiplier))
    if multiplier < 0:
        raise ValueError('usage_multiplier must be greater than or equal to 0')
    if total_tokens <= 0 or multiplier == 0:
        return 0

    raw_chatpoints = Decimal(total_tokens) / Decimal(TOKENS_PER_CHATPOINT) * multiplier
    return chatpoint_to_micros(raw_chatpoints)


def calculate_token_cost_micros(
    *,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    input_chatpoint_per_million: str | Decimal | int,
    output_chatpoint_per_million: str | Decimal | int,
    cache_creation_chatpoint_per_million: str | Decimal | int,
    cache_read_chatpoint_per_million: str | Decimal | int,
) -> int:
    token_counts = [input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens]
    prices = [
        Decimal(str(input_chatpoint_per_million)),
        Decimal(str(output_chatpoint_per_million)),
        Decimal(str(cache_creation_chatpoint_per_million)),
        Decimal(str(cache_read_chatpoint_per_million)),
    ]
    if any(value < 0 for value in token_counts):
        raise ValueError('token counts must be greater than or equal to 0')
    if any(not value.is_finite() or value < 0 for value in prices):
        raise ValueError('token prices must be greater than or equal to 0')

    raw_chatpoints = sum(Decimal(tokens) * price for tokens, price in zip(token_counts, prices)) / Decimal(
        TOKENS_PER_MILLION
    )
    return chatpoint_to_micros(raw_chatpoints)


def debit_balances(plan_balance_micros: int, check_balance_micros: int, cost_micros: int) -> DebitResult:
    if cost_micros <= 0:
        return DebitResult(
            plan_cost_micros=0,
            check_cost_micros=0,
            plan_balance_after_micros=plan_balance_micros,
            check_balance_after_micros=check_balance_micros,
            unpaid_cost_micros=0,
        )

    available_plan = max(plan_balance_micros, 0)
    available_check = max(check_balance_micros, 0)
    paid_cost = min(cost_micros, available_plan + available_check)
    plan_cost = min(available_plan, paid_cost)
    check_cost = min(available_check, paid_cost - plan_cost)

    return DebitResult(
        plan_cost_micros=plan_cost,
        check_cost_micros=check_cost,
        plan_balance_after_micros=plan_balance_micros - plan_cost,
        check_balance_after_micros=check_balance_micros - check_cost,
        unpaid_cost_micros=cost_micros - paid_cost,
    )


def _json_safe_value(value: Any, *, depth: int = 0, seen: set[int] | None = None) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if callable(value) or depth > 8:
        return _SKIP_JSON_VALUE

    seen = seen or set()

    if isinstance(value, dict):
        value_id = id(value)
        if value_id in seen:
            return _SKIP_JSON_VALUE
        seen.add(value_id)
        result = {}
        for key, item in value.items():
            safe_item = _json_safe_value(item, depth=depth + 1, seen=seen)
            if safe_item is not _SKIP_JSON_VALUE:
                result[str(key)] = safe_item
        seen.remove(value_id)
        return result

    if isinstance(value, (list, tuple, set)):
        value_id = id(value)
        if value_id in seen:
            return _SKIP_JSON_VALUE
        seen.add(value_id)
        result = []
        for item in value:
            safe_item = _json_safe_value(item, depth=depth + 1, seen=seen)
            if safe_item is not _SKIP_JSON_VALUE:
                result.append(safe_item)
        seen.remove(value_id)
        return result

    return _SKIP_JSON_VALUE


def json_safe_metadata(metadata: dict | None) -> dict | None:
    if metadata is None:
        return None
    safe = _json_safe_value(metadata)
    return safe if isinstance(safe, dict) else None


@asynccontextmanager
async def get_subscription_db_context(db: AsyncSession | None = None) -> AsyncIterator[AsyncSession]:
    if db is not None:
        yield db
    else:
        async with get_async_db_context() as session:
            yield session


class SubscriptionPlan(Base):
    __tablename__ = 'subscription_plan'

    id = Column(Text, primary_key=True)
    display_name = Column(Text, nullable=False)
    tier_rank = Column(Integer, nullable=False)
    period_days = Column(Integer, nullable=False, default=DEFAULT_PERIOD_DAYS)
    plan_chatpoint_allowance_micros = Column(BigInteger, nullable=False)
    description = Column(Text, nullable=True)
    features = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class UserSubscription(Base):
    __tablename__ = 'user_subscription'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, unique=True, index=True)
    tier = Column(Text, nullable=False)
    tier_rank = Column(Integer, nullable=False)
    display_name = Column(Text, nullable=False)
    period_days = Column(Integer, nullable=False)
    plan_chatpoint_allowance_micros = Column(BigInteger, nullable=False)
    plan_balance_micros = Column(BigInteger, nullable=False)
    check_balance_micros = Column(BigInteger, nullable=False, default=0)
    balance_version = Column(BigInteger, nullable=False, default=0)
    starts_at = Column(BigInteger, nullable=False)
    expires_at = Column(BigInteger, nullable=True)
    period_start_at = Column(BigInteger, nullable=False)
    period_end_at = Column(BigInteger, nullable=False)
    next_reset_at = Column(BigInteger, nullable=False)
    status = Column(Text, nullable=False, default='active')
    source = Column(Text, nullable=False, default='default')
    snapshot = Column(JSON, nullable=True)
    billing_address = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class SubscriptionLedger(Base):
    __tablename__ = 'subscription_ledger'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    event_type = Column(Text, nullable=False)
    tier_before = Column(Text, nullable=True)
    tier_after = Column(Text, nullable=True)
    plan_delta_micros = Column(BigInteger, nullable=False, default=0)
    check_delta_micros = Column(BigInteger, nullable=False, default=0)
    plan_balance_after_micros = Column(BigInteger, nullable=False)
    check_balance_after_micros = Column(BigInteger, nullable=False)
    reference_type = Column(Text, nullable=True)
    reference_id = Column(Text, nullable=True)
    meta = Column('metadata', JSON, nullable=True)
    created_by = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class RedemptionCode(Base):
    __tablename__ = 'redemption_code'

    id = Column(Text, primary_key=True)
    code = Column(Text, nullable=True)
    code_hash = Column(Text, nullable=False, unique=True, index=True)
    code_preview = Column(Text, nullable=False)
    benefit_type = Column(Text, nullable=False, default='legacy', server_default='legacy')
    mode = Column(Text, nullable=False)
    max_uses = Column(Integer, nullable=False)
    used_count = Column(Integer, nullable=False, default=0)
    tier = Column(Text, nullable=True)
    duration_days = Column(Integer, nullable=True)
    plan_chatpoint_micros = Column(BigInteger, nullable=False, default=0)
    check_chatpoint_micros = Column(BigInteger, nullable=False, default=0)
    expires_at = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    purged_at = Column(BigInteger, nullable=True)
    batch_id = Column(Text, nullable=True)
    memo = Column(Text, nullable=True)
    created_by = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class RedemptionRecord(Base):
    __tablename__ = 'redemption_record'

    id = Column(Text, primary_key=True)
    redemption_code_id = Column(Text, nullable=False, index=True)
    user_id = Column(Text, nullable=False, index=True)
    tier_before = Column(Text, nullable=True)
    tier_after = Column(Text, nullable=True)
    plan_delta_micros = Column(BigInteger, nullable=False, default=0)
    check_delta_micros = Column(BigInteger, nullable=False, default=0)
    subscription_expires_at_before = Column(BigInteger, nullable=True)
    subscription_expires_at_after = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)

    __table_args__ = (Index('redemption_record_code_user_idx', 'redemption_code_id', 'user_id', unique=True),)


class GiftCardGrant(Base):
    __tablename__ = 'gift_card_grant'

    id = Column(Text, primary_key=True)
    redemption_code_id = Column(Text, nullable=False, index=True)
    user_id = Column(Text, nullable=False, index=True)
    status = Column(Text, nullable=False, default='pending')
    batch_id = Column(Text, nullable=False, index=True)
    claimed_at = Column(BigInteger, nullable=True)
    memo = Column(Text, nullable=True)
    created_by = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (Index('gift_card_grant_user_status_idx', 'user_id', 'status'),)


class SubscriptionUsage(Base):
    __tablename__ = 'subscription_usage'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    chat_id = Column(Text, nullable=True)
    message_id = Column(Text, nullable=True)
    request_id = Column(Text, nullable=True, index=True)
    idempotency_key = Column(String(64), nullable=True)
    reservation_id = Column(Text, nullable=True)
    model_id = Column(Text, nullable=False, index=True)
    tier = Column(Text, nullable=False)
    quota_mode = Column(Text, nullable=False)
    usage_multiplier = Column(Text, nullable=False, default='1')
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cache_creation_tokens = Column(Integer, nullable=True)
    cache_read_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=False, default=0)
    input_chatpoint_per_million = Column(Text, nullable=True)
    output_chatpoint_per_million = Column(Text, nullable=True)
    cache_creation_chatpoint_per_million = Column(Text, nullable=True)
    cache_read_chatpoint_per_million = Column(Text, nullable=True)
    cost_micros = Column(BigInteger, nullable=False, default=0)
    plan_cost_micros = Column(BigInteger, nullable=False, default=0)
    check_cost_micros = Column(BigInteger, nullable=False, default=0)
    unpaid_cost_micros = Column(BigInteger, nullable=False, default=0)
    plan_balance_after_micros = Column(BigInteger, nullable=True)
    check_balance_after_micros = Column(BigInteger, nullable=True)
    first_token_latency_ms = Column(Integer, nullable=True)
    total_duration_ms = Column(Integer, nullable=True)
    client_ip = Column(Text, nullable=True)
    status = Column(Text, nullable=False)
    raw_usage = Column(JSON, nullable=True)
    meta = Column('metadata', JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index('uq_subscription_usage_idempotency_key', 'idempotency_key', unique=True),
        Index('uq_subscription_usage_reservation_id', 'reservation_id', unique=True),
    )


class SubscriptionReservation(Base):
    __tablename__ = 'subscription_reservation'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    request_id = Column(Text, nullable=False)
    model_id = Column(Text, nullable=False)
    idempotency_key = Column(String(64), nullable=False)
    status = Column(Text, nullable=False, default='active')
    period_start_at = Column(BigInteger, nullable=False)
    reserved_micros = Column(BigInteger, nullable=False)
    reserved_plan_micros = Column(BigInteger, nullable=False)
    reserved_check_micros = Column(BigInteger, nullable=False)
    actual_cost_micros = Column(BigInteger, nullable=True)
    settled_plan_micros = Column(BigInteger, nullable=False, default=0)
    settled_check_micros = Column(BigInteger, nullable=False, default=0)
    refunded_plan_micros = Column(BigInteger, nullable=False, default=0)
    refunded_check_micros = Column(BigInteger, nullable=False, default=0)
    forfeited_plan_micros = Column(BigInteger, nullable=False, default=0)
    unpaid_cost_micros = Column(BigInteger, nullable=False, default=0)
    expires_at = Column(BigInteger, nullable=True)
    release_reason = Column(Text, nullable=True)
    meta = Column('metadata', JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    settled_at = Column(BigInteger, nullable=True)
    released_at = Column(BigInteger, nullable=True)

    __table_args__ = (
        Index('uq_subscription_reservation_idempotency_key', 'idempotency_key', unique=True),
        Index('ix_subscription_reservation_user_status', 'user_id', 'status'),
        Index('ix_subscription_reservation_status_expires', 'status', 'expires_at'),
        CheckConstraint(
            "status IN ('active', 'settled', 'partially_settled', 'released', 'expired')",
            name='ck_subscription_reservation_status',
        ),
        CheckConstraint('reserved_micros >= 0', name='ck_subscription_reservation_reserved_nonnegative'),
        CheckConstraint(
            'reserved_plan_micros >= 0 AND reserved_check_micros >= 0',
            name='ck_subscription_reservation_split_nonnegative',
        ),
        CheckConstraint(
            'reserved_micros = reserved_plan_micros + reserved_check_micros',
            name='ck_subscription_reservation_split_total',
        ),
        CheckConstraint(
            'settled_plan_micros >= 0 AND settled_check_micros >= 0',
            name='ck_subscription_reservation_settled_nonnegative',
        ),
        CheckConstraint(
            'refunded_plan_micros >= 0 AND refunded_check_micros >= 0',
            name='ck_subscription_reservation_refunded_nonnegative',
        ),
        CheckConstraint(
            'forfeited_plan_micros >= 0 AND unpaid_cost_micros >= 0',
            name='ck_subscription_reservation_audit_nonnegative',
        ),
    )


class SubscriptionPlanModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    tier_rank: int
    period_days: int
    plan_chatpoint_allowance_micros: int
    description: str | None = None
    features: dict | list | None = None
    is_active: bool
    sort_order: int
    created_at: int
    updated_at: int


class SubscriptionPlansTable:
    async def seed_defaults(
        self,
        db: AsyncSession | None = None,
        *,
        commit: bool = True,
    ) -> None:
        async with get_subscription_db_context(db) as session:
            existing = await session.execute(select(SubscriptionPlan))
            existing_plans = {plan.id: plan for plan in existing.scalars().all()}
            timestamp = now_ts()
            defaults_changed = False

            defaults = [
                (
                    FREE_TIER,
                    'Free',
                    0,
                    DEFAULT_PLAN_CHATPOINTS[FREE_TIER],
                    '基础模型访问额度。',
                    {
                        'icon': 'sparkles',
                        'subtitle': '基础体验',
                        'highlights': ['每月 100 Chatpoint', '可访问基础模型'],
                        'model_summary': '适合轻量对话和试用模型。',
                        'cta_label': '当前计划',
                    },
                ),
                (
                    PLUS_TIER,
                    'Plus',
                    1,
                    DEFAULT_PLAN_CHATPOINTS[PLUS_TIER],
                    '更多模型访问权限和更高用量。',
                    {
                        'icon': 'badge',
                        'subtitle': '进阶体验',
                        'highlights': ['每月 3000 Chatpoint', '可访问 Plus 模型'],
                        'model_summary': '适合日常高频使用和更强模型。',
                        'cta_label': '购买',
                    },
                ),
                (
                    CHATPOWER_TIER,
                    'ChatPower',
                    2,
                    DEFAULT_PLAN_CHATPOINTS[CHATPOWER_TIER],
                    '最高用量和完整模型访问档位。',
                    {
                        'icon': 'zap',
                        'subtitle': '高阶体验',
                        'highlights': ['每月 10000 Chatpoint', '可访问完整高级模型'],
                        'model_summary': '适合重度创作、研究和高频工作流。',
                        'cta_label': '购买',
                    },
                ),
            ]
            legacy_defaults = {
                FREE_TIER: (
                    {'Free', '免费版'},
                    {'Starter access for basic models.', '基础模型访问额度。'},
                ),
                PLUS_TIER: (
                    {'Plus'},
                    {'Expanded access and higher usage.', '更多模型访问权限和更高用量。'},
                ),
                CHATPOWER_TIER: (
                    {'ChatPower'},
                    {'Highest ArtiChat usage tier.', '最高用量和完整模型访问档位。'},
                ),
            }
            for plan_id, display_name, rank, allowance, description, features in defaults:
                if plan_id in existing_plans:
                    plan = existing_plans[plan_id]
                    legacy_names, legacy_descriptions = legacy_defaults[plan_id]
                    changed = False
                    if plan.display_name != display_name and plan.display_name in legacy_names:
                        plan.display_name = display_name
                        changed = True
                    if plan.description != description and plan.description in legacy_descriptions:
                        plan.description = description
                        changed = True
                    legacy_allowances = {chatpoint_to_micros(item) for item in LEGACY_PLAN_CHATPOINTS[plan_id]}
                    if plan.plan_chatpoint_allowance_micros in legacy_allowances:
                        plan.plan_chatpoint_allowance_micros = chatpoint_to_micros(allowance)
                        changed = True
                    if plan.features in (None, [], {}):
                        plan.features = features
                        changed = True
                    if changed:
                        plan.updated_at = timestamp
                        defaults_changed = True
                    continue
                session.add(
                    SubscriptionPlan(
                        id=plan_id,
                        display_name=display_name,
                        tier_rank=rank,
                        period_days=DEFAULT_PERIOD_DAYS,
                        plan_chatpoint_allowance_micros=chatpoint_to_micros(allowance),
                        description=description,
                        features=features,
                        is_active=True,
                        sort_order=rank,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                defaults_changed = True
            if defaults_changed and commit:
                await session.commit()
            elif defaults_changed:
                await session.flush()

    async def get_plans(self, db: AsyncSession | None = None) -> list[SubscriptionPlanModel]:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order.asc()))
            return [SubscriptionPlanModel.model_validate(row) for row in result.scalars().all()]

    async def get_plan_by_id(self, plan_id: str, db: AsyncSession | None = None) -> SubscriptionPlanModel | None:
        async with get_subscription_db_context(db) as session:
            plan = await session.get(SubscriptionPlan, plan_id)
            return SubscriptionPlanModel.model_validate(plan) if plan else None

    async def update_plan(
        self,
        plan_id: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
        plan_chatpoint_allowance_micros: int | None = None,
        period_days: int | None = None,
        features: dict | list | None = None,
        is_active: bool | None = None,
        db: AsyncSession | None = None,
    ) -> SubscriptionPlanModel:
        async with get_subscription_db_context(db) as session:
            plan = await session.get(SubscriptionPlan, plan_id)
            if plan is None:
                raise ValueError('SUBSCRIPTION_PLAN_NOT_FOUND')
            if display_name is not None:
                plan.display_name = display_name
            if description is not None:
                plan.description = description
            if plan_chatpoint_allowance_micros is not None:
                plan.plan_chatpoint_allowance_micros = plan_chatpoint_allowance_micros
            if period_days is not None:
                plan.period_days = period_days
            if features is not None:
                plan.features = features
            if is_active is not None:
                plan.is_active = is_active
            plan.updated_at = now_ts()
            await session.commit()
            await session.refresh(plan)
            return SubscriptionPlanModel.model_validate(plan)


SubscriptionPlans = SubscriptionPlansTable()


class UserSubscriptionModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    tier: str
    tier_rank: int
    display_name: str
    period_days: int
    plan_chatpoint_allowance_micros: int
    plan_balance_micros: int
    check_balance_micros: int
    balance_version: int
    starts_at: int
    expires_at: int | None = None
    period_start_at: int
    period_end_at: int
    next_reset_at: int
    status: str
    source: str
    snapshot: dict | None = None
    billing_address: dict | None = None
    notes: str | None = None
    created_at: int
    updated_at: int


class UserSubscriptionSummaryModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    tier: str
    display_name: str
    status: str
    expires_at: int | None = None
    plan_balance_micros: int
    check_balance_micros: int
    notes: str | None = None


class SubscriptionLedgerModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_id: str
    event_type: str
    tier_before: str | None = None
    tier_after: str | None = None
    plan_delta_micros: int
    check_delta_micros: int
    plan_balance_after_micros: int
    check_balance_after_micros: int
    reference_type: str | None = None
    reference_id: str | None = None
    metadata: dict | None = Field(default=None, alias='meta')
    created_by: str | None = None
    created_at: int


class UserSummaryModel(BaseModel):
    id: str
    email: str | None = None
    username: str | None = None
    name: str | None = None
    created_at: int | None = None


def user_summary(user: User | None) -> dict | None:
    if user is None:
        return None
    return UserSummaryModel.model_validate(user, from_attributes=True).model_dump()


def new_id(prefix: str) -> str:
    return f'{prefix}_{secrets.token_urlsafe(18)}'


class SubscriptionLedgersTable:
    async def insert(
        self,
        *,
        user_id: str,
        event_type: str,
        tier_before: str | None,
        tier_after: str | None,
        plan_delta_micros: int,
        check_delta_micros: int,
        plan_balance_after_micros: int,
        check_balance_after_micros: int,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
        created_at: int | None = None,
        commit: bool = True,
        db: AsyncSession | None = None,
    ) -> SubscriptionLedgerModel:
        async with get_subscription_db_context(db) as session:
            row = SubscriptionLedger(
                id=new_id('ledger'),
                user_id=user_id,
                event_type=event_type,
                tier_before=tier_before,
                tier_after=tier_after,
                plan_delta_micros=plan_delta_micros,
                check_delta_micros=check_delta_micros,
                plan_balance_after_micros=plan_balance_after_micros,
                check_balance_after_micros=check_balance_after_micros,
                reference_type=reference_type,
                reference_id=reference_id,
                meta=json_safe_metadata(metadata),
                created_by=created_by,
                created_at=created_at or now_ts(),
            )
            session.add(row)
            if commit:
                await session.commit()
                await session.refresh(row)
            else:
                await session.flush()
            return SubscriptionLedgerModel.model_validate(row)

    async def get_recent_for_user(
        self, user_id: str, limit: int = 50, db: AsyncSession | None = None
    ) -> list[SubscriptionLedgerModel]:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(SubscriptionLedger)
                .filter(SubscriptionLedger.user_id == user_id)
                .order_by(SubscriptionLedger.created_at.desc())
                .limit(limit)
            )
            return [SubscriptionLedgerModel.model_validate(row) for row in result.scalars().all()]

    async def search(
        self,
        *,
        user_id: str | None = None,
        event_type: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        limit: int | None = 100,
        offset: int = 0,
        include_user: bool = False,
        db: AsyncSession | None = None,
    ) -> list[SubscriptionLedgerModel] | list[dict]:
        async with get_subscription_db_context(db) as session:
            if include_user:
                stmt = select(SubscriptionLedger, User).outerjoin(User, User.id == SubscriptionLedger.user_id)
            else:
                stmt = select(SubscriptionLedger)
            if user_id:
                stmt = stmt.filter(SubscriptionLedger.user_id == user_id)
            if event_type:
                stmt = stmt.filter(SubscriptionLedger.event_type == event_type)
            if start_at is not None:
                stmt = stmt.filter(SubscriptionLedger.created_at >= start_at)
            if end_at is not None:
                stmt = stmt.filter(SubscriptionLedger.created_at <= end_at)
            stmt = stmt.order_by(SubscriptionLedger.created_at.desc()).offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            if include_user:
                return [
                    {
                        'ledger': SubscriptionLedgerModel.model_validate(ledger),
                        'user': user_summary(user),
                        **SubscriptionLedgerModel.model_validate(ledger).model_dump(by_alias=True),
                    }
                    for ledger, user in result.all()
                ]
            return [SubscriptionLedgerModel.model_validate(row) for row in result.scalars().all()]

    async def count(
        self,
        *,
        user_id: str | None = None,
        event_type: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        db: AsyncSession | None = None,
    ) -> int:
        async with get_subscription_db_context(db) as session:
            stmt = select(func.count(SubscriptionLedger.id))
            if user_id:
                stmt = stmt.where(SubscriptionLedger.user_id == user_id)
            if event_type:
                stmt = stmt.where(SubscriptionLedger.event_type == event_type)
            if start_at is not None:
                stmt = stmt.where(SubscriptionLedger.created_at >= start_at)
            if end_at is not None:
                stmt = stmt.where(SubscriptionLedger.created_at <= end_at)
            return int((await session.execute(stmt)).scalar_one())


SubscriptionLedgers = SubscriptionLedgersTable()


class UserSubscriptionsTable:
    async def get_by_user_id(self, user_id: str, db: AsyncSession | None = None) -> UserSubscriptionModel | None:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(select(UserSubscription).filter(UserSubscription.user_id == user_id))
            row = result.scalar_one_or_none()
            return UserSubscriptionModel.model_validate(row) if row else None

    async def lock_for_billing(self, user_id: str, db: AsyncSession | None = None) -> UserSubscriptionModel:
        async with get_subscription_db_context(db) as session:
            locked = await session.execute(
                update(UserSubscription)
                .where(UserSubscription.user_id == user_id)
                .values(updated_at=UserSubscription.updated_at)
            )
            if locked.rowcount != 1:
                raise ValueError(f'user subscription not found: {user_id}')
            result = await session.execute(
                select(UserSubscription)
                .where(UserSubscription.user_id == user_id)
                .execution_options(populate_existing=True)
            )
            return UserSubscriptionModel.model_validate(result.scalar_one())

    async def get_summaries_by_user_ids(
        self, user_ids: list[str], db: AsyncSession | None = None
    ) -> dict[str, UserSubscriptionSummaryModel]:
        unique_ids = list(dict.fromkeys([item for item in user_ids if item]))
        if not unique_ids:
            return {}
        async with get_subscription_db_context(db) as session:
            result = await session.execute(select(UserSubscription).filter(UserSubscription.user_id.in_(unique_ids)))
            return {row.user_id: UserSubscriptionSummaryModel.model_validate(row) for row in result.scalars().all()}

    async def create_from_plan(
        self,
        *,
        user_id: str,
        plan_id: str,
        starts_at: int,
        expires_at: int | None,
        source: str,
        commit: bool = True,
        db: AsyncSession | None = None,
    ) -> UserSubscriptionModel:
        async with get_subscription_db_context(db) as session:
            plan = await SubscriptionPlans.get_plan_by_id(plan_id, db=session)
            if not plan:
                raise ValueError(f'subscription plan not found: {plan_id}')

            period_end = starts_at + plan.period_days * 24 * 60 * 60
            existing = await session.execute(select(UserSubscription).filter(UserSubscription.user_id == user_id))
            existing_row = existing.scalar_one_or_none()
            if existing_row is not None:
                current = await self.lock_for_billing(user_id, db=session)
                row = await session.get(UserSubscription, current.id)
                check_balance = current.check_balance_micros
                row.balance_version = current.balance_version + 1
            else:
                row = UserSubscription(
                    id=new_id('sub'),
                    user_id=user_id,
                    balance_version=0,
                    created_at=starts_at,
                )
                check_balance = 0
            row.tier = plan.id
            row.tier_rank = plan.tier_rank
            row.display_name = plan.display_name
            row.period_days = plan.period_days
            row.plan_chatpoint_allowance_micros = plan.plan_chatpoint_allowance_micros
            row.plan_balance_micros = plan.plan_chatpoint_allowance_micros
            row.check_balance_micros = check_balance
            row.starts_at = starts_at
            row.expires_at = expires_at
            row.period_start_at = starts_at
            row.period_end_at = period_end
            row.next_reset_at = period_end
            row.status = 'free' if plan.id == FREE_TIER else 'active'
            row.source = source
            row.snapshot = plan.model_dump()
            row.updated_at = starts_at
            session.add(row)
            if commit:
                await session.commit()
                await session.refresh(row)
            else:
                await session.flush()
            return UserSubscriptionModel.model_validate(row)

    async def save(
        self,
        subscription: UserSubscriptionModel,
        *,
        allow_balance_change: bool = False,
        commit: bool = True,
        db: AsyncSession | None = None,
    ) -> UserSubscriptionModel:
        async with get_subscription_db_context(db) as session:
            if subscription.plan_balance_micros < 0 or subscription.check_balance_micros < 0:
                raise ValueError('CHATPOINT_BALANCE_NEGATIVE')
            current = await session.get(UserSubscription, subscription.id)
            if current is None:
                raise ValueError(f'user subscription not found: {subscription.id}')
            if not allow_balance_change and (
                subscription.plan_balance_micros != current.plan_balance_micros
                or subscription.check_balance_micros != current.check_balance_micros
            ):
                raise ValueError('SUBSCRIPTION_BALANCE_CHANGE_REQUIRES_ADJUSTMENT')
            excluded = {'id', 'user_id', 'balance_version'}
            if not allow_balance_change:
                excluded.update({'plan_balance_micros', 'check_balance_micros'})
            values = subscription.model_dump(exclude=excluded)
            saved = await session.execute(
                update(UserSubscription)
                .where(
                    UserSubscription.id == subscription.id,
                    UserSubscription.user_id == subscription.user_id,
                    UserSubscription.balance_version == subscription.balance_version,
                )
                .values(**values, balance_version=subscription.balance_version + 1)
            )
            if saved.rowcount != 1:
                raise ValueError('SUBSCRIPTION_CONCURRENT_UPDATE')
            if commit:
                await session.commit()
            else:
                await session.flush()
            result = await session.execute(
                select(UserSubscription)
                .where(UserSubscription.id == subscription.id)
                .execution_options(populate_existing=True)
            )
            return UserSubscriptionModel.model_validate(result.scalar_one())

    async def adjust_balances(
        self,
        user_id: str,
        *,
        plan_delta_micros: int = 0,
        check_delta_micros: int = 0,
        event_type: str,
        created_by: str | None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict | None = None,
        created_at: int | None = None,
        commit: bool = True,
        db: AsyncSession | None = None,
    ) -> UserSubscriptionModel:
        async with get_subscription_db_context(db) as session:
            sub = await self.get_by_user_id(user_id, db=session)
            if not sub:
                sub = await self.create_from_plan(
                    user_id=user_id,
                    plan_id=FREE_TIER,
                    starts_at=now_ts(),
                    expires_at=None,
                    source='default',
                    commit=False,
                    db=session,
                )

            sub = await self.lock_for_billing(user_id, db=session)
            plan_balance = sub.plan_balance_micros + plan_delta_micros
            check_balance = sub.check_balance_micros + check_delta_micros
            if plan_balance < 0 or check_balance < 0:
                raise ValueError('CHATPOINT_BALANCE_NEGATIVE')

            timestamp = created_at if created_at is not None else now_ts()
            row = await session.get(UserSubscription, sub.id)
            row.plan_balance_micros = plan_balance
            row.check_balance_micros = check_balance
            row.balance_version = sub.balance_version + 1
            row.updated_at = timestamp
            await session.flush()
            model = UserSubscriptionModel.model_validate(row)
            await SubscriptionLedgers.insert(
                user_id=user_id,
                event_type=event_type,
                tier_before=sub.tier,
                tier_after=model.tier,
                plan_delta_micros=plan_delta_micros,
                check_delta_micros=check_delta_micros,
                plan_balance_after_micros=model.plan_balance_micros,
                check_balance_after_micros=model.check_balance_micros,
                reference_type=reference_type,
                reference_id=reference_id,
                metadata=metadata,
                created_by=created_by,
                created_at=timestamp,
                commit=False,
                db=session,
            )
            if commit:
                await session.commit()
                await session.refresh(row)
                model = UserSubscriptionModel.model_validate(row)
            return model

    async def list_subscriptions(
        self,
        *,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession | None = None,
    ) -> list[UserSubscriptionModel]:
        async with get_subscription_db_context(db) as session:
            stmt = select(UserSubscription).order_by(UserSubscription.updated_at.desc()).limit(limit).offset(offset)
            if query:
                stmt = stmt.filter(UserSubscription.user_id.contains(query))
            result = await session.execute(stmt)
            return [UserSubscriptionModel.model_validate(row) for row in result.scalars().all()]

    async def list_subscriptions_with_users(
        self,
        *,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession | None = None,
    ) -> list[dict]:
        async with get_subscription_db_context(db) as session:
            stmt = select(UserSubscription, User).outerjoin(User, User.id == UserSubscription.user_id)
            if query:
                pattern = f'%{query}%'
                stmt = stmt.filter(
                    or_(
                        UserSubscription.user_id.like(pattern),
                        User.email.like(pattern),
                        User.username.like(pattern),
                        User.name.like(pattern),
                    )
                )
            stmt = stmt.order_by(UserSubscription.updated_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [
                {
                    'subscription': UserSubscriptionModel.model_validate(subscription),
                    'user': user_summary(user),
                }
                for subscription, user in result.all()
            ]


UserSubscriptions = UserSubscriptionsTable()


def hash_redemption_code(code: str) -> str:
    return hashlib.sha256(normalize_redemption_code(code).encode('utf-8')).hexdigest()


def normalize_redemption_code(code: str) -> str:
    return code.strip().upper()


def preview_redemption_code(code: str) -> str:
    normalized = normalize_redemption_code(code)
    return f'{normalized[:4]}-{normalized[-4:]}'


REDEMPTION_BENEFIT_TYPES = {'subscription', 'recharge', 'legacy'}


def resolve_redemption_benefit_type(
    benefit_type: str | None,
    *,
    tier: str | None,
    duration_days: int | None,
    plan_chatpoint_micros: int,
    check_chatpoint_micros: int,
) -> str:
    if benefit_type is None:
        if check_chatpoint_micros == 0 and (tier is not None or duration_days is not None or plan_chatpoint_micros > 0):
            benefit_type = 'subscription'
        elif plan_chatpoint_micros == 0 and check_chatpoint_micros > 0 and tier is None and duration_days is None:
            benefit_type = 'recharge'
        else:
            benefit_type = 'legacy'

    if benefit_type not in REDEMPTION_BENEFIT_TYPES:
        raise ValueError('REDEMPTION_BENEFIT_TYPE_INVALID')
    if benefit_type == 'subscription' and check_chatpoint_micros:
        raise ValueError('REDEMPTION_BENEFIT_CONFLICT')
    if benefit_type == 'recharge' and (plan_chatpoint_micros or tier is not None or duration_days is not None):
        raise ValueError('REDEMPTION_BENEFIT_CONFLICT')
    return benefit_type


def generate_redemption_code() -> str:
    return f'ARTI-{secrets.token_urlsafe(6).upper()}-{secrets.token_urlsafe(6).upper()}'


REDEMPTION_CODE_TEMPLATE_MIN_LENGTH = 8
REDEMPTION_CODE_TEMPLATE_MAX_LENGTH = 128
REDEMPTION_CODE_TEMPLATE_MIN_PLACEHOLDERS = 6
REDEMPTION_CODE_GENERATION_ATTEMPTS = 10
REDEMPTION_CODE_TEMPLATE_PATTERN = re.compile(r'^[A-Z0-9]+(?:-[A-Z0-9]+)*$')
REDEMPTION_CODE_PREFIX_MAX_LENGTH = 40


def normalize_redemption_code_template(template: str) -> str:
    normalized = normalize_redemption_code(template)
    if not (REDEMPTION_CODE_TEMPLATE_MIN_LENGTH <= len(normalized) <= REDEMPTION_CODE_TEMPLATE_MAX_LENGTH):
        raise ValueError('REDEMPTION_CODE_TEMPLATE_INVALID')
    if not REDEMPTION_CODE_TEMPLATE_PATTERN.fullmatch(normalized):
        raise ValueError('REDEMPTION_CODE_TEMPLATE_INVALID')
    if normalized.count('0') < REDEMPTION_CODE_TEMPLATE_MIN_PLACEHOLDERS:
        raise ValueError('REDEMPTION_CODE_TEMPLATE_TOO_WEAK')
    return normalized


def normalize_redemption_code_prefix(prefix: str) -> str:
    normalized = normalize_redemption_code(prefix).strip('-')
    if not normalized or len(normalized) > REDEMPTION_CODE_PREFIX_MAX_LENGTH:
        raise ValueError('REDEMPTION_CODE_PREFIX_INVALID')
    if not REDEMPTION_CODE_TEMPLATE_PATTERN.fullmatch(normalized):
        raise ValueError('REDEMPTION_CODE_PREFIX_INVALID')
    return normalized


def generate_redemption_code_with_prefix(prefix: str) -> str:
    normalized = normalize_redemption_code_prefix(prefix)
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    suffix = ''.join(secrets.choice(alphabet) for _ in range(16))
    return f'{normalized}-{suffix[:8]}-{suffix[8:]}'


def generate_redemption_code_from_template(template: str) -> str:
    normalized = normalize_redemption_code_template(template)
    return ''.join(secrets.choice('0123456789') if character == '0' else character for character in normalized)


def _validated_redemption_code_inputs(
    *,
    mode: str,
    quantity: int,
    max_uses: int,
    custom_code: str | None,
    code_template: str | None,
    code_prefix: str | None,
) -> tuple[str | None, str | None, str | None]:
    if mode not in {'single_use', 'multi_use'}:
        raise ValueError('redemption mode must be single_use or multi_use')
    if quantity < 1:
        raise ValueError('quantity must be greater than 0')
    if max_uses < 1:
        raise ValueError('max_uses must be greater than 0')
    if mode == 'multi_use' and quantity != 1:
        raise ValueError('multi_use creation creates exactly one code')

    normalized_custom_code = normalize_redemption_code(custom_code) if custom_code is not None else None
    if custom_code is not None and not normalized_custom_code:
        raise ValueError('REDEMPTION_CODE_INVALID')
    if normalized_custom_code and quantity != 1:
        raise ValueError('custom_code can only create one code at a time')
    if normalized_custom_code and (code_template or code_prefix):
        raise ValueError('REDEMPTION_CODE_INPUT_CONFLICT')
    if code_template and code_prefix:
        raise ValueError('REDEMPTION_CODE_INPUT_CONFLICT')

    normalized_template = normalize_redemption_code_template(code_template) if code_template else None
    normalized_prefix = normalize_redemption_code_prefix(code_prefix) if code_prefix else None
    return normalized_custom_code, normalized_template, normalized_prefix


def _redemption_code_candidate(
    custom_code: str | None,
    code_template: str | None,
    code_prefix: str | None,
) -> str:
    if custom_code:
        return custom_code
    if code_template:
        return generate_redemption_code_from_template(code_template)
    if code_prefix:
        return generate_redemption_code_with_prefix(code_prefix)
    return generate_redemption_code()


def _generate_redemption_code_batch(
    *,
    quantity: int,
    custom_code: str | None,
    code_template: str | None,
    code_prefix: str | None,
) -> tuple[list[str], list[str]]:
    raw_codes: list[str] = []
    code_hashes: list[str] = []
    seen_hashes: set[str] = set()
    candidate_attempts = 0
    while len(raw_codes) < quantity:
        candidate_attempts += 1
        if candidate_attempts > max(quantity * REDEMPTION_CODE_GENERATION_ATTEMPTS, 100):
            raise ValueError('REDEMPTION_CODE_GENERATION_EXHAUSTED')
        raw_code = _redemption_code_candidate(custom_code, code_template, code_prefix)
        code_hash = hash_redemption_code(raw_code)
        if code_hash in seen_hashes:
            if custom_code:
                raise ValueError('REDEMPTION_CODE_DUPLICATE')
            continue
        raw_codes.append(raw_code)
        code_hashes.append(code_hash)
        seen_hashes.add(code_hash)
    return raw_codes, code_hashes


async def _generate_unique_redemption_code_batch(
    session: AsyncSession,
    *,
    quantity: int,
    custom_code: str | None,
    code_template: str | None,
    code_prefix: str | None,
) -> tuple[list[str], list[str]]:
    for _ in range(REDEMPTION_CODE_GENERATION_ATTEMPTS):
        raw_codes, code_hashes = _generate_redemption_code_batch(
            quantity=quantity,
            custom_code=custom_code,
            code_template=code_template,
            code_prefix=code_prefix,
        )
        existing = await session.execute(
            select(RedemptionCode.code_hash).where(RedemptionCode.code_hash.in_(code_hashes))
        )
        if not existing.first():
            return raw_codes, code_hashes
        if custom_code:
            raise ValueError('REDEMPTION_CODE_DUPLICATE')
    raise ValueError('REDEMPTION_CODE_GENERATION_EXHAUSTED')


class RedemptionCodeCreateResult(BaseModel):
    raw_codes: list[str]
    code_ids: list[str]


class RedemptionCodeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str | None = None
    code_hash: str
    code_preview: str
    benefit_type: str
    mode: str
    max_uses: int
    used_count: int
    tier: str | None = None
    duration_days: int | None = None
    plan_chatpoint_micros: int
    check_chatpoint_micros: int
    expires_at: int | None = None
    is_active: bool
    purged_at: int | None = None
    batch_id: str | None = None
    memo: str | None = None
    created_by: str
    created_at: int
    updated_at: int


class RedemptionRecordModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    redemption_code_id: str
    user_id: str
    tier_before: str | None = None
    tier_after: str | None = None
    plan_delta_micros: int
    check_delta_micros: int
    subscription_expires_at_before: int | None = None
    subscription_expires_at_after: int | None = None
    created_at: int


class RedemptionCodesTable:
    async def create_codes(
        self,
        *,
        benefit_type: str | None = None,
        mode: str,
        quantity: int,
        max_uses: int,
        tier: str | None,
        duration_days: int | None,
        plan_chatpoint_micros: int,
        check_chatpoint_micros: int,
        expires_at: int | None,
        memo: str | None,
        created_by: str,
        custom_code: str | None = None,
        code_template: str | None = None,
        code_prefix: str | None = None,
        batch_id: str | None = None,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> RedemptionCodeCreateResult:
        normalized_custom_code, normalized_template, normalized_prefix = _validated_redemption_code_inputs(
            mode=mode,
            quantity=quantity,
            max_uses=max_uses,
            custom_code=custom_code,
            code_template=code_template,
            code_prefix=code_prefix,
        )
        resolved_benefit_type = resolve_redemption_benefit_type(
            benefit_type,
            tier=tier,
            duration_days=duration_days,
            plan_chatpoint_micros=plan_chatpoint_micros,
            check_chatpoint_micros=check_chatpoint_micros,
        )

        timestamp = now or now_ts()
        resolved_batch_id = batch_id or new_id('batch')

        async with get_subscription_db_context(db) as session:
            raw_codes, code_hashes = await _generate_unique_redemption_code_batch(
                session,
                quantity=quantity,
                custom_code=normalized_custom_code,
                code_template=normalized_template,
                code_prefix=normalized_prefix,
            )

            code_ids: list[str] = []
            for raw_code, code_hash in zip(raw_codes, code_hashes):
                code_id = new_id('code')
                session.add(
                    RedemptionCode(
                        id=code_id,
                        code=raw_code,
                        code_hash=code_hash,
                        code_preview=preview_redemption_code(raw_code),
                        benefit_type=resolved_benefit_type,
                        mode=mode,
                        max_uses=max_uses,
                        used_count=0,
                        tier=tier,
                        duration_days=duration_days,
                        plan_chatpoint_micros=plan_chatpoint_micros,
                        check_chatpoint_micros=check_chatpoint_micros,
                        expires_at=expires_at,
                        is_active=True,
                        purged_at=None,
                        batch_id=resolved_batch_id,
                        memo=memo,
                        created_by=created_by,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                code_ids.append(code_id)
            await session.commit()
        return RedemptionCodeCreateResult(raw_codes=raw_codes, code_ids=code_ids)

    async def get_by_raw_code(self, code: str, db: AsyncSession | None = None) -> RedemptionCodeModel | None:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(RedemptionCode).filter(RedemptionCode.code_hash == hash_redemption_code(code))
            )
            row = result.scalar_one_or_none()
            return RedemptionCodeModel.model_validate(row) if row else None

    async def increment_used_count(
        self,
        code_id: str,
        db: AsyncSession | None = None,
        *,
        commit: bool = True,
    ) -> RedemptionCodeModel:
        async with get_subscription_db_context(db) as session:
            row = await session.get(RedemptionCode, code_id)
            if not row:
                raise ValueError('REDEMPTION_CODE_INVALID')
            row.used_count += 1
            row.updated_at = now_ts()
            if commit:
                await session.commit()
                await session.refresh(row)
            else:
                await session.flush()
            return RedemptionCodeModel.model_validate(row)

    async def list_codes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str = 'all',
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> list[RedemptionCodeModel]:
        if status not in {'available', 'archive', 'all'}:
            raise ValueError('REDEMPTION_CODE_STATUS_INVALID')
        current_time = now if now is not None else now_ts()
        async with get_subscription_db_context(db) as session:
            stmt = select(RedemptionCode)
            available = (
                RedemptionCode.is_active.is_(True),
                RedemptionCode.purged_at.is_(None),
                RedemptionCode.used_count < RedemptionCode.max_uses,
                or_(RedemptionCode.expires_at.is_(None), RedemptionCode.expires_at > current_time),
            )
            if status == 'available':
                stmt = stmt.filter(*available)
            elif status == 'archive':
                stmt = stmt.filter(
                    ~RedemptionCode.is_active
                    | RedemptionCode.purged_at.is_not(None)
                    | (RedemptionCode.used_count >= RedemptionCode.max_uses)
                    | (RedemptionCode.expires_at.is_not(None) & (RedemptionCode.expires_at <= current_time))
                )
            result = await session.execute(stmt.order_by(RedemptionCode.created_at.desc()).limit(limit).offset(offset))
            return [RedemptionCodeModel.model_validate(row) for row in result.scalars().all()]

    async def update_code(
        self,
        code_id: str,
        *,
        is_active: bool | None = None,
        memo: str | None = None,
        db: AsyncSession | None = None,
    ) -> RedemptionCodeModel:
        async with get_subscription_db_context(db) as session:
            code = await session.get(RedemptionCode, code_id)
            if code is None:
                raise ValueError('REDEMPTION_CODE_NOT_FOUND')
            if is_active and code.purged_at is not None:
                raise ValueError('REDEMPTION_CODE_PURGED')
            if is_active is not None:
                code.is_active = is_active
            if memo is not None:
                code.memo = memo
            code.updated_at = now_ts()
            await session.commit()
            await session.refresh(code)
            return RedemptionCodeModel.model_validate(code)

    async def delete_code(self, code_id: str, db: AsyncSession | None = None) -> RedemptionCodeModel:
        async with get_subscription_db_context(db) as session:
            code = await session.get(RedemptionCode, code_id)
            if code is None:
                raise ValueError('REDEMPTION_CODE_NOT_FOUND')
            if code.is_active:
                code.is_active = False
            code.updated_at = now_ts()
            await session.commit()
            await session.refresh(code)
            return RedemptionCodeModel.model_validate(code)

    async def clear_codes(
        self,
        code_ids: list[str],
        *,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> list[RedemptionCodeModel]:
        unique_ids = list(dict.fromkeys(item for item in code_ids if item))
        if not unique_ids:
            raise ValueError('REDEMPTION_CODE_IDS_REQUIRED')
        current_time = now if now is not None else now_ts()
        async with get_subscription_db_context(db) as session:
            rows = []
            for code_id in unique_ids:
                code = await session.get(RedemptionCode, code_id)
                if code is None:
                    raise ValueError('REDEMPTION_CODE_NOT_FOUND')
                available = (
                    code.is_active
                    and code.purged_at is None
                    and code.used_count < code.max_uses
                    and (code.expires_at is None or code.expires_at > current_time)
                )
                if available:
                    raise ValueError('REDEMPTION_CODE_ACTIVE')
                code.is_active = False
                code.code = None
                code.code_preview = '[已清除]'
                code.memo = None
                code.purged_at = current_time
                code.updated_at = current_time
                rows.append(code)
            await session.commit()
            for row in rows:
                await session.refresh(row)
            return [RedemptionCodeModel.model_validate(row) for row in rows]


RedemptionCodes = RedemptionCodesTable()


class RedemptionRecordsTable:
    async def get_by_code_and_user(
        self, code_id: str, user_id: str, db: AsyncSession | None = None
    ) -> RedemptionRecordModel | None:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(RedemptionRecord).filter(
                    RedemptionRecord.redemption_code_id == code_id,
                    RedemptionRecord.user_id == user_id,
                )
            )
            row = result.scalar_one_or_none()
            return RedemptionRecordModel.model_validate(row) if row else None

    async def insert(
        self,
        *,
        redemption_code_id: str,
        user_id: str,
        tier_before: str | None,
        tier_after: str | None,
        plan_delta_micros: int,
        check_delta_micros: int,
        subscription_expires_at_before: int | None,
        subscription_expires_at_after: int | None,
        created_at: int,
        db: AsyncSession | None = None,
        commit: bool = True,
    ) -> RedemptionRecordModel:
        async with get_subscription_db_context(db) as session:
            row = RedemptionRecord(
                id=new_id('redeem'),
                redemption_code_id=redemption_code_id,
                user_id=user_id,
                tier_before=tier_before,
                tier_after=tier_after,
                plan_delta_micros=plan_delta_micros,
                check_delta_micros=check_delta_micros,
                subscription_expires_at_before=subscription_expires_at_before,
                subscription_expires_at_after=subscription_expires_at_after,
                created_at=created_at,
            )
            session.add(row)
            if commit:
                await session.commit()
                await session.refresh(row)
            else:
                await session.flush()
            return RedemptionRecordModel.model_validate(row)

    async def list_for_code(self, code_id: str, *, db: AsyncSession | None = None) -> list[RedemptionRecordModel]:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(RedemptionRecord)
                .filter(RedemptionRecord.redemption_code_id == code_id)
                .order_by(RedemptionRecord.created_at.desc())
            )
            return [RedemptionRecordModel.model_validate(row) for row in result.scalars().all()]


RedemptionRecords = RedemptionRecordsTable()


class GiftCardGrantModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    redemption_code_id: str
    user_id: str
    status: str
    batch_id: str
    claimed_at: int | None = None
    memo: str | None = None
    created_by: str
    created_at: int
    updated_at: int


class GiftCardIssueResult(BaseModel):
    batch_id: str
    grants: list[GiftCardGrantModel]
    raw_codes: list[str]


class GiftCardClaimResult(BaseModel):
    subscription: UserSubscriptionModel
    grant: GiftCardGrantModel
    tier_before: str | None
    tier_after: str | None
    plan_delta_micros: int
    check_delta_micros: int


class GiftCardGrantsTable:
    async def issue_grants(
        self,
        *,
        user_ids: list[str],
        mode: str,
        benefit_type: str | None = None,
        tier: str | None,
        duration_days: int | None,
        plan_chatpoint_micros: int,
        check_chatpoint_micros: int,
        expires_at: int | None,
        memo: str | None,
        created_by: str,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> GiftCardIssueResult:
        unique_user_ids = list(dict.fromkeys([item for item in user_ids if item]))
        if not unique_user_ids:
            raise ValueError('GIFT_CARD_USERS_REQUIRED')
        if mode not in {'single_use', 'multi_use'}:
            raise ValueError('redemption mode must be single_use or multi_use')
        resolved_benefit_type = resolve_redemption_benefit_type(
            benefit_type,
            tier=tier,
            duration_days=duration_days,
            plan_chatpoint_micros=plan_chatpoint_micros,
            check_chatpoint_micros=check_chatpoint_micros,
        )

        timestamp = now or now_ts()
        batch_id = new_id('giftbatch')
        raw_codes: list[str] = []

        async with get_subscription_db_context(db) as session:
            for user_id in unique_user_ids:
                raw_code = generate_redemption_code()
                code_id = new_id('code')
                grant_id = new_id('gift')
                session.add(
                    RedemptionCode(
                        id=code_id,
                        code=raw_code,
                        code_hash=hash_redemption_code(raw_code),
                        code_preview=preview_redemption_code(raw_code),
                        benefit_type=resolved_benefit_type,
                        mode='single_use',
                        max_uses=1,
                        used_count=0,
                        tier=tier,
                        duration_days=duration_days,
                        plan_chatpoint_micros=plan_chatpoint_micros,
                        check_chatpoint_micros=check_chatpoint_micros,
                        expires_at=expires_at,
                        is_active=True,
                        purged_at=None,
                        batch_id=batch_id,
                        memo=memo,
                        created_by=created_by,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                session.add(
                    GiftCardGrant(
                        id=grant_id,
                        redemption_code_id=code_id,
                        user_id=user_id,
                        status='pending',
                        batch_id=batch_id,
                        claimed_at=None,
                        memo=memo,
                        created_by=created_by,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                raw_codes.append(raw_code)
            await session.commit()
            result = await session.execute(
                select(GiftCardGrant)
                .filter(GiftCardGrant.batch_id == batch_id)
                .order_by(GiftCardGrant.created_at.asc())
            )
            grants = [GiftCardGrantModel.model_validate(row) for row in result.scalars().all()]
        return GiftCardIssueResult(batch_id=batch_id, grants=grants, raw_codes=raw_codes)

    async def issue_for_all_current_users(
        self,
        *,
        mode: str,
        benefit_type: str | None = None,
        tier: str | None,
        duration_days: int | None,
        plan_chatpoint_micros: int,
        check_chatpoint_micros: int,
        expires_at: int | None,
        memo: str | None,
        created_by: str,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> GiftCardIssueResult:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(select(User.id).filter(User.role.in_(['user', 'admin'])))
            user_ids = list(result.scalars().all())
            return await self.issue_grants(
                user_ids=user_ids,
                mode=mode,
                benefit_type=benefit_type,
                tier=tier,
                duration_days=duration_days,
                plan_chatpoint_micros=plan_chatpoint_micros,
                check_chatpoint_micros=check_chatpoint_micros,
                expires_at=expires_at,
                memo=memo,
                created_by=created_by,
                now=now,
                db=session,
            )

    async def list_pending_for_user(
        self, user_id: str, *, now: int | None = None, db: AsyncSession | None = None
    ) -> list[GiftCardGrantModel]:
        current_time = now if now is not None else now_ts()
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(GiftCardGrant)
                .join(RedemptionCode, RedemptionCode.id == GiftCardGrant.redemption_code_id)
                .filter(
                    GiftCardGrant.user_id == user_id,
                    GiftCardGrant.status == 'pending',
                    RedemptionCode.is_active.is_(True),
                    RedemptionCode.used_count < RedemptionCode.max_uses,
                    or_(RedemptionCode.expires_at.is_(None), RedemptionCode.expires_at > current_time),
                )
                .order_by(GiftCardGrant.created_at.desc())
            )
            return [GiftCardGrantModel.model_validate(row) for row in result.scalars().all()]

    async def list_grants(
        self,
        *,
        batch_id: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession | None = None,
    ) -> list[dict]:
        async with get_subscription_db_context(db) as session:
            stmt = (
                select(GiftCardGrant, RedemptionCode, User)
                .outerjoin(RedemptionCode, RedemptionCode.id == GiftCardGrant.redemption_code_id)
                .outerjoin(User, User.id == GiftCardGrant.user_id)
            )
            if batch_id:
                stmt = stmt.filter(GiftCardGrant.batch_id == batch_id)
            if user_id:
                stmt = stmt.filter(GiftCardGrant.user_id == user_id)
            stmt = stmt.order_by(GiftCardGrant.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [
                {
                    'grant': GiftCardGrantModel.model_validate(grant),
                    'code': RedemptionCodeModel.model_validate(code) if code else None,
                    'user': user_summary(user),
                }
                for grant, code, user in result.all()
            ]

    async def claim(
        self, grant_id: str, *, user_id: str, now: int | None = None, db: AsyncSession | None = None
    ) -> GiftCardClaimResult:
        from open_webui.utils.subscriptions import redeem_code

        current_time = now or now_ts()
        async with get_subscription_db_context(db) as session:
            grant = await session.get(GiftCardGrant, grant_id)
            if grant is None or grant.user_id != user_id:
                raise ValueError('GIFT_CARD_NOT_FOUND')
            if grant.status == 'claimed':
                raise ValueError('GIFT_CARD_ALREADY_CLAIMED')
            if grant.status != 'pending':
                raise ValueError('GIFT_CARD_NOT_PENDING')
            code = await session.get(RedemptionCode, grant.redemption_code_id)
            if code is None or not code.code:
                raise ValueError('GIFT_CARD_CODE_MISSING')

            redemption = await redeem_code(
                user_id,
                code.code,
                now=current_time,
                db=session,
                commit=False,
            )
            grant = await session.get(GiftCardGrant, grant_id)
            grant.status = 'claimed'
            grant.claimed_at = current_time
            grant.updated_at = current_time
            await session.commit()
            await session.refresh(grant)
            model = GiftCardGrantModel.model_validate(grant)
            return GiftCardClaimResult(
                subscription=redemption.subscription,
                grant=model,
                tier_before=redemption.tier_before,
                tier_after=redemption.tier_after,
                plan_delta_micros=redemption.plan_delta_micros,
                check_delta_micros=redemption.check_delta_micros,
            )

    async def revoke(self, grant_id: str, db: AsyncSession | None = None) -> GiftCardGrantModel:
        async with get_subscription_db_context(db) as session:
            grant = await session.get(GiftCardGrant, grant_id)
            if grant is None:
                raise ValueError('GIFT_CARD_NOT_FOUND')
            if grant.status == 'claimed':
                raise ValueError('GIFT_CARD_ALREADY_CLAIMED')
            grant.status = 'revoked'
            grant.updated_at = now_ts()
            code = await session.get(RedemptionCode, grant.redemption_code_id)
            if code is not None:
                code.is_active = False
                code.updated_at = grant.updated_at
            await session.commit()
            await session.refresh(grant)
            return GiftCardGrantModel.model_validate(grant)


GiftCardGrants = GiftCardGrantsTable()


class SubscriptionReservationModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_id: str
    request_id: str
    model_id: str
    idempotency_key: str
    status: str
    period_start_at: int
    reserved_micros: int
    reserved_plan_micros: int
    reserved_check_micros: int
    actual_cost_micros: int | None = None
    settled_plan_micros: int
    settled_check_micros: int
    refunded_plan_micros: int
    refunded_check_micros: int
    forfeited_plan_micros: int
    unpaid_cost_micros: int
    expires_at: int | None = None
    release_reason: str | None = None
    metadata: dict | None = Field(default=None, alias='meta')
    created_at: int
    updated_at: int
    settled_at: int | None = None
    released_at: int | None = None


class SubscriptionReservationsTable:
    async def get_by_id(
        self,
        reservation_id: str,
        db: AsyncSession | None = None,
    ) -> SubscriptionReservationModel | None:
        async with get_subscription_db_context(db) as session:
            row = await session.get(SubscriptionReservation, reservation_id)
            return SubscriptionReservationModel.model_validate(row) if row else None

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
        db: AsyncSession | None = None,
    ) -> SubscriptionReservationModel | None:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(SubscriptionReservation).where(SubscriptionReservation.idempotency_key == idempotency_key)
            )
            row = result.scalar_one_or_none()
            return SubscriptionReservationModel.model_validate(row) if row else None

    async def get_by_idempotency_keys(
        self,
        idempotency_keys: list[str],
        db: AsyncSession | None = None,
    ) -> dict[str, SubscriptionReservationModel]:
        if not idempotency_keys:
            return {}
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(SubscriptionReservation).where(SubscriptionReservation.idempotency_key.in_(idempotency_keys))
            )
            return {
                row.idempotency_key: SubscriptionReservationModel.model_validate(row) for row in result.scalars().all()
            }

    async def lock_by_id(
        self,
        reservation_id: str,
        db: AsyncSession | None = None,
    ) -> SubscriptionReservationModel | None:
        async with get_subscription_db_context(db) as session:
            locked = await session.execute(
                update(SubscriptionReservation)
                .where(SubscriptionReservation.id == reservation_id)
                .values(updated_at=SubscriptionReservation.updated_at)
            )
            if locked.rowcount != 1:
                return None
            result = await session.execute(
                select(SubscriptionReservation)
                .where(SubscriptionReservation.id == reservation_id)
                .execution_options(populate_existing=True)
            )
            return SubscriptionReservationModel.model_validate(result.scalar_one())

    async def insert(
        self,
        *,
        user_id: str,
        request_id: str,
        model_id: str,
        idempotency_key: str,
        period_start_at: int,
        reserved_micros: int,
        reserved_plan_micros: int,
        reserved_check_micros: int,
        expires_at: int | None,
        metadata: dict | None,
        created_at: int,
        commit: bool = True,
        db: AsyncSession | None = None,
    ) -> SubscriptionReservationModel:
        async with get_subscription_db_context(db) as session:
            row = SubscriptionReservation(
                id=new_id('reservation'),
                user_id=user_id,
                request_id=request_id,
                model_id=model_id,
                idempotency_key=idempotency_key,
                status='active',
                period_start_at=period_start_at,
                reserved_micros=reserved_micros,
                reserved_plan_micros=reserved_plan_micros,
                reserved_check_micros=reserved_check_micros,
                actual_cost_micros=None,
                settled_plan_micros=0,
                settled_check_micros=0,
                refunded_plan_micros=0,
                refunded_check_micros=0,
                forfeited_plan_micros=0,
                unpaid_cost_micros=0,
                expires_at=expires_at,
                meta=json_safe_metadata(metadata),
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(row)
            if commit:
                await session.commit()
                await session.refresh(row)
            else:
                await session.flush()
            return SubscriptionReservationModel.model_validate(row)

    async def update_state(
        self,
        reservation_id: str,
        *,
        values: dict[str, Any],
        commit: bool = True,
        db: AsyncSession | None = None,
    ) -> SubscriptionReservationModel:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                update(SubscriptionReservation).where(SubscriptionReservation.id == reservation_id).values(**values)
            )
            if result.rowcount != 1:
                raise ValueError(f'subscription reservation not found: {reservation_id}')
            if commit:
                await session.commit()
            else:
                await session.flush()
            refreshed = await session.execute(
                select(SubscriptionReservation)
                .where(SubscriptionReservation.id == reservation_id)
                .execution_options(populate_existing=True)
            )
            return SubscriptionReservationModel.model_validate(refreshed.scalar_one())

    async def list_expired_active_ids(
        self,
        *,
        now: int,
        limit: int,
        db: AsyncSession | None = None,
    ) -> list[str]:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(SubscriptionReservation.id)
                .where(
                    SubscriptionReservation.status == 'active',
                    SubscriptionReservation.expires_at.is_not(None),
                    SubscriptionReservation.expires_at <= now,
                )
                .order_by(SubscriptionReservation.expires_at.asc())
                .limit(max(1, limit))
            )
            return list(result.scalars().all())

    async def list_active(
        self,
        *,
        user_id: str | None = None,
        limit: int = 100,
        db: AsyncSession | None = None,
    ) -> list[SubscriptionReservationModel]:
        async with get_subscription_db_context(db) as session:
            filters = [SubscriptionReservation.status == 'active']
            if user_id is not None:
                filters.append(SubscriptionReservation.user_id == user_id)
            result = await session.execute(
                select(SubscriptionReservation)
                .where(*filters)
                .order_by(SubscriptionReservation.created_at.asc())
                .limit(max(1, limit))
            )
            return [SubscriptionReservationModel.model_validate(row) for row in result.scalars().all()]


SubscriptionReservations = SubscriptionReservationsTable()


class SubscriptionUsageModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_id: str
    chat_id: str | None = None
    message_id: str | None = None
    request_id: str | None = None
    idempotency_key: str | None = None
    reservation_id: str | None = None
    model_id: str
    tier: str
    quota_mode: str
    usage_multiplier: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int | None = None
    cache_read_tokens: int | None = None
    total_tokens: int
    input_chatpoint_per_million: str | None = None
    output_chatpoint_per_million: str | None = None
    cache_creation_chatpoint_per_million: str | None = None
    cache_read_chatpoint_per_million: str | None = None
    cost_micros: int
    plan_cost_micros: int
    check_cost_micros: int
    unpaid_cost_micros: int
    plan_balance_after_micros: int | None = None
    check_balance_after_micros: int | None = None
    first_token_latency_ms: int | None = None
    total_duration_ms: int | None = None
    client_ip: str | None = None
    status: str
    raw_usage: dict | None = None
    metadata: dict | None = Field(default=None, alias='meta')
    created_at: int


class SubscriptionUsagePublicModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_id: str
    tier: str
    quota_mode: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int | None = None
    cache_read_tokens: int | None = None
    total_tokens: int
    cost_micros: int
    plan_cost_micros: int
    check_cost_micros: int
    unpaid_cost_micros: int
    first_token_latency_ms: int | None = None
    total_duration_ms: int | None = None
    status: str
    created_at: int


class SubscriptionUsagesTable:
    async def get_by_reservation_id(
        self,
        reservation_id: str,
        db: AsyncSession | None = None,
    ) -> SubscriptionUsageModel | None:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(SubscriptionUsage).where(SubscriptionUsage.reservation_id == reservation_id)
            )
            row = result.scalar_one_or_none()
            return SubscriptionUsageModel.model_validate(row) if row else None

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
        db: AsyncSession | None = None,
    ) -> SubscriptionUsageModel | None:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(SubscriptionUsage).where(SubscriptionUsage.idempotency_key == idempotency_key)
            )
            row = result.scalar_one_or_none()
            return SubscriptionUsageModel.model_validate(row) if row else None

    async def insert(
        self,
        *,
        user_id: str,
        chat_id: str | None,
        message_id: str | None,
        request_id: str | None = None,
        idempotency_key: str | None = None,
        reservation_id: str | None = None,
        model_id: str,
        tier: str,
        quota_mode: str,
        usage_multiplier: str,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int | None = None,
        cache_read_tokens: int | None = None,
        total_tokens: int,
        input_chatpoint_per_million: str | None = None,
        output_chatpoint_per_million: str | None = None,
        cache_creation_chatpoint_per_million: str | None = None,
        cache_read_chatpoint_per_million: str | None = None,
        cost_micros: int,
        plan_cost_micros: int,
        check_cost_micros: int,
        unpaid_cost_micros: int = 0,
        plan_balance_after_micros: int | None,
        check_balance_after_micros: int | None,
        first_token_latency_ms: int | None = None,
        total_duration_ms: int | None = None,
        client_ip: str | None = None,
        status: str,
        raw_usage: dict | None = None,
        metadata: dict | None,
        created_at: int,
        commit: bool = True,
        db: AsyncSession | None = None,
    ) -> SubscriptionUsageModel:
        async with get_subscription_db_context(db) as session:
            row = SubscriptionUsage(
                id=new_id('usage'),
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                request_id=request_id,
                idempotency_key=idempotency_key,
                reservation_id=reservation_id,
                model_id=model_id,
                tier=tier,
                quota_mode=quota_mode,
                usage_multiplier=usage_multiplier,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=cache_read_tokens,
                total_tokens=total_tokens,
                input_chatpoint_per_million=input_chatpoint_per_million,
                output_chatpoint_per_million=output_chatpoint_per_million,
                cache_creation_chatpoint_per_million=cache_creation_chatpoint_per_million,
                cache_read_chatpoint_per_million=cache_read_chatpoint_per_million,
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
                raw_usage=json_safe_metadata(raw_usage),
                meta=json_safe_metadata(metadata),
                created_at=created_at,
            )
            session.add(row)
            if commit:
                await session.commit()
                await session.refresh(row)
            else:
                await session.flush()
            return SubscriptionUsageModel.model_validate(row)

    async def get_usage_summary(
        self,
        *,
        user_id: str | None = None,
        user_email: str | None = None,
        model_id: str | None = None,
        status: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        limit: int | None = 100,
        offset: int = 0,
        include_user: bool = False,
        public: bool = False,
        db: AsyncSession | None = None,
    ) -> dict:
        async with get_subscription_db_context(db) as session:
            filters = []
            if user_id:
                filters.append(SubscriptionUsage.user_id == user_id)
            if user_email:
                filters.append(User.email.ilike(f'%{user_email}%'))
            if model_id:
                filters.append(SubscriptionUsage.model_id == model_id)
            if status:
                filters.append(SubscriptionUsage.status == status)
            if start_at is not None:
                filters.append(SubscriptionUsage.created_at >= start_at)
            if end_at is not None:
                filters.append(SubscriptionUsage.created_at <= end_at)

            if include_user or user_email:
                stmt = select(SubscriptionUsage, User).outerjoin(User, User.id == SubscriptionUsage.user_id)
            else:
                stmt = select(SubscriptionUsage)
            stmt = stmt.where(*filters)
            stmt = stmt.order_by(SubscriptionUsage.created_at.desc()).offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            if include_user:
                usage_rows = result.all()
                usage_models = [SubscriptionUsageModel.model_validate(usage) for usage, _ in usage_rows]
                items = [
                    {
                        'usage': usage_model,
                        'user': user_summary(user),
                        **usage_model.model_dump(by_alias=True),
                    }
                    for usage_model, (_, user) in zip(usage_models, usage_rows)
                ]
            else:
                rows = result.scalars().all()
                usage_models = [SubscriptionUsageModel.model_validate(row) for row in rows]
                if public:
                    items = [SubscriptionUsagePublicModel.model_validate(row) for row in rows]
                else:
                    items = usage_models

            totals_stmt = select(
                func.coalesce(func.sum(SubscriptionUsage.cost_micros), 0),
                func.coalesce(func.sum(SubscriptionUsage.input_tokens), 0),
                func.coalesce(func.sum(SubscriptionUsage.output_tokens), 0),
                func.coalesce(func.sum(SubscriptionUsage.cache_creation_tokens), 0),
                func.coalesce(func.sum(SubscriptionUsage.cache_read_tokens), 0),
                func.coalesce(func.sum(SubscriptionUsage.unpaid_cost_micros), 0),
                func.coalesce(func.sum(SubscriptionUsage.plan_cost_micros), 0),
                func.coalesce(func.sum(SubscriptionUsage.check_cost_micros), 0),
                func.coalesce(func.sum(SubscriptionUsage.total_tokens), 0),
                func.count(SubscriptionUsage.id),
                func.count(func.distinct(func.coalesce(SubscriptionUsage.request_id, SubscriptionUsage.id))),
            )
            if user_email:
                totals_stmt = totals_stmt.select_from(SubscriptionUsage).outerjoin(
                    User, User.id == SubscriptionUsage.user_id
                )
            totals = (await session.execute(totals_stmt.where(*filters))).one()

            model_totals_stmt = select(
                SubscriptionUsage.model_id,
                func.coalesce(func.sum(SubscriptionUsage.total_tokens), 0),
                func.count(func.distinct(func.coalesce(SubscriptionUsage.request_id, SubscriptionUsage.id))),
                func.coalesce(func.sum(SubscriptionUsage.cost_micros), 0),
                func.coalesce(func.sum(SubscriptionUsage.plan_cost_micros), 0),
                func.coalesce(func.sum(SubscriptionUsage.check_cost_micros), 0),
                func.coalesce(func.sum(SubscriptionUsage.unpaid_cost_micros), 0),
            )
            if user_email:
                model_totals_stmt = model_totals_stmt.select_from(SubscriptionUsage).outerjoin(
                    User, User.id == SubscriptionUsage.user_id
                )
            model_totals = (
                await session.execute(
                    model_totals_stmt.where(*filters)
                    .group_by(SubscriptionUsage.model_id)
                    .order_by(func.sum(SubscriptionUsage.total_tokens).desc())
                )
            ).all()
            return {
                'items': items,
                'total_cost_micros': int(totals[0]),
                'total_input_tokens': int(totals[1]),
                'total_output_tokens': int(totals[2]),
                'total_cache_creation_tokens': int(totals[3]),
                'total_cache_read_tokens': int(totals[4]),
                'total_unpaid_cost_micros': int(totals[5]),
                'total_plan_cost_micros': int(totals[6]),
                'total_check_cost_micros': int(totals[7]),
                'total_tokens': int(totals[8]),
                'total_item_count': int(totals[9]),
                'total_request_count': int(totals[10]),
                'model_totals': [
                    {
                        'model_id': model_id,
                        'total_tokens': int(total_tokens),
                        'request_count': int(request_count),
                        'cost_micros': int(cost_micros),
                        'plan_cost_micros': int(plan_cost_micros),
                        'check_cost_micros': int(check_cost_micros),
                        'unpaid_cost_micros': int(unpaid_cost_micros),
                    }
                    for (
                        model_id,
                        total_tokens,
                        request_count,
                        cost_micros,
                        plan_cost_micros,
                        check_cost_micros,
                        unpaid_cost_micros,
                    ) in model_totals
                ],
            }

    async def get_admin_overview(self, db: AsyncSession | None = None) -> dict:
        generated_at = now_ts()
        recent_30d_start_at = generated_at - 30 * 24 * 60 * 60
        summary = await self.get_usage_summary(limit=1, db=db)
        async with get_subscription_db_context(db) as session:
            recent_request_count = (
                await session.execute(
                    select(
                        func.count(func.distinct(func.coalesce(SubscriptionUsage.request_id, SubscriptionUsage.id)))
                    ).where(SubscriptionUsage.created_at >= recent_30d_start_at)
                )
            ).scalar_one()
        return {
            'generated_at': generated_at,
            'recent_30d_start_at': recent_30d_start_at,
            'recent_30d_request_count': int(recent_request_count),
            'total_cost_micros': summary['total_cost_micros'],
            'total_plan_cost_micros': summary['total_plan_cost_micros'],
            'total_check_cost_micros': summary['total_check_cost_micros'],
            'total_unpaid_cost_micros': summary['total_unpaid_cost_micros'],
            'total_input_tokens': summary['total_input_tokens'],
            'total_output_tokens': summary['total_output_tokens'],
            'total_cache_creation_tokens': summary['total_cache_creation_tokens'],
            'total_cache_read_tokens': summary['total_cache_read_tokens'],
            'total_tokens': summary['total_tokens'],
            'total_request_count': summary['total_request_count'],
            'model_totals': summary['model_totals'],
        }

    async def get_daily_request_counts(
        self,
        model_ids: list[str],
        *,
        days: int = 30,
        db: AsyncSession | None = None,
    ) -> dict[str, list[dict[str, int | str]]]:
        if not model_ids:
            return {}

        start_at = now_ts() - max(1, days) * 24 * 60 * 60
        async with get_subscription_db_context(db) as session:
            dialect = session.bind.dialect.name if session.bind is not None else 'sqlite'
            if dialect == 'postgresql':
                day = func.to_char(func.to_timestamp(SubscriptionUsage.created_at), 'YYYY-MM-DD')
            elif dialect in {'mysql', 'mariadb'}:
                day = func.date_format(func.from_unixtime(SubscriptionUsage.created_at), '%Y-%m-%d')
            else:
                day = func.strftime('%Y-%m-%d', SubscriptionUsage.created_at, 'unixepoch')

            result = await session.execute(
                select(
                    SubscriptionUsage.model_id,
                    day.label('day'),
                    func.count(SubscriptionUsage.id).label('count'),
                )
                .where(
                    SubscriptionUsage.model_id.in_(model_ids),
                    SubscriptionUsage.created_at >= start_at,
                )
                .group_by(SubscriptionUsage.model_id, day)
                .order_by(day.asc())
            )
            history: dict[str, list[dict[str, int | str]]] = {model_id: [] for model_id in model_ids}
            for model_id, date, count in result.all():
                history.setdefault(model_id, []).append({'date': str(date), 'count': int(count)})
            return history


SubscriptionUsages = SubscriptionUsagesTable()
