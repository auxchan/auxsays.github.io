import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import motionFixture from "../fixtures/motion-qa-read-model.json";
import { SnapshotProvider } from "../src/app/SnapshotContext";
import { SystemsMonitorApp } from "../src/app/SystemsMonitorApp";
import { motionOutcomes, validateMotionQaReadModel } from "../src/data/motionQaReadModel";
import { applyStructuralViewport, blendConnectorColor, connectorGlintProgress, createStructuralCamera, easeConnectorHover, interpolateCamera, MAX_STRUCTURAL_ZOOM, MIN_STRUCTURAL_ZOOM, outcomeTravel, projectNode, resolveStructuralDepths, resolveStructuralDepthVisual, sampleRelationship, stepSpringParallax, zoomStructuralViewportAt } from "../src/views/motion/structuralRenderer";
import { EMPLOYMENT_ORBIT_RADIUS, layoutEmploymentOrbit, layoutSpatialLabels, layoutSpatialNodes, MAX_VISIBLE_RELATIONSHIPS, nextNodeInDirection, resolveSpatialViewport } from "../src/views/motion/spatialNavigation";
import { layoutStructuralContextFactors, structuralContextFactors } from "../src/views/motion/structuralContextFactors";
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
    expect(model.nodes.find((node) => node.id === "fixture-producer")?.portrait).toMatchObject({ imageUrl: "/systems-monitor/__local-review/media/petroleum-refining-public-domain.jpg", license: "PUBLIC_DOMAIN" });
    expect(model.nodes.find((node) => node.id === "fixture-junction")?.portrait).toMatchObject({ imageUrl: "/systems-monitor/__local-review/media/distribution-port-public-domain.jpg", license: "PUBLIC_DOMAIN" });
    expect(model.nodes.find((node) => node.id === "fixture-transport")?.portrait).toMatchObject({ imageUrl: "/systems-monitor/__local-review/media/freight-intermodal-cc0.jpg", license: "CC0_1_0" });
    expect(model.nodes.every((node) => node.portrait.imageUrl.startsWith("/systems-monitor/__local-review/media/"))).toBe(true);
    expect(new Set(model.nodes.map((node) => node.portrait.imageUrl)).size).toBe(model.nodes.length);
    expect(model.nodes.every((node) => node.portrait.sourcePage.startsWith("https://commons.wikimedia.org/wiki/File:"))).toBe(true);
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

    const remotePortrait = structuredClone(motionFixture) as unknown as { nodes: Array<{ portrait?: { imageUrl: string } }> };
    const portraitNode = remotePortrait.nodes.find((node) => node.portrait);
    if (!portraitNode?.portrait) throw new Error("Expected fixture portrait");
    portraitNode.portrait.imageUrl = "https://example.com/unreviewed-photo.jpg";
    expect(() => validateMotionQaReadModel(remotePortrait)).toThrow(/approved local-review image/);

    const missingPortrait = structuredClone(motionFixture) as unknown as { nodes: Array<{ portrait?: unknown }> };
    delete missingPortrait.nodes[0].portrait;
    expect(() => validateMotionQaReadModel(missingPortrait)).toThrow(/Every Motion QA node must include approved portrait imagery/);
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
    const guide = screen.getByRole("complementary", { name: "Selected factor guide" });
    expect(guide.getAttribute("data-connected-count")).toBe("4");
    expect(screen.getByRole("heading", { name: "What it tracks" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Why it matters" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Why these 4 connections are here" })).toBeTruthy();
    expect(guide.textContent).toContain("Inventory capacity that holds product between production and use");
    expect(guide.querySelector('[data-factor-portrait="tank"]')).toBeTruthy();
    expect(node.querySelector('[data-selected-node-anchor="visible"]')).toBeTruthy();
    expect(guide.textContent).not.toContain("fixture-derivation");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("complementary", { name: "Selected factor guide" })).toBeNull();
  });

  it("keeps licensed imagery subordinate to the factor symbol and exposes exact credit", async () => {
    render(<SnapshotProvider><SystemsMonitorApp /></SnapshotProvider>);
    await screen.findByRole("heading", { name: /See the system\.\s*Follow the pressure\./ });
    fireEvent.click(screen.getByRole("button", { name: /Petroleum Refining.*Enter this system/ }));
    const guide = screen.getByRole("complementary", { name: "Selected factor guide" });
    expect(guide.querySelector('[data-factor-portrait="refinery"]')?.getAttribute("data-has-photo")).toBe("true");
    expect(screen.getByRole("img", { name: /Dusk view of a petroleum refinery/ })).toBeTruthy();
    expect(guide.querySelector(".sm-node-guide__portrait-symbol svg")).toBeTruthy();
    const credit = screen.getByRole("link", { name: /Carol M\. Highsmith.*Public domain/ });
    expect(credit.getAttribute("href")).toBe("https://commons.wikimedia.org/wiki/File:Industrial-720706_640.jpg");
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

  it("unfolds node guidance at the far left and reports plain-language live state", async () => {
    await renderReducedHarness();
    stepPath("Branch + reconvergence", 3);
    const node = screen.getByRole("button", { name: /Industrial Utilities.*DELAYING.*Enter this system/ });
    fireEvent.click(node);
    const guide = screen.getByRole("complementary", { name: "Selected factor guide" });
    expect(guide.parentElement?.classList.contains("sm-viz-workspace")).toBe(true);
    expect(guide.parentElement?.firstElementChild).toBe(guide);
    expect(guide.getAttribute("data-selected-node-id")).toBe("fixture-branch-a");
    expect(guide.textContent).toContain("INFRASTRUCTURE · Waiting");
    expect(guide.textContent).toContain("Why these 2 connections are here");
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

  it("shows legible synthetic sublayers with their own information panels", async () => {
    await renderReducedHarness();
    const surface = document.querySelector<HTMLElement>(".sm-viz-surface")!;
    const factors = [...document.querySelectorAll<HTMLButtonElement>("[data-context-factor-id]")];
    expect(surface.dataset.contextFactorCount).toBe("18");
    expect(surface.dataset.depthParticleCount).toBe("72");
    expect(surface.dataset.cameraMotion).toBe("stable-map-swing-focus");
    expect(surface.dataset.layoutMode).toBe("employment-concentric-orbit");
    expect(surface.dataset.orbitGeometry).toBe("eight-around-one");
    expect(surface.dataset.visibleRelationshipIds).toContain("fixture-edge-09");
    expect(surface.dataset.visibleRelationshipIds).toContain("fixture-edge-11");
    expect(factors).toHaveLength(18);
    expect(factors.every((factor) => factor.querySelector("svg"))).toBe(true);
    expect(new Set(factors.map((factor) => factor.dataset.contextFactorDepth)).size).toBeGreaterThan(4);
    const utilization = document.querySelector<HTMLButtonElement>('[data-context-factor-id="context-utilization"]')!;
    fireEvent.pointerEnter(utilization);
    expect(surface.dataset.hoveredNodeId).toBe("fixture-producer");
    expect(utilization.tabIndex).toBe(0);
    fireEvent.click(utilization);
    const guide = screen.getByRole("complementary", { name: "Selected factor guide" });
    expect(guide.getAttribute("data-selected-context-factor-id")).toBe("context-utilization");
    expect(guide.textContent).toContain("Refinery utilization");
    expect(guide.textContent).toContain("The share of available refining capacity currently in use.");
    expect(guide.textContent).toContain("How it connects to Refining");
    expect(surface.dataset.selectedContextFactorId).toBe("context-utilization");
    fireEvent.click(screen.getByRole("button", { name: "View the parent factor" }));
    expect(guide.getAttribute("data-selected-context-factor-id")).toBe("");
    expect(guide.textContent).toContain("Petroleum Refining");
    expect(guide.textContent).toContain("Maintenance capacity");
  });

  it("keeps every sublayer informative and arranges each pair symmetrically outside its parent", () => {
    expect(structuralContextFactors).toHaveLength(18);
    expect(structuralContextFactors.every((factor) => Object.values(factor.insight).every((value) => value.trim().length > 24))).toBe(true);
    const model = validateMotionQaReadModel(motionFixture);
    const orbit = layoutEmploymentOrbit(model);
    const camera = createStructuralCamera(1000, 620);
    const layouts = layoutStructuralContextFactors(orbit, camera, resolveStructuralDepths({ ...model, nodes: orbit }), new Set(orbit.map((node) => node.id)));
    for (const parent of orbit) {
      const pair = layouts.filter((factor) => factor.parentNodeId === parent.id);
      expect(pair).toHaveLength(2);
      const projectedParent = projectNode(parent, camera);
      const distances = pair.map((factor) => Math.hypot(factor.x - projectedParent.x, factor.y - projectedParent.y));
      expect(Math.abs(distances[0] - distances[1])).toBeLessThan(0.01);
    }
  });

  it("keeps the primary delayed route visibly connected to Employment in overview", () => {
    const model = validateMotionQaReadModel(motionFixture);
    const path = model.paths.find((candidate) => candidate.id === "fixture-path-common-origin")!;
    const overview = resolveSpatialViewport(model, null, new Set(path.steps.flat()));
    expect(overview.visibleRelationshipIds.has("fixture-edge-09")).toBe(true);
    expect(overview.visibleNodeIds.has("fixture-employment")).toBe(true);
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

  it("eases connector emphasis instead of snapping on hover", () => {
    expect(easeConnectorHover(0, 1, 0)).toBe(0);
    const firstFrame = easeConnectorHover(0, 1, 16);
    expect(firstFrame).toBeGreaterThan(0);
    expect(firstFrame).toBeLessThan(0.2);
    const laterFrame = easeConnectorHover(firstFrame, 1, 160);
    expect(laterFrame).toBeGreaterThan(firstFrame);
    expect(laterFrame).toBeLessThan(1);
    expect(easeConnectorHover(0, 1, 16, true)).toBe(1);
  });

  it("fades connector lighting into the node accent without changing travel timing", () => {
    expect(blendConnectorColor("#75c9bd", "#f0b768", 0)).toBe("rgb(117, 201, 189)");
    expect(blendConnectorColor("#75c9bd", "#f0b768", 0.5)).toBe("rgb(179, 192, 147)");
    expect(blendConnectorColor("#75c9bd", "#f0b768", 1)).toBe("rgb(240, 183, 104)");
    expect(blendConnectorColor("#568491", "#f0b768", 0.5, 0.34)).toBe("rgba(163, 158, 125, 0.34)");
    expect(connectorGlintProgress(0, 0)).toBe(0);
    expect(connectorGlintProgress(1250, 0)).toBe(0.5);
    expect(connectorGlintProgress(2500, 0)).toBe(0);
  });

  it("layers deeper structural nodes without turning visual depth into factual magnitude", () => {
    const depths = resolveStructuralDepths(motionFixture as never);
    expect(depths.get("fixture-origin")).toBe(0);
    expect(depths.get("fixture-producer")).toBe(1);
    expect(depths.get("fixture-transport")).toBe(5);
    expect(depths.get("fixture-employment")).toBe(7);
    expect(resolveStructuralDepthVisual(0)).toEqual({ scale: 1, opacity: 0.92 });
    expect(resolveStructuralDepthVisual(10)).toEqual({ scale: 0.72, opacity: 0.46 });
    expect(resolveStructuralDepthVisual(10, true)).toEqual({ scale: 1, opacity: 1 });
  });

  it("uses a damped parallax spring and disables it for reduced motion", () => {
    const initial = { position: { x: 0, y: 0 }, velocity: { x: 0, y: 0 } };
    const moved = stepSpringParallax(initial, { x: 1, y: -1 }, 16);
    expect(moved.position.x).toBeGreaterThan(0);
    expect(moved.position.x).toBeLessThan(1);
    expect(moved.position.y).toBeLessThan(0);
    expect(stepSpringParallax(moved, { x: 1, y: -1 }, 16).position.x).toBeGreaterThan(moved.position.x);
    expect(stepSpringParallax(moved, { x: 1, y: -1 }, 16, true)).toEqual(initial);
  });

  it("zooms under the mouse wheel, pans only with the middle button, and resets", async () => {
    await renderReducedHarness();
    const surface = document.querySelector<HTMLElement>(".sm-viz-surface")!;
    expect(surface.dataset.viewportZoom).toBe("1.000");
    const zoomEvent = new WheelEvent("wheel", { deltaY: -180, clientX: 320, clientY: 240, bubbles: true, cancelable: true });
    expect(fireEvent(surface, zoomEvent)).toBe(false);
    expect(zoomEvent.defaultPrevented).toBe(true);
    expect(Number(surface.dataset.viewportZoom)).toBeGreaterThan(1);

    fireEvent.pointerDown(surface, { button: 0, pointerId: 4, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(surface, { button: 0, pointerId: 4, clientX: 180, clientY: 160 });
    expect(surface.dataset.viewportPanX).not.toBe("80");

    fireEvent.pointerDown(surface, { button: 1, pointerId: 7, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(surface, { button: 1, pointerId: 7, clientX: 180, clientY: 160 });
    fireEvent.pointerUp(surface, { button: 1, pointerId: 7, clientX: 180, clientY: 160 });
    expect(Number(surface.dataset.viewportPanX)).toBeGreaterThan(0);
    expect(Number(surface.dataset.viewportPanY)).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Reset — show all core factors" }));
    expect(surface.dataset.viewportZoom).toBe("1.000");
    expect(surface.dataset.viewportPanX).toBe("0");
    expect(surface.dataset.viewportPanY).toBe("0");
  });

  it("expands the complete node workspace and exposes a clear exit state", async () => {
    await renderReducedHarness();
    const surface = document.querySelector<HTMLElement>(".sm-viz-surface")!;
    const workspace = document.querySelector<HTMLElement>(".sm-viz-workspace")!;
    const enter = screen.getByRole("button", { name: "Enter full screen" });
    expect(enter.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(enter);
    expect(workspace.classList.contains("is-fullscreen-fallback")).toBe(true);
    expect(surface.dataset.fullscreen).toBe("true");
    expect(screen.getByRole("button", { name: "Exit full screen" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(workspace.classList.contains("is-fullscreen-fallback")).toBe(false);
    expect(surface.dataset.fullscreen).toBe("false");
  });

  it("returns selection, mode, and camera to the complete core-factor reset view", async () => {
    await renderReducedHarness();
    const surface = document.querySelector<HTMLElement>(".sm-viz-surface")!;
    fireEvent.click(screen.getByRole("button", { name: /Product Storage Capacity.*Enter this system/ }));
    expect(surface.dataset.focusDepth).toBe("1");
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
    const zoomEvent = new WheelEvent("wheel", { deltaY: -180, clientX: 320, clientY: 240, bubbles: true, cancelable: true });
    fireEvent(surface, zoomEvent);
    expect(Number(surface.dataset.viewportZoom)).toBeGreaterThan(1);

    fireEvent.click(screen.getByRole("button", { name: "Reset — show all core factors" }));
    expect(surface.dataset.focusDepth).toBe("0");
    expect(surface.dataset.viewportZoom).toBe("1.000");
    expect(surface.dataset.viewportPanX).toBe("0");
    expect(surface.dataset.viewportPanY).toBe("0");
    expect(surface.dataset.traceMode).toBe("false");
    expect(screen.queryByRole("complementary", { name: "Selected factor guide" })).toBeNull();
    expect(screen.getByText("Synthetic system overview")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Petroleum Refining.*Enter this system/ }));
    expect(surface.dataset.focusDepth).toBe("1");
    fireEvent.doubleClick(surface);
    expect(surface.dataset.focusDepth).toBe("0");
    expect(surface.dataset.viewportZoom).toBe("1.000");
    expect(screen.queryByRole("complementary", { name: "Selected factor guide" })).toBeNull();
  });

  it("keeps Employment central with eight core factors at equal radius and 45-degree intervals", () => {
    const model = validateMotionQaReadModel(motionFixture);
    const orbit = layoutEmploymentOrbit(model);
    const employment = orbit.find((node) => node.id === "fixture-employment")!;
    expect(employment).toMatchObject({ x: 520, y: 310 });
    const outer = orbit.filter((node) => node.id !== employment.id);
    expect(outer).toHaveLength(8);
    expect(outer.every((node) => Math.abs(Math.hypot(node.x - employment.x, node.y - employment.y) - EMPLOYMENT_ORBIT_RADIUS) < 0.002)).toBe(true);
    const octants = outer.map((node) => Math.round(((Math.atan2(node.y - employment.y, node.x - employment.x) + Math.PI * 2) % (Math.PI * 2)) / (Math.PI / 4))).sort((a, b) => a - b);
    expect(octants).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
  });

  it("contains wheel scrolling inside the open factor guide", async () => {
    await renderReducedHarness();
    fireEvent.click(screen.getByRole("button", { name: /Product Storage Capacity.*Enter this system/ }));
    const guide = screen.getByRole("complementary", { name: "Selected factor guide" }) as HTMLElement;
    expect(guide.scrollTop).toBe(0);
    const guideWheel = new WheelEvent("wheel", { deltaY: 140, bubbles: true, cancelable: true });
    expect(fireEvent(guide, guideWheel)).toBe(false);
    expect(guideWheel.defaultPrevented).toBe(true);
    expect(guide.scrollTop).toBe(140);
    expect(document.querySelector(".sm-viz-workspace")?.classList.contains("has-guide")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Close factor guide" }));
    expect(screen.queryByRole("complementary", { name: "Selected factor guide" })).toBeNull();
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
    expect(screen.getByRole("complementary", { name: "Selected factor guide" }).textContent).toContain("Product Storage Capacity");
    fireEvent.click(screen.getByRole("button", { name: "Refining" }));
    expect(document.querySelector('.sm-viz-surface')?.getAttribute("data-focus-depth")).toBe("1");
    expect(screen.getByRole("complementary", { name: "Selected factor guide" }).textContent).toContain("Petroleum Refining");
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
    const overviewCamera = createStructuralCamera(420, 420);
    expect(focusedCamera.scale).toBeGreaterThan(overviewCamera.scale * 1.45);
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
    expect(screen.getAllByRole("complementary", { name: "Selected factor guide" })).toHaveLength(1);
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
