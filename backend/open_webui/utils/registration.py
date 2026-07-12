from __future__ import annotations

from typing import Any

from open_webui.utils.email_security import (
    is_registration_email_allowed,
    validate_email_verification_ticket,
)
from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_signup_email_verified_at(
    *,
    email: str,
    has_users: bool,
    verification_token: str | None,
    registration_settings: dict[str, Any],
    now: int,
    db: AsyncSession | None = None,
) -> int | None:
    if not has_users:
        return now

    if not is_registration_email_allowed(
        email,
        registration_settings.get('allowed_domains'),
        allow_subdomains=bool(registration_settings.get('allow_subdomains')),
    ):
        raise ValueError('REGISTRATION_EMAIL_DOMAIN_NOT_ALLOWED')

    if not registration_settings.get('verification_enabled'):
        return None
    if not verification_token:
        raise ValueError('REGISTRATION_VERIFICATION_REQUIRED')

    ticket = await validate_email_verification_ticket(
        verification_token,
        email=email,
        purpose='registration',
        now=now,
        db=db,
    )
    return ticket.consumed_at
