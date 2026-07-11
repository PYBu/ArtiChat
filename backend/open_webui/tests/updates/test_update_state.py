import json

import pytest

from open_webui.utils.update_state import (
    ACTIVE_UPDATE_STAGES,
    UpdateInProgressError,
    UpdateStateStore,
)


def test_begin_writes_atomic_queued_state(tmp_path):
    store = UpdateStateStore(
        tmp_path / "update-state" / "status.json", stale_after_seconds=1800
    )
    state = store.begin("0.1.2")
    on_disk = json.loads((tmp_path / "update-state" / "status.json").read_text())
    assert state["operation_id"] == on_disk["operation_id"]
    assert state["target_version"] == "0.1.2"
    assert state["stage"] == "queued"
    assert state["active"] is True
    assert "token" not in json.dumps(on_disk).lower()


def test_begin_rejects_a_fresh_active_operation(tmp_path):
    store = UpdateStateStore(tmp_path / "status.json", stale_after_seconds=1800)
    store.begin("0.1.2")
    with pytest.raises(UpdateInProgressError):
        store.begin("0.1.3")


def test_dispatch_failure_releases_operation(tmp_path):
    store = UpdateStateStore(tmp_path / "status.json", stale_after_seconds=1800)
    state = store.begin("0.1.2")
    failed = store.fail(state["operation_id"], "GitHub dispatch failed")
    assert failed["active"] is False
    assert failed["stage"] == "failed"


def test_stale_active_operation_is_reported_as_failed(tmp_path, monkeypatch):
    store = UpdateStateStore(tmp_path / "status.json", stale_after_seconds=30)
    state = store.begin("0.1.2")
    monkeypatch.setattr(
        "open_webui.utils.update_state.time.time", lambda: state["updated_at"] + 31
    )
    assert store.read()["stage"] == "failed"
    assert store.read()["active"] is False


def test_active_stage_contract_is_stable():
    assert ACTIVE_UPDATE_STAGES == {
        "queued",
        "preparing",
        "pulling",
        "backing_up",
        "restarting",
        "verifying",
    }
