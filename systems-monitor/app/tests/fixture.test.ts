import { describe, expect, it } from "vitest";
import { phase2Fixture } from "../src/fixtures/phase2Fixture";
import { publicPayloadHasIndependentFixtureFlag, validatePublicSnapshot } from "../src/data/validatePublicSnapshot";
import { createSnapshotViewModel } from "../src/data/snapshotViewModelFactory";

describe("Phase-2 public fixture", () => {
  it("validates the complete typed public envelope", () => {
    expect(validatePublicSnapshot(phase2Fixture)).toBe(phase2Fixture);
    expect(publicPayloadHasIndependentFixtureFlag(phase2Fixture)).toBe(false);
  });

  it("exercises hierarchy, ranking, horizons, states, timing, and trace boundaries", () => {
    const view = createSnapshotViewModel(validatePublicSnapshot(phase2Fixture));
    expect(view.systems).toHaveLength(10);
    expect(view.systems[0].children).toHaveLength(11);
    expect(view.systems[0].children?.[0].children).toHaveLength(10);
    expect(view.systems[0].children?.slice(9, 11).every((item) => item.nearTie)).toBe(true);
    expect(new Set(phase2Fixture.outlook.forecasts.map((item) => item.stateType))).toEqual(new Set(["FCST", "SCEN"]));
    expect(new Set(phase2Fixture.outlook.horizons.map((item) => item.id))).toEqual(new Set(["current-year", "next-year", "plus-3-years"]));
    expect(new Set(Object.values(phase2Fixture.sources).map((item) => item.freshness))).toEqual(new Set(["current", "delayed", "stale"]));
    expect(new Set(phase2Fixture.extensions["auxsays.phase2.trace"].edges.map((item) => item.classification))).toEqual(new Set(["Direct", "Statistical", "Modeled", "Hypothesis"]));
    expect(phase2Fixture.extensions["auxsays.phase2.trace"].edges.some((item) => item.direction === "offsetting")).toBe(true);
  });

  it("rejects an independent public isFixture flag", () => {
    expect(() => validatePublicSnapshot({ ...phase2Fixture, isFixture: true })).toThrow(/isFixture/);
  });

  it("rejects embedded public children and resolves childRefs only after validation", () => {
    const invalid = structuredClone(phase2Fixture) as unknown as { systems: Array<Record<string, unknown>> };
    invalid.systems[0].children = [];
    expect(() => validatePublicSnapshot(invalid)).toThrow(/embedded children/);
    expect(createSnapshotViewModel(phase2Fixture).systems[0].children).toHaveLength(11);
  });

  it("contains every required degraded-state fixture variant", () => {
    expect(new Set(phase2Fixture.extensions["auxsays.phase2.fixtureVariants"])).toEqual(new Set([
      "normal", "loading", "delayed", "stale", "insufficient-evidence", "forecast-unavailable",
      "high-disagreement", "partial-payload", "snapshot-unavailable"
    ]));
  });

  it("preserves hiring/openings and distinct demand-allocation meanings", () => {
    expect(phase2Fixture.outlook.occupations.every((item) => item.displayValue.includes("expected-opening"))).toBe(true);
    const allocationTypes = phase2Fixture.outlook.demandAllocation.map((item) => item.allocationType);
    expect(allocationTypes).toContain("final-demand allocation share");
    expect(allocationTypes).toContain("constrained resource allocation share");
    expect(allocationTypes).not.toContain("company market share");
  });

  it("keeps source and snapshot timing dimensions independent", () => {
    const source = phase2Fixture.sources["fixture-source-current"];
    expect(new Set([source.observationTime, source.publishedAt, source.retrievedAt, source.freshnessEvaluatedAt, source.nextExpectedReleaseAt]).size).toBe(5);
    expect(phase2Fixture.snapshot.generatedAt).not.toBe(phase2Fixture.snapshot.publishedAt);
  });
});
