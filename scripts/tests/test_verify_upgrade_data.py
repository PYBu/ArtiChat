from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'verify-upgrade-data.py'


def _run(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(argument) for argument in arguments)],
        capture_output=True,
        check=False,
        text=True,
    )


def _create_database(data_dir: Path) -> Path:
    data_dir.mkdir()
    database = data_dir / 'webui.db'
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE alembic_version (version_num TEXT NOT NULL);
            INSERT INTO alembic_version VALUES ('pre-upgrade-head');

            CREATE TABLE account (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                quota INTEGER NOT NULL,
                secret_blob BLOB
            );
            INSERT INTO account VALUES (
                'user-alice',
                'alice-private@example.test',
                4200,
                X'73757065722d736563726574'
            );
            INSERT INTO account VALUES (
                'user-bob',
                'bob-private@example.test',
                7300,
                X'616e6f746865722d736563726574'
            );
            """
        )
    return database


def _snapshot(tmp_path: Path, data_dir: Path) -> tuple[Path, Path, subprocess.CompletedProcess[str]]:
    output = tmp_path / 'before.json'
    key_file = tmp_path / 'snapshot.key'
    result = _run(
        'snapshot',
        '--data-dir',
        data_dir,
        '--output',
        output,
        '--key-file',
        key_file,
    )
    return output, key_file, result


def _verify(
    data_dir: Path,
    snapshot: Path,
    key_file: Path,
    *extra: object,
) -> subprocess.CompletedProcess[str]:
    return _run(
        'verify',
        '--data-dir',
        data_dir,
        '--snapshot',
        snapshot,
        '--key-file',
        key_file,
        *extra,
    )


def test_snapshot_is_deterministic_and_contains_no_values_paths_or_key(tmp_path: Path):
    data_dir = tmp_path / 'data'
    _create_database(data_dir)
    uploads = data_dir / 'uploads'
    uploads.mkdir()
    (uploads / 'customer-alice-private-document.txt').write_text('confidential document body', encoding='utf-8')
    cache = data_dir / 'cache'
    cache.mkdir()
    (cache / 'provider-secret.cache').write_text('cache secret', encoding='utf-8')
    (data_dir / 'other.sqlite-wal').write_bytes(b'transient wal bytes')

    snapshot, key_file, result = _snapshot(tmp_path, data_dir)

    assert result.returncode == 0, result.stderr
    first_bytes = snapshot.read_bytes()
    key_bytes = key_file.read_bytes()
    second = _run(
        'snapshot',
        '--data-dir',
        data_dir,
        '--output',
        snapshot,
        '--key-file',
        key_file,
    )
    assert second.returncode == 0, second.stderr
    assert snapshot.read_bytes() == first_bytes

    rendered = first_bytes.decode('utf-8')
    for private_value in (
        'user-alice',
        'alice-private@example.test',
        'super-secret',
        'customer-alice-private-document.txt',
        'confidential document body',
        'provider-secret.cache',
        key_bytes.hex(),
    ):
        assert private_value not in rendered

    document = json.loads(rendered)
    assert document['database']['integrity_check'] == 'ok'
    assert document['database']['foreign_key_violations'] == 0
    assert document['database']['tables']['account']['row_count'] == 2
    assert len(document['files']) == 1
    assert document['files'][0]['size'] == len('confidential document body')
    assert document['hashes']['file_contents'] == 'SHA-256'


def test_verify_tolerates_additions_and_requires_explicit_alembic_mutability(tmp_path: Path):
    data_dir = tmp_path / 'data'
    database = _create_database(data_dir)
    uploads = data_dir / 'uploads'
    uploads.mkdir()
    (uploads / 'existing.bin').write_bytes(b'preserve me')
    snapshot, key_file, result = _snapshot(tmp_path, data_dir)
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            ALTER TABLE account ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1;
            INSERT INTO account VALUES (
                'new-user', 'new-user@example.test', 10, NULL, 1
            );
            UPDATE alembic_version SET version_num = 'post-upgrade-head';
            CREATE TABLE new_release_table (id INTEGER PRIMARY KEY, value TEXT);
            INSERT INTO new_release_table (value) VALUES ('new data is allowed');
            """
        )
    (uploads / 'new-after-upgrade.bin').write_bytes(b'new file is allowed')

    rejected = _verify(data_dir, snapshot, key_file)
    assert rejected.returncode == 1
    assert "table 'alembic_version'" in rejected.stdout

    accepted = _verify(
        data_dir,
        snapshot,
        key_file,
        '--allow-mutable-table',
        'alembic_version',
    )
    assert accepted.returncode == 0, accepted.stderr
    report = json.loads(accepted.stdout)
    assert report['status'] == 'ok'
    assert report['database']['new_tables'] == 1
    assert report['database']['checked_rows'] == 2
    assert report['files']['new_files'] == 1


