"""
differ.py — incremental update of an existing context .txt file.

Instead of regenerating the whole file, we:
  1. Parse the existing output into named blocks
  2. Reprocess only changed / new files
  3. Splice updated blocks back in
  4. Remove blocks for deleted files
  5. Rewrite the header tree and footer token count

Block format (written by core.py):
    ── FILE: src/auth.ts [847B | prio:2 | full] ──
    ...content...
    ── END: src/auth.ts ──
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from repoview.cache import (
    DiffResult,
    FileCacheEntry,
    ProjectCache,
    _hash_file,
    build_cache,
    save_cache,
)
from repoview.core import (
    FileEntry,
    build_tree,
    collect_folder,
    count_tokens,
    GenerateResult,
)
from repoview.config import TOKEN_BUDGET


# ─────────────────────────────────────────────────────────────────────────────
# Block parsing
# ─────────────────────────────────────────────────────────────────────────────

# Matches:  ── FILE: some/path.ts [847B | prio:2 | full] ──
_FILE_START_RE = re.compile(
    r"^── FILE: (.+?) \[.*?\] ──$"
)
# Matches:  ── END: some/path.ts ──
_FILE_END_RE = re.compile(
    r"^── END: (.+?) ──$"
)


@dataclass
class _Block:
    """Represents one FILE…END block inside the context file."""
    rel_path:    str
    start_line:  int    # index of FILE: line
    end_line:    int    # index of END: line (inclusive)
    raw_header:  str    # the FILE: header line (we'll rewrite it)


def _parse_blocks(lines: List[str]) -> Dict[str, _Block]:
    """Return {rel_path: _Block} for every FILE…END section."""
    blocks: Dict[str, _Block] = {}
    open_block: Optional[Tuple[str, int, str]] = None  # (rel_path, start_line, header)

    for i, line in enumerate(lines):
        m_start = _FILE_START_RE.match(line.rstrip("\n"))
        if m_start and open_block is None:
            open_block = (m_start.group(1), i, line.rstrip("\n"))
            continue

        m_end = _FILE_END_RE.match(line.rstrip("\n"))
        if m_end and open_block is not None:
            rel, start, hdr = open_block
            if m_end.group(1) == rel:
                blocks[rel] = _Block(rel, start, i, hdr)
                open_block = None

    return blocks


# ─────────────────────────────────────────────────────────────────────────────
# Incremental update
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class UpdateResult:
    output_path:   str
    total_tokens:  int
    files_updated: int = 0
    files_added:   int = 0
    files_removed: int = 0
    elapsed:       float = 0.0
    warnings:      List[str] = field(default_factory=list)


def incremental_update(
    project_path:      str,
    cache:             ProjectCache,
    diff:              DiffResult,
    all_entries:       List[FileEntry],   # fresh full scan, already processed
    progress_cb=None,
) -> UpdateResult:
    """
    Perform an incremental update on the existing context file.

    Strategy
    --------
    * Modified files → reprocess + replace their block
    * Added files    → process + insert at correct priority position
    * Deleted files  → remove their block
    * Unchanged      → keep as-is (not re-read from disk)

    Returns UpdateResult with new token count.
    """
    start = time.time()
    output_path = cache.output_path

    # ── Read existing file ────────────────────────────────────────────────────
    try:
        with open(output_path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        raise RuntimeError(
            f"Cannot read existing context file: {output_path}\n{e}"
        )

    blocks = _parse_blocks(lines)

    # ── Build a map of rel_path → FileEntry for quick lookup ─────────────────
    entry_map: Dict[str, FileEntry] = {
        e.relative_path: e
        for e in all_entries
        if not e.is_dir
    }

    total = len(diff.modified) + len(diff.added) + len(diff.deleted)
    done = 0

    # ── Process modified files ────────────────────────────────────────────────
    result = UpdateResult(output_path=output_path, total_tokens=0)

    for rel in diff.modified:
        entry = entry_map.get(rel)
        if entry is None:
            continue
        # entry.process() was already called in the caller with skip settings
        _replace_block(lines, blocks, entry)
        result.files_updated += 1
        done += 1
        if progress_cb:
            progress_cb(done, total)

    # ── Process deleted files ─────────────────────────────────────────────────
    for rel in diff.deleted:
        _remove_block(lines, blocks, rel)
        result.files_removed += 1
        done += 1
        if progress_cb:
            progress_cb(done, total)

    # ── Process added files ───────────────────────────────────────────────────
    for rel in diff.added:
        entry = entry_map.get(rel)
        if entry is None:
            continue
        _insert_block(lines, blocks, entry, all_entries)
        result.files_added += 1
        done += 1
        if progress_cb:
            progress_cb(done, total)

    # ── Rewrite header tree ───────────────────────────────────────────────────
    _rewrite_header_tree(lines, all_entries, project_path)

    # ── Rewrite footer token count ────────────────────────────────────────────
    full_text = "".join(lines)
    actual_tokens = count_tokens(full_text)
    _rewrite_footer(lines, actual_tokens)

    # ── Write back ────────────────────────────────────────────────────────────
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # ── Update cache ──────────────────────────────────────────────────────────
    new_cache = build_cache(
        project_path=project_path,
        output_path=output_path,
        settings=cache.settings,
        file_entries=all_entries,
    )
    save_cache(new_cache)

    result.total_tokens = actual_tokens
    result.elapsed = time.time() - start

    if actual_tokens > TOKEN_BUDGET * 1.05:
        result.warnings.append(
            f"Exceeded budget by {actual_tokens - TOKEN_BUDGET:,} tokens."
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Block manipulation helpers  (operate on the `lines` list in-place)
# ─────────────────────────────────────────────────────────────────────────────

def _make_block_lines(entry: FileEntry) -> List[str]:
    """Build the FILE…END lines for an entry."""
    header = (
        f"── FILE: {entry.relative_path} "
        f"[{entry.size}B | prio:{entry.priority} | {entry.chosen}] ──\n"
    )
    body   = entry.final_content()
    footer = f"\n── END: {entry.relative_path} ──\n\n"
    return [header, body, footer]


def _replace_block(
    lines:   List[str],
    blocks:  Dict[str, _Block],
    entry:   FileEntry,
) -> None:
    """Replace an existing block with freshly processed content."""
    block = blocks.get(entry.relative_path)
    if block is None:
        # Not found in file — treat as insert
        _insert_block(lines, blocks, entry, [])
        return

    new_lines = _make_block_lines(entry)
    lines[block.start_line : block.end_line + 1] = new_lines

    # Update block map offsets (everything after shifts)
    shift = len(new_lines) - (block.end_line - block.start_line + 1)
    blocks[entry.relative_path] = _Block(
        entry.relative_path,
        block.start_line,
        block.start_line + len(new_lines) - 1,
        new_lines[0].rstrip("\n"),
    )
    _shift_blocks(blocks, after=block.start_line, amount=shift,
                  exclude=entry.relative_path)


def _remove_block(
    lines:   List[str],
    blocks:  Dict[str, _Block],
    rel:     str,
) -> None:
    """Delete the block for a removed file."""
    block = blocks.get(rel)
    if block is None:
        return
    count = block.end_line - block.start_line + 1
    del lines[block.start_line : block.end_line + 1]
    _shift_blocks(blocks, after=block.start_line, amount=-count, exclude=rel)
    del blocks[rel]


def _insert_block(
    lines:       List[str],
    blocks:      Dict[str, _Block],
    entry:       FileEntry,
    all_entries: List[FileEntry],
) -> None:
    """
    Insert a new block in the correct priority order.
    We find the last block whose priority <= entry.priority and insert after it.
    Falls back to inserting before the footer.
    """
    new_lines = _make_block_lines(entry)

    # Build priority map for existing blocks
    prio_by_rel: Dict[str, int] = {}
    for e in all_entries:
        if not e.is_dir:
            prio_by_rel[e.relative_path] = e.priority

    # Find insertion point — after the last block with same or lower priority
    insert_after_line: Optional[int] = None
    for rel, block in sorted(blocks.items(),
                              key=lambda x: (prio_by_rel.get(x[0], 99), x[1].start_line)):
        if prio_by_rel.get(rel, 99) <= entry.priority:
            insert_after_line = block.end_line + 1

    if insert_after_line is None:
        # Insert before the footer (last 5 lines)
        insert_after_line = max(0, len(lines) - 5)

    lines[insert_after_line:insert_after_line] = new_lines

    new_block = _Block(
        entry.relative_path,
        insert_after_line,
        insert_after_line + len(new_lines) - 1,
        new_lines[0].rstrip("\n"),
    )
    blocks[entry.relative_path] = new_block
    _shift_blocks(blocks, after=insert_after_line,
                  amount=len(new_lines), exclude=entry.relative_path)


def _shift_blocks(
    blocks:  Dict[str, _Block],
    after:   int,
    amount:  int,
    exclude: str = "",
) -> None:
    """Shift all block line numbers that start after `after` by `amount`."""
    for rel, block in blocks.items():
        if rel == exclude:
            continue
        if block.start_line > after:
            blocks[rel] = _Block(
                rel,
                block.start_line + amount,
                block.end_line + amount,
                block.raw_header,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Header / footer rewrite
# ─────────────────────────────────────────────────────────────────────────────

_TREE_START = "Directory structure:\n"
_TREE_END   = "\n" + "─" * 60 + "\n"

def _rewrite_header_tree(
    lines:       List[str],
    all_entries: List[FileEntry],
    project_path: str,
) -> None:
    """Rebuild the directory tree section at the top of the file."""
    full = "".join(lines)
    tree_start = full.find(_TREE_START)
    tree_end   = full.find(_TREE_END)
    if tree_start == -1 or tree_end == -1:
        return

    new_tree = _TREE_START + build_tree(all_entries) + _TREE_END
    new_full = full[: tree_start] + new_tree + full[tree_end + len(_TREE_END):]

    lines.clear()
    lines.extend(new_full.splitlines(keepends=True))


_FOOTER_TOKEN_RE = re.compile(r"(repoview \| tokens used: )([\d,]+)( / [\d,]+)")

def _rewrite_footer(lines: List[str], actual_tokens: int) -> None:
    """Update the token count line in the footer."""
    for i in range(len(lines) - 1, max(len(lines) - 10, -1), -1):
        m = _FOOTER_TOKEN_RE.search(lines[i])
        if m:
            lines[i] = _FOOTER_TOKEN_RE.sub(
                lambda _: f"{m.group(1)}{actual_tokens:,}{m.group(3)}",
                lines[i],
            )
            break