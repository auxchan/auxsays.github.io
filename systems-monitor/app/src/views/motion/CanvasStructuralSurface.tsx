import { useEffect, useMemo, useRef, useState } from "react";
import type { MotionQaNode, MotionQaPath, MotionQaReadModel, MotionQaRelationship } from "../../data/motionQaReadModel";
import { CanvasStructuralRenderer, createStructuralCamera, projectNode } from "./structuralRenderer";

interface CanvasStructuralSurfaceProps {
  model: MotionQaReadModel;
  path: MotionQaPath;
  currentEdges: MotionQaRelationship[];
  completedEdgeIds: Set<string>;
  pathEdgeIds: Set<string>;
  nodeStates: Map<string, string>;
  selectedNodeId: string | null;
  traceMode: boolean;
  reducedMotion: boolean;
  reconciliationTargetId: string | null;
  onSelectNode: (nodeId: string, target: HTMLButtonElement) => void;
}

export function CanvasStructuralSurface({ model, path, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, traceMode, reducedMotion, reconciliationTargetId, onSelectNode }: CanvasStructuralSurfaceProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<CanvasStructuralRenderer | null>(null);
  const stepStartedAt = useRef(0);
  const [size, setSize] = useState({ width: 1000, height: 620 });
  const nodes = useMemo(() => new Map(model.nodes.map((node) => [node.id, node])), [model.nodes]);
  const selectedNode = selectedNodeId ? nodes.get(selectedNodeId) : undefined;
  const camera = useMemo(() => createStructuralCamera(size.width, size.height, selectedNode), [size, selectedNode]);
  const pathNodes = useMemo(() => new Set(model.relationships.filter((edge) => pathEdgeIds.has(edge.id)).flatMap((edge) => [edge.from, edge.to])), [model.relationships, pathEdgeIds]);
  const currentKey = currentEdges.map((edge) => edge.id).join("|");
  const commonOriginNodeId = path.commonCauseId ? model.relationships.find((edge) => edge.id === path.steps[0][0])?.from ?? null : null;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const measure = () => {
      const bounds = host.getBoundingClientRect();
      setSize({ width: Math.max(320, bounds.width), height: Math.max(420, bounds.height) });
    };
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(host);
    window.addEventListener("resize", measure);
    return () => { observer?.disconnect(); window.removeEventListener("resize", measure); };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof CanvasRenderingContext2D === "undefined") return;
    let context: CanvasRenderingContext2D | null = null;
    try { context = canvas.getContext("2d", { alpha: false }); } catch { context = null; }
    if (!context) return;
    rendererRef.current = new CanvasStructuralRenderer(canvas, context);
    return () => { rendererRef.current?.destroy(); rendererRef.current = null; };
  }, []);

  useEffect(() => { stepStartedAt.current = performance.now(); }, [currentKey]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.resize(size.width, size.height, window.devicePixelRatio || 1);
    let frame = 0;
    const draw = (now: number) => {
      renderer.render({ model, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, traceMode, reducedMotion, elapsedMs: reducedMotion ? 900 : now - stepStartedAt.current, reconciliationTargetId, commonOriginNodeId });
      if (!reducedMotion) frame = window.requestAnimationFrame(draw);
    };
    draw(performance.now());
    return () => window.cancelAnimationFrame(frame);
  }, [model, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, traceMode, reducedMotion, reconciliationTargetId, commonOriginNodeId, size]);

  return <div ref={hostRef} className="sm-viz-surface" data-structural-renderer="canvas-rd" data-trace-mode={traceMode}>
    <canvas ref={canvasRef} className="sm-viz-canvas" role="img" aria-label="Synthetic structural pressure surface with nine distinct node forms and continuous routed dependencies" data-renderer-surface="canvas" />
    <p className="sm-sr-only">The canvas is supplemented by keyboard-accessible node controls and a complete structured relationship list.</p>
    <div className="sm-viz-node-layer" aria-label="Synthetic structural nodes">{model.nodes.map((node) => {
      const point = projectNode(node, camera);
      const state = nodeStates.get(node.id) ?? "IDLE";
      const active = state !== "IDLE" && state !== "SIGNAL_READY";
      const onPath = pathNodes.has(node.id);
      return <button key={node.id} type="button" style={{ left: point.x, top: point.y }} className={`sm-viz-node-label is-${node.kind.toLowerCase()} ${selectedNodeId === node.id ? "is-selected" : ""} ${active ? "is-active" : ""} ${onPath ? "is-path" : ""}`} aria-label={`${node.label}. ${node.kind}. ${state}. Enter this system.`} aria-pressed={selectedNodeId === node.id} data-motion-node-id={node.id} data-motion-state={state} data-motion-active={active} onClick={(event) => onSelectNode(node.id, event.currentTarget)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectNode(node.id, event.currentTarget); } }}><span>{node.label}</span><small>{node.kind.replaceAll("_", " ")}</small></button>;
    })}</div>
    <div className="sm-viz-semantic-state" hidden>{currentEdges.map((edge) => {
      const terminal = ["BLOCKED", "ABSORBED", "UNKNOWN"].includes(edge.outcome);
      return <span key={edge.id} className="sm-motion-current-signal sm-motion-signal is-current" data-motion-edge-id={edge.id} data-motion-outcome={edge.outcome} data-direction="forward" data-origin-id={edge.originId} data-signal-terminates={terminal ? "before-destination" : "at-destination"} data-motion-component={edge.outcome === "PARTIALLY_ABSORBED" ? "surviving" : undefined} data-motion-phase={edge.outcome === "DELAYED" ? "WAITING" : undefined} data-motion-strength={edge.outcome === "AMPLIFIED" ? "stronger" : undefined} data-motion-terminal={edge.outcome === "BLOCKED" ? "BLOCKED" : edge.outcome === "ABSORBED" ? "ABSORBED" : edge.outcome === "UNKNOWN" ? "UNRESOLVED" : undefined} />;
    })}{currentEdges.some((edge) => edge.outcome === "PARTIALLY_ABSORBED") && <span data-motion-component="absorbed" />}{currentEdges.some((edge) => edge.outcome === "AMPLIFIED") && <span className="sm-motion-amplified-halo" />}{commonOriginNodeId && <span className="sm-motion-origin-token" data-origin-id={path.originId} data-anchor-node-id={commonOriginNodeId} />}{reconciliationTargetId && <span data-common-origin-reconciliation="single" data-anchor-node-id={reconciliationTargetId} />}</div>
  </div>;
}
