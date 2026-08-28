import asyncio
from types import SimpleNamespace

import pytest

from open_webui.models.config import Config
from open_webui.utils import access_restrictions as restrictions


class Request:
    def __init__(self, host='203.0.113.10'):
        self.client = SimpleNamespace(host=host)
        self.headers = {'user-agent': 'access-restrictions-test'}


def test_normalize_ip_network_and_country_code():
    assert restrictions.normalize_ip_network('203.0.113.10') == '203.0.113.10/32'
    assert restrictions.normalize_ip_network('2001:db8::1') == '2001:db8::1/128'
    assert restrictions.normalize_country_code(' cn ') == 'CN'

    with pytest.raises(ValueError, match='IP_NETWORK_INVALID'):
        restrictions.normalize_ip_network('not-an-ip')
    with pytest.raises(ValueError, match='COUNTRY_CODE_INVALID'):
        restrictions.normalize_country_code('CHN')


def test_ip_blacklist_is_checked_before_country(monkeypatch):
    async def fake_config_get(key, default=None):
        return True if key == restrictions.ACCESS_RESTRICTIONS_ENABLED_KEY else default

    async def fake_ip_rules(**_kwargs):
        return [SimpleNamespace(id='iprule_1', network='203.0.113.0/24')]

    async def fake_region_rules(**_kwargs):
        return [SimpleNamespace(id='region_1', country_code='CN')]

    monkeypatch.setattr(Config, 'get', staticmethod(fake_config_get))
    monkeypatch.setattr(restrictions.AccessRestrictionIPRulesTable, 'list', fake_ip_rules)
    monkeypatch.setattr(restrictions.AccessRestrictionRegionRulesTable, 'list', fake_region_rules)
    monkeypatch.setattr(restrictions.geoip_country_resolver, 'lookup', lambda _ip: 'CN')

    decision = asyncio.run(restrictions.evaluate_login_access(Request()))
    assert decision.allowed is False
    assert decision.code == restrictions.IP_BANNED
    assert decision.rule_id == 'iprule_1'


def test_admin_bypasses_enabled_policy(monkeypatch):
    async def fail_config_get(*_args, **_kwargs):
        raise AssertionError('admin bypass should not read policy config')

    monkeypatch.setattr(Config, 'get', staticmethod(fail_config_get))
    decision = asyncio.run(
        restrictions.evaluate_login_access(Request(), user=SimpleNamespace(role='admin'))
    )
    assert decision.allowed is True
    assert decision.bypassed is True
    assert decision.reason == 'admin_bypass'


def test_region_rule_blocks_when_geoip_resolves(monkeypatch):
    async def fake_config_get(key, default=None):
        return True if key == restrictions.ACCESS_RESTRICTIONS_ENABLED_KEY else default

    async def no_ip_rules(**_kwargs):
        return []

    async def region_rules(**_kwargs):
        return [SimpleNamespace(id='region_1', country_code='CN')]

    monkeypatch.setattr(Config, 'get', staticmethod(fake_config_get))
    monkeypatch.setattr(restrictions.AccessRestrictionIPRulesTable, 'list', no_ip_rules)
    monkeypatch.setattr(restrictions.AccessRestrictionRegionRulesTable, 'list', region_rules)
    monkeypatch.setattr(restrictions.geoip_country_resolver, 'lookup', lambda _ip: 'CN')

    decision = asyncio.run(restrictions.evaluate_login_access(Request('198.51.100.2')))
    assert decision.allowed is False
    assert decision.code == restrictions.IP_RESTRICTED_REGION
    assert decision.country_code == 'CN'
