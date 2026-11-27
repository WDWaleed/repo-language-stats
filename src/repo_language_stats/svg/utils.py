"""SVG geometry math, XML escaping, unit formatting, and Linguist color resolution."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from repo_language_stats.language import get_default_classifier, get_language_color


def escape_xml(text: Any) -> str:
    """Safely escape text for interpolation into XML/SVG documents.

    Escapes &, <, >, ", and '. None is converted to an empty string.
    """
    if text is None:
        return ""
    s = str(text)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_bytes(bytes_count: int | float, precision: int = 1) -> str:
    """Format byte counts into human-readable strings (e.g. 500 B, 1.2 KB, 3.4 MB, 1.5 GB)."""
    if bytes_count < 0:
        return f"-{format_bytes(-bytes_count, precision=precision)}"

    count = float(bytes_count)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_idx = 0
    while count >= 1024.0 and unit_idx < len(units) - 1:
        count /= 1024.0
        unit_idx += 1

    if unit_idx == 0:
        return f"{int(count)} B"

    formatted = f"{count:.{precision}f}"
    return f"{formatted} {units[unit_idx]}"


def format_number(n: int | float, compact: bool = True) -> str:
    """Format numeric counts into readable strings (e.g. 1.2k, 10.5M, or 1,234)."""
    if n < 0:
        return f"-{format_number(-n, compact=compact)}"

    val = float(n)
    if not compact:
        return f"{int(val):,}" if val.is_integer() else f"{val:,.1f}"

    if val < 1000:
        return f"{int(val)}" if val.is_integer() else f"{val:.1f}"
    elif val < 1_000_000:
        k = val / 1000.0
        return f"{k:.1f}k" if k < 100 else f"{int(round(k))}k"
    elif val < 1_000_000_000:
        m = val / 1_000_000.0
        return f"{m:.1f}M" if m < 100 else f"{int(round(m))}M"
    else:
        b = val / 1_000_000_000.0
        return f"{b:.1f}B" if b < 100 else f"{int(round(b))}B"


def resolve_language_color(language: str, default: str = "#8b949e") -> str:
    """Resolve a language name to its Linguist hex color code.

    Returns the hex color code with leading '#' (e.g. '#3572A5' for Python),
    or the default color if not found.
    """
    if not language:
        return default

    # Direct lookup with classifier's overrides and exact names
    color = get_language_color(language)
    if color:
        return color

    # Case-insensitive and alias search in languages dataset
    classifier = get_default_classifier()
    lang_lower = language.strip().lower()
    for raw_name, info in classifier._languages_data.items():
        if raw_name.lower() == lang_lower:
            c = info.get("color")
            if c:
                return c
            break
        aliases = [a.lower() for a in info.get("aliases", [])]
        if lang_lower in aliases:
            c = info.get("color")
            if c:
                return c
            break

    return default


def polar_to_cartesian(
    cx: float,
    cy: float,
    radius: float,
    angle_in_degrees: float,
) -> tuple[float, float]:
    """Convert polar coordinates to Cartesian (x, y) coordinates.

    0 degrees is at the 12 o'clock position; angles increase clockwise.
    """
    angle_in_radians = math.radians(angle_in_degrees - 90.0)
    x = cx + (radius * math.cos(angle_in_radians))
    y = cy + (radius * math.sin(angle_in_radians))
    return (round(x, 3), round(y, 3))


def describe_donut_arc(
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    start_angle: float,
    end_angle: float,
) -> str:
    """Generate SVG path data 'd' string for a donut chart slice."""
    angle_diff = end_angle - start_angle
    if angle_diff <= 0:
        return ""

    if angle_diff >= 360.0:
        # Full circle: draw as two 180-degree half-donuts to prevent SVG arc degenerate paths
        mid_angle = start_angle + 180.0
        part1 = describe_donut_arc(cx, cy, r_inner, r_outer, start_angle, mid_angle)
        part2 = describe_donut_arc(cx, cy, r_inner, r_outer, mid_angle, start_angle + 360.0)
        return f"{part1} {part2}"

    large_arc_flag = 1 if angle_diff > 180.0 else 0

    start_outer = polar_to_cartesian(cx, cy, r_outer, start_angle)
    end_outer = polar_to_cartesian(cx, cy, r_outer, end_angle)

    if r_inner <= 0:
        # Standard pie slice without inner cutout
        return (
            f"M {cx} {cy} "
            f"L {start_outer[0]} {start_outer[1]} "
            f"A {r_outer} {r_outer} 0 {large_arc_flag} 1 {end_outer[0]} {end_outer[1]} "
            "Z"
        )

    end_inner = polar_to_cartesian(cx, cy, r_inner, end_angle)
    start_inner = polar_to_cartesian(cx, cy, r_inner, start_angle)

    return (
        f"M {start_outer[0]} {start_outer[1]} "
        f"A {r_outer} {r_outer} 0 {large_arc_flag} 1 {end_outer[0]} {end_outer[1]} "
        f"L {end_inner[0]} {end_inner[1]} "
        f"A {r_inner} {r_inner} 0 {large_arc_flag} 0 {start_inner[0]} {start_inner[1]} "
        "Z"
    )


@dataclass(frozen=True)
class DonutSlice:
    label: str
    value: float
    percentage: float
    color: str
    start_angle: float
    end_angle: float
    path_d: str


def compute_donut_slices(
    items: list[dict[str, Any]],
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    value_key: str = "bytes",
    label_key: str = "language",
    color_key: str = "color",
) -> list[DonutSlice]:
    """Compute donut arc path data for a list of language items."""
    total = sum(float(item.get(value_key, 0)) for item in items)
    if total <= 0:
        return []

    slices: list[DonutSlice] = []
    current_angle = 0.0
    for item in items:
        val = float(item.get(value_key, 0))
        if val <= 0:
            continue
        pct = (val / total) * 100.0
        angle_span = (val / total) * 360.0
        end_angle = current_angle + angle_span
        color = item.get(color_key) or resolve_language_color(item.get(label_key, ""))
        path_d = describe_donut_arc(cx, cy, r_inner, r_outer, current_angle, end_angle)
        slices.append(
            DonutSlice(
                label=str(item.get(label_key, "")),
                value=val,
                percentage=round(pct, 2),
                color=color,
                start_angle=round(current_angle, 2),
                end_angle=round(end_angle, 2),
                path_d=path_d,
            )
        )
        current_angle = end_angle

    return slices
