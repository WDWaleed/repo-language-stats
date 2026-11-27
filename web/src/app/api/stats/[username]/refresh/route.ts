import { NextRequest, NextResponse } from "next/server";
import { redis } from "@/lib/redis";

const COOLDOWN_SECONDS = 600; // 10 minutes (Decision D5)

export async function POST(
  _request: NextRequest,
  context: { params: Promise<{ username: string }> }
) {
  const { username } = await context.params;
  const cleanUser = username?.trim();
  if (!cleanUser) {
    return NextResponse.json({ error: "Username is required" }, { status: 400 });
  }

  const rateKey = `ratelimit:refresh:${cleanUser}`;

  // Check / acquire 10-minute cooldown lock
  const acquired = await redis.set(rateKey, String(Date.now()), {
    nx: true,
    ex: COOLDOWN_SECONDS,
  });

  if (acquired === null) {
    const ttl = await redis.ttl(rateKey);
    const retryAfter = ttl > 0 ? ttl : COOLDOWN_SECONDS;
    return NextResponse.json(
      {
        error: `Refresh cooldown active. Try again in ${retryAfter}s.`,
        retryAfter,
      },
      {
        status: 429,
        headers: { "Retry-After": String(retryAfter) },
      }
    );
  }

  const githubToken =
    process.env.GITHUB_WORKFLOW_TOKEN || process.env.GITHUB_TOKEN;
  const repo =
    process.env.GITHUB_WORKFLOW_REPO || process.env.GITHUB_REPOSITORY;
  const workflowId = process.env.GITHUB_WORKFLOW_ID || "sync-stats.yml";
  const ref = process.env.GITHUB_WORKFLOW_REF || "main";

  if (!githubToken || !repo) {
    await redis.del(rateKey);
    return NextResponse.json(
      {
        error:
          "Server is missing GITHUB_WORKFLOW_TOKEN or GITHUB_WORKFLOW_REPO configuration.",
      },
      { status: 503 }
    );
  }

  const dispatchUrl = `https://api.github.com/repos/${repo}/actions/workflows/${workflowId}/dispatches`;

  try {
    const ghRes = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${githubToken}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref }),
    });

    if (!ghRes.ok) {
      await redis.del(rateKey);
      const errText = await ghRes.text().catch(() => ghRes.statusText);
      return NextResponse.json(
        { error: `GitHub dispatch failed (${ghRes.status}): ${errText}` },
        { status: 502 }
      );
    }

    return NextResponse.json(
      {
        status: "accepted",
        username: cleanUser,
        message: "Refresh workflow dispatched. Stats will update shortly.",
        retryAfter: COOLDOWN_SECONDS,
      },
      { status: 202 }
    );
  } catch (err) {
    await redis.del(rateKey);
    const message =
      err instanceof Error ? err.message : "Failed to reach GitHub API";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
