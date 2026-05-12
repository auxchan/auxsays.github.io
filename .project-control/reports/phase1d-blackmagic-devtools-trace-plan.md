# Phase 1D — Blackmagic DevTools Network Trace Plan

**Phase:** 1D  
**Date:** 2026-05-12  
**Purpose:** Manual browser inspection guide to discover whether an unauthenticated Blackmagic content API exists.

---

## 1. Why This Is Needed

Phase 1C static fetch probes confirmed that all Blackmagic pages return a JavaScript single-page-app shell to static fetchers. No content, version strings, or API endpoints were discoverable from the HTML alone. The content is loaded dynamically by JavaScript after page render. This plan gives the operator step-by-step instructions to inspect those network requests in a browser.

Playwright is not available in the Replit environment. This manual trace substitutes for what a headless browser with network interception would do automatically.

---

## 2. URLs to Trace

Priority order:

| Priority | URL | Purpose |
|---|---|---|
| P1 (required) | `https://www.blackmagicdesign.com/media/release/20260414-01` | The specific DaVinci 21 Beta 1 press release |
| P2 (if P1 finds an API) | `https://www.blackmagicdesign.com/media` | Press release listing/index |
| P3 (if useful) | `https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion` | DaVinci support family page |

Do NOT trace `/support/download/` — this path is disallowed in `robots.txt`.

---

## 3. Required Tools

- Browser: Chrome, Edge, or Brave (any Chromium-based browser)
- DevTools: Press F12 or right-click → Inspect
- No extensions required
- No credentials, no login, no account

---

## 4. Step-by-Step Instructions

### Step 1 — Open the press release URL

Open a new, private/incognito browser window. Navigate to:

```
https://www.blackmagicdesign.com/media/release/20260414-01
```

Do not press Enter yet.

### Step 2 — Open DevTools before the page loads

Press **F12** to open DevTools. The DevTools panel should open (usually docked to the right or bottom of the browser).

### Step 3 — Go to the Network tab

Click the **Network** tab in the DevTools panel. You should see an empty request list.

### Step 4 — Enable Preserve Log and Disable Cache

At the top of the Network panel:
- Check the box labeled **Preserve log** (keeps requests visible after page redirects)
- Check the box labeled **Disable cache** (forces fresh requests; do this before loading the page)

### Step 5 — Load the page

Now press **Enter** in the address bar (or navigate to the URL). Watch the Network tab fill with requests.

### Step 6 — Filter by Fetch/XHR

In the Network panel filter bar, click **Fetch/XHR** (or **XHR** in older DevTools versions). This filters out image, CSS, font, and other non-data requests and shows only JavaScript data fetches.

Wait for the page to finish loading. You should see a list of API requests the JavaScript made after the initial page load.

### Step 7 — Search for content-related requests

Look through the XHR/Fetch requests for anything that does NOT look like analytics, GTM, or CDN asset loading. Likely candidates are requests to:
- URLs containing `/api/` or `/content/` or `/media/` or `/release/`
- URLs returning `application/json` or `text/plain` content type
- URLs with a response body that looks like text/HTML with the press release content

### Step 8 — Inspect each candidate request

Click on a candidate request to inspect it. Check these tabs:

**Headers tab:**
- Copy the full **Request URL**
- Note the **Method** (GET is preferred for a clean API endpoint)
- Check for any **Request Headers** that look like authentication (Authorization, Cookie, X-API-Key, X-Session-Token, etc.)
- Note the **Status Code** (200 = success; 401/403 = auth required)

**Preview tab:**
- Check if the response contains meaningful text: press release title, body, date, version string

**Response tab:**
- View the raw response text
- Search for: `DaVinci`, `Resolve`, `21`, `Public Beta`, `release`, `download`

### Step 9 — Capture the key fields

For each viable candidate request, note:

| Field | What to look for |
|---|---|
| Request URL | The full URL (e.g., `https://www.blackmagicdesign.com/api/...`) |
| Method | GET or POST |
| HTTP Status | 200 = public; 401/403 = auth required |
| Content-Type | `application/json` or `text/html` |
| Response size | Large responses (>1KB) are more likely to contain content |
| Auth headers present? | Look for Authorization, Cookie, X-Token in request headers |
| Response contains version/title? | Search response preview for "DaVinci", "21", "Beta" |
| URL contains date-based ID? | e.g., `20260414-01` in the URL path |

### Step 10 — Test the endpoint directly (in a new tab)

