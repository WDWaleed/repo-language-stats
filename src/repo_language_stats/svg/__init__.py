"""SVG rendering package for repo-language-stats."""

from __future__ import annotations

__all__ = ["render_svg"]


def render_svg(*args, **kwargs):
    """Stub for SVG rendering orchestrator (implemented in M1.2)."""
    from repo_language_stats.svg.renderer import render_svg as _render_svg

    return _render_svg(*args, **kwargs)
