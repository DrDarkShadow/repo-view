"""Interactive wizard for repoview."""

import os
import shutil
import threading
import time
from typing import Optional

import questionary
import typer
from rich.table import Table

from repoview.cache import load_cache, diff_cache
from repoview.cli.input_resolver import resolve_input
from repoview.cli.menus import post_menu, post_menu_from_path
from repoview.cli.ui import (
    console,
    banner,
    show_scan,
    ask,
    CC_STYLE,
    print_update_result,
    print_result,
    auto_copy as _auto_copy,
    create_progress,
)
from repoview.config import TOKEN_BUDGET
from repoview.core import generate_context, collect_folder, GenerateResult
from repoview.differ import incremental_update
from repoview.error_handler import error_handler, safe_execute, FileAccessError
from repoview.scanner import scan_project


@error_handler("running wizard")
def run_wizard_for_watch(preset_path: Optional[str] = None) -> None:
    """Run the wizard for watch mode - skips post menu."""
    run_wizard(preset_path=preset_path, auto_copy=False, skip_post_menu=True)


@error_handler("running wizard")
def run_wizard(preset_path: Optional[str] = None, auto_copy: bool = False, skip_post_menu: bool = False) -> None:  # noqa: F811
    """Run the interactive wizard."""
    banner()

    # Resolve input
    if preset_path:
        input_path, folder_name, _temp_dir = resolve_input(preset_path)
    else:
        raw_input = ask(
            questionary.text,
            message="Project path, ZIP file, or GitHub URL:",
            default=os.getcwd(),
            style=CC_STYLE,
        )
        console.print()
        input_path, folder_name, _temp_dir = resolve_input(raw_input.strip() or None)

    # Scan
    scan = scan_project(input_path)
    show_scan(scan, folder_name)

    # Check if it's a zip (no cache for zips)
    is_zip = _temp_dir is not None

    # Diff check (folders only)
    if not is_zip:
        cached = load_cache(input_path)
        if cached and os.path.exists(cached.output_path):
            did_incremental = _try_incremental(input_path, cached, scan)
            if did_incremental:
                if _temp_dir:
                    shutil.rmtree(_temp_dir, ignore_errors=True)
                return

    # Q1: Skip docs?
    doc_info = (
        f"(.md  .txt  .rst  .mdx)  "
        f"[dim]{scan.doc_file_count} files found[/dim]"
        if scan.doc_file_count else "(.md  .txt  .rst  .mdx)"
    )
    console.print(
        "  [dim]These are README, notes, and documentation files.\n"
        "  Skip them to keep context focused on actual code.[/dim]\n"
    )
    skip_docs = ask(
        questionary.confirm,
        message=f"Skip documentation files?  {doc_info}",
        default=True,
        style=CC_STYLE,
    )
    console.print()

    # Q2: Skip tests?
    skip_tests = False
    if scan.has_test_files:
        console.print(
            "  [dim]Test files match patterns like:  "
            "test_*.py  •  *.test.js  •  *.spec.ts  •  /tests/\n"
            "  Skip them for feature/bug context. Include for test coverage understanding.[/dim]\n"
        )
        skip_tests = ask(
            questionary.confirm,
            message=f"Skip test files?  [dim]{scan.test_file_count} found[/dim]",
            default=True,
            style=CC_STYLE,
        )
        console.print()

    # Q3: Respect .gitignore?
    respect_gitignore = True
    if scan.has_gitignore:
        console.print(
            f"  [dim].gitignore found with {scan.gitignore_rules} rules.\n"
            "  Respecting it will exclude node_modules, .env, dist, build, etc.[/dim]\n"
        )
        respect_gitignore = ask(
            questionary.confirm,
            message="Respect .gitignore?",
            default=True,
            style=CC_STYLE,
        )
        console.print()

    # Q4: Output filename
    default_name = f"{folder_name}-context.txt"
    console.print(
        f"  [dim]This file will contain your full LLM context.\n"
        f"  Leave blank to use the default: [bold]{default_name}[/bold][/dim]\n"
    )
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

    # Q5: Output location
    inside_path = os.path.join(input_path, out_name)
    parent_path = os.path.join(os.path.dirname(input_path), out_name)

    console.print("  [dim]Where should the output file be saved?[/dim]\n")
    loc_choice = ask(
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
        raw_loc = ask(
            questionary.path,
            message="Enter output folder path:",
            only_directories=True,
            style=CC_STYLE,
        )
        output_path = os.path.join(
            os.path.abspath(os.path.expanduser(raw_loc)), out_name
        )
    console.print()

    # Confirm summary
    _print_summary(
        input_path, output_path, skip_docs, skip_tests,
        respect_gitignore, scan,
    )

    go = ask(
        questionary.confirm,
        message="Generate context file?",
        default=True,
        style=CC_STYLE,
    )
    if not go:
        console.print("\n[yellow]Cancelled.[/yellow]\n")
        raise typer.Exit(0)
    console.print()

    # Execute
    result = _execute(
        input_path=input_path,
        output_path=output_path,
        skip_docs=skip_docs,
        skip_tests=skip_tests,
        respect_gitignore=respect_gitignore,
    )

    # Cleanup temp dir
    if _temp_dir:
        shutil.rmtree(_temp_dir, ignore_errors=True)

    if result:
        if auto_copy:
            _auto_copy(result.output_path)
        if not skip_post_menu:
            post_menu(result)


def _try_incremental(input_path: str, cached, scan) -> bool:
    """Try automatic incremental update. Returns True if handled."""
    entries = collect_folder(
        input_path,
        respect_gitignore=cached.settings.get("respect_gitignore", True),
    )
    diff = diff_cache(cached, entries)

    # No changes
    if not diff.has_changes:
        console.print(
            f"  [green]✔[/green]  Context is already up to date  "
            f"[dim]({cached.age_human()})[/dim]\n"
        )
        post_menu_from_path(cached.output_path)
        return True

    # Show changes
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

    # Auto incremental update
    skip_docs = cached.settings.get("skip_docs", True)
    skip_tests = cached.settings.get("skip_tests", True)

    affected_rels = set(diff.modified) | set(diff.added)
    for e in entries:
        if not e.is_dir and e.relative_path in affected_rels:
            e.process(skip_docs=skip_docs, skip_tests=skip_tests)

    start = time.time()
    with create_progress() as prog:
        task = prog.add_task(
            f"Updating {diff.total_changes} file(s)…",
            total=diff.total_changes,
        )
        done_box = [0]
        result_box = [None]
        error_box = [None]

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

    upd = result_box[0]
    print_update_result(upd, time.time() - start)

    gr = GenerateResult(
        output_path=upd.output_path,
        total_tokens=upd.total_tokens,
        warnings=upd.warnings,
    )
    post_menu(gr)
    return True


def _print_summary(input_path, output_path, skip_docs, skip_tests,
                   respect_gitignore, scan) -> None:
    """Print confirmation summary."""
    skipped = []
    if skip_docs:
        skipped.append("docs")
    if skip_tests:
        skipped.append("tests")
    skip_str = ", ".join(skipped) if skipped else "nothing"

    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="dim", justify="right", min_width=14)
    table.add_column()
    table.add_row("Source", f"[bold]{input_path}[/bold]")
    table.add_row("Output", f"[bold]{output_path}[/bold]")
    table.add_row("Skipping", f"[cyan]{skip_str}[/cyan]")
    if scan.has_gitignore:
        table.add_row(
            ".gitignore",
            "[green]respected[/green]" if respect_gitignore else "[yellow]ignored[/yellow]",
        )

    from rich.panel import Panel
    console.print(Panel(table, title="[bold]Ready to generate[/bold]",
                        border_style="#7c3aed", padding=(0, 1)))
    console.print()


def _execute(
    input_path: str,
    output_path: str,
    skip_docs: bool,
    skip_tests: bool,
    respect_gitignore: bool,
    focus_path: str = "",
) -> Optional[GenerateResult]:
    """Execute generation with progress bar."""
    state = {"done": 0, "total": 0}

    def _cb(done: int, total: int) -> None:
        state["done"] = done
        state["total"] = total

    result_box = [None]
    error_box = [None]

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

    with create_progress() as prog:
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
    print_result(result, elapsed)
    return result
