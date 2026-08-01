from types import SimpleNamespace

import pytest
from fastapi.encoders import jsonable_encoder
from open_webui.models.subscriptions import (
    FREE_TIER,
    SubscriptionLedgers,
    SubscriptionPlans,
    SubscriptionUsages,
    UserSubscriptions,
    now_ts,
)
from open_webui.models.users import User
from open_webui.routers.subscriptions import export_admin_usage, get_my_usage


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
    assert usage['model_totals'] == [
        {
            'model_id': 'model-1',
            'total_tokens': 30,
            'request_count': 1,
            'cost_micros': 3,
            'plan_cost_micros': 3,
            'check_cost_micros': 0,
            'unpaid_cost_micros': 0,
        }
    ]
    assert ledger[0]['user']['email'] == 'alice@example.com'


@pytest.mark.asyncio
async def test_admin_usage_filters_by_partial_user_email(db_session):
    await create_user(db_session, 'usage-alice', 'alice.usage@example.com', 'alice-usage', 'Alice Usage')
    await create_user(db_session, 'usage-bob', 'bob.usage@example.com', 'bob-usage', 'Bob Usage')
    for user_id, model_id, created_at in [
        ('usage-alice', 'model-alice', 1_720_000_000),
        ('usage-bob', 'model-bob', 1_720_000_100),
    ]:
        await SubscriptionUsages.insert(
            user_id=user_id,
            chat_id=None,
            message_id=None,
            model_id=model_id,
            tier='free',
            quota_mode='metered',
            usage_multiplier='1',
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_micros=2,
            plan_cost_micros=2,
            check_cost_micros=0,
            plan_balance_after_micros=100,
            check_balance_after_micros=0,
            status='billed',
            metadata={},
            created_at=created_at,
            db=db_session,
        )

    usage = await SubscriptionUsages.get_usage_summary(
        user_email='alice.usage',
        include_user=True,
        db=db_session,
    )

    assert [item['model_id'] for item in usage['items']] == ['model-alice']
    assert usage['items'][0]['user']['email'] == 'alice.usage@example.com'
    assert usage['total_input_tokens'] == 10
    assert usage['model_totals'] == [
        {
            'model_id': 'model-alice',
            'total_tokens': 15,
            'request_count': 1,
            'cost_micros': 2,
            'plan_cost_micros': 2,
            'check_cost_micros': 0,
            'unpaid_cost_micros': 0,
        }
    ]


@pytest.mark.asyncio
async def test_user_usage_projection_never_serializes_sensitive_audit_fields(db_session):
    current_time = now_ts()
    await SubscriptionPlans.seed_defaults(db=db_session)
    await create_user(db_session, 'private-user', 'private@example.com', 'private', 'Private User')
    await UserSubscriptions.create_from_plan(
        user_id='private-user',
        plan_id=FREE_TIER,
        starts_at=current_time - 60,
        expires_at=None,
        source='default',
        db=db_session,
    )
    await SubscriptionUsages.insert(
        user_id='private-user',
        chat_id=None,
        message_id=None,
        request_id='req-previous-period',
        model_id='model-previous-period',
        tier='free',
        quota_mode='metered',
        usage_multiplier='1',
        input_tokens=999,
        output_tokens=0,
        total_tokens=999,
        cost_micros=99,
        plan_cost_micros=99,
        check_cost_micros=0,
        plan_balance_after_micros=100,
        check_balance_after_micros=0,
        status='billed',
        metadata={},
        created_at=current_time - 90,
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
        created_at=current_time - 30,
        db=db_session,
    )

    response = jsonable_encoder(await get_my_usage(user=SimpleNamespace(id='private-user'), db=db_session))
    item = response['usage']['items'][0]

    assert item['model_id'] == 'model-private'
    assert item['cache_creation_tokens'] == 5
    assert item['first_token_latency_ms'] == 50
    assert {'client_ip', 'raw_usage', 'metadata', 'user_id'}.isdisjoint(item)
    assert response['usage']['total_request_count'] == 1
    assert response['usage']['total_input_tokens'] == 10


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
    assert result['total_plan_cost_micros'] == 201
    assert result['total_check_cost_micros'] == 0
    assert result['total_unpaid_cost_micros'] == 0
    assert result['total_tokens'] == 62
    assert result['total_item_count'] == 2
    assert result['total_request_count'] == 2


