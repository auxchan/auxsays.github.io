# Phase-4 Structural Surface R&D Round 2 — Human Visual QA

Status: **PENDING HUMAN VISUAL QA**

Licensed factor-imagery treatment: **PASS — Taylor, 2026-08-23**

Connector-hover easing and Home navigation: **PENDING HUMAN VISUAL QA**

Node-color connector lighting correction: **PENDING HUMAN VISUAL QA**

Layered depth and spring-parallax exploration field: **PENDING HUMAN VISUAL QA**

Interface-first overview and explicit underlying factors: **PENDING HUMAN VISUAL QA**

Stable-map camera swing and legible sublayers: **PENDING HUMAN VISUAL QA**

Employment-centered orbital overview and Reset behavior: **PENDING HUMAN VISUAL QA**

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

## Taylor follow-up — educational close-up and legibility

Taylor found the factor-guide direction strong but rejected its very small text
and reported that the selected node/icon could disappear during selection. The
candidate now uses materially larger guide typography and a large visual factor
portrait. Each portrait reuses that factor's distinct symbol in an atmospheric,
code-native scene that teaches category and connectedness without pretending a
synthetic factor is factual evidence or relying on generic stock photography.

Selection now triggers a stronger camera fly-in. A DOM-backed selected-node
anchor remains present above the animated canvas throughout the layout and panel
transition, so the chosen factor stays visible, colored, and identifiable even
while the network repositions. The canvas node also receives a larger selected
render and halo. Reduced-motion mode keeps the same visual hierarchy without the
orbit or fly-in animation.

Human review should confirm:

1. the guide is comfortably readable at 100% browser zoom;
2. every factor portrait is visually distinct and relevant to its role;
3. the selected graph node remains visible from click through settled layout;
4. selection feels like a purposeful close-up rather than a disappearing filter;
5. the portrait helps explain the factor without overwhelming the short copy.

## Taylor follow-up — blended real-world context

Taylor approved using appropriately licensed real-world imagery for selected
factor closeups provided it does not read as an out-of-place stock-photo card.
The petroleum-refining, product-distribution, and freight-transportation guides
now use reviewed public-domain or CC0 images as subdued environmental
backplates. A site-matched cyan/indigo grade, lowered saturation and brightness,
strong radial edge fade, grid/texture overlays, and the existing factor symbol
keep each image inside the established visual system.

The original source and rights credit remain one concise link below the guide.
Images are available only from an exact loopback-development allowlist and are
not bundled into production. They illustrate the factor category; they are not
evidence for the synthetic relationships.

Human review should additionally confirm:

1. imagery feels integrated with the site rather than pasted into a rectangle;
2. the factor icon and title remain visually primary;
3. the subject remains recognizable through the grade and edge fade; and
4. the credit is reachable without adding clutter to the main explanation.

Taylor passed that four-part licensed-imagery treatment test. The approved
blend is now applied to every current factor. This is a subtest PASS only;
overall spatial-renderer and Motion QA remain pending.

The renderer now enforces a future-node media gate: a new node is invalid until
it supplies a distinct reviewed local image plus plain alt text, exact source
page, license classification, and credit. The loopback server must also add the
file to its explicit allowlist. Tests reject missing imagery and surface
duplicate coverage during review.

## Safety boundary

- Fixture class: `TEST_FIXTURE`
- Candidate eligibility: `NEVER_ACCEPTED_NEVER_PUBLISHED`
- Accepted/factual relationships: `0 / 0`
- Gate B: `OPEN_UNCHANGED`
- Phase 5: `LOCKED`
- Public activation/deployment: not authorized

The labels are realistic synthetic names for typography and navigation review.
They are not claims about the U.S. economy.

## Taylor follow-up — connector easing, Home, and numbers boundary

Taylor found the connector emphasis too abrupt on factor hover and requested a
clear route back to the full core-factor viewpoint. Explore connectors now ease
between baseline and focused states rather than changing opacity, thickness,
arrows, and glow in one frame. Reduced-motion mode keeps the same semantics
without an animated ramp.

A visible Home control now performs the complete reset: leave Trace, stop fixture
playback, close the factor guide, clear navigation depth, restore default zoom
and pan, and show the full core-factor overview.

Real structural numbers were deliberately not added in this UI correction. The
current Phase-4B candidate reports `BLOCKED_LIVE_BEA_CREDENTIAL`, zero accepted
structural relationships, and no structural calculations. Adding values to the
synthetic nodes now would visually overstate the evidence. Existing governed
factual labor observations remain separate until an authoritative node mapping
and accepted structural read model exist.

## Taylor correction — connector light color, not speed

Taylor's first visual check found that the connector lights accelerated briefly
instead of visibly fading into the selected factor's palette. The hover-speed
coupling has been removed. Glints now retain one constant travel period and
constant trail length; the connector rails, arrows, glints, and glow ease into
the hovered node's accent color and ease back to the ambient palette on exit.

