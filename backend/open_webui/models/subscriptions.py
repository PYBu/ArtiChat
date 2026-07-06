from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import AsyncIterator

from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, JSON, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

CHATPOINT_MICROS = 1_000_000
TOKENS_PER_CHATPOINT = 10_000

FREE_TIER = 'free'
PLUS_TIER = 'plus'
CHATPOWER_TIER = 'chatpower'
TIER_RANKS = {FREE_TIER: 0, PLUS_TIER: 1, CHATPOWER_TIER: 2}
DEFAULT_PLAN_CHATPOINTS = {FREE_TIER: Decimal('10'), PLUS_TIER: Decimal('100'), CHATPOWER_TIER: Decimal('500')}
DEFAULT_PERIOD_DAYS = 30


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


class SubscriptionUsage(Base):
    __tablename__ = 'subscription_usage'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    chat_id = Column(Text, nullable=True)
    message_id = Column(Text, nullable=True)
    model_id = Column(Text, nullable=False, index=True)
    tier = Column(Text, nullable=False)
    quota_mode = Column(Text, nullable=False)
    usage_multiplier = Column(Text, nullable=False, default='1')
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_micros = Column(BigInteger, nullable=False, default=0)
    plan_cost_micros = Column(BigInteger, nullable=False, default=0)
    check_cost_micros = Column(BigInteger, nullable=False, default=0)
    plan_balance_after_micros = Column(BigInteger, nullable=True)
    check_balance_after_micros = Column(BigInteger, nullable=True)
    status = Column(Text, nullable=False)
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
            existing = await session.execute(select(SubscriptionPlan.id))
            existing_ids = set(existing.scalars().all())
            timestamp = now_ts()

            defaults = [
                (FREE_TIER, 'Free', 0, DEFAULT_PLAN_CHATPOINTS[FREE_TIER], 'Starter access for basic models.'),
                (PLUS_TIER, 'Plus', 1, DEFAULT_PLAN_CHATPOINTS[PLUS_TIER], 'Expanded access and higher usage.'),
                (
                    CHATPOWER_TIER,
                    'ChatPower',
                    2,
                    DEFAULT_PLAN_CHATPOINTS[CHATPOWER_TIER],
                    'Highest ArtiChat usage tier.',
                ),
            ]
            for plan_id, display_name, rank, allowance, description in defaults:
                if plan_id in existing_ids:
                    continue
                session.add(
                    SubscriptionPlan(
                        id=plan_id,
                        display_name=display_name,
                        tier_rank=rank,
                        period_days=DEFAULT_PERIOD_DAYS,
                        plan_chatpoint_allowance_micros=chatpoint_to_micros(allowance),
                        description=description,
                        features=[],
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


SubscriptionPlans = SubscriptionPlansTable()
