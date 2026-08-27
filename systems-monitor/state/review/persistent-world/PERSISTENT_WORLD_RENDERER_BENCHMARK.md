# Persistent World Renderer Benchmark

Decision: **KEEP CANVAS 2D WITH STRICT LOD**
Dependency change: **NONE**

## Baseline measurements

Chrome 151 headless/software mode, 1440×900, DPR 1, deterministic 1,111-node /
3,000-edge fixture:

| Mode | Mean | p95 | Result |
|---|---:|---:|---|
| Every node/edge in full detail | 304.0 ms | 319.7 ms | FAIL (~3.3 FPS) |
| Full model resident; 11 nodes/10 edges detailed | 10.0 ms | 14.7 ms | PASS |
| Same LOD, reduced motion | 8.5 ms | 9.9 ms | PASS |

The failure is detailed per-frame work, not immutable model residency. Existing
hot spots include 65 curve samples per detailed edge, per-frame maps/BFS/path
sets, eight particles per model node, shadow work, and one React control per
rendered node.

## Adopted LOD

- Overview: outcome + 10 Level-1 semantic controls; lower levels are cheap
  density marks.
- Focus: selected context plus exactly ten children receive labels, controls,
  and animated hierarchy emphasis.
- Full-world: explicit density view; synthetic cross-links are hairlines, not
  individually operable claims.
- Reduced motion: camera snaps and connector glints stop.

Graphology/Sigma 3 was not installed or benchmarked because the optimized
Canvas path satisfies the bounded focused budget. Reconsider only if measured
post-implementation overview/focus p95 materially misses the recorded gates.

## Post-implementation browser instrumentation

Codex in-app Chromium, live local Vite preview, current viewport, 30 measured
draws per mode. All 1,111 placements and 3,110 relationships remained resident:

| Mode | Semantic nodes | Mean | Median | p95 | Result |
|---|---:|---:|---:|---:|---|
| Overview LOD | 11 | 0.787 ms | 0.800 ms | 1.400 ms | PASS |
| Focus LOD | 12 | 0.450 ms | 0.500 ms | 0.700 ms | PASS |
| Full-world density LOD | 12 | 1.027 ms | 1.100 ms | 1.500 ms | PASS |

These are Canvas draw-work durations, not end-to-end display-frame intervals.
The surface publishes the measured mode, mean, median, and p95 as local DOM
diagnostic attributes after 30 frames; they are not part of the PDI.

One clean local reload measured deterministic model generation at 15.0 ms,
component-mount-to-first-draw at 242.3 ms, focus-camera settle at about 1.15 s,
wheel handling at 1.0 ms, and semantic hover hit-testing at 0.1 ms. Wheel input
inside the graph changed graph zoom while page scroll remained zero. The local
browser's coarse `performance.memory` counter reported a zero-byte delta, so no
memory-pass claim is made from that unreliable counter; model residency is
instead locked by the 1,111-placement/3,110-relationship assertions.
