"""Output reporting formatters: rich terminal tables, JSON, and CSV."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from rich.console import Console
from rich.table import Table

from repo_language_stats.counting import (
    AggregateStats,
    LanguageStats,
    RepoStats,
    calculate_percentage,
)


def _sorted_languages(languages: dict[str, LanguageStats]) -> list[LanguageStats]:
    """Sort languages by bytes descending, then lines descending, then name ascending."""
    return sorted(
        languages.values(),
        key=lambda s: (s.total_bytes, s.total_lines, -ord(s.language[0]) if s.language else 0),
        reverse=True,
    )


def build_rich_table(
    languages: dict[str, LanguageStats],
    title: str | None = None,
    total_bytes: int | None = None,
    total_lines: int | None = None,
    show_files: bool = False,
) -> Table:
    """Build a rich Table for a dictionary of LanguageStats."""
    table = Table(
        title=title,
        title_style="bold magenta",
        header_style="bold cyan",
        show_footer=True,
    )

    table.add_column("Language", footer="TOTAL", justify="left")
    table.add_column("Bytes", justify="right")
    table.add_column("Byte %", justify="right")
    table.add_column("Lines", justify="right")
    table.add_column("Line %", justify="right")
    if show_files:
        table.add_column("Files", justify="right")

    tot_b = total_bytes if total_bytes is not None else sum(s.total_bytes for s in languages.values())
    tot_l = total_lines if total_lines is not None else sum(s.total_lines for s in languages.values())
    tot_f = sum(s.file_count for s in languages.values())

    sorted_langs = _sorted_languages(languages)

    for item in sorted_langs:
        b_pct = calculate_percentage(item.total_bytes, tot_b)
        l_pct = calculate_percentage(item.total_lines, tot_l)

        row = [
            item.language,
            f"{item.total_bytes:,}",
            f"{b_pct:.1f}%",
            f"{item.total_lines:,}",
            f"{l_pct:.1f}%",
        ]
        if show_files:
            row.append(f"{item.file_count:,}")
        table.add_row(*row)

    # Set footers
    table.columns[1].footer = f"{tot_b:,}"
    table.columns[2].footer = "100.0%" if tot_b > 0 else "0.0%"
    table.columns[3].footer = f"{tot_l:,}"
    table.columns[4].footer = "100.0%" if tot_l > 0 else "0.0%"
    if show_files:
        table.columns[5].footer = f"{tot_f:,}"

    return table


def format_table(
    stats: AggregateStats,
    per_repo: bool = False,
    show_files: bool = False,
) -> str:
    """Format AggregateStats into a styled rich terminal table string."""
    console = Console(record=True, width=100)

    console.print(f"\n[bold]GitHub Language Statistics for:[/bold] [green]{stats.username}[/green]")
    console.print(f"Repositories scanned: {stats.repos_scanned} │ Skipped: {stats.repos_skipped}\n")

    if per_repo and stats.per_repo:
        for repo in stats.per_repo:
            console.print(f"[bold yellow]Repository: {repo.repo_name}[/bold yellow]")
            if not repo.languages:
                console.print("  [italic dim]No eligible source files found.[/italic dim]\n")
            else:
                table = build_rich_table(
                    languages=repo.languages,
                    total_bytes=repo.total_bytes,
                    total_lines=repo.total_lines,
                    show_files=show_files,
                )
                console.print(table)
                console.print()

        console.print("[bold underline cyan]Aggregate Summary (All Repositories):[/bold underline cyan]")

    # Aggregate table
    agg_table = build_rich_table(
        languages=stats.aggregate,
        total_bytes=stats.total_bytes,
        total_lines=stats.total_lines,
        show_files=show_files,
    )
    console.print(agg_table)
    console.print("\n[dim]Note: Notebook (.ipynb) statistics count only code cell source text.[/dim]\n")

    return console.export_text()


def format_json(
    stats: AggregateStats,
    per_repo: bool = False,
    show_files: bool = False,
    indent: int = 2,
) -> str:
    """Format AggregateStats into JSON string."""
    tot_b = stats.total_bytes
    tot_l = stats.total_lines

    def _format_lang_list(langs: dict[str, LanguageStats], b_total: int, l_total: int) -> list[dict[str, Any]]:
        result = []
        for item in _sorted_languages(langs):
            entry: dict[str, Any] = {
                "language": item.language,
                "bytes": item.total_bytes,
                "byte_percent": calculate_percentage(item.total_bytes, b_total),
                "lines": item.total_lines,
                "line_percent": calculate_percentage(item.total_lines, l_total),
            }
            if show_files:
                entry["files"] = item.file_count
            result.append(entry)
        return result

    data: dict[str, Any] = {
        "username": stats.username,
        "repos_scanned": stats.repos_scanned,
        "repos_skipped": stats.repos_skipped,
        "total_bytes": stats.total_bytes,
        "total_lines": stats.total_lines,
        "languages": _format_lang_list(stats.aggregate, tot_b, tot_l),
    }

    if per_repo:
        per_repo_list = []
        for repo in stats.per_repo:
            repo_entry = {
                "repo_name": repo.repo_name,
                "total_bytes": repo.total_bytes,
                "total_lines": repo.total_lines,
                "languages": _format_lang_list(repo.languages, repo.total_bytes, repo.total_lines),
            }
            per_repo_list.append(repo_entry)
        data["per_repo"] = per_repo_list

    return json.dumps(data, indent=indent)


def format_csv(
    stats: AggregateStats,
    per_repo: bool = False,
    show_files: bool = False,
) -> str:
    """Format AggregateStats into CSV string."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    headers = ["language", "bytes", "byte_percent", "lines", "line_percent"]
    if per_repo:
        headers.insert(0, "repository")
    if show_files:
        headers.append("files")

    writer.writerow(headers)

    if per_repo and stats.per_repo:
        for repo in stats.per_repo:
            for item in _sorted_languages(repo.languages):
                b_pct = calculate_percentage(item.total_bytes, repo.total_bytes)
                l_pct = calculate_percentage(item.total_lines, repo.total_lines)
                row = [
                    repo.repo_name,
                    item.language,
                    item.total_bytes,
                    b_pct,
                    item.total_lines,
                    l_pct,
                ]
                if show_files:
                    row.append(item.file_count)
                writer.writerow(row)
    else:
        for item in _sorted_languages(stats.aggregate):
            b_pct = calculate_percentage(item.total_bytes, stats.total_bytes)
            l_pct = calculate_percentage(item.total_lines, stats.total_lines)
            row = [
                item.language,
                item.total_bytes,
                b_pct,
                item.total_lines,
                l_pct,
            ]
            if show_files:
                row.append(item.file_count)
            writer.writerow(row)

    return output.getvalue()


def render_report(
    stats: AggregateStats,
    fmt: str = "table",
    per_repo: bool = False,
    show_files: bool = False,
) -> str:
    """Render AggregateStats into the requested format (table, json, csv)."""
    fmt_clean = fmt.strip().lower()
    if fmt_clean == "json":
        return format_json(stats, per_repo=per_repo, show_files=show_files)
    elif fmt_clean == "csv":
        return format_csv(stats, per_repo=per_repo, show_files=show_files)
    else:
        return format_table(stats, per_repo=per_repo, show_files=show_files)

