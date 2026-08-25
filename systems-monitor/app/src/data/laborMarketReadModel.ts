import type {
  LaborMarketCanonicalFactor,
  LaborMarketHierarchyExtension,
  LaborMarketHierarchyPlacement,
  MetricRecord,
  NavigationNode,
  ProvenanceRecord,
  SnapshotViewModel,
  SourceRecord
} from "./publicSnapshotTypes";

type FactorDefinition = Omit<LaborMarketCanonicalFactor, "availability">;

const factorDefinitions: readonly FactorDefinition[] = [
  {
    id: "factor:payroll-employment",
    slug: "payroll-employment",
    label: "Payroll Employment",
    definition: "The number of people on nonfarm employer payrolls.",
    tracks: "Broad employer-reported job levels across the U.S. economy.",
    impact: "A wider payroll base generally means more earned income and household demand.",
    metricRef: "US_LABOR_TOTAL_NONFARM_PAYROLLS",
    candidateSeriesId: "CES0000000001"
  },
  {
    id: "factor:u3-unemployment",
    slug: "u3-unemployment",
    label: "U-3 Unemployment",
    definition: "The share of the labor force without a job and actively looking for work.",
    tracks: "The official headline unemployment rate from the household survey.",
    impact: "It helps show how much available labor is not currently employed.",
    metricRef: "US_LABOR_U3_UNEMPLOYMENT_RATE",
    candidateSeriesId: "LNS14000000"
  },
  {
    id: "factor:labor-force-participation",
    slug: "labor-force-participation",
    label: "Labor-Force Participation",
    definition: "The share of the civilian population age 16 and older working or looking for work.",
    tracks: "How much of the working-age population is engaged with the labor market.",
    impact: "Participation changes the economy's available labor supply and the meaning of unemployment moves.",
    metricRef: "US_LABOR_FORCE_PARTICIPATION_RATE",
    candidateSeriesId: "LNS11300000"
  },
  {
    id: "factor:initial-claims",
    slug: "initial-claims",
    label: "Initial Claims",
    definition: "New applications for unemployment insurance filed during the week.",
    tracks: "A timely weekly signal of newly displaced workers.",
    impact: "A sustained rise can reveal labor-market weakening before slower monthly releases.",
    metricRef: "US_LABOR_INITIAL_UI_CLAIMS",
    candidateSeriesId: "DOL-UI-SA-INITIAL"
  },
  {
    id: "factor:job-openings",
    slug: "job-openings",
    label: "Job Openings",
    definition: "Positions employers are actively recruiting to fill.",
    tracks: "Employer demand for workers at the end of the month.",
    impact: "Openings help distinguish strong hiring demand from a labor market that is merely maintaining payrolls.",
    metricRef: "US_LABOR_JOB_OPENINGS",
    candidateSeriesId: "JTS000000000000000JOL"
  },
  {
    id: "factor:hires",
    slug: "hires",
    label: "Hires",
    definition: "Workers added to employer payrolls during the month.",
    tracks: "The realized flow of people into jobs, not just advertised demand.",
    impact: "Hiring flow shows whether available positions are turning into actual employment.",
    metricRef: "US_LABOR_HIRES",
    candidateSeriesId: "JTS000000000000000HIL"
  },
  {
    id: "factor:average-weekly-hours",
    slug: "average-weekly-hours",
    label: "Average Weekly Hours",
    definition: "Average weekly hours worked by private-sector production and nonsupervisory employees.",
    tracks: "How intensively employers are using their existing workforce.",
    impact: "Hours can adjust before headcount, making them useful context for changing labor demand.",
    candidateSeriesId: "CES0500000002"
  },
  {
    id: "factor:average-hourly-earnings",
    slug: "average-hourly-earnings",
    label: "Average Hourly Earnings",
    definition: "Average hourly pay for private-sector production and nonsupervisory employees.",
    tracks: "Current wage levels in the approved BLS earnings series.",
    impact: "Pay affects household purchasing power and employers' labor costs.",
    candidateSeriesId: "CES0500000003"
  },
  {
    id: "factor:total-separations",
    slug: "total-separations",
    label: "Total Separations",
    definition: "All workers leaving payrolls through quits, layoffs, discharges, or other separations.",
    tracks: "Gross labor-market exits and turnover rather than job destruction alone.",
    impact: "Separations show how much employment churn sits behind the net change in payrolls."
  },
  {
    id: "factor:employment-population-ratio",
    slug: "employment-population-ratio",
    label: "Employment-Population Ratio",
    definition: "The share of the civilian population age 16 and older that is employed.",
    tracks: "How broadly employment reaches across the working-age population.",
    impact: "It combines employment and population context without depending on active job-search status.",
    candidateSeriesId: "LNS12300000"
  }
] as const;

