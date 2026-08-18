import { describe, expect, it } from "vitest";
import { adaptLocalFactualCandidate, validateLocalFactualCandidate, type LocalFactualCandidate } from "../src/data/factualSnapshotAdapter";
import { validatePublicSnapshot } from "../src/data/validatePublicSnapshot";

export function candidate(): LocalFactualCandidate {
  const metrics = Array.from({ length: 6 }, (_, index) => ({
    id: `US_LABOR_TEST_${index}`,
    label: `Observed labor metric ${index}`,
    stateType: "OBS" as const,
    value: String(index + 1),
    unit: "percent",
    observationPeriod: "2026-07",
    sourceId: index === 3 ? "dol-ui-claims" : index > 3 ? "bls-jolts" : index === 0 ? "bls-ces" : "bls-cps",
    sourceLabel: "Original authority",
    publicTime: "2026-08-01T00:00:00Z",
    retrievedTime: "2026-08-01T00:01:00Z",
    acceptedTime: "2026-08-01T00:02:00Z",
    publicationTimeKind: "official" as const,
    vintageId: "v1",
    revisionNumber: 0,
    sourceHealth: "current" as const,
    rightsState: "ALLOW" as const,
    provenanceUrl: "https://www.bls.gov/",
    artifactSha256: "a".repeat(64)
  }));
  return { schemaVersion: "phase3-factual-candidate-1.0.0", publicationClass: "factual", activationStatus: "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED", generatedAt: "2026-08-01T00:03:00Z", geography: "US", metrics, forecasts: [], scenarios: [], rankings: [], events: [], outlook: { status: "unavailable_not_yet_supported", message: "Forecast unavailable / not yet supported" } };
}

describe("Phase-3 local factual candidate", () => {
  it("adapts and validates six factual OBS records", () => {
    const adapted = adaptLocalFactualCandidate(candidate());
    expect(validatePublicSnapshot(adapted)).toBe(adapted);
    expect(adapted.extensions["auxsays.phase2.metrics"]).toHaveLength(6);
  });

  it("contains no fixture or outlook claims", () => {
    const adapted = adaptLocalFactualCandidate(candidate());
    expect(adapted.outlook.forecasts).toEqual([]);
    expect(adapted.outlook.industries).toEqual([]);
    expect(JSON.stringify(adapted)).not.toContain("SYNTHETIC TEST");
  });

  it("rejects a forecast mixed into factual metrics", () => {
    const invalid = candidate() as unknown as { metrics: Array<{ stateType: string }> };
    invalid.metrics[0].stateType = "FCST";
    expect(() => validateLocalFactualCandidate(invalid)).toThrow(/OBS/);
  });

  it("rejects impossible temporal ordering", () => {
    const invalid = candidate();
    invalid.metrics[0].retrievedTime = "2026-07-01T00:00:00Z";
    expect(() => validateLocalFactualCandidate(invalid)).toThrow(/temporal/);
  });
});
