import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_default_announcement_cleanup_preserves_admin_content(tmp_path, monkeypatch):
    engine = sa.create_engine(f'sqlite:///{tmp_path / "announcement-cleanup.db"}')
    metadata = sa.MetaData()
    announcement = sa.Table(
        'announcement',
        metadata,
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Text(), nullable=False),
    )
    announcement_view = sa.Table(
        'announcement_view',
        metadata,
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('announcement_id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
    )
    metadata.create_all(engine)

    migration = importlib.import_module('open_webui.migrations.versions.c2d3e4f5a6b7_remove_default_announcements')
    with engine.begin() as connection:
        connection.execute(
            announcement.insert(),
            [
                {'id': 'ann_release_0_1_3', 'title': 'Release 0.1.3', 'created_by': 'system'},
                {'id': 'ann_release_0_1_4', 'title': 'Release 0.1.4', 'created_by': 'system'},
                {'id': 'admin-announcement', 'title': 'Admin content', 'created_by': 'admin-1'},
            ],
        )
        connection.execute(
            announcement_view.insert(),
            [
                {'id': 'view-system', 'announcement_id': 'ann_release_0_1_4', 'user_id': 'user-1'},
                {'id': 'view-admin', 'announcement_id': 'admin-announcement', 'user_id': 'user-1'},
            ],
        )
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        migration.upgrade()

        assert connection.execute(sa.select(announcement.c.id)).scalars().all() == ['admin-announcement']
        assert connection.execute(sa.select(announcement_view.c.id)).scalars().all() == ['view-admin']

        migration.downgrade()
        assert connection.execute(sa.select(announcement.c.id)).scalar_one() == 'admin-announcement'

    engine.dispose()
