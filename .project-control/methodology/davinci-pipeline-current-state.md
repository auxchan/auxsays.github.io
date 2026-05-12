# DaVinci Resolve — Current Pipeline State

**Status:** Research document — Phase 1A  
**Date:** 2026-05-11  
**Scope:** Read-only audit of the DaVinci Resolve ingestion pipeline as it exists today. No production changes.

---

## 1. Summary

DaVinci Resolve is **disabled in production ingestion**. The adapter path is technically wired but has failed on every recorded attempt. No evidence rows exist. The one live DaVinci record contains a report count that is not backed by `consensus_evidence.yml` rows.

---

## 2. Source Configuration

**File:** `auxsays/_data/patch_ingestion_sources.yml`

| Field | Value |
|---|---|
| `product_id` | `blackmagic-davinci` |
| `company_id` | `blackmagic-design` |
| `enabled` | **`false`** |
| `recommended_priority` | P2 manual watch active |
| `ingestion.adapter` | `html_blog` |
| `ingestion.official_url` | `https://www.blackmagicdesign.com/media` |
| `ingestion.secondary_official_url` | `https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion` |
| `ingestion.parser_profile` | `blackmagic_media_keyword_filter` |
| `ingestion.include_prereleases` | `false` |
| `ingestion.version_pattern` | `^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$` |
| `ingestion.scrape_feasibility` | Medium |
| `ingestion.reliability` | Medium |
| `ingestion.breakage_risk` | **Medium-High** |
| `ingestion.polling_frequency` | 12 h |
| `ingestion.update_detection_method` | manual watch with title-date keyword filter candidate |
| `ingestion.requires_javascript` | `false` |

**Note on `source_health_note` in config:**
> "Official record tracked; automated ingestion is not active because the current Blackmagic adapter path is not source-specific enough for safe unattended runs."

---

## 3. Adapter Chain

### 3.1 `fetch_davinci_updates.py` — the legacy stub

**File:** `auxsays/scripts/fetch_davinci_updates.py`

This is an **11-line hardcoded stub**. It does not scrape, fetch, or parse anything. It writes a single fixed state entry to `patch_ingest_state.json` regardless of what is live on Blackmagic's site. It is not called by `patch_ingest.py`.

```python
# Actual behavior: writes a fixed static dict to state JSON.
# No HTTP requests. No parsing. No record generation.
```

This script is a placeholder from an earlier prototype phase. It has no role in the current ingestion architecture.

### 3.2 `html_blog.py` — the compatibility wrapper

**File:** `auxsays/scripts/adapters/html_blog.py`

One-line module: `from adapters.html_changelog import fetch`

This re-exports the `fetch` function from `html_changelog.py` under the adapter name `html_blog`. `patch_ingest.py` dynamically imports `adapters.html_blog` and calls `fetch(source, limit=...)`.

### 3.3 `html_changelog.py` — the actual parser

**File:** `auxsays/scripts/adapters/html_changelog.py`

Generic HTML changelog adapter. Its dispatch logic:

1. If `parser_profile` starts with `adobe_` and ends with `_release_notes` → runs Adobe-specific heading parser.
2. Otherwise → fetches `ingestion.official_url` as a listing page, extracts `<a>` links, filters by profile:
   - `netlify_changelog` → Netlify URL pattern matcher.
   - Default/generic → looks for `/changelog/`, `/release-notes/`, `/releases/` in href or link text; excludes `/tag/`, `/category/`, `/author/`, `/page/`, `/feed/`, `/rss/`, `/atom/`.
3. Follows up to 10 candidate links, fetches each, extracts title (h1→h2→title), date (DATE_RE scan on first 8000 chars of text), and body (article→main→full strip, capped at 6000 chars).
4. If no candidate links found: falls back to `allow_listing_snapshot` (not set for DaVinci).

**The `blackmagic_media_keyword_filter` parser_profile is not implemented.** The adapter has no branch for this profile name — it falls through to the generic link-filter logic. The Blackmagic `/media` page is a JavaScript-rendered press release index; the generic `<a>` link filter finds no `/changelog/`, `/release-notes/`, or `/releases/` paths, so zero candidate links are returned, and with `allow_listing_snapshot` not set, the fetch returns an empty list.

