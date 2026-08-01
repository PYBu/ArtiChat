import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_release_announcement_migration_is_idempotent_and_reversible(tmp_path, monkeypatch):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'release-announcement.db'}")
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
        'open_webui.migrations.versions.f9a0b1c2d3e4_add_0_1_3_release_announcement'
    )
    with engine.begin() as connection:
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        migration.upgrade()

        rows = connection.execute(sa.select(announcement)).mappings().all()
        assert len(rows) == 1
        assert rows[0]['id'] == migration.ANNOUNCEMENT_ID
        assert rows[0]['title'] == 'ArtiChat 0.1.3 已发布'
        assert rows[0]['display_mode'] == 'once'
        assert rows[0]['button_label'] == '开始使用'
        assert rows[0]['is_active'] is True
        assert '品牌化 HTML 邮件' in rows[0]['body']
        assert '数据库迁移' in rows[0]['body']

        migration.downgrade()
        assert connection.execute(sa.select(sa.func.count()).select_from(announcement)).scalar_one() == 0

    engine.dispose()
