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
from repoview.cache import load_cache, diff_cache, build_cache, save_cache
from repoview.differ import incremental_update, UpdateResult
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


def _try_incremental(
    input_path: str,
    cached,
    scan,
) -> bool:
    """
    Automatic incremental update — no prompts, no choices.

    Logic:
      - No changes detected  →  go straight to post menu (nothing to do)
      - Changes detected     →  auto incremental update, then post menu
      - Incremental fails    →  return False so caller falls through to full wizard

    Returns True if we handled everything, False if full wizard should run.
    """
    from repoview.core import collect_folder

    # ── Diff ─────────────────────────────────────────────────────────────────
    entries = collect_folder(
        input_path,
        respect_gitignore=cached.settings.get("respect_gitignore", True),
    )
    diff = diff_cache(cached, entries)

    # ── No changes ────────────────────────────────────────────────────────────
    if not diff.has_changes:
        console.print(
            f"  [green]✔[/green]  Context is already up to date  "
            f"[dim]({cached.age_human()})[/dim]\n"
        )
        _post_menu_from_path(cached.output_path)
        return True

    # ── Show what changed (informational, no prompt) ──────────────────────────
    console.print(
        f"  [bold]Changes since last run[/bold]  "
        f"[dim]({cached.age_human()})[/dim]\n"
    )
    if diff.modified:
        for f in diff.modified[:8]:
            console.print(f"    [yellow]✎[/yellow]  {f}")
        if len(diff.modified) > 8:
            console.print(f"    [dim]… and {len(diff.modified)-8} more modified[/dim]")
    if diff.added:
        for f in diff.added[:5]:
            console.print(f"    [green]+[/green]  {f}")
        if len(diff.added) > 5:
            console.print(f"    [dim]… and {len(diff.added)-5} more added[/dim]")
    if diff.deleted:
        for f in diff.deleted[:5]:
            console.print(f"    [red]-[/red]  {f}")
        if len(diff.deleted) > 5:
            console.print(f"    [dim]… and {len(diff.deleted)-5} more deleted[/dim]")
    console.print()

    # ── Auto incremental update ───────────────────────────────────────────────
    skip_docs  = cached.settings.get("skip_docs",  True)
    skip_tests = cached.settings.get("skip_tests", True)

    affected_rels = set(diff.modified) | set(diff.added)
    for e in entries:
        if not e.is_dir and e.relative_path in affected_rels:
            e.process(skip_docs=skip_docs, skip_tests=skip_tests)

    start = time.time()
    with Progress(
        SpinnerColumn(spinner_name="dots", style="#7c3aed"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=28, complete_style="#7c3aed", finished_style="#06b6d4"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as prog:
        task = prog.add_task(
            f"Updating {diff.total_changes} file(s)…",
            total=diff.total_changes,
        )
        done_box   = [0]
        result_box = [None]
        error_box  = [None]

        def _inc_cb(done: int, total: int) -> None:
            done_box[0] = done
            prog.update(task, completed=done)

        def _worker():
            try:
                result_box[0] = incremental_update(
                    project_path=input_path,
                    cache=cached,
                    diff=diff,
                    all_entries=entries,
                    progress_cb=_inc_cb,
                )
            except Exception as e:
                error_box[0] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        while t.is_alive():
            prog.update(task, completed=done_box[0])
            time.sleep(0.05)
        t.join()

    if error_box[0]:
        console.print(f"\n[red]✗ Update failed:[/red] {error_box[0]}")
        console.print("[dim]Falling back to full regeneration…[/dim]\n")
        return False

    upd: UpdateResult = result_box[0]
    _print_update_result(upd, time.time() - start)

    gr = GenerateResult(
        output_path=upd.output_path,
        total_tokens=upd.total_tokens,
        warnings=upd.warnings,
    )
    _post_menu(gr)
    return True


def _print_update_result(upd: UpdateResult, elapsed: float) -> None:
    console.print(f"[bold green]✔[/bold green] Updated in [bold]{elapsed:.1f}s[/bold]\n")

    pct = upd.total_tokens / TOKEN_BUDGET * 100
    bar_len = 24
    filled = int(bar_len * min(pct, 100) / 100)
    color = "green" if pct < 75 else "yellow" if pct < 95 else "red"
    bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * (bar_len - filled)}[/dim]"

    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=14)
    table.add_column()
    table.add_row("Output",    f"[bold cyan]{upd.output_path}[/bold cyan]")
    table.add_row("Tokens",    f"{bar}  [bold]{upd.total_tokens:,}[/bold] / {TOKEN_BUDGET:,}")
    table.add_row("Updated",   f"[yellow]{upd.files_updated}[/yellow] file(s)")
    table.add_row("Added",     f"[green]{upd.files_added}[/green] file(s)")
    table.add_row("Removed",   f"[red]{upd.files_removed}[/red] file(s)")
    console.print(Panel(table, border_style="green", padding=(0, 1)))

    for w in upd.warnings:
        console.print(f"\n  [yellow]⚠[/yellow]  {w}")
    console.print()


