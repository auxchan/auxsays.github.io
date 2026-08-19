# Phase 4 — State, Dependency, Allocation, and Derivation Design

```text
Document: Phase-4 State / Dependency / Allocation Design
Version: 0.1.0
Status: DRAFT — REVIEW REQUIRED
Parent Master Spec: V4.1
Branch: codex/systems-monitor-state-dependency-design
Base: Phase-3 closure commit bab19662046e70c1c1b963e40aa48bae55d233ea
Last Updated: 2026-08-18
Implementation Authorized: NO
Gate B: OPEN
```

## 1. Decision boundary

Phase 3 established a factual, replayable observation layer. Phase 4 is designed
to answer a different present-tense question: **given the evidence eligible at a
cutoff, what is the current/as-of state, what approved dependencies connect that
state, and how would an observed constraint be allocated or transmitted under a
bounded reproducible method?**

This design does not forecast. It creates no future employment, economic,
ranking, scenario, recommendation, or policy claim. Phase 5 remains the earliest
forecast/scenario phase. It also does not activate factual data publicly, ingest
new sources, install dependencies, select graph infrastructure, or implement the
deferred master/interconnectivity UI.

## 2. Proposed authority stack

All five Phase-4 contracts are DRAFT 0.1.0 and have no authority until Taylor
reviews and explicitly promotes them:

1. `STATE_MODEL_CONTRACT.md` — eligible evidence to current/as-of state.
2. `DEPENDENCY_RELATIONSHIP_CONTRACT.md` — typed, versioned, evidence-backed
   relationships and their lifecycle.
3. `ALLOCATION_PROPAGATION_CONTRACT.md` — finite deterministic transmission and
   current/as-of allocation consequences.
4. `DERIVATION_TRANSPARENCY_CONTRACT.md` — independently reproducible OBS/CALC
   evidence and bounded explanation.
5. `PHASE4_TESTING_CONTRACT.md` — objective Gate-B evidence.

The BINDING Master Spec and existing BINDING contracts remain superior. A DRAFT
conflict is a draft defect, not an amendment to BINDING authority.

## 3. Conceptual architecture

```text
accepted Phase-3 OBS / source snapshots
                |
                v
cutoff + replay + rights + health eligibility
                |
                v
versioned baseline/reference rules -----> current/as-of State (CALC)
                |                              |
                |                              v
                +---- approved relationship snapshot
                                               |
                                               v
bounded propagation / absorption / allocation (CALC)
                                               |
                                               v
immutable derivation graph + public-safe read model candidate
```

Each boundary consumes immutable IDs/versions and emits immutable records. The
pipeline fails or degrades visibly when knowledge, evidence, units, rights,
calibration, or bounds are insufficient.

## 4. Logical records and versioning

The design requires logical records, not a premature storage technology:

- `StateDefinition` and `StateRecord`
- `RelationshipDefinition`, `RelationshipVersion`, and `RelationshipEvidence`
- `PropagationRunProfile`, `Contribution`, and `PropagationRun`
- `AllocationResult`
- `CalculationDerivation` and `DerivationReference`

Every record has stable identity, schema version, content hash, created/accepted
time, effective and knowledge intervals where applicable, authority/status, and
immutable references. Corrections append versions. Historical replay selects
versions eligible at the cutoff instead of rewriting history.

Candidate and production authority are different dimensions. A schema-valid
candidate is not an accepted relationship, state method, propagation profile, or
public claim.

## 5. State construction

### 5.1 Evidence eligibility

A state run begins with a declared cutoff and replay mode. Eligible observations
must pass Phase-3 identity, vintage, timing, rights, validation, and source-health
rules. `as_known` excludes evidence unavailable at the cutoff;
`latest_revised` may use the latest accepted vintage while retaining its history.

The run never equates observation time, reference period, official publication,
retrieval, acceptance, and calculation time. Mixed-frequency evidence retains
its native time semantics and has an explicit age at the cutoff.

### 5.2 Reference and baseline

State is a CALC, not a relabeled OBS. A `StateDefinition` declares:

- subject/quantity, geography, unit and adjustment semantics;
- ordered state vocabulary and explicit `UNKNOWN`/degraded conditions;
- reference method, window, seasonal/vintage treatment, and configuration;
- minimum evidence/coverage and contradiction handling;
- numerical or ordinal thresholds and their calibration evidence;
- derivation and public-safe description.

Supported reference strategies may later include comparison with an official
reference, prior accepted period, trailing historical distribution, or approved
structural baseline. The first implementation must choose a small approved set.
No global “normal” is assumed, and missing/stale evidence is never treated as
neutral or zero.

### 5.3 Proposed first vocabulary

The initial review vocabulary is intentionally small:

