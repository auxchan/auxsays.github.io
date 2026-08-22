# Phase-4B Structural Source Discovery

Status: **DISCOVERY COMPLETE / PRODUCTION IMPLEMENTATION BLOCKED**

Evidence date: **2026-08-21**

Authority: Taylor-authorized Phase-4B structural source discovery/intake only

Gate B: **OPEN**

This document records live official-source discovery. It is review evidence,
not a contract, source configuration, parser specification, accepted
relationship set, or authorization to ingest data.

## 1. Result

The approved first Phase-4B structural domain is a bounded **energy supply,
refining, utilities, and transport** slice at BEA's current annual summary
level. The future topology source should be the after-redefinitions **Direct
Requirements** matrix. The corresponding **Total Requirements,
Industry-by-Commodity** matrix should be used only as a non-recursive benchmark
and validation control. Supply, Use, Import, Market Share, and Domestic Direct
products have distinct supporting roles; they are not interchangeable.

This sprint passed as a discovery exercise. Production ingestion remains
blocked until Taylor approves the proposed slice and access posture, a BEA API
credential is provisioned outside the repository, live API metadata resolves
the current integer `TableID` values, the unresolved rights dimensions are
closed or deliberately denied, and the BEA-to-BLS crosswalk is validated.

No BEA file was retained, no parser or scheduler was implemented, no accepted
structural relationship was generated, and no Phase-4A runtime, UI,
publication, deployment, or BINDING contract changed.

## 2. Official access architecture verified live

