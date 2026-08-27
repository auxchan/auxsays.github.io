import activeFactualSnapshot from "../../../data/review/local-active-pdi-test-snapshot.json";
import { laborMarketHierarchy, observationForFactor, evidenceForFactor } from "./laborMarketReadModel";
import { createSnapshotViewModel } from "./snapshotViewModelFactory";
import { validatePublicSnapshot } from "./validatePublicSnapshot";

export type PersistentWorldBindingStatus = "CONNECTED" | "SOURCE_IDENTIFIED" | "UNMAPPED";

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
