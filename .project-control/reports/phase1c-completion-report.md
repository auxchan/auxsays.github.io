# Phase 1C Completion Report — DaVinci Evidence Source Discovery + Access Proof of Concept

**Phase:** 1C  
**Status:** Complete  
**Date:** 2026-05-12  
**Constraint:** No production scraper. No consensus_evidence.yml rows. No GitHub Actions. No generated records modified. No OBS records. One allowed code change: `qa_patch_records.py` only.

---

## 1. Files Changed

| File | Type | Why changed |
|---|---|---|
| `auxsays/scripts/qa_patch_records.py` | Production script (allowed) | Task 1 — add `manual_watch` to `VALID_INTELLIGENCE_STAGES` |
| `.project-control/prototypes/blackmagic-source-access-probe.py` | Internal prototype | Task 2 — static fetch probe for official Blackmagic sources |
| `.project-control/prototypes/davinci-forum-source-probe.py` | Internal prototype | Task 4 — forum/Reddit source discovery probe |
| `.project-control/probe-output/phase1c/blackmagic-static-fetch-result.json` | Probe output | Task 2 deliverable |
| `.project-control/probe-output/phase1c/davinci-source-matrix.json` | Probe output | Task 4 deliverable |
| `.project-control/reports/phase1c-blackmagic-official-source-access.md` | Internal documentation | Task 6 deliverable |
| `.project-control/reports/phase1c-davinci-source-matrix.md` | Internal documentation | Task 4 deliverable |
| `.project-control/reports/phase1c-davinci-version-source-patterns.md` | Internal documentation | Task 5 deliverable |
| `.project-control/reports/phase1c-completion-report.md` | Internal documentation | Task 7 deliverable — this file |

---

## 2. Task 0 — Baseline Status

### git status at Phase 1C start

Working tree was clean. HEAD was `d57050c` ("Create a clean transfer package").

### Confirmations

| Check | Status |
|---|---|
| Phase 1B files exist | Confirmed — all 5 Phase 1B files present in repo |
| DaVinci Beta 1 shows 0 verified reports | Confirmed — `confirmed_patch_specific_report_count: 0`, `evidence_state: official_only` |
| DaVinci ingestion disabled | Confirmed — `enabled: false` at line 1403 of `patch_ingestion_sources.yml` |
| `consensus_evidence.yml` has no DaVinci rows | Confirmed — file structure is `{schema_version: 1, evidence: [...]}` dict; no `blackmagic-davinci` rows exist |
| Working tree clean before Phase 1C | Confirmed — `git status --short` returned empty |

### GitHub connection

This Replit project is NOT connected to GitHub (no `git push` has occurred and no `origin` remote points to the actual GitHub repository). The repo state exists only in the Replit environment. The user's local repo at `C:\GITHUB PROJECTS\auxsays.github.io` is the canonical GitHub state.

---

## 3. Task 1 — QA False-Positive Fix for `manual_watch`

**Change made:**

```diff
# auxsays/scripts/qa_patch_records.py, line 22
-VALID_INTELLIGENCE_STAGES = {"staged", "official_live", "pilot", "consensus_live", "archived"}
+VALID_INTELLIGENCE_STAGES = {"staged", "official_live", "pilot", "consensus_live", "archived", "manual_watch"}
```

This is the smallest possible change: one set literal extended by one string. No other logic was modified.

**QA result before fix:**
```
QA scanned 38 generated records and 14 priority products: 0 errors, 4 warnings
::warning ...unknown_intelligence_stage: Intelligence stage 'manual_watch' is not recognized.
::warning ...official_only_zero_reports_known_issues_yes: ...
::warning ...official_only_zero_reports_complaint_themes: ...
::warning ...official_only_zero_reports_recommendation_language: ...
```

**QA result after fix:**
```
QA scanned 38 generated records and 14 priority products: 0 errors, 3 warnings
::warning ...official_only_zero_reports_known_issues_yes: ...
::warning ...official_only_zero_reports_complaint_themes: ...
::warning ...official_only_zero_reports_recommendation_language: ...
```

