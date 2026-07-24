"""Remove system-seeded default announcements.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SYSTEM_ANNOUNCEMENT_CREATOR = 'system'


def upgrade() -> None:
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if 'announcement' not in tables:
        return

    announcement = sa.table(
        'announcement',
        sa.column('id', sa.Text()),
        sa.column('created_by', sa.Text()),
    )
    default_ids = sa.select(announcement.c.id).where(
        announcement.c.created_by == SYSTEM_ANNOUNCEMENT_CREATOR
    )

    if 'announcement_view' in tables:
        announcement_view = sa.table(
            'announcement_view',
            sa.column('announcement_id', sa.Text()),
        )
        conn.execute(
            announcement_view.delete().where(
                announcement_view.c.announcement_id.in_(default_ids)
            )
        )

    conn.execute(
        announcement.delete().where(
            announcement.c.created_by == SYSTEM_ANNOUNCEMENT_CREATOR
        )
    )


def downgrade() -> None:
    # Removed system content is intentionally not recreated during rollback.
    pass
