// THIRD_PARTY_NOTICES.txt: write it, or check it. See third-party-notices.mjs for why it exists.
//
//   --write               regenerate it from package-lock.json and node_modules (`npm run notices`)
//   --check               regenerate in memory after `npm ci` and require the committed bytes (the build)
//   --check-committed     without node_modules: it names exactly the locked production set, at the locked
//                         versions and licences, and agrees with DEPENDENCY_LICENSE_INVENTORY.json
//   --check-built [SITE]  the built site serves it at /systems-monitor/THIRD_PARTY_NOTICES.txt, byte-identical,
//                         beside the bundle, and the bundle links to it (default SITE: auxsays/_site)
//
// Exit 0 clean, 1 on any named finding (printed as CODE: detail), 2 on a usage error.
import { readFile, writeFile } from "node:fs/promises";
import { appRoot, builtSiteRoot, committedNotices, licenseInventory, lockfile } from "./paths.mjs";
import { checkBuiltSite, checkCommitted, checkRegenerated, formatFindings, generateNotices } from "./third-party-notices.mjs";

const [mode, site] = process.argv.slice(2);
const files = { lockfile, inventoryFile: licenseInventory, noticesFile: committedNotices };

function finish(findings, success) {
  if (findings.length) {
    console.error(formatFindings(findings));
    console.error(`third-party notices: ${findings.length} finding(s)`);
    process.exit(1);
  }
  console.log(success);
}

if (mode === "--write") {
  const generated = await generateNotices(JSON.parse(await readFile(lockfile, "utf8")), appRoot);
  if (generated.findings.length) finish(generated.findings, "");
  await writeFile(committedNotices, generated.text, "utf8");
  console.log(`third-party notices written: ${generated.packageCount} packages, ${generated.textCount} distinct licence texts`);
} else if (mode === "--check") {
  finish(await checkRegenerated(files), "third-party notices reproducible: the committed file is byte-identical to a regeneration");
} else if (mode === "--check-committed") {
  finish(await checkCommitted(files), "third-party notices cover exactly the locked production dependencies");
} else if (mode === "--check-built") {
  finish(await checkBuiltSite({ ...files, siteRoot: site ?? builtSiteRoot }), "third-party notices served beside the bundle and linked from it");
} else {
  console.error("usage: generate-third-party-notices.mjs --write | --check | --check-committed | --check-built [SITE]");
  process.exit(2);
}
