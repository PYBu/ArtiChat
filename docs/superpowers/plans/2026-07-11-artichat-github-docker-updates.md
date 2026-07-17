# ArtiChat GitHub Docker Update System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish tested ArtiChat Docker releases to GitHub/GHCR and let an administrator deploy a selected release from ArtiChat with persistent data, health checks, and automatic rollback.

**Architecture:** A tag-driven GitHub Actions workflow builds immutable GHCR images and publishes release metadata. A small backend update service reads the public release, persists deployment state, and dispatches a second GitHub workflow; that workflow connects through a restricted SSH key to a fixed host script that pulls the image, backs up `/data/artichat-prod/data`, recreates only ArtiChat, verifies health/version, and rolls back on failure.

**Tech Stack:** Python 3.11, FastAPI, httpx, pytest, SvelteKit, TypeScript, Vitest, Docker Compose, Bash, GitHub Actions, GHCR, PowerShell/GitHub CLI for the one-time public repository bootstrap.

---

## Scope And Existing State

- Work in `C:\Users\admin\Desktop\Pro\ArtiChat\.worktrees\artichat-brand-whitelabel` until the clean public branch is created.
- Production currently reports version `0.1.1` from `http://18.234.239.56:13000/api/version`.
- Preserve the uncommitted `0.1.1 (Artivis Alpha)` and About-page work; Task 1 cleans and commits it before update-system code begins.
- Never commit `.env`, GitHub tokens, SSH private keys, Docker data, or deployment backups.
- Never run a Docker cleanup command with `--volumes`.
- The public repository is named `ArtiChat`; workflows derive its owner from `github.repository`, so committed files contain no account-name placeholder.

## File Structure

### Version Baseline

- Modify `package.json`, `package-lock.json`: preserve the current `0.1.1` baseline and add update-system guard scripts later.
- Modify `Dockerfile`: expose the release build hash through the backend variable actually read by `env.py`.
- Modify `src/lib/constants.ts`: keep semantic and display versions separate without hardcoding the semantic version twice.
- Modify `src/lib/components/ChangelogModal.svelte`: show the branded display version.
- Modify `src/lib/components/chat/Settings/About.svelte`: retain the new product copy while removing disabled update code and unused imports.
- Modify `scripts/check-release-version.mjs`: derive the expected version from package metadata and optionally validate a release tag.

### Backend Update Domain

- Create `backend/open_webui/utils/update_versions.py`: strict semantic-version normalization and comparison.
- Create `backend/open_webui/utils/update_state.py`: atomic JSON deployment state and request mutual exclusion.
- Create `backend/open_webui/utils/github_updates.py`: GitHub Releases and workflow-dispatch HTTP client.
- Create `backend/open_webui/utils/update_service.py`: release caching, eligibility checks, dispatch orchestration, and response construction.
- Create `backend/open_webui/routers/updates.py`: admin-only update endpoints.
- Modify `backend/open_webui/env.py`: update repository, workflow, token, ref, state path, cache TTL, and stale-operation settings.
- Modify `backend/open_webui/main.py`: mount the router, enrich `/api/version`, and remove the inert upstream-compatible update stub.
- Create `backend/open_webui/tests/updates/*`: focused unit and router contract tests.

### Frontend Update Surface

- Create `src/lib/apis/updates/index.ts`: typed update API client.
- Create `src/lib/utils/updates.ts`: pure status and polling helpers.
- Create `src/lib/utils/updates.test.ts`: Vitest coverage for helper behavior.
- Create `src/lib/components/admin/Settings/VersionUpdatePanel.svelte`: version, release notes, confirmation, deployment, and polling UI.
- Modify `src/lib/components/admin/Settings/General.svelte`: replace the legacy version block with the focused panel.
- Modify `src/routes/(app)/+layout.svelte` and `src/lib/components/layout/UpdateInfoToast.svelte`: use the ArtiChat update response for the admin toast.
- Modify `src/lib/i18n/locales/en-US/translation.json` and `src/lib/i18n/locales/zh-CN/translation.json`: add update UI strings.

### Release And Deployment

- Create `deploy/aws-1panel/artichat-deploy.sh`: fixed-scope deploy/backup/health/rollback script.
- Create `deploy/aws-1panel/artichat-deploy-ssh.sh`: strict forced-command wrapper.
- Create `deploy/aws-1panel/install-update-runner.sh`: one-time host installer for scripts, sudoers, state directories, and restricted SSH key.
- Create `deploy/aws-1panel/tests/test-artichat-deploy.sh`: fake-Docker success and rollback tests.
- Modify `deploy/aws-1panel/docker-compose.artichat-prod.yaml`: immutable image variable and update-state mount/config.
- Modify `deploy/aws-1panel/README.zh-CN.md`: bootstrap, normal update, backup, and emergency recovery commands.
- Create `.github/workflows/artichat-release.yml`: tag validation, tests, image build/push, and release publication.
- Create `.github/workflows/artichat-deploy.yml`: validated manual dispatch and restricted SSH deployment.
- Delete `.github/workflows/docker.yaml`, `.github/workflows/release.yml`, `.github/workflows/release-pypi.yml`: remove upstream publication behavior.
- Create `scripts/check-update-system.mjs`: source/workflow safety contract.
- Create `scripts/export-public-repo.ps1`: clean public snapshot with secret scan and fresh history.
- Modify `.gitattributes`, `.gitignore`, `.env.example`, `package.json`: export exclusions, local secret exclusions, documented configuration, and guard commands.
- Create `docs/releases/0.1.2.md`: human-written first updater release notes.

---

### Task 1: Stabilize And Commit The 0.1.1 Release Baseline

**Files:**
- Modify: `Dockerfile`
- Modify: `scripts/check-release-version.mjs`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `src/lib/constants.ts`
- Modify: `src/lib/components/ChangelogModal.svelte`
- Modify: `src/lib/components/chat/Settings/About.svelte`
- Verify: `backend/open_webui/main.py`

- [ ] **Step 1: Turn the release guard into a forward-compatible failing check**

Replace the hardcoded version declarations in `scripts/check-release-version.mjs` with package-derived values and require a dynamic frontend display version:

```js
const packageJson = JSON.parse(read('package.json'));
const expectedVersion = packageJson.version;
const expectedDisplayVersion = `${expectedVersion} (Artivis Alpha)`;
const requestedTag = process.argv.find((value) => value.startsWith('--tag='))?.slice('--tag='.length);

if (requestedTag && requestedTag.replace(/^v/, '') !== expectedVersion) {
	failures.push(`release tag ${requestedTag} does not match package version ${expectedVersion}`);
}

const constants = read('src/lib/constants.ts');
if (!constants.includes('export const WEBUI_VERSION = APP_VERSION;')) {
	failures.push('WEBUI_VERSION must remain the semantic APP_VERSION value');
}
if (!constants.includes('export const WEBUI_DISPLAY_VERSION = `${WEBUI_VERSION} (Artivis Alpha)`;')) {
	failures.push('WEBUI_DISPLAY_VERSION must derive from WEBUI_VERSION');
}
```

Keep the existing package-lock, About, changelog-modal, and backend changelog checks.
Add this build-hash contract:

```js
const dockerfile = read('Dockerfile');
if (!dockerfile.includes('ENV WEBUI_BUILD_HASH=${BUILD_HASH}')) {
	failures.push('Docker image must expose BUILD_HASH as WEBUI_BUILD_HASH');
}
if (dockerfile.includes('ENV WEBUI_BUILD_VERSION=${BUILD_HASH}')) {
	failures.push('Docker image still uses the unread WEBUI_BUILD_VERSION variable');
}
```

- [ ] **Step 2: Run the guard and verify the new assertion fails**

Run:

```powershell
npm run test:release-version
```

Expected: `FAIL` with both the dynamic display-version assertion and the backend build-hash assertion.

- [ ] **Step 3: Make the display version dynamic and clean the About component**

In `src/lib/constants.ts` use:

```ts
export const WEBUI_VERSION = APP_VERSION;
export const WEBUI_DISPLAY_VERSION = `${WEBUI_VERSION} (Artivis Alpha)`;
export const WEBUI_BUILD_HASH = APP_BUILD_HASH;
```

