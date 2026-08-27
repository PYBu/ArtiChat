import asyncio
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from open_webui.models.video_generation import VideoGenerationJob
from open_webui.utils import video_generation as video_generation_module
from open_webui.utils.video_generation import (
    MiniMaxH3Provider,
    SeedanceProvider,
    VideoTask,
    VideoProviderError,
    _validate_video_options,
    _normalise_video_status,
    create_video_job,
)


def _job(**overrides):
    values = {
        'id': 'video-job-1',
        'user_id': 'user-1',
        'chat_id': 'chat-1',
        'message_id': 'message-1',
        'provider': 'minimax',
        'model': 'MiniMax-H3',
        'prompt': 'A quiet lake',
        'input_mode': 'text',
        'request_payload': {'first_frame_url': None, 'options': {'duration': 5}},
        'status': 'running',
        'next_poll_at': 100,
        'created_at': 100,
        'updated_at': 100,
    }
    values.update(overrides)
    return VideoGenerationJob(**values)


class _RequestApp:
    def url_path_for(self, _name, *, id):
        return f'/files/{id}'


class _Request:
    app = _RequestApp()


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        ('Preparing', 'queued'),
        ('queueing', 'queued'),
        ('Processing', 'running'),
        ('success', 'succeeded'),
        ('Fail', 'failed'),
        ('canceled', 'cancelled'),
        ('expired', 'expired'),
    ],
)
def test_provider_statuses_normalize_to_worker_states(raw, expected):
    assert _normalise_video_status(raw) == expected


def test_unknown_provider_status_stays_active_for_safe_polling():
    assert _normalise_video_status('vendor-specific-progress') == 'running'


def test_minimax_h3_rejects_unsupported_resolution_before_queueing():
    with pytest.raises(HTTPException, match='supports only 768P or 2K'):
        _validate_video_options(
            SimpleNamespace(
                provider='minimax',
                api_version='v2',
                model='MiniMAX-H3',
                resolution='768P',
            ),
            {'resolution': '1080P'},
        )


@pytest.mark.asyncio
async def test_non_retryable_provider_error_fails_job_without_repeating(monkeypatch):
    row = _job(status='queued', provider_task_id=None, attempts=0)
    provider = SimpleNamespace(
        submit=AsyncMock(
            side_effect=VideoProviderError(
                'bad_request_error',
                'invalid resolution',
                retryable=False,
                status=400,
            )
        )
    )
    release = AsyncMock()
    monkeypatch.setattr(
        video_generation_module,
        '_load_provider_config',
        AsyncMock(
            return_value=SimpleNamespace(
                provider='minimax',
                api_version='v2',
                model='MiniMax-H3',
                poll_interval=1,
                max_attempts=5,
                max_output_mb=1,
                duration=5,
            )
        ),
    )
    monkeypatch.setattr(video_generation_module, 'get_video_provider', lambda _config: provider)
    monkeypatch.setattr(video_generation_module, '_release_job_billing', release)
    monkeypatch.setattr(video_generation_module, '_emit_job_event', AsyncMock())

    await video_generation_module._process_job(_Request(), row)

    assert row.status == 'failed'
    assert row.attempts == 1
    assert row.error_code == 'bad_request_error'
    assert row.error_message == 'invalid resolution'
    provider.submit.assert_awaited_once()
    release.assert_awaited_once()


@pytest.mark.asyncio
async def test_video_generation_requires_explicit_cost_confirmation(monkeypatch):
    config = {
        'video_generation.enable': True,
        'video_generation.admin_only': False,
        'video_generation.provider': 'minimax',
        'video_generation.api_version': 'v2',
        'video_generation.base_url': 'https://api.example.test',
        'video_generation.api_key': 'test-key',
        'video_generation.model': 'MiniMax-H3',
        'video_generation.region': 'cn-beijing',
        'video_generation.resolution': '768P',
        'video_generation.duration': 5,
        'video_generation.ratio': '16:9',
        'video_generation.watermark': False,
        'video_generation.poll_interval': 1,
        'video_generation.max_concurrency': 1,
        'video_generation.max_output_mb': 1,
        'video_generation.max_attempts': 1,
        'billing.media.video_chatpoints_per_second': '1',
        'billing.media.video_require_confirmation': True,
        'billing.media.video_daily_max_chatpoints': '0',
    }

    async def get_many(*_keys):
        return config

    async def get_value(key, default=None):
        return {'video_generation.prompt.enable': False, 'user.permissions': {}}.get(key, default)

    monkeypatch.setattr(video_generation_module.Config, 'get_many', get_many)
    monkeypatch.setattr(video_generation_module.Config, 'get', get_value)
    monkeypatch.setattr(video_generation_module, 'get_video_provider', lambda _config: object())
    async def has_permission(*_args):
        return True

    monkeypatch.setattr(video_generation_module, 'has_permission', has_permission)

    with pytest.raises(HTTPException) as error:
        await create_video_job(
            None,
            prompt='A slow camera pan',
            first_frame_url=None,
            model=None,
            options={'duration': 6},
            user=SimpleNamespace(id='video-user', role='user'),
            chat_id=None,
            message_id=None,
        )

    assert error.value.status_code == 409
    assert error.value.detail['code'] == 'VIDEO_COST_CONFIRMATION_REQUIRED'
    assert error.value.detail['estimated_chatpoints'] == '6'


