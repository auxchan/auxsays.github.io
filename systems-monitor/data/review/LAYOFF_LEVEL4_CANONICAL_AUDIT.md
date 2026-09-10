# Layoffs Level-4 Canonical Audit

Status: **REVIEW EVIDENCE — NO OBSERVATION OR RELATIONSHIP PROMOTION**

## Recalculated boundary

- 100 reviewed Layoffs Level-4 placements.
- 64 canonical Level-4 factors.
- 77 UI-side factor/source state records.
- 48 expanded acquisition bindings across 42 records.
- 35 source-identified placeholders without a configured binding.
- 9 configured source identities outside the current taxonomy.

The historical `77 source profiles` label was imprecise: 77 is the size of the UI-side factor/source-state map, not the number of canonical factors or acquisition adapters. The machine-readable reconciliation is `data/config/layoffs/level4_source_profile_roles.json`.

## All 64 canonical factors

| Factor | Class | Placements | Source state | Selector | Sources |
|---|---|---:|---|---|---|
| `factor:canonical:average-weekly-hours` — Average Weekly Hours | A_DIRECT_OBS | 3 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bls-ces (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:borrowing-costs` — Borrowing Costs | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-h15 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:business-bankruptcy-filings` — Business Bankruptcy Filings | A_DIRECT_OBS | 1 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | uscourts-f2 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:business-bankruptcy-stress` — Business Bankruptcy Stress | B_CALC | 3 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:business-failure-stress` — Business Failure Stress | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:business-formation` — Business Formations | A_DIRECT_OBS | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:business-formation-dynamism` — Business Formation / Dynamism | B_CALC | 1 | BLOCKED | EXACT | census-bfs (CALC_INPUT) |
| `factor:canonical:candi-credit-conditions` — C&I Credit Conditions | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:candi-lending-standards` — C&I Lending Standards | A_DIRECT_OBS | 5 | BLOCKED | PENDING_OR_UNMAPPED | fed-sloos (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:candi-loan-demand` — C&I Loan Demand | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-sloos (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:capacity-utilization` — Capacity Utilization | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-g17 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:consumer-demand` — Consumer Demand | D_TAXONOMY_OR_SOURCE_PROBLEM | 3 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:consumer-spending` — Consumer Spending | A_DIRECT_OBS | 2 | BLOCKED | PENDING_OR_UNMAPPED | bea-nipa (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:corporate-profitability` — Corporate Profitability | B_CALC | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:corporate-profits` — Corporate Profits | A_DIRECT_OBS | 4 | BLOCKED | PENDING_OR_UNMAPPED | bea-nipa (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:disaster-external-shock` — Disaster / External Shock | C_EVENT_OR_STRUCTURAL | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:disaster-operational-shock` — Disaster / Operational Shock | C_EVENT_OR_STRUCTURAL | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:disaster-weather-shock` — Disaster / Weather Shock | C_EVENT_OR_STRUCTURAL | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:energy-input-shock` — Energy / Input Shock | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:establishment-closures` — Establishment Closures | A_DIRECT_OBS | 2 | BLOCKED | EXACT | bls-bed (PRIMARY_OBSERVATION_SOURCE); census-bds (ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE) |
| `factor:canonical:establishment-contractions` — Establishment Contractions | A_DIRECT_OBS | 1 | BLOCKED | EXACT | bls-bed (PRIMARY_OBSERVATION_SOURCE); census-bds (ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE) |
| `factor:canonical:establishment-deaths` — Establishment Deaths | A_DIRECT_OBS | 3 | BLOCKED | EXACT | bls-bed (PRIMARY_OBSERVATION_SOURCE); census-bds (ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE) |
| `factor:canonical:firm-age-size` — Firm Age / Size | C_EVENT_OR_STRUCTURAL | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:firm-age-size-vulnerability` — Firm Age / Size Vulnerability | B_CALC | 1 | BLOCKED | EXACT | census-bds (CALC_INPUT) |
| `factor:canonical:firm-deaths` — Firm Deaths | A_DIRECT_OBS | 1 | BLOCKED | EXACT | census-bds (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:gross-job-losses` — Gross Job Losses | A_DIRECT_OBS | 2 | BLOCKED | EXACT | bls-bed (PRIMARY_OBSERVATION_SOURCE); census-bds (ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE) |
| `factor:canonical:hires-rate` — Hires Rate | A_DIRECT_OBS | 2 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bls-jolts (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:import-exposure` — Import Exposure | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industrial-production` — Industrial Production | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-g17 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:industry-capacity-utilization` — Industry Capacity Utilization | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-g17 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:industry-credit-conditions` — Industry Credit Conditions | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-sloos (FALLBACK_ACQUISITION_METHOD) |
| `factor:canonical:industry-gross-job-losses` — Industry Gross Job Losses | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-input-prices` — Industry Input Prices | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-layoffs-and-discharges` — Industry Layoffs & Discharges | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-new-orders` — Industry New Orders | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-output` — Industry Output | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | bea-gdp-industry (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:industry-payroll-contraction` — Industry Payroll Contraction | B_CALC | 3 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-sales-shipments` — Industry Sales / Shipments | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:industry-unit-labor-costs` — Industry Unit Labor Costs | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:initial-claims` — Initial UI Claims | A_DIRECT_OBS | 1 | ACCEPTED | EXACT | dol-ui-claims (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:input-costs` — Input Costs | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:interest-rates` — Interest Rates | A_DIRECT_OBS | 2 | BLOCKED | PENDING_OR_UNMAPPED | fed-h15 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:inventory-sales-balance` — Inventory / Sales Balance | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:inventory-sales-imbalance` — Inventory / Sales Imbalance | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:inventory-sales-ratio` — Inventory / Sales Ratio | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:job-openings-rate` — Job Openings Rate | A_DIRECT_OBS | 2 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bls-jolts (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:layoffs-and-discharges` — Layoffs & Discharges | A_DIRECT_OBS | 1 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bls-jolts (PRIMARY_OBSERVATION_SOURCE); bls-jolts (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:manufacturing-output` — Manufacturing Output | A_DIRECT_OBS | 1 | BLOCKED | PENDING_OR_UNMAPPED | fed-g17 (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:new-orders` — New Orders | A_DIRECT_OBS | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:payroll-growth` — Payroll Growth | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:permanent-job-losers` — Permanent Job Losers | A_DIRECT_OBS | 1 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bls-cps (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:producer-input-costs` — Producer Input Costs | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:producer-input-prices` — Producer Input Prices | A_DIRECT_OBS | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:productivity-automation` — Productivity / Automation | D_TAXONOMY_OR_SOURCE_PROBLEM | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:real-output-growth` — Real Output Growth | A_DIRECT_OBS | 6 | BLOCKED | PENDING_OR_UNMAPPED | bea-nipa (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:regional-employment-growth` — Regional Employment Growth | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:retail-sales` — Retail Sales | A_DIRECT_OBS | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:sales-revenue` — Sales / Revenue | D_TAXONOMY_OR_SOURCE_PROBLEM | 2 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:sales-revenue-growth` — Sales / Revenue Growth | B_CALC | 1 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |
| `factor:canonical:temporary-help-employment` — Temporary Help Employment | A_DIRECT_OBS | 1 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bls-ces (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:temporary-layoffs` — Temporary Layoffs | A_DIRECT_OBS | 1 | SOURCE_ENABLED_PENDING_ACCEPTANCE | EXACT | bls-cps (PRIMARY_OBSERVATION_SOURCE) |
| `factor:canonical:trade-external-shock` — Trade / External Shock | C_EVENT_OR_STRUCTURAL | 1 | BLOCKED | EXACT | census-ftd (STRUCTURAL_SOURCE) |
| `factor:canonical:trade-import-pressure` — Import / Trade Pressure | B_CALC | 2 | BLOCKED | EXACT | census-ftd (CALC_INPUT) |
| `factor:canonical:unit-labor-costs` — Unit Labor Costs | A_DIRECT_OBS | 3 | SOURCE_IDENTIFIED | PENDING_OR_UNMAPPED | No configured binding |

## Reconciled 77-record state map

| Canonical/source-state record | Kind | State | Source bindings | Roles |
|---|---|---|---|---|
| `factor:canonical:average-weekly-hours` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-ces:CES0500000002 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:borrowing-costs` | LEVEL4_CANONICAL | BLOCKED | fed-h15:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:business-bankruptcy-filings` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | uscourts-f2:F2:US:BUSINESS:ALL | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:business-bankruptcy-stress` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:business-failure-bankruptcy-stress` | LEVEL3_PARENT | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:business-failure-stress` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:business-formation` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:business-formation-dynamism` | LEVEL4_CANONICAL | BLOCKED | census-bfs:BFS:T:BF_BF4Q:SA | CALC_INPUT |
| `factor:canonical:business-formations` | SOURCE_ONLY | BLOCKED | census-bfs:BFS:T:BF_BF4Q:SA | LEGACY_DUPLICATE_SHOULD_REMOVE |
| `factor:canonical:candi-credit-conditions` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:candi-lending-standards` | LEVEL4_CANONICAL | BLOCKED | fed-sloos:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:candi-loan-demand` | LEVEL4_CANONICAL | BLOCKED | fed-sloos:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:capacity-utilization` | LEVEL4_CANONICAL | BLOCKED | fed-g17:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:consumer-demand` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:consumer-spending` | LEVEL4_CANONICAL | BLOCKED | bea-nipa:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:continued-claims-insured-unemployment` | LEVEL3_PARENT | SOURCE_ENABLED_PENDING_ACCEPTANCE | dol-ui-claims:DOL-UI-SA-CONTINUED; dol-ui-claims:DOL-UI-SA-IUR | CALC_INPUT; CALC_INPUT |
| `factor:canonical:corporate-profitability` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:corporate-profits` | LEVEL4_CANONICAL | BLOCKED | bea-nipa:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:courts-business-chapter-11` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | uscourts-f2:F2:US:BUSINESS:CH11 | CALC_INPUT |
| `factor:canonical:courts-business-chapter-12` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | uscourts-f2:F2:US:BUSINESS:CH12 | CALC_INPUT |
| `factor:canonical:courts-business-chapter-13` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | uscourts-f2:F2:US:BUSINESS:CH13 | CALC_INPUT |
| `factor:canonical:courts-business-chapter-7` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | uscourts-f2:F2:US:BUSINESS:CH7 | CALC_INPUT |
| `factor:canonical:disaster-external-shock` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:disaster-operational-shock` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:disaster-weather-shock` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:energy-input-shock` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:establishment-birth-job-gains` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-bed:BDS0000000000000000110007LQ5 | CALC_INPUT |
| `factor:canonical:establishment-closures` | LEVEL4_CANONICAL | BLOCKED | bls-bed:BDS0000000000000000110006LQ5; census-bds:JOB_DESTRUCTION_DEATHS | PRIMARY_OBSERVATION_SOURCE; ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE |
| `factor:canonical:establishment-contractions` | LEVEL4_CANONICAL | BLOCKED | bls-bed:BDS0000000000000000110005LQ5; census-bds:JOB_DESTRUCTION_CONTINUERS | PRIMARY_OBSERVATION_SOURCE; ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE |
| `factor:canonical:establishment-death-closure-losses` | LEVEL3_PARENT | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:establishment-deaths` | LEVEL4_CANONICAL | BLOCKED | bls-bed:BDS0000000000000000110008LQ5; census-bds:ESTABS_EXIT | PRIMARY_OBSERVATION_SOURCE; ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE |
| `factor:canonical:establishment-expansions` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-bed:BDS0000000000000000110002LQ5 | CALC_INPUT |
| `factor:canonical:establishment-openings` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-bed:BDS0000000000000000110003LQ5 | CALC_INPUT |
| `factor:canonical:firm-age-size` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:firm-age-size-vulnerability` | LEVEL4_CANONICAL | BLOCKED | census-bds:FIRMDEATH_ESTABS | CALC_INPUT |
| `factor:canonical:firm-death-shutdown-stress` | LEVEL3_PARENT | BLOCKED | census-bds:FIRMDEATH_EMP | CALC_INPUT |
| `factor:canonical:firm-deaths` | LEVEL4_CANONICAL | BLOCKED | census-bds:FIRMDEATH_FIRMS | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:gross-job-gains` | SOURCE_ONLY | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-bed:BDS0000000000000000110001LQ5 | CALC_INPUT |
| `factor:canonical:gross-job-losses` | LEVEL4_CANONICAL | BLOCKED | bls-bed:BDS0000000000000000110004LQ5; census-bds:JOB_DESTRUCTION | PRIMARY_OBSERVATION_SOURCE; ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE |
| `factor:canonical:hires-rate` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-jolts:JTS000000000000000HIR | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:import-exposure` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industrial-production` | LEVEL4_CANONICAL | BLOCKED | fed-g17:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:industry-capacity-utilization` | LEVEL4_CANONICAL | BLOCKED | fed-g17:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:industry-credit-conditions` | LEVEL4_CANONICAL | BLOCKED | fed-sloos:selector-pending | FALLBACK_ACQUISITION_METHOD |
| `factor:canonical:industry-gross-job-losses` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-input-prices` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-layoffs-and-discharges` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-new-orders` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-output` | LEVEL4_CANONICAL | BLOCKED | bea-gdp-industry:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:industry-payroll-contraction` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-sales-shipments` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:industry-unit-labor-costs` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:initial-claims` | LEVEL3_PARENT | ACCEPTED | dol-ui-claims:DOL-UI-SA-INITIAL | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:input-costs` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:interest-rates` | LEVEL4_CANONICAL | BLOCKED | fed-h15:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:inventory-sales-balance` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:inventory-sales-imbalance` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:inventory-sales-ratio` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:job-openings-rate` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-jolts:JTS000000000000000JOR | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:layoffs-and-discharges` | LEVEL3_PARENT | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-jolts:JTS000000000000000LDL; bls-jolts:JTS000000000000000LDR | PRIMARY_OBSERVATION_SOURCE; PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:manufacturing-output` | LEVEL4_CANONICAL | BLOCKED | fed-g17:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:new-orders` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:payroll-growth` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:permanent-job-losers` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-cps:LNS13026638 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:producer-input-costs` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:producer-input-prices` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:productivity-automation` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:real-output-growth` | LEVEL4_CANONICAL | BLOCKED | bea-nipa:selector-pending | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:regional-employment-growth` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:retail-sales` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:sales-revenue` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:sales-revenue-growth` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |
| `factor:canonical:temporary-help-employment` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-ces:CES6056132001 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:temporary-layoffs` | LEVEL4_CANONICAL | SOURCE_ENABLED_PENDING_ACCEPTANCE | bls-cps:LNS13023653 | PRIMARY_OBSERVATION_SOURCE |
| `factor:canonical:trade-external-shock` | LEVEL4_CANONICAL | BLOCKED | census-ftd:FTD:IMP:BOPGS:SA | STRUCTURAL_SOURCE |
| `factor:canonical:trade-import-pressure` | LEVEL4_CANONICAL | BLOCKED | census-ftd:FTD:IMP:BOPGS:SA | CALC_INPUT |
| `factor:canonical:unit-labor-costs` | LEVEL4_CANONICAL | SOURCE_IDENTIFIED | — | UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER |

## Required cleanup before reuse on the other nine branches

The following source-only records do not resolve to a current taxonomy identity and therefore cannot remain unexplained:

- `factor:canonical:business-formations`
- `factor:canonical:courts-business-chapter-11`
- `factor:canonical:courts-business-chapter-12`
- `factor:canonical:courts-business-chapter-13`
- `factor:canonical:courts-business-chapter-7`
- `factor:canonical:establishment-birth-job-gains`
- `factor:canonical:establishment-expansions`
- `factor:canonical:establishment-openings`
- `factor:canonical:gross-job-gains`

`business-formations` is a legacy plural alias and should canonicalize to the singular factor after review. The four BED gain/opening records and four Courts chapter records are useful calculation/corroboration inputs, but they are not current Level-4 placements and must remain explicitly typed as such.

## Promotion boundary

A/B/C/D classification, source identity, selector readiness, and collector availability do not accept an observation, calculation, history, or relationship. Human Level-4 QA remains pending.
