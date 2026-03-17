"""CLI modes: quick, info, focus, reset, watch."""

import os
import threading
import time
from typing import Optional

import questionary
import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from repoview.cache import load_cache, delete_cache, cache_path_for, diff_cache
from repoview.cli.menus import post_menu
from repoview.cli.ui import (
    console,
    banner,
    show_scan,
    ask,
    CC_STYLE,
    print_result,
    auto_copy as _auto_copy,
)
from repoview.cli.wizard import _execute
from repoview.config import TOKEN_BUDGET
from repoview.core import collect_folder
from repoview.error_handler import error_handler, FileAccessError, WatchError
from repoview.scanner import scan_project


@error_handler("quick mode")
def run_quick(path: Optional[str], auto_copy_flag: bool = False) -> None:
    """Non-interactive run with all defaults."""
    banner()
    input_path = os.path.abspath(path or os.getcwd())
    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    folder_name = os.path.basename(input_path.rstrip("/\\"))
    output_path = os.path.join(input_path, f"{folder_name}-context.txt")

    scan = scan_project(input_path)
    show_scan(scan, folder_name)

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
        if auto_copy_flag:
            _auto_copy(result.output_path)
        post_menu(result)


@error_handler("reset mode")
def run_reset(path: Optional[str]) -> None:
    """Delete cache and run wizard fresh."""
    banner()

    input_path = os.path.abspath(path or os.getcwd())
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
    from repoview.cli.wizard import run_wizard
    run_wizard(preset_path=input_path)


@error_handler("focus mode")
def run_focus(path: Optional[str], focus_path: str) -> None:
    """Focus mode - short wizard for focused context."""
    banner()

    input_path = os.path.abspath(path or os.getcwd())
    folder_name = os.path.basename(input_path.rstrip("/\\"))

    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    # Validate focus path
    focus_abs = os.path.join(input_path, focus_path.replace("/", os.sep))
    if not os.path.exists(focus_abs):
        console.print(
            f"  [red]✗[/red]  Focus path not found: [bold]{focus_path}[/bold]\n"
            f"  [dim]Looked in: {focus_abs}[/dim]\n"
        )
        raise typer.Exit(1)

    is_dir_focus = os.path.isdir(focus_abs)
    focus_type = "folder" if is_dir_focus else "file"

    # Scan
    scan = scan_project(input_path)
    show_scan(scan, folder_name)

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

    # Q1: Gitignore
    respect_gitignore = True
    if scan.has_gitignore:
        console.print(f"  [dim].gitignore found ({scan.gitignore_rules} rules).[/dim]\n")
        respect_gitignore = ask(
            questionary.confirm,
            message="Respect .gitignore?",
            default=True,
            style=CC_STYLE,
        )
        console.print()

    # Q2: Output filename
    focus_slug = focus_path.strip("/").replace("/", "-").replace(".", "-")
    default_name = f"{folder_name}-{focus_slug}-context.txt"

    console.print(f"  [dim]Default output name: [bold]{default_name}[/bold][/dim]\n")
    out_name = ask(
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

    # Q3: Output location
    inside_path = os.path.join(input_path, out_name)
    parent_path = os.path.join(os.path.dirname(input_path), out_name)

    loc_choice = ask(
        questionary.select,
        message="Save output to:",
        choices=[
            questionary.Choice(f"Inside the project folder   ({inside_path})", value="inside"),
            questionary.Choice(f"Next to the project folder  ({parent_path})", value="parent"),
            questionary.Choice("Custom path…", value="custom"),
        ],
        style=CC_STYLE,
    )

    if loc_choice == "inside":
        output_path = inside_path
    elif loc_choice == "parent":
        output_path = parent_path
    else:
        raw = ask(
            questionary.path,
            message="Enter output folder path:",
            only_directories=True,
            style=CC_STYLE,
        )
        output_path = os.path.join(os.path.abspath(os.path.expanduser(raw)), out_name)
    console.print()

    # Summary
    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=14)
    table.add_column()
    table.add_row("Source", f"[bold]{input_path}[/bold]")
    table.add_row("Focus", f"[bold #7c3aed]{focus_path}[/bold #7c3aed]")
    table.add_row("Output", f"[bold]{output_path}[/bold]")
    if scan.has_gitignore:
        table.add_row(".gitignore",
            "[green]respected[/green]" if respect_gitignore else "[yellow]ignored[/yellow]")
    console.print(Panel(table, title="[bold]Ready to generate[/bold]",
                        border_style="#7c3aed", padding=(0, 1)))
    console.print()

    go = ask(questionary.confirm, message="Generate focused context?",
              default=True, style=CC_STYLE)
    if not go:
        console.print("\n[yellow]Cancelled.[/yellow]\n")
        raise typer.Exit(0)
    console.print()

    result = _execute(
        input_path=input_path,
        output_path=output_path,
        skip_docs=False,
        skip_tests=False,
        respect_gitignore=respect_gitignore,
        focus_path=focus_path,
    )
    # Skip post menu in focus mode - user wants to continue with their work


