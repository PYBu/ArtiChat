from __future__ import annotations

import hashlib
import time
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Any, AsyncIterator

from open_webui.internal.db import Base, get_async_db_context
from open_webui.models.users import User
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, JSON, Text, or_, select
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
        )

    plan_cost = min(max(plan_balance_micros, 0), cost_micros)
    remaining = cost_micros - plan_cost
    check_cost = remaining

    return DebitResult(
        plan_cost_micros=plan_cost,
        check_cost_micros=check_cost,
        plan_balance_after_micros=plan_balance_micros - plan_cost,
        check_balance_after_micros=check_balance_micros - check_cost,
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
    mode = Column(Text, nullable=False)
    max_uses = Column(Integer, nullable=False)
    used_count = Column(Integer, nullable=False, default=0)
    tier = Column(Text, nullable=True)
    duration_days = Column(Integer, nullable=True)
    plan_chatpoint_micros = Column(BigInteger, nullable=False, default=0)
    check_chatpoint_micros = Column(BigInteger, nullable=False, default=0)
    expires_at = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
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
    plan_balance_after_micros = Column(BigInteger, nullable=True)
    check_balance_after_micros = Column(BigInteger, nullable=True)
    first_token_latency_ms = Column(Integer, nullable=True)
    total_duration_ms = Column(Integer, nullable=True)
    client_ip = Column(Text, nullable=True)
    status = Column(Text, nullable=False)
    raw_usage = Column(JSON, nullable=True)
    meta = Column('metadata', JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)


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
    async def seed_defaults(self, db: AsyncSession | None = None) -> None:
        async with get_subscription_db_context(db) as session:
            existing = await session.execute(select(SubscriptionPlan))
            existing_plans = {plan.id: plan for plan in existing.scalars().all()}
            timestamp = now_ts()

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
                    if plan.display_name in legacy_names:
                        plan.display_name = display_name
                        changed = True
                    if plan.description in legacy_descriptions:
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
            await session.commit()

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
            await session.commit()
            await session.refresh(row)
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
        limit: int = 100,
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
            stmt = stmt.order_by(SubscriptionLedger.created_at.desc()).limit(limit).offset(offset)
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


SubscriptionLedgers = SubscriptionLedgersTable()


class UserSubscriptionsTable:
    async def get_by_user_id(self, user_id: str, db: AsyncSession | None = None) -> UserSubscriptionModel | None:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(select(UserSubscription).filter(UserSubscription.user_id == user_id))
            row = result.scalar_one_or_none()
            return UserSubscriptionModel.model_validate(row) if row else None

    async def create_from_plan(
        self,
        *,
        user_id: str,
        plan_id: str,
        starts_at: int,
        expires_at: int | None,
        source: str,
        db: AsyncSession | None = None,
    ) -> UserSubscriptionModel:
        async with get_subscription_db_context(db) as session:
            plan = await SubscriptionPlans.get_plan_by_id(plan_id, db=session)
            if not plan:
                raise ValueError(f'subscription plan not found: {plan_id}')

            period_end = starts_at + plan.period_days * 24 * 60 * 60
            existing = await session.execute(select(UserSubscription).filter(UserSubscription.user_id == user_id))
            existing_row = existing.scalar_one_or_none()
            check_balance = existing_row.check_balance_micros if existing_row else 0
            row = existing_row or UserSubscription(id=new_id('sub'), user_id=user_id, created_at=starts_at)
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
            await session.commit()
            await session.refresh(row)
            return UserSubscriptionModel.model_validate(row)

    async def save(self, subscription: UserSubscriptionModel, db: AsyncSession | None = None) -> UserSubscriptionModel:
        async with get_subscription_db_context(db) as session:
            row = await session.get(UserSubscription, subscription.id)
            if row is None:
                raise ValueError(f'user subscription not found: {subscription.id}')
            for key, value in subscription.model_dump().items():
                setattr(row, key, value)
            await session.commit()
            await session.refresh(row)
            return UserSubscriptionModel.model_validate(row)

    async def adjust_balances(
        self,
        user_id: str,
        *,
        plan_delta_micros: int = 0,
        check_delta_micros: int = 0,
        event_type: str,
        created_by: str | None,
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
                    db=session,
                )

            row = await session.get(UserSubscription, sub.id)
            row.plan_balance_micros = sub.plan_balance_micros + plan_delta_micros
            row.check_balance_micros = sub.check_balance_micros + check_delta_micros
            row.updated_at = now_ts()
            await session.commit()
            await session.refresh(row)
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
                created_by=created_by,
                db=session,
            )
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


