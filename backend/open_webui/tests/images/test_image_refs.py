from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from open_webui.utils import image_refs


def test_extract_internal_file_id_supports_relative_and_absolute_urls():
    file_id = 'file-123'

    assert image_refs.extract_internal_file_id(f'/api/v1/files/{file_id}/content') == file_id
    assert (
        image_refs.extract_internal_file_id(f'https://chat.example/api/v1/files/{file_id}/content?download=1')
        == file_id
    )
    assert image_refs.extract_internal_file_id('https://example.com/image.png') is None


def test_complete_image_data_url_is_resolved():
    source = b'png-image-bytes'
    reference = f'data:image/png;base64,{base64.b64encode(source).decode("ascii")}'

    resolved = asyncio.run(image_refs.resolve_image_reference(reference, SimpleNamespace(id='user-1', role='user')))

    assert resolved.data == source
    assert resolved.content_type == 'image/png'
    assert resolved.as_data_url() == reference


def test_raw_base64_and_local_paths_are_rejected(monkeypatch):
    file_lookup = AsyncMock()
    monkeypatch.setattr(image_refs.Files, 'get_file_by_id', file_lookup)

    references = [base64.b64encode(b'x' * 120).decode('ascii'), '/etc/passwd', 'file:///etc/passwd']
    for reference in references:
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(image_refs.resolve_image_reference(reference, SimpleNamespace(id='user-1', role='user')))
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail['code'] == 'invalid_image_reference'

    file_lookup.assert_not_awaited()


def test_absolute_internal_url_uses_authorized_local_resolution(monkeypatch, tmp_path):
    source = tmp_path / 'source.png'
    source.write_bytes(b'local-image-bytes')
    file = SimpleNamespace(
        id='file-123',
        user_id='user-1',
        path='stored/source.png',
        filename='source.png',
        meta={'content_type': 'image/png'},
    )
    monkeypatch.setattr(image_refs.Files, 'get_file_by_id', AsyncMock(return_value=file))
    monkeypatch.setattr(image_refs, '_get_stored_file_path', lambda _path: source)
    external_resolver = AsyncMock()
    monkeypatch.setattr(image_refs, '_resolve_external_url', external_resolver)

    resolved = asyncio.run(
        image_refs.resolve_image_reference(
            'https://chat.example/api/v1/files/file-123/content',
            SimpleNamespace(id='user-1', role='user'),
        )
    )

    assert resolved.data == b'local-image-bytes'
    assert resolved.content_type == 'image/png'
    external_resolver.assert_not_awaited()


def test_file_access_is_checked_before_storage_read(monkeypatch):
    file = SimpleNamespace(
        id='file-123',
        user_id='another-user',
        path='stored/source.png',
        filename='source.png',
        meta={'content_type': 'image/png'},
    )
    monkeypatch.setattr(image_refs.Files, 'get_file_by_id', AsyncMock(return_value=file))
    monkeypatch.setattr(image_refs, '_has_file_access', AsyncMock(return_value=False))
    storage_get = AsyncMock()
    monkeypatch.setattr(image_refs, '_get_stored_file_path', storage_get)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(image_refs.resolve_image_reference('file-123', SimpleNamespace(id='user-1', role='user')))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail['code'] == 'image_file_not_found'
    storage_get.assert_not_called()


def test_combined_image_size_is_bounded(monkeypatch):
    monkeypatch.setattr(image_refs, '_MAX_TOTAL_IMAGE_BYTES', 10)
    resolver = AsyncMock(
        side_effect=[
            image_refs.ResolvedImage(b'a' * 6, 'image/png', 'one.png'),
            image_refs.ResolvedImage(b'b' * 5, 'image/png', 'two.png'),
        ]
    )
    monkeypatch.setattr(image_refs, 'resolve_image_reference', resolver)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(image_refs.resolve_image_references(['one', 'two'], SimpleNamespace(id='user-1')))

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail['code'] == 'images_too_large'


def test_stored_image_size_is_checked_before_read(monkeypatch, tmp_path):
    source = tmp_path / 'oversize.png'
    source.write_bytes(b'x' * 6)
    file = SimpleNamespace(
        id='file-123',
        user_id='user-1',
        path='stored/oversize.png',
        filename='oversize.png',
        meta={'content_type': 'image/png'},
    )
    reader = Mock(side_effect=AssertionError('oversize stored image must not be read'))
    monkeypatch.setattr(image_refs, '_MAX_IMAGE_BYTES', 5)
    monkeypatch.setattr(image_refs.Files, 'get_file_by_id', AsyncMock(return_value=file))
    monkeypatch.setattr(image_refs, '_get_stored_file_path', lambda _path: source)
    monkeypatch.setattr(image_refs, '_read_image_file_bounded', reader)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(image_refs.resolve_image_reference('file-123', SimpleNamespace(id='user-1', role='user')))

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail['code'] == 'image_too_large'
    reader.assert_not_called()


def test_external_image_declared_over_limit_is_rejected_before_body_read(monkeypatch):
    from open_webui.retrieval.web import utils as web_utils

    class Content:
        def iter_chunked(self, _size):
            raise AssertionError('response body must not be read')

    class Response:
        headers = {'content-type': 'image/png'}
        content_length = image_refs._MAX_IMAGE_BYTES + 1
        content = Content()

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def raise_for_status(self):
            return None

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(web_utils, 'validate_url', lambda _url: None)
    monkeypatch.setattr(web_utils, 'get_ssrf_safe_session', lambda: Session())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            image_refs.resolve_image_reference(
                'https://images.example/source.png',
                SimpleNamespace(id='user-1', role='user'),
            )
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail['code'] == 'image_too_large'
