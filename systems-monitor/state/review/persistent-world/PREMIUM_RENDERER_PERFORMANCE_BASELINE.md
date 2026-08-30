# Premium Renderer Performance / Accessibility Baseline

Status: **PASS WITH STRICT LOD GUARDS**  
Baseline: commit `66677cbea1bd129c2738809fdaa8994029a3ab29`  
Fingerprint: `fnv1a32:d8ccde70`

## Resident world

| Item | Count |
|---|---:|
| placements | 1,111 |
| Level 1 / Level 2 / Level 3 | 10 / 100 / 1,000 |
| hierarchy / fixture influence | 1,110 / 2,000 |
| accepted factual relationships | 0 |

## Measured baseline

| Mode | Semantic nodes | Mean draw | p95 draw |
|---|---:|---:|---:|
| overview | 11 | 0.787 ms | 1.4 ms |
| focus | 12 | 0.450 ms | 0.7 ms |
| full-world density | bounded | 1.027 ms | 1.5 ms |

Other observations: model initialization 15.0 ms, first draw 242.3 ms, camera settle about 1.15 s, wheel handler 1.0 ms, semantic hover hit test 0.1 ms. Retained-model Node measurement was about 1.04 MB heap per model; this is not a browser/GPU memory PASS.

An earlier full-detail stress prototype (1,111 rich nodes / ~3,000 rich edges) measured 304.0 ms mean and 319.7 ms p95 and therefore failed.

## Integration budgets

- overview/focus/full-world Canvas draw p95: **≤4 ms**;
- pan/zoom/camera displayed-frame p95: ≤20 ms;
- interaction tasks: <50 ms, representative INP ≤200 ms;
- model generation p95: ≤25 ms;
- first-draw median/p95: ≤275/350 ms;
- hover hit-test p95: ≤1 ms;
- wheel/pan handler p95: ≤4 ms;
- one immutable model, one full-size Canvas, no per-frame large buffers;
- premium shells/rails/glints/labels remain bounded to the semantic neighborhood.

## Accessibility guard

Canvas is not the information authority. Keep native DOM breadcrumbs, inspector, exact-ten buttons, fixture warnings, factual link, selection status and unavailable states. Meaning cannot exist only in color, glow, motion or position.

Reduced motion must stop glints, ambient drift and parallax but retain fully functional focus, Reset, zoom and pan through on-demand redraw. Touch must not remain permanently trapped; normal embedded mode permits page pan, while fullscreen may capture the graph.
