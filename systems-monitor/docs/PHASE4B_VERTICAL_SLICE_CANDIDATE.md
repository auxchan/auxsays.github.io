# Phase-4B Vertical Slice Candidate

Status: **RECOMMENDED / TAYLOR APPROVAL REQUIRED**

Date: **2026-08-21**

Recommended domain: **Energy supply, refining, utilities, and transport**

This is a bounded implementation candidate. It contains no accepted
relationships, production source records, parser output, propagation result,
forecast, or Gate-B claim.

## 1. Decision recommendation

Approve an initial annual-2024, BEA 71-summary-category structural proof using
after-redefinitions Direct Requirements as the topology source and
Industry-by-Commodity Total Requirements as a non-recursive benchmark. Attach
only the minimum EIA and BLS current-state evidence needed to exercise real
buffer, capacity, lag, common-cause, and employment-exposure behavior.

Do not approve all-energy ingestion or all 71x71 cells. The future
implementation should query/parse the authoritative matrix, validate it as a
whole enough to establish identity, then materialize only the approved bounded
code subset and evidence-preserving candidate relationships.

## 2. Alternatives considered

| Domain | Strength | Limitation | Result |
|---|---|---|---|
| Construction | Clear BEA 23 node; Census monthly spending; strong BLS employment | Weak inventory/buffer and substitution proof | Reserve alternative |
| Energy | Clear 211/22/324/486 structure; EIA weekly stocks/storage/utilization; exact BLS 211 employment | Technical substitution still incomplete; requires rights/crosswalk closure | **Recommended** |
| Freight/transport | BEA 484/486; BTS Freight TSI; recognizable downstream effects | Capacity and modal substitution are fragmented; TSI is broader than one BEA node | Reserve alternative |
| Manufacturing | Strong BEA structure, Census M3, Fed capacity, BLS employment | Scope/crosswalk complexity is too high for the first 8–20-node proof | Later expansion |

## 3. Structural products

| Need | Exact current product | Role | Status |
|---|---|---|---|
| Direct topology | BEA after-redefinitions Direct Requirements, `CxIDRAR`, summary, 2024, producers' prices | `GRAPH_EDGE_SOURCE` | CONFIRMED FROM OFFICIAL SOURCE |
| Aggregate control | BEA Total Requirements Industry-by-Commodity, `IxCTRAR`, summary, 2024, producers' prices | `NON_RECURSIVE_BENCHMARK` | CONFIRMED FROM OFFICIAL SOURCE |
| Industry/commodity handoff | BEA Make AR `MakeAR` and Market Share AR `IxCMSAR` | `STRUCTURAL_QUANTITY` / `MARKET_SHARE` | CONFIRMED product; exact handoff rule PROPOSED |
| Domestic/import split | `CxIDDRAR` plus `UIMARI` | `VALIDATION` / `ALLOCATION` | CONFIRMED products; first-proof use PROPOSED |
| Source audit | Supply, Use AR producers' prices | `STRUCTURAL_QUANTITY` / validation | CONFIRMED; supporting only |

Direct and total products will never be arithmetically combined. Total output
may validate or bound a direct-path result but may not be recursively traversed.

## 4. Proposed node set

| ID | Proposed node | Type | Authority/classification | Current evidence |
|---|---|---|---|---|
| N01 | U.S. crude/petroleum stocks | Current buffer state | EIA WPSR | Weekly stock quantity |
| N02 | U.S. refinery utilization | Current capacity state | EIA WPSR | Weekly percentage |
| N03 | U.S. working natural gas in storage | Current buffer state | EIA WNGSR | Weekly stock quantity |
| N04 | Oil and gas extraction commodity | Structural commodity | BEA `211` | Annual 2024 |
| N05 | Utilities commodity | Structural commodity | BEA `22` | Annual 2024 |
| N06 | Petroleum and coal products commodity | Structural commodity | BEA `324` | Annual 2024 |
| N07 | Pipeline transportation commodity | Structural commodity | BEA `486` | Annual 2024 |
| N08 | Oil and gas extraction industry | Structural industry | BEA `211` | Annual 2024 |
| N09 | Utilities industry | Structural industry | BEA `22` | Annual 2024 |
| N10 | Petroleum and coal products industry | Structural industry | BEA `324` | Annual 2024 |
| N11 | Truck transportation industry | Structural downstream | BEA `484` | Annual 2024 |
| N12 | Oil and gas extraction employment | Current employment endpoint | BLS `CES1021100001`, NAICS 211 | Monthly, thousands, SA |

Pipeline transportation industry `486` is the recommended first reserve node.
Taylor may substitute it for N11 if the implementation-time common-cause and
employment linkage tests are stronger. The node set must remain within the
approved bound.

## 5. Proposed relationship envelope

Expected future count: **18–26** validated direct structural relationships,
selected only after schema and code validation. Expected categories:

- commodity requirements of 211, 22, 324, 484, and optional 486 industries;
- Make/Market-Share handoffs from industry output to commodities;
- current EIA state attachments to the matching BEA nodes;
- one authoritative BEA-to-BLS classification link to current employment;
- explicit origin/path identity for the common-cause proof.

