# OBS-to-DaVinci Field Mapping and Version Normalization

**Status:** Research document — Phase 1A  
**Date:** 2026-05-11  
**Scope:** Field-level mapping of OBS ingestion outputs to the equivalent DaVinci fields, plus version normalization analysis. Research only — no production changes.

---

## 1. Purpose

When DaVinci ingestion is eventually enabled, the adapter output must populate the same front matter schema that the `aux-update.html` layout consumes. This document maps OBS adapter output fields → front matter fields → layout consumption, then identifies the gaps and normalization requirements specific to DaVinci.

---

## 2. Canonical Front Matter Schema

The following fields are defined in the `generated_record.front_matter_fields` arrays for both OBS and DaVinci in `patch_ingestion_sources.yml`. Both products share the same schema.

| Front Matter Field | Source for OBS | Source for DaVinci (proposed) | Notes |
|---|---|---|---|
| `layout` | Hard-coded: `aux-update` | Same | Shared layout |
| `title` | Adapter title | Page H1 / constructed | Requires normalization |
| `description` | Adapter body summary | Constructed from body | |
| `permalink` | `/updates/obs-project/obs-studio/{version_slug}/` | `/updates/blackmagic-design/blackmagic-davinci/{version_slug}/` | Pattern differs by company/product slug |
| `update_entry` | `true` | `true` | |
| `company_id` | `obs-project` | `blackmagic-design` | |
| `product_id` | `obs-studio` | `blackmagic-davinci` | |
| `update_product` | `OBS Studio` | `DaVinci Resolve` | |
| `update_version` | Extracted from tag (e.g. `32.1.2`) | Extracted from title (e.g. `21 Public Beta 1`) | **Key normalization gap** |
| `update_published_at` | GitHub release `published_at` (ISO 8601) | URL date prefix `YYYYMMDD` or page text | |
| `update_last_checked` | `source_last_checked` from ingest run | Same | |
| `patch_file_size` | GitHub release asset `.size` in bytes | Not available from Blackmagic | Will always be absent |
| `patch_file_size_note` | `not_provided_by_source` / populated | `not_provided_by_source` | Config `extractable_fields.file_size: false` |
| `update_source_url` | GitHub release URL | Blackmagic press release URL | |
| `update_download_url` | GitHub release asset URL | Blackmagic support page URL | Different page than source URL |
| `official_summary` | Adapter-generated | Constructed or body excerpt | |
| `release_summary` | From release body | From press release body | |
| `official_patch_notes_body` | Full release body (markdown) | Press release body (plain text → markdown) | Structure differs |
| `official_checksums_body` | Parsed from `## Checksums` section | Not available | Config `extractable_fields.checksum: false` |
| `update_consensus_label` | Set by `build_consensus_from_evidence.py` | Same (when evidence exists) | |
| `update_report_count` | Set by consensus script | Same | Currently manual estimate on DaVinci Beta 1 |
| `update_consensus_confidence` | Set by consensus script | Same | |
| `consensus_report` | Manual or consensus script | Manual | |
| `complaint_themes` | Manual curation | Manual | |
| `status_events` | Manual curation | Manual | |

---

## 3. Fields the Layout Uses That Are Not in the Ingestion Schema

The `aux-update.html` layout references additional fields beyond the base `front_matter_fields` list. These are populated manually or by the consensus script.

| Layout Field | Source | OBS Status | DaVinci Status |
|---|---|---|---|
| `update_consensus_label` | Consensus script | Populated | Not populated (no evidence) |
| `consensus_collection_status` | Manual / consensus script | Set | Inconsistent on Beta 1 record |
| `evidence_state` | Manual / consensus script | Set on pilot records | Set to `pilot_sample` on Beta 1 (no backing rows) |
| `evidence_last_checked` | Consensus script | Set | Not set |
| `source_last_checked` | Ingest runner | Set | Not set (ingest disabled) |
| `official_body_last_checked` | Refresh runner | Set where captured | Not captured |
| `record_last_updated` | Write script | Set | Manually set |
| `quick_verdict` | Manual | Set on some records | Set on Beta 1 |
| `update_decision_label` | Manual | Set on some records | Set on Beta 1 |
| `official_patch_notes_source_type` | Adapter / manual | `github-release` | Should be `vendor_announcement` or `release_notes` |
| `official_patch_notes_capture_status` | Adapter / refresh runner | Populated | `official-source-parser-failed` |
| `security_sensitive` | Manual | Set where relevant | Not set |
| `practical_recommendations` | Manual | Set on some records | Set on Beta 1 |
| `evidence_samples` | Manual / evidence script | Set on pilot records | Not set |
| `known_issues_present` | Manual | Set where known | Not set |
| `patch_file_size_status` | Adapter / manual | `not_provided_by_source` | Same |
| `official_sources` | Manual / adapter | Set | Partially set |
| `record_note` | Manual | Rarely set | Not set on Beta 1 (should be) |

---

## 4. Version Normalization

### 4.1 OBS version format

OBS Studio uses standard semver-compatible release tags: `v32.1.2`, `v32.1.1`, `v32.0.0`.

The `version_pattern` in config: `^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$`

This strips the leading `v` prefix and captures the numeric version string. Result: `32.1.2`.

**Slug derivation:** Dots are replaced with hyphens → `32-1-2`. Combined with date: `2026-01-29-obs-studio-32-1-2.md`.

### 4.2 DaVinci version format

DaVinci Resolve uses a mixed scheme:

| Release type | Example tag / title | Issues |
|---|---|---|
| Stable release | `DaVinci Resolve 21` | No minor/patch components |
| Stable with patch | `DaVinci Resolve 21.0.1` | Three-component |
| Beta | `DaVinci Resolve 21 Public Beta 1` | Non-numeric suffix |
| Beta with build | `DaVinci Resolve 21 Public Beta 2` | Ordinal suffix |
| Speed Editor | (version tied to resolve) | |

