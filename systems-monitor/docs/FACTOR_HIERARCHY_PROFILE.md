# AUXSAYS Systems Monitor — Factor Hierarchy Profile

```text
Profile: Factor Hierarchy Profile
Version: 1.0.0
Status: APPROVED GOVERNANCE PROFILE / IMPLEMENTATION NOT AUTHORIZED
Date: 2026-08-25
Authority: Taylor-approved EMP-001, EMP-002, EMP-003, FAC-001, and UXA-001
Implementation authority: NONE
```

## A. Purpose

Record the approved public information hierarchy for Systems Monitor without
turning the hierarchy into a dependency graph, inventing factors to satisfy the
10 × 10 requirement, or implementing the BINDING UI/UX Contract. This profile
establishes:

- the national Core taxonomy already named by the Master Spec;
- exact Core → Sub-A → Sub-B cardinality and completeness rules;
- Employment as the first factual outcome branch;
- factor, source, derivation, ontology, evidence, coverage, versioning, and
  navigation requirements;
- an explicit boundary between public hierarchy, accepted structural
  relationships, active propagation, and R&D fixtures.

This profile does not implement a schema, UI, source, state, relationship,
poller, public snapshot, or factual node.

## B. Hierarchy versus structural graph invariant

The two models answer different questions.

| Model | Question | Membership means | Membership does not mean |
|---|---|---|---|
| Public information hierarchy | What information belongs underneath this subject? | Semantic organization and navigation | Causation, dependency, direction, weight, exposure, or propagation |
| Structural/dependency graph | What actually depends on what? | An evidence-governed relationship version | Parent/child taxonomy membership or display priority |

Example:

```text
INFORMATION HIERARCHY

Labor Market State
├─ Payroll Employment
├─ Unemployment
├─ Labor-Force Participation
├─ Initial Claims
├─ Job Openings
├─ Hires
└─ ...

STRUCTURAL GRAPH

Crude Supply
→ Refining
→ Petroleum Products
→ Freight
→ Current Employment Exposure
```

A hierarchy tether is not a structural edge. A structural edge does not create
a hierarchy parent. Active propagation is a run result over eligible accepted
edges, not a decorative connector. These identities, evidence classes,
provenance records, lifecycle states, and visual treatments must remain
separate.

Authority: `DEPENDENCY_RELATIONSHIP_CONTRACT.md` DR-001–DR-003, DR-021–DR-022;
`UI_UX_CONTRACT.md` UX-024–UX-027; `ALLOCATION_PROPAGATION_CONTRACT.md` AP-001,
AP-011, AP-024–AP-025.

## C. Core, Sub-A, and Sub-B definitions

### Canonical factor

One versioned economic/system concept with one canonical identity, definition,
ontology posture, claim eligibility, source/derivation eligibility, unit and
geography semantics, cadence, reference/state-profile posture, evidence
identity, effective interval, knowledge interval, and status. A canonical
factor has no mandatory permanent navigation parent.

### Hierarchy placement

One versioned navigational occurrence of a canonical factor. A placement owns
its parent placement, hierarchy level, navigation role, context-justified label
override, exact-ten order/rank, child placement references, and related-record
references. It does not own or alter analytical truth.

### Core driver system

A Master-defined top-level system that materially helps explain current U.S.
employment/unemployment conditions. The Core layer is a driver-system taxonomy,
not the current R&D renderer's node list and not the Employment outcome itself.

### Outcome branch

A separately identified result domain, initially Employment, that organizes
measurements and approved calculations describing the outcome the Core driver
systems are intended to illuminate. Outcome branches do not silently become an
eleventh Core driver.

### Sub-A factor

One of exactly ten semantically distinct, parent-justified canonical factors
referenced by Sub-A placements beneath an approved Core or outcome branch. A
factor must remain meaningful outside any one screen position.

### Sub-B factor

One of exactly ten coherent canonical factors referenced by Sub-B placements
beneath an approved Sub-A placement. The ten siblings share one declared
decomposition basis.

### Related record

Evidence, alternate series, geography, history, method, source, search result,
or supporting dataset associated with a factor but not counted as one of its
hierarchy children.

## D. Exact 10 × 10 rule

Draft decision LD-001 is resolved as a product requirement:

1. Every approved Core or approved outcome branch has exactly ten Sub-A
   hierarchy placements.
2. Every approved Sub-A placement has exactly ten Sub-B hierarchy placements.
3. “Up to ten” is not the target state.
4. Exactly ten is not permission to manufacture filler.
5. A branch is not complete until every required canonical factor and placement
   is defensibly defined, distinct, parent-justified, evidence-capable,
   cadence-aware, reference-aware, and versioned.
