import type { CardTheme } from "./types";

export interface ThemePalette {
  name: CardTheme;
  bgColor: string;
  textColor: string;
  borderColor: string;
  secondaryColor: string;
  trackColor: string;
  isAuto: boolean;
  darkBgColor: string;
  darkTextColor: string;
  darkBorderColor: string;
  darkSecondaryColor: string;
  darkTrackColor: string;
}

export const LIGHT_THEME: ThemePalette = {
  name: "light",
  bgColor: "#ffffff",
  textColor: "#24292f",
  borderColor: "#d0d7de",
  secondaryColor: "#57606a",
  trackColor: "#ebedf0",
  isAuto: false,
  darkBgColor: "#0d1117",
  darkTextColor: "#e6edf3",
  darkBorderColor: "#30363d",
  darkSecondaryColor: "#8b949e",
  darkTrackColor: "#21262d",
};

export const DARK_THEME: ThemePalette = {
  name: "dark",
  bgColor: "#0d1117",
  textColor: "#e6edf3",
  borderColor: "#30363d",
  secondaryColor: "#8b949e",
  trackColor: "#21262d",
  isAuto: false,
  darkBgColor: "#0d1117",
  darkTextColor: "#e6edf3",
  darkBorderColor: "#30363d",
  darkSecondaryColor: "#8b949e",
  darkTrackColor: "#21262d",
};

export const AUTO_THEME: ThemePalette = {
  name: "auto",
  bgColor: "#ffffff",
  textColor: "#24292f",
  borderColor: "#d0d7de",
  secondaryColor: "#57606a",
  trackColor: "#ebedf0",
  isAuto: true,
  darkBgColor: "#0d1117",
  darkTextColor: "#e6edf3",
  darkBorderColor: "#30363d",
  darkSecondaryColor: "#8b949e",
  darkTrackColor: "#21262d",
};

const THEMES: Record<string, ThemePalette> = {
  light: LIGHT_THEME,
  dark: DARK_THEME,
  auto: AUTO_THEME,
};

export function getTheme(name?: string | null): ThemePalette {
  if (!name) return LIGHT_THEME;
  const normalized = name.trim().toLowerCase();
  return THEMES[normalized] ?? LIGHT_THEME;
}

export function getThemeCss(theme: ThemePalette): string {
  if (theme.isAuto) {
    return [
      ":root {",
      `  --card-bg: ${theme.bgColor};`,
      `  --card-text: ${theme.textColor};`,
      `  --card-border: ${theme.borderColor};`,
      `  --card-secondary: ${theme.secondaryColor};`,
      `  --card-track: ${theme.trackColor};`,
      "}",
      "@media (prefers-color-scheme: dark) {",
      "  :root {",
      `    --card-bg: ${theme.darkBgColor};`,
      `    --card-text: ${theme.darkTextColor};`,
      `    --card-border: ${theme.darkBorderColor};`,
      `    --card-secondary: ${theme.darkSecondaryColor};`,
      `    --card-track: ${theme.darkTrackColor};`,
      "  }",
      "}",
    ].join("\n");
  }

  return [
    ":root {",
    `  --card-bg: ${theme.bgColor};`,
    `  --card-text: ${theme.textColor};`,
    `  --card-border: ${theme.borderColor};`,
    `  --card-secondary: ${theme.secondaryColor};`,
    `  --card-track: ${theme.trackColor};`,
    "}",
  ].join("\n");
}
