export const LAYOFFS_JOB_DESTRUCTION_DRIVER_ID = "layoffs-job-destruction" as const;

export interface LayoffsBranchPlacementCandidate {
  readonly label: string;
  readonly canonicalFactorId: string;
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
const canonicalAliases: Readonly<Record<string, string>> = Object.freeze({
  "Initial UI Claims": "Initial Claims",
  "Closing Establishment Losses": "Establishment Closures",
  "Business Formations": "Business Formation",
  "Import / Trade Pressure": "Trade / Import Pressure"
});

export function layoffsCanonicalLabel(label: string) {
  return canonicalAliases[label] ?? label;
}

export function layoffsCanonicalFactorId(label: string) {
  return `factor:canonical:${slug(layoffsCanonicalLabel(label))}`;
}

function placement(label: string): LayoffsBranchPlacementCandidate {
  return Object.freeze({ label, canonicalFactorId: layoffsCanonicalFactorId(label) });
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
    ["Real Output Growth", "Consumer Spending", "Retail Sales", "Job Openings Rate", "Hires Rate", "Average Weekly Hours", "Corporate Profits", "C&I Lending Standards", "Unit Labor Costs", "Business Failure Stress"]
  ),
  group(
    "initial-ui-claims",
    "Initial UI Claims",
    "New entries into insured unemployment after a separation; this measures claims activity, not job destruction accounting.",
    "U.S. Department of Labor ETA; BLS JOLTS/CPS/CES/BED; BEA; disaster authorities",
    ["Layoffs & Discharges", "Temporary Layoffs", "Permanent Job Losers", "Industry Payroll Contraction", "Gross Job Losses", "Establishment Deaths", "Business Bankruptcy Stress", "Real Output Growth", "Consumer Demand", "Disaster / Operational Shock"]
  ),
  group(
    "continued-claims-insured-unemployment",
    "Continued Claims / Insured Unemployment",
    "The persistence of insured unemployment and the capacity of the labor market to return claimants to work.",
    "U.S. Department of Labor ETA; BLS JOLTS/CES; Census; BEA",
    ["Initial Claims", "Hires Rate", "Job Openings Rate", "Payroll Growth", "Temporary Help Employment", "Average Weekly Hours", "Business Formations", "Real Output Growth", "Consumer Demand", "Regional Employment Growth"]
  ),
  group(
    "permanent-job-losers",
    "Permanent Job Losers",
    "People whose employment ended involuntarily and who do not expect recall to the former job.",
    "BLS CPS/BED/CES/Productivity; Census BDS/trade; U.S. Courts; Federal Reserve; BEA",
    ["Establishment Deaths", "Firm Deaths", "Business Bankruptcy Stress", "Industry Payroll Contraction", "Gross Job Losses", "Productivity / Automation", "Import / Trade Pressure", "C&I Credit Conditions", "Corporate Profitability", "Real Output Growth"]
  ),
  group(
    "temporary-layoffs",
    "Temporary Layoffs",
    "People separated from work who expect recall, distinguished from permanent job loss.",
    "BLS CPS/CES; Federal Reserve; Census; BEA; EIA and disaster authorities",
    ["Average Weekly Hours", "Industrial Production", "Capacity Utilization", "New Orders", "Inventory / Sales Balance", "Consumer Demand", "Manufacturing Output", "Energy / Input Shock", "Disaster / Weather Shock", "Industry Payroll Contraction"]
  ),
  group(
    "gross-job-losses",
    "Gross Job Losses",
    "Employment losses at contracting and closing establishments before gross gains are netted against them.",
    "BLS BED; BEA; Census; Federal Reserve SLOOS; BLS Productivity/PPI",
    ["Establishment Contractions", "Establishment Closures", "Real Output Growth", "Consumer Spending", "New Orders", "Corporate Profits", "C&I Lending Standards", "Unit Labor Costs", "Producer Input Prices", "Trade / Import Pressure"]
  ),
  group(
    "establishment-death-closure-losses",
    "Establishment Death / Closure Losses",
    "Employment losses associated with closing establishments and permanent establishment exits.",
    "BLS BED; Census BDS/BFS; U.S. Courts; BEA; Federal Reserve; BLS PPI; disaster authorities",
    ["Closing Establishment Losses", "Business Bankruptcy Stress", "Corporate Profitability", "C&I Lending Standards", "Borrowing Costs", "Sales / Revenue Growth", "Producer Input Prices", "Business Formation / Dynamism", "Firm Age / Size Vulnerability", "Disaster / External Shock"]
  ),
  group(
    "firm-death-shutdown-stress",
    "Firm Death / Shutdown Stress",
    "Conditions associated with permanent firm exit and shutdown pressure, without equating a stress signal to an observed closure.",
    "Census BDS; U.S. Courts; BLS BED; BEA; Federal Reserve; Census economic indicators",
    ["Establishment Deaths", "Business Bankruptcy Filings", "Corporate Profits", "Interest Rates", "C&I Lending Standards", "Sales / Revenue", "Input Costs", "Inventory / Sales Imbalance", "Firm Age / Size", "Trade / External Shock"]
  ),
  group(
    "industry-payroll-contraction",
    "Industry Payroll Contraction",
    "Declines in payroll employment within an industry, interpreted with explicit source classifications and crosswalks.",
    "BLS CES/JOLTS/BED/Productivity/PPI; BEA industry accounts; Census; Federal Reserve",
    ["Industry Output", "Industry Sales / Shipments", "Industry New Orders", "Industry Layoffs & Discharges", "Industry Gross Job Losses", "Industry Capacity Utilization", "Industry Unit Labor Costs", "Industry Input Prices", "Import Exposure", "Industry Credit Conditions"]
  ),
  group(
    "business-failure-bankruptcy-stress",
    "Business Failure / Bankruptcy Stress",
    "A leading stress context for potential business distress; it is not a direct measure of layoffs, firm death, or establishment death.",
    "U.S. Courts; BEA; Federal Reserve; Census; BLS Productivity/PPI",
    ["Corporate Profits", "Interest Rates", "C&I Lending Standards", "C&I Loan Demand", "Sales / Revenue", "Producer Input Costs", "Unit Labor Costs", "Inventory / Sales Ratio", "Business Formation", "Real Output Growth"]
  )
]);

const legacyLevel2PlacementSlugs = Object.freeze(["initial-claims", "continued-claims", "layoffs-and-discharges", "establishment-closings", "gross-job-losses", "mass-layoff-signals", "permanent-job-losers", "temporary-layoffs", "contraction-breadth", "job-loss-duration"]);

export const layoffsBranchPlacementMigration: Readonly<Record<string, string>> = Object.freeze(Object.fromEntries(
  layoffsBranchTaxonomy.flatMap((item, groupIndex) => [
    [`placement:${LAYOFFS_JOB_DESTRUCTION_DRIVER_ID}:${legacyLevel2PlacementSlugs[groupIndex]}`, `placement:${LAYOFFS_JOB_DESTRUCTION_DRIVER_ID}:${item.id}`] as const,
    ...item.placements.map((candidate, placementIndex) => [
      `fixture-placement:${LAYOFFS_JOB_DESTRUCTION_DRIVER_ID}:${String(groupIndex + 1).padStart(2, "0")}:${String(placementIndex + 1).padStart(2, "0")}`,
      `placement:${LAYOFFS_JOB_DESTRUCTION_DRIVER_ID}:${item.id}:${slug(candidate.label)}`
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
