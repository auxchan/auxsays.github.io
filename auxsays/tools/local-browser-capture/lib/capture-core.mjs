import fs from "node:fs/promises";
import path from "node:path";

export const COLLECTOR_ID = "local_browser_capture";
export const SOURCE_ID = "blackmagic_forum";
export const DEFAULT_CAPTURE_ROOT = "C:\\AUXSAYS_CAPTURE";

export const CAPTURE_STATUSES = new Set([
  "captured",
  "blocked_or_verification",
  "no_readable_text",
  "failed",
  "skipped_duplicate",
  "dry_run",
]);

const RECORD_FIELD_ORDER = [
  "collector_id",
  "source_id",
  "product_id",
  "target_version",
  "query_variant_used",
  "source_url",
  "report_title",
  "forum_category",
  "source_date",
  "captured_at",
  "report_text",
  "capture_status",
  "notes",
];

const FORBIDDEN_RECORD_FIELDS = new Set([
  "verdict",
  "decision",
  "evidence_state",
  "confidence",
  "counted",
  "sentiment",
  "severity",
]);

export function utcTimestamp() {
  return new Date().toISOString();
}

export function fileTimestamp(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-");
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

export function sanitizePathSegment(value) {
  const segment = String(value ?? "")
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return segment || "capture";
}

export function canonicalSourceUrl(value) {
  const parsed = new URL(String(value ?? "").trim(), "https://forum.blackmagicdesign.com/");
  parsed.hash = "";
  parsed.username = "";
  parsed.password = "";
  parsed.protocol = parsed.protocol.toLowerCase();
  parsed.hostname = parsed.hostname.toLowerCase();

  if (parsed.hostname === "forum.blackmagicdesign.com" && /\/viewtopic\.php$/i.test(parsed.pathname)) {
    const canonicalParams = new URLSearchParams();
    if (parsed.searchParams.has("f")) {
      canonicalParams.set("f", parsed.searchParams.get("f"));
    }
    if (parsed.searchParams.has("t")) {
      canonicalParams.set("t", parsed.searchParams.get("t"));
    } else if (parsed.searchParams.has("p")) {
      canonicalParams.set("p", parsed.searchParams.get("p"));
    }
    parsed.search = canonicalParams.toString();
    return parsed.toString();
  }

  const noisyParams = [
    "sid",
    "hilit",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
  ];
  for (const param of noisyParams) {
    parsed.searchParams.delete(param);
  }
  parsed.searchParams.sort();
  return parsed.toString();
}

export function hostMatchesAllowedDomain(hostname, allowedDomain) {
  const host = String(hostname ?? "").toLowerCase().replace(/^www\./, "");
  const allowed = String(allowedDomain ?? "").toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*$/, "");
  return host === allowed || host.endsWith(`.${allowed}`);
}

export function isAllowedSourceUrl(value, allowedDomains) {
  if (!Array.isArray(allowedDomains) || allowedDomains.length === 0) {
    return false;
  }
  try {
    const parsed = new URL(value);
    return allowedDomains.some((domain) => hostMatchesAllowedDomain(parsed.hostname, domain));
  } catch {
    return false;
  }
}

