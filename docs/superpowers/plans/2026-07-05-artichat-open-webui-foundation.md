# ArtiChat Open WebUI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import Open WebUI into the ArtiChat project root while preserving the existing Artivis logo assets and keeping a project-local progress record.

**Architecture:** ArtiChat starts as a fork-derived working tree based on Open WebUI. The import uses a temporary clone, copies upstream source files into the existing project root, preserves `artivis-ass`, records the upstream source commit, and avoids Docker or Ollama startup paths in this phase.

**Tech Stack:** Git, PowerShell, Open WebUI source tree, Markdown project documentation.

---

## File Structure

- Create: `docs/progress/2026-07-05-foundation-import.md`
  - Records factual progress entries for this foundation import.
- Modify: `docs/progress/2026-07-05-foundation-import.md`
  - Adds source commit, verification results, and completion notes as tasks finish.
- Modify: `.git/config`
  - Adds the `upstream` remote for `https://github.com/open-webui/open-webui.git`.
- Modify: project root files under `C:\Users\admin\Desktop\Pro\ArtiChat`
  - Receives Open WebUI source files copied from the temporary clone.
- Preserve: `artivis-ass/logo/artimage-mark-dark.png`
- Preserve: `artivis-ass/logo/artimage-mark-light.png`
- Preserve: `artivis-ass/logo/artivis-black.svg`
- Preserve: `artivis-ass/logo/artivis-white.svg`

## Task 1: Confirm Baseline And Progress Log

**Files:**
- Modify: `docs/progress/2026-07-05-foundation-import.md`

- [ ] **Step 1: Check the repository baseline**

Run:

```powershell
git status --short
git log --oneline -1
Get-ChildItem -LiteralPath 'C:\Users\admin\Desktop\Pro\ArtiChat\artivis-ass\logo' -File | Select-Object Name,Length
```

Expected:

- `git status --short` is empty before implementation starts.
- `git log --oneline -1` shows `docs: add foundation import plan and progress log`.
- The logo list contains exactly these files:
  - `artimage-mark-dark.png`
  - `artimage-mark-light.png`
  - `artivis-black.svg`
  - `artivis-white.svg`

- [ ] **Step 2: Add the implementation start entry to the progress log**

Run:

```powershell
$ProgressPath = 'C:\Users\admin\Desktop\Pro\ArtiChat\docs\progress\2026-07-05-foundation-import.md'
$ProgressLines = @(
  ''
  '## 2026-07-05 - Foundation Import'
  ''
  '- Status: In progress'
  '- Approved design: `docs/superpowers/specs/2026-07-05-artichat-open-webui-foundation-design.md`'
  '- Plan: `docs/superpowers/plans/2026-07-05-artichat-open-webui-foundation.md`'
  '- Baseline commit: `5dbd67c docs: add ArtiChat foundation design`'
  '- Notes:'
  '  - Preserve `artivis-ass/logo`.'
  '  - Import Open WebUI source into the ArtiChat root.'
  '  - Do not use Docker or Ollama startup commands in this phase.'
)
Add-Content -LiteralPath $ProgressPath -Value $ProgressLines
```

Expected:

- `docs/progress/2026-07-05-foundation-import.md` contains a `Status: In progress` entry.

- [ ] **Step 3: Commit the progress start entry**

Run:

```powershell
git add -- docs/progress/2026-07-05-foundation-import.md
git commit -m "docs: mark foundation import in progress"
```

Expected:

- Commit succeeds.
- `git status --short` is empty after the commit.

## Task 2: Clone Upstream Into A Temporary Directory

**Files:**
- Modify: `docs/progress/2026-07-05-foundation-import.md`

- [ ] **Step 1: Create a clean temporary clone**

Run:

```powershell
$TempRoot = Join-Path $env:TEMP 'artichat-open-webui-import'
if (Test-Path -LiteralPath $TempRoot) {
  Remove-Item -LiteralPath $TempRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
git clone --depth 1 --branch main https://github.com/open-webui/open-webui.git (Join-Path $TempRoot 'open-webui')
```

Expected:

- Clone exits with code 0.
- Temporary clone exists at `%TEMP%\artichat-open-webui-import\open-webui`.

- [ ] **Step 2: Record the upstream source commit**

