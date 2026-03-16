"""
watcher.py — file system watcher for --watch mode.

Uses watchdog for cross-platform FS events.
Debounces rapid saves (e.g. git checkout, npm install) by 2 seconds.
On each stable batch of changes, runs incremental_update automatically.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Set

try:
    from watchdog.observers import Observer
    from watchdog.events import (
        FileSystemEventHandler,
        FileSystemEvent,
        FileCreatedEvent,
        FileModifiedEvent,
        FileDeletedEvent,
        FileMovedEvent,
    )
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from repoview.config import EXCLUDE_DIRS, WATCH_DEBOUNCE_SECONDS, METADATA_ONLY_EXTS


# ─────────────────────────────────────────────────────────────────────────────
# Change event
# ─────────────────────────────────────────────────────────────────────────────

class ChangeSet:
    """Thread-safe set of changed relative paths + debounce timer."""

    def __init__(
        self,
        base: str,
        debounce: float,
        on_stable: Callable[[List[str]], None],
    ):
        self._base     = os.path.abspath(base)
        self._debounce = debounce
        self._callback = on_stable
        self._lock     = threading.Lock()
        self._paths:    Set[str] = set()
        self._timer:    Optional[threading.Timer] = None

    def push(self, full_path: str) -> None:
        rel = os.path.relpath(full_path, self._base).replace(os.sep, "/")

        # Ignore excluded dirs
        parts = rel.split("/")
        if any(p.lower() in {d.lower() for d in EXCLUDE_DIRS} for p in parts):
            return

        # Ignore output file and cache
        ext = os.path.splitext(full_path)[1].lower()
        if ext in METADATA_ONLY_EXTS:
            return
        if full_path.endswith("-context.txt"):
            return

        with self._lock:
            self._paths.add(rel)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            paths = sorted(self._paths)
            self._paths.clear()
            self._timer = None
        if paths:
            self._callback(paths)

    def cancel(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None


# ─────────────────────────────────────────────────────────────────────────────
# Watchdog event handler
# ─────────────────────────────────────────────────────────────────────────────

if WATCHDOG_AVAILABLE:
    class _Handler(FileSystemEventHandler):
        def __init__(self, change_set: ChangeSet):
            self._cs = change_set

        def on_modified(self, event: FileSystemEvent):
            if not event.is_directory:
                self._cs.push(event.src_path)

        def on_created(self, event: FileSystemEvent):
            if not event.is_directory:
                self._cs.push(event.src_path)

        def on_deleted(self, event: FileSystemEvent):
            if not event.is_directory:
                self._cs.push(event.src_path)

        def on_moved(self, event: FileSystemEvent):
            if not event.is_directory:
                self._cs.push(event.dest_path)
                self._cs.push(event.src_path)
else:
    _Handler = None  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# Public watch function
# ─────────────────────────────────────────────────────────────────────────────

def watch(
    project_path: str,
    on_change: Callable[[List[str]], None],
    debounce: float = WATCH_DEBOUNCE_SECONDS,
) -> None:
    """
    Start watching `project_path` for file changes.
    Calls `on_change(changed_paths)` after each debounced batch.
    Blocks until KeyboardInterrupt.

    Raises ImportError if watchdog is not installed.
    """
    if not WATCHDOG_AVAILABLE:
        raise ImportError(
            "watchdog is required for --watch mode.\n"
            "Install it with:  pip install watchdog"
        )

    cs = ChangeSet(project_path, debounce, on_change)
    handler  = _Handler(cs)
    observer = Observer()
    observer.schedule(handler, path=project_path, recursive=True)
    observer.start()

    try:
        while observer.is_alive():
            observer.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        cs.cancel()
        observer.stop()
        observer.join()