In `About.svelte`, remove `getVersionUpdates`, `WEBUI_VERSION`, `compareVersion`, `updateAvailable`, `version`, `checkForVersionUpdates`, both commented update blocks, and the version-check branch in `onMount`. Preserve Ollama loading, `WEBUI_DISPLAY_VERSION`, the ArtiChat/MineAPI copy, and the Artivis copyright. Correct the opening sentence to:

```svelte
<div class="text-xs text-gray-500 dark:text-gray-400">
	ArtiChat 是一个 AI 多模型聚合平台，主要为用户提供 AI 模型对话服务。
</div>
```

In the final Docker stage replace:

```dockerfile
ENV WEBUI_BUILD_VERSION=${BUILD_HASH}
```

with:

```dockerfile
ENV WEBUI_BUILD_HASH=${BUILD_HASH}
```

- [ ] **Step 4: Verify package metadata and changelog display**

Confirm these exact invariants:

```text
package.json version: 0.1.1
package-lock.json root version: 0.1.1
package-lock.json packages[""] version: 0.1.1
backend changelog key: f'{VERSION} (Artivis Alpha)'
ChangelogModal renders WEBUI_DISPLAY_VERSION
```

- [ ] **Step 5: Run focused and build verification**

Run:

```powershell
npm run test:release-version
npm run test:branding
npm run build
```

Expected: both guards pass and Vite completes the production build. Existing non-fatal Svelte/Vite warnings may remain.

- [ ] **Step 6: Commit only the baseline files**

```powershell
git add Dockerfile package.json package-lock.json scripts/check-release-version.mjs src/lib/constants.ts src/lib/components/ChangelogModal.svelte src/lib/components/chat/Settings/About.svelte
git commit -m "chore: establish ArtiChat 0.1.1 release baseline"
```

### Task 2: Add Semantic Version And Deployment State Primitives

**Files:**
- Create: `backend/open_webui/utils/update_versions.py`
- Create: `backend/open_webui/utils/update_state.py`
- Create: `backend/open_webui/tests/updates/conftest.py`
- Create: `backend/open_webui/tests/updates/test_update_versions.py`
- Create: `backend/open_webui/tests/updates/test_update_state.py`

- [ ] **Step 1: Write failing semantic-version tests**

Create `test_update_versions.py`:

```py
import pytest

from open_webui.utils.update_versions import normalize_version, version_is_newer


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [('v0.1.2', '0.1.2'), ('0.1.2', '0.1.2'), (' 1.20.3 ', '1.20.3')],
)
def test_normalize_version_accepts_three_part_versions(raw, expected):
    assert normalize_version(raw) == expected


@pytest.mark.parametrize('raw', ['', 'latest', '1.2', '1.2.3-beta', '1.2.3;rm -rf /'])
def test_normalize_version_rejects_non_release_values(raw):
    with pytest.raises(ValueError, match='invalid release version'):
        normalize_version(raw)


def test_version_is_newer_compares_numerically():
    assert version_is_newer('0.1.10', '0.1.2') is True
    assert version_is_newer('0.1.2', '0.1.2') is False
    assert version_is_newer('0.1.1', '0.1.2') is False
```

- [ ] **Step 2: Write failing atomic-state tests**

Create `test_update_state.py` with the shared schema:

```py
import json

import pytest

from open_webui.utils.update_state import ACTIVE_UPDATE_STAGES, UpdateInProgressError, UpdateStateStore


def test_begin_writes_atomic_queued_state(tmp_path):
    store = UpdateStateStore(tmp_path / 'update-state' / 'status.json', stale_after_seconds=1800)
    state = store.begin('0.1.2')
    on_disk = json.loads((tmp_path / 'update-state' / 'status.json').read_text())

    assert state['operation_id'] == on_disk['operation_id']
    assert state['target_version'] == '0.1.2'
    assert state['stage'] == 'queued'
    assert state['active'] is True
    assert 'token' not in json.dumps(on_disk).lower()


def test_begin_rejects_a_fresh_active_operation(tmp_path):
    store = UpdateStateStore(tmp_path / 'status.json', stale_after_seconds=1800)
    store.begin('0.1.2')
    with pytest.raises(UpdateInProgressError):
        store.begin('0.1.3')


def test_dispatch_failure_releases_operation(tmp_path):
    store = UpdateStateStore(tmp_path / 'status.json', stale_after_seconds=1800)
    state = store.begin('0.1.2')
    failed = store.fail(state['operation_id'], 'GitHub dispatch failed')
    assert failed['active'] is False
    assert failed['stage'] == 'failed'


def test_stale_active_operation_is_reported_as_failed(tmp_path, monkeypatch):
    store = UpdateStateStore(tmp_path / 'status.json', stale_after_seconds=30)
    state = store.begin('0.1.2')
    monkeypatch.setattr('open_webui.utils.update_state.time.time', lambda: state['updated_at'] + 31)
    assert store.read()['stage'] == 'failed'
    assert store.read()['active'] is False


def test_active_stage_contract_is_stable():
    assert ACTIVE_UPDATE_STAGES == {'queued', 'preparing', 'pulling', 'backing_up', 'restarting', 'verifying'}
```

- [ ] **Step 3: Run tests to verify missing modules fail**

Run:

```powershell
pytest backend/open_webui/tests/updates/test_update_versions.py backend/open_webui/tests/updates/test_update_state.py -q
```

Expected: collection errors for missing `update_versions` and `update_state`.

- [ ] **Step 4: Implement strict version helpers**

Create `update_versions.py`:

```py
import re

RELEASE_VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+$')


def normalize_version(value: str) -> str:
    normalized = str(value or '').strip()
    if normalized.startswith('v'):
        normalized = normalized[1:]
    if not RELEASE_VERSION_PATTERN.fullmatch(normalized):
        raise ValueError('invalid release version')
    return normalized


def version_tuple(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in normalize_version(value).split('.'))


def version_is_newer(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)
```

- [ ] **Step 5: Implement atomic state and request locking**

Create `update_state.py` with these public members and behavior:

```py
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

ACTIVE_UPDATE_STAGES = {'queued', 'preparing', 'pulling', 'backing_up', 'restarting', 'verifying'}


class UpdateInProgressError(RuntimeError):
    pass


class UpdateStateStore:
    def __init__(self, path: Path, stale_after_seconds: int = 1800):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix('.lock')
        self.stale_after_seconds = stale_after_seconds

    def read(self) -> dict:
        if not self.path.exists():
            return {'stage': 'idle', 'active': False, 'updated_at': 0}
        try:
            state = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return {'stage': 'failed', 'active': False, 'error': 'Update state is unreadable', 'updated_at': 0}
        age = time.time() - int(state.get('updated_at') or 0)
        if state.get('stage') in ACTIVE_UPDATE_STAGES and age > self.stale_after_seconds:
            return self.write({**state, 'stage': 'failed', 'active': False, 'error': 'Deployment status timed out'})
        return state

    def write(self, state: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = {**state, 'updated_at': int(time.time())}
        temporary = self.path.with_suffix(f'.{uuid4().hex}.tmp')
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, self.path)
        return state

    @contextmanager
    def request_lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists() and time.time() - self.lock_path.stat().st_mtime > self.stale_after_seconds:
            self.lock_path.unlink(missing_ok=True)
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise UpdateInProgressError('another update request is being processed') from exc
        os.close(descriptor)
        try:
            yield
        finally:
            self.lock_path.unlink(missing_ok=True)

    def begin(self, target_version: str) -> dict:
        with self.request_lock():
            current = self.read()
            fresh = time.time() - int(current.get('updated_at') or 0) <= self.stale_after_seconds
            if current.get('stage') in ACTIVE_UPDATE_STAGES and fresh:
                raise UpdateInProgressError('an update is already in progress')
            return self.write({
                'operation_id': uuid4().hex,
                'target_version': target_version,
                'previous_version': None,
                'stage': 'queued',
                'active': True,
                'message': 'Deployment queued',
                'error': None,
            })

    def fail(self, operation_id: str, message: str) -> dict:
        current = self.read()
        if current.get('operation_id') != operation_id:
            return current
        return self.write({**current, 'stage': 'failed', 'active': False, 'error': message, 'message': 'Deployment failed'})
```

