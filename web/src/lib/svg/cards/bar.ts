import { getTheme, getThemeCss } from "../themes";
import type { CachedUserStats } from "../types";
import { escapeXml, extractStatsData, roundTo } from "../utils";

export interface BarCardOptions {
  theme?: string;
  metric?: string;
  langsCount?: number;
  minPercent?: number;
  hideTitle?: boolean;
  title?: string;
  emptyMessage?: string;
}

export function generateBarCard(
  stats: Partial<CachedUserStats> | null | undefined,
  options: BarCardOptions = {}
): string {
  const {
    theme = "light",
    metric = "bytes",
    langsCount,
    minPercent,
    hideTitle = false,
    title,
    emptyMessage = "No language statistics found",
  } = options;

  const themeObj = getTheme(theme);
  const { username, languages, totalBytes, totalLines } = extractStatsData(
    stats,
    metric,
    langsCount,
    minPercent
  );

  const primaryMetricTotal = metric === "lines" ? totalLines : totalBytes;
  const hasStats = languages.length > 0 && primaryMetricTotal > 0;

  const barY = hideTitle ? 20 : 50;
  const legendStartY = barY + 28;
  const totalBarWidth = 445.0;
  let currentX = 25.0;

  const segments: Array<{
    x: number;
    width: number;
    color: string;
    escapedName: string;
    percentage: number;
  }> = [];

  const items: Array<{
    dotX: number;
    dotY: number;
    textX: number;
    textY: number;
    metricX: number;
    color: string;
    escapedName: string;
    percentage: number;
  }> = [];

  let height = 130;

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
        segWidth = Math.max(0.0, roundTo(25.0 + totalBarWidth - currentX, 2));
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

    // Legend items in 2 columns, ordered column-first
    const rowHeight = 24;
    const colSize = Math.ceil(languages.length / 2);
    for (let idx = 0; idx < languages.length; idx++) {
      const lang = languages[idx];
      const col = Math.floor(idx / colSize);
      const row = idx % colSize;
      const baseX = col === 0 ? 25 : 247;
      const dotY = legendStartY + row * rowHeight;
      const textY = dotY + 4;

      items.push({
        dotX: baseX + 5,
        dotY,
        textX: baseX + 18,
        textY,
        metricX: baseX + 120,
        color: lang.color,
        escapedName: lang.escapedName,
        percentage: lang.percentage,
      });
    }

    height = legendStartY + colSize * rowHeight + 16;
  }

  const cardTitle = escapeXml(
    title ? title : username ? `${username}'s Top Languages` : "Most Used Languages"
  );
  const escapedEmpty = escapeXml(emptyMessage);

  const lines: string[] = [
    `<svg width="495" height="${height}" viewBox="0 0 495 ${height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${cardTitle}">`,
    "  <style>",
    getThemeCss(themeObj),
    "    .card-bg { fill: var(--card-bg); stroke: var(--card-border); }",
    "    .card-track { fill: var(--card-track); }",
    '    .card-title { fill: var(--card-text); font-weight: 600; font-size: 15px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    '    .card-text { fill: var(--card-text); font-size: 12px; font-weight: 500; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    '    .card-secondary { fill: var(--card-secondary); font-size: 11px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    "  </style>",
    `  <rect x="0.5" y="0.5" width="494" height="${height - 1}" rx="6" class="card-bg" stroke="var(--card-border)"/>`,
  ];

  if (!hideTitle) {
    lines.push(`  <text x="25" y="32" class="card-title">${cardTitle}</text>`);
  }

  if (!hasStats) {
    lines.push(
      `  <text x="247.5" y="${height / 2 + 4}" class="card-secondary" text-anchor="middle" font-size="12">${escapedEmpty}</text>`
    );
  } else {
    lines.push(
      '  <clipPath id="bar-clip">',
      `    <rect x="25" y="${barY}" width="445" height="10" rx="5"/>`,
      "  </clipPath>",
      `  <rect x="25" y="${barY}" width="445" height="10" rx="5" class="card-track"/>`,
      '  <g clip-path="url(#bar-clip)">'
    );
    for (const seg of segments) {
      lines.push(
        `    <rect x="${seg.x}" y="${barY}" width="${seg.width}" height="10" fill="${seg.color}">`,
        `      <title>${seg.escapedName}: ${seg.percentage}%</title>`,
        "    </rect>"
      );
    }
    lines.push("  </g>", '  <g class="legend">');
    for (const item of items) {
      lines.push(
        `    <circle cx="${item.dotX}" cy="${item.dotY}" r="4.5" fill="${item.color}"/>`,
        `    <text x="${item.textX}" y="${item.textY}" class="card-text">${item.escapedName}</text>`,
        `    <text x="${item.metricX}" y="${item.textY}" class="card-secondary">${item.percentage}%</text>`
      );
    }
    lines.push("  </g>");
  }

  lines.push("</svg>");
  return lines.join("\n");
}
