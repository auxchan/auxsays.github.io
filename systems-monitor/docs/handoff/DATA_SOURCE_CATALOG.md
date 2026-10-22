# Data source catalog

Current repository truth: 160 unique factor labels have candidate dataset profiles, including all 100 Level-2 factors plus reviewed Layoffs expansion paths. Earlier UI/review snapshots displayed 100 paths. Four persistent-world nodes are factually linked and 6 labor readings are accepted. Cataloguing is not ingestion; a factual binding is not a structural relationship.

| Factor | Value / period | Official series |
|---|---|---|
| Payroll Employment | 158,858 thousand; Jul 2026 | BLS CES0000000001 |
| U-3 Unemployment | 4.1%; Jul 2026 | BLS LNS14000000 |
| Labor-Force Participation | 61.4%; Jul 2026 | BLS LNS11300000 |
| Initial Claims | 209,000; week ending 2026-08-08 | DOL ETA |
| Job Openings | 7,359 thousand; Jun 2026 | BLS JTS000000000000000JOL |
| Hires | 5,348 thousand; Jun 2026 | BLS JTS000000000000000HIL |

Official/candidate families include BLS CES/CPS/JOLTS/BED/Productivity/PPI, DOL UI, Census BDS/BFS/economic indicators, BEA, Federal Reserve/SLOOS, U.S. Courts, EIA, USDA, NOAA/FEMA, and BTS. Credentials are environment-only. `AUXSAYS_BEA_USER_ID` and `AUXSAYS_CENSUS_API_KEY` gate implemented candidates; `AUXSAYS_EIA_API_KEY` belongs to a blocked candidate route and is not yet an actionable production requirement. Never print credential-bearing transport URLs.

Machine acquisition URL, human evidence page, and methodology reference are separate fields. Newly retrieved rows remain pending until provenance, rights, unit, period, revision behavior, and acceptance are reviewed.