### 4.3 Version normalization gaps

| OBS | DaVinci | Gap | Proposed normalization |
|---|---|---|---|
| `32.1.2` (clean semver) | `21` (major only) | DaVinci major-only versions will not match the `version_pattern` regex's `[0-9]+(\.[0-9]+)+` requirement — at least two numeric components required | Add `[0-9]+(\.[0-9]+)*` to allow major-only |
| `32.1.2` | `21 Public Beta 1` | Suffix after version is non-numeric | Strip non-numeric suffix for normalized `update_version`; preserve full string in `update_version_label` or title |
| Slug: `32-1-2` | Slug: `21` or `21-public-beta-1` | Slug must be consistent for permalink stability | DaVinci slugs should be constructed as `{major}[-{minor}[-{patch}]][-{channel_slug}]` |

### 4.4 Proposed DaVinci version normalization rules

```
Input: "DaVinci Resolve 21 Public Beta 1"

Step 1 — Strip product name prefix:
  "21 Public Beta 1"

Step 2 — Extract numeric version:
  Major: 21
  Minor: (absent) → 0
  Patch: (absent) → 0
  Normalized version: "21.0.0" or simply "21"

Step 3 — Detect channel:
  "Public Beta 1" → channel = "beta", channel_seq = 1
  "Public Beta 2" → channel = "beta", channel_seq = 2
  (none) → channel = "stable"

Step 4 — Construct update_version:
  Stable: "21" or "21.0.1"
  Beta: "21 Public Beta 1" (preserve for display); normalized slug: "21-public-beta-1"

Step 5 — Construct slug:
  "21-public-beta-1" → file: "{date}-davinci-resolve-21-public-beta-1.md"
  "21" → file: "{date}-davinci-resolve-21.md"
```

### 4.5 Version pattern change required

Current `version_pattern` in both OBS and DaVinci config entries:
```
^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$
```

The `+` quantifier on `(\.[0-9]+)+` requires at least one `.`-separated component. `21` alone will not match.

Proposed change for DaVinci only:
```
^(v)?(?P<version>[0-9]+(\.[0-9]+)*.*)$
```

(Change `+` to `*` after the inner group to allow zero additional components.)

**This change should only be applied to the DaVinci config entry, not OBS.** OBS versions will always have at least two numeric components.

---

## 5. Adapter Output Field Mapping (GitHub Releases → `html_changelog`)

The two adapters produce different key names in some cases. The `write_update_record.py` function must handle both.

| Concept | `github_releases` output key | `html_changelog` output key | `write_update_record.py` mapping |
|---|---|---|---|
| Unique record ID | `record_id` | `record_id` | Same |
| Version string | `version` | `version` | Same |
| Display title | `title` | `title` | Same |
| Release date | `published_at` | `published_at` | Same |
| Primary source URL | `source_url` | `source_url` | → `update_source_url` |
| Official listing URL | `official_url` | `official_url` | → stored as `primary_official_source` |
| Download URL | `download_url` | `download_url` | → `update_download_url` |
| File size | `file_size` | `file_size` (always empty) | → `patch_file_size` |
| File size note | (not set by adapter) | `file_size_note` | → `patch_file_size_note` |
| Release body | `body` | `body` | → `official_patch_notes_body` |
| Checksums | `checksums_body` | `checksums_body` (always empty) | → `official_checksums_body` |
| Capture status | `capture_status` | `capture_status` | → `official_patch_notes_capture_status` |
| Source type string | `"github-release"` | `"html-changelog"` or `"html-changelog-snapshot"` | → `official_patch_notes_source_type` |
| Official summary | `official_summary` | `official_summary` (not always set) | → `official_summary` |

---

## 6. Evidence Schema Compatibility

OBS evidence rows in `consensus_evidence.yml` use these fields:

```
id, product_id, update_version, source_type, source_name, source_url,
parent_title, report_title, report_text_excerpt, captured_at,
patch_version_matched, matched_version, match_basis, counted,
exclusion_reason, issue_theme, workflow_area, platform, severity,
sentiment, source_weight
```

For DaVinci, the same schema applies. The key difference is `source_type`:

| OBS source type | DaVinci equivalent |
|---|---|
| `github_issue` | `blackmagic_forum_post`, `reddit_post`, `user_report` |
| `github_discussion` | (no direct equivalent; Blackmagic uses their own forum) |

**Version matching complexity:** OBS version matching uses `matched_version: 32.1.2` which maps cleanly to the record's `update_version`. For DaVinci, `matched_version` may be `21 Public Beta 1` — the matching logic in any future DaVinci evidence collector must normalize this to match the front matter `update_version` field.

---

## 7. Summary of Gaps Requiring Code Changes

| Gap | File(s) affected | Priority |
|---|---|---|
| `blackmagic_media_keyword_filter` profile not implemented | `adapters/html_changelog.py` | P2 |
| Blackmagic press release body not extractable | `adapters/html_changelog.py` | P2 |
| `version_pattern` requires two numeric components | `_data/patch_ingestion_sources.yml` (DaVinci entry) | P2 |
| No DaVinci evidence collector exists | New script needed | P3 |
| `fetch_davinci_updates.py` is a dead stub | `scripts/fetch_davinci_updates.py` | P3 (retire) |
| `requires_javascript: false` inaccurate for `/media` listing | `_data/patch_ingestion_sources.yml` (DaVinci entry) | Documentation |
| Beta 1 record `update_report_count: 7` not evidence-backed | `updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md` | Editorial correction |
