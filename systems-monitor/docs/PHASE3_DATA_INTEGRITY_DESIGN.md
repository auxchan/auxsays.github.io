# Phase-3 Data Integrity Design — APPROVED

```text
Artifact: Phase-3 Data Integrity Design
Version: 1.0.0
Status: APPROVED — GOVERNED BY BINDING PHASE-3 CONTRACTS
Parent Master Spec: V4.1
Governing Contracts: DATA_CONTRACT.md, SOURCE_CONTRACT.md, ONTOLOGY_CROSSWALK_CONTRACT.md, TESTING_CONTRACT.md
Last Updated: 2026-08-17
```

This is the approved design boundary for a later scoped Phase-3 implementation. This approval task creates no collector, API call, downloaded data, dependency, database, Parquet file, scheduled job, factual public snapshot, forecast, or deployment. Gate-A evidence and separate factual-activation approval remain required before public activation.

## 1. Approved source inventory

All endpoints and access rules must be rediscovered from official metadata immediately before implementation. API credentials are secrets and may never enter source control or public payloads.

### FIRST-SLICE ENABLED

| Registry ID | Provider / dataset | Tier | Intended coverage | Official access surface known at draft time | Auth / cost | Cadence and revision behavior | Rights posture | Fallback / cross-check |
|---|---|---|---|---|---|---|---|---|
| `src_bls_ces` | BLS Current Employment Statistics | A | Total nonfarm payroll employment | Current official BLS API/flat-file surface must be rediscovered before enablement | BLS v2 currently requires registration; verified limits/renewal are registry metadata, not timeless invariants | Monthly; revisions/benchmarking preserved | BLS states published material is generally public domain; exact terms evidence and attribution still recorded | Official BLS surface only |
| `src_bls_cps` | BLS Current Population Survey / Labor Force Statistics | A | U-3 unemployment; participation | Same official BLS discovery requirement | Same source-definition requirement | Monthly; publication/revision events preserved | Same fail-closed rights record | Official BLS surface only |
| `src_bls_jolts` | BLS Job Openings and Labor Turnover Survey | A | Job openings; hires | Same official BLS discovery requirement | Same source-definition requirement | Monthly; preliminary/final/republication events preserved | Same fail-closed rights record | Official BLS surface only |
| `src_dol_claims` | DOL ETA Weekly Claims | A | Initial unemployment-insurance claims and Gate-A revision proof | Official release/archive/data surface; exact current machine mechanism remains implementation-time discovery | No credential assumption | Weekly advance/revised values; independently retain consecutive releases and publication times | Exact DOL terms/third-party exceptions recorded before enablement | Official DOL release/archive only |

Official documentation reviewed 2026-08-17:

- BLS API limits/registration: <https://www.bls.gov/developers/api_faqs.htm>. On this review date, registered v2 documentation states 500 queries/day, 50 series/query, 20 years/query, 50 requests/10 seconds, and annual registration renewal. These values must be reverified and stored with `verified_at` before enablement.
- BLS publication rights statement: <https://www.bls.gov/opub/copyright-information.htm>.
- DOL Weekly Claims releases/archive evidence: <https://www.dol.gov/newsroom/releases/eta> and official release artifacts linked there. Implementation must rediscover the exact current archive/download surface.
- FRED Services/API terms rechecked 2026-08-17: <https://fred.stlouisfed.org/legal/>. Current prohibitions on software/system or machine-learning use and storing/caching/archiving/database incorporation make FRED/ALFRED incompatible with this pipeline absent written permission or materially changed terms plus new Taylor approval.

### APPROVED REGISTRY / FOLLOW-ON — NOT FIRST-SLICE ENABLED

| Registry ID | Provider / dataset | Indicator | Posture |
|---|---|---|---|
| `src_bls_cpi` | BLS Consumer Price Index | CPI-U all items | Approved registry item; no first-slice retrieval/implementation |
| `src_bea_nipa` | BEA National Income and Product Accounts | Real GDP | Approved registry item; no first-slice retrieval/implementation; query-parameter credential redaction must be proven before any later use |

### LATER

| Source family | Intended future coverage | Entry condition |
|---|---|---|
| Census Bureau | Trade, construction, manufacturing, population, business formation | Current phase passes Gate A and a bounded indicator requires it |
| EIA | Electricity, petroleum, natural gas | Exact API-v2 route/key/rights validation and measured value; official documentation currently requires a free API key |
| USDA, USGS, NOAA, Reclamation | Food, materials, weather, water | Future source contracts define spatial/temporal semantics and publication rights |
| BTS, Treasury, Federal Reserve Board | Freight, fiscal/financial conditions, industrial production | A later approved indicator scope requires them |
| ISOs/RTOs, ports, regulatory filings | Grid, logistics, entity-specific evidence | Source-specific rights, entity resolution, and operational security pass review |

