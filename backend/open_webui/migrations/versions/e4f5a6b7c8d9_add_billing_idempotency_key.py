"""Add a database-enforced billing idempotency key.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e4f5a6b7c8d9'
down_revision: str = 'd3e4f5a6b7c8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if 'subscription_usage' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('subscription_usage')}
    if 'idempotency_key' not in columns:
        op.add_column('subscription_usage', sa.Column('idempotency_key', sa.String(length=64), nullable=True))

    inspector = sa.inspect(connection)
    indexes = {index['name'] for index in inspector.get_indexes('subscription_usage')}
    if 'uq_subscription_usage_idempotency_key' not in indexes:
        op.create_index(
            'uq_subscription_usage_idempotency_key',
            'subscription_usage',
            ['idempotency_key'],
            unique=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if 'subscription_usage' not in inspector.get_table_names():
        return

    indexes = {index['name'] for index in inspector.get_indexes('subscription_usage')}
    if 'uq_subscription_usage_idempotency_key' in indexes:
        op.drop_index('uq_subscription_usage_idempotency_key', table_name='subscription_usage')

    inspector = sa.inspect(connection)
    columns = {column['name'] for column in inspector.get_columns('subscription_usage')}
    if 'idempotency_key' in columns:
        op.drop_column('subscription_usage', 'idempotency_key')
