import { describe, expect, it } from "vitest";
import { persistentBindingPresentationLabel, persistentChangePresentationLabel, persistentChangesForScope, persistentCoverageSummary, persistentSourceHealthExceptions, persistentVerifiedMovements, persistentWorldBranchRootId, sortPersistentNotices } from "../src/data/persistentWorldBriefing";
import { persistentWorldFactualBindingForFactor, type PersistentWorldFactualBinding } from "../src/data/persistentWorldFactualBindings";
import { createPersistentWorld, persistentWorldPlacementLabel } from "../src/data/persistentWorldModel";
import { persistentChangeNotices, type PersistentChangeNotice } from "../src/data/persistentWorldTemporalReadModel";
import { persistentWorldLabelRequired, persistentWorldLabelVisible } from "../src/views/persistent/PremiumPersistentWorldSurface";

const model = createPersistentWorld();
const layoffsBranchId = "placement:layoffs-job-destruction";

function notice(overrides: Partial<PersistentChangeNotice>): PersistentChangeNotice {
  return {
    id: "test:a",
    kind: "NEW_OFFICIAL_OBSERVATION",
    factorLabel: "Test factor",
    placementId: layoffsBranchId,
    knownAt: "2026-09-01T00:00:00Z",
    officialPublishedAt: "2026-09-01T00:00:00Z",
    validTime: "2026-08",
    currentDisplay: "11 people",
    comparisonBasis: "Test only",
    impactClass: "UNKNOWN",
    economicSignalEligible: false,
    headline: "Test observation",
    summary: "Test summary",
    sourceLabel: "Official source",
    sourceHealthOnly: false,
    ...overrides,
  };
}

describe("persistent-world five-second briefing", () => {
  it("admits only comparable accepted observation movements and never source health or single observations", () => {
    const eligible = persistentVerifiedMovements(persistentChangeNotices, 100);
    expect(eligible.length).toBeGreaterThan(0);
    expect(eligible.every((row) => row.id.startsWith("accepted-history:") && row.previousDisplay && row.absoluteDeltaDisplay && row.direction)).toBe(true);
    expect(eligible.some((row) => row.sourceHealthOnly || row.kind !== "NEW_OFFICIAL_OBSERVATION")).toBe(false);
    expect(persistentVerifiedMovements([notice({ previousDisplay: undefined, absoluteDelta: undefined }), notice({ id: "test:source", sourceHealthOnly: true, previousDisplay: "10", absoluteDelta: 1, absoluteDeltaDisplay: "1 person", direction: "UP" })])).toHaveLength(0);
  });

  it("orders by official publication time with stable ID tie-breaking", () => {
    const ordered = sortPersistentNotices([
      notice({ id: "b", officialPublishedAt: "2026-09-02T00:00:00Z" }),
      notice({ id: "c", officialPublishedAt: "2026-09-03T00:00:00Z" }),
      notice({ id: "a", officialPublishedAt: "2026-09-02T00:00:00Z" }),
    ]);
    expect(ordered.map((row) => row.id)).toEqual(["c", "a", "b"]);
  });

  it("keeps selected-branch and all-system scopes explicit", () => {
    const initialClaims = persistentChangeNotices.find((row) => row.id.startsWith("accepted-history:") && row.factorLabel.toLowerCase().includes("initial"))!.placementId;
    expect(persistentWorldBranchRootId(model, initialClaims)).toBe(layoffsBranchId);
    const branchRows = persistentChangesForScope(persistentChangeNotices, model, layoffsBranchId, "BRANCH");
    const allRows = persistentChangesForScope(persistentChangeNotices, model, layoffsBranchId, "ALL");
    expect(branchRows.length).toBeGreaterThan(0);
    expect(branchRows.length).toBeLessThan(allRows.length);
    expect(branchRows.every((row) => row.placementId.startsWith(layoffsBranchId))).toBe(true);
  });

  it("reports branch coverage from unique canonical factors", () => {
    const bindings = Object.fromEntries(Object.values(model.placements).filter((placement) => placement.depth > 0).map((placement) => [placement.id, persistentWorldFactualBindingForFactor(placement.canonicalFactorId, persistentWorldPlacementLabel(model, placement))]));
    const coverage = persistentCoverageSummary(model, bindings, layoffsBranchId);
    expect(coverage.scopeLabel).toBe("Layoffs & Job Destruction");
    expect(coverage.acceptedHistoryFactors).toBe(12);
    expect(coverage.comparableHistoryFactors).toBe(11);
    expect(coverage.acceptedReadingFactors).toBe(12);
    expect(coverage.totalFactors).toBeGreaterThan(coverage.acceptedReadingFactors);
  });

  it("preserves the stale-primary/current-fallback operational exception", () => {
    const exception = persistentSourceHealthExceptions(persistentChangeNotices).find((row) => row.id.startsWith("source-health:dol-ui-claims"));
    expect(exception?.summary).toContain("DOL XML source ends at 2026-08-15");
    expect(exception?.summary).toContain("official release fallback ending 2026-09-05");
    expect(exception?.economicSignalEligible).toBe(false);
  });

  it("maps unknown evidence states to specific human wording", () => {
    const binding = (status: PersistentWorldFactualBinding["status"]): PersistentWorldFactualBinding => ({ status, label: "Test" });
    expect(persistentBindingPresentationLabel(binding("SOURCE_IDENTIFIED"))).toBe("Source identified · verified reading not yet available");
    expect(persistentBindingPresentationLabel(binding("BLOCKED"))).toBe("Source currently blocked");
    expect(persistentBindingPresentationLabel(binding("CONNECTED"))).toBe("Not enough comparable history yet");
    expect(persistentBindingPresentationLabel(undefined)).toBe("Verified reading not yet available");
    expect(persistentChangePresentationLabel(notice({ previousDisplay: "10", absoluteDelta: 1 }))).toBe("Direction verified · interpretation not yet governed");
    expect(persistentChangePresentationLabel(notice({}))).toBe("Not enough comparable history yet");
  });

  it("uses label omission rather than mandatory crowding on narrow screens", () => {
    const path = new Set([model.outcomePlacementId, layoffsBranchId]);
    expect(persistentWorldLabelRequired(375, "placement:consumer-demand", layoffsBranchId, path, true)).toBe(false);
    expect(persistentWorldLabelRequired(375, layoffsBranchId, layoffsBranchId, path, true)).toBe(true);
    expect(persistentWorldLabelRequired(1200, "placement:consumer-demand", layoffsBranchId, path, true)).toBe(true);
    expect(persistentWorldLabelVisible(375, "placement:consumer-demand", layoffsBranchId, path)).toBe(false);
    expect(persistentWorldLabelVisible(375, layoffsBranchId, layoffsBranchId, path)).toBe(true);
    expect(persistentWorldLabelVisible(375, model.outcomePlacementId, layoffsBranchId, path)).toBe(true);
    expect(persistentWorldLabelVisible(1200, "placement:consumer-demand", layoffsBranchId, path)).toBe(true);
  });
});
