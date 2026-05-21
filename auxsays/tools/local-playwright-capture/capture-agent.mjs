#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

export const CAPTURE_METHOD = "local_playwright";
export const APP_NAME = "AUXSAYS Local Playwright Capture";
export const DEFAULT_MAX_URLS_PER_RUN = 10;
export const DEFAULT_TIMEOUT_MS = 30000;
export const DEFAULT_TEXT_LIMIT = 60000;
export const CAPTURE_STATUSES = new Set(["success", "blocked", "error"]);

export const REQUIRED_CANDIDATE_FIELDS = [
  "source_url",
  "source_name",
  "product_hint",
  "version_hint",
];

export const REQUIRED_OUTPUT_FIELDS = [
  "source_url",
  "final_url",
  "source_name",
  "product_hint",
  "version_hint",
  "page_title",
  "visible_text",
  "captured_at",
  "capture_method",
  "capture_status",
];

export const FORBIDDEN_REPO_WRITE_PATH_MARKERS = [
  "auxsays/_data/consensus_evidence.yml",
  "auxsays/_data/evidence_method_health.yml",
  "auxsays/_data/source_health.yml",
  "auxsays/_data/qa_status.json",
  "auxsays/_data/consensus_status.json",
  "auxsays/_data/patch_ingest_state.json",
  "auxsays/updates/generated/",
];

const USAGE = `
${APP_NAME}

Usage:
  node capture-agent.mjs
  node capture-agent.mjs --config app/config/candidates.json --max-urls 10
  node capture-agent.mjs --interval-minutes 360

Options:
  --config <path>               Candidate config path. Default: ./config/candidates.json
  --outbox <path>               JSONL output file. Default: ./outbox/captured-pages.jsonl
  --log-file <path>             Human-readable log. Default: ./logs/capture.log
  --meta-log <path>             JSONL meta log. Default: ./logs/capture-meta.jsonl
  --max-urls <number>           Maximum candidate URLs per run. Default: 10
  --timeout-ms <number>         Timeout per page. Default: 30000
  --interval-minutes <number>   Run repeatedly with this delay between runs.
  --headed                      Show the Chromium window. Default: headless.
  --dry-run                     Validate config and paths without opening pages.
  --allow-localhost-test        Allow localhost URLs for explicit local fixture tests only.
  --help                        Show this help.
`;

export function utcTimestamp(date = new Date()) {
  return date.toISOString();
}

export function normalizeText(value, maxLength = 0) {
  const text = String(value ?? "")
    .replace(/\u00a0/g, " ")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t\f\v]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (maxLength > 0 && text.length > maxLength) {
    return `${text.slice(0, maxLength).trimEnd()}...`;
  }
  return text;
}

export function appRootFromImportMeta(importMetaUrl = import.meta.url) {
  return path.dirname(fileURLToPath(importMetaUrl));
}

export function resolveRuntimePaths(options = {}) {
  const appRoot = path.resolve(options.appRoot || appRootFromImportMeta());
  return {
    appRoot,
    configPath: path.resolve(options.config || path.join(appRoot, "config", "candidates.json")),
    outboxPath: path.resolve(options.outbox || path.join(appRoot, "outbox", "captured-pages.jsonl")),
    logFilePath: path.resolve(options.logFile || path.join(appRoot, "logs", "capture.log")),
    metaLogPath: path.resolve(options.metaLog || path.join(appRoot, "logs", "capture-meta.jsonl")),
  };
}

export async function loadCandidateConfig(configPath, options = {}) {
  let parsed;
  try {
    parsed = JSON.parse(await fs.readFile(configPath, "utf8"));
  } catch (error) {
    throw new Error(`Unable to read candidate config at ${configPath}: ${error.message}`);
  }

  const candidates = Array.isArray(parsed) ? parsed : parsed.candidates;
  if (!Array.isArray(candidates)) {
    throw new Error("candidate config must be an array or an object with a candidates array");
  }

  const maxUrlsPerRun = Number(parsed.max_urls_per_run ?? parsed.maxUrlsPerRun ?? DEFAULT_MAX_URLS_PER_RUN);
  return {
    candidates: validateCandidates(candidates, options),
    maxUrlsPerRun: Number.isFinite(maxUrlsPerRun) && maxUrlsPerRun > 0
      ? Math.floor(maxUrlsPerRun)
      : DEFAULT_MAX_URLS_PER_RUN,
  };
}

