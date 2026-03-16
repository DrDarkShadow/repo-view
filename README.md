# repoview

> Turn any codebase into LLM-ready context — in seconds.

`repoview` scans your project, intelligently processes every file, and generates a single `.txt` file you can paste directly into Claude, ChatGPT, Gemini, or any LLM. It respects your `.gitignore`, summarises large files to fit within token limits, and remembers your settings between runs so updates are near-instant.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Interactive Wizard](#interactive-wizard)
- [CLI Reference](#cli-reference)
- [Watch Mode](#watch-mode)
- [Smart Diff / Incremental Updates](#smart-diff--incremental-updates)
- [File Classification](#file-classification)
- [Token Budget & Trimming](#token-budget--trimming)
- [Cache System](#cache-system)
- [Output File Format](#output-file-format)
- [Publishing a New Version](#publishing-a-new-version)
- [Requirements](#requirements)

---

## Installation

```bash
pip install repoview
```

That's it. The `repoview` command is now available anywhere in your terminal.

---

## Quick Start

```bash
# Navigate to your project and run
cd my-project
repoview

# Or pass the path directly
repoview "C:\Users\Prateek\Desktop\my-project"
repoview ~/projects/my-project
```

The interactive wizard will guide you through everything. When it's done, a `.txt` file is ready to paste into any LLM.

---

## How It Works

```
repoview <path>
      │
      ▼
  Scan project          ← counts files, detects test files, finds .gitignore
      │
      ▼
  Check cache           ← was this project run before?
      │                    yes → show diff, offer incremental update
      │                    no  → continue to wizard
      ▼
  Ask questions         ← only the ones relevant to your project
      │                    skip docs? skip tests? respect .gitignore?
      │                    output name? output location?
      ▼
  Classify files        ← essential / code / config / general / metadata
      │
      ▼
  Token budget check    ← if over budget: summarise → omit (lowest priority first)
      │
      ▼
  Write output file     ← structured .txt with directory tree + all file contents
      │
      ▼
  Save cache            ← stored in ~/.repoview/cache/ for next run
      │
      ▼
  Post-completion menu  ← copy text / copy file / open folder / run again / exit
```

---

## Interactive Wizard

Running `repoview` or `repoview <path>` launches the interactive wizard. Every question is conditional — you only see questions that are relevant to your specific project.

### Scan Preview

Before any questions, repoview scans your project and shows:

```
  Scanning my-project…

  ╭─────────────────────────────────────────╮
  │  Files found      147                   │
  │  Total size       3.1 MB                │
  │  Est. tokens      ~218,000              │
  │  Top types        .ts 43  .tsx 28  ...  │
  │  .gitignore       found (24 rules)      │
  │  Test files       31 detected           │
  ╰─────────────────────────────────────────╯
```

This gives you the information you need to make good decisions in the questions that follow.

### Diff Check (if previous run exists)

If you have run repoview on this project before, it checks for changes before asking any questions:

```
  Changes since last run  (2h ago)

    ✎  src/auth.ts              (modified)
    +  src/middleware/rate-limit.ts  (new)
    -  src/old-utils.ts         (deleted)

  ❯  ⚡ Update changed files only    (fast)
     🔄 Regenerate full context      (slower, same settings)
     ⚙️  Regenerate with new settings
```

Choosing **Update changed files only** skips all questions and updates only the affected parts of the output file in a fraction of the time.

### Q1 — Skip Documentation Files?

Always shown. Asks whether to exclude `.md`, `.txt`, `.rst`, and `.mdx` files.

- **Default: Yes (skip)**
- Recommended when giving context for code understanding, bug fixes, or feature work
- Choose No if you want the LLM to understand your README, changelogs, or written docs

### Q2 — Skip Test Files? *(only shown if test files are detected)*

Shown only when the scan finds files matching test patterns:
`test_*.py` · `*.test.js` · `*.test.ts` · `*.spec.ts` · `*.spec.js` · `*_test.go` · `conftest.py` · files inside `/tests/`, `/__tests__/`, `/spec/` directories.

- **Default: Yes (skip)**
- Recommended for feature/bug context where test files add noise
- Choose No if you want the LLM to understand your test coverage or debug failing tests

### Q3 — Respect `.gitignore`? *(only shown if `.gitignore` exists)*

Shown only when a `.gitignore` file is found in the project root.

- **Default: Yes (respect)**
- Respecting it excludes `node_modules`, `.env`, `dist`, `build`, etc.
- Choose No only if you specifically need something that is gitignored (e.g. a local config file)

Note: Even when ignoring `.gitignore`, repoview always excludes `node_modules`, `.git`, `__pycache__`, `venv`, and other standard directories that would be useless noise.

### Q4 — Output File Name

```
Output file name:  my-project-context.txt  [Enter to confirm]
```

- **Default: `<foldername>-context.txt`**
- You can type any name. `.txt` is added automatically if you omit it.

### Q5 — Output Location

```
  ❯  Inside the project folder   /path/to/my-project/my-project-context.txt
     Next to the project folder  /path/to/my-project-context.txt
     Custom path…
```

- **Default: Inside the project folder**

### Confirmation Summary

Before generating, a summary is shown:

```
  ╭─ Ready to generate ──────────────────────╮
  │  Source    my-project/                   │
  │  Output    my-project-context.txt        │
  │  Skipping  ✔ Docs   ✔ Tests             │
  │  Gitignore ✔ respected                   │
  ╰──────────────────────────────────────────╯

  Generate context file?  [Y/n]
```

### Result

```
  ✔ Done in 3.8s

  ╭──────────────────────────────────────────────────╮
  │  Output     my-project-context.txt               │
  │  Tokens     ████████████░░░░  142k / 800k  (18%) │
  │  Full        98 files                            │
  │  Summarised  12 files                            │
  │  Skipped     37 files                            │
  │  Omitted      0 files                            │
  ╰──────────────────────────────────────────────────╯
```

### Post-Completion Menu

```
  ❯  📋  Copy text to clipboard    (paste directly into Claude / ChatGPT)
     📄  Copy file to clipboard    (paste the file itself)
     📁  Open output folder        (opens in Explorer / Finder)
     🔁  Run again                 (same project, change settings)
     ❌  Exit
```

**Copy text** — reads the entire output file and puts it in your clipboard as plain text. Paste directly into any LLM chat window.

**Copy file** — copies the `.txt` file itself to clipboard (not the text inside it).
- Windows: uses PowerShell `Set-Clipboard -Path`
- Mac: uses `osascript`
- Linux: falls back to copying text (file clipboard not widely supported on Linux)

**Open output folder** — opens the containing folder in your file manager.

**Run again** — restarts the wizard for the same project. Useful for trying different skip settings.

---

## CLI Reference

### `repoview [PATH]`

Launches the interactive wizard. If `PATH` is omitted, uses the current directory.

```bash
repoview
repoview ./my-project
repoview "C:\Users\Prateek\Desktop\my-project"
```

---

### `--quick` / `-q`

Skips all questions. Uses sensible defaults and runs immediately.

```bash
repoview --quick
repoview --quick ./my-project
repoview -q ./my-project
```

Defaults used in quick mode:

| Setting | Default |
|---------|---------|
| Skip docs | Yes |
| Skip tests | Yes (if any are found) |
| Respect `.gitignore` | Yes (if `.gitignore` exists) |
| Output filename | `<foldername>-context.txt` |
| Output location | Inside the project folder |

After generating, the post-completion menu is shown as normal.

---

### `--watch` / `-w`

Starts watch mode. Monitors your project for file changes and automatically updates the context file after every save.

```bash
repoview --watch
repoview --watch ./my-project
repoview -w ./my-project
```

Full details in the [Watch Mode](#watch-mode) section below.

---

### `--reset` / `-r`

Deletes the saved cache for a project and runs the wizard fresh. Use this when your settings are wrong and you want to start over — different skip choices, different output location, etc.

```bash
repoview --reset
repoview --reset ./my-project
repoview -r ./my-project
```

What it does:
1. Deletes `~/.repoview/cache/<project-hash>.json`
2. Launches the full interactive wizard
3. Saves the new cache on completion

Common workflow when settings need changing:

```bash
repoview --reset ./my-project    # clear cache + wizard
repoview --watch ./my-project    # now watch with new settings
```

---

### `--version` / `-v`

Prints the installed version and exits.

```bash
repoview --version
# repoview v1.0.0
```

---

### `--help`

Prints usage information and exits.

```bash
repoview --help
```

---

## Watch Mode

Watch mode keeps your context file permanently up to date as you work. Every time you hit save in your editor, the context file is updated automatically — usually in under a second.

```bash
repoview --watch ./my-project
```

### First Run Behaviour

If no previous context exists for the project, the **interactive wizard runs first** so you can choose exactly what to include, where to save, and what to skip. Watch mode starts automatically after generation completes.

```
  First time setup
  No previous context found for this project.
  The wizard will run once so you can choose your settings.
  Watch mode will start automatically after generation.

  [wizard questions run here — same as normal repoview]

  ✔ Generation complete — starting watch mode

  ╭─────────────────────────────────────────────────────╮
  │  👁  Watching  my-project/                          │
  │  Output    →  my-project-context.txt                │
  │  Settings  →  docs skipped  •  gitignore respected  │
  │  Press Ctrl+C to stop                               │
  ╰─────────────────────────────────────────────────────╯
```

If a previous context **already exists** (cache found), the wizard is skipped entirely and watch starts immediately using the saved settings.

### During Watch

Every time you save a file, repoview detects the change and updates the context file automatically:

```
  14:32:11  src/auth.ts changed
  14:32:11  ✔ Updated in 0.3s  143,201 tokens  (+0 ✎1 -0)

  14:35:44  src/api/users.ts + 2 more changed
  14:35:46  ✔ Updated in 0.6s  144,890 tokens  (+2 ✎1 -0)
```

The `(+0 ✎1 -0)` notation means: 0 files added, 1 file updated, 0 files deleted.

### Debounce

When multiple files change in quick succession (e.g. a `git checkout`, running `npm install`, or your editor saving multiple buffers at once), repoview waits **2 seconds** after the last change before running the update. This prevents it from running dozens of times unnecessarily.

### What Gets Ignored in Watch Mode

- The output `.txt` file itself — prevents an infinite loop
- `~/.repoview/cache/` files
- `node_modules/`, `.git/`, `__pycache__/`, `venv/`, and all other standard excluded directories
- Binary files (images, fonts, compiled files, etc.)

### Stopping Watch Mode

Press `Ctrl+C` at any time. A summary panel is shown with the exact commands to resume or change settings:

```
  ╭──────────────────────────────────────────────────────────╮
  │  Watch stopped.                                          │
  │                                                          │
  │  Settings used:  docs skipped  •  gitignore respected    │
  │  Output:         /path/to/my-project-context.txt         │
  │                                                          │
  │  To resume watching with the same settings:              │
  │    repoview --watch ./my-project                         │
  │                                                          │
  │  To change settings, reset the cache first:              │
  │    repoview --reset ./my-project                         │
  │    repoview --watch ./my-project                         │
  ╰──────────────────────────────────────────────────────────╯
```

### Requirements for Watch Mode

`watchdog` is installed automatically with repoview. If for some reason it's missing:

```bash
pip install watchdog
```

---

## Smart Diff / Incremental Updates

Every time repoview successfully generates a context file, it saves a cache entry at `~/.repoview/cache/`. The next time you run `repoview` on the same project, it checks this cache and shows you exactly what changed — then lets you choose how to update.

### How the Diff Works

repoview uses a two-step check to determine what changed since the last run:

1. **Fast path — modification time (`mtime`)**: If a file's `mtime` is unchanged, it hasn't changed. This check takes microseconds and covers the vast majority of files.

2. **Hash verification — SHA1**: If `mtime` changed, repoview computes a SHA1 hash of the file's content. If the hash matches the cached hash, the file was touched (e.g. by a tool) but the content is actually the same — it's treated as unchanged.

3. **True change**: If both `mtime` and hash differ, the file is marked as modified and will be reprocessed.

This design means even on a 1,000-file project, the diff check completes in well under a second.

### What Incremental Update Does

Instead of rewriting the entire output file, the incremental updater surgically patches only the changed sections:

- **Modified files** → reprocesses the file and replaces its block in the output file
- **New files** → processes the file and inserts its block at the correct position (sorted by priority)
- **Deleted files** → removes their block from the output file entirely
- **Unchanged files** → not touched, not re-read from disk

After patching, two things are updated:
- The **directory tree** at the top of the output file is rebuilt to reflect the current folder structure
- The **token count** in the footer is recalculated and updated

### Automatic Update

No prompt, no choices. repoview just does the right thing:

| Situation | What happens |
|-----------|-------------|
| Cache exists, output file exists, files changed | Incremental update — only changed files reprocessed |
| Cache exists, output file exists, nothing changed | Skips straight to post-completion menu |
| Cache missing or output file deleted | Full generation runs automatically |
| Incremental update fails (e.g. output was manually edited) | Falls back to full generation automatically |

Incremental update typically completes in **0.1s–1s** regardless of project size, because unchanged files are never touched.

---

## File Classification

repoview assigns every file a priority level which controls both the order files appear in the output and how aggressively they are trimmed when the token budget is tight.

| Priority | Level | What's included |
|----------|-------|-----------------|
| 1 | **Essential** | `README.md` · `package.json` · `requirements.txt` · `Dockerfile` · `pyproject.toml` · `manage.py` · `main.py` · `app.py` · `go.mod` · `tsconfig.json` · `docker-compose.yml` · `vite.config.ts` · `.env.example` · `cargo.toml` · and other project-definition files |
| 2 | **Important Code** | `.py` `.js` `.ts` `.tsx` `.jsx` `.go` `.rs` `.java` `.cs` `.cpp` `.c` `.h` `.rb` `.php` `.swift` `.kt` `.vue` `.svelte` `.sql` `.graphql` `.proto` `.sol` `.scss` `.css` `.html` |
| 3 | **Config & Support** | `.json` `.yml` `.yaml` `.toml` `.ini` `.env` `.sh` `.bat` `.ps1` `.tf` `.tfvars` `.xml` `.conf` `.cfg` |
| 4 | **General Code** | Less common languages: `.lua` `.dart` `.scala` `.hs` `.ex` `.erl` `.clj` `.r` `.tex` `.fs` `.gd` and others |
| 5 | **General Text** | Files with unrecognised extensions that appear to be text |
| 10 | **Metadata only** | Binary files, images, fonts, compiled files, lock files, `.log` `.cache` `.tmp` — never read, only noted as `[metadata-only or empty file]` |

Files you choose to skip (docs, tests) are treated as **Metadata only** regardless of extension.

### Always-Excluded Directories

These directories are never walked, regardless of `.gitignore` settings:

`.git` · `node_modules` · `vendor` · `venv` · `env` · `__pycache__` · `target` · `build` · `dist` · `out` · `bin` · `obj` · `.vscode` · `.idea` · `.gradle` · `.pytest_cache` · `coverage` · `.mypy_cache` · `.tox` · `.next` · `.nuxt` · `.svelte-kit` · `storybook-static`

---

## Token Budget & Trimming

The default token budget is **800,000 tokens**, suitable for Claude 3.5 Sonnet and most large-context models. repoview uses `tiktoken` with the `cl100k_base` encoding — the same tokenizer used by GPT-4 and Claude — so the count is accurate.

### What Happens When the Budget is Exceeded

repoview trims in two passes, always preserving higher-priority files first.

**Pass 1 — Full content → Summary**

Lower-priority files are replaced with a summary instead of their full content. The summary type depends on the file:

- **Python files**: imports, class names, function signatures extracted via AST (Python's abstract syntax tree). Accurate and fast.
- **Other code files**: function and class signatures extracted via regex patterns. Works across JS, TS, Go, Java, C++, and most other languages.
- **Text and config files**: first 3,000 characters as a preview, with a note of the full token count.

Essential files (priority 1) are **never** summarised.

**Pass 2 — Summary → Omitted**

If still over budget after summarising everything possible, the lowest-priority files are removed entirely:

```
[Omitted to fit token budget: path/to/large-file.ts]
```

Essential files are **never** omitted.

The result display shows exactly what happened:

```
  Full        98 files    ← complete content included
  Summarised  12 files    ← signatures/preview only
  Skipped     37 files    ← metadata note (binary, gitignored, or your skip choice)
  Omitted      0 files    ← removed entirely to fit budget
```

---

## Cache System

### Location

```
~/.repoview/
└── cache/
    ├── a3f9c2b1d4e8f012.json    ← project A
    ├── bc1234567890abcd.json    ← project B
    └── ...
```

Each project gets its own cache file named by a 16-character SHA1 hash of the project's absolute path. **Your project folder is never modified.** No hidden files, no `.repoview` directory in your repo.

### Cache File Contents

```json
{
  "version": 1,
  "project_path": "/abs/path/to/project",
  "generated_at": "2025-03-16T14:32:11",
  "output_path": "/abs/path/to/project/project-context.txt",
  "settings": {
    "skip_docs": true,
    "skip_tests": true,
    "respect_gitignore": true
  },
  "files": {
    "src/auth.ts": {
      "mtime": 1710598331.4,
      "hash": "a3f9c2b1...",
      "decision": "full",
      "tokens": 847
    },
    "src/big-file.ts": {
      "mtime": 1710598290.1,
      "hash": "bc123456...",
      "decision": "summary",
      "tokens": 312
    }
  }
}
```

### Cache Reliability

- Written **atomically** via a temp file + rename — a crash or power cut during write never corrupts the cache
- If the cache is missing, corrupt, or from an older schema version, repoview treats it as if no cache exists and runs a full generation
- If the output `.txt` file has been deleted but the cache exists, repoview detects this and runs a full generation automatically

---

## Output File Format

The generated `.txt` file has a consistent, human-readable structure:

```
repoview context — my-project
Generated by: repoview

Directory structure:
└── my-project/
    ├── src/
    │   ├── auth.ts
    │   └── api/
    │       └── users.ts
    ├── package.json
    └── README.md

────────────────────────────────────────────────────────────

── FILE: package.json [1823B | prio:1 | full] ──
{
  "name": "my-project",
  ...full content...
}
── END: package.json ──

── FILE: src/auth.ts [4201B | prio:2 | full] ──
...full content...
── END: src/auth.ts ──

── FILE: src/large-file.ts [98420B | prio:2 | summary] ──
[Code summary: large-file.ts]
  imports: express, zod, prisma
  class AuthController(BaseController)
  class TokenService
  def generateToken(payload) -> string
  def verifyToken(token) -> Payload | null
  ... [8,431 tokens full]
── END: src/large-file.ts ──

────────────────────────────────────────────────────────────
repoview | tokens used: 142,847 / 800,000
full: 98  summary: 12  metadata: 37  omitted: 0
```

Each file block header includes the file size in bytes, its priority level, and the decision made (full / summary / metadata / omitted). This metadata helps the LLM understand which files are complete and which were trimmed.

---

## Publishing a New Version

```bash
# 1. Bump the version in TWO places:

# repoview/__init__.py
__version__ = "1.1.0"

# pyproject.toml
version = "1.1.0"

# 2. Remove old build artifacts
rm -rf dist/ build/ *.egg-info

# 3. Build the package
python -m build

# 4. Upload to PyPI
twine upload dist/*
```

### Versioning convention

| Change type | Example |
|-------------|---------|
| Bug fix | `1.0.0 → 1.0.1` |
| New feature, backward compatible | `1.0.0 → 1.1.0` |
| Breaking change | `1.0.0 → 2.0.0` |

### Automate version bumping

```bash
pip install bump2version
bump2version patch   # 1.0.0 → 1.0.1  (updates both files automatically)
bump2version minor   # 1.0.0 → 1.1.0
bump2version major   # 1.0.0 → 2.0.0
```

### Save PyPI credentials

Create `~/.pypirc` so you don't type your password every release:

```ini
[pypi]
username = __token__
password = pypi-AgENdGVzdC5weXBpLm9yZwI...
```

Get your API token at: https://pypi.org/manage/account/token/

---

## Requirements

| Package | Version | Purpose |
|---------|---------|---------|
| `tiktoken` | ≥ 0.7.0 | Accurate token counting using the same tokenizer as GPT-4 / Claude |
| `pathspec` | ≥ 0.12.1 | `.gitignore` pattern matching |
| `questionary` | ≥ 2.0.1 | Interactive terminal prompts |
| `rich` | ≥ 13.0.0 | Coloured output, progress bars, panels, tables |
| `typer` | ≥ 0.12.0 | CLI argument parsing |
| `pyperclip` | ≥ 1.8.2 | Cross-platform clipboard support |
| `watchdog` | ≥ 4.0.0 | File system events for `--watch` mode (Windows, Mac, Linux) |

**Python 3.9 or higher required.**

All dependencies are installed automatically when you run `pip install repoview`.

---

## License

MIT