"""
scanner.py — fast pre-scan of a project folder.
Returns stats used to drive conditional questions in the wizard.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import pathspec as _pathspec_mod
except ImportError:
    _pathspec_mod = None

from repoview.config import (
    DOC_EXTS,
    EXCLUDE_DIRS,
    METADATA_ONLY_EXTS,
    TEST_DIR_NAMES,
    TEST_FILENAME_PATTERNS,
)


@dataclass
class ScanResult:
    total_files: int = 0
    total_size_bytes: int = 0
    has_gitignore: bool = False
    gitignore_rules: int = 0
    has_test_files: bool = False
    test_file_count: int = 0
    doc_file_count: int = 0
    ext_counter: Counter = field(default_factory=Counter)
    top_extensions: List[tuple] = field(default_factory=list)   # [(ext, count), …]
    gitignore_path: Optional[str] = None

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    @property
    def est_tokens(self) -> int:
        # ~1 token per 4 chars; avg code file ~40% of raw bytes is text
        return int(self.total_size_bytes * 0.4 / 4)


_TEST_RE = [re.compile(p, re.IGNORECASE) for p in TEST_FILENAME_PATTERNS]


def _is_test_file(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    # test directory
    for part in parts[:-1]:
        if part.lower() in TEST_DIR_NAMES:
            return True
    # filename pattern
    filename = parts[-1]
    return any(rx.search(filename) for rx in _TEST_RE)


def scan_project(folder_path: str) -> ScanResult:
    result = ScanResult()
    base = os.path.abspath(folder_path)
    exclude_lower = {d.lower() for d in EXCLUDE_DIRS}

    # Check for .gitignore
    gi_path = os.path.join(base, ".gitignore")
    if os.path.exists(gi_path):
        result.has_gitignore = True
        result.gitignore_path = gi_path
        try:
            with open(gi_path, encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            result.gitignore_rules = len(lines)
        except OSError:
            pass

    for root, dirs, files in os.walk(base, topdown=True):
        dirs[:] = [
            d for d in dirs
            if d.lower() not in exclude_lower
        ]

        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            ext = os.path.splitext(fname)[1].lower()

            if ext in METADATA_ONLY_EXTS:
                continue

            try:
                size = os.path.getsize(full)
            except OSError:
                continue

            result.total_files += 1
            result.total_size_bytes += size
            result.ext_counter[ext] += 1

            if ext in DOC_EXTS:
                result.doc_file_count += 1

            if _is_test_file(rel):
                result.has_test_files = True
                result.test_file_count += 1

    result.top_extensions = result.ext_counter.most_common(6)
    return result