The `unknown_intelligence_stage` warning is **eliminated**. 3 warnings remain — all are the known Phase 1B false positives (QA coherence checks for `complaint_themes` and `practical_recommendations` on `official_only` records). These are unchanged from Phase 1B and remain classified as QA model gaps, not record errors. See §8 for updated classification.

---

## 4. Task 2 — Blackmagic Official Source Access Proof

Full report: `.project-control/reports/phase1c-blackmagic-official-source-access.md`

### Summary of findings

**Playwright availability:** NOT installed in this Replit environment. Static (urllib) fetches only.

| Source | HTTP | Content | Version strings | Download links | Verdict |
|---|---|---|---|---|---|
| Press release `/media/release/20260414-01` | 200 | Generic SPA shell | **0** | 0 | **JS rendering wall — content not in static HTML** |
| Listing `/media` | 200 | Generic SPA shell | 0 | 0 | **JS rendering wall — release list not discoverable** |
| Support `/support/family/davinci-resolve-and-fusion` | 200 | Generic SPA shell | **0** | 0 | JS rendering wall |
| Download `/support/download/20260414-01` | 200 | Generic SPA shell | 0 | 0 | Also robots.txt-disallowed |
| `robots.txt` | 200 | Policy text | n/a | n/a | Key signals (see §4.1) |
| `sitemap.xml` | **404** | None | n/a | n/a | No sitemap exists |
| `sitemap_index.xml` | **404** | None | n/a | n/a | No sitemap index exists |

### 4.1 robots.txt Key Findings

```
user-agent: *
crawl-delay: 1
disallow: /support/download/
disallow: /api/print/to-pdf/*
disallow: /api/print/to-txt/*
```

Critical implications:
1. **`/support/download/` is explicitly disallowed** — this path is removed as a scrape target.
2. **`/api/` namespace exists** — the disallows reveal a `/api/` prefix. However, the only visible endpoints are document rendering utilities (`/api/print/to-pdf/*`), not release-note data APIs.
3. **`crawl-delay: 1`** — Blackmagic permits well-behaved crawlers with 1-second delay.
4. **`/media/` and `/support/family/` are not disallowed** — the policy does not block these paths; the inaccessibility is an SPA architecture issue, not a policy block.

### 4.2 Correction: No RSS Feeds Exist

The Phase 1C probe's `rss_links` field initially appeared to list many RSS feed URLs. These are **NOT RSS feeds**. They are `<link rel="alternate" hreflang="xx">` internationalization tags pointing to regional versions of the same page (`/ar/media/release/20260414-01`, `/de/media/release/20260414-01`, etc.). Blackmagic does **not** publish an RSS or Atom feed for press releases.

### 4.3 No API Endpoints Discoverable via Static Analysis

9 inline script blocks were found on the press release page. None contain:
- `fetch()` calls with hardcoded content API URLs
- `XMLHttpRequest` patterns
- `baseUrl` or `apiUrl` config objects

The only embedded script content is `dataLayer.push(arguments)` — a Google Tag Manager bootstrap. The actual content-fetching JS is in separately loaded bundle files not present in the initial HTML shell.

### 4.4 Key Novel Finding vs. Phase 1B

Phase 1B confirmed the JS rendering wall on the press release URL.

Phase 1C adds:
- **No sitemap exists** (both XML formats 404) — release URL discovery cannot be done via sitemap
- **No RSS feed exists** — no feed-based monitoring is possible
- **`/support/download/` is robots.txt-disallowed** — this path is ruled out
- **`/api/` namespace exists** but only document rendering endpoints are visible — the actual release content API is in dynamically loaded JS bundles
- **The listing page serves the same SPA shell** as the release-specific URL — even the release list is JS-rendered
- **Canonical tag is set correctly** on the press release URL — the server knows the URL is valid but deliberately serves the same shell regardless

---

## 5. Task 3 — Blackmagic Internal API / Network Endpoint Investigation

**Result: No internal API endpoints were discoverable via static analysis.**

The press release page's inline JavaScript contains only GTM bootstrap code. The actual content-fetching logic is in JS bundle files referenced by `<script src="...">` tags — these bundles are not analyzed in this probe (would require downloading and parsing them, which is out of scope for a static fetch probe).

