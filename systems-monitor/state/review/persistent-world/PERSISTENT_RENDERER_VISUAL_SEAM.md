# Persistent Renderer Visual Seam

Status: **READ-ONLY FORENSICS COMPLETE**

## Ownership

- `PersistentWorldShell` creates one frozen model and owns selection, URL history, full-world, fullscreen, Reset, inspector and reduced-motion state.
- `persistentWorldModel.ts` owns all stable IDs, parentage, 1,111 coordinates, 3,110 relationships and fingerprint.
- the Canvas surface owns only camera, viewport, hover, pan, drawing and instrumentation.

Selection already changes camera and semantic LOD without changing graph membership. That division remains authoritative.

## Coordinate/camera seam

World coordinates are projected as:

`screen = viewport center + (world - camera) × scale × zoom + pan`

The deterministic camera targets remain overview/full-world/Level-1/Level-2/Level-3 view states. Premium visual primitives consume projected points and must never write coordinates back to the model.

## Render seam

The safe seam is the visual draw block in the persistent Canvas surface:

1. atmospheric background, grid and vignette;
2. orbital guides and bounded particles;
3. inexpensive resident hierarchy/influence density;
4. premium curved semantic rails and glints;
5. inexpensive nonsemantic density points;
6. premium Outcome/Level-1/focused node shells and glyphs;
7. deterministic collision-managed labels.

## Interaction/LOD seam

The existing `semanticIds()` bounds hit testing and detail:

- overview: Outcome + ten Level-1 nodes;
- nonleaf focus: parent + selected + exact-ten children;
- leaf focus: parent + ten siblings.

All 1,111 placements stay resident. The semantic set receives rich visuals. The rest receives inexpensive structural presence.

## Required correction discovered

Reduced motion previously drew only once, so wheel/pan ref updates could be visually stale. The premium surface needs an on-demand invalidation function while keeping glints, particles and parallax stopped.

## Hard prohibition

Do not route the persistent model through the old complete `CanvasStructuralRenderer`. Its drawing primitives are useful; its selection-keyed layout machinery is not.
