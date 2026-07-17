# 2026-07-11 GitHub Docker Update System Progress

## Status

- Overall status: Tasks 1-11 and the automated Task 12 production bootstrap are complete; authenticated UI spot checks remain.
- Active branch: `artichat-brand-whitelabel`.
- Worktree: `.worktrees/artichat-brand-whitelabel`.
- Design: `docs/superpowers/specs/2026-07-11-artichat-github-docker-updates-design.zh-CN.md`.
- Implementation plan: `docs/superpowers/plans/2026-07-11-artichat-github-docker-updates.md`.
- Released version: `0.1.2`.
- Public repository: `https://github.com/PYBu/ArtiChat`.
- Release: `https://github.com/PYBu/ArtiChat/releases/tag/v0.1.2`.

## Completed Tasks And Commits

- Task 1: release baseline, `097ff5c`.
- Task 2: semantic version and deployment state primitives, `8d6b0b7` and `3da2e1e`.
- Task 3: GitHub release client and update orchestration, `57a715e`.
- Task 4: admin update API and runtime configuration, `8e948ef`.
- Task 5: typed frontend update API and helpers, `f46da64`.
- Task 6: administrator update panel, `5d2a74f`.
- Task 7: fixed-scope deploy/backup/rollback harness, `bde1d5e`.
- Task 8: restricted SSH wrapper, installer, immutable production Compose, and deployment documentation, `0ab2d02`.
- Task 9: ArtiChat GHCR release/deploy workflows and removal of upstream publication workflows, `9d376ff`.
- Task 10: version `0.1.2`, release notes, changelog, and source verification, `df8490b`.
- Task 11 local steps: export-ignore rules and secret-scanned one-commit public export tooling, `0d1118b`.
- Docker frontend dependency fix and completed local smoke, `d6a2a7d`.

## Verification

- `npm run test:release-version -- --tag=v0.1.2`: passed.
- `npm run test:branding`: passed, scanning 155 files.
- `npm run test:subscriptions`: passed.
- `npm run test:updates`: passed.
- `CI=true npm run test:frontend`: 3 passed.
- `pytest backend/open_webui/tests/updates backend/open_webui/tests/subscriptions -q`: 87 passed, 1 existing SQLAlchemy warning.
- `npm run build`: passed in about 177 seconds with existing non-fatal Svelte/Vite warnings.
- Task 8 Bash syntax checks: passed with Git Bash.
- Task 8 deploy harness: `artichat deploy tests passed`.
- Task 8 production Compose rendering: passed with both host mounts and no Docker socket.
- Task 9 workflow source contracts and Prettier parsing: passed.
- Task 11 PowerShell parser, dirty-worktree gate, fail-closed secret fixture, custom forbidden-value scan, and clean ScanOnly checks: passed.
- Task 11 normal export: passed; generated one clean root commit, excluded `docs/progress`, `docs/superpowers`, backups, worktrees, and local forbidden values, while retaining licenses, release notes, workflows, and deployment tooling.

## Local Docker Smoke Resolution

The Docker build blocker was traced to `onnxruntime-node` downloading unused Linux CUDA binaries during frontend `npm ci`. The Dockerfile now sets `ONNXRUNTIME_NODE_INSTALL_CUDA=skip` before installing frontend dependencies; the CPU/Slim build does not need CUDA for the browser frontend.

After the fix, `docker compose -p artichat build --build-arg BUILD_HASH=$(git rev-parse HEAD) --build-arg USE_SLIM=true artichat` passed in about 300 seconds, and only `artichat` was recreated with `--no-deps --force-recreate`.

- `/health`: `{"status":true}`.
- `/api/version`: `0.1.2`, display version `0.1.2 (Artivis Alpha)`, build hash `655381431dedeeedde7d4b83c7590af0a9387ea3`.
- Container image: new image ID `sha256:de62e9a68ff2945fd050567f8a4b76f3a2bc1f68352661fda7ac8242123ad527`.
- `artichat_data` remained the mounted volume.
- Data counts stayed unchanged: users 3, chats 14, knowledge bases 1, redemption codes 4, subscription plans 3, announcements 1.

The container logs showed normal startup and the existing non-fatal model-loading/API warnings only.

## Public Release And Production Bootstrap

- Created public repository `PYBu/ArtiChat` from the secret-scanned export with one root commit, `672d2a9`.
- Verified licenses, release/deploy workflows, and the absence of internal progress and planning documents through the GitHub API.
- Configured the four deployment Actions Secrets and installed the dedicated forced-command SSH runner. Arbitrary commands through the deployment key were rejected.
- Published `v0.1.2`; GitHub Actions run `29164990277` passed all guards, tests, application build, image push, image inspection, and Release publication.
- Verified anonymous GHCR access. Image `ghcr.io/pybu/artichat:0.1.2` has digest `sha256:c427117c479e8dc028863dc3bc9241a7d367d2b6b3246cc36f95ad209fda4393` and build hash `672d2a9ec811495bf3a0b07ff3d606de19204c5e`.
- The first production pull exposed insufficient Docker-root space. The root EBS volume was expanded from 20 GiB to 40 GiB, then partition 1 and its ext4 filesystem were grown online to 37.6 GiB. ArtiChat remained healthy on `0.1.1` during the resize.
- Production operation `bootstrap-0.1.2-20260711T194923Z` completed. The verified backup is `/data/artichat-prod/backups/artichat-data-20260711-194930-bootstrap-0.1.2-20260711T194923Z.tar.gz` (987,543,082 bytes).
- Production `/health` returned true and `/api/version` returned `0.1.2 (Artivis Alpha)` with the release build hash. The container is healthy and uses only the fixed data and update-state bind mounts; no Docker socket is mounted.
- All 20 recorded user/chat/file/knowledge/subscription/redemption/announcement table counts remained unchanged. Other production containers were not restarted.
- The updater token was verified from inside the new container against the active deploy workflow. The workflow has no dry-run input, so no test dispatch was made; the first real administrator-triggered update remains `v0.1.3`.

## Next Continue Point

1. Complete a manual authenticated UI spot check for accounts, chats, model connections, subscriptions, balances, announcements, redemption codes, gift cards, uploads, and knowledge data.
2. Use `public-main` for future public release changes; keep `docs/progress` and `docs/superpowers` internal-only.
3. Prepare and test `v0.1.3` before using the administrator-triggered deployment path for the first time.
