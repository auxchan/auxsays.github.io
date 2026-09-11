import activeFactualSnapshot from "../../../data/review/local-active-pdi-test-snapshot.json";
import { createSnapshotViewModel } from "./snapshotViewModelFactory";
import { validatePublicSnapshot } from "./validatePublicSnapshot";
import { layoffsBranchTaxonomy, layoffsCanonicalFactorId } from "./layoffsBranchTaxonomy";
import { layoffsAcceptedFactorSummaries, LAYOFFS_ACCEPTED_HISTORY_AS_OF, LAYOFFS_DOL_SOURCE_FRESHNESS } from "./layoffsAcceptedHistoryReadModel";

export type PersistentTimeWindow = "RECENT" | "24H" | "7D" | "30D" | "90D" | "1Y";
export type PersistentChangeKind = "NEW_OFFICIAL_OBSERVATION" | "REVISION" | "SOURCE_STALE";
export type PersistentImpactClass = "SUPPORTIVE" | "ADVERSE" | "MIXED" | "NEUTRAL" | "UNKNOWN";

export interface PersistentChangeNotice {
  id: string;
  kind: PersistentChangeKind;
  factorLabel: string;
  placementId: string;
  knownAt: string;
  officialPublishedAt?: string;
  validTime?: string;
  currentDisplay?: string;
  previousDisplay?: string;
  absoluteDelta?: number;
  relativeDeltaPercent?: number;
  comparisonBasis: string;
  impactClass: PersistentImpactClass;
  economicSignalEligible: boolean;
  headline: string;
  summary: string;
  sourceLabel: string;
  evidenceUrl?: string;
  methodologyUrl?: string;
  sourceHealthOnly: boolean;
}

const snapshot = createSnapshotViewModel(validatePublicSnapshot(activeFactualSnapshot as unknown));
const outcomePlacementId = "placement:employment-labor-outcome";

const placementByMetricId: Readonly<Record<string, string>> = Object.freeze({
  US_LABOR_TOTAL_NONFARM_PAYROLLS: "placement:employment-labor-outcome",
  US_LABOR_U3_UNEMPLOYMENT_RATE: "placement:employment-labor-outcome",
  US_LABOR_FORCE_PARTICIPATION_RATE: "placement:labor-supply:labor-force-participation",
  US_LABOR_INITIAL_UI_CLAIMS: "placement:layoffs-job-destruction:initial-claims",
  US_LABOR_JOB_OPENINGS: "placement:employer-labor-demand:job-openings",
  US_LABOR_HIRES: "placement:employer-labor-demand:hires",
});

function exactEvidenceUrl(metric: (typeof snapshot.extensions)["auxsays.phase2.metrics"][number]) {
  const provenance = snapshot.extensions["auxsays.phase3.provenance"]?.[metric.provenanceRefs[0]];
  const seriesId = metric.sourceSeriesIds?.[0];
  return seriesId ? provenance?.seriesEvidenceUrls[seriesId] : undefined;
}

function observationNotices(): PersistentChangeNotice[] {
  return snapshot.extensions["auxsays.phase2.metrics"].flatMap((metric) => {
    if (metric.id === "US_LABOR_INITIAL_UI_CLAIMS") return [];
    const placementId = placementByMetricId[metric.id];
    const source = snapshot.sources[metric.sourceRefs[0]];
    const provenance = snapshot.extensions["auxsays.phase3.provenance"]?.[metric.provenanceRefs[0]];
    if (!placementId || !source || !provenance) return [];
    return [{
      id: `accepted-observation:${snapshot.snapshot.id}:${metric.id}`,
      kind: "NEW_OFFICIAL_OBSERVATION" as const,
      factorLabel: metric.label,
      placementId,
      knownAt: provenance.acceptedAt,
      officialPublishedAt: source.publishedAt,
      validTime: metric.validTime,
      currentDisplay: metric.displayValue,
      comparisonBasis: "No prior comparable observation is present in the current public snapshot.",
      impactClass: "UNKNOWN" as const,
      economicSignalEligible: false,
      headline: `Official ${metric.label} observation accepted`,
      summary: `${metric.displayValue} for ${metric.validTime}. AUXSAYS cannot claim a material increase or decrease until an accepted comparable prior observation and governed materiality profile are available.`,
      sourceLabel: `${source.provider} · ${source.dataset}`,
      evidenceUrl: exactEvidenceUrl(metric),
      methodologyUrl: source.methodologyUrl,
      sourceHealthOnly: false,
    }];
  });
}

