"""Add redemption benefit types and purge tombstones.

Revision ID: c3d4e5f6a7b8
Revises: f5a6b7c8d9e0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'f5a6b7c8d9e0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'redemption_code' not in inspector.get_table_names():
        return

    columns = _columns('redemption_code')
    if 'benefit_type' not in columns:
        op.add_column(
            'redemption_code',
            sa.Column('benefit_type', sa.Text(), nullable=True, server_default='legacy'),
        )
    if 'purged_at' not in columns:
        op.add_column('redemption_code', sa.Column('purged_at', sa.BigInteger(), nullable=True))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE redemption_code
            SET benefit_type = CASE
                WHEN check_chatpoint_micros = 0
                    AND (tier IS NOT NULL OR duration_days IS NOT NULL OR plan_chatpoint_micros > 0)
                    THEN 'subscription'
                WHEN plan_chatpoint_micros = 0
                    AND check_chatpoint_micros > 0
                    AND tier IS NULL
                    AND duration_days IS NULL
                    THEN 'recharge'
                ELSE 'legacy'
            END
            WHERE benefit_type IS NULL OR benefit_type = ''
            """
        )
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'redemption_code' not in inspector.get_table_names():
        return
    columns = _columns('redemption_code')
    if 'purged_at' in columns:
        op.drop_column('redemption_code', 'purged_at')
    if 'benefit_type' in columns:
        op.drop_column('redemption_code', 'benefit_type')
