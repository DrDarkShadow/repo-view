"""UI helpers for CLI - banners, displays, menus, copy functions."""

import os
import platform
import subprocess
import time
from typing import Optional

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from repoview import __version__
from repoview.config import TOKEN_BUDGET
from repoview.core import GenerateResult
from repoview.differ import UpdateResult
from repoview.scanner import ScanResult

console = Console()

CC_STYLE = Style([
    ("qmark", "fg:#7c3aed bold"),
    ("question", "bold"),
    ("answer", "fg:#7c3aed bold"),
    ("pointer", "fg:#7c3aed bold"),
    ("highlighted", "fg:#7c3aed bold"),
    ("selected", "fg:#06b6d4"),
    ("instruction", "fg:#666666"),
    ("text", ""),
    ("disabled", "fg:#444444 italic"),
])


def banner() -> None:
    """Display the repoview banner."""
    console.print()
    console.print(Panel.fit(
        Text.from_markup(
            f"[bold #7c3aed]repoview[/]  [dim]v{__version__}[/]\n"
            "[dim]Turn any codebase into LLM-ready context[/]"
        ),
        border_style="#7c3aed",
        padding=(0, 2),
    ))
    console.print()


def show_scan(scan: ScanResult, folder_name: str) -> None:
    """Display scan results."""
    console.print(f"  [dim]Scanning[/dim] [bold]{folder_name}[/bold][dim]…[/dim]")
    time.sleep(0.1)

    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=16)
    table.add_column()

    table.add_row("Files found", f"[bold]{scan.total_files}[/bold]")
    table.add_row("Total size", f"[bold]{scan.total_size_mb:.1f} MB[/bold]")
    table.add_row("Est. tokens", f"[bold]~{scan.est_tokens:,}[/bold]")

    if scan.top_extensions:
        ext_str = "  ".join(
            f"[cyan]{ext or '(none)'}[/cyan] [dim]{count}[/dim]"
            for ext, count in scan.top_extensions[:5]
        )
        table.add_row("Top types", ext_str)

    if scan.has_gitignore:
        table.add_row(
            ".gitignore",
            f"[green]found[/green] [dim]({scan.gitignore_rules} rules)[/dim]"
        )
    else:
        table.add_row(".gitignore", "[dim]not found[/dim]")

    if scan.has_test_files:
        table.add_row("Test files", f"[dim]{scan.test_file_count} detected[/dim]")

    console.print(Panel(table, border_style="dim", padding=(0, 1)))
    console.print()


def print_update_result(upd: UpdateResult, elapsed: float) -> None:
    """Display incremental update results."""
    console.print(f"[bold green]✔[/bold green] Updated in [bold]{elapsed:.1f}s[/bold]\n")

    pct = upd.total_tokens / TOKEN_BUDGET * 100
    bar_len = 24
    filled = int(bar_len * min(pct, 100) / 100)
    color = "green" if pct < 75 else "yellow" if pct < 95 else "red"
    bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * (bar_len - filled)}[/dim]"

    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=14)
    table.add_column()
    table.add_row("Output", f"[bold cyan]{upd.output_path}[/bold cyan]")
    table.add_row("Tokens", f"{bar}  [bold]{upd.total_tokens:,}[/bold] / {TOKEN_BUDGET:,}")
    table.add_row("Updated", f"[yellow]{upd.files_updated}[/yellow] file(s)")
    table.add_row("Added", f"[green]{upd.files_added}[/green] file(s)")
    table.add_row("Removed", f"[red]{upd.files_removed}[/red] file(s)")
    console.print(Panel(table, border_style="green", padding=(0, 1)))

    for w in upd.warnings:
        console.print(f"\n  [yellow]⚠[/yellow]  {w}")
    console.print()


def print_result(result: GenerateResult, elapsed: float) -> None:
    """Display generation results."""
    console.print(f"[bold green]✔[/bold green] Done in [bold]{elapsed:.1f}s[/bold]\n")

    pct = result.total_tokens / TOKEN_BUDGET * 100
    bar_len = 24
    filled = int(bar_len * min(pct, 100) / 100)
    color = "green" if pct < 75 else "yellow" if pct < 95 else "red"
    bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * (bar_len - filled)}[/dim]"

    fit_label = (
        "[green]fits comfortably[/green]" if pct < 75
        else "[yellow]tight fit[/yellow]" if pct < 100
        else "[red]over budget[/red]"
    )

    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=14)
    table.add_column()

    table.add_row("Output", f"[bold cyan]{result.output_path}[/bold cyan]")
    table.add_row(
        "Tokens",
        f"{bar}  [bold]{result.total_tokens:,}[/bold] / {TOKEN_BUDGET:,}  "
        f"[dim]({pct:.0f}%)[/dim]  {fit_label}",
    )
    if result.focus_path:
        table.add_row("Focus", f"[bold #7c3aed]{result.focus_path}[/bold #7c3aed]")
        table.add_row("Focused files", f"[green]{result.files_full}[/green]")
        table.add_row("Structure only", f"[dim]{result.files_structure_only}[/dim]")
    else:
        table.add_row("Full files", f"[green]{result.files_full}[/green]")
        table.add_row("Summarised", f"[yellow]{result.files_summary}[/yellow]")
        table.add_row("Skipped", f"[dim]{result.files_metadata}[/dim]")
        if result.files_omitted:
            table.add_row("Omitted", f"[red]{result.files_omitted}[/red]")

    console.print(Panel(table, border_style="green", padding=(0, 1)))

    for w in result.warnings:
        console.print(f"\n  [yellow]⚠[/yellow]  {w}")

    console.print(
        "\n  [dim]Tip: Paste your context file directly into "
        "[link=https://claude.ai/new]claude.ai/new[/link] or ChatGPT.[/dim]\n"
    )


