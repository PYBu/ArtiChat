# ArtiChat AWS / 1Panel 无干扰部署说明

## 目标

把本地 `localhost:3000` 已配置好的 ArtiChat 迁移到 AWS 服务器，并保留账号、外部模型配置、聊天记录、订阅、兑换码、礼品卡、公告、用量账本和知识库等运行数据。

## 不影响现有服务的约定

- 使用独立容器名：`artichat-prod`。
- 使用独立数据卷：`artichat_prod_data`。
- 默认宿主机端口：`13000`，避免占用 `80`、`443`、`3000`。
- 不修改 1Panel 已有应用、数据库、反向代理站点或现有 Docker 数据卷。
- 初次部署先用 `http://服务器IP:13000` 验证，确认无误后再在 1Panel 中配置域名反向代理。

## 本地已生成的数据备份

本地备份目录：

```text
deploy-backups/
```

当前备份文件示例：

```text
artichat_data_20260706-185102.tar.gz
```

这个备份来自 Docker 数据卷 `artichat_data`，包含 ArtiChat 的运行数据。

## 服务器部署方式

### 方式 A：服务器构建镜像

适合服务器网络正常、可以拉取 npm/Python/Docker 依赖的情况。

1. 上传 ArtiChat 源码到服务器，例如 `/opt/artichat/source`。
2. 在服务器源码目录执行：

```bash
docker compose -p artichat-prod build artichat
```

3. 确认镜像存在：

```bash
docker images | grep artichat
```

### 方式 B：本地导出镜像再上传

适合服务器构建慢、网络不稳定，或希望服务器不重新下载构建依赖的情况。

本地导出：

```powershell
docker save artichat:main -o deploy-backups\artichat-main-image.tar
```

上传到服务器后导入：

```bash
docker load -i artichat-main-image.tar
```

这种方式文件会比较大，但服务器不需要重新构建镜像。

## 恢复数据卷

上传本地备份文件到服务器，例如：

```text
/opt/artichat/artichat_data_20260706-185102.tar.gz
```

创建独立数据卷：

```bash
docker volume create artichat_prod_data
```

恢复备份：

```bash
docker run --rm \
  -v artichat_prod_data:/to \
  -v /opt/artichat:/backup \
  alpine:3.20 \
  sh -c "cd /to && tar -xzf /backup/artichat_data_20260706-185102.tar.gz"
```

## 启动服务

把 `docker-compose.artichat-prod.yaml` 上传到服务器，例如：

```text
/opt/artichat/docker-compose.yaml
```

启动：

```bash
cd /opt/artichat
ARTICHAT_PORT=13000 docker compose -p artichat-prod up -d
```

检查容器：

```bash
docker ps --filter name=artichat-prod
```

检查健康状态：

```bash
curl http://127.0.0.1:13000/health
```

期望返回：

```json
{"status":true}
```

## 1Panel 反向代理

服务验证通过后，再到 1Panel 中添加网站或反向代理。

反向代理目标：

```text
http://127.0.0.1:13000
```

如果已有网站正在使用 `80/443`，不要直接改动已有站点配置。建议新建独立站点或独立反向代理规则。

## 回滚

如果新部署异常，直接停止并删除新容器，不会影响其他服务：

```bash
docker rm -f artichat-prod
```

如果确认不再需要新部署的数据卷，再删除：

```bash
docker volume rm artichat_prod_data
```

不要删除其他 1Panel 创建的数据卷。

## 注意

- 如果本地使用的是外部中转站模型，只需要迁移 `artichat_data`。
- 如果本地还使用了 Ollama 本地模型，另需迁移 `artichat_ollama` 数据卷，并在服务器部署 Ollama。
- 不要执行 `docker system prune --volumes`，它可能删除其他服务的数据卷。
