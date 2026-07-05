# ArtiChat Brand Whitelabel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the user-visible upstream product identity with ArtiChat across the app shell, About screens, static assets, runtime metadata, and Docker-served build output.

**Architecture:** Use existing app constants and backend environment defaults as the source of truth, then remove user-visible hardcoded upstream strings from focused UI components. Add a branding guard script that scans the curated user-visible surface so future changes cannot reintroduce upstream branding in those paths.

**Tech Stack:** SvelteKit, TypeScript, Python/FastAPI, Node.js verification scripts, PowerShell asset generation, Docker Compose.

---

## File Structure

- Create `scripts/check-branding.mjs`: node-based guard that scans the user-visible branding surface for forbidden upstream strings.
- Create `scripts/generate-artichat-assets.ps1`: repeatable Windows asset generator using the existing `artivis-ass/logo/artimage-mark-*.png` files.
- Modify `package.json`: add `test:branding`.
- Modify `src/lib/constants.ts`: define the ArtiChat product name in the existing constants module.
- Modify `backend/open_webui/env.py`: set the backend default name and favicon URL.
- Modify `backend/open_webui/main.py`: update FastAPI title, startup banner, and release check behavior.
- Modify `backend/open_webui/constants.py`, `backend/open_webui/events.py`, `backend/open_webui/utils/automations.py`, `backend/open_webui/routers/audio.py`, `backend/open_webui/routers/openai.py`, `backend/open_webui/utils/oauth.py`: remove user-visible fallback strings that name the upstream product.
- Modify `src/app.html`, `src/routes/+layout.svelte`, `src/lib/components/channel/Channel.svelte`: update app shell titles and notifications.
- Modify `static/static/site.webmanifest`, `backend/open_webui/static/site.webmanifest`, `static/opensearch.xml`: update static metadata.
- Modify `src/lib/components/chat/Settings/About.svelte`: replace About with ArtiChat content.
- Modify `src/lib/components/admin/Settings/General.svelte`: remove upstream help/social/license marketing links and use neutral ArtiChat content.
- Modify `src/lib/components/layout/Sidebar/UserMenu.svelte`, `src/lib/components/layout/UpdateInfoToast.svelte`, `src/lib/components/chat/Settings/General.svelte`: remove upstream documentation, release, and translation links.
- Modify upstream community surfaces where they expose upstream names or domains:
  - `src/lib/components/workspace/Models.svelte`
  - `src/lib/components/workspace/Prompts.svelte`
  - `src/lib/components/workspace/Tools.svelte`
  - `src/lib/components/admin/Functions.svelte`
  - `src/lib/components/admin/Evaluations/Feedbacks.svelte`
  - `src/lib/components/chat/ShareChatModal.svelte`
  - `src/lib/components/chat/Settings/SyncStatsModal.svelte`
  - `src/lib/components/workspace/common/ManifestModal.svelte`
- Modify remaining active UI helper text where it names the upstream product:
  - `src/lib/components/chat/ToolServersModal.svelte`
  - `src/lib/components/admin/Settings/Audio.svelte`
  - `src/lib/components/admin/Settings/Events.svelte`
  - `src/lib/components/admin/Settings/ExternalKnowledge.svelte`
  - `src/lib/components/chat/Settings/Connections.svelte`
  - `src/lib/components/chat/Settings/Integrations.svelte`
- Generate or replace these static assets:
  - `static/favicon.png`
  - `static/static/favicon.png`
  - `static/static/favicon-dark.png`
  - `static/static/favicon-96x96.png`
  - `static/static/favicon.ico`
  - `static/static/favicon.svg`
  - `static/static/apple-touch-icon.png`
  - `static/static/logo.png`
  - `static/static/splash.png`
  - `static/static/splash-dark.png`
  - `static/static/web-app-manifest-192x192.png`
  - `static/static/web-app-manifest-512x512.png`
  - matching `backend/open_webui/static/*` aliases when they exist.

### Task 1: Add Branding Guard

**Files:**
- Create: `scripts/check-branding.mjs`
- Modify: `package.json`

- [ ] **Step 1: Write the failing branding guard**

Create `scripts/check-branding.mjs`:

