"""
core.py — file reading, classification, summarisation, output writing.
Fully decoupled from UI.
"""

from __future__ import annotations

import ast
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

try:
    import tiktoken
    _tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    _tokenizer = None

try:
    import pathspec as _pathspec_mod
except ImportError:
    _pathspec_mod = None

from repoview.config import (
    DOC_EXTS,
    ESSENTIAL_FILENAMES,
    EXCLUDE_DIRS,
    GENERAL_CODE_EXTS,
    IMPORTANT_CODE_EXTS,
    MAX_CHARS_TEXT_PREVIEW,
    MAX_FILE_SIZE_BYTES,
    MAX_LINES_FALLBACK,
    MAX_SIGNATURES_SUMMARY,
    METADATA_ONLY_EXTS,
    PRIORITY_ESSENTIAL,
    PRIORITY_FOCUS,
    PRIORITY_GENERAL_CODE,
    PRIORITY_GENERAL_TEXT,
    PRIORITY_IMPORTANT_CODE,
    PRIORITY_METADATA_ONLY,
    PRIORITY_SUPPORTING_CONFIG,
    SUPPORTING_CONFIG_EXTS,
    TEST_DIR_NAMES,
    TEST_FILENAME_PATTERNS,
    TOKEN_BUDGET,
)


# ── Token counting ────────────────────────────────────────────────────────────

def count_tokens(text: str) -> int:
    if _tokenizer:
        return len(_tokenizer.encode(text, disallowed_special=()))
    return len(text) // 3


# ── Test file detection ───────────────────────────────────────────────────────

_TEST_RE = [re.compile(p, re.IGNORECASE) for p in TEST_FILENAME_PATTERNS]

