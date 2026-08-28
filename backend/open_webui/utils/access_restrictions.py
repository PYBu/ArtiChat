"""Login-time IP access policy and GeoIP lookup helpers."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status
from open_webui.env import ARTICHAT_GEOIP_DB_PATH
from open_webui.models.access_restrictions import (
    AccessRestrictionIPRulesTable,
    AccessRestrictionRegionRulesTable,
    LoginEventsTable,
)
from open_webui.models.config import Config

log = logging.getLogger(__name__)

ACCESS_RESTRICTIONS_ENABLED_KEY = 'access_restrictions.enabled'
ACCESS_RESTRICTIONS_FAILURE_MODE_KEY = 'access_restrictions.geoip_failure_mode'
ACCESS_RESTRICTIONS_RETENTION_DAYS = 7

IP_BANNED = 'IP_BANNED'
IP_RESTRICTED_REGION = 'IP_RESTRICTED_REGION'


@dataclass(frozen=True)
class AccessRestrictionDecision:
    allowed: bool
    ip_address: str | None
    country_code: str | None = None
    code: str | None = None
    result: str = 'success'
    reason: str | None = None
    rule_id: str | None = None
    bypassed: bool = False


def get_request_client_ip(request) -> str | None:
    client = getattr(request, 'client', None)
    host = getattr(client, 'host', None)
    if not host:
        return None
    try:
        address = ipaddress.ip_address(str(host).strip())
    except ValueError:
        return None
    mapped = getattr(address, 'ipv4_mapped', None)
    return str(mapped or address)


def normalize_ip_network(value: str) -> str:
    try:
        return str(ipaddress.ip_network(str(value).strip(), strict=False))
    except ValueError as exc:
        raise ValueError('IP_NETWORK_INVALID') from exc


def normalize_country_code(value: str) -> str:
    country = str(value or '').strip().upper()
    if len(country) != 2 or not country.isascii() or not country.isalpha():
        raise ValueError('COUNTRY_CODE_INVALID')
    return country


class GeoIPCountryResolver:
    """Read an MMDB country database without making a network request."""

    def __init__(self, database_path: str | Path = ARTICHAT_GEOIP_DB_PATH) -> None:
        self.database_path = Path(database_path)
        self._reader = None
        self._reader_mtime_ns: int | None = None
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, str | None]] = {}
        self._cache_ttl = 3600
        self._cache_limit = 4096

    def _get_reader(self):
        try:
            stat = self.database_path.stat()
        except OSError:
            self._reader = None
            self._reader_mtime_ns = None
            return None

        if self._reader is not None and self._reader_mtime_ns == stat.st_mtime_ns:
            return self._reader

        try:
            import maxminddb

            reader = maxminddb.open_database(str(self.database_path))
        except Exception as exc:
            log.warning('GeoIP country database is unavailable: %s', exc)
            self._reader = None
            self._reader_mtime_ns = None
            return None

        old_reader = self._reader
        self._reader = reader
        self._reader_mtime_ns = stat.st_mtime_ns
        self._cache.clear()
        if old_reader is not None:
            try:
                old_reader.close()
            except Exception:
                pass
        return reader

    @staticmethod
    def _country_from_record(record) -> str | None:
        if not isinstance(record, dict):
            return None
        for key in ('country', 'registered_country'):
            country = record.get(key)
            if isinstance(country, dict):
                code = country.get('iso_code')
                if isinstance(code, str) and len(code) == 2 and code.isascii() and code.isalpha():
                    return code.upper()
        return None

    def lookup(self, ip_address: str) -> str | None:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(ip_address)
            if cached and cached[0] > now:
                return cached[1]
            reader = self._get_reader()
            if reader is None:
                return None
            try:
                country = self._country_from_record(reader.get(ip_address))
            except Exception as exc:
                log.warning('GeoIP lookup failed for %s: %s', ip_address, exc)
                country = None
            if len(self._cache) >= self._cache_limit:
                self._cache.pop(next(iter(self._cache)))
            self._cache[ip_address] = (now + self._cache_ttl, country)
            return country

    def status(self) -> dict:
        try:
            stat = self.database_path.stat()
        except OSError:
            return {
                'provider': 'db-ip-lite',
                'available': False,
                'updated_at': None,
            }
        return {
            'provider': 'db-ip-lite',
            'available': stat.st_size > 0,
            'updated_at': int(stat.st_mtime),
        }


geoip_country_resolver = GeoIPCountryResolver()


async def evaluate_login_access(
    request,
    *,
    user=None,
    db=None,
) -> AccessRestrictionDecision:
    ip_address = get_request_client_ip(request)

    if getattr(user, 'role', None) == 'admin':
        return AccessRestrictionDecision(
            allowed=True,
            ip_address=ip_address,
            reason='admin_bypass',
            bypassed=True,
        )

    if not bool(await Config.get(ACCESS_RESTRICTIONS_ENABLED_KEY, False)):
        return AccessRestrictionDecision(allowed=True, ip_address=ip_address, reason='disabled')

    if not ip_address:
        return AccessRestrictionDecision(
            allowed=True,
            ip_address=None,
            reason='ip_unavailable',
        )

    ip_value = ipaddress.ip_address(ip_address)
    ip_rules = await AccessRestrictionIPRulesTable.list(enabled_only=True, db=db)
    for rule in ip_rules:
        try:
            if ip_value in ipaddress.ip_network(rule.network, strict=False):
                return AccessRestrictionDecision(
                    allowed=False,
                    ip_address=ip_address,
                    code=IP_BANNED,
                    result='blocked_ip',
                    reason='ip_blacklist',
                    rule_id=rule.id,
                )
        except ValueError:
            log.warning('Ignoring invalid stored IP restriction network %s', rule.network)

    country_code = await asyncio.to_thread(geoip_country_resolver.lookup, ip_address)
    if not country_code:
        return AccessRestrictionDecision(
            allowed=True,
            ip_address=ip_address,
            reason='country_unavailable',
        )

    region_rules = await AccessRestrictionRegionRulesTable.list(enabled_only=True, db=db)
    for rule in region_rules:
        if rule.country_code.upper() == country_code:
            return AccessRestrictionDecision(
                allowed=False,
                ip_address=ip_address,
                country_code=country_code,
                code=IP_RESTRICTED_REGION,
                result='blocked_region',
                reason='region_blacklist',
                rule_id=rule.id,
            )

    return AccessRestrictionDecision(
        allowed=True,
        ip_address=ip_address,
        country_code=country_code,
    )


async def record_login_event(
    request,
    *,
    user=None,
    email: str | None = None,
    auth_method: str,
    decision: AccessRestrictionDecision,
    result: str | None = None,
    db=None,
) -> None:
    user_email = getattr(user, 'email', None) or (str(email or '').strip().lower() or None)
    user_name = getattr(user, 'name', None)
    try:
        await LoginEventsTable.insert(
            user_id=getattr(user, 'id', None),
            user_email=user_email[:320] if user_email else None,
            user_name=str(user_name)[:255] if user_name else None,
            ip_address=decision.ip_address,
            country_code=decision.country_code,
            auth_method=str(auth_method or 'unknown')[:64],
            result=result or decision.result,
            reason=decision.reason,
            rule_id=decision.rule_id,
            user_agent=str(getattr(request, 'headers', {}).get('user-agent', ''))[:512] or None,
            db=db,
        )
    except Exception:
        # Login audit must not turn a valid authentication into an outage.
        log.exception('Unable to persist login history event')


async def enforce_login_access(
    request,
    *,
    user=None,
    email: str | None = None,
    auth_method: str,
    db=None,
) -> AccessRestrictionDecision:
    decision = await evaluate_login_access(request, user=user, db=db)
    if not decision.allowed:
        await record_login_event(
            request,
            user=user,
            email=email,
            auth_method=auth_method,
            decision=decision,
            db=db,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.code)
    return decision


async def cleanup_login_history() -> int:
    return await LoginEventsTable.purge()
