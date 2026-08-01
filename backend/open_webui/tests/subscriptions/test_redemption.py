import re

import open_webui.models.subscriptions as subscription_models
import pytest
from open_webui.models.subscriptions import (
    CHATPOWER_TIER,
    GiftCardGrants,
    PLUS_TIER,
    RedemptionCode,
    RedemptionCodes,
    RedemptionRecords,
    SubscriptionLedgers,
    SubscriptionPlans,
    UserSubscriptions,
    chatpoint_to_micros,
    generate_redemption_code_from_template,
    generate_redemption_code_with_prefix,
    normalize_redemption_code_template,
)
from open_webui.utils.subscriptions import redeem_code
from sqlalchemy import event


def test_redemption_code_template_uses_secure_numeric_placeholders(monkeypatch):
    digits = iter('123456789012')
    monkeypatch.setattr(subscription_models.secrets, 'choice', lambda _alphabet: next(digits))

    assert (
        generate_redemption_code_from_template(' artipass-0000-0000-0000 ')
        == 'ARTIPASS-1234-5678-9012'
    )


@pytest.mark.parametrize(
    ('template', 'error'),
    [
        ('PASS-0000', 'REDEMPTION_CODE_TEMPLATE_TOO_WEAK'),
        ('PASS 0000 0000', 'REDEMPTION_CODE_TEMPLATE_INVALID'),
        ('-PASS-000000', 'REDEMPTION_CODE_TEMPLATE_INVALID'),
    ],
)
def test_redemption_code_template_rejects_weak_or_invalid_formats(template, error):
    with pytest.raises(ValueError, match=error):
        normalize_redemption_code_template(template)


def test_redemption_code_prefix_generates_secure_alphanumeric_suffix():
    generated = generate_redemption_code_with_prefix(' arti- ')
    assert re.fullmatch(r'ARTI-[A-Z0-9]{8}-[A-Z0-9]{8}', generated)


@pytest.mark.asyncio
async def test_batch_code_creation_supports_a_named_template(db_session):
    created = await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=3,
        max_uses=1,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=0,
        expires_at=None,
        memo='template batch',
        created_by='admin',
        code_template='ARTIPASS-0000-0000-0000',
        db=db_session,
    )

    assert len(created.raw_codes) == 3
    assert len(set(created.raw_codes)) == 3
    assert all(re.fullmatch(r'ARTIPASS-\d{4}-\d{4}-\d{4}', code) for code in created.raw_codes)


@pytest.mark.asyncio
async def test_batch_code_creation_checks_existing_hashes_once(db_session, monkeypatch):
    generated = iter(['BATCH-CODE-001', 'BATCH-CODE-002', 'BATCH-CODE-003'])
    monkeypatch.setattr(subscription_models, 'generate_redemption_code', lambda: next(generated))
    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(db_session.bind.sync_engine, 'before_cursor_execute', record_statement)
    try:
        created = await RedemptionCodes.create_codes(
            mode='single_use',
            quantity=3,
            max_uses=1,
            tier=None,
            duration_days=None,
            plan_chatpoint_micros=0,
            check_chatpoint_micros=0,
            expires_at=None,
            memo='batch query check',
            created_by='admin',
            db=db_session,
        )
    finally:
        event.remove(db_session.bind.sync_engine, 'before_cursor_execute', record_statement)

    duplicate_checks = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith('SELECT') and 'redemption_code' in statement.lower()
    ]
    assert created.raw_codes == ['BATCH-CODE-001', 'BATCH-CODE-002', 'BATCH-CODE-003']
    assert len(duplicate_checks) == 1


@pytest.mark.asyncio
async def test_single_use_code_can_only_be_redeemed_once(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    created = await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=0,
        expires_at=None,
        memo='plus trial',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    result = await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)
    assert result.subscription.tier == PLUS_TIER

    with pytest.raises(ValueError, match='REDEMPTION_CODE_EXHAUSTED'):
        await redeem_code('user-2', created.raw_codes[0], now=1_720_000_010, db=db_session)