6. If only seven defensible factors exist, the taxonomy is incomplete; three
   neutral placeholders are prohibited.
7. The complete registry may contain hundreds of factors, but the UI never
   renders the theoretical whole registry as one graph.

### Resolved BINDING conflict

UI/UX Contract 1.0.0 said each level showed **at most ten** defensible ranked
children and UX-006 defined View All around additional hierarchy candidates.
Taylor-approved UI/UX Contract 1.0.1 now governs exact-ten placement cardinality
and related-record View All semantics. The Public Data Interface Contract's
illustrative navigation node still describes `childRefs[]` as up to ten default
children and does not itself impose taxonomy cardinality.

The Master Spec §1 asks for the ten most important systems and ten most important
factors, and §2.1/§4 explicitly names ten driver systems. UI/UX 1.0.1 is the
BINDING amendment that resolves the former conflict. This profile records the
taxonomy consequence and grants no implementation authority.

## E. Complete versus incomplete branch

| State | Definition | Public posture |
|---|---|---|
| `TAXONOMY_COMPLETE` | All required canonical concepts and exact-ten placements are approved and versioned | Eligible for complete hierarchy representation, subject to data and activation authority |
| `TAXONOMY_INCOMPLETE` | One or more required concepts, placements, or parent/child justifications are missing or unapproved | Must not appear complete; no filler |
| `DATA_COMPLETE` | Every required current claim is eligible at the snapshot cutoff | May support a complete-data statement |
| `DATA_PARTIAL` | Taxonomy is complete but one or more source/derivation records are unavailable, stale under policy, rights-blocked, or ineligible | Show exact coverage and reasons |
| `DATA_SPARSE` | Too little eligible evidence exists for a representative headline | Suppress or qualify headline state |
| `BLOCKED` | A required authority, source, mapping, relationship, or gate is unavailable | Identify the blocking prerequisite |

Taxonomy completeness and current data coverage are independent. For example,
`10/10 concepts defined; 6/10 currently eligible` is partial data coverage.
`6/10 concepts defined` is an incomplete taxonomy, even if all six have data.

Missing is not zero. Stale is not neutral. Rights-blocked is not missing.
Unavailable is not zero.

## F. Related records versus hierarchy children

An exact-ten parent placement has exactly ten hierarchy child placements. “View
All” cannot add child placement 11 while retaining an exact-ten claim.

Additional records belong to explicitly typed collections such as:

- `relatedIndicatorRefs`;
- `evidenceRefs`;
- `alternateSeriesRefs`;
- `geographyBreakdownRefs`;
- `historicalRecordRefs`;
- `sourceRefs`;
- `methodRefs`;
- search results.

These proposed names are not final schema. A later UI/UX amendment should
redefine View All as a bounded list of related/context records when the exact-ten
profile applies, or otherwise reconcile the conflict explicitly.

## G. Public Core taxonomy candidates

The current renderer concepts—Supply, Refining, Storage, Utilities, Fuel,
Distribution, Freight, Industry, and Employment—are rejected as the national
Core taxonomy. They mix an outcome, industries, commodities, capacities, and
network functions from the Phase-4B energy proof.

The Master Spec already supplies the ten top-level driver systems in §2.1 and
§4. Workstream 0 therefore proposes retaining those names and clarifying their
factor profiles rather than reverse-engineering a taxonomy from the renderer.

