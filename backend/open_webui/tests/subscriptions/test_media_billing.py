import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from open_webui.models.subscriptions import (
    SubscriptionPlans,
    SubscriptionReservations,
    SubscriptionUsages,
    UserSubscriptions,
    chatpoint_to_micros,
)
from open_webui.utils.media_billing import (
    release_media_generation,
    reserve_media_generation,
    settle_media_generation,
)
from open_webui.utils.subscriptions import ensure_subscription_current

NOW = int(time.time())


async def _set_balance(db_session, user_id: str, amount: int):
    await SubscriptionPlans.seed_defaults(db=db_session)
    current = await ensure_subscription_current(user_id, now=NOW, db=db_session)
    return await UserSubscriptions.adjust_balances(
        user_id,
        plan_delta_micros=chatpoint_to_micros(amount) - current.plan_balance_micros,
        check_delta_micros=-current.check_balance_micros,
        event_type='test_media_balance_setup',
        created_by='test',
        db=db_session,
    )


@pytest.mark.asyncio
async def test_media_settlement_is_idempotent_and_uses_actual_units(db_session):
    await _set_balance(db_session, 'media-settle-user', 20)
    user = SimpleNamespace(id='media-settle-user', role='user')
    starting = (await UserSubscriptions.get_by_user_id(user.id, db=db_session)).plan_balance_micros
    context = await reserve_media_generation(
        user,
        media_type='video',
        units=10,
        rate_chatpoints='1',
        model_id='video-model',
        request_id='media-settle-request',
        db=db_session,
    )

    first = await settle_media_generation(
        context,
        units=6,
        metadata={'actual_duration_seconds': 6},
        db=db_session,
    )
    second = await settle_media_generation(context, units=6, db=db_session)

    assert first.id == second.id
    reservation = await SubscriptionReservations.get_by_id(context.reservation_id, db=db_session)
    usage = await SubscriptionUsages.get_by_reservation_id(context.reservation_id, db=db_session)
    subscription = await UserSubscriptions.get_by_user_id(user.id, db=db_session)
    assert reservation.status == 'settled'
    assert reservation.actual_cost_micros == chatpoint_to_micros(6)
    assert usage.media_units == 6
    assert usage.cost_micros == chatpoint_to_micros(6)
    assert subscription.plan_balance_micros == starting - chatpoint_to_micros(6)


@pytest.mark.asyncio
async def test_media_release_is_idempotent_and_writes_zero_cost_audit(db_session):
    await _set_balance(db_session, 'media-release-user', 20)
    user = SimpleNamespace(id='media-release-user', role='user')
    starting = (await UserSubscriptions.get_by_user_id(user.id, db=db_session)).plan_balance_micros
    context = await reserve_media_generation(
        user,
        media_type='image',
        units=2,
        rate_chatpoints='1',
        model_id='image-model',
        request_id='media-release-request',
        db=db_session,
    )

    first = await release_media_generation(context, reason='provider failed', db=db_session)
    second = await release_media_generation(context, reason='duplicate callback', db=db_session)

    assert first.id == second.id
    reservation = await SubscriptionReservations.get_by_id(context.reservation_id, db=db_session)
    usage = await SubscriptionUsages.get_by_reservation_id(context.reservation_id, db=db_session)
    subscription = await UserSubscriptions.get_by_user_id(user.id, db=db_session)
    assert reservation.status == 'released'
    assert usage.media_units == 0
    assert usage.cost_micros == 0
    assert usage.status == 'failed'
    assert subscription.plan_balance_micros == starting


@pytest.mark.asyncio
async def test_media_daily_cap_counts_active_reservations_atomically(db_session):
    await _set_balance(db_session, 'media-cap-user', 20)
    user = SimpleNamespace(id='media-cap-user', role='user')

    first = await reserve_media_generation(
        user,
        media_type='video',
        units=4,
        rate_chatpoints='1',
        model_id='video-model',
        request_id='media-cap-request-1',
        daily_cap_chatpoints='5',
        db=db_session,
    )

    with pytest.raises(HTTPException) as error:
        await reserve_media_generation(
            user,
            media_type='video',
            units=2,
            rate_chatpoints='1',
            model_id='video-model',
            request_id='media-cap-request-2',
            daily_cap_chatpoints='5',
            db=db_session,
        )

    assert error.value.status_code == 429
    assert error.value.detail['code'] == 'MEDIA_DAILY_CAP_EXCEEDED'
    await release_media_generation(first, reason='test cleanup', db=db_session)
