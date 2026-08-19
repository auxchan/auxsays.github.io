# Systems Monitor State Model Contract

```text
Contract: Systems Monitor State Model Contract
Version: 0.1.0
Status: DRAFT
Parent Master Spec: V4.1
Depends On: PRODUCT_CONTRACT.md, ARCHITECTURE_CONTRACT.md, DATA_CONTRACT.md, SOURCE_CONTRACT.md, ONTOLOGY_CROSSWALK_CONTRACT.md, PUBLIC_DATA_INTERFACE_CONTRACT.md
Supersedes: None
Approved By: —
Approved At: —
Content Hash: PENDING — DRAFT
Last Updated: 2026-08-18
```

## Authority / Status

Governing Master sections: §3, §8–9, §11.1, §31.1–31.5, §32, §37.1,
§64.1, §67 Phase 4, and §68. This DRAFT is review material only. It does not
authorize State Engine implementation, a relationship dataset, a `CALC`
publication, factual activation, forecasting, or deployment. Taylor alone may
promote it.

## Purpose

Define a reproducible Current-State / Informative Engine that answers:

> What is the best rights-cleared representation of system state as of cutoff T?

It does not answer what will happen next.

## Scope

- Eligibility of `OBS` and approved deterministic `CALC` inputs at a named
  knowledge cutoff and replay mode.
- Mixed-frequency state assembly with native valid time, age, freshness,
  coverage, and evidence retained.
- Quantitative or governed ordinal state, explicit reference/baseline,
  constraints, capacity/headroom, buffers/inventory, and geography.
- Versioned state outputs, derivation references, and a public-safe current-state
  read-model boundary.
- Design of the bounded six-observation U.S. labor proof slice.

## Explicitly Out of Scope

- Forecasts, prediction intervals, scenarios, future observations, Phase-5
  models, or employment forecasts.
- Phase-4 implementation, new-source ingestion, BEA ingestion, accepted
  relationship creation, UI redesign, public activation, or deployment.
- Inventing continuous scores when evidence supports only an ordinal state.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT STM-001:** A state run declares `stateRunId`, engine
  version, configuration version, source snapshot ID, replay mode, knowledge
  cutoff, evaluation time, geography, and rights decision set.
- **BINDING REQUIREMENT STM-002:** Eligible inputs are rights-cleared `OBS` or
  previously approved deterministic `CALC` records whose required knowledge
  time is at or before the cutoff. `FCST`, `SCEN`, later revisions, future
  observations, and records with unknown eligibility cannot enter current state.
- **BINDING REQUIREMENT STM-003:** `PUBLICLY_AVAILABLE_AS_OF(T)` and
  `OPERATIONALLY_KNOWN_AS_OF(T)` remain distinct. A state result records which
  mode selected every input and never substitutes one for the other silently.
- **BINDING REQUIREMENT STM-004:** Every state record has a stable ID, node ID,
  geography identity/semantic basis, valid time or interval, knowledge cutoff,
  source snapshot, state type, value or typed state, unit when quantitative,
  and source/derivation references.
- **BINDING REQUIREMENT STM-005:** Mixed-frequency inputs retain native valid
  time, official publication time, accepted time, age, cadence-relative
  freshness, and carry-forward status. Carry-forward is not a new observation.
- **BINDING REQUIREMENT STM-006:** Every deviation, pressure, direction, or
  magnitude declares a versioned reference: previous eligible observation,
  rolling historical baseline, official benchmark, governed long-run state, or
  explicit reference period. Hidden or moving baselines are prohibited.
- **BINDING REQUIREMENT STM-007:** Quantitative output is permitted only when
  units, aggregation, geography, baseline, and method support it. Otherwise use
  a governed ordinal vocabulary such as `NORMAL`, `TIGHTENING`, `CONSTRAINED`,
  `SEVERELY_CONSTRAINED`, `EXPANDING`, `WEAKENING`, or `UNKNOWN`.
- **BINDING REQUIREMENT STM-008:** `UNKNOWN`, missing, stale, unavailable,
  rights-blocked, and not-applicable are distinct from zero, normal, or no
  effect. Missing inputs cannot be silently imputed.
- **BINDING REQUIREMENT STM-009:** Evidence uses typed dimensions rather than a
  generic percentage: evidence class (`DIRECT`, `STRUCTURAL`, `STATISTICAL`,
  `MODELED`, `HYPOTHESIS`), quality (`STRONG`, `MODERATE`, `WEAK`,
  `INSUFFICIENT`), coverage (`COMPLETE`, `PARTIAL`, `SPARSE`), calibration
  (`CALIBRATED`, `UNCALIBRATED`, `NOT_APPLICABLE`), and regime (`STABLE`,
  `SHIFTING`, `UNKNOWN`).
- **BINDING REQUIREMENT STM-010:** A state record may express direction and
  magnitude only separately from evidence quality. Weak evidence cannot be
  converted into precise magnitude by presentation or aggregation.
- **BINDING REQUIREMENT STM-011:** Constraint state, capacity, headroom,
  inventory/buffer state, age, and data coverage are optional typed fields.
  Unsupported fields remain absent/unknown, never zero-filled.
