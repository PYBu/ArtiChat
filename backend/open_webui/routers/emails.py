from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from open_webui.env import WEBUI_SECRET_KEY
from open_webui.internal.db import get_async_session
from open_webui.models.config import Config
from open_webui.models.email_security import EmailDeliveries, EmailTemplates
from open_webui.models.auths import Auths
from open_webui.models.subscriptions import now_ts
from open_webui.models.users import Users
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
from open_webui.utils.email_security import (
    consume_password_reset_token,
    create_password_reset_token,
    create_email_challenge,
    generate_email_code,
    generate_reset_token,
    invalidate_email_challenge,
    is_registration_email_allowed,
    normalize_allowed_domains,
    validate_password_reset_token,
    verify_email_challenge,
)
from open_webui.utils.passwords import get_password_hash, validate_password
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()
bearer_security = HTTPBearer(auto_error=False)
log = logging.getLogger(__name__)


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
REGISTRATION_CONFIG_KEYS = {
    'allowed_domains': 'registration.allowed_domains',
    'allow_subdomains': 'registration.allow_subdomains',
    'verification_enabled': 'registration.verification_enabled',
    'email_code_login_enabled': 'registration.email_code_login_enabled',
    'sensitive_action_verification_enabled': 'registration.sensitive_action_verification_enabled',
}
REGISTRATION_CONFIG_DEFAULTS = {
    REGISTRATION_CONFIG_KEYS['allowed_domains']: [],
    REGISTRATION_CONFIG_KEYS['allow_subdomains']: False,
    REGISTRATION_CONFIG_KEYS['verification_enabled']: False,
    REGISTRATION_CONFIG_KEYS['email_code_login_enabled']: False,
    REGISTRATION_CONFIG_KEYS['sensitive_action_verification_enabled']: False,
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


class RegistrationSettingsForm(BaseModel):
    allowed_domains: list[str] = Field(default_factory=list)
    allow_subdomains: bool = False
    verification_enabled: bool = False
    email_code_login_enabled: bool = False
    sensitive_action_verification_enabled: bool = False


class EmailChallengeRequestForm(BaseModel):
    email: str
    purpose: str


class EmailChallengeVerifyForm(BaseModel):
    email: str
    purpose: str
    code: str


class ForgotPasswordForm(BaseModel):
    email: str


class ResetPasswordForm(BaseModel):
    token: str
    new_password: str


async def load_smtp_settings() -> dict[str, Any]:
    values = await Config.get_many(*SMTP_CONFIG_KEYS.values())
    return {
        field: values.get(storage_key, SMTP_CONFIG_DEFAULTS[storage_key])
        for field, storage_key in SMTP_CONFIG_KEYS.items()
    }


async def load_registration_settings() -> dict[str, Any]:
    values = await Config.get_many(*REGISTRATION_CONFIG_KEYS.values())
    return {
        field: values.get(storage_key, REGISTRATION_CONFIG_DEFAULTS[storage_key])
        for field, storage_key in REGISTRATION_CONFIG_KEYS.items()
    }


def _smtp_updates(settings: dict[str, Any]) -> dict[str, Any]:
    return {SMTP_CONFIG_KEYS[field]: value for field, value in settings.items() if field in SMTP_CONFIG_KEYS}


def _registration_updates(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        REGISTRATION_CONFIG_KEYS[field]: value
        for field, value in settings.items()
        if field in REGISTRATION_CONFIG_KEYS
    }


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


@router.get('/registration/public')
async def get_public_registration_settings():
    settings = await load_registration_settings()
    return {
        'verification_enabled': bool(settings['verification_enabled']),
        'email_code_login_enabled': bool(settings['email_code_login_enabled']),
    }


@router.get('/admin/registration')
async def get_registration_settings(user=Depends(get_email_admin_user)):
    return await load_registration_settings()


@router.put('/admin/registration')
async def update_registration_settings(
    form_data: RegistrationSettingsForm,
    user=Depends(get_email_admin_user),
):
    normalized = {
        **form_data.model_dump(),
        'allowed_domains': normalize_allowed_domains(form_data.allowed_domains),
    }
    await Config.upsert(_registration_updates(normalized))
    return normalized


@router.post('/challenges/request')
async def request_email_challenge(
    request: Request,
    form_data: EmailChallengeRequestForm,
    db: AsyncSession = Depends(get_async_session),
):
    purpose = form_data.purpose.strip().lower()
    if purpose not in {'registration', 'login'}:
        raise HTTPException(status_code=400, detail='EMAIL_CODE_PURPOSE_INVALID')

    email = form_data.email.strip().lower()
    registration = await load_registration_settings()
    if purpose == 'registration':
        if not registration['verification_enabled']:
            raise HTTPException(status_code=400, detail='REGISTRATION_VERIFICATION_DISABLED')
        if not is_registration_email_allowed(
            email,
            registration['allowed_domains'],
            allow_subdomains=bool(registration['allow_subdomains']),
        ):
            raise HTTPException(status_code=400, detail='REGISTRATION_EMAIL_DOMAIN_NOT_ALLOWED')
    elif not registration['email_code_login_enabled']:
        raise HTTPException(status_code=400, detail='EMAIL_CODE_LOGIN_DISABLED')

    user = await Users.get_user_by_email(email, db=db)
    if (purpose == 'registration' and user is not None) or (purpose == 'login' and user is None):
        return {'status': True}

    settings = await load_smtp_settings()
    if not settings.get('enabled'):
        return {'status': True}

    code = generate_email_code()
    timestamp = now_ts()
    try:
        challenge = await create_email_challenge(
            email=email,
            purpose=purpose,
            code=code,
            secret_key=WEBUI_SECRET_KEY,
            user_id=getattr(user, 'id', None),
            ip_address=request.client.host if request.client else None,
            now=timestamp,
            db=db,
        )
    except ValueError as exc:
        status_code = 429 if str(exc) in {
            'EMAIL_CODE_RESEND_COOLDOWN',
            'EMAIL_CODE_EMAIL_RATE_LIMIT',
            'EMAIL_CODE_IP_RATE_LIMIT',
        } else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    delivery = await deliver_email(
        template_key='registration_code' if purpose == 'registration' else 'login_code',
        recipient=email,
        variables={
            'platform_name': settings.get('sender_name') or 'ArtiChat',
            'platform_url': settings.get('public_url') or '',
            'user_name': getattr(user, 'name', None) or email.split('@', 1)[0],
            'code': code,
            'expires_minutes': 10,
        },
        settings=settings,
        secret_key=WEBUI_SECRET_KEY,
        db=db,
    )
    if delivery.status != 'sent':
        await invalidate_email_challenge(challenge.id, now=now_ts(), db=db)
    return {'status': True}


@router.post('/challenges/verify')
async def verify_challenge_code(
    form_data: EmailChallengeVerifyForm,
    db: AsyncSession = Depends(get_async_session),
):
    purpose = form_data.purpose.strip().lower()
    if purpose not in {'registration', 'login'}:
        raise HTTPException(status_code=400, detail='EMAIL_CODE_PURPOSE_INVALID')
    try:
        challenge = await verify_email_challenge(
            email=form_data.email,
            purpose=purpose,
            code=form_data.code,
            secret_key=WEBUI_SECRET_KEY,
            now=now_ts(),
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'verification_token': challenge.id}


@router.post('/password/forgot')
async def forgot_password(
    request: Request,
    form_data: ForgotPasswordForm,
    db: AsyncSession = Depends(get_async_session),
):
    email = form_data.email.strip().lower()
    raw_token: str | None = None
    try:
        user = await Users.get_user_by_email(email, db=db)
        settings = await load_smtp_settings()
        if user is None or not settings.get('enabled'):
            return {'status': True}

        raw_token = generate_reset_token()
        timestamp = now_ts()
        await create_password_reset_token(
            email=user.email,
            user_id=user.id,
            token=raw_token,
            secret_key=WEBUI_SECRET_KEY,
            ip_address=request.client.host if request.client else None,
            now=timestamp,
            db=db,
        )
        public_url = str(settings.get('public_url') or str(request.base_url)).rstrip('/')
        reset_url = f'{public_url}/auth/reset-password?{urlencode({"token": raw_token})}'
        delivery = await deliver_email(
            template_key='password_reset',
            recipient=user.email,
            variables={
                'platform_name': settings.get('sender_name') or 'ArtiChat',
                'platform_url': public_url,
                'user_name': user.name or user.email.split('@', 1)[0],
                'reset_url': reset_url,
                'expires_minutes': 30,
            },
            settings=settings,
            secret_key=WEBUI_SECRET_KEY,
            db=db,
        )
        if delivery.status != 'sent':
            await consume_password_reset_token(
                raw_token,
                secret_key=WEBUI_SECRET_KEY,
                now=now_ts(),
                db=db,
            )
    except Exception:
        if raw_token is not None:
            try:
                await consume_password_reset_token(
                    raw_token,
                    secret_key=WEBUI_SECRET_KEY,
                    now=now_ts(),
                    db=db,
                )
            except ValueError:
                pass
        log.warning('Password reset email could not be dispatched', exc_info=True)
    return {'status': True}


@router.post('/password/reset')
async def reset_password(
    request: Request,
    form_data: ResetPasswordForm,
    db: AsyncSession = Depends(get_async_session),
):
    timestamp = now_ts()
    try:
        reset_token = await validate_password_reset_token(
            form_data.token,
            secret_key=WEBUI_SECRET_KEY,
            now=timestamp,
            db=db,
        )
        validate_password(form_data.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = await Users.get_user_by_id(reset_token.user_id, db=db)
    if user is None or user.email.strip().lower() != reset_token.email:
        raise HTTPException(status_code=400, detail='PASSWORD_RESET_TOKEN_INVALID')

    await consume_password_reset_token(
        form_data.token,
        secret_key=WEBUI_SECRET_KEY,
        now=timestamp,
        db=db,
    )
    hashed_password = await get_password_hash(form_data.new_password)
    if not await Auths.update_user_password_by_id(user.id, hashed_password, db=db):
        raise HTTPException(status_code=400, detail='PASSWORD_RESET_FAILED')

    try:
        settings = await load_smtp_settings()
        if settings.get('enabled'):
            await deliver_email(
                template_key='password_changed',
                recipient=user.email,
                variables={
                    'platform_name': settings.get('sender_name') or 'ArtiChat',
                    'platform_url': settings.get('public_url') or str(request.base_url).rstrip('/'),
                    'user_name': user.name or user.email.split('@', 1)[0],
                    'changed_at': datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC'),
                },
                settings=settings,
                secret_key=WEBUI_SECRET_KEY,
                db=db,
            )
    except Exception:
        log.warning('Password changed notice could not be dispatched', exc_info=True)
    return {'status': True}


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
