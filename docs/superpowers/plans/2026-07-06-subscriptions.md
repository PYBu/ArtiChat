# ArtiChat Subscriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved ArtiChat subscription MVP: tiered model access, Plan/Check Chatpoint balances, redemption codes, usage billing, user UI, lower-left quota ring, and admin management.

**Architecture:** Add a focused subscription backend module with SQLAlchemy tables, service functions, and a `/api/v1/subscriptions` router. Store model subscription policy in `model.meta.subscription`, enforce it in `/api/models` and `/api/chat/completions`, and debit Chatpoint from normalized provider usage after chat responses complete. Add user and admin Svelte panels that use the existing settings/admin layouts.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, Alembic, Pydantic, pytest/pytest-asyncio, Svelte, TypeScript fetch API helpers, Tailwind utility classes, existing ArtiChat settings/admin components.

---

## Scope Check

This plan covers one MVP but splits it into independently testable stages. Backend accounting, lifecycle, redemption, model policy, runtime billing, user UI, and admin UI each have their own commit. Do not start a later stage until the prior stage is green, because later UI and runtime hooks depend on the service contracts created first.

## File Structure

Create:

- `backend/open_webui/models/subscriptions.py`: SQLAlchemy tables, Pydantic response models, constants, fixed-point Chatpoint helpers, and table access methods.
- `backend/open_webui/utils/subscriptions.py`: subscription lifecycle, redemption, model policy, quota checks, usage billing, and admin mutation service functions.
- `backend/open_webui/routers/subscriptions.py`: user and admin API routes.
- `backend/open_webui/migrations/versions/e7f8a9b0c1d2_add_subscription_tables.py`: Alembic migration connected to current head `42e2978c7933`.
- `backend/open_webui/tests/subscriptions/conftest.py`: async SQLite test fixture.
- `backend/open_webui/tests/subscriptions/test_accounting.py`
- `backend/open_webui/tests/subscriptions/test_lifecycle.py`
- `backend/open_webui/tests/subscriptions/test_redemption.py`
- `backend/open_webui/tests/subscriptions/test_model_policy.py`
- `backend/open_webui/tests/subscriptions/test_usage_billing.py`
- `backend/open_webui/tests/subscriptions/test_router_contract.py`
- `src/lib/apis/subscriptions/index.ts`: frontend API client.
- `src/lib/components/chat/Settings/Subscription.svelte`: user subscription plan page.
- `src/lib/components/chat/Settings/RedeemCode.svelte`: user redemption page.
- `src/lib/components/chat/Settings/Usage.svelte`: user usage page.
- `src/lib/components/chat/Settings/Account/BillingAddress.svelte`: billing address editor.
- `src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte`: lower-left quota ring and popover.
- `src/lib/components/admin/Settings/Subscriptions.svelte`: admin subscriptions shell.
- `src/lib/components/admin/Settings/Subscriptions/Plans.svelte`
- `src/lib/components/admin/Settings/Subscriptions/ModelAccess.svelte`
- `src/lib/components/admin/Settings/Subscriptions/RedeemCodes.svelte`
- `src/lib/components/admin/Settings/Subscriptions/UserSubscriptions.svelte`
- `src/lib/components/admin/Settings/Subscriptions/UsageLedger.svelte`
- `src/lib/components/workspace/Models/SubscriptionPolicy.svelte`: model editor policy section.
- `scripts/check-subscriptions.mjs`: static guard for required subscription UI/API files and strings.

Modify:

- `backend/open_webui/main.py`: include subscription router, apply model filtering, add preflight quota checks, pass subscription context into response handling.
- `backend/open_webui/utils/middleware.py`: call billing hook after normalized usage is available in non-streaming and streaming paths.
- `backend/open_webui/models/models.py`: validate subscription policy in `ModelMeta` while preserving extra meta fields.
- `backend/open_webui/routers/models.py`: expose/admin-update model policies through subscription router rather than duplicating model route logic.
- `src/lib/components/chat/SettingsModal.svelte`: add Subscription, Redeem Code, and Usage tabs.
- `src/lib/components/chat/Settings/Account.svelte`: mount billing address and records summary.
- `src/lib/components/layout/Sidebar/UserMenu.svelte`: show plan badge, quota ring, and click-through to Usage.
- `src/lib/components/admin/Settings.svelte`: add Subscriptions admin settings tab.
- `src/lib/components/admin/Users/UserList/EditUserModal.svelte`: show compact subscription summary and "Manage Subscription" link.
- `src/lib/components/workspace/Models/ModelEditor.svelte`: mount `SubscriptionPolicy.svelte` and submit `meta.subscription`.
- `package.json`: add `test:subscriptions` script for the static guard.

## Common Commands

Use these commands from `C:\Users\admin\Desktop\Pro\ArtiChat\.worktrees\artichat-brand-whitelabel`.

Backend focused tests:

```powershell
python -m pytest backend/open_webui/tests/subscriptions -q
```

Frontend static subscription guard:

```powershell
npm run test:subscriptions
```

Branding guard after UI work:

```powershell
npm run test:branding
```

Full frontend type check is currently known to fail on unrelated existing files. Run it after UI work to capture status, but do not treat existing unrelated failures as subscription regressions:

```powershell
npm run check
```

---

### Task 1: Chatpoint Arithmetic Helpers

**Files:**
- Create: `backend/open_webui/tests/subscriptions/test_accounting.py`
- Create: `backend/open_webui/models/subscriptions.py`

- [ ] **Step 1: Write the failing accounting tests**

Add `backend/open_webui/tests/subscriptions/test_accounting.py`:

```python
from decimal import Decimal

from open_webui.models.subscriptions import (
    CHATPOINT_MICROS,
    calculate_cost_micros,
    chatpoint_to_micros,
    debit_balances,
    micros_to_chatpoint,
)


def test_chatpoint_conversion_uses_fixed_precision():
    assert CHATPOINT_MICROS == 1_000_000
    assert chatpoint_to_micros(Decimal('1')) == 1_000_000
    assert chatpoint_to_micros(Decimal('0.000001')) == 1
    assert micros_to_chatpoint(1_500_000) == Decimal('1.5')


def test_cost_uses_tokens_per_chatpoint_and_multiplier():
    assert calculate_cost_micros(total_tokens=10_000, usage_multiplier='1') == 1_000_000
    assert calculate_cost_micros(total_tokens=10_000, usage_multiplier='2.5') == 2_500_000
    assert calculate_cost_micros(total_tokens=1, usage_multiplier='1') == 100


def test_cost_rounds_up_to_avoid_underbilling():
    assert calculate_cost_micros(total_tokens=1, usage_multiplier='0.001') == 1


def test_negative_multiplier_is_rejected():
    try:
        calculate_cost_micros(total_tokens=10_000, usage_multiplier='-1')
    except ValueError as exc:
        assert 'usage_multiplier must be greater than or equal to 0' in str(exc)
    else:
        raise AssertionError('negative multiplier should fail')


def test_debit_uses_plan_before_check():
    result = debit_balances(plan_balance_micros=1_000_000, check_balance_micros=2_000_000, cost_micros=2_500_000)

    assert result.plan_cost_micros == 1_000_000
    assert result.check_cost_micros == 1_500_000
    assert result.plan_balance_after_micros == 0
    assert result.check_balance_after_micros == 500_000


def test_debit_can_make_check_balance_negative():
    result = debit_balances(plan_balance_micros=500_000, check_balance_micros=250_000, cost_micros=1_000_000)

    assert result.plan_cost_micros == 500_000
    assert result.check_cost_micros == 500_000
    assert result.plan_balance_after_micros == 0
    assert result.check_balance_after_micros == -250_000
```

- [ ] **Step 2: Verify the tests fail for the expected reason**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_accounting.py -q
```

Expected: FAIL because `open_webui.models.subscriptions` does not exist or the requested helper functions are missing.

- [ ] **Step 3: Implement the arithmetic helpers**

Create the top of `backend/open_webui/models/subscriptions.py` with this code:

```python
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Any

from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, JSON, String, Text, select
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
```

- [ ] **Step 4: Verify the accounting tests pass**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_accounting.py -q
```

Expected: PASS for all tests in `test_accounting.py`.

- [ ] **Step 5: Commit**

```powershell
git add backend/open_webui/models/subscriptions.py backend/open_webui/tests/subscriptions/test_accounting.py
git commit -m "feat: add Chatpoint accounting helpers"
```

---

### Task 2: Subscription Tables, Migration, And Seed Defaults

**Files:**
- Modify: `backend/open_webui/models/subscriptions.py`
- Create: `backend/open_webui/migrations/versions/e7f8a9b0c1d2_add_subscription_tables.py`
- Create: `backend/open_webui/tests/subscriptions/conftest.py`
- Create: `backend/open_webui/tests/subscriptions/test_lifecycle.py`

- [ ] **Step 1: Write failing table and seed tests**

Create `backend/open_webui/tests/subscriptions/conftest.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from open_webui.internal.db import Base


@pytest.fixture()
async def db_session(tmp_path):
    import open_webui.models.subscriptions  # noqa: F401
    import open_webui.models.users  # noqa: F401

    db_path = tmp_path / 'subscriptions-test.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_path}', connect_args={'check_same_thread': False})

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()
```

Create `backend/open_webui/tests/subscriptions/test_lifecycle.py` with the first table tests:

```python
import pytest

from open_webui.models.subscriptions import (
    CHATPOWER_TIER,
    FREE_TIER,
    PLUS_TIER,
    SubscriptionPlans,
    chatpoint_to_micros,
)


@pytest.mark.asyncio
async def test_seed_default_plans_creates_three_tiers(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    plans = await SubscriptionPlans.get_plans(db=db_session)
    by_id = {plan.id: plan for plan in plans}

    assert set(by_id) == {FREE_TIER, PLUS_TIER, CHATPOWER_TIER}
    assert by_id[FREE_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(10)
    assert by_id[PLUS_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(100)
    assert by_id[CHATPOWER_TIER].plan_chatpoint_allowance_micros == chatpoint_to_micros(500)
    assert by_id[FREE_TIER].period_days == 30


@pytest.mark.asyncio
async def test_seed_default_plans_is_idempotent(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await SubscriptionPlans.seed_defaults(db=db_session)

    plans = await SubscriptionPlans.get_plans(db=db_session)

    assert len(plans) == 3
```

- [ ] **Step 2: Verify the tests fail for missing tables/classes**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_lifecycle.py -q
```

Expected: FAIL because `SubscriptionPlans` and SQLAlchemy table classes are not implemented.

- [ ] **Step 3: Add SQLAlchemy tables and Pydantic models**

Append these table and response models to `backend/open_webui/models/subscriptions.py`:

```python
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
    metadata = Column(JSON, nullable=True)
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
    metadata = Column(JSON, nullable=True)
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
```

- [ ] **Step 4: Add plan table access methods**

Append this table access object to `backend/open_webui/models/subscriptions.py`:

```python
class SubscriptionPlansTable:
    async def seed_defaults(self, db: AsyncSession | None = None) -> None:
        async with get_async_db_context(db) as session:
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
        async with get_async_db_context(db) as session:
            result = await session.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order.asc()))
            return [SubscriptionPlanModel.model_validate(row) for row in result.scalars().all()]

    async def get_plan_by_id(self, plan_id: str, db: AsyncSession | None = None) -> SubscriptionPlanModel | None:
        async with get_async_db_context(db) as session:
            plan = await session.get(SubscriptionPlan, plan_id)
            return SubscriptionPlanModel.model_validate(plan) if plan else None


