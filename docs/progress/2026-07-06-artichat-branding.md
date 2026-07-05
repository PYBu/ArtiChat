# 2026-07-06 ArtiChat Branding Pass

## Summary

- Replaced user-facing product identity with ArtiChat across app shell metadata, settings, about/help surfaces, update/changelog responses, share/community helpers, notifications, manifests, OpenSearch metadata, and static logo/favicon/splash assets.
- Replaced Docker operator-facing names with ArtiChat: compose service `artichat`, container `artichat`, image `artichat:main`, port variable `ARTICHAT_PORT`, and data volume `artichat_data`.
- Added `npm run test:branding` as a focused guard for user-visible and operator-visible branding regressions.

## Verification

- `npm run test:branding`: passed, scanning 38 files.
- `npm run build`: passed.
- Build output scan for old branding terms: passed.
- `docker compose -p artichat build --build-arg USE_SLIM=true artichat`: passed.
- `docker compose -p artichat up -d --no-deps artichat`: running healthy at `http://localhost:3000`.
- `/health`: 200, `{"status":true}`.
- `/`: 200, page title is `ArtiChat`.
- `/api/config`: 200, reports name `ArtiChat`.
- `/api/changelog`: 200, returns a neutral ArtiChat release note.
- Runtime scan of `/`, `/manifest.json`, `/static/site.webmanifest`, `/static/favicon.svg`, `/api/config`, and `/api/changelog`: no old branding terms found.
- Recent `artichat` container logs: no old branding terms found.

## Cleanup

- Migrated app data from the old compose volume to `artichat_data`.
- Removed old Docker volumes `artichat_artichat-data` and `artichat_open-webui`.
- Removed old image tag `ghcr.io/open-webui/open-webui:main`.
- No failed Docker build occurred during the final rebuild, so no failed-build image cleanup was required.

## Known Baseline Issue

- `npm run check` still fails on the inherited Svelte/TypeScript baseline. Latest observed baseline was about 9.5k errors and 273 warnings, concentrated in existing route/component typing issues unrelated to this branding pass.
