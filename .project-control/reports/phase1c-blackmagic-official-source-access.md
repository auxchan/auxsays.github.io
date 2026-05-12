# Phase 1C — Blackmagic Official Source Access Feasibility

**Phase:** 1C  
**Date:** 2026-05-12  
**Probe script:** `.project-control/prototypes/blackmagic-source-access-probe.py`  
**Output file:** `.project-control/probe-output/phase1c/blackmagic-static-fetch-result.json`  
**Read-only:** Yes. No records, state files, or evidence rows were modified.

---

## 1. Sources Tested

| URL | Purpose | HTTP Status | Response Length |
|---|---|---|---|
| `https://www.blackmagicdesign.com/media/release/20260414-01` | Specific press release (DaVinci Beta 1) | 200 | 67,212 chars |
| `https://www.blackmagicdesign.com/media` | Press release listing/index | 200 | 63,972 chars |
| `https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion` | DaVinci support center | 200 | 138,465 chars |
| `https://www.blackmagicdesign.com/support/download/20260414-01` | Download page for specific release | 200 | 137,343 chars |
| `https://www.blackmagicdesign.com/robots.txt` | Crawl policy | 200 | 1,745 chars |
| `https://www.blackmagicdesign.com/sitemap.xml` | Sitemap | **404** | 0 chars |
| `https://www.blackmagicdesign.com/sitemap_index.xml` | Sitemap index | **404** | 0 chars |

Playwright / headless browser: **Not available in this Replit environment.** Only static (urllib) fetches were possible.

---

## 2. Static Fetch Results

### 2.1 Press Release Specific URL (`/media/release/20260414-01`)

**Result: JS rendering wall confirmed.**

- HTTP 200, but page title is `"Media | Blackmagic Design"` — the generic media section title, not the press release title.
- H1 tags found: `Products`, `Support`, `Community`, `Company` — these are navigation items, not press release content.
- The canonical URL is set correctly to `https://www.blackmagicdesign.com/media/release/20260414-01`, confirming the server acknowledges the URL as valid. But it delivers the same single-page-app shell regardless of the specific release path.
- **129 `/media/release/` link tags found** — but these are `<link rel="alternate" hreflang="xx">` internationalization tags pointing to regional versions of this same URL (`/ar/media/release/20260414-01`, `/au/media/release/...`, etc.). They are **not** links to other press releases and are **not** RSS feeds. The probe's broad alternate-tag detection incorrectly classified these as RSS. There is no actual RSS feed.
- 9 inline scripts found. No API endpoint hints in any script. The only embedded config discovered is `dataLayer.push(arguments)` — a Google Tag Manager stub, not a content API.
- No JSON-LD structured data blocks.
- **Zero version strings** matching any DaVinci Resolve version pattern.
- **Zero download links**.

**Conclusion:** The static HTML for the press release URL contains no useful content. It is a single-page-app shell.

### 2.2 Press Release Listing (`/media`)

**Result: Identical shell; no release link index.**

- Same generic shell page (`"Media | Blackmagic Design"` title, navigation H1s only).
- Only 1 `/media/release/` href found: `/media/release/archive` — the archive landing page. All other release links are absent from static HTML; the release list is JS-populated.
- Zero version strings. Zero download links. No JSON-LD.

**Conclusion:** The listing page does not expose a static index of press releases. Release links are dynamically loaded. There is no static way to discover the list of releases without executing JavaScript.

### 2.3 Support/DaVinci Family Page (`/support/family/davinci-resolve-and-fusion`)

**Result: Generic support center shell; no version or download data.**

- Title: `"Support Center | Blackmagic Design"`. Canonical redirects to `/support` (not the DaVinci-specific URL), suggesting the route is a JS-rendered subpage of the support SPA.
- 209 links — all navigation; zero DaVinci-version links.
- Zero version strings. Zero download links.

**Conclusion:** The support family page is also a client-side rendered SPA shell. No useful version or download data accessible via static fetch.

### 2.4 Download Page (`/support/download/20260414-01`)

**Result: Generic support shell; same as support page.**

- Title: `"Support Center | Blackmagic Design"`. Identical shell to the support page.
- **Note:** `robots.txt` explicitly disallows scraping the `/support/download/` path:

```
disallow: /support/download/
```

This means even if the download page were statically accessible, the crawl policy directs automated tools not to access it.

### 2.5 robots.txt

**Content is highly informative:**

