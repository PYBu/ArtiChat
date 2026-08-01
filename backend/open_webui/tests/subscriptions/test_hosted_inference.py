from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.responses import StreamingResponse
from open_webui.utils import hosted_inference
from open_webui.utils.subscriptions import ModelSubscriptionPolicy

CHAT_PATH = Path(__file__).resolve().parents[2] / 'utils' / 'chat.py'
MAIN_PATH = Path(__file__).resolve().parents[2] / 'main.py'
PAYLOAD_PATH = Path(__file__).resolve().parents[2] / 'utils' / 'payload.py'
MIDDLEWARE_PATH = Path(__file__).resolve().parents[2] / 'utils' / 'middleware.py'


def _load_ollama_payload_converter():
    source = PAYLOAD_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'convert_payload_openai_to_ollama'
    )
    namespace = {
        'json': __import__('json'),
        'convert_messages_openai_to_ollama': lambda messages: messages or [],
    }
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(PAYLOAD_PATH), 'exec'),
        namespace,
    )
    return namespace['convert_payload_openai_to_ollama']


def _load_connect_mcp_server(namespace):
    source = MIDDLEWARE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'connect_mcp_server'
    )
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(MIDDLEWARE_PATH), 'exec'),
        namespace,
    )
    return namespace['connect_mcp_server']


def _request(*, direct_model_id: str | None = None):
    state = SimpleNamespace(direct=direct_model_id is not None)
    if direct_model_id is not None:
        state.model = {'id': direct_model_id, 'direct': True}
    return SimpleNamespace(
        state=state,
        app=SimpleNamespace(state=SimpleNamespace(MODELS={'hosted': {'id': 'hosted'}})),
        headers={},
        client=None,
    )


def _user():
    return SimpleNamespace(id='user-1', role='user')


def _policy(price: str = '1') -> ModelSubscriptionPolicy:
    return ModelSubscriptionPolicy(
        quota_mode='metered',
        input_chatpoint_per_million=price,
        output_chatpoint_per_million=price,
    )


def _mock_access(monkeypatch, policy=None):
    policy = policy or _policy()

    async def ensure_subscription(_user_id):
        return SimpleNamespace(
            tier='free',
            plan_balance_micros=10_000_000,
            check_balance_micros=0,
        )

    async def assert_balance(*_args, **_kwargs):
        return None

    async def reserve(*_args, **_kwargs):
        return SimpleNamespace(
            acquired=True,
            reservation=SimpleNamespace(id='reservation-1'),
        )

    monkeypatch.setattr(hosted_inference, 'ensure_subscription_current', ensure_subscription)
    monkeypatch.setattr(hosted_inference, 'assert_chatpoint_available', assert_balance)
    monkeypatch.setattr(hosted_inference, 'assert_model_subscription_access', lambda *_args, **_kwargs: policy)
    monkeypatch.setattr(hosted_inference, 'reserve_chatpoints', reserve)
    monkeypatch.setattr(hosted_inference, '_start_reservation_heartbeat', lambda _reservation_id: None)
    return policy


@pytest.mark.asyncio
async def test_child_inference_gets_an_independent_request_id(monkeypatch):
    _mock_access(monkeypatch)
    payload = {
        'model': 'hosted',
        'stream': True,
        'metadata': {'request_id': 'parent-request', 'task': 'title_generation'},
    }

    context = await hosted_inference.prepare_hosted_inference(
        _request(),
        payload,
        _user(),
        new_child_request=True,
    )

    assert context is not None
    assert context.metadata['request_id'] != 'parent-request'
    assert context.metadata['parent_request_id'] == 'parent-request'
    assert context.metadata[hosted_inference.INTERNAL_BILLING_MARKER] is True
    assert context.metadata[hosted_inference.HOSTED_POLICY_MODEL_ID] == 'hosted'
    assert payload['stream_options']['include_usage'] is True


