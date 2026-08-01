import pytest

from open_webui.utils.update_service import ArtiChatUpdateService
from open_webui.utils.update_state import UpdateStateStore


RELEASE = {
    "version": "0.1.2",
    "name": "ArtiChat 0.1.2",
    "body": "Release notes",
    "published_at": "2026-07-11T00:00:00Z",
    "html_url": "https://github.com/Artivis-Studio/ArtiChat/releases/tag/v0.1.2",
}


class FakeGitHubClient:
    def __init__(self, release=None, token="deploy-token"):
        self.release = release or RELEASE
        self.token = token
        self.latest_calls = 0
        self.dispatch_calls = []
        self.latest_error = None
        self.dispatch_error = None

    async def latest_release(self):
        self.latest_calls += 1
        if self.latest_error:
            raise self.latest_error
        return dict(self.release)

    async def dispatch(self, workflow, ref, version, operation_id):
        self.dispatch_calls.append((workflow, ref, version, operation_id))
        if self.dispatch_error:
            raise self.dispatch_error


def make_service(tmp_path, github, *, clock=None):
    return ArtiChatUpdateService(
        current_version="0.1.1",
        display_version="ArtiChat 0.1.1",
        build_hash="abc123",
        state_store=UpdateStateStore(tmp_path / "status.json"),
        github=github,
        workflow="artichat-deploy.yml",
        ref="main",
        clock=clock,
    )


@pytest.mark.asyncio
async def test_check_reports_available_release_and_deployment_capability(tmp_path):
    service = make_service(tmp_path, FakeGitHubClient())

    result = await service.check()

    assert result["current"] == "0.1.1"
    assert result["latest"] == "0.1.2"
    assert result["update_available"] is True
    assert result["deployment_enabled"] is True
    assert result["release"]["body"] == "Release notes"
    assert result["status"]["stage"] == "idle"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_deploy_rejects_target_other_than_latest_published_release(tmp_path):
    service = make_service(tmp_path, FakeGitHubClient())

    with pytest.raises(ValueError, match="latest published release"):
        await service.deploy("0.1.3")


@pytest.mark.asyncio
async def test_deploy_marks_state_failed_and_reraises_dispatch_error(tmp_path):
    github = FakeGitHubClient()
    github.dispatch_error = RuntimeError("dispatch unavailable")
    service = make_service(tmp_path, github)

    with pytest.raises(RuntimeError, match="dispatch unavailable"):
        await service.deploy("0.1.2")

    state = service.status()
    assert state["stage"] == "failed"
    assert state["active"] is False
    assert state["error"] == "dispatch unavailable"


@pytest.mark.asyncio
async def test_check_without_repository_does_not_call_external_service(tmp_path):
    service = make_service(tmp_path, None)

    result = await service.check()

    assert result["current"] == "0.1.1"
    assert result["latest"] == "0.1.1"
    assert result["update_available"] is False
    assert result["deployment_enabled"] is False
    assert result["release"] is None
    assert result["error"] is None


@pytest.mark.asyncio
async def test_check_release_failure_preserves_running_version(tmp_path):
    github = FakeGitHubClient()
    github.latest_error = RuntimeError("GitHub is unavailable")
    service = make_service(tmp_path, github)

    result = await service.check()

    assert result["current"] == "0.1.1"
    assert result["latest"] == "0.1.1"
    assert result["update_available"] is False
    assert result["deployment_enabled"] is True
    assert result["release"] is None
    assert result["error"] == "GitHub is unavailable"


@pytest.mark.asyncio
async def test_errors_are_redacted_before_return_or_state_persistence(tmp_path):
    token = "deploy-token"
    github = FakeGitHubClient(token=token)
    github.latest_error = RuntimeError(f"request failed with {token}")
    service = make_service(tmp_path, github)

    result = await service.check()

    assert token not in result["error"]

    github.latest_error = None
    github.dispatch_error = RuntimeError(f"dispatch failed with {token}")
    with pytest.raises(RuntimeError, match=token):
        await service.deploy("0.1.2")
    assert token not in service.status()["error"]


@pytest.mark.asyncio
async def test_check_caches_release_until_ttl_and_force_refreshes(tmp_path):
    now = [1000.0]
    github = FakeGitHubClient()
    service = make_service(tmp_path, github, clock=lambda: now[0])

    await service.check()
    await service.check()
    assert github.latest_calls == 1

    await service.check(force=True)
    assert github.latest_calls == 2

    now[0] += 301
    await service.check()
    assert github.latest_calls == 3


@pytest.mark.asyncio
async def test_successful_deploy_dispatches_and_returns_queued_state(tmp_path):
    github = FakeGitHubClient()
    service = make_service(tmp_path, github)

    state = await service.deploy("v0.1.2")

    assert state["stage"] == "queued"
    assert state["target_version"] == "0.1.2"
    assert github.dispatch_calls == [
        (
            "artichat-deploy.yml",
            "main",
            "0.1.2",
            state["operation_id"],
        )
    ]


@pytest.mark.asyncio
async def test_deploy_without_repository_is_rejected(tmp_path):
    service = make_service(tmp_path, None)

    with pytest.raises(ValueError, match="update repository is not configured"):
        await service.deploy("0.1.2")
