from datetime import datetime, timezone

import httpx
import pytest

from open_webui.utils.announcement_service import (
    AnnouncementError,
    AnnouncementService,
    normalize_announcement,
)


ANNOUNCEMENT = {
    'id': 'notice-1',
    'title': 'ArtiChat announcement',
    'content': 'A single plain-text announcement.',
    'type': 'info',
    'published_at': '2026-07-18T10:00:00+08:00',
    'expires_at': None,
}


def test_announcement_service_requires_https_url():
    with pytest.raises(ValueError, match='HTTPS'):
        AnnouncementService('http://example.com/index.json')


def test_normalize_announcement_rejects_unexpected_payloads():
    with pytest.raises(AnnouncementError, match='JSON object'):
        normalize_announcement([ANNOUNCEMENT])

    with pytest.raises(AnnouncementError, match='type'):
        normalize_announcement({**ANNOUNCEMENT, 'type': 'html'})


@pytest.mark.asyncio
async def test_get_returns_and_caches_one_normalized_announcement():
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        assert request.headers['accept'] == 'application/json'
        return httpx.Response(200, json=ANNOUNCEMENT)

    service = AnnouncementService(
        'https://example.com/index.json',
        transport=httpx.MockTransport(handler),
    )

    first = await service.get()
    second = await service.get()

    assert first == second
    assert first['id'] == 'notice-1'
    assert first['published_at'] == '2026-07-18T10:00:00+08:00'
    assert calls == 1


@pytest.mark.asyncio
async def test_expired_announcement_is_hidden():
    payload = {**ANNOUNCEMENT, 'expires_at': '2026-07-18T09:00:00+00:00'}
    service = AnnouncementService(
        'https://example.com/index.json',
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        ),
        utcnow=lambda: datetime(2026, 7, 18, 10, tzinfo=timezone.utc),
    )

    assert await service.get() is None


@pytest.mark.asyncio
async def test_failed_refresh_falls_back_to_last_good_announcement():
    requests = 0

    def handler(request: httpx.Request):
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(200, json=ANNOUNCEMENT)
        return httpx.Response(503)

    service = AnnouncementService(
        'https://example.com/index.json',
        transport=httpx.MockTransport(handler),
    )

    cached = await service.get()
    fallback = await service.get(force=True)

    assert fallback == cached
    assert requests == 2


@pytest.mark.asyncio
async def test_failed_initial_request_raises_safe_error():
    service = AnnouncementService(
        'https://example.com/index.json',
        transport=httpx.MockTransport(
            lambda request: httpx.Response(503, text='upstream details')
        ),
    )

    with pytest.raises(AnnouncementError, match='status 503'):
        await service.get()
