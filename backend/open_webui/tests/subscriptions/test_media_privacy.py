from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import aiofiles
import pytest
from fastapi import HTTPException

OPEN_WEBUI_ROOT = Path(__file__).resolve().parents[2]
AUDIO_PATH = OPEN_WEBUI_ROOT / 'routers' / 'audio.py'
IMAGES_PATH = OPEN_WEBUI_ROOT / 'routers' / 'images.py'
OPENAI_PATH = OPEN_WEBUI_ROOT / 'routers' / 'openai.py'
FILES_PATH = OPEN_WEBUI_ROOT / 'utils' / 'files.py'
MIDDLEWARE_PATH = OPEN_WEBUI_ROOT / 'utils' / 'middleware.py'


def _source_and_function(path: Path, name: str):
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    return source, function


def _load_function(path: Path, name: str, namespace: dict):
    _, function = _source_and_function(path, name)
    function.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    globals_dict = dict(namespace)
    exec(compile(module, str(path), 'exec'), globals_dict)
    return globals_dict[name]


def _event_data_keys(path: Path, function_name: str) -> set[str]:
    _, function = _source_and_function(path, function_name)
    keys = set()
    for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
        if not isinstance(call.func, ast.Name) or call.func.id != 'publish_event':
            continue
        data_keyword = next((keyword for keyword in call.keywords if keyword.arg == 'data'), None)
        if data_keyword is None or not isinstance(data_keyword.value, ast.Dict):
            continue
        keys.update(
            key.value for key in data_keyword.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
        )
    return keys


def test_legacy_tts_request_sidecars_are_purged_without_touching_audio_or_unrelated_json(tmp_path):
    hash_name = 'a' * 64
    hashed_sidecar = tmp_path / f'{hash_name}.json'
    cached_audio = tmp_path / f'{hash_name}.mp3'
    unrelated_json = tmp_path / 'settings.json'
    hashed_sidecar.write_text('{"input":"private speech"}', encoding='utf-8')
    cached_audio.write_bytes(b'audio')
    unrelated_json.write_text('{}', encoding='utf-8')

    purge = _load_function(
        AUDIO_PATH,
        '_purge_legacy_tts_request_sidecars',
        {'SPEECH_CACHE_DIR': tmp_path, 'log': SimpleNamespace(warning=lambda *_args: None)},
    )
    purge()

    assert not hashed_sidecar.exists()
    assert cached_audio.read_bytes() == b'audio'
    assert unrelated_json.exists()


def test_tts_audio_cache_writes_audio_without_request_metadata(tmp_path):
    writer = _load_function(
        AUDIO_PATH,
        '_write_tts_cache',
        {
            'Path': Path,
            'aiofiles': aiofiles,
            'MAX_TTS_OUTPUT_BYTES': 1024,
        },
    )
    audio_path = tmp_path / 'speech.mp3'

    asyncio.run(writer(audio_path, b'generated-audio'))

    assert audio_path.read_bytes() == b'generated-audio'
    assert list(tmp_path.iterdir()) == [audio_path]


def test_all_tts_routes_avoid_plaintext_request_sidecars():
    audio_source = AUDIO_PATH.read_text(encoding='utf-8')
    audio_tree = ast.parse(audio_source)
    tts_functions = [
        node
        for node in audio_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (node.name == 'speech' or node.name == '_write_tts_cache' or node.name.startswith('_tts_'))
    ]
    for function in tts_functions:
        function_source = ast.get_source_segment(audio_source, function) or ''
        assert 'file_body_path' not in function_source
        assert 'json.dumps(payload)' not in function_source
        assert "joinpath(f'{name}.json')" not in function_source

    openai_source, legacy_speech = _source_and_function(OPENAI_PATH, 'speech')
    legacy_source = ast.get_source_segment(openai_source, legacy_speech) or ''
    assert 'file_body_path' not in legacy_source
    assert 'json.dumps(payload)' not in legacy_source
    assert "joinpath(f'{name}.json')" not in legacy_source

    cleanup_calls = [
        node
        for node in audio_tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
    ]
    assert any(call.value.func.id == '_purge_legacy_tts_request_sidecars' for call in cleanup_calls)


def test_media_events_never_publish_prompt_or_speech_content():
    assert _event_data_keys(IMAGES_PATH, 'generate_images') == {'model', 'size', 'n'}
    assert _event_data_keys(IMAGES_PATH, 'edit_images') == {'model', 'size', 'n'}
    assert _event_data_keys(AUDIO_PATH, 'speech') == {'engine', 'model', 'cached'}


def test_multimodal_image_loader_uses_the_bounded_user_aware_resolver():
    calls = []

    async def resolver(reference, user):
        calls.append((reference, user))
        return SimpleNamespace(as_data_url=lambda: 'data:image/png;base64,c2FmZQ==')

    loader = _load_function(
        FILES_PATH,
        'get_image_base64_from_url',
        {'Optional': Optional, 'resolve_image_reference': resolver},
    )
    file_loader = _load_function(
        FILES_PATH,
        'get_image_base64_from_file_id',
        {'Optional': Optional, 'resolve_image_reference': resolver},
    )
    user = SimpleNamespace(id='user-1', role='user')

    result = asyncio.run(loader('https://images.example/source.png', user=user))
    file_result = asyncio.run(file_loader('file-1', user=user))

    assert result == 'data:image/png;base64,c2FmZQ=='
    assert file_result == 'data:image/png;base64,c2FmZQ=='
    assert calls == [('https://images.example/source.png', user), ('file-1', user)]

    for function_name in ('get_image_base64_from_url', 'get_image_base64_from_file_id'):
        source, function = _source_and_function(FILES_PATH, function_name)
        function_source = ast.get_source_segment(source, function) or ''
        assert 'resolve_image_reference' in function_source
        assert '.read()' not in function_source
        assert '.get(' not in function_source


def test_multimodal_conversion_validates_data_urls_and_fails_closed():
    calls = []

    async def resolver(reference, user=None):
        calls.append((reference, user))
        return 'data:image/png;base64,c2FmZQ=='

    converter = _load_function(
        MIDDLEWARE_PATH,
        'convert_url_images_to_base64',
        {
            'HTTPException': HTTPException,
            'get_image_base64_from_url': resolver,
            'log': SimpleNamespace(debug=lambda *_args: None),
        },
    )
    user = SimpleNamespace(id='user-1')
    data_url = 'data:image/png;base64,dW50cnVzdGVk'
    form_data = {
        'messages': [
            {
                'content': [
                    {'type': 'image_url', 'image_url': {'url': data_url}},
                ]
            }
        ]
    }

    result = asyncio.run(converter(form_data, user=user))

    assert calls == [(data_url, user)]
    assert result['messages'][0]['content'][0]['image_url']['url'] == 'data:image/png;base64,c2FmZQ=='

    async def failed_resolver(_reference, user=None):
        return None

    failed_converter = _load_function(
        MIDDLEWARE_PATH,
        'convert_url_images_to_base64',
        {
            'HTTPException': HTTPException,
            'get_image_base64_from_url': failed_resolver,
            'log': SimpleNamespace(debug=lambda *_args: None),
        },
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            failed_converter(
                {
                    'messages': [
                        {
                            'content': [
                                {
                                    'type': 'image_url',
                                    'image_url': {'url': 'https://images.example/untrusted.png'},
                                }
                            ]
                        }
                    ]
                },
                user=user,
            )
        )

    assert exc_info.value.status_code == 400
