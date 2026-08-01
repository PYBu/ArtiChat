import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status


OPEN_WEBUI_ROOT = Path(__file__).resolve().parents[2]
AUDIO_PATH = OPEN_WEBUI_ROOT / 'routers' / 'audio.py'
OPENAI_PATH = OPEN_WEBUI_ROOT / 'routers' / 'openai.py'


def _source_and_function(path: Path, name: str):
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    return source, function


def _load_audio_function(name: str, namespace: dict):
    _, function = _source_and_function(AUDIO_PATH, name)
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    globals_dict = dict(namespace)
    exec(compile(module, str(AUDIO_PATH), 'exec'), globals_dict)
    return globals_dict[name]


class _Request:
    def __init__(self, chunks, content_length=None):
        self.headers = {} if content_length is None else {'content-length': str(content_length)}
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


def test_tts_request_reader_rejects_declared_and_streamed_oversize_bodies():
    reader = _load_audio_function(
        '_read_request_body_limited',
        {'HTTPException': HTTPException, 'Request': object, 'status': status},
    )

    with pytest.raises(HTTPException) as declared_error:
        asyncio.run(reader(_Request([], content_length=11), 10))
    with pytest.raises(HTTPException) as streamed_error:
        asyncio.run(reader(_Request([b'123456', b'78901']), 10))

    assert declared_error.value.status_code == 413
    assert streamed_error.value.status_code == 413


def test_tts_response_reader_enforces_declared_limit_before_iteration():
    reader = _load_audio_function(
        '_read_response_body_limited',
        {'AIOHTTP_FILE_STREAM_CHUNK_SIZE': 4, 'MAX_TTS_OUTPUT_BYTES': 10},
    )

    class Content:
        def iter_chunked(self, _size):
            raise AssertionError('oversize response body must not be read')

    response = SimpleNamespace(content_length=11, content=Content())
    with pytest.raises(ValueError, match='size limit'):
        asyncio.run(reader(response, 10))


def test_stt_upload_and_chunk_concurrency_are_bounded_by_contract():
    source, transcription = _source_and_function(AUDIO_PATH, 'transcription')
    transcription_source = ast.get_source_segment(source, transcription)
    _, transcribe = _source_and_function(AUDIO_PATH, 'transcribe')
    transcribe_source = ast.get_source_segment(source, transcribe)

    assert 'file.read(AIOHTTP_FILE_STREAM_CHUNK_SIZE)' in transcription_source
    assert 'MAX_TRANSCRIPTION_UPLOAD_BYTES' in transcription_source
    assert 'contents = await file.read()' not in transcription_source
    assert 'asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)' in transcribe_source
    assert 'MAX_TRANSCRIPTION_CHUNKS' in transcribe_source


def test_legacy_openai_speech_is_admin_gated_and_size_bounded():
    source, speech = _source_and_function(OPENAI_PATH, 'speech')
    speech_source = ast.get_source_segment(source, speech)

    assert 'assert_raw_provider_generation_access(request, user)' in speech_source
    assert 'request.stream()' in speech_source
    assert 'max_speech_bytes = 50 * 1024 * 1024' in speech_source
    assert 'file_path.unlink' in speech_source
