import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from open_webui.models.users import User
from open_webui.utils.email_security import (
    claim_email_verification_ticket,
    claim_sensitive_action_grant,
    create_email_challenge,
    validate_email_verification_ticket,
    verify_email_challenge,
)


def test_user_table_tracks_email_verification_time():
    assert 'email_verified_at' in User.__table__.columns


@pytest.mark.asyncio
async def test_challenge_enforces_resend_cooldown_and_hourly_email_limit(db_session):
    challenge = await create_email_challenge(
        email='alice@example.com',
        purpose='registration',
        code='123456',
        secret_key='test-secret',
        ip_address='203.0.113.10',
        now=100,
        db=db_session,
    )

    assert challenge.expires_at == 700
    assert challenge.resend_available_at == 160
    assert challenge.attempts == 0

    with pytest.raises(ValueError, match='EMAIL_CODE_RESEND_COOLDOWN'):
        await create_email_challenge(
            email='alice@example.com',
            purpose='registration',
            code='234567',
            secret_key='test-secret',
            ip_address='203.0.113.10',
            now=159,
            db=db_session,
        )

    for index, timestamp in enumerate([160, 220, 280, 340], start=2):
        await create_email_challenge(
            email='alice@example.com',
            purpose='registration',
            code=f'{index:06d}',
            secret_key='test-secret',
            ip_address='203.0.113.10',
            now=timestamp,
            db=db_session,
        )

    with pytest.raises(ValueError, match='EMAIL_CODE_EMAIL_RATE_LIMIT'):
        await create_email_challenge(
            email='alice@example.com',
            purpose='registration',
            code='999999',
            secret_key='test-secret',
            ip_address='203.0.113.11',
            now=400,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_challenge_consumes_on_success_and_cannot_be_replayed(db_session):
    await create_email_challenge(
        email='alice@example.com',
        purpose='login',
        code='123456',
        secret_key='test-secret',
        now=100,
        db=db_session,
    )

    verified = await verify_email_challenge(
        email='alice@example.com',
        purpose='login',
        code='123456',
        secret_key='test-secret',
        now=200,
        db=db_session,
    )
    assert verified.consumed_at == 200

    with pytest.raises(ValueError, match='EMAIL_CODE_ALREADY_USED'):
        await verify_email_challenge(
            email='alice@example.com',
            purpose='login',
            code='123456',
            secret_key='test-secret',
            now=201,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_challenge_expires_and_locks_after_five_wrong_attempts(db_session):
    await create_email_challenge(
        email='alice@example.com',
        purpose='login',
        code='123456',
        secret_key='test-secret',
        now=100,
        db=db_session,
    )

    for attempt in range(5):
        with pytest.raises(ValueError, match='EMAIL_CODE_INVALID'):
            await verify_email_challenge(
                email='alice@example.com',
                purpose='login',
                code='000000',
                secret_key='test-secret',
                now=200 + attempt,
                db=db_session,
            )

    with pytest.raises(ValueError, match='EMAIL_CODE_ATTEMPTS_EXCEEDED'):
        await verify_email_challenge(
            email='alice@example.com',
            purpose='login',
            code='123456',
            secret_key='test-secret',
            now=210,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_consumed_ticket_is_bound_to_email_purpose_and_expiry(db_session):
    challenge = await create_email_challenge(
        email='alice@example.com',
        purpose='registration',
        code='123456',
        secret_key='test-secret',
        now=100,
        db=db_session,
    )
    await verify_email_challenge(
        email='alice@example.com',
        purpose='registration',
        code='123456',
        secret_key='test-secret',
        now=200,
        db=db_session,
    )

    ticket = await validate_email_verification_ticket(
        challenge.id,
        email='alice@example.com',
        purpose='registration',
        now=201,
        db=db_session,
    )
    assert ticket.id == challenge.id

    claimed = await claim_email_verification_ticket(
        challenge.id,
        email='alice@example.com',
        purpose='registration',
        now=202,
        db=db_session,
    )
    assert claimed.claimed_at == 202
    with pytest.raises(ValueError, match='EMAIL_VERIFICATION_TICKET_USED'):
        await claim_email_verification_ticket(
            challenge.id,
            email='alice@example.com',
            purpose='registration',
            now=203,
            db=db_session,
        )

    with pytest.raises(ValueError, match='EMAIL_VERIFICATION_TICKET_INVALID'):
        await validate_email_verification_ticket(
            challenge.id,
            email='other@example.com',
            purpose='registration',
            now=201,
            db=db_session,
        )
    with pytest.raises(ValueError, match='EMAIL_VERIFICATION_TICKET_EXPIRED'):
        await validate_email_verification_ticket(
            challenge.id,
            email='alice@example.com',
            purpose='registration',
            now=701,
            db=db_session,
        )

    await create_email_challenge(
        email='bob@example.com',
        purpose='login',
        code='654321',
        secret_key='test-secret',
        now=100,
        db=db_session,
    )
    with pytest.raises(ValueError, match='EMAIL_CODE_EXPIRED'):
        await verify_email_challenge(
            email='bob@example.com',
            purpose='login',
            code='654321',
            secret_key='test-secret',
            now=701,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_sensitive_action_grant_is_bound_to_user_session_and_action(db_session):
    challenge = await create_email_challenge(
        email='alice@example.com',
        purpose='sensitive:password',
        code='123456',
        secret_key='test-secret',
        user_id='user-1',
        session_id='session-1',
        now=100,
        db=db_session,
    )
    await verify_email_challenge(
        email='alice@example.com',
        purpose='sensitive:password',
        code='123456',
        secret_key='test-secret',
        user_id='user-1',
        session_id='session-1',
        now=200,
        db=db_session,
    )

    with pytest.raises(ValueError, match='SENSITIVE_ACTION_GRANT_INVALID'):
        await claim_sensitive_action_grant(
            challenge.id,
            action='billing_address',
            user_id='user-1',
            session_id='session-1',
            now=201,
            db=db_session,
        )
    with pytest.raises(ValueError, match='SENSITIVE_ACTION_GRANT_INVALID'):
        await claim_sensitive_action_grant(
            challenge.id,
            action='password',
            user_id='user-1',
            session_id='session-1',
            expected_email='other@example.com',
            now=201,
            db=db_session,
        )
    with pytest.raises(ValueError, match='SENSITIVE_ACTION_GRANT_INVALID'):
        await claim_sensitive_action_grant(
            challenge.id,
            action='password',
            user_id='user-1',
            session_id='session-2',
            now=201,
            db=db_session,
        )

    claimed = await claim_sensitive_action_grant(
        challenge.id,
        action='password',
        user_id='user-1',
        session_id='session-1',
        now=201,
        db=db_session,
    )
    assert claimed.claimed_at == 201
    with pytest.raises(ValueError, match='SENSITIVE_ACTION_GRANT_USED'):
        await claim_sensitive_action_grant(
            challenge.id,
            action='password',
            user_id='user-1',
            session_id='session-1',
            now=202,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_verification_ticket_allows_only_one_concurrent_claim(db_session):
    challenge = await create_email_challenge(
        email='concurrent@example.com',
        purpose='registration',
        code='123456',
        secret_key='test-secret',
        now=100,
        db=db_session,
    )
    await verify_email_challenge(
        email='concurrent@example.com',
        purpose='registration',
        code='123456',
        secret_key='test-secret',
        now=101,
        db=db_session,
    )
    Session = async_sessionmaker(db_session.bind, expire_on_commit=False)

    async def claim_once():
        async with Session() as session:
            try:
                await claim_email_verification_ticket(
                    challenge.id,
                    email='concurrent@example.com',
                    purpose='registration',
                    now=102,
                    db=session,
                )
                return 'claimed'
            except ValueError as exc:
                return str(exc)

    results = await asyncio.gather(claim_once(), claim_once())
    assert sorted(results) == ['EMAIL_VERIFICATION_TICKET_USED', 'claimed']
