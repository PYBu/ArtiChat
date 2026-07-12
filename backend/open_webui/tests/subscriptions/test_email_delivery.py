import pytest

from open_webui.utils.email_delivery import (
    DEFAULT_EMAIL_TEMPLATES,
    decrypt_smtp_password,
    encrypt_smtp_password,
    normalize_smtp_settings,
    render_email_template,
    smtp_admin_settings,
)


def test_smtp_password_is_encrypted_and_requires_the_same_secret_key():
    encrypted = encrypt_smtp_password('mail-password', secret_key='primary-secret')

    assert encrypted != 'mail-password'
    assert decrypt_smtp_password(encrypted, secret_key='primary-secret') == 'mail-password'
    with pytest.raises(ValueError, match='SMTP_PASSWORD_DECRYPT_FAILED'):
        decrypt_smtp_password(encrypted, secret_key='different-secret')


def test_smtp_settings_mask_password_and_preserve_existing_secret():
    saved = normalize_smtp_settings(
        {
            'enabled': True,
            'host': ' smtp.example.com ',
            'port': 587,
            'username': ' sender@example.com ',
            'password': 'mail-password',
            'security': 'starttls',
            'sender_email': ' sender@example.com ',
            'sender_name': ' ArtiChat ',
            'reply_to': ' support@example.com ',
            'public_url': ' https://chat.example.com/ ',
            'subscription_notifications': True,
        },
        secret_key='primary-secret',
    )

    assert saved['host'] == 'smtp.example.com'
    assert saved['public_url'] == 'https://chat.example.com'
    assert saved['password_encrypted'] != 'mail-password'
    assert normalize_smtp_settings(
        {**saved, 'password': ''},
        current_encrypted_password=saved['password_encrypted'],
        secret_key='primary-secret',
    )['password_encrypted'] == saved['password_encrypted']

    response = smtp_admin_settings(saved)
    assert response['password'] == '********'
    assert response['password_configured'] is True
    assert 'password_encrypted' not in response


@pytest.mark.parametrize('security', ['none', 'starttls', 'ssl'])
def test_smtp_settings_accept_supported_security_modes(security):
    settings = normalize_smtp_settings(
        {'host': 'smtp.example.com', 'port': 465, 'security': security},
        secret_key='primary-secret',
    )

    assert settings['security'] == security


def test_smtp_settings_reject_invalid_security_and_port():
    with pytest.raises(ValueError, match='SMTP_SECURITY_INVALID'):
        normalize_smtp_settings(
            {'host': 'smtp.example.com', 'port': 587, 'security': 'tls'},
            secret_key='primary-secret',
        )
    with pytest.raises(ValueError, match='SMTP_PORT_INVALID'):
        normalize_smtp_settings(
            {'host': 'smtp.example.com', 'port': 70000, 'security': 'ssl'},
            secret_key='primary-secret',
        )


def test_default_templates_cover_every_required_email():
    assert set(DEFAULT_EMAIL_TEMPLATES) == {
        'registration_code',
        'login_code',
        'sensitive_action_code',
        'password_reset',
        'password_changed',
        'email_changed',
        'billing_address_changed',
        'subscription_changed',
        'smtp_test',
    }


def test_template_rendering_enforces_variables_and_builds_html_and_plain_text():
    rendered = render_email_template(
        template_key='registration_code',
        subject='{{platform_name}} registration code',
        markdown_body='Hello **{{user_name}}**, your code is `{{code}}`.',
        variables={
            'platform_name': 'ArtiChat',
            'user_name': 'Alice',
            'code': '123456',
        },
    )

    assert rendered.subject == 'ArtiChat registration code'
    assert '<strong>Alice</strong>' in rendered.html_body
    assert '<code>123456</code>' in rendered.html_body
    assert 'Hello Alice, your code is 123456.' in rendered.text_body

    with pytest.raises(ValueError, match='EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED: reset_url'):
        render_email_template(
            template_key='registration_code',
            subject='Registration code',
            markdown_body='{{reset_url}}',
            variables={'reset_url': 'https://example.com/reset'},
        )


def test_template_rendering_escapes_user_values_in_html():
    rendered = render_email_template(
        template_key='registration_code',
        subject='Code for {{user_name}}',
        markdown_body='Hello {{user_name}}',
        variables={'user_name': '<script>alert(1)</script>'},
    )

    assert '<script>' not in rendered.html_body
    assert '&lt;script&gt;' in rendered.html_body


def test_password_reset_link_is_preserved_in_plain_text():
    rendered = render_email_template(
        template_key='password_reset',
        subject='Reset password',
        markdown_body='[Reset password]({{reset_url}})',
        variables={'reset_url': 'https://chat.example.com/reset?token=secret'},
    )

    assert 'https://chat.example.com/reset?token=secret' in rendered.text_body
