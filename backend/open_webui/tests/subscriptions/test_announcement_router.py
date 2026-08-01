from types import SimpleNamespace

import pytest

from open_webui.routers import announcements


def test_announcement_router_exposes_user_and_admin_paths():
    paths = {route.path for route in announcements.router.routes}

    assert '/active' in paths
    assert '/{announcement_id}/viewed' in paths
    assert '/admin' in paths
    assert '/admin/{announcement_id}' in paths


@pytest.mark.asyncio
async def test_admin_router_round_trips_presentation_fields(db_session):
    admin = SimpleNamespace(id='admin-1')
    created = await announcements.create_admin_announcement(
        announcements.AnnouncementForm(
            title='ArtiChat update',
            summary='A focused summary',
            body='The complete announcement body.',
            image_url='/assets/images/galaxy.jpg',
            view_button_label='展开阅读',
            close_button_label='我知道了',
            display_mode='once',
            is_active=True,
        ),
        user=admin,
        db=db_session,
    )

    assert created.summary == 'A focused summary'
    assert created.image_url == '/assets/images/galaxy.jpg'
    assert created.view_button_label == '展开阅读'
    assert created.close_button_label == '我知道了'

    updated = await announcements.update_admin_announcement(
        created.id,
        announcements.AnnouncementUpdateForm(
            summary='Updated summary',
            image_url='/assets/images/earth.jpg',
            view_button_label='查看完整公告',
            close_button_label='关闭',
        ),
        user=admin,
        db=db_session,
    )

    assert updated.summary == 'Updated summary'
    assert updated.image_url == '/assets/images/earth.jpg'
    assert updated.view_button_label == '查看完整公告'
    assert updated.close_button_label == '关闭'


@pytest.mark.asyncio
async def test_active_router_returns_presentation_fields(db_session):
    admin = SimpleNamespace(id='admin-1')
    user = SimpleNamespace(id='user-1', created_at=1_719_000_000)
    created = await announcements.create_admin_announcement(
        announcements.AnnouncementForm(
            title='Visible update',
            summary='Visible summary',
            body='Visible details',
            image_url='/assets/images/space.jpg',
            view_button_label='查看公告',
            close_button_label='关闭',
        ),
        user=admin,
        db=db_session,
    )

    response = await announcements.get_active_announcements(user=user, db=db_session)

    assert [item.id for item in response['items']] == [created.id]
    assert response['items'][0].summary == 'Visible summary'
    assert response['items'][0].close_button_label == '关闭'
