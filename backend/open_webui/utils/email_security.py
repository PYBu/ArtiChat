from __future__ import annotations

import re


DOMAIN_LABEL = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')


def _normalize_domain(value: str) -> str | None:
    raw = str(value or '').strip().lower().rstrip('.')
    if not raw or raw.startswith('.') or '@' in raw or any(char.isspace() for char in raw):
        return None
    try:
        domain = raw.encode('idna').decode('ascii')
    except UnicodeError:
        return None
    labels = domain.split('.')
    if len(labels) < 2 or any(not DOMAIN_LABEL.fullmatch(label) for label in labels):
        return None
    return domain


def normalize_allowed_domains(value: list[str] | str | None) -> list[str]:
    if isinstance(value, str):
        candidates = re.split(r'[,\n\r]+', value)
    else:
        candidates = value or []
    normalized = {_normalize_domain(item) for item in candidates}
    normalized.discard(None)
    return sorted(normalized)


def is_registration_email_allowed(email: str, domains: list[str] | str | None, *, allow_subdomains: bool) -> bool:
    raw = str(email or '').strip()
    if raw.count('@') != 1:
        return False
    local_part, domain_part = raw.rsplit('@', 1)
    if not local_part or any(char.isspace() for char in local_part):
        return False
    domain = _normalize_domain(domain_part)
    if domain is None:
        return False

    allowed = normalize_allowed_domains(domains)
    if not allowed:
        return True
    if domain in allowed:
        return True
    return allow_subdomains and any(domain.endswith(f'.{allowed_domain}') for allowed_domain in allowed)
