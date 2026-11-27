"""Standard multi-language progress bar SVG card generator."""

from __future__ import annotations

import math
from typing import Any

from repo_language_stats.svg.cards import extract_stats_data, render_template
from repo_language_stats.svg.themes import get_theme
from repo_language_stats.svg.utils import escape_xml


def generate_bar_card(
    stats: Any,
    theme: str = "light",
    metric: str = "bytes",
    langs_count: int = 8,
    hide_title: bool = False,
    title: str | None = None,
    empty_message: str = "No language statistics found",
) -> str:
    """Generate a 495 x dynamic bar card SVG with top progress bar and 2-column legend.

    Fixed Decision D3: bar: 495 x dynamic.
    """
    theme_obj = get_theme(theme)
    username, languages, tot_bytes, tot_lines, _ = extract_stats_data(
        stats,
        metric=metric,
        langs_count=langs_count,
    )

    primary_metric_tot = tot_lines if metric == "lines" else tot_bytes
    has_stats = len(languages) > 0 and primary_metric_tot > 0

    bar_y = 20 if hide_title else 50
    legend_start_y = (bar_y + 28)

    segments: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    total_bar_width = 445.0
    current_x = 25.0

    if has_stats:
        top_metric_sum = sum(l["lines"] if metric == "lines" else l["bytes"] for l in languages)
        for i, lang in enumerate(languages):
            val = lang["lines"] if metric == "lines" else lang["bytes"]
            seg_width = round((val / top_metric_sum) * total_bar_width, 2) if top_metric_sum > 0 else 0.0

            if i == len(languages) - 1:
                seg_width = max(0.0, round(25.0 + total_bar_width - current_x, 2))

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

        # Legend items in 2 columns
        row_height = 24
        col_width = 222
        for idx, lang in enumerate(languages):
            col = idx % 2
            row = idx // 2
            base_x = 25 if col == 0 else 247
            dot_y = legend_start_y + (row * row_height)
            text_y = dot_y + 4

            items.append(
                {
                    "dot_x": base_x + 5,
                    "dot_y": dot_y,
                    "text_x": base_x + 18,
                    "text_y": text_y,
                    "metric_x": base_x + 120,
                    "color": lang["color"],
                    "escaped_name": lang["escaped_name"],
                    "formatted_metric": lang["formatted_metric"],
                    "percentage": lang["percentage"],
                }
            )

        num_rows = math.ceil(len(languages) / 2)
        height = legend_start_y + (num_rows * row_height) + 16
    else:
        height = 130

    card_title = escape_xml(title if title else (f"{username}'s Top Languages" if username else "Most Used Languages"))

    context = {
        "title": card_title,
        "hide_title": hide_title,
        "theme_css": theme_obj.get_css(),
        "has_stats": has_stats,
        "empty_message": escape_xml(empty_message),
        "height": height,
        "bar_y": bar_y,
        "segments": segments,
        "items": items,
    }

    return render_template("bar.svg.j2", context)
