# ArtiChat Subscriptions Design

## Goal

Add a first-party subscription and quota system for ArtiChat that controls model visibility, model access, Chatpoint usage, redemption codes, and admin-managed subscription operations.

The MVP supports three tiers: `free`, `plus`, and `chatpower`. Payments are intentionally out of scope for this pass; purchase actions are placeholders, while redemption codes and admin edits are fully supported.

## Current Context

Relevant backend structure:

- Runtime model list endpoint: `backend/open_webui/main.py` at `/api/models`.
- Chat completion endpoint: `backend/open_webui/main.py` at `/api/chat/completions`.
- Workspace model persistence: `backend/open_webui/models/models.py`.
- Workspace model admin/user routes: `backend/open_webui/routers/models.py`.
- User routes: `backend/open_webui/routers/users.py`.
- Token usage normalization: `backend/open_webui/utils/response.py`.
- Chat message token storage and analytics aggregation: `backend/open_webui/models/chat_messages.py`.
- Admin analytics routes: `backend/open_webui/routers/analytics.py`.
- Database base/session helpers: `backend/open_webui/internal/db.py`.

Relevant frontend structure:

- User settings modal: `src/lib/components/chat/SettingsModal.svelte`.
- User account settings: `src/lib/components/chat/Settings/Account.svelte`.
- Admin settings shell: `src/lib/components/admin/Settings.svelte`.
- Admin users shell: `src/lib/components/admin/Users.svelte`.
- Admin user edit modal: `src/lib/components/admin/Users/UserList/EditUserModal.svelte`.
- Workspace model editor: `src/lib/components/workspace/Models/ModelEditor.svelte`.
- Lower-left user menu: `src/lib/components/layout/Sidebar/UserMenu.svelte`.

## Scope

Included:

- Subscription plans for Free, Plus, and ChatPower.
- Periodic Plan Chatpoint reset by user subscription start date.
- Check Chatpoint balance for recharge/redemption value that does not reset.
- Model subscription policies with allowed tiers, quota mode, and usage multiplier.
- Chatpoint deduction from real input + output token usage.
- Redemption code creation, activation, usage limits, and records.
- User subscription, redemption, usage, billing address, and history UI.
- Lower-left subscription badge and quota ring in the user button area.
- Admin subscription settings for plans, model access, redemption codes, user subscriptions, usage, and ledger.
- Backend enforcement in model listing and chat completion paths.
- Automated tests for subscription lifecycle, quota accounting, redemption codes, model filtering, and admin bypass.

Excluded:

- Real payment provider integration.
- Invoice generation, tax calculation, or payment reconciliation.
- Revenue reporting beyond subscription usage and ledger records.
- Hard cost accounting for provider invoices.
- Retroactive billing for historical messages that were created before this feature.

## Subscription Tiers

Default seeded plans:

| Tier | Display Name | Rank | Default Plan Chatpoint | Period |
| --- | --- | ---: | ---: | ---: |
| `free` | Free | 0 | 10 | 30 days |
| `plus` | Plus | 1 | 100 | 30 days |
| `chatpower` | ChatPower | 2 | 500 | 30 days |

Admin plan settings can be edited after launch, but edits do not mutate existing user subscriptions. New subscriptions, future upgrades, and automatic downgrades create a user subscription snapshot from the plan configuration that is current at that moment.

## Chatpoint Accounting

Canonical conversion:

- `100 Chatpoint = 1,000,000 tokens`.
- `1 Chatpoint = 10,000 tokens`.
- Raw token cost before multiplier is `tokens / 10000`.
- Final cost is `tokens / 10000 * usage_multiplier`.

Use integer micro-Chatpoint storage for balances and ledger amounts:

- `1 Chatpoint = 1,000,000 cp_micros`.
- `1 token at multiplier 1 = 100 cp_micros`.
- Store `usage_multiplier` as a decimal string or fixed precision numeric value.
- Do calculations with Decimal semantics server-side, then round up to the nearest micro-Chatpoint so usage is never under-billed by floating point drift.

Balances:

- `Plan Chatpoint`: periodic plan allowance. It resets each subscription period and is consumed first.
- `Check Chatpoint`: recharge/redemption allowance. It is consumed after Plan Chatpoint and does not reset.

Deduction order:

1. Debit Plan Chatpoint until it reaches zero.
2. Debit Check Chatpoint for any remaining cost.
3. If the current request costs more than the remaining total, allow the request to finish and let the resulting balance become negative.
4. Later metered requests are blocked while `plan_balance + check_balance <= 0`.

