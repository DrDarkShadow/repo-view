"""
DEPRECATED: This module is kept for backward compatibility.
All functionality has been moved to repoview.core submodules.

Use:
    from repoview.core import FileEntry, generate_context, GenerateResult, etc.
"""

# Re-export everything from new modular structure
from repoview.core.collectors import collect_folder, collect_zip
from repoview.core.file_entry import FileEntry
from repoview.core.processor import GenerateResult, generate_context
from repoview.core.token_counter import count_tokens
from repoview.core.tree_builder import build_tree

__all__ = [
    "FileEntry",
    "collect_folder",
    "collect_zip",
    "generate_context",
    "GenerateResult",
    "count_tokens",
    "build_tree",
]
