#!/usr/bin/env python3
"""Create and verify privacy-safe ArtiChat SQLite upgrade snapshots.

Run this against a stopped service or a private copy of its data directory. The
snapshot contains schema names, counts, and keyed digests, but no database
values, file names, or secret key material.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import hmac
import json
import os
import sqlite3
import stat
import struct
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1
KEY_BYTES = 32
READ_CHUNK_BYTES = 1024 * 1024

EXCLUDED_DIRECTORY_NAMES = frozenset({'cache', '.cache', 'tmp', 'temp', '__pycache__'})
EXCLUDED_FILE_NAMES = frozenset({'.DS_Store', 'Thumbs.db'})
EXCLUDED_FILE_NAMES_CASEFOLDED = frozenset(name.casefold() for name in EXCLUDED_FILE_NAMES)
EXCLUDED_FILE_SUFFIXES = (
    '-wal',
    '-shm',
    '-journal',
    '.tmp',
    '.temp',
    '.lock',
    '.swp',
    '~',
)
EXPECTED_HASHES = {
    'database_cells': 'HMAC-SHA-256',
    'relative_paths': 'HMAC-SHA-256',
    'file_contents': 'SHA-256',
}


class SafeError(RuntimeError):
    """An error whose message contains no row values, file names, or secrets."""


def _canonical_json(value: Any, *, pretty: bool = False) -> bytes:
    if pretty:
        rendered = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
    else:
        rendered = json.dumps(value, ensure_ascii=True, separators=(',', ':'), sort_keys=True)
    return (rendered + '\n').encode('utf-8')


def _framed(parts: tuple[bytes, ...]) -> bytes:
    output = bytearray()
    for part in parts:
        output.extend(struct.pack('>Q', len(part)))
        output.extend(part)
    return bytes(output)


def _derive_key(raw_key: bytes) -> bytes:
    return hashlib.sha256(b'artichat-upgrade-snapshot-key-v1\0' + raw_key).digest()


def _key_id(key: bytes) -> str:
    return hashlib.sha256(b'artichat-upgrade-snapshot-key-id-v1\0' + key).hexdigest()


def _hmac_hex(key: bytes, domain: bytes, *parts: bytes) -> str:
    return hmac.new(key, domain + b'\0' + _framed(parts), hashlib.sha256).hexdigest()


def _load_key(path: Path, *, create: bool) -> bytes:
    path = path.resolve()
    if create and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(os.urandom(KEY_BYTES))
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise

    try:
        raw_key = path.read_bytes()
    except OSError as exc:
        raise SafeError('snapshot key file could not be read') from exc

    if not KEY_BYTES <= len(raw_key) <= 4096:
        raise SafeError(f'snapshot key file must contain between {KEY_BYTES} and 4096 bytes')
    return _derive_key(raw_key)


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _validate_paths(
    *,
    data_dir: Path,
    database: Path,
    key_file: Path,
    output: Path | None = None,
    snapshot: Path | None = None,
) -> tuple[Path, Path, Path]:
    data_dir = data_dir.resolve()
    database = database.resolve()
    key_file = key_file.resolve()

    if not data_dir.is_dir() or data_dir.is_symlink():
        raise SafeError('data directory must be an existing, non-symbolic-link directory')
    if not database.is_file() or database.is_symlink():
        raise SafeError('SQLite database must be an existing, non-symbolic-link file')
    if _is_within(key_file, data_dir):
        raise SafeError('snapshot key file must be outside the data directory')

    for artifact, label in ((output, 'snapshot output'), (snapshot, 'snapshot input')):
        if artifact is None:
            continue
        resolved = artifact.resolve()
        if resolved == database or resolved == key_file:
            raise SafeError(f'{label} must be distinct from the database and key file')
        if _is_within(resolved, data_dir):
            raise SafeError(f'{label} must be outside the data directory')

    return data_dir, database, key_file


def _sqlite_uri(path: Path) -> str:
    return f'{path.resolve().as_uri()}?mode=ro'


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _encode_text(value: str) -> bytes:
    return value.encode('utf-8', errors='surrogateescape')


def _canonical_value(value: Any) -> bytes:
    if value is None:
        return b'n'
    if isinstance(value, int):
        return b'i' + str(value).encode('ascii')
    if isinstance(value, float):
        return b'f' + struct.pack('>d', value)
    if isinstance(value, str):
        return b't' + _framed((_encode_text(value),))
    if isinstance(value, bytes):
        return b'b' + _framed((value,))
    raise SafeError('SQLite returned an unsupported value type')


def _cell_digest(key: bytes, table: str, column: str, value: Any) -> str:
    return _hmac_hex(
        key,
        b'cell-v1',
        _encode_text(table),
        _encode_text(column),
        _canonical_value(value),
    )


def _check_sqlite(connection: sqlite3.Connection) -> None:
    try:
        integrity_rows = connection.execute('PRAGMA integrity_check').fetchall()
        foreign_key_rows = connection.execute('PRAGMA foreign_key_check').fetchall()
    except sqlite3.DatabaseError as exc:
        raise SafeError('SQLite integrity or foreign-key verification could not complete') from exc

    if len(integrity_rows) != 1 or integrity_rows[0][0] != 'ok':
        raise SafeError(f'SQLite integrity_check failed with {len(integrity_rows)} finding(s)')
    if foreign_key_rows:
        raise SafeError(f'SQLite foreign_key_check failed with {len(foreign_key_rows)} finding(s)')


def _table_columns(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    table_literal = "'" + table.replace("'", "''") + "'"
    try:
        rows = connection.execute(f'PRAGMA table_xinfo({table_literal})').fetchall()
    except sqlite3.DatabaseError as exc:
        raise SafeError('SQLite table metadata could not be read') from exc

    columns = []
    for row in rows:
        hidden = int(row[6]) if len(row) > 6 else 0
        if hidden == 1:
            continue
        columns.append(
            {
                'name': str(row[1]),
                'declared_type': str(row[2] or ''),
                'not_null': bool(row[3]),
                'primary_key_position': int(row[5]),
                'hidden': hidden,
            }
        )
    if not columns:
        raise SafeError('SQLite table has no comparable columns')
    return columns


def _table_rows(
    connection: sqlite3.Connection,
    key: bytes,
    table: str,
    columns: list[dict[str, Any]],
) -> list[list[str]]:
    column_names = [column['name'] for column in columns]
    projection = ', '.join(_quote_identifier(name) for name in column_names)
    statement = f'SELECT {projection} FROM {_quote_identifier(table)}'

    rows: list[list[str]] = []
    try:
        cursor = connection.execute(statement)
        while batch := cursor.fetchmany(1000):
            for values in batch:
                rows.append(
                    [
                        _cell_digest(key, table, column, value)
                        for column, value in zip(column_names, values, strict=True)
                    ]
                )
    except sqlite3.DatabaseError as exc:
        raise SafeError('SQLite table rows could not be read') from exc
    rows.sort()
    return rows


def _inspect_database(database: Path, key: bytes) -> dict[str, Any]:
    try:
        connection = sqlite3.connect(_sqlite_uri(database), uri=True)
    except sqlite3.Error as exc:
        raise SafeError('SQLite database could not be opened read-only') from exc

    connection.text_factory = lambda value: value.decode('utf-8', errors='surrogateescape')
    try:
        connection.execute('PRAGMA query_only = ON')
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('BEGIN')
        _check_sqlite(connection)
        table_names = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        if not table_names or 'alembic_version' not in table_names:
            raise SafeError('SQLite database is missing the required Alembic schema table')

        tables: dict[str, Any] = {}
        for table in table_names:
            columns = _table_columns(connection, table)
            rows = _table_rows(connection, key, table, columns)
            tables[table] = {
                'columns': columns,
                'row_count': len(rows),
                'rows': rows,
            }
        return {
            'integrity_check': 'ok',
            'foreign_key_violations': 0,
            'tables': tables,
        }
    except sqlite3.DatabaseError as exc:
        raise SafeError('SQLite snapshot inspection failed') from exc
    finally:
        connection.close()


def _relative_path(path: Path, data_dir: Path) -> str | None:
    try:
        return path.relative_to(data_dir).as_posix()
    except ValueError:
        return None


def _path_digest(key: bytes, relative_path: str) -> str:
    return _hmac_hex(key, b'path-v1', _encode_text(relative_path))


def _matches_custom_glob(relative_path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(relative_path, pattern) for pattern in patterns)


def _is_excluded(relative_path: str, *, is_directory: bool, patterns: tuple[str, ...]) -> bool:
    parts = relative_path.split('/')
    if any(part.casefold() in EXCLUDED_DIRECTORY_NAMES for part in parts):
        return True
    if _matches_custom_glob(relative_path, patterns):
        return True
    if is_directory:
        return False
    name = parts[-1]
    folded_name = name.casefold()
    if folded_name in EXCLUDED_FILE_NAMES_CASEFOLDED:
        return True
    return any(folded_name.endswith(suffix.casefold()) for suffix in EXCLUDED_FILE_SUFFIXES)


def _hash_file(path: Path) -> tuple[int, str]:
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise SafeError('data directory contains an unsupported non-regular file')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(READ_CHUNK_BYTES):
                digest.update(chunk)
        after = path.lstat()
    except SafeError:
        raise
    except OSError as exc:
        raise SafeError('a data file could not be read') from exc

    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        raise SafeError('a data file changed while it was being hashed')
    return before.st_size, digest.hexdigest()


def _retained_directories(
    root: Path,
    directory_names: list[str],
    data_dir: Path,
    custom_globs: tuple[str, ...],
) -> tuple[list[str], int]:
    retained = []
    symbolic_links = 0
    for name in sorted(directory_names):
        path = root / name
        relative = path.relative_to(data_dir).as_posix()
        if _is_excluded(relative, is_directory=True, patterns=custom_globs):
            continue
        if path.is_symlink():
            symbolic_links += 1
            continue
        retained.append(name)
    return retained, symbolic_links


def _file_record(
    path: Path,
    relative: str,
    key: bytes,
) -> dict[str, Any]:
    size, sha256 = _hash_file(path)
    return {'path_hmac': _path_digest(key, relative), 'size': size, 'sha256': sha256}


def _inspect_files(
    data_dir: Path,
    database: Path,
    key: bytes,
    custom_globs: tuple[str, ...],
) -> tuple[list[dict[str, Any]], str | None]:
    database_relative = _relative_path(database, data_dir)
    database_path_digest = _path_digest(key, database_relative) if database_relative else None
    records: list[dict[str, Any]] = []
    seen_path_digests: set[str] = set()
    unsupported_links = 0

    for current_root, directory_names, file_names in os.walk(data_dir, topdown=True, followlinks=False):
        root = Path(current_root)
        retained, directory_links = _retained_directories(root, directory_names, data_dir, custom_globs)
        directory_names[:] = retained
        unsupported_links += directory_links

        for name in sorted(file_names):
            path = root / name
            relative = path.relative_to(data_dir).as_posix()
            if relative == database_relative:
                continue
            if _is_excluded(relative, is_directory=False, patterns=custom_globs):
                continue
            if path.is_symlink():
                unsupported_links += 1
                continue
            record = _file_record(path, relative, key)
            path_hmac = record['path_hmac']
            if path_hmac in seen_path_digests:
                raise SafeError('data file path digest collision detected')
            seen_path_digests.add(path_hmac)
            records.append(record)

    if unsupported_links:
        raise SafeError(f'data directory contains {unsupported_links} unsupported symbolic link(s)')
    records.sort(key=lambda item: item['path_hmac'])
    return records, database_path_digest


def _manifest_hmac(document: dict[str, Any], key: bytes) -> str:
    unsigned = dict(document)
    unsigned.pop('manifest_hmac', None)
    return _hmac_hex(key, b'manifest-v1', _canonical_json(unsigned))


def _write_atomic(path: Path, content: bytes) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix='.upgrade-snapshot-', dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def create_snapshot(
    *,
    data_dir: Path,
    database: Path,
    output: Path,
    key_file: Path,
    custom_globs: tuple[str, ...] = (),
) -> dict[str, Any]:
    data_dir, database, key_file = _validate_paths(
        data_dir=data_dir,
        database=database,
        key_file=key_file,
        output=output,
    )
    key = _load_key(key_file, create=True)
    normalized_globs = tuple(sorted(set(custom_globs)))
    database_state = _inspect_database(database, key)
    files, database_path_digest = _inspect_files(
        data_dir,
        database,
        key,
        normalized_globs,
    )

    document: dict[str, Any] = {
        'format': 'artichat-upgrade-data-snapshot',
        'format_version': FORMAT_VERSION,
        'key_id': _key_id(key),
        'hashes': EXPECTED_HASHES,
        'database': database_state,
        'files': files,
        'file_policy': {
            'database_path_hmac': database_path_digest,
            'excluded_directory_names': sorted(EXCLUDED_DIRECTORY_NAMES),
            'excluded_file_names': sorted(EXCLUDED_FILE_NAMES),
            'excluded_file_suffixes': sorted(EXCLUDED_FILE_SUFFIXES),
            'custom_globs': list(normalized_globs),
        },
    }
    document['manifest_hmac'] = _manifest_hmac(document, key)
    _write_atomic(output, _canonical_json(document, pretty=True))
    return document


def _load_snapshot(path: Path, key: bytes) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SafeError('snapshot JSON could not be read') from exc

    if not isinstance(document, dict):
        raise SafeError('snapshot JSON has an invalid top-level structure')
    if document.get('format') != 'artichat-upgrade-data-snapshot':
        raise SafeError('snapshot JSON has an unsupported format')
    if document.get('format_version') != FORMAT_VERSION:
        raise SafeError('snapshot JSON has an unsupported format version')
    if not hmac.compare_digest(str(document.get('key_id', '')), _key_id(key)):
        raise SafeError('snapshot key does not match the snapshot JSON')

    expected_hmac = _manifest_hmac(document, key)
    if not hmac.compare_digest(str(document.get('manifest_hmac', '')), expected_hmac):
        raise SafeError('snapshot JSON authentication failed')
    _validate_snapshot_structure(document)
    return document


def _is_hex_digest(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in '0123456789abcdef' for character in value)


def _validate_file_policy(policy: Any) -> None:
    if not isinstance(policy, dict):
        raise SafeError('snapshot JSON file policy is invalid')
    expected_static_policy = {
        'excluded_directory_names': sorted(EXCLUDED_DIRECTORY_NAMES),
        'excluded_file_names': sorted(EXCLUDED_FILE_NAMES),
        'excluded_file_suffixes': sorted(EXCLUDED_FILE_SUFFIXES),
    }
    if any(policy.get(name) != value for name, value in expected_static_policy.items()):
        raise SafeError('snapshot JSON uses an unsupported file exclusion policy')
    if not isinstance(policy.get('custom_globs'), list) or not all(
        isinstance(pattern, str) for pattern in policy['custom_globs']
    ):
        raise SafeError('snapshot JSON file policy is invalid')
    database_path_hmac = policy.get('database_path_hmac')
    if database_path_hmac is not None and not _is_hex_digest(database_path_hmac):
        raise SafeError('snapshot JSON database path digest is invalid')


def _validate_column(column: Any) -> bool:
    return (
        isinstance(column, dict)
        and isinstance(column.get('name'), str)
        and isinstance(column.get('declared_type'), str)
        and isinstance(column.get('not_null'), bool)
        and isinstance(column.get('primary_key_position'), int)
        and column['primary_key_position'] >= 0
        and isinstance(column.get('hidden'), int)
        and column['hidden'] in {0, 2, 3}
    )


def _validate_table_snapshot(table: Any, state: Any) -> None:
    if not isinstance(table, str) or not isinstance(state, dict):
        raise SafeError('snapshot JSON table structure is invalid')
    columns = state.get('columns')
    rows = state.get('rows')
    if (
        not isinstance(columns, list)
        or not columns
        or not all(_validate_column(column) for column in columns)
        or not isinstance(rows, list)
    ):
        raise SafeError('snapshot JSON table structure is invalid')
    names = [column['name'] for column in columns]
    if len(set(names)) != len(names):
        raise SafeError('snapshot JSON contains duplicate columns')
    if state.get('row_count') != len(rows):
        raise SafeError('snapshot JSON row count is invalid')
    if any(
        not isinstance(row, list) or len(row) != len(columns) or not all(_is_hex_digest(value) for value in row)
        for row in rows
    ):
        raise SafeError('snapshot JSON row digest structure is invalid')


def _validate_file_records(files: Any) -> None:
    if not isinstance(files, list):
        raise SafeError('snapshot JSON file structure is invalid')
    path_hmacs: set[str] = set()
    for record in files:
        if (
            not isinstance(record, dict)
            or not _is_hex_digest(record.get('path_hmac'))
            or not _is_hex_digest(record.get('sha256'))
            or not isinstance(record.get('size'), int)
            or record['size'] < 0
        ):
            raise SafeError('snapshot JSON file digest structure is invalid')
        if record['path_hmac'] in path_hmacs:
            raise SafeError('snapshot JSON contains duplicate file paths')
        path_hmacs.add(record['path_hmac'])


def _validate_snapshot_structure(document: dict[str, Any]) -> None:
    database = document.get('database')
    if (
        not isinstance(database, dict)
        or database.get('integrity_check') != 'ok'
        or database.get('foreign_key_violations') != 0
        or not isinstance(database.get('tables'), dict)
    ):
        raise SafeError('snapshot JSON database structure is invalid')
    if document.get('hashes') != EXPECTED_HASHES:
        raise SafeError('snapshot JSON uses unsupported digest algorithms')

    _validate_file_policy(document.get('file_policy'))
    for table, state in database['tables'].items():
        _validate_table_snapshot(table, state)
    _validate_file_records(document.get('files'))


def _compare_database(
    before: dict[str, Any],
    after: dict[str, Any],
    mutable_tables: set[str],
) -> tuple[list[str], dict[str, int]]:
    before_tables = before['tables']
    after_tables = after['tables']
    unknown_mutable = sorted(mutable_tables - set(before_tables))
    if unknown_mutable:
        raise SafeError('one or more explicitly mutable tables are absent from the snapshot')

    errors: list[str] = []
    checked_rows = 0
    missing_columns = 0
    for table, before_state in before_tables.items():
        after_state = after_tables.get(table)
        if after_state is None:
            errors.append(f"pre-upgrade table '{table}' is missing")
            continue
        if table in mutable_tables:
            continue

        before_names = [column['name'] for column in before_state['columns']]
        after_names = [column['name'] for column in after_state['columns']]
        after_indexes = {name: index for index, name in enumerate(after_names)}
        common_names = [name for name in before_names if name in after_indexes]
        removed_from_table = len(before_names) - len(common_names)
        missing_columns += removed_from_table
        if removed_from_table:
            errors.append(f"table '{table}' is missing {removed_from_table} pre-upgrade column(s)")
        if not common_names:
            if before_state['row_count']:
                errors.append(f"table '{table}' has no common columns for row preservation")
            continue

        before_indexes = [before_names.index(name) for name in common_names]
        current_indexes = [after_indexes[name] for name in common_names]
        before_rows = Counter(tuple(row[index] for index in before_indexes) for row in before_state['rows'])
        current_rows = Counter(tuple(row[index] for index in current_indexes) for row in after_state['rows'])
        missing_rows = sum((before_rows - current_rows).values())
        checked_rows += before_state['row_count']
        if missing_rows:
            errors.append(
                f"table '{table}' is missing or changed {missing_rows} pre-upgrade row(s) "
                f'on {len(common_names)} common column(s)'
            )

    return errors, {
        'pre_upgrade_tables': len(before_tables),
        'new_tables': len(set(after_tables) - set(before_tables)),
        'checked_rows': checked_rows,
        'missing_columns': missing_columns,
        'mutable_tables': len(mutable_tables),
    }


def _compare_files(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> tuple[list[str], dict[str, int]]:
    before_by_path = {record['path_hmac']: record for record in before}
    after_by_path = {record['path_hmac']: record for record in after}
    missing = 0
    changed = 0
    for path_hmac, before_record in before_by_path.items():
        after_record = after_by_path.get(path_hmac)
        if after_record is None:
            missing += 1
        elif before_record['size'] != after_record['size'] or before_record['sha256'] != after_record['sha256']:
            changed += 1

    errors = []
    if missing:
        errors.append(f'{missing} pre-upgrade data file(s) are missing')
    if changed:
        errors.append(f'{changed} pre-upgrade data file(s) changed size or SHA-256')
    return errors, {
        'pre_upgrade_files': len(before),
        'new_files': len(set(after_by_path) - set(before_by_path)),
        'missing_files': missing,
        'changed_files': changed,
    }


def verify_snapshot(
    *,
    data_dir: Path,
    database: Path,
    snapshot: Path,
    key_file: Path,
    mutable_tables: set[str] | None = None,
) -> dict[str, Any]:
    data_dir, database, key_file = _validate_paths(
        data_dir=data_dir,
        database=database,
        key_file=key_file,
        snapshot=snapshot,
    )
    key = _load_key(key_file, create=False)
    document = _load_snapshot(snapshot.resolve(), key)
    policy = document['file_policy']
    custom_globs = tuple(policy['custom_globs'])

    expected_database_path = policy.get('database_path_hmac')
    current_database_relative = _relative_path(database, data_dir)
    current_database_path = _path_digest(key, current_database_relative) if current_database_relative else None
    if not hmac.compare_digest(str(expected_database_path or ''), str(current_database_path or '')):
        raise SafeError('current database location does not match the snapshot')

    current_database = _inspect_database(database, key)
    current_files, _ = _inspect_files(data_dir, database, key, custom_globs)
    database_errors, database_summary = _compare_database(
        document['database'],
        current_database,
        mutable_tables or set(),
    )
    file_errors, file_summary = _compare_files(document['files'], current_files)
    errors = database_errors + file_errors
    return {
        'status': 'ok' if not errors else 'failed',
        'database': database_summary,
        'files': file_summary,
        'errors': errors,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'Snapshot or verify a stopped/copied ArtiChat data directory without exposing '
            'database values, file names, or key material.'
        )
    )
    commands = parser.add_subparsers(dest='command', required=True)

    snapshot = commands.add_parser('snapshot', help='write a deterministic keyed snapshot JSON')
    snapshot.add_argument('--data-dir', type=Path, required=True)
    snapshot.add_argument('--database', type=Path)
    snapshot.add_argument('--output', type=Path, required=True)
    snapshot.add_argument('--key-file', type=Path, required=True)
    snapshot.add_argument(
        '--exclude-path',
        action='append',
        default=[],
        metavar='GLOB',
        help='explicit POSIX-style relative path glob to exclude (recorded in the snapshot)',
    )

    verify = commands.add_parser('verify', help='verify an upgraded copy against a snapshot JSON')
    verify.add_argument('--data-dir', type=Path, required=True)
    verify.add_argument('--database', type=Path)
    verify.add_argument('--snapshot', type=Path, required=True)
    verify.add_argument('--key-file', type=Path, required=True)
    verify.add_argument(
        '--allow-mutable-table',
        action='append',
        default=[],
        metavar='TABLE',
        help=('explicitly allow row changes in a pre-upgrade table; normally only alembic_version should need this'),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    database = args.database or (args.data_dir / 'webui.db')
    try:
        if args.command == 'snapshot':
            document = create_snapshot(
                data_dir=args.data_dir,
                database=database,
                output=args.output,
                key_file=args.key_file,
                custom_globs=tuple(args.exclude_path),
            )
            summary = {
                'status': 'ok',
                'tables': len(document['database']['tables']),
                'rows': sum(table['row_count'] for table in document['database']['tables'].values()),
                'files': len(document['files']),
            }
            print(json.dumps(summary, sort_keys=True))
            return 0

        report = verify_snapshot(
            data_dir=args.data_dir,
            database=database,
            snapshot=args.snapshot,
            key_file=args.key_file,
            mutable_tables=set(args.allow_mutable_table),
        )
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if report['status'] == 'ok' else 1
    except SafeError as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    except Exception:
        print(
            json.dumps({'status': 'error', 'error': 'unexpected verification failure'}, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