SubscriptionPlans = SubscriptionPlansTable()
```

- [ ] **Step 5: Add the Alembic migration**

Create `backend/open_webui/migrations/versions/e7f8a9b0c1d2_add_subscription_tables.py`:

```python
"""Add subscription tables

Revision ID: e7f8a9b0c1d2
Revises: 42e2978c7933
Create Date: 2026-07-06 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = '42e2978c7933'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'subscription_plan' not in existing_tables:
        op.create_table(
            'subscription_plan',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('display_name', sa.Text(), nullable=False),
            sa.Column('tier_rank', sa.Integer(), nullable=False),
            sa.Column('period_days', sa.Integer(), nullable=False),
            sa.Column('plan_chatpoint_allowance_micros', sa.BigInteger(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('features', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )

    if 'user_subscription' not in existing_tables:
        op.create_table(
            'user_subscription',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('user_id', sa.Text(), nullable=False, unique=True),
            sa.Column('tier', sa.Text(), nullable=False),
            sa.Column('tier_rank', sa.Integer(), nullable=False),
            sa.Column('display_name', sa.Text(), nullable=False),
            sa.Column('period_days', sa.Integer(), nullable=False),
            sa.Column('plan_chatpoint_allowance_micros', sa.BigInteger(), nullable=False),
            sa.Column('plan_balance_micros', sa.BigInteger(), nullable=False),
            sa.Column('check_balance_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('starts_at', sa.BigInteger(), nullable=False),
            sa.Column('expires_at', sa.BigInteger(), nullable=True),
            sa.Column('period_start_at', sa.BigInteger(), nullable=False),
            sa.Column('period_end_at', sa.BigInteger(), nullable=False),
            sa.Column('next_reset_at', sa.BigInteger(), nullable=False),
            sa.Column('status', sa.Text(), nullable=False),
            sa.Column('source', sa.Text(), nullable=False),
            sa.Column('snapshot', sa.JSON(), nullable=True),
            sa.Column('billing_address', sa.JSON(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_user_subscription_user_id', 'user_subscription', ['user_id'])

    if 'subscription_ledger' not in existing_tables:
        op.create_table(
            'subscription_ledger',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('event_type', sa.Text(), nullable=False),
            sa.Column('tier_before', sa.Text(), nullable=True),
            sa.Column('tier_after', sa.Text(), nullable=True),
            sa.Column('plan_delta_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('check_delta_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('plan_balance_after_micros', sa.BigInteger(), nullable=False),
            sa.Column('check_balance_after_micros', sa.BigInteger(), nullable=False),
            sa.Column('reference_type', sa.Text(), nullable=True),
            sa.Column('reference_id', sa.Text(), nullable=True),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_by', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_subscription_ledger_user_id', 'subscription_ledger', ['user_id'])

    if 'redemption_code' not in existing_tables:
        op.create_table(
            'redemption_code',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('code_hash', sa.Text(), nullable=False, unique=True),
            sa.Column('code_preview', sa.Text(), nullable=False),
            sa.Column('mode', sa.Text(), nullable=False),
            sa.Column('max_uses', sa.Integer(), nullable=False),
            sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('tier', sa.Text(), nullable=True),
            sa.Column('duration_days', sa.Integer(), nullable=True),
            sa.Column('plan_chatpoint_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('check_chatpoint_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('expires_at', sa.BigInteger(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
            sa.Column('batch_id', sa.Text(), nullable=True),
            sa.Column('memo', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Text(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_redemption_code_code_hash', 'redemption_code', ['code_hash'])

    if 'redemption_record' not in existing_tables:
        op.create_table(
            'redemption_record',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('redemption_code_id', sa.Text(), nullable=False),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('tier_before', sa.Text(), nullable=True),
            sa.Column('tier_after', sa.Text(), nullable=True),
            sa.Column('plan_delta_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('check_delta_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('subscription_expires_at_before', sa.BigInteger(), nullable=True),
            sa.Column('subscription_expires_at_after', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_redemption_record_code_id', 'redemption_record', ['redemption_code_id'])
        op.create_index('ix_redemption_record_user_id', 'redemption_record', ['user_id'])
        op.create_index(
            'redemption_record_code_user_idx',
            'redemption_record',
            ['redemption_code_id', 'user_id'],
            unique=True,
        )

    if 'subscription_usage' not in existing_tables:
        op.create_table(
            'subscription_usage',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('chat_id', sa.Text(), nullable=True),
            sa.Column('message_id', sa.Text(), nullable=True),
            sa.Column('model_id', sa.Text(), nullable=False),
            sa.Column('tier', sa.Text(), nullable=False),
            sa.Column('quota_mode', sa.Text(), nullable=False),
            sa.Column('usage_multiplier', sa.Text(), nullable=False),
            sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('cost_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('plan_cost_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('check_cost_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('plan_balance_after_micros', sa.BigInteger(), nullable=True),
            sa.Column('check_balance_after_micros', sa.BigInteger(), nullable=True),
            sa.Column('status', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_subscription_usage_user_id', 'subscription_usage', ['user_id'])
        op.create_index('ix_subscription_usage_model_id', 'subscription_usage', ['model_id'])


def downgrade() -> None:
    for index_name, table_name in [
        ('ix_subscription_usage_model_id', 'subscription_usage'),
        ('ix_subscription_usage_user_id', 'subscription_usage'),
        ('redemption_record_code_user_idx', 'redemption_record'),
        ('ix_redemption_record_user_id', 'redemption_record'),
        ('ix_redemption_record_code_id', 'redemption_record'),
        ('ix_redemption_code_code_hash', 'redemption_code'),
        ('ix_subscription_ledger_user_id', 'subscription_ledger'),
        ('ix_user_subscription_user_id', 'user_subscription'),
    ]:
        try:
            op.drop_index(index_name, table_name=table_name)
        except Exception:
            pass

    for table_name in [
        'subscription_usage',
        'redemption_record',
        'redemption_code',
        'subscription_ledger',
        'user_subscription',
        'subscription_plan',
    ]:
        try:
            op.drop_table(table_name)
        except Exception:
            pass
```

- [ ] **Step 6: Verify tests pass**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_lifecycle.py::test_seed_default_plans_creates_three_tiers backend/open_webui/tests/subscriptions/test_lifecycle.py::test_seed_default_plans_is_idempotent -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/open_webui/models/subscriptions.py backend/open_webui/migrations/versions/e7f8a9b0c1d2_add_subscription_tables.py backend/open_webui/tests/subscriptions
git commit -m "feat: add subscription schema and plan seeds"
```

---

### Task 3: Subscription Lifecycle Service

**Files:**
- Modify: `backend/open_webui/models/subscriptions.py`
- Create: `backend/open_webui/utils/subscriptions.py`
- Modify: `backend/open_webui/tests/subscriptions/test_lifecycle.py`

- [ ] **Step 1: Add failing lifecycle tests**

Append to `backend/open_webui/tests/subscriptions/test_lifecycle.py`:

```python
import time

from open_webui.models.subscriptions import SubscriptionLedgers, UserSubscriptions
from open_webui.utils.subscriptions import ensure_subscription_current


@pytest.mark.asyncio
async def test_new_user_gets_free_subscription(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    subscription = await ensure_subscription_current('user-1', now=1_720_000_000, db=db_session)

    assert subscription.user_id == 'user-1'
    assert subscription.tier == FREE_TIER
    assert subscription.plan_balance_micros == chatpoint_to_micros(10)
    assert subscription.check_balance_micros == 0
    assert subscription.period_end_at == 1_720_000_000 + 30 * 24 * 60 * 60


@pytest.mark.asyncio
async def test_period_reset_preserves_check_balance(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    subscription = await ensure_subscription_current('user-2', now=1_720_000_000, db=db_session)
    await UserSubscriptions.adjust_balances(
        'user-2',
        plan_delta_micros=-chatpoint_to_micros(7),
        check_delta_micros=chatpoint_to_micros(25),
        event_type='admin_adjustment',
        created_by='admin',
        db=db_session,
    )

    reset = await ensure_subscription_current('user-2', now=subscription.period_end_at + 10, db=db_session)

    assert reset.plan_balance_micros == chatpoint_to_micros(10)
    assert reset.check_balance_micros == chatpoint_to_micros(25)
    assert reset.period_start_at == subscription.period_end_at


@pytest.mark.asyncio
async def test_expired_plus_auto_downgrades_to_free_before_reset(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    start = 1_720_000_000
    await UserSubscriptions.create_from_plan(
        user_id='user-3',
        plan_id=PLUS_TIER,
        starts_at=start,
        expires_at=start + 30 * 24 * 60 * 60,
        source='redemption',
        db=db_session,
    )

    subscription = await ensure_subscription_current('user-3', now=start + 31 * 24 * 60 * 60, db=db_session)

    assert subscription.tier == FREE_TIER
    assert subscription.plan_chatpoint_allowance_micros == chatpoint_to_micros(10)
    assert subscription.plan_balance_micros == chatpoint_to_micros(10)

    ledger = await SubscriptionLedgers.get_recent_for_user('user-3', limit=5, db=db_session)
    assert any(entry.event_type == 'auto_downgrade' for entry in ledger)
```

- [ ] **Step 2: Verify lifecycle tests fail**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_lifecycle.py -q
```

Expected: FAIL because `ensure_subscription_current`, `UserSubscriptions`, and `SubscriptionLedgers` are not implemented.

- [ ] **Step 3: Add subscription Pydantic models and table methods**

Append to `backend/open_webui/models/subscriptions.py`:

```python
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
    model_config = ConfigDict(from_attributes=True)

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
    metadata: dict | None = None
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
        async with get_async_db_context(db) as session:
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
                metadata=metadata,
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
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(SubscriptionLedger)
                .filter(SubscriptionLedger.user_id == user_id)
                .order_by(SubscriptionLedger.created_at.desc())
                .limit(limit)
            )
            return [SubscriptionLedgerModel.model_validate(row) for row in result.scalars().all()]


SubscriptionLedgers = SubscriptionLedgersTable()
```

Also append `UserSubscriptionsTable` with these methods:

```python
class UserSubscriptionsTable:
    async def get_by_user_id(self, user_id: str, db: AsyncSession | None = None) -> UserSubscriptionModel | None:
        async with get_async_db_context(db) as session:
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
        async with get_async_db_context(db) as session:
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
        async with get_async_db_context(db) as session:
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
        async with get_async_db_context(db) as session:
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
            before_plan = sub.plan_balance_micros
            before_check = sub.check_balance_micros
            row = await session.get(UserSubscription, sub.id)
            row.plan_balance_micros = before_plan + plan_delta_micros
            row.check_balance_micros = before_check + check_delta_micros
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
```

- [ ] **Step 4: Implement lifecycle service**

Create `backend/open_webui/utils/subscriptions.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

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
        periods_elapsed = max(1, (current_time - subscription.period_start_at) // period_seconds(subscription.period_days))
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
```

- [ ] **Step 5: Verify lifecycle tests pass**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_lifecycle.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/open_webui/models/subscriptions.py backend/open_webui/utils/subscriptions.py backend/open_webui/tests/subscriptions
git commit -m "feat: add subscription lifecycle service"
```

---

### Task 4: Redemption Code Service

**Files:**
- Modify: `backend/open_webui/models/subscriptions.py`
- Modify: `backend/open_webui/utils/subscriptions.py`
- Create: `backend/open_webui/tests/subscriptions/test_redemption.py`

- [ ] **Step 1: Write failing redemption tests**

Create `backend/open_webui/tests/subscriptions/test_redemption.py`:

```python
import pytest

from open_webui.models.subscriptions import (
    CHATPOWER_TIER,
    FREE_TIER,
    PLUS_TIER,
    RedemptionCodes,
    RedemptionRecords,
    SubscriptionPlans,
    UserSubscriptions,
    chatpoint_to_micros,
)
from open_webui.utils.subscriptions import redeem_code


@pytest.mark.asyncio
async def test_single_use_code_can_only_be_redeemed_once(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    created = await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=0,
        expires_at=None,
        memo='plus trial',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    result = await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)
    assert result.subscription.tier == PLUS_TIER

    with pytest.raises(ValueError, match='REDEMPTION_CODE_EXHAUSTED'):
        await redeem_code('user-2', created.raw_codes[0], now=1_720_000_010, db=db_session)


@pytest.mark.asyncio
async def test_multi_use_code_prevents_same_user_redeeming_twice(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    created = await RedemptionCodes.create_codes(
        mode='multi_use',
        quantity=1,
        max_uses=5,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=chatpoint_to_micros(25),
        expires_at=None,
        memo='check topup',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)
    with pytest.raises(ValueError, match='REDEMPTION_CODE_ALREADY_USED'):
        await redeem_code('user-1', created.raw_codes[0], now=1_720_000_001, db=db_session)


@pytest.mark.asyncio
async def test_lower_tier_code_does_not_downgrade_higher_subscription(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await UserSubscriptions.create_from_plan(
        user_id='user-1',
        plan_id=CHATPOWER_TIER,
        starts_at=1_720_000_000,
        expires_at=1_720_000_000 + 30 * 24 * 60 * 60,
        source='admin',
        db=db_session,
    )
    created = await RedemptionCodes.create_codes(
        mode='multi_use',
        quantity=1,
        max_uses=10,
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=chatpoint_to_micros(3),
        check_chatpoint_micros=chatpoint_to_micros(4),
        expires_at=None,
        memo='lower tier grant',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    result = await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)

    assert result.subscription.tier == CHATPOWER_TIER
    assert result.subscription.plan_balance_micros == chatpoint_to_micros(503)
    assert result.subscription.check_balance_micros == chatpoint_to_micros(4)
```

- [ ] **Step 2: Verify redemption tests fail**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_redemption.py -q
```

Expected: FAIL because `RedemptionCodes`, `RedemptionRecords`, and `redeem_code` are missing.

- [ ] **Step 3: Add redemption model helpers**

Append to `backend/open_webui/models/subscriptions.py`:

```python
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
        if mode == 'multi_use' and quantity != 1:
            raise ValueError('multi_use creation creates exactly one code')

        timestamp = now or now_ts()
        batch_id = new_id('batch')
        raw_codes = []
        code_ids = []

        async with get_async_db_context(db) as session:
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
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(RedemptionCode).filter(RedemptionCode.code_hash == hash_redemption_code(code))
            )
            row = result.scalar_one_or_none()
            return RedemptionCodeModel.model_validate(row) if row else None

    async def increment_used_count(self, code_id: str, db: AsyncSession | None = None) -> RedemptionCodeModel:
        async with get_async_db_context(db) as session:
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
        async with get_async_db_context(db) as session:
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
        async with get_async_db_context(db) as session:
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
```

- [ ] **Step 4: Add redemption service**

Append to `backend/open_webui/utils/subscriptions.py`:

```python
from pydantic import BaseModel

from open_webui.models.subscriptions import (
    RedemptionCodes,
    RedemptionRecords,
    SubscriptionPlans,
    UserSubscriptions,
)


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
```

- [ ] **Step 5: Verify redemption tests pass**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_redemption.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/open_webui/models/subscriptions.py backend/open_webui/utils/subscriptions.py backend/open_webui/tests/subscriptions/test_redemption.py
git commit -m "feat: add subscription redemption service"
```

---

### Task 5: Model Subscription Policy

**Files:**
- Modify: `backend/open_webui/utils/subscriptions.py`
- Modify: `backend/open_webui/models/models.py`
- Create: `backend/open_webui/tests/subscriptions/test_model_policy.py`

- [ ] **Step 1: Write failing model policy tests**

Create `backend/open_webui/tests/subscriptions/test_model_policy.py`:

```python
import pytest

from open_webui.utils.subscriptions import (
    ModelSubscriptionPolicy,
    assert_model_subscription_access,
    filter_models_for_subscription,
    get_model_subscription_policy,
)


def model(model_id, subscription=None):
    return {'id': model_id, 'info': {'meta': {'subscription': subscription or {}}}}


def test_missing_policy_allows_all_tiers_and_is_metered():
    policy = get_model_subscription_policy(model('gpt-test'))

    assert policy.allowed_tiers == ['free', 'plus', 'chatpower']
    assert policy.quota_mode == 'metered'
    assert policy.usage_multiplier == '1'


def test_filter_removes_models_not_allowed_for_tier():
    models = [
        model('free-model', {'allowed_tiers': ['free', 'plus', 'chatpower'], 'quota_mode': 'unlimited'}),
        model('plus-model', {'allowed_tiers': ['plus', 'chatpower'], 'quota_mode': 'metered'}),
    ]

    filtered = filter_models_for_subscription(models, tier='free', is_admin=False)

    assert [item['id'] for item in filtered] == ['free-model']


def test_admin_sees_all_models():
    models = [
        model('free-model', {'allowed_tiers': ['free'], 'quota_mode': 'unlimited'}),
        model('power-model', {'allowed_tiers': ['chatpower'], 'quota_mode': 'metered'}),
    ]

    filtered = filter_models_for_subscription(models, tier='free', is_admin=True)

    assert [item['id'] for item in filtered] == ['free-model', 'power-model']


def test_disallowed_tier_raises_stable_error():
    with pytest.raises(PermissionError, match='SUBSCRIPTION_TIER_REQUIRED'):
        assert_model_subscription_access(
            model('plus-model', {'allowed_tiers': ['plus'], 'quota_mode': 'metered'}),
            tier='free',
            is_admin=False,
        )


def test_negative_multiplier_is_invalid():
    with pytest.raises(ValueError, match='MODEL_SUBSCRIPTION_POLICY_INVALID'):
        ModelSubscriptionPolicy.model_validate(
            {'allowed_tiers': ['free'], 'quota_mode': 'metered', 'usage_multiplier': '-1'}
        )
```

- [ ] **Step 2: Verify model policy tests fail**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_model_policy.py -q
```

Expected: FAIL because the policy model and helpers do not exist.

- [ ] **Step 3: Implement policy helpers**

Append to `backend/open_webui/utils/subscriptions.py`:

```python
from decimal import Decimal
from pydantic import ConfigDict, field_validator

from open_webui.models.subscriptions import CHATPOWER_TIER, FREE_TIER, PLUS_TIER


class ModelSubscriptionPolicy(BaseModel):
    model_config = ConfigDict(extra='ignore')

    allowed_tiers: list[str] = [FREE_TIER, PLUS_TIER, CHATPOWER_TIER]
    quota_mode: str = 'metered'
    usage_multiplier: str = '1'

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
        if Decimal(str(value)) < 0:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: usage_multiplier must be >= 0')
        return str(value)


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
```

- [ ] **Step 4: Add model meta schema field**

Modify `ModelMeta` in `backend/open_webui/models/models.py` to include the subscription field while preserving `extra='allow'`:

```python
class ModelMeta(BaseModel):
    """Metadata for a workspace model entry (profile, description, tags, capabilities)."""

    profile_image_url: str | None = None
    description: str | None = Field(default=None, description='User-facing description of the model.')
    capabilities: dict | None = None
    subscription: dict | None = None

    model_config = ConfigDict(extra='allow')
```

- [ ] **Step 5: Verify model policy tests pass**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_model_policy.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/open_webui/utils/subscriptions.py backend/open_webui/models/models.py backend/open_webui/tests/subscriptions/test_model_policy.py
git commit -m "feat: add model subscription policies"
```

---

### Task 6: Quota Checks And Usage Billing

**Files:**
- Modify: `backend/open_webui/models/subscriptions.py`
- Modify: `backend/open_webui/utils/subscriptions.py`
- Modify: `backend/open_webui/main.py`
- Modify: `backend/open_webui/utils/middleware.py`
- Create: `backend/open_webui/tests/subscriptions/test_usage_billing.py`

- [ ] **Step 1: Write failing usage billing tests**

Create `backend/open_webui/tests/subscriptions/test_usage_billing.py`:

```python
import pytest

from open_webui.models.subscriptions import SubscriptionPlans, SubscriptionUsages, UserSubscriptions, chatpoint_to_micros
from open_webui.utils.subscriptions import (
    assert_chatpoint_available,
    bill_model_usage,
    ensure_subscription_current,
)


@pytest.mark.asyncio
async def test_metered_usage_debits_plan_before_check(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await ensure_subscription_current('user-1', now=1_720_000_000, db=db_session)
    await UserSubscriptions.adjust_balances(
        'user-1',
        plan_delta_micros=-chatpoint_to_micros(9),
        check_delta_micros=chatpoint_to_micros(2),
        event_type='admin_adjustment',
        created_by='admin',
        db=db_session,
    )

    usage = await bill_model_usage(
        user_id='user-1',
        model_id='metered-model',
        quota_mode='metered',
        usage_multiplier='1',
        usage={'input_tokens': 10_000, 'output_tokens': 10_000, 'total_tokens': 20_000},
        metadata={'chat_id': 'chat-1', 'message_id': 'msg-1'},
        is_admin=False,
        now=1_720_000_010,
        db=db_session,
    )

    assert usage.cost_micros == chatpoint_to_micros(2)
    assert usage.plan_cost_micros == chatpoint_to_micros(1)
    assert usage.check_cost_micros == chatpoint_to_micros(1)
    assert usage.check_balance_after_micros == chatpoint_to_micros(1)


@pytest.mark.asyncio
async def test_request_can_make_balance_negative_then_next_metered_request_is_blocked(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await ensure_subscription_current('user-2', now=1_720_000_000, db=db_session)
    await UserSubscriptions.adjust_balances(
        'user-2',
        plan_delta_micros=-chatpoint_to_micros(9),
        check_delta_micros=0,
        event_type='admin_adjustment',
        created_by='admin',
        db=db_session,
    )

    await bill_model_usage(
        user_id='user-2',
        model_id='metered-model',
        quota_mode='metered',
        usage_multiplier='1',
        usage={'total_tokens': 20_000},
        metadata={},
        is_admin=False,
        now=1_720_000_010,
        db=db_session,
    )

    with pytest.raises(PermissionError, match='CHATPOINT_BALANCE_EXHAUSTED'):
        await assert_chatpoint_available('user-2', quota_mode='metered', is_admin=False, db=db_session)


@pytest.mark.asyncio
async def test_unlimited_usage_records_zero_cost(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    usage = await bill_model_usage(
        user_id='user-3',
        model_id='free-model',
        quota_mode='unlimited',
        usage_multiplier='9',
        usage={'input_tokens': 50_000, 'output_tokens': 50_000, 'total_tokens': 100_000},
        metadata={},
        is_admin=False,
        now=1_720_000_000,
        db=db_session,
    )

    assert usage.status == 'unlimited'
    assert usage.cost_micros == 0


@pytest.mark.asyncio
async def test_admin_usage_records_bypass_without_debit(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    usage = await bill_model_usage(
        user_id='admin-1',
        model_id='power-model',
        quota_mode='metered',
        usage_multiplier='10',
        usage={'total_tokens': 1_000_000},
        metadata={},
        is_admin=True,
        now=1_720_000_000,
        db=db_session,
    )

    assert usage.status == 'admin_bypass'
    assert usage.cost_micros == 0
```

- [ ] **Step 2: Verify billing tests fail**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_usage_billing.py -q
```

Expected: FAIL because `SubscriptionUsages`, `assert_chatpoint_available`, and `bill_model_usage` are missing.

- [ ] **Step 3: Add usage model access methods**

Append to `backend/open_webui/models/subscriptions.py`:

```python
class SubscriptionUsageModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    metadata: dict | None = None
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
        async with get_async_db_context(db) as session:
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
                metadata=metadata,
                created_at=created_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return SubscriptionUsageModel.model_validate(row)


SubscriptionUsages = SubscriptionUsagesTable()
```

- [ ] **Step 4: Implement quota preflight and billing service**

Append to `backend/open_webui/utils/subscriptions.py`:

```python
from open_webui.models.subscriptions import (
    SubscriptionLedgers,
    SubscriptionUsages,
    calculate_cost_micros,
    debit_balances,
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
    now: int | None = None,
    db: AsyncSession | None = None,
):
    current_time = now if now is not None else now_ts()
    input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
    subscription = await ensure_subscription_current(user_id, now=current_time, db=db)

    if is_admin:
        return await SubscriptionUsages.insert(
            user_id=user_id,
            chat_id=metadata.get('chat_id'),
            message_id=metadata.get('message_id'),
            model_id=model_id,
            tier='admin',
            quota_mode=quota_mode,
            usage_multiplier=usage_multiplier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_micros=0,
            plan_cost_micros=0,
            check_cost_micros=0,
            plan_balance_after_micros=None,
            check_balance_after_micros=None,
            status='admin_bypass',
            metadata=metadata,
            created_at=current_time,
            db=db,
        )

    if quota_mode == 'unlimited':
        return await SubscriptionUsages.insert(
            user_id=user_id,
            chat_id=metadata.get('chat_id'),
            message_id=metadata.get('message_id'),
            model_id=model_id,
            tier=subscription.tier,
            quota_mode=quota_mode,
            usage_multiplier=usage_multiplier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_micros=0,
            plan_cost_micros=0,
            check_cost_micros=0,
            plan_balance_after_micros=subscription.plan_balance_micros,
            check_balance_after_micros=subscription.check_balance_micros,
            status='unlimited',
            metadata=metadata,
            created_at=current_time,
            db=db,
        )

    if total_tokens <= 0:
        return await SubscriptionUsages.insert(
            user_id=user_id,
            chat_id=metadata.get('chat_id'),
            message_id=metadata.get('message_id'),
            model_id=model_id,
            tier=subscription.tier,
            quota_mode=quota_mode,
            usage_multiplier=usage_multiplier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_micros=0,
            plan_cost_micros=0,
            check_cost_micros=0,
            plan_balance_after_micros=subscription.plan_balance_micros,
            check_balance_after_micros=subscription.check_balance_micros,
            status='missing_usage',
            metadata=metadata,
            created_at=current_time,
            db=db,
        )

    cost_micros = calculate_cost_micros(total_tokens, usage_multiplier)
    debit = debit_balances(subscription.plan_balance_micros, subscription.check_balance_micros, cost_micros)
    updated = await UserSubscriptions.adjust_balances(
        user_id,
        plan_delta_micros=-debit.plan_cost_micros,
        check_delta_micros=-debit.check_cost_micros,
        event_type='usage_debit',
        created_by=None,
        db=db,
    )
    usage_row = await SubscriptionUsages.insert(
        user_id=user_id,
        chat_id=metadata.get('chat_id'),
        message_id=metadata.get('message_id'),
        model_id=model_id,
        tier=subscription.tier,
        quota_mode=quota_mode,
        usage_multiplier=usage_multiplier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_micros=cost_micros,
        plan_cost_micros=debit.plan_cost_micros,
        check_cost_micros=debit.check_cost_micros,
        plan_balance_after_micros=updated.plan_balance_micros,
        check_balance_after_micros=updated.check_balance_micros,
        status='billed',
        metadata=metadata,
        created_at=current_time,
        db=db,
    )
    return usage_row
```

- [ ] **Step 5: Verify focused billing tests pass**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_usage_billing.py -q
```

Expected: PASS.

- [ ] **Step 6: Integrate runtime model filtering and preflight checks**

Modify `backend/open_webui/main.py` imports:

```python
from open_webui.routers import (
    analytics,
    audio,
    auths,
    automations,
    calendar,
    channels,
    chats,
    configs,
    evaluations,
    files,
    folders,
    functions,
    groups,
    images,
    knowledge,
    memories,
    models,
    notes,
    ollama,
    openai,
    pipelines,
    prompts,
    retrieval,
    scim,
    skills,
    subscriptions,
    tasks,
    terminals,
    tools,
    users,
    utils,
)
```

Add the router include near the other `/api/v1` includes:

```python
app.include_router(subscriptions.router, prefix='/api/v1/subscriptions', tags=['subscriptions'])
```

Import subscription helpers:

```python
from open_webui.utils.subscriptions import (
    assert_chatpoint_available,
    assert_model_subscription_access,
    ensure_subscription_current,
    filter_models_for_subscription,
)
```

In `/api/models`, after `models = await get_filtered_models(models, user)`, add:

```python
    subscription = await ensure_subscription_current(user.id)
    models = filter_models_for_subscription(
        models,
        tier=subscription.tier,
        is_admin=(user.role == 'admin'),
    )
```

In `chat_completion`, after resolving `model` and existing `check_model_access`, add:

```python
            subscription = await ensure_subscription_current(user.id)
            subscription_policy = assert_model_subscription_access(
                model,
                tier=subscription.tier,
                is_admin=(user.role == 'admin'),
            )
            await assert_chatpoint_available(
                user.id,
                quota_mode=subscription_policy.quota_mode,
                is_admin=(user.role == 'admin'),
            )
            request.state.subscription_policy = subscription_policy.model_dump()
            metadata['subscription_policy'] = subscription_policy.model_dump()
```

For multi-model fan-out, call the same `assert_model_subscription_access` and `assert_chatpoint_available` for each `target_model_id` before `create_task`.

- [ ] **Step 7: Add billing hook in middleware**

Modify `backend/open_webui/utils/middleware.py` imports:

```python
from open_webui.utils.subscriptions import bill_model_usage, get_model_subscription_policy
```

In the non-streaming path, after the assignment to `ctx['assistant_message']` and before `await outlet_filter_handler(ctx)`, add:

```python
                    policy_data = metadata.get('subscription_policy')
                    if policy_data and user:
                        await bill_model_usage(
                            user_id=user.id,
                            model_id=form_data.get('model') or model.get('id', ''),
                            quota_mode=policy_data.get('quota_mode', 'metered'),
                            usage_multiplier=policy_data.get('usage_multiplier', '1'),
                            usage=usage,
                            metadata=metadata,
                            is_admin=(getattr(user, 'role', None) == 'admin'),
                        )
```

In the standard streaming path, after the assignment to `ctx['assistant_message']` and before `await outlet_filter_handler(ctx)`, add the same `bill_model_usage` block using the local `usage` variable.

In the fallback streaming wrapper, after `ctx['assistant_message'] = assistant_message` and before outlet filtering, add:

```python
                policy_data = metadata.get('subscription_policy')
                if policy_data and user:
                    await bill_model_usage(
                        user_id=user.id,
                        model_id=form_data.get('model') or model.get('id', ''),
                        quota_mode=policy_data.get('quota_mode', 'metered'),
                        usage_multiplier=policy_data.get('usage_multiplier', '1'),
                        usage=assistant_message.get('usage'),
                        metadata=metadata,
                        is_admin=(getattr(user, 'role', None) == 'admin'),
                    )
```

- [ ] **Step 8: Verify all backend subscription tests pass**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add backend/open_webui/models/subscriptions.py backend/open_webui/utils/subscriptions.py backend/open_webui/main.py backend/open_webui/utils/middleware.py backend/open_webui/tests/subscriptions/test_usage_billing.py
git commit -m "feat: enforce subscription quotas on model usage"
```

---

### Task 7: Subscription API Router

**Files:**
- Create: `backend/open_webui/routers/subscriptions.py`
- Modify: `backend/open_webui/models/subscriptions.py`
- Modify: `backend/open_webui/utils/subscriptions.py`
- Create: `backend/open_webui/tests/subscriptions/test_router_contract.py`

- [ ] **Step 1: Write failing router contract tests**

Create `backend/open_webui/tests/subscriptions/test_router_contract.py`:

```python
from open_webui.routers import subscriptions


def test_router_exposes_user_and_admin_paths():
    paths = {route.path for route in subscriptions.router.routes}

    assert '/me' in paths
    assert '/usage' in paths
    assert '/redeem' in paths
    assert '/records' in paths
    assert '/billing-address' in paths
    assert '/admin/plans' in paths
    assert '/admin/models' in paths
    assert '/admin/codes' in paths
    assert '/admin/users' in paths
    assert '/admin/usage' in paths
    assert '/admin/ledger' in paths
```

- [ ] **Step 2: Verify router contract test fails**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_router_contract.py -q
```

Expected: FAIL because `backend/open_webui/routers/subscriptions.py` does not exist.

- [ ] **Step 3: Implement the router skeleton with real route handlers**

Create `backend/open_webui/routers/subscriptions.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from open_webui.internal.db import get_async_session
from open_webui.models.subscriptions import (
    RedemptionCodes,
    SubscriptionLedgers,
    SubscriptionPlans,
    UserSubscriptions,
    chatpoint_to_micros,
)
from open_webui.models.models import Models
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.subscriptions import ensure_subscription_current, redeem_code
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class RedeemForm(BaseModel):
    code: str


class BillingAddressForm(BaseModel):
    billing_address: dict


class AdminCodeCreateForm(BaseModel):
    mode: str
    quantity: int = 1
    max_uses: int = 1
    tier: str | None = None
    duration_days: int | None = None
    plan_chatpoint: str | int = 0
    check_chatpoint: str | int = 0
    expires_at: int | None = None
    memo: str | None = None


@router.get('/me')
async def get_my_subscription(user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    return await ensure_subscription_current(user.id, db=db)


@router.get('/usage')
async def get_my_usage(user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    subscription = await ensure_subscription_current(user.id, db=db)
    ledger = await SubscriptionLedgers.get_recent_for_user(user.id, limit=50, db=db)
    return {'subscription': subscription, 'ledger': ledger, 'usage': []}


@router.post('/redeem')
async def redeem_subscription_code(
    form_data: RedeemForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await redeem_code(user.id, form_data.code, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get('/records')
async def get_my_records(user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    return {'ledger': await SubscriptionLedgers.get_recent_for_user(user.id, limit=100, db=db)}


@router.put('/billing-address')
async def update_billing_address(
    form_data: BillingAddressForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    subscription = await ensure_subscription_current(user.id, db=db)
    subscription.billing_address = form_data.billing_address
    return await UserSubscriptions.save(subscription, db=db)


@router.get('/admin/plans')
async def get_admin_plans(user=Depends(get_admin_user), db: AsyncSession = Depends(get_async_session)):
    await SubscriptionPlans.seed_defaults(db=db)
    return await SubscriptionPlans.get_plans(db=db)


@router.get('/admin/models')
async def get_admin_model_policies(user=Depends(get_admin_user), db: AsyncSession = Depends(get_async_session)):
    models = await Models.get_all_models(db=db)
    return [model.model_dump() for model in models]


@router.get('/admin/codes')
async def get_admin_codes(user=Depends(get_admin_user), db: AsyncSession = Depends(get_async_session)):
    return {'items': []}


@router.post('/admin/codes')
async def create_admin_codes(
    form_data: AdminCodeCreateForm,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await RedemptionCodes.create_codes(
        mode=form_data.mode,
        quantity=form_data.quantity,
        max_uses=form_data.max_uses,
        tier=form_data.tier,
        duration_days=form_data.duration_days,
        plan_chatpoint_micros=chatpoint_to_micros(form_data.plan_chatpoint),
        check_chatpoint_micros=chatpoint_to_micros(form_data.check_chatpoint),
        expires_at=form_data.expires_at,
        memo=form_data.memo,
        created_by=user.id,
        db=db,
    )


@router.get('/admin/users')
async def get_admin_user_subscriptions(
    query: str | None = None,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {'items': [], 'query': query}


@router.get('/admin/usage')
async def get_admin_usage(user=Depends(get_admin_user), db: AsyncSession = Depends(get_async_session)):
    return {'items': []}


@router.get('/admin/ledger')
async def get_admin_ledger(user=Depends(get_admin_user), db: AsyncSession = Depends(get_async_session)):
    return {'items': []}
```

- [ ] **Step 4: Verify router contract test passes**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions/test_router_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Add admin update/list model methods**

Extend `models/subscriptions.py` table classes with list and update methods used by the UI:

```python
class SubscriptionPlansTable:
    async def update_plan(
        self,
        plan_id: str,
        *,
        display_name: str | None,
        plan_chatpoint_micros: int | None,
        reset_interval_days: int | None,
        features: dict | None,
        is_active: bool | None,
        db: AsyncSession,
    ) -> SubscriptionPlan:
        stmt = select(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id)
        plan = await db.scalar(stmt)
        if plan is None:
            raise ValueError('SUBSCRIPTION_PLAN_NOT_FOUND')
        if display_name is not None:
            plan.display_name = display_name
        if plan_chatpoint_micros is not None:
            plan.plan_chatpoint_micros = plan_chatpoint_micros
        if reset_interval_days is not None:
            plan.reset_interval_days = reset_interval_days
        if features is not None:
            plan.features = features
        if is_active is not None:
            plan.is_active = is_active
        await db.commit()
        await db.refresh(plan)
        return plan


class RedemptionCodesTable:
    async def list_codes(self, *, limit: int, offset: int, db: AsyncSession) -> list[RedemptionCode]:
        result = await db.execute(
            select(RedemptionCode).order_by(RedemptionCode.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update_code(
        self,
        code_id: str,
        *,
        disabled_at: int | None,
        memo: str | None,
        db: AsyncSession,
    ) -> RedemptionCode:
        code = await db.scalar(select(RedemptionCode).filter(RedemptionCode.id == code_id))
        if code is None:
            raise ValueError('REDEMPTION_CODE_NOT_FOUND')
        code.disabled_at = disabled_at
        if memo is not None:
            code.memo = memo
        await db.commit()
        await db.refresh(code)
        return code


class RedemptionRecordsTable:
    async def list_for_code(self, code_id: str, *, db: AsyncSession) -> list[RedemptionRecord]:
        result = await db.execute(
            select(RedemptionRecord)
            .filter(RedemptionRecord.redemption_code_id == code_id)
            .order_by(RedemptionRecord.redeemed_at.desc())
        )
        return list(result.scalars().all())


class UserSubscriptionsTable:
    async def list_subscriptions(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
        db: AsyncSession,
    ) -> list[UserSubscription]:
        stmt = select(UserSubscription).order_by(UserSubscription.updated_at.desc()).limit(limit).offset(offset)
        if query:
            stmt = stmt.filter(UserSubscription.user_id.contains(query))
        result = await db.execute(stmt)
        return list(result.scalars().all())


class SubscriptionUsagesTable:
    async def get_usage_summary(
        self,
        *,
        user_id: str | None,
        model_id: str | None,
        start_at: int | None,
        end_at: int | None,
        db: AsyncSession,
    ) -> dict:
        stmt = select(SubscriptionUsage)
        if user_id:
            stmt = stmt.filter(SubscriptionUsage.user_id == user_id)
        if model_id:
            stmt = stmt.filter(SubscriptionUsage.model_id == model_id)
        if start_at is not None:
            stmt = stmt.filter(SubscriptionUsage.created_at >= start_at)
        if end_at is not None:
            stmt = stmt.filter(SubscriptionUsage.created_at <= end_at)
        result = await db.execute(stmt.order_by(SubscriptionUsage.created_at.desc()))
        items = list(result.scalars().all())
        return {
            'items': items,
            'total_cost_micros': sum(item.cost_micros for item in items),
            'total_input_tokens': sum(item.input_tokens for item in items),
            'total_output_tokens': sum(item.output_tokens for item in items),
        }


class SubscriptionLedgersTable:
    async def search(
        self,
        *,
        user_id: str | None,
        event_type: str | None,
        limit: int,
        offset: int,
        db: AsyncSession,
    ) -> list[SubscriptionLedger]:
        stmt = select(SubscriptionLedger).order_by(SubscriptionLedger.created_at.desc()).limit(limit).offset(offset)
        if user_id:
            stmt = stmt.filter(SubscriptionLedger.user_id == user_id)
        if event_type:
            stmt = stmt.filter(SubscriptionLedger.event_type == event_type)
        result = await db.execute(stmt)
        return list(result.scalars().all())
```

Wire the admin routes from Step 3 to these methods so response keys are `items`, `total_cost_micros`, `total_input_tokens`, and `total_output_tokens` where applicable. Route names and response keys must match the frontend API client in Task 8.

- [ ] **Step 6: Verify all backend subscription tests pass**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/open_webui/routers/subscriptions.py backend/open_webui/models/subscriptions.py backend/open_webui/utils/subscriptions.py backend/open_webui/tests/subscriptions/test_router_contract.py
git commit -m "feat: add subscription API routes"
```

---

### Task 8: Frontend API Client And Static Guard

**Files:**
- Create: `src/lib/apis/subscriptions/index.ts`
- Create: `scripts/check-subscriptions.mjs`
- Modify: `package.json`

- [ ] **Step 1: Write failing static guard**

Create `scripts/check-subscriptions.mjs`:

```javascript
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const exists = (file) => fs.existsSync(path.join(root, file));
const failures = [];

const requiredFiles = [
	'src/lib/apis/subscriptions/index.ts',
	'src/lib/components/chat/Settings/Subscription.svelte',
	'src/lib/components/chat/Settings/RedeemCode.svelte',
	'src/lib/components/chat/Settings/Usage.svelte',
	'src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte',
	'src/lib/components/admin/Settings/Subscriptions.svelte',
	'src/lib/components/workspace/Models/SubscriptionPolicy.svelte'
];

for (const file of requiredFiles) {
	if (!exists(file)) failures.push(`Missing ${file}`);
}

if (exists('src/lib/apis/subscriptions/index.ts')) {
	const api = read('src/lib/apis/subscriptions/index.ts');
	for (const name of [
		'getMySubscription',
		'getMySubscriptionUsage',
		'redeemSubscriptionCode',
		'updateBillingAddress',
		'getAdminSubscriptionPlans',
		'createAdminRedemptionCodes'
	]) {
		if (!api.includes(`export const ${name}`)) failures.push(`Missing API helper ${name}`);
	}
}

if (failures.length > 0) {
	for (const failure of failures) console.error(failure);
	process.exit(1);
}

console.log('Subscription static guard passed.');
```

Modify `package.json` scripts:

```json
"test:subscriptions": "node scripts/check-subscriptions.mjs"
```

- [ ] **Step 2: Verify guard fails**

Run:

```powershell
npm run test:subscriptions
```

Expected: FAIL with missing frontend files and API helpers.

- [ ] **Step 3: Implement frontend API helper**

Create `src/lib/apis/subscriptions/index.ts`:

```typescript
import { WEBUI_API_BASE_URL } from '$lib/constants';

const jsonFetch = async (url: string, token: string, options: RequestInit = {}) => {
	let error = null;
	const headers = Object.assign(
		{
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		options.headers ?? {}
	);
	const request = Object.assign({}, options, { headers });
	const res = await fetch(url, request)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			return null;
		});

	if (error) throw error;
	return res;
};

export const getMySubscription = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/me`, token);
};

export const getMySubscriptionUsage = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/usage`, token);
};

export const redeemSubscriptionCode = async (token: string, code: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/redeem`, token, {
		method: 'POST',
		body: JSON.stringify({ code })
	});
};

export const getMySubscriptionRecords = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/records`, token);
};

export const updateBillingAddress = async (token: string, billingAddress: Record<string, unknown>) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/billing-address`, token, {
		method: 'PUT',
		body: JSON.stringify({ billing_address: billingAddress })
	});
};

export const getAdminSubscriptionPlans = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/plans`, token);
};

export const getAdminSubscriptionModels = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/models`, token);
};

export const getAdminRedemptionCodes = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/codes`, token);
};

export const createAdminRedemptionCodes = async (token: string, payload: Record<string, unknown>) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/codes`, token, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const getAdminUserSubscriptions = async (token: string, query = '') => {
	const params = new URLSearchParams();
	if (query) params.set('query', query);
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/users?${params.toString()}`, token);
};

export const getAdminSubscriptionLedger = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/ledger`, token);
};
```

- [ ] **Step 4: Create temporary minimal components to make the guard pass**

Create each required `.svelte` file with a real exported component skeleton. Example for `src/lib/components/chat/Settings/Subscription.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { getMySubscription } from '$lib/apis/subscriptions';

	let subscription = null;

	onMount(async () => {
		subscription = await getMySubscription(localStorage.token).catch(() => null);
	});
</script>

<div id="tab-subscription" class="flex flex-col h-full text-sm">
	<div class="text-base font-medium">Subscription</div>
	{#if subscription}
		<div class="mt-3 text-sm">{subscription.display_name ?? subscription.tier}</div>
	{/if}
</div>
```

Create analogous minimal components for:

- `RedeemCode.svelte`
- `Usage.svelte`
- `SubscriptionQuotaRing.svelte`
- `Subscriptions.svelte`
- `SubscriptionPolicy.svelte`

Each component must render a stable root element with a useful id, such as `tab-usage`, `subscription-quota-ring`, or `admin-subscriptions`.

- [ ] **Step 5: Verify static guard passes**

Run:

```powershell
npm run test:subscriptions
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/lib/apis/subscriptions/index.ts src/lib/components/chat/Settings/Subscription.svelte src/lib/components/chat/Settings/RedeemCode.svelte src/lib/components/chat/Settings/Usage.svelte src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte src/lib/components/admin/Settings/Subscriptions.svelte src/lib/components/workspace/Models/SubscriptionPolicy.svelte scripts/check-subscriptions.mjs package.json
git commit -m "feat: add subscription frontend API skeleton"
```

---

### Task 9: User Subscription Settings UI

**Files:**
- Modify: `src/lib/components/chat/SettingsModal.svelte`
- Modify: `src/lib/components/chat/Settings/Subscription.svelte`
- Modify: `src/lib/components/chat/Settings/RedeemCode.svelte`
- Modify: `src/lib/components/chat/Settings/Usage.svelte`
- Create: `src/lib/components/chat/Settings/Account/BillingAddress.svelte`
- Modify: `src/lib/components/chat/Settings/Account.svelte`

- [ ] **Step 1: Extend the static guard for user UI wiring**

Update `scripts/check-subscriptions.mjs` to assert:

```javascript
const settingsModal = read('src/lib/components/chat/SettingsModal.svelte');
for (const marker of [
	"import Subscription from './Settings/Subscription.svelte'",
	"import RedeemCode from './Settings/RedeemCode.svelte'",
	"import Usage from './Settings/Usage.svelte'",
	"id: 'subscription'",
	"id: 'redeem_code'",
	"id: 'usage'",
	"<Subscription",
	"<RedeemCode",
	"<Usage"
]) {
	if (!settingsModal.includes(marker)) failures.push(`Settings modal missing ${marker}`);
}

const account = read('src/lib/components/chat/Settings/Account.svelte');
if (!account.includes('BillingAddress')) failures.push('Account settings must include BillingAddress');
```

- [ ] **Step 2: Verify guard fails**

Run:

```powershell
npm run test:subscriptions
```

Expected: FAIL because `SettingsModal.svelte` and `Account.svelte` are not wired.

- [ ] **Step 3: Wire tabs into SettingsModal**

Modify `src/lib/components/chat/SettingsModal.svelte`:

Add imports:

```svelte
import Subscription from './Settings/Subscription.svelte';
import RedeemCode from './Settings/RedeemCode.svelte';
import Usage from './Settings/Usage.svelte';
```

Add `allSettings` entries:

```typescript
{
	id: 'subscription',
	title: 'Subscription',
	keywords: ['subscription', 'plan', 'plus', 'chatpower', 'chatpoint', 'billing']
},
{
	id: 'redeem_code',
	title: 'Redeem Code',
	keywords: ['redeem', 'code', 'voucher', 'chatpoint']
},
{
	id: 'usage',
	title: 'Usage',
	keywords: ['usage', 'quota', 'chatpoint', 'tokens', 'plan', 'check']
}
```

Add tab button branches modeled on existing buttons, using text labels `Subscription`, `Redeem Code`, and `Usage`.

Add panel branches:

```svelte
{:else if selectedTab === 'subscription'}
	<Subscription
		on:redeem={() => {
			selectedTab = 'redeem_code';
		}}
	/>
{:else if selectedTab === 'redeem_code'}
	<RedeemCode
		on:redeemed={() => {
			selectedTab = 'subscription';
		}}
	/>
{:else if selectedTab === 'usage'}
	<Usage />
```

- [ ] **Step 4: Build real Subscription/Redeem/Usage panels**

Replace the skeletons with panels that use the API helpers and existing quiet settings styling.

`Subscription.svelte` must show:

- current tier card.
- expiry.
- period start/end.
- next reset.
- Plan and Check Chatpoint values.
- Free/Plus/ChatPower cards.
- disabled purchase buttons with toast text `Purchases are not available yet.`
- redeem button dispatching `redeem`.

`RedeemCode.svelte` must:

- bind a code input.
- call `redeemSubscriptionCode`.
- show success deltas.
- show API errors.
- dispatch `redeemed`.

`Usage.svelte` must:

- call `getMySubscriptionUsage`.
- show current subscription balances.
- show ledger rows.
- show empty model usage state when API returns no rows.

- [ ] **Step 5: Add BillingAddress component and mount it**

Create `src/lib/components/chat/Settings/Account/BillingAddress.svelte`:

```svelte
<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getMySubscription, updateBillingAddress } from '$lib/apis/subscriptions';

	let billingAddress = {
		name: '',
		country: '',
		address: '',
		postal_code: '',
		tax_id_or_notes: ''
	};

	const load = async () => {
		const subscription = await getMySubscription(localStorage.token).catch(() => null);
		billingAddress = Object.assign({}, billingAddress, subscription?.billing_address ?? {});
	};

	const save = async () => {
		await updateBillingAddress(localStorage.token, billingAddress)
			.then(() => toast.success('Billing address saved.'))
			.catch((error) => toast.error(`${error}`));
	};

	load();
</script>

<div class="mt-4">
	<div class="mb-2 text-sm font-medium">Billing Address</div>
	<div class="flex flex-col gap-2 text-sm">
		<input class="bg-transparent outline-hidden" aria-label="Name or company" bind:value={billingAddress.name} />
		<input class="bg-transparent outline-hidden" aria-label="Country / region" bind:value={billingAddress.country} />
		<input class="bg-transparent outline-hidden" aria-label="Address" bind:value={billingAddress.address} />
		<input class="bg-transparent outline-hidden" aria-label="Postal code" bind:value={billingAddress.postal_code} />
		<input class="bg-transparent outline-hidden" aria-label="Tax ID or notes" bind:value={billingAddress.tax_id_or_notes} />
		<div>
			<button type="button" class="px-3 py-1.5 rounded-full bg-black text-white dark:bg-white dark:text-black" on:click={save}>
				Save Billing Address
			</button>
		</div>
	</div>
</div>
```

Import and mount it in `Account.svelte` near the account details section:

```svelte
import BillingAddress from './Account/BillingAddress.svelte';
```

```svelte
<BillingAddress />
```

- [ ] **Step 6: Verify user UI guard and branding**

Run:

```powershell
npm run test:subscriptions
npm run test:branding
```

Expected: both PASS.

- [ ] **Step 7: Run frontend check and record status**

Run:

```powershell
npm run check
```

Expected: may still fail on existing unrelated Svelte/TypeScript issues. Record the first subscription-related error if any and fix it before committing.

- [ ] **Step 8: Commit**

```powershell
git add src/lib/components/chat/SettingsModal.svelte src/lib/components/chat/Settings/Subscription.svelte src/lib/components/chat/Settings/RedeemCode.svelte src/lib/components/chat/Settings/Usage.svelte src/lib/components/chat/Settings/Account/BillingAddress.svelte src/lib/components/chat/Settings/Account.svelte scripts/check-subscriptions.mjs
git commit -m "feat: add user subscription settings"
```

---

### Task 10: Lower-Left Quota Ring

**Files:**
- Modify: `src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte`
- Modify: `src/lib/components/layout/Sidebar/UserMenu.svelte`
- Modify: `src/lib/stores/index.ts` if a shared subscription store is needed
- Modify: `scripts/check-subscriptions.mjs`

- [ ] **Step 1: Extend static guard for quota ring wiring**

Add checks:

```javascript
const userMenu = read('src/lib/components/layout/Sidebar/UserMenu.svelte');
if (!userMenu.includes('SubscriptionQuotaRing')) failures.push('UserMenu must include SubscriptionQuotaRing');

const ring = read('src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte');
for (const marker of ['Usage', 'Plan Chatpoint', 'Check Chatpoint', 'exhausted', 'stroke-red']) {
	if (!ring.includes(marker)) failures.push(`Quota ring missing ${marker}`);
}
```

- [ ] **Step 2: Verify guard fails**

Run:

```powershell
npm run test:subscriptions
```

Expected: FAIL because UserMenu is not wired and ring states are not implemented.

- [ ] **Step 3: Implement `SubscriptionQuotaRing.svelte`**

Implement the component with:

- `getMySubscription()` on mount.
- computed total allowance and total remaining.
- ring percentage.
- red stroke class when `plan_balance_micros + check_balance_micros <= 0`.
- hover popover with `Usage`, `Plan Chatpoint`, `Check Chatpoint`, linear bars, and next reset.
- click dispatch `openUsage`.

Use SVG circle, not a canvas, so the guard and layout are stable:

```svelte
<svg class="size-8" viewBox="0 0 36 36" aria-label="Usage">
	<circle class="text-gray-200 dark:text-gray-800" stroke="currentColor" stroke-width="4" fill="none" cx="18" cy="18" r="15" />
	<circle
		class={exhausted ? 'stroke-red-500' : low ? 'stroke-yellow-500' : 'stroke-green-500'}
		stroke-width="4"
		fill="none"
		cx="18"
		cy="18"
		r="15"
		stroke-dasharray={`${usedPercent} 100`}
		pathLength="100"
	/>
</svg>
```

- [ ] **Step 4: Wire it into UserMenu**

In `UserMenu.svelte`, import:

```svelte
import SubscriptionQuotaRing from './SubscriptionQuotaRing.svelte';
```

Mount it next to the existing user identity area:

```svelte
{#if $user?.role === 'admin'}
	<div class="text-xs px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-850">Admin</div>
{:else}
	<SubscriptionQuotaRing
		on:openUsage={async () => {
			await showSettings.set('usage');
		}}
	/>
{/if}
```

- [ ] **Step 5: Verify guard and branding**

Run:

```powershell
npm run test:subscriptions
npm run test:branding
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte src/lib/components/layout/Sidebar/UserMenu.svelte scripts/check-subscriptions.mjs
git commit -m "feat: show subscription quota in user menu"
```

---

### Task 11: Admin Subscription UI And Model Policy Editor

**Files:**
- Modify: `src/lib/components/admin/Settings.svelte`
- Modify: `src/lib/components/admin/Settings/Subscriptions.svelte`
- Modify: `src/lib/components/admin/Settings/Subscriptions/Plans.svelte`
- Modify: `src/lib/components/admin/Settings/Subscriptions/ModelAccess.svelte`
- Modify: `src/lib/components/admin/Settings/Subscriptions/RedeemCodes.svelte`
- Modify: `src/lib/components/admin/Settings/Subscriptions/UserSubscriptions.svelte`
- Modify: `src/lib/components/admin/Settings/Subscriptions/UsageLedger.svelte`
- Modify: `src/lib/components/admin/Users/UserList/EditUserModal.svelte`
- Modify: `src/lib/components/workspace/Models/SubscriptionPolicy.svelte`
- Modify: `src/lib/components/workspace/Models/ModelEditor.svelte`
- Modify: `scripts/check-subscriptions.mjs`

- [ ] **Step 1: Extend static guard for admin UI**

Add checks:

```javascript
const adminSettings = read('src/lib/components/admin/Settings.svelte');
for (const marker of ['Subscriptions', "selectedTab === 'subscriptions'", '<Subscriptions']) {
	if (!adminSettings.includes(marker)) failures.push(`Admin settings missing ${marker}`);
}

const modelEditor = read('src/lib/components/workspace/Models/ModelEditor.svelte');
if (!modelEditor.includes('SubscriptionPolicy')) failures.push('ModelEditor must include SubscriptionPolicy');

const editUser = read('src/lib/components/admin/Users/UserList/EditUserModal.svelte');
if (!editUser.includes('Manage Subscription')) failures.push('EditUserModal must link to subscription management');
```

- [ ] **Step 2: Verify guard fails**

Run:

```powershell
npm run test:subscriptions
```

Expected: FAIL because admin wiring is missing.

- [ ] **Step 3: Add Admin Settings tab**

In `src/lib/components/admin/Settings.svelte`, import:

```svelte
import Subscriptions from './Settings/Subscriptions.svelte';
```

Add `subscriptions` to the accepted tab list and `allSettings`:

```typescript
{
	id: 'subscriptions',
	title: 'Subscriptions',
	keywords: ['subscriptions', 'plans', 'chatpoint', 'redeem', 'codes', 'usage', 'ledger']
}
```

Add a tab button branch labeled `Subscriptions`, and panel:

```svelte
{:else if selectedTab === 'subscriptions'}
	<Subscriptions />
```

- [ ] **Step 4: Implement admin subscription shell**

`Subscriptions.svelte` must maintain an internal tab state:

- `plans`
- `model-access`
- `redeem-codes`
- `user-subscriptions`
- `usage-ledger`

Render the corresponding child component. Use the same narrow left tab style as existing admin pages.

- [ ] **Step 5: Implement admin child panels**

Implement concrete API-backed panels:

- `Plans.svelte`: load `getAdminSubscriptionPlans`, show Free/Plus/ChatPower rows, edit allowance/period/name fields.
- `ModelAccess.svelte`: load `getAdminSubscriptionModels`, show policy fields, save through model policy endpoint.
- `RedeemCodes.svelte`: create single-use and multi-use codes, show generated raw codes after creation, list existing code previews.
- `UserSubscriptions.svelte`: search users, show tier, expiry, Plan/Check balances, and edit fields.
- `UsageLedger.svelte`: load usage and ledger rows.

Each panel must show a loading state, empty state, and error toast.

- [ ] **Step 6: Implement model policy editor section**

`SubscriptionPolicy.svelte` must bind to `meta.subscription` through an exported `policy` prop:

```svelte
<script lang="ts">
	export let policy = {
		allowed_tiers: ['free', 'plus', 'chatpower'],
		quota_mode: 'metered',
		usage_multiplier: '1'
	};
</script>
```

Controls:

- three checkboxes for Free, Plus, ChatPower.
- segmented select for unlimited/metered.
- numeric input for multiplier, disabled when unlimited.

In `ModelEditor.svelte`, import and mount:

```svelte
import SubscriptionPolicy from './SubscriptionPolicy.svelte';
```

Before submit, ensure:

```typescript
info.meta.subscription = info.meta.subscription ?? {
	allowed_tiers: ['free', 'plus', 'chatpower'],
	quota_mode: 'metered',
	usage_multiplier: '1'
};
```

Mount under the model params or access area:

```svelte
<SubscriptionPolicy bind:policy={info.meta.subscription} />
```

- [ ] **Step 7: Add user modal link**

In `EditUserModal.svelte`, import `goto` if it is not already present and add:

```svelte
<button
	type="button"
	class="text-xs underline text-gray-500"
	on:click={() => goto(`/admin/settings/subscriptions?user=${selectedUser.id}`)}
>
	Manage Subscription
</button>
```

- [ ] **Step 8: Verify guard and branding**

Run:

```powershell
npm run test:subscriptions
npm run test:branding
```

Expected: PASS.

- [ ] **Step 9: Run frontend check and record status**

Run:

```powershell
npm run check
```

Expected: may fail on existing unrelated type issues. Fix subscription-related syntax/import errors before committing.

- [ ] **Step 10: Commit**

```powershell
git add src/lib/components/admin/Settings.svelte src/lib/components/admin/Settings/Subscriptions.svelte src/lib/components/admin/Settings/Subscriptions src/lib/components/admin/Users/UserList/EditUserModal.svelte src/lib/components/workspace/Models/SubscriptionPolicy.svelte src/lib/components/workspace/Models/ModelEditor.svelte scripts/check-subscriptions.mjs
git commit -m "feat: add admin subscription management UI"
```

---

### Task 12: Full Verification, Runtime Build, And Cleanup

**Files:**
- Modify only files needed to fix issues found by verification.

- [ ] **Step 1: Run all focused backend subscription tests**

Run:

```powershell
python -m pytest backend/open_webui/tests/subscriptions -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend guards**

Run:

```powershell
npm run test:subscriptions
npm run test:branding
npm run test:release-version
```

Expected: PASS.

- [ ] **Step 3: Run frontend check**

Run:

```powershell
npm run check
```

Expected: if it still fails, confirm the failures are the pre-existing unrelated type issues seen before subscription work. Any subscription file syntax/import/type failure must be fixed.

- [ ] **Step 4: Build the frontend**

Run:

```powershell
npm run build
```

Expected: exit code 0. Existing warnings may appear; build must complete.

- [ ] **Step 5: Rebuild Docker image only after source verification passes**

Run:

```powershell
docker build -t artichat:main .
```

Expected: exit code 0.

If the build fails, clean unused runtime artifacts first:

```powershell
docker container prune -f
docker image prune -f
docker system df
```

Do not prune the full BuildKit cache unless disk pressure remains severe after inspecting `docker system df`.

- [ ] **Step 6: Restart container and verify health**

Use the existing project container name:

```powershell
docker rm -f artichat
docker run -d --name artichat -p 3000:8080 artichat:main
Start-Sleep -Seconds 10
Invoke-WebRequest -Uri http://localhost:3000/health -UseBasicParsing
```

Expected: HTTP 200 health response.

- [ ] **Step 7: Manual browser verification**

Open `http://localhost:3000` and verify:

- Settings contains Subscription, Redeem Code, and Usage.
- Left user button shows tier badge and quota ring for a normal user.
- Quota ring turns red when a test user has zero or negative metered balance.
- Admin Settings contains Subscriptions.
- Admin Subscriptions contains Plans, Model Access, Redeem Codes, User Subscriptions, and Usage/Ledger.
- Model editor contains Subscription Policy.
- A Free user cannot see a Plus-only model.
- Redeeming a Plus code makes the Plus-only model visible.
- Metered model usage creates a usage row and ledger row.
- Expired Plus user downgrades to Free before Plan reset.

- [ ] **Step 8: Final git status**

Run:

```powershell
git status --short
```

Expected: only intentional uncommitted files remain. If the user still has unrelated edits in the worktree, leave them untouched and mention them in the final report.

- [ ] **Step 9: Final commit for verification fixes**

If Task 12 required fixes:

```powershell
git add <fixed-files>
git commit -m "fix: stabilize subscription verification"
```

If Task 12 required no fixes, do not create an empty commit.

## Self-Review Checklist

- Backend subscription schema and seed defaults: Tasks 2 and 3.
- Plan/Check Chatpoint split: Tasks 1, 3, 6, 9, 10.
- Paid expiry auto-downgrade to Free before reset: Task 3 tests and service.
- Model tier visibility and runtime access: Tasks 5 and 6.
- Metered/unlimited mode and multiplier: Tasks 5, 6, 11.
- Redemption code modes and only-upgrade behavior: Task 4.
- User settings subscription/redeem/usage: Task 9.
- Account billing address and records: Task 9.
- Lower-left quota ring, hover detail, red exhausted state: Task 10.
- Admin Settings > Subscriptions: Task 11.
- Admin Users lightweight linkage: Task 11.
- Full verification and Docker cleanup policy: Task 12.