```js
import fs from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();

const scannedFiles = [
	'src/app.html',
	'src/lib/constants.ts',
	'src/routes/+layout.svelte',
	'src/lib/components/channel/Channel.svelte',
	'src/lib/components/chat/Settings/About.svelte',
	'src/lib/components/admin/Settings/General.svelte',
	'src/lib/components/layout/UpdateInfoToast.svelte',
	'src/lib/components/layout/Sidebar/UserMenu.svelte',
	'src/lib/components/chat/Settings/General.svelte',
	'src/routes/error/+page.svelte',
	'static/static/site.webmanifest',
	'backend/open_webui/static/site.webmanifest',
	'static/opensearch.xml',
	'backend/open_webui/env.py',
	'backend/open_webui/main.py',
	'backend/open_webui/constants.py',
	'backend/open_webui/events.py',
	'backend/open_webui/utils/automations.py',
	'backend/open_webui/routers/audio.py',
	'backend/open_webui/routers/openai.py',
	'backend/open_webui/utils/oauth.py',
	'src/lib/components/workspace/Models.svelte',
	'src/lib/components/workspace/Prompts.svelte',
	'src/lib/components/workspace/Tools.svelte',
	'src/lib/components/admin/Functions.svelte',
	'src/lib/components/admin/Evaluations/Feedbacks.svelte',
	'src/lib/components/chat/ShareChatModal.svelte',
	'src/lib/components/chat/Settings/SyncStatsModal.svelte',
	'src/lib/components/workspace/common/ManifestModal.svelte',
	'src/lib/components/chat/ToolServersModal.svelte',
	'src/lib/components/admin/Settings/Audio.svelte',
	'src/lib/components/admin/Settings/Events.svelte',
	'src/lib/components/admin/Settings/ExternalKnowledge.svelte',
	'src/lib/components/chat/Settings/Connections.svelte',
	'src/lib/components/chat/Settings/Integrations.svelte'
];

const forbidden = [
	{ label: 'Open WebUI', pattern: /Open WebUI/g },
	{ label: 'OpenWebUI', pattern: /OpenWebUI/g },
	{ label: 'open-webui', pattern: /open-webui/g },
	{ label: 'Open_WebUI', pattern: /Open_WebUI/g },
	{ label: 'openwebui.com', pattern: /openwebui\.com/g },
	{ label: 'docs.openwebui.com', pattern: /docs\.openwebui\.com/g },
	{ label: 'github.com/open-webui', pattern: /github\.com\/open-webui/g }
];

const missing = scannedFiles.filter((file) => !fs.existsSync(path.join(repoRoot, file)));
if (missing.length > 0) {
	console.error(`Branding scan references missing files:\n${missing.map((file) => `- ${file}`).join('\n')}`);
	process.exit(1);
}

const failures = [];
for (const file of scannedFiles) {
	const absolutePath = path.join(repoRoot, file);
	const content = fs.readFileSync(absolutePath, 'utf8');
	const lines = content.split(/\r?\n/);

	for (const { label, pattern } of forbidden) {
		for (const [index, line] of lines.entries()) {
			pattern.lastIndex = 0;
			if (pattern.test(line)) {
				failures.push(`${file}:${index + 1}: forbidden ${label}: ${line.trim()}`);
			}
		}
	}
}

if (failures.length > 0) {
	console.error(`Forbidden upstream branding found in user-visible surface:\n${failures.join('\n')}`);
	process.exit(1);
}

console.log(`Branding scan passed for ${scannedFiles.length} files.`);
```

- [ ] **Step 2: Add the package script**

In `package.json`, add this script entry after `test:frontend`:

```json
"test:branding": "node scripts/check-branding.mjs",
```

- [ ] **Step 3: Run the guard and verify it fails**

Run: `npm run test:branding`

Expected: `FAIL` with lines that include existing upstream strings in `src/app.html`, `src/lib/constants.ts`, `backend/open_webui/env.py`, `src/lib/components/chat/Settings/About.svelte`, and `src/lib/components/admin/Settings/General.svelte`.

- [ ] **Step 4: Commit the failing guard**

```powershell
git add package.json scripts/check-branding.mjs
git commit -m "test: add ArtiChat branding guard"
```

### Task 2: Update Core Product Identity

**Files:**
- Modify: `src/lib/constants.ts`
- Modify: `backend/open_webui/env.py`
- Modify: `backend/open_webui/main.py`
- Modify: `backend/open_webui/events.py`
- Modify: `backend/open_webui/utils/automations.py`
- Modify: `backend/open_webui/constants.py`
- Modify: `backend/open_webui/routers/audio.py`
- Modify: `backend/open_webui/routers/openai.py`
- Modify: `backend/open_webui/utils/oauth.py`

- [ ] **Step 1: Run the guard before edits**

Run: `npm run test:branding`

Expected: `FAIL`, proving Task 1 catches the current branding problem.

