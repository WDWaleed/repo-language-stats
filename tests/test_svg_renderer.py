"""Tests for SVG themes, color resolution, and utility functions."""

from __future__ import annotations

import math
from repo_language_stats.svg.themes import (
    AUTO_THEME,
    DARK_THEME,
    LIGHT_THEME,
    THEMES,
    Theme,
    get_theme,
)
from repo_language_stats.svg.utils import (
    compute_donut_slices,
    describe_donut_arc,
    escape_xml,
    format_bytes,
    format_number,
    polar_to_cartesian,
    resolve_language_color,
)


class TestSVGThemes:
    """Verify theme palettes, D4 specifications, and CSS generation."""

    def test_get_theme_defaults(self):
        assert get_theme() == LIGHT_THEME
        assert get_theme(None) == LIGHT_THEME
        assert get_theme("") == LIGHT_THEME
        assert get_theme("unknown_theme") == LIGHT_THEME

    def test_get_theme_case_insensitivity(self):
        assert get_theme("light") == LIGHT_THEME
        assert get_theme("LIGHT") == LIGHT_THEME
        assert get_theme("dark") == DARK_THEME
        assert get_theme("Dark") == DARK_THEME
        assert get_theme("auto") == AUTO_THEME
        assert get_theme("AuTo") == AUTO_THEME

    def test_theme_colors_match_decision_d4(self):
        # D4: light (#ffffff bg, #24292f text, #d0d7de border)
        assert LIGHT_THEME.bg == "#ffffff"
        assert LIGHT_THEME.text == "#24292f"
        assert LIGHT_THEME.border == "#d0d7de"

        # D4: dark (#0d1117 bg, #e6edf3 text, #30363d border)
        assert DARK_THEME.bg == "#0d1117"
        assert DARK_THEME.text == "#e6edf3"
        assert DARK_THEME.border == "#30363d"

        # D4: auto embeds prefers-color-scheme: dark media query
        assert AUTO_THEME.is_auto is True
        auto_css = AUTO_THEME.get_css()
        assert "@media (prefers-color-scheme: dark)" in auto_css
        assert "#0d1117" in auto_css
        assert "#e6edf3" in auto_css
        assert "#30363d" in auto_css

    def test_theme_css_structure(self):
        light_css = LIGHT_THEME.get_css()
        assert ":root" in light_css
        assert "--card-bg: #ffffff;" in light_css
        assert "--card-text: #24292f;" in light_css
        assert "--card-border: #d0d7de;" in light_css
        assert "@media" not in light_css


class TestXMLEscaping:
    """Verify XML sanitization prevents XSS and malformed SVG output."""

    def test_escape_special_characters(self):
        assert escape_xml("foo & bar") == "foo &amp; bar"
        assert escape_xml("<tag>") == "&lt;tag&gt;"
        assert escape_xml('quote "double"') == "quote &quot;double&quot;"
        assert escape_xml("quote 'single'") == "quote &apos;single&apos;"

    def test_escape_complex_payload(self):
        malicious = '<script>alert("XSS & injection")</script>'
        escaped = escape_xml(malicious)
        assert "<" not in escaped
        assert ">" not in escaped
        assert '"' not in escaped
        assert escaped == "&lt;script&gt;alert(&quot;XSS &amp; injection&quot;)&lt;/script&gt;"

    def test_escape_none_and_non_strings(self):
        assert escape_xml(None) == ""
        assert escape_xml(123) == "123"
        assert escape_xml(45.6) == "45.6"
        assert escape_xml(True) == "True"


class TestFormatters:
    """Verify number and byte formatting utilities."""

    def test_format_bytes(self):
        assert format_bytes(0) == "0 B"
        assert format_bytes(500) == "500 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(1048576) == "1.0 MB"
        assert format_bytes(1048576 * 15.5) == "15.5 MB"
        assert format_bytes(1073741824) == "1.0 GB"
        assert format_bytes(1073741824 * 2.5) == "2.5 GB"
        assert format_bytes(-2048) == "-2.0 KB"

    def test_format_number_compact(self):
        assert format_number(0) == "0"
        assert format_number(55) == "55"
        assert format_number(999) == "999"
        assert format_number(1200) == "1.2k"
        assert format_number(45600) == "45.6k"
        assert format_number(150000) == "150k"
        assert format_number(1200000) == "1.2M"
        assert format_number(35000000) == "35.0M"
        assert format_number(2400000000) == "2.4B"
        assert format_number(-1500) == "-1.5k"

    def test_format_number_full(self):
        assert format_number(1234, compact=False) == "1,234"
        assert format_number(1000000, compact=False) == "1,000,000"


