# ArtiChat

**ArtiChat 是一个可私有化部署的 AI 对话平台,支持接入多种大模型,开箱即用,数据自主可控。**

它可以完全离线运行,兼容 OpenAI 风格 API 与本地 Ollama 模型,内置检索增强(RAG)、多用户与权限管理、插件扩展等能力,适合团队与个人搭建属于自己的 AI 工作台。

> ArtiChat 基于开源项目 [Open WebUI](https://github.com/open-webui/open-webui) 二次开发,在其之上进行品牌化定制与功能演进。

![SvelteKit](https://img.shields.io/badge/frontend-SvelteKit-ff3e00?logo=svelte&logoColor=white)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/deploy-Docker-2496ed?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/python-3.11+-3776ab?logo=python&logoColor=white)

---

## 核心功能

- **多模型接入** — 兼容任意 OpenAI 风格 API(OpenAI、OpenRouter、vLLM、Groq、Mistral 等),同时支持本地 Ollama 模型,自由混用不同来源的模型。
- **检索增强(RAG)** — 内置文档解析与向量检索,可将本地文档、知识库注入对话上下文。
- **多用户与权限管理** — 基于角色的访问控制(RBAC)、用户组与细粒度权限,按团队需求分配访问范围。
- **插件与扩展** — 通过 Filters、Actions、Pipes、Tools 扩展能力,并支持 MCP、OpenAPI 工具服务器等外部集成。
- **智能体与模型编排** — 为基础模型叠加自定义指令、工具与知识,构建专用智能体。
- **笔记工作区** — 独立于对话的内容创作区,支持富文本编辑与 AI 改写,并可挂载到任意对话。
- **私有化与离线** — 全部功能可在本地或内网环境运行,数据留在自己的部署中。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | SvelteKit · TypeScript · Tailwind CSS · Vite |
| 后端 | Python · FastAPI · SQLAlchemy |
| 部署 | Docker · Docker Compose |

## 快速开始

推荐使用 Docker 部署,可将运行环境与主机隔离,免去本地依赖配置。

### 方式一:Docker Compose(推荐)

```bash
git clone https://github.com/PYBu/ArtiChat.git
cd ArtiChat

# 仅启动 ArtiChat 应用(不自动拉起 Ollama)
docker compose up -d --no-deps open-webui
```

启动后访问 [http://localhost:3000](http://localhost:3000),首次进入即可完成管理员账号初始化。

健康检查:

```bash
curl http://localhost:3000/health
# {"status":true}
```

> 默认将主机 `3000` 端口映射到容器内 `8080` 端口。可通过环境变量 `OPEN_WEBUI_PORT` 修改主机端口。
> 若需同时启动本地 Ollama 服务,去掉 `--no-deps` 即可(会一并拉起 `ollama` 容器)。

### 方式二:本地开发

需要 **Node.js `>=18.13 <=22`** 与 **Python 3.11+**。

前端:

```bash
npm install
npm run dev          # 开发服务器
npm run build        # 生产构建
```

后端:

```bash
cd backend
pip install -r requirements.txt
bash start.sh        # 或参考 backend/ 下的启动脚本
```

## 配置

复制示例环境文件并按需修改:

```bash
cp .env.example .env
```

常用环境变量:

| 变量 | 说明 |
| --- | --- |
| `OPENAI_API_BASE_URL` | OpenAI 兼容 API 地址 |
| `OPENAI_API_KEY` | 对应 API 密钥 |
| `OLLAMA_BASE_URL` | 本地 Ollama 服务地址(默认 `http://localhost:11434`) |
| `WEBUI_SECRET_KEY` | 会话签名密钥,生产环境务必设置 |
| `CORS_ALLOW_ORIGIN` | 允许的跨域来源,生产环境应收紧 |
| `OPEN_WEBUI_PORT` | Docker 部署时映射到主机的端口 |

> **安全提示**:生产部署请务必设置 `WEBUI_SECRET_KEY`,并将 `CORS_ALLOW_ORIGIN` 从默认的 `*` 收紧为实际来源域名。

## 目录结构

```
ArtiChat/
├── src/                 # 前端(SvelteKit)
├── backend/             # 后端(FastAPI)
├── static/              # 静态资源与品牌图标
├── artivis-ass/logo/    # ArtiChat 品牌 Logo 资产
├── scripts/             # 构建与工具脚本
├── docs/                # 设计文档与进度记录
├── docker-compose.yaml  # Docker 编排
└── Dockerfile
```

## 关于 Open WebUI

ArtiChat 以 [Open WebUI](https://github.com/open-webui/open-webui) 为基础进行开发。仓库保留了指向上游的 `upstream` 远程,便于后续同步与审计。上游版权与许可信息保留在 [`LICENSE`](LICENSE)、[`LICENSE_NOTICE`](LICENSE_NOTICE) 与 [`LICENSE_HISTORY`](LICENSE_HISTORY) 中。

## 许可证

本项目沿用上游的多许可证约定,详见 [`LICENSE`](LICENSE) 与 [`LICENSE_NOTICE`](LICENSE_NOTICE)。使用与分发前请阅读相关许可条款。
