import acceptedHistoryDocument from "../../../data/review/layoffs-accepted-history.json";
import activationReportDocument from "../../../data/review/layoffs-history-activation-report.json";
import { layoffsResolveCanonicalFactorId } from "./layoffsBranchTaxonomy";

export interface AcceptedHistoryRow {
  observationId: string;
  canonicalFactorId: string;
  sourceId: string;
  sourceSeriesId: string;
  releaseId: string;
  value: string;
  unit: string;
  frequency: "weekly" | "monthly" | "quarterly" | "annual";
  validTime: string;
  publicTime: string;
  retrievedTime: string;
  acceptedTime: string;
  revisionNumber: number;
  supersedesObservationId: string | null;
  publicationTimeKind: "official" | "conservative_retrieval_bound";
  provenanceUrl: string;
  evidenceUrl: string;
  methodologyUrl: string;
  historyUseClass: "CURRENT_REVISED_HISTORY" | "ORIGINAL_RELEASE_VALUE" | "VINTAGE_RECONSTRUCTED";
  forecastVintageEligible: boolean;
  sourceRevisionStatus: string;
}

export interface LayoffsAcceptedSeriesSummary {
  canonicalFactorId: string;
  sourceId: string;
  sourceSeriesId: string;
  seriesLabel: string;
  provider: string;
  dataset: string;
  unit: string;
  frequency: AcceptedHistoryRow["frequency"];
  current: AcceptedHistoryRow;
  previous?: AcceptedHistoryRow;
  currentDisplay: string;
  previousDisplay?: string;
  absoluteDelta?: number;
  relativeDeltaPercent?: number;
  direction?: "UP" | "DOWN" | "FLAT";
  directionGlyph?: "↑" | "↓" | "→";
  materialityStatus: "UNKNOWN";
  impactStatus: "UNKNOWN";
  forecastVintageEligible: false;
  acceptedPeriodCount: number;
  revisionChainCount: number;
  revisions: readonly { current: AcceptedHistoryRow; previous: AcceptedHistoryRow }[];
  history: readonly AcceptedHistoryRow[];
  recentHistory: readonly AcceptedHistoryRow[];
}

export interface LayoffsAcceptedFactorSummary {
  canonicalFactorId: string;
  primary: LayoffsAcceptedSeriesSummary;
  series: readonly LayoffsAcceptedSeriesSummary[];
}

const document = acceptedHistoryDocument as { schemaVersion: string; generatedAt: string; observations: AcceptedHistoryRow[] };
const activation = activationReportDocument as { dolRepair?: { freshness?: { status?: string; newestObservationPeriod?: string; retrievedTime?: string; observationAgeHours?: number; staleAfterHours?: number }; primaryFreshness?: { status?: string; newestObservationPeriod?: string }; overallStatus?: string; methods?: Record<string, unknown> } };
if (document.schemaVersion !== "layoffs-accepted-history-1.0.0") throw new Error("Unsupported Layoffs accepted-history schema");

const seriesIdentity: Readonly<Record<string, { label: string; provider: string; dataset: string }>> = Object.freeze({
  JTS000000000000000LDL: { label: "Layoffs and discharges", provider: "U.S. Bureau of Labor Statistics", dataset: "Job Openings and Labor Turnover Survey" },
  JTS000000000000000LDR: { label: "Layoffs and discharges rate", provider: "U.S. Bureau of Labor Statistics", dataset: "Job Openings and Labor Turnover Survey" },
  JTS000000000000000JOR: { label: "Job openings rate", provider: "U.S. Bureau of Labor Statistics", dataset: "Job Openings and Labor Turnover Survey" },
  JTS000000000000000HIR: { label: "Hires rate", provider: "U.S. Bureau of Labor Statistics", dataset: "Job Openings and Labor Turnover Survey" },
  LNS13026638: { label: "Permanent job losers", provider: "U.S. Bureau of Labor Statistics", dataset: "Current Population Survey" },
  LNS13023653: { label: "Temporary layoffs", provider: "U.S. Bureau of Labor Statistics", dataset: "Current Population Survey" },
  CES0500000002: { label: "Average weekly hours", provider: "U.S. Bureau of Labor Statistics", dataset: "Current Employment Statistics" },
  CES6056132001: { label: "Temporary help employment", provider: "U.S. Bureau of Labor Statistics", dataset: "Current Employment Statistics" },
  BDS0000000000000000110004LQ5: { label: "Gross job losses", provider: "U.S. Bureau of Labor Statistics", dataset: "Business Employment Dynamics" },
  BDS0000000000000000110005LQ5: { label: "Establishment contractions", provider: "U.S. Bureau of Labor Statistics", dataset: "Business Employment Dynamics" },
  BDS0000000000000000110006LQ5: { label: "Establishment closures", provider: "U.S. Bureau of Labor Statistics", dataset: "Business Employment Dynamics" },
  BDS0000000000000000110008LQ5: { label: "Jobs lost at establishment deaths", provider: "U.S. Bureau of Labor Statistics", dataset: "Business Employment Dynamics" },
  "DOL-UI-SA-INITIAL": { label: "Initial unemployment-insurance claims", provider: "U.S. Department of Labor", dataset: "Unemployment Insurance Weekly Claims" },
});

