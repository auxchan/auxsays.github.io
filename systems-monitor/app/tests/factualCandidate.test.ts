import { describe, expect, it } from "vitest";
import publicCandidate from "../../data/review/factual-snapshot-candidate.json";
import activeProof from "../../data/review/local-active-pdi-test-snapshot.json";
import type { PublicationCandidate, PublicSnapshot } from "../src/data/publicSnapshotTypes";
import { validatePublicationCandidate, validatePublicSnapshot } from "../src/data/validatePublicSnapshot";
import { createCandidateViewModel } from "../src/data/snapshotViewModelFactory";

export function candidate(): PublicationCandidate {
  return structuredClone(publicCandidate) as unknown as PublicationCandidate;
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
  it("validates the six-observation pre-activation artifact", () => {
    const value = candidate();
    expect(validatePublicationCandidate(value)).toBe(value);
    expect(value.payload.extensions["auxsays.phase2.metrics"]).toHaveLength(6);
    expect(value.candidate).not.toHaveProperty("publishedAt");
    expect(value).not.toHaveProperty("snapshot");
  });

  it("cannot masquerade as an active PDI snapshot", () => {
    expect(() => validatePublicSnapshot(candidate())).toThrow(/schemaVersion/);
    expect(validatePublicSnapshot(structuredClone(activeProof) as unknown as PublicSnapshot).snapshot.publishedAt).toBe("2026-08-18T23:55:46.897033Z");
  });

  it("rejects the exact pre-correction internal review shape", () => {
    expect(() => validatePublicationCandidate(oldInternalShape)).toThrow(/pre-activation/);
  });

  it("rejects missing contractVersion", () => {
    const value = candidate() as unknown as { candidate: Record<string, unknown> };
    delete value.candidate.targetContractVersion;
    expect(() => validatePublicationCandidate(value)).toThrow(/target contractVersion/);
  });

  it("rejects a fabricated candidate publication time", () => {
    const value = candidate() as unknown as { candidate: Record<string, unknown> };
    value.candidate.publishedAt = "2026-08-18T19:46:00Z";
    expect(() => validatePublicationCandidate(value)).toThrow(/publishedAt/);
  });

  it("rejects missing source snapshot identity", () => {
    const value = candidate();
    value.candidate.sourceSnapshotId = "";
    expect(() => validatePublicationCandidate(value)).toThrow(/sourceSnapshotId/);
  });

  it("rejects non-canonical publicationClass", () => {
    const value = candidate() as unknown as { candidate: { publicationClass: string } };
    value.candidate.publicationClass = "production";
    expect(() => validatePublicationCandidate(value)).toThrow(/publicationClass/);
  });

  it("rejects forecast state mixed into factual metrics", () => {
    const value = candidate();
    value.payload.extensions["auxsays.phase2.metrics"][0].stateType = "FCST";
    expect(() => validatePublicationCandidate(value)).toThrow(/OBS/);
  });

  it("rejects fixture claims in a factual candidate", () => {
    const value = candidate();
    value.payload.sources["bls-ces"].provider = "SYNTHETIC TEST PROVIDER";
    expect(() => validatePublicationCandidate(value)).toThrow(/rights-cleared/);
  });

  it("rejects incompatible schema", () => {
    const value = candidate() as unknown as { candidate: { targetSchemaVersion: string } };
    value.candidate.targetSchemaVersion = "2.0.0";
    expect(() => validatePublicationCandidate(value)).toThrow(/schemaVersion/);
  });

  it("rejects malformed source references", () => {
    const value = candidate();
    value.payload.extensions["auxsays.phase2.metrics"][0].sourceRefs = ["missing-source"];
    expect(() => validatePublicationCandidate(value)).toThrow(/sourceRefs/);
  });

  it("rejects malformed provenance references", () => {
    const value = candidate();
    value.payload.extensions["auxsays.phase2.metrics"][0].provenanceRefs = ["missing-provenance"];
    expect(() => validatePublicationCandidate(value)).toThrow(/provenanceRefs/);
  });

  it("keeps BLS publication times distinct from retrieval and acceptance", () => {
    const records = Object.values(candidate().payload.extensions["auxsays.phase3.provenance"] ?? {});
    const ces = records.find((record) => record.sourceId === "bls-ces")!;
    const jolts = records.find((record) => record.sourceId === "bls-jolts")!;
    expect(ces.publishedAt).toBe("2026-08-07T12:30:00Z");
    expect(jolts.publishedAt).toBe("2026-08-04T14:00:00Z");
    expect(ces.publishedAt).not.toBe(ces.retrievedAt);
    expect(ces.retrievedAt).not.toBe(ces.acceptedAt);
  });

  it("keeps DOL observation freshness separate from XML path health", () => {
    const health = candidate().payload.extensions["auxsays.phase3.sourceHealth"]?.["dol-ui-claims"];
    expect(health?.observationFreshness).toBe("current");
    expect(health?.retrievalPathHealth).toBe("stale");
    expect(health?.retrievalPathReason).toContain("2026-07-18");
  });

  it("contains exact official series IDs", () => {
    const records = Object.values(candidate().payload.extensions["auxsays.phase3.provenance"] ?? {});
    const series = new Set(records.flatMap((record) => record.seriesIds));
    expect(series).toEqual(new Set(["CES0000000001", "LNS14000000", "LNS11300000", "JTS000000000000000JOL", "JTS000000000000000HIL", "DOL-UI-SA-INITIAL"]));
  });

  it("maps every factual metric to one official series and reachable evidence", () => {
    const value = candidate();
    const provenance = value.payload.extensions["auxsays.phase3.provenance"] ?? {};
    const expected = new Map([
      ["US_LABOR_TOTAL_NONFARM_PAYROLLS", "CES0000000001"],
      ["US_LABOR_U3_UNEMPLOYMENT_RATE", "LNS14000000"],
      ["US_LABOR_FORCE_PARTICIPATION_RATE", "LNS11300000"],
      ["US_LABOR_INITIAL_UI_CLAIMS", "DOL-UI-SA-INITIAL"],
      ["US_LABOR_JOB_OPENINGS", "JTS000000000000000JOL"],
      ["US_LABOR_HIRES", "JTS000000000000000HIL"]
    ]);
    for (const metric of value.payload.extensions["auxsays.phase2.metrics"]) {
      expect(metric.sourceSeriesIds).toEqual([expected.get(metric.id)]);
      expect(metric.provenanceRefs.every((reference) => provenance[reference].seriesIds.includes(metric.sourceSeriesIds![0]))).toBe(true);
      expect(metric.provenanceRefs.every((reference) => provenance[reference].evidenceUrl.startsWith("https://"))).toBe(true);
    }
  });

  it("carries the real DOL revision pair and both replay answers", () => {
    const proof = candidate().payload.extensions["auxsays.phase3.revisionEvidence"]?.[0];
    expect(proof?.validTime).toBe("2024-03-02");
    expect(proof?.releases.map((release) => release.value)).toEqual([217000, 210000]);
    expect(proof?.releases.map((release) => release.evidenceUrl)).toEqual([
      "https://www.dol.gov/sites/dolgov/files/OPA/newsreleases/ui-claims/20240471.pdf",
      "https://www.dol.gov/sites/dolgov/files/OPA/newsreleases/ui-claims/20240527.pdf"
    ]);
    expect(proof?.asKnown.value).toBe(217000);
    expect(proof?.latestRevisedTruth.value).toBe(210000);
  });

  it("rejects a factual metric without its exact series mapping", () => {
    const value = candidate();
    delete value.payload.extensions["auxsays.phase2.metrics"][0].sourceSeriesIds;
    expect(() => validatePublicationCandidate(value)).toThrow(/source series ID/);
  });

  it("uses childRefs publicly and derives nested children only in the view model", () => {
    const value = candidate();
    expect(value.payload.systems[0].childRefs).toHaveLength(6);
    expect(value.payload.systems[0]).not.toHaveProperty("children");
    expect(createCandidateViewModel(validatePublicationCandidate(value)).systems[0].children).toHaveLength(6);
  });

  it("rejects embedded public children", () => {
    const value = candidate() as unknown as { payload: { systems: Array<Record<string, unknown>> } };
    value.payload.systems[0].children = [];
    expect(() => validatePublicationCandidate(value)).toThrow(/embedded children/);
  });
});
