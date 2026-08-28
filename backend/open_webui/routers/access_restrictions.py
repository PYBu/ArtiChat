from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from open_webui.models.access_restrictions import (
    AccessRestrictionIPRuleModel,
    AccessRestrictionIPRulesTable,
    AccessRestrictionRegionRuleModel,
    AccessRestrictionRegionRulesTable,
    LoginEventsTable,
)
from open_webui.models.config import Config
from open_webui.utils.access_restrictions import (
    ACCESS_RESTRICTIONS_ENABLED_KEY,
    ACCESS_RESTRICTIONS_FAILURE_MODE_KEY,
    geoip_country_resolver,
    normalize_country_code,
    normalize_ip_network,
)
from open_webui.utils.auth import get_admin_user
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

router = APIRouter()


class AccessRestrictionConfigForm(BaseModel):
    enabled: bool = False


class AccessRestrictionConfigResponse(BaseModel):
    enabled: bool
    geoip: dict[str, Any]
    geoip_failure_mode: str
    retention_days: int = 7


class IPRuleCreateForm(BaseModel):
    network: str = Field(min_length=1, max_length=128)
    note: str | None = Field(default=None, max_length=500)
    enabled: bool = True


class IPRuleUpdateForm(BaseModel):
    enabled: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class RegionRuleCreateForm(BaseModel):
    country_code: str = Field(min_length=2, max_length=2)
    note: str | None = Field(default=None, max_length=500)
    enabled: bool = True


class RegionRuleUpdateForm(BaseModel):
    enabled: bool | None = None
    note: str | None = Field(default=None, max_length=500)


async def _config_response() -> AccessRestrictionConfigResponse:
    return AccessRestrictionConfigResponse(
        enabled=bool(await Config.get(ACCESS_RESTRICTIONS_ENABLED_KEY, False)),
        geoip=geoip_country_resolver.status(),
        geoip_failure_mode=str(await Config.get(ACCESS_RESTRICTIONS_FAILURE_MODE_KEY, 'allow') or 'allow'),
    )


@router.get('/config', response_model=AccessRestrictionConfigResponse)
async def get_access_restriction_config(user=Depends(get_admin_user)):
    return await _config_response()


@router.put('/config', response_model=AccessRestrictionConfigResponse)
async def update_access_restriction_config(
    form_data: AccessRestrictionConfigForm,
    user=Depends(get_admin_user),
):
    await Config.upsert({ACCESS_RESTRICTIONS_ENABLED_KEY: form_data.enabled})
    return await _config_response()


@router.get('/ip-rules', response_model=dict[str, list[AccessRestrictionIPRuleModel]])
async def list_ip_rules(user=Depends(get_admin_user)):
    return {'items': await AccessRestrictionIPRulesTable.list()}


@router.post('/ip-rules', response_model=AccessRestrictionIPRuleModel, status_code=status.HTTP_201_CREATED)
async def create_ip_rule(
    form_data: IPRuleCreateForm,
    user=Depends(get_admin_user),
):
    try:
        network = normalize_ip_network(form_data.network)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return await AccessRestrictionIPRulesTable.create(
            network=network,
            note=form_data.note.strip() if form_data.note else None,
            enabled=form_data.enabled,
            created_by=user.id,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='IP_RULE_ALREADY_EXISTS') from exc


@router.patch('/ip-rules/{rule_id}', response_model=AccessRestrictionIPRuleModel)
async def update_ip_rule(
    rule_id: str,
    form_data: IPRuleUpdateForm,
    user=Depends(get_admin_user),
):
    row = await AccessRestrictionIPRulesTable.update(
        rule_id,
        enabled=form_data.enabled,
        note=form_data.note.strip() if form_data.note is not None else None,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='IP_RULE_NOT_FOUND')
    return row


@router.delete('/ip-rules/{rule_id}')
async def delete_ip_rule(rule_id: str, user=Depends(get_admin_user)):
    if not await AccessRestrictionIPRulesTable.delete(rule_id):
        raise HTTPException(status_code=404, detail='IP_RULE_NOT_FOUND')
    return {'status': True}


@router.get('/regions', response_model=dict[str, list[AccessRestrictionRegionRuleModel]])
async def list_region_rules(user=Depends(get_admin_user)):
    return {'items': await AccessRestrictionRegionRulesTable.list()}


@router.post('/regions', response_model=AccessRestrictionRegionRuleModel, status_code=status.HTTP_201_CREATED)
async def create_region_rule(
    form_data: RegionRuleCreateForm,
    user=Depends(get_admin_user),
):
    try:
        country_code = normalize_country_code(form_data.country_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return await AccessRestrictionRegionRulesTable.create(
            country_code=country_code,
            note=form_data.note.strip() if form_data.note else None,
            enabled=form_data.enabled,
            created_by=user.id,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='REGION_RULE_ALREADY_EXISTS') from exc


@router.patch('/regions/{rule_id}', response_model=AccessRestrictionRegionRuleModel)
async def update_region_rule(
    rule_id: str,
    form_data: RegionRuleUpdateForm,
    user=Depends(get_admin_user),
):
    row = await AccessRestrictionRegionRulesTable.update(
        rule_id,
        enabled=form_data.enabled,
        note=form_data.note.strip() if form_data.note is not None else None,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='REGION_RULE_NOT_FOUND')
    return row


@router.delete('/regions/{rule_id}')
async def delete_region_rule(rule_id: str, user=Depends(get_admin_user)):
    if not await AccessRestrictionRegionRulesTable.delete(rule_id):
        raise HTTPException(status_code=404, detail='REGION_RULE_NOT_FOUND')
    return {'status': True}


@router.get('/login-records')
async def list_login_records(
    query: str | None = None,
    result: str | None = None,
    start_at: int | None = None,
    end_at: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_admin_user),
):
    await LoginEventsTable.purge()
    return await LoginEventsTable.list_recent(
        query=query,
        result=result,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        offset=offset,
    )
