import { getTheme, getThemeCss } from "../themes";
import type { CachedUserStats } from "../types";
import {
  computeDonutSlices,
  escapeXml,
  extractStatsData,
  formatBytes,
  formatNumber,
} from "../utils";

export interface DonutCardOptions {
  theme?: string;
  metric?: string;
  langsCount?: number;
  hideTitle?: boolean;
  title?: string;
  emptyMessage?: string;
}

export function generateDonutCard(
  stats: Partial<CachedUserStats> | null | undefined,
  options: DonutCardOptions = {}
): string {
  const {
    theme = "light",
    metric = "bytes",
    langsCount = 6,
    hideTitle = false,
    title,
    emptyMessage = "No language statistics found",
  } = options;

  const themeObj = getTheme(theme);
  const { username, languages, totalBytes, totalLines } = extractStatsData(
    stats,
    metric,
    langsCount
  );

  const primaryMetricTotal = metric === "lines" ? totalLines : totalBytes;
  const hasStats = languages.length > 0 && primaryMetricTotal > 0;

  const cx = 115.0;
  const cy = hideTitle ? 110.0 : 125.0;
  const rInner = 42.0;
  const rOuter = 68.0;

  const slices = hasStats
    ? computeDonutSlices(
        languages.map((l) => ({
          language: l.name,
          value: metric === "lines" ? l.lines : l.bytes,
          color: l.color,
        })),
        cx,
        cy,
        rInner,
        rOuter
      )
    : [];

  const centerMetric = hasStats
    ? metric === "lines"
      ? formatNumber(totalLines, true)
      : formatBytes(totalBytes, 1)
    : "0 B";
  const centerLabel = hasStats ? (metric === "lines" ? "LINES" : "BYTES") : "TOTAL";

  const legendStartY = hideTitle ? 45.0 : 60.0;
  const rowHeight = 24.0;
  const items = hasStats
    ? languages.map((lang, i) => {
        const dotY = legendStartY + i * rowHeight;
        return {
          dotX: 225,
          dotY,
          textX: 238,
          textY: dotY + 4,
          metricX: 470,
          color: lang.color,
          escapedName: lang.escapedName,
          percentage: lang.percentage,
        };
      })
    : [];

  const cardTitle = escapeXml(
    title ? title : username ? `${username}'s Top Languages` : "Most Used Languages"
  );
  const escapedEmpty = escapeXml(emptyMessage);

  const lines: string[] = [
    `<svg width="495" height="220" viewBox="0 0 495 220" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${cardTitle}">`,
    "  <style>",
    getThemeCss(themeObj),
    "    .card-bg { fill: var(--card-bg); stroke: var(--card-border); }",
    '    .card-title { fill: var(--card-text); font-weight: 600; font-size: 15px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    '    .card-text { fill: var(--card-text); font-size: 12px; font-weight: 500; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    '    .card-secondary { fill: var(--card-secondary); font-size: 11px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    '    .center-metric { fill: var(--card-text); font-weight: 600; font-size: 13px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    '    .center-label { fill: var(--card-secondary); font-size: 10px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    "  </style>",
    '  <rect x="0.5" y="0.5" width="494" height="219" rx="6" class="card-bg" stroke="var(--card-border)"/>',
  ];

  if (!hideTitle) {
    lines.push(`  <text x="25" y="32" class="card-title">${cardTitle}</text>`);
  }

  if (!hasStats) {
    lines.push(
      `  <text x="247.5" y="115" class="card-secondary" text-anchor="middle" font-size="12">${escapedEmpty}</text>`
    );
  } else {
    lines.push('  <g class="donut-chart">');
    for (const s of slices) {
      lines.push(
        `    <path d="${s.pathD}" fill="${s.color}">`,
        `      <title>${s.escapedLabel}: ${s.percentage}%</title>`,
        "    </path>"
      );
    }
    lines.push(
      `    <text x="${cx}" y="${cy + 1}" class="center-metric" text-anchor="middle">${centerMetric}</text>`,
      `    <text x="${cx}" y="${cy + 15}" class="center-label" text-anchor="middle">${centerLabel}</text>`,
      "  </g>",
      '  <g class="donut-legend">'
    );
    for (const item of items) {
      lines.push(
        `    <circle cx="${item.dotX}" cy="${item.dotY}" r="4.5" fill="${item.color}"/>`,
        `    <text x="${item.textX}" y="${item.textY}" class="card-text">${item.escapedName}</text>`,
        `    <text x="${item.metricX}" y="${item.textY}" class="card-secondary" text-anchor="end">${item.percentage}%</text>`
      );
    }
    lines.push("  </g>");
  }

  lines.push("</svg>");
  return lines.join("\n");
}
