# Phase 1A Completion Report — OBS-to-DaVinci Methodology Logistics

**Phase:** 1A  
**Status:** Complete  
**Date:** 2026-05-11  
**Constraint:** Research and documentation only. No production changes. No scraping enabled. No generated records modified. No evidence rows created.

---

## 1. Deliverables Produced

| # | Deliverable | File | Status |
|---|---|---|---|
| 1 | OBS pipeline end-to-end document | `.project-control/methodology/obs-pipeline-end-to-end.md` | Done |
| 2 | DaVinci current pipeline state document | `.project-control/methodology/davinci-pipeline-current-state.md` | Done |
| 3 | Blackmagic official source feasibility assessment | `.project-control/methodology/davinci-official-source-feasibility.md` | Done |
| 4 | OBS-to-DaVinci field mapping and version normalization | `.project-control/methodology/obs-to-davinci-field-mapping.md` | Done |
| 5 | DaVinci version normalization (separate document) | `.project-control/methodology/davinci-version-normalization-phase1a.md` | Done |
| 6 | DaVinci data model mapping (separate document) | `.project-control/methodology/davinci-data-model-mapping-phase1a.md` | Done |
| 7 | Dry-run probe script | `.project-control/prototypes/davinci-probe-dry-run.py` | Done |
| 8 | This completion report | `.project-control/reports/phase1a-completion-report.md` | Done |

---

## 2. Key Findings

### 2.1 OBS pipeline — fully operational

The OBS Studio pipeline is the only production-grade source. Its five stages are documented end-to-end:

1. **Config** → `patch_ingestion_sources.yml` (enabled, P1 priority, GitHub Releases adapter)
2. **Ingest** → `patch_ingest.py` → `adapters/github_releases.py` → GitHub REST API
3. **Record writing** → `lib/write_update_record.py` → `auxsays/updates/generated/*.md`
4. **Evidence collection** → `collect_obs_reports.py` → GitHub Issues search → `consensus_evidence.yml` (59 OBS rows as of audit)
5. **Rendering** → `_layouts/aux-update.html` (Liquid logic driving all display state from front matter)

The audit script (`audit_consensus_evidence.py`) is the integrity guardian. Protected field mechanism in `write_update_record.py` prevents ingest from clobbering verdict/evidence fields.

### 2.2 DaVinci pipeline — disabled and incomplete

Three layers of failure stack to make DaVinci ingestion non-functional:

**Layer 1 — Dead stub:** `fetch_davinci_updates.py` is an 11-line hardcoded stub. It does not fetch anything. It is not called by `patch_ingest.py`. It is a dead artefact.

**Layer 2 — Unimplemented parser profile:** The config specifies `parser_profile: blackmagic_media_keyword_filter`. This profile name has no corresponding branch in `html_changelog.py`. It falls through to the generic link-filter path, which cannot discover links from `blackmagicdesign.com/media` (JavaScript-rendered listing page).

**Layer 3 — Body extraction failure:** Even when a direct press release URL is provided (via the `refresh_linked_official_bodies` retry path), the `<article>`/`<main>` selector finds nothing on Blackmagic's `<div>`-structured pages. All 5 recorded attempts returned `official-source-parser-failed`.

**Layer 4 — Evidence integrity gap:** The DaVinci Beta 1 record carries `update_report_count: 7` and `evidence_state: pilot_sample`. Zero rows in `consensus_evidence.yml` back this count. The layout renders "Verified reports" — a misleading label given no backing evidence exists.

### 2.3 Official source feasibility — Medium

Direct fetching of individual press release URLs (`/media/release/YYYYMMDD-NN`) is feasible with a custom body selector. The JavaScript listing page must be bypassed entirely — URL construction from a known date is the viable discovery strategy. The `/media` listing page is not reliably traversable by static fetch.

### 2.4 Field mapping — schemas are compatible

Both OBS and DaVinci records target the same front matter schema and the same `aux-update.html` layout. The key normalization gaps are:

- **Version pattern:** Current regex requires two numeric components (`[0-9]+(\.[0-9]+)+`). DaVinci `21` (major-only) will not match. A minor pattern change (`+` → `*`) is required for the DaVinci config entry only.
- **Version display vs. slug:** `21 Public Beta 1` must be split into a normalized machine version (`21`) and a display/slug-safe form (`21-public-beta-1`).
- **File size and checksums:** Both fields will always be absent for DaVinci. `patch_file_size_status: not_provided_by_source` is the correct value.
- **Source type string:** DaVinci records should use `vendor_announcement` or `release_notes` as `official_patch_notes_source_type`, not `github-release`.

---

## 3. What Was Not Done (Intentional Scope Limits)

| Item | Reason not done |
|---|---|
| Enabling DaVinci ingestion | Out of scope — Phase 1A is research only |
| Implementing `blackmagic_media_keyword_filter` | Out of scope |
| Fixing Beta 1 record's `update_report_count: 7` | Out of scope — no generated records modified |
| Creating DaVinci evidence rows | Out of scope |
| Running the probe script against live URLs | Probe script exists; not executed — live fetch not authorized for research phase |
| Pushing to GitHub | User retains local repo; no push performed |

---

## 4. Files Created (This Phase)

```
.project-control/methodology/obs-pipeline-end-to-end.md
.project-control/methodology/davinci-pipeline-current-state.md
.project-control/methodology/davinci-official-source-feasibility.md
.project-control/methodology/obs-to-davinci-field-mapping.md
.project-control/methodology/davinci-version-normalization-phase1a.md
.project-control/methodology/davinci-data-model-mapping-phase1a.md
.project-control/reports/phase1a-completion-report.md
.project-control/prototypes/davinci-probe-dry-run.py
```

