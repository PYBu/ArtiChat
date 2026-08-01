import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from open_webui.utils.inference_access import assert_raw_provider_generation_access
from starlette.requests import Request

BACKEND_DIR = Path(__file__).resolve().parents[3]


def make_request(path: str) -> Request:
    return Request(
        {
            'type': 'http',
            'method': 'POST',
            'path': path,
            'headers': [],
        }
    )


@pytest.mark.parametrize(
    'path',
    [
        '/openai/chat/completions',
        '/openai/responses',
        '/ollama/api/generate',
        '/ollama/api/chat',
        '/ollama/v1/completions',
        '/ollama/v1/chat/completions',
        '/ollama/v1/messages',
        '/ollama/v1/responses',
    ],
)
def test_raw_provider_generation_is_admin_only(path):
    with pytest.raises(HTTPException) as exc_info:
        assert_raw_provider_generation_access(make_request(path), SimpleNamespace(role='user'))

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    'path',
    [
        '/api/chat/completions',
        '/api/v1/chat/completions',
        '/api/v1/messages',
        '/api/v1/tasks/title/completions',
    ],
)
def test_metered_and_internal_entrypoints_remain_available_to_users(path):
    assert_raw_provider_generation_access(make_request(path), SimpleNamespace(role='user'))


def test_admin_can_use_raw_provider_generation():
    assert_raw_provider_generation_access(
        make_request('/openai/chat/completions'),
        SimpleNamespace(role='admin'),
    )


@pytest.mark.parametrize(
    ('relative_path', 'function_names'),
    [
        (
            'open_webui/routers/openai.py',
            ['speech', 'generate_chat_completion', 'responses', 'proxy'],
        ),
        (
            'open_webui/routers/ollama.py',
            [
                'generate_completion',
                'generate_chat_completion',
                'generate_openai_completion',
                'generate_openai_chat_completion',
                'generate_anthropic_messages',
                'generate_responses',
            ],
        ),
    ],
)
def test_every_raw_generation_handler_calls_the_access_gate(relative_path, function_names):
    tree = ast.parse((BACKEND_DIR / relative_path).read_text(encoding='utf-8'))
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))}

    for function_name in function_names:
        calls = [
            node
            for node in ast.walk(functions[function_name])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'assert_raw_provider_generation_access'
        ]
        assert calls, f'{relative_path}:{function_name} is missing the raw provider access gate'


def test_native_anthropic_passthrough_is_admin_only():
    source = (BACKEND_DIR / 'open_webui/main.py').read_text(encoding='utf-8')
    assert "user.role == 'admin' and is_anthropic_messages_passthrough" in source
