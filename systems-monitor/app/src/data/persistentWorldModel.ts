export const PERSISTENT_WORLD_SCHEMA = "persistent-world-0.1.0" as const;
export const PERSISTENT_WORLD_LAYOUT = "employment-sectors-1.0.0" as const;

export type PersistentWorldDepth = 0 | 1 | 2 | 3;
export type PersistentWorldRelationshipClass = "HIERARCHY_TETHER" | "SYNTHETIC_INFLUENCE";

export interface PersistentWorldFactor {
  id: string;
  label: string;
  definition: string;
  sourceFamily: string;
  evidencePosture: "MASTER_DEFINED" | "CANDIDATE" | "TEST_FIXTURE";
}

export interface PersistentWorldPlacement {
  id: string;
  canonicalFactorId: string;
  parentPlacementId: string | null;
  depth: PersistentWorldDepth;
  order: number;
  sector: number;
  x: number;
  y: number;
  labelPriority: "OUTCOME" | "DRIVER" | "FACTOR" | "FIXTURE_DETAIL";
}

export interface PersistentWorldRelationship {
  id: string;
  fromPlacementId: string;
  toPlacementId: string;
  relationshipClass: PersistentWorldRelationshipClass;
  status: "TEST_FIXTURE";
  evidenceClass: "SYNTHETIC";
  publicationEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED";
}

export interface PersistentWorldReadModel {
  schemaVersion: typeof PERSISTENT_WORLD_SCHEMA;
  worldId: "persistent-employment-world-rd-001";
  layoutVersion: typeof PERSISTENT_WORLD_LAYOUT;
  graphSnapshotId: string;
  publicationClass: "fixture";
  activationStatus: "DEVELOPMENT_ONLY";
  candidateEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED";
  humanQa: "PENDING";
  gateBStatus: "OPEN_UNCHANGED";
  outcomePlacementId: string;
  factors: Readonly<Record<string, PersistentWorldFactor>>;
  placements: Readonly<Record<string, PersistentWorldPlacement>>;
  relationships: Readonly<Record<string, PersistentWorldRelationship>>;
  childrenByPlacement: Readonly<Record<string, readonly string[]>>;
  topologyFingerprint: string;
  coverage: {
    placementCount: 1111;
    level1Count: 10;
    level2Count: 100;
    level3Count: 1000;
    hierarchyRelationshipCount: 1110;
    syntheticInfluenceCount: 2000;
    factualRelationshipCount: 0;
    acceptedRelationshipCount: 0;
  };
}

interface CandidateGroup {
  id: string;
  label: string;
  definition: string;
  sourceFamily: string;
  children: readonly string[];
}

