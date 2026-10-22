# Premium Persistent-World Benchmark

Date: 2026-08-26  
Route: `http://127.0.0.1:4174/systems-monitor/#persistent-world`  
World: 1,111 placements / 3,110 relationships  
Fingerprint: `fnv1a32:d8ccde70`

## Before / after

| Mode | Baseline p95 draw | Premium p95 draw | Budget | Result |
|---|---:|---:|---:|---|
| overview | 1.4 ms | 2.5 ms | ≤4.0 ms | PASS |
| Level-1 focus | 0.7 ms | 3.0 ms | ≤4.0 ms | PASS |
| full-world density | 1.5 ms | 2.5 ms | ≤4.0 ms | PASS |

Observed premium first draw was 256.8 ms against a 350 ms local p95 gate. Overview exposed 11 semantic labels/nodes. Focus exposed 12 semantic nodes. Full-world kept all 1,111 placements and all 3,110 relationships resident.

The premium cost is intentionally bounded:

- multilayer glow/rails and glints are limited to semantic tethers;
- rich shells/icons/labels are limited to the semantic neighborhood;
- all other nodes/edges use inexpensive Canvas density passes;
- particle count is fixed at 54, independent of resident node count;
- Canvas DPR remains capped at 2;
- reduced motion stops continuous animation and uses explicit invalidation for pan/zoom/hover.

The previous full-detail stress boundary remains 319.7 ms p95 and is not used by this implementation.

Browser/GPU memory remains unproven; no memory PASS is claimed. The retained immutable model baseline is approximately 1.04 MB heap/model under the supplementary Node measurement.