Live official cells demonstrate that a compact graph exists, including 211 ->
324, 211 -> 22, 324 -> 484, and 22 -> 484. The exact future candidate edge list
must be generated deterministically from a validated API payload. No coefficient
in this document is accepted for propagation.

## 6. Current companion evidence

### EIA Weekly Petroleum Status Report

- Authority: U.S. Energy Information Administration.
- Needed metrics: commercial crude/petroleum stocks and refinery utilization.
- Cadence: weekly, normally Wednesday; holiday schedule varies.
- Geography: United States for the first proof.
- Mapping: stocks to BEA 211/324 buffer state; utilization to BEA 324 capacity.
- Access: official WPSR CSV/XLS and EIA API v2 candidate routes.
- Credential: EIA API key for API use; not requested in discovery.
- Rights: EIA-produced material is generally public domain with attribution
  requested, subject to logo/third-party exclusions; intake review still needed.
- Reuse: existing AUXSAYS source/rights/replay infrastructure can be reused; no
  petroleum parser exists yet.

### EIA Weekly Natural Gas Storage Report

- Needed metric: working gas in underground storage.
- Cadence: weekly, normally Thursday.
- Mapping: buffer state for BEA 211/22.
- Status: source family confirmed; exact series/region must be selected live at
  implementation time.

### BLS Current Employment Statistics

- Exact series: `CES1021100001`.
- Title: All employees, thousands, oil and gas extraction, seasonally adjusted.
- NAICS: 211; cadence monthly.
- Human evidence: `https://data.bls.gov/timeseries/CES1021100001`.
- Mapping: BEA summary industry 211 through the versioned BEA concordance to BLS
  2022 NAICS 211.
- No new BLS retrieval or configuration was created.

## 7. Behavioral proof plan

| Gate-B behavior | Candidate evidence | Current status | Future acceptance condition |
|---|---|---|---|
| Buffer | EIA crude/petroleum stocks and natural-gas storage | SUPPORTED | Exact current series, unit, geography, revision, and rights pass intake |
| Capacity | EIA refinery utilization; optional Fed G.17 petroleum/energy capacity | SUPPORTED | Exact active series and sustainable-capacity meaning validated |
| Lag | Weekly inventory coverage/storage and transport cadence | PARTIALLY_SUPPORTED | Use official timing; ordinal if no defensible duration exists |
| Substitution | BEA Import/Market Share plus EIA import/alternate-fuel evidence | PARTIALLY_SUPPORTED | Separate economic sourcing share from physical technical qualification |
| Common cause | 211 origin reaches 484 via 324 and 22 paths | SUPPORTED AS A DESIGN OPPORTUNITY | Validated direct cells, handoff rule, origin identity, and non-naive reconciliation |

No attenuation, amplification, substitution, buffer, or lag coefficient is
approved by this discovery.

## 8. Classification and crosswalk

BEA current summary codes identify industries and commodities. BEA provides an
official Industry and Commodity Codes and NAICS Concordance. BLS CES and QCEW
use 2022 NAICS for current data. Future implementation must:

1. safely inspect and hash the current BEA concordance;
2. record its publication/version and the BEA classification vintage;
3. map through explicit authority, not coincident-looking numeric labels;
4. represent one-to-many, many-to-one, or fractional coverage;
5. keep commodity and industry identities distinct;
6. reject unresolved vintage incompatibility.

The proposed 211 employment endpoint is the simplest direct-looking mapping,
but remains implementation-time validated. Occupation exposure is excluded.

## 9. Bitemporal and revision plan

For every future BEA/EIA/BLS artifact preserve economic period, official public
release time, retrieval time, accepted time, source table/series version,
revision/supersession, classification vintage, schema hash, and content hash.

The current BEA interactive app is a latest-estimate surface. AUXSAYS must retain
each accepted annual release and may answer `PUBLICLY_AVAILABLE_AS_OF(T)` only
from independently proven release evidence. `OPERATIONALLY_KNOWN_AS_OF(T)` also
applies the AUXSAYS retrieval/acceptance cutoff. A later annual revision must not
leak into an earlier replay.

## 10. Expected implementation complexity and cost

Complexity: **medium**. The matrix parser and crosswalk are bounded but require
careful row/column identity, price/redefinition controls, and rights-aware
immutable evidence. The 12-node surface is small enough for human audit, while
the API metadata and matrix validators make the approach self-sustaining.

Recurring cost: **$0**. BEA, EIA, and BLS access is free. Use repository-owned
code and existing SQLite/versioned-file mechanisms; no paid API, graph SaaS,
managed database, or LLM runtime dependency.

## 11. Required Taylor decisions

- Approve/reject the energy domain and 71-summary 2024 first proof.
- Approve/reject `CxIDRAR` as topology and `IxCTRAR` as benchmark-only.
- Choose N11 truck transportation or reserve 486 pipeline transportation.
- Approve external secret provisioning for BEA and any selected EIA API keys.
- Decide whether unresolved BEA retention/derived-publication rights require
  written confirmation before implementation (recommended: yes).
- Authorize a later bounded implementation only after those decisions and exact
  API metadata/crosswalk validation.

Until then this candidate is non-active and Gate B remains OPEN.
