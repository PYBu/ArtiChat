import smtplib
import ssl

import pytest

from open_webui.utils.email_delivery import (
    RenderedEmail,
    SMTPStageError,
    check_smtp_connection,
    normalize_smtp_settings,
    send_smtp_message,
)


class FakeSMTP:
    def __init__(self, *, fail_at=None):
        self.fail_at = fail_at
        self.events = []
        self.sent_message = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append('quit')

    def ehlo(self):
        self.events.append('ehlo')

    def starttls(self, *, context):
        self.events.append('starttls')
        if self.fail_at == 'tls':
            raise ssl.SSLError('certificate failed')

    def login(self, username, password):
        self.events.append(('login', username, password))
        if self.fail_at == 'auth':
            raise smtplib.SMTPAuthenticationError(535, b'bad credentials')

    def send_message(self, message):
        self.events.append('send')
        self.sent_message = message
        if self.fail_at == 'send':
            raise smtplib.SMTPException('mailbox unavailable')


def smtp_settings(security='starttls'):
    return normalize_smtp_settings(
        {
            'enabled': True,
            'host': 'smtp.example.com',
            'port': 465 if security == 'ssl' else 587,
            'username': 'mailer@example.com',
            'password': 'mail-password',
            'security': security,
            'sender_email': 'mailer@example.com',
            'sender_name': 'ArtiChat',
            'reply_to': 'support@example.com',
        },
        secret_key='primary-secret',
    )


@pytest.mark.parametrize(
    ('security', 'uses_ssl', 'uses_starttls'),
    [('none', False, False), ('starttls', False, True), ('ssl', True, False)],
)
def test_connection_check_uses_the_selected_security_mode(security, uses_ssl, uses_starttls):
    transport = FakeSMTP()
    factory_calls = []

    def smtp_factory(host, port, *, timeout):
        factory_calls.append(('smtp', host, port, timeout))
        return transport

    def smtp_ssl_factory(host, port, *, timeout, context):
        factory_calls.append(('ssl', host, port, timeout, context is not None))
        return transport

    result = check_smtp_connection(
        smtp_settings(security),
        secret_key='primary-secret',
        smtp_factory=smtp_factory,
        smtp_ssl_factory=smtp_ssl_factory,
    )

    assert result == {'ok': True, 'stage': 'complete'}
    assert factory_calls[0][0] == ('ssl' if uses_ssl else 'smtp')
    assert ('starttls' in transport.events) is uses_starttls
    assert ('login', 'mailer@example.com', 'mail-password') in transport.events


@pytest.mark.parametrize(
    ('failure_stage', 'expected_stage', 'expected_code'),
    [
        ('connect', 'connect', 'SMTP_CONNECTION_FAILED'),
        ('tls', 'tls', 'SMTP_TLS_FAILED'),
        ('auth', 'auth', 'SMTP_AUTH_FAILED'),
    ],
)
def test_connection_check_reports_safe_stage_errors(failure_stage, expected_stage, expected_code):
    transport = FakeSMTP(fail_at=failure_stage)

    def smtp_factory(host, port, *, timeout):
        if failure_stage == 'connect':
            raise OSError('smtp.example.com: mail-password was rejected')
        return transport

    with pytest.raises(SMTPStageError) as exc_info:
        check_smtp_connection(
            smtp_settings(),
            secret_key='primary-secret',
            smtp_factory=smtp_factory,
        )

    assert exc_info.value.stage == expected_stage
    assert str(exc_info.value) == expected_code
    assert 'mail-password' not in str(exc_info.value)


def test_smtp_send_builds_multipart_message_and_reports_send_stage():
    rendered = RenderedEmail(
        subject='ArtiChat test',
        html_body='<p>Delivery works.</p>',
        text_body='Delivery works.',
    )
    transport = FakeSMTP()

    send_smtp_message(
        recipient='admin@example.com',
        rendered=rendered,
        settings=smtp_settings(),
        secret_key='primary-secret',
        smtp_factory=lambda host, port, *, timeout: transport,
    )

    message = transport.sent_message
    assert message['To'] == 'admin@example.com'
    assert message['From'] == 'ArtiChat <mailer@example.com>'
    assert message['Reply-To'] == 'support@example.com'
    assert message.is_multipart()

    failed_transport = FakeSMTP(fail_at='send')
    with pytest.raises(SMTPStageError) as exc_info:
        send_smtp_message(
            recipient='admin@example.com',
            rendered=rendered,
            settings=smtp_settings(),
            secret_key='primary-secret',
            smtp_factory=lambda host, port, *, timeout: failed_transport,
        )
    assert exc_info.value.stage == 'send'
    assert str(exc_info.value) == 'SMTP_SEND_FAILED'
