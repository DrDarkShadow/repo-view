# codecontext

> Generate LLM-ready context files from your codebase — interactively.

```
pip install codecontext
```

---

## Usage

### Interactive wizard (recommended)

```bash
cc
```

Launches a Vite-style interactive prompt:

```
╭──────────────────────────────────────────╮
│  codecontext  v1.0.0                     │
│  Generate LLM-ready context from your    │
│  codebase                                │
╰──────────────────────────────────────────╯

◆ Where is your project?
  ● Current directory (.)
  ○ Specify a folder path
  ○ Select a ZIP file

◆ Which file categories to include?
  ✔ Essential files (README, requirements, Dockerfile…)
  ✔ Source code (.py, .js, .ts, .go, .rs…)
  ✔ Config & text files (.json, .yml, .md, .toml…)
  ✗ Rare languages (.lua, .dart, .scala, .hs…)
  ✗ Other text files (unclassified extensions)

◆ How should .gitignore be handled?
  ● Respect .gitignore (recommended)
  ○ Include everything

◆ Token budget?
  ● Claude 3.5 (800k)
  ○ GPT-4 Turbo (128k)
  ○ Gemini 1.5 Pro (1M)
  ○ Custom

◆ Output file name: my_project_context.txt

✔ Done in 3.2s
  Output      /path/to/my_project_context.txt
  Tokens      ████████████░░░░░░░░░░░░░░░░░░  142,847 / 800,000  (17.9%)
  Full files  89
  Summary     23
  Metadata    12
  Omitted     0
```

### Non-interactive mode

```bash
# Run on current directory
cc run

# Run on a specific path
cc run ./my-project

# Custom output and budget
cc run ./my-project -o context.txt --budget 128000

# Include files that are in .gitignore
cc run ./my-project --no-gitignore
```

### Other commands

```bash
cc --version     # Show version
cc info          # System info and dependency check
cc --help        # Help
```

---

## How it works

codecontext intelligently processes your project:

| Priority | Files |
|----------|-------|
| Essential | `README.md`, `package.json`, `Dockerfile`, `requirements.txt`, … |
| Code | `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, … |
| Config | `.json`, `.yml`, `.toml`, `.env.example`, … |
| General | Less common languages and text files |

When the output would exceed your token budget, it automatically:
1. **Summarises** lower-priority files (extracts function signatures, first N lines)
2. **Omits** the lowest-priority content with a note in its place

---

## Requirements

- Python 3.9+
- `tiktoken` (token counting)
- `pathspec` (.gitignore parsing)
- `questionary` (interactive prompts)
- `rich` (terminal UI)
- `typer` (CLI framework)

---

## License

MIT