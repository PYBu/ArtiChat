import pytest

from open_webui.models.subscriptions import (
    PLUS_TIER,
    SubscriptionPlans,
    chatpoint_to_micros,
)
from open_webui.models.users import User


def gift_card_grants():
    from open_webui.models import subscriptions

    grants = getattr(subscriptions, 'GiftCardGrants', None)
    if grants is None:
        pytest.fail('GiftCardGrants helper is missing')
    return grants


async def create_user(db_session, user_id: str, email: str, username: str, name: str, created_at: int = 1_720_000_000):
    db_session.add(
        User(
            id=user_id,
            email=email,
            username=username,
            name=name,
            role='user',
            created_at=created_at,
            updated_at=created_at,
            last_active_at=created_at,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_targeted_gift_card_can_be_claimed_once(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await create_user(db_session, 'user-1', 'one@example.com', 'one', 'One')
    GiftCardGrants = gift_card_grants()

    issued = await GiftCardGrants.issue_grants(
        user_ids=['user-1'],
        mode='single_use',
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=chatpoint_to_micros(20),
        check_chatpoint_micros=chatpoint_to_micros(5),
        expires_at=None,
        memo='targeted gift',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )
    pending = await GiftCardGrants.list_pending_for_user('user-1', db=db_session)

    result = await GiftCardGrants.claim(pending[0].id, user_id='user-1', now=1_720_000_010, db=db_session)

    assert issued.batch_id
    assert len(issued.grants) == 1
    assert pending[0].user_id == 'user-1'
    assert result.subscription.tier == PLUS_TIER
    assert result.grant.status == 'claimed'
    with pytest.raises(ValueError, match='GIFT_CARD_ALREADY_CLAIMED'):
        await GiftCardGrants.claim(pending[0].id, user_id='user-1', now=1_720_000_020, db=db_session)


@pytest.mark.asyncio
async def test_revoked_gift_card_cannot_be_claimed(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await create_user(db_session, 'user-1', 'one@example.com', 'one', 'One')
    GiftCardGrants = gift_card_grants()
    issued = await GiftCardGrants.issue_grants(
        user_ids=['user-1'],
        mode='single_use',
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=chatpoint_to_micros(3),
        expires_at=None,
        memo='revoked gift',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    await GiftCardGrants.revoke(issued.grants[0].id, db=db_session)

    with pytest.raises(ValueError, match='GIFT_CARD_NOT_PENDING'):
        await GiftCardGrants.claim(issued.grants[0].id, user_id='user-1', now=1_720_000_020, db=db_session)


@pytest.mark.asyncio
async def test_all_user_gift_card_issue_uses_current_users_only(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await create_user(db_session, 'user-1', 'one@example.com', 'one', 'One')
    await create_user(db_session, 'user-2', 'two@example.com', 'two', 'Two')
    GiftCardGrants = gift_card_grants()

    issued = await GiftCardGrants.issue_for_all_current_users(
        mode='single_use',
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=chatpoint_to_micros(1),
        expires_at=None,
        memo='all users',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )
    await create_user(db_session, 'user-3', 'three@example.com', 'three', 'Three')

    pending_1 = await GiftCardGrants.list_pending_for_user('user-1', db=db_session)
    pending_2 = await GiftCardGrants.list_pending_for_user('user-2', db=db_session)
    pending_3 = await GiftCardGrants.list_pending_for_user('user-3', db=db_session)

    assert len(issued.grants) == 2
    assert len({grant.redemption_code_id for grant in issued.grants}) == 2
    assert len(pending_1) == 1
    assert len(pending_2) == 1
    assert pending_3 == []
