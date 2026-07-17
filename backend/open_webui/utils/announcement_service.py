from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx


ALLOWED_ANNOUNCEMENT_TYPES = {'info', 'warning', 'maintenance'}
MAX_RESPONSE_BYTES = 64 * 1024


class AnnouncementError(RuntimeError):
    pass


def _required_text(payload: dict[str, Any], key: str, max_length: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise AnnouncementError(f'announcement {key} is invalid')
    value = value.strip()
    if not value or len(value) > max_length:
        raise AnnouncementError(f'announcement {key} is invalid')
    return value


def _optional_timestamp(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise AnnouncementError(f'announcement {key} is invalid')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise AnnouncementError(f'announcement {key} is invalid') from exc
    if parsed.tzinfo is None:
        raise AnnouncementError(f'announcement {key} must include a timezone')
    return parsed.isoformat()


def normalize_announcement(payload: Any) -> dict[str, str | None]:
    if not isinstance(payload, dict):
        raise AnnouncementError('announcement response must be a JSON object')

    announcement_type = str(payload.get('type') or 'info').strip().lower()
    if announcement_type not in ALLOWED_ANNOUNCEMENT_TYPES:
        raise AnnouncementError('announcement type is invalid')

    return {
        'id': _required_text(payload, 'id', 128),
        'title': _required_text(payload, 'title', 160),
        'content': _required_text(payload, 'content', 4000),
        'type': announcement_type,
        'published_at': _optional_timestamp(payload, 'published_at'),
        'expires_at': _optional_timestamp(payload, 'expires_at'),
    }


class AnnouncementService:
    def __init__(
        self,
        url: str,
        cache_ttl_seconds: float = 600,
        timeout_seconds: float = 4,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] | None = None,
        utcnow: Callable[[], datetime] | None = None,
    ):
        self.url = url.strip()
        if self.url:
            parsed = urlparse(self.url)
            if (
                parsed.scheme != 'https'
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise ValueError('announcement URL must be a valid HTTPS URL')
        self.cache_ttl_seconds = max(float(cache_ttl_seconds), 0)
        self.timeout_seconds = max(float(timeout_seconds), 0.1)
        self.transport = transport
        self.clock = clock or time.monotonic
        self.utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self._cached_announcement: dict[str, str | None] | None = None
        self._cached_at: float | None = None

    def _is_expired(self, announcement: dict[str, str | None]) -> bool:
        expires_at = announcement.get('expires_at')
        if not expires_at:
            return False
        return datetime.fromisoformat(expires_at) <= self.utcnow()

    async def _fetch(self) -> dict[str, str | None]:
        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=self.timeout_seconds,
                follow_redirects=False,
            ) as client:
                async with client.stream(
                    'GET',
                    self.url,
                    headers={
                        'Accept': 'application/json',
                        'User-Agent': 'ArtiChat-Announcements/1',
                    },
                ) as response:
                    if response.status_code != 200:
                        raise AnnouncementError(
                            f'announcement request failed with status {response.status_code}'
                        )
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise AnnouncementError('announcement response is too large')
        except AnnouncementError:
            raise
        except httpx.HTTPError as exc:
            raise AnnouncementError('announcement request failed') from exc

        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AnnouncementError('announcement response is invalid JSON') from exc
        return normalize_announcement(payload)

    async def get(self, force: bool = False) -> dict[str, str | None] | None:
        if not self.url:
            return None

        now = self.clock()
        cache_is_fresh = (
            self._cached_at is not None
            and now - self._cached_at < self.cache_ttl_seconds
        )
        if not force and cache_is_fresh:
            if self._cached_announcement and self._is_expired(
                self._cached_announcement
            ):
                return None
            return (
                dict(self._cached_announcement)
                if self._cached_announcement
                else None
            )

        try:
            announcement = await self._fetch()
        except AnnouncementError:
            if self._cached_announcement and not self._is_expired(
                self._cached_announcement
            ):
                return dict(self._cached_announcement)
            raise

        self._cached_announcement = announcement
        self._cached_at = now
        if self._is_expired(announcement):
            return None
        return dict(announcement)