export function assertDedicatedBrowserProfile(profileDir) {
  const normalized = String(profileDir ?? "").toLowerCase().replace(/\//g, "\\");
  const personalProfileMarkers = [
    "\\appdata\\local\\google\\chrome\\user data",
    "\\appdata\\local\\microsoft\\edge\\user data",
    "\\appdata\\local\\braveSoftware\\brave-browser\\user data".toLowerCase(),
  ];
  if (personalProfileMarkers.some((marker) => normalized.includes(marker))) {
    throw new Error("browser_profile_dir appears to point at a personal browser profile; use a dedicated AUXSAYS capture profile");
  }
  return true;
}

export function buildBlackmagicForumSearchUrl(queryVariant) {
  const url = new URL("https://forum.blackmagicdesign.com/search.php");
  url.searchParams.set("keywords", String(queryVariant ?? "").trim());
  url.searchParams.set("terms", "all");
  url.searchParams.set("author", "");
  url.searchParams.set("sc", "1");
  url.searchParams.set("sf", "all");
  return url.toString();
}

export function blockOrVerificationReason(text) {
  const lowered = String(text ?? "").toLowerCase();
  if (!lowered.trim()) {
    return "";
  }
  if (lowered.includes("window.gokuprops") || lowered.includes("awswaf")) {
    return "aws_waf_challenge";
  }
  if (lowered.includes("captcha")) {
    return "captcha_challenge";
  }
  if (lowered.includes("verify you are human") || lowered.includes("verification required")) {
    return "human_verification";
  }
  if (lowered.includes("checking your browser") || lowered.includes("please enable javascript")) {
    return "browser_verification";
  }
  if (lowered.includes("access denied") || lowered.includes("forbidden")) {
    return "access_denied";
  }
  return "";
}

export function makeCandidateRecord(input) {
  const record = {
    collector_id: COLLECTOR_ID,
    source_id: SOURCE_ID,
    product_id: String(input.product_id ?? ""),
    target_version: String(input.target_version ?? ""),
    query_variant_used: String(input.query_variant_used ?? ""),
    source_url: canonicalSourceUrl(input.source_url ?? ""),
    report_title: normalizeText(input.report_title ?? ""),
    forum_category: normalizeText(input.forum_category ?? ""),
    source_date: normalizeText(input.source_date ?? ""),
    captured_at: input.captured_at || utcTimestamp(),
    report_text: normalizeText(input.report_text ?? "", Number(input.max_text_chars || 0)),
    capture_status: String(input.capture_status ?? "captured"),
    notes: normalizeText(input.notes ?? ""),
  };

  validateCandidateRecord(record);
  return record;
}

export function validateCandidateRecord(record) {
  for (const field of RECORD_FIELD_ORDER) {
    if (!(field in record)) {
      throw new Error(`candidate record missing required field: ${field}`);
    }
  }
  for (const field of Object.keys(record)) {
    if (FORBIDDEN_RECORD_FIELDS.has(field)) {
      throw new Error(`candidate record contains forbidden evidence-decision field: ${field}`);
    }
  }
  if (!CAPTURE_STATUSES.has(record.capture_status)) {
    throw new Error(`unsupported capture_status: ${record.capture_status}`);
  }
  if (!record.product_id) {
    throw new Error("candidate record requires product_id");
  }
  if (!record.target_version) {
    throw new Error("candidate record requires target_version");
  }
  if (!record.source_url) {
    throw new Error("candidate record requires source_url");
  }
  return true;
}

export function serializeJsonlRecord(record) {
  validateCandidateRecord(record);
  const ordered = {};
  for (const field of RECORD_FIELD_ORDER) {
    ordered[field] = record[field] ?? "";
  }
  return JSON.stringify(ordered);
}

export function dedupeCandidateRecords(records, existingUrls = new Set()) {
  const seen = new Set([...existingUrls].map((url) => canonicalSourceUrl(url)));
  const unique = [];
  const duplicates = [];

  for (const record of records) {
    const key = canonicalSourceUrl(record.source_url);
    if (seen.has(key)) {
      duplicates.push(record);
      continue;
    }
    seen.add(key);
    unique.push({ ...record, source_url: key });
  }

  return { unique, duplicates, seen };
}

export async function loadExistingSourceUrls(outputDir) {
  const urls = new Set();
  let entries = [];
  try {
    entries = await fs.readdir(outputDir, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") {
      return urls;
    }
    throw error;
  }

  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith(".jsonl")) {
      continue;
    }
    const filePath = path.join(outputDir, entry.name);
    const content = await fs.readFile(filePath, "utf8");
    for (const line of content.split(/\r?\n/)) {
      if (!line.trim()) {
        continue;
      }
      try {
        const parsed = JSON.parse(line);
        if (parsed.source_url) {
          urls.add(canonicalSourceUrl(parsed.source_url));
        }
      } catch {
        // Ignore malformed historical lines here; tests cover current JSONL serialization.
      }
    }
  }
  return urls;
}

export function validateCaptureConfig(config) {
  const required = [
    "product_id",
    "target_version",
    "release_date",
    "watch_until",
    "query_variants",
    "allowed_source_domains",
  ];

  for (const field of required) {
    if (!(field in config)) {
      throw new Error(`config missing required field: ${field}`);
    }
  }
  if (!Array.isArray(config.query_variants) || config.query_variants.length === 0) {
    throw new Error("config query_variants must be a non-empty array");
  }
  if (!Array.isArray(config.allowed_source_domains) || config.allowed_source_domains.length === 0) {
    throw new Error("config allowed_source_domains must be a non-empty array");
  }
  for (const field of ["release_date", "watch_until"]) {
    if (Number.isNaN(Date.parse(config[field]))) {
      throw new Error(`config ${field} must be an ISO date string`);
    }
  }
  return true;
}

export function runtimeOptionsFromConfig(config, overrides = {}) {
  const capture = config.capture || {};
  return {
    output_root: overrides.outputRoot || capture.output_root || DEFAULT_CAPTURE_ROOT,
    browser_profile_dir: overrides.profileDir || capture.browser_profile_dir || `${DEFAULT_CAPTURE_ROOT}\\browser-profiles\\blackmagic-forum`,
    browser_channel: overrides.browserChannel || capture.browser_channel || "msedge",
    headless: Boolean(overrides.headless ?? capture.headless ?? false),
    max_pages_per_run: Number(overrides.maxPages ?? capture.max_pages_per_run ?? 20),
    max_results_per_query: Number(overrides.maxResultsPerQuery ?? capture.max_results_per_query ?? 6),
    delay_min_ms: Number(overrides.delayMinMs ?? capture.delay_min_ms ?? 5000),
    delay_max_ms: Number(overrides.delayMaxMs ?? capture.delay_max_ms ?? 12000),
    navigation_timeout_ms: Number(overrides.navigationTimeoutMs ?? capture.navigation_timeout_ms ?? 45000),
    max_text_chars: Number(overrides.maxTextChars ?? capture.max_text_chars ?? 12000),
    stop_on_block: Boolean(overrides.stopOnBlock ?? capture.stop_on_block ?? true),
  };
}
