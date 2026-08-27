export type PersistentWorldSourceReadiness = "CANDIDATE_DATASET" | "DERIVATION_REQUIRED";

export interface PersistentWorldCandidateSourceProfile {
  readiness: PersistentWorldSourceReadiness;
  authority: string;
  dataset: string;
  cadence: string;
  summary: string;
  evidenceUrl: string;
  methodologyUrl?: string;
  registrationState: "CANDIDATE_NOT_REGISTERED" | "SOURCE_DESIGN_REQUIRED";
}

const profiles = {
  "bea-nipa": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Economic Analysis", dataset: "National Income and Product Accounts", cadence: "Monthly / quarterly, series dependent", summary: "Official national output, income, consumption, saving, and investment accounts.", evidenceUrl: "https://www.bea.gov/itable/national-gdp-and-personal-income", methodologyUrl: "https://www.bea.gov/resources/methodologies/nipa-handbook", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bea-regional": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Economic Analysis", dataset: "Regional GDP and Personal Income", cadence: "Quarterly / annual", summary: "Official state and regional output records for breadth and geographic comparison.", evidenceUrl: "https://www.bea.gov/itable/regional-gdp-and-personal-income", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "fed-g17": { readiness: "CANDIDATE_DATASET", authority: "Federal Reserve Board", dataset: "Industrial Production and Capacity Utilization (G.17)", cadence: "Monthly", summary: "Official production, manufacturing, capacity, and utilization indexes.", evidenceUrl: "https://www.federalreserve.gov/releases/g17/current/", methodologyUrl: "https://www.federalreserve.gov/releases/g17/about.htm", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "census-economic": { readiness: "CANDIDATE_DATASET", authority: "U.S. Census Bureau", dataset: "Business and Industry Economic Indicators", cadence: "Monthly / quarterly, survey dependent", summary: "Official retail, services, manufacturing, construction, and trade indicators.", evidenceUrl: "https://www.census.gov/econ_datasets/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "census-bfs": { readiness: "CANDIDATE_DATASET", authority: "U.S. Census Bureau", dataset: "Business Formation Statistics", cadence: "Weekly / monthly", summary: "Official business-application and formation statistics.", evidenceUrl: "https://www.census.gov/econ/bfs/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "fed-g19": { readiness: "CANDIDATE_DATASET", authority: "Federal Reserve Board", dataset: "Consumer Credit (G.19)", cadence: "Monthly", summary: "Official revolving and nonrevolving consumer-credit aggregates.", evidenceUrl: "https://www.federalreserve.gov/releases/g19/current/", methodologyUrl: "https://www.federalreserve.gov/releases/g19/about.htm", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bls-jolts": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Labor Statistics", dataset: "Job Openings and Labor Turnover Survey", cadence: "Monthly", summary: "Official job openings, hires, quits, layoffs, and separations estimates.", evidenceUrl: "https://www.bls.gov/jlt/", methodologyUrl: "https://www.bls.gov/opub/hom/jlt/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bls-ces": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Labor Statistics", dataset: "Current Employment Statistics", cadence: "Monthly", summary: "Official payroll employment, hours, and earnings estimates.", evidenceUrl: "https://www.bls.gov/ces/", methodologyUrl: "https://www.bls.gov/opub/hom/ces/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bls-bed": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Labor Statistics", dataset: "Business Employment Dynamics", cadence: "Quarterly", summary: "Official gross job gains and losses from openings, expansions, closings, and contractions.", evidenceUrl: "https://www.bls.gov/bdm/", methodologyUrl: "https://www.bls.gov/bdm/bdmover.htm", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bls-cps": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Labor Statistics / U.S. Census Bureau", dataset: "Current Population Survey", cadence: "Monthly", summary: "Official household labor-force, employment, unemployment, and demographic estimates.", evidenceUrl: "https://www.bls.gov/cps/", methodologyUrl: "https://www.bls.gov/opub/hom/cps/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "dol-claims": { readiness: "CANDIDATE_DATASET", authority: "U.S. Department of Labor", dataset: "Unemployment Insurance Weekly Claims", cadence: "Weekly", summary: "Official advance and revised unemployment-insurance claims releases.", evidenceUrl: "https://www.dol.gov/ui/data.pdf", methodologyUrl: "https://oui.doleta.gov/unemploy/claims.asp", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bea-fixed": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Economic Analysis", dataset: "Fixed Assets Accounts / NIPA investment tables", cadence: "Quarterly / annual", summary: "Official investment and capital-stock records by asset class.", evidenceUrl: "https://www.bea.gov/itable/fixed-assets", methodologyUrl: "https://www.bea.gov/resources/methodologies/nipa-handbook", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "census-m3": { readiness: "CANDIDATE_DATASET", authority: "U.S. Census Bureau", dataset: "Manufacturers' Shipments, Inventories, and Orders (M3)", cadence: "Monthly", summary: "Official manufacturing orders, shipments, inventories, and unfilled-orders records.", evidenceUrl: "https://www.census.gov/manufacturing/m3/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "census-construction": { readiness: "CANDIDATE_DATASET", authority: "U.S. Census Bureau", dataset: "Construction Spending", cadence: "Monthly", summary: "Official value-of-construction-put-in-place estimates.", evidenceUrl: "https://www.census.gov/constructionspending/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "fed-h15": { readiness: "CANDIDATE_DATASET", authority: "Federal Reserve Board / U.S. Treasury", dataset: "Selected Interest Rates (H.15) and Treasury yield data", cadence: "Daily / weekly", summary: "Official policy and market interest-rate records.", evidenceUrl: "https://www.federalreserve.gov/releases/h15/", methodologyUrl: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "fed-sloos": { readiness: "CANDIDATE_DATASET", authority: "Federal Reserve Board", dataset: "Senior Loan Officer Opinion Survey", cadence: "Quarterly", summary: "Official bank-reported changes in lending standards and demand.", evidenceUrl: "https://www.federalreserve.gov/data/sloos.htm", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "fed-h8": { readiness: "CANDIDATE_DATASET", authority: "Federal Reserve Board", dataset: "Assets and Liabilities of Commercial Banks (H.8)", cadence: "Weekly", summary: "Official commercial-bank loan and balance-sheet aggregates.", evidenceUrl: "https://www.federalreserve.gov/releases/h8/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "fdic-call": { readiness: "CANDIDATE_DATASET", authority: "Federal Deposit Insurance Corporation", dataset: "Call Report / Bank Data", cadence: "Quarterly", summary: "Official bank condition, loan-performance, and delinquency records.", evidenceUrl: "https://www.fdic.gov/bank-data-guide", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "chicago-nfci": { readiness: "CANDIDATE_DATASET", authority: "Federal Reserve Bank of Chicago", dataset: "National Financial Conditions Index", cadence: "Weekly", summary: "A Federal Reserve Bank index summarizing U.S. financial conditions.", evidenceUrl: "https://www.chicagofed.org/research/data/nfci/current-data", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bls-eci": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Labor Statistics", dataset: "Employment Cost Index / Employer Costs for Employee Compensation", cadence: "Quarterly", summary: "Official wage, salary, benefit, and total-compensation cost measures.", evidenceUrl: "https://www.bls.gov/eci/", methodologyUrl: "https://www.bls.gov/opub/hom/eci/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bls-productivity": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Labor Statistics", dataset: "Labor Productivity and Costs", cadence: "Quarterly", summary: "Official output-per-hour, compensation, and unit-labor-cost estimates.", evidenceUrl: "https://www.bls.gov/productivity/", methodologyUrl: "https://www.bls.gov/opub/hom/lpr/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bls-mfp": { readiness: "CANDIDATE_DATASET", authority: "U.S. Bureau of Labor Statistics", dataset: "Multifactor Productivity", cadence: "Annual", summary: "Official productivity contributions from capital, labor, and intermediate inputs.", evidenceUrl: "https://www.bls.gov/productivity/multifactor-productivity.htm", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "census-technology": { readiness: "CANDIDATE_DATASET", authority: "U.S. Census Bureau", dataset: "Annual Business Survey / Business Trends and Outlook Survey", cadence: "Biweekly / annual, measure dependent", summary: "Official business technology, innovation, investment, and operating-condition measures.", evidenceUrl: "https://www.census.gov/programs-surveys/abs.html", methodologyUrl: "https://www.census.gov/hfp/btos.html", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "census-population": { readiness: "CANDIDATE_DATASET", authority: "U.S. Census Bureau", dataset: "American Community Survey / Population Estimates", cadence: "Annual", summary: "Official population, migration, education, and geographic-mobility estimates.", evidenceUrl: "https://www.census.gov/programs-surveys/acs/data.html", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "treasury-mts": { readiness: "CANDIDATE_DATASET", authority: "U.S. Department of the Treasury", dataset: "Monthly Treasury Statement / Fiscal Data", cadence: "Monthly", summary: "Official federal receipts, outlays, deficit, and financing records.", evidenceUrl: "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "census-trade": { readiness: "CANDIDATE_DATASET", authority: "U.S. Census Bureau / U.S. Bureau of Economic Analysis", dataset: "U.S. International Trade in Goods and Services", cadence: "Monthly", summary: "Official import and export value and volume records.", evidenceUrl: "https://www.census.gov/foreign-trade/data/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "usitc-hts": { readiness: "CANDIDATE_DATASET", authority: "U.S. International Trade Commission", dataset: "Harmonized Tariff Schedule", cadence: "Revision driven", summary: "Official tariff classifications, rates, and revision records.", evidenceUrl: "https://hts.usitc.gov/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "eia-open": { readiness: "CANDIDATE_DATASET", authority: "U.S. Energy Information Administration", dataset: "EIA Open Data", cadence: "Hourly to annual, series dependent", summary: "Official electricity, petroleum, natural-gas, coal, and energy-outlook data.", evidenceUrl: "https://www.eia.gov/opendata/", methodologyUrl: "https://www.eia.gov/opendata/documentation.php", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "usda-wasde": { readiness: "CANDIDATE_DATASET", authority: "U.S. Department of Agriculture", dataset: "World Agricultural Supply and Demand Estimates", cadence: "Monthly", summary: "Official crop, livestock, and food-commodity supply-and-use estimates.", evidenceUrl: "https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "noaa-events": { readiness: "CANDIDATE_DATASET", authority: "National Oceanic and Atmospheric Administration", dataset: "Storm Events Database / climate hazard records", cadence: "Event driven", summary: "Official severe-weather event and impact records.", evidenceUrl: "https://www.ncei.noaa.gov/stormevents/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "cdc-surveillance": { readiness: "CANDIDATE_DATASET", authority: "Centers for Disease Control and Prevention", dataset: "CDC Data and Surveillance", cadence: "Varies by surveillance system", summary: "Official public-health surveillance and burden indicators.", evidenceUrl: "https://data.cdc.gov/", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "bts-tsi": { readiness: "CANDIDATE_DATASET", authority: "Bureau of Transportation Statistics", dataset: "Freight Transportation Services Index", cadence: "Monthly", summary: "Official for-hire freight-volume index across major transportation modes.", evidenceUrl: "https://www.bts.gov/topics/transportation-and-economy/transportation-measures-economic-activity", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "federal-register": { readiness: "CANDIDATE_DATASET", authority: "Office of the Federal Register / GPO", dataset: "Federal Register API", cadence: "Daily", summary: "Official rules, proposed rules, notices, and presidential-document metadata.", evidenceUrl: "https://www.federalregister.gov/developers/documentation/api/v1", registrationState: "CANDIDATE_NOT_REGISTERED" },
  "design-required": { readiness: "DERIVATION_REQUIRED", authority: "No single accepted authority", dataset: "Derived indicator design required", cadence: "Not established", summary: "This concept requires a documented combination, rights review, and validation plan before it can become a data claim.", evidenceUrl: "https://www.usa.gov/agency-index", registrationState: "SOURCE_DESIGN_REQUIRED" }
} as const satisfies Record<string, PersistentWorldCandidateSourceProfile>;