def test_changed_row_fails_unless_its_table_is_explicitly_mutable(tmp_path: Path):
    data_dir = tmp_path / 'data'
    database = _create_database(data_dir)
    snapshot, key_file, result = _snapshot(tmp_path, data_dir)
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE account SET email = 'changed-private@example.test' WHERE id = 'user-alice'")

    rejected = _verify(data_dir, snapshot, key_file)
    assert rejected.returncode == 1
    assert 'changed-private@example.test' not in rejected.stdout + rejected.stderr
    assert "table 'account' is missing or changed 1 pre-upgrade row(s)" in rejected.stdout

    accepted = _verify(
        data_dir,
        snapshot,
        key_file,
        '--allow-mutable-table',
        'account',
    )
    assert accepted.returncode == 0, accepted.stderr


def test_verify_rejects_a_removed_pre_upgrade_column(tmp_path: Path):
    data_dir = tmp_path / 'data'
    database = _create_database(data_dir)
    snapshot, key_file, result = _snapshot(tmp_path, data_dir)
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(database) as connection:
        connection.execute('ALTER TABLE account DROP COLUMN secret_blob')

    verified = _verify(data_dir, snapshot, key_file)
    assert verified.returncode == 1
    report = json.loads(verified.stdout)
    assert report['status'] == 'failed'
    assert report['database']['missing_columns'] == 1
    assert report['database']['checked_rows'] == 3


@pytest.mark.parametrize('mutation', ['delete', 'replace'])
def test_missing_or_changed_pre_upgrade_file_fails_without_revealing_its_name(tmp_path: Path, mutation: str):
    data_dir = tmp_path / 'data'
    _create_database(data_dir)
    uploads = data_dir / 'uploads'
    uploads.mkdir()
    file_path = uploads / 'private-customer-file.txt'
    file_path.write_bytes(b'original bytes')
    snapshot, key_file, result = _snapshot(tmp_path, data_dir)
    assert result.returncode == 0, result.stderr

    if mutation == 'delete':
        file_path.unlink()
    else:
        file_path.write_bytes(b'replaced bytes')

    rejected = _verify(data_dir, snapshot, key_file)
    assert rejected.returncode == 1
    assert 'private-customer-file.txt' not in rejected.stdout + rejected.stderr
    assert 'pre-upgrade data file(s)' in rejected.stdout


def test_foreign_key_violation_fails_without_exposing_row_values(tmp_path: Path):
    data_dir = tmp_path / 'data'
    database = _create_database(data_dir)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE parent_record (id TEXT PRIMARY KEY);
            CREATE TABLE child_record (
                id TEXT PRIMARY KEY,
                parent_id TEXT NOT NULL REFERENCES parent_record(id)
            );
            INSERT INTO parent_record VALUES ('valid-parent');
            INSERT INTO child_record VALUES ('valid-child', 'valid-parent');
            """
        )
    snapshot, key_file, result = _snapshot(tmp_path, data_dir)
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO child_record VALUES ('private-child', 'missing-private-parent')")

    rejected = _verify(data_dir, snapshot, key_file)
    assert rejected.returncode == 2
    assert 'foreign_key_check failed with 1 finding(s)' in rejected.stderr
    assert 'private-child' not in rejected.stdout + rejected.stderr
    assert 'missing-private-parent' not in rejected.stdout + rejected.stderr


def test_snapshot_authentication_and_key_identity_are_enforced(tmp_path: Path):
    data_dir = tmp_path / 'data'
    _create_database(data_dir)
    snapshot, key_file, result = _snapshot(tmp_path, data_dir)
    assert result.returncode == 0, result.stderr

    document = json.loads(snapshot.read_text(encoding='utf-8'))
    document['database']['tables']['account']['row_count'] = 0
    snapshot.write_text(json.dumps(document), encoding='utf-8')
    tampered = _verify(data_dir, snapshot, key_file)
    assert tampered.returncode == 2
    assert 'authentication failed' in tampered.stderr

    other_key = tmp_path / 'other.key'
    other_key.write_bytes(b'x' * 32)
    wrong_key = _verify(data_dir, snapshot, other_key)
    assert wrong_key.returncode == 2
    assert 'key does not match' in wrong_key.stderr