const primarySeriesPriority = [
  "JTS000000000000000LDL", "JTS000000000000000LDR", "JTS000000000000000JOR", "JTS000000000000000HIR",
  "LNS13026638", "LNS13023653", "CES0500000002", "CES6056132001", "DOL-UI-SA-INITIAL",
  "BDS0000000000000000110004LQ5", "BDS0000000000000000110005LQ5", "BDS0000000000000000110006LQ5", "BDS0000000000000000110008LQ5",
];

export function displayAcceptedLayoffsValue(value: string, unit: string) {
  const numeric = Number(value);
  if (unit === "thousands of persons") return `${(numeric * 1_000).toLocaleString("en-US", { maximumFractionDigits: 4 })} people`;
  if (unit === "thousands of jobs") return `${(numeric * 1_000).toLocaleString("en-US", { maximumFractionDigits: 4 })} jobs`;
  const formatted = Number.isInteger(numeric)
    ? numeric.toLocaleString("en-US")
    : numeric.toLocaleString("en-US", { maximumFractionDigits: 4 });
  if (unit === "percent") return `${formatted}%`;
  if (unit === "hours") return `${formatted} hours`;
  if (unit === "claims") return `${formatted} claims`;
  return `${formatted} ${unit}`;
}

function latestRevisionByPeriod(rows: AcceptedHistoryRow[]) {
  const byPeriod = new Map<string, AcceptedHistoryRow>();
  for (const row of rows) {
    const prior = byPeriod.get(row.validTime);
    if (!prior || row.revisionNumber > prior.revisionNumber || (row.revisionNumber === prior.revisionNumber && row.acceptedTime > prior.acceptedTime)) {
      byPeriod.set(row.validTime, row);
    }
  }
  return [...byPeriod.values()].sort((left, right) => left.validTime.localeCompare(right.validTime));
}

function buildSeriesSummary(canonicalFactorId: string, rows: AcceptedHistoryRow[]): LayoffsAcceptedSeriesSummary | undefined {
  const periods = latestRevisionByPeriod(rows);
  if (periods.length < 1) return undefined;
  const current = periods.at(-1)!;
  const previous = periods.at(-2);
  const currentValue = Number(current.value);
  const previousValue = previous ? Number(previous.value) : undefined;
  const absoluteDelta = previousValue === undefined ? undefined : currentValue - previousValue;
  const identity = seriesIdentity[current.sourceSeriesId];
  if (!identity) throw new Error(`Missing accepted-series identity for ${current.sourceSeriesId}`);
  const byId = new Map(rows.map((row) => [row.observationId, row]));
  const revisions = rows.flatMap((row) => {
    const previousRevision = row.supersedesObservationId ? byId.get(row.supersedesObservationId) : undefined;
    return previousRevision ? [{ current: row, previous: previousRevision }] : [];
  });
  return Object.freeze({
    canonicalFactorId,
    sourceId: current.sourceId,
    sourceSeriesId: current.sourceSeriesId,
    seriesLabel: identity.label,
    provider: identity.provider,
    dataset: identity.dataset,
    unit: current.unit,
    frequency: current.frequency,
    current,
    previous,
    currentDisplay: displayAcceptedLayoffsValue(current.value, current.unit),
    previousDisplay: previous ? displayAcceptedLayoffsValue(previous.value, previous.unit) : undefined,
    absoluteDelta,
    relativeDeltaPercent: previousValue === undefined || previousValue === 0 || absoluteDelta === undefined ? undefined : absoluteDelta / Math.abs(previousValue) * 100,
    direction: absoluteDelta === undefined ? undefined : absoluteDelta > 0 ? "UP" : absoluteDelta < 0 ? "DOWN" : "FLAT",
    directionGlyph: absoluteDelta === undefined ? undefined : absoluteDelta > 0 ? "↑" : absoluteDelta < 0 ? "↓" : "→",
    materialityStatus: "UNKNOWN",
    impactStatus: "UNKNOWN",
    forecastVintageEligible: false,
    acceptedPeriodCount: periods.length,
    revisionChainCount: rows.filter((row) => row.supersedesObservationId).length,
    revisions: Object.freeze(revisions),
    history: Object.freeze([...periods].reverse()),
    recentHistory: Object.freeze(periods.slice(-6).reverse()),
  });
}

