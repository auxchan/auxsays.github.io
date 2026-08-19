# Systems Monitor Allocation and Propagation Contract

```text
Contract: Systems Monitor Allocation and Propagation Contract
Version: 0.1.1
Status: DRAFT
Parent Master Spec: V4.1
Depends On: ARCHITECTURE_CONTRACT.md, DATA_CONTRACT.md, STATE_MODEL_CONTRACT.md, DEPENDENCY_RELATIONSHIP_CONTRACT.md, DERIVATION_TRANSPARENCY_CONTRACT.md
Supersedes: None
Approved By: —
Approved At: —
Content Hash: PENDING — DRAFT
Last Updated: 2026-08-19
```

## Authority / Status

Governing Master sections: §7–14, §20–20.1, §31.3–31.5, §34.1–34.4,
§51, §64.1, §67 Phase 4, and §68. This DRAFT authorizes no propagation,
allocation, calculated public output, forecast, scenario, or implementation.

## Purpose

Define a finite, deterministic, evidence-aware method for translating an
approved current/as-of state through approved relationships while preserving
origin, common-cause, attenuation, amplification, absorption, uncertainty, and
derivation. It prevents an attractive graph from becoming an unbounded or
falsely precise causal machine.

## Scope

- Eligibility and ordering of state, relationship, propagation, and allocation.
- Contributions, offsets, amplification, saturation, buffers, substitutes,
  capacity, geography, and lag.
- Cycle, common-cause, double-counting, materiality, and termination controls.
- Current/as-of allocation consequences and reproducible CALC records.

Out of scope: forecasting, scenarios, policy recommendations, portfolio or
financial allocation, optimization, autonomous relationship discovery, source
ingestion, public activation, and a runtime graph implementation.

## Normative Requirements

### Eligibility and determinism

- **AP-001 — Approved inputs only.** A propagation run may use only eligible
  State records and relationship versions whose status, effective interval,
  knowledge interval, rights, evidence, and geography qualify at the run cutoff.
- **AP-002 — Deterministic replay.** The same snapshot, cutoff, configuration,
  relationship versions, algorithm version, and inputs must produce byte-
  equivalent canonical results and derivation identifiers.
- **AP-003 — Explicit run profile.** Every run records algorithm/config version,
  cutoff/replay mode, seed state IDs, geography, thresholds, limits, and reason.
- **AP-004 — Current/as-of boundary.** Phase 4 describes current or historically
  replayed state and allocation consequences. It must not emit a future FCST or
  SCEN merely because a relationship has a lag.

### Bounded traversal and stopping

- **AP-005 — Finite traversal.** Traversal is iterative and bounded. The proposed
  Phase-4A proof profile declares `maxDepth = 3`, `maxRounds = 8`, and explicit
  contribution/path/node budgets. O-006 accepts these only as the initial test/
  calibration profile. They are configurable, versioned, reproducible, finite,
  and measurable—not permanent economic constants or proof that longer paths
  are immaterial. Production settings require later structural evidence.
- **AP-006 — Stop rules.** A branch stops when no eligible relationship remains,
  its materiality falls below the versioned unit-aware threshold, it reaches a
  declared boundary, or any depth/round/path/node budget is reached. The reason
  is recorded; truncation is never presented as full coverage.
- **AP-007 — Materiality.** Thresholds are versioned by quantity/state family and
  cannot compare incompatible units. Without calibrated numeric semantics the
  engine uses ordinal/qualitative transmission or `UNKNOWN`, not invented math.

### Cycles and convergence

- **AP-008 — First-slice cycle rule.** The first implementation slice must reject
  same-period strongly connected components. A cycle is eligible only after an
  approved design breaks it with an evidence-backed lag/stage or authorizes a
  separately tested solver profile.
