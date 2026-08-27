import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from open_webui.models.subscriptions import (
    SubscriptionPlans,
    SubscriptionReservations,
    UserSubscriptions,
    chatpoint_to_micros,
)
from open_webui.utils.subscriptions import (
    ChatpointReservationConflictError,
    ChatpointReservationInsufficientError,
    bill_model_usage,
    count_pending_chatpoint_settlements,
    defer_chatpoint_reservation_settlement,
    ensure_subscription_current,
    extend_chatpoint_reservation,
    get_reservation_id,
    get_max_pending_settlements_per_user,
    release_chatpoint_reservation,
    release_expired_chatpoint_reservations,
    renew_chatpoint_reservation,
    reserve_chatpoint_batch,
    reserve_chatpoints,
    resize_chatpoint_reservation_batch,
    settle_chatpoint_reservation,
    process_pending_chatpoint_settlements,
)
from sqlalchemy.ext.asyncio import async_sessionmaker

NOW = 1_720_000_000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('configured', 'expected'),
    [('8', 8), (0, 0), (-4, 0), (999, 100), ('invalid', 3)],
)
async def test_pending_settlement_limit_is_bounded(monkeypatch, configured, expected):
    async def get_config(*_args, **_kwargs):
        return configured

    monkeypatch.setattr('open_webui.utils.subscriptions._pending_settlement_limit_cache', None)
    monkeypatch.setattr('open_webui.utils.subscriptions.Config.get', get_config)

    assert await get_max_pending_settlements_per_user() == expected


def test_reservation_id_helper_accepts_public_and_internal_forms():
    reservation = SimpleNamespace(id='reservation-1')
    grant = SimpleNamespace(reservation=reservation)

    assert get_reservation_id('reservation-1') == 'reservation-1'
    assert get_reservation_id(reservation) == 'reservation-1'
    assert get_reservation_id(grant) == 'reservation-1'


async def set_balances(db_session, user_id: str, *, plan: int, check: int = 0):
    await SubscriptionPlans.seed_defaults(db=db_session)
    current = await ensure_subscription_current(user_id, now=NOW, db=db_session)
    return await UserSubscriptions.adjust_balances(
        user_id,
        plan_delta_micros=chatpoint_to_micros(plan) - current.plan_balance_micros,
        check_delta_micros=chatpoint_to_micros(check) - current.check_balance_micros,
        event_type='test_balance_setup',
        created_by='test',
        db=db_session,
    )


@pytest.mark.asyncio
async def test_deferred_settlement_restores_hold_and_bills_once(db_session):
    await set_balances(db_session, 'deferred-user', plan=10)
    grant = await reserve_chatpoints(
        'deferred-user',
        request_id='deferred-request',
        model_id='model-a',
        amount_micros=chatpoint_to_micros(8),
        now=NOW + 1,
        db=db_session,
    )
    reservation_id = grant.reservation.id

    await defer_chatpoint_reservation_settlement(
        reservation_id,
        {
            'user_id': 'deferred-user',
            'model_id': 'model-a',
            'quota_mode': 'metered',
            'usage_multiplier': '1',
            'usage': {'input_tokens': 10_000, 'output_tokens': 0},
            'metadata': {'request_id': 'deferred-request'},
            'is_admin': False,
            'pricing': {
                'input_chatpoint_per_million': '100',
                'output_chatpoint_per_million': '100',
                'cache_creation_chatpoint_per_million': '0',
                'cache_read_chatpoint_per_million': '0',
            },
            'request_id': 'deferred-request',
        },
        now=NOW + 2,
        db=db_session,
    )

    restored = await UserSubscriptions.get_by_user_id('deferred-user', db=db_session)
    assert restored.plan_balance_micros == chatpoint_to_micros(10)
    assert await count_pending_chatpoint_settlements('deferred-user', db=db_session) == 1

    assert await process_pending_chatpoint_settlements(limit=5, db=db_session) == 1
    settled = await SubscriptionReservations.get_by_id(reservation_id, db=db_session)
    assert settled.status in {'settled', 'partially_settled'}
    assert await count_pending_chatpoint_settlements('deferred-user', db=db_session) == 0
    subscription = await UserSubscriptions.get_by_user_id('deferred-user', db=db_session)
    assert subscription.pending_settlement_count == 0


