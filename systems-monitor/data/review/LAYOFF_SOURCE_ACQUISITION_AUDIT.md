# Layoffs & Job Destruction — Official Source Acquisition Audit

**Audit date:** 2026-08-27  
**Scope:** the ten frozen Level-2 factors and their 100 frozen Level-3 hierarchy placements  
**Artifact status:** review-only source discovery; no source, observation, calculation, relationship, or UI state is accepted by this document

## 1. Outcome

The frozen 10-by-10 branch can be sourced primarily from BLS, DOL, Census, BEA,
the Federal Reserve, U.S. Courts, FEMA, NOAA, and EIA. The official acquisition
surface is viable, but it is not uniformly ready for activation:

- BLS JOLTS, CES, BED, CPS, Productivity, and PPI provide the core labor,
  payroll, hours, productivity, cost, and price evidence.
- DOL provides the authoritative weekly initial and continued-claims evidence.
- Census BDS/BFS and monthly economic-indicator programs provide firm dynamics,
  formations, sales, orders, inventories, and trade candidates.
- BEA provides output, spending, profits, and industry-output candidates.
- Federal Reserve G.17, SLOOS, and H.15 provide production/capacity, bank-credit,
  and interest-rate candidates.
- U.S. Courts provides official bankruptcy filings. Those filings are a legal
  stress indicator, not a count of firm deaths, closures, or layoffs.
- FEMA and NOAA provide event evidence for disaster and operational shocks.
- EIA can support a bounded energy shock measure only after an exact API route,
  facet set, credential path, and rights scope are approved.

The machine-readable acquisition map is
`systems-monitor/data/config/layoffs_source_acquisition_registry.yaml`. It records
all 100 placements and maps each placement to one or more official candidates.

## 2. Non-negotiable acquisition boundaries

1. A hierarchy placement is navigation, not proof of causation.
2. No source candidate becomes an accepted source because it appears here.
3. No value may be displayed before exact source identifier, unit, adjustment,
   represented period, publication time, retrieval time, revision state, rights,
   and provenance pass the binding contracts.
4. A source-family URL is not enough. Collectors must resolve and persist the
   exact series/table/row/facet identifiers selected from official metadata.
5. Machine acquisition, human evidence, and methodology URLs are separate.
6. Credentials are environment variables only. They must not appear in stored
   URLs, logs, snapshots, manifests, or review artifacts.
7. Missing, delayed, discontinued, incomparable, or ambiguous observations stay
   visibly unavailable; they are never filled with fixtures or approximations.
8. Revision-prone sources must preserve every acquired vintage and support both
   as-known-at-time and latest-revised-truth queries.

## 3. Official source acquisition matrix

