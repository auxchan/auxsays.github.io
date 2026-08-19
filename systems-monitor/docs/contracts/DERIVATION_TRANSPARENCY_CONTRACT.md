# Systems Monitor Derivation Transparency Contract

```text
Contract: Systems Monitor Derivation Transparency Contract
Version: 0.1.1
Status: DRAFT
Parent Master Spec: V4.1
Depends On: PUBLIC_DATA_INTERFACE_CONTRACT.md, DATA_CONTRACT.md, SOURCE_CONTRACT.md, ONTOLOGY_CROSSWALK_CONTRACT.md, STATE_MODEL_CONTRACT.md, DEPENDENCY_RELATIONSHIP_CONTRACT.md
Supersedes: None
Approved By: —
Approved At: —
Content Hash: PENDING — DRAFT
Last Updated: 2026-08-19
```

## Authority / Status

Governing Master sections: §3, §8, §20–20.1, §31.3–31.5, §37.1, §51,
§64.1, §67 Phase 4, and §68. This DRAFT authorizes no calculated, forecast,
scenario, Trace, or public output.

## Purpose

Make every observation and AUXSAYS calculation independently understandable,
reproducible, and attributable without turning the public interface into a wall
of technical metadata. “Why does AUXSAYS say this?” must have a bounded answer.

## Scope

- Evidence and derivation requirements for OBS and CALC.
- Reserved boundaries for future FCST and SCEN.
- Versioned reference graphs, replay, public-safe summaries, and focused Trace.

Out of scope: authoring UI layouts, explaining unsupported claims, source
ingestion, forecasting, scenarios, or Phase-4 runtime implementation.

## Normative Requirements

### Claim-class integrity

- **DT-001 — Mandatory class.** Each published claim is exactly one of `OBS`,
  `CALC`, `FCST`, or `SCEN`; class cannot be inferred from prose or display.
- **DT-002 — No class laundering.** A calculated or future claim cannot be shown
  as an observation. Combining observations through an AUXSAYS method produces
  CALC, even if every input is official.

### OBS transparency

- **DT-003 — Observation disclosure.** An OBS record identifies source authority,
  dataset/product, exact series or table/cell, value, unit/scale, adjustment,
  geography, observation/reference period, official publication/release time,
  retrieval and acceptance times, revision/vintage, source health, original
  human-readable evidence, methodology, and rights/publication class.
- **DT-004 — Publisher distinction.** OBS states that AUXSAYS did not calculate
  the value. Machine retrieval provenance and human original-evidence links are
  distinct and both retained when applicable.
- **DT-005 — Revision/replay.** OBS provenance identifies the exact accepted
  release/vintage and supports `as_known` versus `latest_revised` semantics.

### CALC transparency and reproducibility

- **DT-006 — Calculation identity.** CALC records calculation ID, schema/version,
  method/algorithm ID and version, configuration ID/version, run ID, created time,
  cutoff/replay mode, source snapshot ID, and owning contract authority.
- **DT-007 — Exact inputs.** CALC references exact input observation/state/
  relationship/contribution IDs and versions, with units, geography, periods,
  quality/health, and the input order or canonicalization rule.
- **DT-008 — Method detail.** CALC records transformations, mappings, formulas or
  algorithm name, parameters, assumptions, thresholds, intermediate values/
  contributions, unit conversions, stopping/truncation, uncertainty, validation,
  and degraded/failure warnings sufficient for independent reproduction.
- **DT-009 — Result semantics.** CALC states what the result means and does not
  mean, its unit/ordinal vocabulary, reference/cutoff times, geography, coverage,
  uncertainty/evidence class, and whether any component is unknown.
- **DT-010 — Reproducibility.** Given retained inputs and versioned method/config,
  an authorized reviewer can reproduce the canonical CALC result without an
  external AI service or undocumented manual judgment.

### Future classes remain closed

- **DT-011 — FCST reservation.** Future FCST derivations must later add forecast
  origin, horizon, target period, model/training/calibration versions, features,
  uncertainty, validation/backtest, and vintage. Phase 4 emits none.
- **DT-012 — SCEN reservation.** Future SCEN derivations must later add scenario
  identity/version, assumptions, branches, interventions, comparisons, and
  non-predictive labeling. Phase 4 emits none.

### Bounded reference graph and focused explanation

- **DT-013 — References, not duplication.** Derivation is a versioned acyclic
  reference graph. Shared evidence is referenced by stable ID rather than copied
  recursively into every record.
- **DT-014 — Bounded traversal.** Every explanation query declares focus/root,
  max depth, max nodes/edges, and pagination/truncation. Proposed review defaults
  are depth 4 and 100 nodes; any implementation value requires approval/testing.
- **DT-015 — Cycle protection.** Derivation references cannot form a cycle. A
  detected cycle or missing immutable reference fails validation.