const sourceKeyByFactor = new Map<string, keyof typeof profiles>();
function assign(key: keyof typeof profiles, labels: readonly string[]) { labels.forEach((label) => sourceKeyByFactor.set(label, key)); }

assign("bea-nipa", ["Real GDP Growth", "Gross Domestic Income", "Real Final Sales", "Services Output", "Real Personal Consumption", "Services Spending", "Disposable Personal Income", "Real Wage Purchasing Power", "Household Saving"]);
assign("fed-g17", ["Industrial Production", "Capacity Utilization", "Manufacturing Output"]);
assign("census-construction", ["Construction Activity", "Private Construction"]);
assign("census-bfs", ["Business Formation", "Business Applications"]);
assign("bea-regional", ["Regional Output Breadth"]);
assign("census-economic", ["Retail Sales", "Durable Goods Demand", "Housing-Related Spending"]);
assign("fed-g19", ["Consumer Credit", "Consumer Credit Growth"]);
assign("bls-jolts", ["Job Openings", "Hires", "Layoffs and Discharges"]);
assign("bls-ces", ["Average Weekly Hours", "Temporary Help Employment", "Overtime Hours", "Average Hourly Earnings", "Production Worker Earnings", "Overtime Pay"]);
assign("bls-bed", ["Gross Job Gains", "Establishment Closings", "Gross Job Losses", "Contraction Breadth"]);
assign("dol-claims", ["Initial Claims", "Continued Claims"]);
assign("bls-cps", ["Permanent Job Losers", "Temporary Layoffs", "Job-Loss Duration", "Labor-Force Participation", "Employment-Population Ratio", "Working-Age Population", "Prime-Age Participation", "Retirement Flows", "Caregiving Constraints"]);
assign("bea-fixed", ["Equipment Investment", "Structures Investment", "Intellectual Property Investment", "Inventory Investment", "Software Investment", "AI-Related Investment", "Research and Development"]);
assign("census-m3", ["Core Capital Goods Orders", "Capital Goods Shipments", "Manufacturing Backlogs"]);
assign("fed-h15", ["Policy Rate", "Treasury Yield Curve"]);
assign("fed-sloos", ["Bank Lending Standards", "Small-Business Credit"]);
assign("fed-h8", ["Commercial Loan Growth"]);
assign("fdic-call", ["Delinquency Pressure"]);
assign("chicago-nfci", ["Financial Conditions"]);
assign("bls-eci", ["Employment Cost Index", "Benefits Cost", "Wage Growth Breadth", "Wage-Price Pressure"]);
assign("bls-productivity", ["Unit Labor Costs", "Real Hourly Compensation", "Compensation per Hour", "Labor Productivity", "Output per Hour"]);
assign("bls-mfp", ["Multifactor Productivity", "Capital Deepening"]);
assign("census-technology", ["Robotics Adoption", "Process Automation", "Technology Diffusion"]);
assign("census-population", ["Migration and Immigration", "Educational Attainment", "Geographic Mobility"]);
assign("treasury-mts", ["Fiscal Policy"]);
assign("census-trade", ["Trade Volumes"]);
assign("usitc-hts", ["Tariffs and Restrictions"]);
assign("eia-open", ["Energy Supply"]);
assign("usda-wasde", ["Food and Agriculture Supply"]);
assign("noaa-events", ["Weather Disruption"]);
assign("cdc-surveillance", ["Public Health Disruption"]);
assign("bts-tsi", ["Transportation Bottlenecks"]);
assign("federal-register", ["Regulatory Change"]);
assign("design-required", ["Consumer Sentiment", "Hiring Plans", "Vacancy Duration", "Recruiting Intensity", "Labor Demand Breadth", "Mass Layoff Signals", "Investment Intentions", "Corporate Bond Spreads", "Mortgage Rates", "Skills Availability", "Geopolitical Risk"]);

export function persistentWorldCandidateSourceProfile(label: string): PersistentWorldCandidateSourceProfile | undefined {
  const key = sourceKeyByFactor.get(label);
  return key ? profiles[key] : undefined;
}

export const PERSISTENT_WORLD_PROFILED_FACTOR_COUNT = sourceKeyByFactor.size;
