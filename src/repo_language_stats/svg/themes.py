"""SVG theme palettes and CSS style generator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """Theme color configuration for SVG cards.

    Implements Fixed Decision D4:
    - light: #ffffff bg, #24292f text, #d0d7de border
    - dark:  #0d1117 bg, #e6edf3 text, #30363d border
    - auto:  embeds @media (prefers-color-scheme: dark) CSS variables
    """

    name: str
    bg_color: str
    text_color: str
    border_color: str
    secondary_color: str = "#57606a"
    track_color: str = "#ebedf0"
    is_auto: bool = False
    dark_bg_color: str = "#0d1117"
    dark_text_color: str = "#e6edf3"
    dark_border_color: str = "#30363d"
    dark_secondary_color: str = "#8b949e"
    dark_track_color: str = "#21262d"

    @property
    def bg(self) -> str:
        return self.bg_color

    @property
    def text(self) -> str:
        return self.text_color

    @property
    def border(self) -> str:
        return self.border_color

    @property
    def secondary_text(self) -> str:
        return self.secondary_color

    @property
    def track(self) -> str:
        return self.track_color

    def get_css(self) -> str:
        """Generate CSS style rules with variables for SVG embedding."""
        if self.is_auto:
            return (
                ":root {\n"
                f"  --card-bg: {self.bg_color};\n"
                f"  --card-text: {self.text_color};\n"
                f"  --card-border: {self.border_color};\n"
                f"  --card-secondary: {self.secondary_color};\n"
                f"  --card-track: {self.track_color};\n"
                "}\n"
                "@media (prefers-color-scheme: dark) {\n"
                "  :root {\n"
                f"    --card-bg: {self.dark_bg_color};\n"
                f"    --card-text: {self.dark_text_color};\n"
                f"    --card-border: {self.dark_border_color};\n"
                f"    --card-secondary: {self.dark_secondary_color};\n"
                f"    --card-track: {self.dark_track_color};\n"
                "  }\n"
                "}"
            )
        return (
            ":root {\n"
            f"  --card-bg: {self.bg_color};\n"
            f"  --card-text: {self.text_color};\n"
            f"  --card-border: {self.border_color};\n"
            f"  --card-secondary: {self.secondary_color};\n"
            f"  --card-track: {self.track_color};\n"
            "}"
        )


LIGHT_THEME = Theme(
    name="light",
    bg_color="#ffffff",
    text_color="#24292f",
    border_color="#d0d7de",
    secondary_color="#57606a",
    track_color="#ebedf0",
    is_auto=False,
)

DARK_THEME = Theme(
    name="dark",
    bg_color="#0d1117",
    text_color="#e6edf3",
    border_color="#30363d",
    secondary_color="#8b949e",
    track_color="#21262d",
    is_auto=False,
)

AUTO_THEME = Theme(
    name="auto",
    bg_color="#ffffff",
    text_color="#24292f",
    border_color="#d0d7de",
    secondary_color="#57606a",
    track_color="#ebedf0",
    is_auto=True,
    dark_bg_color="#0d1117",
    dark_text_color="#e6edf3",
    dark_border_color="#30363d",
    dark_secondary_color="#8b949e",
    dark_track_color="#21262d",
)

THEMES: dict[str, Theme] = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
    "auto": AUTO_THEME,
}


def get_theme(name: str | None = None) -> Theme:
    """Retrieve theme by name, defaulting to light theme."""
    if not name:
        return LIGHT_THEME
    normalized = name.strip().lower()
    return THEMES.get(normalized, LIGHT_THEME)
