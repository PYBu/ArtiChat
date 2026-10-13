import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from open_webui.internal.db import Base
from open_webui.models import channels, folders, messages, users


@asynccontextmanager
async def isolated_database(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(
                    sync,
                    tables=[model.__table__ for model in (folders.Folder, channels.ChannelMember, messages.Message, users.User)],
                )
            )

        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            @asynccontextmanager
            async def use_session(db=None):
                yield session

            for module in (channels, folders, messages, users):
                monkeypatch.setattr(module, 'get_async_db_context', use_session)

            statements = []
            event.listen(
                engine.sync_engine,
                'before_cursor_execute',
                lambda _connection, _cursor, statement, _parameters, _context, _many: statements.append(statement),
            )
            yield session, statements
    finally:
        await engine.dispose()


def test_folder_subtrees_use_one_query_and_preserve_ownership(monkeypatch):
    async def run():
        async with isolated_database(monkeypatch) as (db, statements):
            rows = [
                ('root', None, 'reader'),
                ('a', 'root', 'reader'),
                ('b', 'root', 'reader'),
                ('a-leaf', 'a', 'reader'),
                ('b-leaf', 'b', 'reader'),
                ('foreign', 'root', 'other'),
                ('foreign-leaf', 'foreign', 'reader'),
                ('cycle-a', 'cycle-b', 'reader'),
                ('cycle-b', 'cycle-a', 'reader'),
                ('self', 'self', 'reader'),
            ]
            rows.extend((f'deep-{i}', f'deep-{i - 1}' if i else None, 'reader') for i in range(1500))
            db.add_all(folders.Folder(id=id, parent_id=parent, user_id=owner) for id, parent, owner in rows)
            await db.commit()

            for root, expected in (
                ('root', ['root', 'a', 'b', 'b-leaf', 'a-leaf']),
                ('cycle-a', ['cycle-a', 'cycle-b']),
                ('self', ['self']),
                ('missing', []),
                ('foreign', []),
                ('deep-0', [f'deep-{i}' for i in range(1500)]),
            ):
                statements.clear()
                assert await folders.Folders.get_folder_ids_by_id_and_user_id_in_subtree(root, 'reader', db=db) == expected
                assert len(statements) == 1

    asyncio.run(run())


def test_channel_summary_queries_match_read_boundaries_without_duplicate_counts(monkeypatch):
    async def run():
        async with isolated_database(monkeypatch) as (db, statements):
            timestamp = 1_700_000_000_000_000_000
            db.add_all([
                channels.ChannelMember(id='read', channel_id='group', user_id='reader', last_read_at=timestamp),
                channels.ChannelMember(id='duplicate', channel_id='group', user_id='reader', last_read_at=timestamp),
                channels.ChannelMember(id='other', channel_id='group', user_id='other', last_read_at=0),
                channels.ChannelMember(id='null', channel_id='dm', user_id='reader', last_read_at=None),
                channels.ChannelMember(id='empty', channel_id='empty', user_id='reader', last_read_at=0),
            ])
            db.add_all(
                messages.Message(id=id, channel_id=channel, user_id=author, parent_id=parent,
                                 content=id, created_at=created, updated_at=created)
                for id, channel, author, parent, created in (
                    ('before', 'group', 'other', None, timestamp - 1),
                    ('at', 'group', 'other', None, timestamp),
                    ('unread', 'group', 'other', None, timestamp + 1),
                    ('own', 'group', 'reader', None, timestamp + 2),
                    ('reply', 'group', 'other', 'unread', timestamp + 3),
                    ('dm-unread', 'dm', 'other', None, 1),
                    ('zero', 'dm', 'other', None, 0),
                    ('unjoined', 'standard', 'other', None, timestamp),
                    ('hidden', 'hidden', 'other', None, timestamp),
                )
            )
            await db.commit()
            channel_ids = ['group', 'dm', 'empty', 'standard']
            expected_unread = {}
            expected_latest = {}
            for channel_id in channel_ids:
                membership = await channels.Channels.get_member_by_channel_and_user_id(channel_id, 'reader', db=db)
                if membership:
                    expected_unread[channel_id] = await messages.Messages.get_unread_message_count(
                        channel_id, 'reader', membership.last_read_at, db=db
                    )
                last = await messages.Messages.get_last_message_by_channel_id(channel_id, db=db)
                expected_latest[channel_id] = last.created_at if last else None

            statements.clear()
            unread = await messages.Messages.get_unread_message_counts_by_channel_ids(channel_ids, 'reader', db=db)
            latest = await messages.Messages.get_last_message_at_by_channel_ids(channel_ids, db=db)
            assert len(statements) == 2
            assert {id: unread.get(id, 0) for id in channel_ids} == {id: expected_unread.get(id, 0) for id in channel_ids}
            assert {id: latest.get(id) for id in channel_ids} == expected_latest
            assert unread == {'group': 1, 'dm': 1}
            assert 'hidden' not in latest

            statements.clear()
            assert await messages.Messages.get_last_message_at_by_channel_ids([], db=db) == {}
            assert await messages.Messages.get_unread_message_counts_by_channel_ids([], 'reader', db=db) == {}
            assert await channels.Channels.get_members_by_channel_ids([], db=db) == {}
            assert statements == []

    asyncio.run(run())


def test_channel_list_batches_dm_users_and_skips_unneeded_members(monkeypatch):
    from open_webui.routers import channels as router

    async def run():
        async with isolated_database(monkeypatch) as (db, statements):
            db.add_all(
                users.User(id=id, name=id, email=f'{id}@example.test', role='user',
                           last_active_at=0, created_at=0, updated_at=0)
                for id in ('reader', 'peer')
            )
            db.add_all([
                channels.ChannelMember(id='reader', channel_id='dm', user_id='reader'),
                channels.ChannelMember(id='peer', channel_id='dm', user_id='peer', is_active=False),
                channels.ChannelMember(id='peer-duplicate', channel_id='dm', user_id='peer'),
                channels.ChannelMember(id='deleted', channel_id='dm', user_id='deleted'),
                channels.ChannelMember(id='hidden', channel_id='hidden', user_id='hidden'),
            ])
            await db.commit()
            access_check = AsyncMock()
            visible_channels = AsyncMock()
            monkeypatch.setattr(router, 'check_channels_access', access_check)
            monkeypatch.setattr(channels.Channels, 'get_channels_by_user_id', visible_channels)

            for count in (1, 30):
                visible_channels.return_value = [
                    channels.ChannelModel(id=f'group-{i}', name=f'Group {i}', type='group',
                                          user_id='reader', created_at=0, updated_at=0)
                    for i in range(count)
                ] + [channels.ChannelModel(id='dm', name='', type='dm', user_id='reader', created_at=0, updated_at=0)]
                statements.clear()
                response = await router.get_channels(None, SimpleNamespace(id='reader'), db=db)
                assert len(statements) == 4
                assert len(response) == count + 1
                assert response[0].users is None and response[0].user_ids is None
                assert response[-1].user_ids == ['reader', 'peer', 'peer', 'deleted']
                assert {user.id for user in response[-1].users} == {'reader', 'peer'}
                assert len(response[-1].users) == 2
                assert all(item.unread_count == 0 and item.last_message_at is None for item in response)

            visible_channels.return_value = visible_channels.return_value[:-1]
            statements.clear()
            await router.get_channels(None, SimpleNamespace(id='reader'), db=db)
            assert len(statements) == 2

            visible_channels.return_value = []
            statements.clear()
            assert await router.get_channels(None, SimpleNamespace(id='reader'), db=db) == []
            assert statements == []
            assert access_check.await_count == 4

    asyncio.run(run())
