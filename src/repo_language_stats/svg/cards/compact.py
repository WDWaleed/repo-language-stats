"""Compact horizontal single-line progress bar SVG generator."""

from __future__ import annotations

from typing import Any

from repo_language_stats.svg.cards import extract_stats_data, render_template
from repo_language_stats.svg.themes import get_theme
from repo_language_stats.svg.utils import escape_xml


def generate_compact_card(
    stats: Any,
    theme: str = "light",
    metric: str = "bytes",
    langs_count: int = 4,
    title: str | None = None,
    empty_message: str = "No language statistics found",
) -> str:
    """Generate a 495x32 compact horizontal progress bar SVG.

    Fixed Decision D3: compact: 495 x 32.
    """
    theme_obj = get_theme(theme)
    username, languages, tot_bytes, tot_lines, _ = extract_stats_data(
        stats,
        metric=metric,
        langs_count=langs_count,
    )

    primary_metric_tot = tot_lines if metric == "lines" else tot_bytes
    has_stats = len(languages) > 0 and primary_metric_tot > 0

    segments: list[dict[str, Any]] = []
    total_bar_width = 471.0
    current_x = 12.0

    if has_stats:
        top_metric_sum = sum(l["lines"] if metric == "lines" else l["bytes"] for l in languages)
        for i, lang in enumerate(languages):
            val = lang["lines"] if metric == "lines" else lang["bytes"]
            if top_metric_sum > 0:
                seg_width = round((val / top_metric_sum) * total_bar_width, 2)
            else:
                seg_width = 0.0

            # Guard against rounding overflow on last element
            if i == len(languages) - 1:
                seg_width = max(0.0, round(12.0 + total_bar_width - current_x, 2))

            segments.append(
                {
                    "x": round(current_x, 2),
                    "width": seg_width,
                    "color": lang["color"],
                    "escaped_name": lang["escaped_name"],
                    "percentage": lang["percentage"],
                }
            )
            current_x += seg_width

    card_title = escape_xml(title if title else (f"{username}'s Language Stats" if username else "Language Stats"))

    context = {
        "title": card_title,
        "theme_css": theme_obj.get_css(),
        "has_stats": has_stats,
        "empty_message": escape_xml(empty_message),
        "segments": segments,
    }

    return render_template("compact.svg.j2", context)
