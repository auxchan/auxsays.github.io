# Human Level-3 Framework QA

Status: `HUMAN_LEVEL3_FRAMEWORK_QA = PENDING`

Machine gate: **PASS**

Framework status: `LEVEL3_FRAMEWORK_READY = PENDING_HUMAN_QA`

Preview: `http://127.0.0.1:4174/systems-monitor/#persistent-world`

This review is intentionally bounded. The automated gate covered all 100 parents in both layouts; Human QA is for visual and product judgment, not manual rechecking of every node.

## Representative run

1. At Employment overview, confirm the ten Level-1 systems are readable and the page states that connectors are hierarchy/drill-down only.
2. Open **Labor Supply**. Confirm the exact-ten neighborhood is readable, search/minimap/breadcrumbs agree, and no previous-view connectors remain after the camera settles.
3. Open **Labor-Force Participation**. Confirm the accepted 61.4% reading, July 2026 period, BLS CPS series `LNS11300000`, evidence, methodology, and acquisition provenance remain separate from the node title.
4. Open **Employer Labor Demand → Average Weekly Hours**. Confirm series `CES0500000002` is source-identified but no factual value is displayed.
5. Open **Output & Growth → Real GDP Growth**. Confirm its BEA NIPA posture is candidate-dataset and no factual value is displayed.
6. Open **Employer Labor Demand → Vacancy Duration**. Confirm its posture is derivation-required and no factual value is displayed.
7. Open one **Renderer fixture** child beneath a non-Layoffs parent. Confirm it is explicitly fixture/configuration-pending, has no value, and does not appear accepted.
8. Open **Policy, Trade & External Shocks** as the diagonal sector and **Layoffs & Job Destruction → Establishment Death / Closure Losses** as the dense/long-label case. Confirm labels, controls, and inspector do not collide.
9. Repeat one drill path in **Top-down** and **Cinematic 2.5D**. Confirm the same nodes and hierarchy remain available, camera travel is smooth, and the angled view does not hide required information.
10. Use Up, Back, Forward, search jump, Reset, Full-world view, Trace, orbit drag, middle-pan, wheel zoom, and fullscreen. Confirm controls do not conflict and settled views contain no stale connectors, highlights, labels, or black frame.
11. With reduced motion enabled at the operating-system/browser level, repeat a drill path. Confirm topology, selection, hierarchy, inspector, and evidence access remain complete while decorative motion is removed.
12. Use keyboard-only navigation through search, the structured exact-ten list, inspector close, Up/Back/Forward, and fullscreen. Confirm focus is visible, not trapped, and returns sensibly.

## Human judgment questions

- Do hierarchy tethers read as organizational navigation rather than causal/economic flow?
- Are fixture children unmistakably incomplete/nonfactual?
- Can a user stay oriented through Root → Level-1 → Level-3 → Level-4 and back?
- Is each exact-ten neighborhood readable in both camera modes without another framework redesign?
- Does the inspector communicate identity, tracking scope, relevance, source posture, and factual status clearly without overwhelming the graph?

## Approval statement

If the run passes, record exactly:

> **HUMAN_LEVEL3_FRAMEWORK_QA: PASS. I approve the current Level-3 parent framework as ready to freeze for the subsequent governed Level-4 development pipeline. This does not approve new Level-4 economic content, structural relationships, forecasting, or fixture publication.**

Only after that approval may governance record `LEVEL3_FRAMEWORK_READY = PASS`. Do not begin the next economic sprint as part of this QA.
