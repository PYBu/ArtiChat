import importlib
import sys
import types

import pytest
from fastapi import HTTPException

from open_webui.utils.github_updates import GitHubUpdateError
from open_webui.utils.update_state import UpdateInProgressError


class FakeUpdateService:
    def __init__(self):
        self.force = None
        self.status_value = {"stage": "idle", "active": False, "updated_at": 0}
        self.deploy_result = {"stage": "queued", "active": True}
        self.deploy_error = None
        self.target_version = None

    async def check(self, force=False):
        self.force = force
        return {"force": force}

    def status(self):
        return self.status_value

    async def deploy(self, target_version):
        self.target_version = target_version
        if self.deploy_error:
            raise self.deploy_error
        return self.deploy_result


@pytest.fixture
def updates_module(monkeypatch):
    auth_module = types.ModuleType("open_webui.utils.auth")

    async def get_admin_user():
        return None

    auth_module.get_admin_user = get_admin_user
    monkeypatch.setitem(sys.modules, "open_webui.utils.auth", auth_module)
    sys.modules.pop("open_webui.routers.updates", None)
    module = importlib.import_module("open_webui.routers.updates")
    yield module, get_admin_user
    sys.modules.pop("open_webui.routers.updates", None)


def test_update_router_exposes_only_expected_paths(updates_module):
    updates, _ = updates_module
    paths = {
        (route.path, method)
        for route in updates.router.routes
        for method in route.methods
    }
    assert paths == {
        ("/check", "GET"),
        ("/status", "GET"),
        ("/deploy", "POST"),
    }


def test_all_update_routes_require_admin_dependency(updates_module):
    updates, get_admin_user = updates_module
    for route in updates.router.routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_admin_user in dependency_calls


def test_get_update_service_stays_offline_without_repository(
    updates_module, monkeypatch, tmp_path
):
    updates, _ = updates_module
    monkeypatch.setattr(updates, "ARTICHAT_UPDATE_REPOSITORY", "")
    monkeypatch.setattr(updates, "ARTICHAT_UPDATE_STATE_PATH", tmp_path / "status.json")
    updates._update_service = None

    service = updates.get_update_service()

    assert service.github is None
    assert service.current_version == updates.VERSION
    assert service.display_version == f"{updates.VERSION} (Artivis Alpha)"
    updates._update_service = None


@pytest.mark.asyncio
async def test_check_for_updates_forwards_force(updates_module):
    updates, _ = updates_module
    service = FakeUpdateService()

    result = await updates.check_for_updates(force=True, user=object(), service=service)

    assert result == {"force": True}
    assert service.force is True


@pytest.mark.asyncio
async def test_get_update_status_returns_persisted_state(updates_module):
    updates, _ = updates_module
    service = FakeUpdateService()

    result = await updates.get_update_status(user=object(), service=service)

    assert result is service.status_value


@pytest.mark.asyncio
async def test_deploy_update_returns_accepted_state(updates_module):
    updates, _ = updates_module
    service = FakeUpdateService()
    form = updates.DeployUpdateForm(target_version="0.1.2")

    result = await updates.deploy_update(form, user=object(), service=service)

    assert result is service.deploy_result
    assert service.target_version == "0.1.2"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ValueError("invalid target"), 400),
        (UpdateInProgressError("already running"), 409),
        (GitHubUpdateError("dispatch failed"), 502),
    ],
)
async def test_deploy_update_maps_domain_errors(updates_module, error, status_code):
    updates, _ = updates_module
    service = FakeUpdateService()
    service.deploy_error = error
    form = updates.DeployUpdateForm(target_version="0.1.2")

    with pytest.raises(HTTPException) as caught:
        await updates.deploy_update(form, user=object(), service=service)

    assert caught.value.status_code == status_code
    assert caught.value.detail == str(error)
