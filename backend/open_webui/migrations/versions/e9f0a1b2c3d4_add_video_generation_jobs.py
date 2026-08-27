"""Add durable video generation jobs.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e9f0a1b2c3d4'
down_revision: str | None = 'd8e9f0a1b2c3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'video_generation_job' in inspector.get_table_names():
        return

    op.create_table(
        'video_generation_job',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('chat_id', sa.Text(), nullable=True),
        sa.Column('message_id', sa.Text(), nullable=True),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('provider_task_id', sa.Text(), nullable=True),
        sa.Column('model', sa.Text(), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('input_mode', sa.Text(), nullable=False, server_default='text'),
        sa.Column('request_payload', sa.Text(), nullable=False),
        sa.Column('provider_response', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='queued'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cancel_requested', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('output_file_id', sa.Text(), nullable=True),
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_poll_at', sa.BigInteger(), nullable=False),
        sa.Column('lease_until', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('completed_at', sa.BigInteger(), nullable=True),
    )
    op.create_index('ix_video_generation_job_user_id', 'video_generation_job', ['user_id'])
    op.create_index('ix_video_generation_job_next_poll_at', 'video_generation_job', ['next_poll_at'])
    op.create_index('ix_video_job_status_poll', 'video_generation_job', ['status', 'next_poll_at'])
    op.create_index('ix_video_job_chat_message', 'video_generation_job', ['chat_id', 'message_id'])
    op.create_index('ix_video_job_provider_task', 'video_generation_job', ['provider', 'provider_task_id'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'video_generation_job' not in inspector.get_table_names():
        return
    for index_name in (
        'ix_video_job_provider_task',
        'ix_video_job_chat_message',
        'ix_video_job_status_poll',
        'ix_video_generation_job_next_poll_at',
        'ix_video_generation_job_user_id',
    ):
        op.drop_index(index_name, table_name='video_generation_job')
    op.drop_table('video_generation_job')
