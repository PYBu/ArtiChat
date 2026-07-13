import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from open_webui.models.subscriptions import SubscriptionUsage


NEW_USAGE_COLUMNS = {
    'request_id',
    'cache_creation_tokens',
    'cache_read_tokens',
    'input_chatpoint_per_million',
    'output_chatpoint_per_million',
    'cache_creation_chatpoint_per_million',
    'cache_read_chatpoint_per_million',
    'first_token_latency_ms',
    'total_duration_ms',
    'client_ip',
    'raw_usage',
}


def test_subscription_usage_orm_exposes_pricing_and_audit_columns():
    assert NEW_USAGE_COLUMNS <= set(SubscriptionUsage.__table__.columns.keys())


def test_usage_migration_adds_columns_and_backfills_legacy_model_policy(tmp_path, monkeypatch):
    db_path = tmp_path / 'usage-migration.db'
    engine = sa.create_engine(f'sqlite:///{db_path}')
    metadata = sa.MetaData()
    model = sa.Table(
        'model',
        metadata,
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('meta', sa.JSON(), nullable=True),
    )
    sa.Table(
        'subscription_usage',
        metadata,
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            model.insert().values(
                id='legacy-model',
                meta={
                    'description': 'keep-me',
                    'subscription': {
                        'allowed_tiers': ['free'],
                        'quota_mode': 'metered',
                        'usage_multiplier': '2.5',
                    },
                },
            )
        )

        migration = importlib.import_module(
            'open_webui.migrations.versions.a4b5c6d7e8f9_add_usage_pricing_and_audit'
        )
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, 'op', operations)
        migration.upgrade()

        inspector = sa.inspect(connection)
        assert NEW_USAGE_COLUMNS <= {column['name'] for column in inspector.get_columns('subscription_usage')}

        migrated_meta = connection.execute(sa.select(model.c.meta).where(model.c.id == 'legacy-model')).scalar_one()
        policy = migrated_meta['subscription']
        assert migrated_meta['description'] == 'keep-me'
        assert policy['usage_multiplier'] == '2.5'
        assert policy['input_chatpoint_per_million'] == '250'
        assert policy['output_chatpoint_per_million'] == '250'
        assert policy['cache_creation_chatpoint_per_million'] == '0'
        assert policy['cache_read_chatpoint_per_million'] == '0'

    engine.dispose()
