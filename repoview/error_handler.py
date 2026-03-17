"""Centralized error handling for repoview."""

import functools
import sys
import traceback
from typing import Any, Callable, Optional, Type

from rich.console import Console

console = Console()


class RepoviewError(Exception):
    """Base exception for repoview-specific errors."""
    
    def __init__(self, message: str, suggestion: Optional[str] = None):
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)


class FileAccessError(RepoviewError):
    """Error accessing files or directories."""
    pass


class GitIgnoreError(RepoviewError):
    """Error processing .gitignore file."""
    pass


class TokenCountError(RepoviewError):
    """Error counting tokens."""
    pass


class CacheError(RepoviewError):
    """Error with cache operations."""
    pass


class WatchError(RepoviewError):
    """Error with watch mode."""
    pass


class GitHubError(RepoviewError):
    """Error with GitHub operations."""
    pass


def handle_error(error: Exception, context: str = "") -> None:
    """Display user-friendly error message and exit."""
    
    # Known repoview errors - show clean message
    if isinstance(error, RepoviewError):
        console.print(f"\n[red]✗ Error:[/red] {error.message}")
        if error.suggestion:
            console.print(f"[dim]💡 Suggestion: {error.suggestion}[/dim]")
        console.print()
        sys.exit(1)
    
    # Common system errors - provide helpful messages
    elif isinstance(error, PermissionError):
        console.print(f"\n[red]✗ Permission Error:[/red] Cannot access file or directory")
        console.print(f"[dim]💡 Try running with appropriate permissions or check file ownership[/dim]")
        if context:
            console.print(f"[dim]Context: {context}[/dim]")
        console.print()
        sys.exit(1)
    
    elif isinstance(error, FileNotFoundError):
        console.print(f"\n[red]✗ File Not Found:[/red] {error}")
        console.print(f"[dim]💡 Check that the path exists and is accessible[/dim]")
        console.print()
        sys.exit(1)
    
    elif isinstance(error, UnicodeDecodeError):
        console.print(f"\n[red]✗ Encoding Error:[/red] Cannot read file with special characters")
        console.print(f"[dim]💡 The file may be binary or use an unsupported encoding[/dim]")
        console.print()
        sys.exit(1)
    
    elif isinstance(error, KeyboardInterrupt):
        console.print(f"\n[yellow]Cancelled by user.[/yellow]")
        sys.exit(0)
    
    elif isinstance(error, ImportError):
        missing_module = str(error).split("'")[1] if "'" in str(error) else "unknown"
        console.print(f"\n[red]✗ Missing Dependency:[/red] {missing_module}")
        console.print(f"[dim]💡 Install it with: pip install {missing_module}[/dim]")
        console.print()
        sys.exit(1)
    
    # Unknown errors - show minimal info in production
    else:
        console.print(f"\n[red]✗ Unexpected Error:[/red] {type(error).__name__}")
        console.print(f"[dim]{str(error)}[/dim]")
        
        # Show full traceback only if debug mode is enabled
        if _is_debug_mode():
            console.print(f"\n[dim]Full traceback:[/dim]")
            console.print(traceback.format_exc())
        else:
            console.print(f"[dim]💡 Run with REPOVIEW_DEBUG=1 for full error details[/dim]")
        
        if context:
            console.print(f"[dim]Context: {context}[/dim]")
        console.print()
        sys.exit(1)


def _is_debug_mode() -> bool:
    """Check if debug mode is enabled via environment variable."""
    import os
    return os.getenv("REPOVIEW_DEBUG", "").lower() in ("1", "true", "yes")


def safe_execute(func: Callable, context: str = "", *args, **kwargs) -> Any:
    """Execute function with error handling."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handle_error(e, context)


def error_handler(context: str = ""):
    """Decorator to add error handling to functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handle_error(e, context or f"in {func.__name__}")
        return wrapper
    return decorator


def cli_error_handler(func: Callable) -> Callable:
    """Decorator specifically for CLI entry points."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            handle_error(e, f"CLI command: {func.__name__}")
    return wrapper


# Utility functions for raising specific errors
def raise_file_error(path: str, operation: str = "access") -> None:
    """Raise a FileAccessError with helpful message."""
    raise FileAccessError(
        f"Cannot {operation} file: {path}",
        "Check that the file exists and you have the necessary permissions"
    )


def raise_cache_error(operation: str, details: str = "") -> None:
    """Raise a CacheError with helpful message."""
    suggestion = "Try running with --reset to clear the cache"
    if details:
        message = f"Cache {operation} failed: {details}"
    else:
        message = f"Cache {operation} failed"
    raise CacheError(message, suggestion)


def raise_watch_error(details: str) -> None:
    """Raise a WatchError with helpful message."""
    raise WatchError(
        f"Watch mode failed: {details}",
        "Make sure watchdog is installed: pip install watchdog"
    )


def raise_github_error(details: str) -> None:
    """Raise a GitHubError with helpful message."""
    raise GitHubError(
        f"GitHub operation failed: {details}",
        "Check your internet connection and that the repository exists"
    )