import type { ChangeDirection, ChangeEvent } from "./temporalTypes";

export type DestinationImpact = "SUPPORTIVE" | "ADVERSE" | "MIXED" | "NEUTRAL" | "UNKNOWN";

export interface DestinationImpactRule {
  direction: ChangeDirection;
  impact: Exclude<DestinationImpact, "UNKNOWN">;
}

export interface DestinationContextProfile {
  profileId: string;
  version: string;
  sourceFactorId: string;
  destinationNodeId: string;
  relationshipId: string;
  relationshipVersion: string;
  relationshipStatus: "PROPOSED" | "ACCEPTED" | "REJECTED" | "RETIRED";
  rules: readonly DestinationImpactRule[];
}

export interface DestinationImpactEvaluation {
  destinationNodeId: string;
  impact: DestinationImpact;
  profileId?: string;
  profileVersion?: string;
  relationshipRef?: string;
  reason: string;
}

export function evaluateDestinationImpact(
  event: ChangeEvent,
  destinationNodeId: string,
  profiles: readonly DestinationContextProfile[],
): DestinationImpactEvaluation {
  const profile = profiles.find((candidate) => candidate.sourceFactorId === event.factorId
    && candidate.destinationNodeId === destinationNodeId
    && candidate.relationshipStatus === "ACCEPTED");
  if (!profile) return { destinationNodeId, impact: "UNKNOWN", reason: "no accepted destination-context mapping" };
  const rule = profile.rules.find((candidate) => candidate.direction === event.direction);
  if (!rule) return { destinationNodeId, impact: "UNKNOWN", reason: "accepted profile has no rule for this direction" };
  return {
    destinationNodeId,
    impact: rule.impact,
    profileId: profile.profileId,
    profileVersion: profile.version,
    relationshipRef: `${profile.relationshipId}@${profile.relationshipVersion}`,
    reason: "deterministic destination-context rule",
  };
}
