import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("build and release boundary", () => {
  it("uses the durable base and exact owned generated paths", () => {
    const vite = readFileSync(path.resolve("vite.config.mjs"), "utf8");
    const paths = readFileSync(path.resolve("scripts/paths.mjs"), "utf8");
    expect(vite).toContain('base: "/systems-monitor/"');
    expect(vite).toContain('outDir: "../.build/ui"');
    expect(paths).toContain('"auxsays", "systems-monitor", "assets"');
    expect(paths).toContain('"generated", "systems-monitor-assets.html"');
  });

  it("cleans only explicit Systems Monitor outputs and validates manifest equality", () => {
    const cleaner = readFileSync(path.resolve("scripts/clean-generated.mjs"), "utf8");
    const validator = readFileSync(path.resolve("scripts/validate-manifest.mjs"), "utf8");
    expect(cleaner).toContain("viteOutput");
    expect(cleaner).toContain("publishedAssetRoot");
    expect(cleaner).toContain("generatedInclude");
    expect(cleaner).not.toMatch(/repoRoot.*rm|builtSiteRoot.*rm/);
    expect(validator).toContain("Manifest/output mismatch");
  });
});
