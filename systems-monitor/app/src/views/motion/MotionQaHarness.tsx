import { useEffect, useMemo, useRef, useState } from "react";
import type { MotionOutcome, MotionQaReadModel } from "../../data/motionQaReadModel";
import { SystemIcon } from "../../shared/SystemIcon";
import type { RouteState } from "../../state/routeSchema";
import { CanvasStructuralSurface } from "./CanvasStructuralSurface";
import { NodeInsightPanel } from "./NodeInsightPanel";
import { resolveSpatialViewport } from "./spatialNavigation";
import { structuralContextFactors } from "./structuralContextFactors";
import "./motionRenderer.css";

const outcomeLabels: Record<MotionOutcome, string> = {
  TRANSMITTED: "Transmitted",
  DELAYED: "Delayed",
  PARTIALLY_ABSORBED: "Partially absorbed",
  ABSORBED: "Absorbed",
  BLOCKED: "Blocked",
  AMPLIFIED: "Amplified",
  UNKNOWN: "Unknown"
};

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return reduced;
}

function MotionGraph({ model }: { model: MotionQaReadModel }) {
  const reducedMotion = useReducedMotion();
  const [pathId, setPathId] = useState("fixture-path-common-origin");
  const [stepIndex, setStepIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [labelsHidden, setLabelsHidden] = useState(false);
  const [traceMode, setTraceMode] = useState(false);
  const [focusHistory, setFocusHistory] = useState<string[]>([]);
  const [selectedContextFactorId, setSelectedContextFactorId] = useState<string | null>(null);
  const restoreFocus = useRef<HTMLButtonElement | null>(null);
  const cameraResumeTimer = useRef<number | null>(null);
  const path = model.paths.find((item) => item.id === pathId) ?? model.paths[0];
  const nodes = useMemo(() => new Map(model.nodes.map((node) => [node.id, node])), [model.nodes]);
  const edges = useMemo(() => new Map(model.relationships.map((edge) => [edge.id, edge])), [model.relationships]);
  const currentEdgeIds = new Set(stepIndex >= 0 ? path.steps[stepIndex] : []);
  const completedEdgeIds = new Set(path.steps.slice(0, Math.max(0, stepIndex)).flat());
  const pathEdgeIds = useMemo(() => new Set(path.steps.flat()), [path]);
  const overviewEdgeIds = useMemo(() => new Set([...pathEdgeIds, ...model.relationships.filter((edge) => edge.from === "fixture-employment" || edge.to === "fixture-employment").map((edge) => edge.id)]), [pathEdgeIds, model.relationships]);
  const currentEdges = [...currentEdgeIds].map((id) => edges.get(id)!).filter(Boolean);
  const hasDelayHold = currentEdges.some((edge) => edge.outcome === "DELAYED");
  const reconciliationTargets = new Set(currentEdges.map((edge) => edge.to));
  const reconciliationTargetId = currentEdges.length > 1 && reconciliationTargets.size === 1 ? currentEdges[0].to : null;
  const terminalOutcomes = new Set<MotionOutcome>(["BLOCKED", "ABSORBED", "UNKNOWN"]);
  const nodeStates = new Map(model.nodes.map((node) => [node.id, node.currentState]));
  completedEdgeIds.forEach((edgeId) => {
    const edge = edges.get(edgeId);
    if (!edge) return;
    nodeStates.set(edge.from, "RESOLVED");
    if (!terminalOutcomes.has(edge.outcome)) nodeStates.set(edge.to, "RESOLVED");
  });
  currentEdges.forEach((edge) => {
    nodeStates.set(edge.from, edge.outcome === "BLOCKED" ? "BLOCKING" : edge.outcome === "ABSORBED" ? "ABSORBING" : "TRANSMITTING");
    if (edge.outcome === "DELAYED") nodeStates.set(edge.to, "DELAYING");
    else if (edge.outcome === "AMPLIFIED") nodeStates.set(edge.to, "AMPLIFYING");
    else if (!terminalOutcomes.has(edge.outcome)) nodeStates.set(edge.to, "ACTIVE");
  });
  const selectedNodeId = focusHistory.at(-1) ?? null;
  const selectedNode = selectedNodeId ? nodes.get(selectedNodeId) : undefined;
  const selectedContextFactor = structuralContextFactors.find((factor) => factor.id === selectedContextFactorId) ?? null;
  const viewport = useMemo(() => resolveSpatialViewport(model, selectedNodeId, selectedNodeId ? new Set() : overviewEdgeIds), [model, selectedNodeId, overviewEdgeIds]);
  const exploreNodeStates = useMemo(() => new Map(model.nodes.map((node) => [node.id, node.currentState])), [model.nodes]);
  const surfaceCurrentEdges = traceMode ? currentEdges : [];
  const surfaceCompletedEdgeIds = traceMode ? completedEdgeIds : new Set<string>();
  const surfacePathEdgeIds = traceMode ? pathEdgeIds : new Set<string>();
  const surfaceNodeStates = traceMode ? nodeStates : exploreNodeStates;

  useEffect(() => {
    if (!playing || reducedMotion) return;
    if (stepIndex >= path.steps.length - 1) { setPlaying(false); return; }
    const timer = window.setTimeout(() => setStepIndex((current) => current + 1), stepIndex < 0 ? 260 : hasDelayHold ? 1180 : 720);
    return () => window.clearTimeout(timer);
  }, [playing, reducedMotion, stepIndex, path.steps.length, hasDelayHold]);

  useEffect(() => {
    if (!reducedMotion) return;
    setPlaying(false);
    setStepIndex(-1);
  }, [reducedMotion]);

  useEffect(() => () => { if (cameraResumeTimer.current !== null) window.clearTimeout(cameraResumeTimer.current); }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && selectedContextFactorId) {
        setSelectedContextFactorId(null);
        window.requestAnimationFrame(() => restoreFocus.current?.focus());
        return;
      }
      if (event.key === "Escape" && selectedNodeId) {
        setFocusHistory((current) => current.slice(0, -1));
        window.requestAnimationFrame(() => restoreFocus.current?.focus());
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedNodeId, selectedContextFactorId]);

  function choosePath(nextPathId: string) {
    setPathId(nextPathId);
    setStepIndex(-1);
    setPlaying(!reducedMotion);
    if (cameraResumeTimer.current !== null) window.clearTimeout(cameraResumeTimer.current);
  }

  function selectNode(nodeId: string, target: HTMLButtonElement) {
    restoreFocus.current = target;
    setSelectedContextFactorId(null);
    if (selectedNodeId === nodeId) return;
    const shouldResume = playing && !reducedMotion;
    setPlaying(false);
    if (cameraResumeTimer.current !== null) window.clearTimeout(cameraResumeTimer.current);
    setFocusHistory((current) => {
      const existing = current.indexOf(nodeId);
      if (existing >= 0) return current.slice(0, existing + 1);
      return current.length < 2 ? [...current, nodeId] : [current.at(-1)!, nodeId];
    });
    if (shouldResume) cameraResumeTimer.current = window.setTimeout(() => setPlaying(true), 540);
  }

  function selectContextFactor(factorId: string, parentNodeId: string, target: HTMLButtonElement) {
    restoreFocus.current = target;
    const shouldResume = playing && !reducedMotion;
    setPlaying(false);
    if (cameraResumeTimer.current !== null) window.clearTimeout(cameraResumeTimer.current);
    setFocusHistory((current) => {
      if (current.at(-1) === parentNodeId) return current;
      const existing = current.indexOf(parentNodeId);
      if (existing >= 0) return current.slice(0, existing + 1);
      return current.length < 2 ? [...current, parentNodeId] : [current.at(-1)!, parentNodeId];
    });
    setSelectedContextFactorId(factorId);
    if (shouldResume) cameraResumeTimer.current = window.setTimeout(() => setPlaying(true), 540);
  }

  function navigateToDepth(depth: number) {
    const shouldResume = playing && !reducedMotion;
    setPlaying(false);
    if (cameraResumeTimer.current !== null) window.clearTimeout(cameraResumeTimer.current);
    setSelectedContextFactorId(null);
    setFocusHistory((current) => current.slice(0, depth));
    if (shouldResume) cameraResumeTimer.current = window.setTimeout(() => setPlaying(true), 540);
  }

  function enterExplore() {
    if (cameraResumeTimer.current !== null) window.clearTimeout(cameraResumeTimer.current);
    setTraceMode(false);
    setPlaying(false);
    setStepIndex(-1);
  }

  function enterTrace() {
    setTraceMode(true);
    setStepIndex(-1);
    setPlaying(!reducedMotion);
  }

  function resetView() {
    if (cameraResumeTimer.current !== null) window.clearTimeout(cameraResumeTimer.current);
    setTraceMode(false);
    setPlaying(false);
    setStepIndex(-1);
    setSelectedContextFactorId(null);
    setFocusHistory([]);
  }

  const currentSummary = stepIndex < 0
    ? `${path.label} ready at its origin.`
    : `${path.label}, step ${stepIndex + 1} of ${path.steps.length}: ${currentEdges.map((edge) => outcomeLabels[edge.outcome]).join(" and ")}.`;

  return <>
    <section className={`sm-viz-instrument ${selectedNode ? "has-focus" : ""}`} aria-label="Spatial structural motion prototype" data-label-independent={labelsHidden}>
      <header className="sm-viz-instrument__header">
        <div><span>Structural surface / R&amp;D 02</span><strong>{selectedContextFactor?.label ?? (selectedNode ? selectedNode.detailLabel : "Synthetic system overview")}</strong></div>
        <div className="sm-viz-status"><span><i aria-hidden="true" />{traceMode ? "Trace" : "Explore"}</span><span>{viewport.visibleRelationshipIds.size} links shown{viewport.additionalRelationshipCount ? ` / ${viewport.additionalRelationshipCount} additional` : ""}</span></div>
      </header>
      <nav className="sm-viz-breadcrumbs" aria-label="Structural exploration history"><button type="button" aria-current={!selectedNode ? "location" : undefined} onClick={() => navigateToDepth(0)}>Synthetic system</button>{focusHistory.map((nodeId, index) => { const node = nodes.get(nodeId); return node ? <span key={`${nodeId}-${index}`}><i aria-hidden="true">›</i><button type="button" aria-current={index === focusHistory.length - 1 && !selectedContextFactor ? "location" : undefined} onClick={() => navigateToDepth(index + 1)}>{node.label}</button></span> : null; })}{selectedContextFactor && <span><i aria-hidden="true">›</i><button type="button" aria-current="location">{selectedContextFactor.label}</button></span>}</nav>
      <div className={`sm-viz-workspace ${selectedNode ? "has-guide" : ""}`}>
        <NodeInsightPanel model={model} node={selectedNode ?? null} contextFactor={selectedContextFactor} state={selectedNode ? nodeStates.get(selectedNode.id) ?? selectedNode.currentState : "IDLE"} onClose={() => navigateToDepth(0)} onSelectParent={() => setSelectedContextFactorId(null)} />
        <CanvasStructuralSurface model={model} path={path} currentEdges={surfaceCurrentEdges} completedEdgeIds={surfaceCompletedEdgeIds} pathEdgeIds={surfacePathEdgeIds} nodeStates={surfaceNodeStates} selectedNodeId={selectedNodeId} selectedContextFactorId={selectedContextFactorId} focusDepth={focusHistory.length} viewport={viewport} traceMode={traceMode} reducedMotion={reducedMotion} reconciliationTargetId={traceMode ? reconciliationTargetId : null} onSelectNode={selectNode} onSelectContextFactor={selectContextFactor} onReset={resetView} />
      </div>
      {traceMode && <div className="sm-viz-readout" hidden={labelsHidden}><p className="sm-motion-live" role="status" aria-live="polite" hidden={labelsHidden}>{currentSummary}</p><div className="sm-viz-legend sm-motion-legend" aria-label="Transmission outcome legend" hidden={labelsHidden}><span><i className="is-flow" />Flow</span><span><i className="is-hold" />Hold</span><span><i className="is-constraint" />Constraint</span><span><i className="is-amplified" />Amplification</span></div></div>}
    </section>

    <section className={`sm-viz-console ${traceMode ? "is-trace" : "is-explore"}`} aria-label="Structural surface controls">
      <div className="sm-viz-mode-lead"><div className="sm-viz-mode-switch" role="group" aria-label="Structural surface mode"><button type="button" aria-pressed={!traceMode} onClick={enterExplore}>Explore</button><button type="button" aria-pressed={traceMode} onClick={enterTrace}>Trace</button></div><p>{traceMode ? "Follow one synthetic route." : "Hover to preview. Select to enter."}</p></div>
      {traceMode && <><div className="sm-viz-route-strip" role="group" aria-label="Synthetic test paths"><span>Test route</span>{model.paths.map((item) => <button key={item.id} type="button" className={path.id === item.id ? "is-selected" : ""} aria-pressed={path.id === item.id} data-motion-fixture-selector={item.id} onClick={() => choosePath(item.id)}>{item.label}</button>)}</div>
      <div className="sm-viz-playback">
        <button type="button" className="is-primary" onClick={() => setPlaying((current) => !current)} disabled={reducedMotion || stepIndex >= path.steps.length - 1}>{playing ? "Pause" : "Play"}</button>
        <button type="button" onClick={() => { setStepIndex(-1); setPlaying(!reducedMotion); }}>Replay</button>
        <button type="button" onClick={() => { setPlaying(false); setStepIndex((current) => Math.min(path.steps.length - 1, current + 1)); }}>Step forward</button>
        <button id="motion-label-independent-qa" type="button" aria-pressed={labelsHidden} data-motion-label-independent-qa onClick={() => setLabelsHidden((current) => !current)}>{labelsHidden ? "Show explanation" : "Hide explanation"}</button>
        <span>{reducedMotion ? "Reduced motion · manual steps" : playing ? "Live transmission" : "Paused"}</span>
      </div></>}
    </section>

    <details className="sm-motion-list"><summary>Open the structured path record <span>{path.steps.flat().length} fixture relationships</span></summary><ol>{path.steps.map((step, index) => <li key={`${path.id}-${index}`}><strong>Step {index + 1}</strong>{step.map((edgeId) => { const edge = edges.get(edgeId)!; return <span key={edge.id}>{nodes.get(edge.from)?.label} → {nodes.get(edge.to)?.label}<b>{outcomeLabels[edge.outcome]}</b><small>{edge.mechanism}{edge.commonCauseId ? ` · shared origin ${edge.commonCauseId}` : ""}</small></span>; })}</li>)}</ol></details>
  </>;
}