@pytest.mark.asyncio
async def test_byok_model_never_receives_a_hosted_policy(monkeypatch):
    async def should_not_load_subscription(_user_id):
        raise AssertionError('BYOK must not load a hosted subscription')

    monkeypatch.setattr(hosted_inference, 'ensure_subscription_current', should_not_load_subscription)
    payload = {
        'model': 'byok',
        'metadata': {'subscription_policy': {'quota_mode': 'unlimited'}},
    }

    context = await hosted_inference.prepare_hosted_inference(
        _request(direct_model_id='byok'),
        payload,
        _user(),
        new_child_request=True,
    )

    assert context is None
    assert payload['metadata']['billing_mode'] == 'byok'
    assert 'subscription_policy' not in payload['metadata']


@pytest.mark.asyncio
async def test_non_streaming_internal_completion_is_billed_with_sanitized_metadata(monkeypatch):
    _mock_access(monkeypatch)
    calls = []

    async def bill(**kwargs):
        calls.append(kwargs)

    async def generate(request, form_data, user):
        assert form_data['metadata']['request_id'] != 'parent-request'
        await hosted_inference.prepare_hosted_inference(
            request,
            form_data,
            user,
            new_child_request=False,
        )
        return {'choices': [{'message': {'content': 'done'}}], 'usage': {'prompt_tokens': 4, 'completion_tokens': 2}}

    monkeypatch.setattr(hosted_inference, 'bill_model_usage', bill)
    monkeypatch.setitem(
        sys.modules,
        'open_webui.utils.chat',
        SimpleNamespace(generate_chat_completion=generate),
    )
    payload = {
        'model': 'hosted',
        'metadata': {
            'request_id': 'parent-request',
            'task': 'memory_review',
            'task_body': {'messages': ['private prompt']},
        },
    }

    response = await hosted_inference.generate_billed_chat_completion(_request(), payload, _user())

    assert response['choices'][0]['message']['content'] == 'done'
    assert len(calls) == 1
    assert calls[0]['model_id'] == 'hosted'
    assert calls[0]['metadata']['parent_request_id'] == 'parent-request'
    assert calls[0]['metadata']['task'] == 'memory_review'
    assert 'task_body' not in calls[0]['metadata']
    assert calls[0]['usage']['input_tokens'] == 4
    assert calls[0]['usage']['output_tokens'] == 2
    assert calls[0]['reservation_id'] == 'reservation-1'
    assert hosted_inference.RESERVATION_ID not in payload['metadata']


@pytest.mark.asyncio
async def test_streaming_internal_completion_bills_on_completion(monkeypatch):
    _mock_access(monkeypatch)
    calls = []

    async def bill(**kwargs):
        calls.append(kwargs)

    async def generate(request, form_data, user):
        await hosted_inference.prepare_hosted_inference(
            request,
            form_data,
            user,
            new_child_request=False,
        )

        async def chunks():
            yield 'data: {"choices":[{"delta":{"content":"done"}}]}\n\n'
            yield 'data: {"usage":{"prompt_tokens":3,"completion_tokens":1}}\n\n'

        return StreamingResponse(chunks(), media_type='text/event-stream')

    def update_usage(message, chunk):
        if '"usage"' in chunk:
            message['usage'] = {'prompt_tokens': 3, 'completion_tokens': 1}

    monkeypatch.setattr(hosted_inference, 'bill_model_usage', bill)
    monkeypatch.setitem(
        sys.modules,
        'open_webui.utils.chat',
        SimpleNamespace(generate_chat_completion=generate),
    )
    monkeypatch.setitem(
        sys.modules,
        'open_webui.utils.middleware',
        SimpleNamespace(update_assistant_message_from_stream=update_usage),
    )

    response = await hosted_inference.generate_billed_chat_completion(
        _request(),
        {'model': 'hosted', 'stream': True, 'metadata': {'task': 'moa'}},
        _user(),
    )
    chunks = [chunk async for chunk in response.body_iterator]

    assert len(chunks) == 2
    assert len(calls) == 1
    assert calls[0]['usage']['prompt_tokens'] == 3
    assert calls[0]['metadata']['billing_completion_status'] == 'completed'
    assert calls[0]['reservation_id'] == 'reservation-1'


