from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import re
import smtplib
import ssl
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlparse

import markdown
from cryptography.fernet import Fernet, InvalidToken
from open_webui.env import DATA_DIR, VERSION
from open_webui.models.email_security import (
    EmailDeliveries,
    EmailDeliveryModel,
    EmailTemplates,
)
from sqlalchemy.ext.asyncio import AsyncSession


SMTP_SECURITY_MODES = {'none', 'starttls', 'ssl'}
PASSWORD_MASK = '********'
TEMPLATE_VARIABLE = re.compile(r'{{\s*([a-z][a-z0-9_]*)\s*}}')
SENSITIVE_DELIVERY_VARIABLES = {'code', 'reset_url'}
EMAIL_LOGO_CID = 'artichat-platform-logo'

ALLOWED_EMAIL_HTML_TAGS = {
    'a',
    'b',
    'br',
    'code',
    'div',
    'em',
    'h1',
    'h2',
    'h3',
    'hr',
    'i',
    'li',
    'ol',
    'p',
    'pre',
    'span',
    'strong',
    'table',
    'tbody',
    'td',
    'th',
    'thead',
    'tr',
    'u',
    'ul',
}
BLOCKED_EMAIL_HTML_TAGS = {'script', 'style', 'iframe', 'object', 'embed', 'form', 'svg', 'math'}
VOID_EMAIL_HTML_TAGS = {'br', 'hr'}
ALLOWED_EMAIL_STYLE_PROPERTIES = {
    'background',
    'background-color',
    'border',
    'border-bottom',
    'border-color',
    'border-left',
    'border-radius',
    'border-right',
    'border-top',
    'color',
    'display',
    'font-family',
    'font-size',
    'font-style',
    'font-weight',
    'line-height',
    'margin',
    'margin-bottom',
    'margin-left',
    'margin-right',
    'margin-top',
    'max-width',
    'padding',
    'padding-bottom',
    'padding-left',
    'padding-right',
    'padding-top',
    'text-align',
    'text-decoration',
    'vertical-align',
    'white-space',
    'width',
}

COMMON_TEMPLATE_VARIABLES = {'platform_name', 'platform_url', 'platform_version', 'user_name'}
EMAIL_TEMPLATE_VARIABLES = {
    'registration_code': COMMON_TEMPLATE_VARIABLES | {'code', 'expires_minutes'},
    'login_code': COMMON_TEMPLATE_VARIABLES | {'code', 'expires_minutes'},
    'sensitive_action_code': COMMON_TEMPLATE_VARIABLES | {'code', 'expires_minutes', 'action_name'},
    'password_reset': COMMON_TEMPLATE_VARIABLES | {'reset_url', 'expires_minutes'},
    'password_changed': COMMON_TEMPLATE_VARIABLES | {'changed_at'},
    'email_changed': COMMON_TEMPLATE_VARIABLES | {'old_email', 'new_email', 'changed_at'},
    'billing_address_changed': COMMON_TEMPLATE_VARIABLES | {'changed_at'},
    'subscription_changed': COMMON_TEMPLATE_VARIABLES | {'subscription_name', 'expires_at'},
    'smtp_test': COMMON_TEMPLATE_VARIABLES | {'tested_at'},
}

