# Systems Monitor Phase-3 Testing Contract

```text
Contract: Systems Monitor Phase-3 Testing Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: DATA_CONTRACT.md, SOURCE_CONTRACT.md, ONTOLOGY_CROSSWALK_CONTRACT.md, SECURITY_INGESTION_CONTRACT.md, RELEASE_ACCEPTANCE_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 02BA2C0BB63FA2534C14BCCB33A3346D59B6BCFF6B366A8F23D882D311FB7835
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §29–32, §34.1–35.5, §38.2, §61–64.1, §64.2–64.12, §65, §67 Phase 3, and §68. This BINDING contract is Taylor-approved Phase-3 testing authority. It does not itself pass Gate A, authorize factual public activation, or permit Phase 4/deployment.

## Purpose

Define objective evidence required to approve and later implement Phase-3 Data Integrity without weakening tests, relying on live-network nondeterminism, leaking secrets, or claiming factual readiness before Gate A passes.

## Scope

- Contract/schema, deterministic fixture, parser/normalizer, bitemporal, mixed-frequency, source-health, ontology/crosswalk, rights/security, idempotency/concurrency, publication, reproducibility, and cost tests.
- Gate-A evidence for the exact approved vertical slice.

## Explicitly Out of Scope

- Phase-4 state/dependency/model tests, forecast skill/backtesting, UI visual-polish closure, production monitoring, deployment, or public factual activation.
- Treating a synthetic fixture as evidence that a real authoritative source was ingested correctly.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT TST-001:** Tests derive from the approved contracts and never weaken, skip, relabel, or rewrite acceptance merely to obtain a pass.
- **BINDING REQUIREMENT TST-002:** Deterministic tests use small, license-reviewed, non-secret fixtures with recorded origin/format version/content hash or clearly labeled synthetic hostile cases.
- **BINDING REQUIREMENT TST-003:** Default unit/integration suites make no uncontrolled external network calls. Later authorized network checks are allowlisted, bounded, separately labeled, secret-safe, and cannot be the sole correctness evidence.
- **BINDING REQUIREMENT TST-004:** Golden parser tests cover official-format success plus malformed, truncated, oversized, duplicate, encoding, missing-field, unknown-field, type, schema-drift, and hostile-content cases.
- **BINDING REQUIREMENT TST-005:** Bitemporal tests cover initial values, multiple revisions, valid intervals, interval closure, and cutoffs before/at/after official publication, retrieval, and system acceptance. They independently test `PUBLICLY_AVAILABLE_AS_OF` against proven archived publication and `OPERATIONALLY_KNOWN_AS_OF` against actual AUXSAYS retrieval/validation, including lag and unknown publication time; neither mode may leak later revisions or substitute for the other.
- **BINDING REQUIREMENT TST-006:** Mixed-frequency tests cover weekly/monthly/quarterly cutoffs as applicable, official publication lag, carry-forward age, missed/holiday releases, timezone edges, and stale/unavailable inputs.
- **BINDING REQUIREMENT TST-007:** Source-health/operational tests cover D-009 no-op evaluation, not-due, due, delayed, stale, failed retrieval, documented quota exhaustion, per-window rate limits, maximum items/history boundaries, credential renewal/expiration, bounded retry/backoff, terms-recheck due/change, schema drift, recovery, and unchanged-content caching.
- **BINDING REQUIREMENT TST-008:** Rights tests independently vary `ALLOW`, `DENY`, and `UNKNOWN` for ingestion, raw/derived retention, transformation, internal analysis, model-feature/training, public display/redistribution, export/download, commercial use, attribution, expiration, and use/geography restrictions. They cover changed/revoked terms, candidate-only failure preserving a still-valid snapshot, current-content revocation causing atomic replacement/withdrawal, and governed raw-byte deletion/restriction with permitted tombstone metadata. Failure is closed per operation.
- **BINDING REQUIREMENT TST-009:** Security tests cover SSRF/private/link-local/metadata networks, redirect and DNS rebinding defenses where applicable, size/time/archive/path bounds, credential redaction from query URLs/request bodies/headers/logs/telemetry/errors/inspectable hashes/public provenance, stored XSS, query/config injection, and spreadsheet formula injection.
- **BINDING REQUIREMENT TST-010:** Ontology tests cover version/effective dates, source identity preservation, one/many mappings, weights/tolerances, unit/geography/seasonal incompatibility, unresolved candidates, and supersession.
- **BINDING REQUIREMENT TST-011:** Idempotency/concurrency tests retry after each durable boundary, repeat the exact source object, ingest two distinct releases containing the same value, overlap workers, expire/reacquire leases, and prove exact retries do not duplicate while separate publication events remain auditable and no partial activation occurs.
- **BINDING REQUIREMENT TST-012:** Publication tests switch only between separate complete snapshots: fixture snapshots may carry synthetic UI claims; factual snapshots contain rights-cleared `OBS`/approved deterministic `CALC` only, never fixture `FCST`, `SCEN`, rankings, or mixed fixture/factual claims. They prove candidate-only failure leaves a currently valid prior pointer, current-content rights revocation atomically replaces/withdraws it, readers never observe mixed versions, and unsupported Outlook is unavailable/not-yet-supported.
- **BINDING REQUIREMENT TST-013:** Windows and Linux clean-environment tests use pinned code/config/fixtures and compare logical records, hashes after defined canonicalization, provenance, and query results.
- **BINDING REQUIREMENT TST-014:** D-010 evidence records bounded requests, bytes, runtime, storage growth, cached/no-op work, and public-read reuse; no paid service or permanent cloud choice is required for the first slice.
- **BINDING REQUIREMENT TST-015:** Real-source Gate-A revision evidence uses Tier-A authoritative material, preferably a DOL Weekly Claims advance release and the subsequent original DOL release that revises that same week. Tests retain both immutable artifacts, hashes, release identities, and independently proven official publication times; current-truth returns the revision while a pre-revision publicly-available-as-of query returns the advance value. Synthetic revisions test edges only and cannot satisfy factual Gate A. FRED/ALFRED is not used.
- **BINDING REQUIREMENT TST-016:** Test reports record contract/schema/source/config/code versions, environment, start/end, assertions, failures, known gaps, and artifact hashes. Secrets and restricted/raw content are excluded from public/repository reports.
- **BINDING REQUIREMENT TST-017:** Skips/quarantines are explicit failures or approved limitations for the affected capability; they cannot silently count as PASS.

## Interfaces / Dependencies

- Data, Source, and Ontology/Crosswalk contracts define subject behavior.
- Security Ingestion defines hostile-input and network boundaries.
- Release Acceptance owns capability-gate promotion; this contract supplies but cannot self-accept evidence.
- CI/local runners are implementation mechanics and do not change required outcomes.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Select test framework, fixture serialization, property-based tools, and coverage tooling after dependency review and authorization.
- **IMPLEMENTATION CHOICE:** Use emulators/fakes for network/storage failure injection if observable contract behavior remains identical.
- **IMPLEMENTATION CHOICE:** Split fast deterministic, controlled network, security, and reproducibility suites while retaining one auditable Gate-A result.

## Prohibited Behavior

- Live production endpoints in default tests; real secrets in fixtures/logs; snapshots updated just to make failures disappear; synthetic data labeled factual; merged fixture/factual snapshots; fixture forecasts in factual snapshots; order-dependent tests; ignored timezones; conflated public/operational replay; current-data-only replay; unbounded fuzz/network workloads; FRED/ALFRED use; Gate-A PASS with missing blocking evidence.

## Failure / Degraded States

- Any blocking contract, rights, temporal-integrity, security, idempotency, atomic-publication, or reproducibility failure keeps Gate A failed and prevents factual activation.
- External network unavailability may defer a separately authorized integration check but cannot erase deterministic evidence or justify fabricated success.
- Platform-only failure is recorded and blocks cross-platform acceptance until resolved or explicitly amended by Taylor.

## Acceptance Criteria

1. Every DAT/SRC/ONT binding requirement has at least one traceable test or an explicit pre-implementation design-only disposition.
2. The full matrix in `PHASE3_DATA_INTEGRITY_DESIGN.md` passes on approved fixtures with no uncontrolled network call.
3. The authorized vertical slice proves a Tier-A DOL advance/revision pair without look-ahead and without FRED/ALFRED.
4. Rights/security failures fail closed; expanded rights, current-publication revocation, retention deletion/tombstone, exact-retry versus same-value-release, and atomic rollback/withdrawal proofs pass.
5. Clean Windows/Linux runs are reproducible and report bounded D-009/D-010 metrics.
6. Gate-A report lists every artifact/version/hash, all failures/gaps, and receives the required human/Taylor acceptance; contract authors do not self-promote it.

## Risks / Open Decisions

- Exact test dependencies remain unselected and uninstalled pending contract approval and license/security review.
- O-003 is accepted and O-004 rejects FRED/ALFRED. DOL Weekly Claims is the preferred Tier-A revision proof. See R-019 through R-025.

## Conditional Test / Security Profile

- Hostile fixtures are synthetic or safely minimized; they are never executed as instructions or active markup/formulas.
- Controlled network checks use dedicated low-privilege credentials, strict budgets, response bounds, and redacted logs.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): Taylor-approved first BINDING version after external-review corrections for dual replay, DOL Tier-A revision proof, snapshot separation, current-rights revocation, governed deletion, expanded rights, operational limits, and full credential redaction.
- 0.1.0 (2026-08-17): Initial Phase-3 review draft. Not approved; Gate A not evaluated.

## Amendment protocol

Use the project amendment protocol and identify requirement coverage, fixture migration, platform impact, and whether acceptance is weakened. Taylor alone may promote this contract.
