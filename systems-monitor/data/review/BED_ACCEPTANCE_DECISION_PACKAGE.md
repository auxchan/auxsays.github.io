# BED acceptance decision package

Prepared 2026-09-14 for Taylor. Status: **pending decision**. Authority and
activation effect: **none**.

## Deterministic no-write result

The existing 282-row candidate batch was replayed through the bounded
acceptance simulator without an output path. The simulation wrote no data and
reported zero validation failures. All four exact BED series passed publisher,
program, identity, factor, unit, geography, adjustment, cadence, parser,
methodology, revision, evidence, and central-rights constraints.

| Exact BED series | Canonical factor | Result | Eligible descriptive rows | Periods | Forecast vintage |
|---|---|---|---:|---|---|
| `BDS0000000000000000110004LQ5` | Gross Job Losses | `READY_FOR_TAYLOR_ACCEPTANCE` | 4 | 2025-Q1..2025-Q4 | Not granted |
| `BDS0000000000000000110005LQ5` | Establishment Contractions | `READY_FOR_TAYLOR_ACCEPTANCE` | 4 | 2025-Q1..2025-Q4 | Not granted |
| `BDS0000000000000000110006LQ5` | Establishment Closures | `READY_FOR_TAYLOR_ACCEPTANCE` | 4 | 2025-Q1..2025-Q4 | Not granted |
| `BDS0000000000000000110008LQ5` | Establishment Deaths | `READY_FOR_TAYLOR_ACCEPTANCE` | 1 | 2025-Q1 | Not granted; archive ceiling partial |

Total eligible descriptive rows: **13**. Accepted rows: **0**.

## Exact audit posture

- Publisher/program: U.S. Bureau of Labor Statistics, Business Employment
  Dynamics.
- Geography: United States.
- Unit: thousands of jobs.
- Cadence: quarterly.
- Seasonal adjustment: seasonally adjusted.
- Collector/parser: bounded BLS Public Data API v2 request using exact `BD`
  series identifiers; `layoffs-bls-json-v1`.
- Methodology: BLS BED program definitions and current methodology.
- Revision behavior: QCEW corrections plus annual concurrent seasonal-adjustment
  revisions; Establishment Deaths also has a three-quarter confirmation lag.
- Evidence: exact BLS series evidence URLs and content-addressed raw API artifact.
- Rights: collection, raw/derived retention, transformation, internal analytical
  use, public display/redistribution, export, and commercial use are allowed with
  attribution. Model-feature and model-training use remain `UNKNOWN`.
- Identity boundary: contractions, closures, deaths, and gross losses remain
  distinct. Deaths are not interchangeable with closures.

## Four separate decisions

A. Routine current/future acceptance: **eligible for Taylor consideration** for
the four exact profiles only. Any identity or metadata mismatch must fail closed.

B. `CURRENT_REVISED_HISTORY` descriptive backfill: **eligible for Taylor
consideration** for the 13 rows listed above.

C. Forecast-vintage eligibility: **not granted**. No row has exact archived
release-artifact proof; current eligible count remains zero.

D. Model-feature/model-training eligibility: **not granted** while the central
rights decision remains `UNKNOWN` for those operations.

Taylor must approve, modify, or reject A and B separately. C and D must remain
closed absent their independent evidence and authority. This package does not
self-grant acceptance.