def auto_copy(output_path: str) -> None:
    """Silent auto-copy triggered by --copy flag."""
    try:
        import pyperclip
        with open(output_path, encoding="utf-8") as f:
            pyperclip.copy(f.read())
        console.print(
            "  [green]✔[/green]  Copied to clipboard  "
            "[dim](--copy flag)[/dim]"
        )
    except ImportError:
        console.print(
            "  [yellow]⚠[/yellow]  --copy flag: pyperclip not installed.  "
            "Run: [bold]pip install pyperclip[/bold]"
        )
    except Exception as e:
        console.print(f"  [red]✗[/red]  --copy flag: could not copy — {e}")


def copy_text(output_path: str) -> None:
    """Copy file text content to clipboard."""
    try:
        import pyperclip
        with open(output_path, encoding="utf-8") as f:
            pyperclip.copy(f.read())
        console.print("  [green]✔[/green] Text copied to clipboard.")
    except ImportError:
        console.print("  [red]✗[/red] pyperclip not installed. Run: pip install pyperclip")
    except Exception as e:
        console.print(f"  [red]✗[/red] Could not copy: {e}")
        show_manual_copy(output_path)


def copy_file(output_path: str) -> None:
    """Copy file object to clipboard (platform-specific)."""
    system = platform.system()
    try:
        if system == "Windows":
            cmd = f'powershell -Command "Set-Clipboard -Path \'{output_path}\'"'
            subprocess.run(cmd, shell=True, check=True,
                           capture_output=True, timeout=10)
            console.print("  [green]✔[/green] File copied to clipboard.")
        elif system == "Darwin":
            subprocess.run(
                ["osascript", "-e",
                 f'set the clipboard to (POSIX file "{output_path}")'],
                check=True, capture_output=True, timeout=10,
            )
            console.print("  [green]✔[/green] File copied to clipboard.")
        else:
            console.print(
                "  [yellow]ℹ[/yellow] File clipboard not supported on Linux. Copying text instead…"
            )
            copy_text(output_path)
    except Exception as e:
        console.print(f"  [red]✗[/red] Could not copy file: {e}")
        show_manual_copy(output_path)


def open_folder(folder: str) -> None:
    """Open folder in file manager."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(folder)
        elif system == "Darwin":
            subprocess.run(["open", folder], check=True)
        else:
            subprocess.run(["xdg-open", folder], check=True)
        console.print("  [green]✔[/green] Folder opened.")
    except Exception as e:
        console.print(f"  [red]✗[/red] Could not open folder: {e}")
        console.print(f"  [dim]Path: {folder}[/dim]")


def show_manual_copy(output_path: str) -> None:
    """Show manual copy commands for the user's platform."""
    system = platform.system()
    console.print("\n  [dim]Manual copy commands:[/dim]")
    if system == "Windows":
        console.print(f'  [cyan]type "{output_path}" | clip[/cyan]')
    elif system == "Darwin":
        console.print(f'  [cyan]cat "{output_path}" | pbcopy[/cyan]')
    else:
        console.print(f'  [cyan]cat "{output_path}" | xclip -selection clipboard[/cyan]')


def ask(prompt, **kwargs):
    """Wrap questionary calls - exit cleanly on Ctrl+C."""
    import typer
    try:
        result = prompt(**kwargs).ask()
    except KeyboardInterrupt:
        abort()
    if result is None:
        abort()
    return result


def abort() -> None:
    """Abort the CLI with a message."""
    import typer
    console.print("\n[yellow]Cancelled.[/yellow]\n")
    raise typer.Exit(0)


def create_progress() -> Progress:
    """Create a standard progress bar."""
    return Progress(
        SpinnerColumn(spinner_name="dots", style="#7c3aed"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=28, complete_style="#7c3aed", finished_style="#06b6d4"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