@pytest.mark.asyncio
async def test_pending_settlement_limit_is_atomic_under_concurrency(db_session):
    await set_balances(db_session, 'pending-concurrency-user', plan=10)
    reservations = [
        (
            await reserve_chatpoints(
                'pending-concurrency-user',
                request_id=f'pending-concurrency-{index}',
                model_id='model-a',
                amount_micros=chatpoint_to_micros(1),
                now=NOW + index + 1,
                db=db_session,
            )
        ).reservation
        for index in range(5)
    ]
    Session = async_sessionmaker(db_session.bind, expire_on_commit=False)
    barrier = asyncio.Barrier(len(reservations))

    async def defer_once(reservation):
        await barrier.wait()
        async with Session() as session:
            return await defer_chatpoint_reservation_settlement(
                reservation.id,
                {'user_id': 'pending-concurrency-user', 'model_id': 'model-a'},
                max_pending_settlements=3,
                now=NOW + 10,
                db=session,
            )

    results = await asyncio.gather(*(defer_once(reservation) for reservation in reservations))
    db_session.expire_all()
    subscription = await UserSubscriptions.get_by_user_id('pending-concurrency-user', db=db_session)

    assert sum(result is not None for result in results) == 3
    assert await count_pending_chatpoint_settlements('pending-concurrency-user', db=db_session) == 3
    assert subscription.pending_settlement_count == 3


@pytest.mark.asyncio
async def test_expired_cleanup_preserves_pending_settlement_for_recovery(db_session):
    await set_balances(db_session, 'pending-expiry-user', plan=10)
    reservation = (
        await reserve_chatpoints(
            'pending-expiry-user',
            request_id='pending-expiry-request',
            model_id='model-a',
            amount_micros=chatpoint_to_micros(5),
            now=NOW + 1,
            db=db_session,
        )
    ).reservation

    await defer_chatpoint_reservation_settlement(
        reservation.id,
        {'user_id': 'pending-expiry-user', 'model_id': 'model-a'},
        max_pending_settlements=3,
        now=NOW + 2,
        db=db_session,
    )

    released = await release_expired_chatpoint_reservations(
        now=NOW + 86403,
        limit=100,
        db=db_session,
    )
    preserved = await SubscriptionReservations.get_by_id(reservation.id, db=db_session)

    assert released == []
    assert preserved.status == 'active'
    assert await count_pending_chatpoint_settlements('pending-expiry-user', db=db_session) == 1
    subscription = await UserSubscriptions.get_by_user_id('pending-expiry-user', db=db_session)
    assert subscription.pending_settlement_count == 1


@pytest.mark.asyncio
async def test_pending_settlement_limit_zero_keeps_reservation_for_sync_billing(db_session):
    await set_balances(db_session, 'pending-zero-user', plan=10)
    reservation = (
        await reserve_chatpoints(
            'pending-zero-user',
            request_id='pending-zero-request',
            model_id='model-a',
            amount_micros=chatpoint_to_micros(5),
            now=NOW + 1,
            db=db_session,
        )
    ).reservation

    deferred = await defer_chatpoint_reservation_settlement(
        reservation.id,
        {'user_id': 'pending-zero-user', 'model_id': 'model-a'},
        max_pending_settlements=0,
        now=NOW + 2,
        db=db_session,
    )
    unchanged = await SubscriptionReservations.get_by_id(reservation.id, db=db_session)
    subscription = await UserSubscriptions.get_by_user_id('pending-zero-user', db=db_session)

    assert deferred is None
    assert unchanged.status == 'active'
    assert unchanged.reserved_micros == chatpoint_to_micros(5)
    assert subscription.plan_balance_micros == chatpoint_to_micros(5)
    assert subscription.pending_settlement_count == 0


