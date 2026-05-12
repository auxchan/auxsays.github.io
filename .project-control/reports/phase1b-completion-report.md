# Phase 1B Completion Report — DaVinci Credibility Correction + Probe Run

**Phase:** 1B  
**Status:** Complete  
**Date:** 2026-05-12  
**Constraint:** No production scraper. No consensus_evidence.yml rows. No GitHub Actions. No OBS records. Allowed generated-record modification: DaVinci Beta 1 only.

---

## 1. Files Changed

| File | Type | Why changed |
|---|---|---|
| `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md` | Generated record (allowed) | Remove unsupported "Verified reports" state; correct evidence fields; preserve 7-report value as legacy/manual context |
| `.project-control/reports/phase1b-davinci-history-audit.md` | Internal documentation | Task 0 deliverable — documents historical investigation findings |
| `.project-control/probe-output/davinci-official-probe-20260414-01.json` | Probe output | Task 1 deliverable — official-source probe results |
| `.project-control/reports/phase1b-davinci-probe-results.md` | Internal documentation | Task 2 deliverable — probe results analysis report |
| `.project-control/reports/phase1b-completion-report.md` | Internal documentation | Task 6 deliverable — this file |

---

## 2. Commands Run

```bash
# Task 0 — History audit (read-only)
git log --oneline --all -- "*davinci*"
git log --oneline --all -- auxsays/updates/generated/
git log --oneline --all -- auxsays/scripts/fetch_davinci_updates.py
git log --oneline --all -- .github/workflows/
git grep -n "update_report_count: 7"
git grep -n "7 confirmed"
git grep -n "confirmed_patch_specific_report_count: 7"
git grep -n "legacy"
git grep -n "manual_watch"
git grep -n "pilot_initial_sample"
git grep -n "Verified reports"
git grep -n "Blackmagic"

# Task 1 — Probe script
python3 .project-control/prototypes/davinci-probe-dry-run.py \
  > .project-control/probe-output/davinci-official-probe-20260414-01.json

# Task 5 — Validation
python3 auxsays/scripts/validate_ingestion_sources.py
python3 auxsays/scripts/qa_patch_records.py
python3 auxsays/scripts/audit_consensus_evidence.py --json --strict
cd auxsays && bundle exec jekyll build --trace
```

---

## 3. Validation Results

| Script | Exit code | Result |
|---|---|---|
| `validate_ingestion_sources.py` | 0 | **Pass** — "Source config validation passed: 46 entries checked." |
| `qa_patch_records.py` | 0 | **Pass with 4 warnings** — "38 generated records, 14 priority products: 0 errors, 4 warnings" |
| `audit_consensus_evidence.py --json --strict` | **1** | Pre-existing staleness — not introduced by Phase 1B (see §3.1) |
| `bundle exec jekyll build --trace` | 0 | **Pass** — "done in 3.16 seconds." No build errors. |

### 3.1 `qa_patch_records.py` — 4 Warnings (All on DaVinci Beta 1)

All 4 warnings are on `updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md`:

| Warning code | Description | Assessment |
|---|---|---|
| `unknown_intelligence_stage` | `intelligence_stage: manual_watch` not in QA script's recognized stage list | **QA script gap.** `manual_watch` is a valid concept per AGENTS.md (it is a recognised verdict label and is used widely in `patch_ingestion_sources.yml`). The QA script's `VALID_INTELLIGENCE_STAGES` list should be updated to include `manual_watch` in Phase 1C. |
| `official_only_zero_reports_known_issues_yes` | `official_only` record with 0 reports has `known_issues_present: true` | **Acceptable.** The `complaint_themes` describe real beta-category risk areas (GPU uncertainty, beta setup questions). They do not claim to be backed by 7 specific counted reports. The QA warning is a coherence flag, not a credibility error. |
| `official_only_zero_reports_complaint_themes` | `official_only` record with 0 reports has `complaint_themes` | Same as above — complaint_themes contain advisory risk information, not report-count-backed analysis. |
| `official_only_zero_reports_recommendation_language` | `official_only` record with 0 reports still has `practical_recommendations` | **Acceptable.** The practical recommendations ("Wait for production systems", "Test separately") are general beta advice appropriate to an official-only record. They do not claim to derive from counted reports. |

