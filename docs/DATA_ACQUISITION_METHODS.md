# AUXSAYS Data Acquisition Methods

How AUXSAYS actually gets data, what each way of getting it is good at, what it systematically
misses, and how it fails.

The machine-readable registry is [`auxsays/scripts/lib/acquisition_methods.py`](../auxsays/scripts/lib/acquisition_methods.py).
This document is the reading of it. When the two disagree, the registry is right — it is validated;
this is prose.

**What this is for.** A new collector should reuse a proven acquisition strategy instead of
rediscovering one. Equally: a method that *failed* should stay on the record, with the measurement
that killed it, so nobody spends a sprint re-proving it. Photoshop is the case study for that, and
it is here precisely because it did not work.

**What this is not.** It is not runtime health — `_data/evidence_method_health.yml`, source health
and the ingest rows answer *what happened this run*, and nothing here is written by a run. It is not
routing — `lib/method_routing.py` decides which method executes and remains authoritative. And it is
not a scraping taxonomy: everything listed is implemented or concretely measured in this repository.

---

## Three things that are not the same

Conflating these is the mistake this registry exists to prevent.

| | question it answers | example |
|---|---|---|
| **Method family** | *How* is information acquired? | `rss_search`, `html_table_enumeration` |
| **Implementation** | That family against which site? | `microsoft_learn_qna_search_rss` |
| **Purpose / evidence authority** | What may the result *count as*? | `candidate_discovery` vs `official_ingestion` |

A vendor name is never a family. `microsoft_learn` describes nobody's mechanics; `rss_search` does,
and it is the same mechanic whether the index belongs to Microsoft or anyone else. The validator
enforces this: a family containing a vendor token fails.

**Discovery is not evidence.** A search result may discover a URL without being evidence for
anything. Several methods are `candidate_discovery` only: they hand candidates to the *same*
acceptance authority every other method uses. Discovery diversity is not acceptance divergence —
widening how we look never widens what counts. The validator refuses any entry that claims both
`candidate_discovery` and `official_ingestion`.

---

## The families

21 families, 58 concrete implementations. Counts are generated from the registry.

| family | methods | purposes | transports |
|---|---|---|---|
| `archive_recheck` | 1 | archive, candidate_discovery, community_discovery | html, rest_json |
| `capability_probe` | 3 | candidate_discovery, capability_probe, fallback, official_ingestion, recheck | html, rest_json |
| `direct_fetch` | 6 | archive, candidate_discovery, community_discovery, enrichment, official_ingestion | html |
| `forum_tab_enumeration` | 1 | candidate_discovery, fallback | html |
| `html_link_enumeration` | 4 | archive, candidate_discovery, capability_probe, fallback, official_ingestion, recheck | html |
| `html_release_history` | 6 | official_ingestion | html, rest_json, rss_xml, subprocess_curl |
| `html_search_result_scrape` | 1 | candidate_discovery, context_resolution | html |
| `html_table_enumeration` | 4 | community_discovery, fallback, official_ingestion | html |
| `in_page_harvest` | 1 | candidate_discovery, context_resolution, recheck | html |
| `issue_tracker_search_api` | 2 | candidate_discovery | github_api, html, rest_json |
| `json_api_listing` | 4 | candidate_discovery, official_ingestion | github_api, rest_json |
| `json_api_search` | 5 | candidate_discovery, community_discovery, context_resolution, fallback, recheck | github_api, html, rest_json |
| `known_url_recheck` | 5 | candidate_discovery, context_resolution, recheck | html, rest_json, rss_xml |
| `manual_watch` | 1 | candidate_discovery | html |
| `open_web_federation` | 1 | candidate_discovery, recheck | html, rest_json |
| `open_web_search_api` | 2 | candidate_discovery, recheck | html, rest_json |
| `paginated_listing_enumeration` | 2 | candidate_discovery, recheck | html, rest_json, rss_xml |
| `rss_feed_poll` | 3 | candidate_discovery, official_ingestion | rest_json, rss_xml |
| `rss_search` | 2 | candidate_discovery, community_discovery, recheck | html, rest_json, rss_xml |
| `sitemap_walk` | 2 | candidate_discovery, recheck | html, rss_xml |
| `transport_failover` | 2 | candidate_discovery, official_ingestion | subprocess_curl |

