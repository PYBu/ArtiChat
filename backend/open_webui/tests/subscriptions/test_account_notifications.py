from types import SimpleNamespace

import pytest

from open_webui.routers import emails
from open_webui.utils import account_notifications


@pytest.mark.asyncio
async def test_notification_failure_never_escapes_to_committed_business_action(monkeypatch):
    user = SimpleNamespace(email='alice@example.com', name='Alice')
    monkeypatch.setattr(
        emails,
        'load_smtp_settings',
        lambda: async_value({'enabled': True, 'sender_name': 'ArtiChat'}),
    )

    async def fail_delivery(**kwargs):
        raise RuntimeError('smtp unavailable')

    monkeypatch.setattr(account_notifications, 'deliver_email', fail_delivery)
    assert not await account_notifications.notify_user(
        'password_changed',
        user,
        {'changed_at': 'now'},
    )


@pytest.mark.asyncio
async def test_subscription_notification_respects_admin_switch(monkeypatch):
    sent = []
    user = SimpleNamespace(email='alice@example.com', name='Alice')
    monkeypatch.setattr(
        emails,
        'load_smtp_settings',
        lambda: async_value({'enabled': True, 'subscription_notifications': False}),
    )
    monkeypatch.setattr(account_notifications, 'deliver_email', lambda **kwargs: sent.append(kwargs))

    assert not await account_notifications.notify_user(
        'subscription_changed',
        user,
        {'subscription_name': 'Plus', 'expires_at': 'later'},
        subscription_notification=True,
    )
    assert sent == []


async def async_value(value):
    return value