| Core ID | Public label | Precise tracked concept and decision value | Distinction / outcome relationship | Likely official source families | Structural overlap | Readiness |
|---|---|---|---|---|---|---|
| `core:economic-output-growth` | Output & Growth | Current scale and change in U.S. production of goods/services; helps identify expanding or contracting activity capable of supporting labor demand | Economy-wide production, not household spending or employer hiring intent | BEA NIPA/GDP, Federal Reserve industrial production/capacity, Census sector output | BEA supply-use/I-O quantities may attach, but hierarchy membership is not an edge | `PROPOSED / INCOMPLETE` |
| `core:consumer-demand` | Consumer Demand | Current household purchasing power and allocation of spending; helps identify final-demand support or weakness | Household final demand, not total output or business capital formation | BEA PCE/income, Census retail/services, Federal Reserve consumer credit | Final-demand allocation may connect through accepted structural evidence | `PROPOSED / INCOMPLETE` |
| `core:employer-labor-demand` | Employer Labor Demand | Employer demand for labor through vacancies, hiring, hours, temporary help, and diffusion | Employer pull for labor, distinct from worker availability and realized employment outcomes | BLS JOLTS/CES, potentially state/industry BLS products | May receive accepted industry/output relationships; no causation from hierarchy | `PROPOSED / PARTIALLY_SOURCE_BACKED` |
| `core:layoffs-job-destruction` | Layoffs & Job Destruction | Flows that remove jobs or workers from employment and early evidence of labor-market contraction | Employment exit/destruction pressure, distinct from low hiring | DOL UI claims, BLS JOLTS/CES/BED | Structural shocks may connect only through accepted relationships | `PROPOSED / PARTIALLY_SOURCE_BACKED` |
| `core:business-investment` | Business Investment | Current business capital formation and forward commitments affecting productive capacity | Business capital demand, not household consumption or current output | BEA fixed investment, Census orders/construction/business formation | Capital/input requirements may attach to BEA structure | `PROPOSED / INCOMPLETE` |
| `core:interest-rates-credit` | Rates & Credit | Price and availability of financing for households and firms | Financing conditions, distinct from spending/investment outcomes themselves | Federal Reserve Board, Treasury, bank lending surveys, official regulator data | Financial dependency requires separately accepted evidence | `PROPOSED / INCOMPLETE` |
| `core:labor-costs-wages` | Labor Costs & Wages | Compensation cost, earnings growth, benefits, and unit labor costs | Price of labor, distinct from labor quantity/supply | BLS CES, ECI, ECEC, productivity/unit-labor-cost programs | Can qualify employer and industry states; hierarchy is not causal | `PROPOSED / PARTIALLY_SOURCE_BACKED` |
| `core:productivity-automation` | Productivity & Automation | Output per labor input and adoption of capital/technology that changes work intensity or composition | Production efficiency/technology, not business investment amount or employment outcome | BLS productivity, BEA capital accounts, Census technology evidence where authoritative | Modeled automation effects require later evidence and governance | `PROPOSED / INCOMPLETE` |
| `core:labor-supply` | Labor Supply | Availability and engagement of people able to work, including participation, demographics, migration, and training pipeline | Worker availability, distinct from employer demand and realized unemployment | BLS CPS, Census population/migration, DHS/State where approved, education/training authorities | Human-capital relationships remain separately governed | `PROPOSED / PARTIALLY_SOURCE_BACKED` |
| `core:government-trade-supply-shocks` | Policy, Trade & External Shocks | Government, trade, physical-supply, geopolitical, weather, health, and infrastructure pressures that can disturb other systems | Exogenous/cross-system pressure family; must be decomposed carefully to avoid becoming a vague catch-all | BEA/Census/USITC, EIA, NOAA, USDA, FEMA, agencies owning specific events | High graph overlap, but every actual edge still needs relationship authority | `PROPOSED / INCOMPLETE / TAXONOMY_RISK` |

### Rejected Core alternatives

| Candidate | Reason rejected as national Core |
|---|---|
| Current nine renderer nodes | Mixed abstraction levels and energy-slice/R&D provenance |
| Employment | Master §4 treats employment/unemployment as outcomes; retain as outcome branch, not an eleventh driver Core |
| Data Sources | Implementation/evidence organization, not an economic system |
| Forecast Confidence | Presentation/model evidence, not a driver system |
| Individual industries such as Refining or Freight | Important structural nodes but lower-level domain concepts |

### Core decisions still open

- Whether any public labels should be shortened without changing Master meaning.
- How to decompose the broad tenth Core coherently into exactly ten Sub-A
  factors without producing a miscellaneous bucket.
- Whether the whole-system spatial center is Labor Market State, a neutral
  system hub, or a context-dependent selection. Employment is not frozen as the
  permanent center in this profile.

## H. EMP-001 — Labor Market State parent semantics

### Alternatives evaluated

| Option | Result | Reason |
|---|---|---|
| Employment | Rejected as too narrow | The candidate children include unemployment, participation, labor demand, turnover, utilization, and compensation—not only employment outcomes |
| Labor Market State | **Approved** | Names the broader current-state question shared by all ten approved dimensions without converting them into causal peers |
| Employment & Labor Market | Rejected | Less precise than Labor Market State and risks treating Employment as both parent and one child concept |

### Approved parent

```text
Canonical parent ID: outcome:labor-market-state
Short public label: Labor Market
Status: EMP-001 APPROVED / RESOLVED BY TAYLOR
```

Definition: the current U.S. condition of employment, unemployment/slack,
labor-force engagement, employer demand, workforce entry/exit flows, labor
utilization, and realized compensation, described through separately governed
canonical factor states.

Question answered: **What is happening across the U.S. labor market now?**

Eligible first-level concepts are stable national labor-market stock, rate,
flow, utilization, or compensation measures that materially help answer that
question. Excluded concepts include macroeconomic drivers such as GDP or credit,
individual structural dependency paths, transient exposure run results, future
forecasts/scenarios, geographies/industries that belong at a coherent Sub-B
level, and source/evidence records.

