import { describe, expect, it } from "vitest";
import {
  appendObservation,
  createChangeEvent,
  evaluateDestinationImpact,
  evaluateHighlight,
  evaluateMateriality,
  evaluateSourceHealth,
  interpretChange,
  selectObservationAsOf,
  validateExternalEventCandidate,
  type DestinationContextProfile,
  type InterpretationProfile,
  type MaterialityProfile,
  type ObservationVersion,
} from "../src/temporal";
import {
  PERSISTENT_ACCEPTED_IMPACT_COUNT,
  persistentChangeNotices,
  persistentChangesForWindow,
} from "../src/data/persistentWorldTemporalReadModel";

const materialityProfile: MaterialityProfile = {
  profileId: "materiality:claims:weekly",
  version: "1.0.0",
  factorId: "factor:initial-claims",
  cadence: "WEEKLY",
  absoluteThreshold: 5,
  relativePercentThreshold: 2,
  thresholdRule: "ANY_CONFIGURED",
};

function observation(overrides: Partial<ObservationVersion> = {}): ObservationVersion {
  return {
    stateType: "OBS",
    observationId: "obs:claims:2026-08-01:advance",
    factorId: "factor:initial-claims",
    sourceId: "dol-ui-claims",
    sourceNativeId: "dol:2026-08-01",
    releaseId: "release:2026-08-06",
    objectHash: "sha256:one",
    value: 200,
    unit: "thousand persons",
    seasonalAdjustment: "seasonally adjusted",
    geography: "United States",
    cadence: "WEEKLY",
    validTime: { start: "2026-08-01T00:00:00Z" },
    officialPublishedAt: "2026-08-06T12:30:00Z",
    publicationTimeProof: "PROVEN",
    retrievedAt: "2026-08-06T12:35:00Z",
    acceptedAt: "2026-08-06T12:45:00Z",
    revisionStatus: "ADVANCE",
    analysisAllowed: true,
    provenanceRefs: ["prov:dol:2026-08-06"],
    ...overrides,
  };
}

describe("temporal observation and change ledger", () => {
  it("retains immutable versions, deduplicates an exact retry, and rejects identity reuse", () => {
    const first = observation();
    const history = appendObservation([], first);
    expect(appendObservation(history, { ...first })).toBe(history);
    expect(() => appendObservation(history, { ...first, objectHash: "sha256:different", value: 999 })).toThrow(/immutable observation identity/);
    const revision = observation({ observationId: "obs:claims:2026-08-01:revised", releaseId: "release:2026-08-13", objectHash: "sha256:two", value: 194, officialPublishedAt: "2026-08-13T12:30:00Z", acceptedAt: "2026-08-13T12:45:00Z", revisionStatus: "REVISED" });
    const revisedHistory = appendObservation(history, revision);
    expect(revisedHistory).toHaveLength(2);
    expect(revisedHistory[0]).toStrictEqual(first);
    expect(revisedHistory[1].revisionStatus).toBe("REVISED");
  });

  it("keeps public and operational replay cutoffs distinct", () => {
    const delayedAcceptance = observation({ acceptedAt: "2026-08-08T10:00:00Z" });
    expect(selectObservationAsOf([delayedAcceptance], delayedAcceptance.factorId, "2026-08-07T00:00:00Z", "PUBLICLY_AVAILABLE_AS_OF")?.observationId).toBe(delayedAcceptance.observationId);
    expect(selectObservationAsOf([delayedAcceptance], delayedAcceptance.factorId, "2026-08-07T00:00:00Z", "OPERATIONALLY_KNOWN_AS_OF")).toBeUndefined();
    expect(selectObservationAsOf([delayedAcceptance], delayedAcceptance.factorId, "2026-08-09T00:00:00Z", "OPERATIONALLY_KNOWN_AS_OF")?.observationId).toBe(delayedAcceptance.observationId);
  });

  it("creates only material comparable change events and never fabricates hourly movement", () => {
    const previous = observation();
    const unchanged = observation({ observationId: "obs:unchanged", releaseId: "release:unchanged", objectHash: "sha256:unchanged", value: 200 });
    const immaterial = observation({ observationId: "obs:small", releaseId: "release:small", objectHash: "sha256:small", value: 202 });
    const material = observation({ observationId: "obs:material", releaseId: "release:material", objectHash: "sha256:material", value: 209 });
    expect(createChangeEvent(previous, unchanged, materialityProfile, "2026-08-13T12:45:00Z")).toBeUndefined();
    expect(createChangeEvent(previous, immaterial, materialityProfile, "2026-08-13T12:45:00Z")).toBeUndefined();
    const event = createChangeEvent(previous, material, materialityProfile, "2026-08-13T12:45:00Z");
    expect(event).toMatchObject({ direction: "INCREASE", absoluteDelta: 9, materiality: "MATERIAL_INCREASE" });
    expect(event?.occurredAt).toBe(material.validTime.start);
  });

  it("applies materiality only to comparable native-cadence observations", () => {
    const current = observation({ value: 209 });
    expect(evaluateMateriality(observation(), current, materialityProfile).state).toBe("MATERIAL_INCREASE");
    expect(evaluateMateriality(observation({ unit: "persons" }), current, materialityProfile).state).toBe("NO_COMPARABLE_REFERENCE");
  });
});

