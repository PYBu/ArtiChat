"""Add email verification state and ticket claims.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('user')}
    if 'email_verified_at' not in columns:
        with op.batch_alter_table('user') as batch_op:
            batch_op.add_column(sa.Column('email_verified_at', sa.BigInteger(), nullable=True))
    challenge_columns = {column['name'] for column in inspector.get_columns('email_challenge')}
    if 'claimed_at' not in challenge_columns:
        with op.batch_alter_table('email_challenge') as batch_op:
            batch_op.add_column(sa.Column('claimed_at', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    challenge_columns = {column['name'] for column in inspector.get_columns('email_challenge')}
    if 'claimed_at' in challenge_columns:
        with op.batch_alter_table('email_challenge') as batch_op:
            batch_op.drop_column('claimed_at')
    columns = {column['name'] for column in inspector.get_columns('user')}
    if 'email_verified_at' in columns:
        with op.batch_alter_table('user') as batch_op:
            batch_op.drop_column('email_verified_at')
