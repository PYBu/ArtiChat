import pytest

from open_webui.models.email_security import EmailDeliveries, EmailTemplates
from open_webui.utils.email_delivery import (
    SMTPStageError,
    deliver_email,
    normalize_smtp_settings,
    retry_email_delivery,
)


def configured_smtp():
    return normalize_smtp_settings(
        {
            'enabled': True,
            'host': 'smtp.example.com',
            'port': 587,
            'security': 'starttls',
            'sender_email': 'mailer@example.com',
            'sender_name': 'ArtiChat',
        },
        secret_key='primary-secret',
    )


@pytest.mark.asyncio
async def test_delivery_seeds_templates_records_success_and_redacts_secrets(db_session):
    sent = []

    def sender(**kwargs):
        sent.append(kwargs)

    delivery = await deliver_email(
        template_key='registration_code',
        recipient='alice@example.com',
        variables={
            'platform_name': 'ArtiChat',
            'user_name': 'Alice',
            'code': '123456',
            'expires_minutes': 10,
        },
        settings=configured_smtp(),
        secret_key='primary-secret',
        send_func=sender,
        now=100,
        db=db_session,
    )

    assert delivery.status == 'sent'
    assert delivery.attempts == 1
    assert delivery.sent_at == 100
    assert delivery.variables['user_name'] == 'Alice'
    assert delivery.variables['code'] == '[redacted]'
    assert len(sent) == 1
    assert sent[0]['recipient'] == 'alice@example.com'
    assert '123456' in sent[0]['rendered'].text_body

    stored = await EmailDeliveries.get(delivery.id, db=db_session)
    assert stored.status == 'sent'
    assert '123456' not in stored.subject
    assert '123456' not in stored.text_body
    assert '123456' not in stored.html_body
    assert '[redacted]' in stored.text_body
    assert len(await EmailTemplates.list_all(db=db_session)) == 9


@pytest.mark.asyncio
async def test_failed_security_delivery_cannot_resend_invalidated_credentials(db_session):
    def failing_sender(**kwargs):
        raise SMTPStageError('send', 'SMTP_SEND_FAILED')

    failed = await deliver_email(
        template_key='password_reset',
        recipient='alice@example.com',
        variables={
            'platform_name': 'ArtiChat',
            'user_name': 'Alice',
            'reset_url': 'https://chat.example.com/reset?token=secret-token',
            'expires_minutes': 30,
        },
        settings=configured_smtp(),
        secret_key='primary-secret',
        send_func=failing_sender,
        now=100,
        db=db_session,
    )

    assert 'secret-token' not in failed.text_body
    assert 'secret-token' not in failed.html_body
    with pytest.raises(ValueError, match='EMAIL_DELIVERY_NOT_RETRYABLE'):
        await retry_email_delivery(
            failed.id,
            settings=configured_smtp(),
            secret_key='primary-secret',
            send_func=lambda **kwargs: None,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_failed_delivery_is_recorded_and_can_be_retried(db_session):
    def failing_sender(**kwargs):
        raise SMTPStageError('send', 'SMTP_SEND_FAILED')

    failed = await deliver_email(
        template_key='smtp_test',
        recipient='admin@example.com',
        variables={'platform_name': 'ArtiChat', 'tested_at': '2026-07-13 12:00'},
        settings=configured_smtp(),
        secret_key='primary-secret',
        send_func=failing_sender,
        now=100,
        db=db_session,
    )

    assert failed.status == 'failed'
    assert failed.error == 'SMTP_SEND_FAILED'
    assert failed.attempts == 1
    assert failed.sent_at is None

    retried = await retry_email_delivery(
        failed.id,
        settings=configured_smtp(),
        secret_key='primary-secret',
        send_func=lambda **kwargs: None,
        now=200,
        db=db_session,
    )

    assert retried.status == 'sent'
    assert retried.error is None
    assert retried.attempts == 2
    assert retried.last_attempt_at == 200
    assert retried.sent_at == 200

    with pytest.raises(ValueError, match='EMAIL_DELIVERY_NOT_RETRYABLE'):
        await retry_email_delivery(
            retried.id,
            settings=configured_smtp(),
            secret_key='primary-secret',
            send_func=lambda **kwargs: None,
            db=db_session,
        )