@pytest.mark.asyncio
async def test_fanout_batch_reservation_is_all_or_nothing(db_session):
    await set_balances(db_session, 'batch-user', plan=25)

    with pytest.raises(ChatpointReservationInsufficientError):
        await reserve_chatpoint_batch(
            'batch-user',
            [
                {'request_id': 'batch-a', 'model_id': 'model-a', 'amount_micros': chatpoint_to_micros(15)},
                {'request_id': 'batch-b', 'model_id': 'model-b', 'amount_micros': chatpoint_to_micros(15)},
            ],
            now=NOW + 1,
            db=db_session,
        )

    unchanged = await UserSubscriptions.get_by_user_id('batch-user', db=db_session)
    assert unchanged.plan_balance_micros == chatpoint_to_micros(25)

    reservations = await reserve_chatpoint_batch(
        'batch-user',
        [
            {'request_id': 'batch-a', 'model_id': 'model-a', 'amount_micros': chatpoint_to_micros(10)},
            {'request_id': 'batch-b', 'model_id': 'model-b', 'amount_micros': chatpoint_to_micros(10)},
        ],
        now=NOW + 2,
        db=db_session,
    )
    remaining = await UserSubscriptions.get_by_user_id('batch-user', db=db_session)

    assert [item.reservation.status for item in reservations] == ['active', 'active']
    assert all(item.acquired for item in reservations)
    assert sum(item.reservation.reserved_micros for item in reservations) == chatpoint_to_micros(20)
    assert remaining.plan_balance_micros == chatpoint_to_micros(5)


@pytest.mark.asyncio
async def test_fanout_batch_resize_reconciles_all_holds_atomically(db_session):
    await set_balances(db_session, 'resize-user', plan=30)
    grants = await reserve_chatpoint_batch(
        'resize-user',
        [
            {'request_id': 'resize-a', 'model_id': 'model-a', 'amount_micros': chatpoint_to_micros(10)},
            {'request_id': 'resize-b', 'model_id': 'model-b', 'amount_micros': chatpoint_to_micros(10)},
        ],
        now=NOW + 1,
        db=db_session,
    )

    resized = await resize_chatpoint_reservation_batch(
        'resize-user',
        [
            {
                'reservation_id': grants[0].reservation.id,
                'request_id': 'resize-a',
                'model_id': 'model-a',
                'amount_micros': chatpoint_to_micros(4),
            },
            {
                'reservation_id': grants[1].reservation.id,
                'request_id': 'resize-b',
                'model_id': 'model-b',
                'amount_micros': chatpoint_to_micros(8),
            },
        ],
        now=NOW + 2,
        db=db_session,
    )

    assert [item.reserved_micros for item in resized] == [chatpoint_to_micros(4), chatpoint_to_micros(8)]
    remaining = await UserSubscriptions.get_by_user_id('resize-user', db=db_session)
    assert remaining.plan_balance_micros == chatpoint_to_micros(18)


@pytest.mark.asyncio
async def test_fanout_batch_resize_failure_preserves_every_original_hold(db_session):
    await set_balances(db_session, 'resize-fail-user', plan=25)
    grants = await reserve_chatpoint_batch(
        'resize-fail-user',
        [
            {'request_id': 'resize-fail-a', 'model_id': 'model-a', 'amount_micros': chatpoint_to_micros(10)},
            {'request_id': 'resize-fail-b', 'model_id': 'model-b', 'amount_micros': chatpoint_to_micros(10)},
        ],
        now=NOW + 1,
        db=db_session,
    )

    with pytest.raises(Exception, match='CHATPOINT_RESERVATION_INSUFFICIENT'):
        await resize_chatpoint_reservation_batch(
            'resize-fail-user',
            [
                {
                    'reservation_id': grants[0].reservation.id,
                    'request_id': 'resize-fail-a',
                    'model_id': 'model-a',
                    'amount_micros': chatpoint_to_micros(20),
                },
                {
                    'reservation_id': grants[1].reservation.id,
                    'request_id': 'resize-fail-b',
                    'model_id': 'model-b',
                    'amount_micros': chatpoint_to_micros(20),
                },
            ],
            now=NOW + 2,
            db=db_session,
        )

    unchanged = [
        await SubscriptionReservations.get_by_id(grant.reservation.id, db=db_session) for grant in grants
    ]
    assert [item.reserved_micros for item in unchanged] == [chatpoint_to_micros(10), chatpoint_to_micros(10)]
    remaining = await UserSubscriptions.get_by_user_id('resize-fail-user', db=db_session)
    assert remaining.plan_balance_micros == chatpoint_to_micros(5)
    assert remaining.check_balance_micros == 0