def test_minimax_submit_builds_text_and_first_frame_payload():
    provider = MiniMaxH3Provider(
        SimpleNamespace(
            base_url='https://api.minimaxi.com',
            api_key='test-key',
            api_version='v2',
            model='MiniMax-H3',
            resolution='768P',
            duration=5,
            ratio='16:9',
            watermark=False,
        )
    )
    captured = {}

    async def request(method, path, **kwargs):
        captured.update({'method': method, 'path': path, 'payload': kwargs['json']})
        return {'task_id': 'minimax-task-1'}

    provider._request = request
    task = asyncio.run(
        provider.submit(
            prompt='A paper boat crosses a calm lake',
            first_frame_url='data:image/png;base64,AAAA',
            model=None,
            options={'duration': 6, 'resolution': '2K', 'watermark': True},
        )
    )

    assert isinstance(task, VideoTask)
    assert task.task_id == 'minimax-task-1'
    assert captured['method'] == 'POST'
    assert captured['path'] == '/v2/video_generation'
    assert captured['payload']['duration'] == 6
    assert captured['payload']['resolution'] == '2K'
    assert captured['payload']['ratio'] == 'adaptive'
    assert captured['payload']['aigc_watermark'] is True
    assert captured['payload']['content'][1]['role'] == 'first_frame'


def test_minimax_query_normalizes_success_response():
    provider = MiniMaxH3Provider(SimpleNamespace(base_url='', api_key='test-key', api_version='v2'))

    async def request(method, path, **kwargs):
        return {
            'task': {
                'status': 'success',
                'content': {'url': 'https://cdn.example/video.mp4'},
            }
        }

    provider._request = request
    task = asyncio.run(provider.query('minimax-task-1'))

    assert task.status == 'succeeded'
    assert task.progress == 100
    assert task.output_url == 'https://cdn.example/video.mp4'


def test_seedance_submit_and_query_use_modelark_contract():
    provider = SeedanceProvider(
        SimpleNamespace(
            base_url='https://ark.cn-beijing.volces.com',
            api_key='test-key',
            region='cn-beijing',
            model='seedance-1-0-pro',
            resolution='720p',
            duration=5,
            ratio='16:9',
            watermark=False,
        )
    )
    requests = []

    async def submit_request(method, path, **kwargs):
        requests.append((method, path, kwargs['json']))
        return {'id': 'seedance-task-1'}

    provider._request = submit_request
    submitted = asyncio.run(
        provider.submit(prompt='A slow camera pan', first_frame_url=None, model=None, options={})
    )

    assert submitted.task_id == 'seedance-task-1'
    assert requests[0][0:2] == ('POST', '/api/v3/contents/generations/tasks')
    assert requests[0][2]['model'] == 'seedance-1-0-pro'

    async def query_request(method, path, **kwargs):
        return {
            'status': 'succeeded',
            'content': {'video_url': 'https://cdn.example/seedance.mp4'},
        }

    provider._request = query_request
    queried = asyncio.run(provider.query('seedance-task-1'))

    assert queried.status == 'succeeded'
    assert queried.output_url == 'https://cdn.example/seedance.mp4'