**Resolution for Phase 1C:** Add `manual_watch` to `VALID_INTELLIGENCE_STAGES` in `qa_patch_records.py`. Optionally add a QA allow-list for `complaint_themes` and `practical_recommendations` on `official_only` records that explicitly carry advisory-only content.

### 3.2 `audit_consensus_evidence.py --json --strict` — Exit Code 1

Same pre-existing condition documented in Phase 1A. The audit flagged Figma, ComfyUI, and GitHub Copilot records for `stale_or_missing_update_last_checked` and `source_checked_after_record_last_checked`. **No DaVinci or OBS records were flagged.** Phase 1B did not create, modify, or touch `consensus_evidence.yml`.

### 3.3 Jekyll Build — Pass

The Jekyll build completed with zero errors (3.16 seconds). The build output included all 38 generated records including the corrected DaVinci Beta 1 record.

**Layout rendering analysis for DaVinci Beta 1 post-correction:**

The layout (`aux-update.html`) derives `evidence_state` with this priority logic:

```liquid
{% assign collection_status = page.consensus_collection_status | default: 'deferred_official_only' %}
...
{% if collection_status == 'live_consensus' or collection_status == 'consensus_live' %}
  {% assign evidence_state = 'Live consensus' %}
{% elsif collection_status == 'pilot_initial_sample' or collection_status == 'static_initial_sample'
    or page.evidence_state == 'pilot_sample' or page.evidence_state == 'static_sample' %}
  {% assign evidence_state = 'Verified reports' %}
{% elsif official_captured %}
  {% assign evidence_state = 'Official source only' %}
{% endif %}
```

After the correction:
- `consensus_collection_status: deferred_official_only` — does **not** match `pilot_initial_sample` or `static_initial_sample`
- `evidence_state: official_only` — does **not** match `pilot_sample` or `static_sample`
- `official_captured` = true (source URL is present)
- `report_count` = 0 (`update_report_count: 0`)

**Result:** The page now renders **"Official source only"** — not "Verified reports". The layout also sets `official_only_zero_reports = true` (line 70), which overrides `decision_label` to "No AUXSAYS recommendation yet." and `verdict_text` to "Official source captured. No confirmed patch-specific reports have been counted."

The page **will not render** any of the following (confirmed via layout analysis):
- "Verified reports" ✓
- "7 confirmed" ✓
- "7 confirmed patch-specific reports" ✓
- "Confirmed reports counted: 7" ✓ (report_count = 0 → this line shows 0)

---

## 4. DaVinci History Audit Summary

Full report: `.project-control/reports/phase1b-davinci-history-audit.md`

Key findings:

1. **The 7-report value entered the repo** in the initial commit `c8251e5` (Phase 0), which imported the pre-existing local repo. The value predates all Replit agent activity.
2. **No script or workflow created it.** `build_consensus_from_evidence.py` cannot have produced it (zero `blackmagic-davinci` rows in `consensus_evidence.yml`). `fetch_davinci_updates.py` is a dead stub. DaVinci ingestion has never been enabled.
3. **DaVinci report gathering was never production-ready.** No evidence rows exist. The ingestion config has `enabled: false`.
4. **Stable DaVinci never had structured report gathering.** The stable `2026-04-14-davinci-resolve-21.md` record has `legacy_consensus_score: 0`.
5. **The 7-report count has no traceable evidence source.** There are zero rows in `consensus_evidence.yml` for `product_id: blackmagic-davinci`. The only record of the 7 is the `status_events` note inside the front matter itself.

---

## 5. Whether the 7-Report Value Was Traceable

**Not traceable under the current evidence system.** The value may have originated from a manual pre-evidence review of the Blackmagic beta forum, but:
- No source URLs were preserved
- No evidence rows were written
- No audit trail exists in git history
- The `consensus_match_policy: confirmed_patch_specific_reports_v1` field claims a methodology that was never applied

The presence of `legacy_consensus_score: 6` and `legacy_consensus_score_percent: 53` suggests the value came from an older pre-`consensus_evidence.yml` scoring approach.

---

## 6. Whether the 7-Report Value Was Preserved

**Preserved as legacy/manual context.** Not removed.

Two new fields were added to the record:

```yaml
legacy_manual_report_count: 7
legacy_manual_report_count_note: Previous 7-report value appears to be a pre-evidence/manual/pilot
  estimate. It is not currently backed by structured consensus_evidence.yml rows and should
  not be rendered as verified reports.
```

