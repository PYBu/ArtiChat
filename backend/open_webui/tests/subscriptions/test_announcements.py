import pytest


def announcements():
    try:
        from open_webui.models.announcements import Announcements
    except ModuleNotFoundError:
        pytest.fail('Announcements model is missing')
    return Announcements


@pytest.mark.asyncio
async def test_once_announcement_is_hidden_after_viewed(db_session):
    Announcements = announcements()
    announcement = await Announcements.create(
        title='Welcome',
        body='Welcome to ArtiChat',
        display_mode='once',
        button_label='知道了',
        icon='sparkles',
        is_active=True,
        starts_at=None,
        ends_at=None,
        sort_order=0,
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    active = await Announcements.get_active_for_user(
        user_id='user-1',
        user_created_at=1_719_000_000,
        now=1_720_000_010,
        db=db_session,
    )
    await Announcements.mark_viewed(announcement.id, user_id='user-1', now=1_720_000_020, db=db_session)
    after_view = await Announcements.get_active_for_user(
        user_id='user-1',
        user_created_at=1_719_000_000,
        now=1_720_000_030,
        db=db_session,
    )

    assert [item.id for item in active] == [announcement.id]
    assert announcement.id not in [item.id for item in after_view]


@pytest.mark.asyncio
async def test_every_login_announcement_remains_available_after_viewed(db_session):
    Announcements = announcements()
    announcement = await Announcements.create(
        title='Maintenance',
        body='Scheduled maintenance',
        display_mode='every_login',
        button_label='知道了',
        icon='bell',
        is_active=True,
        starts_at=None,
        ends_at=None,
        sort_order=0,
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    await Announcements.mark_viewed(announcement.id, user_id='user-1', now=1_720_000_020, db=db_session)
    active = await Announcements.get_active_for_user(
        user_id='user-1',
        user_created_at=1_719_000_000,
        now=1_720_000_030,
        db=db_session,
    )

    assert [item.id for item in active] == [announcement.id]


@pytest.mark.asyncio
async def test_new_user_announcement_only_shows_to_users_created_after_announcement(db_session):
    Announcements = announcements()
    announcement = await Announcements.create(
        title='New users',
        body='New user onboarding',
        display_mode='new_user',
        button_label='开始',
        icon='rocket',
        is_active=True,
        starts_at=None,
        ends_at=None,
        sort_order=0,
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    old_user_active = await Announcements.get_active_for_user(
        user_id='old-user',
        user_created_at=1_719_999_999,
        now=1_720_000_010,
        db=db_session,
    )
    new_user_active = await Announcements.get_active_for_user(
        user_id='new-user',
        user_created_at=1_720_000_001,
        now=1_720_000_010,
        db=db_session,
    )

    assert announcement.id not in [item.id for item in old_user_active]
    assert [item.id for item in new_user_active] == [announcement.id]


@pytest.mark.asyncio
async def test_deleted_announcement_is_hidden_from_default_admin_list(db_session):
    Announcements = announcements()
    announcement = await Announcements.create(
        title='Delete me',
        body='This announcement should leave the default list.',
        display_mode='once',
        button_label='知道了',
        icon='trash',
        is_active=True,
        starts_at=None,
        ends_at=None,
        sort_order=0,
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    await Announcements.delete(announcement.id, db=db_session)

    visible = await Announcements.list_all(db=db_session)
    history = await Announcements.list_all(include_inactive=True, db=db_session)

    assert announcement.id not in [item.id for item in visible]
    assert announcement.id in [item.id for item in history]
