# DaVinci Resolve — OBS-to-DaVinci Data Model Mapping

**Status:** Research document — Phase 1A  
**Date:** 2026-05-11  
**Scope:** Field-by-field mapping of every schema field relevant to the patch feed, from OBS Studio source values to the equivalent DaVinci Resolve values. Research only — no production changes.

---

## 1. Purpose

When DaVinci Resolve ingestion is enabled, every field the adapter produces must land correctly in the front matter schema consumed by `aux-update.html`. This document maps each field: what OBS provides, what DaVinci must provide, where the value comes from, and what gaps or transformations are required.

---

## 2. Identity and Classification Fields

### `product_id`

| | OBS | DaVinci |
|---|---|---|
| Value | `obs-studio` | `blackmagic-davinci` |
| Source | Hard-coded in config | Hard-coded in config |
| Gap | None | None |

### `company_id`

| | OBS | DaVinci |
|---|---|---|
| Value | `obs-project` | `blackmagic-design` |
| Source | Hard-coded in config | Hard-coded in config |
| Gap | None | None |

### `source_type`

| | OBS | DaVinci |
|---|---|---|
| Value | `github-release` | `html-changelog` or custom |
| Front matter field | `official_patch_notes_source_type` | Same field |
| Rendering effect | Layout derives label from this string (e.g. "Official Release Notes") | Should be `vendor_announcement` or `release_notes` — not `html-changelog` |
| Gap | None | Adapter must set this explicitly; do not inherit from generic adapter default |

---

## 3. Version Fields

### `update_version`

| | OBS | DaVinci |
|---|---|---|
| Example value | `32.1.2` | `21 Public Beta 1` |
| Source | GitHub tag, strip `v` prefix | Extracted from page title via regex (see version normalization doc) |
| Stored as | `update_version` in front matter | Same field |
| Gap | None | Raw string may need stripping of "DaVinci Resolve " prefix before storage |

### `display_version` (layout field: none — derived from `update_version` and title)

| | OBS | DaVinci |
|---|---|---|
| How rendered | `update_version` used directly | `update_version` used directly |
| Gap | None | If `update_version` is set to the full natural-language string (`21 Public Beta 1`), layout renders it correctly; if set to the normalized form (`21.0.0-beta.1`), it will look wrong to users |
| Recommendation | Store natural-language form in `update_version` for DaVinci; use `update_detail_title` to override display if needed |

---

## 4. Title Fields

### `update_title` / `update_detail_title` / `update_feed_title`

| Field | OBS | DaVinci |
|---|---|---|
| `update_feed_title` | GitHub release title | Page H1 or constructed string |
| `update_detail_title` | Not set (layout falls back to `update_product + update_version`) | Should be set explicitly, e.g. `DaVinci Resolve 21 Public Beta 1` |
| `title` (Jekyll page title) | `{software} {version} official update breakdown` | Same pattern |
| Gap | None | `update_detail_title` should be set to avoid the layout constructing an awkward string from product + normalized version |

---

## 5. Date Fields

### `update_date` / `update_published_at`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `update_published_at` | `update_published_at` |
| Source | GitHub release `published_at` (ISO 8601, e.g. `2026-01-29T18:00:00Z`) | URL date prefix `YYYYMMDD` (e.g. `20260414` → `2026-04-14T00:00:00Z`) or date in page text |
| Format required | ISO 8601 | ISO 8601 |
| Gap | None | URL-prefix date is date-only (no time component); set time to `T00:00:00Z` as placeholder |

### `update_last_checked`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `update_last_checked` | `update_last_checked` |
| Source | Set by ingest runner at time of run | Will be set when adapter runs |
| Gap | None | Currently not set on DaVinci records (ingestion disabled) |

### `source_last_checked`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `source_last_checked` | `source_last_checked` |
| Source | Set by ingest runner at each run | Will be set when adapter runs |
| Gap | None | Currently not set on DaVinci records — ingest runner sets this |

---

## 6. Source URL Fields

### `official_source_url` / `update_source_url`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `update_source_url` | `update_source_url` |
| Value | GitHub release URL (e.g. `https://github.com/obsproject/obs-studio/releases/tag/32.1.2`) | Blackmagic press release URL (e.g. `https://www.blackmagicdesign.com/media/release/20260414-01`) |
| Gap | None | URL is stable once set; must be constructed from known date or discovered |

### `official_patch_notes_source_url`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `official_patch_notes_source_url` | `official_patch_notes_source_url` |
| Value | Same as `update_source_url` for OBS | Blackmagic press release URL |
| Gap | None | Currently set on Beta 1 record; body capture has failed 5 times |

---

## 7. Release Notes Body Field

### `official_release_notes_body` / `official_patch_notes_body`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `official_patch_notes_body` | `official_patch_notes_body` |
| Source | GitHub release body (Markdown, extracted verbatim) | Press release page body (HTML → plain text → Markdown conversion required) |
| Capture status field | `official_patch_notes_capture_status` | Same field |
| Current DaVinci status | N/A | `official-source-parser-failed` on all 5 recorded attempts |
| Gap | None | Requires custom div-selector parser; current `<article>`/`<main>` selectors return empty |
| Rendering | Rendered inside collapsible `<details>` block as Markdown | Same rendering path; body must be valid Markdown or plain text |

---

## 8. Evidence and Consensus Fields

### `update_report_count`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `update_report_count` | `update_report_count` |
| Source | Set by `build_consensus_from_evidence.py` from counted rows in `consensus_evidence.yml` | Should be set by same script once evidence rows exist |
| Current DaVinci state | Populated (e.g. 7 confirmed reports for OBS 32.1.2) | `7` on Beta 1 record — **not backed by any evidence rows**; manual estimate only |
| Gap | None | Integrity gap: `audit_consensus_evidence.py` would flag this; 0 rows vs count of 7 |

