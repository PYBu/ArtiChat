import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_0_1_4_release_announcement_is_idempotent_and_reversible(tmp_path, monkeypatch):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'release-announcement-0.1.4.db'}")
    metadata = sa.MetaData()
    announcement = sa.Table(
        'announcement',
        metadata,
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('view_button_label', sa.Text(), nullable=False),
        sa.Column('close_button_label', sa.Text(), nullable=False),
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
        'open_webui.migrations.versions.b1c2d3e4f5a6_add_0_1_4_release_announcement'
    )
    with engine.begin() as connection:
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        migration.upgrade()

        rows = connection.execute(sa.select(announcement)).mappings().all()
        assert len(rows) == 1
        assert rows[0]['id'] == migration.ANNOUNCEMENT_ID
        assert rows[0]['title'] == 'ArtiChat 0.1.4 已发布'
        assert rows[0]['summary'] == '版本优化以及 Bug 解决。'
        assert rows[0]['body'] == '1. 邮箱系统优化，排除 Bug。\n2. 公告系统重做。'
        assert rows[0]['image_url'] == '/assets/images/space.jpg'
        assert rows[0]['view_button_label'] == '查看公告'
        assert rows[0]['close_button_label'] == '关闭'
        assert rows[0]['display_mode'] == 'once'
        assert rows[0]['icon'] == '0.1.4'
        assert rows[0]['is_active'] is True

        migration.downgrade()
        assert connection.execute(sa.select(sa.func.count()).select_from(announcement)).scalar_one() == 0

    engine.dispose()
