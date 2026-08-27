import { useEffect, useMemo, useRef, useState } from "react";
import type { PersistentWorldPlacement, PersistentWorldReadModel } from "../../data/persistentWorldModel";

interface Camera { x: number; y: number; scale: number }
interface Viewport { zoom: number; panX: number; panY: number }

interface PersistentWorldSurfaceProps {
  model: PersistentWorldReadModel;
  selectedPlacementId: string | null;
  fullWorld: boolean;
  reducedMotion: boolean;
  resetVersion: number;
  onSelect: (placementId: string) => void;
  onReset: () => void;
}

const sectorColors = ["#6fe4d0", "#59bff5", "#7d9cff", "#ef7f84", "#f0ae54", "#d8ca69", "#e685c4", "#a68cf0", "#66d0a4", "#f18d67"];
const OVERVIEW_SCALE = 0.205;

function targetCamera(model: PersistentWorldReadModel, selectedPlacementId: string | null, fullWorld: boolean): Camera {
  const selected = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
  if (!selected || fullWorld) return { x: 0, y: 0, scale: fullWorld ? 0.17 : OVERVIEW_SCALE };
  return { x: selected.x, y: selected.y, scale: selected.depth === 1 ? 0.64 : selected.depth === 2 ? 1.72 : 2.7 };
}

function project(placement: PersistentWorldPlacement, camera: Camera, viewport: Viewport, width: number, height: number) {
  return { x: width / 2 + (placement.x - camera.x) * camera.scale * viewport.zoom + viewport.panX, y: height / 2 + (placement.y - camera.y) * camera.scale * viewport.zoom + viewport.panY };
}

function semanticIds(model: PersistentWorldReadModel, selectedPlacementId: string | null) {
  if (!selectedPlacementId) return [model.outcomePlacementId, ...model.childrenByPlacement[model.outcomePlacementId]];
  const selected = model.placements[selectedPlacementId];
  if (!selected) return [model.outcomePlacementId];
  const parent = selected.parentPlacementId ? [selected.parentPlacementId] : [];
  const children = model.childrenByPlacement[selected.id] ?? [];
  if (children.length) return [...new Set([...parent, selected.id, ...children])];
  const siblings = selected.parentPlacementId ? model.childrenByPlacement[selected.parentPlacementId] ?? [] : [];
  return [...new Set([...parent, ...siblings])];
}

function isInSelectedSector(model: PersistentWorldReadModel, placement: PersistentWorldPlacement, selectedPlacementId: string | null) {
  if (!selectedPlacementId) return placement.depth < 2;
  const selected = model.placements[selectedPlacementId];
  return selected ? placement.sector === selected.sector || placement.depth === 0 : false;
}

