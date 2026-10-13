import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest

from open_webui.retrieval import utils
from open_webui.retrieval.web import utils as web_utils
from open_webui.routers.folders import validate_folder_parent_id
from open_webui.utils import tools as tool_utils


class FakeResponse:
    headers = {'Content-Type': 'application/pdf'}

    def __init__(self, chunks):
        self.chunks = chunks

    def iter_content(self, _chunk_size):
        yield from self.chunks


def test_binary_download_is_streamed_and_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    monkeypatch.setattr(utils, 'build_loader_from_config', lambda *_args: pytest.fail('oversized input must stop before extraction'))

    with pytest.raises(ValueError, match='too large'):
        utils._extract_text_from_binary_response(
            None,
            FakeResponse([b'a' * (1024 * 1024), b'b']),
            'https://example.com/file.pdf',
            {'file_max_size': 1},
        )

    assert list(Path(tmp_path).iterdir()) == []


def test_address_filter_rejects_private_and_ipv4_mapped_targets(monkeypatch):
    monkeypatch.setattr(web_utils, 'ENABLE_LOCAL_WEB_FETCH', False)

    with pytest.raises(ValueError):
        web_utils._assert_addresses_allowed(['127.0.0.1'])

    with pytest.raises(ValueError):
        web_utils._assert_addresses_allowed(['::ffff:127.0.0.1'])


def test_ssrf_connector_rechecks_connect_time_dns_result(monkeypatch):
    async def fake_resolve(_self, _host, _port, traces=None):
        return [{'host': '127.0.0.1'}]

    monkeypatch.setattr(web_utils, 'ENABLE_LOCAL_WEB_FETCH', False)
    monkeypatch.setattr(web_utils.aiohttp.TCPConnector, '_resolve_host', fake_resolve)

    async def run():
        connector = web_utils._SSRFSafeConnector()
        try:
            with pytest.raises(ValueError):
                await connector._resolve_host('public.example', 443)
        finally:
            await connector.close()

    asyncio.run(run())


def test_filter_list_supports_cidr_ranges():
    assert web_utils.is_host_blocked('10.2.3.4', ['!10.0.0.0/8'])
    assert not web_utils.is_host_blocked('11.2.3.4', ['!10.0.0.0/8'])


def test_folder_parent_validation_rejects_subtree_cycles():
    with pytest.raises(ValueError, match='subtree'):
        validate_folder_parent_id('root', 'child', {'root', 'child'})

    validate_folder_parent_id('root', None, {'root', 'child'})


class FakeToolContent:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_chunked(self, _chunk_size):
        for chunk in self.chunks:
            yield chunk


def test_tool_server_spec_response_is_bounded():
    async def run():
        response = SimpleNamespace(
            headers={},
            content=FakeToolContent([b'{"ok":', b'true}']),
        )
        assert await tool_utils._read_tool_server_response_bounded(response, 32) == b'{"ok":true}'

        oversized = SimpleNamespace(
            headers={},
            content=FakeToolContent([b'a' * 33]),
        )
        with pytest.raises(ValueError, match='too large'):
            await tool_utils._read_tool_server_response_bounded(oversized, 32)

        declared_oversized = SimpleNamespace(
            headers={'Content-Length': '33'},
            content=FakeToolContent([]),
        )
        with pytest.raises(ValueError, match='too large'):
            await tool_utils._read_tool_server_response_bounded(declared_oversized, 32)

    asyncio.run(run())


def test_tool_server_bearer_headers_are_normalized_and_cookies_are_opt_in():
    async def run():
        request = SimpleNamespace(
            cookies={'session': 'secret'},
            state=SimpleNamespace(token=SimpleNamespace(credentials='  session-token  ')),
        )
        user = SimpleNamespace(id='user-1')

        headers, cookies = await tool_utils.build_tool_server_headers(
            {'auth_type': 'bearer', 'key': '  api-token  '}, request, user
        )
        assert headers['Authorization'] == 'Bearer api-token'
        assert cookies == {}

        headers, cookies = await tool_utils.build_tool_server_headers(
            {'auth_type': 'session'}, request, user
        )
        assert headers['Authorization'] == 'Bearer session-token'
        assert cookies == {}

        _, cookies = await tool_utils.build_tool_server_headers(
            {'auth_type': 'session', 'forward_cookies': True}, request, user
        )
        assert cookies == request.cookies

    asyncio.run(run())


def test_playwright_redirect_to_blocked_target_is_aborted(monkeypatch):
    class Headers(dict):
        def getall(self, _name, default=None):
            return default or []

    class Route:
        request = None

        async def abort(self):
            self.aborted = True

        async def fulfill(self, **_kwargs):
            self.fulfilled = True

    async def all_headers():
        return {}

    Route.request = SimpleNamespace(
        url='https://public.example/start',
        method='GET',
        post_data_buffer=None,
        all_headers=all_headers,
    )

    calls = []

    def validate(url):
        calls.append(url)
        if '127.0.0.1' in url:
            raise ValueError('blocked')
        return True

    monkeypatch.setattr(web_utils, 'validate_url', validate)
    monkeypatch.setattr(web_utils, 'AIOHTTP_CLIENT_ALLOW_REDIRECTS', True)

    async def run_in_threadpool(fn, *args):
        return fn(*args)

    monkeypatch.setattr(web_utils, 'run_in_threadpool', run_in_threadpool)

    class Session:
        async def request(self, method, url, **_kwargs):
            assert method == 'GET'
            return SimpleNamespace(
                status=302,
                headers=Headers(location='http://127.0.0.1/private'),
                url=url,
                read=lambda: asyncio.sleep(0),
            )

    loader = object.__new__(web_utils.SafePlaywrightURLLoader)
    loader.verify_ssl = True
    loader.playwright_timeout = 1000
    loader._requests_verify = lambda: False
    route = Route()
    asyncio.run(loader._intercept_navigation(route, Session()))

    assert calls == ['https://public.example/start', 'http://127.0.0.1/private']
    assert getattr(route, 'aborted', False)
    assert not getattr(route, 'fulfilled', False)
