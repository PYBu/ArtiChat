"""Add four-part pricing and request audit fields to subscription usage.

Revision ID: a4b5c6d7e8f9
Revises: f2a3b4c5d6e7
Create Date: 2026-07-12 00:00:00.000000
"""

import json
from decimal import Decimal, InvalidOperation
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USAGE_COLUMNS = (
    sa.Column('request_id', sa.Text(), nullable=True),
    sa.Column('cache_creation_tokens', sa.Integer(), nullable=True),
    sa.Column('cache_read_tokens', sa.Integer(), nullable=True),
    sa.Column('input_chatpoint_per_million', sa.Text(), nullable=True),
    sa.Column('output_chatpoint_per_million', sa.Text(), nullable=True),
    sa.Column('cache_creation_chatpoint_per_million', sa.Text(), nullable=True),
    sa.Column('cache_read_chatpoint_per_million', sa.Text(), nullable=True),
    sa.Column('first_token_latency_ms', sa.Integer(), nullable=True),
    sa.Column('total_duration_ms', sa.Integer(), nullable=True),
    sa.Column('client_ip', sa.Text(), nullable=True),
    sa.Column('raw_usage', sa.JSON(), nullable=True),
)


def _canonical_decimal(value: Decimal) -> str:
    normalized = format(value.normalize(), 'f')
    return '0' if Decimal(normalized) == 0 else normalized


def _backfill_model_prices(connection) -> None:
    inspector = sa.inspect(connection)
    if 'model' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('model')}
    if not {'id', 'meta'} <= columns:
        return

    model = sa.table('model', sa.column('id', sa.Text()), sa.column('meta', sa.JSON()))
    for model_id, raw_meta in connection.execute(sa.select(model.c.id, model.c.meta)).all():
        if isinstance(raw_meta, str):
            try:
                raw_meta = json.loads(raw_meta)
            except json.JSONDecodeError:
                continue
        if not isinstance(raw_meta, dict):
            continue
        policy = raw_meta.get('subscription')
        if not isinstance(policy, dict):
            continue

        try:
            multiplier = Decimal(str(policy.get('usage_multiplier', '1')))
        except InvalidOperation:
            continue
        if not multiplier.is_finite() or multiplier < 0:
            continue

        equivalent_price = _canonical_decimal(multiplier * Decimal('100'))
        updated_policy = dict(policy)
        updated_policy.setdefault('input_chatpoint_per_million', equivalent_price)
        updated_policy.setdefault('output_chatpoint_per_million', equivalent_price)
        updated_policy.setdefault('cache_creation_chatpoint_per_million', '0')
        updated_policy.setdefault('cache_read_chatpoint_per_million', '0')
        if updated_policy == policy:
            continue

        updated_meta = dict(raw_meta)
        updated_meta['subscription'] = updated_policy
        connection.execute(model.update().where(model.c.id == model_id).values(meta=updated_meta))


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if 'subscription_usage' in inspector.get_table_names():
        existing_columns = {column['name'] for column in inspector.get_columns('subscription_usage')}
        for column in USAGE_COLUMNS:
            if column.name not in existing_columns:
                op.add_column('subscription_usage', column)

        inspector = sa.inspect(connection)
        existing_indexes = {index['name'] for index in inspector.get_indexes('subscription_usage')}
        for index_name, columns in (
            ('ix_subscription_usage_request_id', ['request_id']),
            ('ix_subscription_usage_status', ['status']),
            ('ix_subscription_usage_created_at', ['created_at']),
        ):
            if index_name not in existing_indexes:
                op.create_index(index_name, 'subscription_usage', columns)

    _backfill_model_prices(connection)


def downgrade() -> None:
    for index_name in (
        'ix_subscription_usage_created_at',
        'ix_subscription_usage_status',
        'ix_subscription_usage_request_id',
    ):
        try:
            op.drop_index(index_name, table_name='subscription_usage')
        except Exception:
            pass

    for column in reversed(USAGE_COLUMNS):
        try:
            op.drop_column('subscription_usage', column.name)
        except Exception:
            pass
