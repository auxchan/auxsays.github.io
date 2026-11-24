export const LAYOFFS_JOB_DESTRUCTION_DRIVER_ID = "layoffs-job-destruction" as const;

export interface LayoffsBranchPlacementCandidate {
  readonly label: string;
  readonly canonicalFactorId: string;
  readonly placementSlug: string;
}

export interface LayoffsBranchGroup {
  readonly id: string;
  readonly label: string;
  readonly definition: string;
  readonly sourceFamily: string;
  readonly placements: readonly LayoffsBranchPlacementCandidate[];
}

const slug = (value: string) => value.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

// Canonical aliases are intentionally narrow. They cover only reviewed cases
// where different hierarchy labels refer to the same underlying factor. The
// placement label remains available to the UI under UX-060.
export const layoffsCanonicalAliases: Readonly<Record<string, string>> = Object.freeze({
  "Initial UI Claims": "Initial Claims",
  "Closing Establishment Losses": "Establishment Closures",
  "Payroll Growth": "Total Nonfarm Payroll Change",
  "Business Formations": "Business Formations Within 4 Quarters",
  "Business Formation": "Business Formations Within 4 Quarters",
  "Regional Employment Growth": "State-Level Payroll Growth Breadth",
  "Import / Trade Pressure": "Trade / Import Pressure",
  "Industry Payroll Contraction": "Payroll Contraction Breadth",
  "Establishment Deaths": "Jobs Lost at Establishment Deaths",
  "Business Bankruptcy Stress": "Business Bankruptcy Filings, 12-Month Total",
  "Real Output Growth": "Real GDP Growth",
  "Consumer Demand": "Real Personal Consumption Expenditures Growth",
  "Disaster / Operational Shock": "FEMA Disaster Declaration"
});

export const layoffsCanonicalFactorMigration: Readonly<Record<string, string>> = Object.freeze({
  "factor:canonical:payroll-growth": "factor:canonical:total-nonfarm-payroll-change",
  "factor:canonical:business-formation": "factor:canonical:business-formations-within-4-quarters",
  "factor:canonical:business-formations": "factor:canonical:business-formations-within-4-quarters",
  "factor:canonical:regional-employment-growth": "factor:canonical:state-level-payroll-growth-breadth",
  "factor:canonical:industry-payroll-contraction": "factor:canonical:payroll-contraction-breadth",
  "factor:canonical:establishment-deaths": "factor:canonical:jobs-lost-at-establishment-deaths",
  "factor:canonical:business-bankruptcy-stress": "factor:canonical:business-bankruptcy-filings-12-month-total",
  "factor:canonical:real-output-growth": "factor:canonical:real-gdp-growth",
  "factor:canonical:consumer-demand": "factor:canonical:real-personal-consumption-expenditures-growth",
  "factor:canonical:disaster-operational-shock": "factor:canonical:fema-disaster-declaration"
});

const stablePlacementSlugs: Readonly<Record<string, string>> = Object.freeze({
  "Total Nonfarm Payroll Change": "payroll-growth",
  "Business Formations Within 4 Quarters": "business-formations",
  "Business Formation": "business-formation",
  "State-Level Payroll Growth Breadth": "regional-employment-growth",
  "Payroll Contraction Breadth": "industry-payroll-contraction",
  "Jobs Lost at Establishment Deaths": "establishment-deaths",
  "Business Bankruptcy Filings, 12-Month Total": "business-bankruptcy-stress",
  "Real GDP Growth": "real-output-growth",
  "Real Personal Consumption Expenditures Growth": "consumer-demand",
  "FEMA Disaster Declaration": "disaster-operational-shock"
});

export function layoffsCanonicalLabel(label: string) {
  return layoffsCanonicalAliases[label] ?? label;
}

export function layoffsSearchAliasesForFactorId(canonicalFactorId: string) {
  return Object.entries(layoffsCanonicalAliases)
    .filter(([, canonicalLabel]) => layoffsCanonicalFactorId(canonicalLabel) === canonicalFactorId)
    .map(([alias]) => alias);
}

export function layoffsCanonicalFactorId(label: string) {
  return `factor:canonical:${slug(layoffsCanonicalLabel(label))}`;
}