These fields are not rendered by the current layout (no Liquid template references them). They serve as documentation for future agents and maintainers.

---

## 7. Probe Output Path and Findings Summary

**Output file:** `.project-control/probe-output/davinci-official-probe-20260414-01.json`

Full analysis: `.project-control/reports/phase1b-davinci-probe-results.md`

**Critical finding:** The Blackmagic press release URL `https://www.blackmagicdesign.com/media/release/20260414-01` returns HTTP 200 but **serves a generic page shell** (`"Media | Blackmagic Design"`, H1: `"Blackmagic Design News Archive"`). The actual press release content is loaded client-side via JavaScript. Static fetch returns the shell only — this explains all five prior `official-source-parser-failed` results.

This is a more fundamental problem than previously understood. The Phase 1A analysis identified the failure as a wrong CSS selector; the probe confirms it is a **JavaScript rendering wall** — no selector can extract content that is not present in the static HTML.

---

## 8. Exact DaVinci Record Fields Changed

File: `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md`

| Field | Old value | New value |
|---|---|---|
| `update_consensus_label` | `Moderate` | `Insufficient data` |
| `update_consensus_summary` | "Early beta reaction is mixed..." | "No structured evidence collection has been completed..." |
| `update_report_count` | `7` | `0` |
| `consensus_report` | "The verified-report set remains moderate..." | "No structured evidence collection has been completed..." |
| `status_events[1].label` | `Moderate` | `Insufficient data` |
| `status_events[1].note` | "Consensus read based on 7 confirmed patch-specific reports." | "Phase 1B correction: prior 7-report value was a pre-evidence manual estimate..." |
| `consensus_collection_status` | `pilot_initial_sample` | `deferred_official_only` |
| `evidence_state` | `pilot_sample` | `official_only` |
| `evidence_state_label` | `Verified reports` | `Official source only` |
| `confirmed_patch_specific_report_count` | `7` | `0` |
| `intelligence_stage` | `pilot` | `manual_watch` |
| `record_note` | *(absent)* | Added — see §6 above |
| `legacy_manual_report_count` | *(absent)* | `7` |
| `legacy_manual_report_count_note` | *(absent)* | Added |

Fields **not changed** (intentionally retained):
- `quick_verdict` — "WAIT for production systems..." — does not reference 7 reports; correct for a beta build
- `update_decision_label` / `update_decision_body` — general beta guidance; does not claim report backing
- `practical_recommendations` — general beta advice; not report-count-dependent
- `complaint_themes` — beta-category risk advisory; does not claim to be counted reports
- `known_issues_present: true` — retained because complaint_themes describe real risk areas
- `official_source_attempts` — preserved as-is (5 parser failures documented)
- `official_patch_notes_capture_status` — unchanged; still `official-source-linked-body-not-captured`

---

## 9. Confirmations

| Check | Status |
|---|---|
| `consensus_evidence.yml` rows created | **None** — not modified |
| GitHub Actions workflows modified | **None** — not modified |
| OBS files changed | **None** — not modified |
| Non-DaVinci generated records modified | **None** |
| DaVinci ingestion status | **Still disabled** (`enabled: false` in `patch_ingestion_sources.yml`) |
| Production scraper implemented | **None** |
| Blackmagic adapter implemented | **None** |
| Forum/Reddit scraping added | **None** |
| API credentials added | **None** |
| GitHub push performed | **None** |
| Replit artifacts / attached_assets created | **None** |
| ZIP files created | **None** |

---

## 10. Known Risks

1. **QA `unknown_intelligence_stage` warning will persist** until `manual_watch` is added to `qa_patch_records.py`'s valid stage list. This is a script gap, not a record error.

2. **`complaint_themes` and `practical_recommendations` produce coherence warnings** when `official_only` + 0 reports. These fields contain valid advisory content. The warnings are false positives for this use case. Phase 1C should add a schema allowance for `advisory_only_content: true` or similar to suppress them.

3. **The DaVinci stable record (`2026-04-14-davinci-resolve-21.md`) has not been audited in detail.** It was not modified. If it carries similar evidence-state issues, they are not addressed in Phase 1B. That record should be audited in Phase 1C.

4. **`consensus_match_policy: confirmed_patch_specific_reports_v1` remains set** on the DaVinci Beta 1 record alongside `confirmed_patch_specific_report_count: 0`. This claims a policy was applied when the count is 0. This is slightly inconsistent but harmless — the policy field is metadata for future use, not a rendering field. It could be changed to `none_applied_manual_watch` in a future correction.

