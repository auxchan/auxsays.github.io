import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import motionFixture from "../fixtures/motion-qa-read-model.json";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { motionOutcomes, validateMotionQaReadModel } from "../src/data/motionQaReadModel";
import { candidate } from "./factualCandidate.test";

const standardMatchMedia = (query: string) => ({ matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false });
const reducedMatchMedia = (query: string) => ({ matches: query.includes("prefers-reduced-motion"), media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false });

async function renderReducedHarness() {
  Object.defineProperty(window, "matchMedia", { writable: true, value: reducedMatchMedia });
  render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
  await screen.findByRole("heading", { name: /Watch pressure\s*move through a system\./ });
}

function stepPath(pathName: string, steps: number) {
  fireEvent.click(screen.getByRole("button", { name: pathName }));
  const step = screen.getByRole("button", { name: "Step forward" });
  for (let index = 0; index < steps; index += 1) fireEvent.click(step);
}

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
    await renderReducedHarness();
    expect(screen.getByText("Reduced motion · manual steps")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Play" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Step forward" }));
    expect(screen.getByText(/step 1 of 7/i)).toBeTruthy();
  });

  it("terminates BLOCKED before the destination and never activates that node", async () => {
    await renderReducedHarness();
    stepPath("Blocked route", 2);
    const blocked = document.querySelector('[data-motion-outcome="BLOCKED"]');
    const destination = document.querySelector('[data-motion-node-id="fixture-downstream"]');
    expect(blocked?.getAttribute("data-signal-terminates")).toBe("before-destination");
    expect(document.querySelectorAll('[data-motion-terminal="BLOCKED"]')).toHaveLength(1);
    expect(destination?.getAttribute("data-motion-active")).toBe("false");
    expect(destination?.getAttribute("data-motion-state")).toBe("IDLE");
  });

  it("terminates ABSORBED in a sink without downstream activation", async () => {
    await renderReducedHarness();
    stepPath("Absorbed route", 3);
    const absorbed = document.querySelector('[data-motion-outcome="ABSORBED"]');
    const destination = document.querySelector('[data-motion-node-id="fixture-employment"]');
    expect(absorbed?.getAttribute("data-signal-terminates")).toBe("before-destination");
    expect(document.querySelectorAll('[data-motion-terminal="ABSORBED"]')).toHaveLength(1);
    expect(destination?.getAttribute("data-motion-active")).toBe("false");
    expect(destination?.getAttribute("data-motion-state")).toBe("IDLE");
  });

  it("renders separate absorbed and surviving components for PARTIALLY_ABSORBED", async () => {
    await renderReducedHarness();
    stepPath("Primary cascade", 2);
    const surviving = document.querySelector('[data-motion-outcome="PARTIALLY_ABSORBED"][data-motion-component="surviving"]');
    const absorbed = document.querySelectorAll('[data-motion-component="absorbed"]');
    const destination = document.querySelector('[data-motion-node-id="fixture-buffer"]');
    expect(surviving).toBeTruthy();
    expect(absorbed.length).toBeGreaterThanOrEqual(2);
    expect(destination?.getAttribute("data-motion-active")).toBe("true");
    expect(destination?.getAttribute("data-motion-state")).toBe("ACTIVE");
  });

  it("exposes a DELAYED waiting state before downstream continuation", async () => {
    await renderReducedHarness();
    stepPath("Primary cascade", 3);
    const delayed = document.querySelector('[data-motion-outcome="DELAYED"]');
    const delayNode = document.querySelector('[data-motion-node-id="fixture-branch-a"]');
    expect(delayed?.getAttribute("data-motion-phase")).toBe("WAITING");
    expect(delayNode?.getAttribute("data-motion-state")).toBe("DELAYING");
    expect(document.querySelector('[data-motion-edge-id="fixture-edge-05"].is-current')).toBeNull();
  });

  it("makes AMPLIFIED behavior stronger than ordinary transmission", async () => {
    await renderReducedHarness();
    stepPath("Branch + reconvergence", 3);
    const amplified = document.querySelector('[data-motion-outcome="AMPLIFIED"]');
    const ordinary = document.querySelector('[data-motion-outcome="TRANSMITTED"]');
    const amplifierNode = document.querySelector('[data-motion-node-id="fixture-branch-b"]');
    expect(amplified?.getAttribute("data-motion-strength")).toBe("stronger");
    expect(document.querySelector(".sm-motion-amplified-halo")).toBeTruthy();
    expect(ordinary).toBeNull();
    expect(amplifierNode?.getAttribute("data-motion-state")).toBe("AMPLIFYING");
  });

  it("retains one common-origin identity through split and single reconciliation", async () => {
    await renderReducedHarness();
    stepPath("Branch + reconvergence", 3);
    expect(document.querySelectorAll('.sm-motion-current-signal[data-origin-id="fixture-origin-shock-01"]')).toHaveLength(2);
    expect(document.querySelectorAll('.sm-motion-origin-token[data-origin-id="fixture-origin-shock-01"]')).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Step forward" }));
    expect(document.querySelectorAll('[data-common-origin-reconciliation="single"]')).toHaveLength(1);
    expect(document.querySelector('[data-motion-node-id="fixture-junction"]')?.getAttribute("data-motion-active")).toBe("true");
  });

  it("preserves explicit directional affordances independent of graph layout", async () => {
    await renderReducedHarness();
    fireEvent.click(screen.getByRole("button", { name: "Step forward" }));
    const current = document.querySelector(".sm-motion-signal.is-current");
    expect(document.querySelector("#sm-motion-arrow")).toBeTruthy();
    expect(current?.getAttribute("data-direction")).toBe("forward");
    expect(current?.getAttribute("marker-end")).toBe("url(#sm-motion-arrow-active)");
  });

  it("never reports IDLE for nodes participating in the active split", async () => {
    await renderReducedHarness();
    stepPath("Branch + reconvergence", 3);
    expect(document.querySelector('[data-motion-node-id="fixture-buffer"]')?.getAttribute("data-motion-state")).toBe("TRANSMITTING");
    expect(document.querySelector('[data-motion-node-id="fixture-branch-a"]')?.getAttribute("data-motion-state")).toBe("DELAYING");
    expect(document.querySelector('[data-motion-node-id="fixture-branch-b"]')?.getAttribute("data-motion-state")).toBe("AMPLIFYING");
  });

  it("docks node context without covering the graph and reports live motion state", async () => {
    await renderReducedHarness();
    stepPath("Branch + reconvergence", 3);
    const node = screen.getByRole("button", { name: /Branch alpha.*DELAYING.*Open fixture inspector/ });
    fireEvent.click(node);
    const inspector = screen.getByRole("complementary", { name: "Selected synthetic node inspector" });
    expect(inspector.parentElement?.classList.contains("sm-motion-workbench")).toBe(true);
    expect(inspector.getAttribute("data-selected-node-id")).toBe("fixture-branch-a");
    expect(screen.getByText("DELAYING")).toBeTruthy();
  });

  it("suppresses explanatory helpers in label-independent QA without breaking controls", async () => {
    await renderReducedHarness();
    const toggle = screen.getByRole("button", { name: "Hide explanation" });
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-pressed")).toBe("true");
    expect((document.querySelector(".sm-motion-live") as HTMLElement).hidden).toBe(true);
    expect((document.querySelector(".sm-motion-legend") as HTMLElement).hidden).toBe(true);
    expect(screen.getByText("Upstream signal")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Blocked route" }));
    expect(screen.getByRole("button", { name: "Show explanation" })).toBeTruthy();
  });

  it("keeps all static reduced-motion outcome markers semantically distinct", async () => {
    await renderReducedHarness();
    const cases = [
      ["Blocked route", 2, "BLOCKED", "BLOCKED"],
      ["Absorbed route", 3, "ABSORBED", "ABSORBED"],
      ["Unknown route", 1, "UNKNOWN", "UNRESOLVED"]
    ] as const;
    for (const [pathName, steps, outcome, terminal] of cases) {
      stepPath(pathName, steps);
      expect(document.querySelector(`[data-motion-outcome="${outcome}"]`)).toBeTruthy();
      expect(document.querySelector(`[data-motion-terminal="${terminal}"]`)).toBeTruthy();
    }
  });
});