def test_stream_content_detection_ignores_usage_only_events():
    assert hosted_inference._stream_chunk_has_content('data: {"usage":{"total_tokens":4}}\n\n') is False
    assert hosted_inference._stream_chunk_has_content('data: {"choices":[{"delta":{"content":"done"}}]}\n\n') is True


def test_conflicting_output_limit_aliases_are_all_clamped_to_the_safest_value():
    payload = {
        'model': 'hosted',
        'max_tokens': 12,
        'max_completion_tokens': 500,
        'max_output_tokens': 900,
        'options': {'num_predict': -1, 'max_tokens': 1000},
    }

    quote = hosted_inference._quote_hosted_chatpoints(
        payload,
        _policy().model_dump(),
        available_micros=10_000_000,
    )

    assert quote.output_tokens == 12
    assert payload['max_tokens'] == 12
    assert payload['max_completion_tokens'] == 12
    assert payload['max_output_tokens'] == 12
    assert payload['options']['num_predict'] == 12
    assert payload['options']['max_tokens'] == 12


def test_fanout_quote_reserves_all_inputs_before_sharing_output_budget():
    payloads = [
        {'model': 'model-a', 'messages': [{'role': 'user', 'content': 'a'}], 'max_tokens': 1000},
        {'model': 'model-b', 'messages': [{'role': 'user', 'content': 'b'}], 'max_tokens': 1000},
    ]
    input_budget = sum(hosted_inference.estimate_hosted_input_tokens(payload) for payload in payloads)

    quotes = hosted_inference._quote_hosted_chatpoint_batch(
        payloads,
        [_policy().model_dump(), _policy().model_dump()],
        available_micros=input_budget + 200,
    )

    assert sum(quote.amount_micros for quote in quotes) <= input_budget + 200
    assert quotes[0].output_tokens > 0
    assert quotes[1].output_tokens > 0
    assert abs(quotes[0].output_tokens - quotes[1].output_tokens) <= 1
    assert payloads[0]['max_tokens'] == quotes[0].output_tokens
    assert payloads[1]['max_tokens'] == quotes[1].output_tokens


@pytest.mark.asyncio
async def test_fanout_batch_reserves_once_and_first_dispatch_reuses_each_hold(monkeypatch):
    policy = _mock_access(monkeypatch)
    request = _request()
    request.app.state.MODELS = {
        'model-a': {'id': 'model-a'},
        'model-b': {'id': 'model-b'},
    }
    batch_calls = []

    async def reserve_batch(user_id, requests):
        batch_calls.append((user_id, requests))
        return [
            SimpleNamespace(reservation=SimpleNamespace(id=f'reservation-{index}'), acquired=True)
            for index, _request_item in enumerate(requests, start=1)
        ]

    async def unexpected_reserve(*_args, **_kwargs):
        raise AssertionError('prepared dispatch must not reserve twice')

    async def unexpected_extend(*_args, **_kwargs):
        raise AssertionError('first prepared dispatch must not extend its hold')

    monkeypatch.setattr(hosted_inference, 'reserve_chatpoint_batch', reserve_batch)
    monkeypatch.setattr(hosted_inference, 'reserve_chatpoints', unexpected_reserve)
    monkeypatch.setattr(hosted_inference, 'extend_chatpoint_reservation', unexpected_extend)
    payloads = [
        {'model': 'model-a', 'metadata': {'request_id': 'request-a'}},
        {'model': 'model-b', 'metadata': {'request_id': 'request-b'}},
    ]

    await hosted_inference.prepare_hosted_inference_batch(request, payloads, _user())

    assert len(batch_calls) == 1
    assert [item['model_id'] for item in batch_calls[0][1]] == ['model-a', 'model-b']
    for index, payload in enumerate(payloads, start=1):
        assert payload['metadata'][hosted_inference.RESERVATION_ID] == f'reservation-{index}'
        assert payload['metadata'][hosted_inference.RESERVATION_PREPARED_DISPATCH] is True
        context = await hosted_inference.prepare_hosted_inference(
            request,
            payload,
            _user(),
            new_child_request=False,
        )
        assert context.policy == policy.model_dump()
        assert hosted_inference.RESERVATION_PREPARED_DISPATCH not in payload['metadata']


