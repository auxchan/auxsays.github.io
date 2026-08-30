import { assertNonEmpty, timestampMs, type TemporalInterval } from "./temporalTypes";

export interface ExternalEventAdapterDefinition {
  adapterId: string;
  version: string;
  provider: string;
  dataset: string;
  authorityTier: string;
  methodologyUrl: string;
  evidenceUrlTemplate: string;
  cadence: string;
  schemaFingerprint: string;
  rightsDecisionRef: string;
  parserVersion: string;
  enabled: false;
}

export interface ExternalEventCandidate {
  eventId: string;
  status: "CANDIDATE" | "REJECTED";
  adapterRef: string;
  sourceNativeId: string;
  label: string;
  validTime: TemporalInterval;
  knownAt: string;
  affectedNodeRefs: readonly string[];
  evidenceRefs: readonly string[];
  provenanceRefs: readonly string[];
  evidenceState: "SOURCE_IDENTIFIED" | "RETRIEVED_UNVERIFIED" | "VERIFIED_CANDIDATE" | "REJECTED";
}

export function validateExternalEventCandidate(candidate: ExternalEventCandidate): ExternalEventCandidate {
  for (const [field, value] of Object.entries({
    eventId: candidate.eventId, adapterRef: candidate.adapterRef, sourceNativeId: candidate.sourceNativeId, label: candidate.label,
  })) assertNonEmpty(value, field);
  timestampMs(candidate.validTime.start, "validTime.start");
  if (candidate.validTime.end) timestampMs(candidate.validTime.end, "validTime.end");
  timestampMs(candidate.knownAt, "knownAt");
  if (!candidate.evidenceRefs.length || !candidate.provenanceRefs.length) throw new Error("external event candidate requires evidence and provenance");
  if (!candidate.affectedNodeRefs.length) throw new Error("external event candidate requires an explicit affected-node scope");
  return candidate;
}
