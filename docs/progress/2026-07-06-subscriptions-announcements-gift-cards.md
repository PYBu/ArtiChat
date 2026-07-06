# 2026-07-06 Subscriptions, Announcements, and Gift Cards

## Summary

- Added subscription quota foundations for Free, Plus, and ChatPower, including plan quota, check quota, metered model access, model quota multipliers, periodic reset handling, and admin-editable plan/model policy.
- Added user-facing subscription, redemption, and usage surfaces with shared subscription refresh state.
- Updated the sidebar subscription indicator to show the subscription label beside a smaller quota ring, with usage tooltip details and red exhausted state.
- Added admin tools for subscription plans, user subscriptions, usage ledger, model access policy, redemption codes, gift cards, and announcements.
- Added custom redemption code support, full code display in admin, soft-delete support for codes, and pending gift card claiming from the user redemption page.
- Added announcement modal support with once, every-login, and new-user display modes.
- Added user context to admin subscription and usage views so admins can search/display by email or username instead of relying on user IDs.
- Fixed the usage metadata serialization failure that prevented usage rows from being recorded when request metadata contained non-JSON-safe values.

## Defaults

- Free: 100 Chatpoint plan quota.
- Plus: 3000 Chatpoint plan quota.
- ChatPower: 10000 Chatpoint plan quota.
- Existing subscriptions keep their allocated values; admin edits to plan defaults do not rewrite already-subscribed user balances.

## Commits

- `3bb1cf4 docs: plan subscription admin polish`
- `a04f3ee feat: add subscription admin backend polish`
- `f02cf38 feat: add subscription admin frontend polish`

## Verification

- `pytest backend/open_webui/tests/subscriptions -q`: 39 passed, 1 warning.
- `npm run test:subscriptions`: passed.
- `npm run build`: passed.
- `docker compose -p artichat build artichat`: passed.
- `docker compose -p artichat up -d --no-deps artichat`: running healthy at `http://localhost:3000`.
- `/health`: 200, `{"status":true}`.

## Deployment

- Rebuilt Docker image `artichat:main`.
- Recreated container `artichat` with the existing `artichat_data` data volume preserved.
- Current runtime status: `artichat` is healthy on port `3000`.

## Cleanup

- `docker image prune -f`: completed, reclaimed `0B`.
- No failed Docker build occurred in this round, so no failed-build image cleanup was required.

## Notes

- Runtime data such as local accounts, model configuration, chat history, subscriptions, redemption codes, gift cards, announcements, and usage ledger entries lives in the `artichat_data` Docker volume.
- Server deployment should migrate `artichat_data` along with the image if these runtime records need to be preserved.
