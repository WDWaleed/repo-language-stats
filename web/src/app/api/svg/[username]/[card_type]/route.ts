import { createHash } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { redis } from "@/lib/redis";
import {
  renderSvg,
  VALID_CARD_TYPES,
  VALID_METRICS,
  VALID_THEMES,
} from "@/lib/svg/renderer";
import type { CachedUserStats } from "@/lib/svg/types";

const CACHE_CONTROL_HEADER =
  "public, max-age=14400, s-maxage=14400, stale-while-revalidate=3600";

const NOT_SCANNED_MESSAGE = "User not scanned yet. Visit dashboard to sync";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ username: string; card_type: string }> }
) {
  const { username, card_type } = await context.params;
  const normalizedCardType = card_type.trim().toLowerCase();

  if (!VALID_CARD_TYPES.has(normalizedCardType)) {
    return NextResponse.json(
      {
        error: `Invalid card_type '${card_type}'. Must be one of: bar, breakdown, donut, compact.`,
      },
      { status: 400 }
    );
  }

  const { searchParams } = request.nextUrl;
  const rawTheme = (searchParams.get("theme") ?? "light").trim().toLowerCase();
  const theme = VALID_THEMES.has(rawTheme) ? rawTheme : "light";

  const rawMetric = (searchParams.get("metric") ?? "bytes").trim().toLowerCase();
  const metric = VALID_METRICS.has(rawMetric) ? rawMetric : "bytes";

  const rawLangsCount = searchParams.get("langs_count");
  let langsCount: number | undefined;
  if (rawLangsCount !== null) {
    const parsed = Number.parseInt(rawLangsCount, 10);
    if (!Number.isNaN(parsed) && parsed > 0 && parsed <= 50) {
      langsCount = parsed;
    }
  }

  const showFiles = searchParams.get("show_files") === "true";
  const hideTitle = searchParams.get("hide_title") === "true";
  const customTitle = searchParams.get("title") ?? undefined;

  let stats: CachedUserStats | null = null;
  try {
    stats = await redis.get<CachedUserStats>(`stats:${username}`);
  } catch {
    // Fall back to empty/not-scanned SVG with HTTP 200 (Decision D7)
    stats = null;
  }

  const svg = renderSvg(stats, {
    cardType: normalizedCardType,
    theme,
    metric,
    langsCount,
    showFiles,
    hideTitle,
    title: customTitle,
    emptyMessage: stats ? undefined : NOT_SCANNED_MESSAGE,
  });

  const etag = `"${createHash("sha256").update(svg).digest("hex").slice(0, 16)}"`;
  const ifNoneMatch = request.headers.get("if-none-match");

  if (ifNoneMatch && ifNoneMatch === etag) {
    return new NextResponse(null, {
      status: 304,
      headers: {
        ETag: etag,
        "Cache-Control": CACHE_CONTROL_HEADER,
      },
    });
  }

  return new NextResponse(svg, {
    status: 200,
    headers: {
      "Content-Type": "image/svg+xml; charset=utf-8",
      "Cache-Control": CACHE_CONTROL_HEADER,
      ETag: etag,
      "X-Content-Type-Options": "nosniff",
    },
  });
}
