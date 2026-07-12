from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


os.environ.setdefault('WEBUI_SECRET_KEY', 'test-subscriptions-secret-key')

BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from open_webui.internal.db import Base  # noqa: E402


@pytest_asyncio.fixture()
async def db_session(tmp_path):
    import open_webui.models.subscriptions  # noqa: F401
    import open_webui.models.announcements  # noqa: F401
    import open_webui.models.models  # noqa: F401

    db_path = tmp_path / 'subscriptions-test.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_path}', connect_args={'check_same_thread': False})

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()
