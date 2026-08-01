from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault('WEBUI_SECRET_KEY', 'test-subscriptions-secret-key')

BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from open_webui.internal.db import Base  # noqa: E402


@pytest_asyncio.fixture()
async def db_session(tmp_path):
    import open_webui.models.announcements  # noqa: F401
    import open_webui.models.channels  # noqa: F401
    import open_webui.models.email_security  # noqa: F401
    import open_webui.models.messages  # noqa: F401
    import open_webui.models.models  # noqa: F401
    import open_webui.models.subscriptions  # noqa: F401
    from open_webui.models.access_grants import AccessGrant

    db_path = tmp_path / 'subscriptions-test.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_path}', connect_args={'check_same_thread': False})

    @event.listens_for(engine.sync_engine, 'connect')
    def configure_sqlite(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA busy_timeout=10000')
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(AccessGrant.__table__.create, checkfirst=True)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()