export const employmentDriverCandidates: readonly CandidateGroup[] = [
  { id: "economic-output-growth", label: "Output & Growth", definition: "The scale and momentum of U.S. production that can support or weaken labor demand.", sourceFamily: "BEA NIPA; Federal Reserve industrial production; Census", children: ["Real GDP Growth", "Gross Domestic Income", "Industrial Production", "Capacity Utilization", "Real Final Sales", "Manufacturing Output", "Services Output", "Construction Activity", "Business Formation", "Regional Output Breadth"] },
  { id: "consumer-demand", label: "Consumer Demand", definition: "Household spending power and purchasing activity that support demand for goods, services, and workers.", sourceFamily: "BEA PCE/income; Census retail and services; Federal Reserve", children: ["Real Personal Consumption", "Retail Sales", "Services Spending", "Disposable Personal Income", "Real Wage Purchasing Power", "Consumer Credit", "Household Saving", "Consumer Sentiment", "Durable Goods Demand", "Housing-Related Spending"] },
  { id: "employer-labor-demand", label: "Employer Labor Demand", definition: "Employer demand for workers through vacancies, recruiting, hiring, hours, and staffing plans.", sourceFamily: "BLS JOLTS/CES/BED; DOL", children: ["Job Openings", "Hires", "Average Weekly Hours", "Temporary Help Employment", "Overtime Hours", "Hiring Plans", "Vacancy Duration", "Recruiting Intensity", "Gross Job Gains", "Labor Demand Breadth"] },
  { id: "layoffs-job-destruction", label: "Layoffs & Job Destruction", definition: "Flows that remove jobs or move workers out of employment.", sourceFamily: "DOL unemployment insurance; BLS JOLTS/BED/CES", children: ["Initial Claims", "Continued Claims", "Layoffs and Discharges", "Establishment Closings", "Gross Job Losses", "Mass Layoff Signals", "Permanent Job Losers", "Temporary Layoffs", "Contraction Breadth", "Job-Loss Duration"] },
  { id: "business-investment", label: "Business Investment", definition: "Capital formation and forward commitments that shape future productive capacity and staffing.", sourceFamily: "BEA fixed investment; Census orders/construction/business formation", children: ["Equipment Investment", "Structures Investment", "Intellectual Property Investment", "Core Capital Goods Orders", "Capital Goods Shipments", "Private Construction", "Inventory Investment", "Business Applications", "Manufacturing Backlogs", "Investment Intentions"] },
  { id: "interest-rates-credit", label: "Rates & Credit", definition: "The price and availability of financing for households and firms.", sourceFamily: "Federal Reserve; Treasury; FDIC and bank regulators", children: ["Policy Rate", "Treasury Yield Curve", "Corporate Bond Spreads", "Bank Lending Standards", "Commercial Loan Growth", "Consumer Credit Growth", "Mortgage Rates", "Small-Business Credit", "Delinquency Pressure", "Financial Conditions"] },
  { id: "labor-costs-wages", label: "Labor Costs & Wages", definition: "Compensation, benefits, and labor cost pressure facing workers and employers.", sourceFamily: "BLS CES/ECI/ECEC/productivity", children: ["Average Hourly Earnings", "Employment Cost Index", "Benefits Cost", "Unit Labor Costs", "Real Hourly Compensation", "Wage Growth Breadth", "Production Worker Earnings", "Overtime Pay", "Compensation per Hour", "Wage-Price Pressure"] },
  { id: "productivity-automation", label: "Productivity & Automation", definition: "Changes in output per labor input and technology adoption that alter how work is performed.", sourceFamily: "BLS productivity; BEA capital accounts; Census technology surveys", children: ["Labor Productivity", "Multifactor Productivity", "Output per Hour", "Capital Deepening", "Software Investment", "Robotics Adoption", "AI-Related Investment", "Process Automation", "Research and Development", "Technology Diffusion"] },
  { id: "labor-supply", label: "Labor Supply", definition: "The availability and engagement of people able and willing to work.", sourceFamily: "BLS CPS; Census population/migration; education and immigration authorities", children: ["Labor-Force Participation", "Employment-Population Ratio", "Working-Age Population", "Prime-Age Participation", "Migration and Immigration", "Educational Attainment", "Skills Availability", "Retirement Flows", "Caregiving Constraints", "Geographic Mobility"] },
  { id: "policy-trade-external-shocks", label: "Policy, Trade & External Shocks", definition: "Government, trade, physical supply, weather, health, and geopolitical pressures that disturb other systems.", sourceFamily: "Treasury; Census/USITC; EIA; USDA; NOAA; FEMA; BTS", children: ["Fiscal Policy", "Trade Volumes", "Tariffs and Restrictions", "Energy Supply", "Food and Agriculture Supply", "Weather Disruption", "Public Health Disruption", "Geopolitical Risk", "Transportation Bottlenecks", "Regulatory Change"] }
] as const;

const slug = (value: string) => value.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const round = (value: number) => Math.round(value * 1000) / 1000;

function fnv1a(value: string) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function freezeRecord<T>(record: Record<string, T>): Readonly<Record<string, T>> {
  Object.values(record).forEach((value) => Object.freeze(value));
  return Object.freeze(record);
}

export function persistentWorldFingerprint(model: Pick<PersistentWorldReadModel, "layoutVersion" | "placements" | "relationships">) {
  const placements = Object.values(model.placements).sort((left, right) => left.id.localeCompare(right.id)).map((item) => `${item.id}|${item.parentPlacementId ?? "ROOT"}|${item.x}|${item.y}|${item.depth}`);
  const relationships = Object.values(model.relationships).sort((left, right) => left.id.localeCompare(right.id)).map((item) => `${item.id}|${item.fromPlacementId}|${item.toPlacementId}|${item.relationshipClass}`);
  return `fnv1a32:${fnv1a([model.layoutVersion, ...placements, ...relationships].join("\n"))}`;
}