- **DT-016 — Layered disclosure.** The public-safe summary presents claim class,
  value/meaning, period/cutoff, publisher-versus-AUXSAYS role, key inputs/method,
  uncertainty/status, and direct evidence access. Deeper technical derivation is
  available on demand through bounded references.
- **DT-017 — No narrative substitute.** Natural-language explanation may help a
  human but cannot replace structured evidence or reproduction fields. Generated
  prose is untrusted unless independently derived from allowlisted structured
  fields and clearly labeled.

### Security, rights, and immutability

- **DT-018 — Public allowlist.** Public derivation excludes secrets, local paths,
  raw protected payloads, internal stack/configuration detail, disallowed fields,
  and sources whose publication class is not public-safe.
- **DT-019 — Hostile metadata.** Source titles, labels, methodology, and notes are
  untrusted text and must be escaped/validated; they never become instructions or
  executable formulas.
- **DT-020 — Immutable history.** Published derivation snapshots and referenced
  versions are append-only. Corrections create new versions and preserve replay.
- **DT-021 — Honest absence.** Missing evidence, inputs, calibration, or retained
  artifacts is explicit. The system cannot fabricate a derivation, downgrade a
  CALC to OBS, or silently omit warnings to obtain a publishable shape.
- **DT-022 — Structural derivation.** A Phase-4 structural CALC additionally
  records every accepted relationship ID/version, original structural source and
  dataset/table/matrix/version, source classification IDs, target classification
  IDs, crosswalk/version, declared direct/total/Supply/Use/market-share
  computational role, relationship-generation and acceptance-rule versions,
  propagation profile/config, buffer/substitution/lag rules applied, common-
  cause reconciliation, and material intermediate contributions.
- **DT-023 — Proof and coverage identity.** Public/internal derivation declares
  whether it belongs to `PHASE_4A_LIMITED_ENGINE_PROOF` or
  `PHASE_4B_STRUCTURAL_PROOF`, its covered/unsupported domains, structural-input
  health, and derivation completeness. A sparse or Phase-4A graph cannot imply
  authoritative economy-wide coverage.
- **DT-024 — Automated authority trace.** When repository-owned deterministic
  rules automatically materialize an accepted authoritative structural edge,
  derivation retains the approved source/transformation/crosswalk/generation/
  validation/acceptance rule versions and run/writeback identity. Manual judgment
  is not substituted silently, and external AI is not required for reproduction.

## Required Interfaces

- `ObservationEvidenceView`: concise OBS evidence/provenance and official links.
- `CalculationDerivation`: calculation/run/method/config/snapshot identity,
  exact inputs and intermediates, output semantics, warnings and reproduction.
- `DerivationReference`: immutable typed source/target/version relation.
- `PublicDerivationSummary`: allowlisted layered disclosure plus bounded deep
  reference endpoint/fixture when authorized.

Exact file, database, and API shapes remain implementation choices after
contract approval and must conform to the BINDING Public Data Interface.

## Acceptance Criteria

1. Every fixture declares OBS/CALC/FCST/SCEN and rejects class laundering.
2. OBS evidence answers who, what series, value/unit, period, publication,
   revision/status, and original evidence without implying AUXSAYS calculation.
3. CALC fixtures reproduce from exact retained inputs and method/config versions.
4. Derivation is immutable, acyclic, bounded, rights-aware, and public-allowlisted.
5. Tests reject missing references, future knowledge, secret/path leakage,
   recursive explosion, fabricated evidence, and hidden degraded state.
6. Structural CALC fixtures expose exact relationship/source/crosswalk/config
   versions, direct/total role, behavioral adjustments, reconciliation, and
   honest Phase-4A/4B coverage.
7. Every structural CALC includes accepted relationship IDs/versions and structural-source, crosswalk, and configuration versions.

## Risks / Open Decisions

- **OPEN DECISION:** Taylor must approve the public summary/deep-detail boundary
  and first Phase-4 derivation schema before implementation.
- The deferred master-view UI must reduce cognitive load without concealing
  claim class, limitations, evidence, or calculation logic.
- See R-027, R-031, R-033, and R-034.

## Conditional Data / Model / Security Profile

Derivations are immutable analytical records. Public views are minimal
allowlists; reviewer/internal views remain authenticated where required. Any
future LLM explanation is optional, candidate-only, non-authoritative, and not a
substitute for structured reproduction.

## Version / Approval / Change History

- 0.1.1 (2026-08-19): External-review correction adding structural relationship,
  source, crosswalk, generation/acceptance, propagation, behavioral, and coverage
  derivation requirements. Remains DRAFT; no output authority.
- 0.1.0 (2026-08-18): Initial Phase-4 review draft. No output authority.

## Amendment protocol

Use the project amendment protocol. Record affected claim classes, schema and
method versions, replay/public interfaces, migrations, tests, and Taylor's
decision. Never mutate already published derivation snapshots.
