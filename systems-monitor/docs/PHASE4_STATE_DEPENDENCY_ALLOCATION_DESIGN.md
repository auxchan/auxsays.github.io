# Phase 4 — State, Dependency, Allocation, and Derivation Design

```text
Document: Phase-4 State / Dependency / Allocation Design
Version: 0.1.1
Status: DRAFT — REVIEW REQUIRED
Parent Master Spec: V4.1
Branch: codex/systems-monitor-state-dependency-design
Base: Phase-3 closure commit bab19662046e70c1c1b963e40aa48bae55d233ea
Last Updated: 2026-08-19
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

Phase 4 has two implementation/evidence stages, not two new product phases:

- **Phase 4A — Engine / Labor-State Proof:** cheaply proves deterministic State,
  derivation, graph, traversal, cycle, common-cause bookkeeping, failure, and
  read-model mechanics using the six accepted Phase-3 labor observations.
- **Phase 4B — Authoritative Structural Proof:** proves one bounded real
  interconnected-economy slice from original authoritative structural data,
  accepted/versioned relationships, current observations, behavioral evidence,
  employment exposure, and reproducible CALC derivation.

Phase 4A cannot pass Gate B by itself, regardless of automated test count. Gate B
requires Phase-4B evidence and remains OPEN.

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

O-006 is Taylor-accepted only for Phase-4A: the six factual labor indicators,
maximum depth 3, and maximum eight rounds form an initial configurable/versioned
test and calibration profile. They are not permanent economic constants. O-005
remains OPEN, so no contract or implementation is authorized.

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

Phase 4B adds a governed structural path before relationship selection:

```text
original authoritative structural artifact
  -> rights/schema/table/taxonomy/crosswalk validation
  -> approved deterministic generation and acceptance rule
  -> versioned ACCEPTED structural relationships
  -> current observations/state attachment
  -> bounded propagation/allocation/derivation
