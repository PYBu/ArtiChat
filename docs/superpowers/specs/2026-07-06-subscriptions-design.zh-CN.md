# ArtiChat 订阅功能设计稿

## 目标

为 ArtiChat 增加一套内置订阅和额度系统，用来控制模型可见性、模型调用权限、Chatpoint 消耗、兑换码、用户订阅状态，以及管理员后台运营管理。

第一期支持三个档位：

- Free
- Plus
- ChatPower

支付暂时不做真实接入。购买按钮先作为占位功能，兑换码和管理员手动调整需要完整可用。

## 当前项目接入点

后端主要接入点：

- 模型列表：`backend/open_webui/main.py` 的 `/api/models`
- 聊天接口：`backend/open_webui/main.py` 的 `/api/chat/completions`
- 模型数据：`backend/open_webui/models/models.py`
- 模型管理接口：`backend/open_webui/routers/models.py`
- 用户接口：`backend/open_webui/routers/users.py`
- token 用量标准化：`backend/open_webui/utils/response.py`
- 聊天消息 token 存储与统计：`backend/open_webui/models/chat_messages.py`
- 管理员 analytics：`backend/open_webui/routers/analytics.py`

前端主要接入点：

- 用户设置弹窗：`src/lib/components/chat/SettingsModal.svelte`
- 账号设置页：`src/lib/components/chat/Settings/Account.svelte`
- 管理员设置页：`src/lib/components/admin/Settings.svelte`
- 管理员用户页：`src/lib/components/admin/Users.svelte`
- 管理员编辑用户弹窗：`src/lib/components/admin/Users/UserList/EditUserModal.svelte`
- 模型编辑器：`src/lib/components/workspace/Models/ModelEditor.svelte`
- 左下角用户菜单：`src/lib/components/layout/Sidebar/UserMenu.svelte`

## 第一期开工范围

包含：

- Free、Plus、ChatPower 三个套餐。
- Plan Chatpoint 周期重置。
- Check Chatpoint 充值/兑换余额。
- 模型按套餐控制显示和调用。
- 模型支持 unlimited 和 metered 两种额度模式。
- metered 模型支持管理员随时调整倍率。
- 根据真实 input tokens + output tokens 扣除 Chatpoint。
- 兑换码系统，支持单次码和多次码。
- 用户侧订阅页、兑换页、用量页、账单地址、记录展示。
- 左下角用户按钮显示套餐和额度环状图。
- 管理员后台管理套餐、模型权限、兑换码、用户订阅、用量和流水。
- 后端强制校验，防止绕过前端直接调用隐藏模型。
- 自动化测试覆盖订阅生命周期、扣费、兑换码、模型过滤和管理员绕过。

不包含：

- 真实支付平台。
- 发票、税费、支付对账。
- 按供应商账单计算真实成本。
- 对历史聊天消息补扣费用。

## 套餐默认配置

默认套餐如下：

| 套餐 | 内部值 | 等级 | 默认 Plan Chatpoint | 周期 |
| --- | --- | ---: | ---: | ---: |
| Free | `free` | 0 | 10 | 30 天 |
| Plus | `plus` | 1 | 100 | 30 天 |
| ChatPower | `chatpower` | 2 | 500 | 30 天 |

后台可以调整这些默认配置，但不会影响已经开通订阅的用户。用户开通、升级、自动降级时，会保存当时套餐配置的一份快照。

## Chatpoint 规则

换算关系：

- `100 Chatpoint = 100 万 tokens`
- `1 Chatpoint = 1 万 tokens`
- 基础消耗：`tokens / 10000`
- 最终消耗：`tokens / 10000 * 模型倍率`

为了避免小数误差，后端用整数微单位存储：

- `1 Chatpoint = 1,000,000 cp_micros`
- 倍率为 1 时，`1 token = 100 cp_micros`
- 后端计算使用 Decimal 逻辑，最后向上取整到最小微单位，避免浮点数少扣。

用户有两种额度：

- `Plan Chatpoint`：套餐周期额度，会周期重置，优先消耗。
- `Check Chatpoint`：充值或兑换得到的额度，不随周期重置清零，Plan 用完后再消耗。

扣费顺序：

1. 先扣 Plan Chatpoint。
2. Plan 不够时扣 Check Chatpoint。
3. 如果当前请求花费超过剩余额度，允许当前请求完成，可以扣成负数。
4. 之后如果 `Plan + Check <= 0`，再调用 metered 模型会被拒绝。

