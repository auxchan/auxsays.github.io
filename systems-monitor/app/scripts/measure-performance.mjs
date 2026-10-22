import { brotliCompressSync, gzipSync } from "node:zlib";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { viteOutput } from "./paths.mjs";

async function walk(directory) {
  const output = [];
  for (const item of await readdir(directory, { withFileTypes: true })) {
    const itemPath = path.join(directory, item.name);
    if (item.isDirectory()) output.push(...await walk(itemPath));
    else output.push(itemPath);
  }
  return output;
}

const assets = (await walk(path.join(viteOutput, "assets"))).filter((file) => /\.(?:js|css)$/.test(file));
let raw = 0;
let gzip = 0;
let brotli = 0;
for (const file of assets) {
  const bytes = await readFile(file);
  raw += bytes.length;
  gzip += gzipSync(bytes).length;
  brotli += brotliCompressSync(bytes).length;
}
const budget = 360 * 1024;
console.log(JSON.stringify({ assetCount: assets.length, rawBytes: raw, gzipBytes: gzip, brotliBytes: brotli, gzipBudgetBytes: budget }, null, 2));
if (gzip > budget) throw new Error(`Initial UI bundle exceeds ${budget} gzip bytes`);
