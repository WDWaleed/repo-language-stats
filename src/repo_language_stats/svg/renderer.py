"""SVG rendering dispatch engine and API orchestrator."""

from __future__ import annotations

from typing import Any
import xml.etree.ElementTree as ET

from repo_language_stats.svg.cards.bar import generate_bar_card
from repo_language_stats.svg.cards.breakdown import generate_breakdown_card
from repo_language_stats.svg.cards.compact import generate_compact_card
from repo_language_stats.svg.cards.donut import generate_donut_card

CARD_GENERATORS = {
    "bar": generate_bar_card,
    "breakdown": generate_breakdown_card,
    "donut": generate_donut_card,
    "compact": generate_compact_card,
}

DEFAULT_LANGS_COUNT = {
    "bar": None,
    "breakdown": 10,
    "donut": 6,
    "compact": 4,
}


def render_svg(
    stats: Any,
    card_type: str = "bar",
    theme: str = "light",
    metric: str = "bytes",
    langs_count: int | None = None,
    show_files: bool = False,
    hide_title: bool = False,
    title: str | None = None,
) -> str:
    """Render an SVG card for the given repository language stats.

    Args:
        stats: AggregateStats instance or dictionary containing language metrics.
        card_type: Card style ("bar", "breakdown", "donut", "compact").
        theme: Color theme ("light", "dark", "auto").
        metric: Metric to display ("bytes", "lines", "both").
        langs_count: Maximum number of languages to display.
        show_files: Whether to display file count column (breakdown card).
        hide_title: Whether to omit the title header.
        title: Optional custom card title.

    Returns:
        Valid SVG XML string.

    Raises:
        ValueError: If card_type is unrecognized.
    """
    card_type_norm = card_type.strip().lower()
    if card_type_norm not in CARD_GENERATORS:
        valid_types = ", ".join(CARD_GENERATORS.keys())
        raise ValueError(f"Invalid card_type '{card_type}'. Valid choices: {valid_types}")

    theme_norm = theme.strip().lower() if theme else "light"
    metric_norm = metric.strip().lower() if metric else "bytes"
    if metric_norm not in ("bytes", "lines", "both"):
        metric_norm = "bytes"

    # Single metrics for cards that don't support "both"
    if card_type_norm != "breakdown" and metric_norm == "both":
        metric_norm = "bytes"

    effective_langs_count = (
        langs_count
        if (langs_count is not None and langs_count > 0)
        else DEFAULT_LANGS_COUNT.get(card_type_norm)
    )

    generator = CARD_GENERATORS[card_type_norm]

    if card_type_norm == "compact":
        svg_content = generator(
            stats=stats,
            theme=theme_norm,
            metric=metric_norm,
            langs_count=effective_langs_count,
            title=title,
        )
    elif card_type_norm == "breakdown":
        svg_content = generator(
            stats=stats,
            theme=theme_norm,
            metric=metric_norm,
            langs_count=effective_langs_count,
            show_files=show_files,
            hide_title=hide_title,
            title=title,
        )
    elif card_type_norm == "bar":
        svg_content = generator(
            stats=stats,
            theme=theme_norm,
            metric=metric_norm,
            langs_count=effective_langs_count,
            min_percent=1.0 if effective_langs_count is None else None,
            hide_title=hide_title,
            title=title,
        )
    else:  # donut
        svg_content = generator(
            stats=stats,
            theme=theme_norm,
            metric=metric_norm,
            langs_count=effective_langs_count,
            hide_title=hide_title,
            title=title,
        )

    # Validate XML syntax before returning
    ET.fromstring(svg_content)
    return svg_content
