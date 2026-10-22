import path from "node:path";
import { fileURLToPath } from "node:url";

export const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const systemsRoot = path.resolve(appRoot, "..");
export const repoRoot = path.resolve(systemsRoot, "..");
export const viteOutput = path.join(systemsRoot, ".build", "ui");
export const viteManifest = path.join(viteOutput, ".vite", "manifest.json");
export const publishedAssetRoot = path.join(repoRoot, "auxsays", "systems-monitor", "assets");
export const publishedMediaRoot = path.join(repoRoot, "auxsays", "systems-monitor", "media");
export const reviewedMediaRoot = path.join(appRoot, "fixtures", "media");
export const generatedInclude = path.join(repoRoot, "auxsays", "_includes", "generated", "systems-monitor-assets.html");
export const builtSiteRoot = path.join(repoRoot, "auxsays", "_site");
export const builtPage = path.join(builtSiteRoot, "systems-monitor", "index.html");

export function assertExactPath(candidate, expected, label) {
  if (path.resolve(candidate) !== path.resolve(expected)) {
    throw new Error(`${label} resolved outside its approved path: ${candidate}`);
  }
}
