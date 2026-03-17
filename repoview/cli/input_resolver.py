"""Input resolution for GitHub URLs, ZIP files, and folders."""

import os
import shutil
import tempfile
import zipfile as _zf
from typing import Optional, Tuple

import typer
from rich.progress import Progress

from repoview.cli.ui import console, create_progress, ask, CC_STYLE
from repoview.github import (
    parse_github_url,
    fetch_branches,
    download_zip,
    GitHubError,
)
import questionary


def resolve_input(raw: Optional[str]) -> Tuple[str, str, Optional[str]]:
    """
    Resolve any input to (input_path, folder_name, temp_dir_or_None).

    Handles:
      - GitHub URL / shorthand  → fetch branches → download zip → extract
      - ZIP file path           → extract to temp
      - Folder path             → use as-is
      - None                    → current directory

    Caller must shutil.rmtree(temp_dir) when done if temp_dir is not None.
    """
    # GitHub URL or shorthand
    if raw:
        gh = parse_github_url(raw)
        if gh:
            return _resolve_github(gh)

    # Resolve to absolute path
    resolved = os.path.abspath(os.path.expanduser(raw)) if raw else os.getcwd()

    # ZIP file
    if resolved.lower().endswith(".zip"):
        return _resolve_zip(resolved)

    # Plain folder
    if not os.path.exists(resolved):
        console.print(
            f"\n[red]✗[/red] Path not found: [bold]{resolved}[/bold]\n"
        )
        raise typer.Exit(1)
    folder_name = os.path.basename(resolved.rstrip("/\\"))
    return resolved, folder_name, None


def _resolve_github(gh) -> Tuple[str, str, str]:
    """Resolve GitHub URL to local path."""
    console.print(
        f"  [dim]GitHub repository:[/dim] "
        f"[bold #7c3aed]{gh.owner}/{gh.repo}[/bold #7c3aed]\n"
    )

    # Fetch branches
    branches = []
    try:
        console.print("  [dim]Fetching branches…[/dim]")
        branches = fetch_branches(gh)
        console.print()
    except GitHubError:
        console.print()

    if branches:
        default_branch = gh.branch if gh.branch in branches else branches[0]
        choices = [
            questionary.Choice(
                f"{b}  [dim](default)[/dim]" if b == default_branch else b,
                value=b,
            )
            for b in branches[:10]
        ]
        choices.append(questionary.Choice("✏️   Enter branch manually…", value="__manual__"))

        selected = ask(
            questionary.select,
            message=f"Select branch for {gh.owner}/{gh.repo}:",
            choices=choices,
            default=default_branch,
            style=CC_STYLE,
        )
    else:
        selected = "__manual__"

    if selected == "__manual__":
        selected = ask(
            questionary.text,
            message="Branch name:",
            default=gh.branch,
            style=CC_STYLE,
        )
        if not selected or not selected.strip():
            selected = "main"

    gh.branch = selected.strip()
    console.print()

    # Download
    tmp = tempfile.mkdtemp(prefix="repoview_")
    zip_path = os.path.join(tmp, f"{gh.repo}.zip")

    with create_progress() as prog:
        task = prog.add_task(
            f"Downloading {gh.owner}/{gh.repo} [{gh.branch}]…",
            total=None,
        )

        def _dl_cb(done: int, total: int) -> None:
            if total:
                prog.update(
                    task, completed=done, total=total,
                    description=(
                        f"Downloading [dim]{done//1024:,} KB"
                        f" / {total//1024:,} KB[/dim]"
                    ),
                )

        try:
            download_zip(gh, zip_path, progress_cb=_dl_cb)
        except GitHubError as e:
            shutil.rmtree(tmp, ignore_errors=True)
            console.print(f"\n[red]✗[/red]  {e}\n")
            raise typer.Exit(1)

    console.print(
        f"  [green]✔[/green]  Downloaded  "
        f"[bold]{gh.owner}/{gh.repo}[/bold]  "
        f"[dim]branch: {gh.branch}[/dim]\n"
    )

    # Extract
    extract_dir = os.path.join(tmp, "src")
    os.makedirs(extract_dir, exist_ok=True)
    with _zf.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    os.remove(zip_path)

    entries = os.listdir(extract_dir)
    if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
        input_path = os.path.join(extract_dir, entries[0])
    else:
        input_path = extract_dir

    return input_path, gh.repo, tmp


def _resolve_zip(resolved: str) -> Tuple[str, str, str]:
    """Resolve ZIP file to extracted path."""
    if not os.path.isfile(resolved):
        console.print(
            f"\n[red]✗[/red] ZIP file not found: [bold]{resolved}[/bold]\n"
        )
        raise typer.Exit(1)
    
    folder_name = os.path.splitext(os.path.basename(resolved))[0]
    console.print(
        f"  [dim]Extracting[/dim] "
        f"[bold]{os.path.basename(resolved)}[/bold][dim]…[/dim]\n"
    )
    
    tmp = tempfile.mkdtemp(prefix="repoview_")
    try:
        with _zf.ZipFile(resolved, "r") as zf:
            zf.extractall(tmp)
    except _zf.BadZipFile:
        shutil.rmtree(tmp, ignore_errors=True)
        console.print(
            f"\n[red]✗[/red] Not a valid ZIP file: "
            f"[bold]{resolved}[/bold]\n"
        )
        raise typer.Exit(1)
    
    entries = os.listdir(tmp)
    if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
        input_path = os.path.join(tmp, entries[0])
    else:
        input_path = tmp
    
    return input_path, folder_name, tmp
