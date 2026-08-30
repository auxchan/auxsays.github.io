# AUXSAYS Systems Monitor — Live-State Presentation Profile

```text
Profile: Live-State Presentation Profile
Version: 0.1.2
Status: DRAFT / PROPOSED FOR REVIEW / NOT BINDING
Date: 2026-08-25
Authority: Workstream-0 profile drafting plus Taylor-approved FAC-001/UXA-001 references
Implementation authority: NONE
```

## 1. Purpose

Define how an already governed analytical state may become understandable
public presentation without creating a second analytical model. The profile
separates claim class, direction, condition, stability/regime, freshness,
revision, evidence, coverage, and reference. It proposes wording and interaction
rules but does not calculate, publish, activate, poll, ingest, render, or amend a
BINDING contract.

## 2. Governing principle

The analytical producer owns state. The public interface faithfully maps that
state through a versioned, deterministic, factor/domain-specific presentation
profile.

```text
eligible OBS / approved CALC
        ↓
governed analytical state + explicit reference + evidence
        ↓
versioned display mapping
        ↓
concise public wording + progressive evidence disclosure
```

Frontend code may format an approved label; it may not choose the baseline,
infer desirability, invent a threshold, average disagreement away, recalculate
freshness from page age, or turn missing evidence into neutral.

### 2.1 Canonical analytical truth versus hierarchy placement

Analytical truth belongs to the canonical material claim, source evidence,
state profile, and derivation—not to a hierarchy placement.

One canonical factor may appear in multiple justified navigation contexts. All
placements reference the same eligible `OBS`/`CALC` value and claim class at the
named snapshot/cutoff. A placement cannot independently change analytical
state, reference calculation, direction, stability, freshness, revision,
coverage evidence, provenance, rights, or derivation.

A placement may supply context, a justified short label, and related-record
suggestions. Contextual wording may vary only through an already-governed,
versioned presentation mapping compatible with the same canonical state and
reference. One placement cannot independently describe that state as
“Supportive” while another calls it “Critical.” Multiple placements create no
duplicate observation, source record, CALC, or publication authority.

Authority: `STATE_MODEL_CONTRACT.md` STM-004–STM-010, STM-013–STM-018;
`DERIVATION_TRANSPARENCY_CONTRACT.md` DT-001–DT-010, DT-013–DT-018;
`UI_UX_CONTRACT.md` UX-028–UX-032.

## 3. Independent presentation dimensions

| Dimension | Question answered | Analytical/public examples | Must not be confused with |
|---|---|---|---|
| Information class | Who produced what kind of claim? | `OBS`, `CALC`, `FCST`, `SCEN` | Freshness, desirability, or evidence quality |
| Direction | Which numeric/ordinal way did it move relative to a reference? | Rising, Falling, Flat, Mixed, Insufficient history | Good/bad, strength, or forecast |
| Condition | What is the governed current state relative to its explicit reference? | Existing factor-specific ordinal state | Direction or universal economic score |
| Stability/regime | Is the recent comparable pattern stable or shifting? | `STABLE`, `SHIFTING`, `UNKNOWN` | Source health or one surprising value |
| Freshness | Is the source/record current relative to official cadence? | Current, Delayed, Stale, Unavailable | Observation period or page-load age |
| Revision | What publication/vintage posture applies? | Advance, Preliminary, Revised, Final, Not stated | Freshness or AUXSAYS correction |
| Evidence | What method/authority supports the claim? | Direct, Structural, Statistical, Modeled, Hypothesis + quality | Generic confidence percent |
| Coverage | How much intended evidence is eligible? | Complete, Partial, Sparse, plus concrete counts | Taxonomy completeness |
| Reference | Compared with what? | Previous observation, year ago, rolling distribution, official benchmark, fixed period | A hidden moving baseline |

All applicable dimensions remain independently inspectable even when the
overview shows only one or two.

## 4. Information class

The public-facing translation may use plain words, but the governed token remains
available at the claim/series level.

| Governed class | Plain-language short form | Required meaning |
|---|---|---|
| `OBS` | Official measurement | Source-owned observed/reported value; AUXSAYS did not calculate it |
| `CALC` | AUXSAYS calculation | Deterministic documented calculation with exact inputs and derivation |
| `FCST` | Forecast | Future estimate with horizon, origin, interval/evidence, and later Phase-5 authority |
| `SCEN` | Scenario | Conditional result under named assumptions; not observed history or baseline |

