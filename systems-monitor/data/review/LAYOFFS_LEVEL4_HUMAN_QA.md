# LAYOFFS LEVEL-4 PILOT HUMAN QA

Status: `HUMAN_LEVEL4_LAYOFFS_QA = PASS`

Pilot status: `LAYOFFS DESCRIPTIVE/TEMPORAL LEVEL-4 PILOT = CLOSED / PASSED`

Taylor approved the browser presentation on 2026-09-18 against implementation
checkpoint `e7ed0e3b7b6b668953fe32a394bec349eb8599e4`.

Loopback review URL:

`http://127.0.0.1:4173/systems-monitor/__local-review/layoffs-level4`

Start from `systems-monitor/app` with `npm run dev:layoffs-qa`.

The `FAIL_MINOR / REPAIR_REQUIRED` presentation review was addressed on
2026-09-15: the shared badge now reports 12 factors, history counts are labeled
as accepted periods, readings use "latest accepted" language, reused canonical
factors expose all Layoffs placements, rate deltas use percentage points, and
human-readable people/job counts retain their source-native unit in Deep Dive.
Taylor's final browser review confirmed that taxonomy-derived placement labels
are present and legible and that the visual layout is acceptable.

## Review boundary

This is a Human-QA package, not an approval. It exposes 203 immutable accepted
observations across 12 canonical factors and 13 exact series. Eleven factors
and 12 series have a previous compatible period; Establishment Deaths has one
accepted period and therefore no direction or delta.

All accepted rows are descriptive evidence. Materiality is `UNKNOWN`,
destination impact is `UNKNOWN`, forecast is unavailable, forecast-vintage
eligible rows remain zero, and accepted structural relationships remain zero.

## BED activation result

Taylor authority is active only for Gross Job Losses
`BDS0000000000000000110004LQ5`, Establishment Contractions
`BDS0000000000000000110005LQ5`, Establishment Closures
`BDS0000000000000000110006LQ5`, and Establishment Deaths
`BDS0000000000000000110008LQ5`. The accepted backfill contains 4, 4, 4, and 1
rows respectively, all `CURRENT_REVISED_HISTORY`. An identical second pass
added zero observations and did not rewrite history.

## DOL current-source result

The official `r539cyNational` XML remains `STALE` through 2026-08-15. The
official DOL release fallback is `CURRENT` through 2026-09-05, so overall DOL
acquisition is `SUCCESS_WITH_PRIMARY_STALE`. The latest accepted Initial Claims
are 206,000 for 2026-09-05; the release also supplies the revised prior-week
value of 207,000 for 2026-08-29. The accepted 2026-08-08 revision chain remains
209,000 -> 212,000.

## Closure boundary

This PASS closes only the Layoffs descriptive/temporal Level-4 Human-QA pilot.
Gate B remains `OPEN`; accepted structural relationships remain `0`;
forecast-vintage observations remain `0`; materiality remains unauthorized;
destination impact and forecasting remain unavailable; Phase 5 remains
`LOCKED`.
