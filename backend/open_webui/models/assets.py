"""Asset-center metadata and revocable public share records."""

from __future__ import annotations

import time
import uuid
import mimetypes
from pathlib import Path

from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, Index, String, Text, select, update
from sqlalchemy.ext.asyncio import AsyncSession


ASSET_CATEGORIES = frozenset({'image', 'video', 'other'})
ASSET_SOURCES = frozenset({'uploaded', 'generated'})


def normalize_asset_category(content_type: str | None, filename: str | None = None) -> str:
    value = (content_type or '').split(';', 1)[0].strip().lower()
    if value.startswith('image/'):
        return 'image'
    if value.startswith('video/'):
        return 'video'
    guessed = mimetypes.guess_type(Path(filename or '').name)[0] or ''
    if guessed.startswith('image/'):
        return 'image'
    if guessed.startswith('video/'):
        return 'video'
    return 'other'


def normalize_asset_source(source: str | None) -> str:
    return source if source in ASSET_SOURCES else 'uploaded'


class AssetShare(Base):
    __tablename__ = 'asset_share'
    __table_args__ = (
        Index('ix_asset_share_file_id', 'file_id'),
        Index('ix_asset_share_owner_id', 'owner_id'),
        Index('ix_asset_share_token_hash', 'token_hash', unique=True),
    )

    id = Column(String, primary_key=True, unique=True)
    file_id = Column(String, nullable=False)
    owner_id = Column(String, nullable=False)
    token_hash = Column(Text, nullable=False)
    expires_at = Column(BigInteger, nullable=True)
    revoked_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    last_access_at = Column(BigInteger, nullable=True)


class AssetShareModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_id: str
    owner_id: str
    expires_at: int | None = None
    revoked_at: int | None = None
    created_at: int
    last_access_at: int | None = None


class AssetSharesTable:
    async def create(
        self,
        *,
        file_id: str,
        owner_id: str,
        token_hash: str,
        expires_at: int | None = None,
        db: AsyncSession | None = None,
    ) -> AssetShareModel:
        async with get_async_db_context(db) as session:
            now = int(time.time())
            row = AssetShare(
                id=str(uuid.uuid4()),
                file_id=file_id,
                owner_id=owner_id,
                token_hash=token_hash,
                expires_at=expires_at,
                created_at=now,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return AssetShareModel.model_validate(row)

    async def get_active_by_token_hash(
        self, token_hash: str, *, now: int | None = None, db: AsyncSession | None = None
    ) -> AssetShareModel | None:
        async with get_async_db_context(db) as session:
            current = int(now or time.time())
            result = await session.execute(
                select(AssetShare).where(
                    AssetShare.token_hash == token_hash,
                    AssetShare.revoked_at.is_(None),
                )
            )
            row = result.scalars().first()
            if row is None or (row.expires_at is not None and row.expires_at <= current):
                return None
            return AssetShareModel.model_validate(row)

    async def get_active_for_owner_files(
        self,
        owner_id: str,
        file_ids: list[str],
        db: AsyncSession | None = None,
    ) -> dict[str, list[AssetShareModel]]:
        if not file_ids:
            return {}
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(AssetShare)
                .where(
                    AssetShare.owner_id == owner_id,
                    AssetShare.file_id.in_(file_ids),
                    AssetShare.revoked_at.is_(None),
                )
                .order_by(AssetShare.created_at.desc())
            )
            current = int(time.time())
            grouped: dict[str, list[AssetShareModel]] = {}
            for row in result.scalars().all():
                if row.expires_at is not None and row.expires_at <= current:
                    continue
                grouped.setdefault(row.file_id, []).append(AssetShareModel.model_validate(row))
            return grouped

    async def revoke_for_owner(
        self, share_id: str, owner_id: str, db: AsyncSession | None = None
    ) -> bool:
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(AssetShare).where(
                    AssetShare.id == share_id,
                    AssetShare.owner_id == owner_id,
                    AssetShare.revoked_at.is_(None),
                )
            )
            row = result.scalars().first()
            if row is None:
                return False
            row.revoked_at = int(time.time())
            await session.commit()
            return True

    async def revoke_for_file(self, file_id: str, db: AsyncSession | None = None) -> int:
        async with get_async_db_context(db) as session:
            result = await session.execute(
                update(AssetShare)
                .where(AssetShare.file_id == file_id, AssetShare.revoked_at.is_(None))
                .values(revoked_at=int(time.time()))
            )
            await session.commit()
            return int(result.rowcount or 0)

    async def touch(self, share_id: str, db: AsyncSession | None = None) -> None:
        async with get_async_db_context(db) as session:
            await session.execute(
                update(AssetShare).where(AssetShare.id == share_id).values(last_access_at=int(time.time()))
            )
            await session.commit()


AssetShares = AssetSharesTable()