export function PersistentWorldSurface({ model, selectedPlacementId, fullWorld, reducedMotion, resetVersion, onSelect, onReset }: PersistentWorldSurfaceProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraRef = useRef<Camera>(targetCamera(model, selectedPlacementId, fullWorld));
  const mountedAtRef = useRef(performance.now());
  const viewportRef = useRef<Viewport>({ zoom: 1, panX: 0, panY: 0 });
  const panRef = useRef<{ pointerId: number; startX: number; startY: number; panX: number; panY: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const semantic = useMemo(() => semanticIds(model, selectedPlacementId), [model, selectedPlacementId]);
  const semanticSet = useMemo(() => new Set(semantic), [semantic]);
  const selectedPath = useMemo(() => {
    const ids = new Set<string>();
    let current = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
    while (current) { ids.add(current.id); current = current.parentPlacementId ? model.placements[current.parentPlacementId] : undefined; }
    return ids;
  }, [model, selectedPlacementId]);

  useEffect(() => {
    viewportRef.current = { zoom: 1, panX: 0, panY: 0 };
    const host = hostRef.current;
    if (host) {
      host.dataset.viewportZoom = "1.000";
      host.dataset.viewportPanX = "0";
      host.dataset.viewportPanY = "0";
    }
  }, [fullWorld, resetVersion, selectedPlacementId]);

  useEffect(() => {
    const host = hostRef.current;
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d", { alpha: false });
    if (!host || !canvas || !context) return;
    let frame = 0;
    let last = performance.now();
    let frameCount = 0;
    let accumulated = 0;
    const frameSamples: number[] = [];
    const destination = targetCamera(model, selectedPlacementId, fullWorld);
    const cameraStarted = performance.now();
    let cameraSettled = false;
    delete host.dataset.cameraSettleMs;
    if (reducedMotion) cameraRef.current = destination;

    const resize = () => {
      const bounds = host.getBoundingClientRect();
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.round(bounds.width * ratio));
      canvas.height = Math.max(1, Math.round(bounds.height * ratio));
      canvas.style.width = `${bounds.width}px`;
      canvas.style.height = `${bounds.height}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(host);

    const placements = Object.values(model.placements);
    const hierarchy = Object.values(model.relationships).filter((edge) => edge.relationshipClass === "HIERARCHY_TETHER");
    const influence = Object.values(model.relationships).filter((edge) => edge.relationshipClass === "SYNTHETIC_INFLUENCE");
    const highlightedEdges = hierarchy.filter((edge) => semanticSet.has(edge.fromPlacementId) && semanticSet.has(edge.toPlacementId));

    const draw = (now: number) => {
      const started = performance.now();
      const bounds = host.getBoundingClientRect();
      const width = bounds.width;
      const height = bounds.height;
      const camera = cameraRef.current;
      const viewport = viewportRef.current;
      if (!reducedMotion) {
        const amount = 1 - Math.pow(0.0008, Math.min(0.06, (now - last) / 1000));
        camera.x += (destination.x - camera.x) * amount;
        camera.y += (destination.y - camera.y) * amount;
        camera.scale += (destination.scale - camera.scale) * amount;
      }
      if (!cameraSettled && (reducedMotion || (Math.abs(camera.x - destination.x) < .35 && Math.abs(camera.y - destination.y) < .35 && Math.abs(camera.scale - destination.scale) < .001))) {
        cameraSettled = true;
        host.dataset.cameraSettleMs = (performance.now() - cameraStarted).toFixed(3);
      }
      last = now;
      context.fillStyle = "#06151d";
      context.fillRect(0, 0, width, height);
      const gradient = context.createRadialGradient(width / 2, height / 2, 30, width / 2, height / 2, Math.max(width, height) * 0.7);
      gradient.addColorStop(0, "rgba(24,92,101,.22)");
      gradient.addColorStop(1, "rgba(2,12,18,0)");
      context.fillStyle = gradient;
      context.fillRect(0, 0, width, height);

      context.lineWidth = 0.65;
      context.strokeStyle = "rgba(102,205,198,.075)";
      context.beginPath();
      for (const edge of hierarchy) {
        const from = project(model.placements[edge.fromPlacementId], camera, viewport, width, height);
        const to = project(model.placements[edge.toPlacementId], camera, viewport, width, height);
        context.moveTo(from.x, from.y); context.lineTo(to.x, to.y);
      }
      context.stroke();

      if (fullWorld) {
        context.strokeStyle = "rgba(154,124,231,.025)";
        context.lineWidth = 0.42;
        context.beginPath();
        for (const edge of influence) {
          const from = project(model.placements[edge.fromPlacementId], camera, viewport, width, height);
          const to = project(model.placements[edge.toPlacementId], camera, viewport, width, height);
          context.moveTo(from.x, from.y); context.lineTo(to.x, to.y);
        }
        context.stroke();
      }

      context.lineCap = "round";
      for (const edge of highlightedEdges) {
        const from = project(model.placements[edge.fromPlacementId], camera, viewport, width, height);
        const to = project(model.placements[edge.toPlacementId], camera, viewport, width, height);
        const accent = sectorColors[Math.max(0, model.placements[edge.toPlacementId].sector)] ?? sectorColors[0];
        const hoveredEdge = Boolean(hoveredId && (edge.fromPlacementId === hoveredId || edge.toPlacementId === hoveredId));
        context.strokeStyle = `${accent}${hoveredId ? hoveredEdge ? "dd" : "38" : "88"}`;
        context.lineWidth = hoveredEdge ? 3.4 : 2.2;
        context.beginPath(); context.moveTo(from.x, from.y); context.lineTo(to.x, to.y); context.stroke();
        if (!reducedMotion) {
          const progress = (now / 2400 + model.placements[edge.toPlacementId].order * 0.071) % 1;
          const x = from.x + (to.x - from.x) * progress;
          const y = from.y + (to.y - from.y) * progress;
          context.fillStyle = accent;
          context.shadowColor = accent; context.shadowBlur = 10;
          context.beginPath(); context.arc(x, y, 2.3, 0, Math.PI * 2); context.fill();
          context.shadowBlur = 0;
        }
      }

      for (const placement of placements) {
        const point = project(placement, camera, viewport, width, height);
        if (point.x < -30 || point.y < -30 || point.x > width + 30 || point.y > height + 30) continue;
        const emphasized = semanticSet.has(placement.id) || selectedPath.has(placement.id);
        const sectorActive = isInSelectedSector(model, placement, selectedPlacementId);
        const radius = placement.depth === 0 ? 15 : placement.depth === 1 ? 8 : placement.depth === 2 ? 3.4 : Math.max(1.05, camera.scale * 1.15);
        const accent = placement.depth === 0 ? "#f08acb" : sectorColors[Math.max(0, placement.sector)] ?? sectorColors[0];
        context.globalAlpha = emphasized ? 1 : sectorActive ? (placement.depth === 3 ? 0.48 : 0.66) : (fullWorld ? 0.28 : 0.12);
        context.fillStyle = accent;
        context.shadowColor = accent;
        context.shadowBlur = emphasized ? 11 : 0;
        context.beginPath(); context.arc(point.x, point.y, radius, 0, Math.PI * 2); context.fill();
        if (emphasized && placement.depth < 3) {
          context.strokeStyle = `${accent}88`; context.lineWidth = 1.2;
          context.beginPath(); context.arc(point.x, point.y, radius + 5, 0, Math.PI * 2); context.stroke();
        }
        context.shadowBlur = 0;
      }
      context.globalAlpha = 1;

      context.font = "600 12px Inter, system-ui, sans-serif";
      context.textAlign = "center";
      for (const id of semantic) {
        const placement = model.placements[id];
        if (!placement) continue;
        const point = project(placement, camera, viewport, width, height);
        const label = model.factors[placement.canonicalFactorId].label;
        context.fillStyle = id === selectedPlacementId || placement.depth === 0 ? "#eafbf8" : "#b8d4d5";
        context.fillText(label, point.x, point.y + (placement.depth === 0 ? 31 : 23), 180);
      }

      if (hoveredId && model.placements[hoveredId]) {
        const placement = model.placements[hoveredId];
        const point = project(placement, camera, viewport, width, height);
        context.strokeStyle = "#ffffff"; context.lineWidth = 1.5;
        context.beginPath(); context.arc(point.x, point.y, placement.depth === 0 ? 22 : 15, 0, Math.PI * 2); context.stroke();
      }

      const elapsed = performance.now() - started;
      if (frameCount === 0) host.dataset.firstDrawMs = (performance.now() - mountedAtRef.current).toFixed(3);
      frameCount += 1; accumulated += elapsed; frameSamples.push(elapsed);
      if (frameCount === 30) {
        const ordered = [...frameSamples].sort((a, b) => a - b);
        const meanFrameMs = accumulated / frameCount;
        const medianFrameMs = ordered[Math.floor(ordered.length / 2)];
        const p95FrameMs = ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * .95) - 1)];
        const mode = fullWorld ? "FULL_WORLD_LOD" : selectedPlacementId ? "FOCUS_LOD" : "OVERVIEW_LOD";
        window.__AUXSAYS_PERSISTENT_WORLD_METRICS__ = { placementCount: placements.length, relationshipCount: hierarchy.length + influence.length, meanFrameMs, medianFrameMs, p95FrameMs, mode, semanticLabelCount: semantic.length };
        host.dataset.meanFrameMs = meanFrameMs.toFixed(3);
        host.dataset.medianFrameMs = medianFrameMs.toFixed(3);
        host.dataset.p95FrameMs = p95FrameMs.toFixed(3);
        host.dataset.performanceMode = mode;
      }
      if (!reducedMotion) frame = requestAnimationFrame(draw);
    };
    draw(performance.now());
    return () => { observer.disconnect(); cancelAnimationFrame(frame); };
  }, [fullWorld, hoveredId, model, reducedMotion, selectedPath, selectedPlacementId, semantic, semanticSet]);

  function hitTest(event: { clientX: number; clientY: number }) {
    const host = hostRef.current;
    if (!host) return null;
    const bounds = host.getBoundingClientRect();
    const camera = cameraRef.current;
    let best: { id: string; distance: number } | null = null;
    for (const id of semantic) {
      const point = project(model.placements[id], camera, viewportRef.current, bounds.width, bounds.height);
      const distance = Math.hypot(event.clientX - bounds.left - point.x, event.clientY - bounds.top - point.y);
      if (distance <= 24 && (!best || distance < best.distance)) best = { id, distance };
    }
    return best?.id ?? null;
  }

  function updateViewport(next: Viewport) {
    viewportRef.current = next;
    const host = hostRef.current;
    if (host) {
      host.dataset.viewportZoom = next.zoom.toFixed(3);
      host.dataset.viewportPanX = Math.round(next.panX).toString();
      host.dataset.viewportPanY = Math.round(next.panY).toString();
    }
  }

  return <div ref={hostRef} className="sm-pw-surface" role="application" aria-label="Persistent Employment influence world" data-world-id={model.worldId} data-graph-snapshot-id={model.graphSnapshotId} data-layout-version={model.layoutVersion} data-topology-fingerprint={model.topologyFingerprint} data-resident-placement-count={model.coverage.placementCount} data-resident-relationship-count={model.coverage.hierarchyRelationshipCount + model.coverage.syntheticInfluenceCount} data-semantic-node-count={semantic.length} data-lod-mode={fullWorld ? "FULL_WORLD_DENSITY" : selectedPlacementId ? "FOCUS" : "OVERVIEW"} data-selected-placement-id={selectedPlacementId ?? ""} data-viewport-zoom="1.000" data-viewport-pan-x="0" data-viewport-pan-y="0" onWheel={(event) => {
    const started = performance.now();
    event.preventDefault();
    const bounds = event.currentTarget.getBoundingClientRect();
    const current = viewportRef.current;
    const zoom = Math.max(.55, Math.min(3.25, current.zoom * Math.exp(-event.deltaY * .0014)));
    const ratio = zoom / current.zoom;
    const cursorX = event.clientX - bounds.left - bounds.width / 2;
    const cursorY = event.clientY - bounds.top - bounds.height / 2;
    updateViewport({ zoom, panX: cursorX - (cursorX - current.panX) * ratio, panY: cursorY - (cursorY - current.panY) * ratio });
    event.currentTarget.dataset.wheelHandlerMs = (performance.now() - started).toFixed(3);
  }} onPointerDown={(event) => {
    if (event.button !== 1) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const current = viewportRef.current;
    panRef.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, panX: current.panX, panY: current.panY, moved: false };
  }} onPointerMove={(event) => {
    const pan = panRef.current;
    if (pan?.pointerId === event.pointerId) {
      const dx = event.clientX - pan.startX; const dy = event.clientY - pan.startY;
      pan.moved ||= Math.hypot(dx, dy) > 3;
      suppressClickRef.current = pan.moved;
      updateViewport({ ...viewportRef.current, panX: pan.panX + dx, panY: pan.panY + dy });
      return;
    }
    const started = performance.now();
    setHoveredId(hitTest(event));
    event.currentTarget.dataset.hoverHitTestMs = (performance.now() - started).toFixed(3);
  }} onPointerUp={(event) => { if (panRef.current?.pointerId === event.pointerId) { event.currentTarget.releasePointerCapture(event.pointerId); panRef.current = null; } }} onPointerCancel={() => { panRef.current = null; }} onPointerLeave={() => { if (!panRef.current) setHoveredId(null); }} onMouseDown={(event) => { if (event.button === 1) event.preventDefault(); }} onAuxClick={(event) => { if (event.button === 1) event.preventDefault(); }} onDoubleClick={(event) => { if (!hitTest(event)) onReset(); }} onClick={(event) => {
    if (suppressClickRef.current) { suppressClickRef.current = false; return; }
    const id = hitTest(event); if (id) onSelect(id);
  }}>
    <canvas ref={canvasRef} role="img" aria-label="All 1,111 fixture placements remain resident; labels and controls disclose only the current exact-ten neighborhood." />
    <p className="sm-sr-only">Use the structured factor controls following the world to navigate without relying on position, color, hover, or motion.</p>
  </div>;
}

declare global {
  interface Window {
    __AUXSAYS_PERSISTENT_WORLD_METRICS__?: { placementCount: number; relationshipCount: number; meanFrameMs: number; medianFrameMs: number; p95FrameMs: number; mode: string; semanticLabelCount: number };
  }
}