@pytest.mark.asyncio
async def test_fanout_batch_resize_rolls_back_after_partial_update_failure(db_session, monkeypatch):
    await set_balances(db_session, 'resize-rollback-user', plan=25)
    grants = await reserve_chatpoint_batch(
        'resize-rollback-user',
        [
            {'request_id': 'rollback-a', 'model_id': 'model-a', 'amount_micros': chatpoint_to_micros(10)},
            {'request_id': 'rollback-b', 'model_id': 'model-b', 'amount_micros': chatpoint_to_micros(10)},
        ],
        now=NOW + 1,
        db=db_session,
    )
    original_update_state = SubscriptionReservations.update_state
    update_count = 0

    async def fail_second_update(*args, **kwargs):
        nonlocal update_count
        update_count += 1
        if update_count == 2:
            raise RuntimeError('injected second reservation update failure')
        return await original_update_state(*args, **kwargs)

    monkeypatch.setattr(SubscriptionReservations, 'update_state', fail_second_update)

    with pytest.raises(RuntimeError, match='injected second reservation update failure'):
        await resize_chatpoint_reservation_batch(
            'resize-rollback-user',
            [
                {
                    'reservation_id': grants[0].reservation.id,
                    'request_id': 'rollback-a',
                    'model_id': 'model-a',
                    'amount_micros': chatpoint_to_micros(4),
                },
                {
                    'reservation_id': grants[1].reservation.id,
                    'request_id': 'rollback-b',
                    'model_id': 'model-b',
                    'amount_micros': chatpoint_to_micros(8),
                },
            ],
            now=NOW + 2,
            db=db_session,
        )

    unchanged = [
        await SubscriptionReservations.get_by_id(grant.reservation.id, db=db_session) for grant in grants
    ]
    assert [item.reserved_micros for item in unchanged] == [chatpoint_to_micros(10), chatpoint_to_micros(10)]
    remaining = await UserSubscriptions.get_by_user_id('resize-rollback-user', db=db_session)
    assert remaining.plan_balance_micros == chatpoint_to_micros(5)
    assert remaining.check_balance_micros == 0


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_oversubscribe_balance(db_session):
    await set_balances(db_session, 'concurrent-reservation-user', plan=25)
    Session = async_sessionmaker(db_session.bind, expire_on_commit=False)
    request_count = 12
    barrier = asyncio.Barrier(request_count)

    async def reserve_once(index: int):
        await barrier.wait()
        async with Session() as session:
            try:
                return await reserve_chatpoints(
                    'concurrent-reservation-user',
                    request_id=f'concurrent-reservation-{index}',
                    model_id='metered-model',
                    amount_micros=chatpoint_to_micros(10),
                    now=NOW + 1,
                    db=session,
                )
            except ChatpointReservationInsufficientError:
                return None

    results = await asyncio.gather(*(reserve_once(index) for index in range(request_count)))
    successful = [item for item in results if item is not None and item.acquired]
    db_session.expire_all()
    subscription = await UserSubscriptions.get_by_user_id('concurrent-reservation-user', db=db_session)

    assert len(successful) == 2
    assert sum(item.reservation.reserved_micros for item in successful) == chatpoint_to_micros(20)
    assert subscription.plan_balance_micros == chatpoint_to_micros(5)
    assert subscription.check_balance_micros == 0