| Source | Direct acquisition | Human evidence | Methodology | Cadence / revision | Authentication | Rights posture | Current retrieval viability |
|---|---|---|---|---|---|---|---|
| BLS JOLTS | [JT flat files](https://download.bls.gov/pub/time.series/jt/) and [BLS API v2](https://api.bls.gov/publicAPI/v2/timeseries/data/) | [Current JOLTS release](https://www.bls.gov/news.release/jolts.htm) | [JOLTS handbook](https://www.bls.gov/opub/hom/jlt/) | Monthly; preliminary values revise next release | Optional BLS registration key; lower limits without it | Existing BLS review posture | **READY.** June 2026 published 2026-08-04; July scheduled 2026-09-01 |
| DOL weekly claims | [Structured report selector](https://oui.doleta.gov/unemploy/wkclaims/report.asp) | [Official weekly PDF](https://www.dol.gov/ui/data.pdf) | [Claims program page](https://oui.doleta.gov/unemploy/claims.asp) and [archive](https://oui.doleta.gov/unemploy/claims_arch.asp) | Weekly Thursday; advance then revised | None | Existing DOL review posture | **READY, DEGRADED STRUCTURED PATH.** PDF through week ending 2026-08-08; structured XML observed through 2026-07-18 |
| BLS CPS | [LN flat files](https://download.bls.gov/pub/time.series/ln/) and [BLS API v2](https://api.bls.gov/publicAPI/v2/timeseries/data/) | [Employment Situation](https://www.bls.gov/news.release/empsit.htm) | [CPS definitions](https://www.bls.gov/cps/definitions.htm) | Monthly; seasonal factors/population controls can revise history | Optional BLS registration key | Existing BLS review posture | **READY AFTER OFFICIAL METADATA JOIN.** July 2026 published 2026-08-07 |
| BLS CES | [CE flat files](https://download.bls.gov/pub/time.series/ce/) and [BLS API v2](https://api.bls.gov/publicAPI/v2/timeseries/data/) | [Employment Situation](https://www.bls.gov/news.release/empsit.htm) | [CES handbook](https://www.bls.gov/opub/hom/ces/) | Monthly; two monthly revisions and annual benchmark | Optional BLS registration key | Existing BLS review posture | **READY.** July 2026 published 2026-08-07 |
| BLS BED | [BD flat files](https://download.bls.gov/pub/time.series/bd/) | [Current BED release](https://www.bls.gov/news.release/cewbd.nr0.htm) | [BED handbook](https://www.bls.gov/opub/hom/bdm/) | Quarterly with substantial publication lag; history can revise | None | Existing BLS review posture | **READY AFTER OFFICIAL METADATA JOIN.** 2025-Q4 published 2026-07-29; 2026-Q1 scheduled 2026-10-28 |
| Census BDS | [BDS API](https://api.census.gov/data/timeseries/bds) | [BDS data page](https://www.census.gov/programs-surveys/ces/data/public-use-data/experimental-bds.html) | [CES methodology](https://www.census.gov/programs-surveys/ces/technical-documentation/methodology.html) | Annual, lagged; prior years may revise | Census API key | Pending rights acceptance | **READY WITH CREDENTIAL.** Current API reaches reference year 2023 |
| U.S. Courts F-2 | [Current official F-2 page and XLSX discovery](https://www.uscourts.gov/data-news/data-tables/2026/06/30/statistical-tables-federal-judiciary/f-2) | [Bankruptcy filings statistics](https://www.uscourts.gov/data-news/reports/statistical-reports/bankruptcy-filings-statistics) | [Data definitions](https://www.uscourts.gov/data-news/data-tables/data-definitions) | Quarterly rolling 12 months; archived vintages | None | Pending rights acceptance | **READY WITH OFFICIAL-PAGE XLSX DISCOVERY.** Current through 2026-06-30 |
| BEA NIPA | [BEA API](https://apps.bea.gov/api/data) | [GDP](https://www.bea.gov/data/gdp/gross-domestic-product), [Corporate profits](https://www.bea.gov/data/income-saving/corporate-profits), and release pages | [NIPA handbook](https://www.bea.gov/resources/methodologies/nipa-handbook) | Monthly/quarterly by table; advance/second/third and annual/comprehensive revisions | `AUXSAYS_BEA_USER_ID` | Attribution required | **READY WITH CREDENTIAL.** Q2 second GDP/profits and July PIO published 2026-08-26 |
| BEA GDP by Industry | [BEA API](https://apps.bea.gov/api/data) | [GDP by industry](https://www.bea.gov/data/gdp/gdp-industry) | [Industry accounts methodology](https://www.bea.gov/resources/methodologies/industry-economic-accounts) | Quarterly/annual; annual and comprehensive revisions | `AUXSAYS_BEA_USER_ID` | Attribution required | **READY WITH CREDENTIAL**, but exact table/vintage and NAICS crosswalk must be recorded |
| Federal Reserve G.17 | [Current all-tables text](https://www.federalreserve.gov/releases/g17/Current/ipdisk/alltables.txt) | [Current G.17](https://www.federalreserve.gov/releases/g17/current/) | [G.17 technical information](https://www.federalreserve.gov/releases/g17/about.htm) | Monthly; recent and annual revisions | None | Pending rights acceptance | **READY.** July 2026 published/updated 2026-08-18 |
| Federal Reserve SLOOS | [July 2026 release/table package](https://www.federalreserve.gov/data/sloos/sloos-202607.htm) | [SLOOS archive](https://www.federalreserve.gov/data/sloos.htm) | [About SLOOS](https://www.federalreserve.gov/data/sloos/sloos-about.htm) | Quarterly; wording/universe can change | None | Pending rights acceptance | **READY AFTER TABLE-SCHEMA VALIDATION.** July 2026 survey published 2026-08-03 |
| Federal Reserve H.15 | [Data Download Program](https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H15) | [Current H.15](https://www.federalreserve.gov/releases/h15/) | [H.15 description](https://www.federalreserve.gov/releases/h15/about.htm) | Business daily; occasional corrections | None | Pending rights acceptance | **READY AFTER EXACT RATE SELECTION.** Official page current through 2026-08-26 at audit time |
| Census MARTS | [MARTS API](https://api.census.gov/data/timeseries/eits/marts) | [Retail sales](https://www.census.gov/retail/sales.html) | [Survey information](https://www.census.gov/retail/marts/about_the_surveys.html) | Monthly advance, full-survey and annual benchmark revisions | `AUXSAYS_CENSUS_API_KEY` | Pending rights acceptance | **READY WITH CREDENTIAL.** July 2026 published 2026-08-14 |
| Census M3 | [M3 API](https://api.census.gov/data/timeseries/eits/m3) | [Current M3](https://www.census.gov/manufacturing/m3/current/index.html) | [Collection and methodology](https://www.census.gov/manufacturing/m3/how_the_data_are_collected/index.html) | Monthly; advance durable goods then full report; benchmark revisions | `AUXSAYS_CENSUS_API_KEY` | Pending rights acceptance | **READY WITH CREDENTIAL.** July advance 2026-08-26; June full 2026-08-04 |
| Census MTIS | [MTIS API](https://api.census.gov/data/timeseries/eits/mtis) | [Current MTIS](https://www.census.gov/mtis/current/index.html) | [Collection and methodology](https://www.census.gov/mtis/how_the_data_are_collected/index.html) | Monthly; component/annual revisions | `AUXSAYS_CENSUS_API_KEY` | Pending rights acceptance | **READY WITH CREDENTIAL.** June 2026 published 2026-08-14 |
| Census BFS | [BFS API](https://api.census.gov/data/timeseries/eits/bfs) | [Current BFS](https://www.census.gov/econ/bfs/current/index.html) | [BFS methodology](https://www.census.gov/econ/bfs/methodology.html) | Monthly package with weekly estimates; revisions possible | `AUXSAYS_CENSUS_API_KEY` | Pending rights acceptance | **READY WITH CREDENTIAL.** July 2026 published 2026-08-12 |
| Census FTD | [FTD API](https://api.census.gov/data/timeseries/eits/ftd) | [Current trade data](https://www.census.gov/foreign-trade/current/index.html) | [Foreign-trade guide](https://www.census.gov/foreign-trade/guide/index.html) | Monthly advance goods and full release; monthly/annual revisions | `AUXSAYS_CENSUS_API_KEY` | Pending rights acceptance | **READY WITH CREDENTIAL AND CROSSWALK.** June full 2026-08-04; July advance scheduled 2026-08-27 |
| BLS Productivity | [PR flat files](https://download.bls.gov/pub/time.series/pr/) and [BLS API v2](https://api.bls.gov/publicAPI/v2/timeseries/data/) | [Current productivity release](https://www.bls.gov/news.release/prod2.nr0.htm) | [Productivity handbook](https://www.bls.gov/opub/hom/opt/) | Quarterly preliminary/revised plus annual benchmark | Optional BLS registration key | Existing BLS review posture | **READY AFTER OFFICIAL METADATA JOIN.** 2026-Q2 preliminary 2026-08-06; revision 2026-09-03 |
| BLS PPI | [WP flat files](https://download.bls.gov/pub/time.series/wp/) and [BLS API v2](https://api.bls.gov/publicAPI/v2/timeseries/data/) | [Current PPI release](https://www.bls.gov/news.release/ppi.htm) | [PPI handbook](https://www.bls.gov/opub/hom/ppi/) | Monthly; SA values can revise, most NSA values final | Optional BLS registration key | Existing BLS review posture | **READY AFTER OFFICIAL METADATA JOIN.** July 2026 published 2026-08-13 |
| FEMA OpenFEMA | [Disaster Declarations Summaries v2](https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries) | [Official declarations](https://www.fema.gov/disaster/declarations) | [OpenFEMA API](https://www.fema.gov/about/openfema/api) | Event-driven; declarations amend over time | None | Pending rights acceptance | **READY**, with retrieval-time snapshot/versioning |
| NOAA Storm Events | [Official bulk CSV directory](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/) | [Storm Events Database](https://www.ncdc.noaa.gov/stormevents/) | [Storm Data preparation guide](https://www.ncei.noaa.gov/stormevents/pd01016005curr.pdf) | Monthly bulk updates with lag; annual files revise | None | Pending rights acceptance | **READY WITH DYNAMIC FILE DISCOVERY** |
| EIA API v2 | [API root](https://api.eia.gov/v2/) | [EIA](https://www.eia.gov/) | [Open Data documentation](https://www.eia.gov/opendata/documentation.php) | Route-specific | `AUXSAYS_EIA_API_KEY` | Existing approval applies only to already reviewed products | **BLOCKED** until exact route/facets and rights scope are approved |

## 4. Ten Level-2 factors

| Frozen factor | Primary official candidate | Unit / adjustment requirements | Candidate coverage | Activation disposition |
|---|---|---|---|---|
| Layoffs & Discharges | BLS JOLTS | level in thousands and/or rate in percent; SA/NSA explicit; national/industry explicit | Direct monthly national and industry estimates | Source is viable; exact level/rate series must be separately identified |
| Initial UI Claims | DOL weekly claims | claimants, count; SA/NSA explicit; week-ending date | Direct weekly national/state evidence | Existing official evidence path is viable; XML lag must remain visible |
| Continued Claims / Insured Unemployment | DOL weekly claims | continued claimants and insured-unemployment rate; SA/NSA; reference week differs from initial claims | Direct weekly national/state evidence | Viable, but represented-period offsets must be contract-tested |
| Permanent Job Losers | BLS CPS | people in thousands; SA/NSA; monthly reference week | Direct monthly CPS concept/table | Viable after exact LN-series metadata resolution |
| Temporary Layoffs | BLS CPS | people in thousands; SA/NSA; monthly reference week | Direct monthly CPS concept/table | Viable after exact LN-series metadata resolution |
| Gross Job Losses | BLS BED | jobs in thousands and rate in percent; SA/NSA; quarter | Direct quarterly gross-loss measures | Viable but lagged; contraction/closure decomposition must remain explicit |
| Establishment Death / Closure Losses | BLS BED + Census BDS | jobs/establishments; quarterly or annual; generally distinct concepts | BED closures and BDS deaths provide related, not interchangeable, measures | Source identified; blocked from a merged value pending ontology decision |
| Firm Death / Shutdown Stress | Census BDS + U.S. Courts F-2 | firms/establishments/cases; annual vs quarterly; NSA | Firm deaths are available with lag; bankruptcy is current stress context | Source identified; no composite until derivation contract is approved |
| Industry Payroll Contraction | BLS CES | industry employment in thousands; SA; monthly; percent/level change is a CALC | Direct industry payroll series | Viable; industry taxonomy and contraction calculation need accepted definitions |
| Business Failure / Bankruptcy Stress | U.S. Courts F-2 | business cases by chapter; rolling 12 months; NSA | Official quarterly legal-filing counts | Viable as bankruptcy stress only, never as direct layoffs or firm deaths |

## 5. Placement coverage audit

Every frozen Level-2 factor has exactly ten entries in the machine-readable
registry. The placement labels are preserved without renaming or replacing the
approved taxonomy.

| Parent | 10/10 mapped | Strong direct official coverage | Partial/derived coverage | Material caveat |
|---|---:|---|---|---|
| Layoffs & Discharges | Yes | JOLTS, CES, BEA, Census retail, SLOOS, Productivity, Courts | “Business failure stress” is contextual | Mixed cadence; no causal claim |
| Initial UI Claims | Yes | DOL, JOLTS, CPS, CES, BED, BEA, Census, FEMA/NOAA | Establishment deaths and bankruptcy are lagged/contextual | DOL PDF/XML freshness must be split |
| Continued Claims | Yes | DOL, JOLTS, CES, BEA, Census BFS | Consumer demand and regional growth require explicit calculations | Continued-claims reference week differs from initial claims |
| Permanent Job Losers | Yes | CPS, BDS/BED, Courts, CES, BEA, SLOOS | Automation and import pressure are only partial candidates | No official direct “automation layoffs” measure |
| Temporary Layoffs | Yes | CPS, CES, G.17, M3/MTIS, BEA, FEMA/NOAA | Energy shock needs exact EIA/PPI definition | Short-run co-movement is not causation |
| Gross Job Losses | Yes | BED, BEA, Census, SLOOS, Productivity, PPI | Trade pressure requires a crosswalk | Closure and contraction components must not be double-counted |
| Establishment Death / Closure Losses | Yes | BED/BDS, Courts, BEA, SLOOS, H.15, Census, PPI, FEMA/NOAA | Sales/revenue is program-specific | Closure, death, bankruptcy, and job loss are not synonyms |
| Firm Death / Shutdown Stress | Yes | BDS, Courts, BEA, H.15, SLOOS, Census, PPI | Composite “stress” would be a governed CALC | Annual BDS data are structurally lagged |
| Industry Payroll Contraction | Yes | CES, BEA Industry, M3, JOLTS, BED, G.17, Productivity, PPI, FTD | Industry credit is not available at comparable granularity from SLOOS | Cross-program NAICS concordance is required |
| Business Failure / Bankruptcy Stress | Yes | Courts, BEA, H.15, SLOOS, Census, PPI, Productivity | Broad sales/revenue is not one universal series | Filings measure legal cases, not operating shutdowns |

## 6. Exact-series and schema decisions still required

These are implementation gates, not reasons to invent values:

1. **JOLTS:** bind separately to layoffs-and-discharges level and rate series,
   and to job-openings and hires rate series. National totals and industry
   series cannot share one identifier.
2. **CPS:** resolve Permanent Job Losers and Temporary Layoffs from the official
   `ln.series` metadata and persist the exact official series keys. Do not infer
   keys from table labels.
3. **BED:** resolve gross job losses, contractions, closing establishments, and
   establishment deaths through the official BD metadata files. Preserve the
   agency’s distinctions among establishment contraction, closure, and death.
4. **CES:** use direct industry employment series; calculate contraction from
   accepted observations with explicit comparison windows. “Contraction” is not
   itself a raw CES observation.
5. **Census BDS:** query official variables such as job destruction and deaths
   only after the current variables catalog is captured and API-key behavior is
   tested. Annual BDS cannot masquerade as a live monthly signal.
6. **Census EITS:** each program has its own variable catalog and revision
   behavior. A generic EITS URL is not sufficient provenance.
7. **BEA:** select exact dataset/table/line/frequency parameters and strip the
   UserID from persisted URLs and logs.
8. **SLOOS:** bind by official question wording/identifier, not visual row
   position, because questions and respondent universes change.
9. **U.S. Courts:** discover the official XLSX link from the dated table page,
   hash it, and preserve the dated page as human evidence.
10. **EIA:** approve one exact route/facet/series and verify the rights scope
    before using an energy measure.

## 7. Currentness and revision behavior

- **Near-real-time sources:** DOL claims are weekly; H.15 is business-daily;
  disaster declarations are event-driven. Their faster cadence does not make
  slower monthly, quarterly, or annual factors stale by definition.
- **Monthly sources:** JOLTS, CES/CPS, PPI, G.17, Census MARTS/M3/MTIS/BFS/FTD,
  and BEA PIO have different reference periods and release days. The interface
  must show each factor’s own represented period and publication time.
- **Quarterly sources:** BED, Productivity, SLOOS, GDP/corporate profits,
  GDP-by-industry, and U.S. Courts F-2 require vintage-aware handling.
- **Annual source:** BDS is structurally lagged. Its currentness state should say
  “latest official annual vintage,” not “live” and not “stale” merely because it
  does not update monthly.
- **DOL exception:** at audit time the official PDF was newer than the structured
  XML path. The correct behavior is to retain the current PDF observation while
  separately flagging the automated structured acquisition path as stale.

## 8. Rights and credential disposition

The existing BLS and DOL policies may be reused only where the current rights
registry already covers the exact product. BEA data requires attribution. New
Census, Federal Reserve, U.S. Courts, FEMA, and NOAA products remain
`PENDING_RIGHTS_REVIEW` until they receive explicit registry acceptance. An
existing EIA approval does not automatically cover an unreviewed API route.

Credential names proposed for configuration only:

- `AUXSAYS_CENSUS_API_KEY`
- `AUXSAYS_BEA_USER_ID` (existing convention)
- `AUXSAYS_EIA_API_KEY`

No credential value was used, written, or requested in this audit.

Official usage and attribution references include the [BLS copyright
information](https://www.bls.gov/opub/copyright-information.htm), [BLS API terms
of service](https://www.bls.gov/developers/termsOfService.htm), and [BEA data
use/attribution FAQ](https://www.bea.gov/index.php/help/faq/145). Each additional
agency’s exact product rights must be entered into the binding rights registry
before activation.

## 9. Blockers

1. Census API acquisition now requires a key; none is embedded here.
2. BEA API acquisition requires the existing UserID credential path.
3. EIA energy coverage lacks an approved exact route/facet and rights scope.
4. CPS and BED exact series identifiers require authoritative metadata joins.
5. Industry credit conditions lack an official industry-granular equivalent to
   the proposed industry detail; SLOOS is aggregate only.
6. Import exposure requires an accepted commodity/industry crosswalk and a
   governed derivation.
7. “Productivity / Automation” has a defensible official productivity source,
   but not a direct official automation-intensity measure in this audit.
8. Broad sales/revenue does not have one universal official series. It must be
   scoped to a specific official program/sector or remain unavailable.
9. Bankruptcy, firm death, establishment death, closure, contraction, and job
   loss are distinct concepts and cannot be collapsed into one raw observation.
10. New agency products require explicit rights acceptance before publication.

## 10. Recommended bounded acquisition order

1. Reuse accepted DOL initial-claims observations and add continued-claims fields
   only after the represented-period offset is tested.
2. Bind JOLTS layoffs-and-discharges level/rate with exact series metadata.
3. Bind CPS permanent-job-losers and temporary-layoffs from official LN metadata.
4. Bind CES industry payroll and compute contraction transparently.
5. Bind BED gross job losses and its closure/contraction components.
6. Add Courts F-2 strictly as bankruptcy stress.
7. Add BDS deaths and firm-age/size context with its annual-lag disclosure.
8. Add contextual BEA, Federal Reserve, Census, PPI/Productivity, and disaster
   candidates one source family at a time, with separate rights and schema gates.
9. Leave EIA and industry-credit/import-exposure gaps visibly unconnected until
   their exact routes and derivations are approved.

This order creates useful factual connective tissue without pretending the full
100-placement taxonomy is already populated or causally proven.