Phase 5 remains locked. This profile creates no `FCST` or `SCEN` content.

## 5. Direction

Direction is a relation to one declared reference. Candidate display vocabulary:

| Display term | Required analytical condition |
|---|---|
| Rising | Positive numeric/ordinal change exceeds a versioned factor-specific materiality rule |
| Falling | Negative numeric/ordinal change exceeds that rule |
| Flat | Change remains within that rule |
| Mixed | Eligible components disagree and the factor profile has no defensible resolution |
| Insufficient history | Comparable eligible history does not meet the profile minimum |

These are display candidates, not new State Contract vocabulary. The underlying
record must retain reference identity, method/config version, period, and
direction semantics. “Rising” never means forecast to rise.

## 6. Condition and good/bad/neutral language

### No universal ladder

Workstream 0 does not establish `Supportive → Normal → Watch → Strained →
Critical` as universal analytical truth. Those words may be tested as display
language only where a factor-specific mapping makes them accurate.

Examples:

- Rising payroll employment and rising unemployment have the same numeric
  direction but normally opposite employment interpretations.
- High refinery utilization can support current production while simultaneously
  indicating limited spare capacity.
- Falling participation can reduce measured unemployment without representing
  an unambiguously improving labor market.

### Candidate display-mapping record

Names remain proposed:

```text
displayMappingId
factorStateProfileId
analyticalState
analyticalQualifier
displayLabel
plainLanguageMeaning
directionCompatibility
desirabilityInterpretation
referenceProfileRef
evidenceMinimum
coverageMinimum
effectiveTime
version
```

Requirements:

- versioned and deterministic;
- traceable to the analytical state and explicit reference;
- factor/domain appropriate;
- non-contradictory with direction, evidence, and coverage;
- capable of expressing dual implications rather than forcing one color;
- suppressed when evidence or coverage minimum is not met.

The interface may say “improving,” “concerning,” “typical range,” “mixed,” or
similar language only when such wording is approved in the factor's display
mapping. Otherwise it shows the governed state with a short neutral explanation.

## 7. Reference profile requirement

Every directional or condition claim must answer **Compared with what?**

Allowed candidate reference families:

1. previous eligible observation;
2. same period in the previous year;
3. versioned rolling historical distribution;
4. official target/benchmark;
5. authority-supported capacity/headroom threshold;
6. fixed governed historical period.

Every profile records the reference ID/version, eligible series, lookback,
seasonal/frequency/geography compatibility, preliminary/revision treatment,
materiality rule, missingness behavior, and effective interval. No frontend
moving baseline and no universal threshold across incompatible indicators are
allowed.

## 8. Candidate references for the six existing Employment observations

These are research proposals, not thresholds or implemented state rules.

| Existing observation | Defensible primary reference family | Useful secondary context | Validation still required |
|---|---|---|---|
| Payroll employment — BLS CES `CES0000000001` | Previous eligible monthly observation for change/direction | Same month prior year; fixed or rolling distribution of monthly change | Materiality, benchmark-revision treatment, population/economy-size context, whether level ever receives a condition label |
| U-3 unemployment — BLS CPS `LNS14000000` | Previous eligible monthly observation for direction | Same month prior year and a versioned historical distribution | No hidden natural-rate target; annual seasonal/population-control revisions; mapping from rate level/change to display interpretation |
| Labor-force participation — BLS CPS `LNS11300000` | Previous eligible monthly observation | Same month prior year; governed fixed historical period with demographic context | Composition/aging effects; no universal higher-is-better rule; materiality |
| Initial claims — DOL `DOL-UI-SA-INITIAL` | Previous eligible weekly advance/revised observation | Evidence-backed four-week average and same week prior year | Holiday effects, advance/revision choice, minimum history, DOL artifact/publication-time proof |
| Job openings — BLS JOLTS `JTS000000000000000JOL` | Previous eligible monthly observation | Same month prior year; openings rate as a separately identified related series | Level versus rate semantics, annual revision treatment, materiality and employer-demand interpretation |
| Hires — BLS JOLTS `JTS000000000000000HIL` | Previous eligible monthly observation | Same month prior year; hires rate as a separately identified related series | Gross-flow versus net-employment interpretation, revision treatment, materiality |

