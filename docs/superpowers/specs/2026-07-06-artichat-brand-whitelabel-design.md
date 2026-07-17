# ArtiChat Brand Whitelabel Design

## Goal

Replace the user-visible upstream product identity with the ArtiChat brand across the running application and build output.

The visible product name is `ArtiChat`. The visual identity uses the existing A mark from `artivis-ass/logo`, paired with `ArtiChat` text where space allows and reduced to the mark alone for small icons.

## Licensing Assumption

The project owner has confirmed that an enterprise license permits full whitelabeling. Under that assumption, user-facing screens and build artifacts must not display upstream brand names, logos, social links, release links, or attribution text.

Legal license files and internal historical project records are outside this pass and remain unchanged.

## Scope

This pass covers user-visible and build-output branding:

- Browser title and app metadata.
- Frontend default app name.
- Backend default `WEBUI_NAME`.
- Logic that currently appends the upstream brand name to custom names.
- Login page logo and text.
- Sidebar logo and product name.
- Splash images.
- Favicon, apple touch icon, PWA icons, manifest names, and notification icons.
- Settings About content.
- Admin settings About content.
- User-visible strings that mention the upstream product name in active UI surfaces.
- Docker/compose-facing names only where they are visible to a normal operator of this branded product and are safe to change.

## Non-Goals

This pass does not change:

- `LICENSE`, `LICENSE_NOTICE`, or `LICENSE_HISTORY`.
- Historical progress notes and specs that document the source import.
- Internal source comments that are not displayed to users.
- Wire protocol names or internal data keys where changing them could break existing data, integrations, drag/drop behavior, or plugins.
- Third-party package names that are part of dependency metadata.
- Upstream feature behavior unrelated to branding.

## Brand Rules

- Use `ArtiChat` as the visible product name.
- Use the A mark as the favicon, small app icon, notification icon, and splash symbol.
- Use `A mark + ArtiChat` where the UI has enough horizontal space.
- Do not show upstream social badges, upstream repository stars, upstream release links, or upstream company attribution in About.
- About should present ArtiChat simply: product name, current app version if already available, and local/support-neutral product information.

## Implementation Shape

Prefer centralized brand constants and asset replacement over scattered one-off edits.

Expected frontend changes:

- Change `src/lib/constants.ts` default app name to `ArtiChat`.
- Replace hardcoded notification suffixes and page titles that still name the upstream product.
- Replace About page content in `src/lib/components/chat/Settings/About.svelte`.
- Replace admin About/general settings content in `src/lib/components/admin/Settings/General.svelte`.
- Replace user-visible i18n source keys only where active UI components call those strings.
- Keep internal event names and drag/drop MIME strings stable if they are not displayed.

Expected backend changes:

- Change `backend/open_webui/env.py` default `WEBUI_NAME` to `ArtiChat`.
- Remove the logic that appends the upstream product name when `WEBUI_NAME` is customized.
- Change backend defaults that provide profile images, favicon URLs, or operator-visible app metadata when they surface in the frontend.

Expected asset changes:

- Generate or copy ArtiChat-branded replacements for favicon, dark favicon, splash, dark splash, apple touch icon, web app icons, SVG/ICO variants, and manifest files under `static/static` and any root-level static aliases used by the app.
- Preserve image dimensions and filenames expected by the existing app so routing and caching behavior remain stable.

## Verification

Before completion:

- Build the frontend or Docker image using the existing project workflow.
- Run the app and confirm `http://localhost:3000/health` returns success.
- Check the browser title and root page.
- Check login and sidebar identity.
- Check Settings About and Admin Settings About.
- Check `manifest.json` / `site.webmanifest` and static icon paths.
- Search built frontend output and relevant runtime-served static files for upstream brand strings.
- Search source for remaining upstream brand mentions and classify each as either user-visible and fixed, or internal/legal/history and intentionally unchanged.

## Storage And Rebuild Policy

Use Docker build cache normally. If a build fails, run conservative cleanup first:

- `docker container prune -f`
- `docker image prune -f`
- Inspect with `docker system df`

Avoid aggressive BuildKit cache pruning unless disk pressure requires it, because dependency caches prevent repeated large downloads.

## Risks

- Some user-visible strings may be generated from i18n source keys; changing only component text may miss translated or fallback text.
- Some upstream identifiers are also internal protocol/data keys; changing them blindly can break drag/drop, plugins, imports, or saved data.
- Static assets are duplicated in several paths, so all served aliases must be updated together.
- Existing Docker volume data may retain an old configured name; verification should account for backend defaults and persisted configuration separately.