function createPlacement(factor: FactorDefinition, order: number): LaborMarketHierarchyPlacement {
  return {
    id: `placement:labor-market:${factor.slug}`,
    parentId: "outcome:labor-market-state",
    canonicalFactorId: factor.id,
    level: "Sub-A",
    order,
    role: "hierarchy"
  };
}

export function createLaborMarketHierarchy(metrics: readonly MetricRecord[]): LaborMarketHierarchyExtension {
  const metricIds = new Set(metrics.map((metric) => metric.id));
  const factors = Object.fromEntries(factorDefinitions.map((definition) => {
    const populated = Boolean(definition.metricRef && metricIds.has(definition.metricRef));
    return [definition.id, { ...definition, availability: populated ? "populated" : "not_yet_enabled" } satisfies LaborMarketCanonicalFactor];
  }));
  const placements = factorDefinitions.map((factor, index) => createPlacement(factor, index + 1));
  const populated = Object.values(factors).filter((factor) => factor.availability === "populated").length;
  return {
    version: "1.0.0",
    outcome: { id: "outcome:labor-market-state", label: "Labor Market" },
    taxonomy: { approved: 10, defined: placements.length, status: placements.length === 10 ? "TAXONOMY_COMPLETE" : "TAXONOMY_INCOMPLETE" },
    dataCoverage: { populated, defined: placements.length },
    canonicalFactors: factors,
    placements
  };
}

function placementNodes(hierarchy: LaborMarketHierarchyExtension): NavigationNode[] {
  return hierarchy.placements.map((placement) => {
    const factor = hierarchy.canonicalFactors[placement.canonicalFactorId];
    return {
      id: placement.id,
      slug: factor.slug,
      label: factor.label,
      rank: placement.order,
      stateSummaryRefs: factor.metricRef ? [factor.metricRef] : [],
      availableViews: ["summary", "verified"]
    };
  });
}

export function attachLaborMarketHierarchy(snapshot: SnapshotViewModel): SnapshotViewModel {
  if (snapshot.snapshot.publicationClass !== "factual") return snapshot;
  const metrics = snapshot.extensions["auxsays.phase2.metrics"];
  const hierarchy = createLaborMarketHierarchy(metrics);
  const rootIndex = snapshot.systems.findIndex((system) => system.id === "us-labor" || system.slug === "us-labor");
  if (rootIndex < 0) throw new Error("Factual Labor Market snapshot is missing its canonical navigation root");
  const systems = [...snapshot.systems];
  systems[rootIndex] = { ...systems[rootIndex], label: hierarchy.outcome.label, children: placementNodes(hierarchy) };
  return {
    ...snapshot,
    systems,
    extensions: { ...snapshot.extensions, "auxsays.workstream1.factorHierarchy": hierarchy }
  };
}

export function laborMarketHierarchy(snapshot: SnapshotViewModel): LaborMarketHierarchyExtension {
  const hierarchy = snapshot.extensions["auxsays.workstream1.factorHierarchy"];
  if (!hierarchy) throw new Error("Labor Market hierarchy extension is unavailable");
  return hierarchy;
}

export function observationForFactor(snapshot: SnapshotViewModel, factor: LaborMarketCanonicalFactor): MetricRecord | undefined {
  if (!factor.metricRef) return undefined;
  return snapshot.extensions["auxsays.phase2.metrics"].find((metric) => metric.id === factor.metricRef);
}

export function evidenceForFactor(snapshot: SnapshotViewModel, factor: LaborMarketCanonicalFactor): {
  source?: SourceRecord;
  provenance?: ProvenanceRecord;
  evidenceUrl?: string;
} {
  const observation = observationForFactor(snapshot, factor);
  if (!observation) return {};
  const source = snapshot.sources[observation.sourceRefs[0]];
  const provenanceRegistry = snapshot.extensions["auxsays.phase3.provenance"] ?? {};
  const provenance = provenanceRegistry[observation.provenanceRefs[0]];
  const seriesId = observation.sourceSeriesIds?.[0];
  return { source, provenance, evidenceUrl: seriesId ? provenance?.seriesEvidenceUrls[seriesId] : provenance?.evidenceUrl };
}
