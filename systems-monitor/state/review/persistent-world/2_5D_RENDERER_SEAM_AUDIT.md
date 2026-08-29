# Persistent World 2.5D Renderer Seam Audit

Status: IMPLEMENTED FOR HUMAN QA  
Date: 2026-08-29  
Branch: `codex/systems-monitor-persistent-world`

## Decision

The current Canvas renderer remains the correct architecture. No evidence justified a WebGL, Three.js, Pixi, force-layout, or coordinate-authority migration.

The narrow seam is:

```text
immutable canonical x/y placements
        +
deterministic presentation-only z
        +
restrained perspective camera
        ↓
one projected-placement representation
        ↓
connectors / nodes / labels / hit testing
```

Canonical graph membership, parentage, x/y coordinates, relationship records, and navigation identity remain unchanged.

## Authority separation

- Economic topology: `persistentWorldModel.ts`.
- Presentation depth/projection: `persistentWorldSpatialLayout.ts`.
- Camera easing, labels, glyphs, LOD, and connector primitives: `persistentWorldVisuals.ts`.
- Active Canvas controller/render loop: `PremiumPersistentWorldSurface.tsx`.
- URL selection, inspector, breadcrumbs, Reset, fullscreen, Trace, and structured keyboard/touch navigation: `PersistentWorldShell.tsx`.

Depth expresses visual position only. It does not express importance, confidence, severity, freshness, acceptance, weight, or causal strength.

## Deterministic depth

Presentation layout version: `employment-spatial-presentation-1.0.0`  
Projection version: `restrained-perspective-1.0.0`  
Presentation fingerprint: `fnv1a32:68569dc2`

Stable Z is derived from hierarchy depth, sector phase, sibling order, parent Z, and an FNV-1a hash of stable placement identity. Values are rounded to three decimals before fingerprinting. The same model produces the same frozen Z map on every load; selection never changes it.

## Projection and camera

The camera extends the accepted 2D pose with Z, pitch, and yaw. Roll remains zero. Perspective is clamped to `0.82–1.20`; pitch is restrained to approximately `-2°–5°`, and yaw to `±6°`.

Focus transitions carry the current velocity into a bounded Hermite retarget, end at zero velocity, retain the accepted shallow lateral arc and mid-flight pullback, and start from the last rendered pose during rapid path switching. Reduced motion snaps to the same final spatial pose and removes travel/parallax/glints.

## Drawing order and semantics

The renderer uses one frame projection cache. Highlighted connector rails are ordered by mean projected depth; nodes are bucketed far → mid → near so foreground nodes occlude veins. Labels and evidence badges remain last. Depth changes scale, opacity, weight, and lighting only; sector/evidence/temporal semantics retain their existing color channels.

Near nodes receive a restrained extrusion disk, face, rim, directional highlight, halo, and selection ring. Far canonical placements collapse to constellation/dot treatment through existing semantic LOD; no aggregate graph identity is created.

## Atmosphere

The existing 54 deterministic particles are split into three static parallax strata. Graphite/navy haze, the depth-faded grid, sparse dust, and vignette remain subordinate to the economic graph. Particles do not drift or simulate physics.

## Invariants

- Canonical topology fingerprint before: `fnv1a32:88684cdb`.
- Canonical topology fingerprint after: `fnv1a32:88684cdb`.
- Resident placements: 1,111.
- Resident relationships: 3,110.
- Accepted/factual structural relationships: 0.
- Glint period: 2,500 ms.
- Glint trail: 0.085.
- Identity labels remain semantic names only; factual values remain separate.
- Double-click parent and structured navigation retain their existing semantics.

## Known boundary

This sprint changes renderer presentation only. It does not implement Level-4 taxonomy, accept relationships, add observations, change collectors, create forecasts, activate the public site, or alter Gate B.
