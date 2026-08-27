from decimal import Decimal

import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from open_webui.routers.images import _image_billing_settings
from open_webui.utils.media_billing import media_cost_chatpoints, media_cost_micros, parse_media_rate


@pytest.mark.parametrize(
    ('value', 'expected'),
    [('1', Decimal('1')), ('0.125', Decimal('0.125')), (2, Decimal('2'))],
)
def test_media_rate_accepts_decimal_chatpoint_prices(value, expected):
    assert parse_media_rate(value) == expected


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '1000001'])
def test_media_rate_rejects_unsafe_prices(value):
    with pytest.raises(ValueError):
        parse_media_rate(value)


def test_media_cost_is_calculated_from_units_and_rate():
    assert media_cost_micros(3, '0.25') == 750_000
    assert media_cost_micros(5, '0') == 0
    assert media_cost_chatpoints(3, '0.25') == Decimal('0.75')


def test_media_cost_rejects_negative_units():
    with pytest.raises(ValueError):
        media_cost_micros(-1, '1')


def test_image_billing_requires_explicit_confirmation_for_metered_users():
    config = SimpleNamespace(
        IMAGE_GENERATION_CHATPOINTS_PER_IMAGE='1',
        IMAGE_GENERATION_DAILY_MAX_CHATPOINTS='0',
        IMAGE_GENERATION_REQUIRE_CONFIRMATION=True,
    )
    with pytest.raises(HTTPException) as error:
        _image_billing_settings(SimpleNamespace(role='user'), config, 2, False)

    assert error.value.status_code == 409
    assert error.value.detail['code'] == 'IMAGE_COST_CONFIRMATION_REQUIRED'
    assert error.value.detail['estimated_chatpoints'] == '2'