- [ ] **Step 2: Change frontend constants**

In `src/lib/constants.ts`, replace the current app name export with:

```ts
export const APP_NAME = 'ArtiChat';
export const BRAND_NAME = 'ArtiChat';
```

- [ ] **Step 3: Change backend defaults**

In `backend/open_webui/env.py`, replace the WEBUI identity block with:

```py
WEBUI_NAME = os.getenv('WEBUI_NAME', 'ArtiChat')
WEBUI_FAVICON_URL = os.getenv('WEBUI_FAVICON_URL', '/static/favicon.png')
```

- [ ] **Step 4: Change FastAPI title, startup banner, and release checks**

In `backend/open_webui/main.py`:

```py
print(f'ArtiChat v{VERSION}\n{f"Commit: {WEBUI_BUILD_HASH}" if WEBUI_BUILD_HASH != "dev-build" else ""}')
```

Use this fallback print:

```py
print(f'ArtiChat v{VERSION}')
```

Set the FastAPI title:

```py
app = FastAPI(
    title='ArtiChat',
    docs_url='/docs' if ENV == 'dev' else None,
    openapi_url='/openapi.json' if ENV == 'dev' else None,
    redoc_url=None,
    lifespan=lifespan,
)
```

Change `/api/version/updates` so the branded build does not call the upstream GitHub release endpoint:

```py
@app.get('/api/version/updates')
async def get_app_latest_release_version(user=Depends(get_verified_user)):
    return {'current': VERSION, 'latest': VERSION}
```

- [ ] **Step 5: Change backend fallback strings**

Apply these replacements in the listed files:

```text
backend/open_webui/events.py: fallback app name -> 'ArtiChat'
backend/open_webui/utils/automations.py: fallback webui_name -> 'ArtiChat'
backend/open_webui/constants.py: 'Open WebUI: Server Connection Error' -> 'ArtiChat: Server Connection Error'
backend/open_webui/routers/audio.py: 'Open WebUI: Server Connection Error' -> 'ArtiChat: Server Connection Error'
backend/open_webui/routers/openai.py: 'Open WebUI: Server Connection Error' -> 'ArtiChat: Server Connection Error'
backend/open_webui/routers/openai.py: 'X-Title': 'Open WebUI' -> 'X-Title': 'ArtiChat'
backend/open_webui/routers/openai.py: 'HTTP-Referer': 'https://openwebui.com/' -> remove the header entry
backend/open_webui/utils/oauth.py: client_name='Open WebUI' -> client_name='ArtiChat'
```

- [ ] **Step 6: Run focused backend/frontend identity checks**

Run:

```powershell
npm run test:branding
```

Expected: still `FAIL` because app shell and About pages are not fixed yet, but no failures should remain in `src/lib/constants.ts`, `backend/open_webui/env.py`, `backend/open_webui/main.py`, `backend/open_webui/events.py`, `backend/open_webui/utils/automations.py`, `backend/open_webui/constants.py`, `backend/open_webui/routers/audio.py`, `backend/open_webui/routers/openai.py`, or `backend/open_webui/utils/oauth.py`.

- [ ] **Step 7: Commit core identity changes**

```powershell
git add src/lib/constants.ts backend/open_webui/env.py backend/open_webui/main.py backend/open_webui/events.py backend/open_webui/utils/automations.py backend/open_webui/constants.py backend/open_webui/routers/audio.py backend/open_webui/routers/openai.py backend/open_webui/utils/oauth.py
git commit -m "feat: set ArtiChat as core product identity"
```

### Task 3: Update App Shell Metadata

**Files:**
- Modify: `src/app.html`
- Modify: `src/routes/+layout.svelte`
- Modify: `src/lib/components/channel/Channel.svelte`
- Modify: `static/static/site.webmanifest`
- Modify: `backend/open_webui/static/site.webmanifest`
- Modify: `static/opensearch.xml`

- [ ] **Step 1: Run the branding guard**

Run: `npm run test:branding`

Expected: `FAIL` with app shell and static metadata branding hits.

- [ ] **Step 2: Update `src/app.html`**

Change the document title to:

```html
<title>ArtiChat</title>
```

- [ ] **Step 3: Update notification suffixes in `src/routes/+layout.svelte`**

Import `APP_NAME` from constants:

```ts
import { APP_NAME, WEBUI_API_BASE_URL, WEBUI_BASE_URL, WEBUI_HOSTNAME } from '$lib/constants';
```

Replace each browser notification suffix with the current branded name:

```ts
new Notification(`${data.title} • ${$WEBUI_NAME || APP_NAME}`, {
```

