import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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

  it("keeps OBS, relationships, and structural CALC visually distinct", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByRole("heading", { name: "Energy-to-transport system state" })).toBeTruthy();
    expect(screen.getByText("3 factual observations")).toBeTruthy();
    expect(screen.getByText("Official measurements").previousElementSibling?.textContent).toBe("3");
    expect(screen.getByText("AUXSAYS structural calculations").previousElementSibling?.textContent).toBe("0");
    expect(screen.getByText("Accepted structural relationships").previousElementSibling?.textContent).toBe("0");
    expect(screen.getByRole("heading", { name: "Awaiting authoritative BEA acceptance" })).toBeTruthy();
    expect(screen.queryByRole("img", { name: /structural path/i })).toBeNull();
  });

  it("presents the credential state as an analytical block, not an app error", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "Energy-to-transport system state" });
    expect(screen.getByText("Structural relationships pending")).toBeTruthy();
    expect(screen.getByText("Official BEA structural data has not yet been accepted.")).toBeTruthy();
    expect(screen.queryByText("Application error")).toBeNull();
  });

  it("exposes exact Phase-4B evidence with details on demand", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "Energy-to-transport system state" });
    fireEvent.click(screen.getByRole("button", { name: "Verified Data" }));
    const records = await screen.findByRole("region", { name: "Phase-4B factual observation evidence" });
    expect(within(records).getAllByRole("row")).toHaveLength(4);
    expect(within(records).getAllByText("OBS")).toHaveLength(3);
    expect(within(records).getAllByRole("link", { name: "Open original evidence" })).toHaveLength(3);
    expect(screen.getByText("0 structural CALC")).toBeTruthy();
  });

  it("keeps Outlook empty and Phase 5 locked", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: "Energy-to-transport system state" });
    fireEvent.click(screen.getByRole("button", { name: "Outlook" }));
    expect(await screen.findAllByRole("heading", { name: "Forecast unavailable / not yet supported" })).toHaveLength(2);
    expect(screen.getByText(/No forecast has been produced/)).toBeTruthy();
    expect(screen.getByText(/Phase 5 forecasting is locked/)).toBeTruthy();
    expect(document.body.textContent).not.toContain("Scenario alpha");
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
