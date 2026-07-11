"""Subscription admin polish, announcements, and gift cards

Revision ID: f2a3b4c5d6e7
Revises: e7f8a9b0c1d2
Create Date: 2026-07-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'redemption_code' in existing_tables and 'code' not in _columns('redemption_code'):
        op.add_column('redemption_code', sa.Column('code', sa.Text(), nullable=True))

    if 'gift_card_grant' not in existing_tables:
        op.create_table(
            'gift_card_grant',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('redemption_code_id', sa.Text(), nullable=False),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
            sa.Column('batch_id', sa.Text(), nullable=False),
            sa.Column('claimed_at', sa.BigInteger(), nullable=True),
            sa.Column('memo', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Text(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_gift_card_grant_redemption_code_id', 'gift_card_grant', ['redemption_code_id'])
        op.create_index('ix_gift_card_grant_user_id', 'gift_card_grant', ['user_id'])
        op.create_index('ix_gift_card_grant_batch_id', 'gift_card_grant', ['batch_id'])
        op.create_index('gift_card_grant_user_status_idx', 'gift_card_grant', ['user_id', 'status'])

    if 'announcement' not in existing_tables:
        op.create_table(
            'announcement',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('title', sa.Text(), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('display_mode', sa.Text(), nullable=False),
            sa.Column('button_label', sa.Text(), nullable=False, server_default='知道了'),
            sa.Column('icon', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
            sa.Column('starts_at', sa.BigInteger(), nullable=True),
            sa.Column('ends_at', sa.BigInteger(), nullable=True),
            sa.Column('sort_order', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('created_by', sa.Text(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )

    if 'announcement_view' not in existing_tables:
        op.create_table(
            'announcement_view',
            sa.Column('id', sa.Text(), primary_key=True),
            sa.Column('announcement_id', sa.Text(), nullable=False),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('viewed_at', sa.BigInteger(), nullable=False),
        )
        op.create_index('ix_announcement_view_announcement_id', 'announcement_view', ['announcement_id'])
        op.create_index('ix_announcement_view_user_id', 'announcement_view', ['user_id'])
        op.create_index(
            'announcement_view_announcement_user_idx',
            'announcement_view',
            ['announcement_id', 'user_id'],
            unique=True,
        )


def downgrade() -> None:
    for index_name, table_name in [
        ('announcement_view_announcement_user_idx', 'announcement_view'),
        ('ix_announcement_view_user_id', 'announcement_view'),
        ('ix_announcement_view_announcement_id', 'announcement_view'),
        ('gift_card_grant_user_status_idx', 'gift_card_grant'),
        ('ix_gift_card_grant_batch_id', 'gift_card_grant'),
        ('ix_gift_card_grant_user_id', 'gift_card_grant'),
        ('ix_gift_card_grant_redemption_code_id', 'gift_card_grant'),
    ]:
        try:
            op.drop_index(index_name, table_name=table_name)
        except Exception:
            pass

    for table_name in ['announcement_view', 'announcement', 'gift_card_grant']:
        try:
            op.drop_table(table_name)
        except Exception:
            pass

    try:
        op.drop_column('redemption_code', 'code')
    except Exception:
        pass