@error_handler("watch mode")
def run_watch(path: Optional[str], focus_path: str = "") -> None:
    """Watch mode - auto incremental update on file changes."""
    from repoview.watcher import watch, WATCHDOG_AVAILABLE
    from repoview.differ import incremental_update

    banner()

    if not WATCHDOG_AVAILABLE:
        console.print(
            "[red]✗[/red] watchdog is not installed.\n"
            "  Run:  [bold]pip install watchdog[/bold]\n"
        )
        raise typer.Exit(1)

    input_path = os.path.abspath(path or os.getcwd())
    folder_name = os.path.basename(input_path.rstrip("/\\"))

    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    # Check cache
    cached = load_cache(input_path)

    if cached is None or not os.path.exists(cached.output_path):
        # First time: run wizard
        console.print(
            "  [bold yellow]First time setup[/bold yellow]\n"
            "  [dim]No previous context found for this project.\n"
            "  The wizard will run once so you can choose your settings.\n"
            "  Watch mode will start automatically after generation.[/dim]\n"
        )

        from repoview.cli.wizard import run_wizard_for_watch
        run_wizard_for_watch(preset_path=input_path)

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

    # Load settings
    output_path = cached.output_path
    skip_docs = cached.settings.get("skip_docs", True)
    skip_tests = cached.settings.get("skip_tests", True)
    respect_gi = cached.settings.get("respect_gitignore", True)
    _watch_focus = focus_path or cached.settings.get("focus_path", "")

    # Build settings summary
    setting_parts = []
    if _watch_focus:
        setting_parts.append(f"focus: {_watch_focus}")
    if skip_docs:
        setting_parts.append("docs skipped")
    else:
        setting_parts.append("docs included")
    if skip_tests:
        setting_parts.append("tests skipped")
    else:
        setting_parts.append("tests included")
    if respect_gi:
        setting_parts.append("gitignore respected")
    else:
        setting_parts.append("gitignore ignored")
    settings_line = "  •  ".join(setting_parts)

    # Print watch header
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

    # Shared state
    _lock = threading.Lock()
    _running = threading.Event()
    _running.set()

    def _on_change(changed_paths) -> None:
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

        current_cache = load_cache(input_path)
        if current_cache is None:
            console.print(
                f"  [dim]{now}[/dim]  "
                f"[red]✗[/red] Cache lost — "
                f"run [bold]repoview --reset {input_path}[/bold] to reinitialise."
            )
            return

        entries = collect_folder(input_path, respect_gitignore=respect_gi)
        diff = diff_cache(current_cache, entries)

        if not diff.has_changes:
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
                pct = upd.total_tokens / TOKEN_BUDGET * 100
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

    # Start watcher
    try:
        watch(input_path, on_change=_on_change)
    except KeyboardInterrupt:
        pass
    finally:
        _running.clear()

    # Ctrl+C - show guidance
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
