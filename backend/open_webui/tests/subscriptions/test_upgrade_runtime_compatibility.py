import os
import subprocess
import sys
from pathlib import Path


OPEN_WEBUI_ROOT = Path(__file__).resolve().parents[2]


def _source(relative_path: str) -> str:
    return (OPEN_WEBUI_ROOT / relative_path).read_text(encoding='utf-8')


def test_legacy_proxy_configuration_remains_available():
    env_source = _source('env.py')

    assert "TRUSTED_PROXY_IPS = os.getenv('TRUSTED_PROXY_IPS', '')" in env_source


def test_legacy_vector_collection_prefixes_remain_configurable():
    config_source = _source('config.py')
    milvus_source = _source('retrieval/vector/dbs/milvus.py')
    opensearch_source = _source('retrieval/vector/dbs/opensearch.py')

    assert "MILVUS_COLLECTION_PREFIX = os.getenv('MILVUS_COLLECTION_PREFIX', 'artichat')" in config_source
    assert "OPENSEARCH_INDEX_PREFIX = os.getenv('OPENSEARCH_INDEX_PREFIX', 'artichat')" in config_source
    assert 'self.collection_prefix = MILVUS_COLLECTION_PREFIX' in milvus_source
    assert 'self.index_prefix = OPENSEARCH_INDEX_PREFIX' in opensearch_source


def test_experimental_scim_fails_closed_for_this_release(tmp_path):
    environment = os.environ.copy()
    environment.update(
        {
            'DATA_DIR': str(tmp_path),
            'ENABLE_SCIM': 'true',
            'PYTHONPATH': str(OPEN_WEBUI_ROOT.parent),
            'WEBUI_SECRET_KEY': 'test-only-scim-fail-closed-secret-key',
        }
    )

    result = subprocess.run(
        [sys.executable, '-c', 'import open_webui.env'],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert 'SCIM is not supported by ArtiChat 0.3.0' in result.stderr