Run:

```powershell
$Source = Join-Path $env:TEMP 'artichat-open-webui-import\open-webui'
$SourceCommit = (git -C $Source rev-parse HEAD).Trim()
$SourceCommit
```

Expected:

- Output is a 40-character git commit SHA.

- [ ] **Step 3: Append the upstream commit to the progress log**

Run:

```powershell
$ProgressPath = 'C:\Users\admin\Desktop\Pro\ArtiChat\docs\progress\2026-07-05-foundation-import.md'
$ProgressLines = @(
  ''
  '### Upstream Source'
  ''
  '- Repository: `https://github.com/open-webui/open-webui.git`'
  '- Branch: `main`'
  ('- Imported commit: `{0}`' -f $SourceCommit)
)
Add-Content -LiteralPath $ProgressPath -Value $ProgressLines
```

Expected:

- The progress log contains the repository URL, branch name, and a 40-character imported commit SHA.

## Task 3: Detect Import Conflicts Before Copying

**Files:**
- Read: `%TEMP%\artichat-open-webui-import\open-webui`
- Read: `C:\Users\admin\Desktop\Pro\ArtiChat`

- [ ] **Step 1: Check for existing file collisions**

Run:

```powershell
$Target = 'C:\Users\admin\Desktop\Pro\ArtiChat'
$Source = Join-Path $env:TEMP 'artichat-open-webui-import\open-webui'
$FileConflicts = Get-ChildItem -LiteralPath $Source -Force -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\.git(\\|$)' } |
  ForEach-Object {
    $RelativePath = [System.IO.Path]::GetRelativePath($Source, $_.FullName)
    $DestinationPath = Join-Path $Target $RelativePath
    if (Test-Path -LiteralPath $DestinationPath) {
      $RelativePath
    }
  }
$FileConflicts
if ($FileConflicts.Count -gt 0) {
  throw "Import would overwrite existing files. Resolve conflicts before copying."
}
```

Expected:

- No file paths are printed.
- Command exits successfully.

- [ ] **Step 2: Check for directory-to-file collisions**

Run:

```powershell
$Target = 'C:\Users\admin\Desktop\Pro\ArtiChat'
$Source = Join-Path $env:TEMP 'artichat-open-webui-import\open-webui'
$DirectoryConflicts = Get-ChildItem -LiteralPath $Source -Force -Recurse -Directory |
  Where-Object { $_.FullName -notmatch '\\.git(\\|$)' } |
  ForEach-Object {
    $RelativePath = [System.IO.Path]::GetRelativePath($Source, $_.FullName)
    $DestinationPath = Join-Path $Target $RelativePath
    if (Test-Path -LiteralPath $DestinationPath -PathType Leaf) {
      $RelativePath
    }
  }
$DirectoryConflicts
if ($DirectoryConflicts.Count -gt 0) {
  throw "Import would replace existing files with directories. Resolve conflicts before copying."
}
```

Expected:

- No directory paths are printed.
- Command exits successfully.

## Task 4: Copy Open WebUI Source Into ArtiChat

**Files:**
- Modify: project root files under `C:\Users\admin\Desktop\Pro\ArtiChat`
- Modify: `docs/progress/2026-07-05-foundation-import.md`

- [ ] **Step 1: Copy upstream files except `.git`**

Run:

```powershell
$Target = 'C:\Users\admin\Desktop\Pro\ArtiChat'
$Source = Join-Path $env:TEMP 'artichat-open-webui-import\open-webui'
Get-ChildItem -LiteralPath $Source -Force |
  Where-Object { $_.Name -ne '.git' } |
  ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse -Force
  }
