# Persistent World 2.5D Performance — Before / After

Status: TECHNICAL PASS / HUMAN QA PENDING  
Date: 2026-08-29  
Target: local Chromium preview, Canvas2D, DPR capped at 2

## Budgets

- Canvas draw p95: ≤4 ms in overview, Level-1, Level-2, deeper, and full-world modes.
- Displayed-frame p95 during interaction: ≤20 ms.
- First draw p95: ≤350 ms.
- Hover hit test p95: ≤1 ms.
- Wheel/pan handler p95: ≤4 ms.
- Worst interaction task: <50 ms.
- No continuous expensive rendering after the scene settles.

## Recorded baseline

The pre-sprint premium renderer review recorded:

| Mode | Before Canvas p95 |
|---|---:|
| Overview | 2.5 ms |
| Level-1 focus | 3.0 ms |
| Full world | 2.5 ms |
| Ten Level-1 layouts | 2.5–3.9 ms |
| Representative deeper layouts | 2.0–3.1 ms |

Other recorded baseline values: first draw 256.8 ms; camera settle about 1.15 s; model initialization 15 ms; Node-only retained-model heap estimate about 1.04 MB. Browser/GPU memory and GC attribution were not proven by the pre-sprint harness.

## After integration

Fresh-load browser samples after the final optimization:

| Mode | Mean draw | p95 draw | First draw | Camera settle |
|---|---:|---:|---:|---:|
| Overview | 2.42 ms | 3.70 ms | 252.4 ms | bounded transition |
| Level-1 focus (Labor Supply) | 1.94 ms | 2.90 ms | 251.7 ms | 847.4 ms |
| Level-2 focus (Real Wage Purchasing Power) | 1.35 ms | 1.90 ms | 111.0 ms | 826.3 ms |
| Deeper focus | 1.10 ms | 1.50 ms | 278.2 ms | 821.7 ms |
| Full-world LOD | 2.55 ms | 3.90 ms | route transition sample | bounded transition |

The overview sample had one noisy run at 5.1 ms p95 and a repeat at 3.7 ms; the latter is the reported fresh representative sample. Human-perceived smoothness and repeated target switching were also inspected in the browser.

Active accepted temporal connector signaling could not be benchmarked because the current factual graph correctly reports `0 governed connector signals`; no synthetic signal was invented to satisfy the benchmark row.

## Performance changes

- Camera trigonometry is computed once per projection batch.
- A shared per-frame projection map eliminates repeated endpoint projection.
- Nodes use three depth buckets instead of a full 1,111-item depth sort.
- Rich drawing remains bounded to the semantic neighborhood.
- DPR remains capped at 2.
- Hit testing remains bounded to the current semantic set.
- Decorative particles remain fixed at 54 across three static strata.
- Per-node radial gradients were rejected after profiling; dimensionality uses cheaper layered shells and highlights.
- The normal-motion rAF loop now stops at `IDLE` after camera/hover/Trace activity settles and restarts only on invalidation.

## Rapid retarget result

Fifty alternating Level-1 hash targets completed with:

- final selected target correct;
- transition progress `1.000`;
- phase `SETTLED`;
- render loop `IDLE`;
- topology `fnv1a32:88684cdb`;
- presentation `fnv1a32:e163ce8a`;

## Human-review correction

The first integration was visually rejected because its focus angles were too restrained and global ambient hierarchy strands remained visible in deep focus. The corrected focus sample uses a 39-degree pitch, settles in 824.6 ms, returns the render loop to `IDLE`, and measured 1.2 ms Canvas p95 on the reported Vacancy Duration route. Off-context ambient hierarchy strands are now excluded from focus rendering.
- final sampled Canvas p95 1.8 ms.

## Limitations

The browser harness reports Canvas draw work but does not provide trustworthy browser/GPU heap, GC attribution, or end-to-end INP for this local fixture. Those items remain unproven rather than silently passed.
