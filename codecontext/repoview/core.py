"""
Core processing logic for codecontext.
Fully decoupled from UI — pure functions and data classes only.
"""

from __future__ import annotations

import ast
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional

try:
    import tiktoken
    _tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    _tokenizer = None

try:
    import pathspec as _pathspec_mod
except ImportError:
    _pathspec_mod = None

from codecontext.config import (
    ESSENTIAL_FILENAMES,
    EXCLUDE_DIRS,
    GENERAL_CODE_EXTS_FALLBACK,
    IMPORTANT_CODE_EXTS,
    MAX_CHARS_TEXT_SUMMARY,
    MAX_FILE_SIZE_TO_READ_BYTES,
    MAX_LINES_CODE_SUMMARY_FALLBACK,
    MAX_SIGNATURES_CODE_SUMMARY,
    METADATA_ONLY_EXTS,
    PRIORITY_ESSENTIAL,
    PRIORITY_GENERAL_CODE,
    PRIORITY_GENERAL_TEXT,
    PRIORITY_IMPORTANT_CODE,
    PRIORITY_METADATA_ONLY,
    PRIORITY_SUPPORTING_TEXT_CONFIG,
    SUPPORTING_TEXT_CONFIG_EXTS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Token counting
# ─────────────────────────────────────────────────────────────────────────────

def count_tokens(text: str) -> int:
    if _tokenizer:
        return len(_tokenizer.encode(text, disallowed_special=()))
    return len(text) // 3


# ─────────────────────────────────────────────────────────────────────────────
# FileEntry
# ─────────────────────────────────────────────────────────────────────────────

class FileEntry:
    def __init__(
        self,
        relative_path: str,
        size: int,
        get_content_bytes_func: Callable[[], bytes],
        is_dir_entry: bool = False,
    ):
        self.relative_path = relative_path
        self.size = size
        self._get_content_bytes_func = get_content_bytes_func
        self.is_dir_entry = is_dir_entry

        self.priority: int = PRIORITY_METADATA_ONLY
        self.initial_content_type: str = "metadata"

        self.full_content_text: Optional[str] = None
        self.summary_content_text: Optional[str] = None

        self.tokens_full: int = 0
        self.tokens_summary: int = 0

        self.error_processing: Optional[str] = None

        self.chosen_output_type: str = "full"
        self.tokens_for_chosen_output: int = 0

    # ── reading ──────────────────────────────────────────────────────────────

    def _read_and_decode_content(self) -> None:
        if self.is_dir_entry or self.full_content_text is not None:
            return
        if self.size > MAX_FILE_SIZE_TO_READ_BYTES:
            self.error_processing = (
                f"File size ({self.size / (1024*1024):.1f} MB) exceeds limit."
            )
            self.initial_content_type = "metadata"
            return
        try:
            content_bytes = self._get_content_bytes_func()
            self.full_content_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                self.full_content_text = content_bytes.decode("latin-1")  # type: ignore[possibly-undefined]
                self.error_processing = "UTF-8 failed; decoded as Latin-1."
            except UnicodeDecodeError:
                self.error_processing = "Binary content."
                self.full_content_text = (
                    f"[Binary Content Preview]:\n{content_bytes[:256].hex(' ', 8)}"  # type: ignore
                )
                self.initial_content_type = "metadata"
        except Exception as e:
            self.error_processing = f"Read error: {e}"
            self.initial_content_type = "metadata"

    # ── categorize + summarize ───────────────────────────────────────────────

    def categorize_and_summarize(
        self,
        include_categories: Optional[set] = None,
    ) -> None:
        """
        include_categories: set of priority ints to include.
        None means include all.
        """
        if self.is_dir_entry:
            self.initial_content_type = "metadata"
            self.priority = PRIORITY_METADATA_ONLY
            return

        basename_lower = os.path.basename(self.relative_path).lower()
        file_ext = os.path.splitext(self.relative_path)[1].lower()

        if file_ext in METADATA_ONLY_EXTS or self.size == 0:
            self.priority = PRIORITY_METADATA_ONLY
            self.initial_content_type = "metadata"
        elif basename_lower in ESSENTIAL_FILENAMES:
            self.priority = PRIORITY_ESSENTIAL
            self.initial_content_type = "full"
        elif file_ext in IMPORTANT_CODE_EXTS:
            self.priority = PRIORITY_IMPORTANT_CODE
            self.initial_content_type = "full"
        elif file_ext in SUPPORTING_TEXT_CONFIG_EXTS:
            self.priority = PRIORITY_SUPPORTING_TEXT_CONFIG
            self.initial_content_type = "full"
        elif file_ext in GENERAL_CODE_EXTS_FALLBACK:
            self.priority = PRIORITY_GENERAL_CODE
            self.initial_content_type = "full"
        else:
            self.priority = PRIORITY_GENERAL_TEXT
            self.initial_content_type = "full"

        # Honour category filter — downgrade to metadata so they're skipped
        if include_categories and self.priority not in include_categories:
            self.priority = PRIORITY_METADATA_ONLY
            self.initial_content_type = "metadata"

        if self.initial_content_type != "metadata":
            self._read_and_decode_content()

        if self.initial_content_type == "metadata" or self.full_content_text is None:
            self.tokens_full = 0
            if self.error_processing and "[Binary Content Preview" not in (
                self.full_content_text or ""
            ):
                self.summary_content_text = (
                    f"[Error processing: {self.error_processing}]"
                )
            elif self.full_content_text and "[Binary Content Preview" in self.full_content_text:
                self.summary_content_text = self.full_content_text
            else:
                self.summary_content_text = "[Metadata-only or empty file]"
            self.tokens_summary = count_tokens(self.summary_content_text or "")
            return

        self.tokens_full = count_tokens(self.full_content_text)

        if self.priority == PRIORITY_ESSENTIAL:
            self.summary_content_text = "[Essential file; full content preferred]"
            self.tokens_summary = self.tokens_full
        elif self.priority in (PRIORITY_IMPORTANT_CODE, PRIORITY_GENERAL_CODE):
            self.summary_content_text = self._generate_summary_for_code()
            self.tokens_summary = count_tokens(self.summary_content_text)
        elif self.priority in (PRIORITY_SUPPORTING_TEXT_CONFIG, PRIORITY_GENERAL_TEXT):
            self.summary_content_text = self._generate_summary_for_text()
            self.tokens_summary = count_tokens(self.summary_content_text)
        else:
            self.summary_content_text = "[Summary N/A]"
            self.tokens_summary = 0

    # ── summarizers ─────────────────────────────────────────────────────────

    def _generate_summary_for_code(self) -> str:
        if not self.full_content_text:
            return "[No content]"
        if self.relative_path.lower().endswith(".py"):
            try:
                tree = ast.parse(self.full_content_text)
                parts = [
                    f"[Python Code Summary: {os.path.basename(self.relative_path)}]"
                ]
                imports: set[str] = set()
                signatures: list[str] = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name:
                                imports.add(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split(".")[0])
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = (
                            ast.unparse(node.args)
                            if hasattr(ast, "unparse")
                            else "..."
                        )
                        sig = f"  def {node.name}({args}):"
                        if node.returns and hasattr(ast, "unparse"):
                            sig += f" -> {ast.unparse(node.returns)}"
                        signatures.append(sig)
                    elif isinstance(node, ast.ClassDef):
                        bases = (
                            [ast.unparse(b) for b in node.bases]
                            if hasattr(ast, "unparse")
                            else []
                        )
                        sig = (
                            f"  class {node.name}({', '.join(bases)})"
                            if bases
                            else f"  class {node.name}"
                        )
                        signatures.append(sig)
                if imports:
                    parts.append(f"  Imports: {', '.join(sorted(imports))}")
                parts.extend(signatures[:MAX_SIGNATURES_CODE_SUMMARY])
                if len(signatures) >= MAX_SIGNATURES_CODE_SUMMARY:
                    parts.append(
                        f"  … (truncated to {MAX_SIGNATURES_CODE_SUMMARY} signatures)"
                    )
                parts.append(f"  [Full content: {self.tokens_full} tokens]")
                return "\n".join(parts)
            except Exception:
                pass
        return self._generate_basic_code_summary()

    def _generate_basic_code_summary(self) -> str:
        if not self.full_content_text:
            return "[No content]"
        parts = [
            f"[Code Summary: {os.path.basename(self.relative_path)}]"
        ]
        pattern = (
            r"^\s*(?:(?:async\s+)?(?:public\s+|private\s+|protected\s+|static\s+)*"
            r"\b(?:class|interface|struct|enum|function|def|module|type|let|const|var)\b"
            r"\s+\w+.*?[:({])"
        )
        lines = self.full_content_text.splitlines()
        sigs: list[str] = []
        for ln, line in enumerate(lines):
            if len(sigs) >= MAX_SIGNATURES_CODE_SUMMARY:
                break
            if re.search(pattern, line, re.IGNORECASE):
                sigs.append(f"  L{ln+1}: {line.strip()}")
        if sigs:
            parts.extend(sigs)
        else:
            parts.append("  (No signatures; showing first lines)")
            parts.extend(
                f"  {l.strip()}"
                for l in lines[:MAX_LINES_CODE_SUMMARY_FALLBACK]
                if l.strip()
            )
        parts.append(f"  [Full content: {self.tokens_full} tokens]")
        return "\n".join(parts)

    def _generate_summary_for_text(self) -> str:
        if not self.full_content_text:
            return "[No content]"
        preview = self.full_content_text[:MAX_CHARS_TEXT_SUMMARY]
        parts = [
            f"[Text Preview: {os.path.basename(self.relative_path)}]",
            preview,
        ]
        if len(self.full_content_text) > MAX_CHARS_TEXT_SUMMARY:
            parts.append(f"  … [Full: {self.tokens_full} tokens]")
        return "\n".join(parts)

    def get_final_output_string(self) -> str:
        if self.chosen_output_type == "full":
            content = self.full_content_text or ""
            if self.error_processing and "Latin-1" in self.error_processing:
                content = f"[Note: {self.error_processing}]\n{content}"
            return content or "[Content unavailable]"
        elif self.chosen_output_type == "summary":
            return self.summary_content_text or "[Summary unavailable]"
        elif self.chosen_output_type == "metadata":
            return self.summary_content_text or "[Metadata]"
        elif self.chosen_output_type == "metadata_omitted_due_to_budget":
            return (
                f"[Content of {self.relative_path} omitted to meet token budget. "
                f"Original type: {self.initial_content_type}]"
            )
        return "[Invalid output type]"


# ─────────────────────────────────────────────────────────────────────────────
# File entry collectors
# ─────────────────────────────────────────────────────────────────────────────

def get_zip_file_entries(zip_filepath: str) -> List[FileEntry]:
    entries: List[FileEntry] = []
    try:
        with zipfile.ZipFile(zip_filepath, "r") as zf:
            for info in zf.infolist():
                name = info.filename
                if any(
                    part.lower() in {d.lower() for d in EXCLUDE_DIRS}
                    for part in name.split("/")
                ):
                    continue
                is_dir = name.endswith("/")
                size = info.file_size

                def _loader(zf_ref=zf, n=name) -> bytes:
                    return zf_ref.read(n)

                entries.append(FileEntry(name, size, _loader, is_dir_entry=is_dir))
    except zipfile.BadZipFile:
        pass
    return entries


def get_folder_file_entries(
    folder_path: str,
    respect_gitignore: bool = True,
) -> List[FileEntry]:
    entries: List[FileEntry] = []
    base = os.path.abspath(folder_path)
    spec = None

    if respect_gitignore and _pathspec_mod:
        gitignore_path = os.path.join(base, ".gitignore")
        if os.path.exists(gitignore_path):
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    with open(gitignore_path, encoding=enc) as f:
                        content = f.read()
                    spec = _pathspec_mod.PathSpec.from_lines("gitwildmatch", content.splitlines())
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

    exclude_basenames = {d.lower() for d in EXCLUDE_DIRS}

    for root, dirs, files in os.walk(base, topdown=True):
        rel_root = os.path.relpath(root, base).replace(os.sep, "/")
        if rel_root == ".":
            rel_root = ""

        dirs[:] = [
            d
            for d in sorted(dirs)
            if d.lower() not in exclude_basenames
            and not (
                spec
                and spec.match_file(
                    (rel_root + "/" + d if rel_root else d) + "/"
                )
            )
        ]

        for dname in dirs:
            dir_rel = (
                (rel_root + "/" + dname) if rel_root else dname
            ) + "/"
            entries.append(FileEntry(dir_rel, 0, lambda: b"", is_dir_entry=True))

        for fname in sorted(files):
            full_path = os.path.join(root, fname)
            rel_file = (
                (rel_root + "/" + fname) if rel_root else fname
            )
            if spec and spec.match_file(rel_file):
                continue
            try:
                fsize = os.path.getsize(full_path)
                entries.append(
                    FileEntry(
                        rel_file,
                        fsize,
                        lambda fp=full_path: open(fp, "rb").read(),
                    )
                )
            except OSError:
                pass

    return entries


# ─────────────────────────────────────────────────────────────────────────────
# Tree builder
# ─────────────────────────────────────────────────────────────────────────────

def build_structure_string(
    entries: List[FileEntry], root_name: str
) -> str:
    structure = _build_structure_map(entries)
    if not structure:
        return "(empty)\n"
    return _render_tree(structure, "")


def _build_structure_map(entries: List[FileEntry]) -> Dict[str, Any]:
    structure: Dict[str, Any] = {}
    for entry in entries:
        path = entry.relative_path
        parts = path.rstrip("/").split("/")
        current = structure
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            if not is_last or path.endswith("/"):
                current = current.setdefault(part + "/", {})
            else:
                current[part] = None
    return structure


def _render_tree(node: Dict[str, Any], prefix: str) -> str:
    lines: list[str] = []
    items = sorted(node.items())
    for i, (name, children) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{name}")
        if children is not None:
            ext = "    " if is_last else "│   "
            lines.append(_render_tree(children, prefix + ext))
    return "\n".join(filter(None, lines))


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ProcessingResult:
    output_path: str
    total_tokens: int
    token_budget: int
    files_full: int = 0
    files_summary: int = 0
    files_metadata: int = 0
    files_omitted: int = 0
    warnings: List[str] = field(default_factory=list)


def generate_context(
    input_path: str,
    output_filepath: str,
    token_budget: int = 800_000,
    include_categories: Optional[set] = None,
    respect_gitignore: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> ProcessingResult:
    """
    Main entry point.

    Args:
        input_path: folder or .zip file
        output_filepath: destination .txt file
        token_budget: max tokens
        include_categories: set of PRIORITY_* ints to include (None = all)
        respect_gitignore: whether to exclude .gitignore patterns
        progress_callback: called with (processed, total) for each file
    """
    if os.path.isdir(input_path):
        all_entries = get_folder_file_entries(
            input_path, respect_gitignore=respect_gitignore
        )
        display_name = os.path.basename(os.path.abspath(input_path))
    elif os.path.isfile(input_path) and input_path.lower().endswith(".zip"):
        all_entries = get_zip_file_entries(input_path)
        display_name = os.path.basename(input_path)
    else:
        raise ValueError(f"Unsupported input: {input_path}")

    if not all_entries:
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write("(No files found)\n")
        return ProcessingResult(output_filepath, 0, token_budget)

    total = len(all_entries)
    for i, entry in enumerate(all_entries):
        entry.categorize_and_summarize(include_categories=include_categories)
        if progress_callback:
            progress_callback(i + 1, total)

    structure_str = build_structure_string(all_entries, display_name)
    header = (
        f"Context for: {os.path.abspath(input_path)}\n"
        f"Generated by: codecontext\n"
        f"Directory structure:\n{structure_str}\n\n---\n\n"
    )
    current_tokens = count_tokens(header)

    content_entries = [e for e in all_entries if not e.is_dir_entry]
    for entry in content_entries:
        if entry.initial_content_type == "metadata":
            entry.chosen_output_type = "metadata"
            entry.tokens_for_chosen_output = entry.tokens_summary
        else:
            entry.chosen_output_type = "full"
            entry.tokens_for_chosen_output = entry.tokens_full
        wrapper = f"--- FILE: {entry.relative_path} ---\n\n"
        current_tokens += count_tokens(wrapper) + entry.tokens_for_chosen_output

    # ── Trim Pass 1: full → summary ────────────────────────────────────────
    if current_tokens > token_budget:
        trimmable = sorted(
            [
                e
                for e in content_entries
                if e.chosen_output_type == "full"
                and e.priority != PRIORITY_ESSENTIAL
                and e.summary_content_text
                and e.tokens_summary < e.tokens_full
            ],
            key=lambda e: (e.priority, -(e.tokens_full - e.tokens_summary)),
            reverse=True,
        )
        for e in trimmable:
            if current_tokens <= token_budget:
                break
            current_tokens -= e.tokens_full - e.tokens_summary
            e.chosen_output_type = "summary"
            e.tokens_for_chosen_output = e.tokens_summary

    # ── Trim Pass 2: full/summary → omitted ───────────────────────────────
    if current_tokens > token_budget:
        trimmable2 = sorted(
            [
                e
                for e in content_entries
                if e.chosen_output_type in ("full", "summary")
                and e.priority != PRIORITY_ESSENTIAL
            ],
            key=lambda e: (e.priority, -e.tokens_for_chosen_output),
            reverse=True,
        )
        for e in trimmable2:
            if current_tokens <= token_budget:
                break
            note = f"[Omitted to meet token budget: {e.relative_path}]"
            note_tokens = count_tokens(note)
            saving = e.tokens_for_chosen_output - note_tokens
            if saving > 0:
                current_tokens -= saving
                e.chosen_output_type = "metadata_omitted_due_to_budget"
                e.tokens_for_chosen_output = note_tokens

    content_entries.sort(key=lambda e: (e.priority, e.relative_path))

    # ── Write ──────────────────────────────────────────────────────────────
    result = ProcessingResult(
        output_path=output_filepath,
        total_tokens=0,
        token_budget=token_budget,
    )

    actual_tokens = count_tokens(header)
    with open(output_filepath, "w", encoding="utf-8") as out:
        out.write(header)
        for entry in content_entries:
            content = entry.get_final_output_string()
            file_header = (
                f"--- FILE_START: {entry.relative_path} "
                f"(size: {entry.size}B | prio: {entry.priority} | "
                f"decision: {entry.chosen_output_type}) ---\n"
            )
            file_footer = f"\n--- FILE_END: {entry.relative_path} ---\n\n"
            actual_tokens += (
                count_tokens(file_header)
                + count_tokens(content)
                + count_tokens(file_footer)
            )
            out.write(file_header)
            out.write(content)
            out.write(file_footer)

            if entry.chosen_output_type == "full":
                result.files_full += 1
            elif entry.chosen_output_type == "summary":
                result.files_summary += 1
            elif entry.chosen_output_type == "metadata":
                result.files_metadata += 1
            else:
                result.files_omitted += 1

        footer = (
            f"\n---\nProcessed by codecontext\n"
            f"Token budget : {token_budget:,}\n"
            f"Tokens used  : {actual_tokens:,}\n"
            f"Full         : {result.files_full}\n"
            f"Summary      : {result.files_summary}\n"
            f"Metadata     : {result.files_metadata}\n"
            f"Omitted      : {result.files_omitted}\n"
        )
        out.write(footer)
        actual_tokens += count_tokens(footer)

    if actual_tokens > token_budget * 1.05:
        result.warnings.append(
            f"Token budget exceeded by {actual_tokens - token_budget:,} tokens."
        )

    result.total_tokens = actual_tokens
    return result