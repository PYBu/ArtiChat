# ArtiChat Collaboration Rules

## Local Acceptance

- After completing an implementation task, build the current worktree and run it at `http://localhost:3000` for user acceptance before reporting the task as complete.
- Port 3000 is the required final local acceptance target. A disposable port such as 3001 may be used for isolated checks, but it does not replace the port-3000 handoff.
- Preserve the existing `artichat_data` Docker volume and the current container's runtime configuration when replacing the local acceptance container.
- Use a health-gated replacement with a rollback path. If the new container does not become healthy, restore the previous port-3000 container and report the failure.
- Do not push, tag, merge, publish a release, deploy to production, or modify production data without explicit user approval.