**What a proper network trace would reveal:**

To discover the actual API endpoint used to load press release content, manual browser dev tools inspection is required:
1. Open the press release URL in a browser (Chrome/Firefox)
2. Open DevTools → Network → filter by XHR/Fetch
3. Navigate to the page and observe requests made after page load
4. Identify the request URL that returns the press release title, body, date, and version

This step cannot be performed from Replit without a running browser. It requires manual inspection by the operator.

**Guessed endpoint patterns (NOT confirmed — for investigation guidance only):**
- `https://www.blackmagicdesign.com/api/media/releases/20260414-01` (REST-style)
- `https://api.blackmagicdesign.com/content/media/release/20260414-01` (subdomain API)
- `https://www.blackmagicdesign.com/api/v2/news/release/20260414-01` (versioned REST)
- A GraphQL endpoint at `/graphql` or `/api/graphql`

None of these are confirmed. Manual inspection is required before any Phase 1D implementation.

**Robots.txt note:** No `/api/` paths are disallowed except print endpoints. If a content API endpoint is discovered, checking its robots.txt treatment should be a prerequisite before targeting it.

---

## 6. Task 4 — User-Report Source Discovery

Full report: `.project-control/reports/phase1c-davinci-source-matrix.md`

### Probe results

| Source | URL | HTTP | Access | Notes |
|---|---|---|---|---|
| Blackmagic forum (index) | `forum.blackmagicdesign.com/` | **403** | **Denied** | Hard block — zero body returned |
| Blackmagic forum (DaVinci section) | `...viewforum.php?f=21` | **403** | **Denied** | Hard block |
| Blackmagic forum (search) | `...search.php?keywords=...` | **403** | **Denied** | Hard block |
| Reddit r/davinciresolve (HTML) | `reddit.com/r/davinciresolve/` | **403** | **Denied** | Reddit blocks non-browser UA for HTML |
| Reddit JSON API (`new.json`) | `.../new.json?limit=5` | **403** | **Denied** | Old JSON API now requires OAuth2 |
| Reddit JSON search | `.../search.json?q=...` | **403** | **Denied** | Search also requires OAuth2 |
| Reddit RSS/Atom feed | `.../r/davinciresolve/.rss` | **200** | **Public** | 26 items; Atom XML; no version-specific posts in current feed |

### Blackmagic Forum — Hard Block Analysis

The Blackmagic forum (`forum.blackmagicdesign.com`) runs phpBB software. All three URLs probed return HTTP 403 with an empty body. This is a **server-level block on non-browser user-agents**, not a soft login redirect. phpBB can be configured to require authentication for all reads; alternatively, the server may have a WAF rule blocking non-browser user-agent strings.

**Implication:** This source is not accessible for automated evidence collection without either:
1. A browser session (Playwright + session cookie management)
2. A phpBB API key (if one exists)
3. The forum relaxing its access policy

Do not attempt to work around this block. Do not implement a Blackmagic forum scraper in Phase 1D.

### Reddit — Access Reality

Reddit's public API landscape changed significantly in 2023. The old `.json` API endpoints (which were previously accessible without authentication) now require OAuth2. The HTML interface blocks non-browser user-agents. The only access path available without credentials is the RSS/Atom feed.

**Reddit RSS findings:**
- 26 items in the feed; format is Atom XML, fully parseable
- Post titles in the current feed contain no version-specific DaVinci Resolve references (general questions dominate)
- Post bodies are truncated in RSS entries — full text requires individual post access
- The feed is not searchable or filterable by version

**Assessment:** Reddit RSS is useful as a volume signal (detecting elevated activity around a release) but is not sufficient for evidence-backed counting. Full evidence collection requires Reddit OAuth2 API access.

---

## 7. Task 5 — Version Normalization

Full report: `.project-control/reports/phase1c-davinci-version-source-patterns.md`

### Key findings

1. **Blackmagic press release URLs use date-based IDs, not version strings.** The URL `20260414-01` provides a date, not a version. Version information is only in the rendered page content.

