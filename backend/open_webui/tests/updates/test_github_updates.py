import json

import httpx
import pytest

from open_webui.utils.github_updates import GitHubUpdateClient, GitHubUpdateError


@pytest.mark.asyncio
async def test_latest_release_returns_normalized_stable_release():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/repos/Artivis-Studio/ArtiChat/releases/latest"
        return httpx.Response(
            200,
            json={
                "tag_name": "v0.1.2",
                "name": "ArtiChat 0.1.2",
                "body": "Release notes",
                "published_at": "2026-07-11T00:00:00Z",
                "html_url": "https://github.com/Artivis-Studio/ArtiChat/releases/tag/v0.1.2",
                "draft": False,
                "prerelease": False,
            },
        )

    client = GitHubUpdateClient(
        "Artivis-Studio/ArtiChat", transport=httpx.MockTransport(handler)
    )

    release = await client.latest_release()

    assert release["version"] == "0.1.2"
    assert release["body"] == "Release notes"
    assert release["name"] == "ArtiChat 0.1.2"


@pytest.mark.asyncio
async def test_dispatch_authenticates_and_sends_exact_payload_bytes():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith(
            "/actions/workflows/artichat-deploy.yml/dispatches"
        )
        assert request.headers["Authorization"] == "Bearer deploy-token"
        assert request.content == (
            b'{"ref":"main","inputs":{"version":"0.1.2",'
            b'"operation_id":"op-123"}}'
        )
        return httpx.Response(204)

    client = GitHubUpdateClient(
        "Artivis-Studio/ArtiChat",
        token="deploy-token",
        transport=httpx.MockTransport(handler),
    )

    await client.dispatch(
        "artichat-deploy.yml", "main", "v0.1.2", "op-123"
    )


@pytest.mark.asyncio
async def test_dispatch_without_token_is_rejected_before_request():
    client = GitHubUpdateClient("Artivis-Studio/ArtiChat")

    with pytest.raises(GitHubUpdateError, match="token is not configured"):
        await client.dispatch(
            "artichat-deploy.yml", "main", "0.1.2", "op-123"
        )


@pytest.mark.parametrize(
    "repository", ["Artivis-Studio", "owner/repo/extra", "owner/repo?token=x"]
)
def test_repository_must_be_a_valid_owner_and_name(repository):
    with pytest.raises(ValueError, match="invalid GitHub repository"):
        GitHubUpdateClient(repository)


@pytest.mark.asyncio
async def test_latest_release_rejects_unexpected_payload_without_leaking_it():
    secret = "should-not-appear"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[secret])

    client = GitHubUpdateClient(
        "Artivis-Studio/ArtiChat", transport=httpx.MockTransport(handler)
    )

    with pytest.raises(GitHubUpdateError) as caught:
        await client.latest_release()

    assert secret not in str(caught.value)


@pytest.mark.asyncio
async def test_latest_release_defaults_nullable_optional_metadata():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "tag_name": "v0.1.2",
                "name": None,
                "body": None,
                "published_at": None,
                "html_url": None,
            },
        )

    client = GitHubUpdateClient(
        "Artivis-Studio/ArtiChat", transport=httpx.MockTransport(handler)
    )

    release = await client.latest_release()

    assert release == {
        "version": "0.1.2",
        "name": "v0.1.2",
        "body": "",
        "published_at": "",
        "html_url": "",
    }
