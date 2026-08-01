<div align="center">

![ArtiChat Banner](artivis-ass/new/ntitle.png)

# ArtiChat

**企业级私有化定制的 AI 对话平台**

<kbd>开箱即用</kbd> &nbsp; <kbd>订阅计费</kbd> &nbsp; <kbd>体验优化</kbd> &nbsp; <kbd>企业适用</kbd> &nbsp; <kbd>原版优化</kbd>

<br/>

[![Version](https://img.shields.io/badge/version-0.2.0-6366f1?style=flat-square)](https://github.com/PYBu/ArtiChat/releases)
[![OpenWebUI](https://img.shields.io/badge/based_on-OpenWebUI_0.11.0-0ea5e9?style=flat-square)](https://github.com/open-webui/open-webui)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![SvelteKit](https://img.shields.io/badge/SvelteKit-frontend-FF3E00?style=flat-square&logo=svelte&logoColor=white)](https://kit.svelte.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

[![官网](https://img.shields.io/badge/官网-chat.artivis.cc-22c55e?style=flat-square&logo=safari&logoColor=white)](https://chat.artivis.cc)

</div>

<br/>

> 注意：本项目版本为 ArtiChat ProEdition 0.2+ ，次代版本为 ArtiChat ArtivisAlpha 0.1+（0.1.7为已发布最新版），0.2 版本历经重做存在一些不稳定因素或Bug，但 0.1 系列版本仍然可以无缝更新到 0.2，若稳定使用建议依旧使用 0.1 版本，或等待 0.2 正式版本发布以后选择更新！

## 简介

ArtiChat 是由 **Artivis Studio** 基于 [OpenWebUI 0.11.0](https://github.com/open-webui/open-webui) 深度定制的私有 AI 对话平台。在保留 OpenWebUI 强大对话能力的基础上，ArtiChat 引入了完整的**订阅计费体系**、**用户权限管理**和**用户体验优化**，帮助团队或 SaaS 产品快速搭建一套自主可控的 AI 服务，适用于绝大多数的大模型分发计费商业化以及企业、团队内部模型的使用。

> ⚠️ **商业部署须知** — 超过 50 名用户或用于商业用途，请遵循 [OpenWebUI 许可协议](https://github.com/open-webui/open-webui/blob/main/LICENSE) 并向 OpenWebUI 官方获取授权。

<br/>

![主界面](artivis-ass/new/1.png)

---

<br/>

<table>
<tr>
<td width="50%" valign="top">

**💳 &nbsp;订阅计费系统**

四类 Token 精细计价，覆盖推理全链路成本：

- **Input** · **Output** · **Cache Create** · **Cache Read**
- 礼品卡 & 兑换码发放与核销
- 用量审计，消费明细随时可查

</td>
<td width="50%" valign="top">

**⚡ &nbsp;推理强度调节**

针对高阶模型的智能调度控制：

- 五档强度：**Low → Balanced → High → Ultra → Max**
- 专为Claude 与 Codex 系列优化
- 一键切换，无需修改任何配置

</td>
</tr>
<tr>
<td width="50%" valign="top">

**👥 &nbsp;权限管理（RBAC）**

灵活的多级角色体系，精准控制访问边界：

- 多级用户组与角色分配
- 邮箱验证注册流程
- 模型与功能的细粒度权限控制

</td>
<td width="50%" valign="top">

**🛒 &nbsp;模型市场**

统一的模型入口，清晰呈现资源信息：

- 集中展示全部可用模型
- 显示各模型定价与访问条件
- 用户自助完成模型套餐订阅

</td>
</tr>
<tr>
<td width="50%" valign="top">

**🎨 &nbsp;白标定制**

部署即品牌，零代码完成外观替换：

- 平台名称、Logo 可视化配置
- About 页面内容完全自定义
- 适合 SaaS 独立品牌化运营

</td>
<td width="50%" valign="top">

**🐳 &nbsp;开箱即用**

极简部署，专注业务而非运维：

- 单命令 Docker Compose 启动
- 已移除 Ollama 依赖，镜像更轻量
- SvelteKit + FastAPI + SQLAlchemy 全栈

</td>
</tr>
</table>

---

## 📸 &nbsp;界面预览

<br/>

<table>
<tr>
<td width="50%">

![功能截图](artivis-ass/new/s1.png)

</td>
<td width="50%">

![功能截图](artivis-ass/new/s2.png)

</td>
</tr>
<tr>
<td width="50%">

![功能截图](artivis-ass/new/s3.png)

</td>
<td width="50%">

![功能截图](artivis-ass/new/s4.png)

</td>
</tr>
<tr>
<td width="50%">

![功能截图](artivis-ass/new/s5.png)

</td>
<td width="50%">

![功能截图](artivis-ass/new/s6.png)

</td>
</tr>
</table>

<br/>

<table>
<tr>
<td width="50%">

![后台截图](artivis-ass/new/a1.png)

</td>
<td width="50%">

![后台截图](artivis-ass/new/a2.png)

</td>
</tr>
<tr>
<td width="50%">

![后台截图](artivis-ass/new/a3.png)

</td>
<td width="50%">

![后台截图](artivis-ass/new/a4.png)

</td>
</tr>
</table>

<br/>

![用量统计](artivis-ass/new/usage.png)

<br/>

![用户管理](artivis-ass/new/user.png)

<br/>

![订阅页面](artivis-ass/new/sub.png)

<br/>

![登录页面](artivis-ass/new/dy.png)

<br/>

---

## 🎨 &nbsp;设计小巧思

为每一处小细节增添一丝丝设计乐趣。

<br/>

<table>
<tr>
<td width="50%" align="center" valign="top">

**环状额度组件**

直观呈现剩余额度，一眼掌握用量状态。
<br>
 -来自 Minier Buper 的建议。

![环状额度组件](https://github.com/PYBu/ArtiChat/raw/main/artivis-ass/a90b2eb989b596b71ef046eb5868569a.png)

</td>
<td width="50%" align="center" valign="top">

**思考强度动画**

五档强度切换配合流畅过渡动效，操作即反馈。
<br>
 -学习 Codex /CC 的强度动画。

![思考强度动画](artivis-ass/new/ed.png)

</td>
</tr>
</table>

<br/>

---

## 💬 &nbsp;参与反馈

ArtiChat 的每一次迭代都来自用户的真实声音。如果你遇到了Bug、有新功能想法，或者只是想聊聊使用体验——欢迎到反馈站告诉我们，我们很期待社区以及用户的声音！本项目历经 0.1 到 0.2 的系统性升级，可能存在不少Bug，但是我依旧会坚持更新（感情牌）！

<div align="center">

<br/>

[![前往反馈站](https://img.shields.io/badge/前往反馈站提交反馈-chatbug.artivis.cc-f59e0b?style=for-the-badge&logo=gitbook&logoColor=white)](https://chatbug.artivis.cc)

<br/>

</div>

---

## 🚀 &nbsp;快速部署

### 环境要求

| 依赖 | 版本要求 |
|:-----|:--------|
| Docker | 20.10+ |
| Docker Compose | v2.x |
| 服务器内存 | ≥ 2 GB（推荐 4 GB+） |
| 网络 | 可访问目标 AI API |

### 一键启动

```bash
# 1. 克隆仓库
git clone https://github.com/PYBu/ArtiChat.git
cd ArtiChat

# 2. 启动服务（首次构建约需 3–5 分钟）
docker compose -p artichat up -d --build artichat
```

启动完成后访问 **[http://localhost:3000](http://localhost:3000)**，首次进入即可完成管理员账号初始化。

健康检查：

```bash
curl http://localhost:3000/health
# {"status":true}
```

<br/>

### 生产环境配置

| 参数 | 说明 | 默认值 |
|:-----|:-----|:------|
| `WEBUI_SECRET_KEY` | 会话加密密钥，**生产必须修改** | 空（不安全） |
| `CORS_ALLOW_ORIGIN` | 跨域来源白名单 | `*`（不安全） |
| `DATABASE_URL` | 数据库连接字符串 | SQLite 本地文件 |
| `OPENAI_API_BASE_URL` | OpenAI 兼容 API 地址 | — |
| `OPENAI_API_KEY` | 对应 API 密钥 | — |

> 💡 生产环境务必将 `CORS_ALLOW_ORIGIN` 从默认的 `*` 收紧为实际域名，并随机生成 `WEBUI_SECRET_KEY`。

<br/>

---

## 🗺️ &nbsp;路线图

```
v0.1.0 - v0.1.8  ✅  底层适配与修改，加固与ArtiChat稳定运行。
v0.2.0 - now     ✅  系统性升级，ArtiChat组件UI重置与完善，以新功能与用户体验作为优先更新动力。

v0.3.0           🔜  ArtiLINK — 本地 MCP 接入，让模型直接操控 PowerShell 与本地系统资源，实现真正意义上的「网页版 Codex」
```

<br/>

---

## 🛠️ &nbsp;技术栈

<div align="center">

| 层级 | 技术选型 |
|:----:|:--------|
| **前端** | SvelteKit · TypeScript · Tailwind CSS · Vite |
| **后端** | FastAPI · SQLAlchemy · Python 3.11+ |
| **基础平台** | OpenWebUI 0.11.0 |
| **容器化** | Docker · Docker Compose |

</div>

<br/>

---

## 🙏 &nbsp;致谢

感谢以下项目与社区对 ArtiChat 的支持与启发：

[**OpenWebUI**](https://github.com/open-webui/open-webui) — ArtiChat 的基础平台，提供了强大的对话界面与工程底座

[**Linux.Do 社区**](https://linux.do) — 感谢社区成员的反馈、讨论与持续支持

<br/>

---

## 📄 &nbsp;开源声明

本项目基于 [OpenWebUI](https://github.com/open-webui/open-webui) 进行二次开发，遵循其许可协议。上游版权与许可信息保留在 [`LICENSE`](LICENSE)、[`LICENSE_NOTICE`](LICENSE_NOTICE) 与 [`LICENSE_HISTORY`](LICENSE_HISTORY) 中。**超过 50 名用户的部署或任何商业用途，请直接联系 OpenWebUI 官方获取授权。**

<br/>

---

<div align="center">

Built with ❤️ by &nbsp;<strong>Artivis Studio</strong> | <b>Art</b> W<b>i</b>th <b>Vis</b>ion

</div>
