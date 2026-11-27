import { generateBarCard } from "./cards/bar";
import { generateBreakdownCard } from "./cards/breakdown";
import { generateCompactCard } from "./cards/compact";
import { generateDonutCard } from "./cards/donut";
import type { CachedUserStats, CardType, RenderSvgOptions } from "./types";

export const VALID_CARD_TYPES: ReadonlySet<string> = new Set([
  "bar",
  "breakdown",
  "donut",
  "compact",
]);

export const VALID_THEMES: ReadonlySet<string> = new Set([
  "light",
  "dark",
  "auto",
]);

export const VALID_METRICS: ReadonlySet<string> = new Set([
  "bytes",
  "lines",
  "both",
]);

export function renderSvg(
  stats: Partial<CachedUserStats> | null | undefined,
  options: RenderSvgOptions = {}
): string {
  const cardType = String(options.cardType ?? "bar").trim().toLowerCase() as CardType;
  const theme = String(options.theme ?? "light").trim().toLowerCase();
  const metric = String(options.metric ?? "bytes").trim().toLowerCase();

  switch (cardType) {
    case "bar":
      return generateBarCard(stats, {
        theme,
        metric: metric === "both" ? "bytes" : metric,
        langsCount: options.langsCount ?? 8,
        hideTitle: options.hideTitle ?? false,
        title: options.title,
        emptyMessage: options.emptyMessage,
      });
    case "breakdown":
      return generateBreakdownCard(stats, {
        theme,
        metric,
        langsCount: options.langsCount ?? 10,
        showFiles: options.showFiles ?? false,
        hideTitle: options.hideTitle ?? false,
        title: options.title,
        emptyMessage: options.emptyMessage,
      });
    case "donut":
      return generateDonutCard(stats, {
        theme,
        metric: metric === "both" ? "bytes" : metric,
        langsCount: options.langsCount ?? 6,
        hideTitle: options.hideTitle ?? false,
        title: options.title,
        emptyMessage: options.emptyMessage,
      });
    case "compact":
      return generateCompactCard(stats, {
        theme,
        metric: metric === "both" ? "bytes" : metric,
        langsCount: options.langsCount ?? 4,
        title: options.title,
        emptyMessage: options.emptyMessage,
      });
    default:
      throw new Error(`Unsupported cardType: ${cardType}`);
  }
}
