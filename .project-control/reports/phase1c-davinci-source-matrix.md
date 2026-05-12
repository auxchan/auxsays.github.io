# Phase 1C — DaVinci Evidence Source Matrix

**Phase:** 1C  
**Date:** 2026-05-12  
**Probe script:** `.project-control/prototypes/davinci-forum-source-probe.py`  
**Output file:** `.project-control/probe-output/phase1c/davinci-source-matrix.json`  
**Read-only:** Yes. No records, state files, or evidence rows were modified.

---

## 1. Source Discovery Overview

Five source categories were investigated:
1. Blackmagic Design official forum (DaVinci Resolve sections)
2. Reddit r/davinciresolve — HTML
3. Reddit r/davinciresolve — JSON API (old Reddit format)
4. Reddit r/davinciresolve — RSS/Atom feed

An additional category (third-party community sources) is assessed based on general knowledge and architecture rationale; no targeted probe was run for these.

---

## 2. Source Matrix

### 2.1 Blackmagic Design Official Forum

| Attribute | Value |
|---|---|
| **Source name** | Blackmagic Design Forum |
| **URL** | `https://forum.blackmagicdesign.com/` |
| **DaVinci section URL** | `https://forum.blackmagicdesign.com/viewforum.php?f=21` |
| **Beta relevance** | High — dedicated beta discussion boards exist |
| **Stable relevance** | High — primary official support/report channel |
| **Pages public?** | **No — HTTP 403 for all requests** |
| **Search available?** | No — search also returns 403 |
| **Static fetch works?** | **No** — server actively blocks non-browser user-agents (hard 403, zero body) |
| **Playwright required?** | Possible workaround, but session/cookie requirements likely |
| **Login required?** | Possibly not for reading, but bot block is at the UA level |
| **Version-specific search?** | Not testable — 403 blocks all access |
| **Anti-scraping risk?** | **Extreme** — hard 403 on all requests, zero body returned |
| **Evidence-backed counts possible?** | **No — not currently accessible** |
| **Recommended role** | Deferred — cannot access without either Playwright + session simulation or API access |

**Probe result:**
All three URLs probed (`/`, `/viewforum.php?f=21`, `/search.php`) returned **HTTP 403 with empty body**. This is not a soft "login wall" — the forum actively returns 403 to all requests that do not present browser-like session credentials. There is no public content accessible to a bot-identified user-agent.

**Expert judgment:** The Blackmagic forum uses phpBB software. phpBB forums can optionally require login to read content. The 403 response (vs. 302 redirect to login) suggests either:
1. The forum requires session cookies that are not present on a fresh request, or
2. The server identifies and blocks non-browser user-agents at the request level

Either way, scraping the Blackmagic forum without a browser session is not feasible. Playwright with browser fingerprinting might work, but this approaches active bot-block circumvention — which is explicitly out of scope and contrary to AGENTS.md principles. **Do not target this source.**

---

### 2.2 Reddit r/davinciresolve — HTML

| Attribute | Value |
|---|---|
| **Source name** | Reddit r/davinciresolve (HTML) |
| **URL** | `https://www.reddit.com/r/davinciresolve/` |
| **HTTP Status** | **403** |
| **Static fetch works?** | **No** — Reddit blocks non-browser user-agents for HTML |
| **Login required?** | No (content is public), but Reddit blocks bots from HTML access |
| **Anti-scraping risk?** | **High** |
| **Recommended role** | Not viable via HTML scraping |

Reddit has progressively tightened access for non-browser requests. The HTML interface returns 403 for typical bot user-agents.

---

### 2.3 Reddit r/davinciresolve — JSON API (old Reddit / `.json` format)

