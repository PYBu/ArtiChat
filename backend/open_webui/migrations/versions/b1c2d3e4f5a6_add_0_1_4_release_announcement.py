"""Add the ArtiChat 0.1.4 release announcement.

Revision ID: b1c2d3e4f5a6
Revises: 0a1b2c3d4e5f
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '0a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ANNOUNCEMENT_ID = 'ann_release_0_1_4'
ANNOUNCEMENT_TITLE = 'ArtiChat 0.1.4 已发布'
ANNOUNCEMENT_SUMMARY = '版本优化以及 Bug 解决。'
ANNOUNCEMENT_BODY = """1. 邮箱系统优化，排除 Bug。
2. 公告系统重做。"""
ANNOUNCEMENT_IMAGE_URL = '/assets/images/space.jpg'
RELEASED_AT = 1_784_044_800


def _announcement_table() -> sa.TableClause:
    return sa.table(
        'announcement',
        sa.column('id', sa.Text()),
        sa.column('title', sa.Text()),
        sa.column('summary', sa.Text()),
        sa.column('body', sa.Text()),
        sa.column('image_url', sa.Text()),
        sa.column('view_button_label', sa.Text()),
        sa.column('close_button_label', sa.Text()),
        sa.column('display_mode', sa.Text()),
        sa.column('button_label', sa.Text()),
        sa.column('icon', sa.Text()),
        sa.column('is_active', sa.Boolean()),
        sa.column('starts_at', sa.BigInteger()),
        sa.column('ends_at', sa.BigInteger()),
        sa.column('sort_order', sa.BigInteger()),
        sa.column('created_by', sa.Text()),
        sa.column('created_at', sa.BigInteger()),
        sa.column('updated_at', sa.BigInteger()),
    )


def upgrade() -> None:
    conn = op.get_bind()
    if 'announcement' not in sa.inspect(conn).get_table_names():
        return

    announcement = _announcement_table()
    exists = conn.execute(
        sa.select(announcement.c.id).where(announcement.c.id == ANNOUNCEMENT_ID)
    ).scalar_one_or_none()
    if exists is not None:
        return

    conn.execute(
        announcement.insert().values(
            id=ANNOUNCEMENT_ID,
            title=ANNOUNCEMENT_TITLE,
            summary=ANNOUNCEMENT_SUMMARY,
            body=ANNOUNCEMENT_BODY,
            image_url=ANNOUNCEMENT_IMAGE_URL,
            view_button_label='查看公告',
            close_button_label='关闭',
            display_mode='once',
            button_label='关闭',
            icon='0.1.4',
            is_active=True,
            starts_at=None,
            ends_at=None,
            sort_order=-110,
            created_by='system',
            created_at=RELEASED_AT,
            updated_at=RELEASED_AT,
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if 'announcement' not in sa.inspect(conn).get_table_names():
        return

    announcement = _announcement_table()
    conn.execute(announcement.delete().where(announcement.c.id == ANNOUNCEMENT_ID))