`LOW`, `BELOW_REFERENCE`, `NEAR_REFERENCE`, `ABOVE_REFERENCE`, `HIGH`, and
`UNKNOWN`, plus quality/health/coverage fields. These labels require definition-
specific thresholds and must not imply equal intervals or confidence. Where a
simple directional classification is all evidence supports, the output remains
ordinal.

## 6. Relationship graph and governance

### 6.1 Relationship semantics

A relationship is a directed, versioned claim with source and destination
quantity/state types, mechanism, relationship class, polarity, lag, geography,
units, evidence class, quality/coverage/calibration/regime, uncertainty, limits,
effective/knowledge intervals, lifecycle, and reviewer authority.

Evidence classes are `DIRECT`, `STRUCTURAL`, `STATISTICAL`, `MODELED`, and
`HYPOTHESIS`. They describe the kind of support, not a universal confidence
number. Correlation, adjacency, semantic similarity, model score, or LLM output
cannot silently become causality or a numeric transmission weight.

Lifecycle is `CANDIDATE`, `EXPERIMENTAL`, `ACCEPTED`, `DEPRECATED`, or
`REJECTED`. Only the authority and status allowed by a later approved profile may
traverse. Candidates never self-promote.

### 6.2 Structural economic baseline

The future structural baseline should evaluate official BEA Supply-Use and
Input-Output products, their editions, definitions, geography, commodity/
industry crosswalks, imports, and rights. This is a candidate source strategy,
not permission to retrieve or ingest BEA data now.

Structural tables can establish evidence that production relationships exist;
they do not by themselves prove real-time bottleneck, criticality, direction of
a current shock, substitutability, or a calibrated transfer coefficient. Dynamic
evidence and state are separate overlays.

The intended system does not rely on humans manually authoring the whole economy.
It uses governed official structural baselines plus narrowly reviewed candidate
extensions. Automated/LLM discovery, if ever authorized, produces candidates
with evidence and can never promote or become a core runtime dependency.

### 6.3 Physical, hidden, and common-cause dependencies

Economic magnitude is not criticality. A low-dollar input can be essential if
there is no timely substitute and time-to-recover (TTR) exceeds time-to-survive
(TTS). Relationship evidence therefore keeps:

- necessity and failure mode;
- supplier/facility/geographic concentration;
- capacity/headroom, buffers, inventory and redundancy;
- substitutes, qualification and time-to-substitute;
- TTS and TTR with basis and uncertainty;
- shared facility, route, utility, region, weather, policy, or upstream origin;
- common-cause/origin identity.

Unknown values stay unknown. Focused Trace can later traverse a bounded subset
but cannot expose or recursively render the entire graph.

## 7. Bounded propagation design

### 7.1 Proposed deterministic sequence

For a fixed snapshot/configuration, a run would:

1. Validate the run profile and cutoff/replay mode.
2. Resolve immutable seed State records.
3. Select only eligible accepted relationship versions at the cutoff.
4. Validate units, geography, evidence, rights, and declared semantics.
5. Detect same-period strongly connected components.
6. Reject cycles under the proposed first-slice profile unless an approved lag
   makes period ordering acyclic.
7. Create origin/common-cause identities and initial contributions.
8. Traverse in canonical round and relationship-ID order.
9. Apply evidence-backed polarity, lag, geography, and unit transformation.
10. Apply capacity/headroom and saturation bounds.
11. Apply buffers, redundancy, substitution, and time-to-substitute.
12. Classify the outcome as blocked, absorbed, partially absorbed, delayed,
    amplified, or transmitted.
13. Keep offsets/amplifiers and positive/negative components decomposed.
14. Resolve overlapping common-cause contributions using the approved rule or
    retain an unresolved range/qualitative warning.
15. Stop branches on eligibility exhaustion, materiality, boundary, or budget.
16. Reconcile allocation/conservation where applicable.
17. Emit immutable CALC records, derivation references, health, and stop reasons.

### 7.2 Bounds and cycles

The proposed proof profile uses `maxDepth = 3` and `maxRounds = 8`, with explicit
node, path, and contribution budgets to be approved from test evidence. It never
increases limits dynamically and never allows relationships to create new
relationships.

Same-period cycles are rejected in the first slice. A later solver is possible
only under a promoted contract/profile with unit-aware epsilon, maximum
iterations, fixed update order, convergence evidence, and a deterministic
failure fallback. Returning the last iteration as truth is prohibited.

### 7.3 Materiality and arithmetic

Materiality is versioned and unit/state-family aware. A relationship score is not
a transfer coefficient. Numeric propagation requires compatible units and
calibration evidence. Otherwise the engine retains ordinal direction, range, or
`UNKNOWN`. Floors, ceilings, saturation, clipping, and supported ranges are
explicit and visible in derivation.