Unlimited models:

- Track token usage for reporting.
- Record zero Chatpoint cost.
- Do not require a positive balance.

Admin users:

- Bypass subscription tier restrictions.
- Bypass quota checks.
- Do not receive Chatpoint debits.

## Subscription Lifecycle

Every user has an effective subscription. If no paid subscription exists, the user is treated as Free.

Each user subscription stores a plan snapshot:

- `tier`.
- `tier_rank`.
- `display_name`.
- `period_days`.
- `plan_chatpoint_allowance_micros`.
- `starts_at`.
- `expires_at` for paid tiers.
- `period_start_at`.
- `period_end_at`.
- `next_reset_at`.

`ensure_subscription_current(user_id)` is the lifecycle gate. It is called before user subscription reads, model listing, chat completion, redemption, and admin subscription views.

Lifecycle rules:

- If a paid Plus or ChatPower subscription is active, periodic Plan Chatpoint resets use that subscription snapshot.
- If a paid subscription expires and is not renewed, the user is automatically downgraded to Free.
- On automatic downgrade, create a new Free subscription snapshot from the current Free plan configuration.
- After downgrade, Plan Chatpoint resets use Free rules only. An expired Plus or ChatPower subscription must never keep resetting Plus or ChatPower allowance.
- Check Chatpoint survives renewal, downgrade, and periodic reset.
- Admin manual edits create ledger entries and update the user snapshot explicitly.

Period handling:

- Periods are rolling from the user's subscription start or latest downgrade time.
- A user who activates Plus on July 6 has period boundaries on the 6th of each period.
- If multiple periods were missed, `ensure_subscription_current` advances to the current period and performs one current reset, not one ledger spam entry per missed period.

## Data Model

Create a new backend module: `backend/open_webui/models/subscriptions.py`.

### `subscription_plan`

Stores editable plan defaults.

Fields:

- `id`: text primary key, values `free`, `plus`, `chatpower`.
- `display_name`: text.
- `tier_rank`: integer.
- `period_days`: integer, default 30.
- `plan_chatpoint_allowance_micros`: big integer.
- `description`: text nullable.
- `features`: JSON nullable, used for plan display cards.
- `is_active`: boolean.
- `sort_order`: integer.
- `created_at`: big integer epoch seconds.
- `updated_at`: big integer epoch seconds.

### `user_subscription`

Stores the current effective subscription snapshot and balances for each user.

Fields:

- `id`: text primary key.
- `user_id`: text unique index.
- `tier`: text.
- `tier_rank`: integer.
- `display_name`: text.
- `period_days`: integer.
- `plan_chatpoint_allowance_micros`: big integer.
- `plan_balance_micros`: big integer.
- `check_balance_micros`: big integer.
- `starts_at`: big integer.
- `expires_at`: big integer nullable.
- `period_start_at`: big integer.
- `period_end_at`: big integer.
- `next_reset_at`: big integer.
- `status`: text, values `active`, `expired`, `free`, `admin_adjusted`.
- `source`: text, values `default`, `redemption`, `admin`.
- `snapshot`: JSON nullable.
- `billing_address`: JSON nullable.
- `notes`: text nullable.
- `created_at`: big integer.
- `updated_at`: big integer.

### `subscription_ledger`

Append-only balance and subscription event log.

Fields:

- `id`: text primary key.
- `user_id`: text index.
- `event_type`: text, for example `period_reset`, `redemption`, `usage_debit`, `admin_adjustment`, `tier_change`, `auto_downgrade`.
- `tier_before`: text nullable.
- `tier_after`: text nullable.
- `plan_delta_micros`: big integer.
- `check_delta_micros`: big integer.
- `plan_balance_after_micros`: big integer.
- `check_balance_after_micros`: big integer.
- `reference_type`: text nullable, for example `usage`, `redemption_code`, `admin`.
- `reference_id`: text nullable.
- `metadata`: JSON nullable.
- `created_by`: text nullable.
- `created_at`: big integer.

### `redemption_code`

Stores code definitions.

Fields:

- `id`: text primary key.
- `code_hash`: text unique index.
- `code_preview`: text for safe display, for example first 4 and last 4 characters.
- `mode`: text, values `single_use`, `multi_use`.
- `max_uses`: integer.
- `used_count`: integer.
- `tier`: text nullable. Null means do not change subscription tier.
- `duration_days`: integer nullable.
- `plan_chatpoint_micros`: big integer.
- `check_chatpoint_micros`: big integer.
- `expires_at`: big integer nullable.
- `is_active`: boolean.
- `batch_id`: text nullable.
- `memo`: text nullable.
- `created_by`: text.
- `created_at`: big integer.
- `updated_at`: big integer.

