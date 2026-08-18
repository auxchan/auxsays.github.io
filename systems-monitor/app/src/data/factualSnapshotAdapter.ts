import type { FreshnessState, MetricRecord, PublicSnapshot, SourceRecord } from "./publicSnapshotTypes";

export interface LocalFactualMetric {
  id: string;
  label: string;
  stateType: "OBS";
  value: string;
  unit: string;
  observationPeriod: string;
  sourceId: string;
  sourceLabel: string;
  publicTime: string;
  retrievedTime: string;
  acceptedTime: string;
  publicationTimeKind: "official" | "conservative_retrieval_bound";
  vintageId: string;
  revisionNumber: number;
  sourceHealth: FreshnessState;
  rightsState: "ALLOW";
  provenanceUrl: string;
  artifactSha256: string;
}

export interface LocalFactualCandidate {
  schemaVersion: "phase3-factual-candidate-1.0.0";
  publicationClass: "factual";
  activationStatus: "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED";
  generatedAt: string;
  geography: "US";
  metrics: LocalFactualMetric[];
  forecasts: [];
  scenarios: [];
  rankings: [];
  events: [];
  outlook: { status: "unavailable_not_yet_supported"; message: string };
}

const sourceDefinitions: Record<string, Pick<SourceRecord, "provider" | "dataset" | "authorityTier" | "methodologyUrl" | "nextExpectedReleaseAt" | "publicDisplayAllowed" | "attributionRequired">> = {
  "bls-ces": { provider: "U.S. Bureau of Labor Statistics", dataset: "Current Employment Statistics", authorityTier: "Tier A original authority", methodologyUrl: "https://www.bls.gov/opub/hom/ces/home.htm", nextExpectedReleaseAt: "See current BLS release calendar", publicDisplayAllowed: true, attributionRequired: true },
  "bls-cps": { provider: "U.S. Bureau of Labor Statistics", dataset: "Current Population Survey labor-force statistics", authorityTier: "Tier A original authority", methodologyUrl: "https://www.bls.gov/opub/hom/cps/calculation.htm", nextExpectedReleaseAt: "See current BLS release calendar", publicDisplayAllowed: true, attributionRequired: true },
  "bls-jolts": { provider: "U.S. Bureau of Labor Statistics", dataset: "Job Openings and Labor Turnover Survey", authorityTier: "Tier A original authority", methodologyUrl: "https://www.bls.gov/opub/hom/jlt/presentation.htm", nextExpectedReleaseAt: "See current BLS release calendar", publicDisplayAllowed: true, attributionRequired: true },
  "dol-ui-claims": { provider: "U.S. Department of Labor", dataset: "Unemployment Insurance Weekly Claims", authorityTier: "Tier A original authority", methodologyUrl: "https://oui.doleta.gov/unemploy/claims.asp", nextExpectedReleaseAt: "Thursday 08:30 ET", publicDisplayAllowed: true, attributionRequired: true }
};

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`Invalid local factual candidate: ${message}`);
}

export function validateLocalFactualCandidate(value: unknown): asserts value is LocalFactualCandidate {
  assert(value && typeof value === "object", "envelope must be an object");
  const candidate = value as LocalFactualCandidate;
  assert(candidate.schemaVersion === "phase3-factual-candidate-1.0.0", "unsupported schema");
  assert(candidate.publicationClass === "factual", "publicationClass must be factual");
  assert(candidate.activationStatus === "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED", "activation boundary missing");
  assert(candidate.geography === "US", "only approved U.S. geography is allowed");
  assert(Array.isArray(candidate.metrics) && candidate.metrics.length === 6, "exactly six observations required");
  assert(candidate.metrics.every((metric) => metric.stateType === "OBS" && metric.rightsState === "ALLOW"), "only rights-cleared OBS records allowed");
  assert(candidate.metrics.every((metric) => Number.isFinite(Number(metric.value)) && /^[a-f0-9]{64}$/i.test(metric.artifactSha256)), "invalid value or artifact hash");
  assert(candidate.metrics.every((metric) => Date.parse(metric.publicTime) <= Date.parse(metric.retrievedTime) && Date.parse(metric.retrievedTime) <= Date.parse(metric.acceptedTime)), "impossible temporal ordering");
  assert(candidate.forecasts.length === 0 && candidate.scenarios.length === 0 && candidate.rankings.length === 0 && candidate.events.length === 0, "later-phase or fixture claims prohibited");
  assert(candidate.outlook.status === "unavailable_not_yet_supported", "Outlook must remain unavailable");
}

