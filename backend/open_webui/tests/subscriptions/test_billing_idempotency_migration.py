import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_billing_idempotency_migration_preserves_legacy_duplicate_request_ids(tmp_path, monkeypatch):
    db_path = tmp_path / 'billing-idempotency-migration.db'
    engine = create_engine(f'sqlite:///{db_path}')

    with engine.begin() as connection:
        connection.execute(
            text(
                'CREATE TABLE subscription_usage ('
                'id TEXT PRIMARY KEY, '
                'request_id TEXT NULL'
                ')'
            )
        )
        connection.execute(
            text(
                "INSERT INTO subscription_usage (id, request_id) VALUES "
                "('usage-1', 'legacy-retry'), ('usage-2', 'legacy-retry')"
            )
        )

        migration = importlib.import_module(
            'open_webui.migrations.versions.e4f5a6b7c8d9_add_billing_idempotency_key'
        )
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        migration.upgrade()

        rows = connection.execute(
            text(
                'SELECT id, request_id, idempotency_key '
                'FROM subscription_usage ORDER BY id'
            )
        ).mappings().all()
        indexes = {index['name']: index for index in inspect(connection).get_indexes('subscription_usage')}

        assert [dict(row) for row in rows] == [
            {'id': 'usage-1', 'request_id': 'legacy-retry', 'idempotency_key': None},
            {'id': 'usage-2', 'request_id': 'legacy-retry', 'idempotency_key': None},
        ]
        assert indexes['uq_subscription_usage_idempotency_key']['unique'] == 1

        migration.downgrade()
        assert 'idempotency_key' not in {
            column['name'] for column in inspect(connection).get_columns('subscription_usage')
        }

    engine.dispose()
