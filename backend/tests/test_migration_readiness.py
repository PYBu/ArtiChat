from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from open_webui.internal import migrations
from sqlalchemy import create_engine, text

OPEN_WEBUI_DIR = Path(__file__).resolve().parents[1] / 'open_webui'


@pytest.fixture(autouse=True)
def isolated_migration_environment(monkeypatch, tmp_path):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('WEBUI_SECRET_KEY', 'test-only-migration-readiness-secret-key')


def test_packaged_graph_has_expected_merged_head_and_parents():
    config = migrations.make_alembic_config(OPEN_WEBUI_DIR)
    scripts = ScriptDirectory.from_config(config)

    assert frozenset(scripts.get_heads()) == migrations.EXPECTED_ALEMBIC_HEADS
    assert scripts.get_revision('d3e4f5a6b7c8').down_revision == ('c2d3e4f5a6b7', 'f0bd01a18a3d')


def test_migration_exception_propagates(monkeypatch):
    class MigrationFailure(RuntimeError):
        pass

    def fail_upgrade(*_args, **_kwargs):
        raise MigrationFailure('migration failed')

    monkeypatch.setattr(migrations.command, 'upgrade', fail_upgrade)

    with pytest.raises(MigrationFailure, match='migration failed'):
        migrations.upgrade_database(OPEN_WEBUI_DIR)


def test_schema_gate_accepts_expected_head_and_required_structure():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'))
        connection.execute(text("INSERT INTO alembic_version VALUES ('d3e4f5a6b7c8')"))
        connection.execute(text('CREATE TABLE chat (id TEXT, variables TEXT)'))

    migrations.assert_database_schema_ready(
        engine,
        required_schema={'chat': frozenset({'id', 'variables'})},
    )


@pytest.mark.parametrize(
    ('installed_head', 'columns', 'message'),
    [
        ('f0bd01a18a3d', 'id TEXT, variables TEXT', 'Database Alembic heads'),
        ('d3e4f5a6b7c8', 'id TEXT', 'column chat.variables'),
    ],
)
def test_schema_gate_rejects_wrong_head_or_partial_schema(installed_head, columns, message):
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'))
        connection.execute(text('INSERT INTO alembic_version VALUES (:head)'), {'head': installed_head})
        connection.execute(text(f'CREATE TABLE chat ({columns})'))

    with pytest.raises(migrations.DatabaseSchemaNotReadyError, match=message):
        migrations.assert_database_schema_ready(
            engine,
            required_schema={'chat': frozenset({'id', 'variables'})},
        )
