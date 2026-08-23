import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { MotionQaNode, MotionQaPath, MotionQaReadModel, MotionQaRelationship } from "../../data/motionQaReadModel";
import { CanvasStructuralRenderer, createStructuralCamera, projectNode } from "./structuralRenderer";
import { layoutSpatialLabels, layoutSpatialNodes, nextNodeInDirection, type SpatialViewport } from "./spatialNavigation";

interface CanvasStructuralSurfaceProps {
  model: MotionQaReadModel;
  path: MotionQaPath;
  currentEdges: MotionQaRelationship[];
  completedEdgeIds: Set<string>;
  pathEdgeIds: Set<string>;
  nodeStates: Map<string, string>;
  selectedNodeId: string | null;
  focusDepth: number;
  viewport: SpatialViewport;
  traceMode: boolean;
  reducedMotion: boolean;
  reconciliationTargetId: string | null;
  onSelectNode: (nodeId: string, target: HTMLButtonElement) => void;
}

export function CanvasStructuralSurface({ model, path, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, focusDepth, viewport, traceMode, reducedMotion, reconciliationTargetId, onSelectNode }: CanvasStructuralSurfaceProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<CanvasStructuralRenderer | null>(null);
  const nodeButtons = useRef(new Map<string, HTMLButtonElement>());
  const stepStartedAt = useRef(0);
  const [size, setSize] = useState({ width: 1000, height: 620 });
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const spatialNodes = useMemo(() => traceMode ? model.nodes.map((node) => ({ ...node })) : layoutSpatialNodes(model, viewport), [model, viewport, traceMode]);
  const spatialModel = useMemo(() => ({ ...model, nodes: spatialNodes }), [model, spatialNodes]);
  const nodes = useMemo(() => new Map(spatialNodes.map((node) => [node.id, node])), [spatialNodes]);
  const selectedNode = selectedNodeId ? nodes.get(selectedNodeId) : undefined;
  const camera = useMemo(() => createStructuralCamera(size.width, size.height, traceMode ? undefined : selectedNode, traceMode ? 0 : focusDepth), [size, selectedNode, focusDepth, traceMode]);
  const pathNodes = useMemo(() => new Set(model.relationships.filter((edge) => pathEdgeIds.has(edge.id)).flatMap((edge) => [edge.from, edge.to])), [model.relationships, pathEdgeIds]);
  const currentKey = currentEdges.map((edge) => edge.id).join("|");
  const commonOriginNodeId = path.commonCauseId ? model.relationships.find((edge) => edge.id === path.steps[0][0])?.from ?? null : null;
  const labelPlacements = useMemo(() => layoutSpatialLabels({ nodes: spatialNodes, camera, width: size.width, height: size.height, focusDepth, selectedNodeId, visibleNodeIds: viewport.visibleNodeIds, traceNodeIds: pathNodes }), [spatialNodes, camera, size, focusDepth, selectedNodeId, viewport.visibleNodeIds, pathNodes]);
  const labels = useMemo(() => new Map(labelPlacements.map((placement) => [placement.nodeId, placement])), [labelPlacements]);

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
      renderer.render({ model: spatialModel, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, hoveredNodeId, cameraFocusNodeId: traceMode ? null : selectedNodeId, focusDepth: traceMode ? 0 : focusDepth, visibleNodeIds: viewport.visibleNodeIds, visibleRelationshipIds: viewport.visibleRelationshipIds, traceMode, reducedMotion, elapsedMs: reducedMotion ? 900 : now - stepStartedAt.current, nowMs: now, reconciliationTargetId, commonOriginNodeId });
      if (!reducedMotion) frame = window.requestAnimationFrame(draw);
    };
    draw(performance.now());
    return () => window.cancelAnimationFrame(frame);
  }, [spatialModel, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, hoveredNodeId, focusDepth, viewport.visibleNodeIds, viewport.visibleRelationshipIds, traceMode, reducedMotion, reconciliationTargetId, commonOriginNodeId, size]);

  return <div ref={hostRef} className="sm-viz-surface" data-structural-renderer="canvas-rd" data-trace-mode={traceMode} data-focus-depth={focusDepth} data-visible-relationship-count={viewport.visibleRelationshipIds.size} data-hovered-node-id={hoveredNodeId ?? ""}>
    <canvas ref={canvasRef} className="sm-viz-canvas" role="img" aria-label="Synthetic structural pressure surface with spatial neighborhoods and continuous routed dependencies" data-renderer-surface="canvas" />
    <p className="sm-sr-only">The canvas is supplemented by keyboard-accessible node controls and a complete structured relationship list.</p>
    <div className="sm-viz-node-layer" aria-label="Synthetic structural nodes">{spatialNodes.map((node) => {
      const point = projectNode(node, camera);
      const label = labels.get(node.id);
      const state = nodeStates.get(node.id) ?? "IDLE";
      const active = state !== "IDLE" && state !== "SIGNAL_READY";
      const onPath = pathNodes.has(node.id);
      const visible = viewport.visibleNodeIds.has(node.id);
      const style = { left: point.x, top: point.y, "--label-x": `${(label?.x ?? point.x) - point.x}px`, "--label-y": `${(label?.y ?? point.y + 31) - point.y}px`, "--label-width": `${label?.width ?? 120}px` } as CSSProperties;
      const hovered = hoveredNodeId === node.id;
      return <button key={node.id} ref={(element) => { if (element) nodeButtons.current.set(node.id, element); else nodeButtons.current.delete(node.id); }} type="button" style={style} className={`sm-viz-node-label is-${node.kind.toLowerCase()} ${selectedNodeId === node.id ? "is-selected" : ""} ${hovered ? "is-hovered" : ""} ${active ? "is-active" : ""} ${onPath ? "is-path" : ""} ${visible ? "is-neighborhood" : "is-context-hidden"} ${label?.suppressed ? "is-label-suppressed" : ""}`} aria-label={`${node.detailLabel}. ${state}. Enter this system.`} aria-pressed={selectedNodeId === node.id} aria-hidden={!visible} tabIndex={visible ? 0 : -1} data-motion-node-id={node.id} data-motion-state={state} data-motion-active={active} data-node-type={node.kind} data-hovered={hovered} data-label-level={focusDepth} data-label-priority={label?.priority ?? "DETAIL"} data-label-suppressed={label?.suppressed ?? true} onPointerEnter={() => setHoveredNodeId(node.id)} onPointerLeave={() => setHoveredNodeId((current) => current === node.id ? null : current)} onFocus={() => setHoveredNodeId(node.id)} onBlur={() => setHoveredNodeId((current) => current === node.id ? null : current)} onClick={(event) => onSelectNode(node.id, event.currentTarget)} onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectNode(node.id, event.currentTarget); return; }
        if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
          event.preventDefault();
          const nextId = nextNodeInDirection(spatialNodes, viewport.visibleNodeIds, node.id, event.key as "ArrowLeft" | "ArrowRight" | "ArrowUp" | "ArrowDown");
          if (nextId) nodeButtons.current.get(nextId)?.focus();
        }
      }}><span><b>{label?.text ?? node.label}</b><small>{focusDepth > 0 ? node.kind.replaceAll("_", " ") : ""}</small></span></button>;
    })}</div>
    <div className="sm-viz-semantic-state" hidden>{currentEdges.map((edge) => {
      const terminal = ["BLOCKED", "ABSORBED", "UNKNOWN"].includes(edge.outcome);
      return <span key={edge.id} className="sm-motion-current-signal sm-motion-signal is-current" data-motion-edge-id={edge.id} data-motion-outcome={edge.outcome} data-direction="forward" data-origin-id={edge.originId} data-signal-terminates={terminal ? "before-destination" : "at-destination"} data-motion-component={edge.outcome === "PARTIALLY_ABSORBED" ? "surviving" : undefined} data-motion-phase={edge.outcome === "DELAYED" ? "WAITING" : undefined} data-motion-strength={edge.outcome === "AMPLIFIED" ? "stronger" : undefined} data-motion-terminal={edge.outcome === "BLOCKED" ? "BLOCKED" : edge.outcome === "ABSORBED" ? "ABSORBED" : edge.outcome === "UNKNOWN" ? "UNRESOLVED" : undefined} />;
    })}{currentEdges.some((edge) => edge.outcome === "PARTIALLY_ABSORBED") && <span data-motion-component="absorbed" />}{currentEdges.some((edge) => edge.outcome === "AMPLIFIED") && <span className="sm-motion-amplified-halo" />}{traceMode && commonOriginNodeId && <span className="sm-motion-origin-token" data-origin-id={path.originId} data-anchor-node-id={commonOriginNodeId} />}{traceMode && reconciliationTargetId && <span data-common-origin-reconciliation="single" data-anchor-node-id={reconciliationTargetId} />}</div>
  </div>;
}
