import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { viteManifest, viteOutput } from "./paths.mjs";

const manifest = JSON.parse(await readFile(viteManifest, "utf8"));
const entry = manifest["src/main.tsx"];
if (!entry?.isEntry || !entry.file) throw new Error("Vite manifest has no src/main.tsx entry");
const files = new Set(Object.values(manifest).flatMap((record) => [record.file, ...(record.css ?? []), ...(record.assets ?? [])]).filter(Boolean));
if (!files.size) throw new Error("Vite manifest contains no publishable files");
for (const file of files) {
  if (!/^assets\/[A-Za-z0-9_.-]+-[A-Za-z0-9_-]+\.(?:js|css)$/.test(file)) throw new Error(`Asset is not content hashed: ${file}`);
  const filePath = path.join(viteOutput, file);
  const info = await stat(filePath);
  if (!info.isFile() || info.size === 0) throw new Error(`Manifest asset is missing or empty: ${file}`);
}
const emitted = new Set((await readdir(path.join(viteOutput, "assets"))).map((file) => `assets/${file}`));
const stale = [...emitted].filter((file) => !files.has(file));
const missing = [...files].filter((file) => !emitted.has(file));
if (stale.length || missing.length) throw new Error(`Manifest/output mismatch; stale=${stale.join(",") || "none"}; missing=${missing.join(",") || "none"}`);
console.log(`manifest valid: ${files.size} content-hashed assets; no missing or stale assets`);
