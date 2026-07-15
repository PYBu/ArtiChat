# ArtiChat Collaboration Rules

## Local Acceptance

- After completing an implementation task, build the current worktree and run it at `http://localhost:3000` for user acceptance before reporting the task as complete.
- Port 3000 is the required final local acceptance target. A disposable port such as 3001 may be used for isolated checks, but it does not replace the port-3000 handoff.
- Preserve the existing `artichat_data` Docker volume and the current container's runtime configuration when replacing the local acceptance container.
- Use a health-gated replacement with a rollback path. If the new container does not become healthy, restore the previous port-3000 container and report the failure.
- Do not push, tag, merge, publish a release, deploy to production, or modify production data without explicit user approval.

## User-Owned Project Introduction

- `README.md` and the following README introduction images are maintained by the user and must not be edited, regenerated, reformatted, renamed, or removed unless the user explicitly requests that exact change:
  - `artivis-ass/4dea05393d4fcaa23bedee1d19481ca9.png`
  - `artivis-ass/4fde7dee62fd3b77b9026bbe3eda62d1.png`
  - `artivis-ass/5f1d3fbf73802d221dc80af588ea6875.png`
  - `artivis-ass/a90b2eb989b596b71ef046eb5868569a.png`
  - `artivis-ass/title.png`
- Before preparing a GitHub upload, public candidate, tag, or release, remind the user to review and update these files. Preserve the user's latest GitHub versions when assembling the release.

## Current 0.1.4 Handoff

- Before continuing ArtiChat 0.1.4 work, read `docs/progress/2026-07-14-artichat-0.1.4.md`, especially its `Next Session Handoff` section.
