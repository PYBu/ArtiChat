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

Tasks 1-11 和 Task 12 的自动化生产引导已完成。公开仓库为 https://github.com/PYBu/ArtiChat，v0.1.2 Release 和公开 GHCR 镜像已发布。生产服务器已安装受限更新 runner，并通过 operation `bootstrap-0.1.2-20260711T194923Z` 更新到 0.1.2；健康、真实 build hash、备份完整性和 20 项业务表计数均已验证。管理员登录后的 UI 数据抽查仍待人工完成。

根 EBS 卷已从 20 GiB 扩到 40 GiB，根 ext4 文件系统在线扩到 37.6 GiB。生产备份路径和完整结果记录在 docs/progress/2026-07-11-github-docker-update-system.md。

下一步只需完成管理员登录后的 UI 数据抽查。未来公开发布工作使用 public-main；第一次管理员触发的真实自动更新应从 v0.1.3 开始。未经用户明确授权，不要创建新版本、推送新标签或再次操作生产服务器，也不要使用子代理。
```

## Latest Commits

- `0ab2d02 feat: add restricted production update runner`
- `9d376ff ci: add ArtiChat release and deploy workflows`
- `df8490b release: prepare ArtiChat 0.1.2`
- `0d1118b chore: add sanitized public repository export`
- `d6a2a7d fix: skip unused onnxruntime CUDA download`

## Verification Summary

- Source guards, frontend tests, 87 backend tests, full Vite build, Bash syntax, deploy harness, Compose rendering, workflow contracts, public export tests, local Docker smoke, GitHub release workflow, and production bootstrap passed.
- A normal public export produced one clean root commit and passed the secret scanner.
- Public repository, deployment Secrets, public GHCR image, production backup, `0.1.2` health/version, updater token, and unchanged database counts were verified.