Overlap with Employer Labor Demand, Layoffs & Job Destruction, Labor Costs &
Wages, and Labor Supply is intentional but controlled: those Core branches are
primary driver contexts; Labor Market is a secondary outcome/state context.
Canonical factors are not duplicated. A placement under Labor Market does not
change their value, claim class, state, reference, or provenance.

The branch is the first factual hierarchy-design branch because six
original-authority national observations already have governed provenance,
rights, revision, cadence, replay, and candidate evidence. It is not an
eleventh driver Core and is not automatically the permanent visual center.

## I. EMP-002 — Approved Labor Market exact-10 Sub-A dictionary

This is an approved placement dictionary, not source enablement. Taylor approved
all ten canonical concepts and placements with Total Separations corrected to a
primary Labor Market placement. The branch is `TAXONOMY_COMPLETE`. Four
not-yet-enabled claims remain a separate current-data coverage gap, so present
coverage is partial.

| # | Canonical factor / definition | Primary placement | Secondary Labor Market placement | Eligibility / source posture | Readiness | Recommendation |
|---:|---|---|---|---|---|---|
| 1 | `factor:payroll-employment` — employees on U.S. nonfarm establishment payrolls; realized employment level | Labor Market State | Not secondary; this is its primary outcome placement | `OBS`; BLS CES `CES0000000001` enabled | `SOURCE_BACKED` | `APPROVED` |
| 2 | `factor:u3-unemployment` — official U-3 unemployed share of the civilian labor force; labor slack outcome | Labor Market State | Not secondary | `OBS`; BLS CPS `LNS14000000` enabled | `SOURCE_BACKED` | `APPROVED` |
| 3 | `factor:labor-force-participation` — civilian noninstitutional population share in the labor force; labor engagement | Labor Supply Core | Valid secondary placement in Labor Market State | `OBS`; BLS CPS `LNS11300000` enabled | `SOURCE_BACKED` | `APPROVED` |
| 4 | `factor:initial-ui-claims` — new unemployment-insurance claims; early job-loss entry flow | Layoffs & Job Destruction Core | Valid secondary placement in Labor Market State | `OBS`; DOL `DOL-UI-SA-INITIAL` enabled | `SOURCE_BACKED` | `APPROVED` |
| 5 | `factor:job-openings` — positions employers are actively recruiting to fill; unmet labor-demand stock | Employer Labor Demand Core | Valid secondary placement in Labor Market State | `OBS`; BLS JOLTS `JTS000000000000000JOL` enabled | `SOURCE_BACKED` | `APPROVED` |
| 6 | `factor:hires` — additions to payroll during the month; gross realized hiring flow | Employer Labor Demand Core | Valid secondary placement in Labor Market State | `OBS`; BLS JOLTS `JTS000000000000000HIL` enabled | `SOURCE_BACKED` | `APPROVED` |
| 7 | `factor:average-weekly-hours-total-private` — average paid weekly hours of all total-private employees; intensive-margin labor utilization | Employer Labor Demand Core | Valid secondary placement in Labor Market State | Future `OBS`; BLS CES `CES0500000002`, not enabled | `RESEARCH_REQUIRED` | `APPROVED FACTOR / INTAKE PENDING` |
| 8 | `factor:average-hourly-earnings-total-private` — gross average hourly earnings of total-private employees; nominal realized compensation | Labor Costs & Wages Core | Valid secondary placement in Labor Market State | Future `OBS`; BLS CES `CES0500000003`, not enabled | `RESEARCH_REQUIRED` | `APPROVED FACTOR / INTAKE PENDING` |
| 9 | `factor:total-separations-total-nonfarm` — gross employment exits comprising quits, layoffs/discharges, and other separations | Labor Market State | Valid secondary/contextual placement in Layoffs & Job Destruction; layoffs/discharges remain related/Sub-B records | Future `OBS`; official BLS JOLTS concept known, exact current machine identity unresolved | `RESEARCH_REQUIRED` | `APPROVED FACTOR / INTAKE PENDING` |
| 10 | `factor:employment-population-ratio` — employed share of the civilian noninstitutional population age 16+; broad realized employment reach | Labor Market State | Not secondary | Future `OBS`; BLS CPS `LNS12300000`, not enabled | `RESEARCH_REQUIRED` | `APPROVED FACTOR / INTAKE PENDING` |

All ten are approved canonical factor concepts rather than source records. The
first six are currently source-backed; four remain research-required. Therefore
the branch is **conceptually `TAXONOMY_COMPLETE` with partial current data
coverage**. Approval does not enable retrieval, authorize new factual claims, or
make the four unavailable claims appear populated.

### First-level sibling-coherence and related-record test

