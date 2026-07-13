"""Add HTML bodies to customizable email templates.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('email_template')}
    if 'html_body' not in columns:
        with op.batch_alter_table('email_template') as batch_op:
            batch_op.add_column(sa.Column('html_body', sa.Text(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('email_template')}
    if 'html_body' in columns:
        with op.batch_alter_table('email_template') as batch_op:
            batch_op.drop_column('html_body')
