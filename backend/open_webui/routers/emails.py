from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from open_webui.env import WEBUI_SECRET_KEY
from open_webui.internal.db import get_async_session
from open_webui.models.config import Config
from open_webui.models.email_security import EmailDeliveries, EmailTemplates
from open_webui.utils.email_delivery import (
    DEFAULT_EMAIL_TEMPLATES,
    EMAIL_TEMPLATE_VARIABLES,
    SMTPStageError,
    check_smtp_connection,
    deliver_email,
    normalize_smtp_settings,
    retry_email_delivery,
    smtp_admin_settings,
    validate_email_template,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()
bearer_security = HTTPBearer(auto_error=False)


async def get_email_current_user(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    auth_token: HTTPAuthorizationCredentials = Depends(bearer_security),
):
    from open_webui.utils.auth import get_current_user

    return await get_current_user(request, response, background_tasks, auth_token)


def get_email_admin_user(user=Depends(get_email_current_user)):
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='ACCESS_PROHIBITED')
    return user

SMTP_CONFIG_KEYS = {
    'enabled': 'email.enabled',
    'host': 'email.smtp.host',
    'port': 'email.smtp.port',
    'username': 'email.smtp.username',
    'password_encrypted': 'email.smtp.password_encrypted',
    'security': 'email.smtp.security',
    'sender_email': 'email.sender_email',
    'sender_name': 'email.sender_name',
    'reply_to': 'email.reply_to',
    'public_url': 'email.public_url',
    'subscription_notifications': 'email.subscription_notifications',
}
SMTP_CONFIG_DEFAULTS = {
    SMTP_CONFIG_KEYS['enabled']: False,
    SMTP_CONFIG_KEYS['host']: '',
    SMTP_CONFIG_KEYS['port']: 587,
    SMTP_CONFIG_KEYS['username']: '',
    SMTP_CONFIG_KEYS['password_encrypted']: '',
    SMTP_CONFIG_KEYS['security']: 'starttls',
    SMTP_CONFIG_KEYS['sender_email']: '',
    SMTP_CONFIG_KEYS['sender_name']: 'ArtiChat',
    SMTP_CONFIG_KEYS['reply_to']: '',
    SMTP_CONFIG_KEYS['public_url']: '',
    SMTP_CONFIG_KEYS['subscription_notifications']: True,
}


class SMTPSettingsForm(BaseModel):
    enabled: bool = False
    host: str = ''
    port: int = 587
    username: str = ''
    password: str = ''
    security: str = 'starttls'
    sender_email: str = ''
    sender_name: str = 'ArtiChat'
    reply_to: str = ''
    public_url: str = ''
    subscription_notifications: bool = True


class TestEmailForm(BaseModel):
    recipient: str


class EmailTemplateUpdateForm(BaseModel):
    subject: str
    markdown_body: str
    is_enabled: bool = True


async def load_smtp_settings() -> dict[str, Any]:
    values = await Config.get_many(*SMTP_CONFIG_KEYS.values())
    return {
        field: values.get(storage_key, SMTP_CONFIG_DEFAULTS[storage_key])
        for field, storage_key in SMTP_CONFIG_KEYS.items()
    }


def _smtp_updates(settings: dict[str, Any]) -> dict[str, Any]:
    return {SMTP_CONFIG_KEYS[field]: value for field, value in settings.items() if field in SMTP_CONFIG_KEYS}


def _connection_test_settings(settings: dict[str, Any]) -> dict[str, Any]:
    if not settings.get('host'):
        raise ValueError('SMTP_HOST_REQUIRED')
    return {**settings, 'enabled': True}


def _template_response(template) -> dict[str, Any]:
    return {
        **template.model_dump(),
        'allowed_variables': sorted(EMAIL_TEMPLATE_VARIABLES[template.key]),
    }


def _delivery_response(delivery) -> dict[str, Any]:
    return {
        'id': delivery.id,
        'template_key': delivery.template_key,
        'recipient': delivery.recipient,
        'subject': delivery.subject,
        'status': delivery.status,
        'error': delivery.error,
        'attempts': delivery.attempts,
        'last_attempt_at': delivery.last_attempt_at,
        'sent_at': delivery.sent_at,
        'created_at': delivery.created_at,
    }


@router.get('/admin/settings')
async def get_smtp_settings(user=Depends(get_email_admin_user)):
    return smtp_admin_settings(await load_smtp_settings())


@router.put('/admin/settings')
async def update_smtp_settings(form_data: SMTPSettingsForm, user=Depends(get_email_admin_user)):
    current = await load_smtp_settings()
    try:
        normalized = normalize_smtp_settings(
            form_data.model_dump(),
            current_encrypted_password=str(current.get('password_encrypted') or ''),
            secret_key=WEBUI_SECRET_KEY,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await Config.upsert(_smtp_updates(normalized))
    return smtp_admin_settings(normalized)


@router.post('/admin/connection-test')
async def test_smtp_connection(user=Depends(get_email_admin_user)):
    try:
        settings = _connection_test_settings(await load_smtp_settings())
        return await asyncio.to_thread(check_smtp_connection, settings, secret_key=WEBUI_SECRET_KEY)
    except (ValueError, SMTPStageError) as exc:
        detail = str(exc)
        stage = exc.stage if isinstance(exc, SMTPStageError) else 'config'
        raise HTTPException(status_code=400, detail={'stage': stage, 'code': detail}) from exc


@router.post('/admin/test-email')
async def send_test_email(
    form_data: TestEmailForm,
    user=Depends(get_email_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        settings = _connection_test_settings(await load_smtp_settings())
        delivery = await deliver_email(
            template_key='smtp_test',
            recipient=form_data.recipient.strip().lower(),
            variables={
                'platform_name': settings.get('sender_name') or 'ArtiChat',
                'tested_at': datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC'),
            },
            settings=settings,
            secret_key=WEBUI_SECRET_KEY,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _delivery_response(delivery)


@router.get('/admin/templates')
async def list_email_templates(
    user=Depends(get_email_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    await EmailTemplates.seed_defaults(DEFAULT_EMAIL_TEMPLATES, db=db)
    return [_template_response(template) for template in await EmailTemplates.list_all(db=db)]


@router.put('/admin/templates/{template_key}')
async def update_email_template(
    template_key: str,
    form_data: EmailTemplateUpdateForm,
    user=Depends(get_email_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        validate_email_template(
            template_key=template_key,
            subject=form_data.subject,
            markdown_body=form_data.markdown_body,
        )
        await EmailTemplates.seed_defaults(DEFAULT_EMAIL_TEMPLATES, db=db)
        template = await EmailTemplates.update(
            template_key,
            subject=form_data.subject.strip(),
            markdown_body=form_data.markdown_body.strip(),
            is_enabled=form_data.is_enabled,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _template_response(template)


@router.get('/admin/deliveries')
async def list_email_deliveries(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_email_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    deliveries = await EmailDeliveries.list_recent(limit=limit, offset=offset, db=db)
    return [_delivery_response(delivery) for delivery in deliveries]


@router.post('/admin/deliveries/{delivery_id}/retry')
async def retry_delivery(
    delivery_id: str,
    user=Depends(get_email_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        delivery = await retry_email_delivery(
            delivery_id,
            settings=await load_smtp_settings(),
            secret_key=WEBUI_SECRET_KEY,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _delivery_response(delivery)
