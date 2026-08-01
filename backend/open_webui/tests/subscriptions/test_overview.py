import datetime as dt

import pytest
from open_webui.models.subscription_overview import SubscriptionOverview
from open_webui.models.subscriptions import (
    GiftCardGrants,
    RedemptionCode,
    RedemptionCodes,
    SubscriptionLedgers,
    SubscriptionPlans,
    SubscriptionUsages,
    UserSubscriptions,
    chatpoint_to_micros,
)
from open_webui.models.users import User


async def create_user(db_session, user_id: str, email: str):
    db_session.add(
        User(
            id=user_id,
            email=email,
            username=user_id,
            name=user_id,
            role='user',
            created_at=1_700_000_000,
            updated_at=1_700_000_000,
            last_active_at=1_700_000_000,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_subscription_overview_uses_real_metrics_and_filters_activity(db_session, monkeypatch):
    monkeypatch.setenv('WEBUI_TIMEZONE', 'UTC')
    current_time = 1_800_000_000
    local_now = dt.datetime.fromtimestamp(current_time, tz=dt.UTC)
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_start = (month_start - dt.timedelta(days=1)).replace(day=1)

    await SubscriptionPlans.seed_defaults(db=db_session)
    await create_user(db_session, 'overview-current', 'current@example.com')
    await create_user(db_session, 'overview-previous', 'previous@example.com')

    await UserSubscriptions.create_from_plan(
        user_id='overview-current',
        plan_id='plus',
        starts_at=int(month_start.timestamp()) + 100,
        expires_at=None,
        source='redemption',
        db=db_session,
    )
    await UserSubscriptions.create_from_plan(
        user_id='overview-previous',
        plan_id='plus',
        starts_at=int(previous_month_start.timestamp()) + 100,
        expires_at=None,
        source='redemption',
        db=db_session,
    )

    await GiftCardGrants.issue_grants(
        user_ids=['overview-current'],
        mode='single_use',
        tier='plus',
        duration_days=30,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=0,
        expires_at=current_time + 100,
        memo='valid gift',
        created_by='admin',
        now=current_time - 100,
        db=db_session,
    )
    invalid_gift = await GiftCardGrants.issue_grants(
        user_ids=['overview-previous'],
        mode='single_use',
        tier='plus',
        duration_days=30,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=0,
        expires_at=current_time + 100,
        memo='disabled gift',
        created_by='admin',
        now=current_time - 100,
        db=db_session,
    )
    invalid_code = await db_session.get(RedemptionCode, invalid_gift.grants[0].redemption_code_id)
    invalid_code.is_active = False
    await db_session.commit()

    await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier='plus',
        duration_days=30,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=0,
        expires_at=current_time + 100,
        memo='subscription code',
        created_by='admin',
        now=current_time - 100,
        db=db_session,
    )
    await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=chatpoint_to_micros(50),
        check_chatpoint_micros=0,
        expires_at=current_time + 100,
        memo='recharge code',
        created_by='admin',
        now=current_time - 100,
        db=db_session,
    )

    day_start = int(local_now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    await SubscriptionUsages.insert(
        user_id='overview-current',
        chat_id=None,
        message_id=None,
        model_id='model-overview',
        tier='plus',
        quota_mode='metered',
        usage_multiplier='1',
        input_tokens=10,
        output_tokens=10,
        total_tokens=20,
        cost_micros=chatpoint_to_micros(7),
        plan_cost_micros=chatpoint_to_micros(5),
        check_cost_micros=chatpoint_to_micros(2),
        plan_balance_after_micros=0,
        check_balance_after_micros=0,
        status='billed',
        metadata={},
        created_at=day_start + 100,
        db=db_session,
    )
    await SubscriptionUsages.insert(
        user_id='overview-current',
        chat_id=None,
        message_id=None,
        model_id='model-overview',
        tier='plus',
        quota_mode='metered',
        usage_multiplier='1',
        input_tokens=10,
        output_tokens=10,
        total_tokens=20,
        cost_micros=chatpoint_to_micros(9),
        plan_cost_micros=chatpoint_to_micros(9),
        check_cost_micros=0,
        plan_balance_after_micros=0,
        check_balance_after_micros=0,
        status='billed',
        metadata={},
        created_at=day_start - 100,
        db=db_session,
    )

    await SubscriptionLedgers.insert(
        user_id='overview-current',
        event_type='redemption',
        tier_before='free',
        tier_after='plus',
        plan_delta_micros=chatpoint_to_micros(3000),
        check_delta_micros=0,
        plan_balance_after_micros=chatpoint_to_micros(3000),
        check_balance_after_micros=0,
        created_at=current_time - 10,
        db=db_session,
    )
    await SubscriptionLedgers.insert(
        user_id='overview-current',
        event_type='usage_debit',
        tier_before='plus',
        tier_after='plus',
        plan_delta_micros=-chatpoint_to_micros(5),
        check_delta_micros=0,
        plan_balance_after_micros=0,
        check_balance_after_micros=0,
        created_at=current_time - 5,
        db=db_session,
    )
    await SubscriptionLedgers.insert(
        user_id='overview-current',
        event_type='redemption',
        tier_before='plus',
        tier_after='plus',
        plan_delta_micros=0,
        check_delta_micros=chatpoint_to_micros(5),
        plan_balance_after_micros=0,
        check_balance_after_micros=chatpoint_to_micros(5),
        created_at=current_time - 1,
        db=db_session,
    )

    result = await SubscriptionOverview.get(now=current_time, db=db_session)

    assert result['timezone'] == 'UTC'
    assert result['metrics']['active_subscriptions'] == {
        'count': 2,
        'mtd_count': 1,
        'previous_mtd_count': 1,
        'mtd_change_percent': 0.0,
    }
    assert result['metrics']['pending_gifts'] == {'count': 1, 'batch_count': 1}
    assert result['metrics']['daily_deductions']['plan_micros'] == chatpoint_to_micros(5)
    assert result['metrics']['daily_deductions']['check_micros'] == chatpoint_to_micros(2)
    assert result['metrics']['available_codes']['subscription'] == 2
    assert result['metrics']['available_codes']['recharge'] == 1
    assert result['metrics']['available_codes']['total'] == 3
    assert [item['event_type'] for item in result['recent_activity']] == ['redemption']
    assert result['recent_activity'][0]['user']['email'] == 'current@example.com'
