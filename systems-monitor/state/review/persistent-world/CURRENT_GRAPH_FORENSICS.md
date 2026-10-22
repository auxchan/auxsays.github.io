# Current Graph Forensics

Status: **READ-ONLY ROOT-CAUSE RECORD**

## Current path

```text
factual snapshot
→ attachLaborMarketHierarchy
→ LaborMarketShell.createStructuralModel
→ one outcome + ten measurement spokes
→ CanvasStructuralSurface
→ layoutEmploymentOrbit overwrites coordinates
→ resolveSpatialViewport recomputes visible subset
→ renderer keys layout/camera animation to selection
```

## Root cause

- `laborMarketReadModel.ts` owns stable factual identities and exact-ten
  placements, but `LaborMarketShell.tsx` converts the ten measurements into one
  center-and-spoke renderer model.
- `spatialNavigation.ts:layoutEmploymentOrbit()` overwrites every supplied
  coordinate into an equal-radius ring.
- `resolveSpatialViewport()` derives a selection-dependent node/edge subset.
- `CanvasStructuralSurface.tsx` stores hover, pan, zoom, and selection-adjacent
  presentation state locally.
- `structuralRenderer.ts` keys layout interpolation partly to selected IDs and
  visible edges rather than an immutable world/layout identity.

The small graph does not always replace its source array, but filtering,
re-centering, and selection-keyed layout animation make it behave like a new
star on each drill.

## Minimum safe seam used

```text
PersistentWorldReadModel
  canonical factors
  placements
  relationships
  deterministic coordinates
  graph snapshot + fingerprint
        ↓ immutable
PersistentWorldSurface
  camera + LOD + emphasis + inspector only
```

The existing factual shell remains unchanged. The new model is routed only by
the development hash `#persistent-world` and is not loaded from the factual
candidate.