2. **Blackmagic uses full product-name prefix in all formal version strings.** Press release titles are always `DaVinci Resolve {version}` — never bare version numbers.

3. **Community posts use shorthand.** Reddit, forum posts, and social media references use `DR21`, `Resolve 21`, `21 beta`, etc. — not the full Blackmagic form.

4. **Both current and relaxed regex patterns fail for all Blackmagic-format strings** because neither handles a text prefix before the version number.

5. **Required normalization approach:** Pre-processor that strips the product-name prefix (`DaVinci Resolve Studio`, `DaVinci Resolve`, `DaVinci`, `Resolve`) before regex matching, combined with the relaxed `version_pattern`.

6. **Version slug in existing AUXSAYS record includes product name** — the DaVinci Beta 1 record permalink is `/updates/blackmagic-design/blackmagic-davinci/davinci-resolve-21-public-beta-1/`. This contains the product name in the slug, inconsistent with other products (OBS uses bare version slugs). This should be corrected in Phase 1D.

---

## 8. Task 7 — Validation Results

### Commands run

```bash
python3 auxsays/scripts/validate_ingestion_sources.py
python3 auxsays/scripts/qa_patch_records.py
python3 auxsays/scripts/audit_consensus_evidence.py --json --strict
```

### Results

| Script | Exit code | Result |
|---|---|---|
| `validate_ingestion_sources.py` | **0** | Pass — "Source config validation passed: 46 entries checked." |
| `qa_patch_records.py` | **0** | Pass — "0 errors, 3 warnings" (down from 4 warnings in Phase 1B) |
| `audit_consensus_evidence.py --json --strict` | **0** | Pass — (previously was exit 1 in Phase 1B; audit passes in this run) |

### git status / diff at end of Phase 1C

```
===STATUS===
 M auxsays/scripts/qa_patch_records.py
?? .project-control/probe-output/phase1c/blackmagic-static-fetch-result.json
?? .project-control/probe-output/phase1c/davinci-source-matrix.json
?? .project-control/prototypes/blackmagic-source-access-probe.py
?? .project-control/prototypes/davinci-forum-source-probe.py
?? .project-control/reports/phase1c-blackmagic-official-source-access.md
?? .project-control/reports/phase1c-davinci-source-matrix.md
?? .project-control/reports/phase1c-davinci-version-source-patterns.md
?? .project-control/reports/phase1c-completion-report.md
===DIFF-STAT===
 auxsays/scripts/qa_patch_records.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
===DIFF-NAME-STATUS===
M  auxsays/scripts/qa_patch_records.py
```

**Only one tracked file was modified:** `auxsays/scripts/qa_patch_records.py`.  
**All other files are new internal `.project-control/` files** (untracked, not staged).  
**No generated records, OBS records, state files, or workflow files were modified.**

### Remaining 3 QA Warnings — Classification

| Warning code | Classification | Disposition |
|---|---|---|
| `official_only_zero_reports_known_issues_yes` | **QA model gap** | `known_issues_present: true` on a `manual_watch` record is intentional — the complaint_themes describe real beta risk areas that do not require counted reports. Phase 1D should add an `advisory_content_only: true` field or equivalent to suppress this. |
| `official_only_zero_reports_complaint_themes` | **QA model gap** | Same rationale. Complaint themes on an `official_only` record are advisory, not counted claims. |
| `official_only_zero_reports_recommendation_language` | **QA model gap** | "WAIT for production systems" is appropriate for a public beta regardless of report count. The QA check conflates absence of reports with absence of evidence-based advisory. |

All three warnings are false positives for the `manual_watch` / `official_only` + advisory content use case. None indicate actual record errors. Phase 1D should address the QA model rather than removing valid advisory content from the record.

---

## 9. Confirmations

| Check | Status |
|---|---|
| `consensus_evidence.yml` rows created | **None** |
| GitHub Actions workflows modified | **None** |
| Generated records modified | **None** |
| OBS records modified | **None** |
| DaVinci ingestion enabled | **No — still `enabled: false`** |
| Production scraper implemented | **None** |
| Forum/Reddit scraping implemented | **None** |
| Credentials or API keys added | **None** |
| GitHub push occurred | **None** |