DEFAULT_EMAIL_TEMPLATES: dict[str, dict[str, Any]] = {
    'registration_code': {
        'subject': '{{platform_name}} 注册验证码',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">验证你的邮箱</h1>'
            '<p style="margin:0 0 18px;line-height:1.7;color:#3f3f46;">你好 <strong>{{user_name}}</strong>，请输入以下验证码完成注册。</p>'
            '<div style="margin:0 0 18px;padding:20px;text-align:center;background-color:#f4f4f5;border:1px solid #e4e4e7;border-radius:8px;">'
            '<div style="margin-bottom:8px;font-size:12px;color:#71717a;">注册验证码</div>'
            '<div style="font-size:32px;font-weight:700;color:#18181b;">{{code}}</div></div>'
            '<p style="margin:0;font-size:13px;line-height:1.7;color:#71717a;">验证码将在 {{expires_minutes}} 分钟后失效。若非本人操作，请忽略此邮件。</p>'
        ),
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的注册验证码是：**{{code}}**\n\n'
            '验证码将在 {{expires_minutes}} 分钟后失效。若非本人操作，请忽略此邮件。'
        ),
        'is_enabled': True,
    },
    'login_code': {
        'subject': '{{platform_name}} 登录验证码',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">登录验证</h1>'
            '<p style="margin:0 0 18px;line-height:1.7;color:#3f3f46;">你好 <strong>{{user_name}}</strong>，请输入以下验证码登录 {{platform_name}}。</p>'
            '<div style="margin:0 0 18px;padding:20px;text-align:center;background-color:#f4f4f5;border:1px solid #e4e4e7;border-radius:8px;">'
            '<div style="margin-bottom:8px;font-size:12px;color:#71717a;">登录验证码</div>'
            '<div style="font-size:32px;font-weight:700;color:#18181b;">{{code}}</div></div>'
            '<p style="margin:0;font-size:13px;line-height:1.7;color:#71717a;">验证码将在 {{expires_minutes}} 分钟后失效。请勿将验证码转发给他人。</p>'
        ),
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的登录验证码是：**{{code}}**\n\n'
            '验证码将在 {{expires_minutes}} 分钟后失效。请勿将验证码转发给他人。'
        ),
        'is_enabled': True,
    },
    'sensitive_action_code': {
        'subject': '{{platform_name}} 安全验证',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">确认敏感操作</h1>'
            '<p style="margin:0 0 18px;line-height:1.7;color:#3f3f46;">你好 <strong>{{user_name}}</strong>，你正在进行“{{action_name}}”。</p>'
            '<div style="margin:0 0 18px;padding:20px;text-align:center;background-color:#f4f4f5;border:1px solid #e4e4e7;border-radius:8px;">'
            '<div style="margin-bottom:8px;font-size:12px;color:#71717a;">安全验证码</div>'
            '<div style="font-size:32px;font-weight:700;color:#18181b;">{{code}}</div></div>'
            '<p style="margin:0;font-size:13px;line-height:1.7;color:#71717a;">验证码将在 {{expires_minutes}} 分钟后失效。若非本人操作，请立即检查账户安全。</p>'
        ),
        'markdown_body': (
            '你好 {{user_name}}，\n\n你正在进行“{{action_name}}”，验证码是：**{{code}}**\n\n'
            '验证码将在 {{expires_minutes}} 分钟后失效。若非本人操作，请立即检查账户安全。'
        ),
        'is_enabled': True,
    },
    'password_reset': {
        'subject': '重置你的 {{platform_name}} 密码',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">重置密码</h1>'
            '<p style="margin:0 0 20px;line-height:1.7;color:#3f3f46;">你好 <strong>{{user_name}}</strong>，点击下方按钮重置你的登录密码。</p>'
            '<p style="margin:0 0 20px;"><a href="{{reset_url}}" style="display:inline-block;padding:12px 20px;background-color:#18181b;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:700;">重置密码</a></p>'
            '<p style="margin:0;font-size:13px;line-height:1.7;color:#71717a;">链接将在 {{expires_minutes}} 分钟后失效，且只能使用一次。若非本人操作，请忽略此邮件。</p>'
        ),
        'markdown_body': (
            '你好 {{user_name}}，\n\n请点击下面的链接重置密码：\n\n'
            '[重置密码]({{reset_url}})\n\n链接将在 {{expires_minutes}} 分钟后失效，且只能使用一次。'
        ),
        'is_enabled': True,
    },
    'password_changed': {
        'subject': '{{platform_name}} 密码已修改',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">密码已修改</h1>'
            '<p style="margin:0 0 14px;line-height:1.7;color:#3f3f46;">你好 <strong>{{user_name}}</strong>，你的账户密码已于 {{changed_at}} 修改。</p>'
            '<p style="margin:0;font-size:13px;line-height:1.7;color:#71717a;">若非本人操作，请立即重置密码并联系管理员。</p>'
        ),
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的账户密码已于 {{changed_at}} 修改。'
            '若非本人操作，请立即重置密码并联系管理员。'
        ),
        'is_enabled': True,
    },
    'email_changed': {
        'subject': '{{platform_name}} 登录邮箱已修改',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">登录邮箱已修改</h1>'
            '<p style="margin:0 0 14px;line-height:1.7;color:#3f3f46;">你好 <strong>{{user_name}}</strong>，你的登录邮箱已于 {{changed_at}} 从 <strong>{{old_email}}</strong> 修改为 <strong>{{new_email}}</strong>。</p>'
            '<p style="margin:0;font-size:13px;line-height:1.7;color:#71717a;">若非本人操作，请立即联系管理员。</p>'
        ),
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的登录邮箱已于 {{changed_at}} 从 {{old_email}} 修改为 {{new_email}}。'
            '若非本人操作，请立即联系管理员。'
        ),
        'is_enabled': True,
    },
    'billing_address_changed': {
        'subject': '{{platform_name}} 付款信息已修改',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">付款信息已修改</h1>'
            '<p style="margin:0 0 14px;line-height:1.7;color:#3f3f46;">你好 <strong>{{user_name}}</strong>，你的付款信息已于 {{changed_at}} 修改。</p>'
            '<p style="margin:0;font-size:13px;line-height:1.7;color:#71717a;">若非本人操作，请立即检查账户安全。</p>'
        ),
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的付款信息已于 {{changed_at}} 修改。'
            '若非本人操作，请立即检查账户安全。'
        ),
        'is_enabled': True,
    },
    'subscription_changed': {
        'subject': '{{platform_name}} 订阅状态更新',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">订阅状态已更新</h1>'
            '<p style="margin:0 0 18px;line-height:1.7;color:#3f3f46;">你好 <strong>{{user_name}}</strong>，你的订阅已更新。</p>'
            '<table style="width:100%;margin:0 0 18px;border:1px solid #e4e4e7;border-radius:8px;" cellspacing="0" cellpadding="0">'
            '<tr><td style="padding:12px;color:#71717a;">当前订阅</td><td style="padding:12px;text-align:right;font-weight:700;color:#18181b;">{{subscription_name}}</td></tr>'
            '<tr><td style="padding:12px;border-top:1px solid #e4e4e7;color:#71717a;">有效期至</td><td style="padding:12px;border-top:1px solid #e4e4e7;text-align:right;color:#18181b;">{{expires_at}}</td></tr></table>'
            '<p style="margin:0;line-height:1.7;color:#3f3f46;">你可以登录 {{platform_name}} 查看订阅与用量详情。</p>'
        ),
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的订阅已更新为 **{{subscription_name}}**，有效期至 {{expires_at}}。\n\n'
            '你可以登录 {{platform_name}} 查看订阅与用量详情。'
        ),
        'is_enabled': True,
    },
    'smtp_test': {
        'subject': '{{platform_name}} 邮件测试成功',
        'html_body': (
            '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#18181b;">SMTP 配置成功</h1>'
            '<p style="margin:0 0 18px;line-height:1.7;color:#3f3f46;">这是一封来自 {{platform_name}} 的 HTML 测试邮件。</p>'
            '<div style="margin:0 0 18px;padding:16px;background-color:#f4f4f5;border:1px solid #e4e4e7;border-radius:8px;">'
            '<div style="font-size:12px;color:#71717a;">发送时间</div><div style="margin-top:6px;color:#18181b;">{{tested_at}}</div></div>'
            '<p style="margin:0;font-size:13px;line-height:1.7;color:#71717a;">收到此邮件表示当前发信配置可以正常投递 HTML 邮件。</p>'
        ),
        'markdown_body': (
            '这是一封来自 {{platform_name}} 的 SMTP 测试邮件。\n\n发送时间：{{tested_at}}\n\n'
            '收到此邮件表示当前发信配置可以正常投递。'
        ),
        'is_enabled': True,
    },
}


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html_body: str
    text_body: str