export function validateCandidates(candidates, options = {}) {
  return candidates.map((candidate, index) => {
    for (const field of REQUIRED_CANDIDATE_FIELDS) {
      if (!String(candidate[field] ?? "").trim()) {
        throw new Error(`candidate ${index + 1} missing required field: ${field}`);
      }
    }
    const sourceUrl = normalizeCandidateUrl(candidate.source_url, options);
    return {
      source_url: sourceUrl,
      source_name: normalizeText(candidate.source_name),
      product_hint: normalizeText(candidate.product_hint),
      version_hint: normalizeText(candidate.version_hint),
    };
  });
}

export function normalizeCandidateUrl(value, options = {}) {
  let parsed;
  try {
    parsed = new URL(String(value ?? "").trim());
  } catch {
    throw new Error(`invalid source_url: ${value}`);
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error(`source_url must use http or https: ${value}`);
  }

  const host = parsed.hostname.toLowerCase();
  const isLocalhost = host === "localhost" || host === "127.0.0.1" || host === "::1";
  if (isLocalhost && !options.allowLocalhostTest) {
    throw new Error(`localhost source_url is allowed only with --allow-localhost-test: ${value}`);
  }

  parsed.hash = "";
  parsed.username = "";
  parsed.password = "";
  parsed.protocol = parsed.protocol.toLowerCase();
  parsed.hostname = host;
  return parsed.toString();
}

export function selectCandidatesForRun(candidates, maxUrls) {
  const limit = Number.isFinite(Number(maxUrls)) && Number(maxUrls) > 0
    ? Math.floor(Number(maxUrls))
    : DEFAULT_MAX_URLS_PER_RUN;
  return candidates.slice(0, limit);
}

export function classifyBlockedPage({ html = "", title = "", text = "", status = 0 } = {}) {
  const haystack = `${title}\n${text}\n${String(html).slice(0, 8000)}`.toLowerCase();
  if (status === 401 || status === 403 || status === 429) {
    return status === 429 ? "rate_limited" : "access_denied";
  }
  if (haystack.includes("captcha") || haystack.includes("g-recaptcha") || haystack.includes("hcaptcha")) {
    return "captcha_challenge";
  }
  if (haystack.includes("verify you are human") || haystack.includes("verification required")) {
    return "human_verification";
  }
  if (haystack.includes("checking your browser") || haystack.includes("just a moment")) {
    return "browser_challenge";
  }
  if (haystack.includes("cloudflare ray id") || haystack.includes("cf-chl-")) {
    return "cloudflare_challenge";
  }
  if (haystack.includes("window.gokuprops") || haystack.includes("awswaf")) {
    return "aws_waf_challenge";
  }
  if (haystack.includes("access denied") || haystack.includes("forbidden")) {
    return "access_denied";
  }
  return "";
}

export function makeCaptureRow(candidate, pageData = {}) {
  const status = pageData.capture_status || "success";
  if (!CAPTURE_STATUSES.has(status)) {
    throw new Error(`unsupported capture_status: ${status}`);
  }

  const row = {
    source_url: candidate.source_url,
    final_url: pageData.final_url || candidate.source_url,
    source_name: candidate.source_name,
    product_hint: candidate.product_hint,
    version_hint: candidate.version_hint,
    page_title: normalizeText(pageData.page_title || ""),
    visible_text: normalizeText(pageData.visible_text || "", DEFAULT_TEXT_LIMIT),
    captured_at: pageData.captured_at || utcTimestamp(),
    capture_method: CAPTURE_METHOD,
    capture_status: status,
  };

  if (pageData.error_reason) {
    row.error_reason = normalizeText(pageData.error_reason);
  }

  validateCaptureRow(row);
  return row;
}

