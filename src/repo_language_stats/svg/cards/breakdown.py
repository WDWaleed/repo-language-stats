"""Detailed language breakdown table SVG card generator."""

from __future__ import annotations

from typing import Any

from repo_language_stats.svg.cards import extract_stats_data, render_template
from repo_language_stats.svg.themes import get_theme
from repo_language_stats.svg.utils import escape_xml, format_bytes, format_number


def generate_breakdown_card(
    stats: Any,
    theme: str = "light",
    metric: str = "bytes",
    langs_count: int = 10,
    show_files: bool = False,
    hide_title: bool = False,
    title: str | None = None,
    empty_message: str = "No language statistics found",
) -> str:
    """Generate a 520 x dynamic detailed breakdown table SVG card.

    Fixed Decision D3: breakdown: 520 x dynamic.
    """
    theme_obj = get_theme(theme)
    username, languages, tot_bytes, tot_lines, tot_files = extract_stats_data(
        stats,
        metric=metric,
        langs_count=langs_count,
    )

    primary_metric_tot = tot_lines if metric == "lines" else tot_bytes
    has_stats = len(languages) > 0 and primary_metric_tot > 0

    show_bytes = metric in ("bytes", "both")
    show_lines = metric in ("lines", "both")

    # Column x coordinates
    if show_bytes and show_lines and show_files:
        bytes_col_x = 280
        lines_col_x = 405
        files_col_x = 490
    elif show_bytes and show_lines:
        bytes_col_x = 330
        lines_col_x = 490
        files_col_x = 490
    elif show_files:
        bytes_col_x = 380 if show_bytes else 490
        lines_col_x = 380 if show_lines else 490
        files_col_x = 490
    else:
        bytes_col_x = 490
        lines_col_x = 490
        files_col_x = 490

    header_y = 55 if not hide_title else 30
    div_y = header_y + 10
    row_start_y = div_y + 22
    row_height = 26

    rows: list[dict[str, Any]] = []
    if has_stats:
        for i, lang in enumerate(languages):
            row_y = row_start_y + (i * row_height)
            rows.append(
                {
                    "y": row_y,
                    "color": lang["color"],
                    "escaped_name": lang["escaped_name"],
                    "bytes_text": lang["bytes_text"],
                    "byte_percent": lang["byte_percent"],
                    "lines_text": lang["lines_text"],
                    "line_percent": lang["line_percent"],
                    "files_text": lang["files_text"],
                }
            )

        footer_div_y = row_start_y + (len(languages) * row_height) - 4
        footer_y = footer_div_y + 22
        height = footer_y + 16
    else:
        footer_div_y = 0
        footer_y = 0
        height = 140

    card_title = escape_xml(title if title else (f"{username}'s Language Breakdown" if username else "Language Breakdown"))

    context = {
        "title": card_title,
        "hide_title": hide_title,
        "theme_css": theme_obj.get_css(),
        "has_stats": has_stats,
        "empty_message": escape_xml(empty_message),
        "height": height,
        "header_y": header_y,
        "div_y": div_y,
        "rows": rows,
        "footer_div_y": footer_div_y,
        "footer_y": footer_y,
        "show_bytes": show_bytes,
        "show_lines": show_lines,
        "show_files": show_files,
        "bytes_col_x": bytes_col_x,
        "lines_col_x": lines_col_x,
        "files_col_x": files_col_x,
        "total_bytes_text": format_bytes(tot_bytes),
        "total_lines_text": format_number(tot_lines, compact=False),
        "total_files_text": format_number(tot_files, compact=False),
    }

    return render_template("breakdown.svg.j2", context)
