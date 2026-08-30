import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { generatedInclude, publishedAssetRoot, publishedMediaRoot, reviewedMediaRoot, viteManifest, viteOutput } from "./paths.mjs";

const manifest = JSON.parse(await readFile(viteManifest, "utf8"));
const entry = manifest["src/main.tsx"];
if (!entry?.file) throw new Error("Missing Vite entry while composing Jekyll include");
await mkdir(publishedAssetRoot, { recursive: true });
await cp(path.join(viteOutput, "assets"), publishedAssetRoot, { recursive: true });
await mkdir(publishedMediaRoot, { recursive: true });
await cp(reviewedMediaRoot, publishedMediaRoot, { recursive: true });
const assetFiles = [entry.file, ...(entry.css ?? [])];
const hash = createHash("sha256").update(JSON.stringify(manifest)).digest("hex").slice(0, 16);
const tags = assetFiles.map((file) => {
  const asset = file.replace(/^assets\//, "");
  return file.endsWith(".css")
    ? `<link rel="stylesheet" href="{{ '/systems-monitor/assets/${asset}' | relative_url }}">`
    : `<script type="module" src="{{ '/systems-monitor/assets/${asset}' | relative_url }}"></script>`;
});
await mkdir(path.dirname(generatedInclude), { recursive: true });
await writeFile(generatedInclude, `<!-- generated systems-monitor build ${hash}; do not edit -->\n${tags.join("\n")}\n`, "utf8");
console.log(`composed Jekyll assets: ${assetFiles.length} entry assets, build ${hash}`);
