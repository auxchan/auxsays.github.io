# DaVinci Resolve — Official Source Feasibility Assessment

**Status:** Research document — Phase 1A  
**Date:** 2026-05-11  
**Scope:** Assessment of Blackmagic Design's public release pages as an ingestion source. Research only — no scraping enabled, no production changes.

---

## 1. Executive Summary

Automated ingestion of DaVinci Resolve release data from Blackmagic Design's official site is **feasible in principle but requires a purpose-built parser**. The current generic `html_changelog` adapter cannot succeed against Blackmagic's page structure. The `/media` listing page is JavaScript-rendered and the individual press release pages use non-semantic HTML. Five recorded attempts have all returned `official-source-parser-failed`.

**Verdict:** Medium feasibility. A narrow, DaVinci-specific adapter is the correct path. Broad scraping of `/media` is not safe for unattended runs with the current tooling.

---

## 2. URL Structure Analysis

### 2.1 Listing page
`https://www.blackmagicdesign.com/media`

- JavaScript-rendered press release index.
- `requires_javascript: false` is set in config — this is likely inaccurate. The page content is loaded dynamically; a static HTTP fetch returns a near-empty HTML shell.
- The generic `html_changelog` adapter's `<a>` link scan finds no `/changelog/`, `/release-notes/`, or `/releases/` paths in a static fetch.
- **Result: Zero candidate links extracted.**

### 2.2 Individual press release pages
Pattern: `https://www.blackmagicdesign.com/media/release/{YYYYMMDD}-{NN}`

Example: `https://www.blackmagicdesign.com/media/release/20260414-01`

- Static HTML — the press release body itself does not require JavaScript.
- Body content is inside custom `<div>` structures, not `<article>` or `<main>` tags.
- `body_from_html()` in `patch_ingest.py` and `html_changelog.py` both look for `<article>` first, then `<main>`. Neither matches. Fall-through yields the full stripped page text which does not pass `body_matches_record()` (fails length threshold or version match).
- **Result: `official-source-parser-failed` on all 5 recorded attempts.**

### 2.3 Support/download page
`https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion`

- Listed as `secondary_official_url` in config.
- Contains download links and version information.
- Not examined in detail in this research phase, but the structure is static HTML with download cards.

---

## 3. What a Working Parser Would Need

To successfully extract DaVinci release data, a parser must:

| Requirement | Current State | Gap |
|---|---|---|
| Discover individual release URLs without JavaScript | Not possible from `/media` listing | Need known URL pattern or RSS/sitemap alternative |
| Extract body from `<div>`-structured press release pages | Fails — no `<article>`/`<main>` match | Need custom selector for Blackmagic's div structure |
| Match body to product/version for integrity check | Fails downstream of extraction gap | Blocked by above |
| Extract structured version string | Not reached | Would need regex against page title |
| Extract release date | Not reached | Date in title or URL (YYYYMMDD prefix) |
| Extract download URL | Not reached | Download URLs are on the support page, not press releases |
| Handle rate limiting | Not tested | Unknown; no auth required for public pages |

---

## 4. Alternative Source Paths

### 4.1 RSS / Atom feed
Blackmagic does not publish a documented RSS or Atom feed for DaVinci release announcements. No feed URL is present in the config. This would need external verification.

### 4.2 URL pattern construction
Press release URLs follow a predictable pattern: `YYYYMMDD-NN`. If Blackmagic publishes a new release on a known date, the URL can be constructed directly rather than discovered from the listing page. This is a viable narrow approach:
- Requires knowing the release date (from Blackmagic forum announcement, community post, or manual watch).
- Fetches a single known URL directly.
- Bypasses the JavaScript listing page entirely.
- **Feasibility: High** for targeted single-record ingestion.