export function layoffsResolveCanonicalFactorId(canonicalFactorId: string) {
  return layoffsCanonicalFactorMigration[canonicalFactorId] ?? canonicalFactorId;
}

function placement(label: string): LayoffsBranchPlacementCandidate {
  return Object.freeze({ label, canonicalFactorId: layoffsCanonicalFactorId(label), placementSlug: stablePlacementSlugs[label] ?? slug(label) });
}

function group(id: string, label: string, definition: string, sourceFamily: string, labels: readonly string[]): LayoffsBranchGroup {
  return Object.freeze({ id, label, definition, sourceFamily, placements: Object.freeze(labels.map(placement)) });
}

export const layoffsBranchTaxonomy: readonly LayoffsBranchGroup[] = Object.freeze([
  group(
    "layoffs-and-discharges",
    "Layoffs & Discharges",
    "Employer-initiated separations measured by the official JOLTS layoffs and discharges series.",
    "BLS JOLTS; BEA; Census; BLS CES/Productivity; Federal Reserve SLOOS; U.S. Courts",
    ["Real GDP Growth", "Consumer Spending", "Retail Sales", "Job Openings Rate", "Hires Rate", "Average Weekly Hours", "Corporate Profits", "C&I Lending Standards", "Unit Labor Costs", "Business Failure Stress"]
  ),
  group(
    "initial-ui-claims",
    "Initial UI Claims",
    "New entries into insured unemployment after a separation; this measures claims activity, not job destruction accounting.",
    "U.S. Department of Labor ETA; BLS JOLTS/CPS/CES/BED; BEA; disaster authorities",
    ["Layoffs & Discharges", "Temporary Layoffs", "Permanent Job Losers", "Payroll Contraction Breadth", "Gross Job Losses", "Jobs Lost at Establishment Deaths", "Business Bankruptcy Filings, 12-Month Total", "Real GDP Growth", "Real Personal Consumption Expenditures Growth", "FEMA Disaster Declaration"]
  ),
  group(
    "continued-claims-insured-unemployment",
    "Continued Claims / Insured Unemployment",
    "The persistence of insured unemployment and the capacity of the labor market to return claimants to work.",
    "U.S. Department of Labor ETA; BLS JOLTS/CES; Census; BEA",
    ["Initial Claims", "Hires Rate", "Job Openings Rate", "Total Nonfarm Payroll Change", "Temporary Help Employment", "Average Weekly Hours", "Business Formations Within 4 Quarters", "Real GDP Growth", "Real Personal Consumption Expenditures Growth", "State-Level Payroll Growth Breadth"]
  ),
  group(
    "permanent-job-losers",
    "Permanent Job Losers",
    "People whose employment ended involuntarily and who do not expect recall to the former job.",
    "BLS CPS/BED/CES/Productivity; Census BDS/trade; U.S. Courts; Federal Reserve; BEA",
    ["Jobs Lost at Establishment Deaths", "Firm Deaths", "Business Bankruptcy Filings, 12-Month Total", "Payroll Contraction Breadth", "Gross Job Losses", "Productivity / Automation", "Import / Trade Pressure", "C&I Credit Conditions", "Corporate Profitability", "Real GDP Growth"]
  ),
  group(
    "temporary-layoffs",
    "Temporary Layoffs",
    "People separated from work who expect recall, distinguished from permanent job loss.",
    "BLS CPS/CES; Federal Reserve; Census; BEA; EIA and disaster authorities",
    ["Average Weekly Hours", "Industrial Production", "Capacity Utilization", "New Orders", "Inventory / Sales Balance", "Real Personal Consumption Expenditures Growth", "Manufacturing Output", "Energy / Input Shock", "Disaster / Weather Shock", "Payroll Contraction Breadth"]
  ),
  group(
    "gross-job-losses",
    "Gross Job Losses",
    "Employment losses at contracting and closing establishments before gross gains are netted against them.",
    "BLS BED; BEA; Census; Federal Reserve SLOOS; BLS Productivity/PPI",
    ["Establishment Contractions", "Establishment Closures", "Real GDP Growth", "Consumer Spending", "New Orders", "Corporate Profits", "C&I Lending Standards", "Unit Labor Costs", "Producer Input Prices", "Trade / Import Pressure"]
  ),
  group(
    "establishment-death-closure-losses",
    "Establishment Death / Closure Losses",
    "Employment losses associated with closing establishments and permanent establishment exits.",
    "BLS BED; Census BDS/BFS; U.S. Courts; BEA; Federal Reserve; BLS PPI; disaster authorities",
    ["Closing Establishment Losses", "Business Bankruptcy Filings, 12-Month Total", "Corporate Profitability", "C&I Lending Standards", "Borrowing Costs", "Sales / Revenue Growth", "Producer Input Prices", "Business Formation / Dynamism", "Firm Age / Size Vulnerability", "Disaster / External Shock"]
  ),
  group(
    "firm-death-shutdown-stress",
    "Firm Death / Shutdown Stress",
    "Conditions associated with permanent firm exit and shutdown pressure, without equating a stress signal to an observed closure.",
    "Census BDS; U.S. Courts; BLS BED; BEA; Federal Reserve; Census economic indicators",
    ["Jobs Lost at Establishment Deaths", "Business Bankruptcy Filings", "Corporate Profits", "Interest Rates", "C&I Lending Standards", "Sales / Revenue", "Input Costs", "Inventory / Sales Imbalance", "Firm Age / Size", "Trade / External Shock"]
  ),
  group(
    "industry-payroll-contraction",
    "Industry Payroll Contraction",
    "Pending governed calculation: the share of a versioned, mutually exclusive national CES industry universe with lower accepted seasonally adjusted payroll employment than in the prior compatible month.",
    "BLS CES/JOLTS/BED/Productivity/PPI; BEA industry accounts; Census; Federal Reserve",
    ["Industry Output", "Industry Sales / Shipments", "Industry New Orders", "Industry Layoffs & Discharges", "Industry Gross Job Losses", "Industry Capacity Utilization", "Industry Unit Labor Costs", "Industry Input Prices", "Import Exposure", "Industry Credit Conditions"]
  ),
  group(
    "business-failure-bankruptcy-stress",
    "Business Failure / Bankruptcy Stress",
    "A leading stress context for potential business distress; it is not a direct measure of layoffs, firm death, or establishment death.",
    "U.S. Courts; BEA; Federal Reserve; Census; BLS Productivity/PPI",
    ["Corporate Profits", "Interest Rates", "C&I Lending Standards", "C&I Loan Demand", "Sales / Revenue", "Producer Input Costs", "Unit Labor Costs", "Inventory / Sales Ratio", "Business Formation", "Real GDP Growth"]
  )
]);

