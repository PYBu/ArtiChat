from __future__ import annotations

import ast
import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

MAIN_PATH = Path(__file__).resolve().parents[2] / 'main.py'


def _load_process_chat(namespace):
    tree = ast.parse(MAIN_PATH.read_text(encoding='utf-8'))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'process_chat'
    )
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(MAIN_PATH), 'exec'), namespace)
    return namespace['process_chat']


@pytest.mark.asyncio
async def test_fanout_worker_gates_preparation_and_dispatch_and_owns_mcp_cleanup():
    events = []
    prepared_future = asyncio.get_running_loop().create_future()
    preparation_gate = asyncio.Event()
    dispatch_gate = asyncio.Event()
    provider_finished = False

    class FakeJSONResponse:
        pass

    class FakeMCPClient:
        def __init__(self):
            self.created_task = asyncio.current_task()
            self.disconnected_task = None

        async def disconnect(self):
            self.disconnected_task = asyncio.current_task()
            events.append('mcp_disconnected')
            assert provider_finished is True

    mcp_client = None

    async def process_chat_payload(_request, form_data, _user, metadata, _model):
        nonlocal mcp_client
        events.append('payload_started')
        mcp_client = FakeMCPClient()
        metadata['mcp_clients'] = {'server': mcp_client}
        form_data['metadata'] = metadata
        events.append('payload_finished')
        return form_data, metadata, []

    async def chat_completion_handler(_request, _form_data, _user):
        nonlocal provider_finished
        assert prepared_future.done() is True
        events.append('provider_started')
        provider_finished = True
        events.append('provider_finished')
        return object()

    async def build_chat_response_context(*_args, **_kwargs):
        return object()

    async def process_chat_response(_response, _context):
        events.append('response_processed')
        return 'completed'

    process_chat = _load_process_chat(
        {
            'asyncio': asyncio,
            'time': time,
            'JSONResponse': FakeJSONResponse,
            'process_chat_payload': process_chat_payload,
            'chat_completion_handler': chat_completion_handler,
            'build_chat_response_context': build_chat_response_context,
            'process_chat_response': process_chat_response,
        }
    )
    request = SimpleNamespace(state=SimpleNamespace(internal=False))
    metadata = {}
    worker = asyncio.create_task(
        process_chat(
            request,
            {'model': 'hosted'},
            SimpleNamespace(id='user-1'),
            metadata,
            {'id': 'hosted'},
            preparation_gate=preparation_gate,
            prepared_future=prepared_future,
            dispatch_gate=dispatch_gate,
        )
    )

    await asyncio.sleep(0)
    assert events == []
    assert prepared_future.done() is False
    assert worker.done() is False

    preparation_gate.set()
    prepared_payload = await asyncio.wait_for(asyncio.shield(prepared_future), timeout=1)

    assert prepared_payload[0]['model'] == 'hosted'
    assert events == ['payload_started', 'payload_finished']
    assert worker.done() is False

    dispatch_gate.set()
    result = await asyncio.wait_for(worker, timeout=1)

    assert result == 'completed'
    assert events == [
        'payload_started',
        'payload_finished',
        'provider_started',
        'provider_finished',
        'response_processed',
        'mcp_disconnected',
    ]
    assert mcp_client is not None
    assert mcp_client.created_task is worker
    assert mcp_client.disconnected_task is worker