---

## 10. Expert Judgment — Key Findings That Change Phase 1D Scope

### Finding 1: Blackmagic has NO RSS feed and NO sitemap

Previously Phase 1B noted the absence of sitemap as a question. Phase 1C confirms: both `/sitemap.xml` and `/sitemap_index.xml` are **404**. There is no sitemap. There is no RSS feed.

**Implication for Phase 1D:** Release discovery (finding out when a new DaVinci release exists) cannot be done via feed monitoring or sitemap polling. It requires either:
1. Polling the rendered release listing (headless browser, checking for new URLs)
2. Polling the press release URL by constructed date convention
3. Manual check (consistent with `manual_watch`)

This significantly increases the complexity of a Phase 1D Blackmagic adapter. Most AUXSAYS adapters use RSS or GitHub releases for change detection. Blackmagic requires a custom detection mechanism.

### Finding 2: Blackmagic forum is a hard 403 block, not a login redirect

Previously Phase 1B described the Blackmagic forum as a "login wall." Phase 1C probe confirms it is a **hard 403 with empty body** for all requests. This is more severe than a login redirect — it's a server-level block.

**Implication:** Do not plan any Phase 1D implementation that targets the Blackmagic forum. It is not accessible without circumventing the block, which is contrary to AUXSAYS principles.

### Finding 3: Reddit's old JSON API no longer works without OAuth2

The Phase 1B feasibility report listed Reddit as a candidate community source without confirming access. Phase 1C confirms all Reddit access paths except RSS return **403**. Reddit requires OAuth2 for programmatic access.

**Implication:** The Phase 1D Reddit collector decision is binary: either implement Reddit OAuth2 credential management (which requires a Reddit app registration and secret provisioning), or defer Reddit entirely. There is no middle path.

### Finding 4: Reddit RSS is accessible but structurally insufficient

Reddit RSS is accessible and structured. However, it delivers only the latest ~26 posts with truncated bodies. It cannot be version-searched, and post bodies cannot be confirmed from RSS alone. It is useful only as an activity signal, not as an evidence collection source.

**Implication:** Do not build a DaVinci evidence collector that depends on Reddit RSS for counted reports. It is not sufficient for `confirmed_patch_specific_reports_v1` classification.

### Finding 5: Version normalization requires a pre-processor, not just a relaxed regex

The ingestion config's `version_pattern` cannot handle Blackmagic's version string format without a pre-processing step that strips the product name prefix. The relaxed pattern alone is insufficient.

**Implication:** The Blackmagic adapter cannot share the generic version-matching logic used by other adapters. It needs a Blackmagic-specific pre-processor.

---

## 11. Recommended Phase 1D

In priority order:

### P1 (Manual — prerequisite) — Browser dev tools network trace on Blackmagic press release page

**Before any code is written for Phase 1D**, the operator must manually:
1. Open `https://www.blackmagicdesign.com/media/release/20260414-01` in a browser
2. Open DevTools → Network tab
3. Filter for XHR/Fetch requests
4. Identify the API endpoint that returns the press release content
5. Test whether that endpoint is unauthenticated (accessible without cookies)
6. Document: URL, method, response format, whether content includes version/title/body/date

If the endpoint is unauthenticated and stable, Option B (below) is the preferred Phase 1D path.
If the endpoint requires authentication, fall back to Option A (headless rendering).

### P2A (Code — if P1 finds unauthenticated API) — Blackmagic content API adapter

Build a lightweight `blackmagic_api` adapter that:
1. Constructs the API URL from the release date ID
2. Fetches the JSON/XML/HTML response
3. Extracts title, body, date, version string
4. Applies the DaVinci version pre-processor (strip product name prefix)
5. Applies the relaxed `version_pattern`
6. Generates the AUXSAYS record with `evidence_state: official_only`, `consensus_collection_status: deferred_official_only`

**This is the cleanest, lowest-risk path if the endpoint is confirmed.**

### P2B (Code — if P1 finds no unauthenticated API) — Playwright headless adapter

