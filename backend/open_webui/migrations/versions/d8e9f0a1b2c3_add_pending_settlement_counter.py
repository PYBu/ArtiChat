"""Add a per-user pending settlement counter.

Revision ID: d8e9f0a1b2c3
Revises: c3d4e5f6a7b8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd8e9f0a1b2c3'
down_revision: str | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'user_subscription' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('user_subscription')}
    if 'pending_settlement_count' not in columns:
        # Existing rows remain NULL and are reconciled under the user billing
        # lock on their first deferred settlement.
        op.add_column(
            'user_subscription',
            sa.Column('pending_settlement_count', sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'user_subscription' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('user_subscription')}
    if 'pending_settlement_count' in columns:
        op.drop_column('user_subscription', 'pending_settlement_count')
