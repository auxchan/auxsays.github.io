# AUXSAYS deterministic discovery-method framework

Reference for every repo-owned internet-discovery method the evidence pipeline uses or
may adopt. Production evidence collection must not depend on ChatGPT, Claude, Codex, or
any external AI subscription: discovery is HTTP/API clients, deterministic parsers,
regex/token/version matching, deterministic acceptance gates, caching/deduplication,
bounded retry/runtime controls, structured evidence, and method-health telemetry.
AI may help develop and audit this system; it never participates in the live pipeline.

## Two lanes, never mixed

- **OFFICIAL ingestion** (`patch_ingest.py` + `adapters/*`) proves a vendor release
  exists and captures official release notes. It creates/refreshes generated records
  that stay `evidence_state: official_only`, `update_report_count: 0`, consensus
  deferred. Transport: `lib/http.fetch_text` with per-source `ingestion.request`
  bounds (timeout, retries, backoff, max_bytes).
- **CONSENSUS discovery** (`run_patch_evidence_collection.py` + `patch_collectors/*`)
  finds candidate community reports about an already-recorded patch. Candidates pass
  through the strict verifier (`base.apply_acceptance_gates`) before anything counts.
  Transport: `patch_collectors/runtime_budget.py` (hierarchical deadlines, request
  caps, bounded Retry-After, byte caps, hard wall-clock body reads).

Official-source discovery never creates consensus evidence; discovery never sets
`counted=true`. Every counted report keeps `source_weight: 1` — no source-type
weighting exists (`consensus_rules.yml: source_prestige_weighting: false`).

## Method inventory

Legend: **Official** = suitable for official ingestion; **Consensus** = suitable for
consensus discovery. A method is never both in one configuration.

### 1. `zendesk_help_center` — implemented (`adapters/zendesk_help_center.py`), Official

- Discovery input: Zendesk Help Center section page URL (config `official_url`), from
  which host/locale/section-id derive the documented anonymous JSON API
  `https://<host>/api/v2/help_center/<locale>/sections/<id>/articles.json`
  (explicit same-host `api_url` override supported).
- Auth: none (anonymous). Pagination: `next_page` envelope, followed only same-host,
  hard-capped at `MAX_PAGES` (5) with repeat-URL loop protection; truncation is
  surfaced, never a silent full sweep. Rate limits: Zendesk's anonymous tier;
  one request per section per run in practice.
- Version/query strategy: config `version_pattern` (anchored regex, named `version`
  group) against exact article titles; config `product_terms` must appear in
  title/body; section-id, locale, draft-flag, and same-host `html_url` gates.
- Output: official record shape (see `lib/write_update_record.py`).
  Dedup key: version (platform-split articles collapse to one record, newest wins)
  plus the runner's seen-ledger on `record_id`.
- Date gate: `created_at` (ISO) required — no date, no record.
- Runtime bounds: per-request timeout, `MAX_RESPONSE_BYTES` (4 MB) byte cap
  (truncated JSON fails loudly), page ceiling.
- Health: ingest-state vocabulary (`healthy`/`degraded`/`failing` +
  `last_health_note`); zero-record success books `degraded` for parser review.
  Blocked (403/429) propagates as a source error — booked, never silent.
- Fallback: none in-adapter; the section page URL stays the record's official link.

### 2. `discourse_json` — implemented (`patch_collectors/discourse_json_source.py`), Consensus

- Discovery input: forum base URL + exact query terms (a patch version or patch
  title) against the documented anonymous `GET /search.json?q=<term>`.
- Auth: none on the verified targets (community.openai.com; many vendor Discourse
  instances). Pagination: search first page only (keyword-anchored discovery, not
  archive crawling). Rate limits: per-IP; paced by
  `AUXSAYS_DISCOURSE_REQUEST_DELAY_SECONDS` (default 0.35 s) and the method request cap.
- Output: shared candidate contract (below); URLs restricted to specific
  `/t/<slug>/<topic-id>[/<post-number>]` topic/post permalinks.
- Dedup key: canonical post URL (lowercased, trailing-slash-stripped) + deduped queries.
- Date gate: post `created_at` normalized to UTC `Z`; `context.since` drops older
  candidates; the strict verifier re-checks report date vs release date.