**22** methods carry `official_ingestion`; **36** do community or candidate discovery; **19** are not
running today — 13 blocked, 3 disabled, 3 staged — and all of them are kept.

### Enumeration and search are different shapes

The distinction `open_web_source.py` records is worth stating once, because it explains why several
products run two methods against the *same* source family:

- **Enumeration** is bounded by **where you look**. Walk a tag inventory, a sitemap, a forum tab.
  You see everything in that place, in order, whether or not you knew to ask for it.
- **Search** is bounded by **what you ask**. A report is only ever as findable as the words its
  author happened to use.

So `learn_qna_search_rss` and `learn_qna_powerpoint_tags` share a source family but are *independent
primaries*, not a retry chain: a report worded in a way no query anticipated is invisible to the
first and ordinary to the second. Making the second conditional on the first failing would suppress
it exactly when the first is working.

---

## Case study: Photoshop — public content is not an automatable source

The most useful entry in the registry is a method that does not work.

Adobe's Photoshop desktop release notes are **public**. They load normally in an ordinary browser,
carrying the current version and its history. They are also, from production egress, unreachable:

- every `helpx.adobe.com` route answers **HTTP 403 Access Denied** from an Akamai edge in 0.08–0.14 s
  — canonical release notes, the `/en/` locale path, the legacy path, whats-new, the AEM
  `.model.json`, Creative Cloud release notes, and a known-issues control;
- reproduced from **three distinct GitHub Actions runner IPs**;
- `www.adobe.com` answers **200** in the same job, so it is not an egress failure — the block is
  host-scoped;
- the four candidate paths on that reachable host answer **404**: Adobe does not publish equivalent
  desktop release history there;
- request-shape experimentation was **not durable**. Three shapes returned 200 with 67,998 bytes,
  and minutes later *those same shapes* returned 403. The filter is reputation/rate based, not
  header based, so no User-Agent or Accept arrangement fixes it.

The lesson the registry carries forward:

> **Public content ≠ production-automatable source.** Reachability is a property of the *request and
> its history*, not of the document. A source that serves a cold client and refuses a returning one
> cannot be a production dependency, and impersonating a browser harder is not an architecture.

The source stays disabled (AUX-017). The objective recheck is the **Photoshop Source Probe**
workflow, manual dispatch — `auxsays/scripts/probe_photoshop_sources.py`. Registry entries:
`adobe_helpx_release_history_direct_fetch`, `adobe_photoshop_heading_release_notes`,
`adobe_helpx_aem_model_json_probe`, `adobe_www_host_substitution_probe`, and the paired transport
control that distinguishes "this host blocks us" from "this egress is blocked".

---

## Case study: Teams — transport was the easy part

Microsoft's Teams version history is everything Photoshop is not: server-rendered HTML, CI-reachable,
HTTP 200, 481 KB. Transport was never the problem. Three *other* problems were, and they are why
acquisition-method documentation has to cover more than HTTP:

**1. Identity.** The page carries **37 tables** across cloud × edition × platform — Mac, Web, VDI,
Mobile, Classic Teams, Government GCC/GCCH/DoD, Sovereign Gallatin. Exactly **one** chain is the
tracked identity (`public cloud offerings` → `new teams app version` → `windows`). The same calendar
release ships a different build per platform, so mis-scoping does not produce a cosmetic error, it
misreports a Windows user's patch state. The parser is *table-anchored*: identity is consumed by the
first table under a freshly armed heading and never inherited across a table boundary.

