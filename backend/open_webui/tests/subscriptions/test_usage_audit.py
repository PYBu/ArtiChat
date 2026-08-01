from types import SimpleNamespace

from open_webui.utils.subscriptions import get_request_client_ip, stream_event_has_content


def test_stream_content_helper_recognizes_text_reasoning_and_tool_deltas():
    assert stream_event_has_content({'choices': [{'delta': {'content': 'hello'}}]}) is True
    assert stream_event_has_content({'choices': [{'delta': {'reasoning_content': 'think'}}]}) is True
    assert stream_event_has_content({'choices': [{'delta': {'tool_calls': [{'id': 'call-1'}]}}]}) is True
    assert stream_event_has_content({'type': 'response.output_text.delta', 'delta': 'hello'}) is True
    assert stream_event_has_content({'choices': [{'delta': {}}]}) is False
    assert stream_event_has_content({'usage': {'total_tokens': 10}}) is False


def test_request_client_ip_uses_connection_host_and_ignores_forwarded_header():
    request = SimpleNamespace(
        client=SimpleNamespace(host='192.0.2.10'),
        headers={'x-forwarded-for': '198.51.100.20'},
    )

    assert get_request_client_ip(request) == '192.0.2.10'


def test_request_client_ip_is_none_without_connection():
    assert get_request_client_ip(SimpleNamespace(client=None, headers={})) is None
