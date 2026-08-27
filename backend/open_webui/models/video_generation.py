"""Durable video generation jobs and provider-neutral response models."""

from __future__ import annotations

import time
import uuid
from typing import Any

from open_webui.internal.db import Base, JSONField, get_async_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession


class VideoGenerationJob(Base):
    __tablename__ = 'video_generation_job'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    chat_id = Column(Text, nullable=True)
    message_id = Column(Text, nullable=True)
    provider = Column(Text, nullable=False)
    provider_task_id = Column(Text, nullable=True)
    model = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    input_mode = Column(Text, nullable=False, default='text')
    request_payload = Column(JSONField, nullable=False)
    provider_response = Column(JSONField, nullable=True)
    billing_reservation_id = Column(Text, nullable=True, index=True)
    billing_unit_count = Column(Integer, nullable=True)
    billing_unit_price_micros = Column(BigInteger, nullable=True)
    billing_status = Column(Text, nullable=False, default='none', server_default='none')
    billing_usage_id = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default='queued')
    progress = Column(Integer, nullable=False, default=0)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    output_file_id = Column(Text, nullable=True)
    error_code = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_poll_at = Column(BigInteger, nullable=False, index=True)
    lease_until = Column(BigInteger, nullable=True, index=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    completed_at = Column(BigInteger, nullable=True)

    __table_args__ = (
        Index('ix_video_job_status_poll', 'status', 'next_poll_at'),
        Index('ix_video_job_chat_message', 'chat_id', 'message_id'),
        Index('ix_video_job_provider_task', 'provider', 'provider_task_id'),
    )


class VideoGenerationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    chat_id: str | None = None
    message_id: str | None = None
    provider: str
    provider_task_id: str | None = None
    model: str | None = None
    prompt: str
    input_mode: str
    billing_reservation_id: str | None = None
    billing_unit_count: int | None = None
    billing_unit_price_micros: int | None = None
    billing_status: str = 'none'
    billing_usage_id: str | None = None
    status: str
    progress: int
    cancel_requested: bool = False
    output_file_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    attempts: int
    created_at: int
    updated_at: int
    completed_at: int | None = None


class VideoGenerationJobTable:
    async def create(
        self,
        *,
        user_id: str,
        chat_id: str | None,
        message_id: str | None,
        provider: str,
        model: str | None,
        prompt: str,
        input_mode: str,
        request_payload: dict[str, Any],
        billing_reservation_id: str | None = None,
        billing_unit_count: int | None = None,
        billing_unit_price_micros: int | None = None,
        billing_status: str = 'none',
        db: AsyncSession | None = None,
    ) -> VideoGenerationJobResponse:
        now = int(time.time())
        row = VideoGenerationJob(
            id=uuid.uuid4().hex,
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            provider=provider,
            model=model,
            prompt=prompt,
            input_mode=input_mode,
            request_payload=request_payload,
            billing_reservation_id=billing_reservation_id,
            billing_unit_count=billing_unit_count,
            billing_unit_price_micros=billing_unit_price_micros,
            billing_status=billing_status,
            status='queued',
            progress=0,
            next_poll_at=now,
            created_at=now,
            updated_at=now,
        )
        async with get_async_db_context(db) as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return VideoGenerationJobResponse.model_validate(row)

    async def get_for_user(
        self,
        job_id: str,
        user_id: str,
        *,
        is_admin: bool = False,
        db: AsyncSession | None = None,
    ) -> VideoGenerationJobResponse | None:
        async with get_async_db_context(db) as session:
            row = await session.get(VideoGenerationJob, job_id)
            if not row or (not is_admin and row.user_id != user_id):
                return None
            return VideoGenerationJobResponse.model_validate(row)

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 50,
        db: AsyncSession | None = None,
    ) -> list[VideoGenerationJobResponse]:
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(VideoGenerationJob)
                .where(VideoGenerationJob.user_id == user_id)
                .order_by(VideoGenerationJob.created_at.desc())
                .limit(max(1, min(limit, 100)))
            )
            return [VideoGenerationJobResponse.model_validate(row) for row in result.scalars().all()]


VideoGenerationJobs = VideoGenerationJobTable()