```

Production behavior must be repository-owned and deterministic. ChatGPT, Codex,
Claude, Taylor, or any external AI subscription may assist development/review but
cannot be a live ingestion, validation, relationship-generation, promotion,
calculation, scheduling, health, publication, or testing dependency.

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

Lifecycle is `CANDIDATE` → `VALIDATED` → `ACCEPTED`, followed when applicable by
`SUPERSEDED` or `INVALIDATED`; `EXPERIMENTAL` and `REJECTED` remain non-production
review dispositions. Only eligible `ACCEPTED` versions traverse. Candidate-only
relationships cannot satisfy Gate B.

For authoritative deterministic structural data, governance approves the source,
table/matrix semantics, taxonomy/crosswalk, coefficient/filter/transformation
rules, validation, generation rule, and acceptance gate. Repository-owned code
may then automatically materialize `ACCEPTED` edges when every rule passes. It
must not require Taylor to approve thousands of deterministic edges manually.
Ambiguous mappings, inferred/LLM relationships, weak statistical hypotheses, and
unsupported causal candidates remain `CANDIDATE`. An LLM never self-promotes.
Manual review may resolve ambiguity, calibration, or temporary exceptions, but
it cannot become the production relationship-building or promotion process.

### 6.2 Structural economic baseline required for Gate B

Phase 4B must evaluate and implement a bounded subset from original-authority BEA
Supply, Use, Input-Output, direct-requirements, total-requirements, industry/
commodity output, and market-share products as supported by exact future source
discovery. This structural subset is required before Gate B, not optional later
expansion. BEA Real GDP/NIPA remains separate and is not implicitly authorized.
This correction grants no retrieval or ingestion permission.

Before implementation, a separate scoped source-intake decision must verify the
current official location, exact dataset/table/version and access artifact,
rights and terms fingerprint for retrieval/retention/transformation/analysis/
publication, schema/units/value semantics, publication/vintage, classification
versions, crosswalks, health, parser, security, and bounded scope. No coefficient
or table identity is guessed here.

Structural tables can establish evidence that production relationships exist;
they do not by themselves prove real-time bottleneck, criticality, direction of
a current shock, substitutability, or a calibrated transfer coefficient. Dynamic
evidence and state are separate overlays.

The intended system does not rely on humans manually authoring the whole economy.
It uses governed official structural baselines plus narrowly reviewed candidate
extensions. Automated/LLM discovery, if ever authorized, produces candidates
with evidence and can never promote or become a core runtime dependency.

### 6.3 Direct versus total requirements

Structural products are not interchangeable edges. Each matrix/table declares a
single exact computational role supported by authoritative documentation:

- **Direct requirements:** immediate input requirements; candidate topology/
  direct propagation edges after rights, taxonomy, crosswalk, and rule validation.
- **Total requirements:** already incorporate indirect upstream requirements;
  candidate benchmark, validation, decomposition, comparative attribution, or
  another approved non-recursive calculation.
- **Supply/Use:** candidate structural quantities and transformation basis.
- **Market share:** candidate commodity/industry distribution or allocation
  semantics under an approved definition.

These roles are selection criteria, not prevalidated source facts. The engine
must not recursively traverse total-requirement coefficients as direct edges
while also representing their indirect contribution through direct topology.
Overlapping direct/total configurations reject or reconcile explicitly. Where
mathematically appropriate, accumulated direct paths may be compared with a
total-requirements benchmark; discrepancies outside a declared tolerance fail
with evidence rather than passing silently.

### 6.4 Physical, hidden, and common-cause dependencies

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

O-006 accepts the Phase-4A proof profile at `maxDepth = 3` and `maxRounds = 8`,
with explicit node, path, and contribution budgets. These are initial
configurable/versioned test and calibration limits—not permanent economic
constants. They must be measurable and reproducible. Future structural settings
require evidence about termination, runtime, missed paths, false propagation,
trace complexity, cycles, and coverage; depth 3 cannot declare longer paths
economically irrelevant. No run increases limits dynamically or creates edges.

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

Schema identity is insufficient for Gate B. Phase 4B must include accepted real
structural paths sharing an origin where naive aggregation would overattribute,
and the reconciliation must change or bound the result. Synthetic cases may
supplement this proof but cannot replace it.

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

Phase-4B Gate-B evidence must demonstrate behavioral—not merely schema—effects:
an evidence-backed buffer changes transmission; an eligible bounded substitute
or evidence-backed no-substitute result changes disposition; and an accepted
relationship's supported lag changes current-state treatment. Stale/missing
capacity or buffer evidence degrades explicitly. Unknown lag is not zero.

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
- `structuralCoverageState`, covered/unsupported domains, accepted/candidate
  relationship counts, evidence mix, stale/degraded structural inputs, and
  derivation completeness.

It may not expose candidate relationships as fact, dump the internal graph,
conceal unknown/truncated/degraded state, or add forecasts/scenarios/rankings.
Exact icons, layout, interaction, and the major UI overhaul remain deferred.
It must visibly distinguish `PHASE_4A_LIMITED_ENGINE_PROOF` from bounded
`PHASE_4B_STRUCTURAL_COVERAGE`; a sparse graph cannot imply economy-wide coverage.

## 12. Phase 4A — labor engine proof (not authorized)

Phase 4A should prove the contracts on the smallest meaningful subject:
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

Phase 4A proves the machinery, not the economy. It cannot establish an
authoritative I/O backbone, real cross-industry/commodity propagation, or Gate B.

## 13. Phase 4B — bounded authoritative structural proof (not authorized)

### Proposed domain

Use a **construction-oriented structural slice** only if implementation-time
source discovery confirms it best satisfies the criteria below. This candidate
was chosen because it can connect commodity/service inputs, industry output,
current operational conditions, constraints, and employment exposure in a
bounded understandable chain; that rationale does not validate any edge.

Selection criteria are stronger than the domain label:

- original-authority BEA structural tables with clear direct versus total roles;
- manageable commodity/industry classifications and defensible crosswalks;
- current official observations that can attach to structural nodes;
- an evidence-supported employment mapping;
- at least one real lag and buffer plus substitute/no-substitute case;
- accepted structural paths suitable for common-cause reconciliation;
- graph size small enough for human audit and Windows/Linux replay.

If construction fails these criteria, the future source-discovery package must
return to Taylor with a better bounded domain rather than force unsupported data.

### Source and matrix selection

The required source family is original BEA Supply/Use and Input-Output structure,
including the exact direct-requirements, total-requirements, output, or market-
share products needed by the approved method. The future intake selects exact
tables/versions only after authoritative documentation, access, rights, schema,
units, vintage, taxonomy, crosswalk, and health validation. Real GDP/NIPA does
not substitute for structural I/O and remains unauthorized here.

The bounded implementation target is a design budget of approximately 8–20
structural nodes and 12–40 accepted direct relationships. Those are audit and
resource bounds, not invented claims about the BEA tables. Direct requirements
would normally supply topology; total requirements would normally benchmark or
validate without recursive traversal; Supply/Use and market-share products would
have only their explicitly approved non-duplicative roles.

### Current-state and employment attachment

The future slice must attach one or more rights-cleared current official
construction/output/input/capacity observations and an industry-employment
observation or mapping to exact structural nodes. Exact series and source IDs
remain TBD through authorized Source/Ontology intake. Total nonfarm payrolls may
provide broad context but cannot masquerade as construction-specific evidence.

The proof chain is:

```text
authoritative structural input/commodity
  -> accepted direct industry dependence
  -> current observed node condition
  -> evidence-backed lag/buffer/substitute/capacity treatment
  -> bounded downstream current exposure
  -> current employment exposure
  -> reproducible CALC and focused trace