### DEFERRED

- Commercial, licensed, scraped, or human-submitted sources.
- News as numerical truth; news may later supply event evidence only under a separate approved contract.
- Broad physical-input, company/facility, hidden-dependency, model, forecast, and occupation coverage.
- Any source whose license, provenance, geography, revision semantics, or machine-readable stability cannot be established. Unknown rights fail closed.

### NOT AUTHORIZED UNDER CURRENT TERMS

- **FRED/ALFRED:** not an ingestion, archival/vintage, stored cross-check, fallback numerical, historical replay, model-feature, model-training, database, compilation, archive, or cache source. The Master may retain its conceptual Tier-B classification, but O-004 rejects project use under current terms. No substitute aggregator is authorized.

## 2. Initial bounded indicator registry

This is the approved bounded registry, not retrieved data. Exact source metadata, seasonal adjustment, units, series IDs, rights, limits, and release rules must be revalidated from official metadata before enablement.

| Indicator ID | Label | Source | Frequency | Approved canonical intent | Approved role |
|---|---|---|---|---|---|
| `obs_labor_payroll_total` | Total nonfarm payroll employment | BLS CES; candidate official series `CES0000000001` | Monthly | Level, seasonally adjusted, U.S., persons/thousands as official metadata states | Vertical slice |
| `obs_labor_unemployment_u3` | U-3 unemployment rate | BLS CPS; candidate `LNS14000000` | Monthly | Percent, seasonally adjusted, U.S., civilian noninstitutional population scope | Vertical slice |
| `obs_labor_participation` | Labor-force participation rate | BLS CPS; candidate `LNS11300000` | Monthly | Percent, seasonally adjusted, U.S., official population scope | Vertical slice |
| `obs_labor_initial_claims` | Initial unemployment-insurance claims | DOL ETA | Weekly | Count, seasonally adjusted, U.S.; advance/revised status explicit | Vertical slice |
| `obs_labor_job_openings` | Total nonfarm job openings | BLS JOLTS | Monthly | Level, seasonally adjusted, U.S.; exact official series ID discovered from metadata | Vertical slice |
| `obs_labor_hires` | Total nonfarm hires | BLS JOLTS | Monthly | Level, seasonally adjusted, U.S.; exact official series ID discovered from metadata | Vertical slice |
| `obs_prices_cpi_all` | CPI-U all items | BLS CPI; candidate `CUSR0000SA0` | Monthly | Index, seasonally adjusted, U.S. city average | Registry only; not first slice |
| `obs_output_real_gdp` | Real gross domestic product | BEA NIPA | Quarterly | Chained-dollar level, seasonally adjusted annual rate, U.S.; table/line discovered from API metadata | Registry only; mixed-frequency follow-on |

No additional indicator enters MVP without a recorded scope amendment, source/rights review, and test impact.

## 3. Source Registry and health design

Each `source_definition` records stable identity separately from mutable operational state:

```text
source_id, provider_id, dataset_id, authority_tier
official_metadata_url, sanitized_endpoint_template, transport_method
credential_requirement_class, credential_renewal_or_recheck_rule
request_quota, rate_limit, max_items_or_series_per_request
max_historical_range_per_request, retry_backoff_policy
expected_frequency, release_rule, timezone, holiday_policy
revision_policy, fallback_source_ids, methodology_url
terms_url, terms_version_id, terms_evidence_fingerprint
terms_reviewed_at, terms_next_recheck_at, terms_reviewer
rights_policy_id, schema_fingerprint_expected
enabled, owner, values_verified_at, definition_version
```

Each `source_evaluation` is append-only and records:

```text
evaluation_id, source_id, evaluated_at, expected_release_at
last_successful_retrieval_at, last_new_observation_at
last_official_publication_at, observed_schema_fingerprint
health_state, freshness_state, reason_codes
attempt_count, response/content hash references, run_id
```

Freshness is cadence-relative. The D-009 heartbeat evaluates whether work is warranted at least every four hours during normal MVP operation; it does not force every source to be fetched, recomputed, or published. States are `CURRENT`, `EXPECTED_NOT_DUE`, `DUE`, `DELAYED`, `STALE`, `UNAVAILABLE`, `SCHEMA_CHANGED`, `VALIDATION_FAILED`, `RIGHTS_BLOCKED`, and `UNKNOWN`. `UNKNOWN`, schema drift, rights failure, quota/credential limits, or a missed expected release prevents activation of affected new claims. Candidate-only failure preserves prior content only while it remains valid under current rights/security rules.

