from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status
from open_webui.utils.inference_access import assert_raw_embedding_access

OPEN_WEBUI_ROOT = Path(__file__).resolve().parents[2]
FILES_PATH = OPEN_WEBUI_ROOT / 'routers' / 'files.py'
OLLAMA_PATH = OPEN_WEBUI_ROOT / 'routers' / 'ollama.py'
OPENAI_PATH = OPEN_WEBUI_ROOT / 'routers' / 'openai.py'
RETRIEVAL_PATH = OPEN_WEBUI_ROOT / 'routers' / 'retrieval.py'
EMBEDDINGS_PATH = OPEN_WEBUI_ROOT / 'utils' / 'embeddings.py'


def _source_and_function(path: Path, name: str):
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    return source, function


def _function_source(path: Path, name: str) -> str:
    source, function = _source_and_function(path, name)
    return ast.get_source_segment(source, function) or ''


def _load_function(path: Path, name: str, namespace: dict):
    _, function = _source_and_function(path, name)
    function.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    globals_dict = dict(namespace)
    exec(compile(module, str(path), 'exec'), globals_dict)
    return globals_dict[name]


def test_file_permission_helper_fails_closed_for_non_admins():
    permission_check = AsyncMock(return_value=False)

    class FakeConfig:
        @staticmethod
        async def get(_key):
            return {'chat': {'file_upload': False}}

    require_permission = _load_function(
        FILES_PATH,
        '_require_chat_permission',
        {
            'AsyncSession': object,
            'Config': FakeConfig,
            'ERROR_MESSAGES': SimpleNamespace(ACCESS_PROHIBITED='forbidden'),
            'HTTPException': HTTPException,
            'has_permission': permission_check,
            'status': status,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_permission(SimpleNamespace(id='user-1', role='user'), 'chat.file_upload'))
    assert exc_info.value.status_code == 403

    asyncio.run(require_permission(SimpleNamespace(id='admin-1', role='admin'), 'chat.file_upload'))
    assert permission_check.await_count == 1


def test_upload_route_requires_file_upload_and_auto_stt_permissions_before_storage():
    upload_source = _function_source(FILES_PATH, 'upload_file')
    process_source = _function_source(FILES_PATH, 'process_uploaded_file')

    upload_gate = "_require_chat_permission(user, 'chat.file_upload', db=db)"
    stt_gate = "_require_chat_permission(user, 'chat.stt', db=db)"
    assert upload_gate in upload_source
    assert stt_gate in upload_source
    assert upload_source.index(upload_gate) < upload_source.index('upload_file_handler(')
    assert upload_source.index(stt_gate) < upload_source.index('upload_file_handler(')
    assert "_require_chat_permission(user, 'chat.stt', db=db_session)" in process_source


def test_retrieval_embedding_ingestion_uses_file_upload_permission():
    helper_source = _function_source(RETRIEVAL_PATH, '_require_file_upload_permission')
    assert "has_permission(user.id, 'chat.file_upload', await Config.get('user.permissions'))" in helper_source

    for function_name in ('process_file', 'process_text', 'process_web', 'process_files_batch'):
        assert 'await _require_file_upload_permission(user)' in _function_source(RETRIEVAL_PATH, function_name)


def test_raw_embedding_access_is_admin_only():
    with pytest.raises(HTTPException) as exc_info:
        assert_raw_embedding_access(SimpleNamespace(role='user'))
    assert exc_info.value.status_code == 403

    assert_raw_embedding_access(SimpleNamespace(role='admin'))


def test_every_public_embedding_dispatcher_uses_the_admin_guard():
    guarded_functions = [
        (EMBEDDINGS_PATH, 'generate_embeddings'),
        (OPENAI_PATH, 'embeddings'),
        (OLLAMA_PATH, 'embed'),
        (OLLAMA_PATH, 'embeddings'),
        (OLLAMA_PATH, 'generate_openai_embeddings'),
    ]
    for path, function_name in guarded_functions:
        source = _function_source(path, function_name)
        assert 'assert_raw_embedding_access(user)' in source, f'{path.name}:{function_name} is not guarded'

    assert 'Depends(get_admin_user)' in _function_source(RETRIEVAL_PATH, 'get_embeddings')


def test_web_search_retains_feature_permission_and_declares_non_chatpoint_billing():
    module_source = RETRIEVAL_PATH.read_text(encoding='utf-8')
    function_source = _function_source(RETRIEVAL_PATH, 'process_web_search')

    assert "WEB_SEARCH_BILLING_MODE = 'feature_permission_only_no_text_chatpoint'" in module_source
    assert "has_permission(user.id, 'features.web_search', config.USER_PERMISSIONS)" in function_source
    assert '_require_file_upload_permission' not in function_source
    assert 'WEB_SEARCH_BILLING_MODE' in function_source
    assert 'user.id' in function_source
    assert 'form_data.queries}' not in function_source
    assert 'form_data.queries' not in function_source.split('Web search authorized:', 1)[-1].split('urls = []', 1)[0]


def test_retrieval_debug_logging_does_not_emit_queries_or_items():
    source = (OPEN_WEBUI_ROOT / 'retrieval' / 'utils.py').read_text(encoding='utf-8')

    assert "log.debug('items: %s %s %s %s %s'" not in source
    assert 'Retrieval request: item_count=%d query_count=%d' in source
