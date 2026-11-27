"""SVG rendering package for repo-language-stats."""

from __future__ import annotations

from repo_language_stats.svg.themes import (
    AUTO_THEME,
    DARK_THEME,
    LIGHT_THEME,
    THEMES,
    Theme,
    get_theme,
)
from repo_language_stats.svg.utils import (
    DonutSlice,
    compute_donut_slices,
    describe_donut_arc,
    escape_xml,
    format_bytes,
    format_number,
    polar_to_cartesian,
    resolve_language_color,
)

__all__ = [
    "AUTO_THEME",
    "DARK_THEME",
    "LIGHT_THEME",
    "THEMES",
    "DonutSlice",
    "Theme",
    "compute_donut_slices",
    "describe_donut_arc",
    "escape_xml",
    "format_bytes",
    "format_number",
    "get_theme",
    "polar_to_cartesian",
    "render_svg",
    "resolve_language_color",
]


def render_svg(*args, **kwargs):
    """Stub for SVG rendering orchestrator (implemented in M1.2)."""
    from repo_language_stats.svg.renderer import render_svg as _render_svg

    return _render_svg(*args, **kwargs)