Each candidate is a direct first-level Labor Market concept because it describes
one distinct national stock, rate, flow, utilization, compensation, or realized
employment dimension. The peers are not interchangeable: each answers a
different part of the parent question without becoming a source, geography,
industry slice, or structural path result.

| Factor | Direct-child / peer rationale | Related-record alternative |
|---|---|---|
| Payroll Employment | Realized employment stock; complements rather than duplicates household rates or employer flows | Detailed industries, revisions, and alternate household employment remain related/Sub-B records |
| U-3 Unemployment | Official slack rate among labor-force participants; distinct from employment reach and participation | U-1–U-6 and demographic/geographic breakdowns remain related/Sub-B records |
| Labor-Force Participation | Labor-supply engagement rate; distinct from whether participants are employed | Age/sex/race and prime-age alternatives remain related/Sub-B records |
| Initial Claims | High-frequency entry flow into insured unemployment; distinct from monthly employment and turnover stocks | Continued claims, four-week average, state detail, and release evidence remain related records |
| Job Openings | Unfilled employer-demand stock; distinct from realized hires | Openings rate and industry detail remain related/Sub-B records |
| Hires | Gross realized employer-entry flow; distinct from net payroll change and openings | Hires rate and industry detail remain related/Sub-B records |
| Average Weekly Hours | Intensive-margin labor utilization; distinct from headcount and compensation | Production-worker hours and industry detail remain related/Sub-B candidates |
| Average Hourly Earnings | Nominal realized compensation level; distinct from labor quantity and employer-demand flows | Real-wage calculations, production-worker earnings, and industry detail remain separate related/CALC records |
| Total Separations | Gross employer-exit flow; complements gross hires without equating to layoffs alone | Quits, layoffs/discharges, other separations, rates, and industry detail remain related/Sub-B records |
| Employment-Population Ratio | Broad realized employment reach in the working-age civilian population; distinct denominator from U-3 and participation | Demographic, age-specific, and geography ratios remain related/Sub-B records |

None is better reduced to a related record at the parent level. Their narrower
variants are related/Sub-B candidates. Primary placement under another driver
Core for factors 3–9 resolves overlap without duplicating their secondary Labor
Market placement or analytical truth.

Official research references:

- BLS CES Handbook: `https://www.bls.gov/opub/hom/ces/home.htm`
- Hours evidence: `https://data.bls.gov/timeseries/CES0500000002`
- Earnings evidence: `https://data.bls.gov/timeseries/CES0500000003`
- BLS JOLTS Handbook: `https://www.bls.gov/opub/hom/jlt/home.htm`
- Employment–population ratio evidence: `https://data.bls.gov/timeseries/LNS12300000`

No record in this table enables retrieval or makes a new factual claim.

### EMP-003 — Current Industry Employment Exposure disposition

**APPROVED disposition: D — structural-exposure attachment associated with
canonical industry/employment factors, surfaced through focused Trace and
related analytical records.**

It is not one of the ten Sub-A factors. It is a current/as-of `CALC` result whose
identity depends on a structural snapshot, accepted relationships, selected
industry/path, propagation configuration, coverage, cutoff, and derivation. A
new run can create a different result identity. Treating it as a peer of nine
official measurement concepts would obscure its transient calculated nature.

The attachment may have a reusable analytical result family and link to the
canonical employment/industry factors, but it remains blocked pending the live
BEA run, accepted factual relationships, behavioral/common-cause evidence, and
Gate-B/Human QA. This sprint generates no CALC.

### Hours and earnings multi-placement test

| Factor | Canonical identity | Primary placement | Secondary placement | Placement consequence |
|---|---|---|---|---|
| Average Weekly Hours | `factor:average-weekly-hours-total-private` | Employer Labor Demand | Labor Market State | Navigation/context only; same CES OBS, state, reference profile, and provenance |
| Average Hourly Earnings | `factor:average-hourly-earnings-total-private` | Labor Costs & Wages | Labor Market State | Navigation/context only; same CES OBS, state, reference profile, and provenance |

Hours is primarily an employer utilization/demand measure. Earnings is
primarily a labor-cost/compensation measure. Both materially help summarize
labor-market state, so a secondary placement is justified. Neither creates a
second observation or context-specific analytical truth.

### JOLTS Total Separations identity reconciliation

The canonical economic concept is known:

```text
factor:total-separations-total-nonfarm
→ BLS JOLTS total nonfarm total separations, level, thousands, seasonally adjusted
→ human-readable official series evidence identity
→ exact official machine acquisition identity
→ normalized canonical source record
```