const legacyLevel2PlacementSlugs = Object.freeze(["initial-claims", "continued-claims", "layoffs-and-discharges", "establishment-closings", "gross-job-losses", "mass-layoff-signals", "permanent-job-losers", "temporary-layoffs", "contraction-breadth", "job-loss-duration"]);

export const layoffsBranchPlacementMigration: Readonly<Record<string, string>> = Object.freeze(Object.fromEntries(
  layoffsBranchTaxonomy.flatMap((item, groupIndex) => [
    [`placement:${LAYOFFS_JOB_DESTRUCTION_DRIVER_ID}:${legacyLevel2PlacementSlugs[groupIndex]}`, `placement:${LAYOFFS_JOB_DESTRUCTION_DRIVER_ID}:${item.id}`] as const,
    ...item.placements.map((candidate, placementIndex) => [
      `fixture-placement:${LAYOFFS_JOB_DESTRUCTION_DRIVER_ID}:${String(groupIndex + 1).padStart(2, "0")}:${String(placementIndex + 1).padStart(2, "0")}`,
      `placement:${LAYOFFS_JOB_DESTRUCTION_DRIVER_ID}:${item.id}:${candidate.placementSlug}`
    ] as const)
  ])
));

export const layoffsBranchCanonicalFactors = Object.freeze(
  Array.from(new Map(
    layoffsBranchTaxonomy.flatMap((item) => [
      [layoffsCanonicalFactorId(item.label), layoffsCanonicalLabel(item.label)] as const,
      ...item.placements.map((candidate) => [candidate.canonicalFactorId, layoffsCanonicalLabel(candidate.label)] as const)
    ])
  ).entries()).map(([id, label]) => Object.freeze({ id, label }))
);
