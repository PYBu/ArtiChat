# ArtiChat 提示词上下文与平台知识库设计

## 目标

让模型系统提示词可以读取当前用户的订阅、额度、到期与重置状态，并提供一份 ArtiChat 平台知识库，使管理员可以把平台说明注入模型系统提示词，让模型正确回答用户关于本平台功能、订阅、兑换码、用量和数据保存方式的问题。

## 设计决策

- 不默认把订阅和平台知识库塞进所有请求，避免无控制地增加 token 消耗。
- 通过系统提示词变量按需注入。管理员可以在模型系统提示词中写入变量，后端会在请求时用服务端可信数据替换。
- 订阅变量由后端生成，不信任前端传值。
- 生成订阅变量前会调用现有 `ensure_subscription_current`，保证过期订阅先降级、周期额度先重置，再暴露给模型。
- 平台知识库以 Markdown 文件保存到 `backend/open_webui/resources/artichat_platform_knowledge.zh-CN.md`，该路径会随 Docker 镜像复制到运行环境。

## 系统提示词变量

### 聚合变量

- `{{ARTICHAT_SUBSCRIPTION_CONTEXT}}`
  - 多行文本，包含用户当前订阅、状态、到期时间、周期额度、剩余额度、充值额度、总余额、下次重置时间和是否额度耗尽。
- `{{ARTICHAT_PLATFORM_CONTEXT}}`
  - 多行文本，包含平台知识库正文。

推荐模型系统提示词片段：

```text
你是 ArtiChat 平台内的助手。回答平台相关问题时优先依据以下平台知识库和用户上下文。

{{ARTICHAT_PLATFORM_CONTEXT}}

{{ARTICHAT_SUBSCRIPTION_CONTEXT}}
```

### 细粒度订阅变量

- `{{USER_SUBSCRIPTION}}`: 订阅显示名，例如 `Free`、`Plus`、`ChatPower`。
- `{{USER_SUBSCRIPTION_TIER}}`: 订阅档位 ID，例如 `free`、`plus`、`chatpower`。
- `{{USER_SUBSCRIPTION_STATUS}}`: 订阅状态。
- `{{USER_SUBSCRIPTION_EXPIRES_AT}}`: 到期时间，永久 Free 显示为 `Never`。
- `{{USER_SUBSCRIPTION_PERIOD_START_AT}}`: 当前周期开始时间。
- `{{USER_SUBSCRIPTION_PERIOD_END_AT}}`: 当前周期结束时间。
- `{{USER_SUBSCRIPTION_NEXT_RESET_AT}}`: Plan Chatpoint 下次重置时间。
- `{{PLAN_CHATPOINT_ALLOWANCE}}`: 本周期 Plan Chatpoint 发放额度。
- `{{PLAN_CHATPOINT_BALANCE}}`: 当前 Plan Chatpoint 剩余额度。
- `{{PLAN_CHATPOINT_USED}}`: 当前周期已使用 Plan Chatpoint。
- `{{CHECK_CHATPOINT_BALANCE}}`: Check Chatpoint 充值余额。
- `{{TOTAL_CHATPOINT_BALANCE}}`: Plan + Check 总余额。
- `{{CHATPOINT_BALANCE}}`: 总余额别名。
- `{{CHATPOINT_QUOTA_EXHAUSTED}}`: `true` 或 `false`。

## 后端实现

- 在 `backend/open_webui/utils/payload.py` 中增加服务端上下文变量合并逻辑。
- 用 `ensure_subscription_current(user.id)` 获取最新订阅状态。
- 用 `micros_to_chatpoint` 转换展示用 Chatpoint 数值，去掉多余小数零。
- 用 `datetime.fromtimestamp(...).isoformat()` 输出时间，避免本地化歧义。
- 平台知识库文件通过 `Path(__file__).resolve().parents[1] / "resources"` 读取。读取失败时返回空字符串，不阻断聊天请求。

## 测试

- 单元测试验证 `resolve_system_prompt` 能替换订阅聚合变量和细粒度变量。
- 单元测试验证过期 Plus 用户在变量生成前会自动降级为 Free。
- 单元测试验证 `{{ARTICHAT_PLATFORM_CONTEXT}}` 会读取平台知识库内容。

## 平台知识库范围

知识库覆盖：

- ArtiChat 是本地自托管 AI 聊天平台。
- 模型由管理员配置，用户只能看到订阅允许访问的模型。
- Chatpoint 规则：100 Chatpoint = 100 万 token 使用量；实际扣费受模型倍率影响。
- Plan Chatpoint 是周期额度，优先消耗并按订阅周期重置。
- Check Chatpoint 是充值额度，Plan 用尽后消耗，不随周期清零。
- Free、Plus、ChatPower 的默认额度和用途。
- 兑换码、礼品卡、公告、用量页、订阅页、账单地址和管理员能力。
- 迁移与数据保存：账号、模型配置、聊天记录、订阅数据保存在 `artichat_data` 数据卷。

## 非目标

- 不在本轮自动修改所有现有模型的系统提示词。
- 不把平台知识库自动上传为 UI 知识库条目。
- 不让模型绕过后端权限；变量只用于回答和解释，不参与权限判定。
