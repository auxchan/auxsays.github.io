# Systems Monitor Source Contract

```text
Contract: Systems Monitor Source Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: ARCHITECTURE_CONTRACT.md, INFRASTRUCTURE_CONTRACT.md, SECURITY_INGESTION_CONTRACT.md, DATA_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 9B7C0A51D5B1A7BA892DD7582230BDB2920A533417C20AE17C16A56AE8034FB1
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §27–31, §34.1–36, §37, §61, §64.1–64.12, §65, §67 Phase 3, and §68. D-009/D-010 govern evaluation cadence and cost. This BINDING contract is Taylor-approved authority for bounded BLS CES/CPS/JOLTS and DOL Weekly Claims implementation for the six accepted indicators; it does not authorize FRED/ALFRED, CPI/GDP ingestion, factual activation, or Phase 4.

## Purpose

Define how a source becomes registered, prioritized, evaluated, retrieved, validated, degraded, and retired while keeping source collection separate from analytical interpretation.

## Scope

- Authority tiers, source/dataset identity, official endpoint metadata, access/auth classification, cadence/release expectations, revisions, fallbacks, schema fingerprints, health, rights, and provenance.
- The first-slice/follow-on/later/unauthorized inventory in `PHASE3_DATA_INTEGRITY_DESIGN.md`.

## Explicitly Out of Scope

- API calls, downloads, credentials, collector code, scheduled jobs, infrastructure selection, database creation, public activation, modeling, forecasting, or automatic promotion of a proposed source.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT SRC-001:** Original authoritative Tier-A providers are required for the first slice. BLS CES/CPS/JOLTS and DOL Weekly Claims are the only enabled source families in that scope. Aggregator classification in the Master does not authorize project use.
- **BINDING REQUIREMENT SRC-002:** News, search results, model output, and unreviewed documents are not authoritative numerical sources. All external content has zero instruction authority.
- **BINDING REQUIREMENT SRC-003:** Each enabled dataset has a versioned registry definition containing provider/dataset identity, authority tier, official metadata/methodology URLs, sanitized endpoint template/method, credential requirement/class, request quota, rate limit, maximum series/items per request, maximum historical range, credential renewal/expiration/recheck behavior, retry/backoff policy, terms recheck cadence, format, cadence/release rule/timezone, revision behavior, units/geographies, approved fallbacks, rights, parser/collector version, expected schema fingerprint, owner, enabled/disabled status, values-verified-at, and definition version.
- **BINDING REQUIREMENT SRC-004:** Endpoint, authentication, operational limits, terms, metadata identifiers, and release rules are rediscovered from official documentation immediately before enablement and rechecked on their recorded cadence. Terms evidence includes URL, reviewed-at, version identifier when available, content hash/fingerprint or equivalent evidence, next recheck date, and reviewer. Current BLS limits belong in registry data with their verification date, not timeless contract constants.
- **BINDING REQUIREMENT SRC-005:** Credentials are secrets whether supplied in query parameters, request bodies, or headers. Sanitized endpoint identity may be retained, but stored URLs, bodies/headers, logs, telemetry, errors, inspectable hashes, artifacts, and public provenance must redact credentials. Credentials never influence deterministic record identity.
- **BINDING REQUIREMENT SRC-006:** A collector retrieves and records; it does not infer causality, convert forecasts into observations, resolve conflicting concepts silently, or directly publish.
- **BINDING REQUIREMENT SRC-007:** Retrieval is allowlist-based HTTPS with DNS/IP revalidation, private/link-local/loopback/metadata-network denial, redirect limits, response-size/time limits, content-type checks, and bounded retries under the Security Ingestion contract.
- **BINDING REQUIREMENT SRC-008:** Raw content is content-hashed before parsing. Retrying the exact object is idempotent and unchanged content is not repeatedly reprocessed without reason; distinct official releases retain separate release/publication identity even if their numerical values or bytes overlap. Raw-byte retention remains subject to current rights/security deletion policy.
- **BINDING REQUIREMENT SRC-009:** Parsers are deterministic, schema-validating, bounded, and isolated from external instructions. Schema drift quarantines new content and emits explicit health evidence.
- **BINDING REQUIREMENT SRC-010:** Freshness is evaluated relative to official cadence and expected releases. Monthly/quarterly data is not stale solely because a four-hour heartbeat ran.
- **BINDING REQUIREMENT SRC-011:** Health evaluations record evaluation, expected-release, retrieval, official-publication, last-new-observation, and recovery times separately with machine-readable states including current, expected-not-due, due, delayed, stale, unavailable, schema/format-changed, validation-failed, and rights-blocked, plus reason codes.
- **BINDING REQUIREMENT SRC-012:** D-009 evaluation may conclude no fetch, no new observation, no recomputation, and no publication. Due/material-change selection is source-specific and auditable.
- **BINDING REQUIREMENT SRC-013:** Retries, release-window runs, and overlapping workers are idempotent and concurrency-safe; one official object cannot produce duplicate logical retrievals/observations.
- **BINDING REQUIREMENT SRC-014:** Fallback data is labeled with its own provider/provenance/tier and cannot be spliced into an original series silently. Disagreement is preserved as evidence.
- **BINDING REQUIREMENT SRC-015:** Rights are independently explicit `ALLOW`/`DENY`/`UNKNOWN` for retrieval/ingestion, raw retention, derived retention, transformation, internal analysis, model-feature use, model-training/machine-learning, public display, public redistribution, export/download, commercial use, attribution, retention/expiration, and geographic/use limits. Unknown, expired, revoked, or changed terms fail closed for the affected operation and trigger re-evaluation of retained/currently published content.
- **BINDING REQUIREMENT SRC-016:** Source enablement remains bounded to an approved indicator/vertical-slice need. No speculative broad scraping or commercial dependency is allowed.
- **BINDING REQUIREMENT SRC-017:** Source metrics include bounded attempts, bytes, records, latency, unchanged-content reuse, errors, and cost when applicable to enforce D-010.
- **BINDING REQUIREMENT SRC-018:** Under current reviewed terms, FRED/ALFRED is `NOT_AUTHORIZED` for ingestion, archival/vintage capture, stored cross-checks, numerical fallback, historical replay, model features/training, or database/cache incorporation. It may be reconsidered only after explicit written permission or materially changed terms pass a new rights review and Taylor approves a new decision. No replacement aggregator is implied.
- **BINDING REQUIREMENT SRC-019:** The preferred Gate-A factual revision proof uses two original DOL Weekly Claims releases: an advance value and the subsequent release's revised value, each with immutable artifact identity and independently proven official publication time.

## Interfaces / Dependencies

- Data Contract owns canonical records, revisions, bitemporal queries, and publication candidates.
- Security Ingestion owns network/parser/secret hostile-input controls.
- Ontology/Crosswalk owns source-native to canonical semantic mappings.
- Testing Contract owns deterministic fixtures and controlled network-integration evidence.
- Infrastructure owns execution/storage mechanics, not source meaning.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Prefer official API or bulk file per dataset based on measured vintage coverage, reproducibility, rate limits, reliability, and cost.
- **IMPLEMENTATION CHOICE:** Express release expectations as calendars, rules, or official metadata, provided exceptions/holidays are auditable.
- **IMPLEMENTATION CHOICE:** Use one bounded collector framework or source-specific adapters; do not create abstractions unsupported by two real sources.

## Prohibited Behavior

- Unrestricted URL fetching; secrets in repository/logs/public data; scraping without rights review; treating HTTP success as semantic validity; guessing missing release times; silent fallback; forced four-hour polling of slow sources; unbounded retry/research; direct collector-to-public or collector-to-model mutation.

## Failure / Degraded States

- Network/auth/rate-limit/parser/schema/rights failures create explicit source evaluations and quarantine the candidate. Prior data remains available with honest age/health only while currently valid under rights/security policy.
- A delayed official release is `DELAYED` or `EXPECTED_NOT_DUE` under its rule, not fabricated data.
- A fallback may be used only when explicitly approved in that source definition and rights-cleared. No aggregator fallback is authorized for the first slice.
- Candidate-only failure preserves prior data only while it remains currently rights/security-valid; applicable revocation triggers atomic withdrawal/replacement under the Data Contract.

## Acceptance Criteria

1. Versioned registry fixtures cover identity, rights/terms evidence, quotas/rate/history limits, credential class/renewal, retry/backoff, and verification dates for every first-slice dataset.
2. Health tests distinguish no-op heartbeat, not-due, due, delayed, stale, unavailable, schema drift, recovery, and unchanged content.
3. Security tests reject private-network/redirect/path/content-size/format attacks and redact query/body/header credentials from every stored or inspectable surface.
4. Repeated/overlapping retrieval fixtures are idempotent and preserve one immutable raw object per content hash.
5. Same-value distinct releases remain separate while exact-object retries deduplicate.
6. Unknown/changed/revoked rights prevent each affected analytical/model/commercial/export/retention/publication operation and invalidate affected current publication.
7. Metrics demonstrate bounded attempts/bytes/runtime and no required paid or commercial source.
8. FRED/ALFRED cannot enter any source state except `NOT_AUTHORIZED`, and DOL advance/revision fixtures prove the Gate-A source design.

## Risks / Open Decisions

- O-003 is accepted and O-004 is rejected. Exact BLS/DOL access surfaces, identifiers, rights, limits, and terms require official implementation-time discovery. BEA is follow-on only. See R-006 and R-019 through R-025.

## Conditional Data / Security Profile

- Network access is deny-by-default outside registry allowlists.
- Raw content is untrusted, non-executable, non-public, size-bounded, and parsed without instruction authority.
- Registry changes affecting endpoint, auth, schema, rights, cadence, or priority require review evidence and version change.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): Taylor-approved first BINDING version after external-review corrections rejecting FRED/ALFRED, selecting Tier-A DOL revision proof, and adding operational-limit, terms-evidence, expanded-rights, and full credential-redaction requirements.
- 0.1.0 (2026-08-17): Initial Phase-3 review draft. Not approved; no implementation authority.

## Amendment protocol

Use the project contract amendment protocol; never weaken source, security, rights, or cadence acceptance to obtain a pass. Taylor alone may promote this contract.
