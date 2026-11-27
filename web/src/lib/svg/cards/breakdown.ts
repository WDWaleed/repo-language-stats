import { getTheme, getThemeCss } from "../themes";
import type { CachedUserStats } from "../types";
import { escapeXml, extractStatsData, formatBytes, formatNumber } from "../utils";

export interface BreakdownCardOptions {
  theme?: string;
  metric?: string;
  langsCount?: number;
  showFiles?: boolean;
  hideTitle?: boolean;
  title?: string;
  emptyMessage?: string;
}

export function generateBreakdownCard(
  stats: Partial<CachedUserStats> | null | undefined,
  options: BreakdownCardOptions = {}
): string {
  const {
    theme = "light",
    metric = "bytes",
    langsCount = 10,
    showFiles = false,
    hideTitle = false,
    title,
    emptyMessage = "No language statistics found",
  } = options;

  const themeObj = getTheme(theme);
  const { username, languages, totalBytes, totalLines, totalFiles } = extractStatsData(
    stats,
    metric,
    langsCount
  );

  const primaryMetricTotal = metric === "lines" ? totalLines : totalBytes;
  const hasStats = languages.length > 0 && primaryMetricTotal > 0;

  const showBytes = metric === "bytes" || metric === "both";
  const showLines = metric === "lines" || metric === "both";

  let bytesColX = 490;
  let linesColX = 490;
  const filesColX = 490;

  if (showBytes && showLines && showFiles) {
    bytesColX = 280;
    linesColX = 405;
  } else if (showBytes && showLines) {
    bytesColX = 330;
    linesColX = 490;
  } else if (showFiles) {
    bytesColX = showBytes ? 380 : 490;
    linesColX = showLines ? 380 : 490;
  }

  const headerY = hideTitle ? 30 : 55;
  const divY = headerY + 10;
  const rowStartY = divY + 22;
  const rowHeight = 26;

  let footerDivY = 0;
  let footerY = 0;
  let height = 140;

  if (hasStats) {
    footerDivY = rowStartY + languages.length * rowHeight - 4;
    footerY = footerDivY + 22;
    height = footerY + 16;
  }

  const cardTitle = escapeXml(
    title ? title : username ? `${username}'s Language Breakdown` : "Language Breakdown"
  );
  const escapedEmpty = escapeXml(emptyMessage);

  const lines: string[] = [
    `<svg width="520" height="${height}" viewBox="0 0 520 ${height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${cardTitle}">`,
    "  <style>",
    getThemeCss(themeObj),
    "    .card-bg { fill: var(--card-bg); stroke: var(--card-border); }",
    '    .card-title { fill: var(--card-text); font-weight: 600; font-size: 15px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    '    .card-header { fill: var(--card-secondary); font-size: 11px; font-weight: 600; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; text-transform: uppercase; letter-spacing: 0.5px; }',
    '    .card-text { fill: var(--card-text); font-size: 12px; font-weight: 500; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    '    .card-secondary { fill: var(--card-secondary); font-size: 11px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
    "    .divider { stroke: var(--card-border); stroke-width: 1; }",
    "  </style>",
    `  <rect x="0.5" y="0.5" width="519" height="${height - 1}" rx="6" class="card-bg" stroke="var(--card-border)"/>`,
  ];

  if (!hideTitle) {
    lines.push(`  <text x="25" y="32" class="card-title">${cardTitle}</text>`);
  }

  if (!hasStats) {
    lines.push(
      `  <text x="260" y="${height / 2 + 4}" class="card-secondary" text-anchor="middle" font-size="12">${escapedEmpty}</text>`
    );
  } else {
    lines.push(`  <text x="25" y="${headerY}" class="card-header">Language</text>`);
    if (showBytes) {
      lines.push(
        `  <text x="${bytesColX}" y="${headerY}" class="card-header" text-anchor="end">Bytes / %</text>`
      );
    }
    if (showLines) {
      lines.push(
        `  <text x="${linesColX}" y="${headerY}" class="card-header" text-anchor="end">Lines / %</text>`
      );
    }
    if (showFiles) {
      lines.push(
        `  <text x="${filesColX}" y="${headerY}" class="card-header" text-anchor="end">Files</text>`
      );
    }
    lines.push(`  <line x1="25" y1="${divY}" x2="495" y2="${divY}" class="divider"/>`);

    languages.forEach((lang, i) => {
      const rowY = rowStartY + i * rowHeight;
      lines.push(
        `  <circle cx="30" cy="${rowY - 4}" r="4.5" fill="${lang.color}"/>`,
        `  <text x="42" y="${rowY}" class="card-text">${lang.escapedName}</text>`
      );
      if (showBytes) {
        lines.push(
          `  <text x="${bytesColX}" y="${rowY}" class="card-secondary" text-anchor="end">${lang.bytesText} (${lang.bytePercent}%)</text>`
        );
      }
      if (showLines) {
        lines.push(
          `  <text x="${linesColX}" y="${rowY}" class="card-secondary" text-anchor="end">${lang.linesText} (${lang.linePercent}%)</text>`
        );
      }
      if (showFiles) {
        lines.push(
          `  <text x="${filesColX}" y="${rowY}" class="card-secondary" text-anchor="end">${lang.filesText}</text>`
        );
      }
    });

    lines.push(
      `  <line x1="25" y1="${footerDivY}" x2="495" y2="${footerDivY}" class="divider"/>`,
      `  <text x="25" y="${footerY}" class="card-title" font-size="12">TOTAL</text>`
    );
    if (showBytes) {
      lines.push(
        `  <text x="${bytesColX}" y="${footerY}" class="card-text" text-anchor="end" font-weight="600">${formatBytes(totalBytes)}</text>`
      );
    }
    if (showLines) {
      lines.push(
        `  <text x="${linesColX}" y="${footerY}" class="card-text" text-anchor="end" font-weight="600">${formatNumber(totalLines, false)}</text>`
      );
    }
    if (showFiles) {
      lines.push(
        `  <text x="${filesColX}" y="${footerY}" class="card-text" text-anchor="end" font-weight="600">${formatNumber(totalFiles, false)}</text>`
      );
    }
  }

  lines.push("</svg>");
  return lines.join("\n");
}