- Runtime bounds: every attempt charged via `RuntimeBudget.note_request()`; body reads
  via `bounded_read` (1.5 MB cap); one bounded transient retry (408/429/5xx) honoring
  seconds-form Retry-After through `backoff_delay`/`note_backoff` (cap-bounded).
- Health/blocked behavior: transport failures classify as
  `blocked`/`rate_limited`/`broken`/`network` signatures appended to the caller's
  `errors` list (fail-soft per query); only `MethodBudgetExhausted` propagates, which
  the collector books as terminal method health. A 403/429/parse failure never
  disappears silently.
- Fallback: none — a blocked Discourse instance is reported blocked.

### 3. `github_issues` — implemented (OBS lane, `patch_collectors/obs.py` + legacy collector), Consensus

- Discovery input: repo + exact version query against the GitHub Issues API.
- Auth: optional `GITHUB_TOKEN` raises rate limits (5000/h vs 60/h anonymous).
- Pagination: bounded `max_pages`. Output: shared candidate shape; URL gate requires
  `/issues/<n>`. Dedup: canonical issue URL. Date gate: issue `created_at` vs release.
- Health: `github_issues` method rows (`success`/`no_results`/`broken`).
- Suitability: Consensus (issue reports). The separate official-side
  `adapters/github_releases.py` covers OFFICIAL ingestion from GitHub Releases.

### 4. `rss_atom` — implemented in both lanes

- Official: `adapters/rss_feed.py` (feed autodiscovery from `official_url`, RSS+Atom,
  guid-keyed records). Consensus: RSS fallbacks inside `reddit_source.py` and the
  Learn Q&A search-RSS lane (`microsoft_learn_qna_source.py` — an RSS **search** API
  driven by exact KB/build/version terms).
- Auth: none. Pagination: none (feeds are windows); backfill beyond the window needs a
  different method. Dedup: guid/link. Date gate: `pubDate`/`updated`.
- Bounds: byte-capped reads; feed parse failures classify `broken`.
- Suitability: Official for vendor release feeds; Consensus only for report-bearing
  feeds (community search RSS), never for vendor announcement feeds (excluded by the
  verifier as official announcements).

### 5. `sitemap_delta` — not implemented (design)

- Discovery input: vendor `sitemap.xml` (index + child sitemaps), diffed across runs
  for new/changed release-note URLs (`<lastmod>` + persisted URL ledger).
- Auth: none. Pagination: sitemap-index fan-out, must be page-capped like Zendesk
  pagination. Dedup: URL + lastmod. Date gate: `lastmod` is a change date, not a
  release date — release date must still come from the page/API (fail-closed if not).
- Bounds: byte caps per sitemap; child-sitemap ceiling; ledger bounded like the
  retired help-center scan ledger. Health: `no_results` vs `stale` (unchanged sitemap
  is healthy-quiet) needs an explicit freshness note.
- Suitability: Official discovery hint only (which URLs to parse) — never a record
  source by itself; unsuitable for consensus (sitemaps carry no reports).

### 6. `html_release_index` — implemented family (Adobe/Microsoft adapters, `html_changelog`), Official

- Discovery input: a vendor release-notes index/changelog page; deterministic
  DOM/regex parsing with anchored version/date patterns.
- The Elgato lesson (theme `<h1>` collision breaking title extraction for months of
  runs, surfaced only as `degraded` zero-record health) is the canonical argument for
  preferring documented JSON APIs when one exists. Keep `html_release_index` for
  vendors without an API (Adobe HelpX, Microsoft Learn release notes).
- Bounds: request bounds via `ingestion.request`; parser misses must fail closed
  (no version/date -> no record) and be visible in diagnostics/health.
- Suitability: Official. Consensus HTML scraping is a separate last-resort method (8).

### 7. `public_algolia` / community search APIs — implemented (Acrobat lane), Consensus

- Discovery input: a community's own public search backend where it is already exposed
  anonymously (Adobe community inSided/Algolia: `searchToken` -> keyless secured query
  -> `getTopics` hydration). Verified CI-reachable where the HTML search is
  CloudFront-blocked.
