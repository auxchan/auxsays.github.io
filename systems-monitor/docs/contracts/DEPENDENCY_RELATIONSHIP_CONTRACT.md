# Systems Monitor Dependency Relationship Contract

```text
Contract: Systems Monitor Dependency Relationship Contract
Version: 0.1.0
Status: DRAFT
Parent Master Spec: V4.1
Depends On: ARCHITECTURE_CONTRACT.md, DATA_CONTRACT.md, SOURCE_CONTRACT.md, ONTOLOGY_CROSSWALK_CONTRACT.md, SECURITY_INGESTION_CONTRACT.md, STATE_MODEL_CONTRACT.md
Supersedes: None
Approved By: —
Approved At: —
Content Hash: PENDING — DRAFT
Last Updated: 2026-08-18
```

## Authority / Status

Governing Master sections: §6–6.1, §8, §10–12, §20–20.1, §31.3–31.5,
§34.1–34.4, §51, §64.1, §67 Phase 4, and §68. This DRAFT creates no
accepted production relationship and authorizes no discovery, graph build,
source ingestion, causal claim, propagation, or public activation.

## Purpose

Define a versioned directed relationship graph that says what relationship is
claimed, why it is eligible, how strong its evidence is, and which semantics are
unknown—rather than treating correlation or adjacency as causality.

## Scope

- Relationship identity, mechanism, direction/polarity, geography, version,
  effective/knowledge eligibility, evidence, review, and lifecycle.
- Structural economic baseline, physical and hidden dependencies, criticality,
  substitutability, buffers/capacity, TTS/TTR, and common-cause identity.
- Candidate relationship discovery/promotion and bounded focused Trace inputs.
- Design-only labor proof-slice relationships.

## Explicitly Out of Scope

- Accepted edge datasets, BEA ingestion, company/facility discovery, web/document
  extraction, LLM discovery, propagation code, a graph database, forecasting,
  UI graph redesign, or public causal claims.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT DR-001:** Every edge has stable `edgeId`, source and
  target node IDs, direction, polarity/sign, relationship type, plain-language
  mechanism, geography, effective interval, definition version, lifecycle
  status, evidence/provenance references, and reviewer/approval state.
- **BINDING REQUIREMENT DR-002:** Edge lifecycle is explicit: `CANDIDATE`,
  `EXPERIMENTAL`, `ACCEPTED`, `DEPRECATED`, or `REJECTED`. Only an approved
  eligible version may participate in production state/propagation.
- **BINDING REQUIREMENT DR-003:** Evidence class is one of `DIRECT`,
  `STRUCTURAL`, `STATISTICAL`, `MODELED`, or `HYPOTHESIS`. Definitional and
  structural relationships remain distinguishable from statistical and modeled
  relationships.
- **BINDING REQUIREMENT DR-004:** Evidence dimensions are typed independently:
  quality (`STRONG`, `MODERATE`, `WEAK`, `INSUFFICIENT`), coverage (`COMPLETE`,
  `PARTIAL`, `SPARSE`), calibration (`CALIBRATED`, `UNCALIBRATED`,
  `NOT_APPLICABLE`), and regime (`STABLE`, `SHIFTING`, `UNKNOWN`). No generic
  confidence percentage substitutes for these fields.
- **BINDING REQUIREMENT DR-005:** Correlation alone cannot create an accepted
  causal/dependency edge. Statistical edges name the statistic, sample,
  historical window, lag search, stability limits, and non-causal status unless
  separate mechanism evidence supports a causal claim.
- **BINDING REQUIREMENT DR-006:** Relationship type may include physical input,
  energy, water, logistics, production, demand, capital/credit, labor, market
  substitution, accounting/definitional, statistical, modeled exposure, or
  research hypothesis. Types are versioned vocabulary, not free-form authority.