@pytest.mark.asyncio
async def test_multi_use_code_prevents_same_user_redeeming_twice(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    created = await RedemptionCodes.create_codes(
        mode='multi_use',
        quantity=1,
        max_uses=5,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=chatpoint_to_micros(25),
        expires_at=None,
        memo='check topup',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)
    with pytest.raises(ValueError, match='REDEMPTION_CODE_ALREADY_USED'):
        await redeem_code('user-1', created.raw_codes[0], now=1_720_000_001, db=db_session)


@pytest.mark.asyncio
async def test_lower_tier_code_does_not_downgrade_higher_subscription(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    await UserSubscriptions.create_from_plan(
        user_id='user-1',
        plan_id=CHATPOWER_TIER,
        starts_at=1_720_000_000,
        expires_at=1_720_000_000 + 30 * 24 * 60 * 60,
        source='admin',
        db=db_session,
    )
    created = await RedemptionCodes.create_codes(
        mode='multi_use',
        quantity=1,
        max_uses=10,
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=chatpoint_to_micros(3),
        check_chatpoint_micros=chatpoint_to_micros(4),
        expires_at=None,
        memo='lower tier grant',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )

    result = await redeem_code('user-1', created.raw_codes[0], now=1_720_000_000, db=db_session)

    assert result.subscription.tier == CHATPOWER_TIER
    assert result.subscription.plan_balance_micros == chatpoint_to_micros(10003)
    assert result.subscription.check_balance_micros == chatpoint_to_micros(4)


@pytest.mark.asyncio
async def test_admin_can_create_custom_code_and_list_full_code(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)

    created = await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=chatpoint_to_micros(12),
        check_chatpoint_micros=0,
        expires_at=None,
        memo='custom launch code',
        created_by='admin',
        custom_code='LAUNCH-PLUS-001',
        now=1_720_000_000,
        db=db_session,
    )

    listed = await RedemptionCodes.list_codes(limit=10, offset=0, db=db_session)

    assert created.raw_codes == ['LAUNCH-PLUS-001']
    assert listed[0].code == 'LAUNCH-PLUS-001'
    assert listed[0].code_preview == 'LAUN--001'


@pytest.mark.asyncio
async def test_redemption_benefit_types_are_explicit_and_mutually_exclusive(db_session):
    subscription = await RedemptionCodes.create_codes(
        benefit_type='subscription',
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=PLUS_TIER,
        duration_days=30,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=0,
        expires_at=None,
        memo='subscription card',
        created_by='admin',
        db=db_session,
    )
    recharge = await RedemptionCodes.create_codes(
        benefit_type='recharge',
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=chatpoint_to_micros(50),
        expires_at=None,
        memo='recharge card',
        created_by='admin',
        db=db_session,
    )

    subscription_row = await RedemptionCodes.get_by_raw_code(subscription.raw_codes[0], db=db_session)
    recharge_row = await RedemptionCodes.get_by_raw_code(recharge.raw_codes[0], db=db_session)
    assert subscription_row.benefit_type == 'subscription'
    assert recharge_row.benefit_type == 'recharge'

    with pytest.raises(ValueError, match='REDEMPTION_BENEFIT_CONFLICT'):
        await RedemptionCodes.create_codes(
            benefit_type='recharge',
            mode='single_use',
            quantity=1,
            max_uses=1,
            tier=PLUS_TIER,
            duration_days=30,
            plan_chatpoint_micros=0,
            check_chatpoint_micros=chatpoint_to_micros(50),
            expires_at=None,
            memo='mixed card',
            created_by='admin',
            db=db_session,
        )


@pytest.mark.asyncio
async def test_archived_code_can_be_tombstone_cleared_without_deleting_audit_row(db_session):
    created = await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=chatpoint_to_micros(5),
        expires_at=None,
        memo='clear me',
        created_by='admin',
        custom_code='CLEAR-ME-001',
        db=db_session,
    )
    await RedemptionCodes.delete_code(created.code_ids[0], db=db_session)

    cleared = await RedemptionCodes.clear_codes(created.code_ids, now=1_720_000_000, db=db_session)
    assert cleared[0].code is None
    assert cleared[0].code_preview == '[已清除]'
    assert cleared[0].purged_at == 1_720_000_000

    archive = await RedemptionCodes.list_codes(status='archive', db=db_session)
    assert archive[0].id == created.code_ids[0]
    assert archive[0].code_hash