No files in `auxsays/updates/generated/`, `auxsays/_data/`, or `.github/workflows/` were created or modified.

---

## 5. Recommended Next Steps (Phase 1B Candidates)

Listed in priority order, each is independently scoped.

### P1 — Editorial correction (no code change)
Add a `record_note` to `2026-04-14-davinci-resolve-21-public-beta-1.md` clarifying that `update_report_count: 7` is a pre-evidence manual estimate and not backed by `consensus_evidence.yml` rows. This corrects the misleading "Verified reports" label without touching consensus fields via a script.

### P2 — Implement Blackmagic body parser
Add a `blackmagic_media_keyword_filter` branch to `html_changelog.py` that:
1. Accepts a known press release URL (constructed or passed in) rather than discovering from the listing page.
2. Uses custom `<div>` selectors (probe script output will identify the correct selector).
3. Passes `body_matches_record()`.

### P3 — Fix version pattern for DaVinci
Change `version_pattern` in the DaVinci config entry from `[0-9]+(\.[0-9]+)+` to `[0-9]+(\.[0-9]+)*` to allow major-only versions like `21`.

### P4 — Retire `fetch_davinci_updates.py`
Remove or clearly mark this 11-line stub. It is not called by the current pipeline and misrepresents the system state to anyone reading it.

### P5 — Correct `requires_javascript` in DaVinci config
Change from `false` to `true` for the `/media` listing page. (The individual press release URLs are static and do not require JS — this correction applies only to the listing page as a discovery mechanism.)

### P6 — Run the probe script
Execute `.project-control/prototypes/davinci-probe-dry-run.py` against the live Blackmagic URL once authorized for Phase 1B. Its output will identify the correct `<div>` selector for body extraction and confirm whether the listing page is JS-rendered in practice. Redirect stdout to `.project-control/probe-output/` for storage.

---

## 6. Protected Files — Confirmed Untouched

| File | Status |
|---|---|
| `.github/workflows/` | Not touched |
| `auxsays/updates/generated/*.md` | Not touched |
| `auxsays/_data/consensus_evidence.yml` | Not touched |
| `auxsays/_data/source_health.yml` | Not touched |
| `auxsays/_data/patch_ingest_state.json` | Not touched |
| `auxsays/assets/img/patch-logos/_generation-report.json` | Not touched |

---

## 7. Validation Run Results

Validation scripts were run at the end of Phase 1A (cleanup session, 2026-05-11) after all deliverable files were committed. No production files were modified before or during these runs.

| Script | Command | Exit code | Result |
|---|---|---|---|
| `validate_ingestion_sources.py` | `python3 auxsays/scripts/validate_ingestion_sources.py` | 0 | **Pass** — "Source config validation passed: 46 entries checked." |
| `qa_patch_records.py` | `python3 auxsays/scripts/qa_patch_records.py` | 0 | **Pass** — "QA scanned 38 generated records and 14 priority products: 0 errors, 0 warnings" |
| `audit_consensus_evidence.py` | `python3 auxsays/scripts/audit_consensus_evidence.py --json --strict` | **1** | See note below |

### `audit_consensus_evidence.py --json --strict` — Exit Code 1

**This exit code 1 is a pre-existing condition. It was not introduced by Phase 1A.**

The audit flagged records with two staleness reasons:

- **`stale_or_missing_update_last_checked`** — `update_last_checked` field is absent or older than the staleness threshold on some existing records.
- **`source_checked_after_record_last_checked`** — the live ingest runner (running on its normal schedule) updated `source_last_checked` timestamps on existing records without bumping `record_last_updated`. This is expected behaviour for freshness-only refresh cycles in `patch_ingest.py`.

All flagged records are Figma, ComfyUI, and GitHub Copilot entries updated by the ingest runner between Phase 0 completion and the Phase 1A validation run. No DaVinci records and no OBS records were flagged.

**Confirmed:** Phase 1A made zero changes to `auxsays/updates/generated/`, `auxsays/_data/consensus_evidence.yml`, `auxsays/_data/source_health.yml`, `auxsays/_data/patch_ingest_state.json`, or `.github/workflows/`. The staleness flags existed before Phase 1A began and would have appeared on any validation run during this period regardless of Phase 1A work.

---

## 8. Files Read (Source of All Findings)

| File | Notes |
|---|---|
| `auxsays/scripts/collect_obs_reports.py` | OBS evidence collection |
| `auxsays/scripts/fetch_davinci_updates.py` | Dead stub — documented |
| `auxsays/scripts/patch_ingest.py` | Ingestion orchestrator |
| `auxsays/scripts/lib/write_update_record.py` | Record writer + protected fields |
| `auxsays/scripts/build_consensus_from_evidence.py` | Consensus aggregation |
| `auxsays/scripts/audit_consensus_evidence.py` | Integrity audit |
| `auxsays/scripts/adapters/github_releases.py` | OBS adapter |
| `auxsays/scripts/adapters/html_blog.py` | DaVinci adapter alias |
| `auxsays/scripts/adapters/html_changelog.py` | Actual HTML parser |
| `auxsays/_data/patch_ingestion_sources.yml` | Source config (both products) |
| `auxsays/_data/consensus_evidence.yml` | 62 rows; 59 OBS, 0 DaVinci |
| `auxsays/_layouts/aux-update.html` | Full rendering pipeline |
| `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md` | Integrity gap identified |
| `auxsays/updates/generated/` (DaVinci 21 archived) | Referenced |
| `.project-control/methodology/patch-feed-methodology-phase0.md` | Prior phase context |