@pytest.mark.asyncio
async def test_fanout_batch_failure_leaves_no_partial_reservation_metadata(monkeypatch):
    _mock_access(monkeypatch)
    request = _request()
    request.app.state.MODELS = {
        'model-a': {'id': 'model-a'},
        'model-b': {'id': 'model-b'},
    }
    payloads = [
        {'model': 'model-a', 'metadata': {'request_id': 'request-a'}},
        {'model': 'model-b', 'metadata': {'request_id': 'request-b'}},
    ]

    async def reject_batch(*_args, **_kwargs):
        raise PermissionError('insufficient batch balance')

    monkeypatch.setattr(hosted_inference, 'reserve_chatpoint_batch', reject_batch)

    with pytest.raises(PermissionError, match='insufficient batch balance'):
        await hosted_inference.prepare_hosted_inference_batch(request, payloads, _user())

    assert all(hosted_inference.RESERVATION_ID not in payload['metadata'] for payload in payloads)
    assert all(
        hosted_inference.RESERVATION_PREPARED_DISPATCH not in payload['metadata'] for payload in payloads
    )


@pytest.mark.asyncio
async def test_fanout_reconciliation_resizes_every_prepared_hold_once(monkeypatch):
    _mock_access(monkeypatch)
    request = _request()
    request.app.state.MODELS = {
        'model-a': {'id': 'model-a'},
        'model-b': {'id': 'model-b'},
    }
    payloads = [
        {
            'model': 'model-a',
            'messages': [{'role': 'user', 'content': 'final a'}],
            'metadata': {
                'request_id': 'request-a',
                hosted_inference.RESERVATION_ID: 'reservation-a',
                hosted_inference.RESERVATION_AMOUNT_MICROS: 100,
            },
        },
        {
            'model': 'model-b',
            'messages': [{'role': 'user', 'content': 'final b'}],
            'metadata': {
                'request_id': 'request-b',
                hosted_inference.RESERVATION_ID: 'reservation-b',
                hosted_inference.RESERVATION_AMOUNT_MICROS: 100,
            },
        },
    ]
    calls = []

    async def resize(user_id, requests):
        calls.append((user_id, requests))
        return []

    monkeypatch.setattr(hosted_inference, 'resize_chatpoint_reservation_batch', resize)

    await hosted_inference.reconcile_hosted_inference_batch(request, payloads, _user())

    assert len(calls) == 1
    resize_requests = calls[0][1]
    assert [item['reservation_id'] for item in resize_requests] == ['reservation-a', 'reservation-b']
    assert [item['request_id'] for item in resize_requests] == ['request-a', 'request-b']
    assert [item['model_id'] for item in resize_requests] == ['model-a', 'model-b']
    assert [
        payload['metadata'][hosted_inference.RESERVATION_AMOUNT_MICROS] for payload in payloads
    ] == [item['amount_micros'] for item in resize_requests]
    assert all(
        payload['metadata'][hosted_inference.RESERVATION_PREPARED_DISPATCH] is True for payload in payloads
    )


