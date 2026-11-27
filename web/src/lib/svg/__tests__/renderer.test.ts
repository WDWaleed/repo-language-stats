import { describe, expect, it } from "vitest";
import { renderSvg } from "../renderer";
import type { CachedUserStats } from "../types";
import { escapeXml, formatBytes, resolveLanguageColor } from "../utils";

const SAMPLE_STATS: CachedUserStats = {
  username: "WDWaleed",
  repos_scanned: 29,
  repos_skipped: 1,
  total_bytes: 100000,
  total_lines: 3000,
  languages: [
    { language: "Python", bytes: 50000, lines: 1500, files: 20, color: "#3572A5" },
    { language: "TypeScript", bytes: 30000, lines: 900, files: 12, color: "#3178c6" },
    { language: "JavaScript", bytes: 15000, lines: 450, files: 8, color: "#f1e05a" },
    { language: "CSS", bytes: 5000, lines: 150, files: 4, color: "#663399" },
  ],
};

/** Stats fixture with one tiny language well below 1% */
const STATS_WITH_TINY: CachedUserStats = {
  username: "tester",
  repos_scanned: 1,
  repos_skipped: 0,
  total_bytes: 100000,
  total_lines: 10000,
  languages: [
    { language: "Python", bytes: 95000, lines: 9500, files: 10 },
    { language: "TypeScript", bytes: 4500, lines: 400, files: 5 },
    { language: "Tiny", bytes: 500, lines: 100, files: 1 }, // 0.5% — below threshold
  ],
};

/** Stats fixture with 10 languages each at ~10% */
const STATS_10_LANGS: CachedUserStats = {
  username: "tester",
  repos_scanned: 1,
  repos_skipped: 0,
  total_bytes: 100000,
  total_lines: 10000,
  languages: Array.from({ length: 10 }, (_, i) => ({
    language: `Lang${i}`,
    bytes: 10000,
    lines: 1000,
    files: 1,
  })),
};

describe("SVG utils", () => {
  it("escapes XML special characters", () => {
    expect(escapeXml('<script>"a"&\'b\'</script>')).toBe(
      "&lt;script&gt;&quot;a&quot;&amp;&apos;b&apos;&lt;/script&gt;"
    );
  });

  it("formats bytes cleanly", () => {
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(1048576)).toBe("1.0 MB");
  });

  it("resolves Linguist colors", () => {
    expect(resolveLanguageColor("Python")).toBe("#3572A5");
    expect(resolveLanguageColor("python")).toBe("#3572A5");
    expect(resolveLanguageColor("UnknownLang123")).toBe("#8b949e");
  });
});

describe("renderSvg", () => {
  it.each(["bar", "breakdown", "donut", "compact"] as const)(
    "renders valid SVG root for cardType=%s",
    (cardType) => {
      const svg = renderSvg(SAMPLE_STATS, { cardType });
      expect(svg.startsWith("<svg ")).toBe(true);
      expect(svg.endsWith("</svg>")).toBe(true);
      expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"');
      expect(svg).toContain("Python");
    }
  );

  it("applies light, dark, and auto themes", () => {
    const light = renderSvg(SAMPLE_STATS, { cardType: "bar", theme: "light" });
    expect(light).toContain("--card-bg: #ffffff");

    const dark = renderSvg(SAMPLE_STATS, { cardType: "bar", theme: "dark" });
    expect(dark).toContain("--card-bg: #0d1117");

    const auto = renderSvg(SAMPLE_STATS, { cardType: "bar", theme: "auto" });
    expect(auto).toContain("@media (prefers-color-scheme: dark)");
  });

  it("orders bar legend column-first and shows percentage only", () => {
    const svg = renderSvg(SAMPLE_STATS, { cardType: "bar" });
    // 4 langs -> colSize = 2. Col 0 (x=43): Python, TypeScript. Col 1 (x=265): JavaScript, CSS.
    expect(svg).toContain('<text x="43" y="82" class="card-text">Python</text>');
    expect(svg).toContain('<text x="43" y="106" class="card-text">TypeScript</text>');
    expect(svg).toContain('<text x="265" y="82" class="card-text">JavaScript</text>');
    expect(svg).toContain('<text x="265" y="106" class="card-text">CSS</text>');
    expect(svg).toContain(">50%</text>");
    expect(svg).not.toContain("48.8 KB");
  });

  it("renders donut legend with names and percentages", () => {
    const svg = renderSvg(SAMPLE_STATS, { cardType: "donut" });
    expect(svg).toContain('<g class="donut-legend">');
    expect(svg).toContain("Python");
    expect(svg).toContain("50%</text>");
    expect(svg).toContain("<path d=");
  });

  it("handles empty stats with fallback message", () => {
    const svg = renderSvg(null, {
      cardType: "bar",
      emptyMessage: "User not scanned yet. Visit dashboard to sync",
    });
    expect(svg).toContain("User not scanned yet. Visit dashboard to sync");
  });

  it("throws on unsupported cardType", () => {
    expect(() => renderSvg(SAMPLE_STATS, { cardType: "invalid" })).toThrow();
  });
});

// ---------------------------------------------------------------------------
// M2.2 — Bar card >= 1% threshold (TypeScript engine)
// ---------------------------------------------------------------------------

describe("renderSvg bar card >= 1% threshold (M2.2)", () => {
  it("shows all languages >= 1% when langsCount is omitted", () => {
    // SAMPLE_STATS: Python 50%, TS 30%, JS 15%, CSS 5% — all >= 1%
    const svg = renderSvg(SAMPLE_STATS, { cardType: "bar" });
    expect(svg).toContain("Python");
    expect(svg).toContain("TypeScript");
    expect(svg).toContain("JavaScript");
    expect(svg).toContain("CSS");
  });

  it("filters out languages below 1% by default for bar card", () => {
    const svg = renderSvg(STATS_WITH_TINY, { cardType: "bar" });
    expect(svg).toContain("Python");
    expect(svg).toContain("TypeScript");
    expect(svg).not.toContain("Tiny"); // 0.5% — below threshold
  });

  it("shows more than 8 languages when all are >= 1%", () => {
    const svg = renderSvg(STATS_10_LANGS, { cardType: "bar" });
    for (let i = 0; i < 10; i++) {
      expect(svg).toContain(`Lang${i}`);
    }
  });

  it("explicit langsCount overrides threshold and caps bar card", () => {
    // langs_count=3: top-3 shown even if 3rd is < 1%
    const svg = renderSvg(STATS_WITH_TINY, { cardType: "bar", langsCount: 3 });
    expect(svg).toContain("Python");
    expect(svg).toContain("TypeScript");
    expect(svg).toContain("Tiny"); // within top-3, threshold bypassed
  });

  it("non-bar cards (donut, compact, breakdown) are unaffected by threshold", () => {
    // STATS_WITH_TINY: Tiny is 0.5% but should appear in donut/compact/breakdown
    for (const cardType of ["donut", "compact", "breakdown"] as const) {
      const svg = renderSvg(STATS_WITH_TINY, { cardType });
      expect(svg).toContain("Tiny");
    }
  });
});
