from __future__ import annotations

import asyncio
import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest
from fastapi import HTTPException

from open_webui.routers import images
from open_webui.tools import builtin
from open_webui.utils import middleware
from open_webui.utils.image_refs import ResolvedImage


def _user_dict() -> dict:
    return {
        'id': 'user-1',
        'email': 'user@example.com',
        'role': 'user',
        'name': 'User',
        'last_active_at': 1,
        'updated_at': 1,
        'created_at': 1,
    }


def test_edit_tool_falls_back_to_the_current_image_attachment(monkeypatch):
    edit_call = AsyncMock(return_value=[{'id': 'edited-1', 'url': '/api/v1/files/edited-1/content'}])
    monkeypatch.setattr(builtin, 'image_edits', edit_call)

    result = json.loads(
        asyncio.run(
            builtin.edit_image(
                prompt='Change the background',
                __request__=SimpleNamespace(),
                __user__=_user_dict(),
                __metadata__={
                    'files': [
                        {
                            'id': 'source-1',
                            'type': 'image',
                            'url': '/api/v1/files/source-1/content',
                            'content_type': 'image/png',
                        }
                    ]
                },
            )
        )
    )

    form_data = edit_call.await_args.kwargs['form_data']
    assert form_data.image == ['source-1']
    assert result['images'][0]['id'] == 'edited-1'


def test_generated_assistant_image_is_added_to_model_file_context(monkeypatch):
    chat = SimpleNamespace(
        chat={
            'history': {
                'currentId': 'user-2',
                'messages': {
                    'user-1': {
                        'id': 'user-1',
                        'parentId': None,
                        'role': 'user',
                        'content': 'Generate an image',
                    },
                    'assistant-1': {
                        'id': 'assistant-1',
                        'parentId': 'user-1',
                        'role': 'assistant',
                        'content': 'Done',
                        'files': [
                            {
                                'type': 'image',
                                'url': 'https://chat.example/api/v1/files/generated-1/content',
                            }
                        ],
                    },
                    'user-2': {
                        'id': 'user-2',
                        'parentId': 'assistant-1',
                        'role': 'user',
                        'content': 'Edit that image',
                    },
                },
            }
        }
    )
    monkeypatch.setattr(middleware.Chats, 'get_chat_by_id_and_user_id', AsyncMock(return_value=chat))
    messages = [
        {'role': 'user', 'content': 'Generate an image'},
        {'role': 'assistant', 'content': 'Done'},
        {'role': 'user', 'content': 'Edit that image'},
    ]

    result = asyncio.run(middleware.add_file_context(messages, 'chat-1', SimpleNamespace(id='user-1')))

    assert 'id="generated-1"' in result[1]['content']
    assert 'url="https://chat.example/api/v1/files/generated-1/content"' in result[1]['content']


class _ResponseContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        output = base64.b64encode(b'edited-image').decode('ascii')
        return {'data': [{'b64_json': output}]}


class _RecordingSession:
    def __init__(self):
        self.request = None

    def post(self, **kwargs):
        self.request = kwargs
        return _ResponseContext()


class _UnauthorizedResponseContext(_ResponseContext):
    def raise_for_status(self):
        raise aiohttp.ClientResponseError(
            request_info=None,
            history=(),
            status=401,
            message='Unauthorized',
        )


class _UnauthorizedSession:
    def post(self, **kwargs):
        return _UnauthorizedResponseContext()


def test_openai_edit_receives_resolved_image_bytes_as_multipart(monkeypatch):
    session = _RecordingSession()
    image_config = SimpleNamespace(
        IMAGE_EDIT_SIZE='',
        IMAGE_EDIT_MODEL='edit-model',
        IMAGE_EDIT_ENGINE='openai',
        IMAGES_EDIT_OPENAI_API_KEY='secret',
        IMAGES_EDIT_OPENAI_API_BASE_URL='https://images.example/v1',
        IMAGES_EDIT_OPENAI_API_VERSION='',
    )
    resolver = AsyncMock(return_value=[ResolvedImage(b'source-image', 'image/png', 'source.png')])
    uploader = AsyncMock(return_value=(SimpleNamespace(id='edited-1'), '/api/v1/files/edited-1/content'))
    monkeypatch.setattr(images, 'get_image_config', AsyncMock(return_value=image_config))
    monkeypatch.setattr(images, 'resolve_image_references', resolver)
    monkeypatch.setattr(images, 'get_session', AsyncMock(return_value=session))
    monkeypatch.setattr(images, 'upload_image', uploader)

    result = asyncio.run(
        images.image_edits(
            request=SimpleNamespace(),
            form_data=images.EditImageForm(
                prompt='Change the background',
                image='https://chat.example/api/v1/files/source-1/content',
            ),
            user=SimpleNamespace(id='user-1', role='user'),
        )
    )

    resolver.assert_awaited_once()
    multipart = session.request['data']
    image_fields = [field for field in multipart._fields if field[0].get('name') == 'image']
    assert len(image_fields) == 1
    assert isinstance(image_fields[0][2], io.BytesIO)
    assert image_fields[0][2].getvalue() == b'source-image'
    assert result == [{'id': 'edited-1', 'url': '/api/v1/files/edited-1/content'}]


def test_openai_edit_reports_upstream_authentication_failure(monkeypatch):
    image_config = SimpleNamespace(
        IMAGE_EDIT_SIZE='',
        IMAGE_EDIT_MODEL='edit-model',
        IMAGE_EDIT_ENGINE='openai',
        IMAGES_EDIT_OPENAI_API_KEY='rejected-key',
        IMAGES_EDIT_OPENAI_API_BASE_URL='https://images.example/v1',
        IMAGES_EDIT_OPENAI_API_VERSION='',
    )
    monkeypatch.setattr(images, 'get_image_config', AsyncMock(return_value=image_config))
    monkeypatch.setattr(
        images,
        'resolve_image_references',
        AsyncMock(return_value=[ResolvedImage(b'source-image', 'image/png', 'source.png')]),
    )
    monkeypatch.setattr(images, 'get_session', AsyncMock(return_value=_UnauthorizedSession()))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            images.image_edits(
                request=SimpleNamespace(),
                form_data=images.EditImageForm(prompt='Change the background', image='source-1'),
                user=SimpleNamespace(id='user-1', role='user'),
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        '[ERROR: Image edit provider authentication failed (HTTP 401). '
        'Check the Image Edit API Base URL and API Key.]'
    )
