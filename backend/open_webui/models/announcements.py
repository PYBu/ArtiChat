from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from open_webui.internal.db import Base, get_async_db_context
from open_webui.models.subscriptions import new_id, now_ts
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Index, Text, select
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def get_announcement_db_context(db: AsyncSession | None = None) -> AsyncIterator[AsyncSession]:
    if db is not None:
        yield db
    else:
        async with get_async_db_context() as session:
            yield session


class Announcement(Base):
    __tablename__ = 'announcement'

    id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    display_mode = Column(Text, nullable=False)
    button_label = Column(Text, nullable=False, default='知道了')
    icon = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    starts_at = Column(BigInteger, nullable=True)
    ends_at = Column(BigInteger, nullable=True)
    sort_order = Column(BigInteger, nullable=False, default=0)
    created_by = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class AnnouncementView(Base):
    __tablename__ = 'announcement_view'

    id = Column(Text, primary_key=True)
    announcement_id = Column(Text, nullable=False, index=True)
    user_id = Column(Text, nullable=False, index=True)
    viewed_at = Column(BigInteger, nullable=False)

    __table_args__ = (Index('announcement_view_announcement_user_idx', 'announcement_id', 'user_id', unique=True),)


class AnnouncementModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    display_mode: str
    button_label: str
    icon: str | None = None
    is_active: bool
    starts_at: int | None = None
    ends_at: int | None = None
    sort_order: int
    created_by: str
    created_at: int
    updated_at: int


class AnnouncementViewModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    announcement_id: str
    user_id: str
    viewed_at: int


class AnnouncementsTable:
    def _validate_display_mode(self, display_mode: str) -> None:
        if display_mode not in {'once', 'every_login', 'new_user'}:
            raise ValueError('ANNOUNCEMENT_DISPLAY_MODE_INVALID')

    async def create(
        self,
        *,
        title: str,
        body: str,
        display_mode: str,
        button_label: str,
        icon: str | None,
        is_active: bool,
        starts_at: int | None,
        ends_at: int | None,
        sort_order: int,
        created_by: str,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> AnnouncementModel:
        self._validate_display_mode(display_mode)
        timestamp = now or now_ts()
        async with get_announcement_db_context(db) as session:
            row = Announcement(
                id=new_id('ann'),
                title=title,
                body=body,
                display_mode=display_mode,
                button_label=button_label or '知道了',
                icon=icon,
                is_active=is_active,
                starts_at=starts_at,
                ends_at=ends_at,
                sort_order=sort_order,
                created_by=created_by,
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return AnnouncementModel.model_validate(row)

    async def list_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        include_inactive: bool = False,
        db: AsyncSession | None = None,
    ) -> list[AnnouncementModel]:
        async with get_announcement_db_context(db) as session:
            stmt = select(Announcement)
            if not include_inactive:
                stmt = stmt.filter(Announcement.is_active == True)  # noqa: E712
            result = await session.execute(
                stmt.order_by(Announcement.sort_order.asc(), Announcement.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return [AnnouncementModel.model_validate(row) for row in result.scalars().all()]

    async def update(
        self,
        announcement_id: str,
        *,
        title: str | None = None,
        body: str | None = None,
        display_mode: str | None = None,
        button_label: str | None = None,
        icon: str | None = None,
        is_active: bool | None = None,
        starts_at: int | None = None,
        ends_at: int | None = None,
        sort_order: int | None = None,
        db: AsyncSession | None = None,
    ) -> AnnouncementModel:
        if display_mode is not None:
            self._validate_display_mode(display_mode)
        async with get_announcement_db_context(db) as session:
            row = await session.get(Announcement, announcement_id)
            if row is None:
                raise ValueError('ANNOUNCEMENT_NOT_FOUND')
            if title is not None:
                row.title = title
            if body is not None:
                row.body = body
            if display_mode is not None:
                row.display_mode = display_mode
            if button_label is not None:
                row.button_label = button_label
            if icon is not None:
                row.icon = icon
            if is_active is not None:
                row.is_active = is_active
            if starts_at is not None:
                row.starts_at = starts_at
            if ends_at is not None:
                row.ends_at = ends_at
            if sort_order is not None:
                row.sort_order = sort_order
            row.updated_at = now_ts()
            await session.commit()
            await session.refresh(row)
            return AnnouncementModel.model_validate(row)

    async def delete(self, announcement_id: str, db: AsyncSession | None = None) -> AnnouncementModel:
        async with get_announcement_db_context(db) as session:
            row = await session.get(Announcement, announcement_id)
            if row is None:
                raise ValueError('ANNOUNCEMENT_NOT_FOUND')
            row.is_active = False
            row.updated_at = now_ts()
            await session.commit()
            await session.refresh(row)
            return AnnouncementModel.model_validate(row)

    async def get_active_for_user(
        self,
        *,
        user_id: str,
        user_created_at: int,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> list[AnnouncementModel]:
        current_time = now or now_ts()
        async with get_announcement_db_context(db) as session:
            result = await session.execute(
                select(Announcement)
                .filter(Announcement.is_active == True)  # noqa: E712
                .order_by(Announcement.sort_order.asc(), Announcement.created_at.asc())
            )
            announcements = result.scalars().all()
            views_result = await session.execute(
                select(AnnouncementView.announcement_id).filter(AnnouncementView.user_id == user_id)
            )
            viewed_ids = set(views_result.scalars().all())

            active = []
            for announcement in announcements:
                if announcement.starts_at is not None and announcement.starts_at > current_time:
                    continue
                if announcement.ends_at is not None and announcement.ends_at <= current_time:
                    continue
                if announcement.display_mode == 'new_user' and user_created_at < announcement.created_at:
                    continue
                if announcement.display_mode in {'once', 'new_user'} and announcement.id in viewed_ids:
                    continue
                active.append(AnnouncementModel.model_validate(announcement))
            return active

    async def mark_viewed(
        self,
        announcement_id: str,
        *,
        user_id: str,
        now: int | None = None,
        db: AsyncSession | None = None,
    ) -> AnnouncementViewModel:
        timestamp = now or now_ts()
        async with get_announcement_db_context(db) as session:
            row = await session.get(Announcement, announcement_id)
            if row is None:
                raise ValueError('ANNOUNCEMENT_NOT_FOUND')
            existing = await session.execute(
                select(AnnouncementView).filter(
                    AnnouncementView.announcement_id == announcement_id,
                    AnnouncementView.user_id == user_id,
                )
            )
            view = existing.scalar_one_or_none()
            if view is None:
                view = AnnouncementView(
                    id=new_id('annview'),
                    announcement_id=announcement_id,
                    user_id=user_id,
                    viewed_at=timestamp,
                )
                session.add(view)
            else:
                view.viewed_at = timestamp
            await session.commit()
            await session.refresh(view)
            return AnnouncementViewModel.model_validate(view)


Announcements = AnnouncementsTable()
