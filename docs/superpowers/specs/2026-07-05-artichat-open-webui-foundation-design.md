# ArtiChat Open WebUI Foundation Design

## Goal

Create the initial ArtiChat project foundation from the open-source Open WebUI codebase while preserving the existing Artivis brand assets already stored in this workspace.

## Current Context

- Project root: `C:\Users\admin\Desktop\Pro\ArtiChat`
- Existing asset directory: `artivis-ass\logo`
- Existing brand assets:
  - `artimage-mark-dark.png`
  - `artimage-mark-light.png`
  - `artivis-black.svg`
  - `artivis-white.svg`
- Upstream repository: `https://github.com/open-webui/open-webui.git`
- Upstream branch: `main`
- Observed upstream HEAD before implementation: `ecd48e2f718220a6400ecf49eafd4867a38feb10`

## Scope

This first step only creates a local ArtiChat foundation from Open WebUI.

Included:

- Preserve `artivis-ass` and all logo files.
- Bring Open WebUI source files into the ArtiChat project root.
- Avoid Docker-based setup.
- Avoid Ollama-specific setup as the default path.
- Keep enough upstream metadata to identify where the foundation came from.
- Verify that the resulting repository can be inspected locally.

Excluded for this step:

- Rebranding UI text, icons, favicons, or theme.
- Removing all Ollama-related code paths from the product.
- Adding model provider integrations.
- Designing production server deployment.
- Running Docker or creating Docker deployment files.

## Recommended Approach

Use a temporary clone of Open WebUI, then merge the working tree into the existing ArtiChat root. This keeps the current logo asset directory safe and avoids cloning directly into a non-empty folder.

The ArtiChat repository should keep an `upstream` remote pointing at Open WebUI and should record the source commit used for the initial foundation. This gives the project a clear baseline for future audits or upstream comparisons, without requiring Docker or Ollama during local setup.

## Architecture

ArtiChat starts as a fork-derived application with Open WebUI as the base. The existing `artivis-ass` directory remains a project-local asset source and is not moved during the initial import.

After the foundation import:

- Open WebUI source files live in the ArtiChat root.
- Artivis logo assets remain under `artivis-ass\logo`.
- Future branding work can copy or reference those assets into the frontend's expected static asset locations.
- Future provider work can replace the default local-model assumptions with the desired model-provider path.

## Data Flow

No runtime data flow changes are introduced in this step. The only data movement is repository setup:

1. Clone Open WebUI into a temporary directory.
2. Copy source files into the ArtiChat root while preserving `artivis-ass`.
3. Initialize or update git metadata for ArtiChat.
4. Record the upstream remote and source commit.

## Error Handling

- If the target root contains a file or folder that conflicts with an upstream path, stop and inspect the conflict before overwriting anything.
- If the upstream clone fails, leave the current ArtiChat directory unchanged except for this design document.
- If git metadata cannot be initialized cleanly, keep the copied files uncommitted and report the exact blocker before continuing.

## Verification

After implementation, verify:

- `artivis-ass\logo` still contains all four existing logo files.
- Open WebUI source files are present at the ArtiChat root.
- The git repository has an `upstream` remote for Open WebUI.
- The recorded upstream commit matches the imported source.
- No Docker or Ollama command is required for this initial project import.

## Follow-Up Work

Subsequent work should be split into separate design and implementation cycles:

- ArtiChat branding and logo replacement.
- Non-Ollama model provider configuration.
- Local non-Docker development startup.
- Authentication, product settings, and deployment strategy.
