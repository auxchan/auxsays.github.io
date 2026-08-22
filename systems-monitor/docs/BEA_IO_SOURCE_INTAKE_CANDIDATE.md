# BEA Input-Output Source Intake Candidate

Status: **CANDIDATE / NOT ACTIVE / NOT APPROVED FOR INGESTION**

Reviewed: **2026-08-21**

Candidate source ID: `bea_io_annual_summary_after_redefinitions`

## Intake record

| Field | Candidate value |
|---|---|
| Authority | U.S. Bureau of Economic Analysis (BEA) |
| Product family | Input-Output Accounts / Industry Economic Accounts |
| Canonical documentation | `https://www.bea.gov/itable/input-output` |
| Current overview | `https://www.bea.gov/data/industries/input-output-accounts-data` |
| Machine route | `https://apps.bea.gov/api/data`, dataset `InputOutput` |
| Human discovery route | BEA I/O interactive applications and official export catalogs |
| Authentication | Registered 36-character BEA API `UserID`; not requested in this sprint |
| Formats | API JSON/XML; interactive/download exports CSV/XLS/ZIP depending product |
| Metadata discovery | API `GETDATASETLIST`, `GETPARAMETERLIST`, and `GETPARAMETERVALUESFILTERED` |
| API table IDs | **UNKNOWN** until credentialed live metadata discovery; never guess |
| Current annual year | 2024, verified live on 2026-08-21 |
| Current annual aggregation | 71 summary industry/commodity groups |
| Release cadence | Annual; BEA states September |
| Current release | 2025 annual update released 2025-09-25 |
| Price/redefinition basis | Product-specific; candidate topology uses after-redefinitions, producers' prices |
| Units | Use/Supply values in millions of dollars; requirements as coefficients per dollar output |
| Classification | BEA industry and commodity codes with versioned BEA-to-NAICS concordance |
| Cost | $0 source/API and $0 recurring infrastructure target |

## Verified live selector identities

These are current interactive-application selector tokens, not API integer
`TableID` values:

| Product | Token | Candidate role |
|---|---|---|
| Supply | `Supply` | `STRUCTURAL_QUANTITY` / validation |
| Use before redefinitions | `UseIo` | `STRUCTURAL_QUANTITY` |
| Make after redefinitions | `MakeAR` | `STRUCTURAL_QUANTITY` |
| Use after redefinitions, producers' prices | `UseARPro` | `STRUCTURAL_QUANTITY` / audit |
| Import matrix after redefinitions | `UIMARI` | `ALLOCATION` / import evidence |
| Direct requirements after redefinitions | `CxIDRAR` | `GRAPH_EDGE_SOURCE` |
| Domestic direct requirements after redefinitions | `CxIDDRAR` | `VALIDATION` / decomposition |
| Market share after redefinitions | `IxCMSAR` | `MARKET_SHARE` only |
| Total requirements industry-by-commodity | `IxCTRAR` | `NON_RECURSIVE_BENCHMARK` |

Stable human evidence links for the primary selectors:

- Direct Requirements, after redefinitions: `https://apps.bea.gov/iTable/?Categories=AR&isURI=1&reqid=1602&step=2#eyJhcHBpZCI6MTYwMiwic3RlcHMiOlsxLDIsM10sImRhdGEiOltbImNhdGVnb3JpZXMiLCJBUiJdLFsiVGFibGVfTGlzdCIsIkN4SURSQVIiXV19`
- Total Requirements, Industry-by-Commodity: `https://apps.bea.gov/iTable/?Categories=Core&isURI=1&reqid=1602&step=2#eyJhcHBpZCI6MTYwMiwic3RlcHMiOlsxLDIsM10sImRhdGEiOltbImNhdGVnb3JpZXMiLCJDb3JlIl0sWyJUYWJsZV9MaXN0IiwiSXhDVFJBUiJdXX0=`

## Official exports verified without retention

Bounded HEAD inspection on 2026-08-21 verified these official product-family
archives. They were not downloaded or added to the repository.

| Archive | Size | Last-Modified | Purpose |
|---|---:|---|---|
| `DIRECT REQUIREMENTS AND MARKET SHARE MATRICES.zip` | 8,486,511 bytes | 2026-02-11 12:01:48 GMT | Direct/domestic direct/market-share export family |
| `TOTAL AND DOMESTIC REQUIREMENTS.zip` | 31,513,386 bytes | 2025-09-25 12:30:07 GMT | Total/domestic total export family |
| `SUPPLY-USE.zip` | 4,791,455 bytes | 2025-09-25 12:30:06 GMT | Supply/use export family |

Official catalogs:

- Core: `https://apps.bea.gov/iTable/?reqid=1602&isuri=1&step=8&categories=Core`
- After Redefinitions: `https://apps.bea.gov/iTable/?reqid=1602&isuri=1&step=8&categories=AR`

Because `apps.bea.gov/robots.txt` disallows general automated paths while
allowing `/api/`, future scheduled retrieval must use the API. Export archives
are a human/manual schema and contingency reference unless BEA explicitly
authorizes an automated export route.

