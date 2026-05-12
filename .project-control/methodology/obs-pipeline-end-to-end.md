# OBS Studio — Patch Feed Pipeline (End-to-End)

**Status:** Research document — Phase 1A  
**Date:** 2026-05-11  
**Scope:** Read-only documentation of the live OBS ingestion and rendering pipeline as it exists today. No production changes.

---

## 1. Overview

OBS Studio is the only fully-enabled, production-grade source in the patch feed. Its pipeline spans five distinct stages: source configuration → official-data ingestion → record writing → evidence collection → consensus aggregation → rendering.

---

## 2. Source Configuration

**File:** `auxsays/_data/patch_ingestion_sources.yml`

| Field | Value |
|---|---|
| `product_id` | `obs-studio` |
| `company_id` | `obs-project` |
| `enabled` | `true` |
| `recommended_priority` | P1 build now |
| `ingestion.adapter` | `github_releases` |
| `ingestion.api_url` | `https://api.github.com/repos/obsproject/obs-studio/releases` |
| `ingestion.official_url` | `https://github.com/obsproject/obs-studio/releases` |
| `ingestion.secondary_official_url` | `https://obsproject.com/download` |
| `ingestion.parser_profile` | `github_release_standard` |
| `ingestion.include_prereleases` | `false` |
| `ingestion.version_pattern` | `^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$` |
| `ingestion.checksum_selector` | `## Checksums` |
| `ingestion.download_selector` | `assets` |
| `ingestion.breakage_risk` | Low |
| `ingestion.polling_frequency` | 6 h |

**Extractable fields confirmed by config:**
version, release_date, title, release_note_body, download_url, file_size, checksum, platform_specific_installers, archived_release_history.

---

## 3. Stage 1 — Official Source Ingestion

**Entry point:** `auxsays/scripts/patch_ingest.py`  
**Adapter:** `auxsays/scripts/adapters/github_releases.py`

### 3.1 How `patch_ingest.py` orchestrates

1. Loads `patch_ingestion_sources.yml` (full list).
2. Filters to enabled sources only (or `--all` / `--source` flags override).
3. For each enabled source, dynamically imports `adapters.<adapter>` and calls `module.fetch(source, limit=args.limit)` (default limit = 2).
4. Iterates returned records: deduplicates via `auxsays/_data/patch_ingest_state.json`, calls `write_record()` or `refresh_existing_record()`, marks seen in state.
5. After all sources: calls `refresh_linked_official_bodies()` to retry body capture on existing records with `official-source-parser-failed` / similar statuses.
6. Writes updated state JSON; prints JSON run summary.
7. `--dry-run` flag fetches and reports but writes nothing.

### 3.2 GitHub Releases adapter

**File:** `auxsays/scripts/adapters/github_releases.py`

The adapter calls the GitHub REST API (`GET /repos/obsproject/obs-studio/releases`). For each release returned (up to `limit`):

- Skips pre-releases if `include_prereleases: false`.
- Extracts version from tag name via `version_pattern` regex (named group `version`).
- Parses release body for a `## Checksums` section (controlled by `checksum_selector`).
- Extracts asset download URLs and file sizes from the `assets` array.
- Produces a normalized record dict with standardized keys.

**Key output fields from adapter:**
`record_id`, `company_id`, `product_id`, `company`, `software`, `version`, `title`, `published_at`, `source_url`, `official_url`, `download_url`, `file_size`, `body`, `checksums_body`, `source_type` = `"github-release"`, `capture_status`.

---

## 4. Stage 2 — Record Writing

**File:** `auxsays/scripts/lib/write_update_record.py`

`write_record(output_dir, record, overwrite_existing)`:
- Derives a slug: `{published_date}-{product_id}-{version_slug}.md`.
- Builds front matter from the record dict using a canonical field mapping (layout, title, description, permalink, update_entry, company_id, product_id, update_product, update_version, update_published_at, update_last_checked, patch_file_size, patch_file_size_note, update_source_url, update_download_url, official_summary, release_summary, official_patch_notes_body, official_checksums_body, update_consensus_label, update_report_count, update_consensus_confidence, consensus_report, complaint_themes, status_events).
- Protected fields (consensus/verdict/evidence) are never overwritten by the ingest runner on an existing record unless `overwrite_existing` is set.
- `refresh_existing_record()` only updates the safe freshness fields: `source_last_checked`, `official_body_last_checked`, `official_patch_notes_body`, `official_patch_notes_capture_status`, and `record_last_updated`.

**Output path:** `auxsays/updates/generated/{slug}.md`

---

## 5. Stage 3 — Evidence Collection

**Script:** `auxsays/scripts/collect_obs_reports.py`

This script runs separately from `patch_ingest.py`. It searches GitHub Issues for OBS-version-specific reports.

