export type StateType = "OBS" | "CALC" | "FCST" | "SCEN";
export type PrimaryView = "summary" | "verified" | "outlook";
export type FreshnessState = "current" | "delayed" | "stale" | "unavailable" | "schema_format_changed" | "validation_failed" | "rights_blocked";
export type RelationshipClass = "Direct" | "Statistical" | "Modeled" | "Hypothesis";
export type HorizonId = "current-year" | "next-year" | "plus-3-years";

export interface SnapshotMetadata {
  id: string;
  evaluatedAt: string;
  generatedAt: string;
  publishedAt: string;
  asOf: string;
  sourceSnapshotId: string;
  publicationClass: "fixture" | "factual";
}

export interface SourceRecord {
  sourceId: string;
  provider: string;
  dataset: string;
  authorityTier: string;
  methodologyUrl: string;
  observationTime: string;
  publishedAt: string;
  retrievedAt: string;
  freshnessEvaluatedAt: string;
  nextExpectedReleaseAt: string;
  freshness: FreshnessState;
  freshnessReason: string;
  revision: string;
  vintage: string;
  publicDisplayAllowed: boolean;
  attributionRequired: boolean;
}

export interface MetricPoint {
  period: string;
  displayPeriod: string;
  value: number;
  rangeLow?: number;
  rangeHigh?: number;
}

export interface MetricRecord {
  id: string;
  stateType: StateType;
  label: string;
  value: number;
  displayValue: string;
  unit: string;
  validTime: string;
  sourceRefs: string[];
  sourceSeriesIds?: string[];
  provenanceRefs: string[];
  direction: "up" | "down" | "flat";
  series: MetricPoint[];
  method?: string;
}

export interface PublicNavigationNode {
  id: string;
  slug: string;
  label: string;
  rank: number;
  priorRank?: number;
  rankState?: "stable" | "changed" | "near-tie";
  nearTie?: boolean;
  nearCutoff?: boolean;
  stateSummaryRefs: string[];
  childRefs: string[];
  availableViews: PrimaryView[];
}

export interface NavigationNode extends Omit<PublicNavigationNode, "childRefs"> {
  children?: NavigationNode[];
}

export interface ForecastEvidence {
  dataCoverage: string;
  relationshipEvidence: string;
  historicalModelSkill: string;
  regimeStability: string;
  sourceSupport: string;
  measuredVsModeled: string;
}

export interface ForecastRecord {
  id: string;
  stateType: "FCST" | "SCEN";
  label: string;
  horizon: HorizonId;
  scenario: string;
  forecastOrigin: string;
  validTime: string;
  range: [number, number];
  displayRange: string;
  unit: "synthetic-index-points";
  sourceRefs: string[];
  evidence: ForecastEvidence;
  positivePressures: string[];
  offsets: string[];
  assumptions: string[];
  whatWouldChangeOurMind: string[];
  changeAttribution: string;
  series: MetricPoint[];
}

export interface RankedHumanCapitalItem {
  id: string;
  label: string;
  rank: number;
  priorRank: number;
  displayValue: string;
  nearTie?: boolean;
  nearCutoff?: boolean;
}

export interface DemandAllocationRecord {
  id: string;
  label: string;
  allocationType:
    | "final-demand allocation share"
    | "industry/output share"
    | "company market share"
    | "constrained resource allocation share";
  stateType: "CALC" | "FCST" | "SCEN";
  displayValue: string;
  changeLabel: string;
  sourceRefs: string[];
}

export interface TraceNode {
  id: string;
  label: string;
  stateType: StateType;
}

export interface TraceEdge {
  id: string;
  from: string;
  to: string;
  classification: RelationshipClass;
  direction: "positive" | "negative" | "offsetting";
  lag: string;
  evidenceStrength: string;
  provenanceRef: string;
  description: string;
}

export interface TraceModel {
  nodes: TraceNode[];
  edges: TraceEdge[];
}

export interface ProvenanceRecord {
  id: string;
  sourceId: string;
  seriesIds: string[];
  seriesEvidenceUrls: Record<string, string>;
  evidenceUrl: string;
  artifactSha256: string;
  publishedAt: string;
  retrievedAt: string;
  acceptedAt: string;
  publicationTimeKind: "official" | "conservative_retrieval_bound";
  vintageId: string;
  revisionNumber: number;
}

export interface SourceHealthRecord {
  observationFreshness: FreshnessState;
  observationFreshnessReason: string;
  retrievalPathHealth: FreshnessState;
  retrievalPathReason: string;
}

export interface RevisionEvidenceRelease {
  label: string;
  releaseId: string;
  publishedAt: string;
  value: number;
  displayValue: string;
  evidenceUrl: string;
  artifactSha256: string;
}

export interface RevisionReplayEvidence {
  id: string;
  indicatorId: string;
  sourceId: string;
  seriesId: string;
  validTime: string;
  label: string;
  releases: RevisionEvidenceRelease[];
  asKnown: {
    cutoff: string;
    value: number;
    displayValue: string;
  };
  latestRevisedTruth: {
    value: number;
    displayValue: string;
  };
}

export type FixtureVariant =
  | "normal"
  | "loading"
  | "delayed"
  | "stale"
  | "insufficient-evidence"
  | "forecast-unavailable"
  | "high-disagreement"
  | "partial-payload"
  | "snapshot-unavailable";

export interface PublicSnapshot {
  schemaVersion: "1.0.0";
  contractVersion: "1.0.0";
  snapshot: SnapshotMetadata;
  systems: PublicNavigationNode[];
  sources: Record<string, SourceRecord>;
  events: Array<{
    id: string;
    label: string;
    stateType: StateType;
    validTime: string;
    sourceRefs: string[];
  }>;
  outlook: {
    status?: "unavailable_not_yet_supported";
    message?: string;
    horizons: Array<{ id: HorizonId; label: string }>;
    forecasts: ForecastRecord[];
    industries: RankedHumanCapitalItem[];
    occupations: RankedHumanCapitalItem[];
    demandAllocation: DemandAllocationRecord[];
  };
  extensions: {
    "auxsays.phase2.metrics": MetricRecord[];
    "auxsays.phase2.trace": TraceModel;
    "auxsays.phase2.fixtureVariants": FixtureVariant[];
    "auxsays.phase2.geographies": Array<{ id: string; label: string }>;
    "auxsays.phase2.ranges": Array<{ id: string; label: string }>;
    "auxsays.phase2.navigationNodes": Record<string, PublicNavigationNode>;
    "auxsays.phase3.provenance"?: Record<string, ProvenanceRecord>;
    "auxsays.phase3.sourceHealth"?: Record<string, SourceHealthRecord>;
    "auxsays.phase3.revisionEvidence"?: RevisionReplayEvidence[];
  };
}

export type PublicationCandidatePayload = Pick<PublicSnapshot, "systems" | "sources" | "events" | "outlook" | "extensions">;

export interface PublicationCandidate {
  artifactType: "PDI_PUBLICATION_CANDIDATE";
  candidate: {
    id: string;
    targetSchemaVersion: "1.0.0";
    targetContractVersion: "1.0.0";
    evaluatedAt: string;
    generatedAt: string;
    asOf: string;
    sourceSnapshotId: string;
    publicationClass: "factual";
    validationProfile: "pdi-1.0.0-factual-pre-activation-v1";
    payloadSha256: string;
  };
  payload: PublicationCandidatePayload;
}

export type SnapshotViewModel = Omit<PublicSnapshot, "snapshot" | "systems"> & {
  snapshot: Omit<SnapshotMetadata, "publishedAt"> & { publishedAt?: string };
  systems: NavigationNode[];
};