```

Expected:

- Command exits successfully.
- Open WebUI root files appear in `C:\Users\admin\Desktop\Pro\ArtiChat`.
- `artivis-ass` remains present.

- [ ] **Step 2: Verify key imported files**

Run:

```powershell
Test-Path -LiteralPath 'C:\Users\admin\Desktop\Pro\ArtiChat\package.json'
Test-Path -LiteralPath 'C:\Users\admin\Desktop\Pro\ArtiChat\backend'
Test-Path -LiteralPath 'C:\Users\admin\Desktop\Pro\ArtiChat\src'
Test-Path -LiteralPath 'C:\Users\admin\Desktop\Pro\ArtiChat\pyproject.toml'
```

Expected:

- Each command prints `True`.

- [ ] **Step 3: Verify brand assets survived**

Run:

```powershell
Get-ChildItem -LiteralPath 'C:\Users\admin\Desktop\Pro\ArtiChat\artivis-ass\logo' -File | Select-Object Name,Length
```

Expected:

- The output contains exactly the four existing logo files.
- File sizes remain non-zero.

## Task 5: Record Upstream Remote And Import Metadata

**Files:**
- Modify: `.git/config`
- Modify: `docs/progress/2026-07-05-foundation-import.md`

- [ ] **Step 1: Add the upstream remote**

Run:

```powershell
$ExistingRemotes = git remote
if ($ExistingRemotes -notcontains 'upstream') {
  git remote add upstream https://github.com/open-webui/open-webui.git
}
git remote -v
```

Expected:

- Output includes:
  - `upstream https://github.com/open-webui/open-webui.git (fetch)`
  - `upstream https://github.com/open-webui/open-webui.git (push)`

- [ ] **Step 2: Append import verification metadata**

Run:

```powershell
$Source = Join-Path $env:TEMP 'artichat-open-webui-import\open-webui'
$SourceCommit = (git -C $Source rev-parse HEAD).Trim()
$ProgressPath = 'C:\Users\admin\Desktop\Pro\ArtiChat\docs\progress\2026-07-05-foundation-import.md'
$ProgressLines = @(
  ''
  '### Import Verification'
  ''
  '- Open WebUI source copied into project root: yes'
  '- Existing Artivis assets preserved: yes'
  '- Upstream remote configured: yes'
  ('- Imported commit: `{0}`' -f $SourceCommit)
  '- Docker commands run: no'
  '- Ollama commands run: no'
)
Add-Content -LiteralPath $ProgressPath -Value $ProgressLines
```

Expected:

- The progress log includes `Docker commands run: no`.
- The progress log includes `Ollama commands run: no`.

## Task 6: Commit Imported Foundation

**Files:**
- Modify: all imported Open WebUI source files
- Modify: `docs/progress/2026-07-05-foundation-import.md`

- [ ] **Step 1: Review changed files**

Run:

```powershell
git status --short
```

Expected:

- Output shows imported Open WebUI files as untracked or modified.
- Output includes `docs/progress/2026-07-05-foundation-import.md`.
- Output does not show deleted files under `artivis-ass/logo`.

- [ ] **Step 2: Commit the import**

Run:

```powershell
git add -- .
git commit -m "chore: import Open WebUI foundation"
```

Expected:

- Commit succeeds.
- Commit includes imported Open WebUI files and the updated progress log.

- [ ] **Step 3: Confirm clean working tree**

Run:

```powershell
git status --short
git log --oneline -3
```

Expected:

- `git status --short` is empty.
- `git log --oneline -3` shows:
  - `chore: import Open WebUI foundation`
  - `docs: add foundation import plan and progress log`
  - `docs: add ArtiChat foundation design`

## Task 7: Final Foundation Verification

**Files:**
- Read: project root files under `C:\Users\admin\Desktop\Pro\ArtiChat`
- Read: `docs/progress/2026-07-05-foundation-import.md`

- [ ] **Step 1: Verify repository metadata**

Run:

```powershell
git remote -v
git status --short
```

Expected:

- `upstream` remote points to `https://github.com/open-webui/open-webui.git`.
- `git status --short` is empty.

- [ ] **Step 2: Verify no Docker or Ollama startup command was used**

Run:

```powershell
Select-String -LiteralPath 'C:\Users\admin\Desktop\Pro\ArtiChat\docs\progress\2026-07-05-foundation-import.md' -Pattern 'Docker commands run: no','Ollama commands run: no'
```

Expected:

- Both progress-log lines are found.

- [ ] **Step 3: Report completion**

Report these facts:

```text
Open WebUI has been imported into the ArtiChat root.
The Artivis logo assets remain under artivis-ass/logo.
The upstream remote is configured.
The imported upstream commit is recorded in docs/progress/2026-07-05-foundation-import.md.
No Docker or Ollama startup command was used.
```
