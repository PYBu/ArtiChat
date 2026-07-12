import pytest

from open_webui.utils.email_security import create_email_challenge, verify_email_challenge


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
