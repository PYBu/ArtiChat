from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from uuid import uuid4

from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, JSON, Text, and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def get_email_security_db_context(
    db: AsyncSession | None = None,
) -> AsyncIterator[AsyncSession]:
    if db is not None:
        yield db
    else:
        async with get_async_db_context() as session:
            yield session


class EmailChallenge(Base):
    __tablename__ = 'email_challenge'
    id = Column(Text, primary_key=True)
    email = Column(Text, nullable=False, index=True)
    purpose = Column(Text, nullable=False, index=True)
    code_hash = Column(Text, nullable=False)
    user_id = Column(Text, nullable=True, index=True)
    session_id = Column(Text, nullable=True)
    ip_address = Column(Text, nullable=True)
    expires_at = Column(BigInteger, nullable=False)
    resend_available_at = Column(BigInteger, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    consumed_at = Column(BigInteger, nullable=True)
    claimed_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    __table_args__ = (Index('email_challenge_lookup_idx', 'email', 'purpose', 'created_at'),)


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_token'
    id = Column(Text, primary_key=True)
    email = Column(Text, nullable=False, index=True)
    user_id = Column(Text, nullable=False, index=True)
    token_hash = Column(Text, nullable=False, unique=True, index=True)
    expires_at = Column(BigInteger, nullable=False)
    consumed_at = Column(BigInteger, nullable=True)
    ip_address = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class EmailTemplate(Base):
    __tablename__ = 'email_template'
    key = Column(Text, primary_key=True)
    subject = Column(Text, nullable=False)
    markdown_body = Column(Text, nullable=False)
    html_body = Column(Text, nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(BigInteger, nullable=False)


class EmailDelivery(Base):
    __tablename__ = 'email_delivery'
    id = Column(Text, primary_key=True)
    template_key = Column(Text, nullable=False, index=True)
    recipient = Column(Text, nullable=False, index=True)
    subject = Column(Text, nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)
    status = Column(Text, nullable=False, index=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(BigInteger, nullable=True)
    sent_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class EmailTemplateModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    subject: str
    markdown_body: str
    html_body: str | None = None
    is_enabled: bool
    updated_at: int


class EmailChallengeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    purpose: str
    user_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    expires_at: int
    resend_available_at: int
    attempts: int
    max_attempts: int
    consumed_at: int | None = None
    claimed_at: int | None = None
    created_at: int


class PasswordResetTokenModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    user_id: str
    token_hash: str
    expires_at: int
    consumed_at: int | None = None
    ip_address: str | None = None
    created_at: int


class EmailDeliveryModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_key: str
    recipient: str
    subject: str
    html_body: str
    text_body: str
    variables: dict[str, Any] | None = None
    status: str
    error: str | None = None
    attempts: int
    last_attempt_at: int | None = None
    sent_at: int | None = None
    created_at: int


class EmailTemplatesTable:
    async def seed_defaults(
        self,
        defaults: dict[str, dict[str, Any]],
        *,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        timestamp = now if now is not None else int(time.time())
        async with get_email_security_db_context(db) as session:
            result = await session.execute(select(EmailTemplate))
            existing = {row.key: row for row in result.scalars().all()}
            changed = False
            for key, template in defaults.items():
                if key not in existing:
                    session.add(
                        EmailTemplate(
                            key=key,
                            subject=template['subject'],
                            markdown_body=template['markdown_body'],
                            html_body=template.get('html_body'),
                            is_enabled=bool(template.get('is_enabled', True)),
                            updated_at=timestamp,
                        )
                    )
                    changed = True
                    continue

                row = existing[key]
                if (
                    row.html_body is None
                    and row.markdown_body == template['markdown_body']
                ):
                    row.html_body = template.get('html_body')
                    changed = True
            if changed:
                await session.commit()

    async def list_all(self, *, db: AsyncSession | None = None) -> list[EmailTemplateModel]:
        async with get_email_security_db_context(db) as session:
            result = await session.execute(select(EmailTemplate).order_by(EmailTemplate.key.asc()))
            return [EmailTemplateModel.model_validate(row) for row in result.scalars().all()]

    async def get(self, key: str, *, db: AsyncSession | None = None) -> EmailTemplateModel | None:
        async with get_email_security_db_context(db) as session:
            row = await session.get(EmailTemplate, key)
            return EmailTemplateModel.model_validate(row) if row is not None else None

    async def update(
        self,
        key: str,
        *,
        subject: str,
        markdown_body: str | None = None,
        html_body: str | None = None,
        is_enabled: bool,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> EmailTemplateModel:
        timestamp = now if now is not None else int(time.time())
        async with get_email_security_db_context(db) as session:
            row = await session.get(EmailTemplate, key)
            if row is None:
                raise ValueError('EMAIL_TEMPLATE_NOT_FOUND')
            row.subject = subject
            if markdown_body is not None:
                row.markdown_body = markdown_body
            if html_body is not None:
                row.html_body = html_body
            row.is_enabled = is_enabled
            row.updated_at = timestamp
            await session.commit()
            await session.refresh(row)
            return EmailTemplateModel.model_validate(row)


class EmailDeliveriesTable:
    async def create(
        self,
        *,
        template_key: str,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: str,
        variables: dict[str, Any],
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> EmailDeliveryModel:
        timestamp = now if now is not None else int(time.time())
        async with get_email_security_db_context(db) as session:
            row = EmailDelivery(
                id=f'mail_{uuid4().hex}',
                template_key=template_key,
                recipient=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                variables=variables,
                status='pending',
                error=None,
                attempts=0,
                last_attempt_at=None,
                sent_at=None,
                created_at=timestamp,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return EmailDeliveryModel.model_validate(row)

    async def get(self, delivery_id: str, *, db: AsyncSession | None = None) -> EmailDeliveryModel | None:
        async with get_email_security_db_context(db) as session:
            row = await session.get(EmailDelivery, delivery_id)
            return EmailDeliveryModel.model_validate(row) if row is not None else None

    async def list_ready(
        self,
        *,
        now: int | None = None,
        limit: int = 20,
        max_attempts: int = 5,
        db: AsyncSession | None = None,
    ) -> list[EmailDeliveryModel]:
        """Return queued, retryable, or stale in-flight deliveries.

        The worker re-checks the status before attempting a row, so a process
        restart cannot strand a delivery in ``sending`` forever.
        """
        timestamp = now if now is not None else int(time.time())
        async with get_email_security_db_context(db) as session:
            result = await session.execute(
                select(EmailDelivery)
                .where(
                    or_(
                        EmailDelivery.status == 'pending',
                        EmailDelivery.status == 'failed',
                        EmailDelivery.status == 'sending',
                    ),
                    EmailDelivery.attempts < max_attempts,
                )
                .order_by(EmailDelivery.created_at.asc())
                .limit(max(1, limit * 4))
            )
            ready: list[EmailDeliveryModel] = []
            for row in result.scalars().all():
                if row.status == 'pending':
                    ready.append(EmailDeliveryModel.model_validate(row))
                    continue
                if row.last_attempt_at is None:
                    ready.append(EmailDeliveryModel.model_validate(row))
                    continue
                # Exponential backoff, capped at one minute. Stale sending
                # rows get a longer lease so an SMTP call is not duplicated
                # while the original process is still alive.
                delay = 120 if row.status == 'sending' else min(60, 2 ** max(row.attempts - 1, 0))
                if timestamp - row.last_attempt_at >= delay:
                    ready.append(EmailDeliveryModel.model_validate(row))
                if len(ready) >= limit:
                    break
            return ready

    async def list_recent(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession | None = None,
    ) -> list[EmailDeliveryModel]:
        async with get_email_security_db_context(db) as session:
            result = await session.execute(
                select(EmailDelivery).order_by(EmailDelivery.created_at.desc()).limit(limit).offset(offset)
            )
            return [EmailDeliveryModel.model_validate(row) for row in result.scalars().all()]

    async def start_attempt(
        self,
        delivery_id: str,
        *,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> EmailDeliveryModel:
        timestamp = now if now is not None else int(time.time())
        async with get_email_security_db_context(db) as session:
            row = await session.get(EmailDelivery, delivery_id)
            if row is None:
                raise ValueError('EMAIL_DELIVERY_NOT_FOUND')
            row.status = 'sending'
            row.error = None
            row.attempts += 1
            row.last_attempt_at = timestamp
            await session.commit()
            await session.refresh(row)
            return EmailDeliveryModel.model_validate(row)

    async def claim_attempt(
        self,
        delivery_id: str,
        *,
        now: int | None = None,
        stale_after: int = 120,
        db: AsyncSession | None = None,
    ) -> EmailDeliveryModel | None:
        timestamp = now if now is not None else int(time.time())
        async with get_email_security_db_context(db) as session:
            claimed = await session.execute(
                update(EmailDelivery)
                .where(
                    EmailDelivery.id == delivery_id,
                    or_(
                        EmailDelivery.status.in_(['pending', 'failed']),
                        and_(
                            EmailDelivery.status == 'sending',
                            or_(
                                EmailDelivery.last_attempt_at.is_(None),
                                EmailDelivery.last_attempt_at <= timestamp - stale_after,
                            ),
                        ),
                    ),
                )
                .values(
                    status='sending',
                    error=None,
                    attempts=EmailDelivery.attempts + 1,
                    last_attempt_at=timestamp,
                )
            )
            if claimed.rowcount != 1:
                await session.rollback()
                return None
            await session.commit()
            row = await session.get(EmailDelivery, delivery_id)
            return EmailDeliveryModel.model_validate(row) if row is not None else None

    async def mark_sent(
        self,
        delivery_id: str,
        *,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> EmailDeliveryModel:
        timestamp = now if now is not None else int(time.time())
        async with get_email_security_db_context(db) as session:
            row = await session.get(EmailDelivery, delivery_id)
            if row is None:
                raise ValueError('EMAIL_DELIVERY_NOT_FOUND')
            row.status = 'sent'
            row.error = None
            row.sent_at = timestamp
            await session.commit()
            await session.refresh(row)
            return EmailDeliveryModel.model_validate(row)

    async def mark_failed(
        self,
        delivery_id: str,
        *,
        error: str,
        db: AsyncSession | None = None,
    ) -> EmailDeliveryModel:
        async with get_email_security_db_context(db) as session:
            row = await session.get(EmailDelivery, delivery_id)
            if row is None:
                raise ValueError('EMAIL_DELIVERY_NOT_FOUND')
            row.status = 'failed'
            row.error = error
            row.sent_at = None
            await session.commit()
            await session.refresh(row)
            return EmailDeliveryModel.model_validate(row)


EmailTemplates = EmailTemplatesTable()
EmailDeliveries = EmailDeliveriesTable()
