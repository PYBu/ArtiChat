"""Add durable Chatpoint reservations and unpaid usage audit.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f5a6b7c8d9e0'
down_revision: str = 'e4f5a6b7c8d9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RESERVATION_COLUMN_NAMES = frozenset(
    {
        'id',
        'user_id',
        'request_id',
        'model_id',
        'idempotency_key',
        'status',
        'period_start_at',
        'reserved_micros',
        'reserved_plan_micros',
        'reserved_check_micros',
        'actual_cost_micros',
        'settled_plan_micros',
        'settled_check_micros',
        'refunded_plan_micros',
        'refunded_check_micros',
        'forfeited_plan_micros',
        'unpaid_cost_micros',
        'expires_at',
        'release_reason',
        'metadata',
        'created_at',
        'updated_at',
        'settled_at',
        'released_at',
    }
)

RESERVATION_INDEXES = (
    ('ix_subscription_reservation_user_id', ('user_id',), False),
    ('uq_subscription_reservation_idempotency_key', ('idempotency_key',), True),
    ('ix_subscription_reservation_user_status', ('user_id', 'status'), False),
    ('ix_subscription_reservation_status_expires', ('status', 'expires_at'), False),
)


def _create_reservation_table() -> None:
    op.create_table(
        'subscription_reservation',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('request_id', sa.Text(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='active'),
        sa.Column('period_start_at', sa.BigInteger(), nullable=False),
        sa.Column('reserved_micros', sa.BigInteger(), nullable=False),
        sa.Column('reserved_plan_micros', sa.BigInteger(), nullable=False),
        sa.Column('reserved_check_micros', sa.BigInteger(), nullable=False),
        sa.Column('actual_cost_micros', sa.BigInteger(), nullable=True),
        sa.Column('settled_plan_micros', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('settled_check_micros', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('refunded_plan_micros', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('refunded_check_micros', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('forfeited_plan_micros', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('unpaid_cost_micros', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.BigInteger(), nullable=True),
        sa.Column('release_reason', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('settled_at', sa.BigInteger(), nullable=True),
        sa.Column('released_at', sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'settled', 'partially_settled', 'released', 'expired')",
            name='ck_subscription_reservation_status',
        ),
        sa.CheckConstraint('reserved_micros >= 0', name='ck_subscription_reservation_reserved_nonnegative'),
        sa.CheckConstraint(
            'reserved_plan_micros >= 0 AND reserved_check_micros >= 0',
            name='ck_subscription_reservation_split_nonnegative',
        ),
        sa.CheckConstraint(
            'reserved_micros = reserved_plan_micros + reserved_check_micros',
            name='ck_subscription_reservation_split_total',
        ),
        sa.CheckConstraint(
            'settled_plan_micros >= 0 AND settled_check_micros >= 0',
            name='ck_subscription_reservation_settled_nonnegative',
        ),
        sa.CheckConstraint(
            'refunded_plan_micros >= 0 AND refunded_check_micros >= 0',
            name='ck_subscription_reservation_refunded_nonnegative',
        ),
        sa.CheckConstraint(
            'forfeited_plan_micros >= 0 AND unpaid_cost_micros >= 0',
            name='ck_subscription_reservation_audit_nonnegative',
        ),
    )


def _ensure_index(
    connection: sa.Connection,
    table_name: str,
    index_name: str,
    column_names: tuple[str, ...],
    *,
    unique: bool,
) -> None:
    indexes = {index['name']: index for index in sa.inspect(connection).get_indexes(table_name)}
    existing = indexes.get(index_name)
    if existing is not None:
        existing_columns = tuple(existing.get('column_names') or ())
        if bool(existing.get('unique')) == unique and existing_columns == column_names:
            return
        op.drop_index(index_name, table_name=table_name)

    op.create_index(index_name, table_name, list(column_names), unique=unique)


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if 'user_subscription' in tables:
        subscription_columns = {column['name'] for column in inspector.get_columns('user_subscription')}
        if 'balance_version' not in subscription_columns:
            op.add_column(
                'user_subscription',
                sa.Column('balance_version', sa.BigInteger(), nullable=False, server_default='0'),
            )

    if 'subscription_usage' in tables:
        usage_columns = {column['name'] for column in inspector.get_columns('subscription_usage')}
        if 'unpaid_cost_micros' not in usage_columns:
            op.add_column(
                'subscription_usage',
                sa.Column('unpaid_cost_micros', sa.BigInteger(), nullable=False, server_default='0'),
            )
        if 'reservation_id' not in usage_columns:
            op.add_column('subscription_usage', sa.Column('reservation_id', sa.Text(), nullable=True))

        _ensure_index(
            connection,
            'subscription_usage',
            'uq_subscription_usage_reservation_id',
            ('reservation_id',),
            unique=True,
        )

    if 'subscription_reservation' in tables:
        reservation_columns = {
            column['name'] for column in sa.inspect(connection).get_columns('subscription_reservation')
        }
        missing_columns = RESERVATION_COLUMN_NAMES - reservation_columns
        if missing_columns:
            has_rows = connection.execute(
                sa.select(sa.literal(1)).select_from(sa.table('subscription_reservation')).limit(1)
            ).first()
            if has_rows is not None:
                raise RuntimeError(
                    'Cannot safely repair a populated partial subscription_reservation table; '
                    f'missing columns: {sorted(missing_columns)}'
                )
            op.drop_table('subscription_reservation')
            _create_reservation_table()
    else:
        _create_reservation_table()

    for index_name, column_names, unique in RESERVATION_INDEXES:
        _ensure_index(
            connection,
            'subscription_reservation',
            index_name,
            column_names,
            unique=unique,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if 'subscription_reservation' in tables:
        op.drop_table('subscription_reservation')

    if 'subscription_usage' in tables:
        usage_indexes = {index['name'] for index in inspector.get_indexes('subscription_usage')}
        if 'uq_subscription_usage_reservation_id' in usage_indexes:
            op.drop_index('uq_subscription_usage_reservation_id', table_name='subscription_usage')
        usage_columns = {column['name'] for column in inspector.get_columns('subscription_usage')}
        if 'reservation_id' in usage_columns:
            op.drop_column('subscription_usage', 'reservation_id')
        if 'unpaid_cost_micros' in usage_columns:
            op.drop_column('subscription_usage', 'unpaid_cost_micros')

    if 'user_subscription' in tables:
        subscription_columns = {column['name'] for column in inspector.get_columns('user_subscription')}
        if 'balance_version' in subscription_columns:
            op.drop_column('user_subscription', 'balance_version')
