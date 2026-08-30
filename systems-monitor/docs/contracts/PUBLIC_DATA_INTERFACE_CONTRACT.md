# Public Data Interface Contract

```text
Contract: Systems Monitor Public Data Interface Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: PRODUCT_CONTRACT.md, ARCHITECTURE_CONTRACT.md, INFRASTRUCTURE_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 097AAA4FBBF16294CFA1757EF873DB02364C46C072B3DD7FF243498861EA484E
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §2–3, §11.1, §16.1, §31–32, §35.3–35.5, §37.1, §64.9, §67 Phase 1, §68–69. This BINDING contract is the current initial public payload authority. It does not authorize fixture/UI implementation until the applicable Phase-2 contracts are approved. Cadence-relative freshness and system-evaluation timing are accepted post-V4.1 Taylor requirements recorded in D-009 pending future Master consolidation; they are not attributed to existing V4.1 text.

## Purpose

Define a small, versioned, read-only public view-model so the Phase-2 UI and future Phase-3 producer share types without exposing internal analytical storage.

## Scope

- Snapshot/version/time metadata, including distinct evaluation, generation, activation, knowledge-cutoff, and source-freshness semantics.
- Typed `OBS`/`CALC`/`FCST`/`SCEN` values and provenance references.
- Top-level Systems Monitor systems, sources, events, and outlook extension points.
- Fixture/publication semantics and atomic snapshot consumption.

## Explicitly Out of Scope

- Internal database tables, normalized observation schema, forecast/model artifacts, collector inputs, administrative endpoints, complete event/forecast domain schemas, or a cloud/API protocol.
- Producing fixtures or implementing validation in Phase 1.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT PDI-001:** The interface is read-only, versioned, explicitly publishable, and independent of internal tables/provider SDKs.
- **BINDING REQUIREMENT PDI-002:** Every material value/claim declares exactly one `stateType`: `OBS`, `CALC`, `FCST`, or `SCEN`.
- **BINDING REQUIREMENT PDI-003:** `OBS`/`CALC` items cannot contain forecast/scenario semantics; `FCST`/`SCEN` cannot be represented as verified facts.
- **BINDING REQUIREMENT PDI-004:** Snapshot metadata includes schema version, contract version, snapshot ID, evaluated-at, generated-at, published/activated-at, as-of, source-snapshot reference, canonical `publicationClass`, and no redundant fixture boolean.
- **BINDING REQUIREMENT PDI-005:** `evaluatedAt` records when the system last evaluated whether relevant changes warranted publication; `generatedAt` records when that snapshot was produced; `publishedAt` records atomic activation for public readers; and `asOf` records the latest knowledge cutoff represented. None substitutes for observation/valid time or official publication time on individual source records.
- **BINDING REQUIREMENT PDI-006:** Public records reference source/provenance IDs; source metadata is deduplicated and includes enough identity/methodology/freshness/public-rights context for public inspection.
- **BINDING REQUIREMENT PDI-007:** Uncertainty is typed (interval, level, model skill, evidence, coverage, regime/scenario dimensions); a generic confidence percentage is not the default.
- **BINDING REQUIREMENT PDI-008:** `publicationClass` is the sole stored/public discriminant with at least `fixture` and `factual` values. Phase-2 fixtures set `publicationClass: fixture` and are visibly non-factual; factual production snapshots set `publicationClass: factual`. A UI may derive an `isFixture`-style boolean locally but must not persist or publish it as independent state.
- **BINDING REQUIREMENT PDI-009:** A `publicationClass: factual` snapshot cannot contain fixture claims and must pass publication-rights/schema validation. Validation rejects missing, unknown, contradictory, or mixed publication-class semantics.
- **BINDING REQUIREMENT PDI-010:** Breaking changes require a new schema major version and contract review; additive optional fields require compatibility tests.
- **BINDING REQUIREMENT PDI-011:** Consumers load the current manifest/pointer, then one immutable valid snapshot; they do not assemble mixed versions.
- **BINDING REQUIREMENT PDI-012:** Unknown additive fields are ignored safely; unknown schema major versions produce an explicit incompatible-data state.
- **BINDING REQUIREMENT PDI-013:** Source metadata distinguishes observation/valid time, official source publication time, retrieval time, freshness-evaluation time, and next expected official release when known.
- **BINDING REQUIREMENT PDI-014:** Freshness is evaluated relative to the source's official cadence and expected release. A monthly or quarterly source is not stale merely because the system heartbeat ran later; it becomes stale or delayed only under explicit source-aware rules such as a missed expected release, failed retrieval, or overdue evaluation.

## Initial top-level shape

Illustrative schema-level example; values are not facts:

```json
{
  "schemaVersion": "1.0.0",
  "contractVersion": "1.0.0",
  "snapshot": {
    "id": "fixture_phase2_001",
    "evaluatedAt": "2026-08-17T00:00:00Z",
    "generatedAt": "2026-08-17T00:00:00Z",
    "publishedAt": "2026-08-17T00:00:00Z",
    "asOf": "2026-08-17T00:00:00Z",
    "sourceSnapshotId": "fixture_sources_001",
    "publicationClass": "fixture"
  },
  "systems": [],
  "sources": {},
  "events": [],
  "outlook": {
    "horizons": [],
    "forecasts": []
  },
  "extensions": {}
}
```

### Common typed item

Required core:

```text
id
stateType: OBS | CALC | FCST | SCEN
label
value/displayValue (one or both under later schema rules)
unit if quantitative
validTime or forecast validity window
sourceRefs[]
provenanceRefs[]
publicationClass inherited from the snapshot; items cannot override it
```

Conditional semantics:

- `OBS`: published/observation time, retrieval time, revision status.
- `CALC`: calculation ID/version, input references, deterministic method reference.
- `FCST`: forecast ID, target/horizon/as-of, model/source snapshot references, interval and typed evidence/skill dimensions.
- `SCEN`: scenario ID, explicit assumptions/conditions, horizon, conditional output range.

### System/navigation node

```text
id
slug
label
rank / priorRank when meaningful
rankState / nearTie / nearCutoff when meaningful
stateSummaryRefs[]
childRefs[] (up to ten default children; View All may use an extension/paged collection)
availableViews[]
```

### Source reference

```text
sourceId
provider
dataset
authorityTier
methodologyUrl
observation/valid time and official source publication time when relevant
retrievedAt and freshnessEvaluatedAt when relevant
nextExpectedReleaseAt when known
cadence-relative freshness state and reason
publicDisplayAllowed / attributionRequired publication result
```

### Events and outlook extensibility

- `events[]` may initially remain empty but reserves stable IDs, evidence state, valid/knowledge time, affected-node references, and provenance.
- `outlook` reserves dynamic horizons and forecast references; its detailed contract may expand only through compatible fields or a schema revision.
- `extensions` keys must be namespaced and may not override core semantics.

## Interfaces / Dependencies

- Product Contract owns view/state meaning.
- Architecture prevents internal storage leakage.
- Infrastructure owns immutable publication/current-manifest mechanics.
- Security Ingestion owns publishability, rights, escaping, and injection controls.
- Repository/UI consumers own safe query state, rendering, and degraded UI.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** JSON files, an equivalent JSON API, or generated modules may transport the same versioned schema.
- **IMPLEMENTATION CHOICE:** Numeric `value` plus localized `displayValue` rules may be finalized in the Phase-2/3 contracts.
- **IMPLEMENTATION CHOICE:** Collections may later be split into immutable chunks referenced by a manifest if snapshot consistency is preserved.

## Prohibited Behavior

- Frontend dependence on internal table/column names; untyped claims; raw restricted data; secrets; administrative controls; executable markup; exact values invented from ranges; fixture-to-fact promotion; a second independently stored fixture flag; mixing snapshot versions.

## Failure / Degraded States

- Schema incompatibility, invalid signature/hash where used, missing snapshot, rights failure, or invalid record prevents activation and presents explicit unavailable/incompatible data.
- The last valid snapshot remains current when a new candidate fails.

## Acceptance Criteria

1. A future Phase-2 fixture can represent all three views and all four state types without internal-table assumptions.
2. JSON Schema or equivalent runtime validation can enforce required metadata, state discrimination, the canonical `publicationClass` enum and fixture/factual rules, and version compatibility without a second stored fixture boolean.
3. A future real producer can replace the fixture producer without changing UI domain types wholesale.
4. Public payload cannot carry secrets/restricted raw data or be partially activated.
5. Generic uncalibrated confidence fields are absent from the core shape.
6. Tests can distinguish source observation/publication freshness, system evaluation, snapshot generation, snapshot activation, and knowledge cutoff without marking a source stale solely because its official cadence is monthly or quarterly.

## Risks / Open Decisions

- Exact JSON Schema, numeric formatting, chunking, integrity verification, and detailed chart-series types are Phase-2/3 work. See R-004, R-005, R-007.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): First BINDING version approved by Taylor after Phase-1 external review, with `publicationClass` as the sole fixture/factual discriminant.
- 0.1.2 (2026-08-17): Made `publicationClass` the sole persisted fixture/factual discriminant and removed the redundant `isFixture` field. Remains DRAFT pending final validation and promotion.
- 0.1.1 (2026-08-17): Added post-V4.1 D-009 evaluation/generation/publication/source-cadence freshness semantics. Remains DRAFT.
- 0.1.0 (2026-08-17): Initial Foundation boundary draft. Not approved.
