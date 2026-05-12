# Phase 1D — DaVinci User-Report Source Decision

**Phase:** 1D  
**Date:** 2026-05-12  
**Based on:** Phase 1C probe results, AGENTS.md, current pipeline architecture

---

## 1. Summary of Phase 1C Access Findings

| Source | Access | Result |
|---|---|---|
| Blackmagic official forum (`forum.blackmagicdesign.com`) | **Hard 403 on all requests** | Not accessible to bots |
| Reddit r/davinciresolve HTML | **HTTP 403** | Blocked for non-browser user-agents |
| Reddit JSON API (`.json` endpoints) | **HTTP 403** | Requires OAuth2 since 2023 |
| Reddit RSS/Atom feed | **HTTP 200, 26 items** | Accessible, structured, but shallow |
| VideoHelp forum | Not probed | Unknown — candidate for Phase 1D inspection |
| Creative COW | Not probed | Unknown — candidate for Phase 1D inspection |

---

## 2. Evidence Source Evaluation

### 2.1 Reddit OAuth2 API

**Description:** Use Reddit's official OAuth2 API (script-type app, read-only) to search r/davinciresolve for version-specific posts.

| Dimension | Assessment |
|---|---|
| **Feasibility** | High — Reddit OAuth2 is publicly documented and available to any registered app |
| **Compliance / access risk** | Low-Medium — this is the legitimate, supported path. Reddit's API ToS allows automated read-only access with OAuth2 |
| **Version-match quality** | Medium — posts must be individually inspected for exact version mention; community uses many shorthand forms |
| **Body text availability** | Full post body available via API |
| **Pagination / search capability** | Full search available (`/search.json?q=...&restrict_sr=1`) with sorting and date filtering |
| **Counted evidence support** | **Yes** — with `patch_version_matched: true` classification enforced at collection time |
| **Role** | **Primary community source** if approved |
| **Decision** | Conditional — requires: Reddit app registration, client_id + client_secret as CI secrets, token refresh implementation |
| **Implementation risk** | Reddit API rate limits (60 req/min); search is keyword-based and noisy; version-match must be strict |
| **Phase 1E priority** | P1 if credential decision is approved |

**Key requirement:** Post titles and bodies must be inspected for **exact version string** (`21 Public Beta 1` or recognizable form). Reddit posts rarely use the full Blackmagic version string. The classification step must normalize user shorthand (see version normalization design) before counting.

---

### 2.2 Reddit RSS Activity Signal Only

**Description:** Use the publicly accessible `https://www.reddit.com/r/davinciresolve/.rss` feed as a detection signal (new post volume) without counting posts as evidence.

| Dimension | Assessment |
|---|---|
| **Feasibility** | **High** — confirmed accessible (HTTP 200) in Phase 1C |
| **Compliance / access risk** | **Low** — no authentication required; public feed |
| **Version-match quality** | **Poor** — feed contains titles only; post bodies truncated; not version-searchable |
| **Body text availability** | Truncated in RSS entries |
| **Pagination / search capability** | None — always last ~26 posts; no version filter |
| **Counted evidence support** | **No** — cannot confirm patch-specific content from RSS alone |
| **Role** | **Activity signal only** — can detect elevated posting volume around a release; not sufficient for counted evidence |
| **Decision** | Use as supplementary detection trigger, not as evidence source |

**How to use RSS as a signal:** Poll the feed after a new Blackmagic release. If post volume increases significantly (new DaVinci posts in the feed title scan), flag for manual review or trigger a Reddit OAuth2 search. Do NOT count RSS posts as evidence.

---

### 2.3 Blackmagic Official Forum

**Description:** Scrape or query `forum.blackmagicdesign.com` DaVinci Resolve section.

| Dimension | Assessment |
|---|---|
| **Feasibility** | **Not feasible** — HTTP 403 on all requests, including index, section, and search |
| **Compliance / access risk** | **High** — server actively blocks non-browser user-agents; circumventing this would require session simulation or bot-block bypass |
| **Version-match quality** | Would be excellent if accessible — dedicated DaVinci sections exist |
| **Body text availability** | Would be full text if accessible |
| **Counted evidence support** | Would be ideal if accessible |
| **Role** | **Deferred indefinitely** |
| **Decision** | Do not target. Do not implement circumvention. Revisit only if Blackmagic provides public API access or relaxes bot policy. |

---

### 2.4 VideoHelp Forum

**Description:** `https://www.videohelp.com/forum` is a long-running creative professional forum covering DaVinci Resolve extensively. Uses phpBB or similar forum software.

| Dimension | Assessment |
|---|---|
| **Feasibility** | **Unknown — not probed in Phase 1C** — must be verified before committing |
| **Compliance / access risk** | Low if publicly readable without login (requires verification) |
| **Version-match quality** | Medium — forum threads may reference versions in titles; search needed |
| **Body text availability** | Likely full text if publicly accessible |
| **Pagination / search capability** | phpBB search available; may be accessible via URL parameters |
| **Counted evidence support** | Potentially yes — if post text and version match can be confirmed |
| **Role** | **Candidate secondary source** — probe before committing |
| **Decision** | Probe in Phase 1E before implementing. Run a static fetch of the DaVinci Resolve forum section. If public and searchable, it is a lower-friction alternative to Reddit OAuth2. |
| **Phase 1E priority** | P2 — probe first; implement only if Reddit OAuth2 is deferred or unavailable |