## Taylor exploration direction — layered depth

Taylor requested a cleaner first read that still signals substantial depth
beyond the foreground. The development surface now derives a bounded visual
depth from non-terminal fixture graph distance. Deeper factors become gradually
smaller and more translucent; selection, hover, and active states restore full
emphasis. Blocked, absorbed, and unknown routes are excluded from overview depth
ranking so they do not visually promote a downstream factor as though pressure
successfully reached it.

A sparse deterministic particle field occupies optical layers 2–10. Its pointer
response uses a damped spring and shallow per-layer displacement to create depth
without behaving like decorative confetti. Reduced-motion mode freezes the
field. These layers are explicitly visual R&D and do not encode factual
magnitude, importance, accepted relationships, or hidden economic observations.

## Taylor correction — show the underlying system

Taylor correctly found that the first depth pass still looked essentially like
the prior nine-node graph: particles and optical depth implied complexity, but
there were no actual subordinate factors to explore. Taylor also found
Employment visually isolated and the large Summary headline disproportionate
to a page whose primary purpose is the structural interface.

The corrected candidate now renders 18 explicit synthetic subordinate factors,
two for every core node. They are smaller and more translucent than the core
system, connected to their parent by quiet tethers, and become fully readable
on hover or keyboard focus. Selecting one opens its parent factor closeup, where
the same two names appear under a short **Underlying factors** explanation. This
is navigable information architecture, not a particle-only depth suggestion.

The 10-link overview cap now preserves the selected primary route before filling
remaining slots. That keeps the governed delayed `Industry → Employment`
fixture relationship visible in the common-origin overview and prevents
Employment from appearing disconnected.

The visible marketing-style Summary hero has been removed from this laboratory;
its route heading remains screen-reader accessible. The graph is placed directly
after the compact product navigation, while Explore/Trace and playback controls
now follow the interface. No factual subfactor values or relationships were
invented for this visual correction.

## Taylor correction — legibility, parallax, and camera continuity

Taylor found the subordinate factors too small to read or select reliably, the
particle/parallax field effectively invisible, and the selected-factor behavior
closer to a graph relayout than a camera moving through one persistent space.

The subordinate controls now provide a 44-pixel target while retaining a smaller
visual hierarchy than the nine core factors. Their markers, labels, and parent
tethers are materially stronger at rest and receive full emphasis on hover,
focus, or parent selection.

The deterministic field now draws eight depth particles per core node plus a
quiet orbital guide. Particle size, alpha, glow, drift, and spring-parallax
travel were raised to a visible but bounded range. Reduced motion continues to
freeze drift and parallax while preserving the static depth cues.

Most importantly, selection no longer recalculates the node map around a new
center. The model retains one stable coordinate system. A 760-millisecond
curved camera interpolation zooms and pans toward the selected factor, while
the detail guide slides over the left edge without changing canvas width. This
borrows the useful interaction principle of a hierarchical galaxy map—entering
a closer level of one continuous space—without copying game artwork or UI.

This remains a synthetic visual laboratory. The stronger depth cues and camera
motion do not represent factual magnitude, causal strength, or accepted
structural evidence.

## Taylor correction — Employment-centered orbit and immediate reset

Taylor found the overview organization insufficiently coherent, the parallax
response too delayed, and the Home terminology less accurate than Reset. Taylor
also requested the familiar spatial shortcut of double-clicking empty space to
recover the complete overview.

The persistent visual map now places Employment at its center and arranges the
other eight core factors around it as an orbital navigation composition. Both
governed synthetic relationships into Employment remain visible within the
ten-link overview limit. This makes the human-impact endpoint visually central
without changing the fixture graph or claiming that Employment is the causal
origin of the system.

The single recovery control is now named Reset and performs a complete reset of
selection, Trace mode, camera focus, zoom, pan, hover emphasis, and parallax.
Double-clicking empty graph space performs the same action; interactive controls
are excluded so their normal double-click behavior cannot trigger it. The former
duplicate icon-only reset control was removed.

The parallax spring is materially more responsive and more strongly damped,
reducing cursor lag without increasing its bounded travel. Reduced-motion mode
continues to disable parallax movement.

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
23. **Orbital overview:** confirm Employment reads as the stable central anchor,
   all other core factors remain easy to locate around it, and both visible
   incoming Employment relationships are legible.
24. **Reset recovery:** enter a factor, enable Trace, zoom, and pan; then use
   Reset. Repeat and double-click empty graph space. Confirm both routes restore
   the same complete overview in one action.
25. **Parallax response:** move the pointer through the graph and confirm the
   depth field responds promptly, settles quickly, and does not trail the cursor
   with the prior sluggish feel.

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