### `update_consensus_label`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `update_consensus_label` | `update_consensus_label` |
| Values | `Negative` / `Moderate` / `Positive` / `Insufficient data` | Same |
| Source | `build_consensus_from_evidence.py` | Same script (when evidence exists) |
| Gap | None | Currently not set by script; would need to be set manually or left to script |

### `evidence_state`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `evidence_state` | `evidence_state` |
| Values | `pilot_sample`, `static_sample`, `live`, `official_only` | Same |
| Current DaVinci state | N/A | `pilot_sample` on Beta 1 record — incorrect; triggers "Verified reports" label with 0 backing rows |
| Gap | `evidence_state: pilot_sample` should not be set without corresponding evidence rows in `consensus_evidence.yml` |

### `confidence`  / `update_consensus_confidence`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `update_consensus_confidence` | `update_consensus_confidence` |
| Values | `Low` / `Medium` / `High` | Same |
| Source | `build_consensus_from_evidence.py` | Same |
| Gap | None | Set to `Low` on Beta 1 record; correct given no real evidence |

---

## 9. Source Health Fields

### `source_health`

This is tracked in `auxsays/_data/source_health.yml`, not in individual record front matter. The ingest runner writes to this file on each run via `update_source_success()` / `update_source_error()`.

| | OBS | DaVinci |
|---|---|---|
| Tracked in | `source_health.yml` | `source_health.yml` |
| Written by | `patch_ingest.py` on each successful/failed run | Same, when enabled |
| Current DaVinci state | N/A — ingestion disabled | Not written; no health entries |
| Gap | None | Will be populated automatically once `enabled: true` |

---

## 10. Verdict and Recommendation Fields

### `verdict` / `quick_verdict` / `update_decision_label` / `update_decision_body`

| Field | Source | OBS usage | DaVinci usage |
|---|---|---|---|
| `quick_verdict` | Manual curation | Set on some records | Set on Beta 1 record |
| `update_decision_label` | Manual or layout default | Set on some records | Set on Beta 1 record |
| `update_decision_body` | Manual | Rarely set | Set on Beta 1 record |
| Layout fallback | Derived from `evidence_state` | Used when fields absent | Used when fields absent |

The layout derives a default verdict automatically from `evidence_state`. For DaVinci records with no evidence, the layout will produce: *"Insufficient data. AUXSAYS has not captured enough official or confirmed community evidence for a recommendation."* — unless `quick_verdict` overrides it.

### `practical_recommendations`

| | OBS | DaVinci |
|---|---|---|
| Front matter field | `practical_recommendations` (YAML list) | Same |
| Source | Manual | Manual |
| Gap | None | Requires human editorial input |

---

## 11. Report Source URL and Evidence Row Fields

### `report source URLs` (in evidence rows)

Evidence rows in `consensus_evidence.yml` carry `source_url` pointing to the original community report. For OBS this is always a GitHub issue URL. For DaVinci:

| Source type | Example URL pattern | Feasibility |
|---|---|---|
| Blackmagic forum | `https://forum.blackmagicdesign.com/viewtopic.php?...` | Medium — static HTML, scrapable |
| Reddit | `https://www.reddit.com/r/davinciresolve/...` | Medium — Reddit API or Pushshift |
| YouTube comment threads | Various | Low — not structured |
| Twitter/X | Various | Low — API access restricted |

### `evidence rows` (schema for DaVinci rows)

Evidence rows for DaVinci must use the same schema as OBS rows. Key field differences:

| Field | OBS value | DaVinci equivalent |
|---|---|---|
| `product_id` | `obs-studio` | `blackmagic-davinci` |
| `source_type` | `github_issue` | `blackmagic_forum_post` / `reddit_post` / `user_report` |
| `source_name` | `obsproject/obs-studio` | `forum.blackmagicdesign.com` / `r/davinciresolve` |
| `matched_version` | `32.1.2` | `21 Public Beta 1` (natural language, or normalized) |
| `match_basis` | `body` / `title` / `both` | Same |
| `counted` | `true` / `false` | Same |

**Version matching in evidence collection:** The collector script must normalize both the `update_version` from the record and the version string extracted from the community post before comparing. A post saying "Resolve 21" must match a record with `update_version: 21 Public Beta 1` only if the beta channel is also matched — or the script must treat `21` as an alias for the stable `21.0.0` record only, not the beta.

---

## 12. Fields OBS Has That DaVinci Will Never Have

| Field | Reason absent for DaVinci |
|---|---|
| `patch_file_size` | Blackmagic does not publish file sizes on public pages |
| `official_checksums_body` | Blackmagic does not publish checksums publicly |
| `update_download_url` (direct) | Download URL is on a different page (`/support/`) than the release notes page |
| `platform_specific_installers` | Not structured on public Blackmagic pages |

These fields should be left empty or set to the appropriate status constant (`not_provided_by_source`).

---

## 13. Relationship to Other Phase 1A Documents

| Document | Relationship |
|---|---|
| `obs-to-davinci-field-mapping.md` | Sections 2–6 of that document are the source of the mapping content summarized here. This document is the field-by-field expansion. |
| `davinci-version-normalization-phase1a.md` | Covers the `update_version` / `normalized_version` / `display_version` split in detail. |
| `davinci-pipeline-current-state.md` | Explains why most DaVinci fields are currently absent or incorrect on existing records. |
