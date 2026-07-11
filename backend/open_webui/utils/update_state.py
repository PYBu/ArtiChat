from __future__ import annotations

import errno
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

if os.name == "nt":
    import msvcrt
else:
    import fcntl


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
        state = self._read_unlocked()
        if not self._is_stale_active(state):
            return state

        try:
            with self.request_lock():
                current = self._read_unlocked()
                if self._is_stale_active(current):
                    return self._write_unlocked(
                        {
                            **current,
                            "stage": "failed",
                            "active": False,
                            "error": "Deployment status timed out",
                        }
                    )
                return current
        except UpdateInProgressError:
            return self._read_unlocked()

    def _read_unlocked(self) -> dict:
        if not self.path.exists():
            return {"stage": "idle", "active": False, "updated_at": 0}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                raise TypeError("update state must be a JSON object")

            raw_updated_at = state.get("updated_at", 0)
            if isinstance(raw_updated_at, bool):
                raise TypeError("updated_at must be an integer")
            updated_at = int(raw_updated_at)
            if isinstance(raw_updated_at, float) and raw_updated_at != updated_at:
                raise ValueError("updated_at must be an integer")

            stage = state.get("stage")
            if stage is not None and not isinstance(stage, str):
                raise TypeError("stage must be a string")
            active = state.get("active")
            if active is not None and not isinstance(active, bool):
                raise TypeError("active must be a boolean")
        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            AttributeError,
        ):
            return {
                "stage": "failed",
                "active": False,
                "error": "Update state is unreadable",
                "updated_at": 0,
            }
        return {**state, "updated_at": updated_at}

    def _is_stale_active(self, state: dict) -> bool:
        age = time.time() - state["updated_at"]
        return (
            state.get("stage") in ACTIVE_UPDATE_STAGES
            and age > self.stale_after_seconds
        )

    def write(self, state: dict) -> dict:
        with self.request_lock():
            return self._write_unlocked(state)

    def _write_unlocked(self, state: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = {**state, "updated_at": int(time.time())}
        temporary = self.path.with_suffix(f".{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return state

    @contextmanager
    def request_lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.lock_path.open("a+b")
        try:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)

            try:
                if os.name == "nt":
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                raise UpdateInProgressError(
                    "another update request is being processed"
                ) from exc

            try:
                yield
            finally:
                lock_file.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()

    def begin(self, target_version: str) -> dict:
        with self.request_lock():
            current = self._read_unlocked()
            fresh = (
                time.time() - int(current.get("updated_at") or 0)
                <= self.stale_after_seconds
            )
            if current.get("stage") in ACTIVE_UPDATE_STAGES and fresh:
                raise UpdateInProgressError("an update is already in progress")
            return self._write_unlocked(
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
        with self.request_lock():
            current = self._read_unlocked()
            if current.get("operation_id") != operation_id:
                return current
            return self._write_unlocked(
                {
                    **current,
                    "stage": "failed",
                    "active": False,
                    "error": message,
                    "message": "Deployment failed",
                }
            )
