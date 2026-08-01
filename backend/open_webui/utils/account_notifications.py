from __future__ import annotations

import logging
from datetime import UTC, datetime

from open_webui.env import WEBUI_SECRET_KEY
from open_webui.utils.email_delivery import deliver_email
from sqlalchemy.ext.asyncio import AsyncSession


log = logging.getLogger(__name__)


async def notify_user(
    template_key: str,
    user,
    variables: dict,
    *,
    subscription_notification: bool = False,
    db: AsyncSession | None = None,
) -> bool:
    try:
        from open_webui.routers.emails import load_smtp_settings

        settings = await load_smtp_settings()
        if not settings.get('enabled'):
            return False
        if subscription_notification and not settings.get('subscription_notifications', True):
            return False
        delivery = await deliver_email(
            template_key=template_key,
            recipient=user.email,
            variables={
                'platform_name': settings.get('sender_name') or 'ArtiChat',
                'platform_url': settings.get('public_url') or '',
                'user_name': user.name or user.email.split('@', 1)[0],
                **variables,
            },
            settings=settings,
            secret_key=WEBUI_SECRET_KEY,
            db=db,
        )
        return delivery.status == 'sent'
    except Exception:
        log.warning('Account notification could not be dispatched: %s', template_key, exc_info=True)
        return False


async def notify_subscription_changed(user, subscription, *, db: AsyncSession | None = None) -> bool:
    expires_at = subscription.expires_at or subscription.period_end_at
    expires_text = (
        datetime.fromtimestamp(expires_at, UTC).strftime('%Y-%m-%d %H:%M UTC')
        if expires_at
        else '长期有效'
    )
    return await notify_user(
        'subscription_changed',
        user,
        {
            'subscription_name': subscription.display_name or subscription.tier,
            'expires_at': expires_text,
        },
        subscription_notification=True,
        db=db,
    )
