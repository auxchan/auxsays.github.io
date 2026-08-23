# Phase-4 Structural Surface R&D Round 2 — Human Visual QA

Status: **PENDING HUMAN VISUAL QA**

This review covers only the development-only structural renderer, spatial
navigation, label hierarchy, node grammar, and Explore/Trace interaction.
`HUMAN_PHASE4_MOTION_QA` remains **PENDING**.

## Taylor correction state — prior composition rejected

Taylor rejected the prior Round-2 composition as visually convoluted. The
focused surface retained unrelated ghost geometry, deep navigation accumulated
an overlong click-history trail, Explore competed with the synthetic motion
controls, and factors did not provide a useful hover response. That judgment is
recorded as a visual **FAIL** for the prior composition; it does not promote or
resolve Human QA.

This correction makes Explore structurally static (no causal playback), removes all
geometry outside the governed visible relationship set, limits the navigation
trail to the current and immediately previous focus, and gives pointer and
keyboard focus a coordinated factor/incident-link preview. Synthetic route
selection, playback, status readout, and motion legend now appear only in
Trace.

## Taylor follow-up — navigable node workspace candidate

Taylor found the cleaned composition directionally better but asked to restore
the sense that the system is alive, make factor roles and identities readable,
and give the graph a professional node-workspace camera. The candidate now:

- runs restrained ambient light along only the governed visible connectors in
  Explore; this is navigational motion, not a causal or factual claim;
- assigns coordinated colors to source, production, buffer, infrastructure,
  demand, and human-impact roles;
- draws a unique intuitive line symbol for every synthetic factor;
- zooms around the cursor with the mouse wheel, bounded to 70–240%;
- pans only while the middle mouse button is held; ordinary clicks retain node
  selection and cannot begin a pan; and
- exposes compact keyboard-accessible zoom/reset controls while reduced-motion
  mode keeps connectors static.

## Taylor follow-up — factor guide and scroll containment

Taylor approved leaning further into the node-workspace direction and requested
more icon breathing room, a premium left-side factor explanation, and reliable
page-scroll containment while the pointer is inside the workspace.

The candidate now enlarges every node shell and hit target around its inner
symbol. Selecting a factor unfolds a color-coordinated guide from the far left
without covering the graph. The guide uses a concise, plain-language structure:

1. what the factor is;
2. what it tracks;
3. why it matters; and
4. why each directly connected factor is present and how the relationship runs.

Connection counts are derived from the model. The guide does not invent or pad
to ten connections when fewer are available. It excludes derivation IDs and
internal implementation jargon from the primary explanation while retaining a
short synthetic-prototype boundary. The explanation copy remains in the guarded
development-only `TEST_FIXTURE` read model and is absent from production assets.

Wheel events over the graph are captured by a non-passive listener and converted
only into cursor-anchored zoom. Wheel events over the guide are contained and
scroll only that guide. Neither surface can scroll the surrounding page.

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
10. **Hover preview:** without selecting a factor, hover it. Confirm its node,
    label, and immediate visible links strengthen while the rest recedes.
11. **Deep navigation:** select at least four successive factors. Confirm the
    trail never becomes a long click history and contains only root, previous,
    and current focus.
12. **Explore/Trace boundary:** confirm Explore has no route controls, running
    signal, outcome legend, or motion readout. Confirm those return in Trace.
13. **Connector life:** confirm Explore connectors carry a restrained traveling
    light without reading as a factual shock, and hovered incident links become
    distinctly brighter.
14. **Node language:** confirm role colors feel coordinated and all nine symbols
    are recognizable enough to distinguish the factors before reading labels.
15. **Wheel zoom:** place the cursor over several parts of the graph and scroll
    in/out. Confirm the point under the cursor remains visually anchored and
    page scrolling resumes outside the graph.
16. **Middle-drag pan:** hold the middle mouse button and drag in several
    directions. Confirm it feels immediate, ordinary left click still selects,
    and no browser autoscroll UI appears.
17. **Viewport recovery:** use the compact controls to zoom and reset. Confirm
    the overview can always be recovered in one action.
18. **Icon breathing room:** inspect all nine node shells at overview and focused
    depths. Confirm every symbol is centered, legible, and evenly padded.
19. **Factor guide:** select Storage, Utilities, Freight, and Employment. Confirm
    the guide unfolds from the far left, the graph makes room without being
    covered, and content changes cleanly between selections.
20. **Explanation quality:** confirm definition, tracking, impact, and connection
    reasons are succinct and understandable without technical knowledge.
21. **Truthful connection count:** confirm each guide reports only its real direct
    fixture connections and does not pad the list to ten.
22. **Scroll containment:** wheel over the graph, the guide, and then the page.
    Confirm the graph zooms, the guide scrolls internally, and the page scrolls
    only when the pointer leaves the workspace.

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
18. Are unrelated ghost nodes and paths completely absent from focused Explore?
19. Does factor hover communicate "this is interactive" and preview its local
    importance before committing to a click?
20. Is the short navigation trail clearer than the rejected accumulated path?
21. Does the connector lighting restore energy without restoring clutter?
22. Do color and symbol together make each factor easier to locate and remember?
23. Does wheel zoom feel anchored, bounded, and predictable?
24. Does middle-button panning feel like a professional node workspace?
25. Does the guide unfold with a premium, deliberate transition?
26. Does the guide feel educational rather than like another technical panel?
27. Are the connection explanations short, useful, and visually scannable?
28. Can the user move between factors without being inundated by text?

Taylor must record PASS or corrections. This R&D record does not approve Motion
QA, factual relationships, Gate B, Phase 5, public activation, or deployment.