class SMTPStageError(RuntimeError):
    def __init__(self, stage: str, code: str):
        super().__init__(code)
        self.stage = stage
        self.code = code


def _smtp_fernet(secret_key: str) -> Fernet:
    if not secret_key:
        raise ValueError('SMTP_SECRET_KEY_REQUIRED')
    digest = hashlib.sha256(f'artichat:smtp:{secret_key}'.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_smtp_password(password: str, *, secret_key: str) -> str:
    return _smtp_fernet(secret_key).encrypt(password.encode('utf-8')).decode('ascii')


def decrypt_smtp_password(encrypted_password: str, *, secret_key: str) -> str:
    try:
        return _smtp_fernet(secret_key).decrypt(encrypted_password.encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise ValueError('SMTP_PASSWORD_DECRYPT_FAILED') from exc


def normalize_smtp_settings(
    data: dict[str, Any],
    *,
    secret_key: str,
    current_encrypted_password: str | None = None,
) -> dict[str, Any]:
    security = str(data.get('security') or 'starttls').strip().lower()
    if security not in SMTP_SECURITY_MODES:
        raise ValueError('SMTP_SECURITY_INVALID')

    try:
        port = int(data.get('port') or 587)
    except (TypeError, ValueError) as exc:
        raise ValueError('SMTP_PORT_INVALID') from exc
    if port < 1 or port > 65535:
        raise ValueError('SMTP_PORT_INVALID')

    enabled = bool(data.get('enabled', False))
    host = str(data.get('host') or '').strip()
    sender_email = str(data.get('sender_email') or '').strip().lower()
    if enabled and not host:
        raise ValueError('SMTP_HOST_REQUIRED')
    if enabled and not sender_email:
        raise ValueError('SMTP_SENDER_EMAIL_REQUIRED')

    password = str(data.get('password') or '')
    encrypted_password = current_encrypted_password or str(data.get('password_encrypted') or '')
    if password and password != PASSWORD_MASK:
        encrypted_password = encrypt_smtp_password(password, secret_key=secret_key)

    return {
        'enabled': enabled,
        'host': host,
        'port': port,
        'username': str(data.get('username') or '').strip(),
        'password_encrypted': encrypted_password,
        'security': security,
        'sender_email': sender_email,
        'sender_name': str(data.get('sender_name') or 'ArtiChat').strip() or 'ArtiChat',
        'reply_to': str(data.get('reply_to') or '').strip().lower(),
        'public_url': str(data.get('public_url') or '').strip().rstrip('/'),
        'subscription_notifications': bool(data.get('subscription_notifications', True)),
    }


def smtp_admin_settings(settings: dict[str, Any]) -> dict[str, Any]:
    encrypted_password = str(settings.get('password_encrypted') or '')
    public_keys = {
        'enabled',
        'host',
        'port',
        'username',
        'security',
        'sender_email',
        'sender_name',
        'reply_to',
        'public_url',
        'subscription_notifications',
    }
    response = {key: settings.get(key) for key in public_keys}
    response['password'] = PASSWORD_MASK if encrypted_password else ''
    response['password_configured'] = bool(encrypted_password)
    return response


def _email_logo_bytes() -> bytes | None:
    candidates = (
        Path(DATA_DIR) / 'platform-assets' / 'logo-light.png',
        Path(__file__).resolve().parents[1] / 'static' / 'favicon.png',
    )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.read_bytes()
        except OSError:
            continue
    return None


def email_logo_data_uri() -> str:
    logo = _email_logo_bytes()
    if not logo:
        return ''
    return f'data:image/png;base64,{base64.b64encode(logo).decode("ascii")}'


@contextmanager
def _smtp_client(
    settings: dict[str, Any],
    *,
    secret_key: str,
    smtp_factory: Callable[..., Any],
    smtp_ssl_factory: Callable[..., Any],
    timeout: float,
) -> Iterator[Any]:
    security = str(settings.get('security') or 'starttls')
    try:
        if security == 'ssl':
            transport = smtp_ssl_factory(
                settings['host'],
                int(settings['port']),
                timeout=timeout,
                context=ssl.create_default_context(),
            )
        else:
            transport = smtp_factory(settings['host'], int(settings['port']), timeout=timeout)
    except Exception as exc:
        raise SMTPStageError('connect', 'SMTP_CONNECTION_FAILED') from exc

    try:
        with transport as client:
            if security == 'starttls':
                try:
                    client.ehlo()
                    client.starttls(context=ssl.create_default_context())
                    client.ehlo()
                except Exception as exc:
                    raise SMTPStageError('tls', 'SMTP_TLS_FAILED') from exc

            username = str(settings.get('username') or '')
            if username:
                try:
                    encrypted_password = str(settings.get('password_encrypted') or '')
                    password = decrypt_smtp_password(encrypted_password, secret_key=secret_key)
                    client.login(username, password)
                except SMTPStageError:
                    raise
                except Exception as exc:
                    raise SMTPStageError('auth', 'SMTP_AUTH_FAILED') from exc
            yield client
    except SMTPStageError:
        raise
    except Exception as exc:
        raise SMTPStageError('connect', 'SMTP_CONNECTION_FAILED') from exc


def check_smtp_connection(
    settings: dict[str, Any],
    *,
    secret_key: str,
    smtp_factory: Callable[..., Any] = smtplib.SMTP,
    smtp_ssl_factory: Callable[..., Any] = smtplib.SMTP_SSL,
    timeout: float = 10,
) -> dict[str, Any]:
    with _smtp_client(
        settings,
        secret_key=secret_key,
        smtp_factory=smtp_factory,
        smtp_ssl_factory=smtp_ssl_factory,
        timeout=timeout,
    ):
        return {'ok': True, 'stage': 'complete'}


def send_smtp_message(
    *,
    recipient: str,
    rendered: RenderedEmail,
    settings: dict[str, Any],
    secret_key: str,
    smtp_factory: Callable[..., Any] = smtplib.SMTP,
    smtp_ssl_factory: Callable[..., Any] = smtplib.SMTP_SSL,
    timeout: float = 10,
) -> None:
    message = EmailMessage()
    message['Subject'] = rendered.subject
    message['From'] = formataddr(
        (str(settings.get('sender_name') or 'ArtiChat'), str(settings.get('sender_email') or ''))
    )
    message['To'] = recipient
    reply_to = str(settings.get('reply_to') or '')
    if reply_to:
        message['Reply-To'] = reply_to
    message.set_content(rendered.text_body)
    message.add_alternative(rendered.html_body, subtype='html')
    logo = _email_logo_bytes()
    if logo:
        html_part = message.get_payload()[-1]
        html_part.add_related(
            logo,
            maintype='image',
            subtype='png',
            cid=f'<{EMAIL_LOGO_CID}>',
            filename='platform-logo.png',
            disposition='inline',
        )

    with _smtp_client(
        settings,
        secret_key=secret_key,
        smtp_factory=smtp_factory,
        smtp_ssl_factory=smtp_ssl_factory,
        timeout=timeout,
    ) as client:
        try:
            client.send_message(message)
        except Exception as exc:
            raise SMTPStageError('send', 'SMTP_SEND_FAILED') from exc


def _stored_delivery_variables(variables: dict[str, Any]) -> dict[str, Any]:
    return {
        key: '[redacted]' if key in SENSITIVE_DELIVERY_VARIABLES else value
        for key, value in variables.items()
    }


async def _attempt_delivery(
    delivery: EmailDeliveryModel,
    *,
    settings: dict[str, Any],
    secret_key: str,
    send_func: Callable[..., None],
    now: int | None,
    db: AsyncSession | None,
    rendered_override: RenderedEmail | None = None,
) -> EmailDeliveryModel:
    delivery = await EmailDeliveries.start_attempt(delivery.id, now=now, db=db)
    rendered = rendered_override or RenderedEmail(
        subject=delivery.subject,
        html_body=delivery.html_body,
        text_body=delivery.text_body,
    )
    try:
        await asyncio.to_thread(
            send_func,
            recipient=delivery.recipient,
            rendered=rendered,
            settings=settings,
            secret_key=secret_key,
        )
    except SMTPStageError as exc:
        return await EmailDeliveries.mark_failed(delivery.id, error=exc.code, db=db)
    except Exception:
        return await EmailDeliveries.mark_failed(delivery.id, error='EMAIL_DELIVERY_FAILED', db=db)
    return await EmailDeliveries.mark_sent(delivery.id, now=now, db=db)


async def deliver_email(
    *,
    template_key: str,
    recipient: str,
    variables: dict[str, Any],
    settings: dict[str, Any],
    secret_key: str,
    send_func: Callable[..., None] = send_smtp_message,
    now: int | None = None,
    db: AsyncSession | None = None,
) -> EmailDeliveryModel:
    if not settings.get('enabled'):
        raise ValueError('EMAIL_DELIVERY_DISABLED')
    await EmailTemplates.seed_defaults(DEFAULT_EMAIL_TEMPLATES, now=now, db=db)
    template = await EmailTemplates.get(template_key, db=db)
    if template is None:
        raise ValueError('EMAIL_TEMPLATE_NOT_FOUND')
    if not template.is_enabled:
        raise ValueError('EMAIL_TEMPLATE_DISABLED')

    render_variables = dict(variables)
    render_variables['platform_name'] = (
        settings.get('_platform_name') or render_variables.get('platform_name') or 'ArtiChat'
    )
    render_variables['platform_url'] = (
        settings.get('public_url') or render_variables.get('platform_url') or ''
    )
    render_variables['platform_version'] = VERSION
    rendered = render_email_template(
        template_key=template.key,
        subject=template.subject,
        markdown_body=template.markdown_body,
        html_body=template.html_body,
        variables=render_variables,
    )
    stored_variables = _stored_delivery_variables(render_variables)
    stored_rendered = render_email_template(
        template_key=template.key,
        subject=template.subject,
        markdown_body=template.markdown_body,
        html_body=template.html_body,
        variables=stored_variables,
    )
    delivery = await EmailDeliveries.create(
        template_key=template.key,
        recipient=recipient,
        subject=stored_rendered.subject,
        html_body=stored_rendered.html_body,
        text_body=stored_rendered.text_body,
        variables=stored_variables,
        now=now,
        db=db,
    )
    return await _attempt_delivery(
        delivery,
        settings=settings,
        secret_key=secret_key,
        send_func=send_func,
        now=now,
        db=db,
        rendered_override=rendered,
    )


async def retry_email_delivery(
    delivery_id: str,
    *,
    settings: dict[str, Any],
    secret_key: str,
    send_func: Callable[..., None] = send_smtp_message,
    now: int | None = None,
    db: AsyncSession | None = None,
) -> EmailDeliveryModel:
    delivery = await EmailDeliveries.get(delivery_id, db=db)
    if delivery is None:
        raise ValueError('EMAIL_DELIVERY_NOT_FOUND')
    if delivery.status != 'failed':
        raise ValueError('EMAIL_DELIVERY_NOT_RETRYABLE')
    if delivery.template_key in {'registration_code', 'login_code', 'sensitive_action_code', 'password_reset'}:
        raise ValueError('EMAIL_DELIVERY_NOT_RETRYABLE')
    return await _attempt_delivery(
        delivery,
        settings=settings,
        secret_key=secret_key,
        send_func=send_func,
        now=now,
        db=db,
    )


def _replace_template_variables(template: str, variables: dict[str, str]) -> str:
    return TEMPLATE_VARIABLE.sub(lambda match: variables[match.group(1)], template)


def _sanitize_email_style(value: str) -> str:
    declarations: list[str] = []
    for raw_declaration in value.split(';'):
        property_name, separator, property_value = raw_declaration.partition(':')
        property_name = property_name.strip().lower()
        property_value = property_value.strip()
        if not separator or property_name not in ALLOWED_EMAIL_STYLE_PROPERTIES or not property_value:
            continue
        lowered = property_value.lower()
        if any(
            token in lowered
            for token in ('url(', 'expression', '@import', 'javascript:', 'behavior:', '-moz-binding')
        ):
            continue
        if any(character in property_value for character in ('<', '>', '`')):
            continue
        declarations.append(f'{property_name}:{property_value}')
    return ';'.join(declarations)


def _sanitize_email_href(value: str) -> str:
    stripped = value.strip()
    if TEMPLATE_VARIABLE.fullmatch(stripped):
        return stripped
    parsed = urlparse(stripped)
    if parsed.scheme.lower() in {'http', 'https', 'mailto'}:
        return stripped
    return ''


class _EmailHTMLSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.blocked_depth = 0

    def _safe_attributes(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        rendered: list[str] = []
        for raw_name, raw_value in attrs:
            name = raw_name.lower()
            value = raw_value or ''
            if name.startswith('on'):
                continue
            if name == 'style':
                value = _sanitize_email_style(value)
                if not value:
                    continue
            elif name == 'title':
                pass
            elif tag == 'a' and name == 'href':
                value = _sanitize_email_href(value)
                if not value:
                    continue
            elif tag == 'a' and name == 'target':
                if value not in {'_blank', '_self'}:
                    continue
            elif tag == 'a' and name == 'rel':
                value = 'noopener noreferrer'
            elif tag == 'table' and name in {'width', 'cellpadding', 'cellspacing'}:
                if not re.fullmatch(r'[0-9]{1,4}%?', value):
                    continue
            elif tag == 'table' and name == 'role':
                if value != 'presentation':
                    continue
            elif tag in {'td', 'th'} and name in {'width', 'colspan', 'rowspan'}:
                if not re.fullmatch(r'[0-9]{1,4}%?', value):
                    continue
            elif tag in {'td', 'th'} and name in {'align', 'valign'}:
                if value.lower() not in {'left', 'center', 'right', 'top', 'middle', 'bottom'}:
                    continue
            else:
                continue
            rendered.append(f' {name}="{html.escape(value, quote=True)}"')
        if tag == 'a' and 'target="_blank"' in ''.join(rendered) and not any(
            attribute.startswith(' rel=') for attribute in rendered
        ):
            rendered.append(' rel="noopener noreferrer"')
        return ''.join(rendered)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in BLOCKED_EMAIL_HTML_TAGS:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag not in ALLOWED_EMAIL_HTML_TAGS:
            return
        self.parts.append(f'<{tag}{self._safe_attributes(tag, attrs)}>')

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in BLOCKED_EMAIL_HTML_TAGS and self.blocked_depth:
            self.blocked_depth -= 1
            return
        if self.blocked_depth or tag not in ALLOWED_EMAIL_HTML_TAGS or tag in VOID_EMAIL_HTML_TAGS:
            return
        self.parts.append(f'</{tag}>')

    def handle_data(self, data: str) -> None:
        if not self.blocked_depth:
            self.parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self.blocked_depth:
            self.parts.append(f'&{name};')

    def handle_charref(self, name: str) -> None:
        if not self.blocked_depth:
            self.parts.append(f'&#{name};')

    def html(self) -> str:
        return ''.join(self.parts).strip()


def sanitize_email_html(value: str) -> str:
    parser = _EmailHTMLSanitizer()
    parser.feed(value)
    parser.close()
    return parser.html()


def email_template_content_html(*, html_body: str | None, markdown_body: str | None) -> str:
    if html_body is not None:
        return sanitize_email_html(html_body)
    return sanitize_email_html(markdown.markdown(markdown_body or '', extensions=['extra']))


def validate_email_template(
    *,
    template_key: str,
    subject: str,
    markdown_body: str | None = None,
    html_body: str | None = None,
) -> list[str]:
    allowed = EMAIL_TEMPLATE_VARIABLES.get(template_key)
    if allowed is None:
        raise ValueError('EMAIL_TEMPLATE_NOT_FOUND')

    body = html_body if html_body is not None else markdown_body
    if body is None or not body.strip():
        raise ValueError('EMAIL_TEMPLATE_BODY_REQUIRED')
    tokens = set(TEMPLATE_VARIABLE.findall(subject)) | set(TEMPLATE_VARIABLE.findall(body))
    unsupported = sorted(tokens - allowed)
    if unsupported:
        raise ValueError(f'EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED: {unsupported[0]}')

    remaining = TEMPLATE_VARIABLE.sub('', f'{subject}\n{body}')
    if '{{' in remaining or '}}' in remaining:
        raise ValueError('EMAIL_TEMPLATE_VARIABLE_INVALID')
    return sorted(tokens)


class _PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.link_targets: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'br':
            self.parts.append('\n')
        elif tag == 'a':
            self.link_targets.append(dict(attrs).get('href') or '')

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self.link_targets:
            target = self.link_targets.pop()
            if target:
                self.parts.append(f' ({target})')
        if tag in {'p', 'div', 'h1', 'h2', 'h3', 'li', 'tr'}:
            self.parts.append('\n')

    def text(self) -> str:
        lines = [' '.join(line.split()) for line in ''.join(self.parts).splitlines()]
        return '\n'.join(line for line in lines if line).strip()


def render_email_template(
    *,
    template_key: str,
    subject: str,
    markdown_body: str | None = None,
    html_body: str | None = None,
    variables: dict[str, Any],
    logo_src: str = f'cid:{EMAIL_LOGO_CID}',
) -> RenderedEmail:
    tokens = set(
        validate_email_template(
            template_key=template_key,
            subject=subject,
            markdown_body=markdown_body,
            html_body=html_body,
        )
    )
    missing = sorted(token for token in tokens if token not in variables)
    if missing:
        raise ValueError(f'EMAIL_TEMPLATE_VARIABLE_REQUIRED: {missing[0]}')

    subject_values = {key: str(value) for key, value in variables.items()}
    rendered_subject = _replace_template_variables(subject, subject_values).strip()
    if not rendered_subject or '\r' in rendered_subject or '\n' in rendered_subject:
        raise ValueError('EMAIL_SUBJECT_INVALID')

    html_values = {key: html.escape(str(value), quote=True) for key, value in variables.items()}
    if html_body is not None:
        content_template = email_template_content_html(html_body=html_body, markdown_body=None)
        content_html = _replace_template_variables(content_template, html_values)
    else:
        rendered_markdown = _replace_template_variables(markdown_body or '', html_values)
        content_html = email_template_content_html(html_body=None, markdown_body=rendered_markdown)
    platform_name = html.escape(str(variables.get('platform_name') or 'ArtiChat'), quote=True)
    platform_version = html.escape(str(variables.get('platform_version') or VERSION), quote=True)
    raw_platform_url = str(variables.get('platform_url') or '').strip()
    platform_url = _sanitize_email_href(raw_platform_url)
    escaped_logo_src = html.escape(logo_src, quote=True)
    logo_content = (
        f'<img src="{escaped_logo_src}" width="40" height="40" alt="{platform_name}" '
        'style="display:block;width:40px;height:40px;border-radius:8px;">'
    )
    name_content = platform_name
    if platform_url:
        escaped_platform_url = html.escape(platform_url, quote=True)
        logo_content = f'<a href="{escaped_platform_url}" style="text-decoration:none;">{logo_content}</a>'
        name_content = (
            f'<a href="{escaped_platform_url}" style="color:#18181b;text-decoration:none;">'
            f'{platform_name}</a>'
        )
    html_body = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f4f4f5;color:#18181b;font-family:Arial,Helvetica,sans-serif;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="width:100%;background:#f4f4f5;">'
        '<tr><td align="center" style="padding:32px 16px;">'
        '<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;">'
        '<tr><td style="padding:0 4px 18px;">'
        '<table role="presentation" cellspacing="0" cellpadding="0"><tr>'
        f'<td width="40" style="width:40px;vertical-align:middle;">{logo_content}</td>'
        f'<td style="padding-left:12px;vertical-align:middle;font-size:20px;font-weight:700;color:#18181b;">{name_content}</td>'
        '</tr></table></td></tr>'
        '<tr><td style="padding:28px;background:#ffffff;border:1px solid #e4e4e7;border-radius:8px;">'
        f'{content_html}</td></tr>'
        '<tr><td align="center" style="padding:18px 12px 0;color:#71717a;font-size:12px;line-height:1.6;">'
        f'{platform_name} v{platform_version}<br>此邮件由 {platform_name} 自动发送。</td></tr>'
        '</table></td></tr></table></body></html>'
    )

    parser = _PlainTextParser()
    parser.feed(content_html)
    text_body = f'{parser.text()}\n\n{platform_name} v{platform_version}'.strip()
    return RenderedEmail(subject=rendered_subject, html_body=html_body, text_body=text_body)