function MotionEvidence({ model }: { model: MotionQaReadModel }) {
  return <div className="sm-motion-view" key="verified"><header className="sm-motion-page-header"><span>Fixture evidence boundary</span><h1 data-route-heading tabIndex={-1}>Inspect the choreography.<br /><em>Not the economy.</em></h1><p>Every record below exists only to test motion semantics and interaction states.</p></header><section className="sm-motion-evidence" aria-labelledby="motion-evidence-title"><div className="sm-section-intro"><div><span>01</span><div><small>Read-model layer</small><h2 id="motion-evidence-title">Fixture relationships</h2></div></div><b>{model.relationships.length} test records</b></div>{model.relationships.map((edge) => <details key={edge.id}><summary><span>{edge.id.replace("fixture-edge-", "")}</span><strong>{model.nodes.find((node) => node.id === edge.from)?.label} → {model.nodes.find((node) => node.id === edge.to)?.label}</strong><b>{outcomeLabels[edge.outcome]}</b><i aria-hidden="true">+</i></summary><dl><div><dt>Identity</dt><dd>TEST_FIXTURE</dd></div><div><dt>Mechanism</dt><dd>{edge.mechanism}</dd></div><div><dt>Origin</dt><dd>{edge.originId}</dd></div><div><dt>Common cause</dt><dd>{edge.commonCauseId ?? "None"}</dd></div><div><dt>Stop reason</dt><dd>{edge.stopReason ?? "Continues"}</dd></div><div><dt>Derivation</dt><dd>{edge.derivationRef}</dd></div></dl></details>)}</section></div>;
}

function MotionOutlook() {
  return <div className="sm-motion-view" key="outlook"><section className="sm-motion-outlook"><div><SystemIcon name="lock" size={38} /></div><span>Outlook boundary test</span><h1 data-route-heading tabIndex={-1}>Motion can travel.<br /><em>Claims cannot.</em></h1><p>This harness tests how a structural path feels. It contains no forecast, scenario, probability, or factual Phase-4B result.</p><div><span><SystemIcon name="check" size={17} />Motion fixture active</span><span><SystemIcon name="lock" size={17} />Gate B unchanged</span><span><SystemIcon name="network" size={17} />Phase 5 locked</span></div></section></div>;
}

export function MotionQaHarness({ model, route }: { model: MotionQaReadModel; route: RouteState }) {
  if (route.view === "verified") return <MotionEvidence model={model} />;
  if (route.view === "outlook") return <MotionOutlook />;
  return <div className="sm-motion-view sm-motion-view--renderer-rd" key="summary"><h1 className="sm-sr-only" data-route-heading tabIndex={-1}>See the system. Follow the pressure.</h1><MotionGraph model={model} /></div>;
}
