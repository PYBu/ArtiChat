# 2026-07-11 GitHub Docker Update System Progress

## Status

- Overall status: Paused after Task 7.
- Active branch: `artichat-brand-whitelabel`.
- Worktree: `.worktrees/artichat-brand-whitelabel`.
- Design: `docs/superpowers/specs/2026-07-11-artichat-github-docker-updates-design.zh-CN.md`.
- Implementation plan: `docs/superpowers/plans/2026-07-11-artichat-github-docker-updates.md`.
- Production version observed before implementation: `0.1.1`.
- GitHub public repository has not been created or pushed.
- Final public repository target: `PYBu/ArtiChat`.

## Completed

### Task 1: Stabilize And Commit The 0.1.1 Release Baseline

- Status: Complete.
- Commit: `097ff5c chore: establish ArtiChat 0.1.1 release baseline`.
- Preserved package version `0.1.1` in `package.json` and `package-lock.json`.
- Added `npm run test:release-version` and made its expected version derive from package metadata.
- Added optional release-tag validation, verified with `--tag=v0.1.1`.
- Made `WEBUI_DISPLAY_VERSION` derive from semantic `WEBUI_VERSION`.
- Updated the changelog modal and About page to display `0.1.1 (Artivis Alpha)`.
- Removed disabled legacy update-check code from the About page while preserving the new ArtiChat/Artivis/MineAPI copy.
- Corrected the Docker backend build-hash environment variable from `WEBUI_BUILD_VERSION` to `WEBUI_BUILD_HASH`.

### Tasks 2-7: GitHub/Docker Update System

- Task 2 complete: semantic version helpers and atomic deployment state store.
  - Commits: `8d6b0b7`, `3da2e1e`.
  - Hardened cross-platform advisory locking, stale-state handling, malformed JSON handling, and temporary-file cleanup.
- Task 3 complete: GitHub Release client and cached update orchestration.
  - Commit: `57a715e`.
  - Release metadata is normalized; dispatch inputs are fixed; token text is redacted from returned/persisted errors.
- Task 4 complete: admin update API, runtime configuration, and enriched `/api/version`.
  - Commit: `8e948ef`.
  - Added `/api/v1/updates/check`, `/status`, and `/deploy`; removed the inert `/api/version/updates` route.
- Task 5 complete: typed frontend update API, update helpers, admin toast migration, and General settings compatibility migration.
  - Commit: `f46da64`.
- Task 6 complete: administrator version update panel with release notes, confirmation, three-second polling, restart tolerance, and cleanup on destroy.
  - Commit: `5d2a74f`.
- Task 7 complete: fixed-scope deployment, backup, health/version verification, rollback, and fake-command harness.
  - Commit: `bde1d5e`.

## Verification

- `npm run test:release-version`: passed.
- `npm run test:release-version -- --tag=v0.1.1`: passed.
- `npm run test:branding`: passed, scanning 155 files.
- `npm run test:subscriptions`: passed.
- `pytest backend/open_webui/tests/subscriptions -q`: 42 passed, 1 existing SQLAlchemy warning.
- `npm run build`: passed in about 110 seconds.
- The build emitted existing Svelte accessibility/self-closing-tag warnings and chunk-size warnings; no new blocking build error was introduced.
- The build did not leave tracked Pyodide output changes.

## Verification Since Task 1

- Task 2 update tests: `19 passed` after concurrency hardening.
- Task 3-4 backend update tests: `45 passed`.
- Task 5 frontend tests: `3 passed`.
- Task 5 `vite build`: passed.
- Task 5 full `npm run build`: passed after Pyodide resources were downloaded.
- Task 6 `npm run test:updates`: passed.
- Task 6 `npm run test:frontend -- --run`: `3 passed`.
- Task 6 `vite build`: passed with existing Svelte accessibility and chunk-size warnings.
- A later full Task 6 `npm run build` exceeded the 15-minute command limit during Pyodide preparation; child processes were terminated and generated Pyodide changes were restored. No source failure was reported.
- Task 7 shell syntax checks: passed with Git Bash.
- Task 7 deployment harness: `artichat deploy tests passed`.
- `npm run test:updates` after Task 7: passed.

## Uncommitted Task 8 Draft

The worktree currently contains uncommitted Task 8 changes. Preserve them when resuming:

- `.env.example`
- `.gitignore`
- `deploy/aws-1panel/artichat-deploy.sh`
- `deploy/aws-1panel/docker-compose.artichat-prod.yaml`
- `deploy/aws-1panel/tests/test-artichat-deploy.sh`
- `scripts/check-update-system.mjs`
- `deploy/aws-1panel/artichat-deploy-ssh.sh`
- `deploy/aws-1panel/install-update-runner.sh`

These changes add repository-derived GHCR image selection, restricted SSH/bootstrap scripts, update-state mounts, and local fixture ignores. They have not yet received the final Task 8 review or commit.

## External State Deferred

- Do not create or push `PYBu/ArtiChat` yet.
- Do not create GitHub Actions deployment secrets yet.
- Do not generate/install the production SSH key on the server yet.
- Do not change GHCR visibility or production files yet.

## Next Continue Point

Resume at **Task 8: Add Restricted SSH Bootstrap And Production Compose Configuration** in the implementation plan.

The next actions are:

1. Review the uncommitted Task 8 SSH wrapper, installer, Compose, README, and environment changes.
2. Run `bash -n` for all three host scripts and render the production Compose file with local ignored fixture env files.
3. Extend and run `npm run test:updates` and verify no Docker socket or volume-prune path is present.
4. Commit Task 8 only after the restricted command and host-path checks pass.
5. Continue with Tasks 9-11 local release/export work.
6. Defer public GitHub creation, release publication, Actions Secrets, and production bootstrap until explicitly started.
