"""Persistence helpers for login access rules and short-lived login history."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from open_webui.internal.db import Base, get_async_db
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Index, Text, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


LOGIN_HISTORY_RETENTION_SECONDS = 7 * 24 * 60 * 60


@asynccontextmanager
async def access_restrictions_db_context(db: AsyncSession | None = None):
    if db is not None:
        yield db
    else:
        async with get_async_db() as session:
            yield session


def new_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4()}'


class AccessRestrictionIPRule(Base):
    __tablename__ = 'access_restriction_ip_rule'

    id = Column(Text, primary_key=True)
    network = Column(Text, nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=True)
    note = Column(Text, nullable=True)
    created_by = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class AccessRestrictionRegionRule(Base):
    __tablename__ = 'access_restriction_region_rule'

    id = Column(Text, primary_key=True)
    country_code = Column(Text, nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=True)
    note = Column(Text, nullable=True)
    created_by = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class LoginEvent(Base):
    __tablename__ = 'login_event'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=True, index=True)
    user_email = Column(Text, nullable=True, index=True)
    user_name = Column(Text, nullable=True)
    ip_address = Column(Text, nullable=True, index=True)
    country_code = Column(Text, nullable=True, index=True)
    auth_method = Column(Text, nullable=False)
    result = Column(Text, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    rule_id = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False, index=True)

    __table_args__ = (
        Index('login_event_search_idx', 'user_email', 'user_name'),
        Index('login_event_created_result_idx', 'created_at', 'result'),
    )


class AccessRestrictionIPRuleModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    network: str
    enabled: bool
    note: str | None = None
    created_by: str
    created_at: int
    updated_at: int


class AccessRestrictionRegionRuleModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    country_code: str
    enabled: bool
    note: str | None = None
    created_by: str
    created_at: int
    updated_at: int


class LoginEventModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None = None
    user_email: str | None = None
    user_name: str | None = None
    ip_address: str | None = None
    country_code: str | None = None
    auth_method: str
    result: str
    reason: str | None = None
    rule_id: str | None = None
    user_agent: str | None = None
    created_at: int


class AccessRestrictionIPRules:
    async def list(self, *, enabled_only: bool = False, db: AsyncSession | None = None) -> list[AccessRestrictionIPRuleModel]:
        async with access_restrictions_db_context(db) as session:
            statement = select(AccessRestrictionIPRule).order_by(
                AccessRestrictionIPRule.created_at.desc(),
                AccessRestrictionIPRule.id.desc(),
            )
            if enabled_only:
                statement = statement.where(AccessRestrictionIPRule.enabled.is_(True))
            rows = (await session.execute(statement)).scalars().all()
            return [AccessRestrictionIPRuleModel.model_validate(row) for row in rows]

    async def get(self, rule_id: str, *, db: AsyncSession | None = None) -> AccessRestrictionIPRule | None:
        async with access_restrictions_db_context(db) as session:
            return await session.get(AccessRestrictionIPRule, rule_id)

    async def create(
        self,
        *,
        network: str,
        note: str | None,
        enabled: bool,
        created_by: str,
        db: AsyncSession | None = None,
    ) -> AccessRestrictionIPRuleModel:
        now = int(time.time())
        row = AccessRestrictionIPRule(
            id=new_id('iprule'),
            network=network,
            note=note,
            enabled=enabled,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        async with access_restrictions_db_context(db) as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return AccessRestrictionIPRuleModel.model_validate(row)

    async def update(
        self,
        rule_id: str,
        *,
        enabled: bool | None = None,
        note: str | None = None,
        db: AsyncSession | None = None,
    ) -> AccessRestrictionIPRuleModel | None:
        async with access_restrictions_db_context(db) as session:
            row = await session.get(AccessRestrictionIPRule, rule_id)
            if row is None:
                return None
            if enabled is not None:
                row.enabled = enabled
            if note is not None:
                row.note = note
            row.updated_at = int(time.time())
            await session.commit()
            await session.refresh(row)
            return AccessRestrictionIPRuleModel.model_validate(row)

    async def delete(self, rule_id: str, *, db: AsyncSession | None = None) -> bool:
        async with access_restrictions_db_context(db) as session:
            row = await session.get(AccessRestrictionIPRule, rule_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True


class AccessRestrictionRegionRules:
    async def list(self, *, enabled_only: bool = False, db: AsyncSession | None = None) -> list[AccessRestrictionRegionRuleModel]:
        async with access_restrictions_db_context(db) as session:
            statement = select(AccessRestrictionRegionRule).order_by(
                AccessRestrictionRegionRule.country_code.asc(),
            )
            if enabled_only:
                statement = statement.where(AccessRestrictionRegionRule.enabled.is_(True))
            rows = (await session.execute(statement)).scalars().all()
            return [AccessRestrictionRegionRuleModel.model_validate(row) for row in rows]

    async def get(self, rule_id: str, *, db: AsyncSession | None = None) -> AccessRestrictionRegionRule | None:
        async with access_restrictions_db_context(db) as session:
            return await session.get(AccessRestrictionRegionRule, rule_id)

    async def create(
        self,
        *,
        country_code: str,
        note: str | None,
        enabled: bool,
        created_by: str,
        db: AsyncSession | None = None,
    ) -> AccessRestrictionRegionRuleModel:
        now = int(time.time())
        row = AccessRestrictionRegionRule(
            id=new_id('regionrule'),
            country_code=country_code,
            note=note,
            enabled=enabled,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        async with access_restrictions_db_context(db) as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return AccessRestrictionRegionRuleModel.model_validate(row)

    async def update(
        self,
        rule_id: str,
        *,
        enabled: bool | None = None,
        note: str | None = None,
        db: AsyncSession | None = None,
    ) -> AccessRestrictionRegionRuleModel | None:
        async with access_restrictions_db_context(db) as session:
            row = await session.get(AccessRestrictionRegionRule, rule_id)
            if row is None:
                return None
            if enabled is not None:
                row.enabled = enabled
            if note is not None:
                row.note = note
            row.updated_at = int(time.time())
            await session.commit()
            await session.refresh(row)
            return AccessRestrictionRegionRuleModel.model_validate(row)

    async def delete(self, rule_id: str, *, db: AsyncSession | None = None) -> bool:
        async with access_restrictions_db_context(db) as session:
            row = await session.get(AccessRestrictionRegionRule, rule_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True


class LoginEvents:
    async def insert(
        self,
        *,
        user_id: str | None,
        user_email: str | None,
        user_name: str | None,
        ip_address: str | None,
        country_code: str | None,
        auth_method: str,
        result: str,
        reason: str | None,
        rule_id: str | None,
        user_agent: str | None,
        created_at: int | None = None,
        db: AsyncSession | None = None,
    ) -> LoginEventModel:
        timestamp = created_at if created_at is not None else int(time.time())
        row = LoginEvent(
            id=new_id('login'),
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            ip_address=ip_address,
            country_code=country_code,
            auth_method=auth_method,
            result=result,
            reason=reason,
            rule_id=rule_id,
            user_agent=user_agent,
            created_at=timestamp,
        )
        async with access_restrictions_db_context(db) as session:
            session.add(row)
            await session.execute(
                delete(LoginEvent).where(
                    LoginEvent.created_at < timestamp - LOGIN_HISTORY_RETENTION_SECONDS,
                )
            )
            await session.commit()
            await session.refresh(row)
            return LoginEventModel.model_validate(row)

    async def purge(self, *, now: int | None = None, db: AsyncSession | None = None) -> int:
        timestamp = now if now is not None else int(time.time())
        async with access_restrictions_db_context(db) as session:
            result = await session.execute(
                delete(LoginEvent).where(
                    LoginEvent.created_at < timestamp - LOGIN_HISTORY_RETENTION_SECONDS,
                )
            )
            await session.commit()
            return int(result.rowcount or 0)

    async def list_recent(
        self,
        *,
        query: str | None = None,
        result: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        timestamp = int(time.time())
        filters = [LoginEvent.created_at >= timestamp - LOGIN_HISTORY_RETENTION_SECONDS]
        if query:
            pattern = f'%{query.strip()}%'
            filters.append(
                or_(
                    LoginEvent.user_email.ilike(pattern),
                    LoginEvent.user_name.ilike(pattern),
                )
            )
        if result:
            filters.append(LoginEvent.result == result)
        if start_at is not None:
            filters.append(LoginEvent.created_at >= start_at)
        if end_at is not None:
            filters.append(LoginEvent.created_at <= end_at)

        async with access_restrictions_db_context(db) as session:
            statement = (
                select(LoginEvent)
                .where(*filters)
                .order_by(LoginEvent.created_at.desc(), LoginEvent.id.desc())
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(statement)).scalars().all()
            total = await session.scalar(select(func.count(LoginEvent.id)).where(*filters))
            return {
                'items': [LoginEventModel.model_validate(row) for row in rows],
                'total_item_count': int(total or 0),
            }


AccessRestrictionIPRulesTable = AccessRestrictionIPRules()
AccessRestrictionRegionRulesTable = AccessRestrictionRegionRules()
LoginEventsTable = LoginEvents()
