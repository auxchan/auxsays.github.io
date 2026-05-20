#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";

import {
  DEFAULT_CAPTURE_ROOT,
  assertDedicatedBrowserProfile,
  blockOrVerificationReason,
  buildBlackmagicForumSearchUrl,
  canonicalSourceUrl,
  dedupeCandidateRecords,
  fileTimestamp,
  isAllowedSourceUrl,
  loadExistingSourceUrls,
  makeCandidateRecord,
  runtimeOptionsFromConfig,
  sanitizePathSegment,
  serializeJsonlRecord,
  utcTimestamp,
  validateCaptureConfig,
} from "./lib/capture-core.mjs";

const USAGE = `
AUXSAYS local browser capture

Usage:
  node tools/local-browser-capture/capture.mjs --config tools/local-browser-capture/configs/blackmagic-davinci.sample.json
  node tools/local-browser-capture/capture.mjs --config tools/local-browser-capture/configs/blackmagic-davinci.sample.json --dry-run

Options:
  --config <path>              Required JSON config file.
  --dry-run                    Validate config and show planned search URLs without launching a browser.
  --max-pages <number>         Override max pages per run.
  --browser-channel <name>     msedge, chrome, or chromium. Default: msedge.
  --headless                   Run browser headless. Default: visible browser window.
  --output-root <path>         Override C:\\AUXSAYS_CAPTURE.
  --profile-dir <path>         Override dedicated browser profile path.
  --continue-on-block          Continue after a block/verification page instead of stopping safely.
`;

