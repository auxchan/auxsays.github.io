# Economic Influence Level-2 Candidates

Status: **REVIEW CANDIDATES / NOT ACCEPTED TAXONOMY OR RELATIONSHIPS**

The Master-defined Level-1 systems are retained exactly in meaning. The 100
Level-2 entries below are deterministic review candidates used to give the
local renderer meaningful labels. Placement does not approve evidence or an
economic relationship.

| Level-1 driver | Ten Level-2 candidates | Primary official source families | Posture |
|---|---|---|---|
| Output & Growth | Real GDP Growth; Gross Domestic Income; Industrial Production; Capacity Utilization; Real Final Sales; Manufacturing Output; Services Output; Construction Activity; Business Formation; Regional Output Breadth | BEA, Federal Reserve, Census | CANDIDATE |
| Consumer Demand | Real Personal Consumption; Retail Sales; Services Spending; Disposable Personal Income; Real Wage Purchasing Power; Consumer Credit; Household Saving; Consumer Sentiment; Durable Goods Demand; Housing-Related Spending | BEA, Census, Federal Reserve | CANDIDATE |
| Employer Labor Demand | Job Openings; Hires; Average Weekly Hours; Temporary Help Employment; Overtime Hours; Hiring Plans; Vacancy Duration; Recruiting Intensity; Gross Job Gains; Labor Demand Breadth | BLS JOLTS/CES/BED, DOL | CANDIDATE; some OBS source-backed |
| Layoffs & Job Destruction | Initial Claims; Continued Claims; Layoffs and Discharges; Establishment Closings; Gross Job Losses; Mass Layoff Signals; Permanent Job Losers; Temporary Layoffs; Contraction Breadth; Job-Loss Duration | DOL, BLS JOLTS/BED/CPS | CANDIDATE; some OBS source-backed |
| Business Investment | Equipment Investment; Structures Investment; Intellectual Property Investment; Core Capital Goods Orders; Capital Goods Shipments; Private Construction; Inventory Investment; Business Applications; Manufacturing Backlogs; Investment Intentions | BEA, Census | CANDIDATE |
| Rates & Credit | Policy Rate; Treasury Yield Curve; Corporate Bond Spreads; Bank Lending Standards; Commercial Loan Growth; Consumer Credit Growth; Mortgage Rates; Small-Business Credit; Delinquency Pressure; Financial Conditions | Federal Reserve, Treasury, regulators | CANDIDATE |
| Labor Costs & Wages | Average Hourly Earnings; Employment Cost Index; Benefits Cost; Unit Labor Costs; Real Hourly Compensation; Wage Growth Breadth; Production Worker Earnings; Overtime Pay; Compensation per Hour; Wage-Price Pressure | BLS | CANDIDATE; some OBS source-backed |
| Productivity & Automation | Labor Productivity; Multifactor Productivity; Output per Hour; Capital Deepening; Software Investment; Robotics Adoption; AI-Related Investment; Process Automation; Research and Development; Technology Diffusion | BLS, BEA, Census | CANDIDATE |
| Labor Supply | Labor-Force Participation; Employment-Population Ratio; Working-Age Population; Prime-Age Participation; Migration and Immigration; Educational Attainment; Skills Availability; Retirement Flows; Caregiving Constraints; Geographic Mobility | BLS CPS, Census, education/immigration authorities | CANDIDATE; some OBS source-backed |
| Policy, Trade & External Shocks | Fiscal Policy; Trade Volumes; Tariffs and Restrictions; Energy Supply; Food and Agriculture Supply; Weather Disruption; Public Health Disruption; Geopolitical Risk; Transportation Bottlenecks; Regulatory Change | Treasury, Census/USITC, EIA, USDA, NOAA, FEMA, BTS | CANDIDATE / broad-branch taxonomy risk |

Each machine-readable entry in `persistentWorldModel.ts` carries a stable
candidate ID, parent, definition, source family, and evidence posture. Cadence,
units, geography, exact dataset/series, references, rights, and relationship
evidence must be supplied by later source-specific profiles before promotion.

## Level-3 scaling

The 1,000 Level-3 records in this sprint are deliberately generic renderer
fixtures. Real Level-3 registries should instead be generated and reviewed from
official taxonomies such as BEA industries/commodities, BLS industries and BED
flow elements, Census geographies/trade categories, EIA energy products, and
official component tables. No fixture label can become factual by surviving a
renderer test.
