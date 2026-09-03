# Level-3 Framework Acceptance Evidence

Date: 2026-08-31

Machine gate: **PASS**

Human gate: **PENDING**

Framework status: `LEVEL3_FRAMEWORK_READY = PENDING_HUMAN_QA`

This is a certification record for the existing persistent-world parent framework. It does not approve additional Level-4 economic content, structural relationships, forecasting, or deployment of fixture claims.

## Certified inventory

| Check | Result |
| --- | ---: |
| Semantic Level-3 parents | 100 / 100 |
| Exact-ten handoffs | 100 / 100 |
| Persistent Level-4 placements | 1,000 / 1,000 |
| Top-down deterministic layout sweep | 100 / 100 |
| Cinematic 2.5D deterministic layout sweep | 100 / 100 |
| Inspector/source-profile resolution | 100 / 100 |
| Accepted structural relationships | 0 |
| Factual structural relationships | 0 |
| Fixture-only Level-4 placements | 900 |

The immutable world remains 1 outcome + 10 Level-1 systems + 100 Level-3 parents + 1,000 Level-4 placements. The current topology fingerprint is `fnv1a32:88684cdb`. The older `fnv1a32:73cac7b9` cited in historical QA evidence is superseded and is not the current gate oracle.

A separate semantic/governance fingerprint, `fnv1a32:9647fd3f`, now covers canonical identities, placement order and labels, evidence posture, source family, and relationship status/evidence/publication eligibility. This closes the gap in which semantic or governance mutation could pass a geometry-only topology check.

## Source and factual boundaries

All 100 Level-3 parents resolve to an explicit source-readiness profile. Four canonical factors have accepted read-only observations in the persistent-world surface:

- Labor-Force Participation — 61.4 percent, July 2026, BLS CPS `LNS11300000`.
- Initial Claims — 209,000 claims, week ending 2026-08-08, DOL ETA `DOL-UI-SA-INITIAL`.
- Job Openings — 7,359 thousand, June 2026, BLS JOLTS `JTS000000000000000JOL`.
- Hires — 5,348 thousand, June 2026, BLS JOLTS `JTS000000000000000HIL`.

Five hierarchy placements point to those four canonical factors; the UI now exposes those two counts separately. Average Weekly Hours (`CES0500000002`), Average Hourly Earnings (`CES0500000003`), and Employment-Population Ratio (`LNS12300000`) remain source-identified and display no factual value. Candidate-dataset, derivation-required, and fixture records display no value and gain no acceptance through hierarchy placement.

## Automated evidence

The independent gate suite uses a frozen, hard-coded Level-1 to Level-3 parent matrix rather than the implementation registry as its own oracle. It verifies all 100 parents, their approved order, identity, parent, depth, unique children, and one-to-one hierarchy tether. It then verifies all 1,000 children remain immutable, discoverable, and nonfactual where fixture-only.

For every parent, both Top-down and Cinematic projection sweeps verify the selected neighborhood fits the target viewport, preserves exact-ten labels, and retains deterministic camera geometry. Browser QA additionally followed an ordinary navigation path rather than loading only a final hash:

`Root → Consumer Demand → Real Wage Purchasing Power → fixture child → Up → Back → Forward → Reset`

At settled Level-3 focus the rendered surface reported 12 semantic nodes, 12 current hierarchy edges, 0 previous-view edges, and both fingerprints unchanged. At the Level-4 leaf it reported 11 semantic nodes, 3 direct ancestry edges, and 0 previous-view edges. Reset returned to 11 semantic nodes, 10 current edges, and 0 previous-view edges.

## Performance

Measured Canvas draw p95 after focus-level semantic culling:

| View | p95 |
| --- | ---: |
| Overview | 2.5 ms |
| Level-1 focus | 2.0 ms |
| Level-3 exact-ten focus | 1.2 ms |
| Cinematic Level-3 focus | 1.2 ms |

All are inside the unchanged 4 ms Canvas budget and the previously observed 2.0–3.9 ms focused envelope. Rapid camera retarget tests remain part of the suite. The renderer stops idle work after motion settles and does not expand the semantic draw set to all 1,111 placements in focused views.

## Accessibility and reduced motion

- Search has bounded keyboard focus containment, Escape dismissal, and focus restoration.
- Closing the inspector removes hidden interactive descendants and restores focus to the selected structured-navigation control.
- Up, Back, Forward, Reset, breadcrumbs, structured exact-ten controls, and fullscreen retain keyboard access.
- Reduced motion is explicitly detectable and tested; it preserves selection, hierarchy, evidence, and navigation while removing decorative motion.
- Canvas remains a visual surface; structured DOM controls remain the accessible information/navigation authority.

## Defects found and repaired

1. The topology fingerprint did not detect semantic/governance mutation. A separate semantic fingerprint and mutation regressions were added.
2. Exact-ten certification reused implementation data as its oracle. An independent approved parent matrix was added.
3. Closed inspector content remained mounted and could retain focus. It is now unmounted and focus is restored.
4. The search dialog did not contain keyboard focus. A bounded focus loop was added.
5. Accepted coverage counts conflated canonical factors and hierarchy placements. Both counts are now named separately.
6. Focused layouts projected and painted unnecessary off-context placements. Focus-aware semantic culling restored the performance margin without changing membership, coordinates, or topology.
7. Sequential traversal coverage was expanded to prove previous-view connectors clear at settled focus.

## Bounded skeptic review

The skeptic challenged exact-ten oracle independence, incomplete fingerprint coverage, connector carryover, public fixture boundaries, source-profile assurance, count semantics, accessibility, reduced motion, and stale historical fingerprint evidence. Material machine-checkable issues were repaired above.

Two judgments deliberately remain for Human QA:

- Animated hierarchy tethers must still read as organizational navigation, not economic direction or causal flow.
- Visible fixture children must remain unmistakably configuration-pending/nonfactual rather than look like accepted economic content.

## Gate result

`LEVEL3_SEMANTIC_STABILITY = PASS`

`LEVEL3_EXACT_TEN_HANDOFF = PASS`

`LEVEL3_NAVIGATION = PASS`

`LEVEL3_CONNECTOR_BOUNDARY = PASS`

`LEVEL3_LAYOUT_SWEEP = PASS`

`LEVEL3_INTERACTION = PASS`

`LEVEL3_INSPECTOR = PASS`

`LEVEL3_PERFORMANCE = PASS`

`LEVEL3_ACCESSIBILITY = PASS`

`LEVEL3_REDUCED_MOTION = PASS`

`LEVEL3_FIXTURE_BOUNDARY = PASS`

The machine gate is complete. The framework is not frozen until Taylor records `HUMAN_LEVEL3_FRAMEWORK_QA = PASS`.
