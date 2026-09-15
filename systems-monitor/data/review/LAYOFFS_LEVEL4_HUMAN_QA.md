# LAYOFFS LEVEL-4 PILOT HUMAN QA

Status: `HUMAN_LEVEL4_LAYOFFS_QA = PENDING`

Loopback review URL:

`http://127.0.0.1:4173/systems-monitor/__local-review/layoffs-level4`

Start from `systems-monitor/app` with `npm run dev:layoffs-qa`.

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
acquisition is `SUCCESS_WITH_PRIMARY_STALE`. Accepted current Initial Claims
are 206,000 for 2026-09-05; the release also supplies the revised prior-week
value of 207,000 for 2026-08-29. The accepted 2026-08-08 revision chain remains
209,000 -> 212,000.

## Taylor checklist

- Verify each canonical name, icon, exact series ID, and hierarchy placement.
- Verify current value, represented period, previous compatible period, arrow,
  and arithmetic delta where comparison exists.
- Confirm Establishment Deaths says comparison unavailable rather than
  manufacturing a direction.
- Confirm Initial Claims presents the current official fallback while retaining
  the stale-primary-XML warning.
- Verify revisions, evidence links, provenance, publication basis, methodology,
  and accepted-history status remain understandable under progressive detail.
- Confirm node titles remain identity-only and the surface makes no materiality,
  destination-impact, causal, structural, or forecasting assertion.
- Record Taylor's Human-QA outcome separately; this artifact must remain
  `PENDING` until that review occurs.
