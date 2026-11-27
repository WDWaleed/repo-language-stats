"""Donut chart SVG card generator."""

from __future__ import annotations

from typing import Any

from repo_language_stats.svg.cards import extract_stats_data, render_template
from repo_language_stats.svg.themes import get_theme
from repo_language_stats.svg.utils import (
    compute_donut_slices,
    escape_xml,
    format_bytes,
    format_number,
)


def generate_donut_card(
    stats: Any,
    theme: str = "light",
    metric: str = "bytes",
    langs_count: int = 6,
    hide_title: bool = False,
    title: str | None = None,
    empty_message: str = "No language statistics found",
) -> str:
    """Generate a fixed 495 x 220 donut chart SVG card.

    Fixed Decision D3: donut: 495 x 220.
    """
    theme_obj = get_theme(theme)
    username, languages, tot_bytes, tot_lines, _ = extract_stats_data(
        stats,
        metric=metric,
        langs_count=langs_count,
    )

    primary_metric_tot = tot_lines if metric == "lines" else tot_bytes
    has_stats = len(languages) > 0 and primary_metric_tot > 0

    cx = 115.0
    cy = 125.0 if not hide_title else 110.0
    r_inner = 42.0
    r_outer = 68.0

    slices_data: list[Any] = []
    items: list[dict[str, Any]] = []

    if has_stats:
        # Compute trigonometric arc paths for donut
        donut_input = [
            {
                "language": l["name"],
                "bytes": l["bytes"] if metric == "bytes" else l["lines"],
                "color": l["color"],
            }
            for l in languages
        ]
        raw_slices = compute_donut_slices(
            donut_input,
            cx=cx,
            cy=cy,
            r_inner=r_inner,
            r_outer=r_outer,
            value_key="bytes",
            label_key="language",
            color_key="color",
        )
        for s in raw_slices:
            slices_data.append(
                {
                    "path_d": s.path_d,
                    "color": s.color,
                    "escaped_label": escape_xml(s.label),
                    "percentage": s.percentage,
                }
            )

        # Center donut hole metric
        if metric == "lines":
            center_metric = format_number(tot_lines, compact=True)
            center_label = "LINES"
        else:
            center_metric = format_bytes(tot_bytes, precision=1)
            center_label = "BYTES"

        # Legend items on the right side
        legend_start_y = 60.0 if not hide_title else 45.0
        row_height = 24.0
        for i, lang in enumerate(languages):
            dot_y = legend_start_y + (i * row_height)
            items.append(
                {
                    "dot_x": 225,
                    "dot_y": dot_y,
                    "text_x": 238,
                    "metric_x": 470,
                    "color": lang["color"],
                    "escaped_name": lang["escaped_name"],
                    "formatted_metric": lang["formatted_metric"],
                    "percentage": lang["percentage"],
                }
            )
    else:
        center_metric = "0 B"
        center_label = "TOTAL"

    card_title = escape_xml(title if title else (f"{username}'s Top Languages" if username else "Most Used Languages"))

    context = {
        "title": card_title,
        "hide_title": hide_title,
        "theme_css": theme_obj.get_css(),
        "has_stats": has_stats,
        "empty_message": escape_xml(empty_message),
        "cx": cx,
        "cy": cy,
        "center_metric": center_metric,
        "center_label": center_label,
        "slices": slices_data,
        "items": items,
    }

    return render_template("donut.svg.j2", context)