unlimited 模型：

- 记录 token 用量。
- Chatpoint 消耗为 0。
- 不要求用户余额大于 0。

管理员：

- 管理员绕过套餐限制。
- 管理员绕过额度限制。
- 管理员使用模型不扣 Chatpoint。

## 订阅生命周期

每个用户都有一个当前有效订阅。没有付费订阅时，视为 Free 用户。

每个用户订阅保存一份套餐快照：

- 套餐内部值。
- 套餐等级。
- 显示名称。
- 周期天数。
- 每周期 Plan Chatpoint 额度。
- 开始时间。
- 到期时间。
- 当前周期开始时间。
- 当前周期结束时间。
- 下次重置时间。

后端提供一个统一函数：`ensure_subscription_current(user_id)`。

它会在这些场景调用：

- 用户打开订阅页。
- 用户打开用量页。
- 用户请求模型列表。
- 用户发起聊天请求。
- 用户兑换兑换码。
- 管理员查看或编辑用户订阅。

生命周期规则：

- 用户有有效 Plus 或 ChatPower 时，按当前订阅快照重置 Plan Chatpoint。
- 如果 Plus 或 ChatPower 到期且没有续费，用户自动降级为 Free。
- 自动降级时，会根据当前 Free 套餐配置创建新的 Free 快照。
- 降级后，下次 Plan Chatpoint 重置只能按 Free 额度进行。
- 不能出现 Plus 到期以后还继续按 Plus 额度重置的情况。
- Check Chatpoint 在续费、降级、周期重置时都保留。
- 管理员手动修改订阅时，明确更新用户快照，并写入流水。

周期规则：

- 按用户订阅开始时间滚动。
- 例如 7 月 6 日开通 Plus，则周期按每月 6 日滚动。
- 如果用户很久没登录，中间错过多个周期，系统会推进到当前周期，只记录当前必要的重置，不产生大量重复流水。

## 数据表设计

新增后端模块：`backend/open_webui/models/subscriptions.py`

### `subscription_plan`

保存套餐默认配置。

主要字段：

- `id`：`free`、`plus`、`chatpower`
- `display_name`：显示名
- `tier_rank`：等级
- `period_days`：周期天数，默认 30
- `plan_chatpoint_allowance_micros`：默认 Plan Chatpoint 周期额度
- `description`：描述
- `features`：套餐卡片展示内容
- `is_active`：是否启用
- `sort_order`：排序
- `created_at` / `updated_at`

### `user_subscription`

保存用户当前订阅快照和余额。

主要字段：

- `user_id`
- `tier`
- `tier_rank`
- `display_name`
- `period_days`
- `plan_chatpoint_allowance_micros`
- `plan_balance_micros`
- `check_balance_micros`
- `starts_at`
- `expires_at`
- `period_start_at`
- `period_end_at`
- `next_reset_at`
- `status`
- `source`
- `snapshot`
- `billing_address`
- `notes`
- `created_at` / `updated_at`

### `subscription_ledger`

额度和订阅事件流水，只追加不覆盖。

记录内容：

- 周期重置
- 兑换码激活
- 模型扣费
- 管理员调整
- 套餐变化
- 自动降级

关键字段：

- `user_id`
- `event_type`
- `tier_before`
- `tier_after`
- `plan_delta_micros`
- `check_delta_micros`
- `plan_balance_after_micros`
- `check_balance_after_micros`
- `reference_type`
- `reference_id`
- `metadata`
- `created_by`
- `created_at`

### `redemption_code`

保存兑换码定义。

支持：

- 单次码
- 多次码
- 最大使用次数
- 套餐
- 时长
- Plan Chatpoint
- Check Chatpoint
- 过期时间
- 是否启用
- 备注

兑换码只保存 hash，不明文保存。后台生成后只在创建结果里展示一次原始码，管理员需要当场复制或导出。

### `redemption_record`

保存兑换记录。

记录：

- 哪个用户用了哪个兑换码。
- 兑换前后套餐。
- 兑换前后到期时间。
- 获得的 Plan Chatpoint。
- 获得的 Check Chatpoint。
- 兑换时间。

同一个用户不能重复兑换同一个兑换码。

### `subscription_usage`

保存每次模型调用的计费或用量记录。

记录：

