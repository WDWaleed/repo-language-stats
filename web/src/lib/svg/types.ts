export type CardType = "bar" | "breakdown" | "donut" | "compact";
export type CardTheme = "light" | "dark" | "auto";
export type MetricType = "bytes" | "lines" | "both";

export interface LanguageEntry {
  language: string;
  bytes: number;
  byte_percent?: number;
  lines: number;
  line_percent?: number;
  files?: number;
  color?: string | null;
}

export interface CachedUserStats {
  username: string;
  repos_scanned: number;
  repos_skipped: number;
  total_bytes: number;
  total_lines: number;
  languages: LanguageEntry[];
  last_scanned?: string;
}

export interface RenderSvgOptions {
  cardType?: CardType | string;
  theme?: CardTheme | string;
  metric?: MetricType | string;
  langsCount?: number;
  showFiles?: boolean;
  hideTitle?: boolean;
  title?: string;
  emptyMessage?: string;
}

export interface ProcessedLanguage {
  name: string;
  escapedName: string;
  bytes: number;
  lines: number;
  files: number;
  color: string;
  bytePercent: number;
  linePercent: number;
  percentage: number;
  formattedMetric: string;
  bytesText: string;
  linesText: string;
  filesText: string;
}