Credentials may arrive in query parameters, request bodies, or headers. Store only sanitized endpoint identity; redact secrets from persisted URLs/bodies/headers, logs, telemetry, errors, inspectable hashes, artifacts, and public provenance.

## 4. Logical storage and bitemporal design

Technology selection is deliberately deferred. The logical design must be implementable in a local, reproducible vertical slice without committing to a cloud provider.

### Cheapest-adequate candidate evaluation

| Candidate | Fit for first slice | Decision posture |
|---|---|---|
| Immutable raw/source files + content hashes | Strong reproducibility and retry boundary; required conceptually | Recommended logical layer; format chosen after approval |
| Parquet normalized/versioned datasets | Compact typed columnar files, portable across Windows/Linux, no always-on service | Recommended implementation candidate; dependency/version not selected or installed |
| DuckDB over local Parquet | Bitemporal/as-of analytical SQL with no server process and bounded local/CI operation | Recommended implementation candidate; must pass exact-version/license/reproducibility tests before use |
| Always-on relational/cloud database | Operational overhead and recurring cost exceed first-slice need | Rejected for the initial slice absent measured evidence and new approval |
| JSON/CSV only | Useful exchange/fixture formats but weaker typed analytical/query behavior | Allowed at boundaries, not preferred as sole analytical store |

The recommended starting shape is immutable raw artifacts plus versioned Parquet queried locally with DuckDB or an equivalently bounded tool. This is a review proposal, not a permanent technology/provider choice and creates no dependency or data file.

### Immutable capture layers

1. `retrieval_run`: `run_id`, `source_id`, trigger reason, `scheduled_period`, `idempotency_key`, start/end, collector version, source-definition version, `attempt`, `status`.
2. `raw_object`: source-object/content hash, source release/publication identity, media type, sanitized retrieval identity, proven public-availability time, AUXSAYS retrieval time, parser eligibility, rights classification, and retention state. Raw bytes are never public by default and may be governed-deleted/restricted when current legal/security policy requires it.
3. `normalized_record`: deterministic parser/version, raw-object hash, source-native identity, validation result.
4. `observation_version`: canonical indicator/entity/geography, value/unit, valid interval, proven public-availability time, AUXSAYS retrieval time, AUXSAYS system-accepted interval, source release/object identity, revision/republication sequence/status, rights state, and provenance chain.
5. `crosswalk_version` and `crosswalk_member`: version/effective interval, source/target vocabularies, weights, confidence/evidence type, provenance, approval state.
6. `source_evaluation`: cadence-relative operational evidence described above.
7. `public_snapshot_candidate`: immutable manifest of only allowlisted, rights-cleared derived records plus hashes and contract/schema versions.

### Bitemporal rules

- `valid_start`/`valid_end` describe when the statistic applies in observed reality.
- `source_published_at` is when that exact version was officially/publicly available, only where an authoritative historical artifact proves it.
- `retrieved_at` is when AUXSAYS fetched the exact artifact. `system_known_start` is when AUXSAYS successfully validated and accepted it; `system_known_end` closes when a later accepted version supersedes it operationally.
- `PUBLICLY_AVAILABLE_AS_OF(T)` admits only exact versions with proven source public availability at or before T. It is for retrospective methodological research/backtesting with authoritative archived evidence.
- `OPERATIONALLY_KNOWN_AS_OF(T)` admits only versions retrieved and accepted by AUXSAYS at or before T. It preserves real retrieval/validation lag and governs live-system accountability.
- These replay modes are named and separate. A current download cannot prove an earlier publication time, and an earlier observation period never backdates availability or system acceptance.
- A revision inserts a new immutable `observation_version`; it never overwrites the prior value.
- Current-truth queries select the latest currently accepted version. Replay queries explicitly choose public-availability or operational-knowledge semantics and constrain valid time separately.
- Unknown release/publication time is not guessed. Such records remain quarantined or use a conservative documented bound that cannot create look-ahead.
- Mixed-frequency state builders use the latest eligible observation known at the state cutoff, retain age/staleness, and never backfill a later revision into an earlier snapshot.
- A revision inserts a new version. A later official release containing the same number is still a distinct publication/knowledge event; retrying the exact same object remains idempotent.
- Every derivation records input observation-version IDs, code/config version, replay mode/cutoff, and source snapshot ID.

## 5. Ontology and crosswalk design

Canonical identifiers are namespaced and versioned for indicator, unit, seasonal adjustment, geography, industry, occupation, entity, and source-native concepts. Crosswalks are explicit many-to-many mappings, never assumed one-to-one.