Current official source material supports the human-facing legacy identity
`JTS00000000TSL`. The repository's enabled JOLTS conventions use a longer
machine-form identity for openings and hires. This sprint does not guess the
corresponding longer Total Separations ID. Future governed intake must retrieve
current official metadata, record both representations when authoritative,
define a deterministic normalization rule, prove they represent the same
series, and retain source-native identity. Status:
`CANONICAL_CONCEPT_KNOWN / EXACT_CURRENT_MACHINE_IDENTITY_UNRESOLVED /
RESEARCH_REQUIRED`.

## J. Sub-B coherence rules

Every Sub-A ultimately requires exactly ten Sub-B children. A valid set:

1. declares one decomposition basis;
2. is mutually intelligible as sibling concepts;
3. is collectively relevant to the parent;
4. does not mix industry, geography, demographic, measure, and source merely to
   reach ten;
5. declares whether children are exhaustive, representative, ranked, or a
   governed partition;
6. records overlap and double-count rules;
7. preserves source-native and canonical identities;
8. uses compatible units/geography/time for any roll-up;
9. keeps related records outside the exact-ten child set;
10. remains incomplete when a coherent set of ten cannot be defended.

Examples of coherent decomposition families include ten approved industry
groups, ten approved demographic groups, or ten distinct flow components under
one documented partition. The following is invalid:

```text
Payroll Employment
├─ Manufacturing          (industry)
├─ California             (geography)
├─ Age 25–34              (demographic)
└─ Average Weekly Hours   (different measure)
```

Workstream 0 does not construct the 900-node Sub-B registry.

## K. Factor eligibility

A factor is eligible for candidate review only when it has:

- stable proposed ID, parent ID, level, label, and definition;
- one precise tracked concept and concept type;
- a defensible parent/child justification;
- distinction from every sibling and overlap disclosure;
- ontology/version and effective-time posture;
- source-owned OBS eligibility or approved CALC eligibility;
- unit, population/universe, geography, frequency/cadence, and valid-time
  meaning where quantitative;
- reference/direction/condition/stability/freshness profile posture;
- evidence, rights, coverage, and version status;
- no dependency/causal assertion encoded in hierarchy membership.

Convenient datasets, implementation technologies, vague buckets, duplicate
concepts, and lower-level industries masquerading as national Core systems are
ineligible.

## L. Source and derivation eligibility

### OBS-backed factor

Requires an enabled, versioned original-authority registry; exact series/table;
source-native identity; parser/schema; unit/geography/cadence/revision semantics;
rights; provenance; health; and bitemporal evidence under Data and Source
contracts.

### CALC-backed factor

Requires an approved calculation identity/version; exact eligible inputs;
reference and configuration; replay mode/cutoff; derivation; evidence/coverage;
and a meaning statement under State Model and Derivation Transparency contracts.

### Prohibited

- treating a CALC as official because it sits beside OBS;
- source enablement by inclusion in this profile;
- converting external text or an AI proposal into accepted evidence;
- using a candidate structural relationship in factual output;
- generating future employment and labeling it current exposure.

## M. Ontology requirements

Each factor concept must satisfy `ONTOLOGY_CROSSWALK_CONTRACT.md` ONT-001–ONT-014:

- namespaced stable identity and vocabulary/version;
- explicit measure, population, unit, seasonal state, frequency, geography,
  aggregation, and valid-time meaning;
- preserved source-native identity;
- versioned/effective-dated mappings and supersession;
- explicit one-to-one, one-to-many, many-to-one, or unresolved state;
- no label-only join or silent conversion;
- candidate status for ambiguous/incomplete/AI-proposed mappings;
- rights and provenance appropriate to the operation.

The exact-ten taxonomy does not weaken mapping evidence.

## N. Evidence requirements

Every public factor must be able to point to:

- exact source or calculation record;
- source authority and evidence/method class;
- methodology and human-readable original evidence when allowed;
- observation/valid time, official publication time, retrieval time, and AUXSAYS
  acceptance time when supported;
- revision/vintage and freshness;
- reference profile and calculation derivation when state/direction is shown;
- taxonomy version and parent/child justification;
- structural relationship version separately when a connector is shown.

## O. Coverage semantics

Coverage is multi-dimensional and may not be reduced to an unexplained percent:

- taxonomy completeness: concepts approved / concepts required;
- current data coverage: eligible/current claims / approved factor claims;
- source coverage: source families healthy / expected;
- structural coverage: accepted relationships/domains versus intended domain;
- derivation completeness: reproducible CALCs / displayed CALCs.

Public wording should prefer concrete counts and reasons. A restrained ring may
summarize one declared coverage dimension, but the inspector must name it.

## P. Versioning and effective-time requirements

Canonical-factor and hierarchy-placement changes are append-only but separately
versioned. Each canonical factor version records:

- identity and profile version;
- status and approval state;
- effective interval;
- system-known/accepted interval;
- definition/ontology/source/derivation references;
- supersession reason and compatibility impact.

