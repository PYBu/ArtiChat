from __future__ import annotations

import hashlib
import time
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import AsyncIterator

from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict, Field
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
                meta=metadata,
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


UserSubscriptions = UserSubscriptionsTable()


def hash_redemption_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode('utf-8')).hexdigest()


def preview_redemption_code(code: str) -> str:
    normalized = code.strip().upper()
    return f'{normalized[:4]}-{normalized[-4:]}'


def generate_redemption_code() -> str:
    return f'ARTI-{secrets.token_urlsafe(6).upper()}-{secrets.token_urlsafe(6).upper()}'


class RedemptionCodeCreateResult(BaseModel):
    raw_codes: list[str]
    code_ids: list[str]


class RedemptionCodeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
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

        timestamp = now or now_ts()
        batch_id = new_id('batch')
        raw_codes = []
        code_ids = []

        async with get_subscription_db_context(db) as session:
            for _ in range(quantity):
                raw_code = generate_redemption_code()
                code_id = new_id('code')
                session.add(
                    RedemptionCode(
                        id=code_id,
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
                        batch_id=batch_id,
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


RedemptionRecords = RedemptionRecordsTable()