**2. History volume, which identity filtering cannot solve.** That one correct table carries the
**full history — 63 builds back to 2023-10-12** — and every one of them is a legitimate member of the
target identity. No identity check could ever stop them. With a per-run record limit of 2 and a
200-wide scan window, activation would have walked three years of builds onto the site two at a time.
That needed a *separate* control: `ingestion.record_floor_date`, a declared release-date boundary,
which turned 63 candidates into 4.

**3. Serialisation, which is downstream of both.** The adapter emitted the full three-part identity,
but the record writer copies only allow-listed fields, and `teams_edition` was in none of them. Every
written record would have carried two thirds of its identity. The suite that asserts the contract was
green only because *zero records existed yet*.

> Identity scoping, historical bounding and field serialisation are three different problems. Getting
> the transport right tells you nothing about any of them.

---

## When a source changes shape

The web AUXSAYS reads from will keep changing underneath it. The concrete changes to expect:

| change | what breaks | proven family to reach for |
|---|---|---|
| server-rendered HTML becomes a JS shell | every HTML parser returns an empty or skeletal document | none implemented — see `FUTURE_CAPABILITIES.browser_rendered_dom` |
| REST endpoint becomes GraphQL | `json_api_listing` / `json_api_search` 404 or 400 | none implemented — `FUTURE_CAPABILITIES.graphql_query` |
| structured data moves to JSON-LD or embedded app state | visible markup stops carrying versions | none implemented — `json_ld_extraction`, `embedded_application_state` |
| feed removed | `rss_feed_poll`, `rss_search` | `html_link_enumeration`, `sitemap_walk` |
| search index degrades or stops covering a corpus | `rss_search`, `open_web_search_api` | `paginated_listing_enumeration`, `sitemap_walk` — enumeration is bounded by *where*, not *what you ask* |
| bot/CDN policy tightens | any direct fetch | `capability_probe` first; if it is reputation-based, there is no request shape that fixes it |
| API authentication becomes mandatory | public API methods | none — only `api.github.com` may ever receive a credential, and that is an origin-scoped allowance in `lib/http.py`, not a general capability |
| pagination becomes infinite scroll | `paginated_listing_enumeration` | `json_api_listing` against whatever endpoint the scroll calls |
| schema drift | any parser | the method's own `broken` health status — *not* `no_results` |

The design principle, in order:

> **site changes → capability probe → select a proven acquisition family → preserve the same evidence
> acceptance rules.**

The last clause is the one that matters most. Changing *how* we find something must never change
*what counts*. Every method in this registry, whatever its transport, hands candidates to the same
acceptance gates — exact build, channel, date, concrete issue, specific URL.

---

## Failure vocabulary

A method must be able to say **blocked** or **broken**, not just **no_results**. The distinction is
the difference between "we looked and there was nothing" and "we never read anything" — and reporting
the second as the first is how a dead source publishes as healthy.

The canonical statuses are imported from `lib/method_routing.py`, not restated here, so the registry
cannot claim a status routing is unable to evaluate:

`success` · `partial` · `no_results` · `blocked` · `stale` · `broken` · `low_confidence` ·
`disabled` · `manual_review_needed`

One measured example of getting this wrong, kept in the registry: the Learn Q&A lane once applied
HTML challenge-phrase detection to *feed bodies*, where "every phrase is somebody's question". A
user's thread mentioning "a brand new Microsoft account" made AUXSAYS discard a feed of five real
results as a login wall and publish `partial` / `login_or_auth_challenge` for a page showing zero
reports. The fix was to make status authoritative and to classify challenge phrases only when the
content type is HTML.

---

## Using the registry

```python
from lib import acquisition_methods as am

am.by_id("learn_qna_search_rss")        # one entry
am.by_family("html_table_enumeration")  # everything sharing a mechanic
am.families()                           # the controlled vocabulary
```

Nothing imports it at runtime, by design: it is a catalogue, not a dependency. `method_routing.py`
still decides what executes. The validator asserts the two agree — every method routing routes to
exists here.

Validated by [`test_acquisition_method_registry.py`](../auxsays/scripts/tests/test_acquisition_method_registry.py).
