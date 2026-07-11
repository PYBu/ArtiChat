# ArtiChat QA Mobile Web Design

## Goal

Convert the existing desktop Markdown QA guide into a polished, mobile-first, self-contained HTML document that can be uploaded to any static web server and opened directly from a phone browser.

## Approved Decisions

- Delivery format: one standalone `.html` file.
- Output location: the Windows desktop only.
- Access model: public URL with no application-level authentication.
- Visual direction: ArtiChat technical-documentation style.
- Feature level: full reading experience.
- Visual companion mockups: declined; implementation will be verified with rendered browser screenshots instead.

## Source And Output

- Source Markdown: `C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.md`.
- Output HTML: `C:\Users\admin\Desktop\ArtiChat-GitHub更新与项目文件QA-2026-07-12.html`.
- The generated page will not be added to the ArtiChat Git repository.
- The HTML will include the rendered document, styles, scripts, and brand image in one file.

## Architecture

The Markdown will be rendered at generation time with the repository's installed Markdown parser. The resulting semantic HTML will be inserted into a fixed page shell. CSS, JavaScript, and an existing ArtiChat bitmap logo will be embedded directly, so the uploaded page has no CDN, package-manager, runtime Markdown parser, API, cookie, database, or server-side dependency.

The page will make no network requests after load. Uploading the single file to Nginx, 1Panel static hosting, object storage, or another ordinary static server is sufficient.

## Information Layout

### Header

- Compact ArtiChat identity using the existing product mark.
- Document title and current version context.
- Search, theme, and navigation controls.
- Thin reading-progress indicator fixed to the top edge.

### Navigation

- Desktop: stable left navigation column containing the four primary questions and their subsections.
- Mobile: icon-triggered slide-over navigation with a backdrop and explicit close control.
- Active section follows scroll position.
- Selecting an item closes the mobile navigation and scrolls to the correct heading.

### Main Document

- Constrained readable line length on desktop.
- Full-width use on narrow phones with safe horizontal padding.
- Semantic headings, paragraphs, lists, tables, block quotes, code blocks, and links.
- Tables use bounded horizontal scrolling rather than shrinking text beyond readability.
- Code blocks have stable layout, language-neutral styling, and copy controls.

### Utilities

- Full-text search with match count and highlighted results.
- Search navigation that scrolls to matched sections.
- Light, dark, and system theme behavior with local persistence.
- Back-to-top control that appears after meaningful scrolling.
- Per-code-block copy button with a temporary success state.
- Print stylesheet that removes controls and produces a clean paper/PDF layout.

## Responsive Behavior

- Target phone width: 360 CSS pixels and above.
- No horizontal page overflow at 360, 390, 430, 768, 1024, or 1440 pixel viewports.
- Only tables and code blocks may scroll horizontally inside their own containers.
- Touch targets are at least 44 by 44 CSS pixels.
- Header controls never overlap the document title.
- Long paths, hashes, commands, and URLs wrap or scroll within their own containers.
- The page respects safe-area insets on mobile browsers.

## Visual System

- Neutral white/charcoal surfaces with restrained ArtiChat green accents and limited blue information accents.
- No decorative gradients, floating cards, or marketing-style hero composition.
- Cards are used only for the opening status summary and search result state.
- Body typography prioritizes Chinese long-form reading with system font fallbacks.
- Heading sizes stay proportional to document context and do not scale with viewport width.
- Borders, spacing, and color contrast remain legible in both themes.

## Accessibility

- Semantic `header`, `nav`, `main`, `article`, and heading structure.
- Every icon control has an accessible label and visible tooltip/title.
- Keyboard-accessible search, navigation drawer, theme control, copy buttons, and back-to-top control.
- Escape closes the mobile navigation and clears focus traps.
- Visible focus rings.
- `prefers-reduced-motion` disables non-essential transitions and smooth scrolling.
- Theme colors meet practical text contrast requirements.

## Content And Security

- The page contains the same public-safe content as the verified Markdown source.
- Generated HTML is sanitized or produced from trusted local Markdown with raw HTML disabled.
- No production IP, GitHub token, SSH key, private-key header, AWS access key, database, backup content, or real `WEBUI_SECRET_KEY` is embedded.
- External links use safe link attributes where appropriate.
- No analytics, trackers, third-party fonts, external scripts, or external stylesheets are included.

## Error Handling

- If JavaScript is disabled, the full document remains readable; only search, drawer enhancements, theme persistence, copy buttons, and active-section tracking are reduced.
- If clipboard access is unavailable, copy controls fall back to selection-based copy where supported and expose a clear failure state.
- Search with no matches shows an explicit empty state without hiding the original document permanently.
- Broken heading targets are prevented by generating stable unique IDs from the rendered heading sequence.

## Verification

### Static checks

- HTML parses without structural errors.
- Exactly one output HTML file is required for display.
- No `http://` or `https://` resource dependency appears in `src`, `href` stylesheet, script, font, or image attributes; ordinary document links may remain.
- Sensitive-value scans pass.
- The rendered document includes all four primary QA sections.

### Browser checks

- Desktop: 1440x900 and 1024x768.
- Mobile: 390x844 and 360x800.
- Verify nonblank rendering, logo visibility, readable typography, no incoherent overlap, and no page-level horizontal overflow.
- Verify navigation drawer open/close, anchor navigation, search results, theme switching, copy controls, back-to-top behavior, and reading-progress movement.
- Verify print media layout at least through browser print emulation or generated PDF preview.

## Deployment Guidance

The final handoff will identify the HTML file and explain that it can be uploaded as-is to a static directory. Because the page is intentionally public, the operator must not add secrets or private production details to later revisions of the source Markdown without re-running the sensitive-value scan.
