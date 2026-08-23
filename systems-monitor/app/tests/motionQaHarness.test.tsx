import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import motionFixture from "../fixtures/motion-qa-read-model.json";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { motionOutcomes, validateMotionQaReadModel } from "../src/data/motionQaReadModel";
import { applyStructuralViewport, createStructuralCamera, interpolateCamera, MAX_STRUCTURAL_ZOOM, MIN_STRUCTURAL_ZOOM, outcomeTravel, projectNode, sampleRelationship, zoomStructuralViewportAt } from "../src/views/motion/structuralRenderer";
import { layoutSpatialLabels, layoutSpatialNodes, MAX_VISIBLE_RELATIONSHIPS, nextNodeInDirection, resolveSpatialViewport } from "../src/views/motion/spatialNavigation";
import { candidate } from "./factualCandidate.test";

const standardMatchMedia = (query: string) => ({ matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false });
const reducedMatchMedia = (query: string) => ({ matches: query.includes("prefers-reduced-motion"), media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false });

async function renderReducedHarness() {
  Object.defineProperty(window, "matchMedia", { writable: true, value: reducedMatchMedia });
  render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
  await screen.findByRole("heading", { name: /See the system\.\s*Follow the pressure\./ });
}

function stepPath(pathName: string, steps: number) {
  const trace = screen.getByRole("button", { name: "Trace" });
  if (trace.getAttribute("aria-pressed") !== "true") fireEvent.click(trace);
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
    expect(model.nodes.map((node) => node.label)).toEqual(expect.arrayContaining(["Crude Supply", "Refining", "Storage", "Freight Network", "Employment"]));
    expect(model.nodes.map((node) => node.kind)).not.toEqual(expect.arrayContaining(["ORIGIN", "BRANCH", "RECONVERGENCE"]));
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
    expect(await screen.findByRole("heading", { name: /See the system\.\s*Follow the pressure\./ })).toBeTruthy();
    expect(screen.getByText("MOTION QA — SYNTHETIC TEST DATA")).toBeTruthy();
    expect(screen.getByRole("img", { name: /Synthetic structural pressure surface/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Commercial Crude Supply.*Enter this system/ })).toBeTruthy();
    expect(document.querySelector('[data-structural-renderer="canvas-rd"]')).toBeTruthy();
    expect(screen.getByRole("button", { name: "Explore" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Hover to preview. Select to enter.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Play" })).toBeNull();
    expect(screen.getAllByText(/TEST_FIXTURE/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("ACCEPTED structural relationship");
  });

  it("accepts rapid path changes without replaying stale selection state", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /See the system\.\s*Follow the pressure\./ });
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
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
    await screen.findByRole("heading", { name: /See the system\.\s*Follow the pressure\./ });
    const node = screen.getByRole("button", { name: /Product Storage Capacity.*Enter this system/ });
    fireEvent.keyDown(node, { key: "Enter" });
    expect(screen.getByRole("complementary", { name: "Selected synthetic node inspector" })).toBeTruthy();
    expect(screen.getByText("fixture-derivation:buffer")).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("complementary", { name: "Selected synthetic node inspector" })).toBeNull();
  });

  it("preserves the three primary views without introducing a production navigation item", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /See the system\.\s*Follow the pressure\./ });
    expect(screen.getAllByRole("navigation", { name: "Systems Monitor views" })).toHaveLength(1);
    expect(screen.getByRole("navigation", { name: "Structural exploration history" })).toBeTruthy();
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
    expect(document.querySelector(".sm-viz-surface")?.getAttribute("data-connector-motion")).toBe("static");
    fireEvent.click(screen.getByRole("button", { name: /Petroleum Refining.*Enter this system/ }));
    expect(document.querySelector('.sm-viz-surface')?.getAttribute("data-focus-depth")).toBe("1");
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
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
    expect(absorbed).toHaveLength(1);
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
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
    fireEvent.click(screen.getByRole("button", { name: "Step forward" }));
    const current = document.querySelector(".sm-motion-signal.is-current");
    expect(document.querySelector('[data-structural-renderer="canvas-rd"]')).toBeTruthy();
    expect(current?.getAttribute("data-direction")).toBe("forward");
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
    const node = screen.getByRole("button", { name: /Industrial Utilities.*DELAYING.*Enter this system/ });
    fireEvent.click(node);
    const inspector = screen.getByRole("complementary", { name: "Selected synthetic node inspector" });
    expect(inspector.parentElement?.classList.contains("sm-viz-instrument")).toBe(true);
    expect(inspector.getAttribute("data-selected-node-id")).toBe("fixture-branch-a");
    expect(screen.getByText(/DELAYING/)).toBeTruthy();
  });

  it("suppresses explanatory helpers in label-independent QA without breaking controls", async () => {
    await renderReducedHarness();
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
    const toggle = screen.getByRole("button", { name: "Hide explanation" });
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-pressed")).toBe("true");
    expect((document.querySelector(".sm-motion-live") as HTMLElement).hidden).toBe(true);
    expect((document.querySelector(".sm-motion-legend") as HTMLElement).hidden).toBe(true);
    expect(screen.getByText("Supply")).toBeTruthy();
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

  it("replaces the SVG viewport with a renderer abstraction and spatial Trace Mode", async () => {
    await renderReducedHarness();
    expect(document.querySelector(".sm-motion-network")).toBeNull();
    expect(document.querySelector('[data-renderer-surface="canvas"]')).toBeTruthy();
    expect(document.querySelectorAll(".sm-viz-node-label")).toHaveLength(9);
    const trace = screen.getByRole("button", { name: "Trace" });
    expect(trace.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(trace);
    expect(trace.getAttribute("aria-pressed")).toBe("true");
    expect(document.querySelector('.sm-viz-surface')?.getAttribute("data-trace-mode")).toBe("true");
    expect(Number(document.querySelector('.sm-viz-surface')?.getAttribute("data-visible-relationship-count"))).toBeLessThanOrEqual(MAX_VISIBLE_RELATIONSHIPS);
  });

  it("keeps Explore static and separates synthetic motion controls into Trace", async () => {
    await renderReducedHarness();
    expect(document.querySelectorAll(".sm-motion-current-signal")).toHaveLength(0);
    expect(document.querySelector(".sm-motion-origin-token")).toBeNull();
    expect(document.querySelector(".sm-viz-readout")).toBeNull();
    expect(screen.queryByRole("button", { name: "Step forward" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
    expect(screen.getByRole("button", { name: "Step forward" })).toBeTruthy();
    expect(screen.getByText("Follow one synthetic route.")).toBeTruthy();
  });

  it("previews a factor on hover and focus without selecting it", async () => {
    await renderReducedHarness();
    const node = screen.getByRole("button", { name: /Petroleum Refining.*Enter this system/ });
    fireEvent.pointerEnter(node);
    expect(document.querySelector(".sm-viz-surface")?.getAttribute("data-hovered-node-id")).toBe("fixture-producer");
    expect(node.getAttribute("data-hovered")).toBe("true");
    expect(node.getAttribute("aria-pressed")).toBe("false");
    fireEvent.pointerLeave(node);
    expect(document.querySelector(".sm-viz-surface")?.getAttribute("data-hovered-node-id")).toBe("");
    fireEvent.focus(node);
    expect(node.getAttribute("data-hovered")).toBe("true");
    fireEvent.blur(node);
    expect(node.getAttribute("data-hovered")).toBe("false");
  });

  it("assigns every synthetic factor a unique symbol and a coordinated role color", async () => {
    await renderReducedHarness();
    const nodes = [...document.querySelectorAll<HTMLElement>("[data-motion-node-id]")];
    expect(nodes).toHaveLength(9);
    expect(new Set(nodes.map((node) => node.dataset.nodeSymbol)).size).toBe(9);
    expect(new Set(nodes.map((node) => node.dataset.nodeRole))).toEqual(new Set(["SOURCE", "PRODUCTION", "BUFFER", "INFRASTRUCTURE", "DEMAND", "HUMAN"]));
    expect(nodes.every((node) => node.style.getPropertyValue("--node-accent").startsWith("#"))).toBe(true);
  });

  it("uses ambient connector motion in Explore and preserves static reduced motion", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /See the system\.\s*Follow the pressure\./ });
    expect(document.querySelector(".sm-viz-surface")?.getAttribute("data-connector-motion")).toBe("ambient");
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
    expect(document.querySelector(".sm-viz-surface")?.getAttribute("data-connector-motion")).toBe("trace");
  });

  it("zooms under the mouse wheel, pans only with the middle button, and resets", async () => {
    await renderReducedHarness();
    const surface = document.querySelector<HTMLElement>(".sm-viz-surface")!;
    expect(surface.dataset.viewportZoom).toBe("1.000");
    fireEvent.wheel(surface, { deltaY: -180, clientX: 320, clientY: 240 });
    expect(Number(surface.dataset.viewportZoom)).toBeGreaterThan(1);

    fireEvent.pointerDown(surface, { button: 0, pointerId: 4, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(surface, { button: 0, pointerId: 4, clientX: 180, clientY: 160 });
    expect(surface.dataset.viewportPanX).not.toBe("80");

    fireEvent.pointerDown(surface, { button: 1, pointerId: 7, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(surface, { button: 1, pointerId: 7, clientX: 180, clientY: 160 });
    fireEvent.pointerUp(surface, { button: 1, pointerId: 7, clientX: 180, clientY: 160 });
    expect(Number(surface.dataset.viewportPanX)).toBeGreaterThan(0);
    expect(Number(surface.dataset.viewportPanY)).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Reset graph view" }));
    expect(surface.dataset.viewportZoom).toBe("1.000");
    expect(surface.dataset.viewportPanX).toBe("0");
    expect(surface.dataset.viewportPanY).toBe("0");
  });

  it("keeps route geometry and camera focus anchored to read-model coordinates", () => {
    const model = validateMotionQaReadModel(motionFixture);
    const nodes = new Map(model.nodes.map((node) => [node.id, node]));
    const samples = sampleRelationship(model.relationships[10], nodes);
    expect(samples[0]).toEqual({ x: 365, y: 310 });
    expect(samples.at(-1)).toEqual({ x: 925, y: 430 });
    const selected = nodes.get("fixture-buffer")!;
    const camera = createStructuralCamera(1000, 620, selected);
    const projected = projectNode(selected, camera);
    expect(projected.x).toBeCloseTo(500);
    expect(projected.y).toBeCloseTo(297.6);
  });

  it("enters deterministic first- and second-level neighborhoods and restores the parent", async () => {
    await renderReducedHarness();
    fireEvent.click(screen.getByRole("button", { name: /Petroleum Refining.*Enter this system/ }));
    expect(document.querySelector('.sm-viz-surface')?.getAttribute("data-focus-depth")).toBe("1");
    expect(screen.getByRole("navigation", { name: "Structural exploration history" }).textContent).toContain("Refining");
    fireEvent.click(screen.getByRole("button", { name: /Product Storage Capacity.*Enter this system/ }));
    expect(document.querySelector('.sm-viz-surface')?.getAttribute("data-focus-depth")).toBe("2");
    expect(screen.getByRole("complementary", { name: "Selected synthetic node inspector" }).textContent).toContain("Product Storage Capacity");
    fireEvent.click(screen.getByRole("button", { name: "Refining" }));
    expect(document.querySelector('.sm-viz-surface')?.getAttribute("data-focus-depth")).toBe("1");
    expect(screen.getByRole("complementary", { name: "Selected synthetic node inspector" }).textContent).toContain("Petroleum Refining");
  });

  it("does not pad sparse neighborhoods and bounds crowded relationship display", () => {
    const model = validateMotionQaReadModel(motionFixture);
    const sparse = resolveSpatialViewport(model, "fixture-employment", new Set());
    expect(sparse.availableRelationshipCount).toBe(2);
    expect(sparse.visibleRelationshipIds.size).toBe(2);
    expect(sparse.additionalRelationshipCount).toBe(0);
    const localLayout = layoutSpatialNodes(model, resolveSpatialViewport(model, "fixture-producer", new Set()));
    expect(localLayout.find((node) => node.id === "fixture-producer")).toMatchObject({ x: 500, y: 310 });
    expect(localLayout.find((node) => node.id === "fixture-origin")?.x).toBeLessThan(500);
    expect(localLayout.find((node) => node.id === "fixture-downstream")?.x).toBeGreaterThan(500);

    const crowded = {
      ...model,
      relationships: Array.from({ length: 12 }, (_, index) => ({ ...model.relationships[index % model.relationships.length], id: `fixture-ranked-${String(index).padStart(2, "0")}`, from: "fixture-buffer", to: index % 2 ? "fixture-branch-a" : "fixture-branch-b" }))
    };
    const bounded = resolveSpatialViewport(crowded, "fixture-buffer", new Set());
    expect(bounded.visibleRelationshipIds.size).toBe(MAX_VISIBLE_RELATIONSHIPS);
    expect(bounded.additionalRelationshipCount).toBe(2);
    expect([...bounded.visibleRelationshipIds].every((id) => crowded.relationships.some((edge) => edge.id === id))).toBe(true);
  });

  it("uses depth-aware label priority, protects the selected label, and suppresses collisions", () => {
    const model = validateMotionQaReadModel(motionFixture);
    const camera = createStructuralCamera(1000, 620);
    const allNodes = new Set(model.nodes.map((node) => node.id));
    const overview = layoutSpatialLabels({ nodes: model.nodes, camera, width: 1000, height: 620, focusDepth: 0, selectedNodeId: null, visibleNodeIds: allNodes, traceNodeIds: new Set() });
    expect(overview.map((label) => label.text)).toContain("Supply");
    expect(overview.map((label) => label.text)).not.toContain("Commercial Crude Supply");

    const focusedCamera = createStructuralCamera(420, 420, model.nodes.find((node) => node.id === "fixture-buffer"), 2);
    const focused = layoutSpatialLabels({ nodes: model.nodes, camera: focusedCamera, width: 420, height: 420, focusDepth: 2, selectedNodeId: "fixture-buffer", visibleNodeIds: allNodes, traceNodeIds: new Set() });
    const selected = focused.find((label) => label.nodeId === "fixture-buffer")!;
    expect(selected).toMatchObject({ text: "Product Storage Capacity", priority: "PRIMARY", suppressed: false });
    const shown = focused.filter((label) => !label.suppressed);
    for (let left = 0; left < shown.length; left += 1) for (let right = left + 1; right < shown.length; right += 1) {
      const a = shown[left]; const b = shown[right];
      const overlaps = Math.abs(a.x - b.x) < (a.width + b.width) / 2 && Math.abs(a.y - b.y) < (a.height + b.height) / 2;
      expect(overlaps).toBe(false);
    }
  });

  it("keeps node type separate from live interaction state", async () => {
    await renderReducedHarness();
    const buffer = document.querySelector('[data-motion-node-id="fixture-buffer"]');
    expect(buffer?.getAttribute("data-node-type")).toBe("BUFFER");
    stepPath("Primary cascade", 2);
    expect(buffer?.getAttribute("data-node-type")).toBe("BUFFER");
    expect(buffer?.getAttribute("data-motion-state")).toBe("ACTIVE");
    expect(motionFixture.nodes.find((node) => node.id === "fixture-buffer")?.currentState).toBe("IDLE");
  });

  it("cancels stale spatial intent during rapid focus changes", async () => {
    await renderReducedHarness();
    fireEvent.click(screen.getByRole("button", { name: /Petroleum Refining.*Enter this system/ }));
    fireEvent.click(screen.getByRole("button", { name: /Product Storage Capacity.*Enter this system/ }));
    fireEvent.click(screen.getByRole("button", { name: /Industrial Utilities.*Enter this system/ }));
    const trail = screen.getByRole("navigation", { name: "Structural exploration history" });
    expect(trail.querySelector('[aria-current="location"]')?.textContent).toBe("Utilities");
    expect(trail.querySelectorAll("button")).toHaveLength(3);
    expect(trail.textContent).not.toContain("Refining");
    expect(screen.getAllByRole("complementary", { name: "Selected synthetic node inspector" })).toHaveLength(1);
    expect(document.querySelector('[data-motion-node-id="fixture-branch-a"]')?.getAttribute("aria-pressed")).toBe("true");
  });

  it("supports directional keyboard focus inside the visible neighborhood", () => {
    const model = validateMotionQaReadModel(motionFixture);
    const visible = new Set(model.nodes.map((node) => node.id));
    expect(nextNodeInDirection(model.nodes, visible, "fixture-origin", "ArrowRight")).toBe("fixture-producer");
    expect(nextNodeInDirection(model.nodes, visible, "fixture-buffer", "ArrowUp")).toBe("fixture-branch-a");
  });

  it("interpolates camera position without overshoot and snaps under reduced motion", () => {
    const overview = createStructuralCamera(1000, 620);
    const model = validateMotionQaReadModel(motionFixture);
    const target = createStructuralCamera(1000, 620, model.nodes.find((node) => node.id === "fixture-buffer"), 2);
    expect(interpolateCamera(overview, target, 0)).toEqual(overview);
    expect(interpolateCamera(overview, target, 1)).toEqual(target);
    const midpoint = interpolateCamera(overview, target, .5);
    expect(midpoint.scale).toBeGreaterThan(overview.scale);
    expect(midpoint.scale).toBeLessThan(target.scale);
  });

  it("keeps cursor-anchored zoom deterministic and bounded", () => {
    const start = { zoom: 1, panX: 0, panY: 0 };
    const zoomed = zoomStructuralViewportAt(start, 250, 180, 1000, 620, 1.5);
    expect(zoomed).toEqual({ zoom: 1.5, panX: 125, panY: 65 });
    expect(zoomStructuralViewportAt(start, 500, 310, 1000, 620, 99).zoom).toBe(MAX_STRUCTURAL_ZOOM);
    expect(zoomStructuralViewportAt(start, 500, 310, 1000, 620, 0.001).zoom).toBe(MIN_STRUCTURAL_ZOOM);
    expect(applyStructuralViewport({ scale: 1, offsetX: 0, offsetY: 0 }, 1000, 620, zoomed)).toEqual({ scale: 1.5, offsetX: -125, offsetY: -90 });
  });

  it("encodes outcome physics without changing terminal semantics", () => {
    expect(outcomeTravel("BLOCKED", 1)).toBeCloseTo(.76);
    expect(outcomeTravel("ABSORBED", 1)).toBeCloseTo(.7);
    expect(outcomeTravel("UNKNOWN", 1)).toBeCloseTo(.58);
    expect(outcomeTravel("DELAYED", .6)).toBeCloseTo(.52);
    expect(outcomeTravel("DELAYED", 1)).toBeCloseTo(1);
    expect(outcomeTravel("AMPLIFIED", 1)).toBeCloseTo(1);
  });
});
