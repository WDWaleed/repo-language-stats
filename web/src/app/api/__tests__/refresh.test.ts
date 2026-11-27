import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockSet, mockTtl, mockDel } = vi.hoisted(() => ({
  mockSet: vi.fn(),
  mockTtl: vi.fn(),
  mockDel: vi.fn(),
}));

vi.mock("@/lib/redis", () => ({
  redis: {
    set: mockSet,
    ttl: mockTtl,
    del: mockDel,
  },
}));

import { POST as postRefresh } from "../stats/[username]/refresh/route";

describe("POST /api/stats/[username]/refresh", () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    vi.clearAllMocks();
    process.env.GITHUB_WORKFLOW_TOKEN = "ghp_test_token";
    process.env.GITHUB_WORKFLOW_REPO = "WDWaleed/repo-language-stats";
    process.env.GITHUB_WORKFLOW_REF = "web";
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    vi.unstubAllGlobals();
  });

  it("returns 202 Accepted on first call and dispatches GitHub workflow", async () => {
    mockSet.mockResolvedValueOnce("OK");
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const req = new NextRequest("http://localhost:3000/api/stats/WDWaleed/refresh", {
      method: "POST",
    });
    const res = await postRefresh(req, {
      params: Promise.resolve({ username: "WDWaleed" }),
    });

    expect(res.status).toBe(202);
    const json = await res.json();
    expect(json.status).toBe("accepted");
    expect(json.retryAfter).toBe(600);
    expect(mockSet).toHaveBeenCalledWith(
      "ratelimit:refresh:WDWaleed",
      expect.any(String),
      { nx: true, ex: 600 }
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.github.com/repos/WDWaleed/repo-language-stats/actions/workflows/sync-stats.yml/dispatches",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("returns 429 Too Many Requests on immediate subsequent call", async () => {
    mockSet.mockResolvedValueOnce(null);
    mockTtl.mockResolvedValueOnce(595);

    const req = new NextRequest("http://localhost:3000/api/stats/WDWaleed/refresh", {
      method: "POST",
    });
    const res = await postRefresh(req, {
      params: Promise.resolve({ username: "WDWaleed" }),
    });

    expect(res.status).toBe(429);
    expect(res.headers.get("retry-after")).toBe("595");
    const json = await res.json();
    expect(json.retryAfter).toBe(595);
  });

  it("returns 503 and releases lock when GitHub token is not configured", async () => {
    delete process.env.GITHUB_WORKFLOW_TOKEN;
    delete process.env.GITHUB_TOKEN;
    mockSet.mockResolvedValueOnce("OK");

    const req = new NextRequest("http://localhost:3000/api/stats/WDWaleed/refresh", {
      method: "POST",
    });
    const res = await postRefresh(req, {
      params: Promise.resolve({ username: "WDWaleed" }),
    });

    expect(res.status).toBe(503);
    expect(mockDel).toHaveBeenCalledWith("ratelimit:refresh:WDWaleed");
  });
});