- 用户
- 聊天
- 消息
- 模型
- 当前套餐
- quota mode
- 倍率
- input tokens
- output tokens
- total tokens
- 总消耗
- Plan 消耗
- Check 消耗
- 扣费后的余额
- 状态

如果 metered 模型的供应商响应没有返回 usage，则记录为 `missing_usage`，Chatpoint 消耗为 0，方便管理员发现未计费调用。

## 模型订阅策略

模型策略放在现有 `model.meta.subscription`，不改 `model` 表结构。

格式：

```json
{
  "subscription": {
    "allowed_tiers": ["free", "plus", "chatpower"],
    "quota_mode": "metered",
    "usage_multiplier": "1.0"
  }
}
```

规则：

- `allowed_tiers` 控制哪些套餐能看到和使用模型。
- `quota_mode = unlimited` 时不扣 Chatpoint。
- `quota_mode = metered` 时按真实 token 扣 Chatpoint。
- `usage_multiplier` 是倍率，管理员可以调整。
- 倍率不能小于 0。
- 缺少策略时，默认所有套餐可用、metered、倍率 1.0，保证老模型不会因为缺配置直接消失。
- 现有用户/组访问控制仍然先生效。
- 普通用户最终权限是：原有访问权限通过，并且当前套餐允许。
- 管理员绕过套餐限制。

后端强制点：

- `/api/models` 和 `/api/v1/models` 过滤普通用户可见模型。
- `/api/chat/completions` 和 `/api/v1/chat/completions` 在生成前再次校验。
- 多模型对话时，每个目标模型都单独校验。

## 兑换码规则

支持两种兑换码：

- 单次码：批量生成多个，每个码只能用一次。
- 多次码：一个码可以多人使用，可设置最大使用次数。

兑换码可以配置：

- 是否改变套餐。
- 套餐：Free、Plus、ChatPower。
- 订阅时长。
- Plan Chatpoint 增量。
- Check Chatpoint 增量。
- 过期时间。
- 是否启用。
- 备注。

兑换规则：

- 兑换码可以只发 Check Chatpoint，不改变套餐。
- 兑换码可以只发本周期临时 Plan Chatpoint，不改变套餐。
- 兑换码可以只延长订阅，也可以同时发额度。
- 订阅只升不降级。
- 低套餐兑换码不会把高套餐用户降级，但额度赠送仍然生效。
- 同套餐兑换码从 `max(当前时间, 当前到期时间)` 往后延长。
- 更高套餐兑换码立即升级，并从 `max(当前时间, 当前到期时间)` 往后增加时长。
- 如果兑换码包含套餐和时长，用户的周期 Plan Chatpoint 快照使用兑换时后台套餐配置。
- 兑换码里的 Plan Chatpoint 增量只影响当前周期，不改变以后周期的固定 Plan 额度。
- 兑换码里的 Check Chatpoint 会追加到 Check 余额，不随重置清零。
- 每次成功兑换都写入兑换记录和订阅流水。

## API 设计

新增后端路由：`/api/v1/subscriptions`

用户接口：

- `GET /api/v1/subscriptions/me`
  - 当前订阅、余额、周期、到期状态。
- `GET /api/v1/subscriptions/usage`
  - 当前周期用量、按模型聚合、最近用量和流水。
- `POST /api/v1/subscriptions/redeem`
  - 激活兑换码。
- `GET /api/v1/subscriptions/records`
  - 用户自己的订阅、兑换、调整、重置、扣费记录。
- `PUT /api/v1/subscriptions/billing-address`
  - 保存账单地址。

管理员接口：

- `GET /api/v1/subscriptions/admin/plans`
- `PUT /api/v1/subscriptions/admin/plans/{plan_id}`
- `GET /api/v1/subscriptions/admin/models`
- `PUT /api/v1/subscriptions/admin/models/{model_id}/policy`
- `GET /api/v1/subscriptions/admin/codes`
- `POST /api/v1/subscriptions/admin/codes`
- `PATCH /api/v1/subscriptions/admin/codes/{code_id}`
- `GET /api/v1/subscriptions/admin/codes/{code_id}/records`
- `GET /api/v1/subscriptions/admin/users`
- `GET /api/v1/subscriptions/admin/users/{user_id}`
- `PUT /api/v1/subscriptions/admin/users/{user_id}`
- `GET /api/v1/subscriptions/admin/usage`
- `GET /api/v1/subscriptions/admin/ledger`

