# Phase 1B — DaVinci Official-Source Probe Results

**Date:** 2026-05-12  
**Probe script:** `.project-control/prototypes/davinci-probe-dry-run.py`  
**Output file:** `.project-control/probe-output/davinci-official-probe-20260414-01.json`  
**Read-only:** Yes. No records or state files were modified.

---

## 1. URL Probed

**Press release:** `https://www.blackmagicdesign.com/media/release/20260414-01`  
**Listing page:** `https://www.blackmagicdesign.com/media`  
**Support page:** `https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion`

---

## 2. HTTP Status

| URL | HTTP Status | Fetch OK | Response length |
|---|---|---|---|
| Press release (`/media/release/20260414-01`) | **200** | Yes | 67,212 chars |
| Listing page (`/media`) | **200** | Yes | 63,972 chars |
| Support page (`/support/family/davinci-resolve-and-fusion`) | **200** | Yes | 138,465 chars |

All three URLs are reachable via static fetch. No connection errors, timeouts, or blocked requests.

---

## 3. Static Fetch — Did It Work?

**Static fetch succeeded for all three URLs.** The server returns HTML content without requiring JavaScript execution.

**However, the press release URL does not serve the expected content.** Despite returning HTTP 200, the page title is `"Media | Blackmagic Design"` and the H1 is `"Blackmagic Design News Archive"`. This is the *generic media archive index page*, not the specific press release for April 14, 2026.

**Interpretation:** The URL `https://www.blackmagicdesign.com/media/release/20260414-01` appears to be rendered client-side — the server returns the same generic shell page regardless of the specific release path. The actual press release content is loaded dynamically via JavaScript after the page shell loads. Static fetch therefore receives the shell but not the content.

This confirms why all five prior `official-source-parser-failed` attempts in the record's `official_source_attempts` log returned empty bodies — it is not a parser selector issue; the content itself is not present in the static HTML.

---

## 4. Current `article`/`main` Selector Path

| Selector | Found | Body length | Passes body-match check |
|---|---|---|---|
| `<article>` | **No** | — | — |
| `<main>` | **No** | — | — |

Neither selector is present in the returned HTML. The page uses a `<div>`-based structure. This explains all five `official-source-parser-failed` results.

---

## 5. Custom Div Selectors

| Pattern | Found | Body content | Passes check |
|---|---|---|---|
| `press-release`, `article-body`, `release-content`, `content-body`, `editorial`, `media-body` | **No** | — | No |
| `body`, `content`, `main-content`, `entry-content` | **Yes** | 74 chars — PR contact info only | **No** |
| `<section class="content|body|main">` | **No** | — | No |

The only div match found was a PR contact block:

```
Terry Frechette
+1 408 954 0500 Ext. 321
pr-usa@blackmagicdesign.com
```

This is the contact information embedded in the page shell, not the press release body. Body length is 74 characters — far below the 300-char minimum for `body_matches_record()`. The div selector approach also fails for the same reason: the content is not present in the static HTML.

---

## 6. Extracted Page Title, H1, Date, Body Excerpt

| Field | Value |
|---|---|
| `page_title` | `"Media | Blackmagic Design"` |
| `h1` | `"Blackmagic Design News Archive"` |
| `date_extracted` | `null` — no date found in first 8,000 characters of static HTML |
| `url_date_prefix` | `"20260414"` — successfully parsed from URL path |
| Body excerpt | PR contact block only (74 chars) |

The URL date prefix (`20260414`) is the **only reliably extractable structured datum** from the URL itself — and it does not require page fetch at all.

---

## 7. Whether Version Text Was Found

**No version text was found in the press release page.**

The page shell contains navigation, PR contact, and generic news archive markup. No strings matching "DaVinci Resolve 21", "Public Beta", or any version pattern were found in the static HTML.

---

## 8. Whether Release Body Extraction Is Feasible via Static Fetch

**Finding: Release body extraction via static fetch of the press release URL is NOT feasible in its current form.**

The Blackmagic `/media/release/{date}-{index}` URL structure is client-side rendered. The server delivers a generic shell (`Media | Blackmagic Design`) for all release URLs. The actual press release content — the announcement text, the download links, the feature list — is loaded after JavaScript execution.

**Options:**

| Approach | Feasibility | Notes |
|---|---|---|
| Static fetch of `/media/release/YYYYMMDD-NN` | **Not feasible** | Returns generic shell, not content |
| Static fetch of `/media` listing | Partial | 213 anchors found, 0 are `/media/release/` links — likely JS-populated |
| Headless browser (Selenium, Playwright) | **Feasible** | Would receive rendered content; not in current toolchain |
| API endpoint discovery | Unknown | No public API documented; Blackmagic may have an internal REST endpoint that the frontend calls |
| Alternative source (press PDF, email release, third-party mirror) | Possible | Some vendors publish PDF press releases; not investigated |

