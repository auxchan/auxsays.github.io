# Layoffs Live Connective-Tissue Implementation Summary

Status: **IMPLEMENTATION PARTIAL — SOURCE ACCEPTANCE AND AUTOMATED WRITEBACK AUTHORITY REMAIN OPEN**

## Implemented

- Frozen 10 × 10 Layoffs & Job Destruction hierarchy with 64 deduplicated canonical factors and zero `Renderer fixture` identities in this branch.
- Bounded, deterministic BLS/DOL, Census, BEA, Federal Reserve, and U.S. Courts source registries and parsers.
- Exact BLS/DOL candidate retrieval uses two bounded requests for 19 reviewed series and retains immutable raw evidence.
- Census and BEA credentials are environment-only and fail closed without exposing secret values.
- Candidate observations cannot display as live values or inherit acceptance from an older observation.
- Six governed semantic relationship candidates remain non-traversable and non-publishable.
- Four-hour evaluation heartbeat semantics, native-cadence due checks, last-valid retention, content-hash no-churn behavior, and immutable local-review snapshots.
- Premium persistent-world UI preserved; every factor displays an honest `CONNECTED`, `SOURCE_ENABLED_PENDING_ACCEPTANCE`, `SOURCE_IDENTIFIED`, or `BLOCKED` state.
- The previously accepted Initial Claims PDI observation is reused by canonical identity; it is not copied or re-accepted.

## Specific blockers

- New BLS/DOL observations are collector-enabled but require their first explicit source/rights/publication acceptance before values may appear.
- Census BDS/BFS/FTD retrieval requires `AUXSAYS_CENSUS_API_KEY`; MARTS/M3/MTIS exact selector bindings remain unresolved.
- BEA requires `AUXSAYS_BEA_USER_ID` plus exact table/line/vintage decisions.
- Federal Reserve G.17/H.15/SLOOS exact series/question bindings and rights acceptance remain open.
- U.S. Courts F-2 parsing is implemented, but workbook schema and rights acceptance remain open.
- Several industry concepts need accepted NAICS/crosswalk semantics; no numeric-ID lookalike join is allowed.
- Creation of an autonomous writeback workflow with repository-write credentials and automatic public Pages dispatch was not activated in this local-review sprint. A bot commit alone must not be assumed to deploy.

## Publication boundary

The immutable snapshot is `fixture` and `LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED`. Gate B remains open, Phase 5 remains locked, and Human Layoffs Live-Branch QA remains pending.
