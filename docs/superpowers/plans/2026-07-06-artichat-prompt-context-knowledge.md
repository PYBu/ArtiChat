# ArtiChat Prompt Context and Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add trusted ArtiChat subscription prompt variables and a platform knowledge context variable for model system prompts.

**Architecture:** Extend the existing system prompt resolver in `backend/open_webui/utils/payload.py` so server-controlled variables are merged before prompt rendering. Store platform knowledge as a backend Markdown resource copied into Docker images. Cover behavior with focused async tests under the existing subscription test suite.

**Tech Stack:** Python, FastAPI backend utilities, SQLAlchemy async sessions, pytest, Markdown resource file.

---

### Task 1: Tests for Prompt Context Variables

**Files:**
- Create: `backend/open_webui/tests/subscriptions/test_prompt_context.py`
- Modify: none

- [ ] **Step 1: Write failing tests**

```python
import pytest

from open_webui.models.subscriptions import PLUS_TIER, SubscriptionPlans, UserSubscriptions, chatpoint_to_micros
from open_webui.utils.payload import resolve_system_prompt


class DummyUser:
    def __init__(self, user_id: str, name: str = 'Alice', email: str = 'alice@example.com'):
        self.id = user_id
        self.name = name
        self.email = email

    def model_dump(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'info': {},
        }


@pytest.mark.asyncio
async def test_resolve_system_prompt_injects_subscription_context(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await UserSubscriptions.create_from_plan(
        user_id='user-plus',
        plan_id=PLUS_TIER,
        starts_at=1_720_000_000,
        expires_at=1_722_592_000,
        source='test',
        db=db_session,
    )
    await UserSubscriptions.adjust_balances(
        'user-plus',
        plan_delta_micros=-chatpoint_to_micros(250),
        check_delta_micros=chatpoint_to_micros(12),
        event_type='test_adjustment',
        created_by='test',
        db=db_session,
    )

    prompt = await resolve_system_prompt(
        'ctx={{ARTICHAT_SUBSCRIPTION_CONTEXT}}\nsub={{USER_SUBSCRIPTION}}\nplan={{PLAN_CHATPOINT_BALANCE}}\ncheck={{CHECK_CHATPOINT_BALANCE}}\ntotal={{TOTAL_CHATPOINT_BALANCE}}',
        metadata={'variables': {}, 'subscription_db': db_session, 'subscription_now': 1_720_000_100},
        user=DummyUser('user-plus'),
    )

    assert 'Current subscription: Plus' in prompt
    assert 'sub=Plus' in prompt
    assert 'plan=2750' in prompt
    assert 'check=12' in prompt
    assert 'total=2762' in prompt


@pytest.mark.asyncio
async def test_resolve_system_prompt_downgrades_expired_subscription_before_injection(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    start = 1_720_000_000
    await UserSubscriptions.create_from_plan(
        user_id='expired-plus',
        plan_id=PLUS_TIER,
        starts_at=start,
        expires_at=start + 30 * 24 * 60 * 60,
        source='test',
        db=db_session,
    )

    prompt = await resolve_system_prompt(
        'sub={{USER_SUBSCRIPTION}} tier={{USER_SUBSCRIPTION_TIER}} allowance={{PLAN_CHATPOINT_ALLOWANCE}}',
        metadata={'variables': {}, 'subscription_db': db_session, 'subscription_now': start + 31 * 24 * 60 * 60},
        user=DummyUser('expired-plus'),
    )

    assert 'sub=Free' in prompt
    assert 'tier=free' in prompt
    assert 'allowance=100' in prompt


@pytest.mark.asyncio
async def test_resolve_system_prompt_injects_platform_context():
    prompt = await resolve_system_prompt(
        'platform={{ARTICHAT_PLATFORM_CONTEXT}}',
        metadata={'variables': {}},
        user=DummyUser('user-free'),
    )

    assert 'ArtiChat' in prompt
    assert 'Chatpoint' in prompt
    assert 'Plan Chatpoint' in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/open_webui/tests/subscriptions/test_prompt_context.py -q`

