"""
DEPRECATED: This module is kept for backward compatibility.
All CLI functionality has been moved to repoview.cli submodules.

The main app is now in repoview.cli.main
"""

# Re-export the main app for backward compatibility
from repoview.cli.main import app

__all__ = ["app"]
