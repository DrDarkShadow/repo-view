"""Post-completion and interactive menus."""

import os
import typer
import questionary

from repoview.cli.ui import console, ask, CC_STYLE, copy_text, copy_file, open_folder
from repoview.core import GenerateResult


def post_menu(result: GenerateResult) -> None:
    """Show post-completion menu with actions."""
    while True:
        action = ask(
            questionary.select,
            message="What do you want to do next?",
            choices=[
                questionary.Choice("📋  Copy text to clipboard   (paste into Claude / ChatGPT)", value="copy_text"),
                questionary.Choice("📄  Copy file to clipboard   (paste the file itself)", value="copy_file"),
                questionary.Choice("📁  Open output folder       (in Explorer / Finder)", value="open_folder"),
                questionary.Choice("🔁  Run again                (same project, new settings)", value="run_again"),
                questionary.Choice("❌  Exit", value="exit"),
            ],
            style=CC_STYLE,
        )

        if action == "copy_text":
            copy_text(result.output_path)

        elif action == "copy_file":
            copy_file(result.output_path)

        elif action == "open_folder":
            open_folder(os.path.dirname(result.output_path))

        elif action == "run_again":
            console.print()
            from repoview.cli.wizard import run_wizard
            run_wizard(preset_path=os.path.dirname(result.output_path))
            return

        elif action == "exit":
            console.print("\n[dim]Bye![/dim]\n")
            raise typer.Exit(0)

        console.print()


def post_menu_from_path(output_path: str) -> None:
    """Post menu when we have a path but no fresh GenerateResult."""
    gr = GenerateResult(output_path=output_path, total_tokens=0)
    post_menu(gr)