Add Playwright to the toolchain and build a `blackmagic_playwright` adapter that:
1. Launches a headless Chromium instance
2. Navigates to the press release URL
3. Waits for DOM content load
4. Extracts the rendered title, body, date, and version
5. Uses the same version pre-processor as P2A
6. Closes the browser and returns the extracted fields

**Implementation prerequisites:**
- Decision: whether to add `playwright` + browser binaries to GitHub Actions runner
- Test: confirm the press release content is accessible after JS render (not behind auth)
- Identify: the CSS selector for the rendered press release body
- Implement: polite request handling (crawl-delay: 1, single request per run)

**Risk note:** Adding Playwright to CI/CD increases build time and storage by ~150MB for browser binaries. This must be an explicit decision, not a side effect of building the adapter.

### P3 (Code — Reddit evidence, conditional) — Reddit OAuth2 collector

If Reddit is chosen as an evidence source:
1. Register a Reddit app at `https://www.reddit.com/prefs/apps`
2. Provision client ID and secret as GitHub Actions secrets
3. Build a `reddit_api` evidence collector that:
   - Uses OAuth2 app credentials (non-user, script type)
   - Searches `r/davinciresolve` for posts mentioning a specific version
   - Filters posts by `confirmed_patch_specific_reports_v1` classification criteria
   - Writes evidence rows to `consensus_evidence.yml`
4. Gate this on Phase 1D official source adapter being ready first

**This is a significant scope commitment.** Do not implement until the official source adapter (P2A or P2B) is complete and tested.

### P4 (Code — VideoHelp/Creative COW probe) — Alternative static community sources

Before committing to Reddit OAuth2, probe VideoHelp forum (`videohelp.com/forum`) and Creative COW (`creativecow.net`) for DaVinci Resolve evidence:
1. Static fetch the DaVinci Resolve forum section
2. Confirm posts are publicly readable
3. Confirm version-specific search is available
4. If yes: these are lower-friction alternatives to Reddit OAuth2

### P5 (Schema) — QA model update for `manual_watch` + advisory content

Update `qa_patch_records.py` to allow `complaint_themes` and `practical_recommendations` on `official_only` records where `intelligence_stage: manual_watch`. This eliminates the remaining 3 false-positive warnings without removing valid advisory content from records.

Options:
1. Check `stage == 'manual_watch'` and suppress the three warnings when true
2. Add a new field `advisory_content_only: true` to the record schema and check it in QA

Option 1 is simpler and requires no record changes.

### P6 (Schema) — Fix version slug convention in DaVinci records

The existing DaVinci Beta 1 permalink includes the product name:
`/updates/blackmagic-design/blackmagic-davinci/davinci-resolve-21-public-beta-1/`

Other products use bare version slugs:
`/updates/obs-project/obs-studio/32.1.2/`

Correct the DaVinci permalink pattern in `patch_ingestion_sources.yml` to use bare version slugs, and update the existing record's permalink accordingly. This is a breaking URL change; redirect rules or `redirect_from` front matter should be added.

---

## 12. Generated Patch Report Boundary

1. Phase 1C created **only internal project-control reports, probe outputs, and prototype-only scripts.** All new files are under `.project-control/` or `auxsays/scripts/`.
2. **No public Patch Feed generated records were created or modified.** The only tracked file change is `auxsays/scripts/qa_patch_records.py` (a validation script, not a generated record).
3. **No public DaVinci update reports were manually authored.** No new files were added under `auxsays/updates/generated/`.
4. **No report counts were manually authored.** No `update_report_count`, `confirmed_patch_specific_report_count`, or equivalent field was written to any generated record.
5. **No `consensus_evidence.yml` rows were created or modified.** The file is unchanged from the start of Phase 1C.
6. **Future public DaVinci Patch Feed reports must be generated programmatically** by AUXSAYS scripts from structured evidence sources. They must not be manually written by an AI agent. Manual authoring of report counts, evidence states, or consensus summaries without a matching `consensus_evidence.yml` row is the root cause of the Phase 1B credibility problem this project is correcting. That error must not recur.

---

