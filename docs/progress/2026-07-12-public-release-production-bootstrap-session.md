# 2026-07-12 Public Release And Production Bootstrap Session

## Scope

This session resumed the completed local ArtiChat update-system implementation and executed the explicitly authorized external publication and production bootstrap phase. No subagents were used.

## Starting State

- Internal worktree: `.worktrees/artichat-brand-whitelabel`.
- Internal branch: `artichat-brand-whitelabel`.
- Prepared version: `0.1.2`.
- Local Docker smoke was already complete.
- Public repository, GHCR release, Actions Secrets, restricted deployment key, and production update runner did not exist yet.
- Production was healthy on `0.1.1` with data mounted from `/data/artichat-prod/data`.

## Public Repository

- GitHub CLI was already installed and authenticated as `PYBu`.
- A clean public export was generated at `C:\Users\admin\Desktop\Pro\ArtiChat-public`.
- The export passed the built-in scanner plus the local `.public-forbidden-values` check.
- The export contained one clean root commit, `672d2a9ec811495bf3a0b07ff3d606de19204c5e`.
- Internal `docs/progress`, `docs/superpowers`, backups, and worktrees were absent.
- Licenses, release notes, workflows, deployment scripts, and tests were present.
- Public repository created: `https://github.com/PYBu/ArtiChat`.
- Public `main` and local `public-main` point to the clean root history.

## GitHub Deployment Configuration

- Generated a dedicated Ed25519 key outside the repository under the user SSH directory.
- Configured these repository Secrets without logging their values:
  - `ARTICHAT_DEPLOY_HOST`
  - `ARTICHAT_DEPLOY_USER`
  - `ARTICHAT_DEPLOY_SSH_KEY`
  - `ARTICHAT_DEPLOY_KNOWN_HOSTS`
- Verified the production ED25519 host key against the existing trusted record.
- Installed `/usr/local/sbin/artichat-deploy` and `/usr/local/sbin/artichat-deploy-ssh`.
- Installed and validated the minimal sudoers rule.
- Installed exactly one forced-command deployment key entry.
- Verified that the deployment key rejects arbitrary SSH commands with `unsupported command`.
- Stored the new fine-grained updater token only in production `.env` and deleted the local temporary token file.
- Verified the token from both the operator machine and the production container against the active deployment workflow.

## Release 0.1.2

- Pushed annotated tag `v0.1.2` from the clean public root commit.
- GitHub Actions run: `https://github.com/PYBu/ArtiChat/actions/runs/29164990277`.
- Run result: success.
- Passed version, branding, subscription, update-system, frontend, and application-build checks.
- Built and pushed the immutable linux/amd64 image.
- Published Release: `https://github.com/PYBu/ArtiChat/releases/tag/v0.1.2`.
- Image: `ghcr.io/pybu/artichat:0.1.2`.
- Digest: `sha256:c427117c479e8dc028863dc3bc9241a7d367d2b6b3246cc36f95ad209fda4393`.
- Build hash: `672d2a9ec811495bf3a0b07ff3d606de19204c5e`.
- Anonymous registry manifest access returned HTTP 200.

## Production Disk Expansion

- The first production pull failed before deployment with `no space left on device` while extracting an image layer.
- No container stop, data backup, or data mutation had occurred at that point.
- Root Docker storage was on the 20 GiB root EBS volume and had about 5 GiB free.
- All four existing images were active, so deleting them was not a safe remediation.
- The user expanded the root EBS volume from 20 GiB to 40 GiB.
- Verified `/dev/nvme0n1` was 40 GiB while `/dev/nvme0n1p1` was still 18.9 GiB.
- Ran `growpart /dev/nvme0n1 1` and `resize2fs /dev/nvme0n1p1` online.
- Root ext4 filesystem became 37.6 GiB with about 24.4 GiB free immediately after growth.
- ArtiChat remained healthy on `0.1.1` throughout the filesystem expansion.
- The second anonymous image pull succeeded and matched the public digest.

## Production Bootstrap

- Operation ID: `bootstrap-0.1.2-20260711T194923Z`.
- The restricted deploy script pulled the fixed image, stopped only ArtiChat, backed up the data directory, recreated the service, and verified health/version.
- Deployment state finished with:
  - stage: `completed`
  - active: `false`
  - previous version: `0.1.1`
  - target version: `0.1.2`
  - error: `null`
- Verified backup:
  - `/data/artichat-prod/backups/artichat-data-20260711-194930-bootstrap-0.1.2-20260711T194923Z.tar.gz`
  - size: 987,543,082 bytes
  - `gzip -t`: passed
  - full tar listing: passed
- Production container:
  - image: `ghcr.io/pybu/artichat:0.1.2`
  - state: running
  - health: healthy
  - no Docker socket mount
  - fixed data and update-state bind mounts only
- `/health` returned true.
- `/api/version` returned `0.1.2 (Artivis Alpha)` and the public release build hash.
- The update API rejected unauthenticated access with HTTP 401.
- SearXNG, Valkey, and 1Panel OpenResty containers were not restarted.

## Data Persistence Verification

The same 20 recorded business-table counts were collected immediately before and after deployment. Every count remained identical, including:

- users: 10
- chats: 12
- chat messages: 51
- files: 8
- knowledge bases: 1
- user subscriptions: 10
- subscription ledger entries: 72
- subscription usage rows: 126
- subscription plans: 3
- redemption codes: 5
- redemption records: 2
- gift-card grants: 3
- announcements: 1

The remaining recorded zero/non-zero related table counts also matched exactly.

## Next-Update Path

- The production container can read the active deploy workflow with its scoped updater token.
- `artichat-deploy.yml` currently has no validated `dry_run` input.
- No test workflow dispatch was made.
- Deploy workflow run count remains zero.
- The first real administrator-triggered update should be `v0.1.3`.

## Final Automated Verification

- Release version guard: passed.
- Branding guard: passed for 155 files.
- Subscription guard: passed.
- Update-system guard: passed.
- Backend tests: 87 passed with one existing SQLAlchemy deprecation warning.
- Frontend tests: 3 passed.
- Deployment harness: passed.
- Full Vite build: passed with existing non-fatal Svelte/Vite warnings.
- Internal worktree: clean after commit.
- Public working tree: clean and tracking `origin/main`.
- Internal session record commit before this note: `a1bbddc docs: record public 0.1.2 bootstrap`.

## Remaining Manual Checks

1. Log in as a production administrator and spot-check accounts, chats, model connections, subscriptions, balances, announcements, redemption codes, gift cards, uploads, and knowledge data through the UI.
2. Confirm the fine-grained token that was exposed in the conversation before replacement is revoked in GitHub settings.
3. Do not create a new version, push another release tag, or operate production again without explicit user authorization.

## Resume Point

After the two manual confirmations above, mark the `0.1.2` bootstrap fully complete. Future release work should use the clean public history and should prepare `v0.1.3` as the first administrator-triggered deployment-path test.
