"""File collection utilities for folders and ZIP files."""

import os
import zipfile
from typing import List

try:
    import pathspec as _pathspec_mod
except ImportError:
    _pathspec_mod = None

from repoview.config import EXCLUDE_DIRS
from repoview.core.file_entry import FileEntry


def collect_folder(
    folder: str,
    respect_gitignore: bool = True,
) -> List[FileEntry]:
    """Collect all files from a folder, respecting .gitignore if requested."""
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
    """Collect all files from a ZIP archive."""
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