- [ ] **Step 6: Run tests and commit**

```powershell
pytest backend/open_webui/tests/updates/test_update_versions.py backend/open_webui/tests/updates/test_update_state.py -q
git add backend/open_webui/utils/update_versions.py backend/open_webui/utils/update_state.py backend/open_webui/tests/updates
git commit -m "feat: add update version and state primitives"
```

Expected: all update primitive tests pass.

### Task 3: Add GitHub Release Client And Update Service

**Files:**
- Create: `backend/open_webui/utils/github_updates.py`
- Create: `backend/open_webui/utils/update_service.py`
- Create: `backend/open_webui/tests/updates/test_github_updates.py`
- Create: `backend/open_webui/tests/updates/test_update_service.py`

- [ ] **Step 1: Write failing GitHub client tests with `httpx.MockTransport`**

Cover these exact cases in `test_github_updates.py`:

```py
import httpx
import pytest

from open_webui.utils.github_updates import GitHubUpdateClient, GitHubUpdateError


@pytest.mark.asyncio
async def test_latest_release_normalizes_release_payload():
    def handler(request):
        assert request.url.path == '/repos/Artivis-Studio/ArtiChat/releases/latest'
        return httpx.Response(200, json={
            'tag_name': 'v0.1.2',
            'name': 'ArtiChat 0.1.2',
            'body': 'Updater release',
            'published_at': '2026-07-11T12:00:00Z',
            'html_url': 'https://github.com/Artivis-Studio/ArtiChat/releases/tag/v0.1.2',
            'draft': False,
            'prerelease': False,
        })
    client = GitHubUpdateClient('Artivis-Studio/ArtiChat', transport=httpx.MockTransport(handler))
    release = await client.latest_release()
    assert release['version'] == '0.1.2'
    assert release['body'] == 'Updater release'


@pytest.mark.asyncio
async def test_dispatch_sends_only_fixed_inputs():
    def handler(request):
        assert request.headers['authorization'] == 'Bearer deploy-token'
        assert request.url.path.endswith('/actions/workflows/artichat-deploy.yml/dispatches')
        assert request.read() == b'{"ref":"main","inputs":{"version":"0.1.2","operation_id":"op-123"}}'
        return httpx.Response(204)
    client = GitHubUpdateClient('Artivis-Studio/ArtiChat', token='deploy-token', transport=httpx.MockTransport(handler))
    await client.dispatch('artichat-deploy.yml', 'main', '0.1.2', 'op-123')


@pytest.mark.asyncio
async def test_dispatch_requires_a_token():
    client = GitHubUpdateClient('Artivis-Studio/ArtiChat')
    with pytest.raises(GitHubUpdateError, match='token is not configured'):
        await client.dispatch('artichat-deploy.yml', 'main', '0.1.2', 'op-123')
```

- [ ] **Step 2: Write failing service orchestration tests**

In `test_update_service.py`, use a fake GitHub client and real temporary `UpdateStateStore` to verify:

```py
@pytest.mark.asyncio
async def test_check_reports_new_release_and_deployment_capability(tmp_path):
    github = FakeGitHubClient(release={'version': '0.1.2', 'name': '0.1.2', 'body': 'notes', 'published_at': '', 'html_url': ''})
    service = make_service(tmp_path, github=github, current_version='0.1.1', token_configured=True)
    result = await service.check(force=True)
    assert result['current'] == '0.1.1'
    assert result['latest'] == '0.1.2'
    assert result['update_available'] is True
    assert result['deployment_enabled'] is True


@pytest.mark.asyncio
async def test_deploy_rejects_unpublished_target(tmp_path):
    service = make_service(tmp_path, github=FakeGitHubClient(release={'version': '0.1.2'}), current_version='0.1.1')
    with pytest.raises(ValueError, match='latest published release'):
        await service.deploy('0.1.3')


@pytest.mark.asyncio
async def test_dispatch_failure_marks_state_failed(tmp_path):
    github = FakeGitHubClient(release={'version': '0.1.2'}, dispatch_error=RuntimeError('dispatch unavailable'))
    service = make_service(tmp_path, github=github, current_version='0.1.1')
    with pytest.raises(RuntimeError, match='dispatch unavailable'):
        await service.deploy('0.1.2')
    assert service.status()['stage'] == 'failed'


@pytest.mark.asyncio
async def test_unconfigured_service_does_not_call_github(tmp_path):
    service = make_service(tmp_path, github=None, current_version='0.1.1')
    result = await service.check(force=True)
    assert result['latest'] == '0.1.1'
    assert result['update_available'] is False
    assert result['deployment_enabled'] is False


@pytest.mark.asyncio
async def test_release_failure_keeps_the_running_version_available(tmp_path):
    github = FakeGitHubClient(release_error=RuntimeError('GitHub unavailable'))
    service = make_service(tmp_path, github=github, current_version='0.1.1')
    result = await service.check(force=True)
    assert result['current'] == '0.1.1'
    assert result['latest'] == '0.1.1'
    assert result['update_available'] is False
    assert result['error'] == 'GitHub unavailable'
```

- [ ] **Step 3: Run tests to verify missing implementation fails**

```powershell
pytest backend/open_webui/tests/updates/test_github_updates.py backend/open_webui/tests/updates/test_update_service.py -q
```

Expected: import/collection failures for the new modules.

- [ ] **Step 4: Implement the GitHub client**

`github_updates.py` must expose `GitHubUpdateError` and `GitHubUpdateClient` with:

```py
class GitHubUpdateClient:
    def __init__(self, repository: str, token: str = '', transport=None, timeout_seconds: float = 15):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('invalid GitHub repository')
        self.repository = repository
        self.token = token
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def _headers(self, authenticated: bool = False) -> dict[str, str]:
        headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
        if authenticated:
            if not self.token:
                raise GitHubUpdateError('GitHub deployment token is not configured')
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    async def latest_release(self) -> dict:
        url = f'https://api.github.com/repos/{self.repository}/releases/latest'
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout_seconds) as client:
            response = await client.get(url, headers=self._headers())
        if response.status_code != 200:
            raise GitHubUpdateError(f'GitHub release request failed with status {response.status_code}')
        payload = response.json()
        if payload.get('draft') or payload.get('prerelease'):
            raise GitHubUpdateError('latest GitHub release is not a stable published release')
        return {
            'version': normalize_version(payload.get('tag_name', '')),
            'name': str(payload.get('name') or payload.get('tag_name') or ''),
            'body': str(payload.get('body') or ''),
            'published_at': str(payload.get('published_at') or ''),
            'html_url': str(payload.get('html_url') or ''),
        }

    async def dispatch(self, workflow: str, ref: str, version: str, operation_id: str) -> None:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+\.ya?ml', workflow):
            raise ValueError('invalid deployment workflow')
        url = f'https://api.github.com/repos/{self.repository}/actions/workflows/{workflow}/dispatches'
        payload = {'ref': ref, 'inputs': {'version': normalize_version(version), 'operation_id': operation_id}}
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout_seconds) as client:
            response = await client.post(url, headers=self._headers(authenticated=True), json=payload)
        if response.status_code != 204:
            raise GitHubUpdateError(f'GitHub workflow dispatch failed with status {response.status_code}')
```

- [ ] **Step 5: Implement cached orchestration**

`update_service.py` must define `ArtiChatUpdateService` with constructor dependencies, a 300-second release cache, and these methods:

```py
async def check(self, force: bool = False) -> dict:
    if self.github is None:
        return {
            'current': self.current_version,
            'latest': self.current_version,
            'display_version': self.display_version,
            'build_hash': self.build_hash,
            'update_available': False,
            'deployment_enabled': False,
            'release': None,
            'status': self.state_store.read(),
            'error': None,
        }
    try:
        release = await self._get_release(force=force)
    except Exception as exc:
        return {
            'current': self.current_version,
            'latest': self.current_version,
            'display_version': self.display_version,
            'build_hash': self.build_hash,
            'update_available': False,
            'deployment_enabled': bool(self.github.token),
            'release': None,
            'status': self.state_store.read(),
            'error': str(exc),
        }
    latest = release['version']
    return {
        'current': self.current_version,
        'latest': latest,
        'display_version': self.display_version,
        'build_hash': self.build_hash,
        'update_available': version_is_newer(latest, self.current_version),
        'deployment_enabled': bool(self.github.token),
        'release': release,
        'status': self.state_store.read(),
        'error': None,
    }

def status(self) -> dict:
    return self.state_store.read()

async def deploy(self, target_version: str) -> dict:
    if self.github is None:
        raise ValueError('update repository is not configured')
    target = normalize_version(target_version)
    release = await self._get_release(force=True)
    if release['version'] != target:
        raise ValueError('target version is not the latest published release')
    if not version_is_newer(target, self.current_version):
        raise ValueError('target version must be newer than the running version')
    state = self.state_store.begin(target)
    try:
        await self.github.dispatch(self.workflow, self.ref, target, state['operation_id'])
    except Exception as exc:
        self.state_store.fail(state['operation_id'], str(exc))
        raise
    return state
```

- [ ] **Step 6: Run tests and commit**

```powershell
pytest backend/open_webui/tests/updates/test_github_updates.py backend/open_webui/tests/updates/test_update_service.py -q
git add backend/open_webui/utils/github_updates.py backend/open_webui/utils/update_service.py backend/open_webui/tests/updates
git commit -m "feat: add GitHub update orchestration"
```

### Task 4: Expose Admin Update APIs And Runtime Configuration

**Files:**
- Create: `backend/open_webui/routers/updates.py`
- Create: `backend/open_webui/tests/updates/test_update_router.py`
- Modify: `backend/open_webui/env.py`
- Modify: `backend/open_webui/main.py`
- Modify: `.env.example`

- [ ] **Step 1: Write failing router contract tests**

Create `test_update_router.py`:

```py
from open_webui.routers import updates
from open_webui.utils.auth import get_admin_user


def test_update_router_exposes_only_expected_paths():
    paths = {(route.path, next(iter(route.methods))) for route in updates.router.routes}
    assert ('/check', 'GET') in paths
    assert ('/status', 'GET') in paths
    assert ('/deploy', 'POST') in paths


def test_all_update_routes_require_admin_dependency():
    for route in updates.router.routes:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert get_admin_user in dependency_calls
```

Also test endpoint functions directly with a fake service: `check` forwards `force`, `status` returns persisted state, `deploy` maps `ValueError` to HTTP 400, and an in-progress error to HTTP 409.

- [ ] **Step 2: Run the test and verify router import fails**

```powershell
pytest backend/open_webui/tests/updates/test_update_router.py -q
```

Expected: import error for `open_webui.routers.updates`.

- [ ] **Step 3: Add environment configuration**

In `env.py`, after `ENABLE_VERSION_UPDATE_CHECK`, define:

```py
ARTICHAT_UPDATE_REPOSITORY = os.getenv('ARTICHAT_UPDATE_REPOSITORY', '').strip()
ARTICHAT_UPDATE_WORKFLOW = os.getenv('ARTICHAT_UPDATE_WORKFLOW', 'artichat-deploy.yml').strip()
ARTICHAT_UPDATE_REF = os.getenv('ARTICHAT_UPDATE_REF', 'main').strip()
ARTICHAT_UPDATE_GITHUB_TOKEN = os.getenv('ARTICHAT_UPDATE_GITHUB_TOKEN', '').strip()
ARTICHAT_UPDATE_STATE_PATH = Path(
    os.getenv('ARTICHAT_UPDATE_STATE_PATH', str(DATA_DIR / 'update-state' / 'status.json'))
).resolve()
ARTICHAT_UPDATE_CACHE_TTL_SECONDS = int(os.getenv('ARTICHAT_UPDATE_CACHE_TTL_SECONDS', '300'))
ARTICHAT_UPDATE_STALE_AFTER_SECONDS = int(os.getenv('ARTICHAT_UPDATE_STALE_AFTER_SECONDS', '1800'))
```

Document the same variables in `.env.example` with empty token and repository values. Never put a real token or repository owner in that file.

- [ ] **Step 4: Implement the admin router**

Create `routers/updates.py` with a lazily constructed singleton service, `DeployUpdateForm(target_version: str)`, and:

```py
@router.get('/check')
async def check_for_updates(force: bool = False, user=Depends(get_admin_user), service=Depends(get_update_service)):
    try:
        return await service.check(force=force)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get('/status')
async def get_update_status(user=Depends(get_admin_user), service=Depends(get_update_service)):
    return service.status()


@router.post('/deploy', status_code=202)
async def deploy_update(form_data: DeployUpdateForm, user=Depends(get_admin_user), service=Depends(get_update_service)):
    try:
        return await service.deploy(form_data.target_version)
    except UpdateInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubUpdateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

The singleton uses `VERSION`, `WEBUI_BUILD_HASH`, `f'{VERSION} (Artivis Alpha)'`, the new environment variables, `GitHubUpdateClient`, and `UpdateStateStore`. When `ARTICHAT_UPDATE_REPOSITORY` is empty, pass `github=None`; local development then reports the running version with `deployment_enabled=false` instead of making an external request.

- [ ] **Step 5: Mount the router and enrich runtime version metadata**

Import `updates` in `main.py`, then mount:

```py
app.include_router(updates.router, prefix='/api/v1/updates', tags=['updates'])
```

Replace `/api/version` with:

```py
@app.get('/api/version')
async def get_app_version():
    return {
        'version': VERSION,
        'display_version': f'{VERSION} (Artivis Alpha)',
        'build_hash': WEBUI_BUILD_HASH,
        'deployment_id': DEPLOYMENT_ID,
    }
```

Delete the inert `/api/version/updates` route; all frontend callers move in Task 5.

- [ ] **Step 6: Run backend tests and commit**

```powershell
pytest backend/open_webui/tests/updates -q
npm run test:branding
git add .env.example backend/open_webui/env.py backend/open_webui/main.py backend/open_webui/routers/updates.py backend/open_webui/tests/updates
git commit -m "feat: expose ArtiChat update APIs"
```

Expected: update tests and branding guard pass.

### Task 5: Add Typed Frontend Update APIs And Pure Helpers

**Files:**
- Create: `src/lib/apis/updates/index.ts`
- Create: `src/lib/utils/updates.ts`
- Create: `src/lib/utils/updates.test.ts`
- Modify: `src/lib/apis/index.ts`
- Modify: `src/routes/(app)/+layout.svelte`
- Modify: `src/lib/components/layout/UpdateInfoToast.svelte`

- [ ] **Step 1: Write failing helper tests**

Create `updates.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { isActiveUpdateStage, shouldPollUpdate, updateStageLabel } from './updates';

describe('update helpers', () => {
	it('recognizes active deployment stages', () => {
		expect(isActiveUpdateStage('queued')).toBe(true);
		expect(isActiveUpdateStage('verifying')).toBe(true);
		expect(isActiveUpdateStage('completed')).toBe(false);
		expect(isActiveUpdateStage('rolled_back')).toBe(false);
	});

	it('polls while an operation is active', () => {
		expect(shouldPollUpdate({ stage: 'pulling', active: true })).toBe(true);
		expect(shouldPollUpdate({ stage: 'failed', active: false })).toBe(false);
	});

	it('uses a stable Chinese label for every deployment stage', () => {
		expect(updateStageLabel('backing_up')).toBe('正在备份数据');
		expect(updateStageLabel('rolled_back')).toBe('更新失败，已回滚');
	});
});
```

- [ ] **Step 2: Run Vitest and verify the module is missing**

```powershell
npm run test:frontend -- src/lib/utils/updates.test.ts
```

Expected: FAIL because `updates.ts` does not exist.

- [ ] **Step 3: Implement shared frontend types and helpers**

Define these exact types in `src/lib/apis/updates/index.ts`:

```ts
export type UpdateStage =
	| 'idle'
	| 'queued'
	| 'preparing'
	| 'pulling'
	| 'backing_up'
	| 'restarting'
	| 'verifying'
	| 'completed'
	| 'failed'
	| 'rolled_back';

export type UpdateState = {
	operation_id?: string;
	target_version?: string;
	previous_version?: string | null;
	stage: UpdateStage;
	active: boolean;
	message?: string | null;
	error?: string | null;
	updated_at: number;
};