export function createPersistentWorld(): PersistentWorldReadModel {
  const factors: Record<string, PersistentWorldFactor> = {};
  const placements: Record<string, PersistentWorldPlacement> = {};
  const relationships: Record<string, PersistentWorldRelationship> = {};
  const childrenByPlacement: Record<string, string[]> = {};
  const outcomeFactorId = "factor:employment-labor-outcome";
  const outcomePlacementId = "placement:employment-labor-outcome";
  factors[outcomeFactorId] = { id: outcomeFactorId, label: "Employment / Labor Outcome", definition: "The realized U.S. employment and labor-market outcome the ten driver systems help contextualize.", sourceFamily: "BLS and DOL factual measurements remain in the separate Workstream-1A snapshot", evidencePosture: "MASTER_DEFINED" };
  placements[outcomePlacementId] = { id: outcomePlacementId, canonicalFactorId: outcomeFactorId, parentPlacementId: null, depth: 0, order: 1, sector: -1, x: 0, y: 0, labelPriority: "OUTCOME" };
  childrenByPlacement[outcomePlacementId] = [];

  employmentDriverCandidates.forEach((driver, driverIndex) => {
    const sectorAngle = -Math.PI / 2 + driverIndex * Math.PI * 2 / 10;
    const l1FactorId = `factor:${driver.id}`;
    const l1PlacementId = `placement:${driver.id}`;
    const l1X = round(Math.cos(sectorAngle) * 1250);
    const l1Y = round(Math.sin(sectorAngle) * 1250);
    factors[l1FactorId] = { id: l1FactorId, label: driver.label, definition: driver.definition, sourceFamily: driver.sourceFamily, evidencePosture: "MASTER_DEFINED" };
    placements[l1PlacementId] = { id: l1PlacementId, canonicalFactorId: l1FactorId, parentPlacementId: outcomePlacementId, depth: 1, order: driverIndex + 1, sector: driverIndex, x: l1X, y: l1Y, labelPriority: "DRIVER" };
    childrenByPlacement[outcomePlacementId].push(l1PlacementId);
    childrenByPlacement[l1PlacementId] = [];
    relationships[`hierarchy:${outcomePlacementId}:${l1PlacementId}`] = { id: `hierarchy:${outcomePlacementId}:${l1PlacementId}`, fromPlacementId: outcomePlacementId, toPlacementId: l1PlacementId, relationshipClass: "HIERARCHY_TETHER", status: "TEST_FIXTURE", evidenceClass: "SYNTHETIC", publicationEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED" };

    driver.children.forEach((label, level2Index) => {
      const l2Angle = sectorAngle + (level2Index - 4.5) * 0.082;
      const l2Radius = 430 + (level2Index % 2) * 72;
      const l2FactorId = `factor:${driver.id}:${slug(label)}`;
      const l2PlacementId = `placement:${driver.id}:${slug(label)}`;
      const l2X = round(l1X + Math.cos(l2Angle) * l2Radius);
      const l2Y = round(l1Y + Math.sin(l2Angle) * l2Radius);
      factors[l2FactorId] = { id: l2FactorId, label, definition: `${label} is a review candidate within ${driver.label}; it does not become a factual relationship through placement.`, sourceFamily: driver.sourceFamily, evidencePosture: "CANDIDATE" };
      placements[l2PlacementId] = { id: l2PlacementId, canonicalFactorId: l2FactorId, parentPlacementId: l1PlacementId, depth: 2, order: level2Index + 1, sector: driverIndex, x: l2X, y: l2Y, labelPriority: "FACTOR" };
      childrenByPlacement[l1PlacementId].push(l2PlacementId);
      childrenByPlacement[l2PlacementId] = [];
      relationships[`hierarchy:${l1PlacementId}:${l2PlacementId}`] = { id: `hierarchy:${l1PlacementId}:${l2PlacementId}`, fromPlacementId: l1PlacementId, toPlacementId: l2PlacementId, relationshipClass: "HIERARCHY_TETHER", status: "TEST_FIXTURE", evidenceClass: "SYNTHETIC", publicationEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED" };

      for (let level3Index = 0; level3Index < 10; level3Index += 1) {
        const localAngle = level3Index * Math.PI * 2 / 10 + driverIndex * 0.11;
        const l3FactorId = `fixture-factor:${driver.id}:${String(level2Index + 1).padStart(2, "0")}:${String(level3Index + 1).padStart(2, "0")}`;
        const l3PlacementId = `fixture-placement:${driver.id}:${String(level2Index + 1).padStart(2, "0")}:${String(level3Index + 1).padStart(2, "0")}`;
        factors[l3FactorId] = { id: l3FactorId, label: `Renderer fixture ${String(level3Index + 1).padStart(2, "0")}`, definition: `Synthetic Level-3 renderer-capacity record under ${label}. It is not an economic claim.`, sourceFamily: "Repository deterministic test fixture", evidencePosture: "TEST_FIXTURE" };
        placements[l3PlacementId] = { id: l3PlacementId, canonicalFactorId: l3FactorId, parentPlacementId: l2PlacementId, depth: 3, order: level3Index + 1, sector: driverIndex, x: round(l2X + Math.cos(localAngle) * 108), y: round(l2Y + Math.sin(localAngle) * 108), labelPriority: "FIXTURE_DETAIL" };
        childrenByPlacement[l2PlacementId].push(l3PlacementId);
        childrenByPlacement[l3PlacementId] = [];
        relationships[`hierarchy:${l2PlacementId}:${l3PlacementId}`] = { id: `hierarchy:${l2PlacementId}:${l3PlacementId}`, fromPlacementId: l2PlacementId, toPlacementId: l3PlacementId, relationshipClass: "HIERARCHY_TETHER", status: "TEST_FIXTURE", evidenceClass: "SYNTHETIC", publicationEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED" };
      }
    });
  });

  const level3 = Object.values(placements).filter((placement) => placement.depth === 3).sort((left, right) => left.id.localeCompare(right.id));
  for (let index = 0; index < 2000; index += 1) {
    const from = level3[index % level3.length];
    const to = level3[(index * 37 + 113) % level3.length];
    const id = `fixture-influence:${String(index + 1).padStart(4, "0")}`;
    relationships[id] = { id, fromPlacementId: from.id, toPlacementId: to.id, relationshipClass: "SYNTHETIC_INFLUENCE", status: "TEST_FIXTURE", evidenceClass: "SYNTHETIC", publicationEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED" };
  }

  const partial = { layoutVersion: PERSISTENT_WORLD_LAYOUT, placements, relationships };
  const topologyFingerprint = persistentWorldFingerprint(partial);
  const model: PersistentWorldReadModel = {
    schemaVersion: PERSISTENT_WORLD_SCHEMA,
    worldId: "persistent-employment-world-rd-001",
    layoutVersion: PERSISTENT_WORLD_LAYOUT,
    graphSnapshotId: `fixture-snapshot:${topologyFingerprint}`,
    publicationClass: "fixture",
    activationStatus: "DEVELOPMENT_ONLY",
    candidateEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED",
    humanQa: "PENDING",
    gateBStatus: "OPEN_UNCHANGED",
    outcomePlacementId,
    factors: freezeRecord(factors),
    placements: freezeRecord(placements),
    relationships: freezeRecord(relationships),
    childrenByPlacement: Object.freeze(Object.fromEntries(Object.entries(childrenByPlacement).map(([id, children]) => [id, Object.freeze(children)]))),
    topologyFingerprint,
    coverage: { placementCount: 1111, level1Count: 10, level2Count: 100, level3Count: 1000, hierarchyRelationshipCount: 1110, syntheticInfluenceCount: 2000, factualRelationshipCount: 0, acceptedRelationshipCount: 0 }
  };
  return Object.freeze(model);
}

export function persistentWorldPath(model: PersistentWorldReadModel, placementId: string | null) {
  const path: PersistentWorldPlacement[] = [];
  let current = placementId ? model.placements[placementId] : undefined;
  while (current) {
    path.unshift(current);
    current = current.parentPlacementId ? model.placements[current.parentPlacementId] : undefined;
  }
  return path;
}

export function persistentWorldSelectionSequence(model: PersistentWorldReadModel, count = 50) {
  const ids = Object.values(model.placements).filter((item) => item.depth > 0).sort((left, right) => left.id.localeCompare(right.id)).map((item) => item.id);
  return Array.from({ length: count }, (_, index) => ids[(index * 97 + 31) % ids.length]);
}
