# 2026-07-06 ArtiChat Branding Pass

## Summary

- Replaced user-facing product identity with ArtiChat across app shell metadata, settings, about/help surfaces, update/changelog responses, share/community helpers, notifications, manifests, OpenSearch metadata, and static logo/favicon/splash assets.
- Replaced Docker operator-facing names with ArtiChat: compose service `artichat`, container `artichat`, image `artichat:main`, port variable `ARTICHAT_PORT`, and data volume `artichat_data`.
- Replaced package/operator metadata and defaults with ArtiChat, including npm package name, Python project metadata, CLI entry name, default forwarded header names, Redis key prefix, OTel service name, and data archive name.
- Removed remaining upstream community import/review/link surfaces, model attribution links, terminal integration references, external search user-agent identifiers, backend default prefixes, and translation entries.
- Added `npm run test:branding` as a focused guard for user-visible, operator-visible, backend outbound, and locale branding regressions.

## Verification

- `npm run test:branding`: passed, scanning 148 files. The npm script banner now reports `artichat@0.10.2`.
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
- Wide source scan across `src`, `backend`, `static`, package metadata, and compose files found no old branding terms outside excluded legal/history static files.

## Cleanup

- Migrated app data from the old compose volume to `artichat_data`.
- Removed old Docker volumes `artichat_artichat-data` and `artichat_open-webui`.
- Removed old image tag `ghcr.io/open-webui/open-webui:main`.
- No failed Docker build occurred during the final rebuild, so no failed-build image cleanup was required.

## Known Baseline Issue

- `npm run check` still fails on the inherited Svelte/TypeScript baseline. Latest observed baseline was about 9.5k errors and 273 warnings, concentrated in existing route/component typing issues unrelated to this branding pass.

## Task 10: 0.1.2 Local Verification

- `npm run test:release-version -- --tag=v0.1.2`: passed.
- `npm run test:branding`: passed, scanning 155 files.
- `npm run test:subscriptions`: passed.
- `npm run test:updates`: passed.
- `CI=true npm run test:frontend`: passed, 3 tests; emitted the inherited `.svelte-kit/tsconfig.json` warning before the build-generated config existed.
- `pytest backend/open_webui/tests/updates backend/open_webui/tests/subscriptions -q`: 87 passed, 1 existing SQLAlchemy deprecation warning.
- `npm run build`: passed in about 177 seconds. Existing Svelte accessibility, self-closing-tag, externalized Node module, and chunk-size warnings remain.

The local Docker smoke could not complete because external dependency downloads were unavailable from the Docker build environment:

- `docker compose -p artichat build --build-arg BUILD_HASH=$(git rev-parse HEAD) artichat`: failed while downloading the onnxruntime GPU archive with `ECONNRESET`.
- Retrying the same command reached Python dependency setup but failed when the build container accessed Hugging Face with `Connection refused`.
- Retrying with the existing Dockerfile `USE_SLIM=true` switch exceeded the 30-minute command limit before producing a new image.

The pre-existing `artichat:main` container remained healthy at `0.1.1`, and the `artichat_data` volume was not recreated or modified by these failed builds. Baseline counts before the smoke were: users 3, chats 14, subscription plans 3, redemption codes 4, announcements 1, and knowledge bases 1.