```ts
new Notification(`${displayTitle} • ${$WEBUI_NAME || APP_NAME}`, {
```

```ts
new Notification(`${title} • ${$WEBUI_NAME || APP_NAME}`, {
```

Limit accepted postMessage origins to local development origins only:

```ts
if (!['http://localhost:9999'].includes(event.origin)) {
    return;
}
```

- [ ] **Step 4: Update channel document titles**

In `src/lib/components/channel/Channel.svelte`, import `WEBUI_NAME` from stores:

```ts
import {
    chatId,
    channels,
    channelId as _channelId,
    showSidebar,
    socket,
    user,
    WEBUI_NAME
} from '$lib/stores';
```

Change titles to:

```svelte
} • {$WEBUI_NAME}</title
```

and:

```svelte
<title>#{channel?.name ?? 'Channel'} • {$WEBUI_NAME}</title>
```

- [ ] **Step 5: Update PWA metadata**

Set both `static/static/site.webmanifest` and `backend/open_webui/static/site.webmanifest` to:

```json
{
  "name": "ArtiChat",
  "short_name": "ArtiChat",
  "icons": [
    {
      "src": "/static/web-app-manifest-192x192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "maskable"
    },
    {
      "src": "/static/web-app-manifest-512x512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ],
  "theme_color": "#ffffff",
  "background_color": "#ffffff",
  "display": "standalone"
}
```

Set `static/opensearch.xml` names to:

```xml
<ShortName>ArtiChat</ShortName>
<Description>Search ArtiChat</Description>
```

- [ ] **Step 6: Run the guard**

Run: `npm run test:branding`

Expected: still `FAIL` because About/community surfaces are not fixed yet, but no app shell or metadata failures remain.

- [ ] **Step 7: Commit app shell changes**

```powershell
git add src/app.html src/routes/+layout.svelte src/lib/components/channel/Channel.svelte static/static/site.webmanifest backend/open_webui/static/site.webmanifest static/opensearch.xml
git commit -m "feat: brand ArtiChat app shell metadata"
```

### Task 4: Replace About, Help, and Update Surfaces

**Files:**
- Modify: `src/lib/components/chat/Settings/About.svelte`
- Modify: `src/lib/components/admin/Settings/General.svelte`
- Modify: `src/lib/components/layout/Sidebar/UserMenu.svelte`
- Modify: `src/lib/components/layout/UpdateInfoToast.svelte`
- Modify: `src/lib/components/chat/Settings/General.svelte`
- Modify: `src/routes/error/+page.svelte`

- [ ] **Step 1: Run the branding guard**

Run: `npm run test:branding`

Expected: `FAIL` with About, admin General, user menu, update toast, and settings help hits.

- [ ] **Step 2: Replace chat About content**

In `src/lib/components/chat/Settings/About.svelte`, keep version, changelog, Ollama version, license metadata, and Twemoji attribution. Remove upstream badges, upstream company copyright, upstream release links, and creator attribution.

Use this neutral license block:

```svelte
{#if $config?.license_metadata}
    <div class="mb-2 text-xs">
        <span class="text-gray-500 dark:text-gray-300 font-medium">{$WEBUI_NAME}</span>
        <span class="capitalize">{$config?.license_metadata?.type}</span> license registered to
        <span class="capitalize">{$config?.license_metadata?.organization_name}</span>
    </div>
{:else}
    <div class="text-xs text-gray-500 dark:text-gray-400">
        {$WEBUI_NAME} is running in a local self-hosted environment.
    </div>
{/if}
```

Use this copyright block:

```svelte
<div>
    <pre class="text-xs text-gray-400 dark:text-gray-500">Copyright (c) {new Date().getFullYear()} ArtiChat. All rights reserved.</pre>
</div>
```

For update status, remove the release link and render text only:

```svelte
{updateAvailable === null
    ? $i18n.t('Checking for updates...')
    : updateAvailable
        ? `(v${version.latest} ${$i18n.t('available!')})`
        : $i18n.t('(latest)')}
```

- [ ] **Step 3: Replace admin General help/license marketing**

In `src/lib/components/admin/Settings/General.svelte`:

Use neutral help text:

```svelte
<div class="text-xs text-gray-500">
    {$i18n.t('Manage ArtiChat system settings for this deployment.')}
</div>
```

Remove the upstream documentation button and all social badge links.

When license metadata exists, render it without an upstream URL:

```svelte
<div class="text-gray-500 mt-0.5">
    <span class="capitalize text-black dark:text-white">{$config?.license_metadata?.type} license</span>
    registered to
    <span class="capitalize text-black dark:text-white">{$config?.license_metadata?.organization_name}</span>
    for
    <span class="font-medium text-black dark:text-white">{$config?.license_metadata?.seats ?? 'Unlimited'} users.</span>
</div>
```

When no license metadata exists, render:

```svelte
<span class="text-gray-500">
    {$i18n.t('ArtiChat is ready for your local deployment.')}
</span>
```

Change visible WebUI labels in this file:

```svelte
<div class=" self-center text-xs font-medium">{$i18n.t('Application URL')}</div>
```

```svelte
{$i18n.t('Enter the public URL of ArtiChat. This URL will be used to generate links in notifications.')}
```

- [ ] **Step 4: Remove upstream user menu links**

In `src/lib/components/layout/Sidebar/UserMenu.svelte`, remove the admin-only Documentation and Releases links. Keep the keyboard shortcuts button and all local menu actions.

- [ ] **Step 5: Make update toast local**

In `src/lib/components/layout/UpdateInfoToast.svelte`, remove the upstream release anchor and render:

```svelte
<span>
    {$i18n.t('Restart or rebuild ArtiChat to apply the latest available build.')}
</span>
```

- [ ] **Step 6: Remove translation prompt**

In `src/lib/components/chat/Settings/General.svelte`, remove the English-only "Help us translate" block that links to the upstream repository.

- [ ] **Step 7: Update frontend-only error page**

In `src/routes/error/+page.svelte`, change the unsupported-method text to:

```svelte
"Oops! You're using an unsupported method (frontend only). Please serve ArtiChat from the backend."
```

Remove the upstream install link from that error page.

- [ ] **Step 8: Run the guard**

Run: `npm run test:branding`

Expected: still `FAIL` only for community and remaining active helper text surfaces.

- [ ] **Step 9: Commit About/help/update changes**

```powershell
git add src/lib/components/chat/Settings/About.svelte src/lib/components/admin/Settings/General.svelte src/lib/components/layout/Sidebar/UserMenu.svelte src/lib/components/layout/UpdateInfoToast.svelte src/lib/components/chat/Settings/General.svelte src/routes/error/+page.svelte
git commit -m "feat: replace upstream about and help surfaces"
```

### Task 5: Neutralize Upstream Community and Helper Text

**Files:**
- Modify: `src/lib/components/workspace/Models.svelte`
- Modify: `src/lib/components/workspace/Prompts.svelte`
- Modify: `src/lib/components/workspace/Tools.svelte`
- Modify: `src/lib/components/admin/Functions.svelte`
- Modify: `src/lib/components/admin/Evaluations/Feedbacks.svelte`
- Modify: `src/lib/components/chat/ShareChatModal.svelte`
- Modify: `src/lib/components/chat/Settings/SyncStatsModal.svelte`
- Modify: `src/lib/components/workspace/common/ManifestModal.svelte`
- Modify: `src/lib/components/chat/ToolServersModal.svelte`
- Modify: `src/lib/components/admin/Settings/Audio.svelte`
- Modify: `src/lib/components/admin/Settings/Events.svelte`
- Modify: `src/lib/components/admin/Settings/ExternalKnowledge.svelte`
- Modify: `src/lib/components/chat/Settings/Connections.svelte`
- Modify: `src/lib/components/chat/Settings/Integrations.svelte`

- [ ] **Step 1: Run the branding guard**

Run: `npm run test:branding`

Expected: `FAIL` with upstream community, marketplace, stats sync, and helper-text hits.

- [ ] **Step 2: Remove upstream marketplace navigation**

In `Models.svelte`, `Prompts.svelte`, `Tools.svelte`, `admin/Functions.svelte`, and `admin/Evaluations/Feedbacks.svelte`:

Replace upstream redirect functions that open `https://openwebui.com` with:

```ts
toast.info($i18n.t('External community sharing is unavailable in this ArtiChat build.'));
```

Remove the `window.open(...)` call from those handlers.

Change visible attribution text:

```svelte
{$i18n.t('Made by Community')}
```

Remove anchors whose `href` starts with `https://openwebui.com/`.

- [ ] **Step 3: Disable upstream share and stats sync copy**

In `src/lib/components/chat/ShareChatModal.svelte`, replace share-to-community success text with:

```ts
toast.info($i18n.t('External sharing is unavailable in this ArtiChat build.'));
```

Remove the `https://openwebui.com` URL open call.