## 13. Codex Baseline Review Alignment

1. **`manual_watch` was correctly treated as an `intelligence_stage` / operational-editorial stage**, not as an evidence state. It describes the operational posture of a source (human monitoring, no automated collection active), not the quality or quantity of evidence collected.
2. **`manual_watch` must not be treated as an `evidence_state`.** Evidence states (`official_only`, `pilot_sample`, `consensus_live`, `insufficient_data`) describe the type and volume of evidence backing a record. `manual_watch` belongs in `intelligence_stage`, which describes the operational pipeline state for that product.
3. **Evidence states must remain evidence-focused.** The allowed evidence states per AGENTS.md are `official_only`, `pilot_sample`, `consensus_live`, and `insufficient_data` (with `static_sample` retained only for backward compatibility). No new evidence state was introduced in Phase 1C.
4. **The `qa_patch_records.py` change is narrow and correctly scoped.** `manual_watch` was added only to `VALID_INTELLIGENCE_STAGES` (line 25). No change was made to `VALID_EVIDENCE_STATES`, QA error logic, source coverage checks, layout copy checks, or any other validation path. No unrelated validation was weakened.
5. **Unrelated QA validation is unchanged.** All existing error and warning checks outside the `unknown_intelligence_stage` path are identical before and after the fix. The change is a one-character-difference set literal extension with no side effects.

---

## 14. Evidence Model Risks to Carry Into Phase 1D

These risks are documented for forward awareness. No production files are changed here.

1. **Report counts can exist in generated records without matching `consensus_evidence.yml` rows** unless validation explicitly prevents drift. The Phase 1B `update_report_count: 7` problem was caused exactly by this gap. The current QA script (`qa_patch_records.py`) does not cross-check generated record counts against `consensus_evidence.yml` row counts. This is the single highest-priority evidence model risk.

2. **`update_report_count` and `confirmed_patch_specific_report_count` can drift independently.** Both fields exist in generated records and can diverge from each other and from the actual `consensus_evidence.yml` row count if written manually or inconsistently. Phase 1D should enforce that these fields are always derived from `consensus_evidence.yml` row aggregation, never manually set.

3. **`evidence_state`, `evidence_state_label`, `consensus_collection_status`, and `intelligence_stage` can drift out of alignment.** A record could have `evidence_state: pilot_sample` with `confirmed_patch_specific_report_count: 0` and zero `consensus_evidence.yml` rows — exactly the Phase 1B state for DaVinci Beta 1. Validation should check cross-field consistency for these four fields together.

4. **`legacy_manual_report_count` is not yet a normalized schema field across records.** It was added to the DaVinci Beta 1 record in Phase 1B as a preservation measure, but it is not defined in the ingestion config's `front_matter_fields` list, is not validated by QA, and does not appear in any other record. Before Phase 1D, decide whether this field becomes a formal schema element or is removed and replaced with a `record_note` only.

5. **`known_issues_present`, `complaint_themes`, `practical_recommendations`, and recommendation language can make a zero-report `official_only`/`manual_watch` record appear evidence-backed** if layout rendering or public labels are not carefully guarded. The current layout uses `official_only_zero_reports` to override verdict rendering, but this protection exists at the layout level only — if a future layout change removes this guard, the advisory content would render misleadingly.

6. **Homepage inclusion may promote zero-report records if `known_issues_present: true`.** If the homepage filter includes `known_issues_present: true` as a display criterion, a `manual_watch` record with advisory complaint themes could be surfaced in a way that implies active evidence collection. The current state of the DaVinci Beta 1 record and its homepage behavior should be confirmed after the Phase 1B correction (Phase 1D pre-work).

7. **Blackmagic version matching is ambiguous across multiple format variants:** `DaVinci Resolve 21`, `DaVinci Resolve 21 Public Beta 1`, `21.0`, `21.0.0`, `DaVinci Resolve Studio 21`, `Resolve 21`, `21b1`, `21 Beta 1`. Without a pre-processor and a normalized canonical version target, the same release could generate duplicate records, fail to match existing records, or be silently skipped. Version matching must be validated end-to-end before any DaVinci adapter is enabled.

