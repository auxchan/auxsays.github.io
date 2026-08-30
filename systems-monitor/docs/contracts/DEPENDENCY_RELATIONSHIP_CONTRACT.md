# Systems Monitor Dependency Relationship Contract

```text
Contract: Systems Monitor Dependency Relationship Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: ARCHITECTURE_CONTRACT.md, DATA_CONTRACT.md, SOURCE_CONTRACT.md, ONTOLOGY_CROSSWALK_CONTRACT.md, SECURITY_INGESTION_CONTRACT.md, STATE_MODEL_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-19
Content Hash: B217E77459179454675CB1C07C60B78A07964F582B2E2642219216C0A7B90DA0
Last Updated: 2026-08-19
```

## Authority / Status

Governing Master sections: §6–6.1, §8, §10–12, §20–20.1, §31.3–31.5,
§34.1–34.4, §51, §64.1, §67 Phase 4, and §68. This BINDING contract authorizes
only the approved Phase-4A proof relationships. It creates no Phase-4B source
authorization, public graph, forecast, Gate-B closure, or deployment authority.

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
- Design-only Phase-4A labor proof relationships and the required Phase-4B
  authoritative structural proof boundary.

## Explicitly Out of Scope

- Accepted edge datasets, BEA ingestion, company/facility discovery, web/document
  extraction, LLM discovery, propagation code, a graph database, forecasting,
  UI graph redesign, or public causal claims.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT DR-001:** Every edge has stable `edgeId`, source and
  target node IDs, direction, polarity/sign, relationship type, plain-language
  mechanism, geography, effective interval, definition version, lifecycle
  status, knowledge/publication eligibility, evidence/provenance references,
  source dataset/table/matrix and classification identities when structural,
  crosswalk/version, derivation and acceptance rules, and approval state.
- **BINDING REQUIREMENT DR-002:** Edge lifecycle is explicit: `CANDIDATE` →
  `VALIDATED` → `ACCEPTED`, followed when applicable by `SUPERSEDED` or
  `INVALIDATED`. `EXPERIMENTAL` and `REJECTED` may be retained as non-production
  review dispositions. Only an eligible `ACCEPTED` version may participate in
  production current-state propagation. Candidate-only relationships cannot satisfy Gate B.
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
  total requirements structures where applicable. An original-authority BEA
  structural subset is required Phase-4B evidence before Gate B, not optional
  later expansion. BEA Real GDP/NIPA remains separate and unauthorized by this
  requirement. BEA structure is a baseline, not the complete current dynamic
  system or a fixed causal coefficient.
- **BINDING REQUIREMENT DR-013:** Dynamic state may qualify structural edges with
  observed prices, capacity, inventory, imports, geography, energy, water,
  transportation, labor, credit, policy, substitution, concentration, and
  event/shock state only through separately governed inputs and methods.
- **BINDING REQUIREMENT DR-014:** Do not manually author a whole-economy graph of
  arbitrary edges. Large-scale graph population requires an approved structural
  source/crosswalk/transformation plan, rights review, deterministic generation,
  validation, acceptance rule, and versioned writeback.
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
- **BINDING REQUIREMENT DR-021:** Governance approves structural sources,
  transformation/table semantics, classifications/crosswalks, coefficient and
  filtering rules, deterministic validation, relationship-generation rules, and
  the acceptance gate. Repository-owned deterministic code may then materialize
  `ACCEPTED` authoritative structural edges automatically when every governed
  rule passes; manual per-edge approval is not required. Ambiguous mappings,
  inferred/LLM edges, weak statistical hypotheses, and unsupported causal claims
  remain `CANDIDATE` until their applicable promotion rule succeeds. All
  promotion/writeback is deterministic, auditable, and reproducible without an
  external AI subscription.
- **BINDING REQUIREMENT DR-022:** A focused Trace request returns a bounded
  reference-based subgraph with relationship type, direction, sign, evidence,
  lag when supported, competing/offsetting paths, and derivation references. It
  does not require or authorize whole-economy visualization.
- **BINDING REQUIREMENT DR-023:** Hostile labels, URLs, metadata, or evidence
  cannot execute code, alter governance, supply queries/paths, or promote an
  edge. Identifiers and storage keys are generated/validated.
