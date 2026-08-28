"""Add login access restriction rules and short-lived login history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f0a1b2c3d4e7'
down_revision: str | None = 'f0a1b2c3d4e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if 'access_restriction_ip_rule' not in tables:
        op.create_table(
            'access_restriction_ip_rule',
            sa.Column('id', sa.Text(), nullable=False),
            sa.Column('network', sa.Text(), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Text(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('network', name='uq_access_restriction_ip_network'),
        )
        op.create_index('ix_access_restriction_ip_enabled', 'access_restriction_ip_rule', ['enabled'])

    if 'access_restriction_region_rule' not in tables:
        op.create_table(
            'access_restriction_region_rule',
            sa.Column('id', sa.Text(), nullable=False),
            sa.Column('country_code', sa.Text(), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Text(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('country_code', name='uq_access_restriction_country_code'),
        )
        op.create_index('ix_access_restriction_region_enabled', 'access_restriction_region_rule', ['enabled'])

    if 'login_event' not in tables:
        op.create_table(
            'login_event',
            sa.Column('id', sa.Text(), nullable=False),
            sa.Column('user_id', sa.Text(), nullable=True),
            sa.Column('user_email', sa.Text(), nullable=True),
            sa.Column('user_name', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.Text(), nullable=True),
            sa.Column('country_code', sa.Text(), nullable=True),
            sa.Column('auth_method', sa.Text(), nullable=False),
            sa.Column('result', sa.Text(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('rule_id', sa.Text(), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_login_event_user_id', 'login_event', ['user_id'])
        op.create_index('ix_login_event_user_email', 'login_event', ['user_email'])
        op.create_index('ix_login_event_ip_address', 'login_event', ['ip_address'])
        op.create_index('ix_login_event_country_code', 'login_event', ['country_code'])
        op.create_index('ix_login_event_result', 'login_event', ['result'])
        op.create_index('ix_login_event_created_at', 'login_event', ['created_at'])
        op.create_index('login_event_search_idx', 'login_event', ['user_email', 'user_name'])
        op.create_index('login_event_created_result_idx', 'login_event', ['created_at', 'result'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if 'login_event' in tables:
        indexes = {index['name'] for index in inspector.get_indexes('login_event')}
        for name in (
            'login_event_created_result_idx',
            'login_event_search_idx',
            'ix_login_event_created_at',
            'ix_login_event_result',
            'ix_login_event_country_code',
            'ix_login_event_ip_address',
            'ix_login_event_user_email',
            'ix_login_event_user_id',
        ):
            if name in indexes:
                op.drop_index(name, table_name='login_event')
        op.drop_table('login_event')

    if 'access_restriction_region_rule' in tables:
        indexes = {index['name'] for index in inspector.get_indexes('access_restriction_region_rule')}
        if 'ix_access_restriction_region_enabled' in indexes:
            op.drop_index('ix_access_restriction_region_enabled', table_name='access_restriction_region_rule')
        op.drop_table('access_restriction_region_rule')

    if 'access_restriction_ip_rule' in tables:
        indexes = {index['name'] for index in inspector.get_indexes('access_restriction_ip_rule')}
        if 'ix_access_restriction_ip_enabled' in indexes:
            op.drop_index('ix_access_restriction_ip_enabled', table_name='access_restriction_ip_rule')
        op.drop_table('access_restriction_ip_rule')