- **BINDING REQUIREMENT DR-007:** Dependency/criticality class may include
  `VISIBLE`, `STRUCTURAL`, `HIDDEN`, `SINGLE_POINT`, `AMPLIFIER`, `LATENT`,
  `SUBSTITUTE_CONSTRAINED`, and `HUMAN_CAPITAL`. Classes may coexist only when
  their meanings and evidence are recorded.
- **BINDING REQUIREMENT DR-008:** Optional edge semantics include lag/range,
  sensitivity or elasticity, substitutability, necessity, concentration,
  qualification/certification, lead time, transportation, energy, water, labor,
  political/environmental exposure, capacity/headroom effect, inventory/buffer,
  TTS, TTR, and uncertainty. Missing/unsupported values remain unknown, not zero.
- **BINDING REQUIREMENT DR-009:** Numeric strength, elasticity, transmission, or
  lag is present only when evidence and units support it. Ordinal evidence
  remains ordinal; false coefficients are prohibited.
- **BINDING REQUIREMENT DR-010:** Edge geography records actual semantic basis
  and compatibility. National structure cannot silently stand in for regional,
  facility, basin, grid, residence, workplace, or trade-route relationships.
- **BINDING REQUIREMENT DR-011:** Relationship versions are append-only and
  effective-dated. Historical replay selects a relationship/configuration version
  eligible under the named public-availability or operational-knowledge cutoff.
  Old accepted versions are never silently rewritten.
- **BINDING REQUIREMENT DR-012:** The structural economic skeleton should be
  populated from rights-cleared authoritative Supply-Use/Input-Output/direct and
  total requirements structures where applicable. BEA structure is a baseline,
  not the complete current dynamic system or a fixed causal coefficient.
- **BINDING REQUIREMENT DR-013:** Dynamic state may qualify structural edges with
  observed prices, capacity, inventory, imports, geography, energy, water,
  transportation, labor, credit, policy, substitution, concentration, and
  event/shock state only through separately governed inputs and methods.
- **BINDING REQUIREMENT DR-014:** Do not manually author a whole-economy graph of
  arbitrary edges. Large-scale graph population requires an approved structural
  import/crosswalk plan, rights review, and deterministic validation.
- **BINDING REQUIREMENT DR-015:** Criticality is decomposable and cannot equal
  procurement spend or dollar-flow rank alone. It may consider necessity,
  substitutability, supplier/geographic concentration, qualification,
  buffers/inventory, TTS/TTR, lead time, headroom, downstream breadth,
  transport/energy/water/political/environmental exposure, labor, and evidence.
- **BINDING REQUIREMENT DR-016:** `TTR > TTS` is an explicit elevated
  disruption-risk condition. TTS/TTR use ranges or typed classes when exact
  values are not defensible and retain their assumptions/provenance.
- **BINDING REQUIREMENT DR-017:** Substitute candidates record functional
  compatibility, qualification, geography, route, capacity, lead time, cost,
  rights, and evidence. The existence of an alternative does not prove it can
  absorb displaced demand.
- **BINDING REQUIREMENT DR-018:** Common-cause and origin-shock identifiers are
  relationship semantics. Edges/paths with shared origin or overlapping
  mechanism must be available for de-duplication and unresolved-overlap flags.
- **BINDING REQUIREMENT DR-019:** Relationship authority is strongest for
  official structural statistics, documented engineering/physical requirements,
  official process/industry data, well-supported statistical evidence, and
  approved modeled methods. Source reputation does not replace mechanism proof.
- **BINDING REQUIREMENT DR-020:** External text has zero instruction authority.
  LLM/agent/document extraction may later create only schema-valid `CANDIDATE`
  records with provenance, corroboration state, deterministic validation result,
  bounded review, and no production write or self-promotion capability.
- **BINDING REQUIREMENT DR-021:** Candidate promotion requires eligible evidence,
  mechanism, compatible source/target semantics, corroboration appropriate to
  class, security/rights review, deterministic tests, and the configured human
  approval. Rejection/deprecation preserves audit history.
