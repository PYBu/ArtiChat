"""Add email security and delivery tables.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if 'email_challenge' not in existing:
        op.create_table('email_challenge', sa.Column('id', sa.Text(), primary_key=True), sa.Column('email', sa.Text(), nullable=False), sa.Column('purpose', sa.Text(), nullable=False), sa.Column('code_hash', sa.Text(), nullable=False), sa.Column('user_id', sa.Text(), nullable=True), sa.Column('session_id', sa.Text(), nullable=True), sa.Column('ip_address', sa.Text(), nullable=True), sa.Column('expires_at', sa.BigInteger(), nullable=False), sa.Column('resend_available_at', sa.BigInteger(), nullable=False), sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'), sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'), sa.Column('consumed_at', sa.BigInteger(), nullable=True), sa.Column('created_at', sa.BigInteger(), nullable=False))
        op.create_index('ix_email_challenge_email', 'email_challenge', ['email'])
        op.create_index('ix_email_challenge_purpose', 'email_challenge', ['purpose'])
        op.create_index('ix_email_challenge_user_id', 'email_challenge', ['user_id'])
        op.create_index('email_challenge_lookup_idx', 'email_challenge', ['email', 'purpose', 'created_at'])
    if 'password_reset_token' not in existing:
        op.create_table('password_reset_token', sa.Column('id', sa.Text(), primary_key=True), sa.Column('email', sa.Text(), nullable=False), sa.Column('user_id', sa.Text(), nullable=False), sa.Column('token_hash', sa.Text(), nullable=False, unique=True), sa.Column('expires_at', sa.BigInteger(), nullable=False), sa.Column('consumed_at', sa.BigInteger(), nullable=True), sa.Column('ip_address', sa.Text(), nullable=True), sa.Column('created_at', sa.BigInteger(), nullable=False))
        op.create_index('ix_password_reset_token_email', 'password_reset_token', ['email'])
        op.create_index('ix_password_reset_token_user_id', 'password_reset_token', ['user_id'])
        op.create_index('ix_password_reset_token_token_hash', 'password_reset_token', ['token_hash'], unique=True)
    if 'email_template' not in existing:
        op.create_table('email_template', sa.Column('key', sa.Text(), primary_key=True), sa.Column('subject', sa.Text(), nullable=False), sa.Column('markdown_body', sa.Text(), nullable=False), sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()), sa.Column('updated_at', sa.BigInteger(), nullable=False))
    if 'email_delivery' not in existing:
        op.create_table('email_delivery', sa.Column('id', sa.Text(), primary_key=True), sa.Column('template_key', sa.Text(), nullable=False), sa.Column('recipient', sa.Text(), nullable=False), sa.Column('subject', sa.Text(), nullable=False), sa.Column('html_body', sa.Text(), nullable=False), sa.Column('text_body', sa.Text(), nullable=False), sa.Column('variables', sa.JSON(), nullable=True), sa.Column('status', sa.Text(), nullable=False), sa.Column('error', sa.Text(), nullable=True), sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'), sa.Column('last_attempt_at', sa.BigInteger(), nullable=True), sa.Column('sent_at', sa.BigInteger(), nullable=True), sa.Column('created_at', sa.BigInteger(), nullable=False))
        op.create_index('ix_email_delivery_template_key', 'email_delivery', ['template_key'])
        op.create_index('ix_email_delivery_recipient', 'email_delivery', ['recipient'])
        op.create_index('ix_email_delivery_status', 'email_delivery', ['status'])


def downgrade() -> None:
    for table in ['email_delivery', 'email_template', 'password_reset_token', 'email_challenge']:
        try:
            op.drop_table(table)
        except Exception:
            pass