Store only a hash of the actual code. Generated codes are shown once in the admin UI and can be copied/exported immediately after creation.

### `redemption_record`

Stores activation history.

Fields:

- `id`: text primary key.
- `redemption_code_id`: text index.
- `user_id`: text index.
- `tier_before`: text nullable.
- `tier_after`: text nullable.
- `plan_delta_micros`: big integer.
- `check_delta_micros`: big integer.
- `subscription_expires_at_before`: big integer nullable.
- `subscription_expires_at_after`: big integer nullable.
- `created_at`: big integer.

Add a uniqueness rule for `(redemption_code_id, user_id)` so one user cannot redeem the same code twice.

### `subscription_usage`

Stores billed and unbilled usage events.

Fields:

- `id`: text primary key.
- `user_id`: text index.
- `chat_id`: text nullable.
- `message_id`: text nullable.
- `model_id`: text index.
- `tier`: text.
- `quota_mode`: text, values `unlimited`, `metered`.
- `usage_multiplier`: text or fixed precision numeric.
- `input_tokens`: integer.
- `output_tokens`: integer.
- `total_tokens`: integer.
- `cost_micros`: big integer.
- `plan_cost_micros`: big integer.
- `check_cost_micros`: big integer.
- `plan_balance_after_micros`: big integer nullable.
- `check_balance_after_micros`: big integer nullable.
- `status`: text, values `billed`, `unlimited`, `admin_bypass`, `missing_usage`.
- `metadata`: JSON nullable.
- `created_at`: big integer.

If a metered provider response lacks usage, record `missing_usage` with zero cost so admins can find unbilled gaps.

## Model Subscription Policy

Use `model.meta.subscription` so the existing `model` table does not need a schema change.

Shape:

```json
{
  "subscription": {
    "allowed_tiers": ["free", "plus", "chatpower"],
    "quota_mode": "metered",
    "usage_multiplier": "1.0"
  }
}
```

Rules:

- Existing access grants still apply first.
- Subscription policy is an additional gate after access grants.
- Effective access for ordinary users is `existing_access && tier_allowed`.
- Admins bypass this gate.
- Missing policy defaults to all tiers allowed, `metered`, multiplier `1.0` to preserve broad availability until admins configure policies.
- `quota_mode = unlimited` means zero Chatpoint debit.
- `quota_mode = metered` means the model requires a positive balance before request start and debits after response completion.
- `usage_multiplier` must be `>= 0`. The UI should use `unlimited` instead of a zero multiplier, but the backend must reject negative values.

Backend enforcement points:

- Filter `/api/models` and `/api/v1/models` output so ordinary users only see tier-allowed models.
- Check `/api/chat/completions` and `/api/v1/chat/completions` before generation so direct API callers cannot bypass UI filtering.
- For multi-model chat requests, check each target model independently.

## Redemption Rules

Code types:

- `single_use`: generated as one or more unique codes, each can be redeemed once.
- `multi_use`: one code with a configurable maximum use count.

Code payload:

- Optional tier: Free, Plus, ChatPower, or no tier change.
- Optional duration days, used only when the code changes or extends a subscription.
- Optional Plan Chatpoint grant.
- Optional Check Chatpoint grant.
- Optional expiration time.
- Active/disabled state.
- Admin memo.

Activation rules:

- Codes may grant only Check Chatpoint, only temporary Plan Chatpoint, only subscription time, or any combination.
- Tier changes are only-upgrade.
- A lower-rank plan code never downgrades an active higher-rank subscription. Its Chatpoint grants still apply.
- Same-tier codes extend from `max(now, current_expires_at)`.
- Higher-tier codes switch the user immediately and set expiry to `max(now, current_expires_at) + duration_days`.
- If a code has a tier and duration, the user's recurring Plan Chatpoint snapshot comes from that tier's current plan configuration.
- Plan Chatpoint grants on a code are added to the current period balance only. They do not modify recurring Plan Chatpoint allowance.
- Check Chatpoint grants are added to Check balance and survive resets and downgrades.
- Every successful redemption writes both `redemption_record` and `subscription_ledger`.

## API Design

Add router: `backend/open_webui/routers/subscriptions.py`.

Include in `backend/open_webui/main.py`:

```python
app.include_router(subscriptions.router, prefix='/api/v1/subscriptions', tags=['subscriptions'])
```

User endpoints:

- `GET /api/v1/subscriptions/me`
  - Returns current subscription snapshot, balances, period, status, and display-ready totals.
- `GET /api/v1/subscriptions/usage`
  - Returns current period usage summary, model breakdown, recent usage events, and recent ledger events.
- `POST /api/v1/subscriptions/redeem`
  - Body: `{ "code": "..." }`.
  - Applies code and returns the updated subscription plus redemption result.
- `GET /api/v1/subscriptions/records`
  - Returns user's subscription, redemption, adjustment, reset, and usage ledger records.
- `PUT /api/v1/subscriptions/billing-address`
  - Saves billing address JSON on the user's subscription record.

Admin endpoints:

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

## User Interface

### Settings Tabs

Add user settings tabs in `src/lib/components/chat/SettingsModal.svelte`:

- `Subscription`
- `Redeem Code`
- `Usage`

Subscription tab:

- Current plan card.
- Status: active, expiring, expired/downgraded to Free.
- Expiry time.
- Current period start/end.
- Next reset time.
- Plan Chatpoint balance.
- Check Chatpoint balance.
- Three tier cards for Free, Plus, and ChatPower using the existing quiet card style.
- Purchase buttons are placeholders and show a "not available yet" message.
- Redeem button switches to the Redeem Code tab.

Redeem Code tab:

- Code input.
- Activate button.
- Success result showing tier, duration, Plan Chatpoint, and Check Chatpoint gained.
- Specific errors for invalid, expired, disabled, exhausted, and already-redeemed codes.
- Refresh subscription state after success.

Usage tab:

- Current period total usage.
- Plan and Check Chatpoint consumed.
- Model grouped table:
  - model name/id.
  - input tokens.
  - output tokens.
  - total tokens.
  - multiplier.
  - Chatpoint cost.
- Recent usage events.
- Unlimited models show token usage with zero Chatpoint cost.

### Account Tab

Extend `src/lib/components/chat/Settings/Account.svelte` with:

- Billing address fields:
  - name or company.
  - country/region.
  - address.
  - postal code.
  - tax id or notes.
- Subscription and redemption history summary:
  - event type.
  - timestamp.
  - tier change.
  - Plan/Check Chatpoint delta.
  - source.

### Lower-Left User Button

Extend the lower-left user button area:

- Show tier badge: Free, Plus, ChatPower.
- Show a compact quota ring chart for ordinary users.
- Admin users show an Admin badge and no quota ring.
- Ring represents overall metered quota usage.
- Normal color for healthy balance.
- Warning color for low balance.
- Red when Plan + Check Chatpoint is exhausted or negative.
- Hovering the ring opens a compact popover:
  - Title: `Usage`.
  - `Plan Chatpoint 100 / 1000` plus a line progress bar.
  - `Check Chatpoint 20 / 200` plus a line progress bar.
  - `Next reset: YYYY-MM-DD`.
  - If exhausted, show that metered models are unavailable until reset, redemption, or admin adjustment.
- Clicking the ring opens settings directly to the Usage tab.
- On mobile, tapping the ring opens Usage because hover is unavailable.

## Admin Interface

Use the previously agreed structure:

- Full subscription management lives under `Admin Settings > Subscriptions`.
- `Admin > Users` remains focused on users, roles, and groups.
- Admin user edit modal shows a compact subscription summary and a "Manage Subscription" action that navigates to the full subscription admin screen for that user.

Admin subscription areas:

### Plans

- Edit Free, Plus, and ChatPower defaults.
- Fields:
  - display name.
  - enabled state.
  - default Plan Chatpoint period allowance.
  - period days.
  - description.
  - feature bullets for plan cards.
  - sort order.
- Display a note that plan edits affect future snapshots only.

### Model Access

- List all workspace/base models.
- Show each model policy:
  - allowed tiers.
  - quota mode.
  - usage multiplier.
- Inline edit policy.
- Also expose the same policy section in `ModelEditor.svelte` for create/edit flows.

### Redeem Codes

- Create single-use batches or multi-use codes.
- Configure:
  - code type.
  - quantity for single-use.
  - max uses.
  - tier.
  - duration days.
  - Plan Chatpoint grant.
  - Check Chatpoint grant.
  - expiration.
  - memo.
- List code previews, use counts, state, expiration, created time.
- Copy/export newly generated raw codes at creation time.
- Disable codes.
- View redemption records.

### User Subscriptions