---

## 9. Whether the Support/Download Page Is Useful

**Finding: The support page also does not expose useful version-structured content via static fetch.**

```
support_page_probe:
  http_status: 200
  fetch_ok: true
  response_length_chars: 138,465
  version_strings_found: []
  download_links_found: 0
```

Despite being 138,465 characters, the support page returned zero version strings matching "DaVinci Resolve XX" and zero download links with `.zip`, `.dmg`, `.exe`, or other installer extensions. This is consistent with a page that loads download buttons and version info via JavaScript calls to a backend API.

The support page is **not a viable static-fetch source** for version or download information.

---

## 10. Recommended Selector/Parser Strategy for Phase 1C

Given that both the press release page and the support page are client-side rendered, the following options exist for Phase 1C, in priority order:

### Option A — Headless browser fetch (recommended)
Use Playwright or Selenium to fetch and render the press release URL before extracting content. After JS execution, the page should contain actual press release text. Requires adding a headless browser dependency to the toolchain.

**Estimated selector after JS render:**
Based on typical Blackmagic press release structure from the static PR contact div found, likely:
- A `<div class="content">` or `<div class="body">` wrapping the actual article text (larger instance than the 74-char PR contact block)
- Or a `<p>` sequence within the article section

These would need to be confirmed with an actual headless browser run.

### Option B — Discover the underlying API endpoint (research required)
The frontend JavaScript almost certainly fetches the press release content from an API (e.g. `/api/v1/releases/20260414-01.json` or similar). Intercepting this request with browser dev tools would identify the API endpoint. If the endpoint is unauthenticated, it would be a cleaner source than HTML parsing.

### Option C — Blackmagic RSS / sitemap
Blackmagic may publish a press release RSS feed or XML sitemap that is statically accessible and includes release URLs with dates. Not investigated in Phase 1B.

### Option D — Third-party mirrors (not recommended for AUXSAYS)
Some press release services mirror Blackmagic announcements as static HTML. These should not be treated as the official source per AGENTS.md source classification rules.

---

## 11. Failure Modes

| Failure mode | Status | Notes |
|---|---|---|
| HTTP connection failure | Not observed | All URLs returned 200 |
| JavaScript rendering wall | **Confirmed** | Press release and support pages are JS-rendered |
| Wrong CSS selector | Confirmed (secondary) | Even if content were present, no standard selector matches |
| Redirect to generic page | **Confirmed** | `/media/release/20260414-01` serves generic archive shell |
| Rate limiting or blocking | Not observed in this probe | Single request per URL; no 403/429 received |

---

## 12. Version Normalization Probe Results

The version normalization probe tested 10 sample strings against the current and proposed relaxed patterns:

| Input | Current pattern matches | Relaxed pattern matches |
|---|---|---|
| `DaVinci Resolve 21 Public Beta 1` | **No** | **No** |
| `DaVinci Resolve 21 Public Beta 2` | **No** | **No** |
| `DaVinci Resolve 21` | **No** | **No** |
| `DaVinci Resolve 21.0.1` | **No** | **No** |
| `DaVinci Resolve 20.0.0` | **No** | **No** |
| `DaVinci Resolve 19.1` | **No** | **No** |
| `v21.0.1` | Yes | Yes |
| `21` | **No** | Yes |
| `21.0.1` | Yes | Yes |
| `21 Public Beta 1` | **No** | Yes |

**Key finding:** All inputs that begin with "DaVinci Resolve " fail **both** patterns because neither regex handles a text prefix before the version number. The relaxed pattern (`+` → `*`) only helps with bare version strings. A full pre-strip of the product name prefix is required before regex matching.

This is more severe than the Phase 1A analysis anticipated — the relaxed pattern alone is insufficient. The adapter must strip the "DaVinci Resolve " prefix before applying `version_pattern`.

---

## 13. Whether This Supports Building a Blackmagic-Specific Adapter

**Finding: A static-fetch Blackmagic adapter is not viable without headless browser support. A headless adapter is technically feasible but requires a new dependency.**

The current adapter infrastructure (`html_changelog.py`, `html_blog.py`) is designed for sites that serve press release content in static HTML. Blackmagic's site does not. A custom `blackmagic_media` adapter would need to either:

1. **Use headless browser rendering** — adds Playwright/Selenium dependency, significant complexity
2. **Target an internal API endpoint** — requires discovery work (browser dev tools), potentially fragile if endpoint changes
3. **Source content from a third-party static mirror** — not acceptable per AGENTS.md

Additionally, the version normalization problem (prefix stripping required) must be solved before any adapter can correctly match the extracted version string against the config pattern.

**Phase 1C recommendation:** Before implementing an adapter, run a single headless browser fetch of the press release URL to confirm:
(a) content is present after JS render, and
(b) a reliable CSS selector can extract it.

Only if both are confirmed should a headless adapter be scoped for implementation.