Required crosswalk fields include source/target namespace and version, member IDs, effective dates, weight and weight basis, geography, provenance, evidence classification, quality state, reviewer/approval status, and supersession link. Weights must be validated for range and expected sums where applicable. Unresolved or ambiguous mappings remain candidates and cannot silently aggregate public facts.

The first slice needs only source-series-to-canonical-indicator mappings and U.S.-national geography/unit vocabularies. NAICS/SOC/entity/facility mapping is deferred until an approved later scope needs it.

## 6. Machine-enforceable rights model

Each source/dataset and, where necessary, each record carries:

```text
license_id, license_version_or_retrieved_at, terms_url
terms_version_id, terms_evidence_fingerprint, reviewed_at
next_recheck_at, reviewer
retrieval_or_ingestion_allowed, raw_retention_allowed
derived_retention_allowed, transformation_allowed
internal_analytical_use_allowed, model_feature_use_allowed
model_training_or_ml_use_allowed
public_display_allowed, public_redistribution_allowed
export_or_download_allowed, commercial_use_allowed
attribution_required, attribution_text, citation_url
retention_class, retention_expires_at, raw_publication_allowed
geographic_or_use_limits, review_status
```

Allowed values are explicit `ALLOW`, `DENY`, or `UNKNOWN`; absence is `UNKNOWN`. Each operation is independent: public display does not imply model training, internal analysis does not imply redistribution, and public accessibility does not imply commercial/export permission. `DENY`, `UNKNOWN`, expiration, terms change, or fingerprint/rule mismatch fails closed for that operation.

An ordinary candidate-only rights failure leaves a still-currently-valid snapshot active. If re-evaluation revokes rights for content already current, that snapshot is no longer valid: build a rights-safe replacement/unavailable state and atomically activate it, or atomically withdraw the pointer. Do not mutate the immutable artifact. Record invalidation/tombstone status and the governing rule where permitted.

Immutable semantic history does not force retention of prohibited bytes. Required deletion/restriction removes raw payloads under policy, preserves only permitted hash/identity/provenance/tombstone evidence, records actor/rule/effective time, marks reproduction degraded/unavailable, and never invents replacement data.

## 7. Atomic publication and idempotency

- Candidate snapshot ID is derived from schema/contract versions, knowledge cutoff, sorted publishable record identities, and content hashes.
- Generation writes a complete immutable candidate, then validates schema, rights, provenance, publication class, referential integrity, hashes, and compatibility.
- Activation changes one current-manifest pointer only after all checks pass. Readers load the pointer and one immutable snapshot; partial candidates are unreachable.
- A complete fixture snapshot (`publicationClass: fixture`) and a complete factual snapshot (`publicationClass: factual`) are separate alternatives. Factual snapshots contain rights-cleared `OBS` and approved deterministic `CALC` only; no fixture `FCST`, `SCEN`, rankings, or synthetic claims. Unsupported Outlook is explicitly unavailable/not yet supported. Test harnesses may switch snapshots but never merge their claim sets.
- An identical source object/input/config/code snapshot produces the same logical output and does not create duplicate observations or public activations. A separate official publication/release remains a distinct knowledge event even when its value is unchanged.
- Runs use a deterministic idempotency key, bounded retries with backoff, and one concurrency lease per source/release window. A retry may resume or safely repeat immutable stages.
- Candidate failure before activation preserves the prior pointer only if it remains valid under current rights/security rules. Applicable revocation triggers atomic rights-safe replacement/unavailable activation or withdrawal. Rollback may reactivate only a currently valid immutable snapshot.

## 8. Exact first vertical slice

Goal: prove authoritative-source capture through a factual, non-predictive read-only candidate payload for six U.S. labor indicators—payrolls, U-3 unemployment, participation, initial claims, job openings, and hires—without forecasts, Phase-4 relationships, or production deployment.

The future, separately authorized implementation must prove:

1. BLS CES/CPS/JOLTS and DOL sources are registered with official metadata, rights, cadence, and schema fingerprints.
2. A bounded historical window is captured with content hashes and normalized into the six canonical indicators under current retention rights.
3. Gate-A revision proof uses an original DOL Weekly Claims release containing an advance value and the subsequent original DOL release containing its revised value, with separate source identities/hashes and independently proven official publication times. Synthetic corrections remain edge fixtures only.
4. Current-truth returns the DOL revision; `PUBLICLY_AVAILABLE_AS_OF` before the later release returns the advance value; `OPERATIONALLY_KNOWN_AS_OF` reflects the actual AUXSAYS retrieval/validation lag.
5. Weekly and monthly values build an as-of state without future leakage and expose age/freshness.
6. A complete rights-cleared `publicationClass: factual` candidate conforms to the BINDING Public Data Interface, contains `OBS`/approved deterministic `CALC` only, and uses unavailable/not-yet-supported Outlook. It remains unactivated until separate Gate-A/activation approval.
7. The same run repeated creates no duplicate versions or activation and performs no work when D-009 evaluation finds no due/material change.
8. All work runs locally or in an already-approved bounded environment. No cloud provider, commercial source, model, or recurring paid service is required.
9. Local development may switch between the complete fixture and complete factual candidates through the unchanged Public Data Interface; it never replaces individual fixture claims in place or mixes classes. No real `FCST`, `SCEN`, ranking, propagation, industry forecast, or occupation forecast is introduced.
10. FRED/ALFRED, CPI ingestion, and GDP ingestion remain outside the first slice.

Success is measurable only when the Data Integrity contracts are BINDING and Gate-A evidence passes. This draft does not claim that result.

## 9. Test plan

| Layer | Required proof before Gate A |
|---|---|
| Contract/schema | Header/status/index consistency; observation, source, health, crosswalk, rights, and public schemas reject missing/unknown semantics |
| Parser/normalizer | Golden official-format fixtures; malformed/truncated/oversized/duplicate/encoding/schema-drift cases; deterministic normalized hashes |
| Bitemporal | Initial/revised values; separate public-availability/retrieval/system-acceptance cutoffs; public versus operational replay; unknown publication; no later-revision leakage |
| Mixed frequency | Weekly/monthly cutoff boundaries, publication lag, missing releases, holidays, stale values, timezone edges |
| Source health | D-009 no-op heartbeat, due/delayed release, quota/rate/history boundaries, credential renewal, retry/backoff, terms/schema change, recovery |
| Rights/security | Independent analytical/model-training/commercial/export/retention/public permissions; terms fingerprints/recheck; candidate failure; current revocation/withdrawal; governed deletion; URL/body/header secret redaction; hostile inputs |
| Crosswalk | Version/effective dates, many-to-many weights, unresolved candidates, geography/unit incompatibility, supersession |
| Idempotency/concurrency | Exact-object retry versus same-value distinct release, retry after each stage, overlapping workers, lease expiry, deterministic outputs |
| Publication | Separate complete fixture/factual snapshots; no factual `FCST`/`SCEN`; candidate-only failure; current-rights revocation; atomic replacement/withdrawal; reader never mixes snapshots |
| Gate-A factual revision | Original DOL advance/subsequent-revision release pair, proven publication times, immutable identities/hashes, current/publicly-available/operational queries; no ALFRED |
| Reproducibility | Clean Windows and Linux execution from pinned code/config/fixtures produces matching logical results and provenance |
| Cost | Bounded request/storage/runtime counters demonstrate D-010 compute-once/read-many and no paid dependency requirement |

No acceptance test may call an uncontrolled external endpoint. Network integration checks, when later authorized, use strict allowlists, budgets, and non-secret logs and remain separate from deterministic fixtures.

## 10. Resolved decisions and implementation choices

- **O-003 — ACCEPTED / RESOLVED, Taylor 2026-08-17:** Eight indicators are approved in the bounded registry; only six labor indicators and BLS CES/CPS/JOLTS plus DOL Weekly Claims are enabled in the first slice.
- **O-004 — RESOLVED, REJECTED / NOT AUTHORIZED, Taylor 2026-08-17:** Current FRED/ALFRED terms are materially incompatible with planned software/system, archival/storage/database, replay, and eventual model uses. No pipeline use absent written permission or changed terms plus new rights review and Taylor approval.
- **IMPLEMENTATION CHOICE P3-IC-001:** Select a minimal local storage engine/file format only after contracts are BINDING and acceptance fixtures exist; preserve the logical contract and provider neutrality.
- **IMPLEMENTATION CHOICE P3-IC-002:** Select official bulk files versus API per source using measured reproducibility, vintage coverage, rate limits, and cost; do not embed secrets or require a paid source.
- Risks R-005, R-006, R-011, R-013, and R-019 through R-025 in `RISKS.md` govern this design.

## 11. Review and change history

- 1.0.0 (2026-08-17): Taylor-approved design after external-review corrections: O-003 accepted, O-004 rejected, FRED/ALFRED removed, DOL revision proof selected, dual replay semantics, snapshot separation, current-rights withdrawal, governed deletion, expanded rights, operational limits, and credential redaction.
- 0.1.0 (2026-08-17): Initial Phase-3 review design. DRAFT; no implementation authority.
