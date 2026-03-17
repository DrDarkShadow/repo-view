"""Main CLI entry point for repoview."""

from typing import Optional

import typer

from repoview import __version__
from repoview.cli.ui import console
from repoview.error_handler import cli_error_handler

app = typer.Typer(
    name="repoview",
    help="Turn any codebase into LLM-ready context — in seconds.",
    add_completion=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
@cli_error_handler
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
    copy: bool = typer.Option(
        False, "--copy", "-c",
        help="After generating, auto-copy the output text to clipboard.",
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

    # Import modes here to avoid circular imports
    from repoview.cli.modes import run_quick, run_reset, run_focus, run_watch
    from repoview.cli.info_mode import run_info
    from repoview.cli.wizard import run_wizard

    if reset:
        run_reset(path)
    elif info:
        run_info(path)
    elif watch and focus:
        run_watch(path, focus_path=focus)
    elif watch:
        run_watch(path)
    elif focus:
        run_focus(path, focus_path=focus)
    elif quick:
        run_quick(path, auto_copy_flag=copy)
    else:
        run_wizard(preset_path=path, auto_copy=copy)
