import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_announcement_presentation_migration_backfills_legacy_rows(tmp_path, monkeypatch):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'announcement-presentation.db'}")
    metadata = sa.MetaData()
    announcement = sa.Table(
        'announcement',
        metadata,
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('display_mode', sa.Text(), nullable=False),
        sa.Column('button_label', sa.Text(), nullable=False),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('starts_at', sa.BigInteger(), nullable=True),
        sa.Column('ends_at', sa.BigInteger(), nullable=True),
        sa.Column('sort_order', sa.BigInteger(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )
    metadata.create_all(engine)

    migration = importlib.import_module(
        'open_webui.migrations.versions.0a1b2c3d4e5f_add_announcement_presentation_fields'
    )
    with engine.begin() as connection:
        connection.execute(
            announcement.insert().values(
                id='legacy-announcement',
                title='Legacy title',
                body='Legacy full content',
                display_mode='once',
                button_label='开始使用',
                icon='0.1.3',
                is_active=True,
                sort_order=0,
                created_by='system',
                created_at=1,
                updated_at=1,
            )
        )
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        migration.upgrade()

        upgraded = sa.Table('announcement', sa.MetaData(), autoload_with=connection)
        row = connection.execute(sa.select(upgraded)).mappings().one()
        assert row['summary'] == 'Legacy full content'
        assert row['image_url'] == '/assets/images/space.jpg'
        assert row['view_button_label'] == '查看公告'
        assert row['close_button_label'] == '开始使用'

        migration.downgrade()
        remaining_columns = {column['name'] for column in sa.inspect(connection).get_columns('announcement')}
        assert {'summary', 'image_url', 'view_button_label', 'close_button_label'}.isdisjoint(
            remaining_columns
        )
        assert connection.execute(sa.text('SELECT body FROM announcement')).scalar_one() == 'Legacy full content'

    engine.dispose()