- Bounds: query cap (`MAX_ALGOLIA_QUERIES`), hits cap, topics cap, budget-charged
  requests. Dedup: canonical thread URL. Date gate: thread dates re-verified during
  gating. Health: `adobe_community_algolia_search` rows (`success`/`no_results`).
- Suitability: Consensus only. Never reverse-engineer private/authenticated APIs; use
  only endpoints the public site itself calls anonymously.

### 8. `community_html` fallback — implemented family (Premiere/CreativeCow/vendor forums), Consensus (last resort)

- Direct HTML listing/thread scraping where no JSON/RSS/API surface exists
  (`creative_cow_forum_search`, `vendor_forum_search`, `adobe_community_search`).
- Highest breakage/block rate in production health history (most `blocked` rows in
  `evidence_method_health.yml` come from this family). Use only with: bounded reads
  (`bounded_read`), per-method request caps, honest `blocked` classification, and a
  preference to migrate to methods 2/3/4/7 when the target exposes one.
- Suitability: Consensus last resort; never Official (official pages get a dedicated
  fail-closed adapter instead).

## Shared consensus-candidate contract (Part F)

Discovery libraries (`reddit_source`, `microsoft_learn_qna_source`,
`discourse_json_source`) emit normalized candidate rows:

| field | meaning |
|---|---|
| `source_type` | caller-scoped type (e.g. `discourse_forum_report`) |
| `source_name` | human source label (e.g. `r/davinciresolve`, forum host) |
| `source_url` | specific report/thread/post permalink (must pass `source_url_is_specific`) |
| `parent_title` | thread/topic title |
| `report_title` | report title (topic title for forum posts) |
| `report_text` | cleaned title+body/blurb excerpt, capped |
| `source_date` | ISO UTC date of the report, `''` when unknown (never fabricated) |
| `matched_query` | the exact discovery term that surfaced the row |

The registering collector attaches patch identity during evaluation — `product_id`,
`update_version`, exact-version-token result (`base.exact_version_match`), product
match, and gate outcomes — then `base.make_evidence_row` + `apply_acceptance_gates`
decide `counted`/`exclusion_reason` and stamp `discovered_at` (`captured_at`) and
candidate health. Discovery cannot set `counted=true`.

## Acceptance stays strict (Part G)

Unchanged, enforced in `base.apply_acceptance_gates` per
`consensus_rules.yml` (`confirmed_patch_specific_reports_v1`): exact product; exact
patch/version in the report or a patch-specific parent; report date on/after release
when known; specific URL; concrete user-facing issue; duplicates, official
announcements, and general complaints excluded; replies count only inside a
patch-specific parent under the existing reply rule; `source_weight: 1` always.

## Method health (Part H)

Every method books rows in the EXISTING vocabulary only
(`validate_evidence_method_health.ALLOWED_STATUSES` /
`base.VALID_METHOD_HEALTH_STATUSES`):

`success, partial, no_results, blocked, stale, broken, low_confidence, disabled,
manual_review_needed`

Structured reason detail goes in `blocked_reason`/`notes` and the scrubbed
`[auxsays:runtime]` diagnostics — not new states. A 403/429/parse failure must end as
a `blocked`/`broken` (or `partial`) row with its signature preserved; it must never
disappear silently. New scrapers add new `method_id` values (registered in
`lib/collector_ownership.ALLOWED_METHODS`), never new health vocabulary.

## Runtime/network safety (Part I)

Any new consensus method uses `runtime_budget.py`: total request wall-clock deadline
(`bounded_request`/`bounded_read`), body byte caps, per-method deadline + request cap
(`start_method`/`note_request`), collector deadline with finalize reserve, bounded
retries with bounded seconds-form Retry-After (`backoff_delay`, `note_backoff`),
endpoint dedup/cache (`cache_get`/`cache_put`), no worker threads, flushed
secret-scrubbed diagnostics (`emit`/`scrub_url`), public-safe URLs only. Official
adapters use the `lib/http.fetch_text` bounds (`ingestion.request` timeout/retries/
backoff/max_bytes plus adapter-level page/byte ceilings). Never reintroduce the
unbounded-read class of failure fixed after run 31086662777 (PR #43).
