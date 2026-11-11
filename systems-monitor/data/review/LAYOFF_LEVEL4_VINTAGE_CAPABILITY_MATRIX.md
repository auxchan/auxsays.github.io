# Layoffs Level-4 vintage capability matrix

Reviewed 2026-09-10. Authority: **research evidence only**. Activation effect: **none**.

## Result

The current 282-row candidate batch is a current-series snapshot. Its historical rows are useful as `CURRENT_REVISED_HISTORY`, but none is proven to be the value available at an earlier forecast cutoff. All 13 exact series are therefore Level 0 in the current collector and all 200 in-scope rows are forecast-vintage ineligible. Official archives can support a future Level-2 reconstruction for most series, but archive capability is not row-level evidence.

| Program | Exact series | Canonical factor | Current | Verified official ceiling | Exact reconstruction source and principal risk |
|---|---|---|---:|---:|---|
| JOLTS | `JTS000000000000000LDL` | Layoffs & Discharges | L0 | L2 | Archived JOLTS total-nonfarm level tables; preliminary, prior-month, annual, and definition vintages must remain distinct. |
| JOLTS | `JTS000000000000000LDR` | Layoffs & Discharges | L0 | L2 | Archived JOLTS rate tables; rate must never be substituted for the level. |
| JOLTS | `JTS000000000000000JOR` | Job Openings Rate | L0 | L2 | Archived JOLTS rate tables; openings are a last-business-day stock, not a monthly flow. |
| JOLTS | `JTS000000000000000HIR` | Hires Rate | L0 | L2 | Archived JOLTS rate tables; preserve published precision and revisions. |
| CPS | `LNS13026638` | Permanent Job Losers | L0 | L2 | Archived Employment Situation Table A-11; annual seasonal re-estimation and population-control breaks require explicit versions. |
| CPS | `LNS13023653` | Temporary Layoffs | L0 | L2 | Archived Employment Situation Table A-11; keep temporary layoffs distinct from permanent losers. |
| CES | `CES0500000002` | Average Weekly Hours | L0 | L2 | Archived Employment Situation Table B-2. CES machine-readable vintage files do not cover hours/earnings. |
| CES | `CES6056132001` | Temporary Help Employment | L0 | L2 | Archived Employment Situation Table B-1. CES machine-readable vintage coverage stops above this detailed series. |
| BED | `BDS0000000000000000110004LQ5` | Gross Job Losses | L0 | L2 | Archived BED Table 1; annual revisions affect recent NSA quarters and five years of SA history. |
| BED | `BDS0000000000000000110005LQ5` | Establishment Contractions | L0 | L2 | Archived BED component tables; retain component identity separately from aggregate losses. |
| BED | `BDS0000000000000000110006LQ5` | Establishment Closures | L0 | L2 | Archived BED component tables; closings and confirmed deaths are different concepts. |
| BED | `BDS0000000000000000110008LQ5` | Establishment Deaths | L0 | L2 partial | Archived BED Table 8; three-quarter confirmation lag and in-place archive reissues can make displaced bytes unrecoverable. |
| DOL UI | `DOL-UI-SA-INITIAL` | Initial Claims | L0 | L2 | Official weekly archives; advance, revised, annual-SA, holiday, and no-release states must be explicit. |

No exact series has verified Level-3 machine-readable vintage support.

## Capability definitions

- **L0:** current published snapshot only; historical release identity is not recoverable from the collected payload.
- **L1:** official publication date is known but the exact value-as-published artifact is unavailable.
- **L2:** an official archived release artifact can support exact row reconstruction after parsing, hashing, and timestamp validation.
- **L3:** an official machine-readable vintage dataset supports reproducible point-in-time reconstruction for the exact series.

## Required reconstruction record

Every `ORIGINAL_RELEASE_VALUE` or `VINTAGE_RECONSTRUCTED` row must retain the official archived artifact, SHA-256, release identity and header timestamp, exact table/row selector, published precision, revision state, valid time, public time, retrieval time, acceptance time, method version, and any supersession link. America/New_York release times must be converted with daylight-saving rules.

Forbidden substitutes include the reference period, generic cadence arithmetic, page-modified or crawl time, retrieval time labeled as an official time, and a current API value substituted for an archived rounded value. Unknown publication time remains unknown or a conservative retrieval bound.

## Official evidence

- [BLS Public Data API documentation](https://www.bls.gov/developers/api_signature_v2.htm)
- [CES vintage-data information](https://www.bls.gov/web/empsit/cesvininfo.htm)
- [CES vintage data](https://www.bls.gov/web/empsit/cesvindata.htm)
- [Archived Employment Situation releases](https://www.bls.gov/bls/news-release/empsit.htm)
- [Archived JOLTS releases](https://www.bls.gov/bls/news-release/jolts.htm)
- [Archived BED releases](https://www.bls.gov/bls/news-release/cewbd.htm)
- [DOL UI weekly claims archive](https://oui.doleta.gov/unemploy/archive.asp)

The machine-readable source of truth is `data/config/layoffs/vintage_capability_matrix.json`.