Each placement version separately records canonical factor reference, parent
placement, level, role, context label, exact-ten order/rank, child placement
references, related-record references, effective/knowledge intervals, and
supersession. Repositioning a factor does not create or revise an observation.

Historical replay selects the hierarchy and mappings eligible under the named
replay mode/cutoff. A current taxonomy cannot be silently backdated.

## Q. Navigation semantics

```text
WHOLE SYSTEM
→ select Core or Outcome context
→ selected context placement + exactly 10 Sub-A placements
→ select Sub-A
→ selected Sub-A placement + exactly 10 Sub-B placements
→ select Sub-B
→ evidence/measurement focus
```

- Parent context remains perceptible.
- Transitions preserve spatial continuity but do not imply a relationship.
- Breadcrumbs, URL/history, Reset, keyboard, touch, and list/search equivalents
  remain available.
- Hover/focus previews but does not move the camera.
- A hierarchy tether is visually quieter and categorically distinct from an
  accepted structural connector.
- No 999-node graph is a landing or ordinary navigation state.
- Related records open outside the exact-ten child ring.
- Employment's permanent spatial-center role remains an open product decision.

These are semantic requirements only; this sprint changes no renderer.

## R. R&D fixture versus factual node rules

| Class | Allowed use | Prohibited implication |
|---|---|---|
| R&D concept | Development interaction/taxonomy exploration | Approved Core or source-backed fact |
| `TEST_FIXTURE` hierarchy node | Local QA with persistent fixture disclosure | Factual taxonomy readiness |
| Candidate factual factor | Review and validation | Public activation or accepted relationship |
| Factual OBS factor | Rights-cleared activated snapshot after authority | AUXSAYS-calculated or causal claim |
| Factual CALC factor | Approved reproducible derivation after authority | Original-source measurement |

Factual structural connectors remain prohibited until source evidence is
accepted, the relationship reaches `ACCEPTED`, applicable Gate-B evidence
exists, and Human QA passes. The current accepted factual structural
relationship count remains zero.

## S. FAC-001 canonical-factor and hierarchy-placement model

Field names remain draft.

### Layer 1 — canonical factor

Conceptually owns or references:

```text
canonicalFactorId
canonicalDefinition
ontologyIdentity/version
trackedConcept
claimEligibility
sourceEligibility
derivationEligibility
unitSemantics
geographySemantics
cadence
referenceProfileRef
factorStateProfileEligibility
evidenceIdentity
effectiveInterval
knowledge/versionInterval
status/version
```

It has no mandatory navigation `parentId`. Any canonical concept taxonomy
relationships must use separately named ontology relation types; they cannot be
overloaded as public navigation parentage.

### Layer 2 — hierarchy placement

Conceptually owns:

```text
placementId
canonicalFactorId
parentPlacementId
hierarchyLevel
navigationRole
displayLabelOverride (only when justified)
exactTenOrderOrRank
childPlacementRefs
relatedRecordRefs
effective/versionInterval
```

A placement owns parentage. Multiple placements can reference one canonical
factor. A placement may change navigation, context, a justified short label, and
related-record suggestions. It may not independently change value, claim class,
analytical state, reference calculation, source provenance, derivation truth,
rights, revision, or publication authority.

### Multi-placement deduplication invariant

```text
one canonical factor
→ one eligible canonical OBS/CALC state at a named snapshot/cutoff
→ one source/provenance or derivation truth
→ one or more navigation placements referencing that truth
```

Two placements cannot generate two economic identities or contradictory states.
One placement cannot call the same canonical state “Supportive” while another
independently calls it “Critical.” Any contextual display wording must come from
an already-governed presentation profile that is compatible with the same
canonical state and reference.

### PDI compatibility assessment

| Candidate field group | Compatibility assessment |
|---|---|
| canonical claim state, value/unit/time, source/provenance refs | Existing PDI material-item concepts; claims remain `OBS`/`CALC`/`FCST`/`SCEN` |
| navigation node ID/label, child references, rank/context, available views | Existing PDI navigation-node concepts can represent placement-like records |
| source identity, cadence, freshness, methodology, rights context | Existing PDI/source-reference concepts |
| canonical factor registry and placement registry | Candidate additive namespaced extension; no current PDI requirement forbids reference-based multi-placement |
| `parentPlacementId`, `hierarchyLevel`, navigation role, context label, factor/placement version | Candidate additive namespaced placement extension; names require later schema review |
| taxonomy completeness, current-data coverage, related-record collections | Candidate additive namespaced extension; must not override core evidence/coverage semantics |
| item-level `publicationClass` | Prohibited; snapshot owns publication class under PDI-008 |
| exact-ten enforcement and View All redefinition | Governed by BINDING UI/UX 1.0.1; no PDI amendment is identified |

