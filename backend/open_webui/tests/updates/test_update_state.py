import json
import threading

import pytest

import open_webui.utils.update_state as update_state
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


def test_read_reports_non_object_json_as_unreadable(tmp_path):
    path = tmp_path / "status.json"
    path.write_text("[]", encoding="utf-8")

    state = UpdateStateStore(path).read()

    assert state == {
        "stage": "failed",
        "active": False,
        "error": "Update state is unreadable",
        "updated_at": 0,
    }


def test_read_reports_non_integer_updated_at_as_unreadable(tmp_path):
    path = tmp_path / "status.json"
    path.write_text(
        json.dumps({"stage": "queued", "active": True, "updated_at": "yesterday"}),
        encoding="utf-8",
    )

    state = UpdateStateStore(path).read()

    assert state == {
        "stage": "failed",
        "active": False,
        "error": "Update state is unreadable",
        "updated_at": 0,
    }


def test_fail_cannot_overwrite_a_newer_operation(tmp_path, monkeypatch):
    store = UpdateStateStore(tmp_path / "status.json")
    old_state = store.begin("0.1.2")
    fail_at_replace = threading.Event()
    release_fail = threading.Event()
    writer_started = threading.Event()
    writer_finished = threading.Event()
    errors = []
    real_replace = update_state.os.replace

    def controlled_replace(source, destination):
        pending = json.loads(source.read_text(encoding="utf-8"))
        if (
            threading.current_thread().name == "fail-old-operation"
            and pending.get("operation_id") == old_state["operation_id"]
            and pending.get("stage") == "failed"
        ):
            fail_at_replace.set()
            if not release_fail.wait(timeout=5):
                raise TimeoutError("test did not release the failed write")
        real_replace(source, destination)

    monkeypatch.setattr(update_state.os, "replace", controlled_replace)

    def fail_old_operation():
        try:
            store.fail(old_state["operation_id"], "old dispatch failed")
        except BaseException as exc:
            errors.append(exc)

    new_state = {
        "operation_id": "new-operation",
        "target_version": "0.1.3",
        "previous_version": "0.1.2",
        "stage": "queued",
        "active": True,
        "message": "Deployment queued",
        "error": None,
    }

    def write_new_operation():
        writer_started.set()
        try:
            store.write(new_state)
        except BaseException as exc:
            errors.append(exc)
        finally:
            writer_finished.set()

    fail_thread = threading.Thread(
        target=fail_old_operation, name="fail-old-operation"
    )
    fail_thread.start()
    assert fail_at_replace.wait(timeout=5)

    writer_thread = threading.Thread(target=write_new_operation)
    writer_thread.start()
    assert writer_started.wait(timeout=5)
    assert writer_finished.wait(timeout=5)
    release_fail.set()

    fail_thread.join(timeout=5)
    writer_thread.join(timeout=5)
    assert not fail_thread.is_alive()
    assert not writer_thread.is_alive()
    final_state = store.read()
    if errors:
        assert len(errors) == 1
        assert isinstance(errors[0], UpdateInProgressError)
        assert final_state["operation_id"] == old_state["operation_id"]
        assert final_state["stage"] == "failed"
    else:
        assert final_state["operation_id"] == "new-operation"


def test_request_lock_prevents_a_second_holder_from_entering(tmp_path):
    store = UpdateStateStore(tmp_path / "status.json")
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    second_rejected = threading.Event()

    def hold_first_lock():
        with store.request_lock():
            first_entered.set()
            release_first.wait(timeout=5)

    def try_second_lock():
        try:
            with store.request_lock():
                second_entered.set()
        except UpdateInProgressError:
            second_rejected.set()

    first_thread = threading.Thread(target=hold_first_lock)
    first_thread.start()
    assert first_entered.wait(timeout=5)

    second_thread = threading.Thread(target=try_second_lock)
    second_thread.start()
    second_thread.join(timeout=5)

    assert not second_thread.is_alive()
    assert not second_entered.is_set()
    assert second_rejected.is_set()

    release_first.set()
    first_thread.join(timeout=5)
    assert not first_thread.is_alive()


def test_replace_failure_preserves_old_state_and_removes_temporary_file(
    tmp_path, monkeypatch
):
    path = tmp_path / "status.json"
    store = UpdateStateStore(path)
    old_state = store.write({"stage": "idle", "active": False})

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(update_state.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        store.write({"stage": "queued", "active": True})

    assert json.loads(path.read_text(encoding="utf-8")) == old_state
    assert list(tmp_path.glob("status.*.tmp")) == []
