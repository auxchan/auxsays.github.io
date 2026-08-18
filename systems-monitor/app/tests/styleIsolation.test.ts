import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("style isolation", () => {
  it("scopes every selector block to the product root except owned keyframes and media rules", () => {
    const css = readFileSync(path.resolve("src/styles.css"), "utf8");
    const selectorBlocks = css.match(/(?:^|\})\s*([^@][^{]+)\{/gm) ?? [];
    const unsafe = selectorBlocks
      .map((block) => block.replace(/^\}\s*/, "").replace(/\{$/, "").trim())
      .filter((selector) => selector && !selector.includes('[data-aux-product="systems-monitor"]') && selector !== "to" && !selector.includes("@keyframes") && !selector.includes("@media"));
    expect(unsafe).toEqual([]);
  });

  it("contains explicit reduced-motion and three responsive compositions", () => {
    const css = readFileSync(path.resolve("src/styles.css"), "utf8");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(css).toContain("@media (max-width: 1080px)");
    expect(css).toContain("@media (max-width: 780px)");
    expect(css).toContain("@media (max-width: 520px)");
    expect(css).toMatch(/min-height:\s*44px/);
  });

  it("does not import Patch Feed or global AUXSAYS internals", () => {
    const sources = readFileSync(path.resolve("src/main.tsx"), "utf8") + readFileSync(path.resolve("src/app/SystemsMonitorApp.tsx"), "utf8");
    expect(sources).not.toMatch(/patch.feed|updates\//i);
    expect(sources).not.toMatch(/auxsays\/assets|_data/i);
  });
});