| Attribute | Value |
|---|---|
| **Source name** | Reddit r/davinciresolve (JSON API) |
| **URL** | `https://www.reddit.com/r/davinciresolve/new.json` |
| **HTTP Status** | **403** |
| **Static fetch works?** | **No** — Reddit's old JSON API is now blocked for unauthenticated programmatic access |
| **Search available?** | No — search also returns 403 |
| **Recommended role** | Not viable without Reddit OAuth2 API access |

Reddit's old `.json` endpoints were previously accessible without authentication. They now require OAuth2 credentials. This changed following Reddit's 2023 API policy update, which significantly restricted unauthenticated programmatic access. Any AUXSAYS DaVinci evidence collector that targets Reddit will require Reddit OAuth2 API credentials.

**OAuth2 path assessment:**
- Reddit's OAuth2 API is publicly available and supports read-only access
- Access requires creating a Reddit app and obtaining a client ID/secret
- Rate limits apply (60 requests/minute for free tier)
- Read-only OAuth2 access is appropriate for evidence collection
- This is a valid Phase 1D architecture option, but requires credentials (outside Phase 1C scope)

---

### 2.4 Reddit r/davinciresolve — RSS/Atom Feed

| Attribute | Value |
|---|---|
| **Source name** | Reddit r/davinciresolve (RSS/Atom) |
| **URL** | `https://www.reddit.com/r/davinciresolve/.rss` |
| **HTTP Status** | **200** |
| **Response format** | Atom XML, 60,348 chars |
| **Items in feed** | 26 |
| **Static fetch works?** | **Yes** — publicly accessible without authentication |
| **Structured/parseable?** | Yes — standard Atom XML |
| **Recommended role** | **Secondary / detection signal** — not primary evidence source |

**Feed content analysis:**
The RSS feed delivers the 26 most recent posts from r/davinciresolve. Current post sample:
- "May Dev/Tools Monthly Megathread - for tool builders"
- "r/davinciresolve Monthly Hardware Thread"
- "YouTube ProRes 422 HQ vs H624. Two Pass enable or disable?"
- "black boxes/artefacts glitching pls help"
- "Can someone help me to get this look?"
- "Anyone face critical errors and were unable to load an auto backup or save any project in a specific project library on a specific SSD?"
- "PC Slow Response Randomly"

**Observations:**
1. **No version-specific posts in current feed** — the feed does not currently contain posts referencing DaVinci Resolve 21 Beta 1 by version. This is expected; the beta was released April 14, 2026, and the community has moved on.
2. **Post body is truncated in RSS** — Atom entries contain only partial post content. Full post bodies require fetching individual post URLs (which would require HTML access or Reddit API access — both currently blocked).
3. **Feed is not searchable** — the RSS feed is always the last N posts; version-specific content is not filterable via the feed URL alone.
4. **Version references appear by pattern, not structured field** — version mentions appear in freetext titles and bodies; classification requires regex matching on post titles and bodies.
5. **Feed covers all posts** — includes general DaVinci questions, not just update-related reports. Evidence filtering would require significant post-classification work.

**Assessment:** The Reddit RSS feed is the only Reddit access path currently available without credentials. It is useful as a **detection signal** (to know whether DaVinci-related reports are being posted at elevated volume) but is **not sufficient for evidence-backed report counting** because:
- Post bodies are truncated — cannot confirm patch-specific content from RSS alone
- Feed is not version-searchable — requires full text search or tagging, not available in RSS
- No structured evidence metadata is present

---

### 2.5 Other Community Sources (Not Directly Probed)

| Source | Accessibility estimate | Evidence potential | Notes |
|---|---|---|---|
| **VideoHelp forum** (`videohelp.com/forum`) | Likely public (phpBB) | Medium | Covers DaVinci Resolve extensively; version-specific threads exist; static fetch probably works |
| **Creative COW forums** (`creativecow.net`) | Likely public | Medium | Long-standing creative professional forum; DaVinci section active |
| **Blackmagic Twitter/X** | Blocked for bots | Low | Official announcements but not user reports; requires Twitter API |
| **GitHub Issues** (n/a) | n/a | None | DaVinci Resolve is closed-source; no public GitHub issue tracker |
| **MacRumors forums** | Partially public | Low | Occasional DaVinci posts but not a primary community |
| **YouTube comments** | No API without key | Low | Not appropriate for evidence collection |

