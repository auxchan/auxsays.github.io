import activeFactualSnapshot from "../../../data/review/local-active-pdi-test-snapshot.json";
import { laborMarketHierarchy, observationForFactor, evidenceForFactor } from "./laborMarketReadModel";
import { createSnapshotViewModel } from "./snapshotViewModelFactory";
import { validatePublicSnapshot } from "./validatePublicSnapshot";
import { layoffsFactorSourceState } from "./layoffsBranchReadModel";

export type PersistentWorldBindingStatus = "CONNECTED" | "SOURCE_ENABLED_PENDING_ACCEPTANCE" | "SOURCE_IDENTIFIED" | "BLOCKED" | "FIXTURE_ONLY" | "UNMAPPED";

export interface PersistentWorldFactualBinding {
  status: PersistentWorldBindingStatus;
  label: string;
  candidateSeriesId?: string;
  displayValue?: string;
  validTime?: string;
  provider?: string;
  dataset?: string;
  seriesId?: string;
  freshness?: string;
  evidenceUrl?: string;
  methodologyUrl?: string;
  acquisitionProvenanceUrl?: string;
  acceptedAt?: string;
  candidateSeries?: readonly { sourceId: string; seriesId: string; label: string; unit: string; cadence: string; adjustment: string; evidenceUrl: string; methodologyUrl?: string }[];
  blockedReason?: string;
}

const factualSnapshot = createSnapshotViewModel(validatePublicSnapshot(activeFactualSnapshot as unknown));
const hierarchy = laborMarketHierarchy(factualSnapshot);
const factorsByLabel = new Map(Object.values(hierarchy.canonicalFactors).map((factor) => [factor.label.toLowerCase(), factor]));

export const PERSISTENT_FACTUAL_OBSERVATION_COUNT = factualSnapshot.extensions["auxsays.phase2.metrics"].length;

/**
 * Additive read-only bridge from a named persistent-world factor to the already
 * accepted factual snapshot. A hierarchy placement never creates a data claim.
 */
export function persistentWorldFactualBinding(label: string): PersistentWorldFactualBinding {
  const factor = factorsByLabel.get(label.toLowerCase());
  if (!factor) return { status: "UNMAPPED", label };
  const observation = observationForFactor(factualSnapshot, factor);
  if (!observation) return { status: factor.candidateSeriesId ? "SOURCE_IDENTIFIED" : "UNMAPPED", label, candidateSeriesId: factor.candidateSeriesId };
  const evidence = evidenceForFactor(factualSnapshot, factor);
  const seriesId = observation.sourceSeriesIds?.[0];
  return {
    status: "CONNECTED",
    label,
    displayValue: observation.displayValue,
    validTime: observation.validTime,
    provider: evidence.source?.provider,
    dataset: evidence.source?.dataset,
    seriesId,
    freshness: evidence.source?.freshness,
    evidenceUrl: evidence.evidenceUrl,
    methodologyUrl: evidence.source?.methodologyUrl,
    acquisitionProvenanceUrl: evidence.provenance?.evidenceUrl,
    acceptedAt: evidence.provenance?.acceptedAt
  };
}

/** Resolve a canonical persistent-world factor without confusing a hierarchy
 * alias (for example Initial UI Claims) with a second analytical identity. */
export function persistentWorldFactualBindingForFactor(canonicalFactorId: string, label: string): PersistentWorldFactualBinding {
  if (canonicalFactorId.startsWith("fixture-factor:")) return { status: "FIXTURE_ONLY", label };
  const layoffs = layoffsFactorSourceState(canonicalFactorId);
  if (!layoffs) return persistentWorldFactualBinding(label);
  if (layoffs.activationState === "ACCEPTED" && canonicalFactorId === "factor:canonical:initial-claims") {
    const metric = factualSnapshot.extensions["auxsays.phase2.metrics"].find((item) => item.id === "US_LABOR_INITIAL_UI_CLAIMS");
    if (metric) {
      const sourceId = metric.sourceRefs[0];
      const source = factualSnapshot.sources[sourceId];
      const provenanceId = metric.provenanceRefs[0];
      const provenance = factualSnapshot.extensions["auxsays.phase3.provenance"]?.[provenanceId];
      const seriesId = metric.sourceSeriesIds?.[0];
      return {
        status: "CONNECTED", label, displayValue: metric.displayValue, validTime: metric.validTime,
        provider: source?.provider, dataset: source?.dataset, seriesId, freshness: source?.freshness,
        evidenceUrl: seriesId ? provenance?.seriesEvidenceUrls?.[seriesId] ?? provenance?.evidenceUrl : provenance?.evidenceUrl,
        methodologyUrl: source?.methodologyUrl, acquisitionProvenanceUrl: provenance?.evidenceUrl,
        acceptedAt: provenance?.acceptedAt, candidateSeries: layoffs.series
      };
    }
  }
  const status: PersistentWorldBindingStatus = layoffs.activationState === "ACCEPTED"
    ? "SOURCE_IDENTIFIED"
    : layoffs.activationState;
  return {
    status,
    label,
    candidateSeriesId: layoffs.series[0]?.seriesId,
    candidateSeries: layoffs.series,
    blockedReason: layoffs.blockedReason
  };
}
