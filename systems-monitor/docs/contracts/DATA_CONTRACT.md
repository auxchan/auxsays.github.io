# Systems Monitor Data Contract

```text
Contract: Systems Monitor Data Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: ARCHITECTURE_CONTRACT.md, INFRASTRUCTURE_CONTRACT.md, PUBLIC_DATA_INTERFACE_CONTRACT.md, SECURITY_INGESTION_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 78903F61546F7B27035ED28F3FA676C34D98347CE854AF5C0FD23F3CC1908237
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §27–32, §35–37.1, §61, §64.1–64.12, §65, §67 Phase 3, and §68. D-009 and D-010 add Taylor-approved post-V4.1 cadence and cost requirements. This BINDING contract is Taylor-approved authority for the bounded Phase-3 implementation scope; it does not authorize factual public activation or Phase 4.

## Purpose

Stabilize the canonical observation, time, revision, provenance, storage, rights, and public-publication semantics needed to turn authoritative releases into reproducible factual records without look-ahead or internal-schema leakage.

## Scope

- Logical raw, normalized, observation-version, derivation, source-snapshot, and public-candidate records.
- Valid time, proven source-publication/public-availability time, AUXSAYS retrieval time, AUXSAYS system-known/accepted time, and revision history.
- Mixed-frequency as-of reads, typed units/geographies, provenance, rights decisions, and immutable/atomic publication.
- The bounded Phase-3 design and first vertical slice in `PHASE3_DATA_INTEGRITY_DESIGN.md`.

## Explicitly Out of Scope

- Collector implementation, endpoint calls, downloaded data, database/Parquet creation, scheduling, deployment, fixture replacement, or cloud selection.
- State/dependency/allocation engines, causal edges, forecasts, scenarios, models, rankings, and Phase-4+ contracts.
- FRED/ALFRED use; CPI/GDP ingestion in the first slice; permanent technology/cloud selection; or factual public activation without later Gate-A/activation approval.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT DAT-001:** Every material record declares exactly one information state; Phase-3 observation storage accepts `OBS` and deterministic documented `CALC` only, never silently recasting `FCST` or `SCEN` as fact.
- **BINDING REQUIREMENT DAT-002:** Canonical observations have stable identity, source-native identity, source release/publication identity, exact source-object hash, indicator, value, unit, seasonal-adjustment state, geography/entity scope, valid interval, proven official publication/public-availability time when known, AUXSAYS retrieval time, AUXSAYS system-known/accepted interval, revision/republication status, rights state, and provenance.
- **BINDING REQUIREMENT DAT-003:** Valid time, proven source-publication/public-availability time, AUXSAYS retrieval time, and AUXSAYS system-known/accepted time are distinct and no one timestamp silently substitutes for another. `PUBLICLY_AVAILABLE_AS_OF(T)` admits only exact versions proven by an authoritative archived artifact to have been publicly available by T. `OPERATIONALLY_KNOWN_AS_OF(T)` admits only versions successfully retrieved, validated, and accepted by the running AUXSAYS system by T. Live accountability uses operational knowledge; retrospective methodological research may use public availability only with historical artifact/time proof.
- **BINDING REQUIREMENT DAT-004:** Revisions are immutable new versions. A later source release that republishes the same numerical value is a distinct knowledge event when its release/publication identity, object, or publication time differs; retrying the exact same source object remains idempotent. Overwriting or silently correcting a previously known value is prohibited.
- **BINDING REQUIREMENT DAT-005:** Missing official publication/public-availability time is never invented or inferred from a current download or the observation period. It remains unknown or uses an explicitly conservative documented non-leaking bound where permitted. Missing retrieval/acceptance evidence cannot be backdated.
- **BINDING REQUIREMENT DAT-006:** Intraday, daily, weekly, monthly, quarterly, annual, and irregular/release-driven records retain their native temporal meaning. Mixed-frequency state reads select the latest eligible value known at the cutoff, preserve each value's valid date/age/freshness, and never treat carry-forward as a new observation.
- **BINDING REQUIREMENT DAT-007:** Raw objects and normalized records are content-addressed and linked. Normalization is deterministic for the same raw content, parser version, registry version, and configuration. Semantic history is append-only, but legal/security policy may require governed deletion or access restriction of raw bytes under DAT-019.
- **BINDING REQUIREMENT DAT-008:** Every derived value records calculation identity/version, exact input observation-version IDs, configuration/code version, explicit replay mode/cutoff, and source-snapshot reference.
- **BINDING REQUIREMENT DAT-009:** Units, seasonal adjustment, geography, population/universe, frequency, and aggregation method are explicit. Incompatible concepts cannot be combined without an approved conversion/crosswalk.
- **BINDING REQUIREMENT DAT-010:** Rights are independently machine-enforced with explicit `ALLOW`, `DENY`, or `UNKNOWN` for retrieval/ingestion, raw retention, derived retention, transformation, internal analytical use, model-feature use, model-training/machine-learning use, public display, public redistribution, export/download, commercial use, attribution, retention/expiration, and geographic/use restrictions. Permission for one operation never implies another; missing, expired, conflicting, or unknown rights fail closed for the affected operation.
- **BINDING REQUIREMENT DAT-011:** Internal/raw records are private by default. Only an explicit allowlist of rights-cleared, schema-valid fields may enter a public candidate.
- **BINDING REQUIREMENT DAT-012:** Public snapshots are snapshot-wide and complete. A `publicationClass: fixture` snapshot may contain synthetic UI-test claims. A `publicationClass: factual` snapshot contains only rights-cleared factual `OBS` and approved deterministic `CALC`; it contains no fixture values, fixture `FCST`/`SCEN`, synthetic rankings, secrets, restricted data, raw objects, or internal diagnostics. Fixture and factual claim sets are never merged. Unsupported Outlook content in a factual snapshot uses the approved unavailable/not-yet-supported state.
- **BINDING REQUIREMENT DAT-013:** Public snapshots are immutable and activation/withdrawal is atomic. An ordinary candidate-only failure leaves the prior snapshot active only while that snapshot remains valid under current security and rights rules. If current rights/security policy revokes continued publication, the affected snapshot is invalidated and atomically replaced by a rights-safe snapshot/unavailable state or withdrawn; the old artifact is not mutated in place and its publication status is tombstoned where permitted.
- **BINDING REQUIREMENT DAT-014:** Runs and writes are idempotent, bounded, retry-safe, and concurrency-safe. Retrying the exact source object/retrieval cannot create duplicates, while distinct official releases remain distinct knowledge events even when their values are equal. Concurrent jobs cannot expose a partial candidate.
- **BINDING REQUIREMENT DAT-015:** D-009 is a maximum four-hour normal-MVP evaluation heartbeat, not a universal fetch/recompute/publication mandate. Source cadence, known releases, material changes, and affected-state recomputation govern work.
- **BINDING REQUIREMENT DAT-016:** D-010 requires compute-once/read-many outputs, measurable request/runtime/storage bounds, cached unchanged content, and no recurring paid infrastructure/API without measured justification and approval.
- **BINDING REQUIREMENT DAT-017:** Schema, parser, contract, configuration, rights-rule, crosswalk, source-snapshot, code versions, and permitted audit metadata required for reproduction are retained; raw-byte retention remains governed by DAT-019.
- **BINDING REQUIREMENT DAT-018:** Contradictory observations/provenance are preserved and exposed as quality evidence; the pipeline may not silently choose a convenient value.
- **BINDING REQUIREMENT DAT-019:** Immutable semantic history does not require indefinite retention of prohibited bytes. When legal/security/rights policy requires deletion or restriction, the system removes/restricts the affected raw payload, preserves only non-restricted identity/hash/provenance/tombstone metadata where permitted, records the rule/actor and effective time, marks reproduction degraded/unavailable honestly, and never invents a replacement value.
- **BINDING REQUIREMENT DAT-020:** Terms evidence records the terms URL, reviewed-at time, terms/version identifier when available, auditable content hash/fingerprint or equivalent evidence, next recheck date, and reviewer. A later terms change re-evaluates every affected retained and currently published artifact.

## Interfaces / Dependencies

- Source Contract supplies registered retrievals, official metadata, schema fingerprints, release expectations, and health evidence.
- Ontology/Crosswalk Contract supplies versioned semantic mappings.
- Security Ingestion governs network, parser, secret, hostile-content, rendering, query, path, and export boundaries.
- Infrastructure governs provider-neutral durable storage and atomic activation mechanics.
- Public Data Interface owns the stable read-only view-model; internal tables may not become its schema.
- Testing Contract defines the evidence required before Gate A.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Select a minimal local database, object/file format, or combination after approval, provided logical semantics, Windows/Linux reproducibility, and migration/export tests hold.
- **IMPLEMENTATION CHOICE:** Partition, index, compress, and cache immutable data according to measured workload.
- **IMPLEMENTATION CHOICE:** Represent open-ended knowledge intervals with a safe sentinel or null plus query constraints.
- **IMPLEMENTATION CHOICE:** Split public snapshots into immutable chunks if one manifest still guarantees a single consistent version.

## Prohibited Behavior

- Mutable in-place revision history; conflating valid/publication/retrieval/accepted time; backdating from a current download; later-vintage leakage; fabricated metadata; hidden unit/geography coercion; raw-table frontend access; partial public activation; mixing fixture and factual claims; preserving currently prohibited publication merely because it was once valid; treating immutable semantics as a mandate to retain legally prohibited bytes; secret/restricted-data publication; unbounded polling or paid infrastructure by default.

## Failure / Degraded States

- Invalid schema, time ambiguity, unknown rights, missing provenance, incompatible semantics, contradictory publication class, or hash failure quarantines the affected candidate.
- Source failure or delayed release marks explicit health/freshness state; it does not synthesize an observation or automatically invalidate an otherwise valid prior snapshot.
- New candidate failure preserves the last currently valid pointer. Rights/security revocation affecting current content instead triggers atomic rights-safe replacement/unavailable activation or withdrawal. Recovery is a new auditable event, never a history rewrite.

## Acceptance Criteria

1. Fixtures prove initial/revised values and separately correct current-truth, publicly-available-as-of, and operationally-known-as-of results across publication/retrieval/acceptance cutoffs.
2. Mixed weekly/monthly fixtures prove carry-forward age and no future leakage.
3. Every canonical observation traces to immutable raw content, source definition, parser/config version, and rights decision.
4. Each rights dimension can differ independently; `DENY`, `UNKNOWN`, expired, revoked, or incompatible rights prevent the affected operation.
5. Exact-object retry yields one logical retrieval while same-value republication retains distinct release knowledge; overlapping runs cannot duplicate activation.
6. Candidate-only failure preserves a currently valid prior snapshot; current-content rights revocation atomically replaces/withdraws it without mutating history.
7. Separate contract-valid fixture and factual snapshots can be selected in tests, but their claims cannot coexist; factual output is `OBS`/approved `CALC` only.
8. Governed raw-byte deletion/restriction retains only permitted tombstone/audit evidence and reports degraded reproducibility.
9. Request, runtime, storage, and publication counters demonstrate bounded D-009/D-010 behavior without a required paid service or cloud choice.

## Risks / Open Decisions

- O-003 is Taylor-accepted: eight indicators remain bounded; only six labor indicators enter the first implementation slice.
- O-004 is Taylor-rejected: FRED/ALFRED is not authorized for ingestion, storage, cross-checks, fallback, replay, model features, or Gate-A evidence under current terms.
- Storage technology and bulk-file-versus-API selection remain implementation choices after approval. See R-005, R-011, R-013, and R-019 through R-025.

## Conditional Data / Security Profile

- Data classification defaults to internal/raw until an explicit rights and publication decision allows a derived field.
- Retention/deletion, analytical/model/commercial/export, public-display/redistribution, attribution, and re-review rules are stored and evaluated as data.
- Secrets are referenced through approved runtime mechanisms only and are redacted from stored/sanitized URLs, request bodies, headers, logs, telemetry, errors, inspectable hashes, artifacts, tests, and snapshots.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): Taylor-approved first BINDING version after external-review corrections for dual replay semantics, publication identity, snapshot-wide fixture/factual separation, current-rights revocation, governed retention deletion, expanded rights, and DOL Tier-A Gate-A evidence.
- 0.1.0 (2026-08-17): Initial Phase-3 review draft. Not approved; no implementation authority.

## Amendment protocol

Record the problem, failed requirement, minimum proposed change, downstream/interface impact, migration/test impact, and Taylor decision requirement. Update version/index/changelog without rewriting history. Taylor alone may promote this contract.
