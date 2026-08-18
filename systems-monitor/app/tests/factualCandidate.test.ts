import { describe, expect, it } from "vitest";
import publicCandidate from "../../data/review/factual-snapshot-candidate.json";
import type { PublicSnapshot } from "../src/data/publicSnapshotTypes";
import { validatePublicSnapshot } from "../src/data/validatePublicSnapshot";

export function candidate(): PublicSnapshot {
  return structuredClone(publicCandidate) as unknown as PublicSnapshot;
}

const oldInternalShape = {
  schemaVersion: "phase3-factual-candidate-1.0.0",
  publicationClass: "factual",
  activationStatus: "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED",
  generatedAt: "2026-08-18T19:46:00Z",
  geography: "US",
  metrics: [], forecasts: [], scenarios: [], rankings: [], events: [],
  outlook: { status: "unavailable_not_yet_supported" }
};

describe("Phase-3 factual public PDI candidate", () => {
  it("validates the actual six-observation PDI artifact", () => {
    const value = candidate();
    expect(validatePublicSnapshot(value)).toBe(value);
    expect(value.extensions["auxsays.phase2.metrics"]).toHaveLength(6);
  });

  it("rejects the exact pre-correction internal review shape", () => {
    expect(() => validatePublicSnapshot(oldInternalShape)).toThrow(/schemaVersion/);
  });

  it("rejects missing contractVersion", () => {
    const value = candidate() as unknown as Record<string, unknown>;
    delete value.contractVersion;
    expect(() => validatePublicSnapshot(value)).toThrow(/contractVersion/);
  });

  it("rejects missing snapshot metadata", () => {
    const value = candidate() as unknown as Record<string, unknown>;
    delete value.snapshot;
    expect(() => validatePublicSnapshot(value)).toThrow(/snapshot/);
  });

  it("rejects missing snapshot time", () => {
    const value = candidate() as unknown as { snapshot: Record<string, unknown> };
    delete value.snapshot.publishedAt;
    expect(() => validatePublicSnapshot(value)).toThrow(/publishedAt/);
  });

  it("rejects missing source snapshot identity", () => {
    const value = candidate();
    value.snapshot.sourceSnapshotId = "";
    expect(() => validatePublicSnapshot(value)).toThrow(/sourceSnapshotId/);
  });

  it("rejects non-canonical publicationClass", () => {
    const value = candidate() as unknown as { snapshot: { publicationClass: string } };
    value.snapshot.publicationClass = "production";
    expect(() => validatePublicSnapshot(value)).toThrow(/publicationClass/);
  });

  it("rejects forecast state mixed into factual metrics", () => {
    const value = candidate();
    value.extensions["auxsays.phase2.metrics"][0].stateType = "FCST";
    expect(() => validatePublicSnapshot(value)).toThrow(/OBS/);
  });

  it("rejects fixture claims in a factual candidate", () => {
    const value = candidate();
    value.sources["bls-ces"].provider = "SYNTHETIC TEST PROVIDER";
    expect(() => validatePublicSnapshot(value)).toThrow(/rights-cleared/);
  });

  it("rejects incompatible schema", () => {
    const value = candidate() as unknown as { schemaVersion: string };
    value.schemaVersion = "2.0.0";
    expect(() => validatePublicSnapshot(value)).toThrow(/schemaVersion/);
  });

  it("rejects malformed source references", () => {
    const value = candidate();
    value.extensions["auxsays.phase2.metrics"][0].sourceRefs = ["missing-source"];
    expect(() => validatePublicSnapshot(value)).toThrow(/sourceRefs/);
  });

  it("rejects malformed provenance references", () => {
    const value = candidate();
    value.extensions["auxsays.phase2.metrics"][0].provenanceRefs = ["missing-provenance"];
    expect(() => validatePublicSnapshot(value)).toThrow(/provenanceRefs/);
  });

  it("keeps BLS publication times distinct from retrieval and acceptance", () => {
    const records = Object.values(candidate().extensions["auxsays.phase3.provenance"] ?? {});
    const ces = records.find((record) => record.sourceId === "bls-ces")!;
    const jolts = records.find((record) => record.sourceId === "bls-jolts")!;
    expect(ces.publishedAt).toBe("2026-08-07T12:30:00Z");
    expect(jolts.publishedAt).toBe("2026-08-04T14:00:00Z");
    expect(ces.publishedAt).not.toBe(ces.retrievedAt);
    expect(ces.retrievedAt).not.toBe(ces.acceptedAt);
  });

  it("keeps DOL observation freshness separate from XML path health", () => {
    const health = candidate().extensions["auxsays.phase3.sourceHealth"]?.["dol-ui-claims"];
    expect(health?.observationFreshness).toBe("current");
    expect(health?.retrievalPathHealth).toBe("stale");
    expect(health?.retrievalPathReason).toContain("2026-07-18");
  });

  it("contains exact official series IDs", () => {
    const records = Object.values(candidate().extensions["auxsays.phase3.provenance"] ?? {});
    const series = new Set(records.flatMap((record) => record.seriesIds));
    expect(series).toEqual(new Set(["CES0000000001", "LNS14000000", "LNS11300000", "JTS000000000000000JOL", "JTS000000000000000HIL", "DOL-UI-SA-INITIAL"]));
  });
});
