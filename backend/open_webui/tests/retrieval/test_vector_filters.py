import pytest

from open_webui.retrieval.vector.utils import (
    filter_metadata,
    iter_filter_conditions,
    metadata_matches_filter,
    normalize_filter,
)


def test_filter_language_is_exact_and_supports_in_lists():
    value = {'knowledge_id': 'kb-1', 'file_id': {'$in': ['file-1', 'file-2']}}

    assert list(iter_filter_conditions(value)) == [
        ('knowledge_id', '$eq', 'kb-1'),
        ('file_id', '$in', ['file-1', 'file-2']),
    ]
    assert normalize_filter(value) == value
    assert metadata_matches_filter({'knowledge_id': 'kb-1', 'file_id': 'file-2'}, value)
    assert not metadata_matches_filter({'knowledge_id': 'kb-2', 'file_id': 'file-2'}, value)


def test_filter_language_rejects_unsupported_or_scalar_in_values():
    with pytest.raises(ValueError, match='Unsupported metadata filter'):
        list(iter_filter_conditions({'file_id': {'$ne': 'file-1'}}))

    with pytest.raises(ValueError, match="must be a list"):
        list(iter_filter_conditions({'file_id': {'$in': 'file-1'}}))


def test_metadata_filter_drops_extracted_archive_fields():
    value = filter_metadata(
        {
            'title': 'kept',
            'documents': [{'text': 'expanded'}],
            'styles': {'font': 'expanded'},
        }
    )

    assert value == {'title': 'kept'}