@pytest.mark.asyncio
async def test_concurrent_reservation_retry_is_idempotent(db_session):
    await set_balances(db_session, 'reservation-retry-user', plan=25)
    Session = async_sessionmaker(db_session.bind, expire_on_commit=False)
    barrier = asyncio.Barrier(2)

    async def reserve_once():
        await barrier.wait()
        async with Session() as session:
            return await reserve_chatpoints(
                'reservation-retry-user',
                request_id='same-request',
                model_id='same-model',
                amount_micros=chatpoint_to_micros(10),
                now=NOW + 1,
                db=session,
            )

    first, second = await asyncio.gather(reserve_once(), reserve_once())
    db_session.expire_all()
    subscription = await UserSubscriptions.get_by_user_id('reservation-retry-user', db=db_session)

    assert first.reservation.id == second.reservation.id
    assert sorted([first.acquired, second.acquired]) == [False, True]
    assert subscription.plan_balance_micros == chatpoint_to_micros(15)


@pytest.mark.asyncio
async def test_settlement_refunds_unused_hold_and_billing_links_reservation(db_session):
    await set_balances(db_session, 'settlement-user', plan=5, check=10)
    reservation = (
        await reserve_chatpoints(
            'settlement-user',
            request_id='settlement-request',
            model_id='settlement-model',
            amount_micros=chatpoint_to_micros(10),
            now=NOW + 1,
            db=db_session,
        )
    ).reservation

    usage = await bill_model_usage(
        user_id='settlement-user',
        model_id='settlement-model',
        quota_mode='metered',
        usage_multiplier='1',
        pricing={
            'input_chatpoint_per_million': '100',
            'output_chatpoint_per_million': '0',
            'cache_creation_chatpoint_per_million': '0',
            'cache_read_chatpoint_per_million': '0',
        },
        usage={'input_tokens': 60_000},
        metadata={},
        is_admin=False,
        request_id='settlement-request',
        reservation_id=reservation.id,
        now=NOW + 2,
        db=db_session,
    )
    subscription = await UserSubscriptions.get_by_user_id('settlement-user', db=db_session)

    assert usage.status == 'billed'
    assert usage.reservation_id == reservation.id
    assert usage.cost_micros == chatpoint_to_micros(6)
    assert usage.plan_cost_micros == chatpoint_to_micros(5)
    assert usage.check_cost_micros == chatpoint_to_micros(1)
    assert usage.unpaid_cost_micros == 0
    assert subscription.plan_balance_micros == 0
    assert subscription.check_balance_micros == chatpoint_to_micros(9)


@pytest.mark.asyncio
async def test_overage_requires_explicit_partial_settlement(db_session):
    await set_balances(db_session, 'overage-user', plan=10)
    reservation = (
        await reserve_chatpoints(
            'overage-user',
            request_id='overage-request',
            model_id='overage-model',
            amount_micros=chatpoint_to_micros(8),
            now=NOW + 1,
            db=db_session,
        )
    ).reservation

    with pytest.raises(ChatpointReservationInsufficientError):
        await settle_chatpoint_reservation(
            reservation.id,
            actual_cost_micros=chatpoint_to_micros(15),
            now=NOW + 2,
            db=db_session,
        )

    unchanged = await UserSubscriptions.get_by_user_id('overage-user', db=db_session)
    assert unchanged.plan_balance_micros == chatpoint_to_micros(2)

    settled = await settle_chatpoint_reservation(
        reservation.id,
        actual_cost_micros=chatpoint_to_micros(15),
        allow_partial=True,
        now=NOW + 3,
        db=db_session,
    )
    exhausted = await UserSubscriptions.get_by_user_id('overage-user', db=db_session)

    assert settled.status == 'partially_settled'
    assert settled.settled_plan_micros == chatpoint_to_micros(10)
    assert settled.unpaid_cost_micros == chatpoint_to_micros(5)
    assert exhausted.plan_balance_micros == 0
    assert exhausted.check_balance_micros == 0