---

## 4. Official Source Attempt History

From the DaVinci Beta 1 record (`2026-04-14-davinci-resolve-21-public-beta-1.md`):

```yaml
official_source_attempts:
  - url: https://www.blackmagicdesign.com/media/release/20260414-01
    attempted_at: [multiple dates]
    result: official-source-parser-failed
```

**All 5 recorded attempts returned `official-source-parser-failed`.**

The URL pattern `https://www.blackmagicdesign.com/media/release/20260414-01` is a specific press release permalink — not the listing page. The `html_changelog.py` generic parser:
1. Fetches the URL.
2. Looks for article/main tags.
3. The Blackmagic press release pages render body content inside `<div>` structures, not `<article>` or `<main>` tags, so `body_from_html()` in `patch_ingest.py` returns empty.
4. `body_matches_record()` fails (body < 300 chars or no product/version match) → `capture_status: official-source-parser-failed`.

---

## 5. Evidence State

**`auxsays/_data/consensus_evidence.yml`:** 0 DaVinci rows out of 62 total.

No evidence collection script has been run for DaVinci. `collect_obs_reports.py` is OBS-specific (GitHub Issues API). No equivalent script exists for DaVinci forum, Reddit, or Blackmagic forum sources.

---

## 6. Existing DaVinci Records

### 6.1 DaVinci Resolve 21 Public Beta 1 (live record)

**File:** `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md`

| Field | Value | Issue |
|---|---|---|
| `evidence_state` | `pilot_sample` | Triggers "Verified reports" label in layout |
| `update_report_count` | `7` | **Not backed by any consensus_evidence.yml rows** |
| `consensus_collection_status` | Not set / `deferred_official_only` | Inconsistent with `evidence_state: pilot_sample` |
| `official_patch_notes_body` | Not captured | All 5 fetch attempts failed |
| `official_patch_notes_source_url` | Set to Blackmagic press release URL | Linked, body absent |
| `update_consensus_confidence` | Low | |

**Integrity gap:** `audit_consensus_evidence.py` would flag this record — `update_report_count: 7` but 0 counted rows in `consensus_evidence.yml`.

### 6.2 DaVinci Resolve 21 (archived record)

Archived record exists for DaVinci Resolve 21 stable. Not examined for this audit but follows the same pattern.

---

## 7. What Would Need to Be True for DaVinci to Be Enabled

For DaVinci to be enabled (`enabled: true`) in `patch_ingestion_sources.yml` safely:

1. A working parser that can extract structured data from `blackmagicdesign.com` release pages.
2. The parser must pass `body_matches_record()` — body must be ≥ 300 chars and contain the product name or version string.
3. Version normalization must handle DaVinci's versioning scheme (see field mapping document).
4. An evidence collection mechanism for DaVinci community sources must exist before `update_report_count` can reflect real data.
5. `fetch_davinci_updates.py` should be retired or rewritten — it is a dead stub that can cause confusion.

---

## 8. Current Status Labels (as rendered)

Because `evidence_state: pilot_sample` is set on the Beta 1 record, the layout renders **"Verified reports"** — which implies community evidence exists. This is misleading given 0 backing rows. The record's `record_note` field (if set) is the mechanism to surface a correction without modifying consensus fields.

---

## 9. Files Involved

| File | Role | State |
|---|---|---|
| `scripts/fetch_davinci_updates.py` | Legacy stub | Dead / misleading |
| `scripts/adapters/html_blog.py` | Thin re-export | Functional as alias |
| `scripts/adapters/html_changelog.py` | Actual HTML parser | Live but not DaVinci-capable |
| `_data/patch_ingestion_sources.yml` (DaVinci entry) | Config | `enabled: false` |
| `updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md` | Live record | Integrity gap on report count |
| `_data/consensus_evidence.yml` | Evidence store | 0 DaVinci rows |