def test_main_prepares_and_reserves_fanout_before_opening_dispatch_gate():
    source = MAIN_PATH.read_text(encoding='utf-8')
    fanout_start = source.index('    # Fan out: reserve every target first')
    fanout = source[fanout_start : source.index('\n    else:', fanout_start)]

    arena_position = fanout.index('await resolve_arena_model(')
    reservation_position = fanout.index('await prepare_hosted_inference_batch(')
    internal_payload_position = fanout.index('prepared_payload = await process_chat_payload(')
    attempted_position = fanout.index("attempted_task_ids.append(item['metadata']['task_id'])")
    task_position = fanout.index('task_id, local_task = await create_task(')
    preparation_gate_position = fanout.index('preparation_gate.set()')
    preparation_gather_position = fanout.index('prepared_payloads = await asyncio.gather(')
    reconciliation_position = fanout.index(
        'await reconcile_hosted_inference_batch(', preparation_gather_position
    )
    active_event_position = fanout.index("'type': 'chat:active'")
    dispatch_gate_position = fanout.index('dispatch_gate.set()')
    title_position = fanout.index(
        'asyncio.create_task(deferred_title_generation())', dispatch_gate_position
    )

    assert (
        arena_position
        < reservation_position
        < internal_payload_position
    )
    assert (
        reservation_position
        < attempted_position
        < task_position
        < preparation_gate_position
        < preparation_gather_position
        < reconciliation_position
        < active_event_position
        < dispatch_gate_position
        < title_position
    )

    worker_start = source.index('    async def process_chat(')
    worker = source[worker_start:fanout_start]
    preparation_wait_position = worker.index('await preparation_gate.wait()')
    payload_position = worker.index('prepared_payload = await process_chat_payload(')
    prepared_position = worker.index('prepared_future.set_result(prepared_payload)')
    worker_dispatch_position = worker.index('await dispatch_gate.wait()')
    provider_position = worker.index('response = await chat_completion_handler(')

    assert (
        preparation_wait_position
        < payload_position
        < prepared_position
        < worker_dispatch_position
        < provider_position
    )

    cleanup_start = fanout.index('        async def cancel_local_fanout_tasks():')
    cleanup_end = fanout.index('\n        try:', cleanup_start)
    cleanup = fanout[cleanup_start:cleanup_end]
    assert cleanup.index('task.cancel()') < cleanup.index('await asyncio.gather(')
    assert cleanup.index('await asyncio.gather(') < cleanup.index('for task_id in attempted_task_ids:')


def test_no_session_chat_runs_deferred_title_exactly_once_after_chat_processing():
    source = MAIN_PATH.read_text(encoding='utf-8')
    branch_start = source.index('    else:\n        # Legacy/direct: single model, synchronous')
    branch_end = source.index('\n\n\n# Alias for chat_completion', branch_start)
    branch = source[branch_start:branch_end]

    process_position = branch.index('response = await process_chat(')
    title_position = branch.index('asyncio.create_task(deferred_title_generation())')
    return_position = branch.index('return response')

    assert process_position < title_position < return_position
    assert branch.count('asyncio.create_task(deferred_title_generation())') == 1


@pytest.mark.asyncio
async def test_failed_mcp_tool_discovery_disconnects_the_connected_client():
    calls = []

    class Config:
        @staticmethod
        async def get(_key, _default):
            return [{'type': 'mcp', 'info': {'id': 'server-1'}, 'url': 'https://mcp.invalid'}]

    class Client:
        async def connect(self, **_kwargs):
            calls.append('connect')

        async def list_tool_specs(self):
            calls.append('list')
            raise RuntimeError('tool discovery failed')

        async def disconnect(self):
            calls.append('disconnect')

    async def allow_access(_user, _connection):
        return True

    async def build_headers(*_args, **_kwargs):
        return {}, None

    connect_mcp_server = _load_connect_mcp_server(
        {
            'Config': Config,
            'MCPClient': Client,
            'has_connection_access': allow_access,
            'build_tool_server_headers': build_headers,
            'is_string_allowed': lambda *_args: True,
            'log': logging.getLogger(__name__),
        }
    )

    with pytest.raises(RuntimeError, match='tool discovery failed'):
        await connect_mcp_server(
            SimpleNamespace(),
            'server-1',
            SimpleNamespace(id='user-1'),
            {},
            {},
        )

    assert calls == ['connect', 'list', 'disconnect']


def test_mcp_client_is_registered_before_tool_processing_can_fail():
    source = MIDDLEWARE_PATH.read_text(encoding='utf-8')
    start = source.index('async def process_chat_payload(')
    end = source.index('\nasync def process_chat_response(', start)
    payload_source = source[start:end]

    register_position = payload_source.index("metadata['mcp_clients'] = mcp_clients")
    tool_loop_position = payload_source.index('for tool_spec in tool_specs:')
    assert register_position < tool_loop_position


