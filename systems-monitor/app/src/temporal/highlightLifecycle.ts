import { timestampMs, type ChangeEvent } from "./temporalTypes";

export type HighlightState = "INACTIVE" | "NEW" | "RECENT" | "EXPIRED";

export interface HighlightProfile {
  profileId: string;
  version: string;
  newForMs: number;
  recentForMs: number;
}

export interface HighlightEvaluation {
  state: HighlightState;
  eventId: string;
  profileRef: string;
  ageMs: number;
}

export function evaluateHighlight(
  event: ChangeEvent,
  evaluatedAt: string,
  profile: HighlightProfile,
): HighlightEvaluation {
  if (profile.newForMs < 0 || profile.recentForMs < profile.newForMs) throw new Error("invalid highlight durations");
  const ageMs = Math.max(0, timestampMs(evaluatedAt, "evaluatedAt") - timestampMs(event.knownAt, "event.knownAt"));
  const isMaterial = event.materiality === "MATERIAL_INCREASE" || event.materiality === "MATERIAL_DECREASE";
  const state = !isMaterial ? "INACTIVE" : ageMs <= profile.newForMs ? "NEW" : ageMs <= profile.recentForMs ? "RECENT" : "EXPIRED";
  return { state, eventId: event.eventId, profileRef: `${profile.profileId}@${profile.version}`, ageMs };
}
