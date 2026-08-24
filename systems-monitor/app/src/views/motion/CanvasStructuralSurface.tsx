import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent } from "react";
import type { MotionQaNode, MotionQaPath, MotionQaReadModel, MotionQaRelationship } from "../../data/motionQaReadModel";
import { applyStructuralViewport, CanvasStructuralRenderer, createStructuralCamera, projectNode, resolveStructuralDepths, resolveStructuralDepthVisual, STRUCTURAL_PARTICLES_PER_NODE, zoomStructuralViewportAt, type StructuralViewportTransform } from "./structuralRenderer";
import { layoutEmploymentOrbit, layoutSpatialLabels, nextNodeInDirection, type SpatialViewport } from "./spatialNavigation";
import { StructuralNodeIcon } from "./StructuralNodeIcon";
import { layoutStructuralContextFactors } from "./structuralContextFactors";
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
  onReset: () => void;
}

export function CanvasStructuralSurface({ model, path, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, focusDepth, viewport, traceMode, reducedMotion, reconciliationTargetId, onSelectNode, onReset }: CanvasStructuralSurfaceProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<CanvasStructuralRenderer | null>(null);
  const nodeButtons = useRef(new Map<string, HTMLButtonElement>());
  const stepStartedAt = useRef(0);
  const panSession = useRef<{ pointerId: number; startX: number; startY: number; panX: number; panY: number } | null>(null);
  const wheelTimer = useRef<number | null>(null);
  const parallaxTarget = useRef({ x: 0, y: 0 });
  const [size, setSize] = useState({ width: 1000, height: 620 });
  const sizeRef = useRef(size);
  sizeRef.current = size;
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [viewportTransform, setViewportTransform] = useState<StructuralViewportTransform>(DEFAULT_VIEWPORT);
  const [panning, setPanning] = useState(false);
  const [wheelActive, setWheelActive] = useState(false);
  const spatialNodes = useMemo(() => layoutEmploymentOrbit(model), [model]);
  const spatialModel = useMemo(() => ({ ...model, nodes: spatialNodes }), [model, spatialNodes]);
  const nodes = useMemo(() => new Map(spatialNodes.map((node) => [node.id, node])), [spatialNodes]);
  const selectedNode = selectedNodeId ? nodes.get(selectedNodeId) : undefined;
  const camera = useMemo(() => applyStructuralViewport(createStructuralCamera(size.width, size.height, traceMode ? undefined : selectedNode, traceMode ? 0 : focusDepth), size.width, size.height, viewportTransform), [size, selectedNode, focusDepth, traceMode, viewportTransform]);
  const pathNodes = useMemo(() => new Set(model.relationships.filter((edge) => pathEdgeIds.has(edge.id)).flatMap((edge) => [edge.from, edge.to])), [model.relationships, pathEdgeIds]);
  const currentKey = currentEdges.map((edge) => edge.id).join("|");
  const commonOriginNodeId = path.commonCauseId ? model.relationships.find((edge) => edge.id === path.steps[0][0])?.from ?? null : null;
  const labelPlacements = useMemo(() => layoutSpatialLabels({ nodes: spatialNodes, camera, width: size.width, height: size.height, focusDepth, selectedNodeId, visibleNodeIds: viewport.visibleNodeIds, traceNodeIds: pathNodes }), [spatialNodes, camera, size, focusDepth, selectedNodeId, viewport.visibleNodeIds, pathNodes]);
  const labels = useMemo(() => new Map(labelPlacements.map((placement) => [placement.nodeId, placement])), [labelPlacements]);
  const structuralDepths = useMemo(() => resolveStructuralDepths(spatialModel, traceMode ? null : selectedNodeId), [spatialModel, traceMode, selectedNodeId]);
  const contextFactorLayouts = useMemo(() => layoutStructuralContextFactors(spatialNodes, camera, structuralDepths, viewport.visibleNodeIds), [spatialNodes, camera, structuralDepths, viewport.visibleNodeIds]);

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
    const host = hostRef.current;
    if (!host) return;
    const lockPageAndZoom = (event: WheelEvent) => {
      event.preventDefault();
      const currentSize = sizeRef.current;
      const bounds = host.getBoundingClientRect();
      setWheelActive(true);
      if (wheelTimer.current !== null) window.clearTimeout(wheelTimer.current);
      setViewportTransform((current) => zoomStructuralViewportAt(current, event.clientX - bounds.left, event.clientY - bounds.top, currentSize.width, currentSize.height, Math.exp(-event.deltaY * 0.00135)));
      wheelTimer.current = window.setTimeout(() => setWheelActive(false), 140);
    };
    host.addEventListener("wheel", lockPageAndZoom, { passive: false });
    return () => host.removeEventListener("wheel", lockPageAndZoom);
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
      renderer.render({ model: spatialModel, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, hoveredNodeId, viewportTransform, cameraFocusNodeId: traceMode ? null : selectedNodeId, focusDepth: traceMode ? 0 : focusDepth, visibleNodeIds: viewport.visibleNodeIds, visibleRelationshipIds: viewport.visibleRelationshipIds, traceMode, reducedMotion, elapsedMs: reducedMotion ? 900 : now - stepStartedAt.current, nowMs: now, reconciliationTargetId, commonOriginNodeId, parallaxTarget: parallaxTarget.current });
      if (!reducedMotion) frame = window.requestAnimationFrame(draw);
    };
    draw(performance.now());
    return () => window.cancelAnimationFrame(frame);
  }, [spatialModel, currentEdges, completedEdgeIds, pathEdgeIds, nodeStates, selectedNodeId, hoveredNodeId, viewportTransform, focusDepth, viewport.visibleNodeIds, viewport.visibleRelationshipIds, traceMode, reducedMotion, reconciliationTargetId, commonOriginNodeId, size]);

  function zoomAt(factor: number, x = size.width / 2, y = size.height / 2) {
    setViewportTransform((current) => zoomStructuralViewportAt(current, x, y, size.width, size.height, factor));
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 1) return;
    event.preventDefault();
    panSession.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, panX: viewportTransform.panX, panY: viewportTransform.panY };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setPanning(true);
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    parallaxTarget.current = {
      x: Math.max(-1, Math.min(1, ((event.clientX - bounds.left) / bounds.width - 0.5) * 2)),
      y: Math.max(-1, Math.min(1, ((event.clientY - bounds.top) / bounds.height - 0.5) * 2))
    };
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

  function resetSurface() {
    setViewportTransform(DEFAULT_VIEWPORT);
    setHoveredNodeId(null);
    parallaxTarget.current = { x: 0, y: 0 };
    onReset();
  }

  function handleDoubleClick(event: ReactMouseEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("button, a, input, textarea, select, summary")) return;
    event.preventDefault();
    resetSurface();
  }

  return <div ref={hostRef} className={`sm-viz-surface ${panning || wheelActive ? "is-manipulating" : ""} ${panning ? "is-panning" : ""}`} data-structural-renderer="canvas-rd" data-layout-mode="employment-orbit" data-depth-field={reducedMotion ? "static" : "spring-parallax"} data-depth-particle-count={spatialNodes.length * STRUCTURAL_PARTICLES_PER_NODE} data-camera-motion="stable-map-swing-focus" data-context-factor-count={contextFactorLayouts.length} data-trace-mode={traceMode} data-focus-depth={focusDepth} data-visible-relationship-count={viewport.visibleRelationshipIds.size} data-visible-relationship-ids={[...viewport.visibleRelationshipIds].join(" ")} data-hovered-node-id={hoveredNodeId ?? ""} data-connector-motion={reducedMotion ? "static" : traceMode ? "trace" : "ambient"} data-viewport-zoom={viewportTransform.zoom.toFixed(3)} data-viewport-pan-x={Math.round(viewportTransform.panX)} data-viewport-pan-y={Math.round(viewportTransform.panY)} onDoubleClick={handleDoubleClick} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerLeave={() => { if (!panSession.current) parallaxTarget.current = { x: 0, y: 0 }; }} onPointerUp={endPan} onPointerCancel={endPan} onMouseDown={(event) => { if (event.button === 1) event.preventDefault(); }} onAuxClick={(event) => { if (event.button === 1) event.preventDefault(); }}>
    <canvas ref={canvasRef} className="sm-viz-canvas" role="img" aria-label="Synthetic structural pressure surface with spatial neighborhoods and continuous routed dependencies" data-renderer-surface="canvas" />
    <p className="sm-sr-only">The canvas is supplemented by keyboard-accessible node controls and a complete structured relationship list. Mouse wheel zooms. Hold the middle mouse button and drag to pan.</p>
    <svg className="sm-viz-context-links" width={size.width} height={size.height} aria-hidden="true">{contextFactorLayouts.map((factor) => {
      const parentActive = selectedNodeId === factor.parentNodeId || hoveredNodeId === factor.parentNodeId;
      const parent = nodes.get(factor.parentNodeId);
      const visual = parent ? resolveStructuralNodeVisual(parent) : null;
      return <line key={factor.id} x1={factor.parentX} y1={factor.parentY} x2={factor.x} y2={factor.y} className={parentActive ? "is-active" : ""} style={{ "--context-accent": visual?.accent ?? "#82efd5" } as CSSProperties} />;
    })}</svg>
    <div className="sm-viz-context-layer" aria-label="Synthetic underlying factor previews">{contextFactorLayouts.map((factor) => {
      const parent = nodes.get(factor.parentNodeId);
      if (!parent) return null;
      const parentActive = selectedNodeId === factor.parentNodeId || hoveredNodeId === factor.parentNodeId;
      const visual = resolveStructuralNodeVisual(parent);
      const depthVisual = resolveStructuralDepthVisual(factor.visualDepth, parentActive);
      const factorStyle = { left: factor.x, top: factor.y, "--context-accent": visual.accent, "--context-scale": depthVisual.scale, "--context-opacity": depthVisual.opacity } as CSSProperties;
      return <button key={factor.id} type="button" style={factorStyle} className={parentActive ? "is-parent-active" : ""} aria-label={`${factor.label}, synthetic underlying factor for ${parent.detailLabel}. Open parent factor.`} aria-hidden={!parentActive} tabIndex={parentActive ? 0 : -1} data-context-factor-id={factor.id} data-context-parent-id={factor.parentNodeId} data-context-factor-depth={factor.visualDepth} onPointerEnter={() => setHoveredNodeId(factor.parentNodeId)} onPointerLeave={() => setHoveredNodeId((current) => current === factor.parentNodeId ? null : current)} onFocus={() => setHoveredNodeId(factor.parentNodeId)} onBlur={() => setHoveredNodeId((current) => current === factor.parentNodeId ? null : current)} onClick={() => { const parentButton = nodeButtons.current.get(factor.parentNodeId); if (parentButton) onSelectNode(factor.parentNodeId, parentButton); }}><i aria-hidden="true" /><span>{factor.label}</span></button>;
    })}</div>
    <div className="sm-viz-node-layer" aria-label="Synthetic structural nodes">{spatialNodes.map((node) => {
      const point = projectNode(node, camera);
      const label = labels.get(node.id);
      const state = nodeStates.get(node.id) ?? "IDLE";
      const active = state !== "IDLE" && state !== "SIGNAL_READY";
      const onPath = pathNodes.has(node.id);
      const visible = viewport.visibleNodeIds.has(node.id);
      const visual = resolveStructuralNodeVisual(node);
      const hovered = hoveredNodeId === node.id;
      const depthVisual = resolveStructuralDepthVisual(structuralDepths.get(node.id) ?? 0, hovered || selectedNodeId === node.id || active || (!selectedNodeId && node.id === "fixture-employment"));
      const style = { left: point.x, top: point.y, "--label-x": `${(label?.x ?? point.x) - point.x}px`, "--label-y": `${(label?.y ?? point.y + 31) - point.y}px`, "--label-width": `${label?.width ?? 120}px`, "--node-accent": visual.accent, "--node-fill": visual.fill, "--node-depth-scale": depthVisual.scale, "--node-depth-opacity": depthVisual.opacity } as CSSProperties;
      return <button key={node.id} ref={(element) => { if (element) nodeButtons.current.set(node.id, element); else nodeButtons.current.delete(node.id); }} type="button" style={style} className={`sm-viz-node-label is-${node.kind.toLowerCase()} ${selectedNodeId === node.id ? "is-selected" : ""} ${hovered ? "is-hovered" : ""} ${active ? "is-active" : ""} ${onPath ? "is-path" : ""} ${visible ? "is-neighborhood" : "is-context-hidden"} ${label?.suppressed ? "is-label-suppressed" : ""}`} aria-label={`${node.detailLabel}. ${state}. Enter this system.`} aria-pressed={selectedNodeId === node.id} aria-hidden={!visible} tabIndex={visible ? 0 : -1} data-motion-node-id={node.id} data-motion-state={state} data-motion-active={active} data-node-type={node.kind} data-node-role={visual.role} data-node-symbol={visual.symbol} data-visual-depth={structuralDepths.get(node.id) ?? 0} data-hovered={hovered} data-label-level={focusDepth} data-label-priority={label?.priority ?? "DETAIL"} data-label-suppressed={label?.suppressed ?? true} onPointerEnter={() => setHoveredNodeId(node.id)} onPointerLeave={() => setHoveredNodeId((current) => current === node.id ? null : current)} onFocus={() => setHoveredNodeId(node.id)} onBlur={() => setHoveredNodeId((current) => current === node.id ? null : current)} onClick={(event) => onSelectNode(node.id, event.currentTarget)} onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectNode(node.id, event.currentTarget); return; }
        if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
          event.preventDefault();
          const nextId = nextNodeInDirection(spatialNodes, viewport.visibleNodeIds, node.id, event.key as "ArrowLeft" | "ArrowRight" | "ArrowUp" | "ArrowDown");
          if (nextId) nodeButtons.current.get(nextId)?.focus();
        }
      }}><i className="sm-viz-node-anchor" aria-hidden="true" data-selected-node-anchor={selectedNodeId === node.id ? "visible" : undefined}><StructuralNodeIcon symbol={visual.symbol} /></i><span><b>{label?.text ?? node.label}</b><small>{focusDepth > 0 ? node.kind.replaceAll("_", " ") : ""}</small></span></button>;
    })}</div>
    <div className="sm-viz-viewport-controls" aria-label="Graph viewport controls" onPointerDown={(event) => event.stopPropagation()}>
      <button type="button" className="is-reset" aria-label="Reset — show all core factors" onClick={resetSurface}><span aria-hidden="true">↺</span><b>Reset</b></button>
      <button type="button" aria-label="Zoom out" onClick={() => zoomAt(0.85)}>−</button>
      <output aria-label="Graph zoom level">{Math.round(viewportTransform.zoom * 100)}%</output>
      <button type="button" aria-label="Zoom in" onClick={() => zoomAt(1.18)}>+</button>
    </div>
    <div className="sm-viz-semantic-state" hidden>{currentEdges.map((edge) => {
      const terminal = ["BLOCKED", "ABSORBED", "UNKNOWN"].includes(edge.outcome);
      return <span key={edge.id} className="sm-motion-current-signal sm-motion-signal is-current" data-motion-edge-id={edge.id} data-motion-outcome={edge.outcome} data-direction="forward" data-origin-id={edge.originId} data-signal-terminates={terminal ? "before-destination" : "at-destination"} data-motion-component={edge.outcome === "PARTIALLY_ABSORBED" ? "surviving" : undefined} data-motion-phase={edge.outcome === "DELAYED" ? "WAITING" : undefined} data-motion-strength={edge.outcome === "AMPLIFIED" ? "stronger" : undefined} data-motion-terminal={edge.outcome === "BLOCKED" ? "BLOCKED" : edge.outcome === "ABSORBED" ? "ABSORBED" : edge.outcome === "UNKNOWN" ? "UNRESOLVED" : undefined} />;
    })}{currentEdges.some((edge) => edge.outcome === "PARTIALLY_ABSORBED") && <span data-motion-component="absorbed" />}{currentEdges.some((edge) => edge.outcome === "AMPLIFIED") && <span className="sm-motion-amplified-halo" />}{traceMode && commonOriginNodeId && <span className="sm-motion-origin-token" data-origin-id={path.originId} data-anchor-node-id={commonOriginNodeId} />}{traceMode && reconciliationTargetId && <span data-common-origin-reconciliation="single" data-anchor-node-id={reconciliationTargetId} />}</div>
  </div>;
}