No condition label should be activated for these records until the applicable
reference and display profiles are approved and tested.

## 9. Stability and public “Unstable” wording

Current State Contract authority uses typed regime states including `STABLE`,
`SHIFTING`, and `UNKNOWN`. This profile does not add `UNSTABLE` as an analytical
state.

Public “Unstable” may be considered only as a transparent display mapping from
an approved governed state—such as `SHIFTING` plus a separately approved
volatility/direction-change rule. That future rule must specify:

- minimum comparable history;
- lookback window;
- source-cadence compatibility;
- preliminary/revision treatment;
- missing-interval behavior;
- volatility and/or direction-change method;
- structural-break handling;
- materiality and false-alarm tests;
- effective version and derivation.

One surprising value, one official revision, or one source outage is not enough
to label the economy/factor unstable.

## 10. Freshness and live-data semantics

### Definition

`LIVE` means automatically maintained in accordance with the native official
source cadence. It does not mean tick-by-tick streaming.

The system distinguishes:

- observation/valid period;
- official publication/public-availability time;
- AUXSAYS retrieval time;
- AUXSAYS accepted/system-known time;
- system evaluation time;
- snapshot generation time;
- snapshot activation time;
- next expected official release, when known.

### Candidate freshness display

| State | Meaning | Compact treatment |
|---|---|---|
| Current | Source and accepted observation meet the declared cadence/release policy | Usually quiet; exact detail on demand |
| Delayed | Expected official release/retrieval is late but inside the governed delayed policy | Short delayed label and reason/next check |
| Stale | Governed stale threshold/release expectation has been exceeded | Persistent text; retain last valid value only with represented period |
| Unavailable | No eligible value can be displayed | No substitute number; reason and source health when public-safe |

A monthly series does not become stale because the page was opened hours after
the last AUXSAYS check. Page-load age and source freshness are distinct.

## 11. Deferred manifest-revalidation recommendation

Workstream 0 implements no polling. A later implementation review should start
from this conservative candidate:

1. check the current manifest on page load;
2. revalidate on visibility return only when the prior check is sufficiently
   old;
3. use bounded periodic revalidation while continuously open, initially around
   10–15 minutes rather than 60–120 seconds;
4. honor ETag/hash/cache identity;
5. use exponential backoff and visibility/offline awareness;
6. fetch a new immutable snapshot only when manifest identity changes;
7. measure hosting requests, transfer, and user value before tightening cadence.

Exact intervals are implementation choices subject to performance and hosting
review. Official source cadence still governs actual freshness.

## 12. Revision

Revision state is source-specific and separate from direction/freshness:

- Advance;
- Preliminary;
- Revised;
- Final;
- Not stated/unknown.

An official revision produces a new immutable knowledge event. The UI may call
attention to a new revision once, but it must retain the earlier as-of truth and
must not present AUXSAYS retrieval as the official publication event.

## 13. Evidence

The evidence presentation retains typed dimensions from current contracts:

- class: `DIRECT`, `STRUCTURAL`, `STATISTICAL`, `MODELED`, `HYPOTHESIS`;
- quality: `STRONG`, `MODERATE`, `WEAK`, `INSUFFICIENT`;
- calibration: `CALIBRATED`, `UNCALIBRATED`, `NOT_APPLICABLE`;
- regime: `STABLE`, `SHIFTING`, `UNKNOWN`;
- source/provenance and derivation references.

No generic confidence percentage replaces these dimensions. The compact view
may say “Official measurement” or “AUXSAYS calculation”; the inspector exposes
the exact evidence/method and original source/derivation.

## 14. Coverage

Presentation must separate:

| Coverage type | Example |
|---|---|
| Taxonomy completeness | `10 of 10 Employment Sub-A concepts approved` |
| Current data coverage | `6 of 10 approved factors currently eligible` |
| Source health coverage | `3 of 4 expected source families current` |
| Structural coverage | `Energy vertical slice only; not economy-wide` |
| Derivation completeness | `2 of 3 displayed CALCs reproducible from retained public-safe references` |

