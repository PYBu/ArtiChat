"""Add revocable public share records for user assets."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f0a1b2c3d4e6'
down_revision: str | None = 'f0a1b2c3d4e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if 'asset_share' in tables:
        existing_columns = {column['name'] for column in inspector.get_columns('asset_share')}
        additions = (
            ('file_id', sa.Column('file_id', sa.String(), nullable=True)),
            ('owner_id', sa.Column('owner_id', sa.String(), nullable=True)),
            ('token_hash', sa.Column('token_hash', sa.Text(), nullable=True)),
            ('expires_at', sa.Column('expires_at', sa.BigInteger(), nullable=True)),
            ('revoked_at', sa.Column('revoked_at', sa.BigInteger(), nullable=True)),
            ('created_at', sa.Column('created_at', sa.BigInteger(), nullable=True)),
            ('last_access_at', sa.Column('last_access_at', sa.BigInteger(), nullable=True)),
        )
        for name, column in additions:
            if name not in existing_columns:
                op.add_column('asset_share', column)
        existing_indexes = {index['name'] for index in inspector.get_indexes('asset_share')}
        if 'ix_asset_share_file_id' not in existing_indexes:
            op.create_index('ix_asset_share_file_id', 'asset_share', ['file_id'])
        if 'ix_asset_share_owner_id' not in existing_indexes:
            op.create_index('ix_asset_share_owner_id', 'asset_share', ['owner_id'])
        if 'ix_asset_share_token_hash' not in existing_indexes:
            op.create_index('ix_asset_share_token_hash', 'asset_share', ['token_hash'], unique=True)
        return

    op.create_table(
        'asset_share',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('file_id', sa.String(), nullable=False),
        sa.Column('owner_id', sa.String(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=True),
        sa.Column('revoked_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('last_access_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_asset_share_file_id', 'asset_share', ['file_id'])
    op.create_index('ix_asset_share_owner_id', 'asset_share', ['owner_id'])
    op.create_index('ix_asset_share_token_hash', 'asset_share', ['token_hash'], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'asset_share' not in inspector.get_table_names():
        return
    indexes = {index['name'] for index in inspector.get_indexes('asset_share')}
    for name in ('ix_asset_share_token_hash', 'ix_asset_share_owner_id', 'ix_asset_share_file_id'):
        if name in indexes:
            op.drop_index(name, table_name='asset_share')
    op.drop_table('asset_share')
