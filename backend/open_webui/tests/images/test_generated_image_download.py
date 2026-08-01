from __future__ import annotations

import asyncio

from open_webui.routers import images


class _Content:
    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks
        self.iterated = False

    async def iter_chunked(self, _size):
        self.iterated = True
        for chunk in self.chunks:
            yield chunk


class _Response:
    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict | None = None,
        chunks: list[bytes] | None = None,
        content_length: int | None = None,
    ):
        self.status = status
        self.headers = headers or {'content-type': 'image/png'}
        self.content = _Content(chunks or [b'image-bytes'])
        self.content_length = content_length

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f'HTTP {self.status}')


class _Session:
    def __init__(self, responses: list[_Response], calls: list[dict], *, context_manager: bool):
        self.responses = responses
        self.calls = calls
        self.context_manager = context_manager

    async def __aenter__(self):
        if not self.context_manager:
            raise AssertionError('shared session must not be entered')
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False

    def get(self, url, **kwargs):
        self.calls.append({'url': url, **kwargs})
        return self.responses.pop(0)


def test_untrusted_generated_url_never_receives_provider_headers(monkeypatch):
    safe_calls = []
    validated = []
    safe_session = _Session([_Response()], safe_calls, context_manager=True)
    monkeypatch.setattr(images, 'get_ssrf_safe_session', lambda: safe_session)
    monkeypatch.setattr(images, 'validate_url', lambda url: validated.append(url))

    result = asyncio.run(
        images.get_image_data(
            'https://cdn.example/generated.png',
            {'Authorization': 'Bearer provider-secret', 'X-OpenWebUI-User-Email': 'user@example.com'},
            trusted_base_url='https://api.example/v1',
        )
    )

    assert result == (b'image-bytes', 'image/png')
    assert validated == ['https://cdn.example/generated.png']
    assert safe_calls[0]['headers'] is None


def test_cross_origin_redirect_strips_credentials_and_revalidates(monkeypatch):
    trusted_calls = []
    safe_calls = []
    validated = []
    trusted_session = _Session(
        [_Response(status=302, headers={'location': 'https://cdn.example/generated.png'})],
        trusted_calls,
        context_manager=False,
    )
    safe_session = _Session([_Response()], safe_calls, context_manager=True)
    monkeypatch.setattr(images, 'get_session', lambda: asyncio.sleep(0, result=trusted_session))
    monkeypatch.setattr(images, 'get_ssrf_safe_session', lambda: safe_session)
    monkeypatch.setattr(images, 'validate_url', lambda url: validated.append(url))
    monkeypatch.setattr(images, 'AIOHTTP_CLIENT_ALLOW_REDIRECTS', True)

    result = asyncio.run(
        images.get_image_data(
            'https://api.example/v1/generated/1',
            {'Authorization': 'Bearer provider-secret'},
            trusted_base_url='https://api.example/v1',
        )
    )

    assert result == (b'image-bytes', 'image/png')
    assert trusted_calls[0]['headers'] == {'Authorization': 'Bearer provider-secret'}
    assert safe_calls[0]['headers'] is None
    assert validated == ['https://cdn.example/generated.png']


def test_declared_oversize_generated_image_is_not_read(monkeypatch):
    response = _Response(content_length=images.MAX_GENERATED_IMAGE_BYTES + 1)
    safe_session = _Session([response], [], context_manager=True)
    monkeypatch.setattr(images, 'get_ssrf_safe_session', lambda: safe_session)
    monkeypatch.setattr(images, 'validate_url', lambda _url: None)

    result = asyncio.run(images.get_image_data('https://cdn.example/oversize.png'))

    assert result == (None, None)
    assert response.content.iterated is False
