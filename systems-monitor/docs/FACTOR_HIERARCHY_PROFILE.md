# AUXSAYS Systems Monitor — Factor Hierarchy Profile

```text
Profile: Factor Hierarchy Profile
Version: 0.1.0
Status: DRAFT / PROPOSED FOR REVIEW / NOT BINDING
Date: 2026-08-23
Authority: Workstream-0 drafting authorization only
Implementation authority: NONE
```

## A. Purpose

Define a reviewable public information hierarchy for Systems Monitor without
turning the hierarchy into a dependency graph, inventing factors to satisfy the
10 × 10 requirement, or changing any BINDING contract. This profile proposes:

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

Employment Outcome
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

One of exactly ten semantically distinct, parent-justified components beneath
an approved Core or approved outcome branch. A Sub-A factor must be meaningful
without relying on its screen position.

### Sub-B factor

One of exactly ten coherent sibling components beneath an approved Sub-A. The
ten siblings must share one declared decomposition basis.

### Related record

Evidence, alternate series, geography, history, method, source, search result,
or supporting dataset associated with a factor but not counted as one of its
hierarchy children.

## D. Exact 10 × 10 rule

Draft decision LD-001 is resolved as a product requirement:

1. Every approved Core or approved outcome branch has exactly ten Sub-A
   hierarchy children.
2. Every approved Sub-A has exactly ten Sub-B hierarchy children.
3. “Up to ten” is not the target state.
4. Exactly ten is not permission to manufacture filler.
5. A branch is not complete until every required factor is defensibly defined,
   distinct, parent-justified, evidence-capable, cadence-aware, reference-aware,
   and versioned.
6. If only seven defensible factors exist, the taxonomy is incomplete; three
   neutral placeholders are prohibited.
7. The complete registry may contain hundreds of factors, but the UI never
   renders the theoretical whole registry as one graph.

### Identified BINDING conflict

This exact rule is not yet implementation authority. `UI_UX_CONTRACT.md`
UX-003 currently says each level shows **at most ten** defensible ranked children
and UX-006 defines View All around additional hierarchy candidates. The Public
Data Interface Contract's illustrative navigation node likewise describes
`childRefs[]` as up to ten default children.

The Master Spec §1 asks for the ten most important systems and ten most important
factors, and §2.1/§4 explicitly names ten driver systems, but the new exact-child
and related-record semantics are more restrictive than the current BINDING UI
contract. A later scoped amendment is required before implementation. This
profile records the proposal and does not amend either contract.

## E. Complete versus incomplete branch

| State | Definition | Public posture |
|---|---|---|
| `TAXONOMY_COMPLETE` | All required 10 Sub-A and 10 Sub-B-per-Sub-A concepts are approved and versioned | Eligible for complete hierarchy representation, subject to data and activation authority |
| `TAXONOMY_INCOMPLETE` | One or more required concept definitions or parent/child justifications are missing or unapproved | Must not appear complete; no filler |
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

An exact-ten parent has exactly ten hierarchy child IDs. “View All” cannot add
child 11 while retaining an exact-ten claim.

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
- Whether the whole-system spatial center is Employment Outcome, a neutral
  system hub, or a context-dependent selection. Employment is not frozen as the
  permanent center in this profile.

## H. Employment first-branch rationale

Employment is the first factual hierarchy-design branch because six
original-authority national observations already exist with provenance, rights,
revision, cadence, replay, and factual-candidate evidence. It is an outcome
branch defined by Master Spec §5, not automatic proof that it is the permanent
visual center or an additional driver Core.

The branch may contain both source-owned `OBS` factors and future AUXSAYS
`CALC` factors only when claim class remains explicit. Proximity in one
hierarchy never converts a CALC into official data.

## I. Employment exact-10 Sub-A candidate dictionary

This is a candidate dictionary, not source enablement or approval. Items 1–6
reuse existing governed observations. Items 7–9 identify plausible official BLS
series but still require registry, rights, semantics, and intake review. Item 10
is blocked on accepted Phase-4B evidence.