def _post_menu_from_path(output_path: str) -> None:
    """Post menu when we have a path but no fresh GenerateResult."""
    from repoview.core import GenerateResult
    gr = GenerateResult(output_path=output_path, total_tokens=0)
    _post_menu(gr)


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

    # ── Diff check — offer incremental update if cache exists ────────────────
    cached = load_cache(input_path)
    if cached and os.path.exists(cached.output_path):
        did_incremental = _try_incremental(input_path, cached, scan)
        if did_incremental:
            return   # user accepted incremental — we're done

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
    focus_path: str = "",
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
                focus_path=focus_path,
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
    if result.focus_path:
        table.add_row("Focus",        f"[bold #7c3aed]{result.focus_path}[/bold #7c3aed]")
        table.add_row("Focused files",f"[green]{result.files_full}[/green]")
        table.add_row("Structure only",f"[dim]{result.files_structure_only}[/dim]")
    else:
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
    watch: bool = typer.Option(
        False, "--watch", "-w",
        help="Watch for file changes and auto-update context.",
    ),
    reset: bool = typer.Option(
        False, "--reset", "-r",
        help="Delete saved cache for this project and run the wizard fresh.",
    ),
    focus: Optional[str] = typer.Option(
        None, "--focus", "-f",
        help="Focus on a specific folder or file (e.g. src/auth or src/auth/index.ts).",
    ),
    info: bool = typer.Option(
        False, "--info", "-i",
        help="Show project stats without generating anything.",
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

    if reset:
        _run_reset(path)
    elif info:
        _run_info(path)
    elif watch and focus:
        _run_watch(path, focus_path=focus)
    elif watch:
        _run_watch(path)
    elif focus:
        _run_focus(path, focus_path=focus)
    elif quick:
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




def _run_info(path: Optional[str]) -> None:
    """
    Deep project inspection — no generation, no questions.
    Shows everything a developer needs to understand a repo at a glance.
    """
    import math
    from collections import defaultdict
    from repoview.cache import load_cache
    from repoview.config import (
        IMPORTANT_CODE_EXTS, SUPPORTING_CONFIG_EXTS, GENERAL_CODE_EXTS,
        DOC_EXTS, TOKEN_BUDGET, EXCLUDE_DIRS, METADATA_ONLY_EXTS,
        ESSENTIAL_FILENAMES,
    )

    _banner()

    input_path  = os.path.abspath(path or os.getcwd())
    folder_name = os.path.basename(input_path.rstrip("/\\"))

    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    console.print(f"  [dim]Deep scanning[/dim] [bold]{folder_name}[/bold][dim]…[/dim]\n")

    # ── Deep scan ─────────────────────────────────────────────────────────────
    scan = scan_project(input_path)

    # Extra data scan_project doesn't collect
    largest_files   = []   # (size, rel_path)
    largest_by_lines= []   # (lines, rel_path)
    folder_stats    = defaultdict(lambda: {"files": 0, "size": 0})
    total_lines     = 0
    binary_count    = 0
    essential_found = []
    exclude_lower   = {d.lower() for d in EXCLUDE_DIRS}
    base            = input_path

    for root, dirs, files in os.walk(base, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in exclude_lower]
        for fname in files:
            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, base).replace(os.sep, "/")
            ext  = os.path.splitext(fname)[1].lower()

            # Essential files
            if fname.lower() in ESSENTIAL_FILENAMES:
                essential_found.append(fname)

            # Binary
            if ext in METADATA_ONLY_EXTS:
                binary_count += 1
                continue

            try:
                size = os.path.getsize(full)
            except OSError:
                continue

            largest_files.append((size, rel))

            # Top-level folder bucket
            parts = rel.split("/")
            bucket = parts[0] if len(parts) > 1 else "(root)"
            folder_stats[bucket]["files"] += 1
            folder_stats[bucket]["size"]  += size

            # Line count (only readable text files, max 2MB read)
            if size < 2 * 1024 * 1024:
                try:
                    with open(full, "rb") as fh:
                        raw = fh.read()
                    lines = raw.count(b"\n") + 1
                    total_lines += lines
                    largest_by_lines.append((lines, rel))
                except OSError:
                    pass

    largest_files.sort(reverse=True)
    largest_by_lines.sort(reverse=True)

    # ── Helper: mini bar ──────────────────────────────────────────────────────
    def _bar(value: int, maximum: int, width: int = 20, color: str = "#7c3aed") -> str:
        if maximum == 0:
            return ""
        filled = max(1, round(width * value / maximum)) if value else 0
        empty  = width - filled
        return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"

    def _fmt_size(b: int) -> str:
        if b < 1024:        return f"{b} B"
        if b < 1024**2:     return f"{b/1024:.1f} KB"
        return              f"{b/1024**2:.1f} MB"

    # ── Project type detection ────────────────────────────────────────────────
    def _detect_project_type() -> str:
        exts = set(scan.ext_counter.keys())
        ef   = {f.lower() for f in essential_found}
        if "package.json" in ef and (".tsx" in exts or ".jsx" in exts): return "React / TypeScript"
        if "package.json" in ef and ".vue"  in exts:  return "Vue.js"
        if "package.json" in ef and ".svelte" in exts: return "Svelte"
        if "package.json" in ef:                       return "Node.js / JavaScript"
        if "pyproject.toml" in ef or "requirements.txt" in ef:
            if "manage.py" in ef:                      return "Python / Django"
            if "fastapi" in str(ef).lower():           return "Python / FastAPI"
            return "Python"
        if "go.mod" in ef:                             return "Go"
        if "cargo.toml" in ef:                         return "Rust"
        if "pom.xml" in ef or "build.gradle" in ef:   return "Java / JVM"
        if ".cs" in exts:                              return "C#  / .NET"
        if ".rb" in exts:                              return "Ruby"
        if ".php" in exts:                             return "PHP"
        if ".swift" in exts:                           return "Swift"
        if ".kt" in exts:                              return "Kotlin"
        return "Mixed / Unknown"

    project_type = _detect_project_type()

    # ── Category summary ──────────────────────────────────────────────────────
    cat_counts = {"code": 0, "config": 0, "docs": 0, "general": 0, "other": 0}
    for ext, cnt in scan.ext_counter.items():
        if ext in IMPORTANT_CODE_EXTS:    cat_counts["code"]    += cnt
        elif ext in SUPPORTING_CONFIG_EXTS: cat_counts["config"] += cnt
        elif ext in DOC_EXTS:             cat_counts["docs"]    += cnt
        elif ext in GENERAL_CODE_EXTS:    cat_counts["general"] += cnt
        else:                             cat_counts["other"]   += cnt

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 1 — Overview
    # ════════════════════════════════════════════════════════════════════════
    t = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    t.add_column(style="dim", justify="right", min_width=20)
    t.add_column()

    fit_color = "green" if scan.est_tokens < TOKEN_BUDGET * 0.75 else (
                "yellow" if scan.est_tokens < TOKEN_BUDGET else "red")
    fit_label = ("fits comfortably" if scan.est_tokens < TOKEN_BUDGET * 0.75 else
                 "tight fit" if scan.est_tokens < TOKEN_BUDGET else "may need trimming")

    t.add_row("Path",           f"[bold]{input_path}[/bold]")
    t.add_row("Project type",   f"[bold #7c3aed]{project_type}[/bold #7c3aed]")
    t.add_row("",               "")
    t.add_row("Text files",     f"[bold]{scan.total_files:,}[/bold]")
    t.add_row("Binary / assets",f"[dim]{binary_count}[/dim]  [dim](images, fonts, compiled — never read)[/dim]")
    t.add_row("Total size",     f"[bold]{_fmt_size(scan.total_size_bytes)}[/bold]")
    t.add_row("Lines of code",  f"[bold cyan]{total_lines:,}[/bold cyan]")
    t.add_row("",               "")
    t.add_row("Est. tokens",    f"[bold cyan]~{scan.est_tokens:,}[/bold cyan]  [dim](rough estimate before filtering)[/dim]")
    t.add_row("Token budget",   f"[bold]{TOKEN_BUDGET:,}[/bold]  [{fit_color}]— {fit_label}[/{fit_color}]")

    console.print(Panel(t, title=f"[bold]  {folder_name}  [/bold]",
                        border_style="#7c3aed", padding=(0, 1)))
    console.print()

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 2 — Essential files detected
    # ════════════════════════════════════════════════════════════════════════
    if essential_found:
        ef_table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
        ef_table.add_column(min_width=4)
        ef_table.add_column(style="cyan")
        for f in sorted(set(essential_found)):
            ef_table.add_row("[green]✔[/green]", f)
        console.print(Panel(ef_table,
            title="[bold]Essential Files Detected[/bold]",
            subtitle="[dim]always included in context[/dim]",
            border_style="green", padding=(0, 1)))
        console.print()

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 3 — File type breakdown with bar chart
    # ════════════════════════════════════════════════════════════════════════
    if scan.ext_counter:
        top = scan.ext_counter.most_common(10)
        max_count = top[0][1] if top else 1

        ft = Table(show_header=True, box=None, padding=(0, 2), show_edge=False)
        ft.add_column("Ext",      style="bold cyan", min_width=10)
        ft.add_column("Files",    justify="right",   min_width=6)
        ft.add_column("",         min_width=22)   # bar
        ft.add_column("Category", style="dim",    min_width=12)

        def _cat_label(ext: str) -> str:
            if ext in IMPORTANT_CODE_EXTS:    return "[green]code[/green]"
            if ext in SUPPORTING_CONFIG_EXTS: return "[yellow]config[/yellow]"
            if ext in DOC_EXTS:               return "[blue]docs[/blue]"
            if ext in GENERAL_CODE_EXTS:      return "[dim]general[/dim]"
            return "[dim]other[/dim]"

        for ext, cnt in top:
            label = ext if ext else "[dim](no ext)[/dim]"
            ft.add_row(label, str(cnt), _bar(cnt, max_count), _cat_label(ext))

        if len(scan.ext_counter) > 10:
            ft.add_row(
                f"[dim]+{len(scan.ext_counter)-10} more[/dim]", "", "", ""
            )

        console.print(Panel(ft, title="[bold]File Types[/bold]",
                            border_style="dim", padding=(0, 1)))
        console.print()

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 4 — Category breakdown
    # ════════════════════════════════════════════════════════════════════════
    total_categorised = sum(cat_counts.values()) or 1
    cb = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    cb.add_column(style="dim", justify="right", min_width=10)
    cb.add_column(min_width=6, justify="right")
    cb.add_column(min_width=24)
    cb.add_column(style="dim", min_width=6)

    cat_colors = {
        "code":    "green",
        "config":  "yellow",
        "docs":    "blue",
        "general": "cyan",
        "other":   "dim",
    }
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        if cnt == 0:
            continue
        pct = cnt / total_categorised * 100
        color = cat_colors[cat]
        cb.add_row(
            cat,
            f"[{color}]{cnt}[/{color}]",
            _bar(cnt, total_categorised, 20, color),
            f"[dim]{pct:.0f}%[/dim]",
        )

    console.print(Panel(cb, title="[bold]Category Breakdown[/bold]",
                        border_style="dim", padding=(0, 1)))
    console.print()

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 5 — Top-level folder breakdown
    # ════════════════════════════════════════════════════════════════════════
    if folder_stats:
        max_folder_files = max(v["files"] for v in folder_stats.values()) or 1
        fd = Table(show_header=True, box=None, padding=(0, 2), show_edge=False)
        fd.add_column("Folder",  style="bold", min_width=18)
        fd.add_column("Files",   justify="right", min_width=6)
        fd.add_column("",        min_width=22)
        fd.add_column("Size",    style="dim", justify="right", min_width=10)

        for folder, stats in sorted(folder_stats.items(),
                                    key=lambda x: -x[1]["files"])[:12]:
            fd.add_row(
                f"[cyan]{folder}/[/cyan]" if folder != "(root)" else "[dim](root)[/dim]",
                str(stats["files"]),
                _bar(stats["files"], max_folder_files, 20, "#06b6d4"),
                _fmt_size(stats["size"]),
            )

        console.print(Panel(fd, title="[bold]Top-Level Folders[/bold]",
                            border_style="dim", padding=(0, 1)))
        console.print()

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 6 — Largest files by size
    # ════════════════════════════════════════════════════════════════════════
    if largest_files:
        top_files = largest_files[:8]
        max_sz = top_files[0][0] or 1
        lf = Table(show_header=True, box=None, padding=(0, 2), show_edge=False)
        lf.add_column("File",  style="cyan", min_width=32)
        lf.add_column("Size",  justify="right", min_width=10)
        lf.add_column("",      min_width=20)

        for size, rel in top_files:
            lf.add_row(rel, _fmt_size(size), _bar(size, max_sz, 18, "#f59e0b"))

        console.print(Panel(lf, title="[bold]Largest Files[/bold]",
                            border_style="dim", padding=(0, 1)))
        console.print()

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 7 — Longest files by line count
    # ════════════════════════════════════════════════════════════════════════
    if largest_by_lines:
        top_lines = largest_by_lines[:8]
        max_ln = top_lines[0][0] or 1
        ll = Table(show_header=True, box=None, padding=(0, 2), show_edge=False)
        ll.add_column("File",  style="cyan", min_width=32)
        ll.add_column("Lines", justify="right", min_width=8)
        ll.add_column("",      min_width=20)

        for lines, rel in top_lines:
            ll.add_row(rel, f"{lines:,}", _bar(lines, max_ln, 18, "#06b6d4"))

        console.print(Panel(ll, title="[bold]Longest Files[/bold]",
                            border_style="dim", padding=(0, 1)))
        console.print()

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 8 — What gets filtered
    # ════════════════════════════════════════════════════════════════════════
    fi = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    fi.add_column(style="dim", justify="right", min_width=22)
    fi.add_column()

    if scan.doc_file_count:
        fi.add_row(
            "Documentation",
            f"[yellow]{scan.doc_file_count}[/yellow] files  "
            f"[dim](.md .txt .rst .mdx) — skipped by default[/dim]",
        )
    if scan.test_file_count:
        fi.add_row(
            "Test files",
            f"[yellow]{scan.test_file_count}[/yellow] files  "
            f"[dim](test_* *.spec.* *.test.* /tests/) — skipped by default[/dim]",
        )
    if binary_count:
        fi.add_row(
            "Binary / assets",
            f"[dim]{binary_count}[/dim] files  "
            f"[dim](images, fonts, compiled) — never read[/dim]",
        )
    if scan.has_gitignore:
        fi.add_row(
            ".gitignore",
            f"[green]found[/green]  "
            f"[dim]{scan.gitignore_rules} rules — respected by default[/dim]",
        )
    else:
        fi.add_row(".gitignore", "[dim]not found[/dim]")

    console.print(Panel(fi, title="[bold]Filtering[/bold]",
                        border_style="dim", padding=(0, 1)))
    console.print()

    # ════════════════════════════════════════════════════════════════════════
    # PANEL 9 — Cache status
    # ════════════════════════════════════════════════════════════════════════
    cached = load_cache(input_path)
    cs = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    cs.add_column(style="dim", justify="right", min_width=22)
    cs.add_column()

    if cached:
        output_exists = os.path.exists(cached.output_path)
        cs.add_row("Status",     f"[green]● cached[/green]")
        cs.add_row("Last run",   f"[bold]{cached.age_human()}[/bold]  [dim]({cached.generated_at})[/dim]")
        cs.add_row(
            "Output file",
            f"[cyan]{cached.output_path}[/cyan]  "
            + (f"[green]✔ exists[/green]" if output_exists else f"[red]✗ missing[/red]"),
        )
        settings = cached.settings
        parts = []
        if settings.get("focus_path"):        parts.append(f"[#7c3aed]focus: {settings['focus_path']}[/#7c3aed]")
        if settings.get("skip_docs"):         parts.append("docs skipped")
        if settings.get("skip_tests"):        parts.append("tests skipped")
        if settings.get("respect_gitignore"): parts.append("gitignore respected")
        cs.add_row("Settings",   "  •  ".join(parts) if parts else "[dim]defaults[/dim]")
        cs.add_row("Cached files", f"[dim]{len(cached.files)}[/dim]")

        # Changed files since last run
        try:
            from repoview.core import collect_folder
            from repoview.cache import diff_cache
            entries = collect_folder(input_path,
                        respect_gitignore=settings.get("respect_gitignore", True))
            diff = diff_cache(cached, entries)
            if diff.has_changes:
                cs.add_row(
                    "Changes since run",
                    f"[yellow]✎ {len(diff.modified)} modified[/yellow]  "
                    f"[green]+ {len(diff.added)} added[/green]  "
                    f"[red]- {len(diff.deleted)} deleted[/red]",
                )
            else:
                cs.add_row("Changes since run", "[green]✔ up to date[/green]")
        except Exception:
            pass
    else:
        cs.add_row("Status", "[dim]○ no cache — project has not been run yet[/dim]")

    console.print(Panel(cs, title="[bold]Cache Status[/bold]",
                        border_style="dim", padding=(0, 1)))
    console.print()

    # ── Footer tip ────────────────────────────────────────────────────────────
    tip_parts = ["[bold]repoview[/bold]  — full wizard"]
    if cached and os.path.exists(cached.output_path):
        tip_parts.append("[bold]repoview --quick[/bold]  — instant regenerate")
    if scan.has_test_files or scan.doc_file_count:
        tip_parts.append("[bold]repoview --watch[/bold]  — live updates")
    console.print(
        "  [dim]Next steps:  " + "   •   ".join(tip_parts) + "[/dim]\n"
    )