def test_download_video_accepts_bounded_video_and_persists_it(monkeypatch):
    class Content:
        async def iter_chunked(self, _size):
            yield b'video-bytes'

    class Response:
        headers: ClassVar = {'content-type': 'video/mp4; charset=binary'}
        content_length = 11
        content: ClassVar = Content()

        def raise_for_status(self):
            return None

    class Session:
        def get(self, *_args, **_kwargs):
            class Context:
                async def __aenter__(self):
                    return Response()

                async def __aexit__(self, *_args):
                    return None

            return Context()

    class SessionContext:
        async def __aenter__(self):
            return Session()

        async def __aexit__(self, *_args):
            return None

    uploaded = {}

    async def upload(request, file, metadata, process, user):
        uploaded.update(
            {
                'request': request,
                'body': file.file.read(),
                'filename': file.filename,
                'metadata': metadata,
                'process': process,
                'user': user,
            }
        )
        return SimpleNamespace(id='file-1')

    validated = []
    monkeypatch.setattr(video_generation_module, 'validate_url', validated.append)
    monkeypatch.setattr(video_generation_module, 'get_ssrf_safe_session', lambda: SessionContext())
    monkeypatch.setattr(video_generation_module, 'upload_file_handler', upload)

    result = asyncio.run(
        video_generation_module._download_video(
            _Request(),
            'https://cdn.example/video.mp4',
            SimpleNamespace(id='user-1'),
            {'video_generation_job_id': 'job-1'},
            max_output_mb=1,
        )
    )

    assert result == ('file-1', '/files/file-1')
    assert validated == ['https://cdn.example/video.mp4']
    assert uploaded['body'] == b'video-bytes'
    assert uploaded['filename'] == 'generated-video.mp4'
    assert uploaded['process'] is False


def test_download_video_rejects_unsupported_content_type(monkeypatch):
    class Response:
        headers: ClassVar = {'content-type': 'text/html'}
        content_length = 2

        class Content:
            async def iter_chunked(self, _size):
                yield b'no'

        content: ClassVar = Content()

        def raise_for_status(self):
            return None

    class Session:
        def get(self, *_args, **_kwargs):
            class Context:
                async def __aenter__(self):
                    return Response()

                async def __aexit__(self, *_args):
                    return None

            return Context()

    class SessionContext:
        async def __aenter__(self):
            return Session()

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(video_generation_module, 'validate_url', lambda _url: None)
    monkeypatch.setattr(video_generation_module, 'get_ssrf_safe_session', lambda: SessionContext())

    with pytest.raises(RuntimeError, match='unsupported content type'):
        asyncio.run(
            video_generation_module._download_video(
                _Request(),
                'https://cdn.example/video.mp4',
                SimpleNamespace(id='user-1'),
                {},
                max_output_mb=1,
            )
        )


def test_attach_video_does_not_emit_duplicate_event_when_link_already_exists(monkeypatch):
    insert = AsyncMock(return_value=None)
    emitter_factory = AsyncMock()
    monkeypatch.setattr(video_generation_module.Chats, 'insert_chat_files', insert)
    monkeypatch.setattr(video_generation_module, 'get_event_emitter', emitter_factory)

    asyncio.run(
        video_generation_module._attach_video(
            _Request(), _job(), 'file-1', '/files/file-1'
        )
    )

    insert.assert_awaited_once()
    emitter_factory.assert_not_awaited()


def test_process_job_reuses_persisted_output_file_on_retry(monkeypatch):
    row = _job(output_file_id='file-existing', provider_task_id='provider-task-1', billing_status='none')
    provider = SimpleNamespace(
        query=AsyncMock(
            return_value=VideoTask(
                task_id='provider-task-1',
                status='succeeded',
                progress=100,
                output_url='https://cdn.example/video.mp4',
                response={'duration': 7},
            )
        )
    )
    download = AsyncMock()
    attach = AsyncMock()
    settle = AsyncMock()
    monkeypatch.setattr(
        video_generation_module,
        '_load_provider_config',
        AsyncMock(
            return_value=SimpleNamespace(
                provider='minimax',
                api_version='v2',
                model='MiniMax-H3',
                poll_interval=1,
                max_attempts=3,
                max_output_mb=1,
                duration=5,
            )
        ),
    )
    monkeypatch.setattr(video_generation_module, 'get_video_provider', lambda _config: provider)
    monkeypatch.setattr(video_generation_module.Users, 'get_user_by_id', AsyncMock(return_value=SimpleNamespace(id='user-1')))
    monkeypatch.setattr(video_generation_module, '_download_video', download)
    monkeypatch.setattr(video_generation_module, '_attach_video', attach)
    monkeypatch.setattr(video_generation_module, '_settle_job_billing', settle)
    monkeypatch.setattr(video_generation_module, '_emit_job_event', AsyncMock())

    request = _Request()
    asyncio.run(video_generation_module._process_job(request, row))

    assert row.status == 'succeeded'
    assert row.progress == 100
    download.assert_not_awaited()
    attach.assert_awaited_once_with(request, row, 'file-existing', '/files/file-existing')
    settle.assert_awaited_once_with(row, 7)
