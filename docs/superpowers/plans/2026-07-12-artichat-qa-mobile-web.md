# ArtiChat QA Mobile Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and verify a self-contained, mobile-first ArtiChat technical-documentation webpage from the existing desktop QA Markdown.

**Architecture:** A temporary Node generator uses the repository's installed `marked@9.1.6` parser to render trusted Markdown into semantic HTML with stable heading IDs and an embedded table of contents. The generator embeds CSS, JavaScript, and the existing ArtiChat PNG mark directly into one desktop HTML file. Temporary Node and Python verification scripts enforce static/security contracts and exercise the result in installed Microsoft Edge through Python Playwright, then are deleted.

**Tech Stack:** Node.js 22, marked 9.1.6, HTML5, CSS, vanilla JavaScript, Python Playwright, Microsoft Edge.

---

### Task 1: Add A Failing Standalone-HTML Contract

**Files:**

- Create temporarily: `C:\Users\admin\Desktop\artichat-qa-web-check.mjs`
- Expected output: `C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.html`

- [ ] **Step 1: Create the static contract checker**

The checker reads the expected HTML and asserts the full standalone-page contract:

```js
import assert from 'node:assert/strict';
import fs from 'node:fs';

const output = 'C:/Users/admin/Desktop/ArtiChat-GitHub更新与项目文件QA-2026-07-12.html';
assert.ok(fs.existsSync(output), 'desktop HTML output is missing');

const html = fs.readFileSync(output, 'utf8');
for (const marker of [
	'<html lang="zh-CN"',
	'id="app-header"',
	'id="toc"',
	'id="mobile-nav"',
	'id="doc-search"',
	'id="theme-toggle"',
	'id="reading-progress"',
	'id="back-to-top"',
	'data:image/png;base64,',
	'问题 1：上传 GitHub 为什么能更新服务？',
	'问题 2：ArtiChat 根目录所有项目分别做什么？',
	'问题 3：0.1.3 应该如何上传并让服务器更新？',
	'问题 4：ArtiChat 下一步应该更新或优化什么？'
]) {
	assert.ok(html.includes(marker), `missing required marker: ${marker}`);
}

assert.doesNotMatch(html, /<(?:script|img)[^>]+src=["']https?:/i);
assert.doesNotMatch(html, /<link[^>]+href=["']https?:/i);
assert.doesNotMatch(html, /18\.234\.239\.56|github_pat_|gh[pousr]_[A-Za-z0-9_]{20,}/i);
assert.doesNotMatch(html, /-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----/);
assert.doesNotMatch(html, /<meta[^>]+http-equiv=["']refresh/i);

console.log('Standalone QA webpage contract passed.');
```

- [ ] **Step 2: Run the contract before generation**

Run:

```powershell
node 'C:\Users\admin\Desktop\artichat-qa-web-check.mjs'
```

Expected: failure with `desktop HTML output is missing` because the approved output has not been generated.

### Task 2: Generate The Self-Contained Mobile Page

**Files:**

- Source: `C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.md`
- Source asset: `artivis-ass/logo/artimage-mark-dark.png`
- Create temporarily: `C:\Users\admin\Desktop\generate-artichat-qa-web.mjs`
- Create: `C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.html`

- [ ] **Step 1: Implement deterministic Markdown rendering**

The generator will:

```js
import fs from 'node:fs';
import { marked } from 'marked';

const usedIds = new Map();
const headings = [];
const slug = (value) => {
	const base =
		value
			.replace(/<[^>]+>/g, '')
			.trim()
			.toLowerCase()
			.replace(/[^\p{L}\p{N}]+/gu, '-')
			.replace(/^-|-$/g, '') || 'section';
	const count = usedIds.get(base) ?? 0;
	usedIds.set(base, count + 1);
	return count === 0 ? base : `${base}-${count + 1}`;
};

const renderer = new marked.Renderer();
renderer.heading = (text, level, raw) => {
	const id = slug(raw);
	headings.push({ id, level, text: raw.replace(/<[^>]+>/g, '') });
	return `<h${level} id="${id}" data-heading><a class="heading-anchor" href="#${id}" aria-label="链接到本节">#</a>${text}</h${level}>`;
};
renderer.html = (html) =>
	html.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