If you find a promising URL (e.g., `https://www.blackmagicdesign.com/api/media/release/20260414-01`):

1. Copy the URL from the Request URL field
2. Open a new incognito tab
3. Paste the URL and press Enter

If the response loads successfully with press release content, this is a candidate unauthenticated API endpoint. If you get a login page or 403, it requires authentication.

### Step 11 — Also check the press release listing page

After inspecting the specific release URL, repeat steps 5–10 on:

```
https://www.blackmagicdesign.com/media
```

Look for XHR/Fetch requests that load a list of release entries. If found, check whether the response includes `href` or `url` values linking to individual releases — this would solve the release-discovery problem.

### Step 12 — Export HAR file (optional but useful for sharing)

If you want to share the network trace:
1. In the Network tab, click the **Download** icon (down arrow) or right-click and choose **Save all as HAR with content**
2. Save the `.har` file

**Before sharing**, open the HAR file in a text editor and verify it does not contain:
- Any `Authorization` header values
- Any `Cookie` header values with session tokens
- Any `Set-Cookie` response headers with session values
- Any API keys in URL query parameters

If present, redact these before sharing. Replace with `[REDACTED]`.

---

## 5. What Qualifies as a Viable API Endpoint

An endpoint is viable for Phase 1E adapter development if ALL of these are true:

| Criterion | Requirement |
|---|---|
| Public access | Returns 200 without any authorization headers or session cookies |
| Content present | Response body contains the press release title, body text, and/or version string |
| Stable URL pattern | URL contains the date-based ID (`20260414-01`) and follows a predictable pattern |
| No anti-bot check | Does not return 403 or CAPTCHA when accessed from a plain browser with no session |
| Not disallowed by robots.txt | The path is not listed under `disallow:` in `https://www.blackmagicdesign.com/robots.txt` |

Current `robots.txt` disallows:
- `/support/download/`
- `/api/print/to-pdf/*`
- `/api/print/to-txt/*`

All other `/api/` paths are not currently disallowed for well-behaved bots with `crawl-delay: 1`.

---

## 6. What Disqualifies an Endpoint

An endpoint is NOT viable if any of these are true:

| Disqualifier | Action |
|---|---|
| Requires `Cookie` header with session token | Deferred — would require session management in adapter |
| Requires `Authorization` header | Deferred — would require credential management |
| Returns a 403 for fresh requests (no session) | Not publicly accessible |
| Response is the same SPA shell HTML | Content is not in this endpoint — keep looking |
| Endpoint is in the `robots.txt` disallow list | Do not use |
| Response body contains no version/title/body text | This is a non-content request (analytics, CDN, etc.) |
| URL contains temporary tokens or UUID session IDs | Endpoint is session-specific and not stable |

---

## 7. What to Document and Report

After completing the trace, document these findings and provide them for Phase 1E scoping:

1. **Primary press release endpoint:** Full URL of the XHR/Fetch request that loads press release content (if found)
2. **Authentication required?** Yes/No. If yes, what type (cookie, bearer token, API key)?
3. **Response format:** JSON / HTML / other
4. **Content includes:** title / body / date / version / download URL (check each)
5. **Listing endpoint:** URL that loads the list of press releases (if found)
6. **robots.txt compliance:** Is the discovered endpoint disallowed?
7. **Stability assessment:** Does the URL contain the date-based ID? Does it appear to be a stable pattern?

---

## 8. Fallback: If No API Endpoint Is Found

If all XHR/Fetch requests are analytics, CDN, or GTM traffic and no content API is found, the content is almost certainly in the initial JavaScript bundle (rendered by the SPA framework on client-side without additional API calls after load). In this case:

1. **Phase 1E path:** Playwright headless rendering (requires explicit CI/CD dependency decision)
2. **Current fallback:** Continue `manual_watch` / `official_only` — honest and correct state

If this happens, document:
- All XHR/Fetch URLs observed (to confirm no content API)
- Whether the page renders the press release content in the browser (confirms Playwright would work)
- Which CSS selector the press release body appears under (for Playwright adapter targeting)

---

## 9. Do Not Share These

When reporting trace results:
- Do NOT share browser session cookies
- Do NOT share Authorization header values
- Do NOT share any tokens, keys, or credentials from request headers
- Do NOT share any personally identifiable information visible in the trace

The only information needed is: the request URL, method, status code, content-type, and whether the response body contains press release content. All of this is publicly observable from a fresh browser session with no account.
