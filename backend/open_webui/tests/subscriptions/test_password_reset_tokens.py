import pytest

from open_webui.utils.email_security import (
    consume_password_reset_token,
    create_password_reset_token,
    validate_password_reset_token,
)


@pytest.mark.asyncio
async def test_password_reset_token_expires_after_thirty_minutes_and_is_single_use(db_session):
    created = await create_password_reset_token(
        email='Alice@Example.com',
        user_id='user-1',
        token='reset-secret',
        secret_key='test-secret',
        ip_address='203.0.113.10',
        now=100,
        db=db_session,
    )

    assert created.email == 'alice@example.com'
    assert created.expires_at == 1900
    assert created.token_hash != 'reset-secret'

    valid = await validate_password_reset_token(
        'reset-secret',
        secret_key='test-secret',
        now=1899,
        db=db_session,
    )
    assert valid.user_id == 'user-1'

    consumed = await consume_password_reset_token(
        'reset-secret',
        secret_key='test-secret',
        now=300,
        db=db_session,
    )
    assert consumed.consumed_at == 300

    with pytest.raises(ValueError, match='PASSWORD_RESET_TOKEN_USED'):
        await consume_password_reset_token(
            'reset-secret',
            secret_key='test-secret',
            now=301,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_new_password_reset_token_invalidates_older_active_token(db_session):
    await create_password_reset_token(
        email='alice@example.com',
        user_id='user-1',
        token='old-secret',
        secret_key='test-secret',
        now=100,
        db=db_session,
    )
    await create_password_reset_token(
        email='alice@example.com',
        user_id='user-1',
        token='new-secret',
        secret_key='test-secret',
        now=200,
        db=db_session,
    )

    with pytest.raises(ValueError, match='PASSWORD_RESET_TOKEN_USED'):
        await validate_password_reset_token(
            'old-secret',
            secret_key='test-secret',
            now=201,
            db=db_session,
        )

    assert (
        await validate_password_reset_token(
            'new-secret',
            secret_key='test-secret',
            now=201,
            db=db_session,
        )
    ).user_id == 'user-1'


@pytest.mark.asyncio
async def test_password_reset_token_rejects_unknown_and_expired_values(db_session):
    await create_password_reset_token(
        email='alice@example.com',
        user_id='user-1',
        token='reset-secret',
        secret_key='test-secret',
        now=100,
        db=db_session,
    )

    with pytest.raises(ValueError, match='PASSWORD_RESET_TOKEN_INVALID'):
        await validate_password_reset_token(
            'wrong-secret',
            secret_key='test-secret',
            now=200,
            db=db_session,
        )

    with pytest.raises(ValueError, match='PASSWORD_RESET_TOKEN_EXPIRED'):
        await validate_password_reset_token(
            'reset-secret',
            secret_key='test-secret',
            now=1901,
            db=db_session,
        )
