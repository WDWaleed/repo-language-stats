import linguistColors from "../linguist-colors.json";
import type { CachedUserStats, ProcessedLanguage } from "./types";

const COLOR_MAP: Record<string, string> = linguistColors as Record<string, string>;
const LOWER_COLOR_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(COLOR_MAP).map(([k, v]) => [k.toLowerCase(), v])
);

export function escapeXml(text: unknown): string {
  if (text === null || text === undefined) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function formatBytes(bytesCount: number, precision = 1): string {
  if (bytesCount < 0) return `-${formatBytes(-bytesCount, precision)}`;
  let count = Number(bytesCount);
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let unitIdx = 0;
  while (count >= 1024.0 && unitIdx < units.length - 1) {
    count /= 1024.0;
    unitIdx++;
  }
  if (unitIdx === 0) return `${Math.trunc(count)} B`;
  return `${count.toFixed(precision)} ${units[unitIdx]}`;
}

export function formatNumber(n: number, compact = true): string {
  if (n < 0) return `-${formatNumber(-n, compact)}`;
  const val = Number(n);
  if (!compact) {
    return Number.isInteger(val)
      ? val.toLocaleString("en-US")
      : val.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }
  if (val < 1000) {
    return Number.isInteger(val) ? String(val) : val.toFixed(1);
  }
  if (val < 1_000_000) {
    const k = val / 1000.0;
    return k < 100 ? `${k.toFixed(1)}k` : `${Math.round(k)}k`;
  }
  if (val < 1_000_000_000) {
    const m = val / 1_000_000.0;
    return m < 100 ? `${m.toFixed(1)}M` : `${Math.round(m)}M`;
  }
  const b = val / 1_000_000_000.0;
  return b < 100 ? `${b.toFixed(1)}B` : `${Math.round(b)}B`;
}

export function resolveLanguageColor(language: string, fallback = "#8b949e"): string {
  if (!language) return fallback;
  if (COLOR_MAP[language]) return COLOR_MAP[language];
  const lower = language.trim().toLowerCase();
  if (LOWER_COLOR_MAP[lower]) return LOWER_COLOR_MAP[lower];
  return fallback;
}

export function roundTo(num: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round((num + Number.EPSILON) * factor) / factor;
}

export function polarToCartesian(
  cx: number,
  cy: number,
  radius: number,
  angleInDegrees: number
): [number, number] {
  const angleInRadians = ((angleInDegrees - 90.0) * Math.PI) / 180.0;
  const x = cx + radius * Math.cos(angleInRadians);
  const y = cy + radius * Math.sin(angleInRadians);
  return [roundTo(x, 3), roundTo(y, 3)];
}

export function describeDonutArc(
  cx: number,
  cy: number,
  rInner: number,
  rOuter: number,
  startAngle: number,
  endAngle: number
): string {
  const angleDiff = endAngle - startAngle;
  if (angleDiff <= 0) return "";

  if (angleDiff >= 360.0) {
    const midAngle = startAngle + 180.0;
    const part1 = describeDonutArc(cx, cy, rInner, rOuter, startAngle, midAngle);
    const part2 = describeDonutArc(cx, cy, rInner, rOuter, midAngle, startAngle + 360.0);
    return `${part1} ${part2}`;
  }

  const largeArcFlag = angleDiff > 180.0 ? 1 : 0;
  const startOuter = polarToCartesian(cx, cy, rOuter, startAngle);
  const endOuter = polarToCartesian(cx, cy, rOuter, endAngle);

  if (rInner <= 0) {
    return [
      `M ${cx} ${cy}`,
      `L ${startOuter[0]} ${startOuter[1]}`,
      `A ${rOuter} ${rOuter} 0 ${largeArcFlag} 1 ${endOuter[0]} ${endOuter[1]}`,
      "Z",
    ].join(" ");
  }

  const endInner = polarToCartesian(cx, cy, rInner, endAngle);
  const startInner = polarToCartesian(cx, cy, rInner, startAngle);

  return [
    `M ${startOuter[0]} ${startOuter[1]}`,
    `A ${rOuter} ${rOuter} 0 ${largeArcFlag} 1 ${endOuter[0]} ${endOuter[1]}`,
    `L ${endInner[0]} ${endInner[1]}`,
    `A ${rInner} ${rInner} 0 ${largeArcFlag} 0 ${startInner[0]} ${startInner[1]}`,
    "Z",
  ].join(" ");
}

export interface DonutSlice {
  label: string;
  escapedLabel: string;
  value: number;
  percentage: number;
  color: string;
  startAngle: number;
  endAngle: number;
  pathD: string;
}

export function computeDonutSlices(
  items: Array<{ language: string; value: number; color?: string }>,
  cx: number,
  cy: number,
  rInner: number,
  rOuter: number
): DonutSlice[] {
  const total = items.reduce((acc, item) => acc + item.value, 0);
  if (total <= 0) return [];

  const slices: DonutSlice[] = [];
  let currentAngle = 0.0;
  for (const item of items) {
    if (item.value <= 0) continue;
    const pct = (item.value / total) * 100.0;
    const angleSpan = (item.value / total) * 360.0;
    const endAngle = currentAngle + angleSpan;
    const color = item.color || resolveLanguageColor(item.language);
    const pathD = describeDonutArc(cx, cy, rInner, rOuter, currentAngle, endAngle);

    slices.push({
      label: item.language,
      escapedLabel: escapeXml(item.language),
      value: item.value,
      percentage: roundTo(pct, 2),
      color,
      startAngle: roundTo(currentAngle, 2),
      endAngle: roundTo(endAngle, 2),
      pathD,
    });
    currentAngle = endAngle;
  }

  return slices;
}

export function extractStatsData(
  stats: Partial<CachedUserStats> | null | undefined,
  metric = "bytes",
  langsCount?: number,
  minPercent?: number
): {
  username: string;
  languages: ProcessedLanguage[];
  totalBytes: number;
  totalLines: number;
  totalFiles: number;
} {
  if (!stats) {
    return { username: "", languages: [], totalBytes: 0, totalLines: 0, totalFiles: 0 };
  }

  const username = String(stats.username ?? "");
  const rawList = Array.isArray(stats.languages) ? stats.languages : [];

  let totalBytes = Number(stats.total_bytes ?? 0);
  let totalLines = Number(stats.total_lines ?? 0);
  const totalFiles = rawList.reduce((acc, item) => acc + Number(item.files ?? 0), 0);

  if (totalBytes === 0) {
    totalBytes = rawList.reduce((acc, item) => acc + Number(item.bytes ?? 0), 0);
  }
  if (totalLines === 0) {
    totalLines = rawList.reduce((acc, item) => acc + Number(item.lines ?? 0), 0);
  }

  const sorted = [...rawList].sort((a, b) => {
    if (metric === "lines") {
      if (b.lines !== a.lines) return b.lines - a.lines;
      if (b.bytes !== a.bytes) return b.bytes - a.bytes;
    } else {
      if (b.bytes !== a.bytes) return b.bytes - a.bytes;
      if (b.lines !== a.lines) return b.lines - a.lines;
    }
    return b.language.localeCompare(a.language);
  });

  const sliced = langsCount && langsCount > 0 ? sorted.slice(0, langsCount) : sorted;

  // Apply minPercent threshold (before langsCount cap, used by bar card)
  let candidates = sliced;
  if (minPercent !== undefined && minPercent > 0) {
    const denominator = metric === "lines" ? totalLines : totalBytes;
    if (denominator > 0) {
      const filtered = sorted.filter((item) => {
        const val = metric === "lines" ? Number(item.lines ?? 0) : Number(item.bytes ?? 0);
        return (val / denominator) * 100.0 >= minPercent;
      });
      candidates = filtered.length > 0 ? filtered : sorted.slice(0, 1);
    }
    // Apply explicit langsCount cap after threshold
    if (langsCount && langsCount > 0) {
      candidates = candidates.slice(0, langsCount);
    }
  }

  const languages: ProcessedLanguage[] = candidates.map((item) => {
    const b = Number(item.bytes ?? 0);
    const l = Number(item.lines ?? 0);
    const f = Number(item.files ?? 0);
    const color = item.color || resolveLanguageColor(item.language);
    const bPct = totalBytes > 0 ? (b / totalBytes) * 100.0 : 0.0;
    const lPct = totalLines > 0 ? (l / totalLines) * 100.0 : 0.0;
    const activePct = metric === "lines" ? lPct : bPct;
    const formattedMetric =
      metric === "lines" ? `${formatNumber(l, true)} lines` : formatBytes(b);

    return {
      name: item.language,
      escapedName: escapeXml(item.language),
      bytes: b,
      lines: l,
      files: f,
      color,
      bytePercent: roundTo(bPct, 1),
      linePercent: roundTo(lPct, 1),
      percentage: roundTo(activePct, 1),
      formattedMetric,
      bytesText: formatBytes(b),
      linesText: formatNumber(l, false),
      filesText: formatNumber(f, false),
    };
  });

  return { username, languages, totalBytes, totalLines, totalFiles };
}