## 用户界面

### 设置页新增三个标签

用户设置弹窗新增：

- Subscription
- Redeem Code
- Usage

Subscription 页面：

- 当前套餐卡片。
- 状态：有效、即将到期、已过期并降级为 Free。
- 到期时间。
- 当前周期开始和结束。
- 下次重置时间。
- Plan Chatpoint 余额。
- Check Chatpoint 余额。
- Free、Plus、ChatPower 三个套餐卡片。
- 购买按钮先占位，提示暂未开放。
- 兑换按钮跳转到 Redeem Code 页面。

Redeem Code 页面：

- 输入兑换码。
- 激活按钮。
- 成功后显示获得内容：
  - 套餐
  - 时长
  - Plan Chatpoint
  - Check Chatpoint
- 错误状态：
  - 无效
  - 已过期
  - 已禁用
  - 次数用完
  - 已兑换过
- 成功后刷新订阅和余额。

Usage 页面：

- 当前周期总用量。
- Plan 和 Check 消耗。
- 按模型分组：
  - 模型名称
  - input tokens
  - output tokens
  - total tokens
  - 倍率
  - Chatpoint 消耗
- 最近使用记录。
- unlimited 模型显示 token 用量，但 Chatpoint 消耗为 0。

### 账号页

账号页增加账单地址：

- 姓名或公司
- 国家/地区
- 地址
- 邮编
- 税号或备注

账号页增加订阅/兑换记录摘要：

- 类型
- 时间
- 套餐变化
- Plan/Check Chatpoint 变化
- 来源

### 左下角用户按钮

左下角用户按钮区域增加订阅摘要：

- 普通用户显示套餐 badge：Free、Plus、ChatPower。
- 普通用户显示一个小型额度环状图。
- 管理员显示 Admin badge，不显示额度环状图。
- 环状图表示 metered 总额度使用比例。
- 额度正常时使用正常颜色。
- 额度较低时使用警示颜色。
- 额度用尽或为负数时，环状图变成红色。
- 鼠标悬停环状图显示小弹窗：
  - 标题：Usage
  - `Plan Chatpoint 100 / 1000`
  - 后面接一条线状用量条
  - `Check Chatpoint 20 / 200`
  - 后面接一条线状用量条
  - `Next reset: YYYY-MM-DD`
  - 如果额度已用尽，提示 metered 模型暂不可用，需要等待重置、兑换或管理员调整。
- 点击环状图直接打开设置里的 Usage 页面。
- 移动端没有 hover，点击环状图直接打开 Usage 页面。

## 管理员后台

采用已确认的结构：

- 完整订阅管理放在 `Admin Settings > Subscriptions`。
- `Admin > Users` 继续专注用户、角色、分组。
- 用户编辑弹窗只显示简版订阅摘要，并提供 `Manage Subscription` 入口跳转到完整订阅管理。

### Plans

管理 Free、Plus、ChatPower 默认配置：

- 显示名
- 是否启用
- 默认 Plan Chatpoint 周期额度
- 周期天数
- 描述
- 套餐卡片展示内容
- 排序

页面要提示：修改默认套餐不会影响已经开通订阅的用户。

### Model Access

管理所有模型的订阅策略：

- 哪些套餐可见/可用。
- unlimited 或 metered。
- 使用倍率。

同样的策略编辑区域也接入模型编辑器，创建和编辑模型时可以直接设置。

### Redeem Codes

管理员可以：

- 创建单次码。
- 创建多次码。
- 批量生成单次码。
- 设置最大使用次数。
- 设置套餐。
- 设置时长。
- 设置 Plan Chatpoint。
- 设置 Check Chatpoint。
- 设置过期时间。
- 设置备注。

列表显示：

- code preview
- 类型
- 已使用/最大次数
- 状态
- 过期时间
- 创建时间

刚生成的原始兑换码可以复制或导出。之后系统只保存 hash，不再显示完整原始码。

### User Subscriptions

管理员可以搜索用户并查看：

- 当前套餐
- 到期时间
- Plan Chatpoint
- Check Chatpoint
- 当前周期
- 下次重置

管理员可以编辑：

- 套餐
- 到期时间
- Plan 余额
- Check 余额
- 周期开始和结束
- 备注

所有手动编辑都写入流水。

### Usage And Ledger

管理员可以查看：

