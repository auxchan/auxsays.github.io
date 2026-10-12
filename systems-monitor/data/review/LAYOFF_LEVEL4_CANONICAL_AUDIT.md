# Layoffs Level-4 Canonical Audit

Status: **REVIEW EVIDENCE — NO OBSERVATION OR RELATIONSHIP PROMOTION**

## Recalculated boundary

- 100 reviewed Layoffs Level-4 placements.
- 64 canonical Level-4 factors.
- 74 UI-side factor/source state records.
- 46 expanded acquisition bindings across 42 records.
- 32 source-identified placeholders without a configured binding.
- 6 configured source identities outside the current taxonomy.

The historical `77 source profiles` label was imprecise: it described a pre-cleanup UI-side state count, not canonical factors or adapters. The current governed registry contains 74 active records after narrowing Courts F-2 to the national all-business selector and separating noninterchangeable Census BDS identities.

## All 64 canonical factors

| Factor | Class | Placements | Source state | Selector | Sources |
|---|---|---:|---|---|---|
| `factor:canonical:average-weekly-hours` — Average Weekly Hours | A_DIRECT_OBS | 3 | ACCEPTED | EXACT | bls-ces (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:borrowing-costs` — Borrowing Costs | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-h15 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:business-bankruptcy-filings` — Business Bankruptcy Filings | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:business-bankruptcy-filings-12-month-total` — Business Bankruptcy Filings, 12-Month Total | A_DIRECT_OBS | 3 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | uscourts-f2 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:business-failure-stress` — Business Failure Stress | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:business-formation` — Business Formations | A_DIRECT_OBS | 2 | BLOCKED | EXACT | census-bfs (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:business-formation-dynamism` — Business Formation / Dynamism | B_CALC | 1 | BLOCKED | EXACT | census-bfs (CALC_INPUT) |
| `factor:canonical:candi-credit-conditions` — C&I Credit Conditions | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:candi-lending-standards` — C&I Lending Standards | A_DIRECT_OBS | 5 | BLOCKED | PENDING_OR_UNMAPPED | fed-sloos (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:candi-loan-demand` — C&I Loan Demand | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-sloos (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:capacity-utilization` — Capacity Utilization | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-g17 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:consumer-spending` — Consumer Spending | A_DIRECT_OBS | 2 | BLOCKED | PENDING_OR_UNMAPPED | bea-nipa (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:corporate-profitability` — Corporate Profitability | B_CALC | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:corporate-profits` — Corporate Profits | A_DIRECT_OBS | 4 | BLOCKED | PENDING_OR_UNMAPPED | bea-nipa (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:disaster-external-shock` — Disaster / External Shock | C_EVENT_OR_STRUCTURAL | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:disaster-weather-shock` — Disaster / Weather Shock | C_EVENT_OR_STRUCTURAL | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:energy-input-shock` — Energy / Input Shock | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:establishment-closures` — Establishment Closures | A_DIRECT_OBS | 2 | ACCEPTED | EXACT | bls-bed (PRIMARY_OBSERVATION_SOURCE); census-bds (ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE) |
| `factor:canonical:establishment-contractions` — Establishment Contractions | A_DIRECT_OBS | 1 | ACCEPTED | EXACT | bls-bed (PRIMARY_OBSERVATION_SOURCE); census-bds (ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE) |
| `factor:canonical:fema-disaster-declaration` — FEMA Disaster Declaration | C_EVENT_OR_STRUCTURAL | 1 | SOURCE_IDENTIFIED | EXACT | fema-openfema (STRUCTURAL_SOURCE) |
| `factor:canonical:firm-age-size` — Firm Age / Size | C_EVENT_OR_STRUCTURAL | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:firm-age-size-vulnerability` — Firm Age / Size Vulnerability | B_CALC | 1 | BLOCKED | EXACT | census-bds (CALC_INPUT) |
| `factor:canonical:firm-deaths` — Firm Deaths | A_DIRECT_OBS | 1 | BLOCKED | EXACT | census-bds (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:gross-job-losses` — Gross Job Losses | A_DIRECT_OBS | 2 | ACCEPTED | EXACT | bls-bed (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:hires-rate` — Hires Rate | A_DIRECT_OBS | 2 | ACCEPTED | EXACT | bls-jolts (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:import-exposure` — Import Exposure | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industrial-production` — Industrial Production | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-g17 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:industry-capacity-utilization` — Industry Capacity Utilization | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-g17 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:industry-credit-conditions` — Industry Credit Conditions | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-sloos (FALLBACK_ACQUISITION_METHOD) |
| `factor:canonical:industry-gross-job-losses` — Industry Gross Job Losses | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-input-prices` — Industry Input Prices | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-layoffs-and-discharges` — Industry Layoffs & Discharges | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-new-orders` — Industry New Orders | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-output` — Industry Output | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | bea-gdp-industry (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:industry-sales-shipments` — Industry Sales / Shipments | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-unit-labor-costs` — Industry Unit Labor Costs | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:initial-claims` — Initial UI Claims | A_DIRECT_OBS | 1 | ACCEPTED | EXACT | dol-ui-claims (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:input-costs` — Input Costs | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:interest-rates` — Interest Rates | A_DIRECT_OBS | 2 | BLOCKED | PENDING_OR_UNMAPPED | fed-h15 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:inventory-sales-balance` — Inventory / Sales Balance | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:inventory-sales-imbalance` — Inventory / Sales Imbalance | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:inventory-sales-ratio` — Inventory / Sales Ratio | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:job-openings-rate` — Job Openings Rate | A_DIRECT_OBS | 2 | ACCEPTED | EXACT | bls-jolts (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:jobs-lost-at-establishment-deaths` — Jobs Lost at Establishment Deaths | A_DIRECT_OBS | 3 | ACCEPTED | EXACT | bls-bed (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:layoffs-and-discharges` — Layoffs & Discharges | A_DIRECT_OBS | 1 | ACCEPTED | EXACT | bls-jolts (PRIMARY_OBSERVATION_SOURCE); bls-jolts (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:manufacturing-output` — Manufacturing Output | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-g17 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:new-orders` — New Orders | A_DIRECT_OBS | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:payroll-contraction-breadth` — Industry Payroll Contraction | B_CALC | 3 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:payroll-growth` — Payroll Growth | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:permanent-job-losers` — Permanent Job Losers | A_DIRECT_OBS | 1 | ACCEPTED | EXACT | bls-cps (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:producer-input-costs` — Producer Input Costs | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:producer-input-prices` — Producer Input Prices | A_DIRECT_OBS | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:productivity-automation` — Productivity / Automation | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:real-gdp-growth` — Real GDP Growth | A_DIRECT_OBS | 6 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bea-nipa (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:real-personal-consumption-expenditures-growth` — Real Personal Consumption Expenditures Growth | A_DIRECT_OBS | 3 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bea-nipa (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:regional-employment-growth` — Regional Employment Growth | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:retail-sales` — Retail Sales | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:sales-revenue` — Sales / Revenue | D_TAXONOMY_OR_SOURCE_PROBLEM | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:sales-revenue-growth` — Sales / Revenue Growth | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:temporary-help-employment` — Temporary Help Employment | A_DIRECT_OBS | 1 | ACCEPTED | EXACT | bls-ces (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:temporary-layoffs` — Temporary Layoffs | A_DIRECT_OBS | 1 | ACCEPTED | EXACT | bls-cps (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:trade-external-shock` — Trade / External Shock | C_EVENT_OR_STRUCTURAL | 1 | BLOCKED | EXACT | census-ftd (STRUCTURAL_SOURCE) |
| `factor:canonical:trade-import-pressure` — Import / Trade Pressure | B_CALC | 2 | BLOCKED | EXACT | census-ftd (CALC_INPUT) |
| `factor:canonical:unit-labor-costs` — Unit Labor Costs | A_DIRECT_OBS | 3 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |

## Reconciled 74-record state map

| Canonical/source-state record | Kind | State | Source bindings | Roles |
|---|---|---|---|---|
| `factor:canonical:average-weekly-hours` | LEVEL4_CANONICAL | ACCEPTED | bls-ces:CES0500000002 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:bds-establishment-exits` | SOURCE_ONLY | BLOCKED | census-bds:ESTABS_EXIT | CALC_INPUT |
| `factor:canonical:bds-job-destruction` | SOURCE_ONLY | BLOCKED | census-bds:JOB_DESTRUCTION | CALC_INPUT |
| `factor:canonical:borrowing-costs` | LEVEL4_CANONICAL | BLOCKED | fed-h15:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:business-bankruptcy-filings` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:business-bankruptcy-filings-12-month-total` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | uscourts-f2:F2:US:BUSINESS:ALL | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:business-failure-bankruptcy-stress` | LEVEL3_PARENT | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:business-failure-stress` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:business-formation` | LEVEL4_CANONICAL | BLOCKED | census-bfs:BFS:T:BF_BF4Q:SA | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:business-formation-dynamism` | LEVEL4_CANONICAL | BLOCKED | census-bfs:BFS:T:BF_BF4Q:SA | CALC_INPUT |
| `factor:canonical:candi-credit-conditions` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:candi-lending-standards` | LEVEL4_CANONICAL | BLOCKED | fed-sloos:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:candi-loan-demand` | LEVEL4_CANONICAL | BLOCKED | fed-sloos:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:capacity-utilization` | LEVEL4_CANONICAL | BLOCKED | fed-g17:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:consumer-spending` | LEVEL4_CANONICAL | BLOCKED | bea-nipa:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:continued-claims-insured-unemployment` | LEVEL3_PARENT | SOURCE_ENABLED_PENDING_ACCEPTANCE | dol-ui-claims:DOL-UI-SA-CONTINUED; dol-ui-claims:DOL-UI-SA-IUR | PRIMARY_OBSERVATION_SOURCE; PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:corporate-profitability` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:corporate-profits` | LEVEL4_CANONICAL | BLOCKED | bea-nipa:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:disaster-external-shock` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:disaster-weather-shock` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:energy-input-shock` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:establishment-birth-job-gains` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-bed:BDS0000000000000000110007LQ5 | CALC_INPUT |
| `factor:canonical:establishment-closures` | LEVEL4_CANONICAL | ACCEPTED | bls-bed:BDS0000000000000000110006LQ5; census-bds:JOB_DESTRUCTION_DEATHS | PRIMARY_OBSERVATION_SOURCE; ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE |
| `factor:canonical:establishment-contractions` | LEVEL4_CANONICAL | ACCEPTED | bls-bed:BDS0000000000000000110005LQ5; census-bds:JOB_DESTRUCTION_CONTINUERS | PRIMARY_OBSERVATION_SOURCE; ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE |
| `factor:canonical:establishment-death-closure-losses` | LEVEL3_PARENT | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:establishment-expansions` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-bed:BDS0000000000000000110002LQ5 | CALC_INPUT |
| `factor:canonical:establishment-openings` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-bed:BDS0000000000000000110003LQ5 | CALC_INPUT |
| `factor:canonical:fema-disaster-declaration` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | fema-openfema:DisasterDeclarationsSummaries-v2 | STRUCTURAL_SOURCE |
| `factor:canonical:firm-age-size` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:firm-age-size-vulnerability` | LEVEL4_CANONICAL | BLOCKED | census-bds:FIRMDEATH_ESTABS | CALC_INPUT |
| `factor:canonical:firm-death-shutdown-stress` | LEVEL3_PARENT | BLOCKED | census-bds:FIRMDEATH_EMP | CALC_INPUT |
| `factor:canonical:firm-deaths` | LEVEL4_CANONICAL | BLOCKED | census-bds:FIRMDEATH_FIRMS | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:gross-job-gains` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-bed:BDS0000000000000000110001LQ5 | CALC_INPUT |
| `factor:canonical:gross-job-losses` | LEVEL4_CANONICAL | ACCEPTED | bls-bed:BDS0000000000000000110004LQ5 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:hires-rate` | LEVEL4_CANONICAL | ACCEPTED | bls-jolts:JTS000000000000000HIR | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:import-exposure` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industrial-production` | LEVEL4_CANONICAL | BLOCKED | fed-g17:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:industry-capacity-utilization` | LEVEL4_CANONICAL | BLOCKED | fed-g17:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:industry-credit-conditions` | LEVEL4_CANONICAL | BLOCKED | fed-sloos:selector-pending | FALLBACK_ACQUISITION_METHOD |
| `factor:canonical:industry-gross-job-losses` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-input-prices` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-layoffs-and-discharges` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-new-orders` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-output` | LEVEL4_CANONICAL | BLOCKED | bea-gdp-industry:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:industry-sales-shipments` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-unit-labor-costs` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:initial-claims` | LEVEL3_PARENT | ACCEPTED | dol-ui-claims:DOL-UI-SA-INITIAL | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:input-costs` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:interest-rates` | LEVEL4_CANONICAL | BLOCKED | fed-h15:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:inventory-sales-balance` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:inventory-sales-imbalance` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:inventory-sales-ratio` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:job-openings-rate` | LEVEL4_CANONICAL | ACCEPTED | bls-jolts:JTS000000000000000JOR | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:jobs-lost-at-establishment-deaths` | LEVEL4_CANONICAL | ACCEPTED | bls-bed:BDS0000000000000000110008LQ5 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:layoffs-and-discharges` | LEVEL3_PARENT | ACCEPTED | bls-jolts:JTS000000000000000LDL; bls-jolts:JTS000000000000000LDR | PRIMARY_OBSERVATION_SOURCE; PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:manufacturing-output` | LEVEL4_CANONICAL | BLOCKED | fed-g17:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:new-orders` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:payroll-contraction-breadth` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:payroll-growth` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:permanent-job-losers` | LEVEL4_CANONICAL | ACCEPTED | bls-cps:LNS13026638 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:producer-input-costs` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:producer-input-prices` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:productivity-automation` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:real-gdp-growth` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | bea-nipa:BEA:NIPA:T10101:1:Q | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:real-personal-consumption-expenditures-growth` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | bea-nipa:BEA:NIPA:T10101:2:Q | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:regional-employment-growth` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:retail-sales` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:sales-revenue` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:sales-revenue-growth` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:temporary-help-employment` | LEVEL4_CANONICAL | ACCEPTED | bls-ces:CES6056132001 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:temporary-layoffs` | LEVEL4_CANONICAL | ACCEPTED | bls-cps:LNS13023653 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:trade-external-shock` | LEVEL4_CANONICAL | BLOCKED | census-ftd:FTD:IMP:BOPGS:SA | STRUCTURAL_SOURCE |
| `factor:canonical:trade-import-pressure` | LEVEL4_CANONICAL | BLOCKED | census-ftd:FTD:IMP:BOPGS:SA | CALC_INPUT |
| `factor:canonical:unit-labor-costs` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |

## Required cleanup before reuse on the other nine branches

The following source-only records do not resolve to a current taxonomy identity and therefore cannot remain unexplained:

- `factor:canonical:bds-establishment-exits` — **SECONDARY_CONTEXT_ONLY**; target `factor:canonical:jobs-lost-at-establishment-deaths`; no activation effect.
- `factor:canonical:bds-job-destruction` — **SECONDARY_CONTEXT_ONLY**; target `factor:canonical:gross-job-losses`; no activation effect.
- `factor:canonical:business-formations` — **ALIAS_SUPERSEDED**; target `factor:canonical:business-formation`; no activation effect.
- `factor:canonical:establishment-birth-job-gains` — **CALC_INPUT_ONLY**; target `factor:canonical:establishment-openings`; no activation effect.
- `factor:canonical:establishment-expansions` — **CALC_INPUT_ONLY**; target `factor:canonical:gross-job-gains`; no activation effect.
- `factor:canonical:establishment-openings` — **CALC_INPUT_ONLY**; target `factor:canonical:gross-job-gains`; no activation effect.
- `factor:canonical:gross-job-gains` — **SECONDARY_CONTEXT_ONLY**; target `factor:canonical:gross-job-losses`; no activation effect.

`business-formations` is canonicalized to the singular factor while its legacy identity remains recorded. Three BED component records are calculation-input-only. BED gross gains and the two noninterchangeable Census BDS identities remain context-only. Courts F-2 is narrowed to one exact national all-business selector. None of these cleanup records becomes a new placement or accepted observation.

## Promotion boundary

A/B/C/D classification, source identity, selector readiness, and collector availability do not accept an observation, calculation, history, or relationship. Human Level-4 QA remains pending.
