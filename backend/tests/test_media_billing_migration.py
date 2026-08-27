import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_media_billing_migration_adds_usage_and_video_columns(tmp_path, monkeypatch):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'media-billing.db'}")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                'CREATE TABLE subscription_usage ('
                'id TEXT PRIMARY KEY, user_id TEXT NOT NULL, model_id TEXT NOT NULL, '
                'status TEXT NOT NULL, created_at BIGINT NOT NULL)'
            )
        )
        connection.execute(
            sa.text(
                'CREATE TABLE video_generation_job ('
                'id TEXT PRIMARY KEY, user_id TEXT NOT NULL, provider TEXT NOT NULL, '
                'prompt TEXT NOT NULL, request_payload TEXT NOT NULL, next_poll_at BIGINT NOT NULL)'
            )
        )

        migration = importlib.import_module(
            'open_webui.migrations.versions.f0a1b2c3d4e5_add_media_billing_fields'
        )
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()

        usage_columns = {column['name'] for column in sa.inspect(connection).get_columns('subscription_usage')}
        job_columns = {column['name'] for column in sa.inspect(connection).get_columns('video_generation_job')}
        assert {'usage_type', 'media_unit', 'media_units', 'media_unit_price_micros'} <= usage_columns
        assert {
            'billing_reservation_id',
            'billing_unit_count',
            'billing_unit_price_micros',
            'billing_status',
            'billing_usage_id',
        } <= job_columns

    engine.dispose()
