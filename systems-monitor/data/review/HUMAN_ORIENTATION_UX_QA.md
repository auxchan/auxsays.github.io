# HUMAN_ORIENTATION_UX_QA

Status: **PASS**

Gate ownership: independent human reviewer

Implementation start: `270812c0d8951ac0839639ddf0f1e8f798e71833`

Loopback route: `http://127.0.0.1:4173/__local-review/orientation`

Start the review surface from `systems-monitor/app`:

```text
npm run dev:orientation-qa
```

Taylor completed the governed review and approved the current orientation UX on
2026-09-27. This approval closes the orientation gate only; it does not approve
Level-4 economic content, structural relationships, causal interpretation,
materiality, forecasting, or fixture publication.

## Five-second orientation questions

- [x] Can I tell what changed within five seconds?
- [x] Can I tell which branch the changes belong to?
- [x] Can I switch to **All systems**?
- [x] Can I identify source-health exceptions without mistaking them for economic signals?
- [x] Can I understand why a factor lacks interpretation?
- [x] Can I orient myself in the persistent world?
- [x] Can I navigate Back, Up, and Search without losing context?
- [x] On mobile, can I see the graph without controls obscuring it?
- [x] On mobile, can I open and close the inspector cleanly?
- [x] Are mobile labels legible and touch controls usable?
- [x] Does the mobile briefing remain concise?

## Five-second desktop briefing

- [x] The first scan answers **What moved?**, **What is covered?**, and **What needs attention?** without scrolling.
- [x] Movement rows contain only accepted comparable factual observations and show factor, direction, absolute change, and period.
- [x] No movement row implies importance, supportive/adverse impact, materiality, causality, or a forecast.
- [x] Movement order is newest official publication/observation first and remains stable on refresh.
- [x] Clicking a movement focuses the existing factor and opens its existing inspector; it creates no second analytical object.
- [x] Coverage counts clearly name the current branch or the whole-system scope.
- [x] The DOL primary-method stale state remains visible while the separate official fallback remains current.
- [x] The briefing reads as one compact instrument, not a wall of cards.

## State language and scope

- [x] Comparable accepted history says **Direction verified · interpretation not governed**.
- [x] A single accepted observation says **Not enough comparable history**.
- [x] An identified source without an accepted reading says **Source identified · verified reading not yet available**.
- [x] A blocked path says **Source currently blocked**.
- [x] A derivation-dependent concept says **Structural interpretation unavailable**.
- [x] Movement language says **materiality not assessed**.
- [x] What Changed defaults to the selected branch after entering a branch.
- [x] **All systems** is an explicit control and never silently mixes with selected-branch results.
- [x] Operational source events are visually and semantically separate from factual observation/revision events.

## Mobile and touch

- [x] At 375 × 812 and 430 × 932, the map remains the primary surface and is not covered by a vertical control stack.
- [x] The bottom toolbar prioritizes Back, Up, Search, World, and Inspector; secondary modes live under More.
- [x] Toolbar and inspector controls have at least 44 CSS-pixel targets.
- [x] The inspector opens as a full or near-full dialog, traps keyboard focus, closes with Escape, and restores focus to Inspector.
- [x] Touch selection is reliable for map nodes, briefing rows, toolbar controls, and inspector links.
- [x] Mobile label density is reduced through label selection; text is not made too small to read.

## Accessibility and motion

- [x] Keyboard users can reach briefing rows, scope/window controls, map alternatives, toolbar controls, and inspector actions in a sensible order.
- [x] Visible focus is clear; controls have names, states, and disabled semantics.
- [x] Reduced-motion mode removes decorative transition/arrival animation without removing information or navigation.
- [x] Screen-reader reading order keeps the briefing before map controls and distinguishes the mobile inspector as a modal dialog.

## Reviewer result

Reviewer: Taylor

Date/time: 2026-09-27

Viewport/device/browser: Governed desktop and mobile review surfaces

Result: `PASS`

Notes or blocker: Approved as the framework orientation checkpoint; scientific and Level-4 boundaries remain unchanged.
