from __future__ import annotations

import asyncio
import base64
import binascii
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, status

from open_webui.env import AIOHTTP_CLIENT_ALLOW_REDIRECTS, AIOHTTP_CLIENT_SESSION_SSL
from open_webui.models.files import Files


_INTERNAL_FILE_PATH = re.compile(r'^/api/v1/files/([^/]+)/content(?:/[^/]*)?/?$')
_DATA_URL = re.compile(r'^data:([^;,]+);base64,(.*)$', re.IGNORECASE | re.DOTALL)
_RAW_BASE64 = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')


@dataclass(frozen=True)
class ResolvedImage:
    data: bytes
    content_type: str
    filename: str

    def as_data_url(self) -> str:
        encoded = base64.b64encode(self.data).decode('ascii')
        return f'data:{self.content_type};base64,{encoded}'


def extract_internal_file_id(reference: str) -> str | None:
    """Return the file ID from a relative or absolute ArtiChat content URL."""
    if not isinstance(reference, str):
        return None

    parsed = urlparse(reference.strip())
    match = _INTERNAL_FILE_PATH.fullmatch(parsed.path)
    if not match:
        return None
    return unquote(match.group(1))


def _image_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={'code': code, 'message': message})


def _normalize_image_content_type(content_type: str | None) -> str | None:
    normalized = (content_type or '').split(';', 1)[0].strip().lower()
    return normalized if normalized.startswith('image/') else None


def _filename_for_content_type(content_type: str) -> str:
    extension = mimetypes.guess_extension(content_type) or '.png'
    return f'image-edit-source{extension}'


def _get_stored_file_path(path: str) -> str:
    from open_webui.storage.provider import Storage

    return Storage.get_file(path)


async def _has_file_access(file_id: str, user) -> bool:
    from open_webui.utils.access_control.files import has_access_to_file

    return await has_access_to_file(file_id, 'read', user)


def _resolve_data_url(reference: str) -> ResolvedImage:
    match = _DATA_URL.fullmatch(reference)
    if not match:
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'invalid_image_reference',
            'Image data must be a complete base64 data URL.',
        )

    content_type = _normalize_image_content_type(match.group(1))
    if not content_type:
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'unsupported_image_type',
            'The data URL does not contain an image.',
        )

    try:
        encoded = re.sub(r'\s+', '', match.group(2))
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'invalid_image_reference',
            'The image data URL contains invalid base64 data.',
        ) from exc

    if not data:
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'invalid_image_reference',
            'The image data URL is empty.',
        )

    return ResolvedImage(
        data=data,
        content_type=content_type,
        filename=_filename_for_content_type(content_type),
    )


async def _resolve_file_id(file_id: str, user) -> ResolvedImage:
    if user is None:
        raise _image_error(
            status.HTTP_401_UNAUTHORIZED,
            'image_access_denied',
            'A signed-in user is required to read an image file.',
        )

    file = await Files.get_file_by_id(file_id)
    if not file:
        raise _image_error(
            status.HTTP_404_NOT_FOUND,
            'image_file_not_found',
            'The image file was not found or is not accessible.',
        )

    if file.user_id != user.id and user.role != 'admin' and not await _has_file_access(file.id, user):
        raise _image_error(
            status.HTTP_404_NOT_FOUND,
            'image_file_not_found',
            'The image file was not found or is not accessible.',
        )

    try:
        file_path = Path(await asyncio.to_thread(_get_stored_file_path, file.path))
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        data = await asyncio.to_thread(file_path.read_bytes)
    except FileNotFoundError as exc:
        raise _image_error(
            status.HTTP_404_NOT_FOUND,
            'image_file_not_found',
            'The image file was not found or is not accessible.',
        ) from exc
    except Exception as exc:
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'image_file_read_failed',
            'The image file could not be read.',
        ) from exc

    metadata = file.meta or {}
    content_type = _normalize_image_content_type(metadata.get('content_type'))
    content_type = content_type or _normalize_image_content_type(mimetypes.guess_type(file_path.name)[0])
    if not content_type:
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'unsupported_image_type',
            'The referenced file is not a supported image.',
        )

    return ResolvedImage(
        data=data,
        content_type=content_type,
        filename=Path(metadata.get('name') or file.filename or file_path.name).name,
    )


async def _resolve_external_url(reference: str) -> ResolvedImage:
    from open_webui.retrieval.web.utils import get_ssrf_safe_session, validate_url

    try:
        await asyncio.to_thread(validate_url, reference)
        async with get_ssrf_safe_session() as session:
            async with session.get(
                reference,
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
                allow_redirects=AIOHTTP_CLIENT_ALLOW_REDIRECTS,
            ) as response:
                response.raise_for_status()
                content_type = _normalize_image_content_type(response.headers.get('content-type'))
                if not content_type:
                    raise _image_error(
                        status.HTTP_400_BAD_REQUEST,
                        'unsupported_image_type',
                        'The external URL did not return an image.',
                    )
                data = await response.read()
    except HTTPException:
        raise
    except Exception as exc:
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'external_image_fetch_failed',
            'The external image could not be loaded.',
        ) from exc

    filename = Path(unquote(urlparse(reference).path)).name or _filename_for_content_type(content_type)
    return ResolvedImage(data=data, content_type=content_type, filename=filename)


def _looks_like_raw_base64(reference: str) -> bool:
    compact = re.sub(r'\s+', '', reference)
    return len(compact) >= 64 and len(compact) % 4 == 0 and _RAW_BASE64.fullmatch(compact) is not None


async def resolve_image_reference(reference: str, user) -> ResolvedImage:
    if not isinstance(reference, str) or not reference.strip():
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'invalid_image_reference',
            'An image file ID, URL, or data URL is required.',
        )

    reference = reference.strip()
    if reference.lower().startswith('data:'):
        return _resolve_data_url(reference)

    if file_id := extract_internal_file_id(reference):
        return await _resolve_file_id(file_id, user)

    parsed = urlparse(reference)
    if parsed.scheme in {'http', 'https'}:
        return await _resolve_external_url(reference)

    if parsed.scheme or reference.startswith('/') or _looks_like_raw_base64(reference):
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'invalid_image_reference',
            'Use a file ID, an ArtiChat file-content URL, an HTTPS image URL, or a complete data URL.',
        )

    return await _resolve_file_id(reference, user)


async def resolve_image_references(references: list[str], user) -> list[ResolvedImage]:
    if not references:
        raise _image_error(
            status.HTTP_400_BAD_REQUEST,
            'invalid_image_reference',
            'At least one source image is required.',
        )
    return list(await asyncio.gather(*(resolve_image_reference(reference, user) for reference in references)))
