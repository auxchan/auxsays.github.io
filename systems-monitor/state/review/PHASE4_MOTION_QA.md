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

The persistent banner must read:

```text
MOTION QA — SYNTHETIC TEST DATA
```

## Suggested review sequence

1. Let **Branch + reconvergence** play. Confirm the signal is transmitted,
   partially absorbed, then split into delayed and amplified branches before
   the shared target activates once.
2. Select **Primary cascade**, press **Replay**, then pause and use
   **Step forward**.
3. Select **Absorbed route** and confirm motion stops at the absorbed outcome.
4. Select **Blocked route** and confirm the route visibly stops as blocked.
5. Select **Unknown route** and confirm unresolved evidence does not look like
   successful transmission.
6. During playback, rapidly change paths and select a node. Confirm stale
   playback does not continue and the inspector opens immediately.
7. Close the inspector with its button, then reopen a node with the keyboard
   and press Escape. Focus should return to the selected node.
8. Open **Verified Data**, expand several relationship records, then open
   **Outlook**. Confirm the fixture boundary persists and no forecast appears.
9. Repeat with the operating system's reduced-motion preference enabled.
   Autoplay must be disabled while manual steps retain all meaning.
10. At a narrow browser width, confirm the graph is contained in a labeled,
    keyboard-focusable horizontal viewport and the page itself does not scroll
    horizontally.

## Human Motion QA checklist

1. Does propagation motion make the direction obvious?
2. Can I tell where a signal starts and ends?
3. Can I distinguish transmitted, delayed, partially absorbed, absorbed,
   blocked, amplified, and unknown states?
4. Does branching and reconvergence make sense?
5. Does common-origin behavior avoid looking like two independent shocks?
6. Does selection remain responsive during playback?
7. Does focused node inspection feel like navigating a system rather than a
   dashboard?
8. Are Summary, Verified Data, and Outlook transitions restrained enough?
9. Is there too much movement?
10. Does reduced-motion presentation preserve every material meaning?
11. Does the motion feel premium and analytical rather than gimmicky?
12. Do dependency relationships have a convincing visual home?

Taylor must record PASS or corrections. This file does not close Gate B,
authorize Phase 5, or authorize public activation or deployment.