@pytest.mark.asyncio
async def test_admin_usage_overview_counts_logical_requests_and_recent_window(db_session):
    current_time = now_ts()
    for request_id, model_id, created_at in [
        ('shared-request', 'model-a', current_time - 60),
        ('shared-request', 'model-a', current_time - 30),
        ('old-request', 'model-b', current_time - 31 * 24 * 60 * 60),
    ]:
        await SubscriptionUsages.insert(
            user_id='overview-user',
            chat_id=None,
            message_id=None,
            request_id=request_id,
            model_id=model_id,
            tier='plus',
            quota_mode='metered',
            usage_multiplier='1',
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_micros=3,
            plan_cost_micros=2,
            check_cost_micros=1,
            plan_balance_after_micros=100,
            check_balance_after_micros=50,
            status='billed',
            metadata={},
            created_at=created_at,
            db=db_session,
        )

    overview = await SubscriptionUsages.get_admin_overview(db=db_session)
    filtered = await SubscriptionUsages.get_usage_summary(user_id='overview-user', limit=1, db=db_session)

    assert overview['total_request_count'] == 2
    assert overview['recent_30d_request_count'] == 1
    assert overview['total_plan_cost_micros'] == 6
    assert overview['total_check_cost_micros'] == 3
    assert [item['model_id'] for item in overview['model_totals']] == ['model-a', 'model-b']
    assert overview['model_totals'][0]['request_count'] == 1
    assert filtered['total_item_count'] == 3
    assert filtered['total_request_count'] == 2


@pytest.mark.asyncio
async def test_admin_ledger_supports_user_time_filters_and_total_count(db_session):
    for user_id, created_at in [
        ('ledger-user-a', 1_720_000_000),
        ('ledger-user-a', 1_720_000_100),
        ('ledger-user-b', 1_720_000_200),
    ]:
        await SubscriptionLedgers.insert(
            user_id=user_id,
            event_type='usage_debit',
            tier_before='free',
            tier_after='free',
            plan_delta_micros=-1,
            check_delta_micros=0,
            plan_balance_after_micros=10,
            check_balance_after_micros=0,
            created_at=created_at,
            db=db_session,
        )

    rows = await SubscriptionLedgers.search(
        user_id='ledger-user-a',
        start_at=1_720_000_050,
        end_at=1_720_000_150,
        include_user=True,
        db=db_session,
    )
    count = await SubscriptionLedgers.count(
        user_id='ledger-user-a',
        start_at=1_720_000_050,
        end_at=1_720_000_150,
        db=db_session,
    )

    assert len(rows) == 1
    assert rows[0]['created_at'] == 1_720_000_100
    assert count == 1


@pytest.mark.asyncio
async def test_admin_usage_csv_exports_full_filtered_result(db_session):
    await create_user(db_session, 'csv-user', 'csv@example.com', 'csv-user', 'CSV User')
    for index in range(2):
        await SubscriptionUsages.insert(
            user_id='csv-user',
            chat_id=None,
            message_id=None,
            request_id=f'csv-request-{index}',
            model_id='csv-model',
            tier='plus',
            quota_mode='metered',
            usage_multiplier='1',
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_micros=3,
            plan_cost_micros=2,
            check_cost_micros=1,
            plan_balance_after_micros=100,
            check_balance_after_micros=50,
            status='billed',
            metadata={},
            created_at=1_720_000_000 + index,
            db=db_session,
        )

    response = await export_admin_usage(
        kind='requests',
        user_id='csv-user',
        model_id=None,
        status='billed',
        start_at=None,
        end_at=None,
        user=SimpleNamespace(id='admin-user', role='admin'),
        db=db_session,
    )
    csv_text = response.body.decode('utf-8-sig')

    assert response.headers['content-disposition'] == 'attachment; filename="usage-ledger-requests.csv"'
    assert csv_text.count('csv-request-') == 2
    assert 'csv@example.com' in csv_text
    assert '创建缓存Token' in csv_text


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
    await UserSubscriptions.save(subscription, allow_balance_change=True, db=db_session)

    summaries = await UserSubscriptions.get_summaries_by_user_ids(['summary-user'], db=db_session)

    summary = summaries['summary-user']
    assert summary.tier == 'free'
    assert summary.display_name == 'Free'
    assert summary.status == 'free'
    assert summary.expires_at == 1_730_000_000
    assert summary.plan_balance_micros == 100_000_000
    assert summary.check_balance_micros == 2_500_000


@pytest.mark.asyncio
async def test_admin_plan_update_persists_card_fields_and_allowance(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    updated = await SubscriptionPlans.update_plan(
        FREE_TIER,
        display_name='Starter',
        description='A compact starter plan.',
        plan_chatpoint_allowance_micros=750_000_000,
        period_days=60,
        features={
            'icon': 'sparkles',
            'subtitle': '轻量体验',
            'highlights': ['750 Chatpoint', '基础模型'],
            'model_summary': '基础模型',
            'cta_label': '当前计划',
        },
        is_active=True,
        db=db_session,
    )

    assert updated.display_name == 'Starter'
    assert updated.plan_chatpoint_allowance_micros == 750_000_000
    assert updated.period_days == 60
    assert updated.features['subtitle'] == '轻量体验'

    persisted = await SubscriptionPlans.get_plan_by_id(FREE_TIER, db=db_session)
    assert persisted is not None
    assert persisted.plan_chatpoint_allowance_micros == 750_000_000
    assert persisted.period_days == 60
