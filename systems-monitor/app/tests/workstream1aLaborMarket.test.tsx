import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import activeProof from "../../data/review/local-active-pdi-test-snapshot.json";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { createSnapshotViewModel } from "../src/data/snapshotViewModelFactory";
import { laborMarketHierarchy, observationForFactor } from "../src/data/laborMarketReadModel";
import type { PublicSnapshot } from "../src/data/publicSnapshotTypes";
import { validatePublicSnapshot } from "../src/data/validatePublicSnapshot";
import { phase2Fixture } from "../src/fixtures/phase2Fixture";

function activeSnapshot() {
  return createSnapshotViewModel(validatePublicSnapshot(structuredClone(activeProof) as unknown as PublicSnapshot));
}

describe("Workstream 1A factual Labor Market hierarchy", () => {
  it("keeps taxonomy completeness separate from factual data coverage", () => {
    const snapshot = activeSnapshot();
    const hierarchy = laborMarketHierarchy(snapshot);
    expect(hierarchy.outcome).toEqual({ id: "outcome:labor-market-state", label: "Labor Market" });
    expect(hierarchy.taxonomy).toEqual({ approved: 10, defined: 10, status: "TAXONOMY_COMPLETE" });
    expect(hierarchy.dataCoverage).toEqual({ populated: 6, defined: 10 });
    expect(hierarchy.placements).toHaveLength(10);
    expect(snapshot.systems[0].children).toHaveLength(10);
  });

  it("maps each populated canonical factor to the accepted activated observation without copying truth into the placement", () => {
    const snapshot = activeSnapshot();
    const hierarchy = laborMarketHierarchy(snapshot);
    const expected = new Map([
      ["factor:payroll-employment", ["US_LABOR_TOTAL_NONFARM_PAYROLLS", "CES0000000001", 158858, "thousands of persons", "2026-07"]],
      ["factor:u3-unemployment", ["US_LABOR_U3_UNEMPLOYMENT_RATE", "LNS14000000", 4.1, "percent", "2026-07"]],
      ["factor:labor-force-participation", ["US_LABOR_FORCE_PARTICIPATION_RATE", "LNS11300000", 61.4, "percent", "2026-07"]],
      ["factor:initial-claims", ["US_LABOR_INITIAL_UI_CLAIMS", "DOL-UI-SA-INITIAL", 209000, "claims", "2026-08-08"]],
      ["factor:job-openings", ["US_LABOR_JOB_OPENINGS", "JTS000000000000000JOL", 7359, "thousands", "2026-06"]],
      ["factor:hires", ["US_LABOR_HIRES", "JTS000000000000000HIL", 5348, "thousands", "2026-06"]]
    ]);
    for (const [factorId, [metricId, seriesId, value, unit, period]] of expected) {
      const factor = hierarchy.canonicalFactors[factorId];
      const observation = observationForFactor(snapshot, factor);
      expect(factor.metricRef).toBe(metricId);
      expect(observation?.sourceSeriesIds).toEqual([seriesId]);
      expect(observation?.value).toBe(value);
      expect(observation?.unit).toBe(unit);
      expect(observation?.validTime).toBe(period);
      const placement = hierarchy.placements.find((item) => item.canonicalFactorId === factorId)!;
      expect(placement).not.toHaveProperty("value");
      expect(placement).not.toHaveProperty("sourceRefs");
      expect(placement).not.toHaveProperty("provenanceRefs");
      expect(placement).not.toHaveProperty("stateType");
    }
  });

  it("keeps the four approved unavailable factors free of placeholders, fake states, and synthetic evidence", () => {
    const snapshot = activeSnapshot();
    const hierarchy = laborMarketHierarchy(snapshot);
    const missing = ["factor:average-weekly-hours", "factor:average-hourly-earnings", "factor:total-separations", "factor:employment-population-ratio"];
    for (const factorId of missing) {
      const factor = hierarchy.canonicalFactors[factorId];
      expect(factor.availability).toBe("not_yet_enabled");
      expect(observationForFactor(snapshot, factor)).toBeUndefined();
      expect(factor).not.toHaveProperty("value");
      expect(factor).not.toHaveProperty("direction");
      expect(factor).not.toHaveProperty("condition");
      expect(factor).not.toHaveProperty("evidenceUrl");
    }
  });

  it("never overlays factual hierarchy metadata onto the synthetic fixture", () => {
    const fixture = createSnapshotViewModel(phase2Fixture);
    expect(fixture.snapshot.publicationClass).toBe("fixture");
    expect(fixture.extensions["auxsays.workstream1.factorHierarchy"]).toBeUndefined();
    expect(JSON.stringify(activeSnapshot())).not.toContain("TEST_FIXTURE");
  });
});

