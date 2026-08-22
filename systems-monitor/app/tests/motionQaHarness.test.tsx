import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import motionFixture from "../fixtures/motion-qa-read-model.json";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { motionOutcomes, validateMotionQaReadModel } from "../src/data/motionQaReadModel";
import { candidate } from "./factualCandidate.test";

const standardMatchMedia = (query: string) => ({ matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false });

describe("development-only structural Motion QA harness", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/systems-monitor/");
    window.localStorage.clear();
    window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__ = candidate();
    window.localStorage.setItem("auxsays.localMotionQaState", JSON.stringify(motionFixture));
    Object.defineProperty(window, "matchMedia", { writable: true, value: standardMatchMedia });
  });

  afterEach(() => {
    vi.useRealTimers();
    delete window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__;
    window.localStorage.clear();
    Object.defineProperty(window, "matchMedia", { writable: true, value: standardMatchMedia });
  });

  it("validates a bounded TEST_FIXTURE with every governed motion outcome", () => {
    const model = validateMotionQaReadModel(motionFixture);
    expect(model.nodes).toHaveLength(9);
    expect(model.relationships).toHaveLength(12);
    expect(new Set(model.relationships.map((edge) => edge.outcome))).toEqual(new Set(motionOutcomes));
    expect(model.coverage).toMatchObject({ factualRelationshipCount: 0, acceptedRelationshipCount: 0 });
    expect(model.candidateEligibility).toBe("NEVER_ACCEPTED_NEVER_PUBLISHED");
  });

  it("rejects factual, accepted, or gate-changing fixture shapes", () => {
    const factual = structuredClone(motionFixture) as unknown as Record<string, unknown>;
    factual.publicationClass = "factual";
    expect(() => validateMotionQaReadModel(factual)).toThrow(/explicit TEST_FIXTURE/);

    const accepted = structuredClone(motionFixture) as unknown as { relationships: Array<Record<string, unknown>> };
    accepted.relationships[0].status = "ACCEPTED";
    expect(() => validateMotionQaReadModel(accepted)).toThrow(/supported TEST_FIXTURE outcome/);

    const gateChange = structuredClone(motionFixture) as unknown as Record<string, unknown>;
    gateChange.gateBStatus = "PASS";
    expect(() => validateMotionQaReadModel(gateChange)).toThrow(/cannot change approval gates/);
  });

  it("renders an unmistakable synthetic boundary and a controllable graph", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    expect(await screen.findByRole("heading", { name: /Watch pressure\s*move through a system\./ })).toBeTruthy();
    expect(screen.getByText("MOTION QA — SYNTHETIC TEST DATA")).toBeTruthy();
    expect(screen.getByRole("img", { name: /Synthetic structural motion test network/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Upstream signal.*Open fixture inspector/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy();
    expect(screen.getAllByText(/TEST_FIXTURE/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("ACCEPTED structural relationship");
  });

  it("accepts rapid path changes without replaying stale selection state", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /Watch pressure\s*move through a system\./ });
    const blocked = screen.getByRole("button", { name: "Blocked route" });
    const absorbed = screen.getByRole("button", { name: "Absorbed route" });
    fireEvent.click(blocked);
    fireEvent.click(absorbed);
    expect(absorbed.getAttribute("aria-pressed")).toBe("true");
    expect(blocked.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText(/Absorbed route ready at its origin/)).toBeTruthy();
  });

  it("opens node detail by keyboard and closes it with Escape", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /Watch pressure\s*move through a system\./ });
    const node = screen.getByRole("button", { name: /Buffer stage.*Open fixture inspector/ });
    fireEvent.keyDown(node, { key: "Enter" });
    expect(screen.getByRole("complementary", { name: "Selected synthetic node inspector" })).toBeTruthy();
    expect(screen.getByText("fixture-derivation:buffer")).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("complementary", { name: "Selected synthetic node inspector" })).toBeNull();
  });

  it("preserves the three primary views without introducing a production navigation item", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /Watch pressure\s*move through a system\./ });
    expect(screen.getAllByRole("navigation")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Verified Data" }));
    expect(await screen.findByRole("heading", { name: /Inspect the choreography\.\s*Not the economy\./ })).toBeTruthy();
    expect(screen.getByText("12 test records")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Outlook" }));
    expect(await screen.findByRole("heading", { name: /Motion can travel\.\s*Claims cannot\./ })).toBeTruthy();
    expect(document.body.textContent).not.toContain("Scenario alpha");
    expect(document.body.textContent).not.toContain("FCST");
  });

  it("disables causal autoplay when reduced motion is requested", async () => {
    Object.defineProperty(window, "matchMedia", { writable: true, value: (query: string) => ({ matches: query.includes("prefers-reduced-motion"), media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false }) });
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /Watch pressure\s*move through a system\./ });
    expect(screen.getByText("Reduced motion · manual steps")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Play" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Step forward" }));
    expect(screen.getByText(/step 1 of 7/i)).toBeTruthy();
  });
});