- 按用户用量
- 按模型用量
- 按日期筛选
- 按套餐筛选
- 按事件类型筛选
- 重置、兑换、管理员调整、扣费、套餐变化、自动降级等流水

## 错误处理

后端返回稳定错误码，前端按错误码显示文案。

建议错误码：

- `SUBSCRIPTION_TIER_REQUIRED`：当前套餐不能使用该模型。
- `CHATPOINT_BALANCE_EXHAUSTED`：Chatpoint 不足，不能开始 metered 模型请求。
- `REDEMPTION_CODE_INVALID`：兑换码不存在。
- `REDEMPTION_CODE_DISABLED`：兑换码已停用。
- `REDEMPTION_CODE_EXPIRED`：兑换码已过期。
- `REDEMPTION_CODE_EXHAUSTED`：兑换码次数用完。
- `REDEMPTION_CODE_ALREADY_USED`：该用户已经兑换过这个码。
- `SUBSCRIPTION_PLAN_INACTIVE`：套餐未启用。
- `MODEL_SUBSCRIPTION_POLICY_INVALID`：模型订阅策略无效。

套餐权限不足用 HTTP 403。

Chatpoint 余额不足建议用 HTTP 402，前端可以明确识别为额度不足，而不是普通权限错误。

## 测试策略

实现时后端必须先写测试，再写功能。

重点测试：

- 默认套餐种子数据。
- 新用户默认 Free 订阅，Plan Chatpoint 为 10。
- 周期到期后 Plan Chatpoint 重置。
- Check Chatpoint 不随周期重置清零。
- Plus 到期后自动降级 Free。
- Plus 过期后不能继续按 Plus 额度重置。
- 先扣 Plan，再扣 Check。
- 当前请求可以扣成负数。
- 负数或 0 余额后，后续 metered 请求被拒绝。
- unlimited 模型不扣 Chatpoint。
- 管理员不受限制也不扣费。
- 模型按套餐过滤。
- 不允许套餐调用的模型在聊天接口被拒绝。
- 单次码只能用一次。
- 多次码按最大次数限制。
- 同一用户不能重复兑换同一个码。
- 低档套餐码不会降级高档订阅。
- 同档套餐码会延长时间。
- 高档套餐码会升级。
- 使用、兑换、调整、重置都写入流水。

前端验证：

- 设置页有 Subscription、Redeem Code、Usage 三个标签。
- 账号页有账单地址和记录。
- 左下角有套餐 badge 和环状额度图。
- 额度用尽时环状图变红。
- 点击环状图打开 Usage 页面。
- 管理员设置里有 Subscriptions 入口。
- 管理员订阅页有 Plans、Model Access、Redeem Codes、User Subscriptions、Usage、Ledger。
- 管理员用户编辑弹窗有订阅摘要和管理入口。

集成验证：

- Free 用户只能看到 Free 允许的模型。
- 兑换 Plus 后可以看到 Plus 模型。
- metered 模型调用后产生用量和扣费流水。
- unlimited 模型调用后用量为 token，Chatpoint 消耗为 0。
- 付费订阅过期后自动降级 Free，并按 Free 额度重置。

## 上线顺序

建议按阶段实现：

1. 数据库表、迁移、默认套餐种子数据、纯后端服务测试。
2. 订阅服务和兑换码服务。
3. 模型列表过滤和聊天接口强制校验。
4. 模型响应后的用量捕获和 Chatpoint 扣费。
5. 用户订阅页、兑换页、用量页、账单地址、左下角环状图。
6. 管理员订阅后台和模型策略编辑器。
7. 完整集成验证和 Docker 镜像重建。

不要每个小改动都重建 Docker。一个阶段完成并需要运行验证时再构建。构建失败时先清理无用容器和悬空镜像，再看 `docker system df`，不要一上来清掉全部 build cache。

## 风险点

- 流式响应的 usage 可能在最后才返回，扣费逻辑必须在响应完成后执行。
- 有些模型供应商可能不返回 usage，需要记录 `missing_usage`。
- 多模型对话需要每个模型单独检查和单独记录用量。
- 后台套餐调整不影响已有用户，这必须靠用户订阅快照保证，不能只靠页面提示。
- 自动降级必须发生在周期重置之前，避免过期 Plus 继续刷新 Plus 额度。
- Chatpoint 小数计算不能用普通 float。
- 模型订阅策略存在 `meta` 里，后端必须校验，不能相信前端提交的 JSON。