function revisionNotices(): PersistentChangeNotice[] {
  return (snapshot.extensions["auxsays.phase3.revisionEvidence"] ?? []).flatMap((revision) => {
    if (revision.indicatorId === "US_LABOR_INITIAL_UI_CLAIMS") return [];
    const first = revision.releases[0];
    const latest = revision.releases[revision.releases.length - 1];
    const absoluteDelta = latest.value - first.value;
    return [{
      id: `accepted-revision:${revision.id}`,
      kind: "REVISION",
      factorLabel: revision.label,
      placementId: placementByMetricId[revision.indicatorId] ?? outcomePlacementId,
      knownAt: latest.publishedAt,
      officialPublishedAt: latest.publishedAt,
      validTime: revision.validTime,
      currentDisplay: latest.displayValue,
      previousDisplay: first.displayValue,
      absoluteDelta,
      relativeDeltaPercent: first.value === 0 ? undefined : absoluteDelta / Math.abs(first.value) * 100,
      comparisonBasis: `${first.label} compared with ${latest.label}`,
      impactClass: "UNKNOWN",
      economicSignalEligible: false,
      headline: `${revision.label} revised`,
      summary: `${first.displayValue} was revised to ${latest.displayValue}. The revision is historical evidence; no persistent-world connector receives an economic color because this fixture has no accepted structural relationship for that path.`,
      sourceLabel: "U.S. Department of Labor · Unemployment Insurance Weekly Claims",
      evidenceUrl: latest.evidenceUrl,
      methodologyUrl: snapshot.sources[revision.sourceId]?.methodologyUrl,
      sourceHealthOnly: false,
    }];
  });
}

const slug = (value: string) => value.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

function acceptedPlacementId(canonicalFactorId: string) {
  for (const group of layoffsBranchTaxonomy) {
    if (layoffsCanonicalFactorId(group.label) === canonicalFactorId) return `placement:layoffs-job-destruction:${group.id}`;
    const child = group.placements.find((row) => row.canonicalFactorId === canonicalFactorId);
    if (child) return `placement:layoffs-job-destruction:${group.id}:${slug(child.label)}`;
  }
  return "placement:layoffs-job-destruction";
}

function acceptedHistoryNotices(): PersistentChangeNotice[] {
  return layoffsAcceptedFactorSummaries.flatMap((factor) => factor.series.flatMap((series) => {
    const sourceLabel = `${series.provider} · ${series.dataset}`;
    const relative = series.relativeDeltaPercent === undefined ? "" : ` (${series.relativeDeltaPercent >= 0 ? "+" : ""}${series.relativeDeltaPercent.toFixed(2)}%)`;
    const change: PersistentChangeNotice = {
      id: `accepted-history:${series.sourceId}:${series.sourceSeriesId}:${series.current.validTime}`,
      kind: "NEW_OFFICIAL_OBSERVATION",
      factorLabel: series.seriesLabel,
      placementId: acceptedPlacementId(series.canonicalFactorId),
      knownAt: series.current.acceptedTime,
      officialPublishedAt: series.current.publicTime,
      validTime: series.current.validTime,
      currentDisplay: series.currentDisplay,
      previousDisplay: series.previousDisplay,
      absoluteDelta: series.absoluteDelta,
      relativeDeltaPercent: series.relativeDeltaPercent,
      comparisonBasis: `${series.current.validTime} compared with the previous compatible ${series.frequency} observation, ${series.previous.validTime}.`,
      impactClass: "UNKNOWN",
      economicSignalEligible: false,
      headline: `${series.seriesLabel}: ${series.directionGlyph} ${series.direction.toLowerCase()}`,
      summary: `${series.currentDisplay}, from ${series.previousDisplay}; factual change ${series.absoluteDelta >= 0 ? "+" : ""}${series.absoluteDelta.toLocaleString("en-US")}${relative}. Materiality and destination impact remain unknown.`,
      sourceLabel,
      evidenceUrl: series.current.evidenceUrl,
      methodologyUrl: series.current.methodologyUrl,
      sourceHealthOnly: false,
    };
    const revisions: PersistentChangeNotice[] = series.revisions.map(({ current, previous }) => ({
      id: `accepted-history-revision:${current.observationId}`,
      kind: "REVISION",
      factorLabel: series.seriesLabel,
      placementId: acceptedPlacementId(series.canonicalFactorId),
      knownAt: current.acceptedTime,
      officialPublishedAt: current.publicTime,
      validTime: current.validTime,
      currentDisplay: `${Number(current.value).toLocaleString("en-US")} ${current.unit}`,
      previousDisplay: `${Number(previous.value).toLocaleString("en-US")} ${previous.unit}`,
      absoluteDelta: Number(current.value) - Number(previous.value),
      relativeDeltaPercent: Number(previous.value) === 0 ? undefined : (Number(current.value) - Number(previous.value)) / Math.abs(Number(previous.value)) * 100,
      comparisonBasis: `Revision ${current.revisionNumber} supersedes the accepted revision ${previous.revisionNumber} for the same ${current.validTime} period.`,
      impactClass: "UNKNOWN",
      economicSignalEligible: false,
      headline: `${series.seriesLabel} revised`,
      summary: `${Number(previous.value).toLocaleString("en-US")} ${previous.unit} was revised to ${Number(current.value).toLocaleString("en-US")} ${current.unit}. This is revision evidence, not a materiality or impact signal.`,
      sourceLabel,
      evidenceUrl: current.evidenceUrl,
      methodologyUrl: current.methodologyUrl,
      sourceHealthOnly: false,
    }));
    return [change, ...revisions];
  }));
}

