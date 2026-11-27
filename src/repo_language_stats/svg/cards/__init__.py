"""SVG card generators and shared template utilities."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader

from repo_language_stats.counting import AggregateStats, LanguageStats
from repo_language_stats.svg.themes import Theme, get_theme
from repo_language_stats.svg.utils import (
    escape_xml,
    format_bytes,
    format_number,
    resolve_language_color,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_JINJA_ENV = Environment(
    loader=ChoiceLoader(
        [
            FileSystemLoader(str(TEMPLATES_DIR)),
            PackageLoader("repo_language_stats.svg", "templates"),
        ]
    ),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 SVG template with the provided context."""
    template = _JINJA_ENV.get_template(template_name)
    return template.render(**context)


def extract_stats_data(
    stats: Any,
    metric: str = "bytes",
    langs_count: int | None = None,
    min_percent: float | None = None,
) -> tuple[str, list[dict[str, Any]], int, int, int]:
    """Extract and normalize language statistics from AggregateStats or dictionary.

    Returns:
        (username, sorted_languages_list, total_bytes, total_lines, total_files)
    """
    username = ""
    raw_languages: list[dict[str, Any]] = []
    tot_bytes = 0
    tot_lines = 0
    tot_files = 0

    if isinstance(stats, AggregateStats):
        username = stats.username or ""
        tot_bytes = stats.total_bytes
        tot_lines = stats.total_lines
        for lang_stat in stats.aggregate.values():
            raw_languages.append(
                {
                    "language": lang_stat.language,
                    "bytes": lang_stat.total_bytes,
                    "lines": lang_stat.total_lines,
                    "files": lang_stat.file_count,
                }
            )
            tot_files += lang_stat.file_count
    elif isinstance(stats, dict):
        username = str(stats.get("username", ""))
        tot_bytes = int(stats.get("total_bytes", 0))
        tot_lines = int(stats.get("total_lines", 0))

        # Check for languages array
        if "languages" in stats and isinstance(stats["languages"], list):
            for item in stats["languages"]:
                raw_languages.append(
                    {
                        "language": item.get("language", ""),
                        "bytes": int(item.get("bytes", item.get("total_bytes", 0))),
                        "lines": int(item.get("lines", item.get("total_lines", 0))),
                        "files": int(item.get("files", item.get("file_count", 0))),
                        "color": item.get("color"),
                    }
                )
        elif "aggregate" in stats and isinstance(stats["aggregate"], dict):
            for lang_name, info in stats["aggregate"].items():
                if isinstance(info, (LanguageStats, dict)):
                    b = info.total_bytes if isinstance(info, LanguageStats) else int(info.get("total_bytes", 0))
                    l = info.total_lines if isinstance(info, LanguageStats) else int(info.get("total_lines", 0))
                    f = info.file_count if isinstance(info, LanguageStats) else int(info.get("file_count", 0))
                else:
                    b, l, f = 0, 0, 0
                raw_languages.append(
                    {
                        "language": lang_name,
                        "bytes": b,
                        "lines": l,
                        "files": f,
                    }
                )

        if tot_files == 0:
            tot_files = sum(item.get("files", 0) for item in raw_languages)
        if tot_bytes == 0:
            tot_bytes = sum(item.get("bytes", 0) for item in raw_languages)
        if tot_lines == 0:
            tot_lines = sum(item.get("lines", 0) for item in raw_languages)

    # Sort languages
    if metric == "lines":
        raw_languages.sort(key=lambda x: (x["lines"], x["bytes"], x["language"]), reverse=True)
    else:
        raw_languages.sort(key=lambda x: (x["bytes"], x["lines"], x["language"]), reverse=True)

    # Apply min_percent threshold (before langs_count cap)
    if min_percent is not None:
        denominator = tot_lines if metric == "lines" else tot_bytes
        if denominator > 0:
            filtered = [
                lang for lang in raw_languages
                if (lang["lines"] if metric == "lines" else lang["bytes"]) / denominator * 100.0 >= min_percent
            ]
            # top-1 fallback: never return empty when input is non-empty
            raw_languages = filtered if filtered else (raw_languages[:1] if raw_languages else [])

    if langs_count is not None and langs_count > 0:
        raw_languages = raw_languages[:langs_count]

    # Normalize language details
    processed_languages: list[dict[str, Any]] = []
    for item in raw_languages:
        name = item.get("language", "")
        b = item.get("bytes", 0)
        l = item.get("lines", 0)
        f = item.get("files", 0)
        color = item.get("color") or resolve_language_color(name)
        b_pct = (b / tot_bytes * 100.0) if tot_bytes > 0 else 0.0
        l_pct = (l / tot_lines * 100.0) if tot_lines > 0 else 0.0

        if metric == "lines":
            active_pct = l_pct
            active_metric_text = f"{format_number(l, compact=True)} lines"
        else:
            active_pct = b_pct
            active_metric_text = format_bytes(b)

        processed_languages.append(
            {
                "name": name,
                "escaped_name": escape_xml(name),
                "bytes": b,
                "lines": l,
                "files": f,
                "color": color,
                "byte_percent": round(b_pct, 1),
                "line_percent": round(l_pct, 1),
                "percentage": round(active_pct, 1),
                "formatted_metric": active_metric_text,
                "bytes_text": format_bytes(b),
                "lines_text": format_number(l, compact=False),
                "files_text": format_number(f, compact=False),
            }
        )

    return username, processed_languages, tot_bytes, tot_lines, tot_files
