"""Add persistent user authentication epochs.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, None] = 'c6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('user')}
    if 'auth_epoch' not in columns:
        with op.batch_alter_table('user') as batch_op:
            batch_op.add_column(sa.Column('auth_epoch', sa.String(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('user')}
    if 'auth_epoch' in columns:
        with op.batch_alter_table('user') as batch_op:
            batch_op.drop_column('auth_epoch')
