import pytest

from open_webui.utils.email_security import create_email_challenge, verify_email_challenge
from open_webui.utils.registration import resolve_signup_email_verified_at


def settings(**overrides):
    return {
        'allowed_domains': ['example.com'],
        'allow_subdomains': False,
        'verification_enabled': True,
        **overrides,
    }


@pytest.mark.asyncio
async def test_first_admin_bypasses_domain_and_verification(db_session):
    assert await resolve_signup_email_verified_at(
        email='admin@localhost',
        has_users=False,
        verification_token=None,
        registration_settings=settings(),
        now=100,
        db=db_session,
    ) == 100


@pytest.mark.asyncio
async def test_later_signup_enforces_domain_and_ticket(db_session):
    with pytest.raises(ValueError, match='REGISTRATION_EMAIL_DOMAIN_NOT_ALLOWED'):
        await resolve_signup_email_verified_at(
            email='alice@other.com',
            has_users=True,
            verification_token=None,
            registration_settings=settings(),
            now=100,
            db=db_session,
        )

    with pytest.raises(ValueError, match='REGISTRATION_VERIFICATION_REQUIRED'):
        await resolve_signup_email_verified_at(
            email='alice@example.com',
            has_users=True,
            verification_token=None,
            registration_settings=settings(),
            now=100,
            db=db_session,
        )

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

    assert await resolve_signup_email_verified_at(
        email='alice@example.com',
        has_users=True,
        verification_token=challenge.id,
        registration_settings=settings(),
        now=201,
        db=db_session,
    ) == 200


@pytest.mark.asyncio
async def test_signup_without_verification_keeps_unverified_state(db_session):
    assert await resolve_signup_email_verified_at(
        email='alice@example.com',
        has_users=True,
        verification_token=None,
        registration_settings=settings(verification_enabled=False),
        now=100,
        db=db_session,
    ) is None