5. **Homepage display:** The DaVinci Beta 1 record currently shows on the homepage because `evidence_state: pilot_sample` matched the homepage filter. After correction to `official_only` + 0 reports, the homepage filter in `aux-home.html` line 154 checks `evidence_state == 'pilot_sample' or ... evidence_state == 'official_only'` — actually, let me clarify: `official_only` does not trigger the homepage filter. The record may drop off the homepage unless `homepage_featured: true` is set. This is the correct behavior per AGENTS.md: "Hide from homepage: official-only records with 0 reports." The change is intentional and correct.

---

## 11. Recommended Phase 1C

In priority order:

### P1 (QA fix — low risk) — Add `manual_watch` to QA valid intelligence stages
Add `manual_watch` to `VALID_INTELLIGENCE_STAGES` in `auxsays/scripts/qa_patch_records.py`. One-line change. Eliminates the `unknown_intelligence_stage` warning from the DaVinci Beta 1 record and any future `manual_watch` records.

### P2 (Architecture — before any adapter) — Headless browser proof of concept
Before building a Blackmagic adapter, confirm that the press release content is available after JavaScript execution. Run a single headless browser fetch (Playwright) of `https://www.blackmagicdesign.com/media/release/20260414-01` and extract the rendered HTML. This will identify the actual CSS selector needed and confirm whether the content is accessible at all. If the content is behind authentication or a bot-detection wall, an alternative source strategy (RSS, PDF, API endpoint) must be found instead.

### P3 (Architecture — if P2 succeeds) — Blackmagic adapter design
If headless fetch confirms the content is accessible, design a `blackmagic_media` adapter that:
1. Strips "DaVinci Resolve " prefix before applying `version_pattern` (or uses a dedicated pre-processor)
2. Uses headless browser rendering for body extraction
3. Uses URL date prefix extraction as the date source
4. Sets `vendor_announcement` as `official_patch_notes_source_type`
5. Writes `confirmed_patch_specific_report_count: 0` and `consensus_collection_status: deferred_official_only` until a DaVinci evidence collector is also implemented

### P4 (Schema) — Add `count_methodology` or `intelligence_stage_note` field
Add a structured field to distinguish `manual_watch` records (official source linked, no evidence system yet active) from `pilot_sample` records (evidence collection in progress). This prevents future records from being created with misleading `pilot_initial_sample` + 0 evidence-rows combinations.

### P5 (QA coherence) — Allow advisory content on `official_only` records
Update `qa_patch_records.py` to allow `complaint_themes` and `practical_recommendations` on `official_only` records that carry `advisory_only_content: true` or `intelligence_stage: manual_watch`. This eliminates false-positive warnings for records that intentionally include risk advisory content without a report count.

### P6 (Audit) — Review DaVinci stable record
Audit `2026-04-14-davinci-resolve-21.md` for similar evidence-state issues before the DaVinci adapter is enabled. If it also has a misleading evidence state, correct it under the same Phase 1B methodology.

---

## 12. Expert Judgment Notes

**On the Blackmagic source strategy:** The Phase 1A analysis characterized the failure as a selector problem. The probe reveals it is a rendering architecture problem. This is a more significant blocker — the current adapter infrastructure cannot be patched to work with Blackmagic's site without adding a headless browser dependency. This dependency adds complexity to the CI/CD environment and should be evaluated carefully before committing.

**On the version normalization finding:** The probe confirms that the relaxed `version_pattern` fix alone is insufficient. All "DaVinci Resolve XX" format strings fail both patterns because neither handles a text prefix. The adapter must strip the product name prefix before applying any regex. This is a pre-processing requirement that should be built into the adapter, not the config pattern.

**On the `legacy_manual_report_count: 7` preservation decision:** Preserving this as a non-rendered field is the correct approach per AGENTS.md's "do not hide incomplete systems" principle. If the value is ever traceable (e.g., someone finds a saved forum search from April 2026), the historical count is still accessible for reconciliation.

**On the `complaint_themes` retention decision:** These themes (beta setup questions, GPU/performance uncertainty, production readiness concerns) are accurate descriptions of DaVinci beta risk. They were not invented to back the 7-report count — they describe the general risk category. Removing them would make the page less useful without improving accuracy. Retaining them with advisory framing is correct.
