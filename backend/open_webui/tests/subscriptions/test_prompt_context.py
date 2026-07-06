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
        (
            'ctx={{ARTICHAT_SUBSCRIPTION_CONTEXT}}\n'
            'sub={{USER_SUBSCRIPTION}}\n'
            'plan={{PLAN_CHATPOINT_BALANCE}}\n'
            'check={{CHECK_CHATPOINT_BALANCE}}\n'
            'total={{TOTAL_CHATPOINT_BALANCE}}'
        ),
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