`COMPLETE`, `PARTIAL`, and `SPARSE` remain governed analytical/evidence labels
where applicable. A visual ring must name the dimension it summarizes. If the
taxonomy itself is incomplete, the UI cannot call the branch merely
“partial-data.”

## 15. Factor-specific headline and roll-up requirements

There is no universal good/bad score and no generic `average(children)`.
Every Core/Sub-A headline CALC requires a versioned factor-state profile with:

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

When evidence does not support weights, use a governed ordinal method or return
`MIXED`, `PARTIAL`, `UNKNOWN`, or no headline. Positive, negative, unknown, and
conflicting components remain inspectable.

## 16. Visual status cues

### Priority

State meaning should usually be visually stronger than node type. The overview
shows only information that earns space.

Candidate compact content, shown selectively:

- short factor label;
- condition when justified;
- direction when justified;
- one primary value only when it honestly represents the factor;
- freshness only when materially useful;
- restrained, explicitly named coverage indication.

### No mandatory icon system

A factor may use a recognizable identity mark only when it materially improves
recognition without requiring a legend. Arbitrary legend-dependent glyphs are
prohibited. This profile does not require every node to contain an icon.

### Redundant state meaning

- Text is required for material state meaning.
- Color is supplementary and never the sole carrier.
- At least one additional non-color cue is available where needed: boundary,
  form, line pattern, direction mark, static treatment, or motion with a
  reduced-motion equivalent.
- Do not mechanically require word + icon + shape + color on every node.
- Avoid a universal green=good/red=bad mapping when factor interpretation is
  conditional or dual.

## 17. Hover, focus, selection, and progressive disclosure

### Whole-system overview

- prioritize the primary interface over large explanatory text;
- show concise state only when evidence and coverage justify it;
- keep detailed provenance off the node.

### Hover and keyboard focus

- concise preview;
- immediate emphasis of accepted factual relationships only;
- no camera movement from hover alone;
- focus at least as visible as hover;
- no critical meaning available only on hover.

### Selection

- spatial drill into the hierarchy;
- parent context remains perceptible;
- contextual inspector opens progressively;
- first layer: definition, what is tracked, current supported state, represented
  period, and source/claim class;
- second layer: compared-with reference and why the state reads this way;
- third layer: evidence, timing, revision, methodology, and derivation.

Touch, keyboard, list/search, browser history, and reduced-motion equivalents
must preserve the same material information. Workstream 0 changes no UI.

## 18. Connector presentation boundary

The interface must visually and semantically separate:

```text
hierarchy tether
≠ accepted structural relationship
≠ active propagation
≠ R&D test fixture
```

A hierarchy tether indicates only parent/child navigation. A factual structural
connector requires accepted evidence and lifecycle state. Active propagation
requires an eligible run and retains outcome semantics such as `BLOCKED`,
`ABSORBED`, `PARTIALLY_ABSORBED`, `DELAYED`, `AMPLIFIED`, or `TRANSMITTED`.
Fixture animation remains unmistakably fixture-only.

The current accepted factual structural relationship count is zero; this draft
creates none and does not change Gate B.

## 19. PDI compatibility review

| Need | Current compatibility | Draft recommendation |
|---|---|---|
| Claim class and material value/unit/time/source/provenance | Existing PDI common typed item | Reuse; do not duplicate in presentation extension |
| Snapshot evaluation/generation/activation/as-of/publication class | Existing PDI snapshot metadata | Reuse exact semantics |
| Cadence-aware source freshness/methodology/rights | Existing PDI source reference | Reuse and present progressively |
| Evidence, coverage, regime dimensions | Existing typed uncertainty/evidence approach | Reference approved fields; no generic confidence |
| Canonical factor registry and hierarchy placement registry | Candidate additive namespaced extension | Placements reference one canonical analytical truth; review schema names later |
| Direction/condition/stability display mapping IDs and labels | Candidate additive namespaced extension | Mapping remains canonical-state/profile authority, not placement-owned truth |
| Reference-profile identity and “compared with” summary | Candidate additive namespaced extension or CALC derivation reference | Avoid duplicating analytical authority |
| Taxonomy completeness versus current-data coverage | Candidate additive namespaced extension | Keep dimensions separate |
| Related-record collections | Candidate additive namespaced extension | Must not redefine `childRefs[]` silently |
| Item-level `publicationClass` | Conflicts with PDI snapshot ownership | Prohibited |
| Exact-ten/View All behavior | Governed by BINDING UI/UX 1.0.1 UX-003/UX-006/UX-060–UX-062 | Preserve canonical truth, exact-ten placement, and related-record distinctions |