export function validateCaptureRow(row) {
  for (const field of REQUIRED_OUTPUT_FIELDS) {
    if (!(field in row)) {
      throw new Error(`capture row missing required field: ${field}`);
    }
  }
  if (!CAPTURE_STATUSES.has(row.capture_status)) {
    throw new Error(`unsupported capture_status: ${row.capture_status}`);
  }
  if (row.capture_method !== CAPTURE_METHOD) {
    throw new Error(`capture_method must be ${CAPTURE_METHOD}`);
  }
  if ((row.capture_status === "blocked" || row.capture_status === "error") && !row.error_reason) {
    throw new Error("blocked/error rows require error_reason");
  }
  for (const forbidden of ["verdict", "decision", "evidence_state", "confidence", "counted"]) {
    if (forbidden in row) {
      throw new Error(`capture row contains forbidden decision field: ${forbidden}`);
    }
  }
  return true;
}

export function serializeJsonl(row) {
  validateCaptureRow(row);
  return JSON.stringify(row);
}

export async function appendJsonl(filePath, row) {
  await assertOutboxPath(filePath);
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.appendFile(filePath, `${serializeJsonl(row)}\n`, "utf8");
}

export async function writeLogLine(filePath, message) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.appendFile(filePath, `[${utcTimestamp()}] ${message}\n`, "utf8");
}

export async function writeMetaLine(filePath, event) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.appendFile(filePath, `${JSON.stringify({ captured_at: utcTimestamp(), app_name: APP_NAME, ...event })}\n`, "utf8");
}

export async function assertOutboxPath(filePath) {
  const normalized = path.resolve(filePath).replace(/\\/g, "/").toLowerCase();
  for (const marker of FORBIDDEN_REPO_WRITE_PATH_MARKERS) {
    if (normalized.includes(marker.toLowerCase())) {
      throw new Error(`refusing to write capture output to protected AUXSAYS path: ${filePath}`);
    }
  }
  return true;
}

export async function captureCandidate(page, candidate, timeoutMs) {
  try {
    const response = await page.goto(candidate.source_url, {
      waitUntil: "domcontentloaded",
      timeout: timeoutMs,
    });
    await page.waitForLoadState("networkidle", { timeout: 3000 }).catch(() => {});

    const pageTitle = await page.title().catch(() => "");
    const visibleText = await page.locator("body").innerText({ timeout: 3000 }).catch(() => "");
    const html = await page.content().catch(() => "");
    const status = response ? response.status() : 0;
    const blockReason = classifyBlockedPage({
      html,
      title: pageTitle,
      text: visibleText,
      status,
    });

    if (blockReason) {
      return makeCaptureRow(candidate, {
        final_url: page.url(),
        page_title: pageTitle,
        visible_text: "",
        capture_status: "blocked",
        error_reason: blockReason,
      });
    }

    return makeCaptureRow(candidate, {
      final_url: page.url(),
      page_title: pageTitle,
      visible_text: visibleText,
      capture_status: "success",
    });
  } catch (error) {
    return makeCaptureRow(candidate, {
      final_url: candidate.source_url,
      page_title: "",
      visible_text: "",
      capture_status: "error",
      error_reason: error.message,
    });
  }
}

