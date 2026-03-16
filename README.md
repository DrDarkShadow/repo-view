# repoview

> Turn any codebase into LLM-ready context — in seconds.

```bash
pip install repoview
```

---

## Usage

```bash
# Interactive wizard (recommended)
repoview
repoview "C:\Users\Prateek\Desktop\myproject"

# Skip all questions — sensible defaults
repoview --quick
repoview --quick ./my-project

# Version
repoview --version
```

---

## What it does

1. **Scans** your project — shows file count, size, top extensions
2. **Asks** a few quick questions (only what's relevant to your project):
   - Skip docs? (`.md`, `.txt`, `.rst`)
   - Skip test files? *(only asked if tests are found)*
   - Respect `.gitignore`? *(only asked if `.gitignore` exists)*
   - Output filename and location
3. **Generates** a single `.txt` file with all your code, intelligently trimmed to fit within the token budget
4. **Post-menu** — copy text, copy file, open folder, run again

---

## After it's done

```
❯  What do you want to do next?

  📋  Copy text to clipboard   (paste into Claude / ChatGPT)
  📄  Copy file to clipboard   (paste the file itself)
  📁  Open output folder       (in Explorer / Finder)
  🔁  Run again                (same project, new settings)
  ❌  Exit
```

---

## Requirements

- Python 3.9+
- `tiktoken` — token counting
- `pathspec` — `.gitignore` parsing
- `questionary` — interactive prompts
- `rich` — terminal UI
- `typer` — CLI framework
- `pyperclip` — clipboard support

---

## Publishing a new version

```bash
# 1. Bump version in repoview/__init__.py and pyproject.toml
# 2. Clean old builds
rm -rf dist/ build/ *.egg-info
# 3. Build
python -m build
# 4. Upload
twine upload dist/*
```

---

## License

MIT