def _run_focus(path: Optional[str], focus_path: str) -> None:
    """
    Focus mode — short wizard, only focused folder/file gets full content.

    Flow:
      Scan preview
      Q1: Respect .gitignore?  (only if .gitignore exists)
      Q2: Output filename?
      Q3: Output location?
      Confirm + generate
    """
    _banner()

    input_path  = os.path.abspath(path or os.getcwd())
    folder_name = os.path.basename(input_path.rstrip("/\\"))

    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    # Validate focus path exists
    focus_abs = os.path.join(input_path, focus_path.replace("/", os.sep))
    if not os.path.exists(focus_abs):
        console.print(
            f"  [red]✗[/red]  Focus path not found: [bold]{focus_path}[/bold]\n"
            f"  [dim]Looked in: {focus_abs}[/dim]\n"
        )
        raise typer.Exit(1)

    is_dir_focus = os.path.isdir(focus_abs)
    focus_type   = "folder" if is_dir_focus else "file"

    # ── Scan ─────────────────────────────────────────────────────────────────
    scan = scan_project(input_path)
    _show_scan(scan, folder_name)

    # Show focus info
    console.print(
        Panel.fit(
            Text.from_markup(
                f"[bold #7c3aed]⚡  Focus mode[/]\n"
                f"[dim]{focus_type}: [bold]{focus_path}[/bold][/dim]\n"
                f"[dim]All other files will appear in tree only — no content.[/dim]"
            ),
            border_style="#7c3aed",
            padding=(0, 2),
        )
    )
    console.print()

    # ── Q1: Gitignore (only if exists) ────────────────────────────────────────
    respect_gitignore = True
    if scan.has_gitignore:
        console.print(
            f"  [dim].gitignore found ({scan.gitignore_rules} rules).[/dim]\n"
        )
        respect_gitignore = _ask(
            questionary.confirm,
            message="Respect .gitignore?",
            default=True,
            style=CC_STYLE,
        )
        console.print()

    # ── Q2: Output filename ───────────────────────────────────────────────────
    # Derive a focused name: <folder>-<focus_slug>-context.txt
    focus_slug   = focus_path.strip("/").replace("/", "-").replace(".", "-")
    default_name = f"{folder_name}-{focus_slug}-context.txt"

    console.print(f"  [dim]Default output name: [bold]{default_name}[/bold][/dim]\n")
    out_name = _ask(
        questionary.text,
        message="Output file name:",
        default=default_name,
        style=CC_STYLE,
    )
    if not out_name.strip(): out_name = default_name
    if not out_name.endswith(".txt"): out_name += ".txt"
    console.print()

    # ── Q3: Output location ───────────────────────────────────────────────────
    inside_path = os.path.join(input_path, out_name)
    parent_path = os.path.join(os.path.dirname(input_path), out_name)

    loc_choice = _ask(
        questionary.select,
        message="Save output to:",
        choices=[
            questionary.Choice(f"Inside the project folder   ({inside_path})", value="inside"),
            questionary.Choice(f"Next to the project folder  ({parent_path})", value="parent"),
            questionary.Choice("Custom path…",                                  value="custom"),
        ],
        style=CC_STYLE,
    )

    if loc_choice == "inside":
        output_path = inside_path
    elif loc_choice == "parent":
        output_path = parent_path
    else:
        raw = _ask(
            questionary.path,
            message="Enter output folder path:",
            only_directories=True,
            style=CC_STYLE,
        )
        output_path = os.path.join(os.path.abspath(os.path.expanduser(raw)), out_name)
    console.print()

    # ── Summary ───────────────────────────────────────────────────────────────
    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=14)
    table.add_column()
    table.add_row("Source",    f"[bold]{input_path}[/bold]")
    table.add_row("Focus",     f"[bold #7c3aed]{focus_path}[/bold #7c3aed]")
    table.add_row("Output",    f"[bold]{output_path}[/bold]")
    if scan.has_gitignore:
        table.add_row(".gitignore",
            "[green]respected[/green]" if respect_gitignore else "[yellow]ignored[/yellow]")
    console.print(Panel(table, title="[bold]Ready to generate[/bold]",
                        border_style="#7c3aed", padding=(0, 1)))
    console.print()

    go = _ask(questionary.confirm, message="Generate focused context?",
              default=True, style=CC_STYLE)
    if not go:
        console.print("\n[yellow]Cancelled.[/yellow]\n")
        raise typer.Exit(0)
    console.print()

    result = _execute(
        input_path=input_path,
        output_path=output_path,
        skip_docs=False,      # focus mode includes everything in focus path
        skip_tests=False,
        respect_gitignore=respect_gitignore,
        focus_path=focus_path,
    )
    if result:
        _post_menu(result)