function sourceHealthNotices(): PersistentChangeNotice[] {
  const health = snapshot.extensions["auxsays.phase3.sourceHealth"] ?? {};
  return Object.entries(health).flatMap(([sourceId, state]) => {
    if (sourceId === "dol-ui-claims") return [];
    if (state.retrievalPathHealth !== "stale") return [];
    const source = snapshot.sources[sourceId];
    const placementId = sourceId === "dol-ui-claims" ? placementByMetricId.US_LABOR_INITIAL_UI_CLAIMS : outcomePlacementId;
    return [{
      id: `source-health:${snapshot.snapshot.id}:${sourceId}:stale`,
      kind: "SOURCE_STALE" as const,
      factorLabel: source?.dataset ?? sourceId,
      placementId,
      knownAt: snapshot.snapshot.evaluatedAt,
      comparisonBasis: "Operational source health; not an economic comparison.",
      impactClass: "UNKNOWN" as const,
      economicSignalEligible: false,
      headline: "Structured retrieval path is stale",
      summary: state.retrievalPathReason,
      sourceLabel: source ? `${source.provider} · ${source.dataset}` : sourceId,
      methodologyUrl: source?.methodologyUrl,
      sourceHealthOnly: true,
    }];
  });
}

function acceptedSourceHealthNotices(): PersistentChangeNotice[] {
  if (LAYOFFS_DOL_SOURCE_FRESHNESS.status !== "STALE") return [];
  return [{
    id: `source-health:dol-ui-claims:${LAYOFFS_DOL_SOURCE_FRESHNESS.retrievedTime}:stale`,
    kind: "SOURCE_STALE",
    factorLabel: "Unemployment Insurance Weekly Claims",
    placementId: acceptedPlacementId("factor:canonical:initial-claims"),
    knownAt: LAYOFFS_ACCEPTED_HISTORY_AS_OF,
    validTime: LAYOFFS_DOL_SOURCE_FRESHNESS.newestObservationPeriod,
    comparisonBasis: "Operational source freshness; not an economic comparison.",
    impactClass: "UNKNOWN",
    economicSignalEligible: false,
    headline: "Structured retrieval path is stale",
    summary: `The repaired DOL XML source ends at ${LAYOFFS_DOL_SOURCE_FRESHNESS.newestObservationPeriod}; the ${LAYOFFS_DOL_SOURCE_FRESHNESS.observationAgeHours}-hour observation age exceeds the governed ${LAYOFFS_DOL_SOURCE_FRESHNESS.staleAfterHours}-hour limit. Routine current acceptance fails closed while accepted history remains available.`,
    sourceLabel: "U.S. Department of Labor · Unemployment Insurance Weekly Claims",
    methodologyUrl: "https://oui.doleta.gov/unemploy/claims.asp",
    sourceHealthOnly: true,
  }];
}

export const PERSISTENT_TEMPORAL_AS_OF = Date.parse(LAYOFFS_ACCEPTED_HISTORY_AS_OF) > Date.parse(snapshot.snapshot.evaluatedAt)
  ? LAYOFFS_ACCEPTED_HISTORY_AS_OF
  : snapshot.snapshot.evaluatedAt;
export const persistentChangeNotices: readonly PersistentChangeNotice[] = Object.freeze([
  ...acceptedHistoryNotices(),
  ...acceptedSourceHealthNotices(),
  ...observationNotices(),
  ...sourceHealthNotices(),
  ...revisionNotices(),
].sort((left, right) => Date.parse(right.knownAt) - Date.parse(left.knownAt)));

const windowMs: Readonly<Record<PersistentTimeWindow, number>> = Object.freeze({
  RECENT: 30 * 86_400_000,
  "24H": 86_400_000,
  "7D": 7 * 86_400_000,
  "30D": 30 * 86_400_000,
  "90D": 90 * 86_400_000,
  "1Y": 365 * 86_400_000,
});

export function persistentChangesForWindow(window: PersistentTimeWindow, asOf = PERSISTENT_TEMPORAL_AS_OF) {
  const cutoff = Date.parse(asOf) - windowMs[window];
  return persistentChangeNotices.filter((notice) => Date.parse(notice.knownAt) >= cutoff && Date.parse(notice.knownAt) <= Date.parse(asOf));
}

export const PERSISTENT_ACCEPTED_IMPACT_COUNT = persistentChangeNotices.filter((notice) => notice.economicSignalEligible).length;
