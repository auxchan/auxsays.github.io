# Phase-4 Development Motion QA

Status: **HUMAN_PHASE4_MOTION_QA = PENDING**

Scope: **DEVELOPMENT-ONLY UI / MOTION QA**

Fixture identity: **TEST_FIXTURE — NOT ECONOMIC EVIDENCE**

Gate B: **OPEN / UNCHANGED**

Phase 5: **LOCKED**

## Purpose

This harness allows Human QA of the structural-network motion and interaction
language before factual BEA relationships are available. It does not supply,
alter, or simulate evidence for Gate B.

The harness exercises nine synthetic nodes and twelve test-only relationships
through the same architectural concepts expected from a later structural read
model: nodes, relationships, path steps, origin IDs, common-cause IDs,
transmission outcomes, current states, evidence classes, derivation references,
coverage, source health, and stop reasons.

## Round-2 semantic correction

Round 2 changes the motion grammar without changing fixture evidence or the
production application architecture:

- `TRANSMITTED` uses one neutral directional signal and activates its target.
- `PARTIALLY_ABSORBED` separates an absorbed component from a thinner surviving
  continuation; only the surviving component reaches and activates the target.
- `DELAYED` visibly advances to a hold marker, waits, then resumes. Its static
  equivalent exposes `WAITING` / `DELAYING` state.
- `AMPLIFIED` widens and strengthens downstream instead of using the delayed
  hold language.
- `BLOCKED` collides with a restrained barrier before the target. The target
  remains inactive.
- `ABSORBED` contracts into a sink before the downstream target. The target
  remains inactive.
- `UNKNOWN` stops at an unresolved boundary and makes no definite downstream
  activation claim.
- One persistent origin signature follows the common-origin path through split
  and one reconciliation event.

Node state and the contextual inspector now use interaction-only motion states,
not factual economic state. The inspector occupies a reserved rail beside the
network on wide screens and a connected region below it on narrower screens.

## Round-3 SVG marker-positioning microfix

Round-3 keeps the approved Round-2 state machine unchanged and corrects only
SVG transform ownership:

- outer SVG groups exclusively own route/node translation and edge rotation;
- nested marker groups exclusively own scale, contraction, expansion, recoil,
  pulse, and opacity animation;
- absorbed, partial-absorption, amplified, origin, and reconciliation graphics
  therefore retain their governed spatial coordinates during animation;
- blocked, absorbed, and unresolved terminal treatments include a small local
  direction chevron without implying arrival at the destination;
- topology and active arrowheads are slightly larger and higher contrast while
  remaining subordinate to the analytical graph.

No motion-state meaning, inspector behavior, graph topology, fixture scenario,
factual data, or approval state changed.

## Evidence isolation

- The fixture is stored at
  `systems-monitor/app/fixtures/motion-qa-read-model.json`, outside the factual
  candidate and evidence directories.
- Every relationship and derivation is typed `TEST_FIXTURE`.
- The fixture declares `NEVER_ACCEPTED_NEVER_PUBLISHED`, zero factual
  relationships, and zero accepted relationships.
- Validation rejects factual publication class, accepted relationship status,
  changed Gate-B state, changed Phase-5 state, unsupported outcomes, invalid
  endpoints, or references outside the fixture.
- Loading is available only through a loopback development-server middleware
  registered with Vite's `apply: "serve"` boundary.
- The application reads the fixture storage key only when
  `import.meta.env.DEV` is true. A production build cannot activate it through
  URL state or local storage.
- No production navigation item is added.
- The factual Phase-4B read-model candidate, accepted relationship count,
  Gate-B evidence, and source evidence remain unchanged.

## Local demo

From `systems-monitor/app`:

```text
npm run dev:phase4b
```

Load the fixture once at:

```text
http://127.0.0.1:4174/systems-monitor/__local-review/motion-qa
```

The loader redirects to:

```text
http://127.0.0.1:4174/systems-monitor/?view=summary
```

Fixture path selectors:

```text
[data-motion-fixture-selector="fixture-path-blocked"]
[data-motion-fixture-selector="fixture-path-absorbed"]
[data-motion-fixture-selector="fixture-path-primary"]
[data-motion-fixture-selector="fixture-path-common-origin"]
```

Label-independent QA selector:

```text
#motion-label-independent-qa
```

The control is labeled **Hide explanation**. It removes the status sentence and
legend while retaining node labels, motion controls, keyboard interaction, and
the outcome graphics.

The persistent banner must read:

```text
MOTION QA — SYNTHETIC TEST DATA
```

## Round-2 suggested review sequence

1. Select **Blocked route**. Confirm the signal meets a barrier before the
   downstream node and that node never activates.
2. Select **Absorbed route**. Confirm the signal contracts into a sink before
   Employment exposure and does not activate it.
3. Select **Primary cascade**, pause, and step twice. Confirm partial absorption
   visibly separates a contained component from a thinner continuation.
4. Continue one step. Confirm the delayed signal advances, visibly waits, and
   identifies the receiving node as `DELAYING` when inspected.
5. Select **Branch + reconvergence** and step three times. Compare the amplified
   branch with the delayed branch: one strengthens while the other waits.
6. Replay **Branch + reconvergence**. Follow the persistent origin signature
   through one split and one reconciliation at Shared target.
7. Rapidly switch among several paths. Confirm no previous signal remains
   current and playback immediately adopts the final selection.
8. During playback, select a node. Confirm the graph makes the connection clear,
   the inspector does not cover the network, and Escape restores focus.
9. Press **Hide explanation** and repeat blocked, absorbed, partial, delayed,
   and amplified checks using only the motion grammar and node labels.
10. Enable the operating system's reduced-motion preference. Confirm autoplay
    is disabled and manual steps preserve all terminal, hold, attenuation,
    strengthening, origin, direction, and node-state meanings.

## Human Motion QA Round-2 checklist

1. Can I distinguish blocked from absorbed without reading text?
2. Does blocked visibly stop before the destination?
3. Does fully absorbed disappear or terminate before downstream activation?
4. Can I visually see that partial absorption leaves a smaller continuation?
5. Does delayed visibly wait?
6. Does amplified visibly strengthen rather than wait?
7. Can I follow one origin through branch and reconvergence?
8. Does reconvergence look like one event with multiple paths?
9. Is direction obvious without relying on left-to-right layout?
10. Does the inspector feel connected to the selected node?
11. Does node state remain semantically correct during motion?
12. Can I understand the core outcome with explanatory copy hidden?
13. Does reduced-motion preserve the same meaning?
14. Does the system still feel restrained and analytical?

## Human Motion QA Round-3 checklist

Use **Hide explanation** and answer only these six questions:

1. Can blocked and absorbed be distinguished immediately with explanations
   hidden?
2. Does partial absorption visibly show where the missing portion was absorbed?
3. Does amplified visibly strengthen at the correct spatial point?
4. Does one persistent origin remain visually attached to the true origin
   through split?
5. Does reconciliation occur visually at the true shared target?
6. Is direction obvious enough on curved and terminal paths without relying on
   layout?

Do not reopen inspector or rapid-switching review unless a regression appears.

Taylor must record PASS or corrections. This file does not close Gate B,
authorize Phase 5, or authorize public activation or deployment.
