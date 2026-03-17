"""Info mode - deep project inspection without generation."""

import os
from collections import defaultdict

import typer
from rich.panel import Panel
from rich.table import Table

from repoview.cache import load_cache
from repoview.cli.ui import console, banner
from repoview.config import (
    IMPORTANT_CODE_EXTS,
    SUPPORTING_CONFIG_EXTS,
    GENERAL_CODE_EXTS,
    DOC_EXTS,
    TOKEN_BUDGET,
    EXCLUDE_DIRS,
    METADATA_ONLY_EXTS,
    ESSENTIAL_FILENAMES,
)
from repoview.error_handler import error_handler
from repoview.scanner import scan_project


@error_handler("info mode")
def run_info(path: str = None) -> None:
    """Deep project inspection - no generation, no questions."""
    banner()

    input_path = os.path.abspath(path or os.getcwd())
    folder_name = os.path.basename(input_path.rstrip("/\\"))

    if not os.path.exists(input_path):
        console.print(f"[red]✗[/red] Path not found: {input_path}")
        raise typer.Exit(1)

    console.print(f"  [dim]Deep scanning[/dim] [bold]{folder_name}[/bold][dim]…[/dim]\n")

    # Deep scan
    scan = scan_project(input_path)

    # Extra data
    largest_files = []
    largest_by_lines = []
    folder_stats = defaultdict(lambda: {"files": 0, "size": 0})
    total_lines = 0
    binary_count = 0
    essential_found = []
    exclude_lower = {d.lower() for d in EXCLUDE_DIRS}
    base = input_path

    for root, dirs, files in os.walk(base, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in exclude_lower]
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            ext = os.path.splitext(fname)[1].lower()

            if fname.lower() in ESSENTIAL_FILENAMES:
                essential_found.append(fname)

            if ext in METADATA_ONLY_EXTS:
                binary_count += 1
                continue

            try:
                size = os.path.getsize(full)
            except OSError:
                continue

            largest_files.append((size, rel))

            parts = rel.split("/")
            bucket = parts[0] if len(parts) > 1 else "(root)"
            folder_stats[bucket]["files"] += 1
            folder_stats[bucket]["size"] += size

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

    # Helper functions
    def _bar(value: int, maximum: int, width: int = 20, color: str = "#7c3aed") -> str:
        if maximum == 0:
            return ""
        filled = max(1, round(width * value / maximum)) if value else 0
        empty = width - filled
        return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"

    def _fmt_size(b: int) -> str:
        if b < 1024:
            return f"{b} B"
        if b < 1024**2:
            return f"{b/1024:.1f} KB"
        return f"{b/1024**2:.1f} MB"

    def _detect_project_type() -> str:
        exts = set(scan.ext_counter.keys())
        ef = {f.lower() for f in essential_found}
        if "package.json" in ef and (".tsx" in exts or ".jsx" in exts):
            return "React / TypeScript"
        if "package.json" in ef and ".vue" in exts:
            return "Vue.js"
        if "package.json" in ef and ".svelte" in exts:
            return "Svelte"
        if "package.json" in ef:
            return "Node.js / JavaScript"
        if "pyproject.toml" in ef or "requirements.txt" in ef:
            if "manage.py" in ef:
                return "Python / Django"
            if "fastapi" in str(ef).lower():
                return "Python / FastAPI"
            return "Python"
        if "go.mod" in ef:
            return "Go"
        if "cargo.toml" in ef:
            return "Rust"
        if "pom.xml" in ef or "build.gradle" in ef:
            return "Java / JVM"
        if ".cs" in exts:
            return "C# / .NET"
        if ".rb" in exts:
            return "Ruby"
        if ".php" in exts:
            return "PHP"
        if ".swift" in exts:
            return "Swift"
        if ".kt" in exts:
            return "Kotlin"
        return "Mixed / Unknown"

    project_type = _detect_project_type()

    # Category summary
    cat_counts = {"code": 0, "config": 0, "docs": 0, "general": 0, "other": 0}
    for ext, cnt in scan.ext_counter.items():
        if ext in IMPORTANT_CODE_EXTS:
            cat_counts["code"] += cnt
        elif ext in SUPPORTING_CONFIG_EXTS:
            cat_counts["config"] += cnt
        elif ext in DOC_EXTS:
            cat_counts["docs"] += cnt
        elif ext in GENERAL_CODE_EXTS:
            cat_counts["general"] += cnt
        else:
            cat_counts["other"] += cnt

    # PANEL 1 - Overview
    t = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    t.add_column(style="dim", justify="right", min_width=20)
    t.add_column()

    fit_color = "green" if scan.est_tokens < TOKEN_BUDGET * 0.75 else (
                "yellow" if scan.est_tokens < TOKEN_BUDGET else "red")
    fit_label = ("fits comfortably" if scan.est_tokens < TOKEN_BUDGET * 0.75 else
                 "tight fit" if scan.est_tokens < TOKEN_BUDGET else "may need trimming")

    t.add_row("Path", f"[bold]{input_path}[/bold]")
    t.add_row("Project type", f"[bold #7c3aed]{project_type}[/bold #7c3aed]")
    t.add_row("", "")
    t.add_row("Text files", f"[bold]{scan.total_files:,}[/bold]")
    t.add_row("Binary / assets", f"[dim]{binary_count}[/dim]  [dim](images, fonts, compiled — never read)[/dim]")
    t.add_row("Total size", f"[bold]{_fmt_size(scan.total_size_bytes)}[/bold]")
    t.add_row("Lines of code", f"[bold cyan]{total_lines:,}[/bold cyan]")
    t.add_row("", "")
    t.add_row("Est. tokens", f"[bold cyan]~{scan.est_tokens:,}[/bold cyan]  [dim](rough estimate before filtering)[/dim]")
    t.add_row("Token budget", f"[bold]{TOKEN_BUDGET:,}[/bold]  [{fit_color}]— {fit_label}[/{fit_color}]")

    console.print(Panel(t, title=f"[bold]  {folder_name}  [/bold]",
                        border_style="#7c3aed", padding=(0, 1)))
    console.print()

    # PANEL 2 - Essential files
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

    # PANEL 3 - File type breakdown
    if scan.ext_counter:
        top = scan.ext_counter.most_common(10)
        max_count = top[0][1] if top else 1

        ft = Table(show_header=True, box=None, padding=(0, 2), show_edge=False)
        ft.add_column("Ext", style="bold cyan", min_width=10)
        ft.add_column("Files", justify="right", min_width=6)
        ft.add_column("", min_width=22)
        ft.add_column("Category", style="dim", min_width=12)

        def _cat_label(ext: str) -> str:
            if ext in IMPORTANT_CODE_EXTS:
                return "[green]code[/green]"
            if ext in SUPPORTING_CONFIG_EXTS:
                return "[yellow]config[/yellow]"
            if ext in DOC_EXTS:
                return "[blue]docs[/blue]"
            if ext in GENERAL_CODE_EXTS:
                return "[dim]general[/dim]"
            return "[dim]other[/dim]"

        for ext, cnt in top:
            label = ext if ext else "[dim](no ext)[/dim]"
            ft.add_row(label, str(cnt), _bar(cnt, max_count), _cat_label(ext))

        if len(scan.ext_counter) > 10:
            ft.add_row(f"[dim]+{len(scan.ext_counter)-10} more[/dim]", "", "", "")

        console.print(Panel(ft, title="[bold]File Types[/bold]",
                            border_style="dim", padding=(0, 1)))
        console.print()

    # PANEL 4 - Category breakdown
    total_categorised = sum(cat_counts.values()) or 1
    cb = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    cb.add_column(style="dim", justify="right", min_width=10)
    cb.add_column(min_width=6, justify="right")
    cb.add_column(min_width=24)
    cb.add_column(style="dim", min_width=6)

    cat_colors = {
        "code": "green",
        "config": "yellow",
        "docs": "blue",
        "general": "cyan",
        "other": "dim",
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

    # PANEL 5 - Top-level folders
    if folder_stats:
        max_folder_files = max(v["files"] for v in folder_stats.values()) or 1
        fd = Table(show_header=True, box=None, padding=(0, 2), show_edge=False)
        fd.add_column("Folder", style="bold", min_width=18)
        fd.add_column("Files", justify="right", min_width=6)
        fd.add_column("", min_width=22)
        fd.add_column("Size", style="dim", justify="right", min_width=10)

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

    # PANEL 6 - Largest files
    if largest_files:
        top_files = largest_files[:8]
        max_sz = top_files[0][0] or 1
        lf = Table(show_header=True, box=None, padding=(0, 2), show_edge=False)
        lf.add_column("File", style="cyan", min_width=32)
        lf.add_column("Size", justify="right", min_width=10)
        lf.add_column("", min_width=20)

        for size, rel in top_files:
            lf.add_row(rel, _fmt_size(size), _bar(size, max_sz, 18, "#f59e0b"))

        console.print(Panel(lf, title="[bold]Largest Files[/bold]",
                            border_style="dim", padding=(0, 1)))
        console.print()

    # PANEL 7 - Longest files
    if largest_by_lines:
        top_lines = largest_by_lines[:8]
        max_ln = top_lines[0][0] or 1
        ll = Table(show_header=True, box=None, padding=(0, 2), show_edge=False)
        ll.add_column("File", style="cyan", min_width=32)
        ll.add_column("Lines", justify="right", min_width=8)
        ll.add_column("", min_width=20)

        for lines, rel in top_lines:
            ll.add_row(rel, f"{lines:,}", _bar(lines, max_ln, 18, "#06b6d4"))

        console.print(Panel(ll, title="[bold]Longest Files[/bold]",
                            border_style="dim", padding=(0, 1)))
        console.print()

    # PANEL 8 - Filtering
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

    # PANEL 9 - Cache status
    cached = load_cache(input_path)
    cs = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    cs.add_column(style="dim", justify="right", min_width=22)
    cs.add_column()

    if cached:
        output_exists = os.path.exists(cached.output_path)
        cs.add_row("Status", f"[green]● cached[/green]")
        cs.add_row("Last run", f"[bold]{cached.age_human()}[/bold]  [dim]({cached.generated_at})[/dim]")
        cs.add_row(
            "Output file",
            f"[cyan]{cached.output_path}[/cyan]  "
            + (f"[green]✔ exists[/green]" if output_exists else f"[red]✗ missing[/red]"),
        )
        settings = cached.settings
        parts = []
        if settings.get("focus_path"):
            parts.append(f"[#7c3aed]focus: {settings['focus_path']}[/#7c3aed]")
        if settings.get("skip_docs"):
            parts.append("docs skipped")
        if settings.get("skip_tests"):
            parts.append("tests skipped")
        if settings.get("respect_gitignore"):
            parts.append("gitignore respected")
        cs.add_row("Settings", "  •  ".join(parts) if parts else "[dim]defaults[/dim]")
        cs.add_row("Cached files", f"[dim]{len(cached.files)}[/dim]")

        # Changed files
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

    # Footer tip
    tip_parts = ["[bold]repoview[/bold]  — full wizard"]
    if cached and os.path.exists(cached.output_path):
        tip_parts.append("[bold]repoview --quick[/bold]  — instant regenerate")
    if scan.has_test_files or scan.doc_file_count:
        tip_parts.append("[bold]repoview --watch[/bold]  — live updates")
    console.print(
        "  [dim]Next steps:  " + "   •   ".join(tip_parts) + "[/dim]\n"
    )
