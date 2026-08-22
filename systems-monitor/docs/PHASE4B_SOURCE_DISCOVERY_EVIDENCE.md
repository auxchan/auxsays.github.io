# Phase-4B Source Discovery Evidence

Status: **DISCOVERY PASS / PRODUCTION BLOCKED**

Review date: **2026-08-21**

Gate B: **OPEN**

## 1. Evidence register

All sources below are original official authorities. Retrieval was human/live
discovery only. No external content had instruction authority and no downloaded
matrix was retained.

| Evidence ID | Official source | Claim supported | Current information |
|---|---|---|---|
| E-4B-001 | [BEA I/O landing](https://www.bea.gov/itable/input-output) | Current product/application links, concordance, methodology | Page current 2026-05-21 |
| E-4B-002 | [BEA I/O overview](https://www.bea.gov/data/industries/input-output-accounts-data) | Annual 71 categories, 402 detailed benchmark industries, September release | Page current 2026-07-22 |
| E-4B-003 | [BEA interactive guide](https://www.bea.gov/resources/guide-interactive-industry-input-output-accounts-tables) | 15/71/138/402 levels and table concepts | Live 2026-08-21 |
| E-4B-004 | [BEA API signup/guide](https://apps.bea.gov/api/signup/) | Registered key, API dataset/metadata and limits | Guide dated 2026-04-20 |
| E-4B-005 | [BEA API terms](https://apps.bea.gov/API/_pdf/bea_api_tos.pdf) | API-use rights, attribution, no endorsement | Retrieved 2026-08-21 |
| E-4B-006 | [BEA robots](https://apps.bea.gov/robots.txt) | `/api/` allowed; other automated paths disallowed | Retrieved 2026-08-21 |
| E-4B-007 | [BEA Direct Requirements definition](https://www.bea.gov/help/faq/32) | Immediate input coefficients | Live 2026-08-21 |
| E-4B-008 | [BEA Total Requirements glossary](https://www.bea.gov/help/glossary/total-requirements-table) | Direct plus indirect requirements | Live 2026-08-21 |
| E-4B-009 | [BEA concepts/methods](https://www.bea.gov/index.php/resources/methodologies/concepts-methods-io-accounts) | Authoritative matrix derivation and semantics | Live 2026-08-21 |
| E-4B-010 | [BEA 2025 annual update](https://apps.bea.gov/scb/issues/2025/11-november/1125-nea-annual-update.htm) | Annual update released 2025-09-25; revised 2020–2024 | Published 2025-11-19 |
| E-4B-011 | [BEA citation guidance](https://www.bea.gov/help/guidelines-for-citing-bea) | Title/link/access date and vintage guidance | Live 2026-08-21 |
| E-4B-012 | [BEA concordance](https://www.bea.gov/system/files/2023-10/BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx) | Official BEA industry/commodity-to-NAICS mapping source | Current linked workbook |
| E-4B-013 | [EIA WPSR](https://www.eia.gov/petroleum/supply/weekly/) | Weekly petroleum stocks, refinery inputs/utilization, production/import evidence | Week ending 2026-08-14 at review |
| E-4B-014 | [EIA WPSR schedule](https://www.eia.gov/petroleum/supply/weekly/schedule.php) | Normal Wednesday publication and holiday timing | Live 2026-08-21 |
| E-4B-015 | [EIA natural-gas data](https://www.eia.gov/naturalgas/data.php) | Weekly working-gas storage and capacity data families | Live 2026-08-21 |
| E-4B-016 | [EIA API v2 documentation](https://www.eia.gov/opendata/documentation.php) | API hierarchy, facets, metadata, key requirement | v2.1.12, March 2026 |
| E-4B-017 | [EIA reuse](https://www.eia.gov/about/copyrights_reuse.php) | EIA-produced content generally public domain; attribution requested | Live 2026-08-21 |
| E-4B-018 | [BLS CES series](https://data.bls.gov/timeseries/CES1021100001) | Exact NAICS 211 employment endpoint, unit and adjustment | Extracted 2026-08-21 |
| E-4B-019 | [BLS current NAICS](https://www.bls.gov/ces/naics/home.htm) | CES current classification posture | 2022 NAICS |
| E-4B-020 | [Census construction spending](https://www.census.gov/construction/c30/c30index.html) | Monthly construction alternative | Current 2026-08-21 |
| E-4B-021 | [BTS TSI](https://www.bts.gov/learn-about-bts-and-our-work/statistical-methods-and-policies/tsi-frequently-asked-questions) | Monthly freight-volume alternative and coverage | Official methodology |
| E-4B-022 | [Federal Reserve G.17](https://www.federalreserve.gov/releases/g17/current/) | Monthly industrial capacity/utilization alternative | Current release 2026-07-17 |

## 2. Live application observations

BEA's interactive application was inspected on 2026-08-21. The current summary
year selector included 1997-A through 2024-A. The 2024 Use summary displayed 71
summary groups plus final-use/value-added rows in millions of dollars. Direct
and Total Requirements displayed producers' price coefficients.

Verified selector tokens: `Supply`, `UseIo`, `MakeAR`, `UseARPro`, `UIMARI`,
`CxIDRAR`, `CxIDDRAR`, `IxCMSAR`, and `IxCTRAR`.

Selected 2024 `CxIDRAR` cells inspected for topology existence:

| Commodity row | Industry column | Coefficient |
|---|---|---:|
| 211 Oil and gas extraction | 324 Petroleum and coal products | 0.5633060 |
| 211 Oil and gas extraction | 22 Utilities | 0.0283052 |
| 324 Petroleum and coal products | 484 Truck transportation | 0.0466609 |
| 22 Utilities | 484 Truck transportation | 0.0129218 |
| 486 Pipeline transportation | 211 Oil and gas extraction | 0.0225524 |
| 493 Warehousing and storage | 484 Truck transportation | 0.0128279 |

These observations prove that the proposed domain has real authoritative
topology and a common-origin case. They are not accepted relationship records.

## 3. Schema and identity findings

- Requirements matrices are rectangular commodity-row by industry-column
  structures; row and column code namespaces must remain distinct.
- Product token, economic year, aggregation, price basis, before/after
  redefinitions, unit, and classification vintage are material schema fields.
- Interactive tokens are not API integer `TableID` values.
- API table identifiers remain UNKNOWN until a registered key permits live
  `GETPARAMETERVALUESFILTERED` discovery.
- BEA current summary tables use 71 categories. Detailed benchmark tables use
  402 industries; 138 underlying-summary and 15-sector views also exist.
- The first proof chooses summary, not maximum detail, for crosswalk stability
  and human auditability.

## 4. Rights and access evidence

The API is the only approved candidate for scheduled automation. BEA API terms
allow search/display/analysis/retrieval/view use subject to attribution, access
limits, accuracy, and no implied endorsement. General interactive application
automation is disallowed by robots. Local immutable retention, public generated
relationship publication, and raw bulk redistribution remain UNKNOWN and must
fail closed until written evidence resolves them.

No credential was created, requested, exposed, or committed. No source secret
appears in this evidence package.

## 5. Release and replay findings

BEA updates I/O data annually, normally in September. The current 2024 annual
data reflect the 2025 annual update released 2025-09-25. Annual updates revise
earlier economic years. The current interactive surface alone cannot recreate
what was published at every earlier cutoff.

Future public replay therefore needs an official release time and immutable
artifact/metadata captured for that release. Future operational replay also
needs retrieval and AUXSAYS acceptance times. Today’s matrix cannot be
backdated into an earlier knowledge state.

## 6. Discovery validation matrix

| # | Check | Result | Evidence |
|---:|---|---|---|
| 1 | Every claimed BEA URL/reference is official | PASS | E-4B-001–012 use `bea.gov`/`apps.bea.gov` |
| 2 | Current access route resolves | PASS | Landing, apps, API route, catalogs resolved live |
| 3 | Current table discovery works | PASS | Live selectors and year/detail controls inspected |
| 4 | No stale hardcoded table identifiers | PASS | UI tokens verified; API integers explicitly UNKNOWN |
| 5 | Schema/header claims match official output | PASS | Commodity rows, industry columns, units inspected |
| 6 | Units identified | PASS | Millions for Use; coefficients for requirements |
| 7 | Classification level identified | PASS | 71 summary selected; 15/138/402 documented |
| 8 | Years/vintages identified | PASS | Current 2024, 2025-09-25 release; annual revisions |
| 9 | Direct semantics match BEA | PASS | E-4B-007/009 |
| 10 | Total semantics match BEA | PASS | E-4B-008/009 |
| 11 | Direct/total roles avoid double count | PASS | Direct topology; total non-recursive benchmark |
| 12 | Rights dimensions recorded | PASS | Intake rights matrix; UNKNOWN retained |
| 13 | Credential requirement recorded | PASS | Registered BEA `UserID`; no key requested |
| 14 | Update/revision behavior recorded | PASS | Annual September/current-release evidence |
| 15 | Selected domain has actual structural data | PASS | Live 211/22/324/484/486 cells |
| 16 | Proposed slice fits bounded size | PASS | 12 nodes, expected 18–26 relationships |
| 17 | Employment linkage authoritative | PASS | BLS `CES1021100001`, NAICS 211 |
| 18 | Buffer evidence status recorded | PASS | EIA stocks/storage: SUPPORTED |
| 19 | Substitution evidence status recorded | PASS | PARTIALLY_SUPPORTED; technical proof open |
| 20 | Lag evidence status recorded | PASS | PARTIALLY_SUPPORTED; no invented duration |
| 21 | Capacity evidence status recorded | PASS | EIA/Fed candidates: SUPPORTED |
| 22 | Common-cause case grounded in topology | PASS | 211 -> 324/22 -> 484 cells |
| 23 | Unsupported areas remain UNKNOWN | PASS | API IDs, rights, crosswalk/technical substitution |
| 24 | No production BEA ingestion | PASS | Documentation-only diff |
| 25 | No accepted structural edges | PASS | No relationship data/config created |
| 26 | No parser implemented | PASS | No runtime code changed |
| 27 | No scheduler implemented | PASS | No runtime/workflow changed |
| 28 | No Phase-5 work | PASS | No forecasting files/claims |
| 29 | No UI work | PASS | App/Jekyll paths unchanged |
| 30 | No public activation | PASS | Publication/deployment unchanged |
| 31 | `MASTER_SPEC.md` unchanged | PASS | SHA-256 remains `08895B471909DC600FC6AA5F373E2D6E16F457580A9BA141363ED210676397EA` |
| 32 | BINDING contracts unchanged | PASS | Five Phase-4 contracts remain BINDING 1.0.0 |
| 33 | Phase-4A outputs unchanged | PASS | Candidate identity/hash preserved |
| 34 | Gate B remains OPEN | PASS | Governance and review evidence say OPEN |
| 35 | Recurring cost remains $0 | PASS | Free official sources; no dependency/infrastructure selected |
| 36 | Nothing pushed | PASS | Local refs only |
| 37 | Nothing merged | PASS | Branch commit only |
| 38 | Nothing deployed | PASS | Workflows/site/deployment untouched |

The discovery sprint status is **PASS**. Phase-4B production is **BLOCKED** by
the explicit open decisions and unknowns; this is not a validation failure.

## 7. Negative-scope evidence

No production BEA/EIA/BLS data file, API response, parser, collector, scheduler,
SQLite row, relationship record, propagation configuration, UI file, Jekyll
file, GitHub Actions file, Patch Feed file, dependency, secret, public snapshot,
or deployment artifact was created or modified.

No official matrix export was retained. Therefore no retained external evidence
file requires a SHA-256 entry; URLs, access observations, dates, and live selector
identities are recorded above.