**Probe required:** Static GET to `https://www.videohelp.com/forum/forum-davinci-resolve` (or equivalent section URL). Check HTTP status, whether posts are readable, whether a search URL exists, whether version strings appear in post titles.

---

### 2.5 Creative COW Forum

**Description:** `https://creativecow.net` is a long-running creative professional forum. A DaVinci Resolve section likely exists.

| Dimension | Assessment |
|---|---|
| **Feasibility** | **Unknown — not probed** |
| **Compliance / access risk** | Low if public |
| **Version-match quality** | Low-Medium — less DaVinci-focused than VideoHelp; smaller volume |
| **Body text availability** | Likely full text if public |
| **Counted evidence support** | Potentially yes, but lower volume |
| **Role** | **Tertiary candidate** |
| **Decision** | Lower priority than VideoHelp. Probe only if VideoHelp is inaccessible. |
| **Phase 1E priority** | P3 |

---

### 2.6 Manual Evidence Review Workflow

**Description:** Operator manually reviews community sources (Reddit, VideoHelp, Blackmagic forum if logged in) and writes evidence rows directly to `consensus_evidence.yml`.

| Dimension | Assessment |
|---|---|
| **Feasibility** | **High** — operator can access any public or logged-in source |
| **Compliance / access risk** | **None** — no automated bot access |
| **Version-match quality** | **Highest** — human reviewer confirms patch-specificity |
| **Body text availability** | Full |
| **Counted evidence support** | **Yes** — rows written with `patch_version_matched: true` by human judgment |
| **Role** | **Bridge path** — enables evidence collection before automated collector is ready |
| **Decision** | Valid for Phase 1E if automated collection is unavailable. Requires strict discipline: every row must have source_url, report_text_excerpt, and `patch_version_matched: true` set by the reviewer. |
| **Phase 1E priority** | P1 as fallback if automated collection is delayed |

**Safeguard required:** Manual rows must pass the same `audit_consensus_evidence.py` validation as automated rows. No manual row should be written without a source URL and report text excerpt.

---

### 2.7 No Automated Community Evidence (Status Quo)

**Description:** Keep DaVinci as `manual_watch / official_only` with no community evidence collection.

| Dimension | Assessment |
|---|---|
| **Feasibility** | **Already in place** |
| **Risk** | **None** — current state is correct and honest |
| **Counted evidence support** | No |
| **Role** | **Active fallback** — correct choice if no source can be confirmed viable |
| **Decision** | This is the right default until at least one evidence source is confirmed |

---

## 3. Source Priority Matrix

| Source | Recommended role | Phase 1E priority | Prerequisite |
|---|---|---|---|
| Reddit OAuth2 API | Primary community evidence | P1 (conditional) | Credential decision + Reddit app registration |
| VideoHelp forum | Secondary community evidence | P2 | Static fetch probe to confirm public access |
| Manual evidence review | Bridge path / fallback | P1 (fallback) | Operator availability + discipline |
| Reddit RSS | Activity signal only | P2 | No prerequisites — already accessible |
| Creative COW | Tertiary candidate | P3 | Probe only if VideoHelp fails |
| Blackmagic forum | Deferred indefinitely | Do not implement | Requires policy change by Blackmagic |
| No automated evidence | Status quo / fallback | Active now | None |

---

## 4. Strict Access Policy

The following actions are explicitly excluded from this project regardless of phase:

1. **Do not circumvent the Blackmagic forum 403 block.** Session simulation, browser fingerprinting, or credential injection are not compliant and must not be implemented.

2. **Do not treat Reddit RSS as counted evidence.** RSS delivers truncated post bodies and is not version-searchable. Any evidence counted from RSS would not meet the `confirmed_patch_specific_reports_v1` standard.

3. **Do not use Reddit HTML scraping.** Reddit blocks HTML access for bots; circumventing this is against Reddit's ToS.

4. **Do not add API keys, tokens, or credentials in Phase 1D.** Credential management is a Phase 1E implementation decision.

5. **Do not count reports from any source that cannot confirm the exact DaVinci version.** General DaVinci questions are not patch-specific evidence.

---

## 5. Minimum Viable Evidence Configuration for Phase 1E

The minimum viable evidence configuration before any DaVinci report count can be set above 0:

1. At least one evidence source is confirmed accessible (Reddit OAuth2 OR VideoHelp OR manual review)
2. At least one evidence row exists in `consensus_evidence.yml` for `product_id: blackmagic-davinci` with `update_version: '21 Public Beta 1'`, `patch_version_matched: true`, `counted: true`
3. The write-back script (`apply_consensus_to_records.py`) has been tested against the DaVinci row and produces a correct dry-run output
4. `audit_consensus_evidence.py` shows zero mismatches after write-back
5. The official Blackmagic source adapter is either functional (returning release body) or the write-back is gated on official source status