export type ReleaseInfo = {
	version: string;
	name: string;
	body: string;
	published_at: string;
	html_url: string;
};

export type UpdateInfo = {
	current: string;
	latest: string;
	display_version: string;
	build_hash: string;
	update_available: boolean;
	deployment_enabled: boolean;
	release: ReleaseInfo | null;
	status: UpdateState;
	error: string | null;
};
```

Implement authenticated `getUpdateInfo(token, force)`, `getUpdateStatus(token)`, and `deployUpdate(token, targetVersion)` for `GET /api/v1/updates/check`, `GET /api/v1/updates/status`, and `POST /api/v1/updates/deploy` using the existing fetch/error pattern. `deployUpdate` sends `{ target_version: targetVersion }`.

Implement `updates.ts`:

```ts
import type { UpdateStage, UpdateState } from '$lib/apis/updates';

const activeStages = new Set<UpdateStage>([
	'queued',
	'preparing',
	'pulling',
	'backing_up',
	'restarting',
	'verifying'
]);

const labels: Record<UpdateStage, string> = {
	idle: '尚未开始更新',
	queued: '等待部署任务',
	preparing: '正在准备更新',
	pulling: '正在下载新镜像',
	backing_up: '正在备份数据',
	restarting: '正在重启 ArtiChat',
	verifying: '正在验证新版本',
	completed: '更新完成',
	failed: '更新失败',
	rolled_back: '更新失败，已回滚'
};

export const isActiveUpdateStage = (stage: UpdateStage) => activeStages.has(stage);
export const shouldPollUpdate = (state?: Pick<UpdateState, 'stage' | 'active'> | null) =>
	Boolean(state?.active || (state && isActiveUpdateStage(state.stage)));
export const updateStageLabel = (stage: UpdateStage) => labels[stage] ?? labels.failed;
```

- [ ] **Step 4: Remove the legacy API and update the admin toast caller**

Delete `getVersionUpdates` from `src/lib/apis/index.ts`. In `(app)/+layout.svelte`, import `getUpdateInfo` from `$lib/apis/updates`, call it only for admins, and show `UpdateInfoToast` when `version.update_available` is true. Update the toast prop type to `UpdateInfo` and retain its close behavior.

- [ ] **Step 5: Run frontend tests and commit**

```powershell
npm run test:frontend -- src/lib/utils/updates.test.ts
npm run build
git add src/lib/apis/index.ts src/lib/apis/updates src/lib/utils/updates.ts src/lib/utils/updates.test.ts 'src/routes/(app)/+layout.svelte' src/lib/components/layout/UpdateInfoToast.svelte
git commit -m "feat: add frontend update client"
```

### Task 6: Build The Administrator Version Update Panel

**Files:**
- Create: `src/lib/components/admin/Settings/VersionUpdatePanel.svelte`
- Modify: `src/lib/components/admin/Settings/General.svelte`
- Modify: `src/lib/i18n/locales/en-US/translation.json`
- Modify: `src/lib/i18n/locales/zh-CN/translation.json`

- [ ] **Step 1: Add a failing source contract for the panel**

Extend `scripts/check-update-system.mjs` initially with a panel check, or create the script now with this minimal content:

```js
import fs from 'node:fs';

const panel = fs.readFileSync('src/lib/components/admin/Settings/VersionUpdatePanel.svelte', 'utf8');
for (const required of ['getUpdateInfo', 'getUpdateStatus', 'deployUpdate', 'ConfirmDialog', 'shouldPollUpdate']) {
	if (!panel.includes(required)) throw new Error(`Version update panel is missing ${required}`);
}
```

Add `"test:updates": "node scripts/check-update-system.mjs"` to `package.json` and run it.

Expected: FAIL because the panel does not exist.

- [ ] **Step 2: Implement the focused panel component**

The component must:

- Load update info and state on mount.
- Offer an icon refresh button with a tooltip.
- Render current/display version and abbreviated build hash.
- Render plain-text release notes with `whitespace-pre-wrap`; do not use `{@html}`.
- Show “部署更新” only when `update_available && deployment_enabled && !status.active`.
- Open `ConfirmDialog` before dispatch.
- Poll every three seconds while `shouldPollUpdate(status)` is true.
- Treat temporary fetch failures during `restarting` as expected and keep polling.
- Stop polling in `onDestroy`.
- Show backend errors with `svelte-sonner`.

Use the existing `Refresh.svelte`, `CloudArrowUp.svelte`, `Spinner.svelte`, `Tooltip.svelte`, and `ConfirmDialog.svelte` components. The deploy handler is:

```ts
const confirmDeploy = async () => {
	if (!info?.latest || deploying) return;
	deploying = true;
	const accepted = await deployUpdate(localStorage.token, info.latest).catch((error) => {
		toast.error(error?.detail ?? `${error}`);
		return null;
	});
	if (accepted) {
		status = accepted;
		toast.success('更新任务已提交。');
		startPolling();
	}
	deploying = false;
};
```

- [ ] **Step 3: Replace the legacy General version block**

In `General.svelte`, remove `getVersionUpdates`, `WEBUI_BUILD_HASH`, `WEBUI_VERSION`, `compareVersion`, the local version state, and `checkForVersionUpdates`. Import `VersionUpdatePanel` and replace only the existing Version section with:

```svelte
<div class="mb-2.5">
	<VersionUpdatePanel />
</div>
```

Leave Help, License, feature settings, banners, and the form save behavior unchanged.

- [ ] **Step 4: Add exact Chinese translations**

Add these keys to `zh-CN/translation.json`; use empty values in `en-US` so English falls back to the source key:

```json
{
  "Deploy update": "部署更新",
  "Deployment is not configured": "尚未配置自动部署",
  "Release notes": "版本说明",
  "Update task submitted.": "更新任务已提交。",
  "ArtiChat will briefly restart. Server data will be backed up before deployment.": "ArtiChat 将短暂重启，部署前会备份服务器数据。",
  "Confirm deployment": "确认部署",
  "Running version": "当前运行版本"
}
```

- [ ] **Step 5: Run panel guard, frontend tests, and build**

```powershell
npm run test:updates
npm run test:frontend
npm run build
```

Expected: panel contract and Vitest pass; Vite build succeeds.

- [ ] **Step 6: Commit the administrator UI**

```powershell
git add package.json package-lock.json scripts/check-update-system.mjs src/lib/components/admin/Settings/VersionUpdatePanel.svelte src/lib/components/admin/Settings/General.svelte src/lib/i18n/locales/en-US/translation.json src/lib/i18n/locales/zh-CN/translation.json
git commit -m "feat: add administrator update panel"
```

### Task 7: Implement And Test The Fixed-Scope Server Deployment Script

**Files:**
- Create: `deploy/aws-1panel/artichat-deploy.sh`
- Create: `deploy/aws-1panel/tests/test-artichat-deploy.sh`
- Modify: `scripts/check-update-system.mjs`

- [ ] **Step 1: Write the fake-command deployment tests**

Create a Bash test harness that builds a temporary deploy tree, puts fake `docker` and `curl` executables first in `PATH`, and runs the real script with these overrides:

```bash
export ARTICHAT_DEPLOY_DIR="$TMP/deploy"
export ARTICHAT_DATA_DIR="$TMP/deploy/data"
export ARTICHAT_BACKUP_DIR="$TMP/deploy/backups"
export ARTICHAT_UPDATE_STATE_FILE="$TMP/deploy/update-state/status.json"
export ARTICHAT_IMAGE_REPOSITORY="ghcr.io/artivis-test/artichat"
export ARTICHAT_COMPOSE_FILE="$TMP/deploy/docker-compose.yaml"
export ARTICHAT_ENV_FILE="$TMP/deploy/.env"
export ARTICHAT_IMAGE_ENV_FILE="$TMP/deploy/image.env"
export ARTICHAT_HEALTH_URL="http://127.0.0.1:13000"
```

The success test must assert:

```bash
grep -q 'ARTICHAT_IMAGE=ghcr.io/artivis-test/artichat:0.1.2' "$ARTICHAT_IMAGE_ENV_FILE"
grep -q '"stage": "completed"' "$ARTICHAT_UPDATE_STATE_FILE"
test -f "$ARTICHAT_DATA_DIR/user-data.txt"
test "$(find "$ARTICHAT_BACKUP_DIR" -type f | wc -l)" -eq 1
```

The failure test makes fake `curl /api/version` return `0.1.1` after the new start and asserts that `image.env` returns to `0.1.1`, original data is restored, and state is `rolled_back`.

- [ ] **Step 2: Run the harness and verify the deploy script is missing**

Use Git Bash or WSL:

```bash
bash deploy/aws-1panel/tests/test-artichat-deploy.sh
```

Expected: FAIL because `artichat-deploy.sh` does not exist.

- [ ] **Step 3: Implement strict argument, path, lock, and state helpers**

Start `artichat-deploy.sh` with:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_VERSION="${1:-}"
OPERATION_ID="${2:-}"
[[ "$TARGET_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "invalid version" >&2; exit 2; }
[[ "$OPERATION_ID" =~ ^[A-Za-z0-9._-]{8,128}$ ]] || { echo "invalid operation id" >&2; exit 2; }

DEPLOY_DIR="${ARTICHAT_DEPLOY_DIR:-/data/artichat-prod}"
DATA_DIR="${ARTICHAT_DATA_DIR:-$DEPLOY_DIR/data}"
BACKUP_DIR="${ARTICHAT_BACKUP_DIR:-$DEPLOY_DIR/backups}"
STATE_FILE="${ARTICHAT_UPDATE_STATE_FILE:-$DEPLOY_DIR/update-state/status.json}"
COMPOSE_FILE="${ARTICHAT_COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yaml}"
ENV_FILE="${ARTICHAT_ENV_FILE:-$DEPLOY_DIR/.env}"
IMAGE_ENV_FILE="${ARTICHAT_IMAGE_ENV_FILE:-$DEPLOY_DIR/image.env}"
IMAGE_REPOSITORY="${ARTICHAT_IMAGE_REPOSITORY:?ARTICHAT_IMAGE_REPOSITORY is required}"
HEALTH_URL="${ARTICHAT_HEALTH_URL:-http://127.0.0.1:13000}"
LOCK_FILE="$DEPLOY_DIR/update.lock"

mkdir -p "$BACKUP_DIR" "$(dirname "$STATE_FILE")"
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "another deployment is running" >&2; exit 3; }
```