@pytest.mark.parametrize(
    'limits',
    [
        {},
        {'max_tokens': 128},
        {'max_output_tokens': 256},
        {'options': {'num_predict': 512}},
        {'max_tokens': 64, 'options': {'num_predict': 4096}},
    ],
)
def test_final_ollama_payload_uses_the_reserved_output_limit(limits):
    payload = {'model': 'hosted', 'messages': [], **limits}
    quote = hosted_inference._quote_hosted_chatpoints(
        payload,
        _policy().model_dump(),
        available_micros=10_000_000,
    )

    ollama_payload = _load_ollama_payload_converter()(payload)

    assert ollama_payload['options']['num_predict'] == quote.output_tokens
    assert 'num_predict' not in {key for key in ollama_payload if key != 'options'}


def test_ollama_payload_maps_nested_options_without_a_top_level_limit():
    payload = {
        'model': 'hosted',
        'messages': [],
        'options': {
            'max_tokens': 321,
            'format': '{"type":"object"}',
            'keep_alive': '60',
            'think': True,
            'system': 'system prompt',
        },
    }

    ollama_payload = _load_ollama_payload_converter()(payload)

    assert ollama_payload['options'] == {'num_predict': 321}
    assert ollama_payload['format'] == {'type': 'object'}
    assert ollama_payload['keep_alive'] == 60
    assert ollama_payload['think'] is True
    assert ollama_payload['system'] == 'system prompt'


def test_ollama_payload_uses_the_safest_conflicting_output_limit():
    ollama_payload = _load_ollama_payload_converter()(
        {
            'model': 'hosted',
            'messages': [],
            'max_tokens': 12,
            'options': {'max_tokens': 900, 'num_predict': 500},
        }
    )

    assert ollama_payload['options']['num_predict'] == 12
    assert 'max_tokens' not in ollama_payload['options']


@pytest.mark.asyncio
async def test_each_provider_continuation_extends_the_existing_reservation(monkeypatch):
    _mock_access(monkeypatch)
    extensions = []

    async def extend(reservation_id, **kwargs):
        extensions.append((reservation_id, kwargs))
        return SimpleNamespace(id=reservation_id)

    monkeypatch.setattr(hosted_inference, 'extend_chatpoint_reservation', extend)
    payload = {'model': 'hosted', 'metadata': {'request_id': 'request-1'}}

    await hosted_inference.prepare_hosted_inference(
        _request(),
        payload,
        _user(),
        new_child_request=False,
    )
    first_input_estimate = payload['metadata'][hosted_inference.RESERVATION_INPUT_TOKENS]
    first_reserved_amount = payload['metadata'][hosted_inference.RESERVATION_AMOUNT_MICROS]
    await hosted_inference.prepare_hosted_inference(
        _request(),
        payload,
        _user(),
        new_child_request=False,
    )

    assert len(extensions) == 1
    assert extensions[0][0] == 'reservation-1'
    assert extensions[0][1]['amount_micros'] > 0
    assert payload['metadata'][hosted_inference.RESERVATION_INPUT_TOKENS] > first_input_estimate
    assert (
        payload['metadata'][hosted_inference.RESERVATION_AMOUNT_MICROS]
        == first_reserved_amount + extensions[0][1]['amount_micros']
    )


@pytest.mark.asyncio
async def test_reservation_heartbeat_retries_after_a_transient_failure(monkeypatch):
    attempts = []

    async def no_wait(_seconds):
        return None

    async def renew(reservation_id, **_kwargs):
        attempts.append(reservation_id)
        if len(attempts) == 1:
            raise RuntimeError('temporary database error')
        raise hosted_inference.ChatpointReservationConflictError('reservation is terminal')

    monkeypatch.setattr(hosted_inference.asyncio, 'sleep', no_wait)
    monkeypatch.setattr(hosted_inference, 'renew_chatpoint_reservation', renew)

    await hosted_inference._reservation_heartbeat('reservation-retry')

    assert attempts == ['reservation-retry', 'reservation-retry']


@pytest.mark.asyncio
async def test_internal_completion_fails_closed_without_hosted_policy(monkeypatch):
    async def generate(request, form_data, user):
        return {'choices': [{'message': {'content': 'untracked'}}]}

    monkeypatch.setitem(
        sys.modules,
        'open_webui.utils.chat',
        SimpleNamespace(generate_chat_completion=generate),
    )

    with pytest.raises(RuntimeError, match='billing context is missing'):
        await hosted_inference.generate_billed_chat_completion(
            _request(),
            {'model': 'hosted', 'metadata': {}},
            _user(),
        )


