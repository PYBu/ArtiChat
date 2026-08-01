import importlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_reservation_migration_is_additive_and_preserves_balances_and_usage(tmp_path, monkeypatch):
    db_path = tmp_path / 'reservation-migration.db'
    engine = create_engine(f'sqlite:///{db_path}')

    with engine.begin() as connection:
        connection.execute(
            text(
                'CREATE TABLE user_subscription ('
                'id TEXT PRIMARY KEY, user_id TEXT NOT NULL, '
                'plan_balance_micros BIGINT NOT NULL, check_balance_micros BIGINT NOT NULL)'
            )
        )
        connection.execute(
            text(
                'INSERT INTO user_subscription '
                "(id, user_id, plan_balance_micros, check_balance_micros) VALUES ('sub-1', 'user-1', 123, 456)"
            )
        )
        connection.execute(
            text(
                'CREATE TABLE subscription_usage ('
                'id TEXT PRIMARY KEY, cost_micros BIGINT NOT NULL)'
            )
        )
        connection.execute(text("INSERT INTO subscription_usage (id, cost_micros) VALUES ('usage-1', 789)"))

        migration = importlib.import_module(
            'open_webui.migrations.versions.f5a6b7c8d9e0_add_subscription_reservations'
        )
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        migration.upgrade()

        connection.execute(
            text(
                'INSERT INTO subscription_reservation ('
                'id, user_id, request_id, model_id, idempotency_key, status, period_start_at, '
                'reserved_micros, reserved_plan_micros, reserved_check_micros, created_at, updated_at'
                ') VALUES ('
                "'reservation-1', 'user-1', 'request-1', 'model-1', 'key-1', 'active', 10, "
                '30, 20, 10, 11, 11)'
            )
        )
        connection.execute(text('DROP INDEX uq_subscription_usage_reservation_id'))
        connection.execute(text('DROP INDEX uq_subscription_reservation_idempotency_key'))

        migration.upgrade()

        inspector = inspect(connection)
        assert 'subscription_reservation' in inspector.get_table_names()
        assert {'balance_version'} <= {
            column['name'] for column in inspector.get_columns('user_subscription')
        }
        assert {'reservation_id', 'unpaid_cost_micros'} <= {
            column['name'] for column in inspector.get_columns('subscription_usage')
        }
        assert {
            'model_id',
            'reserved_micros',
            'reserved_plan_micros',
            'reserved_check_micros',
            'unpaid_cost_micros',
        } <= {column['name'] for column in inspector.get_columns('subscription_reservation')}
        usage_indexes = {index['name']: index for index in inspector.get_indexes('subscription_usage')}
        reservation_indexes = {
            index['name']: index for index in inspector.get_indexes('subscription_reservation')
        }
        assert usage_indexes['uq_subscription_usage_reservation_id']['unique'] == 1
        assert reservation_indexes['uq_subscription_reservation_idempotency_key']['unique'] == 1

        subscription = connection.execute(
            text(
                'SELECT plan_balance_micros, check_balance_micros, balance_version '
                'FROM user_subscription WHERE id = :id'
            ),
            {'id': 'sub-1'},
        ).mappings().one()
        usage = connection.execute(
            text(
                'SELECT cost_micros, unpaid_cost_micros, reservation_id '
                'FROM subscription_usage WHERE id = :id'
            ),
            {'id': 'usage-1'},
        ).mappings().one()
        assert dict(subscription) == {
            'plan_balance_micros': 123,
            'check_balance_micros': 456,
            'balance_version': 0,
        }
        assert dict(usage) == {
            'cost_micros': 789,
            'unpaid_cost_micros': 0,
            'reservation_id': None,
        }
        reservation = connection.execute(
            text(
                'SELECT user_id, reserved_micros, reserved_plan_micros, reserved_check_micros '
                'FROM subscription_reservation WHERE id = :id'
            ),
            {'id': 'reservation-1'},
        ).mappings().one()
        assert dict(reservation) == {
            'user_id': 'user-1',
            'reserved_micros': 30,
            'reserved_plan_micros': 20,
            'reserved_check_micros': 10,
        }

    engine.dispose()


def test_reservation_migration_rebuilds_an_empty_partial_table(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'partial-reservation.db'}")

    with engine.begin() as connection:
        connection.execute(
            text('CREATE TABLE subscription_reservation (id TEXT PRIMARY KEY, user_id TEXT NOT NULL)')
        )

        migration = importlib.import_module(
            'open_webui.migrations.versions.f5a6b7c8d9e0_add_subscription_reservations'
        )
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        migration.upgrade()

        inspector = inspect(connection)
        assert migration.RESERVATION_COLUMN_NAMES == {
            column['name'] for column in inspector.get_columns('subscription_reservation')
        }
        indexes = {index['name']: index for index in inspector.get_indexes('subscription_reservation')}
        assert set(indexes) == {name for name, _columns, _unique in migration.RESERVATION_INDEXES}
        assert indexes['uq_subscription_reservation_idempotency_key']['unique'] == 1

    engine.dispose()


def test_reservation_migration_refuses_to_drop_a_populated_partial_table(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'populated-partial-reservation.db'}")

    with engine.begin() as connection:
        connection.execute(
            text('CREATE TABLE subscription_reservation (id TEXT PRIMARY KEY, user_id TEXT NOT NULL)')
        )
        connection.execute(
            text("INSERT INTO subscription_reservation (id, user_id) VALUES ('keep-me', 'user-1')")
        )

        migration = importlib.import_module(
            'open_webui.migrations.versions.f5a6b7c8d9e0_add_subscription_reservations'
        )
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        with pytest.raises(RuntimeError, match='Cannot safely repair a populated partial'):
            migration.upgrade()

        assert connection.execute(
            text("SELECT user_id FROM subscription_reservation WHERE id = 'keep-me'")
        ).scalar_one() == 'user-1'

    engine.dispose()
