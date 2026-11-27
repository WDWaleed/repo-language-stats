import { NextRequest, NextResponse } from "next/server";
import { redis } from "@/lib/redis";
import type { CachedUserStats } from "@/lib/svg/types";

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ username: string }> }
) {
  const { username } = await context.params;
  if (!username || !username.trim()) {
    return NextResponse.json({ error: "Username is required" }, { status: 400 });
  }

  try {
    const stats = await redis.get<CachedUserStats>(`stats:${username.trim()}`);
    if (!stats) {
      return NextResponse.json(
        { error: `No cached stats found for '${username}'` },
        { status: 404 }
      );
    }

    return NextResponse.json(stats, {
      status: 200,
      headers: {
        "Cache-Control": "public, max-age=300, s-maxage=300",
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to fetch stats";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