This profile does not amend a BINDING contract or schema. UI/UX 1.0.1 was
separately Taylor-approved and promoted. PDI `extensions` permits namespaced
additive candidates that do not override core semantics, but actual public
schema activation requires separate review and compatibility tests.

## 20. Failure and degraded presentation

| Condition | Required behavior |
|---|---|
| Missing | No value; explicit missing reason when known; never zero |
| Stale | Retain represented period and stale text if last valid value remains publishable; never neutral |
| Delayed official release | Distinguish source delay from system failure |
| Rights-blocked | Suppress affected content and state the public-safe rights condition; not missing |
| Contradictory evidence | Preserve disagreement; use Mixed/Unknown or suppress headline per profile |
| Insufficient history | Do not infer trend/stability |
| Candidate calculation failure | Do not activate; prior valid snapshot behavior remains governed by Data Contract |
| Unsupported forecast | Forecast unavailable/not yet supported; no fixture substitution |
| Sparse structure | State bounded domain; never imply economy-wide coverage |

## 21. Draft decisions and risks

### Decision posture

| Decision | Draft result |
|---|---|
| LD-003 universal condition vocabulary | Not frozen; display mappings are factor/domain specific |
| LD-004 per-indicator references | Approved principle; six candidate families documented, thresholds unresolved |
| LD-005 public “Unstable” | Possible only as a transparent mapping from governed state plus approved rule; no new analytical state |
| LD-006 PDI extension | Prefer compatible namespaced additive extension; review only |
| LD-007 headline condition | Complete taxonomy + sufficient eligible evidence + factor-specific conflict/coverage rule; otherwise Partial/Mixed/Unknown/no headline |
| LD-008 factual connectors | Accepted relationships + applicable Gate-B evidence + Human QA only |
| LD-010 activation | Local QA → technical/external audit → Taylor Human QA → explicit factual activation → explicit deployment authorization |

### Principal risks

- Friendly display words can become an ungoverned second analytical model.
- Direction may be mistaken for desirability or a forecast.
- “Live” may be mistaken for real-time streaming.
- Source freshness may be confused with page/snapshot age.
- Coverage rings may hide which coverage dimension they represent.
- Universal color semantics may misstate dual or context-dependent factors.
- A short-term movement may be mislabeled unstable.
- A hierarchy tether may look causal.
- A CALC may look like an official measurement when placed beside OBS.
- Aggressive polling may add cost without fresher official information.

Controls are versioned mapping profiles, explicit references, independent
dimensions, progressive evidence, source-cadence health, non-color cues, strict
claim labels, bounded connectors, and fail-closed coverage rules.

## 22. Validation requirements for later implementation

Before any public activation, tests must prove:

- identical analytical input/profile produces identical display output;
- frontend cannot change reference, direction, condition, or freshness;
- direction and desirability remain separate for opposite-polarity indicators;
- each display label traces to a governed analytical state and mapping version;
- every placement of one canonical factor resolves to the same eligible claim,
  state, reference, and provenance at a named snapshot/cutoff;
- placement metadata cannot create, duplicate, or contradict analytical truth;
- revisions preserve earlier as-of truth;
- source-relative delayed/stale behavior follows cadence;
- taxonomy completeness and current coverage cannot substitute for each other;
- color, pointer hover, motion, and icons are not required to understand state;
- OBS and CALC remain distinguishable;
- fixture and factual states cannot mix;
- structural connectors cannot appear before accepted relationship authority;
- no Phase-5 language appears in current-state presentation.

## 23. Recommendation

**RETAIN AS DRAFT PRESENTATION PROFILE — NO IMPLEMENTATION AUTHORITY.**

External review should still resolve display-mapping vocabulary, the six
reference families, and exact field ownership. Exact-ten/View All authority is
now BINDING in UI/UX 1.0.1. Do not implement Workstream 1, manifest polling, UI
changes, source changes, BEA work, Gate-B closure, forecasting, activation, or
deployment from this draft alone.