const body = marked.parse(markdown, { gfm: true, mangle: false, headerIds: false, renderer });
```

The final implementation also normalizes external links with safe attributes and adds a copy control to every rendered code block.

- [ ] **Step 2: Build the responsive document shell**

Embed in one HTML file:

- Compact branded header and inline PNG Data URI.
- Desktop sidebar navigation and mobile slide-over navigation.
- Search field, match count, theme control, reading-progress bar, and back-to-top button.
- Semantic article content produced by `marked`.
- Responsive CSS with stable breakpoints, `overflow-x: auto` on table/code wrappers, safe-area insets, focus styles, print rules, and reduced-motion rules.
- Vanilla JavaScript for navigation, active section, search highlighting, theme persistence, code copy, progress, and back-to-top behavior.

- [ ] **Step 3: Generate the desktop HTML**

Run:

```powershell
node 'C:\Users\admin\Desktop\generate-artichat-qa-web.mjs'
```

Expected: one HTML file is written and the generator reports its byte size, heading count, and embedded-logo byte size without creating an asset folder.

- [ ] **Step 4: Run the static contract**

Run:

```powershell
node 'C:\Users\admin\Desktop\artichat-qa-web-check.mjs'
```

Expected: `Standalone QA webpage contract passed.`

### Task 3: Verify Browser Rendering And Interaction

**Files:**

- Create temporarily: `C:\Users\admin\Desktop\verify-artichat-qa-web.py`
- Create temporarily: `%TEMP%\artichat-qa-web-verification\*.png`
- Verify: `C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.html`

- [ ] **Step 1: Implement the Playwright verifier**

The verifier launches installed Edge headlessly and checks each viewport:

```python
VIEWPORTS = {
    "desktop-1440": {"width": 1440, "height": 900},
    "desktop-1024": {"width": 1024, "height": 768},
    "mobile-390": {"width": 390, "height": 844},
    "mobile-360": {"width": 360, "height": 800},
}

page.goto(output.as_uri(), wait_until="load")
assert page.locator("article h2").count() >= 4
assert page.locator("#toc a").count() > 10
assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
assert page.locator("#brand-mark").evaluate("el => el.naturalWidth > 0")
```

It captures full-page screenshots, verifies nonblank screenshot dimensions, opens/closes the mobile navigation, searches for `GitHub Actions`, toggles theme, clicks an anchor, scrolls to change reading progress, exercises a copy button with a mocked clipboard, and checks browser console/page errors.

- [ ] **Step 2: Run browser verification**

Run:

```powershell
python 'C:\Users\admin\Desktop\verify-artichat-qa-web.py'
```

Expected: all four viewports pass with no page-level horizontal overflow, missing logo, console errors, or failed interactions.

- [ ] **Step 3: Inspect desktop and mobile screenshots**

Open at least the `desktop-1440` and `mobile-390` screenshots with the local image viewer. Confirm the page is nonblank, typography is readable, the logo and header are correctly framed, controls do not overlap, tables are contained, and the mobile layout shows a usable document surface.

### Task 4: Clean Temporary Files And Deliver

**Files:**

- Keep: `C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.html`
- Delete: `C:\Users\admin\Desktop\artichat-qa-web-check.mjs`
- Delete: `C:\Users\admin\Desktop\generate-artichat-qa-web.mjs`
- Delete: `C:\Users\admin\Desktop\verify-artichat-qa-web.py`
- Delete: `%TEMP%\artichat-qa-web-verification\`

- [ ] **Step 1: Re-run final static and browser checks**

Run the static contract and Playwright verifier once more against the final HTML immediately before cleanup. Expected: both pass.

- [ ] **Step 2: Remove only the verified temporary helper files**

Resolve each exact path, confirm it matches the expected desktop or temp verification path, remove the three helpers and screenshot directory, and leave the Markdown and HTML files untouched.

- [ ] **Step 3: Verify final delivery state**

Run:

```powershell
Get-Item 'C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.html'
Get-FileHash -Algorithm SHA256 'C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.html'
git status --short --branch
```

Expected: the standalone HTML exists, has a stable SHA-256 hash, no helper file remains, and the ArtiChat worktree is clean because the webpage is a desktop-only artifact.