| # | ID / label | Definition and first-level justification | Claim eligibility | Likely authoritative source / exact known series | Unit / geography / cadence | Candidate reference family (no threshold) | Readiness / risks | Recommendation |
|---:|---|---|---|---|---|---|---|---|
| 1 | `employment:payroll-employment` / Payroll Employment | Number of employees on U.S. nonfarm establishment payrolls; direct realized-employment level | `OBS` | BLS CES `CES0000000001` (existing) | Thousands of persons; U.S.; monthly; SA | Previous eligible month for direction; same month prior year and fixed historical distribution for context | Source-backed; preliminary and benchmark revisions must remain visible | `ACCEPT_CANDIDATE` |
| 2 | `employment:unemployment` / U-3 Unemployment | Share of the civilian labor force unemployed under the official U-3 definition; core labor-slack outcome | `OBS` | BLS CPS `LNS14000000` (existing) | Percent; U.S.; monthly; SA | Previous eligible month; rolling historical distribution; no assumed “natural rate” | Source-backed; rising numeric direction is not favorable; population controls/seasonal revisions matter | `ACCEPT_CANDIDATE` |
| 3 | `employment:participation` / Labor-Force Participation | Share of the civilian noninstitutional population in the labor force; engagement/availability outcome | `OBS` | BLS CPS `LNS11300000` (existing) | Percent; U.S.; monthly; SA | Previous eligible month; same month prior year; governed fixed period with demographic context | Source-backed; higher/lower is not universally good without composition context | `ACCEPT_CANDIDATE` |
| 4 | `employment:initial-claims` / Initial Claims | New unemployment-insurance claims during the week; early entry-flow evidence of job loss | `OBS` | DOL ETA `DOL-UI-SA-INITIAL` (existing) | Claims; U.S.; weekly; SA | Previous eligible week; evidence-backed four-week average; same week prior year | Source-backed; advance/revised values and XML/PDF path health remain separate | `ACCEPT_CANDIDATE` |
| 5 | `employment:job-openings` / Job Openings | Open positions employers are actively recruiting to fill; unmet labor-demand stock | `OBS` | BLS JOLTS `JTS000000000000000JOL` (existing AUXSAYS identity) | Thousands; U.S.; monthly; SA | Previous eligible month; same month prior year; openings rate only as a distinct related series | Source-backed; level changes with economy size and revisions | `ACCEPT_CANDIDATE` |
| 6 | `employment:hires` / Hires | Additions to payroll during the month; realized hiring flow | `OBS` | BLS JOLTS `JTS000000000000000HIL` (existing AUXSAYS identity) | Thousands; U.S.; monthly; SA | Previous eligible month; same month prior year; hires rate only as a distinct related series | Source-backed; hires are gross flows, not net job growth | `ACCEPT_CANDIDATE` |
| 7 | `employment:hours-worked` / Average Weekly Hours | Average paid weekly hours for all employees in total private industry; intensive-margin labor utilization that can move before headcount | Future `OBS` candidate | BLS CES `CES0500000002`; official CES Series Report and Handbook require intake verification | Hours per week; U.S. total private; monthly; SA | Previous eligible month; same month prior year; rolling historical distribution | Exact series is official and plausible, but it is not enabled in the current source/indicator registry | `RESEARCH_REQUIRED` |
| 8 | `employment:earnings` / Average Hourly Earnings | Gross average hourly earnings of all employees in total private industry; realized nominal compensation level | Future `OBS` candidate | BLS CES `CES0500000003`; official Series Report identifies monthly SA total-private AHE | Dollars per hour; U.S. total private; monthly; SA | Month-over-month and year-over-year nominal change; real-wage interpretation requires a separately approved price input | Exact series is plausible but not enabled; composition effects mean it is not a pure wage-rate measure | `RESEARCH_REQUIRED` |
| 9 | `employment:separations` / Total Separations | Workers leaving payroll through quits, layoffs/discharges, and other separations; gross employment-exit flow | Future `OBS` candidate | BLS JOLTS `JTS00000000TSL` candidate; BLS defines total separations as quits + layoffs/discharges + other separations | Thousands; U.S. total nonfarm; monthly; SA | Previous eligible month; same month prior year; components remain related/Sub-B candidates, not interchangeable | Exact current series identity must be reconciled with AUXSAYS's longer JOLTS identifier convention and enabled through governed intake | `RESEARCH_REQUIRED` |
| 10 | `employment:industry-exposure` / Current Industry Employment Exposure | Current, not future, employment quantity exposed through accepted structural relationships and present state | Future `CALC` only | BEA direct requirements + approved Make/Market-Share handoff + BLS industry employment; initial endpoint candidate `CES4348400001` | Governed ordinal or supported employment unit; U.S./industry; mixed source cadence | Current accepted structural snapshot versus prior comparable accepted snapshot; factor-specific derivation | Blocked: live BEA credential/run, accepted relationships, common-cause/coverage proof, and Gate-B QA remain open | `RESEARCH_REQUIRED / BLOCKED` |

Official research references for candidate confirmation:

