from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError


MAX_PLATFORM_LOGO_BYTES = 2 * 1024 * 1024
PLATFORM_LOGO_CONTENT_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
PLATFORM_SIDEBAR_ICONS = {
    'link',
    'globe',
    'home',
    'document',
    'book',
    'chat',
    'star',
    'bolt',
    'calendar',
    'cube',
    'grid',
    'help',
}


def normalize_sidebar_buttons(value: Any) -> list[dict[str, str]]:
    if value in (None, ''):
        return []
    if not isinstance(value, list) or len(value) > 8:
        raise ValueError('PLATFORM_SIDEBAR_BUTTONS_INVALID')

    buttons = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError('PLATFORM_SIDEBAR_BUTTON_INVALID')
        name = str(raw.get('name') or '').strip()
        url = str(raw.get('url') or '').strip()
        icon = str(raw.get('icon') or 'link').strip().lower()
        if not name or len(name) > 40:
            raise ValueError('PLATFORM_SIDEBAR_BUTTON_NAME_INVALID')
        if len(url) > 2048:
            raise ValueError('PLATFORM_SIDEBAR_BUTTON_URL_INVALID')
        parsed = urlsplit(url)
        is_internal = url.startswith('/') and not url.startswith('//')
        is_external = parsed.scheme in {'http', 'https'} and bool(parsed.netloc)
        if not (is_internal or is_external):
            raise ValueError('PLATFORM_SIDEBAR_BUTTON_URL_INVALID')
        if icon not in PLATFORM_SIDEBAR_ICONS:
            raise ValueError('PLATFORM_SIDEBAR_BUTTON_ICON_INVALID')
        buttons.append({'name': name, 'url': url, 'icon': icon})
    return buttons


def normalize_platform_settings(data: dict) -> dict[str, Any]:
    name = str(data.get('name') or '').strip()
    if not name:
        raise ValueError('PLATFORM_NAME_REQUIRED')
    if len(name) > 100:
        raise ValueError('PLATFORM_NAME_TOO_LONG')
    return {
        'name': name,
        'about_title': str(data.get('about_title') or '').strip(),
        'about_content': str(data.get('about_content') or '').strip(),
        'sidebar_buttons': normalize_sidebar_buttons(data.get('sidebar_buttons')),
    }


def save_platform_logo(*, content: bytes, content_type: str, theme: str, assets_dir: Path) -> Path:
    if theme not in {'light', 'dark'}:
        raise ValueError('PLATFORM_LOGO_THEME_INVALID')
    if content_type not in PLATFORM_LOGO_CONTENT_TYPES:
        raise ValueError('PLATFORM_LOGO_TYPE_INVALID')
    if len(content) > MAX_PLATFORM_LOGO_BYTES:
        raise ValueError('PLATFORM_LOGO_TOO_LARGE')

    try:
        with Image.open(BytesIO(content)) as candidate:
            candidate.verify()
        with Image.open(BytesIO(content)) as source:
            image = source.convert('RGBA')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError('PLATFORM_LOGO_INVALID') from exc

    assets_dir.mkdir(parents=True, exist_ok=True)
    target = assets_dir / f'logo-{theme}.png'
    image.save(target, format='PNG', optimize=True)
    return target
