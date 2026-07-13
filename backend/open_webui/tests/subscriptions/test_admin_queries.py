import pytest
from fastapi.encoders import jsonable_encoder
from types import SimpleNamespace

from open_webui.models.subscriptions import (
    FREE_TIER,
    SubscriptionLedgers,
    SubscriptionPlans,
    SubscriptionUsages,
    UserSubscriptions,
)
from open_webui.models.users import User
from open_webui.routers.subscriptions import get_my_usage


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
        cache_creation_tokens=5,
        cache_read_tokens=7,
        total_tokens=30,
        input_chatpoint_per_million='10',
        output_chatpoint_per_million='20',
        cache_creation_chatpoint_per_million='4',
        cache_read_chatpoint_per_million='1',
        cost_micros=3,
        plan_cost_micros=3,
        check_cost_micros=0,
        plan_balance_after_micros=100,
        check_balance_after_micros=0,
        client_ip='203.0.113.8',
        raw_usage={'prompt_tokens': 22},
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
    assert usage['items'][0]['client_ip'] == '203.0.113.8'
    assert usage['total_cache_creation_tokens'] == 5
    assert usage['total_cache_read_tokens'] == 7
    assert ledger[0]['user']['email'] == 'alice@example.com'


@pytest.mark.asyncio
async def test_user_usage_projection_never_serializes_sensitive_audit_fields(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await create_user(db_session, 'private-user', 'private@example.com', 'private', 'Private User')
    await UserSubscriptions.create_from_plan(
        user_id='private-user',
        plan_id=FREE_TIER,
        starts_at=1_720_000_000,
        expires_at=None,
        source='default',
        db=db_session,
    )
    await SubscriptionUsages.insert(
        user_id='private-user',
        chat_id='chat-private',
        message_id='msg-private',
        request_id='req-private',
        model_id='model-private',
        tier='free',
        quota_mode='metered',
        usage_multiplier='1',
        input_tokens=10,
        output_tokens=20,
        cache_creation_tokens=5,
        cache_read_tokens=7,
        total_tokens=42,
        cost_micros=3,
        plan_cost_micros=3,
        check_cost_micros=0,
        plan_balance_after_micros=100,
        check_balance_after_micros=0,
        first_token_latency_ms=50,
        total_duration_ms=400,
        client_ip='203.0.113.9',
        raw_usage={'secret_provider_detail': True},
        status='billed',
        metadata={'internal': 'value'},
        created_at=1_720_000_000,
        db=db_session,
    )

    response = jsonable_encoder(await get_my_usage(user=SimpleNamespace(id='private-user'), db=db_session))
    item = response['usage']['items'][0]

    assert item['model_id'] == 'model-private'
    assert item['cache_creation_tokens'] == 5
    assert item['first_token_latency_ms'] == 50
    assert {'client_ip', 'raw_usage', 'metadata', 'user_id'}.isdisjoint(item)


@pytest.mark.asyncio
async def test_admin_usage_filters_by_status(db_session):
    await SubscriptionUsages.insert(
        user_id='filter-user',
        chat_id=None,
        message_id=None,
        model_id='model-filter',
        tier='free',
        quota_mode='metered',
        usage_multiplier='1',
        input_tokens=1,
        output_tokens=0,
        total_tokens=1,
        cost_micros=1,
        plan_cost_micros=1,
        check_cost_micros=0,
        plan_balance_after_micros=0,
        check_balance_after_micros=0,
        status='billed',
        metadata={},
        created_at=1_720_000_000,
        db=db_session,
    )
    await SubscriptionUsages.insert(
        user_id='filter-user',
        chat_id=None,
        message_id=None,
        model_id='model-filter',
        tier='free',
        quota_mode='unlimited',
        usage_multiplier='1',
        input_tokens=2,
        output_tokens=0,
        total_tokens=2,
        cost_micros=0,
        plan_cost_micros=0,
        check_cost_micros=0,
        plan_balance_after_micros=0,
        check_balance_after_micros=0,
        status='unlimited',
        metadata={},
        created_at=1_720_000_001,
        db=db_session,
    )

    result = await SubscriptionUsages.get_usage_summary(status='unlimited', db=db_session)

    assert [item.status for item in result['items']] == ['unlimited']


@pytest.mark.asyncio
async def test_usage_totals_cover_full_filter_when_items_are_paginated(db_session):
    for index in range(2):
        await SubscriptionUsages.insert(
            user_id='summary-user',
            chat_id=None,
            message_id=None,
            model_id='summary-model',
            tier='free',
            quota_mode='metered',
            usage_multiplier='1',
            input_tokens=10 + index,
            output_tokens=20 + index,
            cache_creation_tokens=2,
            cache_read_tokens=3,
            total_tokens=30 + index * 2,
            cost_micros=100 + index,
            plan_cost_micros=100 + index,
            check_cost_micros=0,
            plan_balance_after_micros=0,
            check_balance_after_micros=0,
            status='billed',
            metadata={},
            created_at=1_720_000_000 + index,
            db=db_session,
        )

    result = await SubscriptionUsages.get_usage_summary(
        user_id='summary-user',
        limit=1,
        db=db_session,
    )

    assert len(result['items']) == 1
    assert result['total_cost_micros'] == 201
    assert result['total_input_tokens'] == 21
    assert result['total_output_tokens'] == 41
    assert result['total_cache_creation_tokens'] == 4
    assert result['total_cache_read_tokens'] == 6


@pytest.mark.asyncio
async def test_admin_user_list_includes_subscription_summary(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await create_user(db_session, 'summary-user', 'summary@example.com', 'summary', 'Summary User')
    subscription = await UserSubscriptions.create_from_plan(
        user_id='summary-user',
        plan_id=FREE_TIER,
        starts_at=1_720_000_000,
        expires_at=1_730_000_000,
        source='default',
        db=db_session,
    )
    subscription.check_balance_micros = 2_500_000
    await UserSubscriptions.save(subscription, db=db_session)

    summaries = await UserSubscriptions.get_summaries_by_user_ids(['summary-user'], db=db_session)

    summary = summaries['summary-user']
    assert summary.tier == 'free'
    assert summary.display_name == 'Free'
    assert summary.status == 'free'
    assert summary.expires_at == 1_730_000_000
    assert summary.plan_balance_micros == 100_000_000
    assert summary.check_balance_micros == 2_500_000