### 5.1 Search strategy
- Queries GitHub Issues API with version-specific search terms.
- Inspects issue body and title for explicit version mentions matching `update_version`.
- Produces one evidence row per confirmed, patch-version-matched issue.

### 5.2 Evidence row schema (`consensus_evidence.yml`)
From the live data (62 total rows, 59 OBS rows, 0 DaVinci rows):

```yaml
id: obs-studio-32-1-2-github-issue-13367
product_id: obs-studio
update_version: 32.1.2
source_type: github_issue
source_name: obsproject/obs-studio
source_url: https://github.com/obsproject/obs-studio/issues/13367
parent_title: "Crash if service restrictions..."
report_title: "Crash if service restrictions..."
report_text_excerpt: "..."
captured_at: 2026-05-03T01:00:10Z
patch_version_matched: true
matched_version: 32.1.2
match_basis: body
counted: true
exclusion_reason: null
issue_theme: crash / stability
workflow_area: application stability
platform: windows
severity: high
sentiment: negative
source_weight: 1
```

**Written to:** `auxsays/_data/consensus_evidence.yml`

---

## 6. Stage 4 — Consensus Aggregation

**Script:** `auxsays/scripts/build_consensus_from_evidence.py`

Reads `consensus_evidence.yml`, groups rows by `product_id` + `update_version`, aggregates:
- `update_report_count` — count of rows where `counted: true`.
- `update_consensus_label` — derived from sentiment distribution (Positive / Moderate / Negative / Insufficient data).
- `consensus_score_percent` — numeric position on the 0–100 scale.
- `update_consensus_confidence` — Low / Medium / High based on sample size.
- Writes aggregated values back into the relevant generated record's front matter (protected write: only consensus/evidence fields are updated).

**Audited by:** `auxsays/scripts/audit_consensus_evidence.py` — cross-checks `update_report_count` in front matter against actual counted rows in `consensus_evidence.yml`.

---

## 7. Stage 5 — Rendering

**Layout:** `auxsays/_layouts/aux-update.html`  
**Base layout:** `aux-base`

The layout derives all display state from front matter fields using Liquid logic. Key rendering decisions:

| Front matter field | Rendering effect |
|---|---|
| `consensus_collection_status` | Controls `evidence_state` label: `live_consensus`, `pilot_initial_sample`, `static_initial_sample` → "Verified reports"; `official_captured` → "Official source only"; else "Insufficient data" |
| `evidence_state: pilot_sample` | Also triggers "Verified reports" label |
| `update_report_count` | Drives report count display and `patch_specific_reports_label` |
| `update_consensus_label` | Drives the Consensus word and bar position |
| `consensus_score_percent` | Overrides auto-derived bar position |
| `official_patch_notes_body` | Renders the collapsible official notes section |
| `official_patch_notes_source_url` | Used if body is absent (shows "body not captured yet") |
| `update_consensus_confidence` | Low / Medium / High label in verdict card |
| `security_sensitive` | Overrides verdict text for security patches |
| `practical_recommendations` | Renders recommendation list |
| `evidence_samples` | Renders community risk sample cards |
| `complaint_themes` | Renders complaint theme table |
| `known_issues_present` | Controls known-issues label |

**Verdict card resolution order:**
1. `quick_verdict` (manual override)
2. Derived from `evidence_state` (Live consensus / Verified reports / Official source only / Insufficient data)

---

## 8. Data Stores

| File | Role | Protected? |
|---|---|---|
| `auxsays/_data/patch_ingestion_sources.yml` | Source config | No (editable) |
| `auxsays/_data/patch_ingest_state.json` | Dedupe + run state | Yes — ingest runner owns it |
| `auxsays/_data/consensus_evidence.yml` | Evidence rows | Yes — collect script owns it |
| `auxsays/_data/source_health.yml` | Source run health log | Yes — ingest runner owns it |
| `auxsays/updates/generated/*.md` | Generated records | Yes — protected field set |

---

## 9. Current OBS Evidence Coverage (as of 2026-05-11)

| Version | Evidence rows (counted) | Notes |
|---|---|---|
| 32.1.2 | ~59 rows | Live, multi-theme |
| 32.1.1 | See record | Separate version bucket |
| DaVinci (any) | 0 rows | No evidence collected |

---

## 10. Pipeline Integrity Notes

- The audit script (`audit_consensus_evidence.py`) is the integrity check: it will flag a discrepancy if `update_report_count` in a record does not match the actual counted rows.
- The DaVinci Beta 1 record currently has `update_report_count: 7` with zero backing rows in `consensus_evidence.yml` — this is a known integrity gap documented separately in the DaVinci pipeline document.
- The `write_update_record.py` protected-field mechanism is the primary guard against ingest clobbering manually curated content.
