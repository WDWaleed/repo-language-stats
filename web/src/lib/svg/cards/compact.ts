import { getTheme, getThemeCss } from "../themes";
import type { CachedUserStats } from "../types";
import { escapeXml, extractStatsData, roundTo } from "../utils";

export interface CompactCardOptions {
  theme?: string;
  metric?: string;
  langsCount?: number;
  title?: string;
  emptyMessage?: string;
}

export function generateCompactCard(
  stats: Partial<CachedUserStats> | null | undefined,
  options: CompactCardOptions = {}
): string {
  const {
    theme = "light",
    metric = "bytes",
    langsCount = 4,
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

  const totalBarWidth = 471.0;
  let currentX = 12.0;

  const segments: Array<{
    x: number;
    width: number;
    color: string;
    escapedName: string;
    percentage: number;
  }> = [];

  if (hasStats) {
    const topMetricSum = languages.reduce(
      (sum, l) => sum + (metric === "lines" ? l.lines : l.bytes),
      0
    );

    for (let i = 0; i < languages.length; i++) {
      const lang = languages[i];
      const val = metric === "lines" ? lang.lines : lang.bytes;
      let segWidth = topMetricSum > 0 ? roundTo((val / topMetricSum) * totalBarWidth, 2) : 0.0;

      if (i === languages.length - 1) {
        segWidth = Math.max(0.0, roundTo(12.0 + totalBarWidth - currentX, 2));
      }

      segments.push({
        x: roundTo(currentX, 2),
        width: segWidth,
        color: lang.color,
        escapedName: lang.escapedName,
        percentage: lang.percentage,
      });
      currentX += segWidth;
    }
  }

  const cardTitle = escapeXml(
    title ? title : username ? `${username}'s Language Stats` : "Language Stats"
  );
  const escapedEmpty = escapeXml(emptyMessage);

  const lines: string[] = [
    `<svg width="495" height="32" viewBox="0 0 495 32" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${cardTitle}">`,
    "  <style>",
    getThemeCss(themeObj),
    "    .card-bg { fill: var(--card-bg); stroke: var(--card-border); }",
    "    .card-track { fill: var(--card-track); }",
    '    .card-secondary { fill: var(--card-secondary); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    "  </style>",
    '  <rect x="0.5" y="0.5" width="494" height="31" rx="6" class="card-bg" stroke="var(--card-border)"/>',
  ];

  if (!hasStats) {
    lines.push(
      `  <text x="247.5" y="20" class="card-secondary" text-anchor="middle" font-size="11">${escapedEmpty}</text>`
    );
  } else {
    lines.push(
      '  <clipPath id="compact-clip">',
      '    <rect x="12" y="9" width="471" height="14" rx="4"/>',
      "  </clipPath>",
      '  <rect x="12" y="9" width="471" height="14" rx="4" class="card-track"/>',
      '  <g clip-path="url(#compact-clip)">'
    );
    for (const seg of segments) {
      lines.push(
        `    <rect x="${seg.x}" y="9" width="${seg.width}" height="14" fill="${seg.color}">`,
        `      <title>${seg.escapedName}: ${seg.percentage}%</title>`,
        "    </rect>"
      );
    }
    lines.push("  </g>");
  }

  lines.push("</svg>");
  return lines.join("\n");
}
