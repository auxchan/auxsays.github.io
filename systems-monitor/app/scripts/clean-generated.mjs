import { rm } from "node:fs/promises";
import { assertExactPath, generatedInclude, publishedAssetRoot, viteOutput } from "./paths.mjs";

for (const [target, label] of [[viteOutput, "Vite output"], [publishedAssetRoot, "published assets"], [generatedInclude, "generated include"]]) {
  assertExactPath(target, target, label);
  await rm(target, { recursive: true, force: true });
  console.log(`cleaned ${label}: ${target}`);
}
