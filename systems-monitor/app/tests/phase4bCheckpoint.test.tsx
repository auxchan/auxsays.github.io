import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import phase4bCandidate from "../../state/review/phase4b-read-model-candidate.json";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { validatePhase4bReadModel } from "../src/data/phase4bReadModel";
import { candidate } from "./factualCandidate.test";

describe("Phase-4B local factual checkpoint", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/systems-monitor/");
    window.localStorage.clear();
    window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__ = candidate();
    window.localStorage.setItem("auxsays.localPhase4bState", JSON.stringify(phase4bCandidate));
  });

  afterEach(() => {
    cleanup();
    delete window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__;
    window.localStorage.clear();
  });

  it("keeps measured signals, relationships, and calculations distinct without jargon repetition", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByRole("heading", { name: /Energy pressure\.\s*Made legible\./ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /428\.815 million barrels/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /97\.2%/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /1,465\.1 thousand.*Truck transportation employment/ })).toBeTruthy();
    expect(screen.getByText("3 signals ready")).toBeTruthy();
    expect(screen.getByText("No system result yet")).toBeTruthy();
    expect(screen.getByText("0 calculations · 0 accepted paths")).toBeTruthy();
    expect(screen.queryByText("OBS")).toBeNull();
    expect(screen.queryByRole("img", { name: /structural path/i })).toBeNull();
  });

  it("presents the credential state as an analytical block, not an app error", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /Energy pressure\.\s*Made legible\./ });
    expect(screen.getByText("Connections pending")).toBeTruthy();
    expect(screen.getByText("Official BEA structure has not been accepted yet, so no arrows are drawn.")).toBeTruthy();
    expect(screen.queryByText("Application error")).toBeNull();
  });

  it("exposes exact Phase-4B evidence with details on demand", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /Energy pressure\.\s*Made legible\./ });
    fireEvent.click(screen.getByRole("button", { name: "Verified Data" }));
    expect(await screen.findByRole("heading", { name: /Trust the number\.\s*Trace the source\./ })).toBeTruthy();
    expect(screen.getByText("3 records")).toBeTruthy();
    const crudeSummary = screen.getByText("U.S. commercial crude oil stocks excluding SPR");
    fireEvent.click(crudeSummary);
    expect(crudeSummary.closest("details")?.open).toBe(true);
    expect(screen.getAllByText("Official measurement")).toHaveLength(3);
    expect(screen.getAllByText("AUXSAYS calculation")).toHaveLength(3);
    expect(screen.getAllByText("None")).toHaveLength(3);
    expect(screen.getAllByRole("link", { name: /Open original evidence/ })[0].getAttribute("href")).toContain("eia.gov");
    expect(screen.queryByText("OBS")).toBeNull();
  });

  it("keeps Outlook empty and Phase 5 locked", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /Energy pressure\.\s*Made legible\./ });
    fireEvent.click(screen.getByRole("button", { name: "Outlook" }));
    expect(await screen.findByRole("heading", { name: /The forecast begins\s*after the model earns it\./ })).toBeTruthy();
    expect(screen.getByText(/Current-state evidence is live/)).toBeTruthy();
    expect(screen.getByText("Phase 5 locked")).toBeTruthy();
    expect(document.body.textContent).not.toContain("Scenario alpha");
    expect(document.body.textContent).not.toContain("FCST");
  });
});

describe("Phase-4B read-model fail-closed validation", () => {
  it("rejects bounded proof when Gate B is incomplete", () => {
    const invalid = structuredClone(phase4bCandidate) as unknown as Record<string, unknown>;
    invalid.structuralCoverageState = "BOUNDED_STRUCTURAL_PROOF";
    invalid.gateBStatus = "BLOCKED_STRUCTURAL_HANDOFF_UNPROVEN";
    expect(() => validatePhase4bReadModel(invalid)).toThrow(/cannot be presented as bounded structural proof/);
  });

  it("does not infer proof from direct cells alone", () => {
    const partial = structuredClone(phase4bCandidate) as unknown as Record<string, unknown>;
    partial.acceptedRelationships = [{ edgeId: "accepted-direct-cell" }];
    partial.structuralCoverageState = "LIMITED_ENGINE_PROOF";
    partial.gateBStatus = "BLOCKED_STRUCTURAL_HANDOFF_UNPROVEN";
    expect(validatePhase4bReadModel(partial).structuralCoverageState).toBe("LIMITED_ENGINE_PROOF");
  });
});
