"""Add visual presentation fields to announcements.

Revision ID: 0a1b2c3d4e5f
Revises: f9a0b1c2d3e4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0a1b2c3d4e5f'
down_revision: Union[str, None] = 'f9a0b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_IMAGE_URL = '/assets/images/space.jpg'
DEFAULT_VIEW_LABEL = '查看公告'
DEFAULT_CLOSE_LABEL = '关闭'


def _columns() -> set[str]:
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns('announcement')}


def upgrade() -> None:
    conn = op.get_bind()
    if 'announcement' not in sa.inspect(conn).get_table_names():
        return

    existing = _columns()
    additions = (
        ('summary', sa.Column('summary', sa.Text(), nullable=False, server_default='')),
        ('image_url', sa.Column('image_url', sa.Text(), nullable=True, server_default=DEFAULT_IMAGE_URL)),
        (
            'view_button_label',
            sa.Column('view_button_label', sa.Text(), nullable=False, server_default=DEFAULT_VIEW_LABEL),
        ),
        (
            'close_button_label',
            sa.Column('close_button_label', sa.Text(), nullable=False, server_default=DEFAULT_CLOSE_LABEL),
        ),
    )
    added_columns = set()
    for name, column in additions:
        if name not in existing:
            op.add_column('announcement', column)
            added_columns.add(name)

    announcement = sa.table(
        'announcement',
        sa.column('body', sa.Text()),
        sa.column('button_label', sa.Text()),
        sa.column('summary', sa.Text()),
        sa.column('image_url', sa.Text()),
        sa.column('view_button_label', sa.Text()),
        sa.column('close_button_label', sa.Text()),
    )
    conn.execute(
        announcement.update()
        .where(sa.or_(announcement.c.summary.is_(None), announcement.c.summary == ''))
        .values(summary=announcement.c.body)
    )
    conn.execute(
        announcement.update()
        .where(sa.or_(announcement.c.image_url.is_(None), announcement.c.image_url == ''))
        .values(image_url=DEFAULT_IMAGE_URL)
    )
    conn.execute(
        announcement.update()
        .where(sa.or_(announcement.c.view_button_label.is_(None), announcement.c.view_button_label == ''))
        .values(view_button_label=DEFAULT_VIEW_LABEL)
    )
    close_label_update = announcement.update()
    if 'close_button_label' not in added_columns:
        close_label_update = close_label_update.where(
            sa.or_(announcement.c.close_button_label.is_(None), announcement.c.close_button_label == '')
        )
    conn.execute(
        close_label_update.values(
            close_button_label=sa.func.coalesce(announcement.c.button_label, DEFAULT_CLOSE_LABEL)
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if 'announcement' not in sa.inspect(conn).get_table_names():
        return

    existing = _columns()
    for column_name in ['close_button_label', 'view_button_label', 'image_url', 'summary']:
        if column_name in existing:
            op.drop_column('announcement', column_name)