export function adaptLocalFactualCandidate(value: unknown): PublicSnapshot {
  validateLocalFactualCandidate(value);
  const candidate = value;
  const asOf = [...candidate.metrics.map((metric) => metric.acceptedTime)].sort().at(-1) ?? candidate.generatedAt;
  const metrics: MetricRecord[] = candidate.metrics.map((metric) => ({
    id: metric.id,
    stateType: "OBS",
    label: metric.label,
    value: Number(metric.value),
    displayValue: `${Number(metric.value).toLocaleString("en-US")} ${metric.unit}`,
    unit: metric.unit,
    validTime: metric.observationPeriod,
    sourceRefs: [metric.sourceId],
    provenanceRefs: [metric.provenanceUrl, metric.artifactSha256],
    direction: "flat",
    series: [{ period: metric.observationPeriod, displayPeriod: metric.observationPeriod, value: Number(metric.value) }],
    method: `${metric.publicationTimeKind}; vintage ${metric.vintageId}; revision ${metric.revisionNumber}`
  }));
  const sources: Record<string, SourceRecord> = {};
  for (const metric of candidate.metrics) {
    const definition = sourceDefinitions[metric.sourceId];
    assert(definition, `unregistered source ${metric.sourceId}`);
    sources[metric.sourceId] = {
      sourceId: metric.sourceId,
      ...definition,
      observationTime: metric.observationPeriod,
      publishedAt: metric.publicTime,
      retrievedAt: metric.retrievedTime,
      freshnessEvaluatedAt: candidate.generatedAt,
      freshness: metric.sourceHealth,
      freshnessReason: `${metric.publicationTimeKind}; local factual review candidate`,
      revision: `revision ${metric.revisionNumber}`,
      vintage: metric.vintageId
    };
  }
  return {
    schemaVersion: "1.0.0",
    contractVersion: "1.0.0",
    snapshot: { id: `factual-local-${candidate.generatedAt}`, evaluatedAt: candidate.generatedAt, generatedAt: candidate.generatedAt, publishedAt: candidate.generatedAt, asOf, sourceSnapshotId: "phase3-local-review-candidate", publicationClass: "factual" },
    systems: [{ id: "us-labor", slug: "us-labor", label: "U.S. Labor System", rank: 1, stateSummaryRefs: metrics.map((metric) => metric.id), availableViews: ["summary", "verified", "outlook"], children: metrics.map((metric, index) => ({ id: metric.id, slug: metric.id.toLowerCase().replaceAll("_", "-"), label: metric.label, rank: index + 1, stateSummaryRefs: [metric.id], availableViews: ["summary", "verified"] })) }],
    sources,
    events: [],
    outlook: { horizons: [{ id: "current-year", label: "Current Year" }, { id: "next-year", label: "Next Year" }, { id: "plus-3-years", label: "+3 Years" }], forecasts: [], industries: [], occupations: [], demandAllocation: [] },
    extensions: {
      "auxsays.phase2.metrics": metrics,
      "auxsays.phase2.trace": { nodes: [], edges: [] },
      "auxsays.phase2.fixtureVariants": ["normal"],
      "auxsays.phase2.geographies": [{ id: "US", label: "United States" }],
      "auxsays.phase2.ranges": [{ id: "latest", label: "Latest available observation" }]
    }
  };
}