Implement `write_state(stage, active, message, error)` via `python3` JSON serialization and atomic `os.replace`. Implement `compose()` as:

```bash
compose() {
  docker compose --env-file "$ENV_FILE" --env-file "$IMAGE_ENV_FILE" -f "$COMPOSE_FILE" "$@"
}
```

Validate that resolved `DATA_DIR`, `BACKUP_DIR`, and `STATE_FILE` are under resolved `DEPLOY_DIR`, and reject `/`, an empty value, or symlink escape.

- [ ] **Step 4: Implement pull, backup, recreate, and health verification**

Use this exact order:

```text
preparing -> docker pull fixed-repository:target
record old ARTICHAT_IMAGE from image.env
stop artichat
backing_up -> tar data to a temporary archive, then rename
write target image.env atomically
restarting -> docker compose up -d --no-deps --force-recreate artichat
verifying -> poll /health and /api/version for up to 180 seconds
completed -> rotate backups to 3 and keep current/previous image
```

The version verifier must parse JSON using Python and require exact equality with `TARGET_VERSION`. Pull by full fixed image name before stopping the service.

Before pulling, compute `DATA_BYTES` with `du -sb "$DATA_DIR"` and available bytes with `df -PB1 "$DEPLOY_DIR"`. Require at least `DATA_BYTES * 2 + 1073741824` available bytes so a backup and rollback staging directory fit with 1 GiB headroom. A failed preflight writes `failed` state without stopping the old container.

After success, list images only for the exact `IMAGE_REPOSITORY`; retain the target image and previous image, and remove older tags with `docker image rm`. Do not use any global image/container/system prune command.

- [ ] **Step 5: Implement rollback for every post-stop failure**

Register an `ERR` trap after the backup exists. Rollback must:

1. Stop only the `artichat` service.
2. Move failed data to a validated temporary sibling.
3. Recreate `DATA_DIR` and extract the deployment backup.
4. Restore the previous `ARTICHAT_IMAGE` in `image.env`.
5. Run `compose up -d --no-deps --force-recreate artichat`.
6. Require old health and old version.
7. Write `rolled_back` with `active=false`.

If backup creation itself fails, restore the old container without replacing data. Never call `docker compose down`, never prune volumes, and never address another service.

- [ ] **Step 6: Run success and rollback tests**

```bash
bash deploy/aws-1panel/tests/test-artichat-deploy.sh
```

Expected: both scenarios pass and print `artichat deploy tests passed`.

- [ ] **Step 7: Extend the update-system guard and commit**

Require the deploy script to contain `flock`, `--no-deps`, `--force-recreate`, `/health`, `/api/version`, `rolled_back`, and backup rotation. Fail if it contains `--volumes`, `docker system prune`, or `/var/run/docker.sock`.

```powershell
npm run test:updates
git add deploy/aws-1panel/artichat-deploy.sh deploy/aws-1panel/tests/test-artichat-deploy.sh scripts/check-update-system.mjs
git commit -m "feat: add safe ArtiChat deployment script"
```

### Task 8: Add Restricted SSH Bootstrap And Production Compose Configuration

**Files:**
- Create: `deploy/aws-1panel/artichat-deploy-ssh.sh`
- Create: `deploy/aws-1panel/install-update-runner.sh`
- Modify: `deploy/aws-1panel/docker-compose.artichat-prod.yaml`
- Modify: `deploy/aws-1panel/README.zh-CN.md`
- Modify: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Write the forced-command wrapper**

`artichat-deploy-ssh.sh` must accept only the command placed in `SSH_ORIGINAL_COMMAND`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

read -r action version operation_id extra <<<"${SSH_ORIGINAL_COMMAND:-}"
[[ "$action" == "deploy" && -z "${extra:-}" ]] || { echo "unsupported command" >&2; exit 2; }
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "invalid version" >&2; exit 2; }
[[ "$operation_id" =~ ^[A-Za-z0-9._-]{8,128}$ ]] || { echo "invalid operation id" >&2; exit 2; }

