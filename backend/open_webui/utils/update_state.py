from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


ACTIVE_UPDATE_STAGES = {
    "queued",
    "preparing",
    "pulling",
    "backing_up",
    "restarting",
    "verifying",
}


class UpdateInProgressError(RuntimeError):
    pass


class UpdateStateStore:
    def __init__(self, path: Path, stale_after_seconds: int = 1800):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(".lock")
        self.stale_after_seconds = stale_after_seconds

    def read(self) -> dict:
        if not self.path.exists():
            return {"stage": "idle", "active": False, "updated_at": 0}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "stage": "failed",
                "active": False,
                "error": "Update state is unreadable",
                "updated_at": 0,
            }
        age = time.time() - int(state.get("updated_at") or 0)
        if (
            state.get("stage") in ACTIVE_UPDATE_STAGES
            and age > self.stale_after_seconds
        ):
            return self.write(
                {
                    **state,
                    "stage": "failed",
                    "active": False,
                    "error": "Deployment status timed out",
                }
            )
        return state

    def write(self, state: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = {**state, "updated_at": int(time.time())}
        temporary = self.path.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.path)
        return state

    @contextmanager
    def request_lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if (
            self.lock_path.exists()
            and time.time() - self.lock_path.stat().st_mtime
            > self.stale_after_seconds
        ):
            self.lock_path.unlink(missing_ok=True)
        try:
            descriptor = os.open(
                self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
        except FileExistsError as exc:
            raise UpdateInProgressError(
                "another update request is being processed"
            ) from exc
        os.close(descriptor)
        try:
            yield
        finally:
            self.lock_path.unlink(missing_ok=True)

    def begin(self, target_version: str) -> dict:
        with self.request_lock():
            current = self.read()
            fresh = (
                time.time() - int(current.get("updated_at") or 0)
                <= self.stale_after_seconds
            )
            if current.get("stage") in ACTIVE_UPDATE_STAGES and fresh:
                raise UpdateInProgressError("an update is already in progress")
            return self.write(
                {
                    "operation_id": uuid4().hex,
                    "target_version": target_version,
                    "previous_version": None,
                    "stage": "queued",
                    "active": True,
                    "message": "Deployment queued",
                    "error": None,
                }
            )

    def fail(self, operation_id: str, message: str) -> dict:
        current = self.read()
        if current.get("operation_id") != operation_id:
            return current
        return self.write(
            {
                **current,
                "stage": "failed",
                "active": False,
                "error": message,
                "message": "Deployment failed",
            }
        )