- **BINDING REQUIREMENT DR-022:** A focused Trace request returns a bounded
  reference-based subgraph with relationship type, direction, sign, evidence,
  lag when supported, competing/offsetting paths, and derivation references. It
  does not require or authorize whole-economy visualization.
- **BINDING REQUIREMENT DR-023:** Hostile labels, URLs, metadata, or evidence
  cannot execute code, alter governance, supply queries/paths, or promote an
  edge. Identifiers and storage keys are generated/validated.
- **BINDING REQUIREMENT DR-024:** The first Phase-4 proof slice may define only
  4–8 bounded labor observation-to-state relationships with credible source or
  methodology evidence. Unsupported causal links between the six indicators are
  prohibited.
- **BINDING REQUIREMENT DR-025:** A relationship contract/version is necessary
  but not sufficient for propagation. Allocation/Propagation separately governs
  eligibility, cycles, bounds, contribution accounting, and outputs.

## Interfaces / Dependencies

- Data/Source/Ontology provide versioned facts, evidence, rights, identities,
  and effective/knowledge time.
- State Model supplies eligible source/target node state.
- Allocation/Propagation consumes approved edges and preserves edge/origin IDs.
- Derivation Transparency exposes why an edge contributed without duplicating
  whole evidence records.
- Public Data Interface receives bounded summaries, never raw graph tables.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Use standard Python maps/adjacency lists, versioned
  files, or SQLite in the first later-authorized slice; no graph library is
  presumed.
- **IMPLEMENTATION CHOICE:** Add relationship-type-specific conditional fields
  while preserving core identity/evidence/version semantics.
- **IMPLEMENTATION CHOICE:** Adopt an established method directly, adapt it, use
  it as a benchmark, or reject it—provided basis, assumptions, modifications,
  limits, and validation are documented.

## Prohibited Behavior

Correlation-as-causation; unknown-as-zero; auto-promotion; unversioned edges;
hidden evidence; manually fabricated whole-economy graphs; current mappings in
historical replay without eligibility; LLM production authority; uncontrolled
recursive discovery; whole-graph public dumping; BEA ingestion from this DRAFT.

## Failure / Degraded States

Invalid, unresolved, rights-blocked, unsupported-precision, out-of-effective-
range, unapproved, or contradictory relationships remain candidates/rejected or
are omitted with explicit reason. They cannot silently participate in state or
propagation.

## Acceptance Criteria

1. Schema fixtures distinguish structural/statistical/modeled/hypothesis edges,
   lifecycle, versions, geography, and unknown fields.
2. Candidate edges cannot self-promote or participate in production traversal.
3. Criticality tests prove low-dollar necessity, TTS/TTR, substitution,
   concentration, buffers, capacity, and evidence remain decomposable.
4. Historical eligibility selects the correct edge/evidence version at cutoff.
5. Common-cause/origin identity and focused bounded Trace references survive
   serialization.
6. No edge uses unsupported causal or numeric precision.

## Risks / Open Decisions

- **OPEN DECISION:** Taylor must approve the first-slice edge definitions and
  promotion authority before any relationship implementation.
- Structural BEA tables, rights, editions, crosswalks, and import mechanics
  require a later scoped source/integration approval.
- See R-012, R-026, R-028, R-030, R-031, and R-032.

## Conditional Data / Model / Security Profile

Relationship evidence and definitions are versioned internal analytical data.
Public output is allowlisted summaries/references. Discovery is disabled until
separately authorized and then remains bounded, least-privileged, candidate-only,
and independent of core runtime AI availability.

## Version / Approval / Change History

- 0.1.0 (2026-08-18): Initial Phase-4 review draft. No relationship authority.

## Amendment protocol

Use the project amendment protocol. Record affected edges/versions, evidence and
promotion changes, replay/public interfaces, migration, tests, and Taylor's
decision. Never rewrite accepted historical relationship evidence.