| Route | Verified current behavior | Intended role | Production posture |
|---|---|---|---|
| [Input-Output Accounts](https://www.bea.gov/itable/input-output) | Canonical BEA landing page linking current, after-redefinitions, underlying, historical, classification, and methodology resources | Human discovery and evidence | ALLOW for human use |
| [Input-Output Accounts overview](https://www.bea.gov/data/industries/input-output-accounts-data) | Annual 71-category data; detailed benchmark data roughly every five years at 402 industries; release each September | Product/cadence authority | ALLOW |
| [Interactive I/O application](https://apps.bea.gov/iTable/?Categories=Core&isURI=1&reqid=1602&step=2) | Current selectors, years, units, headers, and table tokens resolve | Human discovery and export fallback | No automated scraping |
| After Redefinitions interactive application | Live selectors expose Use, Make, Import, Direct, Domestic Direct, and Market Share products | Human discovery | No automated scraping |
| [BEA Data API](https://apps.bea.gov/api/data) | `InputOutput` dataset; JSON/XML; metadata methods expose datasets, parameters, and parameter values | Required future machine route | Registered 36-character `UserID` required |
| Official ZIP exports | Current product-family ZIP links resolve; reviewed via bounded metadata/HEAD only | Human/manual contingency and schema comparison | Automated use not approved in this sprint |
| [Concepts and Methods](https://www.bea.gov/index.php/resources/methodologies/concepts-methods-io-accounts) | Current official semantic authority | Methodology | ALLOW |
| [Industry/commodity concordance](https://www.bea.gov/system/files/2023-10/BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx) | Current linked BEA-to-NAICS concordance | Future versioned crosswalk input | Inspect safely; no macros/formulas executed |

The API user guide reviewed on 2026-08-21 documents a 100-requests-per-minute,
100-MB-per-minute, and 30-errors-per-minute limit, with `Retry-After` behavior.
Current integer API `TableID` values are deliberately **UNKNOWN** because live
parameter metadata requires a credential and no key was requested or guessed.
Interactive selector tokens were verified live and are recorded separately in
the intake candidate; they must not be substituted for API `TableID` values.

## 3. Current BEA product families

The current annual summary application exposes 71 industry/commodity groups
and 2024 as the newest economic year. The UI offers annual selections from 1997
through 2024. BEA's guide also documents 15-sector, 71-summary,
138-underlying-summary, and 402-detail levels; detailed data generally occur in
benchmark years. Maximum detail is not selected for the first proof.

| Product | Live identity/token | Semantics | Future AUXSAYS role | First slice |
|---|---|---|---|---|
| Supply | `Supply` | Domestic and imported commodity supply by industry/source | `STRUCTURAL_QUANTITY` and validation | Supporting |
| Use, before redefinitions | `UseIo` | Commodity use by industries and final users | `STRUCTURAL_QUANTITY` | Supporting |
| Make, after redefinitions | `MakeAR` | Commodity production by industries after redefinitions | `STRUCTURAL_QUANTITY` | Supporting |
| Use, after redefinitions, producers' prices | `UseARPro` | Industry commodity use after redefinitions | `STRUCTURAL_QUANTITY` and audit | Supporting |
| Import matrix, after redefinitions | `UIMARI` | Imported commodity use | `ALLOCATION` / import-buffer evidence | Supporting |
| Direct requirements, after redefinitions | `CxIDRAR` | Immediate commodity inputs per dollar of industry output | `GRAPH_EDGE_SOURCE` | **Required** |
| Domestic direct requirements, after redefinitions | `CxIDDRAR` | Immediate domestic commodity inputs per dollar of industry output | `VALIDATION` and domestic/import decomposition | Supporting |
| Market share, after redefinitions | `IxCMSAR` | Industry production shares for commodities | `MARKET_SHARE`; never physical substitution proof | Supporting |
| Total requirements, industry-by-commodity | `IxCTRAR` | Direct plus indirect industry production per commodity/final-use demand | `NON_RECURSIVE_BENCHMARK` | **Required control** |

Current summary Use output is in millions of dollars. Current Direct and Total
Requirements output is in producers' price coefficients. Product choice,
economic year, price basis, redefinition status, aggregation, and classification
vintage must all be part of future schema identity.

## 4. Direct versus total requirements

BEA defines direct requirements as the inputs purchased directly by an industry
per dollar of output. Total requirements measure the direct and indirect
production required throughout the economy. This confirms the BINDING contract
assumption; no conflict was found.

Future rule:

1. Generate candidate topology only from `CxIDRAR` direct coefficients.
2. Preserve row commodity, column industry, coefficient, year, aggregation,
   price basis, and redefinition status.
3. Validate generated structure against source Use/Make/Supply evidence.
4. Compare bounded aggregate results to `IxCTRAR` only as a non-recursive
   benchmark.
5. Never add overlapping total-requirements contributions to recursively
   traversed direct paths.

## 5. Domain comparison

Scores are 1 (weak) to 5 (strong) and reflect current official-source
availability, not economic importance.

| Criterion | Construction | Energy | Freight/transport | Manufacturing |
|---|---:|---:|---:|---:|
| BEA structural clarity | 4 | 5 | 4 | 4 |
| Compact graph | 4 | 5 | 4 | 2 |
| Direct-requirements availability | 5 | 5 | 5 | 5 |
| Current-state evidence | 4 | 5 | 4 | 5 |
| Employment linkage | 5 | 5 | 4 | 5 |
| Lag evidence | 4 | 4 | 4 | 3 |
| Buffer/inventory evidence | 2 | 5 | 2 | 4 |
| Substitution evidence | 2 | 3 | 3 | 3 |
| Capacity evidence | 2 | 5 | 3 | 5 |
| Common-cause opportunity | 3 | 5 | 4 | 5 |
| Crosswalk quality | 5 | 5 | 4 | 3 |
| Human auditability | 4 | 5 | 4 | 3 |
| Implementation simplicity | 4 | 4 | 3 | 2 |
| $0 recurring source cost | 5 | 5 | 5 | 5 |
| **Total / 70** | **53** | **66** | **52** | **54** |

Construction has excellent Census current-state and BLS employment evidence
but weak first-proof inventory/substitution behavior. Freight has an official
BTS activity index but fragmented modal capacity/buffer evidence. Broad
manufacturing has strong Census/Federal Reserve current data but is too large
and crosswalk-heavy for the first auditable proof. Energy wins because official
BEA topology, EIA stocks/storage/utilization, and BLS NAICS 211 employment align
within a small, recognizable network.

## 6. Recommended bounded proof

Proposed size: **12 structural/current-state nodes and 18–26 direct structural
relationships** after future validation. This is within the 8–20 / 12–40 design
bound and is not an economic constant.

Proposed nodes:

| Node | Classification | Status |
|---|---|---|
| Crude-oil stocks | EIA petroleum weekly | PROPOSED current buffer OBS |
| Refinery utilization | EIA petroleum weekly | PROPOSED current capacity OBS |
| Natural-gas storage | EIA natural gas weekly | PROPOSED current buffer OBS |
| Oil and gas extraction commodity | BEA summary `211` | CONFIRMED classification |
| Utilities commodity | BEA summary `22` | CONFIRMED classification |
| Petroleum and coal products commodity | BEA summary `324` | CONFIRMED classification |
| Pipeline transportation commodity | BEA summary `486` | CONFIRMED classification |
| Oil and gas extraction industry | BEA summary `211` | CONFIRMED classification |
| Utilities industry | BEA summary `22` | CONFIRMED classification |
| Petroleum and coal products industry | BEA summary `324` | CONFIRMED classification |
| Truck or pipeline transportation industry | BEA summary `484` or `486` | PROPOSED; final target requires Taylor choice |
| Current truck-transportation employment | BLS CES `CES4348400001`, NAICS 484 | APPROVED downstream endpoint; no ingestion yet |

The live 2024 summary Direct Requirements matrix includes, among other cells,
commodity 211 into industry 324 (`0.5633060`), commodity 211 into industry 22
(`0.0283052`), commodity 324 into industry 484 (`0.0466609`), and commodity 22
into industry 484 (`0.0129218`). These values are discovery evidence only. They
are not accepted edges, causal claims, propagation coefficients, or public
calculations.

## 7. Current-state and employment evidence

Minimum future companion sources:

| Need | Official source | Candidate dataset | Cadence | Connection |
|---|---|---|---|---|
| Petroleum stocks and refinery utilization | U.S. EIA | Weekly Petroleum Status Report tables | Weekly, normally Wednesday | Buffer/capacity state for 211/324 |
| Natural-gas storage | U.S. EIA | Weekly Natural Gas Storage Report | Weekly, normally Thursday | Buffer state for 211/22 |
| Current employment | U.S. BLS | CES `CES4348400001` | Monthly | NAICS 484 downstream employment exposure endpoint |

The approved downstream BLS series is “All employees, thousands, truck
transportation, seasonally adjusted,” `CES4348400001`, NAICS 484. The 211 series
may remain an origin companion. Each link must be produced through a versioned
authoritative concordance rather than a handwritten mapping.
BEA-to-BLS mappings that aggregate, split, or cross classification vintages must
retain fractional/many-to-many semantics or remain UNKNOWN.

## 8. Real behavior evidence status

| Behavior | Status | Evidence and limit |
|---|---|---|
| Buffer/inventory | **SUPPORTED** | EIA weekly crude/petroleum stocks and natural-gas storage are original-authority current quantities. No attenuation coefficient is approved. |
| Capacity/headroom | **SUPPORTED** | EIA weekly refinery utilization and Federal Reserve monthly capacity/utilization can support bounded current headroom. Exact selected series remains implementation-time validation. |
| Lag | **PARTIALLY_SUPPORTED** | Weekly stock coverage, storage, production and transport cadence support ordinal timing. No numeric transmission lag is yet accepted. |
| Substitution | **PARTIALLY_SUPPORTED** | BEA import and market-share matrices can describe economic sourcing shares. They do not prove physical interchangeability; technical qualification evidence remains required. |

The discontinued EIA weekly crude-oil storage-capacity series must not be used as
current capacity evidence: EIA states it ended with the week of 2024-02-14.
Current stocks remain weekly, while capacity evidence requires an active
monthly/annual or refinery-utilization series.

## 9. Common-cause proof opportunity

Confirmed topology supports a real future test:

- origin: BEA commodity 211, oil and gas extraction;
- path A: 211 -> industry/commodity 324 -> industry 484;
- path B: 211 -> industry/commodity 22 -> industry 484;
- target: truck transportation industry 484;
- issue: both paths share the same upstream 211 origin, so naïve addition can
  attribute the same initiating pressure twice;
- future reconciliation: retain origin, source-cell, path, period, unit, and
  coefficient identities; use governed overlap/cap rules or emit a range and an
  unresolved-overlap warning.

The future proof must verify the commodity-to-industry handoff through Make or
Market Share evidence before treating these as executable paths.

## 10. Bitemporal, revision, and health design

Each future structural artifact must retain economic year, official release
time, retrieval time, AUXSAYS acceptance time, product/table identity,
aggregation, classification vintage, price/redefinition basis, and
revision/supersession identity. The newest annual 2024 table was released in the
2025 annual update on 2025-09-25. Interactive tables present current estimates;
they are not by themselves a complete vintage archive.

`PUBLICLY_AVAILABLE_AS_OF(T)` therefore requires an official release timestamp
and a retained immutable release artifact/metadata identity. `OPERATIONALLY_KNOWN_AS_OF(T)`
additionally requires AUXSAYS retrieval and acceptance times. A future collector
must preserve each seen release; it must not reconstruct earlier knowledge from
today's interactive table.

Future source health must support `success`, `partial`, `no_results`, `blocked`,
`stale`, `broken`, `low_confidence`, `disabled`, and `manual_review_needed`.
Schema/classification changes, missing metadata, credential/rate-limit failure,
ambiguous rights, or unexplained row/column drift fail closed.

## 11. Rights, security, and cost

The multidimensional rights result is in `BEA_IO_SOURCE_INTAKE_CANDIDATE.md`.
In summary: API retrieval, immutable retention of BEA-produced data,
analysis/transformation, clearly typed AUXSAYS-derived relationship publication,
and public display are allowed with attribution, terms fingerprint, and no
endorsement claim. Automated interactive-site scraping is denied; raw bulk
redistribution is `DENY_NOT_REQUIRED`. Product-specific/third-party restrictions
override and fail the affected operation closed.

All official sources identified are free. The proposed recurring
infrastructure/API cost remains **$0**. No commercial data, managed graph store,
paid API, cloud database, or runtime AI dependency is selected.

## 12. Open blockers

1. A BEA API key provisioned as an external secret; never committed or logged.
2. Live API metadata capture through `GetParameterValues` of current integer
   `TableID` values, years, and schemas.
3. Safe inspection and versioning of the current BEA concordance, plus explicit
   NAICS-vintage compatibility with BLS 2022 NAICS.
4. Exact current EIA/Fed series needed for Gate-B behavior tests.

Until those are resolved, there is no authorization to ingest BEA data or
generate accepted structural relationships.
