# Phase-4 Structural Surface R&D Round 2 — Human Visual QA

Status: **PENDING HUMAN VISUAL QA**

This review covers only the development-only structural renderer, spatial
navigation, label hierarchy, node grammar, and Explore/Trace interaction.
`HUMAN_PHASE4_MOTION_QA` remains **PENDING**.

## Safety boundary

- Fixture class: `TEST_FIXTURE`
- Candidate eligibility: `NEVER_ACCEPTED_NEVER_PUBLISHED`
- Accepted/factual relationships: `0 / 0`
- Gate B: `OPEN_UNCHANGED`
- Phase 5: `LOCKED`
- Public activation/deployment: not authorized

The labels are realistic synthetic names for typography and navigation review.
They are not claims about the U.S. economy.

## Local review

```text
cd D:\Auxsays\auxsays.github.io\systems-monitor\app
npm run dev:phase4b
```

Load the fixture once:

```text
http://127.0.0.1:4174/systems-monitor/__local-review/motion-qa
```

The loader redirects to:

```text
http://127.0.0.1:4174/systems-monitor/?view=summary
```

## Required scenarios

1. **Overview:** confirm the broad system uses short, sparse labels and a quiet
   restrained node vocabulary.
2. **Enter domain:** select **Refining**. Confirm it becomes the local center and
   exactly its available synthetic neighbors resolve; no nodes are added.
3. **Enter second level:** select **Storage**. Confirm the breadcrumb becomes
   `Synthetic system › Refining › Storage` and the local neighborhood changes.
4. **Back out:** select **Refining** in the breadcrumb, then **Synthetic system**.
   Confirm spatial continuity and restored context.
5. **Trace:** enter **Storage**, enable **Trace**, and confirm the selected
   synthetic path dominates while unrelated structure and labels recede.
6. **Rapid change:** quickly select Refining, Storage, and Utilities. Confirm the
   final selection wins without a queued stale camera move.
7. **Label stress:** inspect the longer focused labels. Confirm the selected
   label always remains and lower-priority labels suppress before colliding.
8. **Inspect:** confirm the docked inspector updates without covering the graph,
   and Escape backs out one level while restoring useful keyboard focus.
9. **Reduced motion:** enable the operating-system reduced-motion preference.
   Confirm navigation updates almost immediately, breadcrumbs preserve history,
   and manual motion stepping retains all outcome meanings.

## Taylor checklist

1. Does clicking a node feel like entering that system?
2. Is the zoom smooth enough to preserve spatial context?
3. Do related factors appear naturally around the selected node?
4. Can I understand where I came from and go back easily?
5. Is the graph substantially less cluttered?
6. Are labels appropriate for the current depth?
7. Do labels avoid collisions and unnecessary competition?
8. Are the node forms intuitive enough without an icon legend?
9. Is state more visually important than node type?
10. Does the selected path dominate appropriately?
11. Do unrelated systems recede enough?
12. Does Trace feel different from Explore?
13. Does the inspector feel integrated with spatial navigation?
14. Does a frozen screenshot already look premium?
15. Does the experience still feel like a flowchart or node editor?
16. Is there visible text that does not earn its space?
17. Does the interface feel more like navigating a living system?

Taylor must record PASS or corrections. This R&D record does not approve Motion
QA, factual relationships, Gate B, Phase 5, public activation, or deployment.