def _run_reset(path: Optional[str]) -> None:
    """
    Delete the cache for this project and run the wizard fresh.
    Useful when settings are wrong and user wants to start over.
    """
    from repoview.cache import delete_cache, cache_path_for

    _banner()

    input_path  = os.path.abspath(path or os.getcwd())
    folder_name = os.path.basename(input_path.rstrip("/\\"))

    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    cache_file = cache_path_for(input_path)

    if cache_file.exists():
        delete_cache(input_path)
        console.print(
            f"  [green]✔[/green]  Cache cleared for [bold]{folder_name}[/bold]\n"
            f"  [dim]{cache_file}[/dim]\n"
        )
    else:
        console.print(
            f"  [dim]No cache found for [bold]{folder_name}[/bold] — nothing to clear.[/dim]\n"
        )

    console.print("  Starting wizard with fresh settings…\n")
    _run_wizard(preset_path=input_path)


def _run_watch(path: Optional[str], focus_path: str = "") -> None:
    """
    Watch mode — auto incremental update on every file save.

    Flow:
      No cache  →  wizard runs (user sets settings) → generation → watch starts
      Cache exists → watch starts immediately (settings loaded from cache)
      Ctrl+C    →  stop + show reset hint
    """
    from repoview.watcher import watch, WATCHDOG_AVAILABLE
    from repoview.differ import incremental_update
    from repoview.core import collect_folder

    _banner()

    if not WATCHDOG_AVAILABLE:
        console.print(
            "[red]✗[/red] watchdog is not installed.\n"
            "  Run:  [bold]pip install watchdog[/bold]\n"
        )
        raise typer.Exit(1)

    input_path  = os.path.abspath(path or os.getcwd())
    folder_name = os.path.basename(input_path.rstrip("/\\"))

    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    # ── Check cache ───────────────────────────────────────────────────────────
    cached = load_cache(input_path)

    if cached is None or not os.path.exists(cached.output_path):
        # ── First time: run full wizard so user controls settings ─────────────
        console.print(
            "  [bold yellow]First time setup[/bold yellow]\n"
            "  [dim]No previous context found for this project.\n"
            "  The wizard will run once so you can choose your settings.\n"
            "  Watch mode will start automatically after generation.[/dim]\n"
        )

        # Run the wizard — it saves cache on completion
        _run_wizard(preset_path=input_path)

        # Reload cache written by generate_context inside wizard
        cached = load_cache(input_path)
        if cached is None:
            console.print(
                "\n[red]✗[/red] Cache not found after generation.\n"
                "  [dim]Cannot start watch mode.[/dim]\n"
            )
            raise typer.Exit(1)

        console.print()
        console.print(
            "  [bold #7c3aed]✔  Generation complete — starting watch mode[/bold #7c3aed]\n"
        )

    # ── Load settings from cache ──────────────────────────────────────────────
    output_path  = cached.output_path
    skip_docs    = cached.settings.get("skip_docs",         True)
    skip_tests   = cached.settings.get("skip_tests",        True)
    respect_gi   = cached.settings.get("respect_gitignore", True)
    # --focus flag overrides cached focus_path (user may change it)
    _watch_focus = focus_path or cached.settings.get("focus_path", "")

    # Build a readable settings summary line
    setting_parts = []
    if _watch_focus: setting_parts.append(f"focus: {_watch_focus}")
    if skip_docs:   setting_parts.append("docs skipped")
    else:           setting_parts.append("docs included")
    if skip_tests:  setting_parts.append("tests skipped")
    else:           setting_parts.append("tests included")
    if respect_gi:  setting_parts.append("gitignore respected")
    else:           setting_parts.append("gitignore ignored")
    settings_line = "  •  ".join(setting_parts)

    # ── Print watch header ────────────────────────────────────────────────────
    console.print(
        Panel.fit(
            Text.from_markup(
                f"[bold #7c3aed]👁  Watching[/]  [bold]{folder_name}/[/bold]\n"
                f"[dim]Output    →  {output_path}[/dim]\n"
                f"[dim]Settings  →  {settings_line}[/dim]\n"
                f"[dim]Press Ctrl+C to stop[/dim]"
            ),
            border_style="#7c3aed",
            padding=(0, 2),
        )
    )
    console.print()

    # ── Shared state ──────────────────────────────────────────────────────────
    _lock    = threading.Lock()
    _running = threading.Event()
    _running.set()

    def _on_change(changed_paths: List[str]) -> None:
        """Called from watcher thread after debounce."""
        if not _running.is_set():
            return

        now = time.strftime("%H:%M:%S")

        if len(changed_paths) == 1:
            console.print(
                f"  [dim]{now}[/dim]  "
                f"[yellow]{changed_paths[0]}[/yellow] changed"
            )
        else:
            console.print(
                f"  [dim]{now}[/dim]  "
                f"[yellow]{changed_paths[0]}[/yellow]  "
                f"[dim]+ {len(changed_paths)-1} more[/dim] changed"
            )

        # Reload cache — may have been updated by a previous cycle
        current_cache = load_cache(input_path)
        if current_cache is None:
            console.print(
                f"  [dim]{now}[/dim]  "
                f"[red]✗[/red] Cache lost — "
                f"run [bold]repoview --reset {input_path}[/bold] to reinitialise."
            )
            return

        # Diff + process only affected files
        entries = collect_folder(input_path, respect_gitignore=respect_gi)
        diff    = diff_cache(current_cache, entries)

        if not diff.has_changes:
            # File was touched but content unchanged (e.g. editor auto-save)
            return

        affected = set(diff.modified) | set(diff.added)
        for e in entries:
            if not e.is_dir and e.relative_path in affected:
                e.process(skip_docs=skip_docs, skip_tests=skip_tests, focus_path=_watch_focus)

        with _lock:
            try:
                upd = incremental_update(
                    project_path=input_path,
                    cache=current_cache,
                    diff=diff,
                    all_entries=entries,
                )
                pct   = upd.total_tokens / TOKEN_BUDGET * 100
                color = "green" if pct < 75 else "yellow" if pct < 95 else "red"
                console.print(
                    f"  [dim]{now}[/dim]  "
                    f"[green]✔[/green] "
                    f"Updated in [bold]{upd.elapsed:.1f}s[/bold]  "
                    f"[{color}]{upd.total_tokens:,}[/{color}] tokens  "
                    f"[dim](+{upd.files_added} ✎{upd.files_updated} -{upd.files_removed})[/dim]"
                )
                for w in upd.warnings:
                    console.print(f"  [yellow]⚠[/yellow]  {w}")

            except Exception as e:
                console.print(
                    f"  [dim]{now}[/dim]  [red]✗ Update failed:[/red] {e}"
                )

    # ── Start watcher (blocks until Ctrl+C) ───────────────────────────────────
    try:
        watch(input_path, on_change=_on_change)
    except KeyboardInterrupt:
        pass
    finally:
        _running.clear()

    # ── Ctrl+C — show clear guidance ──────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            Text.from_markup(
                "[bold]Watch stopped.[/bold]\n\n"
                f"[dim]Settings used:  {settings_line}[/dim]\n"
                f"[dim]Output:         {output_path}[/dim]\n\n"
                "To resume watching with the [bold]same settings[/bold]:\n"
                f"  [bold cyan]repoview --watch {input_path}[/bold cyan]\n\n"
                "To change settings, reset the cache first:\n"
                f"  [bold cyan]repoview --reset {input_path}[/bold cyan]\n"
                f"  [bold cyan]repoview --watch {input_path}[/bold cyan]"
            ),
            border_style="dim",
            padding=(0, 2),
        )
    )
    console.print()