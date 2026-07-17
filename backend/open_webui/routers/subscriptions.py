from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from open_webui.internal.db import get_async_session
from open_webui.models.models import Models
from open_webui.models.subscriptions import (
    FREE_TIER,
    GiftCardGrants,
    RedemptionCodes,
    SubscriptionLedgers,
    SubscriptionPlans,
    SubscriptionUsages,
    UserSubscriptions,
    chatpoint_to_micros,
    now_ts,
)
from open_webui.utils.subscriptions import ModelSubscriptionPolicy, ensure_subscription_current, redeem_code
from open_webui.utils.sensitive_actions import authorize_sensitive_action
from open_webui.utils.account_notifications import notify_subscription_changed, notify_user
from open_webui.models.users import Users
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
bearer_security = HTTPBearer(auto_error=False)


async def get_subscription_current_user(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    auth_token: HTTPAuthorizationCredentials = Depends(bearer_security),
):
    from open_webui.utils.auth import get_current_user

    return await get_current_user(request, response, background_tasks, auth_token)


def get_verified_subscription_user(user=Depends(get_subscription_current_user)):
    if user.role not in {'user', 'admin'}:
        raise HTTPException(status_code=401, detail='ACCESS_PROHIBITED')
    return user


def get_admin_subscription_user(user=Depends(get_subscription_current_user)):
    if user.role != 'admin':
        raise HTTPException(status_code=401, detail='ACCESS_PROHIBITED')
    return user


class RedeemForm(BaseModel):
    code: str


class BillingAddressForm(BaseModel):
    billing_address: dict
    verification_token: str | None = None


class AdminCodeCreateForm(BaseModel):
    code: str | None = Field(default=None, max_length=128)
    mode: Literal['single_use', 'multi_use']
    quantity: int = Field(default=1, ge=1, le=500)
    max_uses: int = Field(default=1, ge=1, le=1_000_000)
    tier: str | None = None
    duration_days: int | None = None
    plan_chatpoint: str | int = 0
    check_chatpoint: str | int = 0
    expires_at: int | None = None
    memo: str | None = None


class AdminCodeUpdateForm(BaseModel):
    is_active: bool | None = None
    memo: str | None = None


class AdminPlanUpdateForm(BaseModel):
    display_name: str | None = None
    description: str | None = None
    plan_chatpoint: str | int | None = None
    period_days: int | None = None
    features: dict | list | None = None
    is_active: bool | None = None


class AdminModelPolicyForm(BaseModel):
    subscription: ModelSubscriptionPolicy


class AdminModelPolicyItem(BaseModel):
    id: str
    subscription: ModelSubscriptionPolicy


class AdminModelPoliciesForm(BaseModel):
    models: list[AdminModelPolicyItem]

    @field_validator('models')
    @classmethod
    def validate_models(cls, value: list[AdminModelPolicyItem]) -> list[AdminModelPolicyItem]:
        if not value:
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: models must not be empty')
        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError('MODEL_SUBSCRIPTION_POLICY_INVALID: model ids must be unique')
        return value


class AdminUserSubscriptionUpdateForm(BaseModel):
    tier: str | None = None
    expires_at: int | None = None
    plan_chatpoint: str | int | None = None
    check_chatpoint: str | int | None = None
    status: str | None = None
    notes: str | None = None


class GiftCardCreateForm(BaseModel):
    user_ids: list[str] = Field(default_factory=list, max_length=1000)
    all_users: bool = False
    mode: Literal['single_use', 'multi_use'] = 'single_use'
    tier: str | None = None
    duration_days: int | None = None
    plan_chatpoint: str | int = 0
    check_chatpoint: str | int = 0
    expires_at: int | None = None
    memo: str | None = None


def _admin_model_policy_response(model) -> dict:
    return {
        'id': model.id,
        'name': model.name,
        'base_model_id': model.base_model_id,
        'subscription': model.meta.subscription if model.meta else None,
    }


