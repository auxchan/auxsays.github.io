# Phase-4B Human QA

Status: **HUMAN_PHASE4B_QA = PENDING**  
Reason: **Live BEA metadata and matrix acceptance are blocked by missing external credential.**

## Ready to inspect now

| Check | Expected | Current |
|---|---|---|
| Downstream employment | BLS `CES4348400001`, NAICS 484 | `1465.1` thousand, July 2026, SA, preliminary |
| Exact BLS evidence | Human series page, not generic API | `https://data.bls.gov/timeseries/CES4348400001` |
| Inventory | EIA commercial crude excluding SPR | `428.815` million barrels, week ending Aug. 14, 2026 |
| Capacity | EIA refinery utilization | `97.2%`, week ending Aug. 14, 2026 |
| Coverage | Bounded energy/refining/utilities/transport | Explicit; not whole economy |
| Forecast boundary | No `FCST`, `SCEN`, jobs gained/lost | PASS |

## Must be available before Taylor can pass QA

1. Exact live BEA `CxIDRAR` and `IxCTRAR` TableIDs and 2024 source identity.
2. Twelve to forty automatically accepted direct-requirement relationships.
3. Source coefficient and source-cell evidence for each relationship.
4. Direct topology kept separate from the non-recursive total benchmark.
5. Factual accepted paths converging on 484, including common-cause handling.
6. Current ordinal structural exposure CALC, visibly separate from the BLS OBS.
7. Complete deterministic derivation and replay proof.
8. Honest buffer/capacity/lag/substitution treatment with no fake precision.

## Taylor decision

Do not mark PASS yet. After the bounded live acceptance evidence is added,
Taylor may record `HUMAN_PHASE4B_QA = PASS` or return a consolidated correction.
Gate B remains OPEN and Phase 5 remains LOCKED.
