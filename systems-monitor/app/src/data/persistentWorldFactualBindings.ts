import { productionFactualSnapshot as activeFactualSnapshot } from "./productionDataReadModel";
import { laborMarketHierarchy, observationForFactor, evidenceForFactor } from "./laborMarketReadModel";
import { createSnapshotViewModel } from "./snapshotViewModelFactory";
import { validatePublicSnapshot } from "./validatePublicSnapshot";
import { layoffsFactorSourceState, type LayoffsClaimClassification } from "./layoffsBranchReadModel";
import {
  acceptedLayoffsHistoryForFactor,
  acceptedLayoffsHistoryFreshness,
  LAYOFFS_ACCEPTED_OBSERVATION_COUNT,
  type LayoffsAcceptedFactorSummary,
} from "./layoffsAcceptedHistoryReadModel";

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
  claimClassification?: LayoffsClaimClassification;
  blockedReason?: string;
  temporalHistory?: LayoffsAcceptedFactorSummary;
}

const factualSnapshot = createSnapshotViewModel(validatePublicSnapshot(activeFactualSnapshot as unknown));
const hierarchy = laborMarketHierarchy(factualSnapshot);
const factorsByLabel = new Map(Object.values(hierarchy.canonicalFactors).map((factor) => [factor.label.toLowerCase(), factor]));

export const PERSISTENT_FACTUAL_OBSERVATION_COUNT = factualSnapshot.extensions["auxsays.phase2.metrics"].length + LAYOFFS_ACCEPTED_OBSERVATION_COUNT;

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
  const temporalHistory = acceptedLayoffsHistoryForFactor(canonicalFactorId);
  if (temporalHistory) {
    const primary = temporalHistory.primary;
    return {
      status: "CONNECTED",
      label,
      displayValue: primary.currentDisplay,
      validTime: primary.current.validTime,
      provider: primary.provider,
      dataset: primary.dataset,
      seriesId: primary.sourceSeriesId,
      freshness: acceptedLayoffsHistoryFreshness(primary.sourceId),
      evidenceUrl: primary.current.evidenceUrl,
      methodologyUrl: primary.current.methodologyUrl,
      acquisitionProvenanceUrl: primary.current.provenanceUrl,
      acceptedAt: primary.current.acceptedTime,
      candidateSeries: layoffs.series,
      claimClassification: layoffs.claimClassification,
      temporalHistory,
    };
  }
  const status: PersistentWorldBindingStatus = layoffs.activationState === "ACCEPTED"
    ? "SOURCE_IDENTIFIED"
    : layoffs.activationState;
  return {
    status,
    label,
    candidateSeriesId: layoffs.series[0]?.seriesId,
    candidateSeries: layoffs.series,
    claimClassification: layoffs.claimClassification,
    blockedReason: layoffs.blockedReason
  };
}