- **AP-009 — Solver constraints.** Any later iterative solver must declare an
  epsilon, unit, maximum iterations, update order, convergence proof/test, and
  deterministic non-convergence fallback. Non-convergence returns a degraded or
  failed result; it cannot return the last value as truth.
- **AP-010 — No recursion escape.** Runtime recursion, dynamically increasing
  budgets, and edge-generated edges are prohibited.

### Contributions, common cause, and aggregation

- **AP-011 — Contribution identity.** Every contribution records origin shock or
  state ID, common-cause ID when known, relationship/path IDs, input/output
  units, sign/polarity, lag, geography, evidence class, and derivation reference.
- **AP-012 — Common-cause control.** Contributions sharing an origin/common-cause
  identity are not naively summed. The run must use a versioned approved overlap
  rule, cap, or retain an unresolved range/qualitative result with an explicit
  double-counting warning.
- **AP-013 — Aggregation contract.** Aggregation is associative/order-independent
  under the declared profile or uses a fixed canonical order. It preserves
  positive, negative, absorbed, and unresolved components rather than exposing
  only a net number.
- **AP-014 — No weight fiction.** An edge score, confidence label, or correlation
  is not automatically a multiplicative transmission weight. Numeric transfer
  requires compatible units, calibration evidence, range, and version.

### Transmission mechanics

- **AP-015 — Outcome classification.** Each attempted transmission is classified
  as `BLOCKED`, `ABSORBED`, `PARTIALLY_ABSORBED`, `DELAYED`, `AMPLIFIED`, or
  `TRANSMITTED`, with the mechanism and evidence retained.
- **AP-016 — Buffers and substitutes.** Inventory, redundancy, substitutability,
  alternate suppliers/routes, and time-to-substitute are explicit inputs with
  provenance and uncertainty. Missing buffer/substitute evidence is `UNKNOWN`.
- **AP-017 — Capacity and saturation.** Capacity/headroom, floors, ceilings, and
  saturation functions are versioned, unit-bearing, and bounded. Results beyond
  supported ranges are clipped/unknown with a visible reason, never extrapolated
  silently.
- **AP-018 — Offsets and amplifiers.** Offsetting and amplifying mechanisms remain
  separately traceable. A net effect cannot erase their individual evidence or
  uncertainty.
- **AP-019 — Geography and lag.** A contribution may cross geography or period
  only through an approved mapping/relationship. The output retains source and
  destination geography, applicable lag, and reference-period semantics.

### Allocation and employment consequences

- **AP-020 — Allocation definition.** Phase-4 allocation describes how an
  observed/current constraint or capacity is distributed across eligible
  current entities under a declared rule. It is not investment advice, portfolio
  construction, resource dispatch, or future optimization.
- **AP-021 — Allocation inputs.** Supply, demand, capacity, eligibility, cost,
  priority, geography, and unresolved quantities remain decomposable. Missing
  values produce partial/qualitative results, not zero.
- **AP-022 — Conservation and residuals.** Where quantities support conservation,
  input, allocated amount, absorbed amount, unmet amount, and residual must
  reconcile within a declared tolerance. Otherwise the method states why
  conservation is not applicable.
- **AP-023 — Employment boundary.** Employment effects in Phase 4 are current-
  state CALC consequences of approved evidence and relationships. Future jobs,
  payrolls, unemployment, or rankings are FCST/SCEN and remain prohibited.

### Derivation and publication

- **AP-024 — CALC evidence.** Every propagation/allocation result is a CALC record
  with exact inputs, relationship/config/algorithm versions, intermediate
  contributions, stop reasons, uncertainty, and derivation reference under the
  Derivation Transparency Contract.
- **AP-025 — Public boundary.** Public-safe output is a bounded allowlisted read
  model. It cannot expose internal graph dumps, secret configuration, unsupported
  causal language, or omit degraded/truncated/common-cause warnings.
- **AP-026 — Fail closed.** Invalid units, unauthorized relationships, future-
  dated knowledge, missing required evidence, unsupported precision, exceeded
  limits, cycle violations, and non-convergence fail or degrade explicitly.