### 7.4 Common-cause control

Each contribution carries `originId`, optional `commonCauseId`, relationship and
path IDs. Two paths from the same upstream event are not naively added. A
versioned overlap/cap rule may be used only when approved; otherwise the output
keeps separate components and an unresolved-overlap warning. This preserves
truth better than a falsely precise net number.

## 8. Substitution, buffers, capacity, and delay

Buffers and substitutes are evidence-bearing mechanisms, not generic reduction
percentages. The record distinguishes inventory, redundant capacity, alternate
supplier/facility/route, demand flexibility, qualification constraints, capacity
headroom, depletion time, and time-to-substitute.

An attempted transmission receives one visible disposition:

- `BLOCKED` — relationship/eligibility prevents transmission;
- `ABSORBED` — supported buffers or substitutes cover it;
- `PARTIALLY_ABSORBED` — supported capacity covers part;
- `DELAYED` — evidence supports later current/as-of period transmission;
- `AMPLIFIED` — mechanism increases the supported effect;
- `TRANSMITTED` — eligible effect remains after controls.

These describe calculation mechanics, not future predictions. An unknown buffer
does not mean no buffer.

## 9. Current/as-of allocation

Phase-4 allocation is a transparent present/historical CALC that distributes an
observed constraint or capacity across a declared eligible set. Inputs may
include supply, demand, capacity, eligibility, cost, priority, geography, and
substitution, each with units and provenance.

Where conservation applies, the result reconciles input, allocated, absorbed,
unmet, and residual quantities within a versioned tolerance. Where it does not,
the calculation says why. Missing calibration produces partial or qualitative
output.

Allocation is not investment allocation, advice, autonomous optimization,
policy prescription, dispatch, or a forecast. Employment consequences are
current/as-of calculations only. Any future employment claim belongs to later
FCST/SCEN authority.

## 10. Derivation and explanation transparency

### 10.1 Observations

OBS disclosure answers: what is the number, what unit/period/geography is it for,
who published it, when, which exact series/table/cell and vintage, is it revised/
stale/degraded, can the original evidence and methodology be reached, and did
AUXSAYS calculate it? The answer to the last question is no.

### 10.2 Calculations

CALC disclosure identifies exact immutable inputs; source snapshot and cutoff;
method/algorithm/configuration versions; transformations and unit conversions;
assumptions, thresholds, intermediate contributions, limits and stop reasons;
uncertainty/evidence; result semantics; and a reproduction route.

Derivation is a bounded acyclic reference graph, not recursively duplicated
provenance. The proposed public explanation begins concise, then provides focused
details on demand. Draft defaults are depth 4 and 100 nodes, subject to later
review/testing. Natural-language explanation cannot replace structured evidence.

## 11. Master/interconnectivity read-model boundary

The deferred UI debt is real: the current screen behaves like a factor inspector
and does not yet reveal the system of systems. Phase 4 defines the read-model
boundary needed for a later approved master view without implementing that UI.

A safe master-view candidate may contain:

- concise current/as-of state summaries with claim class and health;
- bounded approved relationship summaries and visible mechanism/evidence type;
- focused origin-to-consequence paths with depth/truncation status;
- common-cause, buffer/substitute, capacity, geography, and lag indicators;
- current/as-of allocation/contribution summaries;
- a short “why” summary and a bounded deeper derivation reference.

It may not expose candidate relationships as fact, dump the internal graph,
conceal unknown/truncated/degraded state, or add forecasts/scenarios/rankings.
Exact icons, layout, interaction, and the major UI overhaul remain deferred.

## 12. Proposed first implementation slice (not authorized)

The first slice should prove the contracts on the smallest meaningful subject:
the six already accepted U.S. labor observations. These are proposed design
candidates only; no relationship is accepted by this document.

| Candidate | Exact Phase-3 observation | Proposed current/as-of state | Evidence posture | Status |
|---|---|---|---|---|
| P4-LAB-01 | Payrolls `CES0000000001` | employment level/change relative to approved reference | DIRECT/definitional; thresholds require review | CANDIDATE — DESIGN ONLY |
| P4-LAB-02 | U-3 `LNS14000000` | unemployment/slack state | DIRECT/definitional; interpretation bounded | CANDIDATE — DESIGN ONLY |
| P4-LAB-03 | Participation `LNS11300000` | participation/labor-supply state | DIRECT/definitional | CANDIDATE — DESIGN ONLY |
| P4-LAB-04 | Initial claims | separation-pressure proxy | STATISTICAL proxy; never unemployment causality | CANDIDATE — DESIGN ONLY |
| P4-LAB-05 | Job openings `JTS000000000000000JOL` | labor-demand proxy | STATISTICAL proxy; calibration required | CANDIDATE — DESIGN ONLY |
| P4-LAB-06 | Hires `JTS000000000000000HIL` | realized hiring-flow state | DIRECT/definitional for the measured flow | CANDIDATE — DESIGN ONLY |

