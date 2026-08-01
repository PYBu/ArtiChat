import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

MIDDLEWARE_PATH = Path(__file__).resolve().parents[2] / 'utils' / 'middleware.py'


def _middleware_source_and_tree():
    source = MIDDLEWARE_PATH.read_text(encoding='utf-8')
    return source, ast.parse(source)


def _top_level_function(name: str):
    source, tree = _middleware_source_and_tree()
    function = next(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    return source, function


def _load_top_level_function(name: str, namespace: dict | None = None):
    _, function = _top_level_function(name)
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    globals_dict = dict(namespace or {})
    exec(compile(module, str(MIDDLEWARE_PATH), 'exec'), globals_dict)
    return globals_dict[name]


def _call_names(node: ast.AST) -> set[str]:
    names = set()
    for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
        if isinstance(call.func, ast.Name):
            names.add(call.func.id)
        elif isinstance(call.func, ast.Attribute):
            names.add(call.func.attr)
    return names


def test_non_streaming_success_detection_includes_tool_and_responses_outputs():
    is_billable = _load_top_level_function('non_streaming_response_is_billable')

    assert is_billable(
        {
            'choices': [
                {
                    'message': {
                        'content': None,
                        'tool_calls': [{'id': 'call-1', 'type': 'function'}],
                    }
                }
            ]
        }
    )
    assert is_billable(
        {
            'status': 'completed',
            'output': [{'id': 'call-1', 'type': 'function_call'}],
        }
    )
    assert is_billable({'usage': {'input_tokens': 12, 'output_tokens': 0}})
    assert not is_billable({'error': {'message': 'provider rejected request'}, 'usage': {'input_tokens': 12}})
    assert not is_billable({'status': 'failed', 'usage': {'input_tokens': 12}})
    assert not is_billable({})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'response_data',
    [
        {
            'choices': [
                {
                    'message': {
                        'content': None,
                        'tool_calls': [{'id': 'call-1', 'type': 'function'}],
                    }
                }
            ],
            'usage': {'input_tokens': 10, 'output_tokens': 3},
        },
        {
            'status': 'completed',
            'output': [{'id': 'call-1', 'type': 'function_call'}],
            'usage': {'input_tokens': 20, 'output_tokens': 4},
        },
    ],
)
async def test_non_streaming_handler_bills_success_without_text(response_data):
    billed = []
    is_billable = _load_top_level_function('non_streaming_response_is_billable')

    async def bill_once(ctx, usage):
        billed.append(usage)

    handler = _load_top_level_function(
        'non_streaming_chat_response_handler',
        {
            'get_response_data': lambda response: (response, response),
            'normalize_usage': lambda usage: dict(usage),
            'non_streaming_response_is_billable': is_billable,
            'bill_subscription_usage_once': bill_once,
            'is_saved_chat_id': lambda chat_id: False,
            'ENABLE_API_OUTLET_FILTERS': False,
            'merge_events_into_response': lambda response, events: response,
        },
    )
    ctx = {
        'request': SimpleNamespace(state=SimpleNamespace(internal=False)),
        'user': SimpleNamespace(id='user-1'),
        'metadata': {'chat_id': ''},
        'events': [],
        'event_emitter': None,
    }

    result = await handler(response_data, ctx)

    assert result == response_data
    assert billed == [response_data['usage']]