exec sudo /usr/local/sbin/artichat-deploy "$version" "$operation_id"
```

- [ ] **Step 2: Implement the one-time host installer**

`install-update-runner.sh` runs as root, accepts `--user` and `--public-key-file`, copies both scripts to `/usr/local/sbin`, creates `/data/artichat-prod/{data,backups,update-state}`, writes a narrowly scoped sudoers file, validates it with `visudo -cf`, and appends this restricted key form:

```text
command="/usr/local/sbin/artichat-deploy-ssh",no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty ssh-ed25519 PUBLIC_KEY_MATERIAL artichat-github-actions
```

The installer must reject a non-Ed25519 key and must not print private material.

- [ ] **Step 3: Make the production Compose image immutable and expose update state**

Change the production service to:

```yaml
services:
  artichat:
    image: "${ARTICHAT_IMAGE:?ARTICHAT_IMAGE is required}"
    container_name: artichat-prod
    ports:
      - "${ARTICHAT_PORT:-13000}:8080"
    volumes:
      - /data/artichat-prod/data:/app/backend/data
      - /data/artichat-prod/update-state:/app/backend/data/update-state
    environment:
      - "OLLAMA_BASE_URL=http://host.docker.internal:11434"
      - "WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}"
      - "ARTICHAT_UPDATE_REPOSITORY=${ARTICHAT_UPDATE_REPOSITORY}"
      - "ARTICHAT_UPDATE_WORKFLOW=artichat-deploy.yml"
      - "ARTICHAT_UPDATE_REF=main"
      - "ARTICHAT_UPDATE_GITHUB_TOKEN=${ARTICHAT_UPDATE_GITHUB_TOKEN}"
      - "ARTICHAT_UPDATE_STATE_PATH=/app/backend/data/update-state/status.json"
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
```

The host uses `.env` for secrets/config and `image.env` for only `ARTICHAT_IMAGE`.

- [ ] **Step 4: Document exact normal and emergency commands**

Update the Chinese deployment README with:

```bash
cd /data/artichat-prod
sudo docker compose --env-file .env --env-file image.env -f docker-compose.yaml ps
curl -fsS http://127.0.0.1:13000/health
curl -fsS http://127.0.0.1:13000/api/version
```

Document backup location, three-backup retention, manual old-image selection, and the prohibition on `docker system prune --volumes`.

- [ ] **Step 5: Verify shell syntax and Compose rendering**

```bash
bash -n deploy/aws-1panel/artichat-deploy.sh
bash -n deploy/aws-1panel/artichat-deploy-ssh.sh
bash -n deploy/aws-1panel/install-update-runner.sh
docker compose --env-file deploy/aws-1panel/test.env --env-file deploy/aws-1panel/test-image.env -f deploy/aws-1panel/docker-compose.artichat-prod.yaml config
```

Create the two test env files only as local ignored files, then delete them. Expected: syntax checks pass and rendered config contains both host mounts and no Docker socket.

Use these non-secret test contents:

```dotenv
# deploy/aws-1panel/test.env
ARTICHAT_PORT=13000
WEBUI_SECRET_KEY=test-only-secret
ARTICHAT_UPDATE_REPOSITORY=artivis-test/ArtiChat
ARTICHAT_UPDATE_GITHUB_TOKEN=test-only-token
```

```dotenv
# deploy/aws-1panel/test-image.env
ARTICHAT_IMAGE=ghcr.io/artivis-test/artichat:0.1.2
```

- [ ] **Step 6: Commit**

```powershell
git add .env.example .gitignore deploy/aws-1panel
git commit -m "feat: add restricted production update runner"
```

### Task 9: Replace Upstream Release Automation With ArtiChat Workflows

**Files:**
- Create: `.github/workflows/artichat-release.yml`
- Create: `.github/workflows/artichat-deploy.yml`
- Delete: `.github/workflows/docker.yaml`
- Delete: `.github/workflows/release.yml`
- Delete: `.github/workflows/release-pypi.yml`
- Modify: `scripts/check-update-system.mjs`
- Modify: `scripts/check-release-version.mjs`
- Modify: `package.json`

- [ ] **Step 1: Make the workflow contract fail against upstream automation**

Extend `check-update-system.mjs` to assert:

```js
const required = [
	'.github/workflows/artichat-release.yml',
	'.github/workflows/artichat-deploy.yml',
	'deploy/aws-1panel/artichat-deploy.sh',
	'deploy/aws-1panel/docker-compose.artichat-prod.yaml'
];
const forbiddenWorkflows = [
	'.github/workflows/docker.yaml',
	'.github/workflows/release.yml',
	'.github/workflows/release-pypi.yml'
];
```

Require release workflow tag-only triggering, GHCR push, guard/test/build commands, and Release creation after image push. Require deploy workflow `workflow_dispatch`, `version`, `operation_id`, a concurrency group, strict validation, and native SSH. Reject `pull_request_target`, `docker.sock`, `latest` as a deployment target, and any Docker Hub/Open WebUI publication string.

Run `npm run test:updates`; expected: FAIL listing missing ArtiChat workflows and present upstream workflows.

- [ ] **Step 2: Create the tag-driven release workflow**

`artichat-release.yml` must use:

```yaml
name: ArtiChat Release
on:
  push:
    tags:
      - 'v*.*.*'
permissions:
  contents: write
  packages: write
concurrency:
  group: artichat-release-${{ github.ref }}
  cancel-in-progress: false