VideoHelp and Creative COW are the best candidates for Phase 1D secondary evidence sources if Blackmagic forum remains inaccessible. Neither was probed in Phase 1C and should be verified before adding to the source config.

---

## 3. Source Priority Classification

| Source | Access status | Phase 1D role | Priority |
|---|---|---|---|
| Blackmagic forum | **Blocked (403)** | Deferred | P3 — investigate bot-block workaround or defer indefinitely |
| Reddit r/davinciresolve RSS | **Accessible** | Detection signal only | P2 — implement as new-post detection; full evidence needs OAuth |
| Reddit OAuth2 API | Not implemented | Primary evidence (if credentials added) | P1 (conditional) — requires Reddit OAuth2 credentials decision |
| VideoHelp forum | Not probed | Secondary evidence candidate | P2 — probe in Phase 1D before committing |
| Creative COW forum | Not probed | Secondary evidence candidate | P3 — probe in Phase 1D, lower volume expected |
| Blackmagic official press release | **Static: blocked (JS wall)** | Official source only | P1 — requires headless browser (see feasibility report) |

---

## 4. Evidence Access Readiness Assessment

For DaVinci Resolve to have **evidence-backed report counts**, AUXSAYS needs:

1. **At least one accessible source where users report patch-specific issues** — currently none of the primary sources (Blackmagic forum, Reddit HTML/JSON) are accessible without credentials or browser simulation.

2. **Post-body access** — RSS feed titles are not sufficient; post body text is needed to confirm patch-specific content vs. general DaVinci questions.

3. **Version-filterable search** — to find reports specifically about a given release version (e.g., "DaVinci Resolve 21 Beta 1"), search functionality is required. The Reddit RSS feed does not support search.

4. **Classification logic** — not all posts about DaVinci are patch-specific. AUXSAYS's `confirmed_patch_specific_reports_v1` policy requires human or automated classification that a post is a patch-specific report, not a general usage question.

**Current readiness: Low.** None of the currently accessible sources (Reddit RSS only) meet all four requirements. The minimum viable evidence collection path for DaVinci requires at minimum:
- Reddit OAuth2 API access (for searchable, post-body-accessible data), **or**
- Successful probe of VideoHelp / Creative COW as static-fetch-accessible alternatives

---

## 5. Recommendation for Phase 1D

**Minimum viable Phase 1D path (in order):**

### Step 1: Probe VideoHelp and Creative COW
Run static fetch probes on VideoHelp forum DaVinci sections and Creative COW DaVinci section. If either allows static fetch of thread lists, post bodies, and version-specific search, they are the lowest-friction evidence path.

### Step 2: Decide on Reddit OAuth2
If static community sources are insufficient, decide whether to add Reddit OAuth2 credentials. This enables the full Reddit API (searchable, paginated, full post bodies). This is a legitimate, supported access path but requires secret management and CI/CD credential provisioning.

### Step 3: Defer Blackmagic forum
The Blackmagic forum is blocked for all bot access. Do not attempt to circumvent this. If Blackmagic ever publishes a public API or relaxes bot access, revisit.

### Step 4: Do not implement a DaVinci evidence collector until Step 1 or 2 is resolved
A DaVinci evidence collector with no accessible evidence sources will produce 0 counts, which is the current state. The collector should only be implemented when at least one source has been confirmed viable through a successful test fetch of actual post content.

### Do not implement a production evidence collection until the official source adapter is also ready
Evidence counts require a paired official source record (for version matching). Until the official Blackmagic source is accessible (headless adapter), there is no point in collecting community reports — you cannot confirm which release a report belongs to without being able to read the release notes.