@pytest.mark.asyncio
async def test_billing_helper_records_completion_audit_and_only_runs_once():
    calls = []

    async def fake_bill_model_usage(**kwargs):
        calls.append(kwargs)

    bill_once = _load_top_level_function(
        'bill_subscription_usage_once',
        {
            'time': SimpleNamespace(perf_counter=lambda: 2.0),
            'bill_model_usage': fake_bill_model_usage,
            'get_request_client_ip': lambda request: '192.0.2.1',
        },
    )
    ctx = {
        'metadata': {
            'request_id': 'request-1',
            'chat_id': 'chat-1',
            'user_prompt': 'must not be persisted',
            'system_prompt': 'must not be persisted',
            'files': [{'name': 'private.txt'}],
            'subscription_policy': {
                'quota_mode': 'metered',
                'usage_multiplier': '1',
            },
            '_artichat_chatpoint_reservation_id': 'reservation-1',
        },
        'user': SimpleNamespace(id='user-1', role='user'),
        'form_data': {'model': 'model-1'},
        'model': {'id': 'fallback-model'},
        'request': object(),
        'request_started_at': 1.0,
        'first_content_at': 1.25,
    }

    await bill_once(
        ctx,
        {'input_tokens': 10, 'output_tokens': 2},
        completion_status='stream_interrupted',
    )
    await bill_once(ctx, {'input_tokens': 999})

    assert len(calls) == 1
    assert calls[0]['metadata']['billing_completion_status'] == 'stream_interrupted'
    assert calls[0]['metadata']['billing_usage_observed'] is True
    assert calls[0]['metadata']['chat_id'] == 'chat-1'
    assert 'user_prompt' not in calls[0]['metadata']
    assert 'system_prompt' not in calls[0]['metadata']
    assert 'files' not in calls[0]['metadata']
    assert 'subscription_policy' not in calls[0]['metadata']
    assert calls[0]['request_id'] == 'request-1'
    assert calls[0]['first_token_latency_ms'] == 250
    assert calls[0]['total_duration_ms'] == 1000
    assert calls[0]['reservation_id'] == 'reservation-1'
    assert calls[0]['allow_partial_reservation'] is True
    assert calls[0]['charge_reserved_on_missing_usage'] is True
    assert '_artichat_chatpoint_reservation_id' not in ctx['metadata']
    assert ctx['subscription_usage_billed'] is True


def _load_fallback_stream_handler(billed, interrupted):
    class FakeStreamingResponse:
        def __init__(self, body_iterator, headers=None, background=None):
            self.body_iterator = body_iterator
            self.headers = headers or {'Content-Type': 'text/event-stream'}
            self.background = background

    async def process_filter_functions(**kwargs):
        return kwargs['form_data'], None

    def track_usage(message, raw):
        if raw == b'usage':
            message['usage'] = {'input_tokens': 8, 'output_tokens': 2}

    async def bill_once(ctx, usage):
        billed.append(usage)

    async def audit_interrupted(ctx, usage):
        interrupted.append(usage)

    handler = _load_top_level_function(
        'streaming_chat_response_handler',
        {
            'UserModel': type('UserModel', (), {}),
            'is_saved_chat_id': lambda chat_id: False,
            'get_system_oauth_token': lambda request, user: asyncio.sleep(0, result=None),
            'ENABLE_PLUGINS': False,
            'FilterContext': type('FilterContext', (), {}),
            'ENABLE_API_OUTLET_FILTERS': False,
            'process_filter_functions': process_filter_functions,
            'update_assistant_message_from_stream': track_usage,
            'stream_event_has_content': lambda data: False,
            'bill_subscription_usage_once': bill_once,
            'audit_interrupted_subscription_usage': audit_interrupted,
            'StreamingResponse': FakeStreamingResponse,
            'time': SimpleNamespace(perf_counter=lambda: 1.0),
        },
    )
    return handler, FakeStreamingResponse


def _fallback_context():
    return {
        'request': SimpleNamespace(state=SimpleNamespace(direct=False)),
        'form_data': {'model': 'model-1'},
        'user': SimpleNamespace(id='user-1'),
        'model': {'id': 'model-1'},
        'metadata': {'chat_id': '', 'message_id': None},
        'events': [],
        'event_emitter': None,
        'event_caller': None,
    }


@pytest.mark.asyncio
async def test_compatibility_stream_bills_usage_with_outlet_filters_disabled():
    billed = []
    interrupted = []
    handler, response_type = _load_fallback_stream_handler(billed, interrupted)

    async def source():
        yield b'usage'

    response = response_type(source())
    wrapped = await handler(response, _fallback_context())

    assert [chunk async for chunk in wrapped.body_iterator] == [b'usage']
    assert billed == [{'input_tokens': 8, 'output_tokens': 2}]
    assert interrupted == []