### 4.3 Blackmagic forum
`https://forum.blackmagicdesign.com/` — Blackmagic staff post official release threads here. These are static HTML, searchable, and contain the version number and release notes inline.
- Feasibility: Medium (requires forum thread discovery; HTML structure is forum-specific).
- Could serve as both official source AND community evidence source.

### 4.4 GitHub mirror (community-maintained)
Some community members maintain unofficial GitHub repositories tracking DaVinci changelogs. These would not count as official sources but could supplement body capture.

### 4.5 Blackmagic support download page
`https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion` contains version-labeled download cards. This page is static HTML and would yield version strings and download URLs, though not release note body text.

---

## 5. `blackmagic_media_keyword_filter` Parser Profile

The config specifies `parser_profile: blackmagic_media_keyword_filter`. **This profile is not implemented in `html_changelog.py`.**

The adapter's dispatch in `fetch()`:
```python
if profile.startswith("adobe_") and profile.endswith("_release_notes"):
    return _fetch_adobe_release_notes(source, limit=limit)
# otherwise: fall through to generic link-filter logic
```

The `blackmagic_media_keyword_filter` name falls through to the generic path. Implementing this profile would require a new branch in `html_changelog.py` that:
1. Constructs or discovers release URLs using the YYYYMMDD pattern.
2. Fetches individual press release pages.
3. Extracts body using a Blackmagic-specific div selector.
4. Filters by keywords (release, update, changelog, patch, version, beta, driver, studio, copilot — as listed in the config keywords array).

**Estimate:** A purpose-built Blackmagic parser branch is approximately 60–100 lines of additional code in `html_changelog.py` plus integration tests.

---

## 6. Extractability Assessment (Per Config Field)

| Field | Config Assessment | Research Assessment | Gap |
|---|---|---|---|
| version | `false` | Extractable from page title or URL date segment | Config underestimates feasibility |
| release_date | `true` | URL date prefix `YYYYMMDD` is reliable | Achievable |
| title | `true` | H1 or title tag on press release page | Achievable |
| release_note_body | `true` | Blocked by div structure | Requires custom selector |
| download_url | `true` | Not on press release page; on support page | Requires two-page fetch strategy |
| file_size | `false` | Not publicly exposed | Confirmed absent |
| checksum | `false` | Not publicly exposed | Confirmed absent |
| known_issues | `false` | Not structured | Confirmed absent |
| platform_specific_installers | `false` | Listed on support page by OS | Partially extractable |
| archived_release_history | `false` | Press release URLs are stable; history accessible by URL | Partially accessible |

---

## 7. Risk Assessment

| Risk | Level | Notes |
|---|---|---|
| JavaScript dependency on listing page | High | Static fetch returns shell; must avoid `/media` as entry point |
| HTML structure change on press release pages | Medium-High | Div-based layout; no semantic anchors |
| Rate limiting / blocking | Unknown | No documented policy; low-frequency polling (12h) should be safe |
| Version string ambiguity | Medium | "DaVinci Resolve 21 Public Beta 1" is not a clean semver string |
| False positives from keyword filter | Medium | `/media` contains non-release press releases; keyword filter is necessary |
| `requires_javascript: false` inaccuracy | Medium | Config may cause confusion in adapter logic |

---

## 8. Recommendation (Research Phase)

For Phase 1B or later work:

1. **Do not enable the current adapter against `/media`** — it cannot discover links from a JS-rendered page via static fetch.
2. **Implement `blackmagic_media_keyword_filter` as a URL-construction strategy**, not a link-discovery strategy. Given a known release date, construct `YYYYMMDD-01` URL and fetch directly.
3. **Add a custom body selector** for Blackmagic press release `<div>` structure to `html_changelog.py`.
4. **Use `secondary_official_url` (support/download page) as a separate record-enrichment step** for download URL capture.
5. **Retire `fetch_davinci_updates.py`** — it is a dead stub that does not participate in the current architecture and could cause confusion.
6. **Correct `requires_javascript`** in config from `false` to `true` for the `/media` listing page.