- Search users.
- View:
  - current tier.
  - expiry.
  - Plan Chatpoint.
  - Check Chatpoint.
  - current period.
  - next reset.
- Edit:
  - tier.
  - expiry.
  - Plan balance.
  - Check balance.
  - period start/end.
  - note.
- Every edit writes a ledger record.

### Usage And Ledger

- View usage by user and model.
- Filter by date, user, model, tier, and event type.
- View ledger entries for resets, redemptions, admin adjustments, usage debits, tier changes, and auto downgrades.

## Error Handling

Backend errors should use stable error codes in response detail so the frontend can show precise text.

Recommended errors:

- `SUBSCRIPTION_TIER_REQUIRED`: model is not allowed for current tier.
- `CHATPOINT_BALANCE_EXHAUSTED`: metered model cannot start because Plan + Check balance is zero or negative.
- `REDEMPTION_CODE_INVALID`: code does not exist.
- `REDEMPTION_CODE_DISABLED`: code exists but is disabled.
- `REDEMPTION_CODE_EXPIRED`: code expired.
- `REDEMPTION_CODE_EXHAUSTED`: max uses reached.
- `REDEMPTION_CODE_ALREADY_USED`: same user already used this code.
- `SUBSCRIPTION_PLAN_INACTIVE`: requested plan is not active.
- `MODEL_SUBSCRIPTION_POLICY_INVALID`: admin submitted invalid policy.

Use HTTP 403 for tier access failures. Use HTTP 402 for exhausted Chatpoint balance so the frontend can distinguish quota from permission.

## Testing Strategy

Implementation must use TDD for backend subscription behavior.

High-value backend tests:

- Seed default plans.
- Create default Free subscription for a user with 10 Plan Chatpoint.
- Reset Plan Chatpoint on rolling period boundary.
- Preserve Check Chatpoint across period reset.
- Auto-downgrade expired Plus to Free before reset.
- Ensure expired Plus cannot reset Plus allowance.
- Debit Plan before Check.
- Allow a request to make balance negative.
- Reject later metered request while total balance is zero or negative.
- Do not debit unlimited models.
- Do not restrict or debit admin users.
- Apply model policy filtering for ordinary users.
- Reject chat completion for a disallowed tier.
- Apply single-use redemption once.
- Apply multi-use redemption until max uses.
- Prevent the same user from redeeming the same code twice.
- Ignore lower-tier plan changes while still applying code Chatpoint grants.
- Extend same-tier plans.
- Upgrade to higher-tier plans.
- Record ledger, redemption, and usage rows.

Frontend verification:

- User settings has Subscription, Redeem Code, and Usage tabs.
- Account settings exposes billing address and records.
- Lower-left user button shows a plan badge and quota ring.
- Quota ring turns red when total metered balance is exhausted or negative.
- Clicking the ring opens the Usage tab.
- Admin settings has a Subscriptions entry with Plans, Model Access, Redeem Codes, User Subscriptions, Usage, and Ledger areas.
- Admin Users edit modal shows a compact subscription summary and links to subscription management.

Integration verification:

- Free user only sees models allowed for Free.
- Plus redemption makes Plus models visible.
- Metered model usage creates usage and ledger rows.
- Unlimited model usage creates usage with zero Chatpoint debit.
- Expired paid subscription downgrades to Free and resets with Free allowance.

## Rollout Strategy

Implement in stages:

1. Database models, migrations, seed data, and pure service tests.
2. Subscription service and redemption service.
3. Model filtering and chat completion enforcement.
4. Usage capture and Chatpoint debit after model responses.
5. User-facing subscription, redemption, usage, billing address, and lower-left quota ring UI.
6. Admin subscription pages and model policy editor.
7. Full integration verification and Docker rebuild.

Do not rebuild the Docker image until a stage is ready to verify in the running app. If a build fails, prune unused containers and dangling images first, then inspect `docker system df` before doing broader cache cleanup.

## Risks

- Streaming responses may report final usage late; usage capture must hook after completion, not only at request start.
- Some providers may omit usage. Those calls should be visible as `missing_usage` rather than silently disappearing.
- Multi-model chats require one quota check and one usage record per model.
- Plan edits not affecting existing users must be enforced by snapshots, not only by UI copy.
- Automatic downgrade must run before period reset to prevent expired paid subscriptions from refreshing paid allowance.
- Decimal Chatpoint math must avoid float drift.
- Model policies stored in `meta` are flexible but need backend validation because clients can submit arbitrary JSON.
