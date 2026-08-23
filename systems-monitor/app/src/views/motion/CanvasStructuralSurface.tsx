import { useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from "react";
import type { MotionQaNode, MotionQaPath, MotionQaReadModel, MotionQaRelationship } from "../../data/motionQaReadModel";
import { applyStructuralViewport, CanvasStructuralRenderer, createStructuralCamera, projectNode, zoomStructuralViewportAt, type StructuralViewportTransform } from "./structuralRenderer";
import { layoutSpatialLabels, layoutSpatialNodes, nextNodeInDirection, type SpatialViewport } from "./spatialNavigation";
import { resolveStructuralNodeVisual } from "./structuralVisualLanguage";

const DEFAULT_VIEWPORT: StructuralViewportTransform = { zoom: 1, panX: 0, panY: 0 };

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
  const panSession = useRef<{ pointerId: number; startX: number; startY: number; panX: number; panY: number } | null>(null);
  const wheelTimer = useRef<number | null>(null);
  const [size, setSize] = useState({ width: 1000, height: 620 });
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [viewportTransform, setViewportTransform] = useState<StructuralViewportTransform>(DEFAULT_VIEWPORT);
  const [panning, setPanning] = useState(false);
  const [wheelActive, setWheelActive] = useState(false);
  const spatialNodes = useMemo(() => traceMode ? model.nodes.map((node) => ({ ...node })) : layoutSpatialNodes(model, viewport), [model, viewport, traceMode]);
  const spatialModel = useMemo(() => ({ ...model, nodes: spatialNodes }), [model, spatialNodes]);
  const nodes = useMemo(() => new Map(spatialNodes.map((node) => [node.id, node])), [spatialNodes]);
  const selectedNode = selectedNodeId ? nodes.get(selectedNodeId) : undefined;
  const camera = useMemo(() => applyStructuralViewport(createStructuralCamera(size.width, size.height, traceMode ? undefined : selectedNode, traceMode ? 0 : focusDepth), size.width, size.height, viewportTransform), [size, selectedNode, focusDepth, traceMode, viewportTransform]);
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

  useEffect(() => () => { if (wheelTimer.current !== null) window.clearTimeout(wheelTimer.current); }, []);

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
      renderer.render({ model: spatialModel, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, hoveredNodeId, viewportTransform, cameraFocusNodeId: traceMode ? null : selectedNodeId, focusDepth: traceMode ? 0 : focusDepth, visibleNodeIds: viewport.visibleNodeIds, visibleRelationshipIds: viewport.visibleRelationshipIds, traceMode, reducedMotion, elapsedMs: reducedMotion ? 900 : now - stepStartedAt.current, nowMs: now, reconciliationTargetId, commonOriginNodeId });
      if (!reducedMotion) frame = window.requestAnimationFrame(draw);
    };
    draw(performance.now());
    return () => window.cancelAnimationFrame(frame);
  }, [spatialModel, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, hoveredNodeId, viewportTransform, focusDepth, viewport.visibleNodeIds, viewport.visibleRelationshipIds, traceMode, reducedMotion, reconciliationTargetId, commonOriginNodeId, size]);

  function zoomAt(factor: number, x = size.width / 2, y = size.height / 2) {
    setViewportTransform((current) => zoomStructuralViewportAt(current, x, y, size.width, size.height, factor));
  }

  function handleWheel(event: ReactWheelEvent<HTMLDivElement>) {
    event.preventDefault();
    const bounds = event.currentTarget.getBoundingClientRect();
    setWheelActive(true);
    if (wheelTimer.current !== null) window.clearTimeout(wheelTimer.current);
    zoomAt(Math.exp(-event.deltaY * 0.00135), event.clientX - bounds.left, event.clientY - bounds.top);
    wheelTimer.current = window.setTimeout(() => setWheelActive(false), 140);
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 1) return;
    event.preventDefault();
    panSession.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, panX: viewportTransform.panX, panY: viewportTransform.panY };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setPanning(true);
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const session = panSession.current;
    if (!session || session.pointerId !== event.pointerId) return;
    event.preventDefault();
    setViewportTransform((current) => ({ ...current, panX: session.panX + event.clientX - session.startX, panY: session.panY + event.clientY - session.startY }));
  }

  function endPan(event: ReactPointerEvent<HTMLDivElement>) {
    if (!panSession.current || panSession.current.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    panSession.current = null;
    setPanning(false);
  }

  return <div ref={hostRef} className={`sm-viz-surface ${panning || wheelActive ? "is-manipulating" : ""} ${panning ? "is-panning" : ""}`} data-structural-renderer="canvas-rd" data-trace-mode={traceMode} data-focus-depth={focusDepth} data-visible-relationship-count={viewport.visibleRelationshipIds.size} data-hovered-node-id={hoveredNodeId ?? ""} data-connector-motion={reducedMotion ? "static" : traceMode ? "trace" : "ambient"} data-viewport-zoom={viewportTransform.zoom.toFixed(3)} data-viewport-pan-x={Math.round(viewportTransform.panX)} data-viewport-pan-y={Math.round(viewportTransform.panY)} onWheel={handleWheel} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={endPan} onPointerCancel={endPan} onMouseDown={(event) => { if (event.button === 1) event.preventDefault(); }} onAuxClick={(event) => { if (event.button === 1) event.preventDefault(); }}>
    <canvas ref={canvasRef} className="sm-viz-canvas" role="img" aria-label="Synthetic structural pressure surface with spatial neighborhoods and continuous routed dependencies" data-renderer-surface="canvas" />
    <p className="sm-sr-only">The canvas is supplemented by keyboard-accessible node controls and a complete structured relationship list. Mouse wheel zooms. Hold the middle mouse button and drag to pan.</p>
    <div className="sm-viz-node-layer" aria-label="Synthetic structural nodes">{spatialNodes.map((node) => {
      const point = projectNode(node, camera);
      const label = labels.get(node.id);
      const state = nodeStates.get(node.id) ?? "IDLE";
      const active = state !== "IDLE" && state !== "SIGNAL_READY";
      const onPath = pathNodes.has(node.id);
      const visible = viewport.visibleNodeIds.has(node.id);
      const visual = resolveStructuralNodeVisual(node);
      const style = { left: point.x, top: point.y, "--label-x": `${(label?.x ?? point.x) - point.x}px`, "--label-y": `${(label?.y ?? point.y + 31) - point.y}px`, "--label-width": `${label?.width ?? 120}px`, "--node-accent": visual.accent, "--node-fill": visual.fill } as CSSProperties;
      const hovered = hoveredNodeId === node.id;
      return <button key={node.id} ref={(element) => { if (element) nodeButtons.current.set(node.id, element); else nodeButtons.current.delete(node.id); }} type="button" style={style} className={`sm-viz-node-label is-${node.kind.toLowerCase()} ${selectedNodeId === node.id ? "is-selected" : ""} ${hovered ? "is-hovered" : ""} ${active ? "is-active" : ""} ${onPath ? "is-path" : ""} ${visible ? "is-neighborhood" : "is-context-hidden"} ${label?.suppressed ? "is-label-suppressed" : ""}`} aria-label={`${node.detailLabel}. ${state}. Enter this system.`} aria-pressed={selectedNodeId === node.id} aria-hidden={!visible} tabIndex={visible ? 0 : -1} data-motion-node-id={node.id} data-motion-state={state} data-motion-active={active} data-node-type={node.kind} data-node-role={visual.role} data-node-symbol={visual.symbol} data-hovered={hovered} data-label-level={focusDepth} data-label-priority={label?.priority ?? "DETAIL"} data-label-suppressed={label?.suppressed ?? true} onPointerEnter={() => setHoveredNodeId(node.id)} onPointerLeave={() => setHoveredNodeId((current) => current === node.id ? null : current)} onFocus={() => setHoveredNodeId(node.id)} onBlur={() => setHoveredNodeId((current) => current === node.id ? null : current)} onClick={(event) => onSelectNode(node.id, event.currentTarget)} onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectNode(node.id, event.currentTarget); return; }
        if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
          event.preventDefault();
          const nextId = nextNodeInDirection(spatialNodes, viewport.visibleNodeIds, node.id, event.key as "ArrowLeft" | "ArrowRight" | "ArrowUp" | "ArrowDown");
          if (nextId) nodeButtons.current.get(nextId)?.focus();
        }
      }}><span><b>{label?.text ?? node.label}</b><small>{focusDepth > 0 ? node.kind.replaceAll("_", " ") : ""}</small></span></button>;
    })}</div>
    <div className="sm-viz-viewport-controls" aria-label="Graph viewport controls" onPointerDown={(event) => event.stopPropagation()}>
      <button type="button" aria-label="Zoom out" onClick={() => zoomAt(0.85)}>−</button>
      <output aria-label="Graph zoom level">{Math.round(viewportTransform.zoom * 100)}%</output>
      <button type="button" aria-label="Zoom in" onClick={() => zoomAt(1.18)}>+</button>
      <button type="button" aria-label="Reset graph view" onClick={() => setViewportTransform(DEFAULT_VIEWPORT)}>⌖</button>
    </div>
    <div className="sm-viz-semantic-state" hidden>{currentEdges.map((edge) => {
      const terminal = ["BLOCKED", "ABSORBED", "UNKNOWN"].includes(edge.outcome);
      return <span key={edge.id} className="sm-motion-current-signal sm-motion-signal is-current" data-motion-edge-id={edge.id} data-motion-outcome={edge.outcome} data-direction="forward" data-origin-id={edge.originId} data-signal-terminates={terminal ? "before-destination" : "at-destination"} data-motion-component={edge.outcome === "PARTIALLY_ABSORBED" ? "surviving" : undefined} data-motion-phase={edge.outcome === "DELAYED" ? "WAITING" : undefined} data-motion-strength={edge.outcome === "AMPLIFIED" ? "stronger" : undefined} data-motion-terminal={edge.outcome === "BLOCKED" ? "BLOCKED" : edge.outcome === "ABSORBED" ? "ABSORBED" : edge.outcome === "UNKNOWN" ? "UNRESOLVED" : undefined} />;
    })}{currentEdges.some((edge) => edge.outcome === "PARTIALLY_ABSORBED") && <span data-motion-component="absorbed" />}{currentEdges.some((edge) => edge.outcome === "AMPLIFIED") && <span className="sm-motion-amplified-halo" />}{traceMode && commonOriginNodeId && <span className="sm-motion-origin-token" data-origin-id={path.originId} data-anchor-node-id={commonOriginNodeId} />}{traceMode && reconciliationTargetId && <span data-common-origin-reconciliation="single" data-anchor-node-id={reconciliationTargetId} />}</div>
  </div>;
}