@router.get('/me')
async def get_my_subscription(
    user=Depends(get_verified_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await ensure_subscription_current(user.id, db=db)


@router.get('/plans')
async def get_subscription_plans(
    user=Depends(get_verified_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    await SubscriptionPlans.seed_defaults(db=db)
    return [plan for plan in await SubscriptionPlans.get_plans(db=db) if plan.is_active]


@router.get('/usage')
async def get_my_usage(user=Depends(get_verified_subscription_user), db: AsyncSession = Depends(get_async_session)):
    subscription = await ensure_subscription_current(user.id, db=db)
    usage = await SubscriptionUsages.get_usage_summary(user_id=user.id, public=True, db=db)
    ledger = await SubscriptionLedgers.get_recent_for_user(user.id, limit=50, db=db)
    return {'subscription': subscription, 'usage': usage, 'ledger': ledger}


@router.post('/redeem')
async def redeem_subscription_code(
    form_data: RedeemForm,
    user=Depends(get_verified_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await redeem_code(user.id, form_data.code, db=db)
        await notify_subscription_changed(user, result.subscription, db=db)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/records')
async def get_my_records(user=Depends(get_verified_subscription_user), db: AsyncSession = Depends(get_async_session)):
    return {'ledger': await SubscriptionLedgers.get_recent_for_user(user.id, limit=100, db=db)}


@router.get('/gift-cards/pending')
async def get_pending_gift_cards(
    user=Depends(get_verified_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {'items': await GiftCardGrants.list_pending_for_user(user.id, db=db)}


@router.post('/gift-cards/{grant_id}/claim')
async def claim_gift_card(
    grant_id: str,
    user=Depends(get_verified_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await GiftCardGrants.claim(grant_id, user_id=user.id, db=db)
        await notify_subscription_changed(user, result.subscription, db=db)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put('/billing-address')
async def update_billing_address(
    request: Request,
    form_data: BillingAddressForm,
    user=Depends(get_verified_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        await authorize_sensitive_action(
            request,
            user,
            action='billing_address',
            verification_token=form_data.verification_token,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    subscription = await ensure_subscription_current(user.id, db=db)
    subscription.billing_address = form_data.billing_address
    saved = await UserSubscriptions.save(subscription, db=db)
    await notify_user(
        'billing_address_changed',
        user,
        {'changed_at': datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')},
        db=db,
    )
    return saved


@router.get('/admin/plans')
async def get_admin_plans(user=Depends(get_admin_subscription_user), db: AsyncSession = Depends(get_async_session)):
    await SubscriptionPlans.seed_defaults(db=db)
    return await SubscriptionPlans.get_plans(db=db)


@router.patch('/admin/plans/{plan_id}')
async def update_admin_plan(
    plan_id: str,
    form_data: AdminPlanUpdateForm,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await SubscriptionPlans.update_plan(
            plan_id,
            display_name=form_data.display_name,
            description=form_data.description,
            plan_chatpoint_allowance_micros=(
                chatpoint_to_micros(form_data.plan_chatpoint) if form_data.plan_chatpoint is not None else None
            ),
            period_days=form_data.period_days,
            features=form_data.features,
            is_active=form_data.is_active,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/admin/models')
async def get_admin_model_policies(
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    models = await Models.get_all_models(db=db)
    return [_admin_model_policy_response(model) for model in models]


@router.put('/admin/models/bulk')
async def update_admin_model_policies(
    form_data: AdminModelPoliciesForm,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    policies = {item.id: item.subscription.model_dump() for item in form_data.models}
    try:
        updated = await Models.update_model_subscription_policies(policies, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_admin_model_policy_response(model) for model in updated]


@router.put('/admin/models/{model_id}')
async def update_admin_model_policy(
    model_id: str,
    form_data: AdminModelPolicyForm,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        updated = await Models.update_model_subscription_policies(
            {model_id: form_data.subscription.model_dump()},
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _admin_model_policy_response(updated[0])


@router.get('/admin/codes')
async def get_admin_codes(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {'items': await RedemptionCodes.list_codes(limit=limit, offset=offset, db=db)}


@router.post('/admin/codes')
async def create_admin_codes(
    form_data: AdminCodeCreateForm,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await RedemptionCodes.create_codes(
        mode=form_data.mode,
        quantity=form_data.quantity,
        max_uses=form_data.max_uses,
        tier=form_data.tier,
        duration_days=form_data.duration_days,
        plan_chatpoint_micros=chatpoint_to_micros(form_data.plan_chatpoint),
        check_chatpoint_micros=chatpoint_to_micros(form_data.check_chatpoint),
        expires_at=form_data.expires_at,
        memo=form_data.memo,
        created_by=user.id,
        custom_code=form_data.code,
        db=db,
    )


@router.patch('/admin/codes/{code_id}')
async def update_admin_code(
    code_id: str,
    form_data: AdminCodeUpdateForm,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await RedemptionCodes.update_code(
            code_id,
            is_active=form_data.is_active,
            memo=form_data.memo,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete('/admin/codes/{code_id}')
async def delete_admin_code(
    code_id: str,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await RedemptionCodes.delete_code(code_id, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/admin/gift-cards')
async def get_admin_gift_cards(
    batch_id: str | None = None,
    user_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {
        'items': await GiftCardGrants.list_grants(
            batch_id=batch_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
            db=db,
        )
    }


@router.post('/admin/gift-cards')
async def create_admin_gift_cards(
    form_data: GiftCardCreateForm,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        if form_data.all_users:
            return await GiftCardGrants.issue_for_all_current_users(
                mode=form_data.mode,
                tier=form_data.tier,
                duration_days=form_data.duration_days,
                plan_chatpoint_micros=chatpoint_to_micros(form_data.plan_chatpoint),
                check_chatpoint_micros=chatpoint_to_micros(form_data.check_chatpoint),
                expires_at=form_data.expires_at,
                memo=form_data.memo,
                created_by=user.id,
                db=db,
            )
        return await GiftCardGrants.issue_grants(
            user_ids=form_data.user_ids,
            mode=form_data.mode,
            tier=form_data.tier,
            duration_days=form_data.duration_days,
            plan_chatpoint_micros=chatpoint_to_micros(form_data.plan_chatpoint),
            check_chatpoint_micros=chatpoint_to_micros(form_data.check_chatpoint),
            expires_at=form_data.expires_at,
            memo=form_data.memo,
            created_by=user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete('/admin/gift-cards/{grant_id}')
async def revoke_admin_gift_card(
    grant_id: str,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await GiftCardGrants.revoke(grant_id, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/admin/users')
async def get_admin_user_subscriptions(
    query: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {
        'items': await UserSubscriptions.list_subscriptions_with_users(
            query=query,
            limit=limit,
            offset=offset,
            db=db,
        )
    }


@router.patch('/admin/users/{user_id}')
async def update_admin_user_subscription(
    user_id: str,
    form_data: AdminUserSubscriptionUpdateForm,
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    subscription = await ensure_subscription_current(user_id, db=db)
    before = subscription.model_copy(deep=True)
    changed_fields = form_data.model_fields_set
    now = now_ts()

    if form_data.tier and form_data.tier != subscription.tier:
        plan = await SubscriptionPlans.get_plan_by_id(form_data.tier, db=db)
        if not plan:
            raise HTTPException(status_code=404, detail='SUBSCRIPTION_PLAN_NOT_FOUND')

        period_end = now + plan.period_days * 24 * 60 * 60
        subscription.tier = plan.id
        subscription.tier_rank = plan.tier_rank
        subscription.display_name = plan.display_name
        subscription.period_days = plan.period_days
        subscription.plan_chatpoint_allowance_micros = plan.plan_chatpoint_allowance_micros
        subscription.plan_balance_micros = plan.plan_chatpoint_allowance_micros
        subscription.starts_at = now
        subscription.period_start_at = now
        subscription.period_end_at = period_end
        subscription.next_reset_at = period_end
        subscription.status = 'free' if plan.id == FREE_TIER else 'active'
        subscription.source = 'admin'
        subscription.snapshot = plan.model_dump()

    if 'expires_at' in changed_fields:
        subscription.expires_at = form_data.expires_at
    if 'plan_chatpoint' in changed_fields and form_data.plan_chatpoint is not None:
        subscription.plan_balance_micros = chatpoint_to_micros(form_data.plan_chatpoint)
    if 'check_chatpoint' in changed_fields and form_data.check_chatpoint is not None:
        subscription.check_balance_micros = chatpoint_to_micros(form_data.check_chatpoint)
    if form_data.status is not None:
        subscription.status = form_data.status
    if 'notes' in changed_fields:
        subscription.notes = form_data.notes

    subscription.updated_at = now
    saved = await UserSubscriptions.save(subscription, db=db)
    await SubscriptionLedgers.insert(
        user_id=user_id,
        event_type='admin_update',
        tier_before=before.tier,
        tier_after=saved.tier,
        plan_delta_micros=saved.plan_balance_micros - before.plan_balance_micros,
        check_delta_micros=saved.check_balance_micros - before.check_balance_micros,
        plan_balance_after_micros=saved.plan_balance_micros,
        check_balance_after_micros=saved.check_balance_micros,
        created_by=user.id,
        db=db,
    )
    target_user = await Users.get_user_by_id(user_id, db=db)
    if target_user is not None:
        await notify_subscription_changed(target_user, saved, db=db)
    return saved


@router.get('/admin/usage')
async def get_admin_usage(
    user_id: str | None = None,
    user_email: str | None = None,
    model_id: str | None = None,
    status: str | None = None,
    start_at: int | None = None,
    end_at: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await SubscriptionUsages.get_usage_summary(
        user_id=user_id,
        user_email=user_email,
        model_id=model_id,
        status=status,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        offset=offset,
        include_user=True,
        db=db,
    )


@router.get('/admin/ledger')
async def get_admin_ledger(
    user_id: str | None = None,
    event_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_admin_subscription_user),
    db: AsyncSession = Depends(get_async_session),
):
    return {
        'items': await SubscriptionLedgers.search(
            user_id=user_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
            include_user=True,
            db=db,
        )
    }
