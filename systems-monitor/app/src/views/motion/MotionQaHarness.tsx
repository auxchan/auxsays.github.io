import { useEffect, useMemo, useRef, useState } from "react";
import type { MotionOutcome, MotionQaNode, MotionQaReadModel, MotionQaRelationship } from "../../data/motionQaReadModel";
import { SystemIcon } from "../../shared/SystemIcon";
import type { RouteState } from "../../state/routeSchema";

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

function edgePath(edge: MotionQaRelationship, nodes: Map<string, MotionQaNode>) {
  const from = nodes.get(edge.from)!; const to = nodes.get(edge.to)!;
  const midpoint = (from.x + to.x) / 2;
  return `M ${from.x} ${from.y} C ${midpoint} ${from.y}, ${midpoint} ${to.y}, ${to.x} ${to.y}`;
}

function edgePoint(edge: MotionQaRelationship, nodes: Map<string, MotionQaNode>, progress: number) {
  const from = nodes.get(edge.from)!; const to = nodes.get(edge.to)!;
  const midpoint = (from.x + to.x) / 2;
  const inverse = 1 - progress;
  const x = inverse ** 3 * from.x + 3 * inverse ** 2 * progress * midpoint + 3 * inverse * progress ** 2 * midpoint + progress ** 3 * to.x;
  const y = inverse ** 3 * from.y + 3 * inverse ** 2 * progress * from.y + 3 * inverse * progress ** 2 * to.y + progress ** 3 * to.y;
  const dx = 3 * inverse ** 2 * (midpoint - from.x) + 3 * inverse * progress * (midpoint - midpoint) + 3 * progress ** 2 * (to.x - midpoint);
  const dy = 3 * inverse ** 2 * (from.y - from.y) + 3 * inverse * progress * (to.y - from.y) + 3 * progress ** 2 * (to.y - to.y);
  return { x, y, angle: Math.atan2(dy, dx) * 180 / Math.PI };
}

function labelLines(label: string) {
  const words = label.split(" ");
  if (words.length < 3) return [label];
  const split = Math.ceil(words.length / 2);
  return [words.slice(0, split).join(" "), words.slice(split).join(" ")];
}

function OutcomeMarker({ edge, nodes }: { edge: MotionQaRelationship; nodes: Map<string, MotionQaNode> }) {
  const progress = edge.outcome === "BLOCKED" ? .76 : edge.outcome === "ABSORBED" ? .7 : edge.outcome === "UNKNOWN" ? .58 : edge.outcome === "PARTIALLY_ABSORBED" ? .67 : edge.outcome === "DELAYED" ? .78 : .72;
  const point = edgePoint(edge, nodes, progress);
  const transform = `translate(${point.x} ${point.y}) rotate(${point.angle})`;

  if (edge.outcome === "BLOCKED") return <g className="sm-motion-outcome-marker is-blocked" transform={transform} data-motion-terminal="BLOCKED" aria-hidden="true"><line x1="0" y1="-18" x2="0" y2="18" /><line x1="6" y1="-13" x2="6" y2="13" /><circle className="sm-motion-collision" cx="-9" r="5" /></g>;
  if (edge.outcome === "ABSORBED") return <g className="sm-motion-outcome-marker is-absorbed" transform={transform} data-motion-terminal="ABSORBED" aria-hidden="true"><circle r="18" /><circle r="10" /><circle className="sm-motion-sink" r="4" /></g>;
  if (edge.outcome === "PARTIALLY_ABSORBED") return <g className="sm-motion-outcome-marker is-partially-absorbed" transform={transform} data-motion-component="absorbed" aria-hidden="true"><path d="M-2 -13 C11 -8 11 8 -2 13" /><circle cx="2" r="4" /></g>;
  if (edge.outcome === "DELAYED") return <g className="sm-motion-outcome-marker is-delayed" transform={transform} data-motion-phase="WAITING" aria-hidden="true"><line x1="0" y1="-13" x2="0" y2="13" /><line x1="7" y1="-13" x2="7" y2="13" /><circle cx="-8" r="4" /></g>;
  if (edge.outcome === "AMPLIFIED") return <g className="sm-motion-outcome-marker is-amplified" transform={transform} data-motion-strength="stronger" aria-hidden="true"><path d="M-10 -7 L3 0 -10 7" /><path d="M0 -11 L17 0 0 11" /></g>;
  if (edge.outcome === "UNKNOWN") return <g className="sm-motion-outcome-marker is-unknown" transform={transform} data-motion-terminal="UNRESOLVED" aria-hidden="true"><path d="M-13 0 A13 13 0 0 1 8 -10" /><path d="M8 10 A13 13 0 0 1 -5 12" /><circle cx="13" cy="-3" r="2" /></g>;
  return <g className="sm-motion-outcome-marker is-transmitted" transform={transform} aria-hidden="true"><circle r="5" /></g>;
}