class TestColorResolution:
    """Verify language color mapping using Linguist dataset."""

    def test_resolve_standard_languages(self):
        assert resolve_language_color("Python") == "#3572A5"
        assert resolve_language_color("TypeScript") == "#3178c6"
        assert resolve_language_color("JavaScript") == "#f1e05a"
        assert resolve_language_color("HTML") == "#e34c26"
        assert resolve_language_color("Rust") == "#dea584"
        assert resolve_language_color("Jupyter Notebook") == "#DA5B0B"

    def test_resolve_case_insensitive(self):
        assert resolve_language_color("python") == "#3572A5"
        assert resolve_language_color("typescript") == "#3178c6"
        assert resolve_language_color("rust") == "#dea584"

    def test_resolve_unknown_fallback(self):
        assert resolve_language_color("NonExistentLang404") == "#8b949e"
        assert resolve_language_color("", default="#123456") == "#123456"
        assert resolve_language_color("Unknown", default="#abcdef") == "#abcdef"


class TestDonutMath:
    """Verify polar-to-cartesian and donut arc geometry generation."""

    def test_polar_to_cartesian_cardinal_points(self):
        cx, cy, r = 100.0, 100.0, 50.0

        # 0 deg = 12 o'clock -> (100, 50)
        p0 = polar_to_cartesian(cx, cy, r, 0.0)
        assert math.isclose(p0[0], 100.0, abs_tol=1e-3)
        assert math.isclose(p0[1], 50.0, abs_tol=1e-3)

        # 90 deg = 3 o'clock -> (150, 100)
        p90 = polar_to_cartesian(cx, cy, r, 90.0)
        assert math.isclose(p90[0], 150.0, abs_tol=1e-3)
        assert math.isclose(p90[1], 100.0, abs_tol=1e-3)

        # 180 deg = 6 o'clock -> (100, 150)
        p180 = polar_to_cartesian(cx, cy, r, 180.0)
        assert math.isclose(p180[0], 100.0, abs_tol=1e-3)
        assert math.isclose(p180[1], 150.0, abs_tol=1e-3)

        # 270 deg = 9 o'clock -> (50, 100)
        p270 = polar_to_cartesian(cx, cy, r, 270.0)
        assert math.isclose(p270[0], 50.0, abs_tol=1e-3)
        assert math.isclose(p270[1], 100.0, abs_tol=1e-3)

    def test_describe_donut_arc_path_structure(self):
        cx, cy, r_in, r_out = 100.0, 100.0, 30.0, 60.0

        # Quadrant slice 0 -> 90 deg
        d = describe_donut_arc(cx, cy, r_in, r_out, 0.0, 90.0)
        assert d.startswith("M ")
        assert " A 60.0 60.0 0 0 1 " in d
        assert " L " in d
        assert " A 30.0 30.0 0 0 0 " in d
        assert d.endswith("Z")

        # Over 180 deg (large arc flag = 1)
        d_large = describe_donut_arc(cx, cy, r_in, r_out, 0.0, 270.0)
        assert " A 60.0 60.0 0 1 1 " in d_large

        # Full 360 degree circle
        d_full = describe_donut_arc(cx, cy, r_in, r_out, 0.0, 360.0)
        assert d_full.count("Z") == 2  # Rendered as two semicircles

        # Invalid/zero angle returns empty
        assert describe_donut_arc(cx, cy, r_in, r_out, 90.0, 90.0) == ""
        assert describe_donut_arc(cx, cy, r_in, r_out, 100.0, 50.0) == ""

    def test_describe_donut_arc_pie_mode(self):
        # When r_inner <= 0, functions as a pie slice
        d = describe_donut_arc(100.0, 100.0, 0.0, 50.0, 0.0, 90.0)
        assert d.startswith("M 100.0 100.0 L ")
        assert " A 50.0 50.0 0 0 1 " in d
        assert d.endswith("Z")

    def test_compute_donut_slices(self):
        items = [
            {"language": "Python", "bytes": 600},
            {"language": "TypeScript", "bytes": 300},
            {"language": "HTML", "bytes": 100},
        ]
        slices = compute_donut_slices(items, cx=110, cy=110, r_inner=40, r_outer=70)
        assert len(slices) == 3

        assert slices[0].label == "Python"
        assert slices[0].percentage == 60.0
        assert slices[0].start_angle == 0.0
        assert slices[0].end_angle == 216.0
        assert slices[0].color == "#3572A5"
        assert slices[0].path_d.startswith("M ")

        assert slices[1].label == "TypeScript"
        assert slices[1].percentage == 30.0
        assert slices[1].start_angle == 216.0
        assert slices[1].end_angle == 324.0
        assert slices[1].color == "#3178c6"

        assert slices[2].label == "HTML"
        assert slices[2].percentage == 10.0
        assert slices[2].start_angle == 324.0
        assert slices[2].end_angle == 360.0
        assert slices[2].color == "#e34c26"

    def test_compute_donut_slices_empty_or_zero(self):
        assert compute_donut_slices([], cx=100, cy=100, r_inner=20, r_outer=40) == []
        assert compute_donut_slices([{"bytes": 0}], cx=100, cy=100, r_inner=20, r_outer=40) == []