Expected: fail because `ARTICHAT_SUBSCRIPTION_CONTEXT`, `USER_SUBSCRIPTION`, and `ARTICHAT_PLATFORM_CONTEXT` are not implemented.

### Task 2: Implement Server-Controlled Prompt Variables

**Files:**
- Modify: `backend/open_webui/utils/payload.py`
- Create: `backend/open_webui/resources/artichat_platform_knowledge.zh-CN.md`

- [ ] **Step 1: Add helper functions in `payload.py`**

Implement:

```python
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from open_webui.models.subscriptions import micros_to_chatpoint
from open_webui.utils.subscriptions import ensure_subscription_current
```

Add helpers:

```python
def _format_chatpoint(value_micros: int) -> str:
    value = micros_to_chatpoint(value_micros)
    return format(value.normalize(), 'f') if isinstance(value, Decimal) else str(value)


def _format_ts(value: int | None) -> str:
    if value is None:
        return 'Never'
    return datetime.fromtimestamp(value).isoformat()


def _load_platform_context() -> str:
    path = Path(__file__).resolve().parents[1] / 'resources' / 'artichat_platform_knowledge.zh-CN.md'
    try:
        return path.read_text(encoding='utf-8').strip()
    except OSError:
        return ''
```

Add async builder:

```python
async def build_server_prompt_variables(metadata: Optional[dict] = None, user=None) -> dict[str, str]:
    variables = {'{{ARTICHAT_PLATFORM_CONTEXT}}': _load_platform_context()}
    user_id = getattr(user, 'id', None)
    if not user_id and isinstance(user, dict):
        user_id = user.get('id')
    if not user_id:
        return variables

    db = (metadata or {}).get('subscription_db')
    now = (metadata or {}).get('subscription_now')
    subscription = await ensure_subscription_current(user_id, now=now, db=db)
    allowance = subscription.plan_chatpoint_allowance_micros
    plan_balance = subscription.plan_balance_micros
    check_balance = subscription.check_balance_micros
    plan_used = max(0, allowance - plan_balance)
    total_balance = plan_balance + check_balance
    exhausted = total_balance <= 0

    context = '\n'.join(
        [
            'ArtiChat user subscription context:',
            f'- Current subscription: {subscription.display_name}',
            f'- Subscription tier: {subscription.tier}',
            f'- Subscription status: {subscription.status}',
            f'- Subscription expires at: {_format_ts(subscription.expires_at)}',
            f'- Plan Chatpoint allowance: {_format_chatpoint(allowance)}',
            f'- Plan Chatpoint balance: {_format_chatpoint(plan_balance)}',
            f'- Plan Chatpoint used this period: {_format_chatpoint(plan_used)}',
            f'- Check Chatpoint balance: {_format_chatpoint(check_balance)}',
            f'- Total Chatpoint balance: {_format_chatpoint(total_balance)}',
            f'- Plan Chatpoint next reset at: {_format_ts(subscription.next_reset_at)}',
            f'- Chatpoint quota exhausted: {str(exhausted).lower()}',
        ]
    )

    variables.update(
        {
            '{{ARTICHAT_SUBSCRIPTION_CONTEXT}}': context,
            '{{USER_SUBSCRIPTION}}': subscription.display_name,
            '{{USER_SUBSCRIPTION_TIER}}': subscription.tier,
            '{{USER_SUBSCRIPTION_STATUS}}': subscription.status,
            '{{USER_SUBSCRIPTION_EXPIRES_AT}}': _format_ts(subscription.expires_at),
            '{{USER_SUBSCRIPTION_PERIOD_START_AT}}': _format_ts(subscription.period_start_at),
            '{{USER_SUBSCRIPTION_PERIOD_END_AT}}': _format_ts(subscription.period_end_at),
            '{{USER_SUBSCRIPTION_NEXT_RESET_AT}}': _format_ts(subscription.next_reset_at),
            '{{PLAN_CHATPOINT_ALLOWANCE}}': _format_chatpoint(allowance),
            '{{PLAN_CHATPOINT_BALANCE}}': _format_chatpoint(plan_balance),
            '{{PLAN_CHATPOINT_USED}}': _format_chatpoint(plan_used),
            '{{CHECK_CHATPOINT_BALANCE}}': _format_chatpoint(check_balance),
            '{{TOTAL_CHATPOINT_BALANCE}}': _format_chatpoint(total_balance),
            '{{CHATPOINT_BALANCE}}': _format_chatpoint(total_balance),
            '{{CHATPOINT_QUOTA_EXHAUSTED}}': str(exhausted).lower(),
        }
    )
    return variables
```