const grouped = new Map<string, AcceptedHistoryRow[]>();
for (const row of document.observations) {
  const key = `${layoffsResolveCanonicalFactorId(row.canonicalFactorId)}\u0000${row.sourceSeriesId}`;
  grouped.set(key, [...(grouped.get(key) ?? []), row]);
}

const seriesSummaries = [...grouped.entries()].map(([key, rows]) => buildSeriesSummary(key.split("\u0000")[0], rows)).filter((row): row is LayoffsAcceptedSeriesSummary => Boolean(row));
const byFactor = new Map<string, LayoffsAcceptedSeriesSummary[]>();
for (const row of seriesSummaries) byFactor.set(row.canonicalFactorId, [...(byFactor.get(row.canonicalFactorId) ?? []), row]);

export const layoffsAcceptedFactorSummaries: readonly LayoffsAcceptedFactorSummary[] = Object.freeze(
  [...byFactor.entries()].map(([canonicalFactorId, series]) => {
    const ordered = [...series].sort((left, right) => primarySeriesPriority.indexOf(left.sourceSeriesId) - primarySeriesPriority.indexOf(right.sourceSeriesId));
    return Object.freeze({ canonicalFactorId, primary: ordered[0], series: Object.freeze(ordered) });
  }),
);

const factorSummaryById = new Map(layoffsAcceptedFactorSummaries.map((row) => [row.canonicalFactorId, row]));

export function acceptedLayoffsHistoryForFactor(canonicalFactorId: string) {
  return factorSummaryById.get(layoffsResolveCanonicalFactorId(canonicalFactorId));
}

export function acceptedLayoffsHistoryFreshness(sourceId: string) {
  if (sourceId !== "dol-ui-claims") return "accepted descriptive history";
  return activation.dolRepair?.overallStatus === "SUCCESS_WITH_PRIMARY_STALE"
    ? "current via official release fallback · primary XML stale"
    : activation.dolRepair?.freshness?.status === "STALE"
      ? "accepted history · current structured source stale"
      : "accepted descriptive history";
}

export const LAYOFFS_DOL_SOURCE_FRESHNESS = Object.freeze({ ...(activation.dolRepair?.freshness ?? {}) });
export const LAYOFFS_DOL_PRIMARY_FRESHNESS = Object.freeze({ ...(activation.dolRepair?.primaryFreshness ?? {}) });
export const LAYOFFS_DOL_ACQUISITION_STATUS = activation.dolRepair?.overallStatus ?? "UNAVAILABLE";

export const LAYOFFS_ACCEPTED_OBSERVATION_COUNT = document.observations.length;
export const LAYOFFS_ACCEPTED_HISTORY_FACTOR_COUNT = layoffsAcceptedFactorSummaries.length;
export const LAYOFFS_ACCEPTED_COMPARABLE_FACTOR_COUNT = layoffsAcceptedFactorSummaries.filter((factor) => factor.series.some((series) => Boolean(series.previous))).length;
export const LAYOFFS_ACCEPTED_COMPARABLE_SERIES_COUNT = seriesSummaries.filter((series) => Boolean(series.previous)).length;
export const LAYOFFS_ACCEPTED_HISTORY_AS_OF = document.generatedAt;
