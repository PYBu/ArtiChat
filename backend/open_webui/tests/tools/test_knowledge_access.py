from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from open_webui.models.files import Files
from open_webui.models.groups import Groups
from open_webui.retrieval import utils as retrieval_utils
from open_webui.tools import builtin


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                EMBEDDING_FUNCTION=AsyncMock(return_value=[[0.1]]),
            )
        )
    )


def test_query_knowledge_files_rejects_attached_file_without_read_access(monkeypatch):
    monkeypatch.setattr(Groups, 'get_groups_by_member_id', AsyncMock(return_value=[]))
    monkeypatch.setattr(
        Files,
        'get_file_by_id',
        AsyncMock(return_value=SimpleNamespace(id='file-1', user_id='owner-1')),
    )
    monkeypatch.setattr(builtin, '_has_read_access_to_file', AsyncMock(return_value=False))
    query_collection = AsyncMock()
    monkeypatch.setattr(retrieval_utils, 'query_collection', query_collection)

    result = asyncio.run(
        builtin.query_knowledge_files(
            query='private document',
            __request__=_request(),
            __user__={'id': 'reader-1', 'role': 'user'},
            __model_knowledge__=[{'type': 'file', 'id': 'file-1'}],
        )
    )

    assert result == '[]'
    query_collection.assert_not_awaited()


def test_query_knowledge_files_keeps_attached_file_accessible_when_authorized(monkeypatch):
    monkeypatch.setattr(Groups, 'get_groups_by_member_id', AsyncMock(return_value=[]))
    monkeypatch.setattr(
        Files,
        'get_file_by_id',
        AsyncMock(return_value=SimpleNamespace(id='file-1', user_id='owner-1')),
    )
    monkeypatch.setattr(builtin, '_has_read_access_to_file', AsyncMock(return_value=True))
    query_collection = AsyncMock(
        return_value={
            'documents': [['authorized content']],
            'metadatas': [[{'file_id': 'file-1', 'name': 'private.md'}]],
            'distances': [[0.9]],
        }
    )
    monkeypatch.setattr(retrieval_utils, 'query_collection', query_collection)

    result = asyncio.run(
        builtin.query_knowledge_files(
            query='private document',
            __request__=_request(),
            __user__={'id': 'reader-1', 'role': 'user'},
            __model_knowledge__=[{'type': 'file', 'id': 'file-1'}],
        )
    )

    assert 'authorized content' in result
    assert query_collection.await_args.kwargs['collection_names'] == ['file-file-1']