```
# Well behaved bots
user-agent: *
crawl-delay: 1
allow: /images/*.jpg$
...
disallow: /support/download/
disallow: /api/print/to-pdf/*
disallow: /api/print/to-txt/*
disallow: /*?rendering-to-pdf=true
disallow: /*ecommerce/
disallow: /*edelivery/
disallow: /*checkout/
```

Key observations:
1. **`/support/download/` is explicitly disallowed** for all bots. This removes the download page as a legitimate scrape target.
2. **`/api/` namespace exists** — the disallow rules for `/api/print/to-pdf/*` and `/api/print/to-txt/*` confirm that Blackmagic uses an internal API path prefix. However, these are document-rendering endpoints, not release-note data endpoints.
3. **`crawl-delay: 1`** — Blackmagic permits well-behaved crawlers with a 1-second delay between requests.
4. **No media/release or support paths are disallowed** for well-behaved bots — the `/media/` and `/support/family/` paths are permitted for crawling. The issue is not a policy block; it is a technical architecture issue (SPA rendering).

### 2.6 Sitemaps

Both `/sitemap.xml` and `/sitemap_index.xml` return **HTTP 404**. Blackmagic does not publish a publicly accessible XML sitemap. There is no sitemap-based release discovery available.

---

## 3. Playwright-Rendered Result

**Playwright is not available in this Replit environment.**

The `playwright` Python package is not installed. The `playwright` CLI is not available. No headless browser probe was possible.

What a headless browser probe would need to confirm:
1. Whether the press release content (title, body, version string, date) is present in the DOM after JavaScript execution.
2. What CSS selector addresses the rendered press release body.
3. Whether the page requires any session state (cookies, tokens) beyond JS execution.
4. What network requests the JavaScript makes to fetch the press release content.

This remains the primary unconfirmed assumption in the Phase 1D Blackmagic adapter design.

---

## 4. Internal API / Network Endpoint Findings

**No API endpoints were discovered via static analysis.**

The inline JavaScript on the Blackmagic pages contains only:
- Google Tag Manager bootstrap (`dataLayer.push(arguments)`)
- No `fetch()` calls with hardcoded URLs
- No `XMLHttpRequest` patterns with API paths
- No `baseUrl`, `apiUrl`, or `endpoint` configuration objects

The `/api/` prefix confirmed in `robots.txt` (`/api/print/to-pdf/*`) suggests an internal API exists, but these are document rendering utilities, not release-note data endpoints.

**Expert judgment:** The release content is almost certainly loaded via a JavaScript `fetch()` call to an internal API endpoint. The fact that no endpoint is visible in the static page shell's inline scripts suggests it is either:
1. Bundled into a separate JS chunk file that the SPA loads dynamically (not visible in the initial HTML)
2. Loaded from a CDN-hosted JS bundle

Discovering the actual endpoint requires either:
- A headless browser with network request interception (Playwright `page.on('request', ...)`)
- Manual browser dev tools inspection (not automatable)

---

## 5. Whether Release Title / Date / Body / Version Were Accessible

| Field | Static fetch accessible | Notes |
|---|---|---|
| Release title | **No** | Page shell title is generic `"Media | Blackmagic Design"` |
| Release date | **Partial** — URL only | Date `20260414` is parseable from the URL path; not in page HTML |
| Release body | **No** | Zero content in static HTML; JS rendering required |
| Version string | **No** | No version text found anywhere in static page |
| Download URL | **No** | No download links in any static page |
| Product name | **No** | Not in static HTML; must be in rendered content |

The URL date (`20260414`) is the only reliably extractable structured datum from the press release URL without headless rendering, and it does not require page fetching at all.

---

## 6. Corrected Understanding of "RSS Feeds" Found

**There is no Blackmagic RSS feed.** The probe initially reported a large number of "RSS links" — this is a false positive. All `<link rel="alternate" hreflang="xx">` tags (used for multilingual page indexing) were incorrectly classified as RSS by the probe's broad alternate-link detection. Blackmagic does not publish an RSS or Atom feed for press releases.

Corrected RSS discovery result: **0 true RSS/Atom feeds found.**

---

## 7. Recommendation: Which Strategy for Phase 1D

In priority order, from most to least recommended:

### Option A — Headless browser (Playwright) — RECOMMENDED, but requires dependency decision

**Rationale:** This is the only approach that can extract the actual press release content from the rendered DOM. If JS execution confirms that content is present and a stable CSS selector exists, this is the cleanest path.

