import pytest

from open_webui.models.subscriptions import (
    FREE_TIER,
    SubscriptionLedgers,
    SubscriptionPlans,
    SubscriptionUsages,
    UserSubscriptions,
)
from open_webui.models.users import User


async def create_user(db_session, user_id: str, email: str, username: str, name: str):
    db_session.add(
        User(
            id=user_id,
            email=email,
            username=username,
            name=name,
            role='user',
            created_at=1_720_000_000,
            updated_at=1_720_000_000,
            last_active_at=1_720_000_000,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_admin_subscription_search_matches_user_email_username_and_name(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await create_user(db_session, 'user-1', 'alice@example.com', 'alice', 'Alice Art')
    await create_user(db_session, 'user-2', 'bob@example.com', 'bob', 'Bob')
    await UserSubscriptions.create_from_plan(
        user_id='user-1',
        plan_id=FREE_TIER,
        starts_at=1_720_000_000,
        expires_at=None,
        source='default',
        db=db_session,
    )
    await UserSubscriptions.create_from_plan(
        user_id='user-2',
        plan_id=FREE_TIER,
        starts_at=1_720_000_000,
        expires_at=None,
        source='default',
        db=db_session,
    )

    by_email = await UserSubscriptions.list_subscriptions_with_users(query='alice@example.com', db=db_session)
    by_username = await UserSubscriptions.list_subscriptions_with_users(query='alice', db=db_session)
    by_name = await UserSubscriptions.list_subscriptions_with_users(query='Alice Art', db=db_session)

    assert [item['user']['email'] for item in by_email] == ['alice@example.com']
    assert [item['user']['email'] for item in by_username] == ['alice@example.com']
    assert [item['user']['email'] for item in by_name] == ['alice@example.com']
    assert by_email[0]['subscription'].user_id == 'user-1'


@pytest.mark.asyncio
async def test_admin_usage_and_ledger_include_user_email(db_session):
    await create_user(db_session, 'user-1', 'alice@example.com', 'alice', 'Alice Art')
    await SubscriptionUsages.insert(
        user_id='user-1',
        chat_id='chat-1',
        message_id='msg-1',
        model_id='model-1',
        tier='free',
        quota_mode='metered',
        usage_multiplier='1',
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        cost_micros=3,
        plan_cost_micros=3,
        check_cost_micros=0,
        plan_balance_after_micros=100,
        check_balance_after_micros=0,
        status='billed',
        metadata={},
        created_at=1_720_000_000,
        db=db_session,
    )
    await SubscriptionLedgers.insert(
        user_id='user-1',
        event_type='usage_debit',
        tier_before='free',
        tier_after='free',
        plan_delta_micros=-3,
        check_delta_micros=0,
        plan_balance_after_micros=100,
        check_balance_after_micros=0,
        db=db_session,
    )

    usage = await SubscriptionUsages.get_usage_summary(include_user=True, db=db_session)
    ledger = await SubscriptionLedgers.search(include_user=True, db=db_session)

    assert usage['items'][0]['user']['email'] == 'alice@example.com'
    assert ledger[0]['user']['email'] == 'alice@example.com'
