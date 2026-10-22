import type { Cadence, MaterialityState, ObservationVersion } from "./temporalTypes";

export interface MaterialityProfile {
  profileId: string;
  version: string;
  factorId: string;
  cadence: Cadence;
  absoluteThreshold?: number;
  relativePercentThreshold?: number;
  thresholdRule: "ANY_CONFIGURED" | "ALL_CONFIGURED";
}

export interface MaterialityEvaluation {
  state: MaterialityState;
  absoluteDelta?: number;
  relativeDeltaPercent?: number;
}

function comparable(previous: ObservationVersion, current: ObservationVersion): boolean {
  return previous.factorId === current.factorId
    && previous.unit === current.unit
    && previous.geography === current.geography
    && previous.seasonalAdjustment === current.seasonalAdjustment
    && previous.cadence === current.cadence;
}

export function evaluateMateriality(
  previous: ObservationVersion | undefined,
  current: ObservationVersion,
  profile: MaterialityProfile,
): MaterialityEvaluation {
  if (profile.factorId !== current.factorId || profile.cadence !== current.cadence) {
    throw new Error("materiality profile does not match the current factor and native cadence");
  }
  if (profile.absoluteThreshold === undefined && profile.relativePercentThreshold === undefined) {
    throw new Error("materiality profile must configure at least one explicit threshold");
  }
  if (!previous || !comparable(previous, current)) return { state: "NO_COMPARABLE_REFERENCE" };

  const absoluteDelta = current.value - previous.value;
  if (absoluteDelta === 0) return { state: "UNCHANGED", absoluteDelta: 0, relativeDeltaPercent: 0 };
  const relativeDeltaPercent = previous.value === 0 ? undefined : (absoluteDelta / Math.abs(previous.value)) * 100;
  const checks: boolean[] = [];
  if (profile.absoluteThreshold !== undefined) checks.push(Math.abs(absoluteDelta) >= profile.absoluteThreshold);
  if (profile.relativePercentThreshold !== undefined) {
    checks.push(relativeDeltaPercent !== undefined && Math.abs(relativeDeltaPercent) >= profile.relativePercentThreshold);
  }
  const material = profile.thresholdRule === "ALL_CONFIGURED" ? checks.every(Boolean) : checks.some(Boolean);
  return {
    state: material ? (absoluteDelta > 0 ? "MATERIAL_INCREASE" : "MATERIAL_DECREASE") : "IMMATERIAL",
    absoluteDelta,
    relativeDeltaPercent,
  };
}
