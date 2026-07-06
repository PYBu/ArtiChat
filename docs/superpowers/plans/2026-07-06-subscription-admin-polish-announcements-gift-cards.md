# Subscription Admin Polish, Announcements, and Gift Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the ArtiChat subscription polish round: live quota refresh, editable plan cards, announcements, full/custom redemption codes, gift card grants, default allowances, and admin user search/display improvements.

**Architecture:** Extend the existing subscription bounded area instead of creating a separate billing module. Keep ordinary redemption codes in `redemption_code`, add `gift_card_grant` for per-user pending gifts, and add `announcement` / `announcement_view` for modal announcements. Frontend state uses one shared subscription store so the quota ring, settings pages, redemption, and chat completion refresh the same data.

**Tech Stack:** FastAPI, SQLAlchemy async models, Alembic migrations, Pydantic models, Svelte 5, Svelte stores, existing Modal and admin settings components, pytest subscription tests, existing Node static subscription guard.

---

## File Map

- Modify `backend/open_webui/models/subscriptions.py`: defaults, plan seeding, full redemption code field, gift card grant models/table helpers, user-enriched subscription/usage/ledger helpers.
- Modify `backend/open_webui/routers/subscriptions.py`: public plans, code delete, custom code payload, gift card admin/user routes, user search and enriched admin responses.
- Create `backend/open_webui/models/announcements.py`: announcement and announcement view DB models/helpers.
- Create `backend/open_webui/routers/announcements.py`: user active announcements, mark viewed, admin CRUD routes.
- Modify `backend/open_webui/main.py`: include announcements router.
- Create migration `backend/open_webui/migrations/versions/f2a3b4c5d6e7_subscription_admin_polish.py`: add `redemption_code.code`, `gift_card_grant`, `announcement`, `announcement_view`.
- Modify tests under `backend/open_webui/tests/subscriptions/`: defaults, redemption, gift cards, announcements, admin user display/search.
- Modify `src/lib/apis/subscriptions/index.ts`: add public plans, code update/delete, gift cards.
- Create `src/lib/apis/announcements/index.ts`: announcement API helpers.
- Modify `src/lib/stores/index.ts`: subscription store or exports for shared subscription state.
- Modify `src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte`: shared state, smaller/thinner ring, label outside.
- Modify `src/lib/components/layout/Sidebar/UserMenu.svelte`: render label/ring in requested layout.
- Modify `src/lib/components/chat/Chat.svelte`: trigger subscription refresh after completion/active false.
- Modify `src/lib/components/chat/Settings/Subscription.svelte`: dynamic cards from plan API.
- Modify `src/lib/components/chat/Settings/RedeemCode.svelte`: pending gift card prompt and claim action.
- Modify `src/lib/components/chat/Settings/Usage.svelte`: use shared subscription refresh on mount.
- Modify admin subscription components: `Plans.svelte`, `RedeemCodes.svelte`, `UserSubscriptions.svelte`, `UsageLedger.svelte`, `Subscriptions.svelte`.
- Create admin components `Announcements.svelte` and `GiftCards.svelte`.
- Create `src/lib/components/AnnouncementModal.svelte` and mount in `src/routes/(app)/+layout.svelte`.
- Modify `scripts/check-subscriptions.mjs`: static checks for new UI/API markers.

## Tasks

### Task 1: Backend Tests First

**Files:**
- Modify tests in `backend/open_webui/tests/subscriptions/`

- [ ] Add failing tests for new default allowances and Free display name.
- [ ] Add failing tests for custom redemption code, full code listing, and soft delete blocking redemption.
- [ ] Add failing tests for gift card grant targeted issue, claim, duplicate claim prevention, revoke, and all-current-users issue.
- [ ] Add failing tests for announcements: once, every_login, new_user, viewed suppression.
- [ ] Add failing tests for admin user subscription search by email/username/name and enriched usage/ledger user data.
- [ ] Run:

```powershell
pytest backend/open_webui/tests/subscriptions -q
```

Expected: new tests fail because implementation is missing.

### Task 2: Backend Schema and Models

**Files:**
- Modify `backend/open_webui/models/subscriptions.py`
- Create `backend/open_webui/models/announcements.py`
- Create migration `backend/open_webui/migrations/versions/f2a3b4c5d6e7_subscription_admin_polish.py`