async function main() {
  const { values } = parseArgs({
    options: {
      config: { type: "string", short: "c" },
      "dry-run": { type: "boolean", default: false },
      "max-pages": { type: "string" },
      "browser-channel": { type: "string" },
      headless: { type: "boolean", default: undefined },
      "output-root": { type: "string" },
      "profile-dir": { type: "string" },
      "continue-on-block": { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });

  if (values.help) {
    process.stdout.write(USAGE.trimStart());
    return 0;
  }

  if (!values.config) {
    process.stderr.write(`${USAGE}\nMissing required --config.\n`);
    return 2;
  }

  const configPath = path.resolve(String(values.config));
  const config = JSON.parse(await fs.readFile(configPath, "utf8"));
  validateCaptureConfig(config);

  if (!isAllowedSourceUrl("https://forum.blackmagicdesign.com/search.php", config.allowed_source_domains)) {
    throw new Error("config allowed_source_domains must allow forum.blackmagicdesign.com for this collector");
  }

  const runtime = runtimeOptionsFromConfig(config, {
    outputRoot: values["output-root"],
    profileDir: values["profile-dir"],
    browserChannel: values["browser-channel"],
    headless: values.headless,
    maxPages: values["max-pages"] ? Number(values["max-pages"]) : undefined,
    stopOnBlock: values["continue-on-block"] ? false : undefined,
  });

  const paths = resolveRunPaths(config.product_id, runtime.output_root, runtime.browser_profile_dir);
  assertDedicatedBrowserProfile(paths.profileDir);
  const searchUrls = config.query_variants.map((query) => buildBlackmagicForumSearchUrl(query));

  if (values["dry-run"]) {
    process.stdout.write(`${JSON.stringify({
      mode: "dry_run",
      config_path: configPath,
      product_id: config.product_id,
      target_version: String(config.target_version),
      release_date: config.release_date,
      watch_until: config.watch_until,
      allowed_source_domains: config.allowed_source_domains,
      search_urls: searchUrls,
      output_dir: paths.outputDir,
      log_dir: paths.logDir,
      screenshot_dir: paths.screenshotDir,
      browser_profile_dir: paths.profileDir,
      max_pages_per_run: runtime.max_pages_per_run,
      note: "Dry run does not launch a browser and does not write candidate JSONL.",
    }, null, 2)}\n`);
    return 0;
  }

  await ensureDirs(paths);

  const runId = fileTimestamp();
  const outputFile = path.join(paths.outputDir, `${sanitizePathSegment(config.product_id)}-${runId}.jsonl`);
  const logFile = path.join(paths.logDir, `${sanitizePathSegment(config.product_id)}-${runId}.log.jsonl`);
  const log = (event) => appendLog(logFile, event);

  await log({
    event: "run_started",
    product_id: config.product_id,
    target_version: String(config.target_version),
    output_file: outputFile,
    profile_dir: paths.profileDir,
    max_pages_per_run: runtime.max_pages_per_run,
  });

  const existingUrls = await loadExistingSourceUrls(paths.outputDir);
  let seenUrls = new Set(existingUrls);
  let browserContext;
  let page;
  let pagesVisited = 0;
  let recordsWritten = 0;
  let duplicatesSkipped = 0;
  let lastNavigationAt = 0;
  let stoppedReason = "";

  const appendCandidate = async (recordInput) => {
    const record = makeCandidateRecord({
      ...recordInput,
      product_id: config.product_id,
      target_version: String(config.target_version),
      max_text_chars: runtime.max_text_chars,
    });
    const deduped = dedupeCandidateRecords([record], seenUrls);
    if (deduped.duplicates.length) {
      duplicatesSkipped += 1;
      await log({ event: "candidate_skipped_duplicate", source_url: record.source_url });
      return false;
    }
    const uniqueRecord = deduped.unique[0];
    await fs.appendFile(outputFile, `${serializeJsonlRecord(uniqueRecord)}\n`, "utf8");
    seenUrls = deduped.seen;
    recordsWritten += 1;
    await log({ event: "candidate_written", capture_status: uniqueRecord.capture_status, source_url: uniqueRecord.source_url });
    return true;
  };

  const captureProblemScreenshot = async (label) => {
    const filename = `${fileTimestamp()}-${sanitizePathSegment(label)}.png`;
    const screenshotPath = path.join(paths.screenshotDir, filename);
    try {
      await page.screenshot({ path: screenshotPath, fullPage: true });
      await log({ event: "screenshot_saved", screenshot_path: screenshotPath });
      return screenshotPath;
    } catch (error) {
      await log({ event: "screenshot_failed", error: error.message });
      return "";
    }
  };

  const safeGoto = async (url, label) => {
    if (pagesVisited >= runtime.max_pages_per_run) {
      return { status: "limit_reached", reason: "max_pages_per_run_reached" };
    }
    await waitBetweenPages(runtime, lastNavigationAt);
    lastNavigationAt = Date.now();
    pagesVisited += 1;
    await log({ event: "page_opening", page_number: pagesVisited, source_url: url, label });
    try {
      const response = await page.goto(url, {
        waitUntil: "domcontentloaded",
        timeout: runtime.navigation_timeout_ms,
      });
      await page.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {});
      const pageState = await inspectPageForBlock(page);
      if (pageState.block_reason) {
        const screenshotPath = await captureProblemScreenshot(`blocked-${label}`);
        return {
          status: "blocked_or_verification",
          reason: pageState.block_reason,
          page_title: pageState.title,
          page_text: pageState.body_text,
          screenshot_path: screenshotPath,
          http_status: response ? response.status() : null,
        };
      }
      return {
        status: "ok",
        http_status: response ? response.status() : null,
      };
    } catch (error) {
      const screenshotPath = await captureProblemScreenshot(`error-${label}`);
      return {
        status: "failed",
        reason: error.message,
        screenshot_path: screenshotPath,
      };
    }
  };

  try {
    const playwright = await importPlaywright();
    browserContext = await launchDedicatedBrowser(playwright.chromium, runtime, paths.profileDir);
    page = await browserContext.newPage();
    page.setDefaultTimeout(runtime.navigation_timeout_ms);

    searchLoop:
    for (const queryVariant of config.query_variants) {
      const searchUrl = buildBlackmagicForumSearchUrl(queryVariant);
      const searchState = await safeGoto(searchUrl, `search-${queryVariant}`);
      if (searchState.status === "limit_reached") {
        stoppedReason = searchState.reason;
        break;
      }
      if (searchState.status === "blocked_or_verification") {
        await appendCandidate({
          query_variant_used: queryVariant,
          source_url: searchUrl,
          report_title: searchState.page_title || "Blackmagic forum search blocked or verification page",
          report_text: "",
          capture_status: "blocked_or_verification",
          notes: `Search page blocked or verification shown: ${searchState.reason}; screenshot=${searchState.screenshot_path}`,
        });
        stoppedReason = `blocked_or_verification:${searchState.reason}`;
        if (runtime.stop_on_block) {
          break;
        }
        continue;
      }
      if (searchState.status === "failed") {
        await appendCandidate({
          query_variant_used: queryVariant,
          source_url: searchUrl,
          report_title: "Blackmagic forum search failed",
          report_text: "",
          capture_status: "failed",
          notes: `Search navigation failed: ${searchState.reason}; screenshot=${searchState.screenshot_path}`,
        });
        continue;
      }

      const links = await extractThreadLinks(page, config.allowed_source_domains);
      await log({ event: "search_links_found", query_variant_used: queryVariant, link_count: links.length });

      for (const sourceUrl of links.slice(0, runtime.max_results_per_query)) {
        if (seenUrls.has(sourceUrl)) {
          duplicatesSkipped += 1;
          await log({ event: "thread_skipped_duplicate", source_url: sourceUrl });
          continue;
        }

        const threadState = await safeGoto(sourceUrl, "thread");
        if (threadState.status === "limit_reached") {
          stoppedReason = threadState.reason;
          break searchLoop;
        }
        if (threadState.status === "blocked_or_verification") {
          await appendCandidate({
            query_variant_used: queryVariant,
            source_url: sourceUrl,
            report_title: threadState.page_title || "Blackmagic forum thread blocked or verification page",
            report_text: "",
            capture_status: "blocked_or_verification",
            notes: `Thread page blocked or verification shown: ${threadState.reason}; screenshot=${threadState.screenshot_path}`,
          });
          stoppedReason = `blocked_or_verification:${threadState.reason}`;
          if (runtime.stop_on_block) {
            break searchLoop;
          }
          continue;
        }
        if (threadState.status === "failed") {
          await appendCandidate({
            query_variant_used: queryVariant,
            source_url: sourceUrl,
            report_title: "Blackmagic forum thread failed",
            report_text: "",
            capture_status: "failed",
            notes: `Thread navigation failed: ${threadState.reason}; screenshot=${threadState.screenshot_path}`,
          });
          continue;
        }

        const forumData = await extractForumData(page);
        await appendCandidate({
          query_variant_used: queryVariant,
          source_url: sourceUrl,
          report_title: forumData.report_title || sourceUrl,
          forum_category: forumData.forum_category || "",
          source_date: forumData.source_date || "",
          report_text: forumData.report_text || "",
          capture_status: forumData.report_text ? "captured" : "no_readable_text",
          notes: forumData.report_text
            ? "Captured visible public forum text only; validity is assessed downstream."
            : "Page loaded but no readable forum post text was extracted.",
        });
      }
    }
  } finally {
    if (browserContext) {
      await browserContext.close().catch(() => {});
    }
    await log({
      event: "run_finished",
      pages_visited: pagesVisited,
      records_written: recordsWritten,
      duplicates_skipped: duplicatesSkipped,
      stopped_reason: stoppedReason,
    });
  }

  process.stdout.write(`${JSON.stringify({
    mode: "capture",
    product_id: config.product_id,
    target_version: String(config.target_version),
    pages_visited: pagesVisited,
    records_written: recordsWritten,
    duplicates_skipped: duplicatesSkipped,
    stopped_reason: stoppedReason || null,
    output_file: recordsWritten > 0 ? outputFile : null,
    log_file: logFile,
    screenshot_dir: paths.screenshotDir,
  }, null, 2)}\n`);

  return 0;
}

function resolveRunPaths(productId, outputRoot = DEFAULT_CAPTURE_ROOT, profileDir) {
  const productSegment = sanitizePathSegment(productId);
  return {
    outputDir: path.join(outputRoot, "outbox", productSegment),
    logDir: path.join(outputRoot, "logs", productSegment),
    screenshotDir: path.join(outputRoot, "screenshots", productSegment),
    profileDir: profileDir || path.join(outputRoot, "browser-profiles", "blackmagic-forum"),
  };
}

async function ensureDirs(paths) {
  await Promise.all([
    fs.mkdir(paths.outputDir, { recursive: true }),
    fs.mkdir(paths.logDir, { recursive: true }),
    fs.mkdir(paths.screenshotDir, { recursive: true }),
    fs.mkdir(paths.profileDir, { recursive: true }),
  ]);
}

async function appendLog(logFile, event) {
  await fs.mkdir(path.dirname(logFile), { recursive: true });
  await fs.appendFile(logFile, `${JSON.stringify({ captured_at: utcTimestamp(), ...event })}\n`, "utf8");
}

async function importPlaywright() {
  try {
    return await import("playwright");
  } catch (error) {
    throw new Error(`Playwright is not installed. From auxsays/, run: npm install --save-dev playwright. Details: ${error.message}`);
  }
}

async function launchDedicatedBrowser(chromium, runtime, profileDir) {
  const launchOptions = {
    headless: runtime.headless,
    viewport: { width: 1366, height: 900 },
    locale: "en-US",
  };
  if (runtime.browser_channel && runtime.browser_channel !== "chromium") {
    launchOptions.channel = runtime.browser_channel;
  }
  return chromium.launchPersistentContext(profileDir, launchOptions);
}

async function waitBetweenPages(runtime, lastNavigationAt) {
  if (!lastNavigationAt) {
    return;
  }
  const minDelay = Math.max(0, runtime.delay_min_ms);
  const maxDelay = Math.max(minDelay, runtime.delay_max_ms);
  const delay = minDelay + Math.floor(Math.random() * (maxDelay - minDelay + 1));
  const elapsed = Date.now() - lastNavigationAt;
  if (elapsed < delay) {
    await new Promise((resolve) => setTimeout(resolve, delay - elapsed));
  }
}

async function inspectPageForBlock(page) {
  const title = await page.title().catch(() => "");
  const bodyText = await page.locator("body").innerText({ timeout: 3000 }).catch(() => "");
  const html = await page.content().catch(() => "");
  const blockReason = blockOrVerificationReason(`${title}\n${bodyText}\n${html.slice(0, 4000)}`);
  return {
    title,
    body_text: bodyText.slice(0, 1000),
    block_reason: blockReason,
  };
}

async function extractThreadLinks(page, allowedDomains) {
  const rawLinks = await page.$$eval("a[href*='viewtopic.php']", (anchors) => (
    anchors
      .map((anchor) => anchor.getAttribute("href"))
      .filter(Boolean)
      .map((href) => new URL(href, window.location.href).toString())
  )).catch(() => []);

  const links = [];
  const seen = new Set();
  for (const rawLink of rawLinks) {
    const sourceUrl = canonicalSourceUrl(rawLink);
    if (!isAllowedSourceUrl(sourceUrl, allowedDomains) || seen.has(sourceUrl)) {
      continue;
    }
    seen.add(sourceUrl);
    links.push(sourceUrl);
  }
  return links;
}

async function extractForumData(page) {
  return page.evaluate(() => {
    const clean = (value) => String(value || "")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t\f\v]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

    const firstText = (selectors) => {
      for (const selector of selectors) {
        const element = document.querySelector(selector);
        const text = clean(element?.textContent);
        if (text) {
          return text;
        }
      }
      return "";
    };

    const title = firstText([
      "h2.topic-title a",
      "h2.topic-title",
      ".topic-title a",
      "a.topictitle",
      "h1",
    ]) || clean(document.title).replace(/\s*-\s*Blackmagic Forum\s*$/i, "");

    const breadcrumbTexts = Array.from(document.querySelectorAll(".breadcrumbs a, .navlinks a, .crumb a"))
      .map((element) => clean(element.textContent))
      .filter(Boolean)
      .filter((text) => !/^(board index|blackmagic design|community forum)$/i.test(text));
    const forumCategory = Array.from(new Set(breadcrumbTexts)).join(" > ");

    const timeElement = document.querySelector("time[datetime]");
    let sourceDate = timeElement?.getAttribute("datetime") || "";
    if (!sourceDate) {
      const authorText = Array.from(document.querySelectorAll(".author, p.author, .postprofile"))
        .map((element) => clean(element.textContent))
        .find((text) => /\b(?:mon|tue|wed|thu|fri|sat|sun)\b|\b\d{4}\b/i.test(text));
      sourceDate = authorText || "";
    }

    const postSelectors = [
      ".postbody .content",
      ".post .content",
      "article .content",
    ];
    let postTexts = [];
    for (const selector of postSelectors) {
      postTexts = Array.from(document.querySelectorAll(selector))
        .map((element) => clean(element.innerText || element.textContent))
        .filter((text) => text.length > 0);
      if (postTexts.length > 0) {
        break;
      }
    }

    let reportText = postTexts.join("\n\n---\n\n");
    if (!reportText) {
      reportText = clean(document.querySelector("main")?.innerText || document.body?.innerText || "");
    }

    return {
      report_title: title,
      forum_category: forumCategory,
      source_date: sourceDate,
      report_text: reportText,
    };
  });
}

main().then((status) => {
  process.exitCode = status;
}).catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
