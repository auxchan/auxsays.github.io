import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

import {
  CAPTURE_METHOD,
  appendJsonl,
  classifyBlockedPage,
  loadCandidateConfig,
  makeCaptureRow,
  resolveRuntimePaths,
  selectCandidatesForRun,
  serializeJsonl,
  validateCandidates,
  validateCaptureRow,
} from "../capture-agent.mjs";

const thisFile = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(thisFile), "..", "..", "..", "..");
const execFileAsync = promisify(execFile);
const protectedPaths = [
  "auxsays/_data/consensus_evidence.yml",
  "auxsays/_data/evidence_method_health.yml",
  "auxsays/_data/source_health.yml",
  "auxsays/_data/qa_status.json",
  "auxsays/_data/consensus_status.json",
  "auxsays/_data/patch_ingest_state.json",
];

const sampleCandidates = [
  {
    source_url: "https://community.adobe.com/t5/premiere-pro-discussions/example/td-p/12345",
    source_name: "Adobe Community",
    product_hint: "adobe-premiere-pro",
    version_hint: "26.2",
  },
  {
    source_url: "https://creativecow.net/forums/thread/premiere-pro-262-test/",
    source_name: "Creative COW",
    product_hint: "adobe-premiere-pro",
    version_hint: "26.2",
  },
];

async function snapshotProtectedFiles() {
  const snapshot = new Map();
  for (const relativePath of protectedPaths) {
    const fullPath = path.join(repoRoot, relativePath);
    try {
      const stat = await fs.stat(fullPath);
      snapshot.set(relativePath, `${stat.mtimeMs}:${stat.size}`);
    } catch (error) {
      if (error.code !== "ENOENT") {
        throw error;
      }
      snapshot.set(relativePath, "missing");
    }
  }
  return snapshot;
}

async function snapshotGeneratedRecords() {
  const generatedRoot = path.join(repoRoot, "auxsays", "updates", "generated");
  const entries = await fs.readdir(generatedRoot, { withFileTypes: true });
  const snapshot = new Map();
  for (const entry of entries) {
    if (!entry.isFile()) {
      continue;
    }
    const fullPath = path.join(generatedRoot, entry.name);
    const stat = await fs.stat(fullPath);
    snapshot.set(entry.name, `${stat.mtimeMs}:${stat.size}`);
  }
  return snapshot;
}

test("parses candidate config arrays and objects", async () => {
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "auxsays-capture-test-"));
  const configPath = path.join(tempDir, "candidates.json");
  await fs.writeFile(configPath, JSON.stringify({ max_urls_per_run: 1, candidates: sampleCandidates }), "utf8");

  const config = await loadCandidateConfig(configPath);
  assert.equal(config.candidates.length, 2);
  assert.equal(config.maxUrlsPerRun, 1);

  const arrayConfigPath = path.join(tempDir, "array-candidates.json");
  await fs.writeFile(arrayConfigPath, JSON.stringify(sampleCandidates), "utf8");
  const arrayConfig = await loadCandidateConfig(arrayConfigPath);
  assert.equal(arrayConfig.candidates.length, 2);
});

test("loads and limits URL list", () => {
  const candidates = validateCandidates(sampleCandidates);
  const selected = selectCandidatesForRun(candidates, 1);
  assert.equal(selected.length, 1);
  assert.equal(selected[0].source_name, "Adobe Community");
  assert.equal(selected[0].source_url, "https://community.adobe.com/t5/premiere-pro-discussions/example/td-p/12345");
});

test("serializes JSONL output shape", () => {
  const row = makeCaptureRow(sampleCandidates[0], {
    final_url: "https://community.adobe.com/t5/premiere-pro-discussions/example/td-p/12345",
    page_title: "Premiere Pro 26.2 issue",
    visible_text: "Premiere Pro 26.2 crashes during export.",
    captured_at: "2026-05-20T20:00:00.000Z",
    capture_status: "success",
  });

  const line = serializeJsonl(row);
  assert.equal(line.includes("\n"), false);
  const parsed = JSON.parse(line);
  assert.equal(parsed.capture_method, CAPTURE_METHOD);
  assert.equal(parsed.capture_status, "success");
  assert.equal(parsed.verdict, undefined);
  assert.equal(parsed.evidence_state, undefined);
});