- **BINDING REQUIREMENT DR-024:** Phase 4A may define only 4–8 bounded labor
  observation-to-state relationships with credible source or methodology
  evidence. Unsupported causal links between the six indicators are prohibited.
  Phase 4A proves software mechanics only and cannot pass Gate B.
- **BINDING REQUIREMENT DR-025:** A relationship contract/version is necessary
  but not sufficient for propagation. Allocation/Propagation separately governs
  eligibility, cycles, bounds, contribution accounting, and outputs.
- **BINDING REQUIREMENT DR-026:** Phase 4B must prove one bounded real structural
  domain using an original-authority structural source, validated source/table/
  matrix and classification versions, deterministic relationship generation,
  accepted versioned edges, current observations attached to structural nodes,
  and a current employment-exposure connection. Synthetic fixtures may test
  mechanics but cannot satisfy this factual Gate-B evidence.
- **BINDING REQUIREMENT DR-027:** Every structural matrix/product declares one
  exact non-duplicative computational role before use. `DIRECT REQUIREMENTS`
  represent immediate input requirements and may become direct topology/edges
  after validation. `TOTAL REQUIREMENTS` already include indirect upstream
  requirements and must not be recursively traversed as ordinary direct edges
  when that topology also represents the indirect paths.
- **BINDING REQUIREMENT DR-028:** Supply/Use data may support structural input/
  output quantities and transformation; market-share structures may support
  governed commodity/industry distribution; total requirements may support
  benchmark, validation, decomposition, or separately defined non-recursive
  attribution. These are proposed role classes, not assumptions: authoritative
  documentation and approved transformation semantics determine the exact role.
- **BINDING REQUIREMENT DR-029:** A configuration combining recursively traversed
  direct-requirement paths with overlapping total-requirement contribution is
  rejected or reconciled under an explicit tested rule. Where mathematically
  appropriate, accumulated direct paths may be compared with the total-
  requirements benchmark; discrepancies outside tolerance fail visibly.
- **BINDING REQUIREMENT DR-030:** Before any structural source is implemented,
  intake must verify the current official source, exact dataset/table/version,
  access artifact, rights/terms fingerprint and operation permissions, schema,
  units, publication/vintage, taxonomy/classification, crosswalk, health,
  deterministic parser, security boundary, and bounded scope approval.

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
recursive discovery; whole-graph public dumping; BEA ingestion under this scope.

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
7. Deterministic structural generation can progress through VALIDATED to
   ACCEPTED without per-edge manual review only under an approved acceptance
   rule, while ambiguous/inferred candidates remain non-production.
8. Direct and total requirements have separate declared roles; double-counting
   configurations reject/reconcile and real authoritative Phase-4B evidence is
   required before Gate B.

## Risks / Open Decisions

- O-006 accepts the Phase-4A inputs and initial traversal profile only. O-005 is
  accepted/resolved for Phase-4A; a later bounded Phase-4B source/slice
  authorization is still required before structural relationship implementation.
- Structural BEA tables, rights, editions, crosswalks, and import mechanics
  require a later scoped source/integration approval.
- See R-012, R-026, R-028, R-030, R-031, and R-032.

## Conditional Data / Model / Security Profile

Relationship evidence and definitions are versioned internal analytical data.
Public output is allowlisted summaries/references. Discovery is disabled until
separately authorized and then remains bounded, least-privileged, candidate-only,
and independent of core runtime AI availability.

## Version / Approval / Change History

- 1.0.0 (2026-08-19): Taylor promoted the externally reviewed contract to
  BINDING and authorized only the Phase-4A Engine / Labor-State Proof.
- 0.1.1 (2026-08-19): External-review correction making Phase-4B authoritative
  structural proof Gate-B-required, adding deterministic rule-based structural
  promotion, and separating direct from total requirements. Remains DRAFT.
- 0.1.0 (2026-08-18): Initial Phase-4 review draft. No relationship authority.

## Amendment protocol

Use the project amendment protocol. Record affected edges/versions, evidence and
promotion changes, replay/public interfaces, migration, tests, and Taylor's
decision. Never rewrite accepted historical relationship evidence.
