"""
cache.py — stores per-project run metadata in ~/.repoview/cache/

Cache lives at:
    ~/.repoview/cache/<project_hash>.json

Where <project_hash> is a short SHA1 of the absolute project path,
so each project gets its own cache file without polluting the project folder.

Schema:
{
    "version":      1,
    "project_path": "/abs/path/to/project",
    "generated_at": "2025-03-16T14:32:11",
    "output_path":  "/abs/path/to/output.txt",
    "settings": {
        "skip_docs":          true,
        "skip_tests":         false,
        "respect_gitignore":  true
    },
    "files": {
        "src/auth.ts": {
            "mtime":    1710598331.4,
            "hash":     "a3f9c2...",       # sha1 of file content (first 64KB)
            "decision": "full",            # full | summary | metadata | omitted
            "tokens":   847
        },
        ...
    }
}
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

CACHE_SCHEMA_VERSION = 1


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FileCacheEntry:
    mtime:    float
    hash:     str
    decision: str   # full | summary | metadata | omitted | skipped
    tokens:   int


@dataclass
class ProjectCache:
    version:      int
    project_path: str
    generated_at: str            # ISO format
    output_path:  str
    settings:     Dict           # skip_docs, skip_tests, respect_gitignore
    files:        Dict[str, FileCacheEntry] = field(default_factory=dict)

    def age_human(self) -> str:
        """Return human-readable age like '2 hours ago' or '3 days ago'."""
        try:
            then = datetime.fromisoformat(self.generated_at)
            delta = datetime.now() - then
            s = int(delta.total_seconds())
            if s < 60:
                return f"{s}s ago"
            elif s < 3600:
                return f"{s // 60}m ago"
            elif s < 86400:
                return f"{s // 3600}h ago"
            else:
                return f"{s // 86400}d ago"
        except Exception:
            return "previously"


# ─────────────────────────────────────────────────────────────────────────────
# Cache path helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cache_dir() -> Path:
    """~/.repoview/cache/  — created on first use."""
    try:
        path = Path.home() / ".repoview" / "cache"
        path.mkdir(parents=True, exist_ok=True)
        return path
    except (OSError, PermissionError) as e:
        # Fallback to temp directory if home directory is not accessible
        import tempfile
        fallback_path = Path(tempfile.gettempdir()) / ".repoview" / "cache"
        fallback_path.mkdir(parents=True, exist_ok=True)
        return fallback_path


def _project_id(project_path: str) -> str:
    """Short SHA1 of the normalised absolute project path."""
    try:
        norm = os.path.normcase(os.path.abspath(project_path))
        return hashlib.sha1(norm.encode()).hexdigest()[:16]
    except (OSError, UnicodeEncodeError) as e:
        # Fallback for paths with special characters or encoding issues
        import uuid
        return str(uuid.uuid4()).replace("-", "")[:16]


def cache_path_for(project_path: str) -> Path:
    return _cache_dir() / f"{_project_id(project_path)}.json"


# ─────────────────────────────────────────────────────────────────────────────
# File hashing
# ─────────────────────────────────────────────────────────────────────────────

def _hash_file(full_path: str, limit: int = 65536) -> str:
    """SHA1 of the first `limit` bytes of a file. Fast enough for watch mode."""
    h = hashlib.sha1()
    try:
        with open(full_path, "rb") as f:
            h.update(f.read(limit))
    except OSError:
        return ""
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Load / Save
# ─────────────────────────────────────────────────────────────────────────────

def load_cache(project_path: str) -> Optional[ProjectCache]:
    """Return ProjectCache if one exists, else None."""
    path = cache_path_for(project_path)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if raw.get("version") != CACHE_SCHEMA_VERSION:
            return None   # stale schema — treat as no cache
        files = {
            rel: FileCacheEntry(**entry)
            for rel, entry in raw.get("files", {}).items()
        }
        return ProjectCache(
            version=raw["version"],
            project_path=raw["project_path"],
            generated_at=raw["generated_at"],
            output_path=raw["output_path"],
            settings=raw.get("settings", {}),
            files=files,
        )
    except Exception:
        return None   # corrupt cache — treat as no cache


def save_cache(cache: ProjectCache) -> None:
    """Write ProjectCache to disk atomically."""
    path = cache_path_for(cache.project_path)
    raw = {
        "version":      cache.version,
        "project_path": cache.project_path,
        "generated_at": cache.generated_at,
        "output_path":  cache.output_path,
        "settings":     cache.settings,
        "files": {
            rel: {
                "mtime":    e.mtime,
                "hash":     e.hash,
                "decision": e.decision,
                "tokens":   e.tokens,
            }
            for rel, e in cache.files.items()
        },
    }
    # Atomic write via temp file
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
        tmp.replace(path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def delete_cache(project_path: str) -> None:
    try:
        cache_path_for(project_path).unlink(missing_ok=True)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Build a fresh cache from a completed generate run
# ─────────────────────────────────────────────────────────────────────────────

def build_cache(
    project_path: str,
    output_path: str,
    settings: dict,
    file_entries,           # List[FileEntry] from core.py
) -> ProjectCache:
    """
    Called after generate_context() finishes.
    Walks actual files on disk to record mtime + hash.
    """
    base = os.path.abspath(project_path)
    files: Dict[str, FileCacheEntry] = {}

    for entry in file_entries:
        if entry.is_dir:
            continue
        full_path = os.path.join(base, entry.relative_path)
        try:
            mtime = os.path.getmtime(full_path)
        except OSError:
            mtime = 0.0

        files[entry.relative_path] = FileCacheEntry(
            mtime=mtime,
            hash=_hash_file(full_path),
            decision=entry.chosen,
            tokens=entry.tokens_chosen,
        )

    return ProjectCache(
        version=CACHE_SCHEMA_VERSION,
        project_path=os.path.abspath(project_path),
        generated_at=datetime.now().isoformat(timespec="seconds"),
        output_path=os.path.abspath(output_path),
        settings=settings,
        files=files,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Diff  — compare cache against current disk state
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DiffResult:
    modified:  list[str] = field(default_factory=list)   # content changed
    added:     list[str] = field(default_factory=list)   # new file
    deleted:   list[str] = field(default_factory=list)   # gone from disk
    unchanged: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.modified or self.added or self.deleted)

    @property
    def total_changes(self) -> int:
        return len(self.modified) + len(self.added) + len(self.deleted)


def diff_cache(
    cache: ProjectCache,
    current_file_entries,       # List[FileEntry] — fresh scan of project
) -> DiffResult:
    """
    Compare a loaded ProjectCache against the current file entries on disk.
    Returns a DiffResult describing what changed.
    """
    base = os.path.abspath(cache.project_path)
    result = DiffResult()

    current_paths = {
        e.relative_path for e in current_file_entries if not e.is_dir
    }
    cached_paths  = set(cache.files.keys())

    # Deleted — in cache but not on disk anymore
    for rel in cached_paths - current_paths:
        result.deleted.append(rel)

    # Added — on disk but not in cache
    for rel in current_paths - cached_paths:
        result.added.append(rel)

    # Modified or unchanged — in both
    for rel in current_paths & cached_paths:
        full_path = os.path.join(base, rel)
        cached = cache.files[rel]

        try:
            mtime = os.path.getmtime(full_path)
        except OSError:
            result.modified.append(rel)
            continue

        # Fast path: mtime unchanged → skip hash
        if abs(mtime - cached.mtime) < 0.01:
            result.unchanged.append(rel)
            continue

        # mtime changed — verify with hash
        new_hash = _hash_file(full_path)
        if new_hash != cached.hash:
            result.modified.append(rel)
        else:
            result.unchanged.append(rel)   # touched but content same

    # Sort for deterministic display
    result.modified.sort()
    result.added.sort()
    result.deleted.sort()
    result.unchanged.sort()

    return result