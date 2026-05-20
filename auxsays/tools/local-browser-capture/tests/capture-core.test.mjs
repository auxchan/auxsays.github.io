import assert from "node:assert/strict";
import test from "node:test";

import {
  assertDedicatedBrowserProfile,
  blockOrVerificationReason,
  buildBlackmagicForumSearchUrl,
  canonicalSourceUrl,
  dedupeCandidateRecords,
  isAllowedSourceUrl,
  makeCandidateRecord,
  serializeJsonlRecord,
  validateCaptureConfig,
} from "../lib/capture-core.mjs";

const sampleConfig = {
  product_id: "blackmagic-davinci",
  target_version: "21",
  release_date: "2026-04-14",
  watch_until: "2026-06-14",
  query_variants: ["DaVinci Resolve 21"],
  allowed_source_domains: ["forum.blackmagicdesign.com"],
};

test("serializes candidate records as one valid JSONL line", () => {
  const record = makeCandidateRecord({
    product_id: "blackmagic-davinci",
    target_version: "21",
    query_variant_used: "DaVinci Resolve 21",
    source_url: "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235117&sid=abc#p1",
    report_title: "Example thread",
    forum_category: "DaVinci Resolve > Post Production",
    source_date: "Tue Apr 14, 2026 10:15 am",
    captured_at: "2026-05-15T18:00:00.000Z",
    report_text: "Visible public post text.\nSecond line.",
    capture_status: "captured",
    notes: "Captured only.",
  });

  const line = serializeJsonlRecord(record);
  assert.equal(line.includes("\n"), false);

  const parsed = JSON.parse(line);
  assert.equal(parsed.collector_id, "local_browser_capture");
  assert.equal(parsed.source_id, "blackmagic_forum");
  assert.equal(parsed.source_url, "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235117");
  assert.equal(parsed.capture_status, "captured");
  assert.equal(parsed.verdict, undefined);
});

test("rejects verdict-like evidence decision fields", () => {
  const record = makeCandidateRecord({
    product_id: "blackmagic-davinci",
    target_version: "21",
    query_variant_used: "DaVinci Resolve 21",
    source_url: "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235118",
    capture_status: "captured",
  });

  assert.throws(
    () => serializeJsonlRecord({ ...record, verdict: "WAIT" }),
    /forbidden evidence-decision field/,
  );
});

test("deduplicates by canonical source_url", () => {
  const first = makeCandidateRecord({
    product_id: "blackmagic-davinci",
    target_version: "21",
    query_variant_used: "DaVinci Resolve 21",
    source_url: "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235117&sid=abc",
    capture_status: "captured",
  });
  const second = makeCandidateRecord({
    product_id: "blackmagic-davinci",
    target_version: "21",
    query_variant_used: "DaVinci Resolve 21 crash",
    source_url: "https://forum.blackmagicdesign.com/viewtopic.php?t=235117&f=21#latest",
    capture_status: "captured",
  });

  const result = dedupeCandidateRecords([first, second]);
  assert.equal(result.unique.length, 1);
  assert.equal(result.duplicates.length, 1);
  assert.equal(result.unique[0].source_url, "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235117");
});

test("deduplicates against existing output URLs", () => {
  const record = makeCandidateRecord({
    product_id: "blackmagic-davinci",
    target_version: "21",
    query_variant_used: "DaVinci Resolve 21 GPU",
    source_url: "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235200",
    capture_status: "captured",
  });

  const existing = new Set(["https://forum.blackmagicdesign.com/viewtopic.php?t=235200&f=21"]);
  const result = dedupeCandidateRecords([record], existing);
  assert.equal(result.unique.length, 0);
  assert.equal(result.duplicates.length, 1);
});

test("validates required config fields and allowed domain", () => {
  assert.equal(validateCaptureConfig(sampleConfig), true);

  const searchUrl = buildBlackmagicForumSearchUrl("DaVinci Resolve 21 crash");
  assert.equal(isAllowedSourceUrl(searchUrl, sampleConfig.allowed_source_domains), true);
  assert.equal(isAllowedSourceUrl("https://example.com/viewtopic.php?t=1", sampleConfig.allowed_source_domains), false);

  assert.throws(
    () => validateCaptureConfig({ ...sampleConfig, query_variants: [] }),
    /query_variants must be a non-empty array/,
  );
});

test("detects block and verification page signatures", () => {
  assert.equal(blockOrVerificationReason("<script>window.gokuProps = {}</script>"), "aws_waf_challenge");
  assert.equal(blockOrVerificationReason("Please verify you are human"), "human_verification");
  assert.equal(blockOrVerificationReason("Normal Blackmagic Design Community Forum thread"), "");
});

test("rejects obvious personal browser profile directories", () => {
  assert.equal(
    assertDedicatedBrowserProfile("C:\\AUXSAYS_CAPTURE\\browser-profiles\\blackmagic-forum"),
    true,
  );
  assert.throws(
    () => assertDedicatedBrowserProfile("C:\\Users\\someone\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default"),
    /personal browser profile/,
  );
});

test("canonicalizes Blackmagic forum thread URLs", () => {
  assert.equal(
    canonicalSourceUrl("https://forum.blackmagicdesign.com/viewtopic.php?sid=abc&t=235117&f=21&hilit=resolve#p1"),
    "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235117",
  );
});
