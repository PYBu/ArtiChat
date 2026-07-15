# ArtiChat Collaboration Rules

## Local Acceptance

- After completing an implementation task, build the current worktree and run it at `http://localhost:3000` for user acceptance before reporting the task as complete.
- Port 3000 is the required final local acceptance target. A disposable port such as 3001 may be used for isolated checks, but it does not replace the port-3000 handoff.
- Preserve the existing `artichat_data` Docker volume and the current container's runtime configuration when replacing the local acceptance container.
- Use a health-gated replacement with a rollback path. If the new container does not become healthy, restore the previous port-3000 container and report the failure.
- Do not push, tag, merge, publish a release, deploy to production, or modify production data without explicit user approval.

## User-Owned Project Introduction

- `README.md` and the entire `artivis-ass/` directory are maintained exclusively by the user. Do not edit, regenerate, reformat, rename, remove, or otherwise manage either path unless the user explicitly requests that exact change.
- When preparing a GitHub upload, public candidate, tag, or release, ignore local changes to `README.md` and `artivis-ass/`. Preserve the exact versions already present on `origin/main`; the user publishes updates to these paths separately.
- Before starting work on a new version milestone such as 0.1.5, fetch `origin/main` and synchronize only `README.md` and `artivis-ass/` from `origin/main` into the active development worktree. Do not use that synchronization to overwrite unrelated local work.

## Current Release Handoff

- ArtiChat 0.1.4 implementation and local acceptance are complete. Its detailed internal record is `docs/progress/2026-07-14-artichat-0.1.4.md`.
- Before beginning the next version, follow the user-owned introduction synchronization rule above and then create a version-specific progress record.
