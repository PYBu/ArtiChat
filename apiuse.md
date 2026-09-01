<div align="center">

![ArtiChat API](artivis-ass/new/ntitle.png)

# ArtiChat 0.3.0 API 开发指南

[![返回主文档](https://img.shields.io/badge/←_返回-主文档-6366f1?style=flat-square)](readme.md)
[![English](https://img.shields.io/badge/English-Documentation-10b981?style=flat-square)](readme-en.md)

**插件开发 · 模型集成 · 前端扩展 · 客户端对接**

</div>

<br/>

---

> **代码基线：** `artichat-0.3.0`  
> **面向对象：** 插件开发者、模型提示词工程师、前端扩展开发者、外部客户端集成工程师

本文档提供 ArtiChat 0.3.0 的完整 API 参考，所有变量和路由均以当前源码为准。接口的实际可用性受权限、功能开关、模型能力和订阅状态影响。

---

## 📋 目录

1. [提示词变量系统](#1-提示词变量系统)
2. [HTTP API 总览](#2-http-api-总览)
3. [模型内置工具](#3-模型内置工具函数调用)
4. [二次开发建议](#4-二开建议)
5. [代码定位索引](#5-代码定位)

---

## 1. 提示词变量系统

### 1.1 通用运行时变量

这些变量在系统提示词、任务提示词和聊天输入预处理阶段可用，用于动态注入上下文信息。

<br/>

<details>
<summary><b>📅 时间与日期变量</b></summary>

| 变量 | 含义 | 示例 |
| --- | --- | --- |
| `{{CURRENT_DATE}}` | 当前日期 | `2026-09-01` |
| `{{CURRENT_TIME}}` | 当前时间 | `02:30:45 PM` |
| `{{CURRENT_DATETIME}}` | 日期时间组合 | `2026-09-01 02:30:45 PM` |
| `{{CURRENT_WEEKDAY}}` | 星期英文名 | `Monday` |
| `{{CURRENT_TIMEZONE}}` | 浏览器时区 | `Asia/Shanghai` |

</details>

<details>
<summary><b>👤 用户信息变量</b></summary>

| 变量 | 含义 | 备注 |
| --- | --- | --- |
| `{{USER_NAME}}` | 当前用户名称 | 未设置时为 `Unknown` |
| `{{USER_EMAIL}}` | 用户邮箱 | 未设置时为 `Unknown` |
| `{{USER_BIO}}` | 用户简介 | — |
| `{{USER_GENDER}}` | 用户性别 | — |
| `{{USER_BIRTH_DATE}}` | 用户出生日期 | — |
| `{{USER_AGE}}` | 根据出生日期计算的年龄 | — |
| `{{USER_LOCATION}}` | 用户位置 | 前端和后端均支持 |
| `{{USER_GROUPS}}` | 用户所属组 | 逗号分隔，如 `admin,vip` |
| `{{USER_LANGUAGE}}` | 前端语言区域 | 如 `zh-CN`，由前端处理 |

> ⚠️ 未登录或缺少用户资料时，字段使用 `Unknown` 或空字符串，**不能作为鉴权凭据**。

</details>

<br/>

### 1.2 消息与上下文变量

用于处理当前对话、历史消息和检索上下文。

<details>
<summary><b>💬 提示词处理变量</b></summary>

| 变量 | 含义 | 示例 |
| --- | --- | --- |
| `{{prompt}}` | 当前用户提示词 | 大小写不敏感 |
| `{{prompt:start:N}}` | 提示词前 N 个字符 | `{{prompt:start:100}}` |
| `{{prompt:end:N}}` | 提示词后 N 个字符 | `{{prompt:end:50}}` |
| `{{prompt:middletruncate:N}}` | 中间截断，保留 N 字符 | `{{prompt:middletruncate:200}}` |

</details>

<details>
<summary><b>📜 消息列表变量</b></summary>

| 变量 | 含义 | 组合示例 |
| --- | --- | --- |
| `{{MESSAGES}}` | 完整消息列表文本 | — |
| `{{MESSAGES:START:N}}` | 前 N 条消息 | `{{MESSAGES:START:5}}` |
| `{{MESSAGES:END:N}}` | 后 N 条消息 | `{{MESSAGES:END:10}}` |
| `{{MESSAGES:MIDDLETRUNCATE:N}}` | 保留首尾，总数不超过 N | `{{MESSAGES:MIDDLETRUNCATE:8}}` |
| `{{MESSAGES\|start:N}}` | 每条消息截取前 N 字符 | `{{MESSAGES:END:6\|start:500}}` |
| `{{MESSAGES\|end:N}}` | 每条消息截取后 N 字符 | — |
| `{{MESSAGES\|middletruncate:N}}` | 每条消息中间截断 | `{{MESSAGES:END:6\|middletruncate:1200}}` |

**组合使用示例：**
```
请根据 {{MESSAGES:END:6|middletruncate:1200}} 总结，并回答 {{prompt:middletruncate:800}}
```

</details>

<details>
<summary><b>🔍 检索与工具变量</b></summary>

| 变量 | 含义 |
| --- | --- |
| `{{CONTEXT}}` / `[context]` | RAG 检索得到的上下文 |
| `{{QUERY}}` / `[query]` | RAG 或网页检索查询 |
| `{{TOOLS}}` | 当前注入给模型的工具规格 |
| `{{TYPE}}` | 自动补全任务的类型 |
| `{{responses}}` | MOA 多模型汇总任务的候选回答 |

</details>

<br/>

### 1.3 上下文压缩变量

用于上下文压缩提示词，支持消息范围/过滤语法。

| 变量 | 含义 |
| --- | --- |
| `{{COMPACTED_MESSAGES}}` | 已被压缩的旧消息 |
| `{{RECENT_MESSAGES}}` | 保留在摘要外的最近消息 |
| `{{PREVIOUS_SUMMARY}}` | 上一次压缩产生的摘要 |

<br/>

### 1.4 聊天变量与用户变量 <sup>0.3.0</sup>

系统提示词可声明模型运行时输入，支持类型校验和默认值。

**声明语法：**
```text
项目名称：{{chat.variables.project}}
输出格式：{{chat.variables.format | type=select:options=[“markdown”,”json”]:default=”markdown”}}
最大结果数：{{chat.variables.max_results | type=number:min=1:max=100:default=10}}
```

<details>
<summary><b>变量类型与参数</b></summary>

| 变量类型 | 参数 | 说明 |
| --- | --- | --- |
| `{{chat.variables.<key>}}` | `type`, `label`, `default`, `required`, `options`, `min`, `max`, `step`, `placeholder` | 本次聊天/模型提示词的变量 |
| `{{user.variables.<key>}}` | 只接受字符串值 | 用户保存的自定义变量 |

> **命名规则：** `<key>` 必须匹配正则 `^[a-z][a-z0-9_]*$`（小写字母开头，仅含小写字母、数字、下划线）

**行为：**
- 未提供的非必填变量渲染为空
- 必填变量或非法 `select` 值会被拒绝/清空
- 调用方应先读取变量 schema

</details>

<br/>

### 1.5 ArtiChat 平台与订阅变量 <sup>0.3.0</sup>

在系统提示词解析阶段，服务端按当前用户订阅状态注入的计费相关变量。

<details>
<summary><b>💳 订阅状态变量</b></summary>

| 变量 | 含义 |
| --- | --- |
| `{{ARTICHAT_PLATFORM_CONTEXT}}` | ArtiChat 平台知识说明<sup>[内置资源]</sup> |
| `{{ARTICHAT_SUBSCRIPTION_CONTEXT}}` | 包含套餐、等级、状态、余额、用量和重置时间的完整上下文 |
| `{{USER_SUBSCRIPTION}}` | 当前套餐显示名 |
| `{{USER_SUBSCRIPTION_TIER}}` | 套餐等级标识 |
| `{{USER_SUBSCRIPTION_STATUS}}` | 套餐状态（active/expired/pending） |
| `{{USER_SUBSCRIPTION_EXPIRES_AT}}` | 套餐到期时间，无期限时为 `Never` |

</details>

<details>
<summary><b>📊 计费周期变量</b></summary>

| 变量 | 含义 |
| --- | --- |
| `{{USER_SUBSCRIPTION_PERIOD_START_AT}}` | 当前计费周期起始时间 |
| `{{USER_SUBSCRIPTION_PERIOD_END_AT}}` | 当前计费周期结束时间 |
| `{{USER_SUBSCRIPTION_NEXT_RESET_AT}}` | 下次套餐额度重置时间 |

</details>

<details>
<summary><b>💰 Chatpoint 余额变量</b></summary>

| 变量 | 含义 |
| --- | --- |
| `{{PLAN_CHATPOINT_ALLOWANCE}}` | 周期内套餐 Chatpoint 总额度 |
| `{{PLAN_CHATPOINT_BALANCE}}` | 套餐余额 |
| `{{PLAN_CHATPOINT_USED}}` | 本周期已使用的套餐额度 |
| `{{CHECK_CHATPOINT_BALANCE}}` | Check Chatpoint 余额（一次性充值） |
| `{{TOTAL_CHATPOINT_BALANCE}}` / `{{CHATPOINT_BALANCE}}` | 套餐余额 + Check 余额 |
| `{{CHATPOINT_QUOTA_EXHAUSTED}}` | 是否耗尽，值为 `true` 或 `false` |

</details>

> 💡 **无用户身份时**不会生成订阅上下文。

<br/>

### 1.6 自定义请求头变量

用于”自定义连接/请求头”模板，**不是**普通模型提示词变量。

<details>
<summary><b>🔐 请求头可用变量</b></summary>

| 变量分类 | 变量列表 |
| --- | --- |
| **会话相关** | `{{CHAT_ID}}`, `{{MESSAGE_ID}}`, `{{USER_MESSAGE_ID}}`, `{{USER_MESSAGE_PARENT_ID}}` |
| **文件相关** | `{{FILE_ID}}`, `{{FILE_NAME}}`, `{{FILE_CONTENT_TYPE}}` |
| **用户相关** | `{{USER_ID}}`, `{{USER_NAME}}`, `{{USER_EMAIL}}`, `{{USER_ROLE}}`, `{{USER_GROUPS}}`, `{{USER_GROUP_IDS}}` |
| **其他** | `{{TASK}}`, `{{USER_AGENT}}` |

</details>

<br/>

---

## 2. HTTP API 总览

### 2.1 调用约定

<div style=”background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px; color: white; margin: 20px 0;”>

**🔗 基础信息**

- **基础地址：** `http://host:port`
- **版本化前缀：** `/api/v1`
- **认证方式：** `Authorization: Bearer <token>`

</div>

<details>
<summary><b>🔐 权限与认证</b></summary>

| 角色 | 权限范围 |
| --- | --- |
| `admin` | 管理员接口完全访问权限 |
| `user` | 普通用户接口访问权限 |
| 匿名 | 仅限公开接口（健康检查、分享链接等） |

</details>

<details>
<summary><b>📦 请求格式</b></summary>

| 内容类型 | 使用场景 |
| --- | --- |
| `application/json` | JSON 请求（默认） |
| `multipart/form-data` | 文件上传 |
| `text/event-stream` | SSE 流式响应 |

</details>

<details>
<summary><b>🔌 兼容性接口</b></summary>

| 客户端类型 | 推荐接口 |
| --- | --- |
| **OpenAI 兼容** | `/api/chat/completions`, `/api/models`, `/api/embeddings` |
| **Anthropic 兼容** | `/api/v1/messages`, `/api/v1/messages/count_tokens` |

</details>

> 💡 所有请求/响应模型和细粒度权限以 `backend/open_webui/routers/*.py` 为准。下面的”能力”是二开入口索引，不替代 Pydantic schema。

<br/>

### 2.2 核心与兼容接口

**源码位置：** `backend/open_webui/main.py`

<details>
<summary><b>🤖 模型相关接口</b></summary>

| 方法和路径 | 功能 | 权限 |
| --- | --- | --- |
| `GET /api/models` | 返回当前用户可访问的模型列表 | User |
| `GET /api/v1/models` | OpenAI 兼容模型列表 | User |
| `GET /api/models/base` | 返回基础模型列表 | User |
| `POST /api/models/unload` | 卸载本地模型 | Admin |

**查询参数：**
- `refresh`: 强制刷新模型列表

</details>

<details>
<summary><b>💬 聊天与补全接口</b></summary>

| 方法和路径 | 功能 | 特性 |
| --- | --- | --- |
| `POST /api/chat/completions` | OpenAI 兼容聊天补全 | 流式响应、工具调用、RAG、订阅计费 |
| `POST /api/v1/chat/completions` | 同上（版本化路径） | 同上 |
| `POST /api/message` | Anthropic Messages 兼容入口 | Anthropic API 格式 |
| `POST /api/v1/messages` | 同上（版本化路径） | 同上 |
| `POST /api/message/count_tokens` | Anthropic 兼容 token 计数 | 预估用量 |
| `POST /api/v1/messages/count_tokens` | 同上（版本化路径） | 同上 |
| `POST /api/chat/completed` | 聊天完成后处理 | 过滤器、用量统计、记忆处理 |
| `POST /api/chat/actions/{action_id}` | 执行模型/聊天动作 | 自定义动作 |

</details>

<details>
<summary><b>🔍 嵌入与向量接口</b></summary>

| 方法和路径 | 功能 | 权限 |
| --- | --- | --- |
| `POST /api/embeddings` | OpenAI 兼容向量嵌入 | User |
| `POST /api/v1/embeddings` | 同上（版本化路径） | User |

</details>

<details>
<summary><b>📊 系统与监控接口</b></summary>

| 方法和路径 | 功能 | 权限 |
| --- | --- | --- |
| `GET /health` | 存活检查 | Public |
| `GET /ready` | 就绪检查 | Public |
| `GET /health/db` | 数据库健康检查 | Admin |
| `GET /api/version` | 版本信息 | Public |
| `GET /api/changelog` | 变更记录 | Public |
| `GET /api/version/updates` | 版本更新摘要 | Public |
| `GET /api/config` | 前端公开配置 | Public |
| `GET /api/usage` | 用量查询 | User |

</details>

<details>
<summary><b>⚙️ 任务与事件接口</b></summary>

| 方法和路径 | 功能 | 权限 |
| --- | --- | --- |
| `GET /api/tasks` | 查询后台任务列表 | User |
| `GET /api/tasks/chat/{chat_id}` | 查询特定聊天的任务 | User |
| `POST /api/tasks/{task_id}/stop` | 取消任务 | User |
| `GET /api/events` | 事件流（SSE） | User |
| `GET /api/events/webhooks` | 用户 webhook 管理 | User |

</details>

<details>
<summary><b>🔑 OAuth 认证接口</b></summary>

| 路径前缀 | 功能 |
| --- | --- |
| `/oauth/*` | OAuth 登录、回调和 back-channel logout |

</details>

<br/>

### 2.3 业务功能模块

所有模块在 `backend/open_webui/main.py` 注册，前缀为 `/api/v1`。

<details>
<summary><b>🎨 媒体生成模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/images` | 图像配置、模型、估价、生成和编辑 | `routers/images.py` |
| `/api/v1/videos` | 视频配置、估价、任务创建、查询和取消 | `routers/videos.py` |
| `/api/v1/audio` | 语音转文字和音频配置 | `routers/audio.py` |

**主要接口：**
- `GET /api/v1/images/models` - 获取可用图像模型
- `POST /api/v1/images/generations` - 生成图像
- `POST /api/v1/videos/generations` - 创建视频生成任务
- `GET /api/v1/videos/generations/{task_id}` - 查询视频任务状态

</details>

<details>
<summary><b>🔧 Pipeline 与工具模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/pipelines` | Pipeline 列表、上传、启停、valves | `routers/pipelines.py` |
| `/api/v1/tools` | 本地工具、OpenAPI 工具服务器、valves 和访问权限 | `routers/tools.py` |
| `/api/v1/functions` | Function/Filter/Pipe 的加载、同步、valves 和访问控制 | `routers/functions.py` |
| `/api/v1/skills` | Skill 创建、导出、访问、启停和更新 | `routers/skills.py` |

</details>

<details>
<summary><b>📚 知识与检索模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/knowledge` | 知识库、文件关联、向量索引和访问权限 | `routers/knowledge.py` |
| `/api/v1/retrieval` | 文档/网页/YouTube 处理、网页搜索、向量查询、RAG 配置 | `routers/retrieval.py` |
| `/api/v1/memories` | 记忆增删改查、搜索、路径和重置 | `routers/memories.py` |

**主要接口：**
- `POST /api/v1/knowledge` - 创建知识库
- `POST /api/v1/retrieval/web` - 网页搜索
- `POST /api/v1/memories/add` - 添加记忆

</details>

<details>
<summary><b>💬 对话与协作模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/chats` | 聊天 CRUD、搜索、归档、分叉、分享、标签和消息 | `routers/chats.py` |
| `/api/v1/channels` | 频道、成员、频道消息、置顶、webhook | `routers/channels.py` |
| `/api/v1/notes` | 笔记 CRUD、搜索和内容版本 | `routers/notes.py` |
| `/api/v1/prompts` | Prompt 库、版本、标签、访问权限和历史 | `routers/prompts.py` |

</details>

<details>
<summary><b>👥 用户与权限模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/auths` | 登录、注册、会话和敏感操作验证 | `routers/auths.py` |
| `/api/v1/users` | 用户资料、权限、偏好、webhook 和用户变量 | `routers/users.py` |
| `/api/v1/groups` | 用户组、成员和权限授予 | `routers/groups.py` |
| `/api/v1/emails` | 注册/登录验证码、密码、SMTP、模板和投递记录 | `routers/emails.py` |

</details>

<details>
<summary><b>💳 订阅与计费模块 <sup>0.3.0</sup></b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/subscriptions` | 套餐、订阅、Chatpoint、账本、兑换码、礼品卡、模型策略和管理员运营概览 | `routers/subscriptions.py` |

**核心接口：**
- `GET /api/v1/subscriptions/plans` - 获取套餐列表
- `POST /api/v1/subscriptions/subscribe` - 订阅套餐
- `GET /api/v1/subscriptions/balance` - 查询 Chatpoint 余额
- `GET /api/v1/subscriptions/ledger` - Chatpoint 账本明细
- `POST /api/v1/subscriptions/redeem` - 兑换码核销
- `POST /api/v1/subscriptions/gift-cards` - 生成礼品卡（管理员）

> 💡 **Chatpoint 账本是计费权威**，`/api/usage` 仅是观察数据。

</details>

<details>
<summary><b>🗂️ 资产与文件模块 <sup>0.3.0</sup></b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/assets` | Asset Center 列表、筛选、分享和撤销分享 | `routers/assets.py` |
| `/api/v1/files` | 文件上传、内容、下载、处理、删除和访问检查 | `routers/files.py` |
| `/api/v1/folders` | 文件夹、聊天归档和访问控制 | `routers/folders.py` |
| `/share` | 公开的、可撤销/过期的 Asset 分享链接 | `routers/assets.py` |

**主要接口：**
- `GET /api/v1/assets/` - 资产列表
- `POST /api/v1/assets/{id}/share` - 创建分享链接
- `DELETE /api/v1/assets/share/{share_id}` - 撤销分享
- `GET /share/{share_token}` - 访问公开分享

</details>

<details>
<summary><b>📢 系统管理模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/configs` | 管理配置、任务模板、Operation Status 配置 | `routers/configs.py` |
| `/api/v1/models` | 模型配置、访问控制和模型元数据 | `routers/models.py` |
| `/api/v1/announcements` | 公告列表、阅读状态、管理员创建/编辑/启停/删除 | `routers/announcements.py` |
| `/api/v1/updates` | 更新检查、状态、公告和一键部署 | `routers/updates.py` |
| `/api/v1/notifications` | 用户通知读取和状态更新 | `routers/notifications.py` |

**Operation Status 配置：** <sup>0.3.0</sup>
- `GET /api/v1/configs/operation-status` - 获取工具调用状态文案
- `POST /api/v1/configs/operation-status` - 更新状态文案（管理员）

</details>

<details>
<summary><b>🔄 自动化与任务模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/tasks` | 标题、标签、跟进问题、查询、自动补全、图像提示词等后台生成任务 | `routers/tasks.py` |
| `/api/v1/automations` | 自动化创建、计划、执行、启停和删除 | `routers/automations.py` |
| `/api/v1/calendars` | 日历、事件搜索/创建/更新/删除和 RSVP | `routers/calendar.py` |

</details>

<details>
<summary><b>📊 分析与评估模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/evaluations` | 反馈、评分、排行榜和历史 | `routers/evaluations.py` |
| `/api/v1/analytics` | 管理分析（需启用 `ENABLE_ADMIN_ANALYTICS`） | `routers/analytics.py` |

</details>

<details>
<summary><b>🛠️ 实用工具模块</b></summary>

| 前缀 | 主要功能 | 源码 |
| --- | --- | --- |
| `/api/v1/utils` | Gravatar、代码格式化/执行、PDF 和数据库下载 | `routers/utils.py` |
| `/api/v1/terminals` | 终端服务器连接和会话 | `routers/terminals.py` |
| `/api/v1/scim/v2` | SCIM 2.0 身份同步（需启用 `ENABLE_SCIM`） | `routers/scim.py` |

</details>

<br/>

### 2.4 外部模型适配器

| 前缀 | 功能 | 源码 |
| --- | --- | --- |
| `/ollama` | Ollama 模型、标签、生成和连接适配 | `backend/open_webui/routers/ollama.py` |
| `/openai` | 外部 OpenAI 兼容连接、模型发现和代理适配 | `backend/open_webui/routers/openai.py` |

<br/>

### 2.5 重点接口速查 <sup>0.3.0</sup>

| 用途 | 典型接口 | 说明 |
| --- | --- | --- |
| **更新检查** | `GET /api/v1/updates/check?force=false` | 检查新版本 |
| | `GET /api/v1/updates/status` | 获取更新状态 |
| | `POST /api/v1/updates/deploy` | 一键部署（管理员） |
| **静默记忆** | `POST /api/v1/memories/add` | 添加记忆 |
| | `PUT /api/v1/memories/update` | 更新记忆 |
| | `POST /api/v1/memories/search` | 搜索记忆 |
| | `DELETE /api/v1/memories/{memory_id}` | 删除记忆 |
| **Asset Center** | `GET /api/v1/assets/` | 资产列表 |
| | `POST /api/v1/assets/{id}/share` | 创建分享链接 |
| | `DELETE /api/v1/assets/share/{share_id}` | 撤销分享 |
| **Operation Status** | `GET /api/v1/configs/operation-status` | 获取工具状态配置 |
| | `POST /api/v1/configs/operation-status` | 更新状态文案（管理员） |
| **订阅/额度** | `/api/v1/subscriptions/*` | Chatpoint 账本是计费权威 |

<br/>

---

## 3. 模型内置工具（函数调用）

内置工具由 `backend/open_webui/utils/tools.py:get_builtin_tools` 按以下条件动态注入：

- ✅ 全局开关
- ✅ 模型 capability
- ✅ 用户权限
- ✅ 当前聊天上下文

关闭某个 `builtinTools` 类别或不满足权限时，模型不会收到对应函数规格。

<br/>

<details>
<summary><b>⏰ 时间工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `get_current_timestamp` | 获取当前时间戳 |
| `calculate_timestamp` | 时间戳计算和日期运算 |

</details>

<details>
<summary><b>📁 聊天文件工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `list_chat_files` | 列出当前聊天的附件 |
| `query_chat_files` | 查询聊天附件内容 |
| `grep_chat_files` | 在聊天附件中搜索文本 |
| `view_file` | 查看文件详情 |

</details>

<details>
<summary><b>📚 知识库工具</b></summary>

| 函数名 | 用途 | 备注 |
| --- | --- | --- |
| `list_knowledge_bases` | 列出知识库 | — |
| `search_knowledge_bases` | 搜索知识库 | — |
| `query_knowledge_bases` | 查询知识库内容 | — |
| `list_knowledge` | 列出知识条目 | — |
| `search_knowledge_files` | 搜索知识文件 | — |
| `grep_knowledge_files` | 在知识文件中搜索文本 | — |
| `query_knowledge_files` | 查询知识文件内容 | — |
| `view_knowledge_file` | 查看知识文件 | — |
| `kb_exec` | 执行知识库操作 | 高级功能 |

> 💡 具体函数集合取决于模型挂载的知识库。

</details>

<details>
<summary><b>💬 历史聊天工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `search_chats` | 搜索用户聊天历史 |
| `view_chat` | 查看特定聊天详情 |

</details>

<details>
<summary><b>🤖 子代理工具</b></summary>

| 函数名 | 用途 | 备注 |
| --- | --- | --- |
| `delegate_task` | 委派任务给后台代理 | 不会再次注入变更型记忆工具 |
| `timer` | 设置计时器 | — |

</details>

<details>
<summary><b>🧠 记忆工具 <sup>0.3.0</sup></b></summary>

| 函数名 | 用途 | 前端展示 |
| --- | --- | --- |
| `search_memories` | 搜索记忆 | 可见 |
| `list_memory_paths` | 列出记忆路径 | 可见 |
| `read_memory_path` | 读取记忆路径 | 可见 |
| `list_memories` | 列出所有记忆 | 可见 |
| `update_memory` | 更新记忆 | **无感** |
| `add_memory` | 添加新记忆 | **无感** |
| `replace_memory_content` | 替换记忆内容 | **无感** |
| `delete_memory` | 删除记忆 | **无感** |

> ⚠️ **0.3.0 前端对维护调用采用无感展示**，但后端执行和审计不变。

</details>

<details>
<summary><b>🌐 网页工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `search_web` | 搜索网页 |
| `fetch_url` | 读取 URL 内容 |

</details>

<details>
<summary><b>🎨 媒体生成工具 <sup>0.3.0</sup></b></summary>

| 函数名 | 用途 | 限制 |
| --- | --- | --- |
| `generate_image` | 生成图像 | 额度、模型 capability、开关 |
| `edit_image` | 编辑图像 | 同上 |
| `generate_video` | 生成视频 | 同上 |

> 💡 受额度、模型 capability 和媒体开关限制。

</details>

<details>
<summary><b>💻 代码执行工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `execute_code` | 在受限代码解释器环境中执行代码 |

> ⚠️ 运行在沙箱环境，无法访问外部网络和文件系统。

</details>

<details>
<summary><b>📝 笔记工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `search_notes` | 搜索笔记 |
| `view_note` | 查看笔记 |
| `write_note` | 写入笔记 |
| `replace_note_content` | 替换笔记内容 |

</details>

<details>
<summary><b>📢 频道工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `search_channels` | 搜索频道 |
| `search_channel_messages` | 搜索频道消息 |
| `view_channel_thread` | 查看频道话题 |
| `view_channel_message` | 查看频道消息 |

</details>

<details>
<summary><b>🎯 Skill 工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `view_skill` | 按需读取被提及 Skill 的完整说明 |

</details>

<details>
<summary><b>✅ 任务管理工具</b></summary>

| 函数名 | 用途 | 限制 |
| --- | --- | --- |
| `create_tasks` | 在已保存聊天中创建任务 | 需要聊天已保存 |
| `update_task` | 更新任务状态 | 同上 |

</details>

<details>
<summary><b>🔄 自动化工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `create_automation` | 创建定时自动化 |
| `update_automation` | 更新自动化 |
| `list_automations` | 列出自动化列表 |
| `toggle_automation` | 启停自动化 |
| `delete_automation` | 删除自动化 |

</details>

<details>
<summary><b>📅 日历工具</b></summary>

| 函数名 | 用途 |
| --- | --- |
| `search_calendar_events` | 搜索日历事件 |
| `create_calendar_event` | 创建日历事件 |
| `update_calendar_event` | 更新日历事件 |
| `delete_calendar_event` | 删除日历事件 |

</details>

<details>
<summary><b>🔔 通知工具</b></summary>

| 函数名 | 用途 | 权限 |
| --- | --- | --- |
| `notify` | 发送用户 webhook/通知 | 需启用并授权 |

</details>

<br/>

> 💡 **工具调用状态文本**由 Operation Status 配置控制；记忆维护工具的执行结果仍会写入后端上下文，前端只隐藏对应的可见详情。

---

## 4. 二开建议

<div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 20px; border-radius: 12px; color: white; margin: 20px 0;">

### 🎯 核心原则

保持架构清晰，遵循现有模式，避免破坏性修改。

</div>

<br/>

### 4.1 架构规范

<details>
<summary><b>📦 模块化开发</b></summary>

**新增业务逻辑放入独立模块：**

```
backend/open_webui/
├── routers/<feature>.py          # 路由定义
├── models/<feature>.py            # 数据模型
└── utils/<feature>.py             # 工具函数

src/lib/apis/<feature>/
└── index.ts                       # 前端 API 封装
```

**注册路由：**
```python
# backend/open_webui/main.py
from open_webui.routers import feature

app.include_router(feature.router, prefix="/api/v1/feature", tags=["feature"])
```

> ❌ **不要把业务逻辑堆进 `main.py`**

</details>

<details>
<summary><b>🛠️ 工具函数规范</b></summary>

**新增模型工具接入流程：**

1. 在 `backend/open_webui/utils/tools.py:get_builtin_tools` 添加函数
2. 配置类别、权限和 capability 门控
3. 提供完整的函数签名和文档字符串
4. 确保自动 schema 生成稳定

**示例：**
```python
def my_custom_tool(query: str, limit: int = 10) -> dict:
    """
    自定义工具函数
    
    Args:
        query: 查询字符串
        limit: 结果数量限制
    
    Returns:
        包含结果的字典
    """
    # 实现逻辑
    pass
```

</details>

<details>
<summary><b>📝 提示词变量规范</b></summary>

**新增系统提示词变量：**

1. 在对应位置增加解析逻辑：
   - `backend/open_webui/utils/task.py` - 任务提示词
   - `backend/open_webui/utils/chat_variables.py` - 聊天变量
   - `backend/open_webui/utils/payload.py` - 请求载荷
2. 补充前端输入控件
3. 添加测试用例

> ⚠️ **不要只做字符串替换**，必须进行校验和类型检查。

</details>

<br/>

### 4.2 安全与权限

<details>
<summary><b>🔐 权限检查</b></summary>

**涉及以下操作必须进行权限检查：**

- ✅ 额度和订阅状态
- ✅ 文件访问权限
- ✅ 记忆所有权
- ✅ 用户角色验证

**示例：**
```python
from open_webui.utils.auth import get_current_user

@router.get("/sensitive-data")
async def get_sensitive_data(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Insufficient permissions")
    # 处理逻辑
```

</details>

<details>
<summary><b>💰 计费集成</b></summary>

**Chatpoint 扣费流程：**

1. 调用前检查余额
2. 执行操作
3. 记录消费到账本
4. 更新用户余额

> 💡 **Chatpoint 账本是计费权威**，其他用量统计仅供参考。

</details>

<details>
<summary><b>🔒 事务与幂等</b></summary>

**数据库操作规范：**

- 使用事务确保数据一致性
- 关键操作实现幂等性
- 避免竞态条件

```python
from sqlalchemy.orm import Session

def create_resource(db: Session, data: dict):
    try:
        # 数据库操作
        db.commit()
    except Exception as e:
        db.rollback()
        raise
```

</details>

<br/>

### 4.3 开发环境

<details>
<summary><b>🚀 本地开发</b></summary>

**调试端口：**
- `3003` - 预览实例（开发调试）
- `3000` - 生产实例（持久化部署）

**启动开发服务器：**
```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn open_webui.main:app --reload --port 8080

# 前端
cd frontend
npm install
npm run dev
```

</details>

<details>
<summary><b>🧪 测试规范</b></summary>

**测试覆盖：**
- 单元测试：工具函数、模型方法
- 集成测试：API 端点
- E2E 测试：关键业务流程

**运行测试：**
```bash
# 后端测试
pytest backend/tests/

# 前端测试
npm run test
```

</details>

<details>
<summary><b>📋 发布审批</b></summary>

**发布到生产环境需要单独审批：**

- ✅ 代码审查通过
- ✅ 测试覆盖充分
- ✅ 数据库迁移脚本验证
- ✅ 持久化 Docker 卷备份

> ⚠️ **生产部署前必须备份 `artichat_data` 卷**

</details>

<br/>

### 4.4 最佳实践

<table>
<tr>
<td width="50%" valign="top">

**✅ 推荐做法**

- 遵循现有代码风格
- 复用已有组件和函数
- 编写清晰的文档字符串
- 添加类型注解
- 使用环境变量配置
- 实现优雅的错误处理
- 记录关键操作日志

</td>
<td width="50%" valign="top">

**❌ 避免做法**

- 硬编码配置信息
- 绕过权限检查
- 直接修改核心文件
- 忽略错误处理
- 不写测试
- 破坏向后兼容性
- 暴露敏感信息

</td>
</tr>
</table>

<br/>

---

## 5. 代码定位

快速定位关键代码位置的索引表。

### 5.1 后端核心模块

<details>
<summary><b>🔧 工具与变量处理</b></summary>

| 功能 | 文件路径 |
| --- | --- |
| 提示词变量替换 | `backend/open_webui/utils/task.py` |
| 聊天/用户变量 | `backend/open_webui/utils/chat_variables.py` |
| 请求载荷处理 | `backend/open_webui/utils/payload.py` |
| 自定义请求头变量 | `backend/open_webui/utils/headers.py` |
| 内置工具注入 | `backend/open_webui/utils/tools.py` |

</details>

<details>
<summary><b>🌐 路由与接口</b></summary>

| 功能 | 文件路径 |
| --- | --- |
| HTTP 路由注册 | `backend/open_webui/main.py` |
| 订阅与计费 | `backend/open_webui/routers/subscriptions.py` |
| 资产中心 | `backend/open_webui/routers/assets.py` |
| 记忆管理 | `backend/open_webui/routers/memories.py` |
| 媒体生成 | `backend/open_webui/routers/images.py`, `videos.py` |
| 更新服务 | `backend/open_webui/routers/updates.py` |

</details>

<details>
<summary><b>⚙️ 配置与服务</b></summary>

| 功能 | 文件路径 |
| --- | --- |
| 更新服务逻辑 | `backend/open_webui/utils/update_service.py` |
| 部署脚本 | `deploy/aws-1panel/artichat-deploy.sh` |
| 环境配置 | `.env`, `docker-compose.yaml` |

</details>

<br/>

### 5.2 前端核心模块

<details>
<summary><b>📡 API 封装</b></summary>

| 功能 | 文件路径 |
| --- | --- |
| API 统一封装 | `src/lib/apis/` |
| 订阅接口 | `src/lib/apis/subscriptions/index.ts` |
| 聊天接口 | `src/lib/apis/chats/index.ts` |
| 资产接口 | `src/lib/apis/assets/index.ts` |

</details>

<details>
<summary><b>🎨 组件与页面</b></summary>

| 功能 | 文件路径 |
| --- | --- |
| 组件库 | `src/lib/components/` |
| 页面路由 | `src/routes/` |
| 状态管理 | `src/lib/stores/` |

</details>

<br/>

### 5.3 配置文件

<details>
<summary><b>📝 关键配置</b></summary>

| 文件 | 用途 |
| --- | --- |
| `docker-compose.yaml` | Docker Compose 配置 |
| `.env` | 环境变量 |
| `backend/requirements.txt` | Python 依赖 |
| `package.json` | Node.js 依赖 |
| `pyproject.toml` | Python 项目配置 |
| `svelte.config.js` | SvelteKit 配置 |
| `tailwind.config.js` | Tailwind CSS 配置 |

</details>

<br/>

---

<div align="center">

## 📚 相关资源

[![返回主文档](https://img.shields.io/badge/←_返回-主文档-6366f1?style=for-the-badge)](readme.md)
[![English](https://img.shields.io/badge/English-Documentation-10b981?style=for-the-badge)](readme-en.md)
[![反馈站](https://img.shields.io/badge/反馈站-chatbug.artivis.cc-f59e0b?style=for-the-badge&logo=gitbook&logoColor=white)](https://chatbug.artivis.cc)

<br/>

**需要帮助？**

如果在开发过程中遇到问题，欢迎到 [反馈站](https://chatbug.artivis.cc) 提交反馈！

<br/>

---

<div align="center">

*Built with ❤️ by Artivis Studio | API Documentation v0.3.0*

</div>

</div>