def test_resolved_context_uses_the_actual_arena_child_policy():
    metadata = {
        hosted_inference.HOSTED_POLICY_MODEL_ID: 'premium-child',
        'subscription_policy': {'quota_mode': 'metered', 'output_chatpoint_per_million': '9'},
    }
    wrapper = hosted_inference.HostedInferenceContext(
        request=_request(),
        user=_user(),
        model_id='arena-wrapper',
        policy={'quota_mode': 'unlimited'},
        metadata=metadata,
        started_at=1.0,
    )

    resolved = hosted_inference._resolved_context(wrapper)

    assert resolved.model_id == 'premium-child'
    assert resolved.policy['output_chatpoint_per_million'] == '9'


def test_new_child_request_drops_an_inherited_parent_reservation():
    payload = {
        'metadata': {
            'request_id': 'parent-request',
            hosted_inference.RESERVATION_ID: 'parent-reservation',
            hosted_inference.RESERVATION_INPUT_TOKENS: 100,
            hosted_inference.RESERVATION_OUTPUT_TOKENS: 200,
        }
    }

    metadata = hosted_inference._ensure_child_request_metadata(payload)

    assert metadata['parent_request_id'] == 'parent-request'
    assert hosted_inference.RESERVATION_ID not in metadata
    assert hosted_inference.RESERVATION_INPUT_TOKENS not in metadata
    assert hosted_inference.RESERVATION_OUTPUT_TOKENS not in metadata


def test_chat_metadata_merge_preserves_the_callers_object_identity():
    source = CHAT_PATH.read_text(encoding='utf-8')

    assert 'form_metadata.clear()' in source
    assert 'form_metadata.update(merged_metadata)' in source
    assert "form_data['metadata'] = form_metadata" in source


@pytest.mark.asyncio
async def test_non_billable_internal_response_releases_the_reservation(monkeypatch):
    _mock_access(monkeypatch)
    releases = []

    async def release(reservation_id, *, reason):
        releases.append((reservation_id, reason))

    async def generate(request, form_data, user):
        await hosted_inference.prepare_hosted_inference(
            request,
            form_data,
            user,
            new_child_request=False,
        )
        return {'error': {'message': 'rejected'}}

    monkeypatch.setattr(hosted_inference, 'release_chatpoint_reservation', release)
    monkeypatch.setitem(
        sys.modules,
        'open_webui.utils.chat',
        SimpleNamespace(generate_chat_completion=generate),
    )
    payload = {'model': 'hosted', 'metadata': {}}

    await hosted_inference.generate_billed_chat_completion(_request(), payload, _user())

    assert releases == [('reservation-1', 'internal inference returned a non-billable response')]
    assert hosted_inference.RESERVATION_ID not in payload['metadata']


@pytest.mark.asyncio
async def test_streaming_internal_error_releases_without_billing(monkeypatch):
    _mock_access(monkeypatch)
    releases = []
    bills = []

    async def release(reservation_id, *, reason):
        releases.append((reservation_id, reason))

    async def bill(**kwargs):
        bills.append(kwargs)

    async def generate(request, form_data, user):
        await hosted_inference.prepare_hosted_inference(
            request,
            form_data,
            user,
            new_child_request=False,
        )

        async def chunks():
            yield 'data: {"error":{"message":"rejected"}}\n\n'

        return StreamingResponse(
            chunks(),
            status_code=429,
            media_type='text/event-stream',
        )

    monkeypatch.setattr(hosted_inference, 'release_chatpoint_reservation', release)
    monkeypatch.setattr(hosted_inference, 'bill_model_usage', bill)
    monkeypatch.setitem(
        sys.modules,
        'open_webui.utils.chat',
        SimpleNamespace(generate_chat_completion=generate),
    )
    payload = {'model': 'hosted', 'stream': True, 'metadata': {}}

    response = await hosted_inference.generate_billed_chat_completion(_request(), payload, _user())

    assert response.status_code == 429
    assert releases == [('reservation-1', 'internal inference returned an error response')]
    assert bills == []
