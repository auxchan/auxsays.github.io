# Premium Renderer Primitive Map

Status: **READ-ONLY ARCHAEOLOGY COMPLETE**  
Baseline branch/HEAD: `codex/systems-monitor-persistent-world` / `66677cbea1bd129c2738809fdaa8994029a3ab29`

## Finding

The accepted premium Structural Surface is already primarily Canvas 2D. Its useful visual language is concentrated in:

- `app/src/views/motion/structuralRenderer.ts`
- `app/src/views/motion/CanvasStructuralSurface.tsx`
- `app/src/views/motion/structuralVisualLanguage.ts`
- `app/src/views/motion/StructuralNodeIcon.tsx`
- `app/src/views/motion/motionRenderer.css`
- `app/src/views/motion/spatialNavigation.ts`

## Exact primitive map

| Primitive | Source implementation | Integration decision |
|---|---|---|
| Backdrop/grid/vignette | `CanvasStructuralRenderer.render`, `structuralRenderer.ts` | Port direct Canvas logic. |
| Curved paths | `sampleRelationship` | Reproduce deterministically from stable placement IDs/endpoints. |
| Outer/inner rails and glow | renderer relationship passes | Port only for bounded semantic edges. |
| Glints | `CONNECTOR_GLINT_PERIOD_MS`, `connectorGlintProgress` | Reuse fixed 2,500 ms period and fixed trail; hover cannot alter either. |
| Hover interpolation | `easeConnectorHover`, `blendConnectorColor` | Reuse exponential easing and node-color inheritance. |
| Arrowheads | `drawArrow` | Use only where direction is supported; hierarchy remains quiet. |
| Node shells/symbols | `drawNodeShape`, `drawNodeSymbol` | Adapt to Outcome/Level-1/focused lower LOD. |
| Identity registry | `resolveStructuralNodeVisual` | Reuse registry pattern with ten upstream driver identities. |
| Orbital guides | `drawConcentricOrbitGuides` | Derive from persistent outcome/sector coordinates. |
| Particles | `drawDepthField`, `seededUnit` | Use a bounded deterministic viewport field, never 1,111×N. |
| Parallax | `stepSpringParallax` | Apply only to atmosphere; never move canonical nodes. |
| Labels | `layoutSpatialLabels`, `.sm-viz-node-label` | Port priority collision suppression and dark plates. |
| Camera | `interpolateCamera`, zoom/pan helpers | Retain view-only motion; targets come only from persistent coordinates. |

## Rejected transient coupling

The following must not be reused:

- `layoutEmploymentOrbit` — overwrites model coordinates.
- `layoutSpatialNodes` — moves selected/upstream/downstream nodes into a replacement layout.
- `spatialNodes → spatialModel` coordinate ownership.
- `layoutCurrent/layoutFrom/layoutTarget/layoutKey` — selection-keyed node-position interpolation.
- old two-context-factor topology.
- whole-model rich DOM label/control loops.

## Performance guard

Full shells, blur, glints, particles, multilayer rails and labels are restricted to roughly 11–12 semantic nodes/edges. The remaining resident world is rendered through inexpensive density/tether passes.

## Decision

The premium visual language is recoverable without restoring the old graph architecture. Port the drawing primitives, reject the old layout ownership, and render directly from `PersistentWorldReadModel`.