@pytest.mark.asyncio
async def test_deleted_redemption_code_cannot_be_redeemed(db_session):
    await SubscriptionPlans.seed_defaults(db=db_session)
    created = await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=0,
        check_chatpoint_micros=chatpoint_to_micros(5),
        expires_at=None,
        memo='delete me',
        created_by='admin',
        custom_code='DELETE-ME-001',
        now=1_720_000_000,
        db=db_session,
    )

    await RedemptionCodes.delete_code(created.code_ids[0], db=db_session)

    with pytest.raises(ValueError, match='REDEMPTION_CODE_DISABLED'):
        await redeem_code('user-1', 'DELETE-ME-001', now=1_720_000_100, db=db_session)


@pytest.mark.asyncio
async def test_redemption_rolls_back_every_write_when_record_insert_fails(db_session, monkeypatch):
    await SubscriptionPlans.seed_defaults(db=db_session)
    created = await RedemptionCodes.create_codes(
        mode='single_use',
        quantity=1,
        max_uses=1,
        tier=None,
        duration_days=None,
        plan_chatpoint_micros=chatpoint_to_micros(7),
        check_chatpoint_micros=chatpoint_to_micros(3),
        expires_at=None,
        memo='atomic redemption',
        created_by='admin',
        now=1_720_000_000,
        db=db_session,
    )
    code = await RedemptionCodes.get_by_raw_code(created.raw_codes[0], db=db_session)

    async def fail_insert(**_kwargs):
        raise RuntimeError('injected redemption record failure')

    monkeypatch.setattr(RedemptionRecords, 'insert', fail_insert)

    with pytest.raises(RuntimeError, match='injected redemption record failure'):
        await redeem_code('user-atomic', created.raw_codes[0], now=1_720_000_010, db=db_session)

    unchanged_code = await RedemptionCodes.get_by_raw_code(created.raw_codes[0], db=db_session)
    assert unchanged_code.used_count == 0
    assert await UserSubscriptions.get_by_user_id('user-atomic', db=db_session) is None
    assert await RedemptionRecords.get_by_code_and_user(code.id, 'user-atomic', db=db_session) is None
    assert await SubscriptionLedgers.get_recent_for_user('user-atomic', db=db_session) == []


@pytest.mark.asyncio
async def test_pending_gift_cards_exclude_disabled_expired_and_exhausted_codes(db_session):
    common = {
        'user_ids': ['user-1'],
        'mode': 'single_use',
        'tier': PLUS_TIER,
        'duration_days': 30,
        'plan_chatpoint_micros': 0,
        'check_chatpoint_micros': 0,
        'memo': 'gift',
        'created_by': 'admin',
        'now': 100,
        'db': db_session,
    }
    active = await GiftCardGrants.issue_grants(**common, expires_at=500)
    disabled = await GiftCardGrants.issue_grants(**common, expires_at=500)
    expired = await GiftCardGrants.issue_grants(**common, expires_at=150)
    exhausted = await GiftCardGrants.issue_grants(**common, expires_at=500)

    disabled_code = await db_session.get(RedemptionCode, disabled.grants[0].redemption_code_id)
    exhausted_code = await db_session.get(RedemptionCode, exhausted.grants[0].redemption_code_id)
    assert disabled_code is not None
    assert exhausted_code is not None
    disabled_code.is_active = False
    exhausted_code.used_count = exhausted_code.max_uses
    await db_session.commit()

    pending = await GiftCardGrants.list_pending_for_user('user-1', now=200, db=db_session)

    assert [item.id for item in pending] == [active.grants[0].id]