- **BINDING REQUIREMENT STM-012:** Geography records the actual semantic basis,
  including residence, workplace, facility, service territory, basin, grid,
  trade origin/destination, or other governed meaning. Incompatible geographies
  cannot be combined without an approved crosswalk.
- **BINDING REQUIREMENT STM-013:** State calculations are deterministic for a
  fixed eligible snapshot, cutoff, engine/configuration/baseline versions, and
  rights set. Repeated execution produces the same canonical logical result.
- **BINDING REQUIREMENT STM-014:** Every `CALC` state output references one
  bounded derivation record containing exact input IDs, algorithm and version,
  configuration, source snapshot, cutoff/replay mode, baseline, transformations,
  units, assumptions, evidence, and output.
- **BINDING REQUIREMENT STM-015:** A source observation retains `OBS` and must
  communicate that AUXSAYS did not calculate the source value. State
  classification derived from it is a separate `CALC` record.
- **BINDING REQUIREMENT STM-016:** State assembly preserves contradictions and
  competing pressures. It does not cherry-pick a convenient source or collapse
  conflicting evidence into one unexplained score.
- **BINDING REQUIREMENT STM-017:** A state output fails closed when required
  rights, provenance, mapping, time eligibility, baseline, configuration, or
  derivation evidence is invalid. A degraded output names the limitation.
- **BINDING REQUIREMENT STM-018:** The public-safe state read model exposes only
  allowlisted versioned summaries and references. It never serializes internal
  graph/storage tables, executable expressions, secrets, or restricted evidence.
- **BINDING REQUIREMENT STM-019:** Phase-4 state may produce current/as-of labor
  supply pressure, demand pressure, slack/tightness, hiring intensity,
  separation pressure, employment stock/change, and labor-capacity constraints
  as `CALC` only when the approved method and inputs justify them. It may not
  label them forecasts.
- **BINDING REQUIREMENT STM-020:** The first implementation slice, if later
  authorized, uses only the already approved six labor observations and a
  bounded historical/reference window. It cannot imply coverage of the whole
  U.S. economy.

## Interfaces / Dependencies

- Data supplies immutable observation/CALC versions, cutoffs, rights, and source
  snapshots.
- Source and Ontology/Crosswalk supply freshness and compatible identities.
- Dependency Relationship supplies only approved, eligible edge references.
- Allocation/Propagation may consume eligible state records but cannot rewrite
  them.
- Derivation Transparency owns inspectable `OBS`/`CALC` explanation records.
- Public Data Interface receives an allowlisted master-view-compatible read
  model, not internal state storage.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Use standard Python structures, versioned files, or
  SQLite/local storage after contract promotion and implementation authorization.
- **IMPLEMENTATION CHOICE:** Select ordinal thresholds and baseline methods per
  state family only with documented evidence, versioning, and tests.
- **IMPLEMENTATION CHOICE:** Materialize state or calculate it on bounded batch
  demand while preserving compute-once/read-many publication.

## Prohibited Behavior

Future-data leakage; hidden imputation; unknown-as-zero; unversioned baselines;
generic confidence percentages; correlation presented as causation; state
presented as forecast; source `OBS` relabeled as AUXSAYS `CALC`; raw-table public
access; unbounded computation; public activation from this DRAFT.

## Failure / Degraded States

- Missing/stale inputs produce explicit partial/sparse/unknown state with input
  age and reason, or no output when a required invariant fails.
- Rights, mapping, provenance, or cutoff failure blocks the affected output.
- A failed run cannot mutate a prior immutable result or public pointer.

## Acceptance Criteria

1. Mixed weekly/monthly inputs reconstruct state at multiple cutoffs without
   future leakage and retain per-input age/freshness.
2. Every output identifies its baseline, geography, source snapshot, cutoff,
   engine/config versions, typed evidence, and derivation reference.
3. Missing, stale, rights-blocked, incompatible, and unknown inputs fail safely.
4. Repeated fixed-input execution is logically identical.
5. `OBS` is visibly source-owned; every `CALC` is reproducible.
6. Public read-model fixtures contain no raw/internal table leakage or
   `FCST`/`SCEN` semantics.

## Risks / Open Decisions

- **OPEN DECISION:** Taylor must approve the initial labor-state vocabulary,
  reference rules, and proof-slice scope before implementation.
- Threshold calibration and historical window selection remain reviewable
  implementation design choices, not permission to fabricate precision.
- See R-022, R-027, R-028, R-031, and R-032.

## Conditional Data / Model / Security Profile

State inputs and results are immutable/versioned analytical records. External
labels/evidence are untrusted text; algorithms are allowlisted/versioned and not
supplied as arbitrary expressions. Rights are evaluated for analytical use and
public display independently.

## Version / Approval / Change History

- 0.1.0 (2026-08-18): Initial Phase-4 review draft. No implementation authority.

## Amendment protocol

Use the project amendment protocol. Record affected state families, replay and
baseline semantics, migrations, tests, public interface impact, and Taylor's
decision. Never rewrite historical state/configuration versions.
