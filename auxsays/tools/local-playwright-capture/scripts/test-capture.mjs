import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
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
