import { access, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { builtPage, builtSiteRoot } from "./paths.mjs";

const html = await readFile(builtPage, "utf8");
if (!html.includes('id="systems-monitor-root"')) throw new Error("Built page is missing the Systems Monitor root");
if (!html.includes("SYNTHETIC TEST DATA")) throw new Error("Built page is missing the fixture disclosure");
const matches = [...html.matchAll(/(?:src|href)="([^"]*\/systems-monitor\/assets\/[^"]+)"/g)].map((match) => match[1]);
if (matches.length < 2) throw new Error("Built page does not reference both JS and CSS assets");
for (const url of matches) {
  const relative = url.replace(/^.*?\/systems-monitor\//, "systems-monitor/");
  const file = path.join(builtSiteRoot, ...relative.split("/"));
  await access(file);
  if ((await stat(file)).size === 0) throw new Error(`Built asset is empty: ${file}`);
}
if (/src\/main\.tsx|node_modules/.test(html)) throw new Error("Built page leaked a source or node_modules reference");
console.log(`static site valid: ${builtPage} with ${matches.length} hashed asset references`);
