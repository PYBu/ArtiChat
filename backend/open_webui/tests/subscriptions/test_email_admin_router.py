import pytest
from fastapi import HTTPException

from open_webui.routers import emails


def test_email_admin_router_exposes_settings_templates_and_delivery_paths():
    paths = {route.path for route in emails.router.routes}

    assert '/registration/public' in paths
    assert '/admin/registration' in paths
    assert '/admin/settings' in paths
    assert '/admin/connection-test' in paths
    assert '/admin/test-email' in paths
    assert '/admin/templates' in paths
    assert '/admin/templates/{template_key}' in paths
    assert '/admin/templates/{template_key}/preview' in paths
    assert '/admin/deliveries' in paths
    assert '/admin/deliveries/{delivery_id}/retry' in paths


@pytest.mark.asyncio
async def test_admin_settings_store_encrypted_password_and_return_only_mask(monkeypatch):
    stored = {storage_key: default for storage_key, default in emails.SMTP_CONFIG_DEFAULTS.items()}

    async def get_many(*keys):
        return {key: stored[key] for key in keys if key in stored}

    async def upsert(updates):
        stored.update(updates)

    monkeypatch.setattr(emails.Config, 'get_many', get_many)
    monkeypatch.setattr(emails.Config, 'upsert', upsert)
    monkeypatch.setattr(emails, 'WEBUI_SECRET_KEY', 'router-test-secret')

    response = await emails.update_smtp_settings(
        emails.SMTPSettingsForm(
            enabled=True,
            host='smtp.example.com',
            port=587,
            username='mailer@example.com',
            password='mail-password',
            security='starttls',
            sender_email='mailer@example.com',
            sender_name='ArtiChat',
            reply_to='support@example.com',
            public_url='https://chat.example.com',
            subscription_notifications=True,
        ),
        user=object(),
    )

    encrypted_key = emails.SMTP_CONFIG_KEYS['password_encrypted']
    assert stored[encrypted_key] != 'mail-password'
    assert response['password'] == '********'
    assert response['password_configured'] is True
    assert 'password_encrypted' not in response


@pytest.mark.asyncio
async def test_registration_settings_normalize_domains_and_public_response_hides_allowlist(monkeypatch):
    stored = {
        **{storage_key: default for storage_key, default in emails.REGISTRATION_CONFIG_DEFAULTS.items()},
        **{storage_key: default for storage_key, default in emails.SMTP_CONFIG_DEFAULTS.items()},
    }
    stored[emails.SMTP_CONFIG_KEYS['enabled']] = True

    async def get_many(*keys):
        return {key: stored[key] for key in keys if key in stored}

    async def upsert(updates):
        stored.update(updates)

    monkeypatch.setattr(emails.Config, 'get_many', get_many)
    monkeypatch.setattr(emails.Config, 'upsert', upsert)

    response = await emails.update_registration_settings(
        emails.RegistrationSettingsForm(
            allowed_domains=[' Example.com ', 'TEAM.example.com', 'example.com'],
            allow_subdomains=True,
            verification_enabled=True,
            email_code_login_enabled=True,
            sensitive_action_verification_enabled=True,
        ),
        user=object(),
    )

    assert response['allowed_domains'] == ['example.com', 'team.example.com']
    public = await emails.get_public_registration_settings()
    assert public == {
        'verification_enabled': True,
        'email_code_login_enabled': True,
    }
    assert 'allowed_domains' not in public


@pytest.mark.asyncio
async def test_disabled_email_service_disables_all_public_verification_features(monkeypatch):
    stored = {
        **{storage_key: default for storage_key, default in emails.REGISTRATION_CONFIG_DEFAULTS.items()},
        **{storage_key: default for storage_key, default in emails.SMTP_CONFIG_DEFAULTS.items()},
    }
    stored[emails.REGISTRATION_CONFIG_KEYS['verification_enabled']] = True
    stored[emails.REGISTRATION_CONFIG_KEYS['email_code_login_enabled']] = True

    async def get_many(*keys):
        return {key: stored[key] for key in keys if key in stored}

    monkeypatch.setattr(emails.Config, 'get_many', get_many)

    assert await emails.get_public_registration_settings() == {
        'verification_enabled': False,
        'email_code_login_enabled': False,
    }


@pytest.mark.asyncio
async def test_template_admin_api_seeds_defaults_and_rejects_unsupported_variables(db_session):
    templates = await emails.list_email_templates(user=object(), db=db_session)

    assert len(templates) == 9
    registration = next(item for item in templates if item['key'] == 'registration_code')
    assert 'code' in registration['allowed_variables']
    assert 'reset_url' not in registration['allowed_variables']

    with pytest.raises(HTTPException) as exc_info:
        await emails.update_email_template(
            'registration_code',
            emails.EmailTemplateUpdateForm(
                subject='Registration',
                markdown_body='{{reset_url}}',
                is_enabled=True,
            ),
            user=object(),
            db=db_session,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == 'EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED: reset_url'