- BLS CES Handbook: `https://www.bls.gov/opub/hom/ces/home.htm`
- BLS series evidence: `https://data.bls.gov/timeseries/CES0500000002`
- BLS series evidence: `https://data.bls.gov/timeseries/CES0500000003`
- BLS JOLTS Handbook: `https://www.bls.gov/opub/hom/jlt/home.htm`
- BLS JOLTS candidate evidence: `https://data.bls.gov/timeseries/JTS00000000TSL`

No record in this table enables retrieval or makes a factual claim.

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

Factor and hierarchy changes are append-only versions. Each version records:

- identity and profile version;
- status and approval state;
- effective interval;
- system-known/accepted interval;
- parent and ordered child identities;
- definition/ontology/source/derivation references;
- supersession reason and compatibility impact.

Historical replay selects the hierarchy and mappings eligible under the named
replay mode/cutoff. A current taxonomy cannot be silently backdated.

## Q. Navigation semantics

```text
WHOLE SYSTEM
→ select Core or Outcome context
→ selected context + exactly 10 Sub-A
→ select Sub-A
→ selected Sub-A + exactly 10 Sub-B
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

## S. Proposed factor-record fields and PDI compatibility

Field names remain draft.

| Candidate field group | Compatibility assessment |
|---|---|
| `nodeId`, `label`, child references, ranking/context, available views | Existing PDI navigation-node concepts; reuse exact approved names where practical |
| claim state, value/unit, valid time, source/provenance refs | Existing PDI material-item concepts; claims remain `OBS`/`CALC`/`FCST`/`SCEN` |
| source identity, cadence, freshness, methodology, rights context | Existing PDI/source-reference and Source Contract concepts |
| `parentId`, `level`, `definition`, `trackedConcept`, `childJustification`, `ontologyRef`, profile references, taxonomy status/version | Candidate additive namespaced hierarchy extension; requires schema compatibility review |
| taxonomy completeness, current-data coverage, related-record collections | Candidate additive namespaced extension; must not override core evidence/coverage semantics |
| `effectiveTime`, `knowledgeTime` on taxonomy versions | Internal/candidate profile requirement; public exposure should use existing temporal vocabulary and avoid ambiguous duplicates |
| item-level `publicationClass` | Prohibited; snapshot owns publication class under PDI-008 |
| exact-ten enforcement and View All redefinition | BINDING UI/UX amendment candidate; do not implement under current UX-003/UX-006 wording |

No PDI body is amended. A namespaced additive extension appears technically
plausible under PDI `extensions`, but runtime schema design and compatibility
tests belong to a later authorized sprint.

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

## T. Open decisions and recommendation

### Workstream decision posture

| Decision | Draft result |
|---|---|
| LD-001 exact 10 × 10 | `RESOLVED / APPROVED AS DRAFT REQUIREMENT`; BINDING UX amendment required before implementation |
| LD-002 current nine R&D nodes as national Core | `REJECTED`; use Master-defined ten driver systems |
| LD-003 universal condition vocabulary | `NOT FROZEN`; factor/domain display mappings only |
| LD-004 per-indicator references | `APPROVED PRINCIPLE`; profiles still require review |
| LD-005 analytical `UNSTABLE` | `NOT AUTHORIZED`; draft display mapping requirements only |
| LD-006 PDI extension | Prefer compatible namespaced additive extension; review only |
| LD-007 Core headline condition | Requires complete taxonomy, sufficient eligible evidence, and factor-specific rules |
| LD-008 factual connectors | Accepted relationships plus applicable Gate-B/Human QA only |
| LD-009 first factual branch | Employment Outcome |
| LD-010 activation | Local QA → technical/external audit → Taylor Human QA → factual activation authorization → deployment authorization |

### Remaining open decisions

1. Approve or correct the Master-defined Core labels/definitions for public use.
2. Approve Employment's exact-ten candidate set or replace weak candidates.
3. Resolve the JOLTS canonical ID representation before source enablement.
4. Decide a coherent Sub-B decomposition separately for each Employment Sub-A.
5. Decide Employment's permanent spatial role only after the taxonomy is
   approved.
6. Scope the necessary UI/UX contract amendment for exact-ten/View All semantics.

### Recommendation

**APPROVE PROFILE FOR EXTERNAL REVIEW.**

External review should focus on the hierarchy/graph separation, exact-ten
contract conflict, Master-defined Core taxonomy, Employment exact-ten sibling
coherence, and whether the proposed extension boundary preserves existing PDI
authority. Do not begin Workstream 1 from this draft alone.
