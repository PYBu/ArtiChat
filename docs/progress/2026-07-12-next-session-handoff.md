# ArtiChat Next Session Handoff

Use this file to resume work in a new Codex session.

## Copy-Paste Prompt

```text
继续 ArtiChat 项目。

工作目录：C:\Users\admin\Desktop\Pro\ArtiChat\.worktrees\artichat-brand-whitelabel
Git 分支：artichat-brand-whitelabel

先完整读取：
docs/progress/2026-07-11-github-docker-update-system.md
docs/superpowers/plans/2026-07-11-artichat-github-docker-updates.md

Tasks 1-11 的本地实现和 0.1.2 Docker smoke 已完成。Dockerfile 已设置 `ONNXRUNTIME_NODE_INSTALL_CUDA=skip`，Slim 镜像成功构建；只重建了 artichat，`/health` 正常，`/api/version` 返回 0.1.2 和真实 build hash，artichat_data 中的关键数据计数保持不变。

下一步是外部发布阶段；开始前先确认用户明确授权。若暂不授权，不要进行任何 GitHub 或生产操作。

不要创建 GitHub 仓库、不要推送、不要安装或登录 gh、不要配置 Actions Secrets、不要修改 GHCR 可见性、不要操作生产服务器，也不要使用子代理。只有用户明确启动“外部发布/生产部署阶段”后，才从 Task 11 Step 5 和 Task 12 继续。
```

## Latest Commits

- `0ab2d02 feat: add restricted production update runner`
- `9d376ff ci: add ArtiChat release and deploy workflows`
- `df8490b release: prepare ArtiChat 0.1.2`
- `0d1118b chore: add sanitized public repository export`

## Verification Summary

- Source guards, frontend tests, 87 backend tests, full Vite build, Bash syntax, deploy harness, Compose rendering, workflow contracts, public export tests, and local Docker smoke passed.
- A normal public export produced one clean root commit and passed the secret scanner.
- Public GitHub creation, push, repository Secrets, GHCR publication, and production bootstrap remain intentionally deferred.