test("classifies blocked and challenge page fixture HTML", () => {
  assert.equal(
    classifyBlockedPage({
      html: "<html><title>Just a moment...</title><body>Checking your browser before accessing</body></html>",
      title: "Just a moment...",
      text: "Checking your browser before accessing",
      status: 200,
    }),
    "browser_challenge",
  );
  assert.equal(
    classifyBlockedPage({
      html: "<script>window.gokuProps = {}</script>",
      title: "Adobe Community",
      text: "",
      status: 200,
    }),
    "aws_waf_challenge",
  );
  assert.equal(classifyBlockedPage({ html: "<main>Normal public forum post</main>", status: 200 }), "");
});

test("requires output fields and error reasons", () => {
  const row = makeCaptureRow(sampleCandidates[1], {
    capture_status: "blocked",
    error_reason: "captcha_challenge",
  });
  assert.equal(validateCaptureRow(row), true);
  assert.throws(
    () => validateCaptureRow({ ...row, capture_status: "blocked", error_reason: "" }),
    /require error_reason/,
  );
  assert.throws(
    () => validateCaptureRow({ ...row, confidence: "high" }),
    /forbidden decision field/,
  );
});

test("writes only capture outbox paths, not consensus/generated/state files", async () => {
  const before = await snapshotProtectedFiles();
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "auxsays-capture-outbox-"));
  const paths = resolveRuntimePaths({
    appRoot: tempDir,
  });
  const row = makeCaptureRow(sampleCandidates[0], {
    page_title: "Fixture",
    visible_text: "Fixture visible text",
    capture_status: "success",
  });

  await appendJsonl(paths.outboxPath, row);
  const output = await fs.readFile(paths.outboxPath, "utf8");
  assert.equal(output.trim().split(/\r?\n/).length, 1);

  const after = await snapshotProtectedFiles();
  assert.deepEqual(after, before);
});

test("portable build creates capture-and-promote command files safely", async () => {
  const beforeProtected = await snapshotProtectedFiles();
  const beforeGenerated = await snapshotGeneratedRecords();
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "auxsays-capture-build-"));
  const buildScript = path.join(repoRoot, "auxsays", "tools", "local-playwright-capture", "scripts", "build-portable.ps1");

  await execFileAsync(
    "powershell.exe",
    [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      buildScript,
      "-OutputRoot",
      tempDir,
      "-SkipInstall",
    ],
    { cwd: repoRoot, windowsHide: true, timeout: 60_000 },
  );

  const commandNames = [
    "Run Capture.cmd",
    "Run Capture Once.cmd",
    "Run Capture Then Promote Dry Run.cmd",
    "Run Capture Then Promote WRITE.cmd",
  ];
  for (const commandName of commandNames) {
    const commandPath = path.join(tempDir, commandName);
    const stat = await fs.stat(commandPath);
    assert.equal(stat.isFile(), true);
  }

  const dryRunCommand = await fs.readFile(path.join(tempDir, "Run Capture Then Promote Dry Run.cmd"), "ascii");
  const writeCommand = await fs.readFile(path.join(tempDir, "Run Capture Then Promote WRITE.cmd"), "ascii");

  assert.match(dryRunCommand, /C:\\GITHUB PROJECTS\\auxsays\.github\.io/);
  assert.match(dryRunCommand, /run-capture-and-promote\.ps1/);
  assert.match(dryRunCommand, /set "PORTABLE_PATH=%~dp0\."/);
  assert.match(dryRunCommand, /-PortablePath "%PORTABLE_PATH%"/);
  assert.doesNotMatch(dryRunCommand, /-PortablePath "%~dp0"/);
  assert.doesNotMatch(dryRunCommand, /(?:^|\s)-(?:-)?write(?:\s|$)/i);
  assert.match(writeCommand, /set \/p AUXSAYS_CONFIRM=Confirmation:/i);
  assert.match(writeCommand, /if not "%AUXSAYS_CONFIRM%"=="WRITE"/i);
  assert.match(writeCommand, /set "PORTABLE_PATH=%~dp0\."/);
  assert.match(writeCommand, /-PortablePath "%PORTABLE_PATH%"/);
  assert.match(writeCommand, /-Write\b/);
  assert.match(writeCommand, /-ConfirmedWrite\b/);

  const afterProtected = await snapshotProtectedFiles();
  const afterGenerated = await snapshotGeneratedRecords();
  assert.deepEqual(afterProtected, beforeProtected);
  assert.deepEqual(afterGenerated, beforeGenerated);
});
