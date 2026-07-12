from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from open_webui.routers import emails
from open_webui.utils.email_security import validate_password_reset_token


def request_from(ip_address='203.0.113.10'):
    return Request(
        {
            'type': 'http',
            'method': 'POST',
            'path': '/api/v1/auths/password/forgot',
            'headers': [],
            'client': (ip_address, 1234),
            'scheme': 'https',
            'server': ('chat.example.com', 443),
        }
    )


def smtp_settings():
    return {
        'enabled': True,
        'sender_name': 'ArtiChat',
        'public_url': 'https://chat.example.com',
    }


@pytest.mark.asyncio
async def test_forgot_password_hides_account_existence(monkeypatch, db_session):
    sent = []
    monkeypatch.setattr(emails.Users, 'get_user_by_email', lambda email, db=None: async_value(None))
    monkeypatch.setattr(emails, 'load_smtp_settings', lambda: async_value(smtp_settings()))
    monkeypatch.setattr(emails, 'deliver_email', lambda **kwargs: sent.append(kwargs))

    response = await emails.forgot_password(
        request_from(),
        emails.ForgotPasswordForm(email='missing@example.com'),
        db=db_session,
    )

    assert response == {'status': True}
    assert sent == []


@pytest.mark.asyncio
async def test_forgot_password_sends_one_time_reset_link(monkeypatch, db_session):
    sent = []
    user = SimpleNamespace(id='user-1', email='alice@example.com', name='Alice')
    monkeypatch.setattr(emails.Users, 'get_user_by_email', lambda email, db=None: async_value(user))
    monkeypatch.setattr(emails, 'load_smtp_settings', lambda: async_value(smtp_settings()))

    async def deliver(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(status='sent')

    monkeypatch.setattr(emails, 'deliver_email', deliver)

    response = await emails.forgot_password(
        request_from(),
        emails.ForgotPasswordForm(email='Alice@Example.com'),
        db=db_session,
    )

    assert response == {'status': True}
    assert sent[0]['template_key'] == 'password_reset'
    reset_url = sent[0]['variables']['reset_url']
    assert reset_url.startswith('https://chat.example.com/auth/reset-password?token=')
    token = reset_url.split('token=', 1)[1]
    stored = await validate_password_reset_token(
        token,
        secret_key=emails.WEBUI_SECRET_KEY,
        now=emails.now_ts(),
        db=db_session,
    )
    assert stored.user_id == 'user-1'


@pytest.mark.asyncio
async def test_reset_password_consumes_token_and_changes_password(monkeypatch, db_session):
    user = SimpleNamespace(id='user-1', email='alice@example.com', name='Alice')
    await emails.create_password_reset_token(
        email=user.email,
        user_id=user.id,
        token='reset-secret',
        secret_key=emails.WEBUI_SECRET_KEY,
        now=emails.now_ts(),
        db=db_session,
    )
    updates = []
    notices = []
    monkeypatch.setattr(emails.Users, 'get_user_by_id', lambda user_id, db=None: async_value(user))
    monkeypatch.setattr(emails, 'get_password_hash', lambda password: async_value('hashed-password'), raising=False)
    monkeypatch.setattr(
        emails.Auths,
        'update_user_password_by_id',
        lambda user_id, password, db=None: append_async(updates, (user_id, password), True),
    )
    monkeypatch.setattr(emails, 'load_smtp_settings', lambda: async_value(smtp_settings()))
    monkeypatch.setattr(
        emails,
        'deliver_email',
        lambda **kwargs: append_async(notices, kwargs, SimpleNamespace(status='sent')),
        raising=False,
    )

    response = await emails.reset_password(
        request_from(),
        emails.ResetPasswordForm(token='reset-secret', new_password='Valid-password-123!'),
        db=db_session,
    )

    assert response == {'status': True}
    assert updates == [('user-1', 'hashed-password')]
    assert notices[0]['template_key'] == 'password_changed'
    with pytest.raises(ValueError, match='PASSWORD_RESET_TOKEN_USED'):
        await validate_password_reset_token(
            'reset-secret',
            secret_key=emails.WEBUI_SECRET_KEY,
            now=emails.now_ts(),
            db=db_session,
        )


@pytest.mark.asyncio
async def test_reset_password_rejects_invalid_token(monkeypatch, db_session):
    with pytest.raises(HTTPException) as exc_info:
        await emails.reset_password(
            request_from(),
            emails.ResetPasswordForm(token='wrong-secret', new_password='Valid-password-123!'),
            db=db_session,
        )
    assert exc_info.value.detail == 'PASSWORD_RESET_TOKEN_INVALID'


async def async_value(value):
    return value


async def append_async(items, value, result):
    items.append(value)
    return result