import xml.etree.ElementTree as ET
import pytest
from repo_language_stats.counting import AggregateStats, LanguageStats
from repo_language_stats.svg.renderer import render_svg


@pytest.fixture
def sample_aggregate_stats():
    stats = AggregateStats(
        username="octocat",
        repos_scanned=5,
        total_bytes=100000,
        total_lines=5000,
    )
    stats.aggregate = {
        "Python": LanguageStats(language="Python", total_bytes=60000, total_lines=3000, file_count=10),
        "TypeScript": LanguageStats(language="TypeScript", total_bytes=25000, total_lines=1200, file_count=5),
        "HTML": LanguageStats(language="HTML", total_bytes=10000, total_lines=600, file_count=2),
        "CSS": LanguageStats(language="CSS", total_bytes=5000, total_lines=200, file_count=1),
    }
    return stats


@pytest.fixture
def sample_dict_stats():
    return {
        "username": "mona",
        "total_bytes": 50000,
        "total_lines": 2500,
        "languages": [
            {"language": "Rust", "bytes": 35000, "lines": 1800, "files": 8},
            {"language": "Go", "bytes": 15000, "lines": 700, "files": 4},
        ],
    }


class TestCardGenerators:
    """Verify that all 4 card generators produce non-empty valid XML SVGs."""

    @pytest.mark.parametrize("card_type", ["bar", "breakdown", "donut", "compact"])
    def test_each_card_produces_valid_xml(self, sample_aggregate_stats, card_type):
        svg_output = render_svg(sample_aggregate_stats, card_type=card_type)
        assert isinstance(svg_output, str)
        assert len(svg_output) > 0
        root = ET.fromstring(svg_output)
        assert root.tag.endswith("svg")

    @pytest.mark.parametrize("card_type", ["bar", "breakdown", "donut", "compact"])
    def test_dict_stats_produces_valid_xml(self, sample_dict_stats, card_type):
        svg_output = render_svg(sample_dict_stats, card_type=card_type)
        assert isinstance(svg_output, str)
        assert len(svg_output) > 0
        root = ET.fromstring(svg_output)
        assert root.tag.endswith("svg")

    def test_compact_card_dimensions(self, sample_aggregate_stats):
        svg = render_svg(sample_aggregate_stats, card_type="compact")
        root = ET.fromstring(svg)
        assert root.attrib.get("width") == "495"
        assert root.attrib.get("height") == "32"

    def test_donut_card_dimensions(self, sample_aggregate_stats):
        svg = render_svg(sample_aggregate_stats, card_type="donut")
        root = ET.fromstring(svg)
        assert root.attrib.get("width") == "495"
        assert root.attrib.get("height") == "220"

    def test_bar_card_dimensions_and_title(self, sample_aggregate_stats):
        svg = render_svg(sample_aggregate_stats, card_type="bar", title="Custom Title")
        assert "Custom Title" in svg
        root = ET.fromstring(svg)
        assert root.attrib.get("width") == "495"

    def test_breakdown_card_with_both_metrics_and_files(self, sample_aggregate_stats):
        svg = render_svg(
            sample_aggregate_stats,
            card_type="breakdown",
            metric="both",
            show_files=True,
        )
        assert "Files" in svg
        assert "Bytes / %" in svg
        assert "Lines / %" in svg
        root = ET.fromstring(svg)
        assert root.attrib.get("width") == "520"

    @pytest.mark.parametrize("theme", ["light", "dark", "auto"])
    def test_card_themes(self, sample_aggregate_stats, theme):
        svg = render_svg(sample_aggregate_stats, card_type="bar", theme=theme)
        if theme == "auto":
            assert "@media (prefers-color-scheme: dark)" in svg
        elif theme == "dark":
            assert "#0d1117" in svg
        elif theme == "light":
            assert "#ffffff" in svg

    def test_empty_stats_produces_valid_svg_without_error(self):
        empty_stats = AggregateStats(username="empty_user")
        for card_type in ["bar", "breakdown", "donut", "compact"]:
            svg = render_svg(empty_stats, card_type=card_type)
            root = ET.fromstring(svg)
            assert root.tag.endswith("svg")
            assert "No language statistics found" in svg

    def test_invalid_card_type_raises_value_error(self, sample_aggregate_stats):
        with pytest.raises(ValueError, match="Invalid card_type"):
            render_svg(sample_aggregate_stats, card_type="nonexistent")
