import { useEffect, useMemo, useRef, useState } from "react";
import type { MotionOutcome, MotionQaNode, MotionQaReadModel } from "../../data/motionQaReadModel";
import { SystemIcon } from "../../shared/SystemIcon";
import type { RouteState } from "../../state/routeSchema";
import { CanvasStructuralSurface } from "./CanvasStructuralSurface";
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

function NodeRelationshipContext({ model, node }: { model: MotionQaReadModel; node: MotionQaNode }) {
  const upstream = model.relationships.filter((edge) => edge.to === node.id).map((edge) => model.nodes.find((item) => item.id === edge.from)?.label).filter(Boolean);
  const downstream = model.relationships.filter((edge) => edge.from === node.id).map((edge) => model.nodes.find((item) => item.id === edge.to)?.label).filter(Boolean);
  return <div className="sm-viz-context-flow">
    <div><span>Upstream</span><strong>{upstream.length ? upstream.join(" · ") : "Origin point"}</strong></div>
    <i aria-hidden="true" />
    <div className="is-current"><span>Current node</span><strong>{node.label}</strong></div>
    <i aria-hidden="true" />
    <div><span>Downstream</span><strong>{downstream.length ? downstream.join(" · ") : "Terminal exposure"}</strong></div>
  </div>;
}

function MotionGraph({ model }: { model: MotionQaReadModel }) {
  const reducedMotion = useReducedMotion();
  const [pathId, setPathId] = useState("fixture-path-common-origin");
  const [stepIndex, setStepIndex] = useState(-1);
  const [playing, setPlaying] = useState(!reducedMotion);
  const [labelsHidden, setLabelsHidden] = useState(false);
  const [traceMode, setTraceMode] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const restoreFocus = useRef<HTMLButtonElement | null>(null);
  const path = model.paths.find((item) => item.id === pathId) ?? model.paths[0];
  const nodes = useMemo(() => new Map(model.nodes.map((node) => [node.id, node])), [model.nodes]);
  const edges = useMemo(() => new Map(model.relationships.map((edge) => [edge.id, edge])), [model.relationships]);
  const currentEdgeIds = new Set(stepIndex >= 0 ? path.steps[stepIndex] : []);
  const completedEdgeIds = new Set(path.steps.slice(0, Math.max(0, stepIndex)).flat());
  const pathEdgeIds = new Set(path.steps.flat());
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
  const selectedNode = selectedNodeId ? nodes.get(selectedNodeId) : undefined;

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

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && selectedNodeId) {
        setSelectedNodeId(null);
        restoreFocus.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedNodeId]);

  function choosePath(nextPathId: string) {
    setPathId(nextPathId);
    setStepIndex(-1);
    setPlaying(!reducedMotion);
    setSelectedNodeId(null);
  }

  function selectNode(nodeId: string, target: HTMLButtonElement) {
    restoreFocus.current = target;
    setSelectedNodeId((current) => current === nodeId ? null : nodeId);
  }

  const currentSummary = stepIndex < 0
    ? `${path.label} ready at its origin.`
    : `${path.label}, step ${stepIndex + 1} of ${path.steps.length}: ${currentEdges.map((edge) => outcomeLabels[edge.outcome]).join(" and ")}.`;

  return <>
    <section className="sm-viz-console" aria-label="Motion QA playback controls">
      <div className="sm-viz-route-strip" role="group" aria-label="Synthetic test paths"><span>Test route</span>{model.paths.map((item) => <button key={item.id} type="button" className={path.id === item.id ? "is-selected" : ""} aria-pressed={path.id === item.id} data-motion-fixture-selector={item.id} onClick={() => choosePath(item.id)}>{item.label}</button>)}</div>
      <div className="sm-viz-playback">
        <button type="button" className="is-primary" onClick={() => setPlaying((current) => !current)} disabled={reducedMotion || stepIndex >= path.steps.length - 1}>{playing ? "Pause" : "Play"}</button>
        <button type="button" onClick={() => { setStepIndex(-1); setPlaying(!reducedMotion); }}>Replay</button>
        <button type="button" onClick={() => { setPlaying(false); setStepIndex((current) => Math.min(path.steps.length - 1, current + 1)); }}>Step forward</button>
        <button type="button" className="sm-viz-trace-toggle" aria-pressed={traceMode} onClick={() => setTraceMode((current) => !current)}>Trace mode</button>
        <button id="motion-label-independent-qa" type="button" aria-pressed={labelsHidden} data-motion-label-independent-qa onClick={() => setLabelsHidden((current) => !current)}>{labelsHidden ? "Show explanation" : "Hide explanation"}</button>
        <span>{reducedMotion ? "Reduced motion · manual steps" : playing ? "Live transmission" : "Paused"}</span>
      </div>
    </section>

    <section className={`sm-viz-instrument ${selectedNode ? "has-focus" : ""}`} aria-label="Spatial structural motion prototype" data-label-independent={labelsHidden}>
      <header className="sm-viz-instrument__header">
        <div><span>Structural surface / R&amp;D 01</span><strong>{path.label}</strong></div>
        <div className="sm-viz-status"><span><i aria-hidden="true" />{traceMode ? "Trace isolated" : "Full topology"}</span><span>{path.stopReason.replaceAll("_", " ")}</span></div>
      </header>
      <CanvasStructuralSurface model={model} path={path} currentEdges={currentEdges} completedEdgeIds={completedEdgeIds} pathEdgeIds={pathEdgeIds} nodeStates={nodeStates} selectedNodeId={selectedNodeId} traceMode={traceMode} reducedMotion={reducedMotion} reconciliationTargetId={reconciliationTargetId} onSelectNode={selectNode} />
      <div className="sm-viz-readout" hidden={labelsHidden}><p className="sm-motion-live" role="status" aria-live="polite" hidden={labelsHidden}>{currentSummary}</p><div className="sm-viz-legend sm-motion-legend" aria-label="Transmission outcome legend" hidden={labelsHidden}><span><i className="is-flow" />Flow</span><span><i className="is-hold" />Hold</span><span><i className="is-constraint" />Constraint</span><span><i className="is-amplified" />Amplification</span></div></div>
      {selectedNode && <aside className="sm-viz-inspector" aria-label="Selected synthetic node inspector" data-selected-node-id={selectedNode.id}>
        <div className="sm-viz-inspector__lead"><span>Inside this system</span><h2>{selectedNode.label}</h2><p>{selectedNode.kind.replaceAll("_", " ")} · {nodeStates.get(selectedNode.id) ?? "IDLE"} · TEST_FIXTURE</p></div>
        <NodeRelationshipContext model={model} node={selectedNode} />
        <div className="sm-viz-inspector__actions"><span>{selectedNode.derivationRef}</span><button type="button" onClick={() => { setSelectedNodeId(null); restoreFocus.current?.focus(); }}>Back to whole system</button></div>
      </aside>}
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
  return <div className="sm-motion-view sm-motion-view--renderer-rd" key="summary"><header className="sm-motion-page-header sm-motion-page-header--renderer"><span>Visual renderer laboratory</span><h1 data-route-heading tabIndex={-1}>See the system.<br /><em>Follow the pressure.</em></h1><p>One synthetic network. Continuous geometry, spatial focus, and physics-led motion—without making an economic claim.</p></header><MotionGraph model={model} /></div>;
}
