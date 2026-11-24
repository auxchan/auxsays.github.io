# Layoffs forecast-leakage adversarial QA

Reviewed 2026-09-10. This is a fail-closed inspection of the candidate and replay boundaries, not permission to forecast.

## Current verdict

**PASS at the governance boundary; zero rows are forecast-vintage eligible.** The current batch is explicitly `CURRENT_REVISED_HISTORY`, and forecast-as-of replay excludes any row without an official publication time, an exact archived-vintage evidence identity, and an eligible vintage class. No production forecasting was started.

| Attack | Result | Enforced boundary |
|---|---|---|
| Current-revised values presented as originally known | PASS | Current batch class is `CURRENT_REVISED_HISTORY`; forecast use forbidden. |
| Reference time substituted for publication time | PASS | Four-time model remains separate; no cadence-derived public times. |
| Retrieval time relabeled as official publication time | PASS | `conservative_retrieval_bound` is descriptive only. |
| Future revisions leaked backward | PASS | Immutable revision rows and supersession links; no overwrite. |
| Current API value substituted for archived release precision | PASS | Exact archive artifact, selector, value, and precision required. |
| JOLTS level/rate or stock/flow mixed | PASS | Exact series, unit, and validator-profile match required. |
| CPS seasonal or population-control break hidden | PASS | Method breaks force manual review. |
| CES detailed series assumed covered by unrelated vintage files | PASS | Exact-series vintage evidence required; both CES rows remain ineligible. |
| BED closing/death or confirmation lag conflated | PASS | Exact series identity and separate revision semantics required. |
| DOL advance value overwritten by a later revision | PASS in model; migration required | Existing accepted 209,000 seed must precede the 212,000 revision. |
| DOL stale XML treated as current | HELD | All 33 DOL rows remain contingent on release identity and freshness. |
| BED rows accepted despite absent central rights | BLOCKED | All 13 BED rows remain blocked. |
| Materiality inferred from arbitrary threshold | PASS | Materiality authority remains `NONE`; result remains `UNKNOWN`. |
| Direction converted to destination impact | PASS | Impact remains `UNKNOWN` without accepted relationship/context authority. |
| Archived-program capability treated as row eligibility | PASS | Capability ceiling and observation eligibility are separate fields. |

## Required future backtest labels

- `REAL_TIME_VINTAGE_BACKTEST`: only information provably public at each forecast cutoff.
- `REVISED_DATA_RESEARCH_BACKTEST`: later/current revised history, clearly labeled and never represented as real-time predictive performance.

Before either path is enabled, add fixture tests using an intentionally revised value, a post-cutoff publication, a DST release boundary, a missing release, a definition break, and an artifact-hash mismatch. The current sprint deliberately stops before that activation boundary.