@pytest.mark.asyncio
async def test_high_concurrency_fallback_billing_never_creates_negative_balance(db_session):
    await set_balances(db_session, 'fallback-user', plan=25)
    Session = async_sessionmaker(db_session.bind, expire_on_commit=False)
    request_count = 12
    barrier = asyncio.Barrier(request_count)

    async def bill_once(index: int):
        await barrier.wait()
        async with Session() as session:
            return await bill_model_usage(
                user_id='fallback-user',
                model_id='metered-model',
                quota_mode='metered',
                usage_multiplier='1',
                pricing={
                    'input_chatpoint_per_million': '100',
                    'output_chatpoint_per_million': '0',
                    'cache_creation_chatpoint_per_million': '0',
                    'cache_read_chatpoint_per_million': '0',
                },
                usage={'input_tokens': 100_000},
                metadata={},
                is_admin=False,
                request_id=f'fallback-{index}',
                now=NOW + 1,
                db=session,
            )

    usages = await asyncio.gather(*(bill_once(index) for index in range(request_count)))
    db_session.expire_all()
    subscription = await UserSubscriptions.get_by_user_id('fallback-user', db=db_session)

    assert sum(item.plan_cost_micros + item.check_cost_micros for item in usages) == chatpoint_to_micros(25)
    assert sum(item.unpaid_cost_micros for item in usages) == chatpoint_to_micros(95)
    assert any(item.status == 'partially_billed' for item in usages)
    assert subscription.plan_balance_micros == 0
    assert subscription.check_balance_micros == 0


@pytest.mark.asyncio
async def test_each_provider_call_can_atomically_extend_one_reservation(db_session):
    await set_balances(db_session, 'extension-user', plan=30)
    reservation = (
        await reserve_chatpoints(
            'extension-user',
            request_id='extension-request',
            model_id='extension-model',
            amount_micros=chatpoint_to_micros(10),
            expires_at=NOW + 100,
            now=NOW,
            db=db_session,
        )
    ).reservation

    extended = await extend_chatpoint_reservation(
        reservation.id,
        user_id='extension-user',
        request_id='extension-request',
        model_id='extension-model',
        amount_micros=chatpoint_to_micros(8),
        expires_at=NOW + 200,
        now=NOW + 1,
        db=db_session,
    )
    subscription = await UserSubscriptions.get_by_user_id('extension-user', db=db_session)

    assert extended.reserved_micros == chatpoint_to_micros(18)
    assert extended.expires_at == NOW + 200
    assert extended.metadata['provider_call_count'] == 2
    assert subscription.plan_balance_micros == chatpoint_to_micros(12)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'provider_usage',
    [
        None,
        {'provider_latency_ms': 25},
        {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
    ],
)
async def test_missing_or_unusable_usage_can_fail_closed_to_the_reserved_amount(
    db_session,
    provider_usage,
):
    await set_balances(db_session, 'fallback-reservation-user', plan=25)
    reservation = (
        await reserve_chatpoints(
            'fallback-reservation-user',
            request_id='fallback-reservation-request',
            model_id='fallback-reservation-model',
            amount_micros=chatpoint_to_micros(10),
            now=NOW,
            db=db_session,
        )
    ).reservation

    usage = await bill_model_usage(
        user_id='fallback-reservation-user',
        model_id='fallback-reservation-model',
        quota_mode='metered',
        usage_multiplier='1',
        usage=provider_usage,
        metadata={},
        is_admin=False,
        request_id='fallback-reservation-request',
        reservation_id=reservation.id,
        charge_reserved_on_missing_usage=True,
        now=NOW + 1,
        db=db_session,
    )
    subscription = await UserSubscriptions.get_by_user_id('fallback-reservation-user', db=db_session)

    assert usage.status == 'reserved_fallback'
    assert usage.cost_micros == chatpoint_to_micros(10)
    assert subscription.plan_balance_micros == chatpoint_to_micros(15)


