// Third-party licence notices for the published Systems Monitor bundle (AUX-082).
//
// WHY THIS EXISTS. The deployed bundle (/systems-monitor/assets/main-*.js) ships React, react-dom,
// react-is, Recharts and their dependencies, and the minifier strips every licence comment from it.
// Nothing served beside it carried the copyright and permission notices those licences require: the
// licence inventory (DEPENDENCY_LICENSE_INVENTORY.json) names each licence but reproduces none, and it
// is not published. This module writes one plain-text notices file for EXACTLY the production
// dependency set the inventory lists, and checks that the file the site serves is that file.
//
// WHERE THE TEXT COMES FROM. Every licence text is read from the files the INSTALLED package ships
// (LICENSE, LICENCE.md, COPYING, NOTICE, ... at any depth outside a nested node_modules) -- never from
// the registry, never typed in -- with one reviewed exception per package in SUPPLEMENTED_TEXTS.
//
// DETERMINISM. Packages are sorted by code point (never by locale), licence files by path, an identical
// text is printed once, line endings are LF, trailing spaces are dropped and the file ends with exactly
// one newline. The same lockfile and node_modules therefore always give the same bytes.
//
// Every failure is a named finding, `[CODE, detail]`. The codes are the contract the build and the
// governed suite (auxsays/scripts/tests/test_systems_monitor_third_party_notices.py) assert on.
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { productionPackages } from "./production-dependencies.mjs";

export const NOTICES_URL = "/systems-monitor/THIRD_PARTY_NOTICES.txt";

const RULE = "=".repeat(80);
const THIN = "-".repeat(80);
const LICENCE_FILE = /^(?:licen[cs]e|copying|notice)(?:[-_.][a-z0-9_.-]*)?$/i;
const NOT_A_LICENCE_FILE = /\.(?:[cm]?js|[cm]?ts|jsx|tsx|json|map|css|html?)$/i;
// A line that STATES a copyright. "The above copyright notice ..." and "COPYRIGHT HOLDERS BE LIABLE"
// talk about copyright and are not notices, so they are excluded by the word that follows.
const COPYRIGHT_LINE = /^(?:copyright\b|\(c\)\s|©)/i;
const NOT_A_COPYRIGHT_LINE = /^copyright\s+(?:holders?|notices?|owners?|laws?)\b/i;

// The MIT License as published by the Open Source Initiative, without a copyright line: it is only
// ever printed for a package that states none (see SUPPLEMENTED_TEXTS).
const MIT_LICENSE_TEXT = `MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`;

// A package that declares a licence for its own code but ships no file carrying that text. Each entry
// is a reviewed decision keyed by package name. It is refused (NOTICE_SUPPLEMENT_STALE) the moment the
// package ships a licence file at its root, so it cannot outlive the gap it fills.
export const SUPPLEMENTED_TEXTS = new Map([
  ["victory-vendor", {
    file: "MIT License (standard text; the package ships none)",
    note: "victory-vendor declares MIT AND ISC. It ships the ISC licence of each d3 module it vendors (lib-vendor/*/LICENSE) but no licence file for its own MIT-licensed code, and states no copyright line for that code (package author: Formidable). The standard MIT License text is reproduced for it.",
    text: MIT_LICENSE_TEXT
  }]
]);

const byCodePoint = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
const keyOf = (item) => `${item.name}@${item.version}`;

export function normaliseText(raw) {
  return raw
    .replace(/^﻿/, "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/, ""))
    .join("\n")
    .replace(/^\n+/, "")
    .replace(/\n+$/, "");
}

export function copyrightLines(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => COPYRIGHT_LINE.test(line) && !NOT_A_COPYRIGHT_LINE.test(line));
}