## Rights matrix

| Operation | State | Evidence / required resolution |
|---|---|---|
| Automated API retrieval | `ALLOW` | API ToS and `/api/` robots allowance, subject to key and limits |
| Automated interactive/export scraping | `DENY` | `robots.txt` disallows `/` except `/api/` |
| Local raw retention | `UNKNOWN` | API ToS does not expressly settle immutable long-term raw retention; obtain written BEA clarification |
| Transformation and analysis | `ALLOW` | API ToS permits services that search, display, analyze, retrieve, and view, with no false representation |
| Publication of derived relationship records | `UNKNOWN` | Analysis is allowed, but derived-dataset publication is not explicit; obtain written clarification |
| Public display of BEA data | `ALLOW` | Subject to attribution, accurate representation, and no endorsement claim |
| Raw bulk redistribution | `UNKNOWN` | Not expressly approved in reviewed terms; fail closed |
| Attribution | `REQUIRED` | “This product uses the Bureau of Economic Analysis (BEA) Data API but is not endorsed or certified by BEA.” |
| Credential sharing/logging | `DENY` | Key is a secret; external secret store only; never repository/log/ZIP |

Rights fingerprint inputs for future intake must include the API ToS PDF, API
guide, `robots.txt`, BEA citation guidance, retrieval time, and hashes of any
retained terms evidence. Written confirmation should be requested from
`IndustryEconomicAccounts@bea.gov` or the BEA API support channel for the three
UNKNOWN dimensions.

## Rate, schema, and security controls

- Enforce 100 requests/minute, 100 MB/minute, and 30 errors/minute or the lower
  current limits returned by BEA.
- Respect `Retry-After`; bounded exponential backoff; no uncontrolled retry.
- Resolve dataset/parameter/table/year values from live metadata before every
  newly enabled configuration and on schema drift.
- Allowlist `https://apps.bea.gov/api/data`; reject redirects to unapproved
  hosts, private IPs, paths, and schemes.
- Bound bytes, rows, columns, cell length, decompressed size, and parse time.
- Treat JSON/XML/CSV/XLS/ZIP content as untrusted data. Never execute macros,
  formulas, scripts, or external links.
- Require expected row/column labels, numeric domains, units, year,
  classification, price basis, aggregation, and redefinition status.
- Quarantine schema mismatch or unexplained duplicate/missing codes.
- Do not log the `UserID`, full query URLs containing it, or raw payload content.

## Bitemporal and immutable identity

Future artifact identity must include:

`authority + dataset + API TableID + product token + economic year + release
time + retrieval time + accepted time + aggregation + classification vintage +
price basis + redefinition status + schema hash + content hash`.

BEA interactive data shows the current estimate, not every earlier published
vintage. AUXSAYS must retain each accepted release identity to support
operational replay. Public replay requires an official release time and retained
official evidence; absence of either produces `low_confidence` or
`manual_review_needed`, never a guessed timestamp.

## Product roles and prohibitions

- `CxIDRAR`: proposed direct topology source after full schema/crosswalk tests.
- `IxCTRAR`: non-recursive aggregate benchmark only.
- `CxIDDRAR` and imports: domestic/import decomposition and validation.
- Supply/Use/Make: quantity, row/column, output, and commodity/industry audit.
- `IxCMSAR`: commodity production-share allocation; not proof of technical
  substitutability.

Prohibited: recursive direct propagation plus overlapping total-requirements
contribution; price-basis mixing; before/after-redefinition mixing; silent
classification coercion; zero for missing evidence; accepting rows solely
because a coefficient is nonzero.

## Source health expectations

| State | Candidate trigger |
|---|---|
| `success` | Current metadata/schema/year and content validated |
| `partial` | Approved subset present but non-required cells/companion metadata incomplete |
| `no_results` | Valid response has no rows for requested table/year |
| `blocked` | Credential, rate, rights, or access gate prevents retrieval |
| `stale` | Expected September update absent beyond governed tolerance |
| `broken` | Endpoint, parse, required schema, or invariant failure |
| `low_confidence` | Release/vintage/classification evidence incomplete |
| `disabled` | Source/configuration deliberately inactive |
| `manual_review_needed` | Rights, schema, revision, or taxonomy change is ambiguous |

## Open questions blocking activation

1. Current API integer `TableID` values and exact JSON/XML schema.
2. Whether BEA authorizes immutable local raw retention.
3. Whether BEA authorizes public generated-relationship datasets and raw bulk
   redistribution; otherwise design a public read model that cites but does not
   redistribute restricted source structure.
4. Exact current BEA classification/NAICS vintage contained in the linked
   concordance and the required BLS 2022 NAICS bridge.
5. Final selected transport target and table subset.
6. Retention/deletion response if terms change.

No candidate becomes active until these questions and Taylor authorization are
resolved through the BINDING Source, Data, Ontology/Crosswalk, Relationship, and
Testing controls.
