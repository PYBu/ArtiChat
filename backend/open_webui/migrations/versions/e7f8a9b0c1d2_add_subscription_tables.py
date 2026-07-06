"""Add subscription tables

Revision ID: e7f8a9b0c1d2
Revises: 42e2978c7933
Create Date: 2026-07-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = '42e2978c7933'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'subscription_plan' not in existing_tables:
        op.create_table(
            'subscription_plan',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('display_name', sa.Text(), nullable=False),
            sa.Column('tier_rank', sa.Integer(), nullable=False),
            sa.Column('period_days', sa.Integer(), nullable=False),
            sa.Column('plan_chatpoint_allowance_micros', sa.BigInteger(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('features', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )

    if 'user_subscription' not in existing_tables:
        op.create_table(
            'user_subscription',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('user_id', sa.Text(), nullable=False, unique=True),
            sa.Column('tier', sa.Text(), nullable=False),
            sa.Column('tier_rank', sa.Integer(), nullable=False),
            sa.Column('display_name', sa.Text(), nullable=False),
            sa.Column('period_days', sa.Integer(), nullable=False),
            sa.Column('plan_chatpoint_allowance_micros', sa.BigInteger(), nullable=False),
            sa.Column('plan_balance_micros', sa.BigInteger(), nullable=False),
            sa.Column('check_balance_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('starts_at', sa.BigInteger(), nullable=False),
            sa.Column('expires_at', sa.BigInteger(), nullable=True),
            sa.Column('period_start_at', sa.BigInteger(), nullable=False),
            sa.Column('period_end_at', sa.BigInteger(), nullable=False),
            sa.Column('next_reset_at', sa.BigInteger(), nullable=False),
            sa.Column('status', sa.Text(), nullable=False),
            sa.Column('source', sa.Text(), nullable=False),
            sa.Column('snapshot', sa.JSON(), nullable=True),
            sa.Column('billing_address', sa.JSON(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_user_subscription_user_id', 'user_subscription', ['user_id'])

    if 'subscription_ledger' not in existing_tables:
        op.create_table(
            'subscription_ledger',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('event_type', sa.Text(), nullable=False),
            sa.Column('tier_before', sa.Text(), nullable=True),
            sa.Column('tier_after', sa.Text(), nullable=True),
            sa.Column('plan_delta_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('check_delta_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('plan_balance_after_micros', sa.BigInteger(), nullable=False),
            sa.Column('check_balance_after_micros', sa.BigInteger(), nullable=False),
            sa.Column('reference_type', sa.Text(), nullable=True),
            sa.Column('reference_id', sa.Text(), nullable=True),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_by', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_subscription_ledger_user_id', 'subscription_ledger', ['user_id'])

    if 'redemption_code' not in existing_tables:
        op.create_table(
            'redemption_code',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('code_hash', sa.Text(), nullable=False, unique=True),
            sa.Column('code_preview', sa.Text(), nullable=False),
            sa.Column('mode', sa.Text(), nullable=False),
            sa.Column('max_uses', sa.Integer(), nullable=False),
            sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('tier', sa.Text(), nullable=True),
            sa.Column('duration_days', sa.Integer(), nullable=True),
            sa.Column('plan_chatpoint_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('check_chatpoint_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('expires_at', sa.BigInteger(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
            sa.Column('batch_id', sa.Text(), nullable=True),
            sa.Column('memo', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Text(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_redemption_code_code_hash', 'redemption_code', ['code_hash'])

    if 'redemption_record' not in existing_tables:
        op.create_table(
            'redemption_record',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('redemption_code_id', sa.Text(), nullable=False),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('tier_before', sa.Text(), nullable=True),
            sa.Column('tier_after', sa.Text(), nullable=True),
            sa.Column('plan_delta_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('check_delta_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('subscription_expires_at_before', sa.BigInteger(), nullable=True),
            sa.Column('subscription_expires_at_after', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_redemption_record_code_id', 'redemption_record', ['redemption_code_id'])
        op.create_index('ix_redemption_record_user_id', 'redemption_record', ['user_id'])
        op.create_index(
            'redemption_record_code_user_idx',
            'redemption_record',
            ['redemption_code_id', 'user_id'],
            unique=True,
        )

    if 'subscription_usage' not in existing_tables:
        op.create_table(
            'subscription_usage',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('chat_id', sa.Text(), nullable=True),
            sa.Column('message_id', sa.Text(), nullable=True),
            sa.Column('model_id', sa.Text(), nullable=False),
            sa.Column('tier', sa.Text(), nullable=False),
            sa.Column('quota_mode', sa.Text(), nullable=False),
            sa.Column('usage_multiplier', sa.Text(), nullable=False),
            sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('cost_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('plan_cost_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('check_cost_micros', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('plan_balance_after_micros', sa.BigInteger(), nullable=True),
            sa.Column('check_balance_after_micros', sa.BigInteger(), nullable=True),
            sa.Column('status', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_subscription_usage_user_id', 'subscription_usage', ['user_id'])
        op.create_index('ix_subscription_usage_model_id', 'subscription_usage', ['model_id'])


def downgrade() -> None:
    for index_name, table_name in [
        ('ix_subscription_usage_model_id', 'subscription_usage'),
        ('ix_subscription_usage_user_id', 'subscription_usage'),
        ('redemption_record_code_user_idx', 'redemption_record'),
        ('ix_redemption_record_user_id', 'redemption_record'),
        ('ix_redemption_record_code_id', 'redemption_record'),
        ('ix_redemption_code_code_hash', 'redemption_code'),
        ('ix_subscription_ledger_user_id', 'subscription_ledger'),
        ('ix_user_subscription_user_id', 'user_subscription'),
    ]:
        try:
            op.drop_index(index_name, table_name=table_name)
        except Exception:
            pass

    for table_name in [
        'subscription_usage',
        'redemption_record',
        'redemption_code',
        'subscription_ledger',
        'user_subscription',
        'subscription_plan',
    ]:
        try:
            op.drop_table(table_name)
        except Exception:
            pass