export async function runCaptureOnce(options = {}) {
  const paths = resolveRuntimePaths(options);
  const config = await loadCandidateConfig(paths.configPath, {
    allowLocalhostTest: options.allowLocalhostTest,
  });
  const candidates = config.candidates;
  const maxUrls = Number(options.maxUrls ?? config.maxUrlsPerRun ?? DEFAULT_MAX_URLS_PER_RUN);
  const selected = selectCandidatesForRun(candidates, maxUrls);
  const timeoutMs = Number(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);

  if (options.dryRun) {
    return {
      mode: "dry_run",
      config_path: paths.configPath,
      outbox_path: paths.outboxPath,
      log_file: paths.logFilePath,
      meta_log: paths.metaLogPath,
      candidates_loaded: candidates.length,
      candidates_selected: selected.length,
    };
  }

  await writeLogLine(paths.logFilePath, `run started; selected ${selected.length} candidate URL(s)`);
  await writeMetaLine(paths.metaLogPath, {
    event: "run_started",
    candidates_loaded: candidates.length,
    candidates_selected: selected.length,
    outbox_path: paths.outboxPath,
  });

  let browser;
  const summary = {
    mode: "capture_once",
    candidates_loaded: candidates.length,
    candidates_selected: selected.length,
    rows_written: 0,
    success: 0,
    blocked: 0,
    error: 0,
    outbox_path: paths.outboxPath,
    log_file: paths.logFilePath,
    meta_log: paths.metaLogPath,
  };

  try {
    const { chromium } = await import("playwright");
    browser = await chromium.launch({
      headless: !options.headed,
      timeout: timeoutMs,
    });
    const context = await browser.newContext({
      viewport: { width: 1366, height: 900 },
      locale: "en-US",
      ignoreHTTPSErrors: false,
    });
    const page = await context.newPage();
    page.setDefaultTimeout(timeoutMs);

    for (const candidate of selected) {
      await writeMetaLine(paths.metaLogPath, {
        event: "candidate_started",
        source_url: candidate.source_url,
        source_name: candidate.source_name,
      });
      const row = await captureCandidate(page, candidate, timeoutMs);
      await appendJsonl(paths.outboxPath, row);
      summary.rows_written += 1;
      summary[row.capture_status] += 1;
      await writeMetaLine(paths.metaLogPath, {
        event: "candidate_finished",
        source_url: candidate.source_url,
        final_url: row.final_url,
        capture_status: row.capture_status,
        error_reason: row.error_reason || "",
      });
    }

    await context.close().catch(() => {});
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    await writeLogLine(
      paths.logFilePath,
      `run finished; rows=${summary.rows_written}; success=${summary.success}; blocked=${summary.blocked}; error=${summary.error}`,
    );
    await writeMetaLine(paths.metaLogPath, {
      event: "run_finished",
      rows_written: summary.rows_written,
      success: summary.success,
      blocked: summary.blocked,
      error: summary.error,
    });
  }

  return summary;
}

export async function runCaptureLoop(options = {}) {
  const intervalMinutes = Number(options.intervalMinutes || 0);
  if (!Number.isFinite(intervalMinutes) || intervalMinutes <= 0) {
    return runCaptureOnce(options);
  }

  let stopping = false;
  const stop = () => {
    stopping = true;
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  let lastSummary = null;
  do {
    lastSummary = await runCaptureOnce(options);
    if (stopping) {
      break;
    }
    await delayMinutes(intervalMinutes, () => stopping);
  } while (!stopping);

  process.removeListener("SIGINT", stop);
  process.removeListener("SIGTERM", stop);
  return { ...lastSummary, mode: "capture_interval", stopped: true };
}

export async function delayMinutes(minutes, shouldStop = () => false) {
  const endAt = Date.now() + Math.max(0, minutes) * 60 * 1000;
  while (Date.now() < endAt && !shouldStop()) {
    await new Promise((resolve) => setTimeout(resolve, Math.min(1000, endAt - Date.now())));
  }
}

async function main() {
  const { values } = parseArgs({
    options: {
      config: { type: "string" },
      outbox: { type: "string" },
      "log-file": { type: "string" },
      "meta-log": { type: "string" },
      "max-urls": { type: "string" },
      "timeout-ms": { type: "string" },
      "interval-minutes": { type: "string" },
      headed: { type: "boolean", default: false },
      "dry-run": { type: "boolean", default: false },
      "allow-localhost-test": { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });

  if (values.help) {
    process.stdout.write(USAGE.trimStart());
    return 0;
  }

  const summary = await runCaptureLoop({
    config: values.config,
    outbox: values.outbox,
    logFile: values["log-file"],
    metaLog: values["meta-log"],
    maxUrls: values["max-urls"] ? Number(values["max-urls"]) : undefined,
    timeoutMs: values["timeout-ms"] ? Number(values["timeout-ms"]) : undefined,
    intervalMinutes: values["interval-minutes"] ? Number(values["interval-minutes"]) : 0,
    headed: values.headed,
    dryRun: values["dry-run"],
    allowLocalhostTest: values["allow-localhost-test"],
  });

  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then((status) => {
    process.exitCode = status;
  }).catch((error) => {
    process.stderr.write(`${error.stack || error.message}\n`);
    process.exitCode = 1;
  });
}
