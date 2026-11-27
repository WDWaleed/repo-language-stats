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