describe("interpretation, destination impact, and highlight lifecycle", () => {
  const event = createChangeEvent(observation(), observation({ observationId: "obs:material", releaseId: "release:material", objectHash: "sha256:material", value: 209 }), materialityProfile, "2026-08-13T12:45:00Z")!;

  it("uses a versioned deterministic interpretation with explicit evidence inputs", () => {
    const profile: InterpretationProfile = {
      profileId: "interpretation:claims",
      version: "1.0.0",
      factorId: event.factorId,
      methodRef: "method:claims-change@1.0.0",
      rules: [{ materiality: "MATERIAL_INCREASE", label: "Claims increased materially", summary: "More initial claims were reported than in the previous comparable week." }],
    };
    expect(interpretChange(event, profile)).toMatchObject({ stateType: "CALC", profileVersion: "1.0.0", inputEventRef: event.eventId });
  });

  it("allows one source change to have opposite destination meanings only through accepted profiles", () => {
    const profiles: DestinationContextProfile[] = [
      { profileId: "impact:claims:labor", version: "1.0.0", sourceFactorId: event.factorId, destinationNodeId: "labor-market", relationshipId: "rel:claims:labor", relationshipVersion: "1.0.0", relationshipStatus: "ACCEPTED", rules: [{ direction: "INCREASE", impact: "ADVERSE" }] },
      { profileId: "impact:claims:staffing", version: "1.0.0", sourceFactorId: event.factorId, destinationNodeId: "claims-processing-demand", relationshipId: "rel:claims:staffing", relationshipVersion: "1.0.0", relationshipStatus: "ACCEPTED", rules: [{ direction: "INCREASE", impact: "SUPPORTIVE" }] },
      { profileId: "impact:claims:candidate", version: "1.0.0", sourceFactorId: event.factorId, destinationNodeId: "candidate", relationshipId: "rel:claims:candidate", relationshipVersion: "0.1.0", relationshipStatus: "PROPOSED", rules: [{ direction: "INCREASE", impact: "ADVERSE" }] },
    ];
    expect(evaluateDestinationImpact(event, "labor-market", profiles).impact).toBe("ADVERSE");
    expect(evaluateDestinationImpact(event, "claims-processing-demand", profiles).impact).toBe("SUPPORTIVE");
    expect(evaluateDestinationImpact(event, "candidate", profiles).impact).toBe("UNKNOWN");
  });

  it("expires visual emphasis without deleting history", () => {
    const profile = { profileId: "highlight:weekly", version: "1.0.0", newForMs: 86_400_000, recentForMs: 7 * 86_400_000 };
    expect(evaluateHighlight(event, "2026-08-13T13:45:00Z", profile).state).toBe("NEW");
    expect(evaluateHighlight(event, "2026-08-15T13:45:00Z", profile).state).toBe("RECENT");
    expect(evaluateHighlight(event, "2026-08-28T13:45:00Z", profile).state).toBe("EXPIRED");
    expect(event.eventId).toContain("change:");
  });
});

describe("source health, notification read model, and external-event boundary", () => {
  it("keeps operational source failure separate from economic impact", () => {
    const health = evaluateSourceHealth({ evaluatedAt: "2026-08-28T00:00:00Z", nextExpectedReleaseAt: "2026-08-13T00:00:00Z", lastSuccessfulRetrievalAt: "2026-08-12T00:00:00Z", operationalCondition: "UNAVAILABLE" }, { profileId: "health:dol", version: "1.0.0", sourceId: "dol-ui-claims", cadence: "WEEKLY", delayGraceMs: 86_400_000, staleAfterMs: 7 * 86_400_000 });
    expect(health.state).toBe("UNAVAILABLE");
    const staleNotice = persistentChangeNotices.find((notice) => notice.kind === "SOURCE_STALE");
    expect(staleNotice).toMatchObject({ sourceHealthOnly: true, economicSignalEligible: false, impactClass: "UNKNOWN" });
    expect(PERSISTENT_ACCEPTED_IMPACT_COUNT).toBe(0);
  });

  it("filters accepted notices deterministically and links every event to a graph placement", () => {
    const recent = persistentChangesForWindow("RECENT");
    expect(recent).toEqual(persistentChangesForWindow("RECENT"));
    expect(persistentChangesForWindow("24H").every((notice) => Date.parse(notice.knownAt) >= Date.parse("2026-08-17T00:00:00Z"))).toBe(true);
    expect(persistentChangesForWindow("1Y").length).toBeGreaterThanOrEqual(recent.length);
    expect(persistentChangeNotices.every((notice) => notice.placementId.startsWith("placement:"))).toBe(true);
    expect(persistentChangeNotices.filter((notice) => notice.kind === "NEW_OFFICIAL_OBSERVATION").every((notice) => notice.evidenceUrl?.startsWith("https://data.bls.gov/timeseries/") || notice.evidenceUrl?.includes("dol.gov"))).toBe(true);
  });

  it("validates static external-event candidates but keeps adapters disabled and provenance mandatory", () => {
    const candidate = { eventId: "event:noaa:storm:1", status: "CANDIDATE" as const, adapterRef: "adapter:noaa@0.1.0", sourceNativeId: "storm:1", label: "Official storm advisory", validTime: { start: "2026-08-27T12:00:00Z" }, knownAt: "2026-08-27T12:05:00Z", affectedNodeRefs: ["placement:policy-trade-external-shocks:weather-disruption"], evidenceRefs: ["evidence:noaa:storm:1"], provenanceRefs: ["prov:noaa:storm:1"], evidenceState: "VERIFIED_CANDIDATE" as const };
    expect(validateExternalEventCandidate(candidate)).toBe(candidate);
    expect(() => validateExternalEventCandidate({ ...candidate, evidenceRefs: [] })).toThrow(/evidence and provenance/);
  });
});