```

Future jobs or output are not predicted.

### Required behavioral opportunities and evidence

- **Common cause:** accepted structural paths share an original upstream cause;
  naive aggregation overattributes and approved reconciliation changes/bounds it.
- **Buffer:** a permitted current inventory/reserve/capacity artifact changes one
  structural path; stale or missing evidence degrades.
- **Substitution:** an official/engineering/industry source proves bounded
  technical eligibility/capacity or proves no valid substitute.
- **Lag:** an official operational/publication/physical basis changes whether a
  contribution is current or delayed.
- **Capacity/saturation:** current authoritative evidence bounds response where
  applicable; otherwise it remains unknown.

Every non-BEA behavior needs an approved source, rights, exact measure/time/unit/
geography, mapping, method, evidence class, and acceptance rule. Narrative
plausibility is never evidence.

### Gate-B outputs

The slice produces retained authoritative artifacts, validated source/crosswalk/
relationship/config versions, deterministic generation and acceptance evidence,
direct/total role and double-count proof, current state/propagation/allocation/
employment-exposure CALCs, behavioral common-cause/buffer/substitution/lag
evidence, performance/cost metrics, derivation, coverage metadata, Human QA, and
Taylor review. No item is implemented by this design.

## 14. Phased source-expansion map (design only)

Every future source needs Source Contract intake, rights review, exact series/
table semantics, retained fixtures, ontology/crosswalk review, and independent
evidence. This map is prioritization, not ingestion authorization.

### Gate-B-required structural source

- A bounded original-source BEA Supply-Use/Input-Output structural subset is
  required for Phase 4B before Gate B. This requirement is not ingestion
  authorization and does not include BEA Real GDP/NIPA implicitly.

### Phase-4 later candidates after Gate-B source authorization

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

## 15. Gate-B validation design

Gate B remains OPEN. The Phase-4 Testing Contract requires contract-semantic
evidence for every item below:

1. reproducible current/as-of State Engine;
2. mixed-frequency timing/freshness;
3. no future leakage;
4. authoritative original-source structural I/O backbone;
5. validated structural source/version;
6. deterministic authoritative relationship generation;
7. accepted/versioned structural relationships;
8. direct-versus-total requirements semantics;
9. prevention of structural-matrix double counting;
10. current observations attached to structural nodes;
11. bounded deterministic propagation;
12. explicit termination/cycle behavior;
13. real evidence-backed lag behavior;
14. real evidence-backed buffer behavior;
15. real evidence-backed substitution or no-substitute behavior;
16. common-cause reconciliation with accepted real behavioral evidence;
17. capacity/saturation handling where applicable;
18. current allocation/residual accounting where applicable;
19. current employment-exposure connection;
20. complete CALC derivation;
21. accepted relationship/source/crosswalk/config versions in derivation;
22. visible OBS/CALC distinction;
23. no FCST/SCEN leakage;
24. public-safe bounded master-view read model;
25. honest incomplete/limited structural coverage state;
26. deterministic tests;
27. clean Windows/Linux reproducibility;
28. measured runtime;
29. measured memory/storage and bounded graph work;
30. $0 recurring infrastructure target unless separately approved;
31. Human QA; and
32. explicit Taylor Gate-B approval.

Phase 4A may satisfy only a subset. Gate B remains OPEN until Phase-4B original-
authority evidence and all applicable items pass. Automated evidence, an
independently readable package, Human QA, and Taylor approval are distinct;
implementation cannot self-close the gate.

## 16. Cost and dependency posture

The design preserves the $0 recurring-cost target. The first implementation
should begin with standard Python data structures, SQLite/versioned files, and
the existing repository toolchain where adequate. No graph/database/math/UI
library is selected or authorized here. A dependency can be proposed later only
after promoted requirements and measured evidence show standard tooling is
insufficient, followed by license/security/cost review.

No permanent cloud or paid infrastructure is selected.

Core state, replay, propagation, derivation, and publication cannot depend on an
LLM, paid API, or continuous external service.

## 17. Open decisions

1. **O-005 — OPEN / Taylor approval:** promote or correct the five DRAFT 0.1.1
   contracts.
2. **O-006 — ACCEPTED / RESOLVED — Taylor:** six factual labor indicators are
   approved as Phase-4A inputs; depth 3 and eight rounds are approved only as an
   initial configurable/versioned test/calibration profile. Phase 4A cannot pass
   Gate B alone.
3. **Engineering choice after authority:** select exact storage/graph structures,
   canonical serialization, indexes, and performance budgets from measured proof.
4. **Taylor approval later:** approve each source expansion and any quantitative
   calibration or iterative cycle solver.

## 18. Principal risks

- unsupported causal interpretation or candidate self-promotion;
- false numeric precision, unknown-as-zero, or relationship-score arithmetic;
- unbounded/cyclic propagation or non-convergent results presented as truth;
- common-cause double counting and net results that hide components;
- a labor-only proof being mistaken for whole-system coverage;
- missing structural coverage, direct/total double counting, source-table or
  taxonomy/crosswalk misclassification, and stale behavioral evidence;
- manual per-edge relationship building becoming a production dependency;
- substitution/capacity/lag behavior being asserted without accepted evidence;
- a sparse graph visually implying economy-wide coverage;
- opaque calculations or derivation/public views leaking secrets/candidates;
- premature graph infrastructure, dependencies, paid services, or UI overhaul.

These are recorded in `RISKS.md` and are contractual concerns, not merely coding
notes.

## 19. Version history

- 0.1.1 (2026-08-19): External-review correction splitting Phase 4 into 4A
  engine proof and Gate-B-required 4B authoritative structural proof; resolves
  O-006's initial profile, adds deterministic structural promotion, direct/total
  roles, a bounded construction-oriented selection design, behavioral evidence,
  coverage metadata, and the 32-item Gate-B standard. Remains DRAFT.
- 0.1.0 (2026-08-18): Initial Phase-4 review design.

## 20. Review exit and next authorization

This drafting task is complete when the five contracts and this design are
internally coherent with the BINDING package, indexed as DRAFT, independently
reviewable, and verified not to change the Master Spec or existing BINDING
contracts.

The next permitted action after this document is **external review and a
consolidated correction/promotion decision**. Phase-4 implementation, source
ingestion, dependency installation, public activation, major UI work, Phase 5,
push, merge, and deployment remain unauthorized.