- [ ] **Step 2: Merge variables inside `resolve_system_prompt`**

Change `resolve_system_prompt` so it applies user-provided metadata variables first, then server variables:

```python
if metadata:
    variables = metadata.get('variables', {})
    if variables:
        system = prompt_variables_template(system, variables)

server_variables = await build_server_prompt_variables(metadata, user)
if server_variables:
    system = prompt_variables_template(system, server_variables)
```

- [ ] **Step 3: Add platform knowledge resource**

Create `backend/open_webui/resources/artichat_platform_knowledge.zh-CN.md` with a concise Chinese knowledge base covering subscriptions, Chatpoint, redeem codes, gift cards, announcements, usage pages, admin capabilities, and Docker data volume preservation.

- [ ] **Step 4: Run prompt context tests**

Run: `pytest backend/open_webui/tests/subscriptions/test_prompt_context.py -q`

Expected: 3 passed.

### Task 3: Documentation and Verification

**Files:**
- Create: `docs/knowledge/artichat-platform-knowledge.zh-CN.md`
- Modify: `docs/progress/2026-07-06-subscriptions-announcements-gift-cards.md`

- [ ] **Step 1: Add admin-facing knowledge copy**

Create a docs copy of the platform knowledge file for easy editing and review.

- [ ] **Step 2: Update progress**

Add an entry noting prompt variables, platform knowledge, tests, build, Docker status, and cleanup.

- [ ] **Step 3: Run focused verification**

Run:

```powershell
pytest backend/open_webui/tests/subscriptions -q
npm run test:subscriptions
npm run build
```

Expected:

- Subscription pytest suite passes.
- Subscription static guard passes.
- Frontend build exits 0.

- [ ] **Step 4: Commit**

```powershell
git add backend/open_webui/utils/payload.py backend/open_webui/resources/artichat_platform_knowledge.zh-CN.md backend/open_webui/tests/subscriptions/test_prompt_context.py docs/knowledge/artichat-platform-knowledge.zh-CN.md docs/progress/2026-07-06-subscriptions-announcements-gift-cards.md docs/superpowers/specs/2026-07-06-artichat-prompt-context-knowledge-design.zh-CN.md docs/superpowers/plans/2026-07-06-artichat-prompt-context-knowledge.md
git commit -m "feat: add ArtiChat prompt context variables"
```

### Task 4: Docker Rebuild

**Files:**
- Docker runtime only.

- [ ] **Step 1: Rebuild image**

Run: `docker compose -p artichat build artichat`

Expected: `Image artichat:main Built`.

- [ ] **Step 2: Recreate container**

Run:

```powershell
docker rm -f artichat
docker compose -p artichat up -d --no-deps artichat
```

Expected: container `artichat` starts using `artichat:main`.

- [ ] **Step 3: Verify health**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri http://localhost:3000/health -TimeoutSec 20
docker ps --filter name=artichat --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

Expected: HTTP 200 with `{"status":true}` and container status `healthy`.

- [ ] **Step 4: Clean unused dangling images**

Run: `docker image prune -f`

Expected: cleanup completes without touching volumes.
