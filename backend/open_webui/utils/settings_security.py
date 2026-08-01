from __future__ import annotations

from copy import deepcopy
from typing import Any


def sanitize_user_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Remove browser-owned secrets before settings reach durable storage."""
    sanitized = deepcopy(settings)
    ui = sanitized.get('ui')
    if isinstance(ui, dict):
        ui.pop('directConnections', None)
    return sanitized
