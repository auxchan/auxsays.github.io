import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { appRoot } from "./paths.mjs";

const lock = JSON.parse(await readFile(path.join(appRoot, "package-lock.json"), "utf8"));
const inventory = new Map();
for (const [packagePath, metadata] of Object.entries(lock.packages ?? {})) {
  if (!packagePath || metadata.dev === true || !metadata.version) continue;
  const name = metadata.name ?? packagePath.split("node_modules/").at(-1);
  inventory.set(`${name}@${metadata.version}`, {
    name,
    version: metadata.version,
    license: metadata.license ?? "UNKNOWN",
    resolved: metadata.resolved ?? null
  });
}
const packages = [...inventory.values()].sort((a, b) => `${a.name}@${a.version}`.localeCompare(`${b.name}@${b.version}`));
const allowedLicenses = new Set(["MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD"]);
const licenseIsAllowed = (expression) => expression.replaceAll(/[()]/g, "").split(/\s+(?:AND|OR)\s+/).every((license) => allowedLicenses.has(license));
const disallowed = packages.filter((item) => !licenseIsAllowed(item.license));
const output = { generatedBy: "package-lock.json production package inventory", packageCount: packages.length, allLicensesAllowlisted: disallowed.length === 0, packages };
await writeFile(path.join(appRoot, "DEPENDENCY_LICENSE_INVENTORY.json"), `${JSON.stringify(output, null, 2)}\n`, "utf8");
if (disallowed.length) throw new Error(`Unreviewed production licenses: ${disallowed.map((item) => `${item.name}@${item.version} (${item.license})`).join(", ")}`);
console.log(`production license inventory valid: ${packages.length} packages`);