def generate_redemption_code() -> str:
    return f'ARTI-{secrets.token_urlsafe(6).upper()}-{secrets.token_urlsafe(6).upper()}'


class RedemptionCodeCreateResult(BaseModel):
    raw_codes: list[str]
    code_ids: list[str]


class RedemptionCodeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str | None = None
    code_hash: str
    code_preview: str
    mode: str
    max_uses: int
    used_count: int
    tier: str | None = None
    duration_days: int | None = None
    plan_chatpoint_micros: int
    check_chatpoint_micros: int
    expires_at: int | None = None
    is_active: bool
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
        batch_id: str | None = None,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> RedemptionCodeCreateResult:
        if mode not in {'single_use', 'multi_use'}:
            raise ValueError('redemption mode must be single_use or multi_use')
        if quantity < 1:
            raise ValueError('quantity must be greater than 0')
        if max_uses < 1:
            raise ValueError('max_uses must be greater than 0')
        if mode == 'multi_use' and quantity != 1:
            raise ValueError('multi_use creation creates exactly one code')
        if custom_code and quantity != 1:
            raise ValueError('custom_code can only create one code at a time')

        timestamp = now or now_ts()
        resolved_batch_id = batch_id or new_id('batch')
        raw_codes = []
        code_ids = []

        async with get_subscription_db_context(db) as session:
            for _ in range(quantity):
                raw_code = normalize_redemption_code(custom_code) if custom_code else generate_redemption_code()
                existing = await session.execute(
                    select(RedemptionCode).filter(RedemptionCode.code_hash == hash_redemption_code(raw_code))
                )
                if existing.scalar_one_or_none() is not None:
                    raise ValueError('REDEMPTION_CODE_DUPLICATE')
                code_id = new_id('code')
                session.add(
                    RedemptionCode(
                        id=code_id,
                        code=raw_code,
                        code_hash=hash_redemption_code(raw_code),
                        code_preview=preview_redemption_code(raw_code),
                        mode=mode,
                        max_uses=max_uses,
                        used_count=0,
                        tier=tier,
                        duration_days=duration_days,
                        plan_chatpoint_micros=plan_chatpoint_micros,
                        check_chatpoint_micros=check_chatpoint_micros,
                        expires_at=expires_at,
                        is_active=True,
                        batch_id=resolved_batch_id,
                        memo=memo,
                        created_by=created_by,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                raw_codes.append(raw_code)
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

    async def increment_used_count(self, code_id: str, db: AsyncSession | None = None) -> RedemptionCodeModel:
        async with get_subscription_db_context(db) as session:
            row = await session.get(RedemptionCode, code_id)
            if not row:
                raise ValueError('REDEMPTION_CODE_INVALID')
            row.used_count += 1
            row.updated_at = now_ts()
            await session.commit()
            await session.refresh(row)
            return RedemptionCodeModel.model_validate(row)

    async def list_codes(
        self, *, limit: int = 100, offset: int = 0, db: AsyncSession | None = None
    ) -> list[RedemptionCodeModel]:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(RedemptionCode).order_by(RedemptionCode.created_at.desc()).limit(limit).offset(offset)
            )
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
            if code.code_hash and not code.code_hash.startswith('deleted:'):
                code.code_hash = f'deleted:{code.id}:{code.code_hash}'
            code.updated_at = now_ts()
            await session.commit()
            await session.refresh(code)
            return RedemptionCodeModel.model_validate(code)


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
            await session.commit()
            await session.refresh(row)
            return RedemptionRecordModel.model_validate(row)

    async def list_for_code(
        self, code_id: str, *, db: AsyncSession | None = None
    ) -> list[RedemptionRecordModel]:
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
                        mode='single_use',
                        max_uses=1,
                        used_count=0,
                        tier=tier,
                        duration_days=duration_days,
                        plan_chatpoint_micros=plan_chatpoint_micros,
                        check_chatpoint_micros=check_chatpoint_micros,
                        expires_at=expires_at,
                        is_active=True,
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
        self, user_id: str, *, db: AsyncSession | None = None
    ) -> list[GiftCardGrantModel]:
        async with get_subscription_db_context(db) as session:
            result = await session.execute(
                select(GiftCardGrant)
                .filter(GiftCardGrant.user_id == user_id, GiftCardGrant.status == 'pending')
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

            redemption = await redeem_code(user_id, code.code, now=current_time, db=session)
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


class SubscriptionUsageModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_id: str
    chat_id: str | None = None
    message_id: str | None = None
    model_id: str
    tier: str
    quota_mode: str
    usage_multiplier: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_micros: int
    plan_cost_micros: int
    check_cost_micros: int
    plan_balance_after_micros: int | None = None
    check_balance_after_micros: int | None = None
    status: str
    metadata: dict | None = Field(default=None, alias='meta')
    created_at: int


class SubscriptionUsagesTable:
    async def insert(
        self,
        *,
        user_id: str,
        chat_id: str | None,
        message_id: str | None,
        model_id: str,
        tier: str,
        quota_mode: str,
        usage_multiplier: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_micros: int,
        plan_cost_micros: int,
        check_cost_micros: int,
        plan_balance_after_micros: int | None,
        check_balance_after_micros: int | None,
        status: str,
        metadata: dict | None,
        created_at: int,
        db: AsyncSession | None = None,
    ) -> SubscriptionUsageModel:
        async with get_subscription_db_context(db) as session:
            row = SubscriptionUsage(
                id=new_id('usage'),
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                model_id=model_id,
                tier=tier,
                quota_mode=quota_mode,
                usage_multiplier=usage_multiplier,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_micros=cost_micros,
                plan_cost_micros=plan_cost_micros,
                check_cost_micros=check_cost_micros,
                plan_balance_after_micros=plan_balance_after_micros,
                check_balance_after_micros=check_balance_after_micros,
                status=status,
                meta=json_safe_metadata(metadata),
                created_at=created_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return SubscriptionUsageModel.model_validate(row)

    async def get_usage_summary(
        self,
        *,
        user_id: str | None = None,
        model_id: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        limit: int = 100,
        offset: int = 0,
        include_user: bool = False,
        db: AsyncSession | None = None,
    ) -> dict:
        async with get_subscription_db_context(db) as session:
            if include_user:
                stmt = select(SubscriptionUsage, User).outerjoin(User, User.id == SubscriptionUsage.user_id)
            else:
                stmt = select(SubscriptionUsage)
            if user_id:
                stmt = stmt.filter(SubscriptionUsage.user_id == user_id)
            if model_id:
                stmt = stmt.filter(SubscriptionUsage.model_id == model_id)
            if start_at is not None:
                stmt = stmt.filter(SubscriptionUsage.created_at >= start_at)
            if end_at is not None:
                stmt = stmt.filter(SubscriptionUsage.created_at <= end_at)
            result = await session.execute(
                stmt.order_by(SubscriptionUsage.created_at.desc()).limit(limit).offset(offset)
            )
            if include_user:
                items = [
                    {
                        'usage': SubscriptionUsageModel.model_validate(usage),
                        'user': user_summary(user),
                        **SubscriptionUsageModel.model_validate(usage).model_dump(by_alias=True),
                    }
                    for usage, user in result.all()
                ]
                usage_models = [item['usage'] for item in items]
            else:
                usage_models = [SubscriptionUsageModel.model_validate(row) for row in result.scalars().all()]
                items = usage_models
            return {
                'items': items,
                'total_cost_micros': sum(item.cost_micros for item in usage_models),
                'total_input_tokens': sum(item.input_tokens for item in usage_models),
                'total_output_tokens': sum(item.output_tokens for item in usage_models),
            }


SubscriptionUsages = SubscriptionUsagesTable()
