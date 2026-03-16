"""
codecontext CLI — interactive, vite-style developer experience.

Usage:
    cc                  # full interactive wizard (recommended)
    cc run [PATH]       # non-interactive, run on a path
    cc --version        # show version
    cc --help
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

import questionary
import typer
from questionary import Style
from rich import print as rprint
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

from codecontext import __version__
from codecontext.config import (
    CATEGORY_LABELS,
    DEFAULT_TOKEN_BUDGET,
    PRIORITY_ESSENTIAL,
    PRIORITY_GENERAL_CODE,
    PRIORITY_GENERAL_TEXT,
    PRIORITY_IMPORTANT_CODE,
    PRIORITY_METADATA_ONLY,
    PRIORITY_SUPPORTING_TEXT_CONFIG,
    TOKEN_BUDGETS,
)
from codecontext.core import generate_context

# ─────────────────────────────────────────────────────────────────────────────
# Typer app
# ─────────────────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="codecontext",
    help="Generate LLM-ready context files from your codebase — interactively.",
    add_completion=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
)

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Style (mimics Vite's questionary theme)
# ─────────────────────────────────────────────────────────────────────────────

CC_STYLE = Style(
    [
        ("qmark", "fg:#7c3aed bold"),
        ("question", "bold"),
        ("answer", "fg:#7c3aed bold"),
        ("pointer", "fg:#7c3aed bold"),
        ("highlighted", "fg:#7c3aed bold"),
        ("selected", "fg:#06b6d4"),
        ("separator", "fg:#444444"),
        ("instruction", "fg:#888888"),
        ("text", ""),
        ("disabled", "fg:#444444 italic"),
    ]
)

PRIORITY_MAP = {
    "essential": PRIORITY_ESSENTIAL,
    "code": PRIORITY_IMPORTANT_CODE,
    "config": PRIORITY_SUPPORTING_TEXT_CONFIG,
    "general_code": PRIORITY_GENERAL_CODE,
    "general_text": PRIORITY_GENERAL_TEXT,
}


# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────

def _print_banner() -> None:
    console.print()
    console.print(
        Panel.fit(
            Text.from_markup(
                f"[bold #7c3aed]codecontext[/]  [dim]v{__version__}[/]\n"
                "[dim]Generate LLM-ready context from your codebase[/]"
            ),
            border_style="#7c3aed",
            padding=(0, 2),
        )
    )
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Interactive wizard
# ─────────────────────────────────────────────────────────────────────────────

def _run_wizard() -> None:
    """Vite-style interactive prompt sequence."""
    _print_banner()

    # ── 1. Source path ───────────────────────────────────────────────────────
    source_choice = questionary.select(
        "Where is your project?",
        choices=[
            questionary.Choice("Current directory  (.)", value="cwd"),
            questionary.Choice("Specify a folder path", value="folder"),
            questionary.Choice("Select a ZIP file", value="zip"),
        ],
        style=CC_STYLE,
    ).ask()

    if source_choice is None:
        _abort()

    if source_choice == "cwd":
        input_path = os.getcwd()
    elif source_choice == "folder":
        raw = questionary.path(
            "Path to project folder:",
            only_directories=True,
            style=CC_STYLE,
        ).ask()
        if not raw:
            _abort()
        input_path = os.path.abspath(os.path.expanduser(raw))
    else:  # zip
        raw = questionary.path(
            "Path to ZIP file:",
            style=CC_STYLE,
        ).ask()
        if not raw:
            _abort()
        input_path = os.path.abspath(os.path.expanduser(raw))

    if not os.path.exists(input_path):
        console.print(f"\n[red]✗[/red] Path not found: [bold]{input_path}[/bold]\n")
        raise typer.Exit(1)

    # ── 2. File categories ───────────────────────────────────────────────────
    console.print()
    selected_cats = questionary.checkbox(
        "Which file categories to include?",
        choices=[
            questionary.Choice(
                title=CATEGORY_LABELS["essential"],
                value="essential",
                checked=True,
            ),
            questionary.Choice(
                title=CATEGORY_LABELS["code"],
                value="code",
                checked=True,
            ),
            questionary.Choice(
                title=CATEGORY_LABELS["config"],
                value="config",
                checked=True,
            ),
            questionary.Choice(
                title=CATEGORY_LABELS["general_code"],
                value="general_code",
                checked=False,
            ),
            questionary.Choice(
                title=CATEGORY_LABELS["general_text"],
                value="general_text",
                checked=False,
            ),
        ],
        style=CC_STYLE,
        instruction="(Space to toggle, Enter to confirm)",
    ).ask()

    if selected_cats is None:
        _abort()

    include_categories = (
        {PRIORITY_MAP[c] for c in selected_cats} if selected_cats else None
    )

    # ── 3. .gitignore ────────────────────────────────────────────────────────
    console.print()
    gitignore_choice = questionary.select(
        "How should .gitignore be handled?",
        choices=[
            questionary.Choice(
                "Respect .gitignore  (recommended)", value="respect"
            ),
            questionary.Choice(
                "Include everything  (ignore .gitignore)", value="ignore"
            ),
        ],
        style=CC_STYLE,
    ).ask()

    if gitignore_choice is None:
        _abort()
    respect_gitignore = gitignore_choice == "respect"

    # ── 4. Token budget ──────────────────────────────────────────────────────
    console.print()
    budget_label = questionary.select(
        "Token budget?",
        choices=list(TOKEN_BUDGETS.keys()),
        default="Claude 3.5 (800k)",
        style=CC_STYLE,
    ).ask()

    if budget_label is None:
        _abort()

    if TOKEN_BUDGETS[budget_label] is None:  # Custom
        raw_budget = questionary.text(
            "Enter token limit (e.g. 500000):",
            validate=lambda v: v.isdigit() and int(v) > 0,
            style=CC_STYLE,
        ).ask()
        if raw_budget is None:
            _abort()
        token_budget = int(raw_budget)
    else:
        token_budget = TOKEN_BUDGETS[budget_label]

    # ── 5. Output file ───────────────────────────────────────────────────────
    console.print()
    base_name = os.path.splitext(os.path.basename(input_path.rstrip("/\\")))[0]
    default_out = f"{base_name}_context.txt"
    output_raw = questionary.text(
        "Output file name:",
        default=default_out,
        style=CC_STYLE,
    ).ask()

    if output_raw is None:
        _abort()

    output_path = os.path.abspath(os.path.expanduser(output_raw))

    # ── 6. Confirm & run ─────────────────────────────────────────────────────
    console.print()
    _print_run_summary(input_path, output_path, token_budget, respect_gitignore)
    console.print()

    go = questionary.confirm(
        "Generate context file?", default=True, style=CC_STYLE
    ).ask()
    if not go:
        console.print("\n[yellow]Cancelled.[/yellow]\n")
        raise typer.Exit(0)

    console.print()
    _execute(
        input_path=input_path,
        output_path=output_path,
        token_budget=token_budget,
        include_categories=include_categories,
        respect_gitignore=respect_gitignore,
    )


def _print_run_summary(
    input_path: str,
    output_path: str,
    token_budget: int,
    respect_gitignore: bool,
) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim", justify="right")
    table.add_column()
    table.add_row("Source", f"[bold]{input_path}[/bold]")
    table.add_row("Output", f"[bold]{output_path}[/bold]")
    table.add_row("Token budget", f"[bold]{token_budget:,}[/bold]")
    table.add_row(
        ".gitignore", "[green]respected[/green]" if respect_gitignore else "[yellow]ignored[/yellow]"
    )
    console.print(table)


def _execute(
    input_path: str,
    output_path: str,
    token_budget: int,
    include_categories,
    respect_gitignore: bool,
) -> None:
    progress_state = {"processed": 0, "total": 0}

    def _cb(processed: int, total: int) -> None:
        progress_state["processed"] = processed
        progress_state["total"] = total

    start = time.time()

    with Progress(
        SpinnerColumn(spinner_name="dots", style="#7c3aed"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30, complete_style="#7c3aed", finished_style="#06b6d4"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Analysing files…", total=None)

        import threading

        result_holder: list = [None]
        error_holder: list = [None]

        def _worker():
            try:
                result_holder[0] = generate_context(
                    input_path=input_path,
                    output_filepath=output_path,
                    token_budget=token_budget,
                    include_categories=include_categories,
                    respect_gitignore=respect_gitignore,
                    progress_callback=_cb,
                )
            except Exception as e:
                error_holder[0] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

        while t.is_alive():
            p, tot = progress_state["processed"], progress_state["total"]
            if tot:
                progress.update(
                    task,
                    completed=p,
                    total=tot,
                    description=f"Analysing files… [dim]({p}/{tot})[/dim]",
                )
            time.sleep(0.05)
        t.join()

    if error_holder[0]:
        console.print(f"\n[red]✗[/red] Error: {error_holder[0]}\n")
        raise typer.Exit(1)

    result = result_holder[0]
    elapsed = time.time() - start

    _print_result(result, elapsed)


def _print_result(result, elapsed: float) -> None:
    console.print(
        f"[bold green]✔[/bold green] Done in [bold]{elapsed:.1f}s[/bold]"
    )
    console.print()

    pct = (result.total_tokens / result.token_budget * 100) if result.token_budget else 0
    bar_len = 30
    filled = int(bar_len * pct / 100)
    bar_color = "green" if pct < 80 else "yellow" if pct < 100 else "red"
    bar = f"[{bar_color}]{'█' * filled}[/{bar_color}][dim]{'░' * (bar_len - filled)}[/dim]"

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim", justify="right")
    table.add_column()
    table.add_row(
        "Output",
        f"[bold cyan]{result.output_path}[/bold cyan]",
    )
    table.add_row(
        "Tokens",
        f"{bar}  [bold]{result.total_tokens:,}[/bold] / {result.token_budget:,}  "
        f"[dim]({pct:.1f}%)[/dim]",
    )
    table.add_row("Full files", f"[green]{result.files_full}[/green]")
    table.add_row("Summary", f"[yellow]{result.files_summary}[/yellow]")
    table.add_row("Metadata", f"[dim]{result.files_metadata}[/dim]")
    table.add_row("Omitted", f"[red]{result.files_omitted}[/red]" if result.files_omitted else "0")

    console.print(table)

    for w in result.warnings:
        console.print(f"[yellow]⚠[/yellow]  {w}")

    console.print()


def _abort() -> None:
    console.print("\n[yellow]Cancelled.[/yellow]\n")
    raise typer.Exit(0)


# ─────────────────────────────────────────────────────────────────────────────
# CLI commands
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit.", is_eager=True
    ),
) -> None:
    """
    [bold #7c3aed]codecontext[/bold #7c3aed] — Generate LLM-ready context from your codebase.

    Run [bold]cc[/bold] with no arguments to start the interactive wizard.
    """
    if version:
        console.print(f"codecontext v{__version__}")
        raise typer.Exit(0)

    if ctx.invoked_subcommand is None:
        _run_wizard()


@app.command("run")
def run_cmd(
    path: Optional[str] = typer.Argument(
        None, help="Project folder or ZIP file. Defaults to current directory."
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path."
    ),
    budget: int = typer.Option(
        DEFAULT_TOKEN_BUDGET, "--budget", "-b", help="Token budget."
    ),
    no_gitignore: bool = typer.Option(
        False, "--no-gitignore", help="Include files listed in .gitignore."
    ),
) -> None:
    """
    [bold]Non-interactive[/bold] mode — run directly without prompts.

    Examples:

        cc run
        cc run ./my-project -o context.txt
        cc run ./project --budget 128000 --no-gitignore
    """
    _print_banner()

    input_path = os.path.abspath(path or os.getcwd())
    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    base = os.path.splitext(os.path.basename(input_path.rstrip("/\\")))[0]
    output_path = os.path.abspath(output or f"{base}_context.txt")

    _print_run_summary(input_path, output_path, budget, not no_gitignore)
    console.print()

    _execute(
        input_path=input_path,
        output_path=output_path,
        token_budget=budget,
        include_categories=None,
        respect_gitignore=not no_gitignore,
    )


@app.command("info")
def info_cmd() -> None:
    """Show system info and codecontext configuration."""
    _print_banner()
    try:
        import tiktoken  # noqa: F401
        tiktoken_ok = True
    except ImportError:
        tiktoken_ok = False

    try:
        import pathspec  # noqa: F401
        pathspec_ok = True
    except ImportError:
        pathspec_ok = False

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim", justify="right")
    table.add_column()
    table.add_row("version", f"[bold]{__version__}[/bold]")
    table.add_row("python", sys.version.split()[0])
    table.add_row(
        "tiktoken",
        "[green]✔ available[/green]" if tiktoken_ok else "[red]✗ missing — pip install tiktoken[/red]",
    )
    table.add_row(
        "pathspec",
        "[green]✔ available[/green]" if pathspec_ok else "[red]✗ missing — pip install pathspec[/red]",
    )
    table.add_row("default budget", f"{DEFAULT_TOKEN_BUDGET:,} tokens")
    console.print(table)
    console.print()