from __future__ import annotations

import re

import httpx

from open_webui.utils.update_versions import normalize_version


GITHUB_API_URL = "https://api.github.com"
GITHUB_REPOSITORY_PATTERN = re.compile(
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
)
GITHUB_WORKFLOW_PATTERN = re.compile(r"[A-Za-z0-9_.-]+\.ya?ml")


class GitHubUpdateError(RuntimeError):
    pass


class GitHubUpdateClient:
    def __init__(
        self,
        repository: str,
        token: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 15,
    ):
        if not isinstance(repository, str) or not GITHUB_REPOSITORY_PATTERN.fullmatch(
            repository
        ):
            raise ValueError("invalid GitHub repository")
        self.repository = repository
        self.token = token
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def _headers(self, authenticated: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if authenticated:
            if not self.token:
                raise GitHubUpdateError(
                    "GitHub deployment token is not configured"
                )
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def latest_release(self) -> dict[str, str]:
        url = f"{GITHUB_API_URL}/repos/{self.repository}/releases/latest"
        async with httpx.AsyncClient(
            transport=self.transport, timeout=self.timeout_seconds
        ) as client:
            response = await client.get(url, headers=self._headers())

        if response.status_code != 200:
            raise GitHubUpdateError(
                f"GitHub release request failed with status {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GitHubUpdateError("GitHub release response is invalid") from exc
        if not isinstance(payload, dict):
            raise GitHubUpdateError("GitHub release response is invalid")
        if payload.get("draft") or payload.get("prerelease"):
            raise GitHubUpdateError(
                "latest GitHub release is not a stable published release"
            )

        tag_name = payload.get("tag_name")
        if not isinstance(tag_name, str):
            raise GitHubUpdateError("GitHub release response is invalid")
        try:
            version = normalize_version(tag_name)
        except ValueError as exc:
            raise GitHubUpdateError("GitHub release response is invalid") from exc

        return {
            "version": version,
            "name": str(payload.get("name") or tag_name),
            "body": str(payload.get("body") or ""),
            "published_at": str(payload.get("published_at") or ""),
            "html_url": str(payload.get("html_url") or ""),
        }

    async def dispatch(
        self,
        workflow: str,
        ref: str,
        version: str,
        operation_id: str,
    ) -> None:
        if not isinstance(workflow, str) or not GITHUB_WORKFLOW_PATTERN.fullmatch(
            workflow
        ):
            raise ValueError("invalid deployment workflow")
        headers = self._headers(authenticated=True)
        payload = {
            "ref": ref,
            "inputs": {
                "version": normalize_version(version),
                "operation_id": operation_id,
            },
        }
        url = (
            f"{GITHUB_API_URL}/repos/{self.repository}/actions/workflows/"
            f"{workflow}/dispatches"
        )
        async with httpx.AsyncClient(
            transport=self.transport, timeout=self.timeout_seconds
        ) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code != 204:
            raise GitHubUpdateError(
                f"GitHub workflow dispatch failed with status {response.status_code}"
            )
