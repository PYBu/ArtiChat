"""Fail-closed Alembic migration and database-readiness checks."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.reflection import Inspector

EXPECTED_ALEMBIC_HEADS = frozenset({'f0a1b2c3d4e5'})

# Every application-owned durable table that must survive a 0.1.7 -> 0.2.1
# upgrade. Alembic head validation alone cannot detect a manually stamped or
# partially restored database, so readiness first verifies the complete table
# inventory and then checks release-critical columns below.
REQUIRED_DURABLE_TABLES = frozenset(
    {
        'access_grant',
        'alembic_version',
        'announcement',
        'announcement_view',
        'api_key',
        'auth',
        'automation',
        'automation_run',
        'calendar',
        'calendar_event',
        'calendar_event_attendee',
        'channel',
        'channel_file',
        'channel_member',
        'channel_webhook',
        'chat',
        'chat_file',
        'chat_message',
        'chatidtag',
        'config',
        'document',
        'email_challenge',
        'email_delivery',
        'email_template',
        'feedback',
        'file',
        'folder',
        'function',
        'gift_card_grant',
        'group',
        'group_member',
        'knowledge',
        'knowledge_directory',
        'knowledge_file',
        'memory',
        'message',
        'message_reaction',
        'model',
        'note',
        'oauth_session',
        'password_reset_token',
        'pinned_note',
        'prompt',
        'prompt_history',
        'redemption_code',
        'redemption_record',
        'shared_chat',
        'skill',
        'subscription_ledger',
        'subscription_plan',
        'subscription_reservation',
        'subscription_usage',
        'tag',
        'tool',
        'user',
        'user_subscription',
        'video_generation_job',
    }
)

# Column checks cover the identities, relationships, balances, and audit fields
# whose absence could otherwise look like a successful but destructive upgrade.
REQUIRED_SCHEMA: dict[str, frozenset[str]] = {
    'auth': frozenset({'id', 'email', 'password', 'active'}),
    'user': frozenset({'id', 'email', 'email_verified_at', 'auth_epoch', 'variables'}),
    'chat': frozenset({'id', 'user_id', 'chat', 'current_message_id', 'variables'}),
    'chat_message': frozenset({'id', 'chat_id', 'parent_id', 'meta'}),
    'file': frozenset({'id', 'user_id', 'filename', 'path', 'meta'}),
    'knowledge': frozenset({'id', 'user_id', 'name', 'data'}),
    'knowledge_file': frozenset({'id', 'knowledge_id', 'file_id', 'user_id'}),
    'model': frozenset({'id', 'user_id', 'base_model_id', 'params', 'meta'}),
    'prompt': frozenset({'id', 'user_id', 'command', 'content'}),
    'tool': frozenset({'id', 'user_id', 'content', 'specs'}),
    'function': frozenset({'id', 'user_id', 'content', 'valves'}),
    'memory': frozenset({'id', 'user_id', 'content', 'meta'}),
    'folder': frozenset({'id', 'user_id', 'parent_id', 'items'}),
    'group': frozenset({'id', 'user_id', 'permissions'}),
    'group_member': frozenset({'id', 'group_id', 'user_id'}),
    'automation': frozenset({'id', 'user_id', 'folder_id'}),
    'subscription_plan': frozenset({'id', 'plan_chatpoint_allowance_micros'}),
    'user_subscription': frozenset(
        {
            'id',
            'user_id',
            'plan_balance_micros',
            'check_balance_micros',
            'balance_version',
            'pending_settlement_count',
            'next_reset_at',
        }
    ),
    'video_generation_job': frozenset(
        {
            'id',
            'user_id',
            'provider',
            'provider_task_id',
            'billing_reservation_id',
            'billing_unit_count',
            'billing_unit_price_micros',
            'billing_status',
            'prompt',
            'request_payload',
            'status',
            'progress',
            'output_file_id',
            'next_poll_at',
            'lease_until',
        }
    ),
    'subscription_ledger': frozenset(
        {
            'id',
            'user_id',
            'plan_balance_after_micros',
            'check_balance_after_micros',
        }
    ),
    'subscription_usage': frozenset(
        {
            'id',
            'user_id',
            'chat_id',
            'message_id',
            'request_id',
            'idempotency_key',
            'reservation_id',
            'usage_type',
            'media_unit',
            'media_units',
            'media_unit_price_micros',
            'input_tokens',
            'output_tokens',
            'cost_micros',
            'unpaid_cost_micros',
            'raw_usage',
        }
    ),
    'subscription_reservation': frozenset(
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
    ),
    'redemption_code': frozenset({'id', 'code_hash', 'used_count', 'benefit_type', 'purged_at'}),
    'redemption_record': frozenset({'id', 'redemption_code_id', 'user_id'}),
    'gift_card_grant': frozenset({'id', 'redemption_code_id', 'user_id', 'status'}),
    'announcement': frozenset({'id', 'title', 'body', 'display_mode'}),
    'announcement_view': frozenset({'id', 'announcement_id', 'user_id'}),
    'email_challenge': frozenset({'id', 'email', 'purpose', 'code_hash'}),
    'password_reset_token': frozenset({'id', 'user_id', 'token_hash'}),
    'email_template': frozenset({'key', 'subject', 'markdown_body', 'html_body'}),
    'email_delivery': frozenset({'id', 'recipient', 'status'}),
}

REQUIRED_UNIQUE_INDEXES: dict[str, dict[str, tuple[str, ...]]] = {
    'subscription_usage': {
        'uq_subscription_usage_idempotency_key': ('idempotency_key',),
        'uq_subscription_usage_reservation_id': ('reservation_id',),
    },
    'subscription_reservation': {
        'uq_subscription_reservation_idempotency_key': ('idempotency_key',),
    },
}


class DatabaseSchemaNotReadyError(RuntimeError):
    """Raised when the database cannot safely serve the current application."""


def make_alembic_config(open_webui_dir: Path) -> AlembicConfig:
    """Create the exact Alembic configuration used by application startup."""
    config = AlembicConfig(open_webui_dir / 'alembic.ini')
    config.set_main_option('script_location', str(open_webui_dir / 'migrations'))
    return config


def assert_migration_script_heads(
    config: AlembicConfig,
    expected_heads: frozenset[str] = EXPECTED_ALEMBIC_HEADS,
) -> None:
    """Reject an incomplete or accidentally divergent packaged migration graph."""
    actual_heads = frozenset(ScriptDirectory.from_config(config).get_heads())
    if actual_heads != expected_heads:
        raise DatabaseSchemaNotReadyError(
            'Packaged Alembic heads do not match the expected release head: '
            f'expected {sorted(expected_heads)}, found {sorted(actual_heads)}'
        )


def upgrade_database(open_webui_dir: Path) -> None:
    """Upgrade to the release head and propagate every migration failure."""
    config = make_alembic_config(open_webui_dir)
    assert_migration_script_heads(config)
    command.upgrade(config, 'head')


def _find_missing_unique_indexes(
    inspector: Inspector,
    table_names: set[str],
    required_unique_indexes: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> list[str]:
    missing: list[str] = []
    for table_name, required_indexes in required_unique_indexes.items():
        if table_name not in table_names:
            continue

        actual_indexes = {index['name']: index for index in inspector.get_indexes(table_name)}
        for index_name, required_columns in required_indexes.items():
            actual_index = actual_indexes.get(index_name)
            actual_columns = tuple(actual_index.get('column_names') or ()) if actual_index else ()
            if actual_index is None or not bool(actual_index.get('unique')) or actual_columns != required_columns:
                missing.append(
                    f'unique index {table_name}.{index_name}({", ".join(required_columns)})'
                )
    return missing


def assert_database_schema_ready(
    connectable: Engine | Connection,
    *,
    expected_heads: frozenset[str] = EXPECTED_ALEMBIC_HEADS,
    required_tables: frozenset[str] = REQUIRED_DURABLE_TABLES,
    required_schema: Mapping[str, frozenset[str]] = REQUIRED_SCHEMA,
    required_unique_indexes: Mapping[str, Mapping[str, tuple[str, ...]]] = REQUIRED_UNIQUE_INDEXES,
) -> None:
    """Verify the installed Alembic head and critical durable structures."""
    connection_context = nullcontext(connectable) if isinstance(connectable, Connection) else connectable.connect()

    with connection_context as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())
        if 'alembic_version' not in table_names:
            raise DatabaseSchemaNotReadyError('Database is missing the alembic_version table')

        actual_heads = frozenset(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())
        if actual_heads != expected_heads:
            raise DatabaseSchemaNotReadyError(
                'Database Alembic heads do not match the expected release head: '
                f'expected {sorted(expected_heads)}, found {sorted(actual_heads)}'
            )

        missing: list[str] = [f'table {table_name}' for table_name in sorted(required_tables - table_names)]
        for table_name, required_columns in required_schema.items():
            if table_name not in table_names:
                if table_name not in required_tables:
                    missing.append(f'table {table_name}')
                continue

            actual_columns = {column['name'] for column in inspector.get_columns(table_name)}
            missing.extend(
                f'column {table_name}.{column_name}' for column_name in sorted(required_columns - actual_columns)
            )

        missing.extend(
            _find_missing_unique_indexes(inspector, table_names, required_unique_indexes)
        )

        if missing:
            raise DatabaseSchemaNotReadyError(
                'Database is stamped at the expected migration head but required schema is missing: '
                + ', '.join(missing)
            )
