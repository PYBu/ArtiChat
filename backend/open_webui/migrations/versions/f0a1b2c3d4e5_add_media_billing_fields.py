"""Add media usage and video billing fields.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f0a1b2c3d4e5'
down_revision: str | None = 'e9f0a1b2c3d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if 'subscription_usage' in tables:
        columns = _columns('subscription_usage')
        additions = (
            ('usage_type', sa.Column('usage_type', sa.Text(), nullable=False, server_default='chat')),
            ('media_unit', sa.Column('media_unit', sa.Text(), nullable=True)),
            ('media_units', sa.Column('media_units', sa.Integer(), nullable=True)),
            ('media_unit_price_micros', sa.Column('media_unit_price_micros', sa.BigInteger(), nullable=True)),
        )
        for name, column in additions:
            if name not in columns:
                op.add_column('subscription_usage', column)
        if 'usage_type' not in columns:
            op.create_index('ix_subscription_usage_usage_type', 'subscription_usage', ['usage_type'])

    if 'video_generation_job' in tables:
        columns = _columns('video_generation_job')
        additions = (
            ('billing_reservation_id', sa.Column('billing_reservation_id', sa.Text(), nullable=True)),
            ('billing_unit_count', sa.Column('billing_unit_count', sa.Integer(), nullable=True)),
            ('billing_unit_price_micros', sa.Column('billing_unit_price_micros', sa.BigInteger(), nullable=True)),
            ('billing_status', sa.Column('billing_status', sa.Text(), nullable=False, server_default='none')),
            ('billing_usage_id', sa.Column('billing_usage_id', sa.Text(), nullable=True)),
        )
        for name, column in additions:
            if name not in columns:
                op.add_column('video_generation_job', column)
        if 'billing_reservation_id' not in columns:
            op.create_index('ix_video_generation_job_billing_reservation_id', 'video_generation_job', ['billing_reservation_id'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if 'video_generation_job' in tables:
        columns = _columns('video_generation_job')
        if 'billing_reservation_id' in columns:
            op.drop_index('ix_video_generation_job_billing_reservation_id', table_name='video_generation_job')
        for name in ('billing_usage_id', 'billing_status', 'billing_unit_price_micros', 'billing_unit_count', 'billing_reservation_id'):
            if name in columns:
                op.drop_column('video_generation_job', name)
    if 'subscription_usage' in tables:
        columns = _columns('subscription_usage')
        if 'usage_type' in columns:
            op.drop_index('ix_subscription_usage_usage_type', table_name='subscription_usage')
        for name in ('media_unit_price_micros', 'media_units', 'media_unit', 'usage_type'):
            if name in columns:
                op.drop_column('subscription_usage', name)