In `src/lib/components/chat/Settings/SyncStatsModal.svelte`, change exported filename prefix:

```ts
const filename = `artichat-stats-${version}-${Date.now()}.json`;
```

Change visible sync modal title and copy to:

```svelte
{$i18n.t('Do you want to export your ArtiChat usage stats?')}
```

```svelte
{$i18n.t('Exported usage stats never include message content.')}
```

```svelte
<li>{$i18n.t('ArtiChat version')}</li>
```

- [ ] **Step 4: Neutralize funding and helper text**

In `src/lib/components/workspace/common/ManifestModal.svelte`, change the funding message to:

```svelte
{$i18n.t('Your entire contribution will go directly to the plugin developer. The chosen funding platform might have its own fees.')}
```

In `src/lib/components/chat/ToolServersModal.svelte`, change:

```svelte
{$i18n.t('ArtiChat can use tools provided by any OpenAPI server.')}
```

Remove the upstream `openapi-servers` link.

In `src/lib/components/admin/Settings/Audio.svelte`, change helper strings to:

```svelte
{$i18n.t('ArtiChat uses faster-whisper internally.')}
```

```svelte
{$i18n.t('ArtiChat uses SpeechT5 and CMU Arctic speaker embeddings.')}
```

In `src/lib/components/admin/Settings/Events.svelte`, change:

```svelte
{$i18n.t('Event names may change as ArtiChat evolves. Use broad patterns like user.* for integrations that should continue across new related events.')}
```

In `src/lib/components/admin/Settings/ExternalKnowledge.svelte`, change:

```svelte
{$i18n.t('External vectors must be generated with the same embedding model configured in ArtiChat.')}
```

In `src/lib/components/chat/Settings/Connections.svelte` and `src/lib/components/chat/Settings/Integrations.svelte`, change:

```svelte
{$i18n.t('CORS must be properly configured by the provider to allow requests from ArtiChat.')}
```

Remove upstream `openapi-servers` and `open-terminal` links from these settings screens.

- [ ] **Step 5: Run the branding guard**

Run: `npm run test:branding`

Expected: `PASS` for the curated user-visible source surface.

- [ ] **Step 6: Commit community/helper cleanup**

```powershell
git add src/lib/components/workspace/Models.svelte src/lib/components/workspace/Prompts.svelte src/lib/components/workspace/Tools.svelte src/lib/components/admin/Functions.svelte src/lib/components/admin/Evaluations/Feedbacks.svelte src/lib/components/chat/ShareChatModal.svelte src/lib/components/chat/Settings/SyncStatsModal.svelte src/lib/components/workspace/common/ManifestModal.svelte src/lib/components/chat/ToolServersModal.svelte src/lib/components/admin/Settings/Audio.svelte src/lib/components/admin/Settings/Events.svelte src/lib/components/admin/Settings/ExternalKnowledge.svelte src/lib/components/chat/Settings/Connections.svelte src/lib/components/chat/Settings/Integrations.svelte
git commit -m "feat: remove upstream community branding surfaces"
```

### Task 6: Generate ArtiChat Static Assets

**Files:**
- Create: `scripts/generate-artichat-assets.ps1`
- Modify generated assets under `static/`, `static/static/`, and `backend/open_webui/static/`.

- [ ] **Step 1: Create repeatable asset generator**

Create `scripts/generate-artichat-assets.ps1`:

```powershell
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')
$DarkMark = Join-Path $Root 'artivis-ass\logo\artimage-mark-dark.png'
$LightMark = Join-Path $Root 'artivis-ass\logo\artimage-mark-light.png'

function Save-Png {
    param(
        [string]$Source,
        [string]$Destination,
        [int]$Width,
        [int]$Height
    )

    $src = [System.Drawing.Image]::FromFile($Source)
    try {
        $bmp = New-Object System.Drawing.Bitmap $Width, $Height
        $graphics = [System.Drawing.Graphics]::FromImage($bmp)
        try {
            $graphics.Clear([System.Drawing.Color]::Transparent)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $graphics.DrawImage($src, 0, 0, $Width, $Height)
            $dir = Split-Path -Parent $Destination
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
            $bmp.Save($Destination, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $graphics.Dispose()
            $bmp.Dispose()
        }
    } finally {
        $src.Dispose()
    }
}

function Save-Ico {
    param(
        [string]$Source,
        [string]$Destination
    )

    $src = [System.Drawing.Image]::FromFile($Source)
    try {
        $bmp = New-Object System.Drawing.Bitmap 32, 32
        $graphics = [System.Drawing.Graphics]::FromImage($bmp)
        try {
            $graphics.Clear([System.Drawing.Color]::Transparent)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.DrawImage($src, 0, 0, 32, 32)
            $icon = [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
            $stream = [System.IO.File]::Open($Destination, [System.IO.FileMode]::Create)
            try {
                $icon.Save($stream)
            } finally {
                $stream.Dispose()
                $icon.Dispose()
            }
        } finally {
            $graphics.Dispose()
            $bmp.Dispose()
        }
    } finally {
        $src.Dispose()
    }
}

function Save-SvgFromPng {
    param(
        [string]$Source,
        [string]$Destination
    )

    $bytes = [System.IO.File]::ReadAllBytes($Source)
    $base64 = [Convert]::ToBase64String($bytes)
    $svg = @"
<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ArtiChat logo" width="512" height="512" viewBox="0 0 512 512">
  <title>ArtiChat</title>
  <image href="data:image/png;base64,$base64" width="512" height="512" preserveAspectRatio="xMidYMid meet"/>
</svg>
"@
    Set-Content -LiteralPath $Destination -Value $svg -Encoding UTF8
}

$targets = @(
    @{ Source = $DarkMark;  Path = 'static\favicon.png'; Width = 512; Height = 512 },
    @{ Source = $DarkMark;  Path = 'static\static\favicon.png'; Width = 512; Height = 512 },
    @{ Source = $LightMark; Path = 'static\static\favicon-dark.png'; Width = 500; Height = 500 },
    @{ Source = $DarkMark;  Path = 'static\static\favicon-96x96.png'; Width = 96; Height = 96 },
    @{ Source = $DarkMark;  Path = 'static\static\apple-touch-icon.png'; Width = 180; Height = 180 },
    @{ Source = $DarkMark;  Path = 'static\static\logo.png'; Width = 500; Height = 500 },
    @{ Source = $DarkMark;  Path = 'static\static\splash.png'; Width = 500; Height = 500 },
    @{ Source = $LightMark; Path = 'static\static\splash-dark.png'; Width = 500; Height = 500 },
    @{ Source = $DarkMark;  Path = 'static\static\web-app-manifest-192x192.png'; Width = 192; Height = 192 },
    @{ Source = $DarkMark;  Path = 'static\static\web-app-manifest-512x512.png'; Width = 512; Height = 512 },
    @{ Source = $DarkMark;  Path = 'backend\open_webui\static\favicon.png'; Width = 512; Height = 512 },
    @{ Source = $LightMark; Path = 'backend\open_webui\static\favicon-dark.png'; Width = 500; Height = 500 },
    @{ Source = $DarkMark;  Path = 'backend\open_webui\static\splash.png'; Width = 500; Height = 500 },
    @{ Source = $LightMark; Path = 'backend\open_webui\static\splash-dark.png'; Width = 500; Height = 500 },
    @{ Source = $DarkMark;  Path = 'backend\open_webui\static\web-app-manifest-192x192.png'; Width = 192; Height = 192 },
    @{ Source = $DarkMark;  Path = 'backend\open_webui\static\web-app-manifest-512x512.png'; Width = 512; Height = 512 }
)

foreach ($target in $targets) {
    Save-Png -Source $target.Source -Destination (Join-Path $Root $target.Path) -Width $target.Width -Height $target.Height
}

Save-Ico -Source $DarkMark -Destination (Join-Path $Root 'static\static\favicon.ico')
Save-SvgFromPng -Source $DarkMark -Destination (Join-Path $Root 'static\static\favicon.svg')

Write-Host 'ArtiChat assets generated.'
```

