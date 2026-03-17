"""FileEntry class for representing files in the project."""

import os
import re
from typing import Callable, Optional

from repoview.config import (
    DOC_EXTS,
    ESSENTIAL_FILENAMES,
    GENERAL_CODE_EXTS,
    IMPORTANT_CODE_EXTS,
    MAX_FILE_SIZE_BYTES,
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
)
from repoview.core.token_counter import count_tokens
from repoview.core.summarizers import code_summary, text_preview


# Test file detection
_TEST_RE = [re.compile(p, re.IGNORECASE) for p in TEST_FILENAME_PATTERNS]


def _is_test_file(rel_path: str) -> bool:
    """Check if a file is a test file based on path patterns."""
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts[:-1]:
        if part.lower() in TEST_DIR_NAMES:
            return True
    return any(rx.search(parts[-1]) for rx in _TEST_RE)


class FileEntry:
    """Represents a file in the project with classification and content."""
    
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
        self.chosen: str = "full"
        self.tokens_chosen: int = 0

    def _read(self) -> None:
        """Read file content from disk."""
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

    def process(
        self,
        skip_docs: bool = False,
        skip_tests: bool = False,
        focus_path: str = "",
    ) -> None:
        """Classify and process the file."""
        if self.is_dir:
            self.initial_content_type = "metadata"
            self.priority = PRIORITY_METADATA_ONLY
            return

        ext = os.path.splitext(self.relative_path)[1].lower()
        basename = os.path.basename(self.relative_path).lower()

        # Focus mode handling
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
            if inside_focus and ext not in METADATA_ONLY_EXTS and self.size > 0:
                self.priority = PRIORITY_FOCUS
                self.initial_content_type = "full"
                self._read()
                if self.full_text is not None:
                    self.tokens_full = count_tokens(self.full_text)
                    self.summary_text = (
                        code_summary(self.full_text, self.relative_path, self.tokens_full)
                        if ext in IMPORTANT_CODE_EXTS
                        else text_preview(self.full_text, self.relative_path, self.tokens_full)
                    )
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
            self.summary_text = code_summary(self.full_text, self.relative_path, self.tokens_full)
            self.tokens_summary = count_tokens(self.summary_text)
        else:
            self.summary_text = text_preview(self.full_text, self.relative_path, self.tokens_full)
            self.tokens_summary = count_tokens(self.summary_text)

    def final_content(self) -> str:
        """Get the final content based on chosen decision."""
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
