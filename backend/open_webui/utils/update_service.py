from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from open_webui.utils.update_state import UpdateStateStore
from open_webui.utils.update_versions import normalize_version, version_is_newer


class ArtiChatUpdateService:
    def __init__(
        self,
        current_version: str,
        display_version: str,
        build_hash: str,
        state_store: UpdateStateStore,
        github: Any | None,
        workflow: str,
        ref: str,
        cache_ttl_seconds: float = 300,
        clock: Callable[[], float] | None = None,
    ):
        self.current_version = normalize_version(current_version)
        self.display_version = display_version
        self.build_hash = build_hash
        self.state_store = state_store
        self.github = github
        self.workflow = workflow
        self.ref = ref
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock or time.monotonic
        self._cached_release: dict | None = None
        self._cached_at: float | None = None

    def _safe_error(self, error: Exception) -> str:
        message = str(error)
        token = str(getattr(self.github, "token", "") or "")
        return message.replace(token, "[redacted]") if token else message

    async def _get_release(self, force: bool = False) -> dict | None:
        if self.github is None:
            return None

        now = self.clock()
        cache_is_fresh = (
            self._cached_release is not None
            and self._cached_at is not None
            and now - self._cached_at < self.cache_ttl_seconds
        )
        if force or not cache_is_fresh:
            release = await self.github.latest_release()
            self._cached_release = dict(release)
            self._cached_at = now
        return dict(self._cached_release)

    async def check(self, force: bool = False) -> dict:
        result = {
            "current": self.current_version,
            "latest": self.current_version,
            "display_version": self.display_version,
            "build_hash": self.build_hash,
            "update_available": False,
            "deployment_enabled": bool(
                self.github is not None and getattr(self.github, "token", "")
            ),
            "release": None,
            "status": self.status(),
            "error": None,
        }
        if self.github is None:
            return result

        try:
            release = await self._get_release(force=force)
            latest = normalize_version(release["version"])
        except Exception as exc:
            result["error"] = self._safe_error(exc)
            return result

        result.update(
            {
                "latest": latest,
                "update_available": version_is_newer(
                    latest, self.current_version
                ),
                "release": release,
            }
        )
        return result

    def status(self) -> dict:
        return self.state_store.read()

    async def deploy(self, target_version: str) -> dict:
        if self.github is None:
            raise ValueError("update repository is not configured")

        target = normalize_version(target_version)
        release = await self._get_release(force=True)
        latest = normalize_version(release["version"])
        if target != latest:
            raise ValueError(
                "target version is not the latest published release"
            )
        if not version_is_newer(target, self.current_version):
            raise ValueError(
                "target version must be newer than the running version"
            )

        state = self.state_store.begin(target)
        operation_id = state["operation_id"]
        try:
            await self.github.dispatch(
                self.workflow, self.ref, target, operation_id
            )
        except Exception as exc:
            self.state_store.fail(operation_id, self._safe_error(exc))
            raise
        return state
