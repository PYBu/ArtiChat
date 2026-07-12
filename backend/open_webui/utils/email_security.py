from __future__ import annotations

import re
import hashlib
import hmac
import secrets

from open_webui.models.email_security import (
    EmailChallenge,
    EmailChallengeModel,
    get_email_security_db_context,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


DOMAIN_LABEL = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')
EMAIL_CODE_TTL_SECONDS = 10 * 60
EMAIL_CODE_RESEND_SECONDS = 60
EMAIL_CODE_MAX_ATTEMPTS = 5
EMAIL_CODE_MAX_SENDS_PER_EMAIL_HOUR = 5
EMAIL_CODE_MAX_SENDS_PER_IP_HOUR = 20


def generate_email_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_email_secret(value: str, *, purpose: str, secret_key: str) -> str:
    payload = f'{purpose}:{value}'.encode('utf-8')
    return hmac.new(secret_key.encode('utf-8'), payload, hashlib.sha256).hexdigest()


def verify_email_secret(value: str, digest: str, *, purpose: str, secret_key: str) -> bool:
    expected = hash_email_secret(value, purpose=purpose, secret_key=secret_key)
    return hmac.compare_digest(expected, digest)


def _normalize_domain(value: str) -> str | None:
    raw = str(value or '').strip().lower().rstrip('.')
    if not raw or raw.startswith('.') or '@' in raw or any(char.isspace() for char in raw):
        return None
    try:
        domain = raw.encode('idna').decode('ascii')
    except UnicodeError:
        return None
    labels = domain.split('.')
    if len(labels) < 2 or any(not DOMAIN_LABEL.fullmatch(label) for label in labels):
        return None
    return domain


def normalize_allowed_domains(value: list[str] | str | None) -> list[str]:
    if isinstance(value, str):
        candidates = re.split(r'[,\n\r]+', value)
    else:
        candidates = value or []
    normalized = {_normalize_domain(item) for item in candidates}
    normalized.discard(None)
    return sorted(normalized)


def is_registration_email_allowed(email: str, domains: list[str] | str | None, *, allow_subdomains: bool) -> bool:
    raw = str(email or '').strip()
    if raw.count('@') != 1:
        return False
    local_part, domain_part = raw.rsplit('@', 1)
    if not local_part or any(char.isspace() for char in local_part):
        return False
    domain = _normalize_domain(domain_part)
    if domain is None:
        return False

    allowed = normalize_allowed_domains(domains)
    if not allowed:
        return True
    if domain in allowed:
        return True
    return allow_subdomains and any(domain.endswith(f'.{allowed_domain}') for allowed_domain in allowed)


async def create_email_challenge(
    *,
    email: str,
    purpose: str,
    code: str,
    secret_key: str,
    user_id: str | None = None,
    session_id: str | None = None,
    ip_address: str | None = None,
    now: int,
    db: AsyncSession | None = None,
) -> EmailChallengeModel:
    normalized_email = email.strip().lower()
    if not re.fullmatch(r'\d{6}', code):
        raise ValueError('EMAIL_CODE_INVALID')

    async with get_email_security_db_context(db) as session:
        latest_result = await session.execute(
            select(EmailChallenge)
            .where(EmailChallenge.email == normalized_email)
            .order_by(EmailChallenge.created_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        if latest is not None and now < latest.resend_available_at:
            raise ValueError('EMAIL_CODE_RESEND_COOLDOWN')

        since = now - 3600
        email_count = await session.scalar(
            select(func.count())
            .select_from(EmailChallenge)
            .where(EmailChallenge.email == normalized_email, EmailChallenge.created_at > since)
        )
        if int(email_count or 0) >= EMAIL_CODE_MAX_SENDS_PER_EMAIL_HOUR:
            raise ValueError('EMAIL_CODE_EMAIL_RATE_LIMIT')

        if ip_address:
            ip_count = await session.scalar(
                select(func.count())
                .select_from(EmailChallenge)
                .where(EmailChallenge.ip_address == ip_address, EmailChallenge.created_at > since)
            )
            if int(ip_count or 0) >= EMAIL_CODE_MAX_SENDS_PER_IP_HOUR:
                raise ValueError('EMAIL_CODE_IP_RATE_LIMIT')

        challenge = EmailChallenge(
            id=f'challenge_{secrets.token_hex(16)}',
            email=normalized_email,
            purpose=purpose,
            code_hash=hash_email_secret(code, purpose=purpose, secret_key=secret_key),
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            expires_at=now + EMAIL_CODE_TTL_SECONDS,
            resend_available_at=now + EMAIL_CODE_RESEND_SECONDS,
            attempts=0,
            max_attempts=EMAIL_CODE_MAX_ATTEMPTS,
            consumed_at=None,
            claimed_at=None,
            created_at=now,
        )
        session.add(challenge)
        await session.commit()
        await session.refresh(challenge)
        return EmailChallengeModel.model_validate(challenge)


async def verify_email_challenge(
    *,
    email: str,
    purpose: str,
    code: str,
    secret_key: str,
    session_id: str | None = None,
    now: int,
    db: AsyncSession | None = None,
) -> EmailChallengeModel:
    normalized_email = email.strip().lower()
    async with get_email_security_db_context(db) as session:
        statement = select(EmailChallenge).where(
            EmailChallenge.email == normalized_email,
            EmailChallenge.purpose == purpose,
        )
        if session_id is not None:
            statement = statement.where(EmailChallenge.session_id == session_id)
        result = await session.execute(statement.order_by(EmailChallenge.created_at.desc()).limit(1))
        challenge = result.scalar_one_or_none()
        if challenge is None:
            raise ValueError('EMAIL_CODE_INVALID')
        if challenge.consumed_at is not None:
            raise ValueError('EMAIL_CODE_ALREADY_USED')
        if now > challenge.expires_at:
            raise ValueError('EMAIL_CODE_EXPIRED')
        if challenge.attempts >= challenge.max_attempts:
            raise ValueError('EMAIL_CODE_ATTEMPTS_EXCEEDED')

        if not verify_email_secret(code, challenge.code_hash, purpose=purpose, secret_key=secret_key):
            challenge.attempts += 1
            await session.commit()
            raise ValueError('EMAIL_CODE_INVALID')

        challenge.consumed_at = now
        await session.commit()
        await session.refresh(challenge)
        return EmailChallengeModel.model_validate(challenge)


async def invalidate_email_challenge(
    challenge_id: str,
    *,
    now: int,
    db: AsyncSession | None = None,
) -> EmailChallengeModel:
    async with get_email_security_db_context(db) as session:
        challenge = await session.get(EmailChallenge, challenge_id)
        if challenge is None:
            raise ValueError('EMAIL_CHALLENGE_NOT_FOUND')
        challenge.consumed_at = now
        await session.commit()
        await session.refresh(challenge)
        return EmailChallengeModel.model_validate(challenge)


async def validate_email_verification_ticket(
    ticket_id: str,
    *,
    email: str,
    purpose: str,
    now: int,
    db: AsyncSession | None = None,
) -> EmailChallengeModel:
    async with get_email_security_db_context(db) as session:
        challenge = await session.get(EmailChallenge, ticket_id)
        if (
            challenge is None
            or challenge.email != email.strip().lower()
            or challenge.purpose != purpose
            or challenge.consumed_at is None
        ):
            raise ValueError('EMAIL_VERIFICATION_TICKET_INVALID')
        if now > challenge.expires_at:
            raise ValueError('EMAIL_VERIFICATION_TICKET_EXPIRED')
        if challenge.claimed_at is not None:
            raise ValueError('EMAIL_VERIFICATION_TICKET_USED')
        return EmailChallengeModel.model_validate(challenge)


async def claim_email_verification_ticket(
    ticket_id: str,
    *,
    email: str,
    purpose: str,
    now: int,
    db: AsyncSession | None = None,
) -> EmailChallengeModel:
    async with get_email_security_db_context(db) as session:
        challenge = await session.get(EmailChallenge, ticket_id)
        if (
            challenge is None
            or challenge.email != email.strip().lower()
            or challenge.purpose != purpose
            or challenge.consumed_at is None
        ):
            raise ValueError('EMAIL_VERIFICATION_TICKET_INVALID')
        if now > challenge.expires_at:
            raise ValueError('EMAIL_VERIFICATION_TICKET_EXPIRED')
        if challenge.claimed_at is not None:
            raise ValueError('EMAIL_VERIFICATION_TICKET_USED')
        challenge.claimed_at = now
        await session.commit()
        await session.refresh(challenge)
        return EmailChallengeModel.model_validate(challenge)
