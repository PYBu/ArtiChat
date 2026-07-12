from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from open_webui.routers import emails
from open_webui.utils.email_security import create_email_challenge, verify_email_challenge


def request_from(ip_address='203.0.113.10'):
    return Request(
        {
            'type': 'http',
            'method': 'POST',
            'path': '/api/v1/emails/challenges/request',
            'headers': [],
            'client': (ip_address, 1234),
        }
    )


def registration_settings(**overrides):
    return {
        'allowed_domains': ['example.com'],
        'allow_subdomains': False,
        'verification_enabled': True,
        'email_code_login_enabled': True,
        'sensitive_action_verification_enabled': False,
        **overrides,
    }


def smtp_settings():
    return {
        'enabled': True,
        'sender_name': 'ArtiChat',
        'public_url': 'https://chat.example.com',
    }


@pytest.mark.asyncio
async def test_challenge_request_hides_account_existence(monkeypatch, db_session):
    sent = []

    async def get_user(email, db=None):
        return SimpleNamespace(name='Existing') if email == 'existing@example.com' else None

    async def deliver(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(status='sent')

    monkeypatch.setattr(emails, 'load_registration_settings', lambda: async_value(registration_settings()))
    monkeypatch.setattr(emails, 'load_smtp_settings', lambda: async_value(smtp_settings()))
    monkeypatch.setattr(emails.Users, 'get_user_by_email', get_user)
    monkeypatch.setattr(emails, 'deliver_email', deliver)

    registration = await emails.request_email_challenge(
        request_from(),
        emails.EmailChallengeRequestForm(email='existing@example.com', purpose='registration'),
        db=db_session,
    )
    login = await emails.request_email_challenge(
        request_from(),
        emails.EmailChallengeRequestForm(email='missing@example.com', purpose='login'),
        db=db_session,
    )

    assert registration == login == {'status': True}
    assert sent == []


@pytest.mark.asyncio
async def test_registration_challenge_applies_domain_rule_and_sends_code(monkeypatch, db_session):
    captured = {}

    monkeypatch.setattr(emails, 'load_registration_settings', lambda: async_value(registration_settings()))
    monkeypatch.setattr(emails, 'load_smtp_settings', lambda: async_value(smtp_settings()))
    monkeypatch.setattr(emails.Users, 'get_user_by_email', lambda email, db=None: async_value(None))

    async def deliver(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status='sent')

    monkeypatch.setattr(emails, 'deliver_email', deliver)

    with pytest.raises(HTTPException) as exc_info:
        await emails.request_email_challenge(
            request_from(),
            emails.EmailChallengeRequestForm(email='alice@other.com', purpose='registration'),
            db=db_session,
        )
    assert exc_info.value.detail == 'REGISTRATION_EMAIL_DOMAIN_NOT_ALLOWED'

    response = await emails.request_email_challenge(
        request_from(),
        emails.EmailChallengeRequestForm(email='alice@example.com', purpose='registration'),
        db=db_session,
    )
    assert response == {'status': True}
    assert captured['template_key'] == 'registration_code'
    assert 'code' in captured['variables']

    verified = await verify_email_challenge(
        email='alice@example.com',
        purpose='registration',
        code=captured['variables']['code'],
        secret_key=emails.WEBUI_SECRET_KEY,
        now=emails.now_ts(),
        db=db_session,
    )
    assert verified.consumed_at is not None


@pytest.mark.asyncio
async def test_failed_mail_invalidates_the_created_challenge(monkeypatch, db_session):
    captured = {}
    monkeypatch.setattr(emails, 'load_registration_settings', lambda: async_value(registration_settings()))
    monkeypatch.setattr(emails, 'load_smtp_settings', lambda: async_value(smtp_settings()))
    monkeypatch.setattr(emails.Users, 'get_user_by_email', lambda email, db=None: async_value(None))

    async def fail_delivery(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status='failed')

    monkeypatch.setattr(emails, 'deliver_email', fail_delivery)

    assert await emails.request_email_challenge(
        request_from(),
        emails.EmailChallengeRequestForm(email='alice@example.com', purpose='registration'),
        db=db_session,
    ) == {'status': True}

    with pytest.raises(ValueError, match='EMAIL_CODE_ALREADY_USED'):
        await verify_email_challenge(
            email='alice@example.com',
            purpose='registration',
            code=captured['variables']['code'],
            secret_key=emails.WEBUI_SECRET_KEY,
            now=emails.now_ts(),
            db=db_session,
        )


@pytest.mark.asyncio
async def test_verify_endpoint_returns_a_consumed_verification_ticket(db_session):
    timestamp = emails.now_ts()
    await create_email_challenge(
        email='alice@example.com',
        purpose='registration',
        code='123456',
        secret_key=emails.WEBUI_SECRET_KEY,
        now=timestamp,
        db=db_session,
    )

    response = await emails.verify_challenge_code(
        emails.EmailChallengeVerifyForm(
            email='alice@example.com',
            purpose='registration',
            code='123456',
        ),
        db=db_session,
    )

    assert response['verification_token'].startswith('challenge_')
    with pytest.raises(HTTPException) as exc_info:
        await emails.verify_challenge_code(
            emails.EmailChallengeVerifyForm(
                email='alice@example.com',
                purpose='registration',
                code='123456',
            ),
            db=db_session,
        )
    assert exc_info.value.detail == 'EMAIL_CODE_ALREADY_USED'


async def async_value(value):
    return value