No PDI body is amended. A namespaced additive extension appears technically
compatible under PDI-010 and the namespaced `extensions` boundary, provided it
does not override core claim/source/publication semantics. Runtime names,
schema, validation, and compatibility tests belong to a later authorized
sprint. **FAC-001 status: APPROVED / RESOLVED BY TAYLOR.**

### Candidate factor-state profile requirements

Every headline Sub-A/Core CALC needs its own versioned profile:

```text
factorStateProfileId
eligibleChildren
requiredChildren
minimumCoverage
referenceRules
polarityRules
materialityRules
normalizationRules
weightingOrOrdinalMethod
missingnessRule
stalenessRule
conflictRule
disagreementRule
calculationVersion
derivationRequirements
```

There is no generic `average(children)` or universal score. Unsupported weights
are prohibited. Use a factor-specific evidence-supported ordinal rule or return
`MIXED`, `PARTIAL`, `UNKNOWN`, or no headline state as permitted by authority.

## T. Approved decisions, remaining work, and recommendation

### Taylor-approved correction-round decisions

| ID / status | Recommendation and rationale | Rejected alternatives | Implementation consequence | Contract consequence |
|---|---|---|---|---|
| EMP-001 — `APPROVED / RESOLVED` | Use `outcome:labor-market-state` / “Labor Market”; it coherently covers stocks, rates, flows, utilization, and compensation | Narrow Employment; vague Employment & Labor Market | Future placements use the broader parent; no UI work now | Recorded Taylor taxonomy authority |
| EMP-002 — `APPROVED / RESOLVED` | Use the final ten canonical factors/placements; Total Separations is primary under Labor Market; six source-backed and four intake-pending | Industry Exposure as child; filler; Total Separations primarily under layoffs | Taxonomy is conceptually complete; source intake separately controls coverage | UI/UX 1.0.1 governs placement cardinality |
| EMP-003 — `APPROVED / RESOLVED` | Industry Employment Exposure is a structural-exposure attachment surfaced in Trace/related analysis | Canonical Sub-A; peer official-looking measurement | No CALC generated; future result references canonical employment/industry factors | Existing CALC/relationship/derivation contracts continue to govern |
| FAC-001 — `APPROVED / RESOLVED` | Separate one canonical factor from one-or-more hierarchy placements | Permanent parent on factor; duplicated factor per branch | Future registry/read model can deduplicate claims and evidence | Additive PDI extension remains compatible; exact schema later |
| UXA-001 — `APPROVED / PROMOTED` | BINDING UI/UX 1.0.1 establishes exact-ten placements, related-record View All, and multi-placement truth preservation | Silent reinterpretation; broad UI redesign | Implementation remains separately scoped | Current BINDING UI/UX 1.0.1 is authoritative |

### Workstream decision posture

| Decision | Draft result |
|---|---|
| LD-001 exact 10 × 10 | `RESOLVED / APPROVED`; governed by BINDING UI/UX 1.0.1; implementation requires separate authorization |
| LD-002 current nine R&D nodes as national Core | `REJECTED`; use Master-defined ten driver systems |
| LD-003 universal condition vocabulary | `NOT FROZEN`; factor/domain display mappings only |
| LD-004 per-indicator references | `APPROVED PRINCIPLE`; profiles still require review |
| LD-005 analytical `UNSTABLE` | `NOT AUTHORIZED`; draft display mapping requirements only |
| LD-006 PDI extension | Prefer compatible namespaced additive extension; review only |
| LD-007 Core headline condition | Requires complete taxonomy, sufficient eligible evidence, and factor-specific rules |
| LD-008 factual connectors | Accepted relationships plus applicable Gate-B/Human QA only |
| LD-009 first factual branch | Labor Market State outcome branch (EMP-001 approved) |
| LD-010 activation | Local QA → technical/external audit → Taylor Human QA → factual activation authorization → deployment authorization |

### Remaining open decisions

1. Exact current JOLTS Total Separations machine identity before source intake.
2. Ontology/source/reference profiles for the four research-required factors.
3. A coherent exact-ten Sub-B decomposition separately for each approved Sub-A.
4. Permanent spatial-center role remains a later design/implementation decision.
5. Later schema names and compatibility tests for factor/placement registries.
6. Explicit authorization before Workstream 1 implementation.

### Recommendation

**WORKSTREAM 0 GOVERNANCE COMPLETE — READY TO AUTHORIZE WORKSTREAM 1 LIVE
FACTUAL LABOR MARKET SHELL.**

The five decisions are approved and UI/UX 1.0.1 is BINDING. Workstream 1 still
requires a separate explicit implementation authorization; this profile does
not begin it.
