import type { ChangeEvent } from "./temporalTypes";

export interface InterpretationRule {
  materiality: ChangeEvent["materiality"];
  label: string;
  summary: string;
}

export interface InterpretationProfile {
  profileId: string;
  version: string;
  factorId: string;
  methodRef: string;
  rules: readonly InterpretationRule[];
}

export interface InterpretationRecord {
  stateType: "CALC";
  calculationId: string;
  profileId: string;
  profileVersion: string;
  methodRef: string;
  inputObservationRefs: readonly string[];
  inputEventRef: string;
  label: string;
  summary: string;
}

export function interpretChange(event: ChangeEvent, profile: InterpretationProfile): InterpretationRecord {
  if (profile.factorId !== event.factorId) throw new Error("interpretation profile does not match event factor");
  const rule = profile.rules.find((candidate) => candidate.materiality === event.materiality);
  if (!rule) throw new Error(`no deterministic interpretation rule for ${event.materiality}`);
  return Object.freeze({
    stateType: "CALC",
    calculationId: `interpretation:${event.eventId}:${profile.profileId}@${profile.version}`,
    profileId: profile.profileId,
    profileVersion: profile.version,
    methodRef: profile.methodRef,
    inputObservationRefs: Object.freeze([event.previousObservationId, event.currentObservationId].filter((id): id is string => Boolean(id))),
    inputEventRef: event.eventId,
    label: rule.label,
    summary: rule.summary,
  });
}