@pytest.mark.asyncio
async def test_reservation_billing_identity_supports_same_request_across_models(db_session):
    await set_balances(db_session, 'multi-billing-user', plan=30)
    grants = await reserve_chatpoint_batch(
        'multi-billing-user',
        [
            {'request_id': 'shared-request', 'model_id': 'model-a', 'amount_micros': chatpoint_to_micros(5)},
            {'request_id': 'shared-request', 'model_id': 'model-b', 'amount_micros': chatpoint_to_micros(5)},
        ],
        now=NOW,
        db=db_session,
    )

    usages = []
    for grant in grants:
        usages.append(
            await bill_model_usage(
                user_id='multi-billing-user',
                model_id=grant.reservation.model_id,
                quota_mode='metered',
                usage_multiplier='1',
                pricing={'input_chatpoint_per_million': '100'},
                usage={'input_tokens': 50_000},
                metadata={},
                is_admin=False,
                request_id='shared-request',
                reservation_id=grant.reservation.id,
                now=NOW + 1,
                db=db_session,
            )
        )

    assert len({usage.idempotency_key for usage in usages}) == 2
    assert {usage.reservation_id for usage in usages} == {grant.reservation.id for grant in grants}


@pytest.mark.asyncio
async def test_renewed_reservation_cannot_be_released_as_expired(db_session):
    await set_balances(db_session, 'lease-user', plan=20)
    reservation = (
        await reserve_chatpoints(
            'lease-user',
            request_id='lease-request',
            model_id='lease-model',
            amount_micros=chatpoint_to_micros(5),
            expires_at=NOW + 5,
            now=NOW,
            db=db_session,
        )
    ).reservation
    await renew_chatpoint_reservation(
        reservation.id,
        expires_at=NOW + 100,
        now=NOW + 4,
        db=db_session,
    )

    with pytest.raises(ChatpointReservationConflictError, match='NOT_EXPIRED'):
        await release_chatpoint_reservation(
            reservation.id,
            expired=True,
            now=NOW + 6,
            db=db_session,
        )

    subscription = await UserSubscriptions.get_by_user_id('lease-user', db=db_session)
    assert subscription.plan_balance_micros == chatpoint_to_micros(15)


@pytest.mark.asyncio
async def test_cross_period_extension_never_consumes_the_new_plan_balance(db_session):
    await set_balances(db_session, 'cross-period-user', plan=20, check=10)
    subscription = await UserSubscriptions.get_by_user_id('cross-period-user', db=db_session)
    reservation = (
        await reserve_chatpoints(
            'cross-period-user',
            request_id='cross-period-request',
            model_id='cross-period-model',
            amount_micros=chatpoint_to_micros(5),
            expires_at=subscription.period_end_at + 100,
            now=NOW,
            db=db_session,
        )
    ).reservation

    await extend_chatpoint_reservation(
        reservation.id,
        user_id='cross-period-user',
        request_id='cross-period-request',
        model_id='cross-period-model',
        amount_micros=chatpoint_to_micros(5),
        expires_at=subscription.period_end_at + 200,
        now=subscription.period_end_at + 1,
        db=db_session,
    )
    renewed_period = await UserSubscriptions.get_by_user_id('cross-period-user', db=db_session)
    plan_after_extension = renewed_period.plan_balance_micros

    await release_chatpoint_reservation(
        reservation.id,
        reason='cross-period test',
        now=subscription.period_end_at + 2,
        db=db_session,
    )
    released = await UserSubscriptions.get_by_user_id('cross-period-user', db=db_session)

    assert plan_after_extension == renewed_period.plan_chatpoint_allowance_micros
    assert released.plan_balance_micros == plan_after_extension
    assert released.check_balance_micros == chatpoint_to_micros(10)


@pytest.mark.asyncio
async def test_terminal_release_respects_commit_false(db_session, monkeypatch):
    await set_balances(db_session, 'terminal-release-user', plan=20)
    reservation = (
        await reserve_chatpoints(
            'terminal-release-user',
            request_id='terminal-release-request',
            model_id='terminal-release-model',
            amount_micros=chatpoint_to_micros(5),
            now=NOW,
            db=db_session,
        )
    ).reservation
    await release_chatpoint_reservation(reservation.id, now=NOW + 1, db=db_session)

    commit = AsyncMock()
    monkeypatch.setattr(db_session, 'commit', commit)
    released = await release_chatpoint_reservation(
        reservation.id,
        now=NOW + 2,
        commit=False,
        db=db_session,
    )

    assert released.status == 'released'
    commit.assert_not_awaited()
    await db_session.rollback()