describe("Workstream 1A factual Labor Market UI", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/systems-monitor/");
    window.localStorage.clear();
    window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__ = structuredClone(activeProof);
  });

  afterEach(() => {
    cleanup();
    delete window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__;
    window.localStorage.clear();
  });

  it("renders one active snapshot as ten selectable hierarchy targets with six readings and four honest unavailable states", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByRole("heading", { name: "Labor Market" }, { timeout: 15_000 })).toBeTruthy();
    expect(screen.getByText("LOCAL FACTUAL SNAPSHOT")).toBeTruthy();
    const map = screen.getByRole("region", { name: "Factual Labor Market structural surface" });
    const surface = map.querySelector<HTMLElement>('[data-structural-renderer="canvas-rd"]')!;
    const factorTargets = map.querySelectorAll<HTMLButtonElement>('[data-motion-node-id^="factor:"]');
    expect(factorTargets).toHaveLength(10);
    expect(map.querySelectorAll('[data-motion-node-id^="factor:"][data-motion-state="SIGNAL_READY"]')).toHaveLength(6);
    expect(map.querySelectorAll('[data-motion-node-id^="factor:"][data-motion-state="IDLE"]')).toHaveLength(4);
    expect(screen.getAllByText(/10\/10 factors/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/6 official readings/).length).toBeGreaterThan(0);
    expect(surface.getAttribute("data-relationship-semantics")).toBe("hierarchy-navigation-only");
    expect(surface.getAttribute("data-orbit-geometry")).toBe("10-around-one");
    expect(surface.getAttribute("data-visible-relationship-count")).toBe("10");
    expect(map.querySelector('[data-motion-node-id="outcome:labor-market-state"]')?.getAttribute("data-node-symbol")).toBe("labor-market");
    expect(map.querySelector('[data-motion-node-id="factor:labor-force-participation"]')?.getAttribute("data-node-symbol")).toBe("participation");
    expect(map.querySelector("marker, [data-motion-edge-id], [data-relationship-class]")).toBeNull();
  });

  it("uses the bounded review route without mixing persisted R&D fixture state", async () => {
    delete window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__;
    window.history.replaceState({}, "", "/systems-monitor/?view=summary#workstream1a");
    window.localStorage.setItem("auxsays.localFactualCandidate", "not-json");
    window.localStorage.setItem("auxsays.localPhase4bState", "not-json");
    window.localStorage.setItem("auxsays.localMotionQaState", "not-json");
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByRole("heading", { name: "Labor Market" }, { timeout: 15_000 })).toBeTruthy();
    expect(screen.getByText("LOCAL FACTUAL SNAPSHOT")).toBeTruthy();
    expect(document.body.textContent).not.toContain("Synthetic system overview");
  });

  it("opens progressive official evidence for a populated factor and keeps route state coherent", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "Labor Market" });
    fireEvent.click(screen.getByRole("button", { name: /Payroll Employment\. 158,858 thousands of persons/ }));
    const inspector = screen.getByRole("complementary", { name: "Payroll Employment details" });
    expect(within(inspector).getAllByText("158,858 thousands of persons")).toHaveLength(2);
    expect(within(inspector).getByText("CES0000000001")).toBeTruthy();
    expect(within(inspector).getByRole("link", { name: "Open original evidence" }).getAttribute("href")).toBe("https://data.bls.gov/timeseries/CES0000000001");
    expect(window.location.search).toContain("path=payroll-employment");
    expect(screen.getByRole("button", { name: /Payroll Employment\./ }).getAttribute("aria-pressed")).toBe("true");
  });

  it("explains an unavailable approved factor without displaying zero or an invented analytical state", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "Labor Market" });
    fireEvent.click(screen.getByRole("button", { name: /Total Separations\. Current data not yet enabled/ }));
    const inspector = screen.getByRole("complementary", { name: "Total Separations details" });
    expect(within(inspector).getAllByText("Data not yet enabled")).toHaveLength(2);
    expect(within(inspector).getByText(/quits, layoffs, discharges/)).toBeTruthy();
    const text = inspector.textContent ?? "";
    expect(text).not.toMatch(/\b0\b/);
    expect(text).not.toMatch(/Neutral|Normal|Stable|Flat/);
    expect(within(inspector).queryByRole("link", { name: "Open original evidence" })).toBeNull();
  });

  it("preserves keyboard-visible controls, textual semantics, and the immutable snapshot identity across interaction", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "Labor Market" });
    const initialIdentity = activeProof.snapshot.id;
    const claims = screen.getByRole("button", { name: /Initial Claims\. 209,000 claims/ });
    claims.focus();
    expect(document.activeElement).toBe(claims);
    fireEvent.click(claims);
    expect(screen.getByText(initialIdentity)).toBeTruthy();
    expect(screen.getByText(/6 official readings · 4 data sources not yet enabled/)).toBeTruthy();
  });
});