- **AP-027 — Two-stage proof.** Phase 4A may prove deterministic propagation
  mechanics with the accepted six labor inputs but cannot satisfy Gate B.
  Phase 4B must run one bounded original-authority structural slice using only
  eligible `ACCEPTED` relationships and attach current/as-of observations.
- **AP-028 — Structural role safety.** Direct-requirement edges may traverse only
  under their approved structural role. Total-requirement values are non-
  recursive benchmarks/attribution inputs unless a separately approved role
  proves no overlap. A run that combines overlapping total contribution with
  recursively accumulated direct paths is rejected or explicitly reconciled.
- **AP-029 — Behavioral Gate-B evidence.** Gate B requires real accepted
  structural evidence—not schema presence alone—for at least one lag that changes
  current-state treatment, one applicable buffer that changes transmission, one
  eligible substitute or evidence-backed no-substitute result, and one common-
  cause overlap whose reconciliation changes or bounds attribution. Synthetic
  fixtures supplement but cannot be the only proof.
- **AP-030 — Structural capacity and allocation.** The Phase-4B slice records
  supported capacity/headroom/saturation and current allocation/residual behavior
  where applicable. Missing evidence stays unknown. Employment output is current
  exposure only, never future hiring or job prediction.

## Required Logical Records

- `PropagationRunProfile`: identity/version, cutoff/replay, algorithms,
  thresholds, limits, cycle strategy, aggregation rule, geography, approval.
- `Contribution`: origin/common-cause/path/relationship IDs, values or ordinal
  states, units, polarity, lag, geography, evidence, uncertainty, disposition.
- `PropagationRun`: seeds, eligible snapshot, ordered rounds, stop/truncation
  reasons, contributions, outputs, health, derivation.
- `AllocationResult`: eligible population, rule/version, capacity and demand,
  allocations, absorption/unmet/residual, uncertainty, derivation.

Exact storage and serialization remain implementation choices after approval.

## Acceptance Criteria

1. Fixed-input replay is deterministic and no run exceeds declared limits.
2. Tests cover one/multiple edges, offsets, amplifiers, buffers, substitutes,
   saturation, materiality, geography, lag, truncation, and invalid units.
3. Cycles reject or converge only under the approved deterministic profile.
4. Common-cause tests prevent naive double counting and preserve components.
5. Allocations reconcile where conservation applies and expose residuals.
6. Every output has a bounded reproducible CALC derivation.
7. Direct/total structural roles cannot double count, and Phase-4B behavioral
   evidence demonstrates lag, buffer, substitution, and common-cause handling.

## Risks / Open Decisions

- O-006 accepts depth 3/eight rounds only for the configurable Phase-4A proof
  profile. O-005 contract promotion, Phase-4B scope, transmission/materiality
  semantics, and any later cycle solver still require applicable approval.
- Quantitative calibration remains evidence-dependent; ordinal output is the
  safe default where calibration is absent.
- See R-027 through R-034.

## Conditional Data / Model / Security Profile

Propagation configurations are versioned controlled data. External text cannot
supply executable formulas. Only allowlisted algorithms/configurations may run;
public results are allowlisted and bounded. No external model or AI service is a
core runtime dependency.

## Version / Approval / Change History

- 0.1.1 (2026-08-19): External-review correction accepting only the initial
  Phase-4A bounded profile and requiring authoritative Phase-4B structural and
  behavioral Gate-B evidence, including direct/total double-count protection.
  Remains DRAFT; no runtime authority.
- 0.1.0 (2026-08-18): Initial Phase-4 review draft. No runtime authority.

## Amendment protocol

Use the project amendment protocol. Record algorithm/configuration and schema
versions, affected replay/public interfaces, migrations, validation evidence,
and Taylor's decision. Never rewrite historical run profiles or derivations.
