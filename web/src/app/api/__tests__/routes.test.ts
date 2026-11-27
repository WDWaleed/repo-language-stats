import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CachedUserStats } from "@/lib/svg/types";

const { mockGet, mockPing } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPing: vi.fn(),
}));

vi.mock("@/lib/redis", () => ({
  redis: {
    get: mockGet,
    ping: mockPing,
  },
}));

import { GET as getHealth } from "../health/route";
import { GET as getStats } from "../stats/[username]/route";
import { GET as getSvg } from "../svg/[username]/[card_type]/route";

const SAMPLE_STATS: CachedUserStats = {
  username: "WDWaleed",
  repos_scanned: 29,
  repos_skipped: 1,
  total_bytes: 100000,
  total_lines: 3000,
  languages: [
    { language: "Python", bytes: 60000, lines: 1800, files: 15, color: "#3572A5" },
    { language: "TypeScript", bytes: 40000, lines: 1200, files: 10, color: "#3178c6" },
  ],
  last_scanned: "2026-11-27T04:00:00Z",
};

describe("API routes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("GET /api/svg/[username]/[card_type]", () => {
    it("returns 200 with image/svg+xml, Cache-Control, and ETag", async () => {
      mockGet.mockResolvedValueOnce(SAMPLE_STATS);
      const req = new NextRequest("http://localhost:3000/api/svg/WDWaleed/bar");
      const res = await getSvg(req, {
        params: Promise.resolve({ username: "WDWaleed", card_type: "bar" }),
      });

      expect(res.status).toBe(200);
      expect(res.headers.get("content-type")).toContain("image/svg+xml");
      expect(res.headers.get("cache-control")).toContain("max-age=14400");
      expect(res.headers.get("etag")).toMatch(/^"[a-f0-9]{16}"$/);

      const body = await res.text();
      expect(body).toContain("<svg ");
      expect(body).toContain("Python");
    });

    it("returns 304 Not Modified when If-None-Match matches ETag", async () => {
      mockGet.mockResolvedValue(SAMPLE_STATS);
      const req1 = new NextRequest("http://localhost:3000/api/svg/WDWaleed/donut");
      const res1 = await getSvg(req1, {
        params: Promise.resolve({ username: "WDWaleed", card_type: "donut" }),
      });
      const etag = res1.headers.get("etag");
      expect(etag).toBeTruthy();

      const req2 = new NextRequest("http://localhost:3000/api/svg/WDWaleed/donut", {
        headers: { "if-none-match": etag! },
      });
      const res2 = await getSvg(req2, {
        params: Promise.resolve({ username: "WDWaleed", card_type: "donut" }),
      });

      expect(res2.status).toBe(304);
      expect(res2.headers.get("etag")).toBe(etag);
    });

    it("applies theme, metric, and langs_count query parameters", async () => {
      mockGet.mockResolvedValueOnce(SAMPLE_STATS);
      const req = new NextRequest(
        "http://localhost:3000/api/svg/WDWaleed/bar?theme=dark&metric=lines&langs_count=1"
      );
      const res = await getSvg(req, {
        params: Promise.resolve({ username: "WDWaleed", card_type: "bar" }),
      });

      expect(res.status).toBe(200);
      const body = await res.text();
      expect(body).toContain("--card-bg: #0d1117");
      expect(body).toContain("Python");
      expect(body).not.toContain("TypeScript");
    });

    it("returns 400 for invalid card_type", async () => {
      const req = new NextRequest("http://localhost:3000/api/svg/WDWaleed/pie");
      const res = await getSvg(req, {
        params: Promise.resolve({ username: "WDWaleed", card_type: "pie" }),
      });

      expect(res.status).toBe(400);
      const json = await res.json();
      expect(json.error).toContain("Invalid card_type");
    });

    it("returns 200 fallback SVG when user is not in Redis (Decision D7)", async () => {
      mockGet.mockResolvedValueOnce(null);
      const req = new NextRequest("http://localhost:3000/api/svg/unknown/bar");
      const res = await getSvg(req, {
        params: Promise.resolve({ username: "unknown", card_type: "bar" }),
      });

      expect(res.status).toBe(200);
      expect(res.headers.get("content-type")).toContain("image/svg+xml");
      const body = await res.text();
      expect(body).toContain("User not scanned yet. Visit dashboard to sync");
    });
  });

  describe("GET /api/stats/[username]", () => {
    it("returns 200 JSON when stats exist", async () => {
      mockGet.mockResolvedValueOnce(SAMPLE_STATS);
      const req = new NextRequest("http://localhost:3000/api/stats/WDWaleed");
      const res = await getStats(req, {
        params: Promise.resolve({ username: "WDWaleed" }),
      });

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json.username).toBe("WDWaleed");
      expect(json.languages).toHaveLength(2);
    });

    it("returns 404 when stats are missing", async () => {
      mockGet.mockResolvedValueOnce(null);
      const req = new NextRequest("http://localhost:3000/api/stats/missing");
      const res = await getStats(req, {
        params: Promise.resolve({ username: "missing" }),
      });

      expect(res.status).toBe(404);
    });
  });

  describe("GET /api/health", () => {
    it("returns 200 when Redis responds PONG", async () => {
      mockPing.mockResolvedValueOnce("PONG");
      const res = await getHealth();

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json.status).toBe("ok");
      expect(json.redis).toBe("connected");
    });

    it("returns 503 when Redis ping throws", async () => {
      mockPing.mockRejectedValueOnce(new Error("timeout"));
      const res = await getHealth();

      expect(res.status).toBe(503);
      const json = await res.json();
      expect(json.status).toBe("error");
      expect(json.redis).toBe("disconnected");
    });
  });
});