def _is_test_file(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts[:-1]:
        if part.lower() in TEST_DIR_NAMES:
            return True
    return any(rx.search(parts[-1]) for rx in _TEST_RE)


# ── FileEntry ─────────────────────────────────────────────────────────────────

class FileEntry:
    def __init__(
        self,
        relative_path: str,
        size: int,
        get_bytes: Callable[[], bytes],
        is_dir: bool = False,
    ):
        self.relative_path = relative_path
        self.size = size
        self._get_bytes = get_bytes
        self.is_dir = is_dir

        self.priority: int = PRIORITY_METADATA_ONLY
        self.initial_content_type: str = "metadata"
        self.full_text: Optional[str] = None
        self.summary_text: Optional[str] = None
        self.tokens_full: int = 0
        self.tokens_summary: int = 0
        self.error: Optional[str] = None
        self.chosen: str = "full"          # full | summary | metadata | omitted
        self.tokens_chosen: int = 0

    # ── reading ──────────────────────────────────────────────────────────────

    def _read(self) -> None:
        if self.is_dir or self.full_text is not None:
            return
        if self.size > MAX_FILE_SIZE_BYTES:
            self.error = f"File too large ({self.size/(1024*1024):.1f} MB)"
            self.initial_content_type = "metadata"
            return
        try:
            raw = self._get_bytes()
            self.full_text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                self.full_text = raw.decode("latin-1")  # type: ignore[possibly-undefined]
                self.error = "Decoded as Latin-1"
            except Exception:
                self.full_text = f"[Binary preview]\n{raw[:256].hex(' ', 8)}"  # type: ignore
                self.initial_content_type = "metadata"
        except Exception as e:
            self.error = str(e)
            self.initial_content_type = "metadata"

    # ── classify + summarise ──────────────────────────────────────────────────

    def process(
        self,
        skip_docs: bool = False,
        skip_tests: bool = False,
        focus_path: str = "",
    ) -> None:
        if self.is_dir:
            self.initial_content_type = "metadata"
            self.priority = PRIORITY_METADATA_ONLY
            return

        ext = os.path.splitext(self.relative_path)[1].lower()
        basename = os.path.basename(self.relative_path).lower()

        # Focus mode — files outside focus path become structure-only
        if focus_path:
            inside_focus = (
                self.relative_path == focus_path
                or self.relative_path.startswith(focus_path.rstrip("/") + "/")
            )
            is_essential = basename in ESSENTIAL_FILENAMES
            if not inside_focus and not is_essential:
                self.priority = PRIORITY_METADATA_ONLY
                self.initial_content_type = "structure_only"
                self.summary_text = "[Structure only]"
                self.tokens_summary = 0
                return
            # Inside focus path → mark priority 0, skip doc/test filtering
            if inside_focus and ext not in METADATA_ONLY_EXTS and self.size > 0:
                self.priority = PRIORITY_FOCUS
                self.initial_content_type = "full"
                self._read()
                if self.full_text is not None:
                    self.tokens_full = count_tokens(self.full_text)
                    self.summary_text = self._code_summary() if ext in IMPORTANT_CODE_EXTS else self._text_preview()
                    self.tokens_summary = count_tokens(self.summary_text)
                else:
                    self.summary_text = f"[Error: {self.error or 'unreadable'}]"
                    self.tokens_summary = count_tokens(self.summary_text)
                return

        # Hard metadata
        if ext in METADATA_ONLY_EXTS or self.size == 0:
            self.priority = PRIORITY_METADATA_ONLY
            self.initial_content_type = "metadata"

        # Skip groups
        elif skip_docs and ext in DOC_EXTS:
            self.priority = PRIORITY_METADATA_ONLY
            self.initial_content_type = "metadata"
        elif skip_tests and _is_test_file(self.relative_path):
            self.priority = PRIORITY_METADATA_ONLY
            self.initial_content_type = "metadata"

        # Essential
        elif basename in ESSENTIAL_FILENAMES:
            self.priority = PRIORITY_ESSENTIAL
            self.initial_content_type = "full"
        elif ext in IMPORTANT_CODE_EXTS:
            self.priority = PRIORITY_IMPORTANT_CODE
            self.initial_content_type = "full"
        elif ext in SUPPORTING_CONFIG_EXTS:
            self.priority = PRIORITY_SUPPORTING_CONFIG
            self.initial_content_type = "full"
        elif ext in GENERAL_CODE_EXTS:
            self.priority = PRIORITY_GENERAL_CODE
            self.initial_content_type = "full"
        else:
            self.priority = PRIORITY_GENERAL_TEXT
            self.initial_content_type = "full"

        if self.initial_content_type == "metadata":
            self.summary_text = "[Skipped / metadata only]"
            self.tokens_summary = count_tokens(self.summary_text)
            return

        self._read()

        if self.full_text is None or self.initial_content_type == "metadata":
            self.summary_text = f"[Error: {self.error or 'unknown'}]"
            self.tokens_summary = count_tokens(self.summary_text)
            return

        self.tokens_full = count_tokens(self.full_text)

        if self.priority == PRIORITY_ESSENTIAL:
            self.summary_text = "[Essential — full content kept]"
            self.tokens_summary = self.tokens_full
        elif self.priority in (PRIORITY_IMPORTANT_CODE, PRIORITY_GENERAL_CODE):
            self.summary_text = self._code_summary()
            self.tokens_summary = count_tokens(self.summary_text)
        else:
            self.summary_text = self._text_preview()
            self.tokens_summary = count_tokens(self.summary_text)

    # ── summarisers ──────────────────────────────────────────────────────────

    def _code_summary(self) -> str:
        if not self.full_text:
            return "[empty]"
        if self.relative_path.endswith(".py"):
            try:
                tree = ast.parse(self.full_text)
                parts = [f"[Python summary: {os.path.basename(self.relative_path)}]"]
                imports: set = set()
                sigs: list = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for a in node.names:
                            if a.name: imports.add(a.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module: imports.add(node.module.split(".")[0])
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = ast.unparse(node.args) if hasattr(ast, "unparse") else "..."
                        sig = f"  def {node.name}({args})"
                        if node.returns and hasattr(ast, "unparse"):
                            sig += f" -> {ast.unparse(node.returns)}"
                        sigs.append(sig)
                    elif isinstance(node, ast.ClassDef):
                        bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
                        sig = f"  class {node.name}" + (f"({', '.join(bases)})" if bases else "")
                        sigs.append(sig)
                if imports:
                    parts.append(f"  imports: {', '.join(sorted(imports))}")
                parts.extend(sigs[:MAX_SIGNATURES_SUMMARY])
                if len(sigs) > MAX_SIGNATURES_SUMMARY:
                    parts.append(f"  … +{len(sigs)-MAX_SIGNATURES_SUMMARY} more")
                parts.append(f"  [{self.tokens_full} tokens full]")
                return "\n".join(parts)
            except Exception:
                pass
        return self._basic_code_summary()

    def _basic_code_summary(self) -> str:
        if not self.full_text:
            return "[empty]"
        parts = [f"[Code summary: {os.path.basename(self.relative_path)}]"]
        pattern = (
            r"^\s*(?:(?:async\s+)?(?:public\s+|private\s+|protected\s+|static\s+)*"
            r"\b(?:class|interface|struct|enum|function|def|fn|func|module|type)\b"
            r"\s+\w+.*?[:({])"
        )
        lines = self.full_text.splitlines()
        sigs = []
        for i, line in enumerate(lines):
            if len(sigs) >= MAX_SIGNATURES_SUMMARY:
                break
            if re.search(pattern, line, re.IGNORECASE):
                sigs.append(f"  L{i+1}: {line.strip()}")
        if sigs:
            parts.extend(sigs)
        else:
            parts.extend(
                f"  {l.strip()}"
                for l in lines[:MAX_LINES_FALLBACK]
                if l.strip()
            )
        parts.append(f"  [{self.tokens_full} tokens full]")
        return "\n".join(parts)

    def _text_preview(self) -> str:
        if not self.full_text:
            return "[empty]"
        preview = self.full_text[:MAX_CHARS_TEXT_PREVIEW]
        suffix = f"\n  … [{self.tokens_full} tokens full]" if len(self.full_text) > MAX_CHARS_TEXT_PREVIEW else ""
        return f"[Preview: {os.path.basename(self.relative_path)}]\n{preview}{suffix}"

    def final_content(self) -> str:
        if self.chosen == "full":
            txt = self.full_text or ""
            if self.error and "Latin-1" in (self.error or ""):
                txt = f"[Note: {self.error}]\n{txt}"
            return txt or "[unavailable]"
        elif self.chosen == "summary":
            return self.summary_text or "[no summary]"
        elif self.chosen == "metadata":
            return self.summary_text or "[metadata]"
        elif self.chosen == "omitted":
            return f"[Omitted to fit token budget: {self.relative_path}]"
        return "[unknown]"


# ── File collectors ───────────────────────────────────────────────────────────

def collect_folder(
    folder: str,
    respect_gitignore: bool = True,
) -> List[FileEntry]:
    entries: List[FileEntry] = []
    base = os.path.abspath(folder)
    spec = None
    exclude_lower = {d.lower() for d in EXCLUDE_DIRS}

    if respect_gitignore and _pathspec_mod:
        gi = os.path.join(base, ".gitignore")
        if os.path.exists(gi):
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    with open(gi, encoding=enc) as f:
                        spec = _pathspec_mod.PathSpec.from_lines(
                            "gitwildmatch", f.read().splitlines()
                        )
                    break
                except Exception:
                    continue

    for root, dirs, files in os.walk(base, topdown=True):
        rel_root = os.path.relpath(root, base).replace(os.sep, "/")
        if rel_root == ".":
            rel_root = ""

        dirs[:] = sorted([
            d for d in dirs
            if d.lower() not in exclude_lower
            and not (spec and spec.match_file(
                (rel_root + "/" + d if rel_root else d) + "/"
            ))
        ])

        for dname in dirs:
            rel = (rel_root + "/" + dname if rel_root else dname) + "/"
            entries.append(FileEntry(rel, 0, lambda: b"", is_dir=True))

        for fname in sorted(files):
            full = os.path.join(root, fname)
            rel = rel_root + "/" + fname if rel_root else fname
            if spec and spec.match_file(rel):
                continue
            try:
                size = os.path.getsize(full)
                entries.append(FileEntry(
                    rel, size,
                    lambda fp=full: open(fp, "rb").read()
                ))
            except OSError:
                pass

    return entries


def collect_zip(zip_path: str) -> List[FileEntry]:
    entries: List[FileEntry] = []
    exclude_lower = {d.lower() for d in EXCLUDE_DIRS}
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                parts = info.filename.split("/")
                if any(p.lower() in exclude_lower for p in parts):
                    continue
                is_dir = info.filename.endswith("/")
                entries.append(FileEntry(
                    info.filename,
                    info.file_size,
                    lambda zf_=zf, n=info.filename: zf_.read(n),
                    is_dir=is_dir,
                ))
    except zipfile.BadZipFile:
        pass
    return entries


# ── Tree builder ──────────────────────────────────────────────────────────────

def build_tree(entries: List[FileEntry]) -> str:
    node: Dict[str, Any] = {}
    for e in entries:
        parts = e.relative_path.rstrip("/").split("/")
        cur = node
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            if not is_last or e.relative_path.endswith("/"):
                cur = cur.setdefault(part + "/", {})
            else:
                cur[part] = None

    def _render(n: dict, prefix: str = "") -> str:
        lines = []
        items = sorted(n.items())
        for i, (name, children) in enumerate(items):
            last = i == len(items) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}")
            if children is not None:
                lines.append(_render(children, prefix + ("    " if last else "│   ")))
        return "\n".join(filter(None, lines))

    return _render(node)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class GenerateResult:
    output_path: str
    total_tokens: int
    files_full: int = 0
    files_summary: int = 0
    files_metadata: int = 0
    files_omitted: int = 0
    warnings: List[str] = field(default_factory=list)
    # populated after run — used by cache + differ
    all_entries: List[Any] = field(default_factory=list)
    # focus mode stats
    files_structure_only: int = 0
    focus_path: str = ""



# ── Focus path normalisation ──────────────────────────────────────────────────

def _norm_focus(project_root: str, focus_path: str) -> str:
    """
    Normalise a user-supplied focus path to a relative POSIX path suitable
    for startswith() matching against FileEntry.relative_path.

    Examples
    --------
    focus_path = "src/auth"       → "src/auth/"
    focus_path = "./src/auth/"    → "src/auth/"
    focus_path = "src/auth.ts"    → "src/auth.ts"  (specific file, no trailing /)
    focus_path = "/abs/path/src"  → "src/"          (absolute → relative)
    """
    if not focus_path:
        return ""

    root = os.path.abspath(project_root)
    fp   = os.path.expanduser(focus_path)

    # If absolute, make relative to project root
    if os.path.isabs(fp):
        try:
            fp = os.path.relpath(fp, root)
        except ValueError:
            pass   # different drive on Windows — leave as-is

    # Normalise separators and strip leading ./
    fp = fp.replace(os.sep, "/").lstrip("./").strip("/")

    if not fp:
        return ""

    # Detect if it's a directory (either user added slash, or it exists as dir)
    abs_candidate = os.path.join(root, fp.replace("/", os.sep))
    if focus_path.rstrip().endswith("/") or (
        os.path.exists(abs_candidate) and os.path.isdir(abs_candidate)
    ):
        return fp + "/"

    return fp   # specific file — no trailing slash


# ── Main orchestrator ─────────────────────────────────────────────────────────

def generate_context(
    input_path: str,
    output_path: str,
    skip_docs: bool = False,
    skip_tests: bool = False,
    respect_gitignore: bool = True,
    token_budget: int = TOKEN_BUDGET,
    focus_path: str = "",
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> GenerateResult:

    # Collect
    if os.path.isdir(input_path):
        entries = collect_folder(input_path, respect_gitignore)
        display = os.path.basename(os.path.abspath(input_path))
    elif input_path.lower().endswith(".zip"):
        entries = collect_zip(input_path)
        display = os.path.basename(input_path)
    else:
        raise ValueError(f"Unsupported input: {input_path}")

    if not entries:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("(No files found)\n")
        return GenerateResult(output_path, 0)

    # Process
    total = len(entries)
    for i, e in enumerate(entries):
        e.process(skip_docs=skip_docs, skip_tests=skip_tests, focus_path=_norm_focus(input_path, focus_path))
        if progress_cb:
            progress_cb(i + 1, total)

    # Budget allocation
    tree = build_tree(entries)
    _focus_norm = _norm_focus(input_path, focus_path)
    focus_note = f"\nFocus mode: {focus_path}  (all other files structure-only)" if focus_path else ""
    header = (
        f"repoview context — {display}{focus_note}\n"
        f"Generated by: repoview\n\n"
        f"Directory structure:\n{tree}\n\n"
        f"{'─'*60}\n\n"
    )
    used = count_tokens(header)

    # structure_only files appear in tree but get no content block
    content = [e for e in entries if not e.is_dir and e.initial_content_type != "structure_only"]
    structure_only_count = sum(1 for e in entries if not e.is_dir and e.initial_content_type == "structure_only")

    for e in content:
        if e.initial_content_type == "metadata":
            e.chosen = "metadata"
            e.tokens_chosen = e.tokens_summary
        else:
            e.chosen = "full"
            e.tokens_chosen = e.tokens_full
        used += count_tokens(f"── {e.relative_path} ──\n\n") + e.tokens_chosen

    # Trim pass 1 — full → summary
    if used > token_budget:
        trimmable = sorted(
            [e for e in content
             if e.chosen == "full"
             and e.priority not in (PRIORITY_ESSENTIAL, PRIORITY_FOCUS)
             and e.tokens_summary < e.tokens_full],
            key=lambda e: (e.priority, -(e.tokens_full - e.tokens_summary)),
            reverse=True,
        )
        for e in trimmable:
            if used <= token_budget: break
            used -= e.tokens_full - e.tokens_summary
            e.chosen = "summary"
            e.tokens_chosen = e.tokens_summary

    # Trim pass 2 — full/summary → omitted
    if used > token_budget:
        trimmable2 = sorted(
            [e for e in content
             if e.chosen in ("full", "summary")
             and e.priority not in (PRIORITY_ESSENTIAL, PRIORITY_FOCUS)],
            key=lambda e: (e.priority, -e.tokens_chosen),
            reverse=True,
        )
        for e in trimmable2:
            if used <= token_budget: break
            note_tokens = count_tokens(f"[Omitted: {e.relative_path}]")
            saving = e.tokens_chosen - note_tokens
            if saving > 0:
                used -= saving
                e.chosen = "omitted"
                e.tokens_chosen = note_tokens

    content.sort(key=lambda e: (e.priority, e.relative_path))

    # Write
    result = GenerateResult(
        output_path=output_path,
        total_tokens=0,
        files_structure_only=structure_only_count,
        focus_path=focus_path,
    )
    actual = count_tokens(header)

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(header)
        for e in content:
            body = e.final_content()
            fh = (
                f"── FILE: {e.relative_path} "
                f"[{e.size}B | prio:{e.priority} | {e.chosen}] ──\n"
            )
            ff = f"\n── END: {e.relative_path} ──\n\n"
            actual += count_tokens(fh) + count_tokens(body) + count_tokens(ff)
            out.write(fh); out.write(body); out.write(ff)

            if e.chosen == "full":    result.files_full += 1
            elif e.chosen == "summary": result.files_summary += 1
            elif e.chosen == "metadata": result.files_metadata += 1
            else: result.files_omitted += 1

        focus_footer = f"  focus: {focus_path}  structure-only: {structure_only_count}" if focus_path else ""
        footer = (
            f"\n{'─'*60}\n"
            f"repoview | tokens used: {actual:,} / {token_budget:,}\n"
            f"full: {result.files_full}  "
            f"summary: {result.files_summary}  "
            f"metadata: {result.files_metadata}  "
            f"omitted: {result.files_omitted}"
            f"{focus_footer}\n"
        )
        out.write(footer)
        actual += count_tokens(footer)

    if actual > token_budget * 1.05:
        result.warnings.append(
            f"Exceeded budget by {actual - token_budget:,} tokens. "
            f"Consider skipping more file types."
        )

    result.total_tokens = actual
    result.all_entries = entries

    # Save cache after every successful full run
    try:
        from repoview.cache import build_cache, save_cache
        settings = {
            "skip_docs":         skip_docs,
            "skip_tests":        skip_tests,
            "respect_gitignore": respect_gitignore,
            "focus_path":        focus_path,
        }
        cache = build_cache(input_path, output_path, settings, entries)
        save_cache(cache)
    except Exception:
        pass   # cache failure never breaks the main run

    return result