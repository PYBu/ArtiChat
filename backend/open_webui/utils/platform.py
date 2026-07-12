from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_PLATFORM_LOGO_BYTES = 2 * 1024 * 1024
PLATFORM_LOGO_CONTENT_TYPES = {'image/png', 'image/jpeg', 'image/webp'}


def normalize_platform_settings(data: dict) -> dict[str, str]:
    name = str(data.get('name') or '').strip()
    if not name:
        raise ValueError('PLATFORM_NAME_REQUIRED')
    if len(name) > 100:
        raise ValueError('PLATFORM_NAME_TOO_LONG')
    return {
        'name': name,
        'about_title': str(data.get('about_title') or '').strip(),
        'about_content': str(data.get('about_content') or '').strip(),
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