- [ ] Update `DEFAULT_PLAN_CHATPOINTS` to `100/3000/10000` and seed legacy old defaults without overwriting admin changes.
- [ ] Add `RedemptionCode.code`.
- [ ] Add `GiftCardGrant` model and helpers for create/list/claim/revoke.
- [ ] Add announcement models and helpers.
- [ ] Add user-enriched admin query helpers that join `User`.
- [ ] Run backend tests from Task 1 until model-level failures are resolved.

### Task 3: Backend Routers

**Files:**
- Modify `backend/open_webui/routers/subscriptions.py`
- Create `backend/open_webui/routers/announcements.py`
- Modify `backend/open_webui/main.py`

- [ ] Add public `GET /api/v1/subscriptions/plans`.
- [ ] Extend admin code creation with optional custom `code`.
- [ ] Add admin code delete/soft-delete route.
- [ ] Add gift card admin routes: create grants, list batches/items, revoke grant.
- [ ] Add user gift card routes: pending list, claim.
- [ ] Add announcement user/admin routes.
- [ ] Update existing admin user, usage, and ledger routes to return enriched user data.
- [ ] Run:

```powershell
pytest backend/open_webui/tests/subscriptions -q
```

Expected: subscription backend tests pass.

### Task 4: Frontend API and Shared Subscription Store

**Files:**
- Modify `src/lib/apis/subscriptions/index.ts`
- Create `src/lib/apis/announcements/index.ts`
- Modify `src/lib/stores/index.ts`

- [ ] Add API helpers for plans, code delete, gift cards, announcements.
- [ ] Add shared subscription writable store and refresh helpers.
- [ ] Run:

```powershell
npm run test:subscriptions
```

Expected: static guard may still fail until UI markers are added.

### Task 5: User Subscription UI

**Files:**
- Modify `src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte`
- Modify `src/lib/components/layout/Sidebar/UserMenu.svelte`
- Modify `src/lib/components/chat/Chat.svelte`
- Modify `src/lib/components/chat/Settings/Subscription.svelte`
- Modify `src/lib/components/chat/Settings/RedeemCode.svelte`
- Modify `src/lib/components/chat/Settings/Usage.svelte`

- [ ] Refactor quota ring to read shared store, shrink ring, thin stroke, move tier label left, keep tooltip details and red exhausted state.
- [ ] Trigger subscription refresh from chat done/active false.
- [ ] Render subscription cards from plan API and features content.
- [ ] Add pending gift card prompt and claim action to redeem page.
- [ ] Refresh shared subscription after redeem/claim and when usage page mounts.
- [ ] Remove user-facing “免费版” subscription name; use `Free`.

### Task 6: Admin UI

**Files:**
- Modify `src/lib/components/admin/Settings/Subscriptions.svelte`
- Modify `src/lib/components/admin/Settings/Subscriptions/Plans.svelte`
- Modify `src/lib/components/admin/Settings/Subscriptions/RedeemCodes.svelte`
- Modify `src/lib/components/admin/Settings/Subscriptions/UserSubscriptions.svelte`
- Modify `src/lib/components/admin/Settings/Subscriptions/UsageLedger.svelte`
- Create `src/lib/components/admin/Settings/Subscriptions/Announcements.svelte`
- Create `src/lib/components/admin/Settings/Subscriptions/GiftCards.svelte`

- [ ] Add tabs for announcements and gift cards.
- [ ] Replace raw JSON plan editor with structured display content fields.
- [ ] Add custom code input, full code display, and delete action to redemption code admin.
- [ ] Add gift card creation/list/revoke UI.
- [ ] Add announcement CRUD UI.
- [ ] Update search placeholder and row display to use email/name.

### Task 7: Announcement Modal

**Files:**
- Create `src/lib/components/AnnouncementModal.svelte`
- Modify `src/routes/(app)/+layout.svelte`

- [ ] Load active announcements after authenticated app layout initializes.
- [ ] Show modal queue using existing `Modal`.
- [ ] Mark viewed/seen based on display mode.
- [ ] Use sessionStorage for every-login suppression within the current session.

### Task 8: Static Checks, Build, and Cleanup

**Files:**
- Modify `scripts/check-subscriptions.mjs`

- [ ] Add checks for Free label, shared subscription refresh, gift card prompt, announcement admin tab, custom code, delete action, and user email display.
- [ ] Run:

```powershell
pytest backend/open_webui/tests/subscriptions -q
npm run test:subscriptions
npm run build
```

Expected: backend subscription tests and frontend build pass. `npm run check` is known to have unrelated existing Svelte/type failures and is not the completion gate for this round unless those failures are in touched files.

- [ ] If a Docker rebuild is performed and fails, clean dangling build artifacts/images before retrying.