async function licenceFilesIn(packageDir, relative = "") {
  const found = [];
  const entries = await readdir(path.join(packageDir, relative), { withFileTypes: true });
  for (const entry of entries) {
    const rel = relative ? `${relative}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      if (entry.name !== "node_modules") found.push(...await licenceFilesIn(packageDir, rel));
    } else if (entry.isFile() && LICENCE_FILE.test(entry.name) && !NOT_A_LICENCE_FILE.test(entry.name)) {
      found.push(rel);
    }
  }
  return found.sort(byCodePoint);
}

function wrap(text, indent, width = 100) {
  const lines = [];
  let line = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    if (line && indent.length + line.length + 1 + word.length > width) {
      lines.push(indent + line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(indent + line);
  return lines;
}

// The production set from the lockfile, sorted. Shared with the licence inventory.
export function lockedProduction(lock) {
  return [...productionPackages(lock).values()].sort((a, b) => byCodePoint(keyOf(a), keyOf(b)));
}

// Read every production package's licence files from node_modules. `appDir` is the directory the
// lockfile's install paths are relative to. Returns the packages (sorted, each with its licence files and
// copyright lines), the distinct texts in first-use order, and findings.
export async function collectInstalled(lock, appDir) {
  const findings = [];
  const packages = [];
  const textIds = new Map();
  const texts = [];
  const textFor = (text, user) => {
    let entry = textIds.get(text);
    if (!entry) {
      entry = { id: `T${texts.length + 1}`, text, users: [] };
      textIds.set(text, entry);
      texts.push(entry);
    }
    if (!entry.users.includes(user)) entry.users.push(user);
    return entry.id;
  };
  for (const locked of lockedProduction(lock)) {
    const label = `${locked.name} ${locked.version}`;
    const installPath = locked.paths[0];
    const packageDir = path.join(appDir, ...installPath.split("/"));
    let installed;
    try {
      installed = JSON.parse(await readFile(path.join(packageDir, "package.json"), "utf8"));
    } catch {
      findings.push(["NOTICE_NOT_INSTALLED", `${keyOf(locked)} is not installed at ${installPath}; run npm ci`]);
      continue;
    }
    if (installed.name !== locked.name || installed.version !== locked.version) {
      findings.push(["NOTICE_INSTALLED_VERSION_MISMATCH", `${installPath} holds ${installed.name}@${installed.version}, the lockfile pins ${keyOf(locked)}; run npm ci`]);
      continue;
    }
    const files = [];
    const copyright = [];
    for (const rel of await licenceFilesIn(packageDir)) {
      const text = normaliseText(await readFile(path.join(packageDir, ...rel.split("/")), "utf8"));
      if (!text) continue;
      files.push({ path: rel, id: textFor(text, label) });
      for (const line of copyrightLines(text)) if (!copyright.includes(line)) copyright.push(line);
    }
    const supplement = SUPPLEMENTED_TEXTS.get(locked.name);
    let note = null;
    if (supplement) {
      if (files.some((file) => !file.path.includes("/"))) {
        findings.push(["NOTICE_SUPPLEMENT_STALE", `${keyOf(locked)} now ships a root licence file; remove its SUPPLEMENTED_TEXTS entry and regenerate`]);
      }
      files.push({ path: supplement.file, id: textFor(supplement.text, label) });
      note = supplement.note;
    }
    if (!files.length) {
      findings.push(["NOTICE_LICENSE_TEXT_MISSING", `${keyOf(locked)} (${locked.license}) ships no licence file; its notice cannot be reproduced`]);
      continue;
    }
    packages.push({ name: locked.name, version: locked.version, license: locked.license, copyright, files, note });
  }
  return { packages, texts, findings };
}

export function renderNotices(packages, texts) {
  const lines = [
    "THIRD-PARTY SOFTWARE NOTICES",
    "AUXSAYS U.S. Systems Monitor (/systems-monitor/)",
    "",
    ...wrap("The U.S. Systems Monitor is built with the open-source packages listed below, each under its own licence. For every production dependency this file gives the package name, version, licence identifier and copyright line(s), and it reproduces in full the licence files the package ships. A licence text that several packages share word for word is printed once and referred to by number.", "", 80),
    "",
    ...wrap("This file is generated from the application's locked production dependency set and is not edited by hand.", "", 80),
    "",
    `Production dependencies: ${packages.length}`,
    `Distinct licence texts: ${texts.length}`,
    "",
    RULE,
    "PACKAGES",
    RULE,
    ""
  ];
  for (const item of packages) {
    lines.push(`${item.name} ${item.version}`);
    lines.push(`  Licence: ${item.license}`);
    const copyright = item.copyright.length ? item.copyright : ["(none stated in the package's licence files)"];
    copyright.forEach((line, index) => lines.push(`${index ? " ".repeat(13) : "  Copyright: "}${line}`));
    item.files.forEach((file, index) => lines.push(`${index ? " ".repeat(16) : "  Licence text: "}[${file.id}] ${file.path}`));
    if (item.note) lines.push(...wrap(`Note: ${item.note}`, "  "));
    lines.push("");
  }
  lines.push(RULE, "LICENCE TEXTS", RULE, "");
  for (const entry of texts) {
    lines.push(THIN, `[${entry.id}] used by:`, ...entry.users.map((user) => `  ${user}`), THIN, "", entry.text, "");
  }
  return `${lines.join("\n").replace(/\n+$/, "")}\n`;
}

export async function generateNotices(lock, appDir) {
  const { packages, texts, findings } = await collectInstalled(lock, appDir);
  return { text: renderNotices(packages, texts), findings, packageCount: packages.length, textCount: texts.length };
}

// Read a notices file back into its package entries and text blocks. Throws on a file whose shape is
// not the one renderNotices writes.
export function parseNotices(content) {
  const lines = content.split("\n");
  const packagesAt = lines.findIndex((line, index) => line === "PACKAGES" && lines[index - 1] === RULE && lines[index + 1] === RULE);
  const textsAt = lines.findIndex((line, index) => line === "LICENCE TEXTS" && lines[index - 1] === RULE && lines[index + 1] === RULE);
  if (packagesAt < 0 || textsAt < packagesAt) throw new Error("no PACKAGES section followed by a LICENCE TEXTS section");
  const declared = (label) => {
    const line = lines.slice(0, packagesAt).find((candidate) => candidate.startsWith(`${label}: `));
    return line ? Number(line.slice(label.length + 2)) : NaN;
  };
  const packages = [];
  let current = null;
  let field = null;
  for (const line of lines.slice(packagesAt + 2, textsAt - 1)) {
    if (!line) { current = null; field = null; continue; }
    if (!line.startsWith(" ")) {
      const space = line.lastIndexOf(" ");
      if (space <= 0) throw new Error(`malformed package line: ${line}`);
      current = { name: line.slice(0, space), version: line.slice(space + 1), license: null, refs: [] };
      packages.push(current);
      field = null;
      continue;
    }
    if (!current) throw new Error(`indented line outside a package: ${line}`);
    if (line.startsWith("  Licence: ")) { current.license = line.slice(11); field = null; continue; }
    if (line.startsWith("  Copyright: ")) { field = "copyright"; continue; }
    if (line.startsWith("  Licence text: ")) field = "text";
    else if (line.startsWith("  Note: ")) { field = "note"; continue; }
    if (field === "text") {
      const ref = /^\s+(?:Licence text: )?\[(T\d+)\] /.exec(line);
      if (!ref) throw new Error(`malformed licence text reference: ${line}`);
      current.refs.push(ref[1]);
    }
  }
  const texts = new Map();
  let block = null;
  for (let index = textsAt + 2; index < lines.length; index += 1) {
    const header = lines[index - 1] === THIN ? /^\[(T\d+)\] used by:$/.exec(lines[index]) : null;
    if (header) {
      if (block) block.body.pop();
      block = { id: header[1], body: [], inUsers: true };
      texts.set(block.id, block);
      continue;
    }
    if (!block) continue;
    if (block.inUsers) { if (lines[index] === THIN) block.inUsers = false; continue; }
    block.body.push(lines[index]);
  }
  return {
    declaredPackages: declared("Production dependencies"),
    declaredTexts: declared("Distinct licence texts"),
    packages,
    texts: new Map([...texts].map(([id, entry]) => [id, entry.body.join("\n").replace(/^\n+|\n+$/g, "")]))
  };
}

// The committed file against the lockfile and the inventory, with no node_modules: what a pull request
// can be judged on. A dependency added or bumped without regenerating the notices fails here by name.
export function coverageFindings(lock, noticePackages) {
  const findings = [];
  const locked = new Map(lockedProduction(lock).map((item) => [keyOf(item), item]));
  const lockedVersions = new Map();
  for (const item of locked.values()) lockedVersions.set(item.name, [...(lockedVersions.get(item.name) ?? []), item.version]);
  const noticed = new Map();
  for (const item of noticePackages) {
    if (noticed.has(keyOf(item))) findings.push(["NOTICE_DUPLICATE_ENTRY", `${keyOf(item)} has more than one notice entry`]);
    noticed.set(keyOf(item), item);
  }
  const staleNames = new Set();
  for (const [key, item] of locked) {
    const notice = noticed.get(key);
    if (notice) {
      if (notice.license !== item.license) findings.push(["NOTICE_LICENCE_MISMATCH", `${key}: the notice says ${notice.license}, the lockfile says ${item.license}`]);
      continue;
    }
    const otherVersions = noticePackages.filter((candidate) => candidate.name === item.name && !locked.has(keyOf(candidate))).map((candidate) => candidate.version);
    if (otherVersions.length) {
      staleNames.add(item.name);
      findings.push(["NOTICE_VERSION_STALE", `${item.name}: the notice covers ${otherVersions.join(", ")}, the lockfile installs ${item.version}`]);
    } else {
      findings.push(["NOTICE_PACKAGE_MISSING", `${key} (${item.license}) is a production dependency with no notice`]);
    }
  }
  for (const [key, item] of noticed) {
    if (locked.has(key) || staleNames.has(item.name)) continue;
    findings.push(["NOTICE_PACKAGE_EXTRA", `${key} has a notice but is not a production dependency`]);
  }
  const order = noticePackages.map(keyOf);
  if (order.some((key, index) => index > 0 && byCodePoint(order[index - 1], key) >= 0)) {
    findings.push(["NOTICE_ORDER", "package entries are not in code-point order of name@version"]);
  }
  return findings;
}

export function inventoryFindings(lock, inventory) {
  const locked = lockedProduction(lock).map(keyOf);
  const listed = [...new Set((inventory.packages ?? []).map(keyOf))].sort(byCodePoint);
  const missing = locked.filter((key) => !listed.includes(key));
  const extra = listed.filter((key) => !locked.includes(key));
  if (!missing.length && !extra.length && inventory.packageCount === locked.length) return [];
  return [["NOTICE_INVENTORY_MISMATCH", `DEPENDENCY_LICENSE_INVENTORY.json is stale against the lockfile (missing: ${missing.join(", ") || "none"}; extra: ${extra.join(", ") || "none"}; packageCount ${inventory.packageCount} vs ${locked.length}); run npm run licenses`]];
}

export function structureFindings(parsed) {
  const findings = [];
  if (parsed.declaredPackages !== parsed.packages.length) findings.push(["NOTICE_COUNT_MISMATCH", `the header declares ${parsed.declaredPackages} production dependencies, the file lists ${parsed.packages.length}`]);
  if (parsed.declaredTexts !== parsed.texts.size) findings.push(["NOTICE_COUNT_MISMATCH", `the header declares ${parsed.declaredTexts} licence texts, the file holds ${parsed.texts.size}`]);
  for (const item of parsed.packages) {
    if (!item.license) findings.push(["NOTICE_MALFORMED", `${keyOf(item)} has no Licence line`]);
    if (!item.refs.length) findings.push(["NOTICE_PACKAGE_WITHOUT_TEXT", `${keyOf(item)} refers to no licence text`]);
    for (const ref of item.refs) if (!parsed.texts.has(ref)) findings.push(["NOTICE_TEXT_UNDEFINED", `${keyOf(item)} refers to [${ref}], which the file does not contain`]);
  }
  for (const [id, text] of parsed.texts) if (!text) findings.push(["NOTICE_TEXT_EMPTY", `[${id}] is empty`]);
  return findings;
}

async function readOptional(file) {
  try {
    return await readFile(file, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

function parseOrFinding(content, findings, label) {
  try {
    return parseNotices(content);
  } catch (error) {
    findings.push(["NOTICE_MALFORMED", `${label}: ${error.message}`]);
    return null;
  }
}

export async function checkCommitted({ lockfile, inventoryFile, noticesFile }) {
  const lock = JSON.parse(await readFile(lockfile, "utf8"));
  const findings = inventoryFindings(lock, JSON.parse(await readFile(inventoryFile, "utf8")));
  const content = await readOptional(noticesFile);
  if (content === null) return [...findings, ["NOTICE_FILE_MISSING", `${path.basename(noticesFile)} is not committed beside the lockfile; run npm run notices`]];
  const parsed = parseOrFinding(content, findings, path.basename(noticesFile));
  if (parsed) findings.push(...structureFindings(parsed), ...coverageFindings(lock, parsed.packages));
  return findings;
}

// The deploy-time proof, after npm ci: regenerating from the installed packages gives the committed bytes.
export async function checkRegenerated({ lockfile, noticesFile }) {
  const lock = JSON.parse(await readFile(lockfile, "utf8"));
  const generated = await generateNotices(lock, path.dirname(lockfile));
  const findings = [...generated.findings];
  const committed = await readOptional(noticesFile);
  if (committed === null) return [...findings, ["NOTICE_FILE_MISSING", `${path.basename(noticesFile)} is not committed beside the lockfile; run npm run notices`]];
  if (committed === generated.text) return findings;
  const parsed = parseOrFinding(committed, findings, path.basename(noticesFile));
  if (parsed) findings.push(...coverageFindings(lock, parsed.packages));
  const a = committed.split("\n");
  const b = generated.text.split("\n");
  let line = 0;
  while (line < a.length && line < b.length && a[line] === b[line]) line += 1;
  findings.push(["NOTICE_NOT_REPRODUCIBLE", `${path.basename(noticesFile)} differs from a regeneration from the installed packages, first at line ${line + 1}; run npm run notices`]);
  return findings;
}

async function filesUnder(directory) {
  const output = [];
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return output;
    throw error;
  }
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) output.push(...await filesUnder(entryPath));
    else if (entry.isFile()) output.push(entryPath);
  }
  return output.sort(byCodePoint);
}

// The built site serves the committed notices at NOTICES_URL, beside the bundle, and the bundle links to it.
export async function checkBuiltSite({ siteRoot, lockfile, inventoryFile, noticesFile }) {
  const findings = await checkCommitted({ lockfile, inventoryFile, noticesFile });
  const served = await readOptional(path.join(siteRoot, ...NOTICES_URL.split("/").filter(Boolean)));
  const committed = await readOptional(noticesFile);
  if (served === null) findings.push(["NOTICE_BUILT_FILE_MISSING", `the built site does not serve ${NOTICES_URL}`]);
  else if (committed !== null && served !== committed) findings.push(["NOTICE_BUILT_FILE_DIFFERS", `the built ${NOTICES_URL} is not byte-identical to the committed ${path.basename(noticesFile)}`]);
  const scripts = (await filesUnder(path.join(siteRoot, "systems-monitor", "assets"))).filter((file) => file.endsWith(".js"));
  if (!scripts.length) {
    findings.push(["NOTICE_NOT_BESIDE_BUNDLE", "the built site has no Systems Monitor bundle under /systems-monitor/assets/"]);
  } else {
    let linked = false;
    for (const file of scripts) if ((await readFile(file, "utf8")).includes(NOTICES_URL)) linked = true;
    if (!linked) findings.push(["NOTICE_LINK_MISSING", `no built Systems Monitor script links to ${NOTICES_URL}`]);
  }
  return findings;
}

export function formatFindings(findings) {
  return findings.map(([code, detail]) => `${code}: ${detail}`).join("\n");
}
