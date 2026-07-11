# ArtiChat AWS / 1Panel 无干扰部署说明

## 目标

把本地 `localhost:3000` 已配置好的 ArtiChat 迁移到 AWS 服务器，并保留账号、外部模型配置、聊天记录、订阅、兑换码、礼品卡、公告、用量账本和知识库等运行数据。

生产环境使用 GHCR 不可变版本镜像，并通过受限 SSH 命令只更新 `artichat-prod` 服务。数据、备份和更新状态都保存在 `/data/artichat-prod` 下。

## 不影响现有服务的约定

- 使用独立容器名：`artichat-prod`。
- 使用独立数据目录：`/data/artichat-prod/data`。
- 默认宿主机端口：`13000`，避免占用 `80`、`443`、`3000`。
- 不修改 1Panel 已有应用、数据库、反向代理站点或现有 Docker 数据卷。
- 不挂载 Docker socket，不执行全局 Docker 清理，不操作其他 Compose 服务。
- 初次部署先用 `http://服务器IP:13000` 验证，确认无误后再在 1Panel 中配置域名反向代理。

## 本地数据备份

本地迁移备份放在仓库外或已忽略的目录：

```text
deploy-backups/
```

备份来自 Docker 数据卷 `artichat_data`，包含 ArtiChat 的运行数据。不要提交备份、数据库、`.env`、令牌或 SSH 密钥。

## 服务器初始化

上传以下文件到服务器上的同一临时目录：

```text
artichat-deploy.sh
artichat-deploy-ssh.sh
install-update-runner.sh
docker-compose.artichat-prod.yaml
```

生产 Compose 固定存放为：

```text
/data/artichat-prod/docker-compose.yaml
```

使用部署用户和 GitHub Actions 的 Ed25519 公钥执行一次 runner 安装：

```bash
sudo bash install-update-runner.sh \
  --user <deployment-user> \
  --public-key-file artichat-github-actions.pub
```

安装器会把两个执行脚本复制到 `/usr/local/sbin`，创建 `/data/artichat-prod/{data,backups,update-state}`，验证最小 sudoers 规则，并把公钥限制为固定部署命令。不要把私钥上传到服务器或仓库。

安装 Compose：

```bash
sudo install -m 0644 docker-compose.artichat-prod.yaml /data/artichat-prod/docker-compose.yaml
```

## 生产环境文件

`/data/artichat-prod/.env` 保存端口、密钥和更新配置：

```dotenv
ARTICHAT_PORT=13000
WEBUI_SECRET_KEY=从本地实例迁移的原值
ARTICHAT_UPDATE_REPOSITORY=<GitHub-owner>/ArtiChat
ARTICHAT_UPDATE_GITHUB_TOKEN=仅用于读取 Release 和触发部署 workflow 的令牌
```

如需覆盖从 `ARTICHAT_UPDATE_REPOSITORY` 推导的 GHCR 地址，可额外设置：

```dotenv
ARTICHAT_IMAGE_REPOSITORY=ghcr.io/<GitHub-owner>/artichat
```

`/data/artichat-prod/image.env` 只能保存当前不可变镜像：

```dotenv
ARTICHAT_IMAGE=ghcr.io/<GitHub-owner>/artichat:0.1.1
```

限制两个文件权限：

```bash
cd /data/artichat-prod
sudo chmod 600 .env image.env
```

## 恢复初始数据

把迁移备份上传到 `/data/artichat-prod`，确认 `/data/artichat-prod/data` 为空后再恢复：

```bash
cd /data/artichat-prod/data
sudo tar -xzf /data/artichat-prod/artichat_data_<timestamp>.tar.gz
```

`WEBUI_SECRET_KEY` 必须使用本地 ArtiChat 的原值，避免加密配置、OAuth 会话或登录令牌相关数据不一致。

- 如果本地使用的是外部中转站模型，只需要迁移 `artichat_data`。
- 如果本地还使用了 Ollama 本地模型，另需迁移 `artichat_ollama` 数据卷，并在服务器部署 Ollama。

## 启动与正常检查

首次启动或人工选择镜像后，只重建 ArtiChat 服务：

```bash
cd /data/artichat-prod
sudo docker compose --env-file .env --env-file image.env -f docker-compose.yaml up -d --no-deps --force-recreate artichat
```

每次更新后使用同一组显式环境文件检查服务：

```bash
cd /data/artichat-prod
sudo docker compose --env-file .env --env-file image.env -f docker-compose.yaml ps
curl -fsS http://127.0.0.1:13000/health
curl -fsS http://127.0.0.1:13000/api/version
```

`/api/version` 应返回当前版本和非 `dev-build` 的构建哈希。更新状态持久化在 `/data/artichat-prod/update-state/status.json`。

## 正常更新与备份

管理员从 ArtiChat 的“设置 -> 通用 -> 版本”发起更新后，服务器脚本会按以下固定顺序执行：

1. 拉取固定 GHCR 仓库中的目标版本镜像。
2. 停止且只停止 `artichat` 服务。
3. 备份 `/data/artichat-prod/data`。
4. 原子更新 `image.env` 并重建 `artichat`。
5. 检查 `/health` 和 `/api/version`。
6. 验证失败时自动恢复旧镜像和旧数据。

部署备份位于：

```text
/data/artichat-prod/backups
```

成功更新后只保留最近 3 份 `artichat-data-*.tar.gz` 备份，同时保留当前镜像和上一版本镜像。

## 紧急恢复

先查看当前状态和可用旧镜像：

```bash
cd /data/artichat-prod
sudo docker compose --env-file .env --env-file image.env -f docker-compose.yaml ps
sudo docker image ls 'ghcr.io/<GitHub-owner>/artichat'
sudo ls -lh /data/artichat-prod/backups
```

确认目标是已知可用的完整版本标签后，手动选择旧镜像并只重建 ArtiChat：

```bash
cd /data/artichat-prod
printf 'ARTICHAT_IMAGE=ghcr.io/<GitHub-owner>/artichat:<known-good-version>\n' | sudo tee image.env >/dev/null
sudo chmod 600 image.env
sudo docker compose --env-file .env --env-file image.env -f docker-compose.yaml up -d --no-deps --force-recreate artichat
curl -fsS http://127.0.0.1:13000/health
curl -fsS http://127.0.0.1:13000/api/version
```

若还需要恢复数据，先停止 `artichat`，把当前 `/data/artichat-prod/data` 移到同级临时目录，再将选定备份解压到新建的数据目录。确认旧版本健康后再删除临时目录。恢复前保留原目录，不要直接覆盖或递归删除整个 `/data/artichat-prod`。

## 1Panel 反向代理

服务验证通过后，再到 1Panel 中添加网站或反向代理，目标为：

```text
http://127.0.0.1:13000
```

如果已有网站正在使用 `80/443`，不要直接改动已有站点配置。建议新建独立站点或独立反向代理规则。

## 禁止操作

- 不要执行 `docker system prune --volumes`，它可能删除其他服务的数据卷。
- 不要执行 `docker compose down`，不要在任何清理命令中使用 `--volumes`。
- 不要挂载 `/var/run/docker.sock`。
- 不要删除其他 1Panel 创建的数据卷、容器或网络。
