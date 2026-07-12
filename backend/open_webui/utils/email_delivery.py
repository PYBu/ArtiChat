from __future__ import annotations

import base64
import hashlib
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

import markdown
from cryptography.fernet import Fernet, InvalidToken


SMTP_SECURITY_MODES = {'none', 'starttls', 'ssl'}
PASSWORD_MASK = '********'
TEMPLATE_VARIABLE = re.compile(r'{{\s*([a-z][a-z0-9_]*)\s*}}')

COMMON_TEMPLATE_VARIABLES = {'platform_name', 'platform_url', 'user_name'}
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
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的注册验证码是：**{{code}}**\n\n'
            '验证码将在 {{expires_minutes}} 分钟后失效。若非本人操作，请忽略此邮件。'
        ),
        'is_enabled': True,
    },
    'login_code': {
        'subject': '{{platform_name}} 登录验证码',
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的登录验证码是：**{{code}}**\n\n'
            '验证码将在 {{expires_minutes}} 分钟后失效。请勿将验证码转发给他人。'
        ),
        'is_enabled': True,
    },
    'sensitive_action_code': {
        'subject': '{{platform_name}} 安全验证',
        'markdown_body': (
            '你好 {{user_name}}，\n\n你正在进行“{{action_name}}”，验证码是：**{{code}}**\n\n'
            '验证码将在 {{expires_minutes}} 分钟后失效。若非本人操作，请立即检查账户安全。'
        ),
        'is_enabled': True,
    },
    'password_reset': {
        'subject': '重置你的 {{platform_name}} 密码',
        'markdown_body': (
            '你好 {{user_name}}，\n\n请点击下面的链接重置密码：\n\n'
            '[重置密码]({{reset_url}})\n\n链接将在 {{expires_minutes}} 分钟后失效，且只能使用一次。'
        ),
        'is_enabled': True,
    },
    'password_changed': {
        'subject': '{{platform_name}} 密码已修改',
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的账户密码已于 {{changed_at}} 修改。'
            '若非本人操作，请立即重置密码并联系管理员。'
        ),
        'is_enabled': True,
    },
    'email_changed': {
        'subject': '{{platform_name}} 登录邮箱已修改',
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的登录邮箱已于 {{changed_at}} 从 {{old_email}} 修改为 {{new_email}}。'
            '若非本人操作，请立即联系管理员。'
        ),
        'is_enabled': True,
    },
    'billing_address_changed': {
        'subject': '{{platform_name}} 付款信息已修改',
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的付款信息已于 {{changed_at}} 修改。'
            '若非本人操作，请立即检查账户安全。'
        ),
        'is_enabled': True,
    },
    'subscription_changed': {
        'subject': '{{platform_name}} 订阅状态更新',
        'markdown_body': (
            '你好 {{user_name}}，\n\n你的订阅已更新为 **{{subscription_name}}**，有效期至 {{expires_at}}。\n\n'
            '你可以登录 {{platform_name}} 查看订阅与用量详情。'
        ),
        'is_enabled': True,
    },
    'smtp_test': {
        'subject': '{{platform_name}} 邮件测试成功',
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
    return {
        key: value
        for key, value in {
            **settings,
            'password': PASSWORD_MASK if encrypted_password else '',
            'password_configured': bool(encrypted_password),
        }.items()
        if key != 'password_encrypted'
    }


def _replace_template_variables(template: str, variables: dict[str, str]) -> str:
    return TEMPLATE_VARIABLE.sub(lambda match: variables[match.group(1)], template)


class _PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'br':
            self.parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag in {'p', 'div', 'h1', 'h2', 'h3', 'li'}:
            self.parts.append('\n')

    def text(self) -> str:
        lines = [' '.join(line.split()) for line in ''.join(self.parts).splitlines()]
        return '\n'.join(line for line in lines if line).strip()


def render_email_template(
    *,
    template_key: str,
    subject: str,
    markdown_body: str,
    variables: dict[str, Any],
) -> RenderedEmail:
    allowed = EMAIL_TEMPLATE_VARIABLES.get(template_key)
    if allowed is None:
        raise ValueError('EMAIL_TEMPLATE_NOT_FOUND')

    tokens = set(TEMPLATE_VARIABLE.findall(subject)) | set(TEMPLATE_VARIABLE.findall(markdown_body))
    unsupported = sorted(tokens - allowed)
    if unsupported:
        raise ValueError(f'EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED: {unsupported[0]}')
    missing = sorted(token for token in tokens if token not in variables)
    if missing:
        raise ValueError(f'EMAIL_TEMPLATE_VARIABLE_REQUIRED: {missing[0]}')

    subject_values = {key: str(value) for key, value in variables.items()}
    rendered_subject = _replace_template_variables(subject, subject_values).strip()
    if not rendered_subject or '\r' in rendered_subject or '\n' in rendered_subject:
        raise ValueError('EMAIL_SUBJECT_INVALID')

    html_values = {key: html.escape(str(value), quote=True) for key, value in variables.items()}
    rendered_markdown = _replace_template_variables(markdown_body, html_values)
    content_html = markdown.markdown(rendered_markdown, extensions=['extra'])
    platform_name = html.escape(str(variables.get('platform_name') or 'ArtiChat'), quote=True)
    html_body = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head>'
        '<body style="margin:0;background:#f4f5f7;color:#171717;font-family:Arial,sans-serif;">'
        '<div style="max-width:640px;margin:0 auto;padding:32px 20px;">'
        f'<div style="font-size:20px;font-weight:700;margin-bottom:20px;">{platform_name}</div>'
        '<div style="background:#ffffff;border:1px solid #e5e7eb;padding:24px;">'
        f'{content_html}</div>'
        '<div style="color:#6b7280;font-size:12px;margin-top:18px;">'
        f'此邮件由 {platform_name} 自动发送。</div></div></body></html>'
    )

    parser = _PlainTextParser()
    parser.feed(content_html)
    return RenderedEmail(subject=rendered_subject, html_body=html_body, text_body=parser.text())
