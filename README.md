# ArtiChat

**ArtiChat 是一个可私有化部署的 AI 对话平台，支持接入多种大模型，开箱即用，数据自主可控。**

它可以完全离线运行，兼容 OpenAI 风格 API 与本地 Ollama 模型，内置检索增强（RAG）、多用户与权限管理、插件扩展等能力，适合团队与个人搭建自己的 AI 工作台。

![SvelteKit](https://img.shields.io/badge/frontend-SvelteKit-ff3e00?logo=svelte&logoColor=white)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/deploy-Docker-2496ed?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/python-3.11+-3776ab?logo=python&logoColor=white)

![ArtiChat 界面](artivis-ass/b6b57ca1dac196f47880bdfdba3bc0e8.png)

## 核心功能

- **上游兼容**：保留原有对话、知识库、工具和模型接入能力。
- **订阅与用量**：支持订阅计划、Chatpoint 额度、四类 Token 计价和用量审计。
- **用户与权限**：支持角色访问控制（RBAC）、用户组、管理员用户管理和细粒度模型权限。
- **注册与邮件**：支持注册域名限制、邮箱验证码登录、密码重置、SMTP 和邮件模板管理。
- **插件与扩展**：通过 Filters、Actions、Pipes、Tools 扩展能力，并支持 MCP、OpenAPI 工具服务器等外部集成。
- **智能体与模型编排**：为基础模型叠加自定义指令、工具与知识，构建专用智能体。
- **笔记工作区**：独立于对话的内容创作区，支持富文本编辑与 AI 改写，并可挂载到任意对话。
- **私有化与离线**：全部功能可在本地或内网环境运行，数据保留在自己的部署中。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | SvelteKit · TypeScript · Tailwind CSS · Vite |
| 后端 | Python · FastAPI · SQLAlchemy |
| 部署 | Docker · Docker Compose |

## 快速开始

推荐使用 Docker 部署，可将运行环境与主机隔离，免去本地依赖配置。

### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/PYBu/ArtiChat.git
cd ArtiChat

# 构建并启动 ArtiChat
docker compose -p artichat up -d --build artichat
```

启动后访问 [http://localhost:3000](http://localhost:3000)，首次进入即可完成管理员账号初始化。

健康检查：

```bash
curl http://localhost:3000/health
# {"status":true}
```

> 默认将主机 `3000` 端口映射到容器内 `8080` 端口，可通过环境变量 `ARTICHAT_PORT` 修改主机端口。Compose 只运行 ArtiChat；如需使用 Ollama，请连接主机或其他服务器上已有的 Ollama 服务。

### 方式二：本地开发

需要 **Node.js `>=18.13 <=22`** 与 **Python 3.11+**。

前端：

```bash
npm install
npm run dev
npm run build
```

后端：

```bash
cd backend
pip install -r requirements.txt
bash start.sh
```

## 配置

复制示例环境文件并按需修改：

```bash
cp .env.example .env
```

常用环境变量：

| 变量 | 说明 |
| --- | --- |
| `OPENAI_API_BASE_URL` | OpenAI 兼容 API 地址 |
| `OPENAI_API_KEY` | 对应 API 密钥 |
| `OLLAMA_BASE_URL` | 本地 Ollama 服务地址 |
| `WEBUI_SECRET_KEY` | 会话及敏感配置加密密钥，生产环境务必设置并保持稳定 |
| `CORS_ALLOW_ORIGIN` | 允许的跨域来源，生产环境应收紧 |
| `ARTICHAT_PORT` | Docker 部署时映射到主机的端口 |

> 生产部署请务必设置稳定的 `WEBUI_SECRET_KEY`，并将 `CORS_ALLOW_ORIGIN` 从默认的 `*` 收紧为实际来源域名。

## 目录结构

```text
ArtiChat/
├── src/                 # 前端（SvelteKit）
├── backend/             # 后端（FastAPI）
├── static/              # 静态资源与品牌图标
├── artivis-ass/         # ArtiChat 品牌与文档资产
├── scripts/             # 构建与工具脚本
├── docs/                # 安全说明、知识文本与发布说明
├── docker-compose.yaml  # Docker 编排
└── Dockerfile
```

## 第三方许可

第三方版权与许可信息保留在 [`LICENSE`](LICENSE)、[`LICENSE_NOTICE`](LICENSE_NOTICE) 与 [`LICENSE_HISTORY`](LICENSE_HISTORY) 中。

## 许可证

本项目沿用上游的多许可证约定，详见 [`LICENSE`](LICENSE) 与 [`LICENSE_NOTICE`](LICENSE_NOTICE)。使用与分发前请阅读相关许可条款。
