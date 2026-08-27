import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { createPersistentWorld, employmentDriverCandidates, persistentWorldFingerprint, persistentWorldSelectionSequence } from "../src/data/persistentWorldModel";
import { PERSISTENT_GLINT_PERIOD_MS, PERSISTENT_GLINT_TRAIL, blendPremiumColor, easePremiumHover, persistentGlintProgress, premiumCurveRoute, resolvePersistentLod, resolvePremiumLabels } from "../src/views/persistent/persistentWorldVisuals";

describe("premium persistent-world visual language", () => {
  it("routes curves deterministically without changing endpoints", () => {
    const first = premiumCurveRoute("hierarchy:a:b", { x: 10, y: 20 }, { x: 300, y: 160 });
    expect(first).toEqual(premiumCurveRoute("hierarchy:a:b", { x: 10, y: 20 }, { x: 300, y: 160 }));
    expect(first.start).toEqual({ x: 10, y: 20 });
    expect(first.end).toEqual({ x: 300, y: 160 });
    expect(first.control1.y).not.toBe(20 + (160 - 20) * .33);
  });

  it("keeps glint period and trail independent from hover emphasis", () => {
    expect(PERSISTENT_GLINT_PERIOD_MS).toBe(2500);
    expect(PERSISTENT_GLINT_TRAIL).toBe(.085);
    expect(persistentGlintProgress(1300, "edge:7")).toBe(persistentGlintProgress(1300, "edge:7"));
    expect(easePremiumHover(0, 1, 16)).toBeGreaterThan(0);
    expect(blendPremiumColor("#315b67", "#ef7f84", .5, .9)).toMatch(/^rgba\(/);
  });

  it("resolves premium LOD and label collisions deterministically", () => {
    expect(resolvePersistentLod(0, .1, true)).toBe(3);
    expect(resolvePersistentLod(3, .2, false)).toBe(0);
    expect(resolvePersistentLod(3, 2.2, true)).toBe(2);
    const candidates = [
      { id: "a", text: "A", x: 100, y: 100, priority: 100, width: 80, height: 22, accent: "#fff" },
      { id: "b", text: "B", x: 108, y: 103, priority: 20, width: 80, height: 22, accent: "#fff" },
      { id: "c", text: "C", x: 250, y: 100, priority: 50, width: 80, height: 22, accent: "#fff" }
    ];
    const first = resolvePremiumLabels(candidates, 400, 240);
    expect(first).toEqual(resolvePremiumLabels(candidates, 400, 240));
    expect(first.map((item) => item.id)).toEqual(["a", "c"]);
  });
});

describe("persistent Employment influence world model", () => {
  it("creates one deterministic 1→10→100→1000 fixture world", () => {
    const first = createPersistentWorld();
    const second = createPersistentWorld();
    expect(first.coverage).toEqual({ placementCount: 1111, level1Count: 10, level2Count: 100, level3Count: 1000, hierarchyRelationshipCount: 1110, syntheticInfluenceCount: 2000, factualRelationshipCount: 0, acceptedRelationshipCount: 0 });
    expect(Object.keys(first.placements)).toHaveLength(1111);
    expect(Object.keys(first.relationships)).toHaveLength(3110);
    expect(first.topologyFingerprint).toBe(second.topologyFingerprint);
    expect(first.graphSnapshotId).toBe(second.graphSnapshotId);
    expect(first.candidateEligibility).toBe("NEVER_ACCEPTED_NEVER_PUBLISHED");
    expect(first.humanQa).toBe("PENDING");
    expect(first.gateBStatus).toBe("OPEN_UNCHANGED");
  });

  it("holds exact-ten placement cardinality at every fixture branch", () => {
    const model = createPersistentWorld();
    expect(model.childrenByPlacement[model.outcomePlacementId]).toHaveLength(10);
    const level1 = Object.values(model.placements).filter((item) => item.depth === 1);
    const level2 = Object.values(model.placements).filter((item) => item.depth === 2);
    expect(level1).toHaveLength(10);
    expect(level2).toHaveLength(100);
    level1.forEach((item) => expect(model.childrenByPlacement[item.id]).toHaveLength(10));
    level2.forEach((item) => expect(model.childrenByPlacement[item.id]).toHaveLength(10));
    expect(employmentDriverCandidates.map((item) => item.label)).toEqual(["Output & Growth", "Consumer Demand", "Employer Labor Demand", "Layoffs & Job Destruction", "Business Investment", "Rates & Credit", "Labor Costs & Wages", "Productivity & Automation", "Labor Supply", "Policy, Trade & External Shocks"]);
  });

  it("keeps topology, coordinates, and relationship identity invariant across 50 deterministic selections and reset", () => {
    const model = createPersistentWorld();
    const before = persistentWorldFingerprint(model);
    const membership = Object.keys(model.placements).sort();
    const relationshipIds = Object.keys(model.relationships).sort();
    for (const id of persistentWorldSelectionSequence(model, 50)) {
      expect(model.placements[id]).toBeTruthy();
      expect(persistentWorldFingerprint(model)).toBe(before);
    }
    expect(Object.keys(model.placements).sort()).toEqual(membership);
    expect(Object.keys(model.relationships).sort()).toEqual(relationshipIds);
    expect(persistentWorldFingerprint(model)).toBe(before);
  });

  it("separates hierarchy tethers from synthetic influence and never accepts a candidate", () => {
    const model = createPersistentWorld();
    const relationships = Object.values(model.relationships);
    expect(relationships.filter((item) => item.relationshipClass === "HIERARCHY_TETHER")).toHaveLength(1110);
    expect(relationships.filter((item) => item.relationshipClass === "SYNTHETIC_INFLUENCE")).toHaveLength(2000);
    expect(relationships.every((item) => item.status === "TEST_FIXTURE" && item.evidenceClass === "SYNTHETIC" && item.publicationEligibility === "NEVER_ACCEPTED_NEVER_PUBLISHED")).toBe(true);
    expect(JSON.stringify(model)).not.toContain('"status":"ACCEPTED"');
    expect(JSON.stringify(model)).not.toContain('"publicationClass":"factual"');
  });
});

describe("persistent world local-review shell", () => {
  it("uses strict overview LOD and drills through the same resident world", async () => {
    window.history.replaceState({}, "", "/systems-monitor/#persistent-world");
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByRole("heading", { name: "Persistent Employment Influence World" }, { timeout: 15_000 })).toBeTruthy();
    expect(screen.getByText("PERSISTENT WORLD R&D — TEST FIXTURE")).toBeTruthy();
    const surface = screen.getByRole("application", { name: "Persistent Employment influence world" });
    expect(surface.getAttribute("data-resident-placement-count")).toBe("1111");
    expect(surface.getAttribute("data-resident-relationship-count")).toBe("3110");
    expect(surface.getAttribute("data-semantic-node-count")).toBe("11");
    expect(surface.getAttribute("data-lod-mode")).toBe("OVERVIEW");
    expect(screen.getByRole("button", { name: "Enter full screen" })).toBeTruthy();
    fireEvent.wheel(surface, { deltaY: -120, clientX: 400, clientY: 300 });
    expect(Number(surface.getAttribute("data-viewport-zoom"))).toBeGreaterThan(1);
    Object.defineProperty(surface, "setPointerCapture", { configurable: true, value: () => undefined });
    Object.defineProperty(surface, "releasePointerCapture", { configurable: true, value: () => undefined });
    fireEvent.pointerDown(surface, { button: 1, pointerId: 7, clientX: 400, clientY: 300 });
    fireEvent.pointerMove(surface, { pointerId: 7, clientX: 440, clientY: 325 });
    fireEvent.pointerUp(surface, { pointerId: 7, clientX: 440, clientY: 325 });
    expect(Number(surface.getAttribute("data-viewport-pan-x"))).not.toBe(0);

    fireEvent.click(screen.getByRole("button", { name: /03Employer Labor DemandMaster-defined system/ }));
    expect(surface.getAttribute("data-selected-placement-id")).toBe("placement:employer-labor-demand");
    expect(surface.getAttribute("data-resident-placement-count")).toBe("1111");
    expect(surface.getAttribute("data-semantic-node-count")).toBe("12");
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
    expect(surface.getAttribute("data-trace-mode")).toBe("true");
    expect(surface.getAttribute("data-topology-fingerprint")).toMatch(/^fnv1a32:/);
    const inspector = screen.getByRole("complementary", { name: "Persistent world factor details" });
    expect(within(inspector).getByRole("heading", { name: "Employer Labor Demand" })).toBeTruthy();
    expect(window.location.hash).toContain("placement%3Aemployer-labor-demand");

    fireEvent.click(screen.getByRole("button", { name: /01Job OpeningsReview candidate/ }));
    expect(surface.getAttribute("data-selected-placement-id")).toContain("job-openings");
    expect(surface.getAttribute("data-resident-placement-count")).toBe("1111");
    expect(screen.getAllByText(/Synthetic renderer record/)).toHaveLength(10);
    fireEvent.doubleClick(surface, { clientX: -100, clientY: -100 });
    expect(surface.getAttribute("data-selected-placement-id")).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(surface.getAttribute("data-selected-placement-id")).toBe("");
    expect(surface.getAttribute("data-trace-mode")).toBe("false");
    expect(surface.getAttribute("data-topology-fingerprint")).toMatch(/^fnv1a32:/);
  });

  it("offers full-world density as an explicit action and keeps factual readings separate", async () => {
    window.history.replaceState({}, "", "/systems-monitor/#persistent-world");
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "Persistent Employment Influence World" });
    const surface = screen.getByRole("application", { name: "Persistent Employment influence world" });
    fireEvent.click(screen.getByRole("button", { name: "Full-world view" }));
    expect(surface.getAttribute("data-lod-mode")).toBe("FULL_WORLD_DENSITY");
    expect(surface.getAttribute("data-semantic-node-count")).toBe("11");
    const factualLink = screen.getByRole("link", { name: "Open factual Labor Market" });
    expect(factualLink.getAttribute("href")).toBe("/systems-monitor/#workstream1a");
    expect(document.body.textContent).toContain("accepted factual relationships 0");
    expect(document.body.textContent).not.toContain("Gate B closed");
    fireEvent.click(factualLink);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    expect(await screen.findByRole("heading", { name: "Labor Market" }, { timeout: 15_000 })).toBeTruthy();
  });
});