8. **Reddit and forum evidence will be noisy unless exact-version matching is enforced at the evidence classification step.** General DaVinci questions (color grading, export settings, hardware questions) far outnumber patch-specific bug reports. Without strict `patch_version_matched: true` classification enforced at the `consensus_evidence.yml` write step, general community noise will inflate confirmed report counts. The `confirmed_patch_specific_reports_v1` policy requires this classification; it must be enforced by code, not assumed.

---

## 15. Recommended Phase 1D Decision Path

This replaces the P1–P6 ordering in §11 with a branching decision structure aligned to actual probe findings.

### Branch A — If an unauthenticated Blackmagic internal API endpoint is found (Manual prerequisite first)

> Manual step required first: browser dev tools network trace on `https://www.blackmagicdesign.com/media/release/20260414-01`. Identify the XHR/Fetch request that returns the press release content after JS render.

- **Prefer the API endpoint over Playwright** if it is: publicly accessible without authentication, returns structured content (JSON or clean HTML), is reachable without session cookies, and is stable enough to be schema-checkable.
- Build a `blackmagic_api` adapter targeting the discovered endpoint.
- Apply the version pre-processor (strip `DaVinci Resolve [Studio] ` prefix) before regex matching.
- Generate records with `evidence_state: official_only`, `consensus_collection_status: deferred_official_only`.
- Check robots.txt treatment of the discovered endpoint before targeting it in production.

### Branch B — If Playwright-rendered pages work but no unauthenticated API is found

- **Treat Playwright as a dependency decision, not an automatic adapter choice.** Adding browser binaries to GitHub Actions adds ~150MB to CI storage and increases build time. This requires an explicit infrastructure decision before any code is written.
- Do not enable DaVinci ingestion until: (a) Playwright renders confirmed release content, (b) a stable CSS selector is identified, (c) CI/CD is updated and tested with the new dependency.
- Keep `enabled: false` and `intelligence_stage: manual_watch` until CI stability is proven over multiple release cycles.

### Branch C — If Blackmagic support/download pages are the best available official source

- Treat them as **download/version metadata sources only**, not release-note body sources.
- Robots.txt disallows `/support/download/` for automated crawlers. Do not target this path.
- Support family pages (`/support/family/davinci-resolve-and-fusion`) are not disallowed but return the same SPA shell — no version or download data is accessible via static fetch.

### Branch D — If Blackmagic forum remains hard-blocked (current state)

- **Do not target the forum.** The current hard 403 applies to all bot user-agents.
- Do not implement workarounds (session simulation, browser fingerprinting, credential injection).
- Do not revisit unless Blackmagic publishes a compliant public access method (e.g., a public forum API or guest-read relaxation).

### Branch E — If Reddit remains OAuth2-gated (current state)

- **Make an explicit binary decision:** implement Reddit OAuth2 credential management (Reddit app registration, CI secrets provisioning, OAuth2 token refresh) or defer Reddit entirely.
- Do not treat Reddit RSS as a substitute for counted evidence — it is an activity signal only (latest N posts, truncated bodies, not version-searchable).
- If Reddit OAuth2 is chosen, gate the evidence collector on the official source adapter being complete first. A community evidence collector is meaningless without a paired, reliably captured official release record to version-match against.

### Branch F — If no reliable automated sources are available

- **Keep DaVinci `manual_watch` / `official_only` indefinitely.** This is the honest and correct state.
- Do not implement an automated count mechanism that will produce 0 counts and claim it is evidence-backed.
- Improve manual-review documentation and labeling rather than creating automated infrastructure that cannot function.
- Revisit source access on each major DaVinci release (manually check whether Blackmagic has changed their site architecture or access policy).

### In all branches — prerequisite before any Phase 1D adapter work

Probe VideoHelp forum (`videohelp.com/forum`) and Creative COW (`creativecow.net`) for static-fetch accessibility. These are potential lower-friction community evidence sources that were not probed in Phase 1C. If either allows static read access to version-specific DaVinci threads, they may be preferable to Reddit OAuth2 for initial evidence collection.