@pytest.mark.asyncio
async def test_compatibility_stream_close_records_interrupted_usage():
    billed = []
    interrupted = []
    handler, response_type = _load_fallback_stream_handler(billed, interrupted)
    release = asyncio.Event()

    async def source():
        yield b'usage'
        await release.wait()

    original = source()
    response = response_type(original)
    wrapped = await handler(response, _fallback_context())

    assert await wrapped.body_iterator.__anext__() == b'usage'
    await wrapped.body_iterator.aclose()
    await original.aclose()

    assert billed == []
    assert interrupted == [{'input_tokens': 8, 'output_tokens': 2}]


def test_non_streaming_billing_precedes_optional_event_and_outlet_work():
    _, function = _top_level_function('non_streaming_chat_response_handler')
    billing_if = next(
        node
        for node in function.body
        if isinstance(node, ast.If) and 'non_streaming_response_is_billable' in _call_names(node.test)
    )
    event_if = next(
        node
        for node in function.body
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == 'event_emitter'
    )

    assert function.body.index(billing_if) < function.body.index(event_if)
    assert 'bill_subscription_usage_once' in _call_names(billing_if)
    assert {'outlet_filter_handler', 'background_tasks_handler'}.isdisjoint(_call_names(billing_if))


def test_compatibility_stream_tracks_raw_usage_and_bills_without_outlet_filters():
    source, function = _top_level_function('streaming_chat_response_handler')
    stream_wrapper = next(
        node for node in ast.walk(function) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'stream_wrapper'
    )
    wrapper_source = ast.get_source_segment(source, stream_wrapper)

    assert 'update_assistant_message_from_stream(billing_message, raw_data)' in wrapper_source

    completion_try = next(
        node
        for node in stream_wrapper.body
        if isinstance(node, ast.Try) and 'stream_completed = True' in ast.get_source_segment(source, node)
    )
    finalizer_calls = _call_names(ast.Module(body=completion_try.finalbody, type_ignores=[]))
    assert 'bill_subscription_usage_once' in finalizer_calls
    assert 'audit_interrupted_subscription_usage' in finalizer_calls

    outlet_if = next(
        node
        for node in stream_wrapper.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.BoolOp)
        and 'has_api_outlet_filters' in ast.get_source_segment(source, node.test)
        and 'outlet_filter_handler' in _call_names(node)
    )
    assert 'bill_subscription_usage_once' not in _call_names(outlet_if)
    assert 'audit_interrupted_subscription_usage' not in _call_names(outlet_if)


def test_saved_chat_cancellation_runs_interrupted_billing_audit():
    source, function = _top_level_function('streaming_chat_response_handler')
    cancellation_handler = next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.ExceptHandler) and 'Task was cancelled!' in (ast.get_source_segment(source, node) or '')
    )

    assert 'audit_interrupted_subscription_usage' in _call_names(cancellation_handler)
    assert 'bill_subscription_usage_once' in _call_names(
        next(
            node
            for node in ast.walk(function)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == 'response_handler'
        )
    )


def test_streaming_billing_precedes_optional_persistence_and_generic_errors_are_audited():
    source, function = _top_level_function('streaming_chat_response_handler')
    response_handler = next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'response_handler'
    )
    response_source = ast.get_source_segment(source, response_handler)

    assert response_source.index('await bill_subscription_usage_once(ctx, usage)') < response_source.index(
        'await Chats.get_chat_title_by_id'
    )
    generic_handler = next(
        node
        for node in response_handler.body
        if isinstance(node, ast.Try)
        for node in node.handlers
        if node.type is not None
        and ast.get_source_segment(source, node.type) == 'Exception'
        and 'audit_interrupted_subscription_usage' in _call_names(node)
    )
    assert 'audit_interrupted_subscription_usage' in _call_names(generic_handler)


def test_interrupted_billing_is_shielded_and_marked_for_audit():
    source, function = _top_level_function('audit_interrupted_subscription_usage')
    function_source = ast.get_source_segment(source, function)

    assert "completion_status='stream_interrupted'" in function_source
    assert 'shield' in _call_names(function)
    assert 'create_task' in _call_names(function)
