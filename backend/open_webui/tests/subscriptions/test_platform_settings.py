from io import BytesIO

import pytest
from PIL import Image

from open_webui.utils.platform import normalize_platform_settings, save_platform_logo


def image_bytes(image_format: str = 'PNG') -> bytes:
    output = BytesIO()
    Image.new('RGB', (32, 32), '#111111').save(output, format=image_format)
    return output.getvalue()


def test_platform_text_settings_are_trimmed_and_defaulted():
    assert normalize_platform_settings(
        {'name': '  My Platform  ', 'about_title': '  About us ', 'about_content': '  Body\n'}
    ) == {
        'name': 'My Platform',
        'about_title': 'About us',
        'about_content': 'Body',
    }

    with pytest.raises(ValueError, match='PLATFORM_NAME_REQUIRED'):
        normalize_platform_settings({'name': '   ', 'about_title': '', 'about_content': ''})


@pytest.mark.parametrize('image_format', ['PNG', 'JPEG', 'WEBP'])
def test_platform_logo_accepts_supported_raster_images_and_reencodes_png(tmp_path, image_format):
    saved = save_platform_logo(
        content=image_bytes(image_format),
        content_type=f'image/{image_format.lower()}',
        theme='dark',
        assets_dir=tmp_path,
    )

    assert saved.name == 'logo-dark.png'
    assert Image.open(saved).format == 'PNG'


def test_platform_logo_rejects_invalid_type_content_and_size(tmp_path):
    with pytest.raises(ValueError, match='PLATFORM_LOGO_TYPE_INVALID'):
        save_platform_logo(content=image_bytes(), content_type='image/gif', theme='light', assets_dir=tmp_path)
    with pytest.raises(ValueError, match='PLATFORM_LOGO_INVALID'):
        save_platform_logo(content=b'not-an-image', content_type='image/png', theme='light', assets_dir=tmp_path)
    with pytest.raises(ValueError, match='PLATFORM_LOGO_TOO_LARGE'):
        save_platform_logo(content=b'x' * (2 * 1024 * 1024 + 1), content_type='image/png', theme='light', assets_dir=tmp_path)
    with pytest.raises(ValueError, match='PLATFORM_LOGO_THEME_INVALID'):
        save_platform_logo(content=image_bytes(), content_type='image/png', theme='other', assets_dir=tmp_path)
