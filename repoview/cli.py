"""
repoview CLI — interactive wizard.

    repoview                   # wizard, uses current directory
    repoview <path>            # wizard, pre-fills path
    repoview --quick <path>    # no questions, sensible defaults
    repoview --version
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import questionary
import typer
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
from repoview.core import generate_context, GenerateResult
from repoview.scanner import scan_project, ScanResult
from repoview.config import TOKEN_BUDGET

# ─────────────────────────────────────────────────────────────────────────────
console = Console()
app = typer.Typer(
    name="repoview",
    help="Turn any codebase into LLM-ready context — in seconds.",
    add_completion=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
)

CC_STYLE = Style([
    ("qmark",       "fg:#7c3aed bold"),
    ("question",    "bold"),
    ("answer",      "fg:#7c3aed bold"),
    ("pointer",     "fg:#7c3aed bold"),
    ("highlighted", "fg:#7c3aed bold"),
    ("selected",    "fg:#06b6d4"),
    ("instruction", "fg:#666666"),
    ("text",        ""),
    ("disabled",    "fg:#444444 italic"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────

def _banner() -> None:
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


# ─────────────────────────────────────────────────────────────────────────────
# Scan preview
# ─────────────────────────────────────────────────────────────────────────────

def _show_scan(scan: ScanResult, folder_name: str) -> None:
    console.print(f"  [dim]Scanning[/dim] [bold]{folder_name}[/bold][dim]…[/dim]")
    time.sleep(0.1)  # tiny pause so it doesn't flash

    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=16)
    table.add_column()

    table.add_row("Files found",   f"[bold]{scan.total_files}[/bold]")
    table.add_row("Total size",    f"[bold]{scan.total_size_mb:.1f} MB[/bold]")
    table.add_row("Est. tokens",   f"[bold]~{scan.est_tokens:,}[/bold]")

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


# ─────────────────────────────────────────────────────────────────────────────
# Wizard
# ─────────────────────────────────────────────────────────────────────────────

def _abort() -> None:
    console.print("\n[yellow]Cancelled.[/yellow]\n")
    raise typer.Exit(0)


def _ask(prompt, **kwargs):
    """Wrap questionary calls — exit cleanly on Ctrl+C."""
    try:
        result = prompt(**kwargs).ask()
    except KeyboardInterrupt:
        _abort()
    if result is None:
        _abort()
    return result


def _run_wizard(preset_path: Optional[str] = None) -> None:
    _banner()

    # ── Resolve path ─────────────────────────────────────────────────────────
    if preset_path:
        input_path = os.path.abspath(os.path.expanduser(preset_path))
    else:
        raw = _ask(
            questionary.path,
            message="Path to your project folder (Enter for current directory):",
            default=os.getcwd(),
            only_directories=True,
            style=CC_STYLE,
        )
        input_path = os.path.abspath(os.path.expanduser(raw))

    if not os.path.exists(input_path):
        console.print(f"\n[red]✗[/red] Path not found: [bold]{input_path}[/bold]\n")
        raise typer.Exit(1)

    folder_name = os.path.basename(input_path.rstrip("/\\"))

    # ── Scan ─────────────────────────────────────────────────────────────────
    scan = scan_project(input_path)
    _show_scan(scan, folder_name)

    # ── Q1: Skip docs? (always shown) ────────────────────────────────────────
    doc_info = (
        f"(.md  .txt  .rst  .mdx)  "
        f"[dim]{scan.doc_file_count} files found[/dim]"
        if scan.doc_file_count else "(.md  .txt  .rst  .mdx)"
    )
    console.print(
        "  [dim]These are README, notes, and documentation files.\n"
        "  Skip them to keep context focused on actual code.[/dim]\n"
    )
    skip_docs = _ask(
        questionary.confirm,
        message=f"Skip documentation files?  {doc_info}",
        default=True,
        style=CC_STYLE,
    )

    console.print()

    # ── Q2: Skip tests? (only if test files found) ────────────────────────────
    skip_tests = False
    if scan.has_test_files:
        console.print(
            "  [dim]Test files match patterns like:  "
            "test_*.py  •  *.test.js  •  *.spec.ts  •  /tests/\n"
            "  Skip them for feature/bug context. Include for test coverage understanding.[/dim]\n"
        )
        skip_tests = _ask(
            questionary.confirm,
            message=f"Skip test files?  [dim]{scan.test_file_count} found[/dim]",
            default=True,
            style=CC_STYLE,
        )
        console.print()

    # ── Q3: Respect .gitignore? (only if .gitignore exists) ──────────────────
    respect_gitignore = True
    if scan.has_gitignore:
        console.print(
            f"  [dim].gitignore found with {scan.gitignore_rules} rules.\n"
            "  Respecting it will exclude node_modules, .env, dist, build, etc.[/dim]\n"
        )
        respect_gitignore = _ask(
            questionary.confirm,
            message="Respect .gitignore?",
            default=True,
            style=CC_STYLE,
        )
        console.print()

    # ── Q4: Output filename ───────────────────────────────────────────────────
    default_name = f"{folder_name}-context.txt"
    console.print(
        f"  [dim]This file will contain your full LLM context.\n"
        f"  Leave blank to use the default: [bold]{default_name}[/bold][/dim]\n"
    )
    out_name = _ask(
        questionary.text,
        message="Output file name:",
        default=default_name,
        style=CC_STYLE,
    )
    if not out_name.strip():
        out_name = default_name
    if not out_name.endswith(".txt"):
        out_name += ".txt"

    console.print()

    # ── Q5: Output location ───────────────────────────────────────────────────
    inside_path = os.path.join(input_path, out_name)
    parent_path = os.path.join(os.path.dirname(input_path), out_name)

    console.print(
        "  [dim]Where should the output file be saved?[/dim]\n"
    )
    loc_choice = _ask(
        questionary.select,
        message="Save output to:",
        choices=[
            questionary.Choice(
                f"Inside the project folder   ({inside_path})",
                value="inside",
            ),
            questionary.Choice(
                f"Next to the project folder  ({parent_path})",
                value="parent",
            ),
            questionary.Choice("Custom path…", value="custom"),
        ],
        style=CC_STYLE,
    )

    if loc_choice == "inside":
        output_path = inside_path
    elif loc_choice == "parent":
        output_path = parent_path
    else:
        raw_loc = _ask(
            questionary.path,
            message="Enter output folder path:",
            only_directories=True,
            style=CC_STYLE,
        )
        output_path = os.path.join(
            os.path.abspath(os.path.expanduser(raw_loc)), out_name
        )

    console.print()

    # ── Confirm summary ───────────────────────────────────────────────────────
    _print_summary(
        input_path, output_path, skip_docs, skip_tests,
        respect_gitignore, scan,
    )

    go = _ask(
        questionary.confirm,
        message="Generate context file?",
        default=True,
        style=CC_STYLE,
    )
    if not go:
        console.print("\n[yellow]Cancelled.[/yellow]\n")
        raise typer.Exit(0)

    console.print()

    # ── Execute ───────────────────────────────────────────────────────────────
    result = _execute(
        input_path=input_path,
        output_path=output_path,
        skip_docs=skip_docs,
        skip_tests=skip_tests,
        respect_gitignore=respect_gitignore,
    )

    if result:
        _post_menu(result)


def _print_summary(
    input_path, output_path, skip_docs, skip_tests,
    respect_gitignore, scan: ScanResult,
) -> None:
    skipped = []
    if skip_docs:   skipped.append("docs")
    if skip_tests:  skipped.append("tests")
    skip_str = ", ".join(skipped) if skipped else "nothing"

    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=14)
    table.add_column()
    table.add_row("Source",    f"[bold]{input_path}[/bold]")
    table.add_row("Output",    f"[bold]{output_path}[/bold]")
    table.add_row("Skipping",  f"[cyan]{skip_str}[/cyan]")
    if scan.has_gitignore:
        table.add_row(
            ".gitignore",
            "[green]respected[/green]" if respect_gitignore else "[yellow]ignored[/yellow]",
        )

    console.print(Panel(table, title="[bold]Ready to generate[/bold]",
                        border_style="#7c3aed", padding=(0, 1)))
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Execution + progress
# ─────────────────────────────────────────────────────────────────────────────

def _execute(
    input_path: str,
    output_path: str,
    skip_docs: bool,
    skip_tests: bool,
    respect_gitignore: bool,
) -> Optional[GenerateResult]:
    state = {"done": 0, "total": 0, "current": ""}

    def _cb(done: int, total: int) -> None:
        state["done"] = done
        state["total"] = total

    result_box: list = [None]
    error_box:  list = [None]

    def _worker():
        try:
            result_box[0] = generate_context(
                input_path=input_path,
                output_path=output_path,
                skip_docs=skip_docs,
                skip_tests=skip_tests,
                respect_gitignore=respect_gitignore,
                token_budget=TOKEN_BUDGET,
                progress_cb=_cb,
            )
        except Exception as e:
            error_box[0] = e

    start = time.time()
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    with Progress(
        SpinnerColumn(spinner_name="dots", style="#7c3aed"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=28, complete_style="#7c3aed", finished_style="#06b6d4"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as prog:
        task = prog.add_task("Processing files…", total=None)
        while t.is_alive():
            d, tot = state["done"], state["total"]
            if tot:
                prog.update(
                    task,
                    completed=d, total=tot,
                    description=f"Processing files… [dim]({d}/{tot})[/dim]",
                )
            time.sleep(0.05)
        t.join()

    if error_box[0]:
        console.print(f"\n[red]✗ Error:[/red] {error_box[0]}\n")
        return None

    result = result_box[0]
    elapsed = time.time() - start
    _print_result(result, elapsed)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Result display
# ─────────────────────────────────────────────────────────────────────────────

def _print_result(result: GenerateResult, elapsed: float) -> None:
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

    table.add_row("Output",     f"[bold cyan]{result.output_path}[/bold cyan]")
    table.add_row(
        "Tokens",
        f"{bar}  [bold]{result.total_tokens:,}[/bold] / {TOKEN_BUDGET:,}  "
        f"[dim]({pct:.0f}%)[/dim]  {fit_label}",
    )
    table.add_row("Full files",  f"[green]{result.files_full}[/green]")
    table.add_row("Summarised",  f"[yellow]{result.files_summary}[/yellow]")
    table.add_row("Skipped",     f"[dim]{result.files_metadata}[/dim]")
    if result.files_omitted:
        table.add_row("Omitted", f"[red]{result.files_omitted}[/red]")

    console.print(Panel(table, border_style="green", padding=(0, 1)))

    for w in result.warnings:
        console.print(f"\n  [yellow]⚠[/yellow]  {w}")

    console.print(
        "\n  [dim]Tip: Paste your context file directly into "
        "[link=https://claude.ai/new]claude.ai/new[/link] or ChatGPT.[/dim]\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Post-completion menu
# ─────────────────────────────────────────────────────────────────────────────

def _post_menu(result: GenerateResult) -> None:
    while True:
        action = _ask(
            questionary.select,
            message="What do you want to do next?",
            choices=[
                questionary.Choice("📋  Copy text to clipboard   (paste into Claude / ChatGPT)", value="copy_text"),
                questionary.Choice("📄  Copy file to clipboard   (paste the file itself)", value="copy_file"),
                questionary.Choice("📁  Open output folder       (in Explorer / Finder)",     value="open_folder"),
                questionary.Choice("🔁  Run again                (same project, new settings)", value="run_again"),
                questionary.Choice("❌  Exit",                                                 value="exit"),
            ],
            style=CC_STYLE,
        )

        if action == "copy_text":
            _copy_text(result.output_path)

        elif action == "copy_file":
            _copy_file(result.output_path)

        elif action == "open_folder":
            _open_folder(os.path.dirname(result.output_path))

        elif action == "run_again":
            console.print()
            _run_wizard(preset_path=os.path.dirname(result.output_path))
            return

        elif action == "exit":
            console.print("\n[dim]Bye![/dim]\n")
            raise typer.Exit(0)

        console.print()


def _copy_text(output_path: str) -> None:
    try:
        import pyperclip
        with open(output_path, encoding="utf-8") as f:
            pyperclip.copy(f.read())
        console.print("  [green]✔[/green] Text copied to clipboard.")
    except ImportError:
        console.print("  [red]✗[/red] pyperclip not installed. Run: pip install pyperclip")
    except Exception as e:
        console.print(f"  [red]✗[/red] Could not copy: {e}")
        _show_manual_copy(output_path)


def _copy_file(output_path: str) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            # PowerShell: Set-Clipboard with file object
            cmd = (
                f'powershell -Command "Set-Clipboard -Path \'{output_path}\'"'
            )
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
            # Linux — xclip / xdotool don't support file objects well
            # Best we can do is copy the text
            console.print(
                "  [yellow]ℹ[/yellow] File clipboard not supported on Linux. Copying text instead…"
            )
            _copy_text(output_path)
    except Exception as e:
        console.print(f"  [red]✗[/red] Could not copy file: {e}")
        _show_manual_copy(output_path)


def _open_folder(folder: str) -> None:
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


def _show_manual_copy(output_path: str) -> None:
    system = platform.system()
    fname = os.path.basename(output_path)
    console.print("\n  [dim]Manual copy commands:[/dim]")
    if system == "Windows":
        console.print(f'  [cyan]type "{output_path}" | clip[/cyan]')
    elif system == "Darwin":
        console.print(f'  [cyan]cat "{output_path}" | pbcopy[/cyan]')
    else:
        console.print(f'  [cyan]cat "{output_path}" | xclip -selection clipboard[/cyan]')


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry points
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    path: Optional[str] = typer.Argument(
        None, help="Project folder path. Defaults to current directory."
    ),
    version: bool = typer.Option(
        False, "--version", "-v", is_eager=True, help="Show version."
    ),
    quick: bool = typer.Option(
        False, "--quick", "-q",
        help="Skip all questions. Use sensible defaults.",
    ),
) -> None:
    """
    [bold #7c3aed]repoview[/bold #7c3aed] — Turn any codebase into LLM-ready context.

    Run with no arguments to start the interactive wizard.
    """
    if version:
        console.print(f"repoview v{__version__}")
        raise typer.Exit(0)

    if ctx.invoked_subcommand is not None:
        return

    if quick:
        _run_quick(path)
    else:
        _run_wizard(preset_path=path)


def _run_quick(path: Optional[str]) -> None:
    """Non-interactive run with all defaults."""
    _banner()
    input_path = os.path.abspath(path or os.getcwd())
    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    folder_name = os.path.basename(input_path.rstrip("/\\"))
    output_path = os.path.join(input_path, f"{folder_name}-context.txt")

    scan = scan_project(input_path)
    _show_scan(scan, folder_name)

    console.print(
        f"  [dim]Quick mode — using defaults:[/dim]\n"
        f"  [dim]  skip docs: yes  •  skip tests: yes  •  "
        f"gitignore: {'respected' if scan.has_gitignore else 'n/a'}[/dim]\n"
        f"  [dim]  output: {output_path}[/dim]\n"
    )

    result = _execute(
        input_path=input_path,
        output_path=output_path,
        skip_docs=True,
        skip_tests=scan.has_test_files,
        respect_gitignore=scan.has_gitignore,
    )
    if result:
        _post_menu(result)