function MotionGraph({ model }: { model: MotionQaReadModel }) {
  const reducedMotion = useReducedMotion();
  const [pathId, setPathId] = useState("fixture-path-common-origin");
  const [stepIndex, setStepIndex] = useState(-1);
  const [playing, setPlaying] = useState(!reducedMotion);
  const [labelsHidden, setLabelsHidden] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const restoreFocus = useRef<SVGGElement | null>(null);
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
  const affectedNodeIds = new Set(currentEdges.filter((edge) => !terminalOutcomes.has(edge.outcome)).map((edge) => edge.to));
  const sourceNodeIds = new Set(currentEdges.map((edge) => edge.from));
  if (stepIndex < 0) affectedNodeIds.add(model.relationships.find((edge) => edge.id === path.steps[0][0])?.from ?? model.nodes[0].id);
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
  const connectedEdgeIds = new Set(selectedNodeId ? model.relationships.filter((edge) => edge.from === selectedNodeId || edge.to === selectedNodeId).map((edge) => edge.id) : []);

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
      if (event.key === "Escape" && inspectorOpen) {
        setInspectorOpen(false);
        restoreFocus.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [inspectorOpen]);

  function choosePath(nextPathId: string) {
    setPathId(nextPathId);
    setStepIndex(-1);
    setPlaying(!reducedMotion);
    setSelectedNodeId(null);
    setInspectorOpen(false);
  }

  function selectNode(nodeId: string, target: SVGGElement) {
    restoreFocus.current = target;
    setSelectedNodeId(nodeId);
    setInspectorOpen(true);
  }

  const currentSummary = stepIndex < 0
    ? `${path.label} ready at its origin.`
    : `${path.label}, step ${stepIndex + 1} of ${path.steps.length}: ${currentEdges.map((edge) => outcomeLabels[edge.outcome]).join(" and ")}.`;

  return <>
    <section className="sm-motion-controls" aria-label="Motion QA playback controls">
      <div className="sm-motion-paths" role="group" aria-label="Synthetic test paths">{model.paths.map((item) => <button key={item.id} type="button" className={path.id === item.id ? "is-selected" : ""} aria-pressed={path.id === item.id} data-motion-fixture-selector={item.id} onClick={() => choosePath(item.id)}>{item.label}</button>)}</div>
      <div className="sm-motion-playback">
        <button type="button" onClick={() => setPlaying((current) => !current)} disabled={reducedMotion || stepIndex >= path.steps.length - 1}>{playing ? "Pause" : "Play"}</button>
        <button type="button" onClick={() => { setStepIndex(-1); setPlaying(!reducedMotion); }}>Replay</button>
        <button type="button" onClick={() => { setPlaying(false); setStepIndex((current) => Math.min(path.steps.length - 1, current + 1)); }}>Step forward</button>
        <button id="motion-label-independent-qa" type="button" className="sm-motion-label-toggle" aria-pressed={labelsHidden} data-motion-label-independent-qa onClick={() => setLabelsHidden((current) => !current)}>{labelsHidden ? "Show explanation" : "Hide explanation"}</button>
        <span>{reducedMotion ? "Reduced motion · manual steps" : playing ? "Playing" : "Paused"}</span>
      </div>
    </section>

    <div className={`sm-motion-workbench ${inspectorOpen ? "has-inspector" : ""}`}>
    <div className="sm-motion-stage" role="region" aria-label="Scrollable synthetic structural motion graph" tabIndex={0} data-label-independent={labelsHidden}>
      <div className="sm-motion-stage__header"><div><span>Active test path</span><strong>{path.label}</strong></div><div><span>Stop condition</span><strong>{path.stopReason.replaceAll("_", " ")}</strong></div></div>
      <svg className="sm-motion-network" viewBox="0 0 1000 620" role="img" aria-labelledby="motion-graph-title motion-graph-description">
        <title id="motion-graph-title">Synthetic structural motion test network</title>
        <desc id="motion-graph-description">Nine synthetic nodes and twelve test-only relationships. Playback and the structured list communicate the same transmission states.</desc>
        <defs><marker id="sm-motion-arrow" className="sm-motion-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 10 5 0 10Z" /></marker><marker id="sm-motion-arrow-active" className="sm-motion-arrow is-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 10 5 0 10Z" /></marker></defs>
        <g className="sm-motion-edges">{model.relationships.map((edge) => {
          const state = completedEdgeIds.has(edge.id) ? "is-complete" : pathEdgeIds.has(edge.id) ? "is-path" : "is-context";
          const focus = selectedNodeId ? connectedEdgeIds.has(edge.id) ? "is-connected" : "is-unrelated" : "";
          return <path key={edge.id} d={edgePath(edge, nodes)} className={`sm-motion-topology-edge ${state} ${focus}`} markerEnd="url(#sm-motion-arrow)" data-motion-edge-id={edge.id} data-direction="forward" />;
        })}{currentEdges.map((edge) => {
          const outcomeClass = edge.outcome.toLowerCase().replaceAll("_", "-");
          const reachesDestination = !terminalOutcomes.has(edge.outcome);
          return <g key={`signal-${edge.id}`} className="sm-motion-current-signal" data-origin-id={edge.originId}>
            {edge.outcome === "PARTIALLY_ABSORBED" && <path d={edgePath(edge, nodes)} pathLength="100" className="sm-motion-absorbed-component" data-motion-component="absorbed" />}
            {edge.outcome === "AMPLIFIED" && <path d={edgePath(edge, nodes)} pathLength="100" className="sm-motion-amplified-halo" aria-hidden="true" />}
            <path d={edgePath(edge, nodes)} pathLength="100" className={`sm-motion-signal is-current is-${outcomeClass}`} markerEnd={reachesDestination ? "url(#sm-motion-arrow-active)" : undefined} data-motion-edge-id={edge.id} data-motion-outcome={edge.outcome} data-direction="forward" data-signal-terminates={reachesDestination ? "at-destination" : "before-destination"} data-motion-component={edge.outcome === "PARTIALLY_ABSORBED" ? "surviving" : undefined} data-motion-phase={edge.outcome === "DELAYED" ? "WAITING" : undefined} data-motion-strength={edge.outcome === "AMPLIFIED" ? "stronger" : undefined} />
            <OutcomeMarker edge={edge} nodes={nodes} />
          </g>;
        })}</g>
        <g className="sm-motion-nodes">{model.nodes.map((node) => {
          const lines = labelLines(node.label);
          const selected = selectedNodeId === node.id;
          const affected = affectedNodeIds.has(node.id);
          const participating = sourceNodeIds.has(node.id);
          const visualState = nodeStates.get(node.id) ?? "IDLE";
          const related = !selectedNodeId || node.id === selectedNodeId || model.relationships.some((edge) => connectedEdgeIds.has(edge.id) && (edge.from === node.id || edge.to === node.id));
          return <g key={node.id} transform={`translate(${node.x} ${node.y})`} role="button" tabIndex={0} aria-label={`${node.label}. ${node.kind}. ${visualState}. Open fixture inspector.`} aria-pressed={selected} data-motion-node-id={node.id} data-motion-state={visualState} data-motion-active={affected || participating} className={`${selected ? "is-selected" : ""} ${affected ? "is-affected" : ""} ${participating ? "is-participating" : ""} is-state-${visualState.toLowerCase()} ${related ? "" : "is-unrelated"}`} onClick={(event) => selectNode(node.id, event.currentTarget)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectNode(node.id, event.currentTarget); } }}><circle r="42" /><circle className="sm-motion-node-core" r="9" /><text textAnchor="middle" y="58">{lines.map((line, index) => <tspan x="0" dy={index ? "15" : "0"} key={line}>{line}</tspan>)}</text></g>;
        })}</g>
        {path.commonCauseId && (() => { const origin = nodes.get(model.relationships.find((edge) => edge.id === path.steps[0][0])!.from)!; return <g className="sm-motion-origin-token" transform={`translate(${origin.x} ${origin.y})`} data-origin-id={path.originId} aria-hidden="true"><circle r="51" /><path d="M-6 0 0-6 6 0 0 6Z" /></g>; })()}
        {path.commonCauseId && reconciliationTargetId && (() => { const junction = nodes.get(reconciliationTargetId)!; return <g className="sm-motion-reconciliation" transform={`translate(${junction.x} ${junction.y})`} data-common-origin-reconciliation="single" data-origin-id={path.originId} aria-hidden="true"><circle r="52" /><path d="M-7 0 0-7 7 0 0 7Z" /></g>; })()}
      </svg>
      <p className="sm-motion-live" role="status" aria-live="polite" hidden={labelsHidden}>{currentSummary}</p>
      <div className="sm-motion-legend" aria-label="Transmission outcome legend" hidden={labelsHidden}>{Object.entries(outcomeLabels).map(([outcome, label]) => <span key={outcome} className={`is-${outcome.toLowerCase().replaceAll("_", "-")}`}><i aria-hidden="true" />{label}</span>)}</div>
    </div>

    {inspectorOpen && selectedNode && <aside className="sm-motion-inspector" aria-label="Selected synthetic node inspector" data-selected-node-id={selectedNode.id}><div><span>Connected node</span><button type="button" onClick={() => { setInspectorOpen(false); restoreFocus.current?.focus(); }}>Close</button></div><h2>{selectedNode.label}</h2><dl><div><dt>Kind</dt><dd>{selectedNode.kind}</dd></div><div><dt>Motion state</dt><dd>{nodeStates.get(selectedNode.id) ?? "IDLE"}</dd></div><div><dt>Upstream</dt><dd>{model.relationships.filter((edge) => edge.to === selectedNode.id).length}</dd></div><div><dt>Downstream</dt><dd>{model.relationships.filter((edge) => edge.from === selectedNode.id).length}</dd></div><div><dt>Evidence</dt><dd>TEST_FIXTURE</dd></div><div><dt>Derivation</dt><dd>{selectedNode.derivationRef}</dd></div></dl><p>Interaction state only. No value or relationship is economic evidence.</p></aside>}
    </div>

    <details className="sm-motion-list"><summary>Read the complete path without animation <span>{path.steps.flat().length} fixture relationships</span></summary><ol>{path.steps.map((step, index) => <li key={`${path.id}-${index}`}><strong>Step {index + 1}</strong>{step.map((edgeId) => { const edge = edges.get(edgeId)!; return <span key={edge.id}>{nodes.get(edge.from)?.label} → {nodes.get(edge.to)?.label}<b>{outcomeLabels[edge.outcome]}</b><small>{edge.mechanism}{edge.commonCauseId ? ` · shared origin ${edge.commonCauseId}` : ""}</small></span>; })}</li>)}</ol></details>
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
  return <div className="sm-motion-view" key="summary"><header className="sm-motion-page-header"><span>Structural motion laboratory</span><h1 data-route-heading tabIndex={-1}>Watch pressure<br /><em>move through a system.</em></h1><p>A compact synthetic topology for testing direction, interruption, branching, and focus. No economic claim is being made.</p></header><MotionGraph model={model} /></div>;
}