```

Its ordered steps are:

1. Checkout.
2. Set `VERSION=${GITHUB_REF_NAME#v}` and lowercase `IMAGE=ghcr.io/${GITHUB_REPOSITORY,,}`.
3. Run `npm ci --force`.
4. Run `npm run test:release-version -- --tag=$GITHUB_REF_NAME`, `test:branding`, `test:subscriptions`, `test:updates`, `test:frontend`, and `build`.
5. Set up Buildx and log into GHCR with `GITHUB_TOKEN`.
6. Build `linux/amd64` with `BUILD_HASH=${GITHUB_SHA}`, tag `${IMAGE}:${VERSION}` and `${IMAGE}:latest`, use registry cache, and push.
7. Inspect `${IMAGE}:${VERSION}`.
8. Create `v${VERSION}` GitHub Release using `docs/releases/${VERSION}.md` only after image inspection succeeds.

- [ ] **Step 3: Create the dispatch-only deployment workflow**

`artichat-deploy.yml` must define required string inputs `version` and `operation_id`, production concurrency with `cancel-in-progress: false`, validate both inputs in Bash, verify the GitHub Release exists, configure SSH from repository secrets, use a pre-recorded `ARTICHAT_DEPLOY_KNOWN_HOSTS`, and run exactly:

```bash
ssh -i ~/.ssh/artichat_deploy \
  "${{ secrets.ARTICHAT_DEPLOY_USER }}@${{ secrets.ARTICHAT_DEPLOY_HOST }}" \
  "deploy ${VERSION} ${OPERATION_ID}"
```

Do not use `StrictHostKeyChecking=no` and do not log secret values.

- [ ] **Step 4: Delete upstream publication workflows**

Remove the three upstream workflows named in the file list. Keep frontend/backend CI workflows, but confirm they contain no deployment secrets and no upstream publication jobs.

- [ ] **Step 5: Run workflow contracts and commit**

```powershell
npm run test:updates
npm run test:release-version
git add .github/workflows package.json package-lock.json scripts/check-update-system.mjs scripts/check-release-version.mjs
git commit -m "ci: add ArtiChat release and deploy workflows"
```

### Task 10: Prepare Version 0.1.2 And Run Full Local Verification

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `backend/open_webui/main.py`
- Create: `docs/releases/0.1.2.md`
- Modify: `docs/progress/2026-07-06-artichat-branding.md`

- [ ] **Step 1: Write the human release note before changing the version**

Create `docs/releases/0.1.2.md`:

```md
# ArtiChat 0.1.2

## 新增

- 管理员可在“设置 -> 通用 -> 版本”中检测 ArtiChat 新版本。
- 支持从 GitHub Release 触发受控 Docker 更新。
- 更新前自动备份服务器数据，并在健康检查失败时恢复旧版本。

## 运维

- Docker 镜像改为不可变版本标签。
- 正常更新不会覆盖 `/data/artichat-prod/data` 中的数据库和用户数据。
```

- [ ] **Step 2: Bump only canonical package metadata**

Run:

```powershell
npm version 0.1.2 --no-git-tag-version
```

Expected: `package.json` and both package-lock version fields become `0.1.2`; dynamic display constants need no manual change.

- [ ] **Step 3: Update the local changelog response**

Keep the dynamic `DISPLAY_VERSION` key and change the current entry to describe the update system. Do not include a GitHub owner or server address.

- [ ] **Step 4: Run complete source verification**

```powershell
npm run test:release-version -- --tag=v0.1.2
npm run test:branding
npm run test:subscriptions
npm run test:updates
npm run test:frontend
pytest backend/open_webui/tests/updates backend/open_webui/tests/subscriptions -q
npm run build
```

Expected: all guards/tests pass; subscription test count is at least the current 42-test baseline plus update tests; Vite build succeeds.

- [ ] **Step 5: Run local Docker smoke and data persistence test**

Build with the release hash, recreate only local ArtiChat, and verify:

```powershell
docker compose -p artichat build --build-arg BUILD_HASH=$(git rev-parse HEAD) artichat
docker compose -p artichat up -d --no-deps --force-recreate artichat
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/api/version
```

Expected: health is true, version is `0.1.2`, build hash is not `dev-build`, and existing local account/subscription data remains present.

- [ ] **Step 6: Record verification and commit**

Append exact command results to the branding progress note without server IP or secret data.

```powershell
git add package.json package-lock.json backend/open_webui/main.py docs/releases/0.1.2.md docs/progress/2026-07-06-artichat-branding.md
git commit -m "release: prepare ArtiChat 0.1.2"
```

### Task 11: Create A Secret-Scanned Public Repository With Fresh History

**Files:**
- Create: `scripts/export-public-repo.ps1`
- Modify: `.gitattributes`
- Modify: `.gitignore`
- Test: local temporary export directory

- [ ] **Step 1: Mark internal-only documentation as export-ignored**

Add:

```gitattributes
docs/progress export-ignore
docs/superpowers export-ignore
deploy-backups export-ignore
.worktrees export-ignore
```

Keep license files, source attribution, generic deployment docs, release notes, workflows, and tests in the public export.

- [ ] **Step 2: Implement a clean export script**

`export-public-repo.ps1` must accept a mandatory PowerShell `-Destination` path plus an optional `-ScanOnly` switch and:

1. In normal export mode, stop if `git status --porcelain` is non-empty.
2. In normal export mode, create a zip with `git archive HEAD` so `export-ignore` is honored.
3. In normal export mode, expand into a caller-supplied empty destination and initialize its one-commit Git history.
4. Recursively scan text files for private-key headers, GitHub tokens, AWS access keys, non-dummy `WEBUI_SECRET_KEY` values, `.env` files, database files, and deployment backups.
5. Read additional deployment-specific forbidden strings from an optional local `.public-forbidden-values` file, one literal value per line; this ignored file contains the production host and any other operator-selected values without embedding them in the export script.
6. Stop with file/line output on any hit.
7. In `-ScanOnly` mode, skip Git status/archive/Git initialization and scan the already existing destination in place.

The scanner allows documented variable names and dummy values such as `change_me`, but rejects non-empty secret assignments.

- [ ] **Step 3: Test the scanner fails closed**

Add `.public-forbidden-values` to `.gitignore`. First create a clean temporary export. Add `fake-secret.env` containing `WEBUI_SECRET_KEY=real-looking-test-secret` inside that temporary export and run the script with `-ScanOnly`; expected: the scan fails and reports the file. Delete the fixture, run `-ScanOnly` again, and expected: the scan passes. Confirm the export has one clean root commit with no `docs/progress` or `docs/superpowers` paths.

- [ ] **Step 4: Commit the export tooling**

```powershell
git add .gitattributes .gitignore scripts/export-public-repo.ps1
git commit -m "chore: add sanitized public repository export"
```

- [ ] **Step 5: Install and authenticate GitHub CLI**

On Windows:

```powershell
winget install --id GitHub.cli --exact
gh auth login --web --git-protocol https
$githubOwner = gh api user --jq .login
```

Expected: `$githubOwner` is the authenticated account; do not write it into committed files.

- [ ] **Step 6: Create and push the public repository**

From the clean export directory:

```powershell
gh repo create ArtiChat --public --source . --remote origin
git push -u origin main
```

Then, in the original repository, add `origin` using the URL returned by `gh repo view --json url --jq .url`, fetch it, and create local branch `public-main` from `origin/main`. Keep internal branches locally; future public release work uses `public-main`.

- [ ] **Step 7: Verify public contents**

```powershell
gh repo view --web
gh api "repos/$githubOwner/ArtiChat/contents/LICENSE"
gh api "repos/$githubOwner/ArtiChat/contents/.github/workflows/artichat-release.yml"
```

Expected: public code contains licenses/workflows and does not contain internal progress documents or server credentials.

### Task 12: Publish v0.1.2 And Perform The One-Time Production Bootstrap

**Files/External State:**
- GitHub repository settings and Actions Secrets
- GHCR package visibility
- Server: `/data/artichat-prod`
- Server: `/usr/local/sbin/artichat-deploy*`
- Server: restricted SSH key and sudoers entry

- [ ] **Step 1: Generate the dedicated deployment SSH key**

Create it outside the repository:

```powershell
$keyDir = Join-Path $env:USERPROFILE '.ssh\artichat-github-actions'
New-Item -ItemType Directory -Force $keyDir
ssh-keygen -t ed25519 -f (Join-Path $keyDir 'id_ed25519') -C 'artichat-github-actions' -N '""'
```

Never add either key file to Git. The public key is installed on the server; the private key becomes a GitHub Actions secret.

- [ ] **Step 2: Configure repository deployment secrets**

Set these GitHub Actions secrets using values read interactively from local untracked files or the operator:

```text
ARTICHAT_DEPLOY_HOST
ARTICHAT_DEPLOY_USER
ARTICHAT_DEPLOY_SSH_KEY
ARTICHAT_DEPLOY_KNOWN_HOSTS
```

Obtain `ARTICHAT_DEPLOY_KNOWN_HOSTS` from a separately verified host key fingerprint, not an unchecked first connection.

- [ ] **Step 3: Configure the server update token and files**

Create a fine-grained GitHub token restricted to the public `ArtiChat` repository with Actions read/write and metadata read. Store it only in `/data/artichat-prod/.env` as `ARTICHAT_UPDATE_GITHUB_TOKEN`; also set `ARTICHAT_UPDATE_REPOSITORY` to the authenticated owner plus `/ArtiChat`.

Upload the production Compose file and three host scripts. Run `install-update-runner.sh` with the existing deployment user and the dedicated public key. Create `/data/artichat-prod/image.env` initially pointing to the current known image until `0.1.2` is available.

- [ ] **Step 4: Push the public release tag**

From the public branch/repository:

```powershell
git tag -a v0.1.2 -m "ArtiChat 0.1.2"
git push origin v0.1.2
```

Expected: `ArtiChat Release` passes, publishes version `0.1.2` under the authenticated account's `artichat` GHCR package, and creates GitHub Release `v0.1.2`. The workflow dynamically determines the owner; do not edit workflow source with a literal account name.

- [ ] **Step 5: Make the GHCR package public and verify the immutable image**

In GitHub package settings for `artichat`, change visibility to Public and link it to the repository if GitHub has not linked it automatically. Verify from an unauthenticated shell:

```bash
GITHUB_OWNER="$(gh api user --jq .login)"
docker pull "ghcr.io/${GITHUB_OWNER,,}/artichat:0.1.2"
docker image inspect "ghcr.io/${GITHUB_OWNER,,}/artichat:0.1.2"
```

- [ ] **Step 6: Take the one-time production backup and bootstrap v0.1.2**

Before any production change, stop only ArtiChat and create a timestamped backup under `/data/artichat-prod/backups`. Install the new Compose/config, set `image.env` to `0.1.2`, and run the deploy script manually with a bootstrap operation ID. Do not restore the local Docker volume and do not alter `/data/artichat-prod/data` except through the script's backup/rollback path.

- [ ] **Step 7: Verify production data and updater behavior**

Verify:

```bash
curl -fsS http://127.0.0.1:13000/health
curl -fsS http://127.0.0.1:13000/api/version
curl -fsS -H "Authorization: Bearer ADMIN_TOKEN" http://127.0.0.1:13000/api/v1/updates/check
docker ps --filter name=artichat-prod
```

Expected: health true, version `0.1.2`, a non-development build hash, update status readable, and the production container healthy. Through the UI, confirm accounts, chats, model connections, subscriptions, balances, announcements, redemption codes, gift cards, uploads, and knowledge data remain present.

- [ ] **Step 8: Prove the next update path without changing production data**

Create a workflow-dispatch dry run only if the deployment workflow has a validated `dry_run` input added and tested; otherwise verify the GitHub token by calling the workflow metadata endpoint and leave production unchanged. The first real administrator-triggered deployment occurs with `v0.1.3`.

- [ ] **Step 9: Record bootstrap completion in the internal branch only**

Add the production result, backup location, release URL, and health/version result to an internal progress note. Do not push that note to the public repository; `docs/progress export-ignore` must remain effective.

---

## Final Verification Matrix

Run from the clean public working tree before declaring completion:

```powershell
npm run test:release-version -- --tag=v0.1.2
npm run test:branding
npm run test:subscriptions
npm run test:updates
npm run test:frontend
pytest backend/open_webui/tests/updates backend/open_webui/tests/subscriptions -q
npm run build
```

Run the deployment harness:

```bash
bash deploy/aws-1panel/tests/test-artichat-deploy.sh
```

Verify GitHub and production:

```text
Public repository contains one sanitized root history before future public commits.
Release v0.1.2 exists only after its GHCR image is available.
Production /health returns true.
Production /api/version returns 0.1.2 and a real build hash.
Production data is unchanged.
No Docker socket is mounted.
No workflow can deploy arbitrary images or arbitrary shell commands.
No cleanup path uses --volumes.
```