The proof would validate mixed frequency, age/staleness, revision replay, exact
series evidence, state derivation, relationship lifecycle, deterministic bounded
trace, and public-safe explanation. It must not invent causal edges among the six
series, calculate a composite index without approval, or generate a labor-market
forecast.

## 13. Phased source-expansion map (design only)

Every future source needs Source Contract intake, rights review, exact series/
table semantics, retained fixtures, ontology/crosswalk review, and independent
evidence. This map is prioritization, not ingestion authorization.

### Near-term structural candidates after first-slice approval

- BEA Supply-Use/Input-Output products for structural commodity/industry links.
- Additional official BLS labor, prices, productivity, output, capacity, and
  occupational/industry evidence where exact products support the use case.
- U.S. Census official trade, production, business, and geographic products.
- EIA official energy production, stocks, capacity, flow, and price products.

### Later physical and hidden-dependency candidates

- Official transportation/freight/port and infrastructure sources.
- NOAA/weather/climate hazard evidence and USGS water/material/geologic evidence.
- USDA agriculture/food supply evidence.
- Federal Reserve/other official credit, financial-condition, capacity,
  inventory, facility, policy, and geographic concentration evidence.

### Phase 5 and later

Forecast/scenario sources, features, model calibration, validation, uncertainty,
and backtesting require their own promoted authority. Phase 4 cannot pre-approve
them or relabel current relationship output as a forecast.

## 14. Gate-B validation design

Gate B remains OPEN. The Phase-4 Testing Contract requires contract-semantic
evidence across:

- mixed-frequency state, baseline, cutoff/vintage replay, missing/stale/rights;
- relationship identity/type/evidence/lifecycle/version and causal restraint;
- deterministic one/multi-edge propagation, bounds, cycles and termination;
- offsets, amplification, buffers, substitutes, capacity, saturation and lag;
- common-cause/double-counting controls;
- allocation conservation/residual and current/as-of boundary;
- reproducible OBS/CALC derivation and bounded public explanation;
- PDI/public allowlist, synthetic/secret/candidate leakage, security and hostile
  inputs;
- $0/offline operability, performance budgets, and Phase-3 regression.

Gate B requires automated evidence, an independently readable evidence package,
human QA, and explicit Taylor approval. Implementation cannot self-close it.

## 15. Cost and dependency posture

The design preserves the $0 recurring-cost target. The first implementation
should begin with standard Python data structures, SQLite/versioned files, and
the existing repository toolchain where adequate. No graph/database/math/UI
library is selected or authorized here. A dependency can be proposed later only
after promoted requirements and measured evidence show standard tooling is
insufficient, followed by license/security/cost review.

No permanent cloud or paid infrastructure is selected.

Core state, replay, propagation, derivation, and publication cannot depend on an
LLM, paid API, or continuous external service.

## 16. Open decisions

1. **Taylor approval:** promote or correct the five DRAFT 0.1.0 contracts.
2. **Taylor approval:** approve/correct the six-observation first slice, state
   vocabulary, reference methods, causal restraint, run bounds, cycle strategy,
   common-cause rule, and Gate-B evidence plan.
3. **Engineering choice after authority:** select exact storage/graph structures,
   canonical serialization, indexes, and performance budgets from measured proof.
4. **Taylor approval later:** approve each source expansion and any quantitative
   calibration or iterative cycle solver.

## 17. Principal risks

- unsupported causal interpretation or candidate self-promotion;
- false numeric precision, unknown-as-zero, or relationship-score arithmetic;
- unbounded/cyclic propagation or non-convergent results presented as truth;
- common-cause double counting and net results that hide components;
- a labor-only proof being mistaken for whole-system coverage;
- opaque calculations or derivation/public views leaking secrets/candidates;
- premature graph infrastructure, dependencies, paid services, or UI overhaul.

These are recorded in `RISKS.md` and are contractual concerns, not merely coding
notes.

## 18. Review exit and next authorization

This drafting task is complete when the five contracts and this design are
internally coherent with the BINDING package, indexed as DRAFT, independently
reviewable, and verified not to change the Master Spec or existing BINDING
contracts.

The next permitted action after this document is **external review and a
consolidated correction/promotion decision**. Phase-4 implementation, source
ingestion, dependency installation, public activation, major UI work, Phase 5,
push, merge, and deployment remain unauthorized.
