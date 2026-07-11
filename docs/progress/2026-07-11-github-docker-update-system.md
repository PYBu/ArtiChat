# 2026-07-11 GitHub Docker Update System Progress

## Status

- Overall status: Local implementation complete through Task 11; external publication and production bootstrap remain deferred.
- Active branch: `artichat-brand-whitelabel`.
- Worktree: `.worktrees/artichat-brand-whitelabel`.
- Design: `docs/superpowers/specs/2026-07-11-artichat-github-docker-updates-design.zh-CN.md`.
- Implementation plan: `docs/superpowers/plans/2026-07-11-artichat-github-docker-updates.md`.
- Prepared release version: `0.1.2`.
- GitHub public repository has not been created or pushed.
- Final public repository target remains `PYBu/ArtiChat`.

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

## External State Deferred

- Do not create or push `PYBu/ArtiChat` without explicit user authorization.
- Do not install/authenticate GitHub CLI as part of the deferred phase unless explicitly requested.
- Do not create GitHub Actions Secrets or change GHCR visibility.
- Do not generate/install the production SSH key.
- Do not upload files to or operate the production server.

## Next Continue Point

1. Re-run the local Docker `0.1.2` smoke when Docker build access to GitHub/Hugging Face is stable, then verify `/health`, `/api/version`, a non-development build hash, and unchanged data counts.
2. If the user explicitly starts the external publication phase, continue Task 11 Step 5 through Task 12 from the implementation plan.
3. Otherwise stop after local verification; keep GitHub creation, push, Secrets, GHCR visibility, and production bootstrap deferred.
