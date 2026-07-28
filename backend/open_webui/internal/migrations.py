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

EXPECTED_ALEMBIC_HEADS = frozenset({'d3e4f5a6b7c8'})

# These are the durable structures that protect an existing ArtiChat service's
# users, conversations, subscriptions, balances, usage, gift cards, and account
# security data. Alembic head validation alone cannot detect a manually stamped
# or partially restored database, so readiness verifies the structures too.
REQUIRED_SCHEMA: dict[str, frozenset[str]] = {
    'user': frozenset({'id', 'email', 'email_verified_at', 'auth_epoch', 'variables'}),
    'chat': frozenset({'id', 'user_id', 'chat', 'current_message_id', 'variables'}),
    'chat_message': frozenset({'id', 'chat_id', 'parent_id', 'meta'}),
    'automation': frozenset({'id', 'user_id', 'folder_id'}),
    'subscription_plan': frozenset({'id', 'plan_chatpoint_allowance_micros'}),
    'user_subscription': frozenset(
        {
            'id',
            'user_id',
            'plan_balance_micros',
            'check_balance_micros',
            'next_reset_at',
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
            'input_tokens',
            'output_tokens',
            'cost_micros',
            'raw_usage',
        }
    ),
    'redemption_code': frozenset({'id', 'code_hash', 'used_count'}),
    'redemption_record': frozenset({'id', 'redemption_code_id', 'user_id'}),
    'gift_card_grant': frozenset({'id', 'redemption_code_id', 'user_id', 'status'}),
    'announcement': frozenset({'id', 'title', 'body', 'display_mode'}),
    'announcement_view': frozenset({'id', 'announcement_id', 'user_id'}),
    'email_challenge': frozenset({'id', 'email', 'purpose', 'code_hash'}),
    'password_reset_token': frozenset({'id', 'user_id', 'token_hash'}),
    'email_template': frozenset({'key', 'subject', 'markdown_body', 'html_body'}),
    'email_delivery': frozenset({'id', 'recipient', 'status'}),
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


def assert_database_schema_ready(
    connectable: Engine | Connection,
    *,
    expected_heads: frozenset[str] = EXPECTED_ALEMBIC_HEADS,
    required_schema: Mapping[str, frozenset[str]] = REQUIRED_SCHEMA,
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

        missing: list[str] = []
        for table_name, required_columns in required_schema.items():
            if table_name not in table_names:
                missing.append(f'table {table_name}')
                continue

            actual_columns = {column['name'] for column in inspector.get_columns(table_name)}
            missing.extend(
                f'column {table_name}.{column_name}' for column_name in sorted(required_columns - actual_columns)
            )

        if missing:
            raise DatabaseSchemaNotReadyError(
                'Database is stamped at the expected migration head but required schema is missing: '
                + ', '.join(missing)
            )