- [ ] **Step 2: Run the asset generator**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/generate-artichat-assets.ps1
```

Expected: `ArtiChat assets generated.`

- [ ] **Step 3: Verify generated image dimensions**

Run:

```powershell
Add-Type -AssemblyName System.Drawing
foreach ($p in @('static\static\favicon.png','static\static\favicon-dark.png','static\static\splash.png','static\static\splash-dark.png','static\static\apple-touch-icon.png','static\static\web-app-manifest-192x192.png','static\static\web-app-manifest-512x512.png')) {
  $img = [System.Drawing.Image]::FromFile((Resolve-Path -LiteralPath $p).Path)
  "$p $($img.Width)x$($img.Height)"
  $img.Dispose()
}
```

Expected:

```text
static\static\favicon.png 512x512
static\static\favicon-dark.png 500x500
static\static\splash.png 500x500
static\static\splash-dark.png 500x500
static\static\apple-touch-icon.png 180x180
static\static\web-app-manifest-192x192.png 192x192
static\static\web-app-manifest-512x512.png 512x512
```

- [ ] **Step 4: Run branding guard**

Run: `npm run test:branding`

Expected: `PASS`.

- [ ] **Step 5: Commit generated assets**

```powershell
git add scripts/generate-artichat-assets.ps1 static/favicon.png static/static/favicon.png static/static/favicon-dark.png static/static/favicon-96x96.png static/static/favicon.ico static/static/favicon.svg static/static/apple-touch-icon.png static/static/logo.png static/static/splash.png static/static/splash-dark.png static/static/web-app-manifest-192x192.png static/static/web-app-manifest-512x512.png backend/open_webui/static/favicon.png backend/open_webui/static/favicon-dark.png backend/open_webui/static/splash.png backend/open_webui/static/splash-dark.png backend/open_webui/static/web-app-manifest-192x192.png backend/open_webui/static/web-app-manifest-512x512.png
git commit -m "feat: replace static assets with ArtiChat branding"
```

### Task 7: Build, Run, and Verify Branded Docker App

**Files:**
- No planned source edits.
- Docker image and running container are verification artifacts.

- [ ] **Step 1: Run source-level checks**

Run:

```powershell
npm run test:branding
npm run check
```

Expected:

```text
Branding scan passed
svelte-check found 0 errors and 0 warnings
```

- [ ] **Step 2: Build frontend**

Run:

```powershell
npm run build
```

Expected: Vite/SvelteKit build exits `0`. Existing upstream Svelte warnings are acceptable only if they were already present and are not introduced by this work.

- [ ] **Step 3: Scan built frontend output**

Run:

```powershell
Select-String -Path 'build\**\*' -Pattern 'Open WebUI','OpenWebUI','open-webui','openwebui.com','github.com/open-webui' -SimpleMatch -ErrorAction SilentlyContinue
```

Expected: no output.

- [ ] **Step 4: Build Docker image**

Run:

```powershell
docker compose build --build-arg USE_SLIM=true open-webui
```

Expected: build exits `0`.

If build fails, run conservative cleanup before another attempt:

```powershell
docker container prune -f
docker image prune -f
docker system df
```

Do not run full BuildKit pruning unless disk pressure requires it.

- [ ] **Step 5: Restart only the branded app container**

Run:

```powershell
docker compose up -d --no-deps open-webui
```

Expected: `open-webui` container starts without starting Ollama.

- [ ] **Step 6: Verify HTTP health and homepage**

Run:

```powershell
docker compose ps
Invoke-WebRequest -Uri 'http://localhost:3000/health' -UseBasicParsing -TimeoutSec 20
Invoke-WebRequest -Uri 'http://localhost:3000/' -UseBasicParsing -TimeoutSec 20
```

Expected:

```text
open-webui ... healthy
/health status 200 with {"status":true}
/ status 200
```

- [ ] **Step 7: Verify runtime pages do not expose upstream branding**

Run:

```powershell
$root = Invoke-WebRequest -Uri 'http://localhost:3000/' -UseBasicParsing -TimeoutSec 20
$manifest = Invoke-WebRequest -Uri 'http://localhost:3000/manifest.json' -UseBasicParsing -TimeoutSec 20
$siteManifest = Invoke-WebRequest -Uri 'http://localhost:3000/static/site.webmanifest' -UseBasicParsing -TimeoutSec 20
($root.Content + $manifest.Content + $siteManifest.Content) | Select-String -Pattern 'Open WebUI|OpenWebUI|open-webui|openwebui.com|github.com/open-webui'
```

Expected: no output.

- [ ] **Step 8: Commit verification note**

Update `docs/progress/2026-07-05-docker-environment.md` with the successful ArtiChat branding build and runtime verification result.

Commit only the progress note:

```powershell
git add docs/progress/2026-07-05-docker-environment.md
git commit -m "docs: record ArtiChat branding verification"
```

## Self-Review Checklist

- Spec coverage:
  - Product name: Task 2 and Task 3.
  - Logo/static assets: Task 6.
  - About and admin About/general settings: Task 4.
  - User-visible upstream community links: Task 5.
  - Build and runtime verification: Task 7.
  - Conservative cleanup after failed Docker builds: Task 7.
- Marker scan: every step names concrete files, commands, and expected results.
- Type consistency: frontend name constants remain in `src/lib/constants.ts`; backend name remains `WEBUI_NAME`; test script uses Node built-ins only; asset script uses Windows PowerShell and .NET drawing APIs already available on the host.