**Requirements:**
- Add `playwright` Python package and browser binaries to the toolchain
- Run `playwright install chromium` (or equivalent)
- Implement a `blackmagic_media` adapter that uses `playwright.sync_api` or `playwright.async_api`
- Keep requests minimal and polite (1 release per run, crawl-delay: 1 honored)
- URL construction strategy: build press release URLs from date-based ID (see Option A2 below)

**URL construction problem:** Even with headless rendering, there is still no static index of press release URLs. Blackmagic uses date-based IDs (`20260414-01`, `20260414-02` etc.) with no enumerable index. A headless adapter would need to:
- Either poll the `/media` listing page after JS render to discover new release links
- Or construct URLs by date convention and probe for 200 responses

**Risk:** Playwright adds a significant dependency (browser binary, ~150MB). GitHub Actions runners support it; the local Replit environment does not currently have it. Production CI/CD must be updated to install it.

### Option B — Internal API endpoint discovery — HIGHEST value if confirmed, HIGH risk

**Rationale:** If the press release content is fetched by the JavaScript from an internal, unauthenticated endpoint, that endpoint would be cleaner than HTML parsing and would not require headless rendering.

**How to discover:** Manual browser dev tools → Network tab → filter by XHR/Fetch → visit a press release URL → observe requests. The endpoint may be something like:
- `https://www.blackmagicdesign.com/api/media/release/20260414-01` (guessed)
- `https://api.blackmagicdesign.com/content/releases/...` (guessed)
- A GraphQL or REST endpoint serving release JSON

**Risk:** If the endpoint requires session cookies, dynamic tokens, or changes without notice, the adapter will break silently. Not appropriate for production ingestion without confirmed stability.

**This must be confirmed by manual browser dev tools inspection before any Phase 1D implementation.**

### Option C — Third-party press release mirrors — NOT RECOMMENDED

Some PR services (BusinessWire, GlobeNewswire, PR Newswire) occasionally mirror Blackmagic press releases as static HTML. These should not be used as the primary source per AGENTS.md source classification. However, they could serve as a fallback signal to detect when a new Blackmagic release exists (without depending on Blackmagic's JS-rendered pages for the announcement itself).

### Option D — `manual_watch` only — FALLBACK, lowest implementation risk

If headless rendering is not appropriate for the CI/CD environment and no clean API endpoint is found, DaVinci should remain `manual_watch` indefinitely. The current state (official-source-linked, body not captured, 0 evidence rows) is accurate and honest. Do not implement a broken adapter just to have one.

---

## 8. Implementation Risks

| Risk | Severity | Notes |
|---|---|---|
| Playwright dependency not in CI/CD | **High** | GitHub Actions runner must install browser binaries on every run; adds build time and storage |
| JS render wall changes selector | **Medium** | CSS selectors in a SPA can change at any deploy; adapter needs resilient error handling |
| API endpoint is authenticated | **High** | If the internal API requires a session token, it cannot be used without credentials |
| API endpoint is undocumented / unstable | **High** | Undocumented internal APIs change without notice; any adapter depending on one will break silently |
| `/support/download/` disallowed by robots.txt | **Low (already scoped out)** | This path is now ruled out as a source target |
| No sitemap or RSS for release discovery | **Medium** | URL construction by date convention is fragile; must handle gaps in numbering and missing releases |
| Blackmagic issue numbering is sequential | **Unknown** | Whether `20260414-01`, `20260414-02`, etc. are used; must verify before building URL construction logic |

---

## 9. Summary Verdict

Blackmagic's website is a JavaScript single-page application. All content pages — press releases, support, download — serve a generic shell to static fetchers. No content, version strings, download links, or structured metadata are accessible via static fetch.

No RSS feed exists. No sitemap exists. The `/support/download/` path is robots.txt-disallowed. No API endpoints were discoverable via static script analysis.

The only viable paths to content extraction are:
1. **Headless browser rendering** (requires Playwright dependency decision)
2. **Internal API endpoint discovery** (requires manual browser dev tools work; cannot be done from Replit without a browser)

**Recommendation for Phase 1D:** Do not implement a Blackmagic adapter until at least one of these is confirmed viable:
- A successful headless browser test run confirms content is extractable after JS render
- A manual network trace confirms an unauthenticated API endpoint serves release content

Until then, `manual_watch` + `official_only` is the correct and honest state for DaVinci Resolve records. The Phase 1B correction that set this state was the right call.
