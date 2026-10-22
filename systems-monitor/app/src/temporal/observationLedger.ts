import { evaluateMateriality, type MaterialityProfile } from "./materiality";
import {
  assertNonEmpty,
  timestampMs,
  type ChangeEvent,
  type ObservationVersion,
  type ReplayMode,
} from "./temporalTypes";

function validateObservation(record: ObservationVersion): void {
  for (const [field, value] of Object.entries({
    observationId: record.observationId, factorId: record.factorId, sourceId: record.sourceId,
    sourceNativeId: record.sourceNativeId, releaseId: record.releaseId, objectHash: record.objectHash,
    unit: record.unit, geography: record.geography, seasonalAdjustment: record.seasonalAdjustment,
  })) assertNonEmpty(value, field);
  if (!Number.isFinite(record.value)) throw new Error("observation value must be finite");
  timestampMs(record.validTime.start, "validTime.start");
  if (record.validTime.end) timestampMs(record.validTime.end, "validTime.end");
  timestampMs(record.retrievedAt, "retrievedAt");
  if (record.acceptedAt) timestampMs(record.acceptedAt, "acceptedAt");
  if (record.publicationTimeProof === "PROVEN") {
    if (!record.officialPublishedAt) throw new Error("proven publication time requires officialPublishedAt");
    timestampMs(record.officialPublishedAt, "officialPublishedAt");
  } else if (record.officialPublishedAt) {
    throw new Error("unknown publication time cannot carry a guessed officialPublishedAt");
  }
}

export function appendObservation(
  history: readonly ObservationVersion[],
  candidate: ObservationVersion,
): readonly ObservationVersion[] {
  validateObservation(candidate);
  const duplicateId = history.find((record) => record.observationId === candidate.observationId);
  if (duplicateId && duplicateId.objectHash !== candidate.objectHash) {
    throw new Error("immutable observation identity cannot be reused for different content");
  }
  const exactRetry = history.some((record) => record.sourceId === candidate.sourceId
    && record.releaseId === candidate.releaseId
    && record.objectHash === candidate.objectHash
    && record.sourceNativeId === candidate.sourceNativeId
    && record.validTime.start === candidate.validTime.start);
  if (exactRetry) return history;
  if (duplicateId) return history;
  return Object.freeze([...history, Object.freeze({ ...candidate, provenanceRefs: Object.freeze([...candidate.provenanceRefs]) })]);
}

function knowledgeTime(record: ObservationVersion, mode: ReplayMode): string | undefined {
  if (!record.analysisAllowed) return undefined;
  if (mode === "PUBLICLY_AVAILABLE_AS_OF") {
    return record.publicationTimeProof === "PROVEN" ? record.officialPublishedAt : undefined;
  }
  return record.acceptedAt;
}

export function selectObservationAsOf(
  history: readonly ObservationVersion[],
  factorId: string,
  cutoff: string,
  mode: ReplayMode,
): ObservationVersion | undefined {
  const cutoffMs = timestampMs(cutoff, "cutoff");
  return history
    .filter((record) => record.factorId === factorId)
    .map((record) => ({ record, knownAt: knowledgeTime(record, mode) }))
    .filter((item): item is { record: ObservationVersion; knownAt: string } => Boolean(item.knownAt))
    .filter((item) => timestampMs(item.knownAt, "knowledge time") <= cutoffMs)
    .sort((left, right) => {
      const knowledgeOrder = timestampMs(right.knownAt, "knowledge time") - timestampMs(left.knownAt, "knowledge time");
      if (knowledgeOrder) return knowledgeOrder;
      const releaseOrder = right.record.releaseId.localeCompare(left.record.releaseId);
      return releaseOrder || right.record.observationId.localeCompare(left.record.observationId);
    })[0]?.record;
}

export function createChangeEvent(
  previous: ObservationVersion | undefined,
  current: ObservationVersion,
  profile: MaterialityProfile,
  knownAt: string,
): ChangeEvent | undefined {
  const evaluation = evaluateMateriality(previous, current, profile);
  if (evaluation.state !== "MATERIAL_INCREASE" && evaluation.state !== "MATERIAL_DECREASE") return undefined;
  const direction = evaluation.absoluteDelta! > 0 ? "INCREASE" : "DECREASE";
  return Object.freeze({
    eventId: `change:${current.observationId}:${profile.profileId}@${profile.version}`,
    factorId: current.factorId,
    previousObservationId: previous?.observationId,
    currentObservationId: current.observationId,
    direction,
    absoluteDelta: evaluation.absoluteDelta,
    relativeDeltaPercent: evaluation.relativeDeltaPercent,
    materiality: evaluation.state,
    materialityProfileId: profile.profileId,
    materialityProfileVersion: profile.version,
    occurredAt: current.validTime.start,
    knownAt,
  });
}
