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
export const DEFAULT_DETAIL_TEXT_LIMIT = 30000;
export const DEFAULT_MAX_LISTING_PAGES = 1;
export const DEFAULT_MAX_DETAIL_PAGES = 10;
export const CAPTURE_STATUSES = new Set(["success", "blocked", "error"]);

export const REQUIRED_CANDIDATE_FIELDS = [
  "source_url",
  "source_name",
  "product_hint",
  "version_hint",
];

export const REQUIRED_SOURCE_FIELDS = [
  "product_id",
  "channel",
  "source_name",
  "source_type",
  "listing_urls",
  "detail_url_allow_patterns",
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
  --detail-log <path>            Captured detail-page JSONL log. Default: ./logs/capture-detail-pages.jsonl
  --skipped-url-log <path>       Skipped candidate URL JSONL log. Default: ./logs/capture-skipped-urls.jsonl
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
    detailLogPath: path.resolve(options.detailLog || path.join(appRoot, "logs", "capture-detail-pages.jsonl")),
    skippedUrlLogPath: path.resolve(options.skippedUrlLog || path.join(appRoot, "logs", "capture-skipped-urls.jsonl")),
  };
}

export async function loadCandidateConfig(configPath, options = {}) {
  let parsed;
  try {
    parsed = JSON.parse(await fs.readFile(configPath, "utf8"));
  } catch (error) {
    throw new Error(`Unable to read candidate config at ${configPath}: ${error.message}`);
  }

  const candidates = Array.isArray(parsed) ? parsed : (parsed.candidates || []);
  const sources = Array.isArray(parsed) ? [] : (parsed.sources || []);
  if (!Array.isArray(candidates)) {
    throw new Error("candidate config candidates field must be an array");
  }
  if (!Array.isArray(sources)) {
    throw new Error("candidate config sources field must be an array");
  }
  if (!candidates.length && !sources.length) {
    throw new Error("candidate config must include candidates or sources");
  }

  const maxUrlsPerRun = Number(parsed.max_urls_per_run ?? parsed.maxUrlsPerRun ?? DEFAULT_MAX_URLS_PER_RUN);
  return {
    candidates: validateCandidates(candidates, options),
    sources: validateSources(sources, options),
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

export function validateSources(sources, options = {}) {
  return sources
    .filter((source) => source && source.enabled !== false)
    .map((source, index) => {
      for (const field of REQUIRED_SOURCE_FIELDS) {
        const value = source[field];
        const missingArray = Array.isArray(value) && value.length === 0;
        if ((!Array.isArray(value) && !String(value ?? "").trim()) || missingArray) {
          throw new Error(`source ${index + 1} missing required field: ${field}`);
        }
      }
      if (!Array.isArray(source.listing_urls)) {
        throw new Error(`source ${index + 1} listing_urls must be an array`);
      }
      if (!Array.isArray(source.detail_url_allow_patterns)) {
        throw new Error(`source ${index + 1} detail_url_allow_patterns must be an array`);
      }
      for (const pattern of source.detail_url_allow_patterns) {
        try {
          new RegExp(String(pattern));
        } catch (error) {
          throw new Error(`source ${index + 1} invalid detail_url_allow_patterns entry: ${error.message}`);
        }
      }
      const listingUrls = source.listing_urls.map((url) => normalizeCandidateUrl(url, options));
      const maxListingPages = positiveInt(source.max_listing_pages ?? source.maxListingPages, DEFAULT_MAX_LISTING_PAGES);
      const maxDetailPages = positiveInt(source.max_detail_pages ?? source.maxDetailPages, DEFAULT_MAX_DETAIL_PAGES);
      return {
        product_id: normalizeText(source.product_id),
        channel: normalizeText(source.channel),
        source_name: normalizeText(source.source_name),
        source_type: normalizeText(source.source_type),
        listing_urls: listingUrls,
        search_urls: Array.isArray(source.search_urls)
          ? source.search_urls.map((url) => normalizeCandidateUrl(url, options))
          : [],
        detail_url_allow_patterns: source.detail_url_allow_patterns.map((pattern) => String(pattern)),
        max_listing_pages: maxListingPages,
        max_detail_pages: maxDetailPages,
        enabled: source.enabled !== false,
        requires_local_capture: source.requires_local_capture !== false,
        notes: normalizeText(source.notes || ""),
        version_hint: normalizeText(source.version_hint || ""),
      };
    });
}

export function positiveInt(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback;
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

export async function appendRawJsonl(filePath, row) {
  await assertOutboxPath(filePath);
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.appendFile(filePath, `${JSON.stringify(row)}\n`, "utf8");
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

export function canonicalDedupeUrl(value) {
  let parsed;
  try {
    parsed = new URL(String(value ?? "").trim());
  } catch {
    return "";
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    return "";
  }
  parsed.hash = "";
  parsed.username = "";
  parsed.password = "";
  parsed.protocol = parsed.protocol.toLowerCase();
  parsed.hostname = parsed.hostname.toLowerCase();
  if (parsed.hostname === "www.creativecow.net") {
    parsed.hostname = "creativecow.net";
  }
  parsed.pathname = parsed.pathname.replace(/\/+/g, "/").replace(/\/$/, "");
  parsed.search = "";
  return parsed.toString();
}

export function sameDomainUrl(candidateUrl, listingUrl) {
  try {
    const candidate = new URL(candidateUrl);
    const listing = new URL(listingUrl);
    const candidateHost = candidate.hostname.toLowerCase().replace(/^www\./, "");
    const listingHost = listing.hostname.toLowerCase().replace(/^www\./, "");
    return candidateHost === listingHost;
  } catch {
    return false;
  }
}

export function urlAllowedByPatterns(url, patterns) {
  return patterns.some((pattern) => new RegExp(pattern).test(url));
}

export function extractDateText(text) {
  const match = String(text || "").match(
    /\b(?:\d+\s+(?:minute|hour|day|week|month|year)s?\s+ago|yesterday|today|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s+20\d{2})\b/i,
  );
  return match ? match[0] : "";
}

export function extractCandidateDetailUrlsFromAnchors(anchors, source, listingUrl) {
  const candidates = [];
  const skipped = [];
  const seen = new Set();

  for (const anchor of anchors) {
    let absoluteUrl = "";
    try {
      absoluteUrl = new URL(String(anchor.href || ""), listingUrl).toString();
    } catch {
      skipped.push({ candidate_url: String(anchor.href || ""), reason: "invalid_url" });
      continue;
    }

    const dedupeKey = canonicalDedupeUrl(absoluteUrl);
    if (!dedupeKey) {
      skipped.push({ candidate_url: absoluteUrl, reason: "unsupported_url" });
      continue;
    }
    if (!sameDomainUrl(dedupeKey, listingUrl)) {
      skipped.push({ candidate_url: absoluteUrl, reason: "different_domain" });
      continue;
    }
    if (!urlAllowedByPatterns(dedupeKey, source.detail_url_allow_patterns)) {
      skipped.push({ candidate_url: absoluteUrl, reason: "allow_pattern_miss" });
      continue;
    }
    if (seen.has(dedupeKey)) {
      skipped.push({ candidate_url: absoluteUrl, reason: "duplicate_candidate_url", url_dedupe_key: dedupeKey });
      continue;
    }
    seen.add(dedupeKey);
    const listingCardTitle = normalizeText(anchor.text || anchor.title || anchor.ariaLabel || "");
    const listingCardDateText = extractDateText(anchor.containerText || "");
    candidates.push({
      detail_url: dedupeKey,
      url_dedupe_key: dedupeKey,
      listing_card_title: listingCardTitle,
      listing_card_date_text: listingCardDateText,
      listing_source_url: listingUrl,
      source_name: source.source_name,
      source_type: source.source_type,
      product_id: source.product_id,
      channel: source.channel,
    });
  }

  return { candidates, skipped };
}

export async function extractCandidateDetailUrls(page, source, listingUrl) {
  const anchors = await page.locator("a[href]").evaluateAll((nodes) => nodes.map((node) => {
    const container = node.closest("article, li, tr, .lia-list-row, .lia-message-view, .message-list-item, .topic, .bbp-topic, div");
    return {
      href: node.getAttribute("href") || "",
      text: node.textContent || "",
      title: node.getAttribute("title") || "",
      ariaLabel: node.getAttribute("aria-label") || "",
      containerText: container ? (container.textContent || "") : (node.parentElement ? node.parentElement.textContent || "" : ""),
    };
  })).catch(() => []);
  return extractCandidateDetailUrlsFromAnchors(anchors, source, listingUrl);
}

export async function captureDetailPage(page, detailCandidate, source, timeoutMs) {
  const candidate = {
    source_url: detailCandidate.detail_url,
    source_name: source.source_name,
    product_hint: source.product_id,
    version_hint: source.version_hint || "",
  };
  const baseRow = await captureCandidate(page, candidate, timeoutMs);
  if (baseRow.capture_status !== "success") {
    return {
      ...baseRow,
      product_id: source.product_id,
      source_type: source.source_type,
      detail_url: detailCandidate.detail_url,
      listing_source_url: detailCandidate.listing_source_url,
      listing_card_title: detailCandidate.listing_card_title || "",
      listing_card_date_text: detailCandidate.listing_card_date_text || "",
      url_dedupe_key: detailCandidate.url_dedupe_key,
    };
  }

  const detailData = await page.evaluate(() => {
    const textOf = (selector) => {
      const node = document.querySelector(selector);
      return node ? (node.textContent || "").trim() : "";
    };
    const title = textOf("h1") || textOf("h2") || document.title || "";
    const main = document.querySelector("article, main, [role='main'], .lia-message-body-content, .bbp-reply-content") || document.body;
    const bodyText = main ? (main.innerText || main.textContent || "") : "";
    const timeNode = document.querySelector("time[datetime], time");
    const timeDate = timeNode ? (timeNode.getAttribute("datetime") || "") : "";
    const timeText = timeNode ? (timeNode.textContent || "").trim() : "";
    const author = textOf("[rel='author']") || textOf(".lia-user-name") || textOf(".author") || textOf(".bbp-author-name");
    const fullText = document.body ? (document.body.innerText || "") : "";
    const categoryMatch = fullText.match(/\b(Bug Reports|Discussions|Questions|Ideas|Feature Requests|Community)\b/i);
    const statusMatch = fullText.match(/\b(Open for Voting|Needs More Info|Solved|Unsolved|Closed|Locked)\b/i);
    return {
      title,
      bodyText,
      sourceDateText: timeText || timeDate,
      sourceDateResolved: timeDate,
      authorContext: author,
      category: categoryMatch ? categoryMatch[1] : "",
      status: statusMatch ? statusMatch[1] : "",
    };
  }).catch(() => ({
    title: baseRow.page_title,
    bodyText: baseRow.visible_text,
    sourceDateText: "",
    sourceDateResolved: "",
    authorContext: "",
    category: "",
    status: "",
  }));

  const title = normalizeText(detailData.title || baseRow.page_title);
  const bodyText = normalizeText(detailData.bodyText || baseRow.visible_text, DEFAULT_DETAIL_TEXT_LIMIT);
  const sourceDateText = normalizeText(detailData.sourceDateText || extractDateText(bodyText) || detailCandidate.listing_card_date_text || "");
  const sourceDateResolved = normalizeResolvedDate(detailData.sourceDateResolved || "");

  return {
    ...baseRow,
    product_id: source.product_id,
    channel: source.channel,
    source_type: source.source_type,
    detail_url: detailCandidate.detail_url,
    listing_source_url: detailCandidate.listing_source_url,
    title,
    body_text: bodyText,
    excerpt: normalizeText(bodyText, 1200),
    source_date_text: sourceDateText,
    source_date_resolved: sourceDateResolved,
    listing_card_title: detailCandidate.listing_card_title || "",
    listing_card_date_text: detailCandidate.listing_card_date_text || "",
    category: normalizeText(detailData.category || ""),
    status: normalizeText(detailData.status || ""),
    author_context: normalizeText(detailData.authorContext || ""),
    url_dedupe_key: detailCandidate.url_dedupe_key,
    visible_text: normalizeText([title, sourceDateText, bodyText].filter(Boolean).join("\n"), DEFAULT_TEXT_LIMIT),
  };
}

export function normalizeResolvedDate(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return text;
  }
  return parsed.toISOString();
}

export async function runCaptureOnce(options = {}) {
  const paths = resolveRuntimePaths(options);
  const config = await loadCandidateConfig(paths.configPath, {
    allowLocalhostTest: options.allowLocalhostTest,
  });
  const candidates = config.candidates;
  const sources = config.sources;
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
      detail_log: paths.detailLogPath,
      skipped_url_log: paths.skippedUrlLogPath,
      candidates_loaded: candidates.length,
      candidates_selected: selected.length,
      sources_loaded: sources.length,
    };
  }

  await writeLogLine(paths.logFilePath, `run started; selected ${selected.length} candidate URL(s), ${sources.length} source(s)`);
  await writeMetaLine(paths.metaLogPath, {
    event: "run_started",
    candidates_loaded: candidates.length,
    candidates_selected: selected.length,
    sources_loaded: sources.length,
    outbox_path: paths.outboxPath,
  });

  let browser;
  const summary = {
    mode: "capture_once",
    candidates_loaded: candidates.length,
    candidates_selected: selected.length,
    rows_written: 0,
    listing_pages_captured: 0,
    candidate_detail_urls_extracted: 0,
    detail_pages_captured: 0,
    skipped_urls: 0,
    success: 0,
    blocked: 0,
    error: 0,
    outbox_path: paths.outboxPath,
    log_file: paths.logFilePath,
    meta_log: paths.metaLogPath,
    detail_log: paths.detailLogPath,
    skipped_url_log: paths.skippedUrlLogPath,
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

    for (const source of sources) {
      const listingUrls = source.listing_urls.slice(0, source.max_listing_pages);
      const sourceDetailSeen = new Set();
      for (const listingUrl of listingUrls) {
        const listingCandidate = {
          source_url: listingUrl,
          source_name: source.source_name,
          product_hint: source.product_id,
          version_hint: source.version_hint || "",
        };
        await writeMetaLine(paths.metaLogPath, {
          event: "listing_started",
          source_url: listingUrl,
          source_name: source.source_name,
          source_type: source.source_type,
        });
        const listingRow = await captureCandidate(page, listingCandidate, timeoutMs);
        listingRow.product_id = source.product_id;
        listingRow.channel = source.channel;
        listingRow.source_type = source.source_type;
        listingRow.requires_local_capture = source.requires_local_capture;
        await appendJsonl(paths.outboxPath, listingRow);
        summary.rows_written += 1;
        summary[listingRow.capture_status] += 1;
        if (listingRow.capture_status === "success") {
          summary.listing_pages_captured += 1;
          const extracted = await extractCandidateDetailUrls(page, source, listingUrl);
          for (const skipped of extracted.skipped) {
            summary.skipped_urls += 1;
            await appendRawJsonl(paths.skippedUrlLogPath, {
              ...skipped,
              source_name: source.source_name,
              source_type: source.source_type,
              source_url: listingUrl,
              captured_at: utcTimestamp(),
            });
          }
          const detailCandidates = [];
          for (const detailCandidate of extracted.candidates) {
            if (sourceDetailSeen.has(detailCandidate.url_dedupe_key)) {
              summary.skipped_urls += 1;
              await appendRawJsonl(paths.skippedUrlLogPath, {
                source_name: source.source_name,
                source_type: source.source_type,
                source_url: listingUrl,
                candidate_url: detailCandidate.detail_url,
                reason: "duplicate_candidate_url",
                url_dedupe_key: detailCandidate.url_dedupe_key,
                captured_at: utcTimestamp(),
              });
              continue;
            }
            sourceDetailSeen.add(detailCandidate.url_dedupe_key);
            detailCandidates.push(detailCandidate);
          }
          summary.candidate_detail_urls_extracted += detailCandidates.length;
          for (const detailCandidate of detailCandidates.slice(0, source.max_detail_pages)) {
            await writeMetaLine(paths.metaLogPath, {
              event: "detail_started",
              source_url: listingUrl,
              detail_url: detailCandidate.detail_url,
              source_name: source.source_name,
            });
            const detailRow = await captureDetailPage(page, detailCandidate, source, timeoutMs);
            await appendJsonl(paths.outboxPath, detailRow);
            await appendJsonl(paths.detailLogPath, detailRow);
            summary.rows_written += 1;
            summary[detailRow.capture_status] += 1;
            if (detailRow.capture_status === "success") {
              summary.detail_pages_captured += 1;
            }
            await writeMetaLine(paths.metaLogPath, {
              event: "detail_finished",
              source_url: listingUrl,
              detail_url: detailCandidate.detail_url,
              capture_status: detailRow.capture_status,
              error_reason: detailRow.error_reason || "",
            });
          }
          for (const detailCandidate of detailCandidates.slice(source.max_detail_pages)) {
            summary.skipped_urls += 1;
            await appendRawJsonl(paths.skippedUrlLogPath, {
              source_name: source.source_name,
              source_type: source.source_type,
              source_url: listingUrl,
              candidate_url: detailCandidate.detail_url,
              reason: "max_detail_pages_exceeded",
              url_dedupe_key: detailCandidate.url_dedupe_key,
              captured_at: utcTimestamp(),
            });
          }
        }
        await writeMetaLine(paths.metaLogPath, {
          event: "listing_finished",
          source_url: listingUrl,
          final_url: listingRow.final_url,
          capture_status: listingRow.capture_status,
          error_reason: listingRow.error_reason || "",
        });
      }
    }

    await context.close().catch(() => {});
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    await writeLogLine(
      paths.logFilePath,
      `run finished; rows=${summary.rows_written}; listings=${summary.listing_pages_captured}; detail_urls=${summary.candidate_detail_urls_extracted}; details=${summary.detail_pages_captured}; success=${summary.success}; blocked=${summary.blocked}; error=${summary.error}`,
    );
    await writeMetaLine(paths.metaLogPath, {
      event: "run_finished",
      rows_written: summary.rows_written,
      listing_pages_captured: summary.listing_pages_captured,
      candidate_detail_urls_extracted: summary.candidate_detail_urls_extracted,
      detail_pages_captured: summary.detail_pages_captured,
      skipped_urls: summary.skipped_urls,
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
      "detail-log": { type: "string" },
      "skipped-url-log": { type: "string" },
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
    detailLog: values["detail-log"],
    skippedUrlLog: values["skipped-url-log"],
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
