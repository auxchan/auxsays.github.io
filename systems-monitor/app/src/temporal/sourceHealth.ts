import { timestampMs, type Cadence } from "./temporalTypes";

export type SourceHealthState =
  | "CURRENT" | "EXPECTED_NOT_DUE" | "DUE" | "DELAYED" | "STALE" | "UNAVAILABLE"
  | "SCHEMA_FORMAT_CHANGED" | "VALIDATION_FAILED" | "RIGHTS_BLOCKED";

export interface SourceHealthProfile {
  profileId: string;
  version: string;
  sourceId: string;
  cadence: Cadence;
  delayGraceMs: number;
  staleAfterMs: number;
}

export interface SourceHealthInput {
  evaluatedAt: string;
  nextExpectedReleaseAt?: string;
  lastSuccessfulRetrievalAt?: string;
  lastNewObservationAt?: string;
  operationalCondition: "OK" | "UNAVAILABLE" | "SCHEMA_FORMAT_CHANGED" | "VALIDATION_FAILED" | "RIGHTS_BLOCKED";
}

export interface SourceHealthEvaluation {
  sourceId: string;
  state: SourceHealthState;
  profileRef: string;
  freshnessEvaluatedAt: string;
  nextExpectedReleaseAt?: string;
  lastSuccessfulRetrievalAt?: string;
  lastNewObservationAt?: string;
  reason: string;
}

export function evaluateSourceHealth(input: SourceHealthInput, profile: SourceHealthProfile): SourceHealthEvaluation {
  if (profile.delayGraceMs < 0 || profile.staleAfterMs < profile.delayGraceMs) throw new Error("invalid source-health windows");
  const base = {
    sourceId: profile.sourceId,
    profileRef: `${profile.profileId}@${profile.version}`,
    freshnessEvaluatedAt: input.evaluatedAt,
    nextExpectedReleaseAt: input.nextExpectedReleaseAt,
    lastSuccessfulRetrievalAt: input.lastSuccessfulRetrievalAt,
    lastNewObservationAt: input.lastNewObservationAt,
  };
  if (input.operationalCondition !== "OK") {
    return { ...base, state: input.operationalCondition, reason: `explicit operational condition: ${input.operationalCondition}` };
  }
  if (!input.nextExpectedReleaseAt) return { ...base, state: "CURRENT", reason: "no expected release is currently recorded" };
  const now = timestampMs(input.evaluatedAt, "evaluatedAt");
  const expected = timestampMs(input.nextExpectedReleaseAt, "nextExpectedReleaseAt");
  if (now < expected) return { ...base, state: "EXPECTED_NOT_DUE", reason: "next official release is not due" };
  const overdue = now - expected;
  if (overdue === 0) return { ...base, state: "DUE", reason: "expected release window has opened" };
  if (overdue <= profile.delayGraceMs) return { ...base, state: "DUE", reason: "inside the explicit release grace window" };
  if (overdue <= profile.staleAfterMs) return { ...base, state: "DELAYED", reason: "expected release is late but not yet stale" };
  return { ...base, state: "STALE", reason: "expected release exceeded the cadence-aware stale window" };
}
