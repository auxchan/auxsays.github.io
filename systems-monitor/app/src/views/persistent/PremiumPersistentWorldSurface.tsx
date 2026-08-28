import { useEffect, useMemo, useRef, useState } from "react";
import { persistentWorldPlacementLabel, type PersistentWorldPlacement, type PersistentWorldReadModel } from "../../data/persistentWorldModel";
import type { PersistentWorldFactualBinding } from "../../data/persistentWorldFactualBindings";
import { persistentWorldCandidateSourceProfile } from "../../data/persistentWorldSourceCatalog";
import {
  PERSISTENT_GLINT_TRAIL, blendPremiumColor, compactPersistentValue, drawPremiumGlyph,
  createPersistentCameraTransition, easePremiumHover, factorGlyph, persistentGlintProgress, pointOnCubic, premiumCurveRoute,
  persistentFocusRotation, persistentPlacementAccent, premiumRadius, resolvePersistentLod, resolvePremiumLabels, traceCubic,
  samplePersistentCameraTransition, type LabelCandidate, type PersistentCameraPose, type Point
} from "./persistentWorldVisuals";

type Camera = PersistentCameraPose;
interface Viewport { zoom: number; panX: number; panY: number }
interface Props {
  model: PersistentWorldReadModel;
  factualBindings: Readonly<Record<string, PersistentWorldFactualBinding>>;
  selectedPlacementId: string | null;
  fullWorld: boolean;
  traceMode: boolean;
  reducedMotion: boolean;
  resetVersion: number;
  onSelect: (placementId: string) => void;
  onReset: () => void;
}

const OVERVIEW_SCALE = .205;
const AMBIENT_EDGE = "#315b67";

function hoverPurpose(model: PersistentWorldReadModel, placement: PersistentWorldPlacement) {
  if (placement.depth === 0) return "The outcome at the center of the employment system.";
  const parent = placement.parentPlacementId ? model.placements[placement.parentPlacementId] : undefined;
  const parentLabel = parent ? persistentWorldPlacementLabel(model, parent) : "the employment system";
  if (placement.depth === 1) return "Organizes ten related factors that can contextualize employment.";
  if (placement.depth === 2) return `Places this signal inside ${parentLabel} without claiming causality.`;
  return `Places this reviewed factor inside ${parentLabel} without claiming causality.`;
}

function hoverWhy(model: PersistentWorldReadModel, placement: PersistentWorldPlacement) {
  if (placement.depth === 0) return "It keeps the map anchored to the labor outcome people are trying to understand.";
  if (placement.depth === 1) return "It groups a major family of conditions that may help explain labor-market movement.";
  if (placement.depth === 2) return "It gives people one specific, independently inspectable part of the parent system.";
  return "It adds a separately inspectable economic concept while evidence and relationships remain governed independently.";
}

function targetCamera(model: PersistentWorldReadModel, selectedPlacementId: string | null, fullWorld: boolean, viewportWidth = 980, viewportHeight = 720): Camera {
  const selected = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
  if (!selected || fullWorld) return { x: 0, y: 0, scale: fullWorld ? .17 : OVERVIEW_SCALE, rotation: 0 };
  const rotation = persistentFocusRotation(selected.sector) + (selected.depth >= 2 ? (selected.order - 5.5) * .008 : 0);
  if (selected.depth === 1) {
    const neighborhood = [selected, ...(model.childrenByPlacement[selected.id] ?? []).map((id) => model.placements[id])];
    const rotated = neighborhood.map((placement) => ({ x: placement.x * Math.cos(rotation) - placement.y * Math.sin(rotation), y: placement.x * Math.sin(rotation) + placement.y * Math.cos(rotation) }));
    const xs = rotated.map((placement) => placement.x); const ys = rotated.map((placement) => placement.y);
    const minX = Math.min(...xs); const maxX = Math.max(...xs); const minY = Math.min(...ys); const maxY = Math.max(...ys);
    const worldWidth = Math.max(1, maxX - minX); const worldHeight = Math.max(1, maxY - minY);
    const scale = Math.max(.72, Math.min(.95, (viewportWidth - Math.min(380, viewportWidth * .42)) / worldWidth, (viewportHeight - Math.min(250, viewportHeight * .35)) / worldHeight));
    const centerX = (minX + maxX) / 2; const centerY = (minY + maxY) / 2;
    return { x: centerX * Math.cos(rotation) + centerY * Math.sin(rotation), y: -centerX * Math.sin(rotation) + centerY * Math.cos(rotation), scale, rotation };
  }
  return { x: selected.x, y: selected.y, scale: selected.depth === 2 ? 1.72 : 2.7, rotation };
}

function project(placement: PersistentWorldPlacement, camera: Camera, viewport: Viewport, width: number, height: number): Point {
  const dx = placement.x - camera.x; const dy = placement.y - camera.y; const cos = Math.cos(camera.rotation); const sin = Math.sin(camera.rotation);
  return { x: width / 2 + (dx * cos - dy * sin) * camera.scale * viewport.zoom + viewport.panX, y: height / 2 + (dx * sin + dy * cos) * camera.scale * viewport.zoom + viewport.panY };
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

function drawBackground(context: CanvasRenderingContext2D, width: number, height: number, parallax: Point, momentum: Point) {
  context.fillStyle = "#041219"; context.fillRect(0, 0, width, height);
  const gradient = context.createRadialGradient(width * .5 + parallax.x, height * .48 + parallax.y, 20, width * .5, height * .5, Math.max(width, height) * .72);
  gradient.addColorStop(0, "rgba(27,111,117,.31)"); gradient.addColorStop(.45, "rgba(7,39,48,.18)"); gradient.addColorStop(1, "rgba(1,9,14,0)");
  context.fillStyle = gradient; context.fillRect(0, 0, width, height);
  context.strokeStyle = "rgba(76,148,156,.055)"; context.lineWidth = 1; context.beginPath();
  const grid = 48;
  for (let x = ((parallax.x * .16) % grid) - grid; x < width + grid; x += grid) { context.moveTo(x, 0); context.lineTo(x, height); }
  for (let y = ((parallax.y * .16) % grid) - grid; y < height + grid; y += grid) { context.moveTo(0, y); context.lineTo(width, y); }
  context.stroke();
  context.save(); context.translate(width / 2 + parallax.x * .22, height / 2 + parallax.y * .22);
  for (const radius of [Math.min(width, height) * .19, Math.min(width, height) * .34, Math.min(width, height) * .49]) {
    context.strokeStyle = `rgba(93,201,195,${radius < 200 ? .08 : .045})`; context.lineWidth = 1; context.setLineDash([3, 11]);
    context.beginPath(); context.ellipse(0, 0, radius * 1.12, radius * .82, -.08, 0, Math.PI * 2); context.stroke();
  }
  context.setLineDash([]); context.restore();
  for (let index = 0; index < 54; index += 1) {
    const depth = .35 + (index % 5) * .19;
    const x = ((index * 193 + 71) % Math.max(1, Math.round(width))) + parallax.x * depth;
    const y = ((index * 97 + 43) % Math.max(1, Math.round(height))) + parallax.y * depth;
    context.strokeStyle = `rgba(111,228,208,${.055 + depth * .09})`; context.fillStyle = `rgba(111,228,208,${.08 + depth * .12})`; context.lineWidth = Math.max(.45, depth * .85);
    if (Math.hypot(momentum.x, momentum.y) > 1.5) { context.beginPath(); context.moveTo(x - momentum.x * depth * .48, y - momentum.y * depth * .48); context.lineTo(x, y); context.stroke(); }
    context.beginPath(); context.arc(x, y, index % 7 === 0 ? 1.1 + depth * .75 : .45 + depth * .35, 0, Math.PI * 2); context.fill();
  }
  const vignette = context.createRadialGradient(width / 2, height / 2, Math.min(width, height) * .3, width / 2, height / 2, Math.max(width, height) * .7);
  vignette.addColorStop(0, "rgba(0,0,0,0)"); vignette.addColorStop(1, "rgba(0,5,9,.58)"); context.fillStyle = vignette; context.fillRect(0, 0, width, height);
}

export function PremiumPersistentWorldSurface({ model, factualBindings, selectedPlacementId, fullWorld, traceMode, reducedMotion, resetVersion, onSelect, onReset }: Props) {
  const hostRef = useRef<HTMLDivElement>(null); const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraRef = useRef<Camera>(targetCamera(model, selectedPlacementId, fullWorld));
  const mountedAtRef = useRef(performance.now()); const viewportRef = useRef<Viewport>({ zoom: 1, panX: 0, panY: 0 });
  const panRef = useRef<{ pointerId: number; startX: number; startY: number; panX: number; panY: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false); const hoveredRef = useRef<string | null>(null); const hoverVisualsRef = useRef(new Map<string, number>());
  const pointerRef = useRef<Point>({ x: 0, y: 0 }); const invalidateRef = useRef<() => void>(() => undefined);
  const semanticHistoryRef = useRef<readonly string[]>([]); const cameraMomentumRef = useRef<Point>({ x: 0, y: 0 });
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const hoveredPlacement = hoveredId ? model.placements[hoveredId] : undefined;
  const hoveredFactor = hoveredPlacement ? model.factors[hoveredPlacement.canonicalFactorId] : undefined;
  const hoveredBinding = hoveredId ? factualBindings[hoveredId] : undefined;
  const hoveredSource = hoveredPlacement && hoveredPlacement.depth >= 2 && hoveredFactor ? persistentWorldCandidateSourceProfile(persistentWorldPlacementLabel(model, hoveredPlacement)) ?? persistentWorldCandidateSourceProfile(hoveredFactor.label) : undefined;
  const hoveredValue = compactPersistentValue(hoveredBinding?.status === "CONNECTED" ? hoveredBinding.displayValue : undefined);
  const semantic = useMemo(() => semanticIds(model, fullWorld ? null : selectedPlacementId), [fullWorld, model, selectedPlacementId]); const semanticSet = useMemo(() => new Set(semantic), [semantic]);
  const selectedPath = useMemo(() => {
    const ids = new Set<string>(); let current = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
    while (current) { ids.add(current.id); current = current.parentPlacementId ? model.placements[current.parentPlacementId] : undefined; } return ids;
  }, [model, selectedPlacementId]);

  useEffect(() => { hoveredRef.current = hoveredId; invalidateRef.current(); }, [hoveredId]);
  useEffect(() => {
    viewportRef.current = { zoom: 1, panX: 0, panY: 0 }; const host = hostRef.current;
    if (host) { host.dataset.viewportZoom = "1.000"; host.dataset.viewportPanX = "0"; host.dataset.viewportPanY = "0"; } invalidateRef.current();
  }, [fullWorld, resetVersion, selectedPlacementId]);

  useEffect(() => {
    const host = hostRef.current; const canvas = canvasRef.current; const context = canvas?.getContext("2d", { alpha: false });
    if (!host || !canvas || !context) return;
    let frame = 0; let last = performance.now(); let frameCount = 0; let accumulated = 0; const frameSamples: number[] = [];
    const initialBounds = host.getBoundingClientRect();
    let destination = targetCamera(model, selectedPlacementId, fullWorld, initialBounds.width, initialBounds.height); const cameraStarted = performance.now(); let cameraSettled = false;
    let cameraTransition = createPersistentCameraTransition(cameraRef.current, destination, cameraStarted, selectedPlacementId ?? (fullWorld ? "full-world" : "overview"));
    const previousSemantic = semanticHistoryRef.current.length ? semanticHistoryRef.current : semantic; semanticHistoryRef.current = semantic;
    const previousSemanticSet = new Set(previousSemantic); const transitionSemanticSet = new Set([...previousSemantic, ...semantic]);
    delete host.dataset.cameraSettleMs; if (reducedMotion) cameraRef.current = destination;
    const resize = () => {
      const bounds = host.getBoundingClientRect(); const ratio = Math.min(2, window.devicePixelRatio || 1); destination = targetCamera(model, selectedPlacementId, fullWorld, bounds.width, bounds.height); cameraTransition.to = destination;
      canvas.width = Math.max(1, Math.round(bounds.width * ratio)); canvas.height = Math.max(1, Math.round(bounds.height * ratio)); canvas.style.width = `${bounds.width}px`; canvas.style.height = `${bounds.height}px`; context.setTransform(ratio, 0, 0, ratio, 0, 0);
      if (reducedMotion) invalidateRef.current();
    };
    resize(); const observer = new ResizeObserver(resize); observer.observe(host);
    const placements = Object.values(model.placements);
    const hierarchy = Object.values(model.relationships).filter((edge) => edge.relationshipClass === "HIERARCHY_TETHER");
    const influence = Object.values(model.relationships).filter((edge) => edge.relationshipClass === "SYNTHETIC_INFLUENCE");
    const highlightedEdges = hierarchy.filter((edge) => transitionSemanticSet.has(edge.fromPlacementId) && transitionSemanticSet.has(edge.toPlacementId));

    const draw = (now: number) => {
      const started = performance.now(); const elapsedMs = Math.min(48, Math.max(0, now - last)); const bounds = host.getBoundingClientRect(); const width = bounds.width; const height = bounds.height; const camera = cameraRef.current; const viewport = viewportRef.current;
      const priorCamera = { ...camera }; const transitionSample = reducedMotion ? { progress: 1, pose: destination } : samplePersistentCameraTransition(cameraTransition, now); Object.assign(camera, transitionSample.pose);
      const targetMomentum = reducedMotion ? { x: 0, y: 0 } : { x: Math.max(-32, Math.min(32, (priorCamera.x - camera.x) * camera.scale * 1.4)), y: Math.max(-32, Math.min(32, (priorCamera.y - camera.y) * camera.scale * 1.4)) };
      cameraMomentumRef.current.x += (targetMomentum.x - cameraMomentumRef.current.x) * .18; cameraMomentumRef.current.y += (targetMomentum.y - cameraMomentumRef.current.y) * .18;
      host.dataset.cameraX = camera.x.toFixed(3); host.dataset.cameraY = camera.y.toFixed(3); host.dataset.cameraScale = camera.scale.toFixed(3); host.dataset.cameraRotationDegrees = (camera.rotation * 180 / Math.PI).toFixed(1);
      host.dataset.cameraTransitionProgress = transitionSample.progress.toFixed(3); host.dataset.cameraTransitionPhase = reducedMotion ? "REDUCED_MOTION" : transitionSample.progress < .28 ? "DOLLY_OUT" : transitionSample.progress < .82 ? "ORBITAL_TRAVEL" : transitionSample.progress < 1 ? "DOLLY_IN" : "SETTLED";
      if (!cameraSettled && transitionSample.progress >= 1) { cameraSettled = true; host.dataset.cameraSettleMs = (performance.now() - cameraStarted).toFixed(3); }
      last = now;
      const parallax = reducedMotion ? { x: 0, y: 0 } : { x: (pointerRef.current.x - width / 2) * .016 + cameraMomentumRef.current.x, y: (pointerRef.current.y - height / 2) * .016 + cameraMomentumRef.current.y };
      drawBackground(context, width, height, parallax, cameraMomentumRef.current);

      context.lineWidth = .58; context.strokeStyle = "rgba(93,176,176,.075)"; context.beginPath();
      for (const edge of hierarchy) { const from = project(model.placements[edge.fromPlacementId], camera, viewport, width, height); const to = project(model.placements[edge.toPlacementId], camera, viewport, width, height); const route = premiumCurveRoute(edge.id, from, to, true); context.moveTo(route.start.x, route.start.y); context.bezierCurveTo(route.control1.x, route.control1.y, route.control2.x, route.control2.y, route.end.x, route.end.y); }
      context.stroke();
      if (fullWorld) { context.strokeStyle = "rgba(166,132,238,.027)"; context.lineWidth = .38; context.beginPath(); for (const edge of influence) { const from = project(model.placements[edge.fromPlacementId], camera, viewport, width, height); const to = project(model.placements[edge.toPlacementId], camera, viewport, width, height); context.moveTo(from.x, from.y); context.lineTo(to.x, to.y); } context.stroke(); }

      context.lineCap = "round"; const currentHovered = hoveredRef.current;
      for (const edge of highlightedEdges) {
        const fromPlacement = model.placements[edge.fromPlacementId]; const toPlacement = model.placements[edge.toPlacementId]; const from = project(fromPlacement, camera, viewport, width, height); const to = project(toPlacement, camera, viewport, width, height); const route = premiumCurveRoute(edge.id, from, to);
        const currentEdge = semanticSet.has(edge.fromPlacementId) && semanticSet.has(edge.toPlacementId); const previousEdge = previousSemanticSet.has(edge.fromPlacementId) && previousSemanticSet.has(edge.toPlacementId); const transitionAlpha = Math.min(1, (currentEdge ? transitionSample.progress : 0) + (previousEdge ? 1 - transitionSample.progress : 0));
        const accent = persistentPlacementAccent(toPlacement); const incident = Boolean(currentHovered && (edge.fromPlacementId === currentHovered || edge.toPlacementId === currentHovered)); const traceEdge = selectedPath.has(edge.fromPlacementId) && selectedPath.has(edge.toPlacementId);
        const hoverAmount = easePremiumHover(hoverVisualsRef.current.get(edge.id) ?? 0, incident ? 1 : 0, elapsedMs, reducedMotion); hoverVisualsRef.current.set(edge.id, hoverAmount);
        const focused = selectedPlacementId ? model.placements[selectedPlacementId] : undefined; const denseFanEdge = Boolean(focused && focused.depth < 3 && (edge.fromPlacementId === focused.id || edge.toPlacementId === focused.id)); const railScale = denseFanEdge ? .64 : 1;
        const traceAlpha = (traceMode ? traceEdge ? 1 : .13 : 1) * transitionAlpha; const color = blendPremiumColor(AMBIENT_EDGE, accent, (denseFanEdge ? .76 : .52) + hoverAmount * (denseFanEdge ? .24 : .48), (currentHovered && !incident ? .24 : .9) * traceAlpha);
        context.save(); context.shadowColor = accent; context.shadowBlur = (denseFanEdge ? 5 + hoverAmount * 8 : 8 + hoverAmount * 10) * traceAlpha; context.strokeStyle = blendPremiumColor(AMBIENT_EDGE, accent, .45 + hoverAmount * .55, (.18 + hoverAmount * .18) * traceAlpha); context.lineWidth = (8 + hoverAmount * 2) * railScale; traceCubic(context, route); context.stroke();
        context.shadowBlur = 0; context.strokeStyle = color; context.lineWidth = (3.2 + hoverAmount * 1.2) * railScale; traceCubic(context, route); context.stroke(); context.strokeStyle = blendPremiumColor("#b8e1df", accent, .42 + hoverAmount * .58, .88); context.lineWidth = denseFanEdge ? .85 : 1.05; traceCubic(context, route); context.stroke(); context.restore();
        if (!reducedMotion && (!traceMode || traceEdge)) { const progress = persistentGlintProgress(now, edge.id); const trailStart = pointOnCubic(route, Math.max(0, progress - PERSISTENT_GLINT_TRAIL)); const trailEnd = pointOnCubic(route, progress); const gradient = context.createLinearGradient(trailStart.x, trailStart.y, trailEnd.x, trailEnd.y); gradient.addColorStop(0, blendPremiumColor(accent, accent, 1, 0)); gradient.addColorStop(1, blendPremiumColor("#ffffff", accent, .26, .98)); context.save(); context.strokeStyle = gradient; context.lineWidth = 3.1; context.shadowColor = accent; context.shadowBlur = 12; context.beginPath(); context.moveTo(trailStart.x, trailStart.y); context.lineTo(trailEnd.x, trailEnd.y); context.stroke(); context.restore(); }
      }

      const labelCandidates: LabelCandidate[] = []; const focusPlacement = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
      for (const placement of placements) {
        const point = project(placement, camera, viewport, width, height); if (point.x < -42 || point.y < -42 || point.x > width + 42 || point.y > height + 42) continue;
        const factorLabel = persistentWorldPlacementLabel(model, placement); const factualBinding = factualBindings[placement.id];
        const semanticAlpha = Math.min(1, (semanticSet.has(placement.id) ? transitionSample.progress : 0) + (previousSemanticSet.has(placement.id) ? 1 - transitionSample.progress : 0)); const emphasized = semanticAlpha > .015 || selectedPath.has(placement.id); const sectorActive = isInSelectedSector(model, placement, selectedPlacementId); const effectiveScale = camera.scale * viewport.zoom; const lod = resolvePersistentLod(placement.depth, effectiveScale, emphasized); const radius = premiumRadius(placement, lod);
        const accent = persistentPlacementAccent(placement); const isHovered = placement.id === currentHovered; const isSelected = placement.id === selectedPlacementId;
        context.globalAlpha = emphasized ? Math.max(.08, semanticAlpha, selectedPath.has(placement.id) ? .7 : 0) : sectorActive ? (placement.depth === 3 ? .36 : .58) : (fullWorld ? .24 : .1);
        if (lod === 0) { context.fillStyle = accent; context.beginPath(); context.arc(point.x, point.y, Math.max(1, radius), 0, Math.PI * 2); context.fill(); }
        else {
          context.save(); context.shadowColor = accent; context.shadowBlur = isSelected ? 25 : isHovered ? 18 : emphasized ? 9 : 0; context.fillStyle = placement.depth === 0 ? "rgba(35,18,42,.96)" : "rgba(5,27,35,.94)"; context.strokeStyle = blendPremiumColor(accent, "#ffffff", isHovered ? .25 : .05, .9); context.lineWidth = placement.depth === 0 ? 3.2 : 2;
          context.beginPath(); context.arc(point.x, point.y, radius + (isHovered ? 2 : 0), 0, Math.PI * 2); context.fill(); context.stroke(); context.shadowBlur = 0; context.strokeStyle = blendPremiumColor(accent, accent, 1, .23); context.lineWidth = 1; context.beginPath(); context.ellipse(point.x, point.y, radius * 1.75, radius * 1.18, placement.sector * .18, 0, Math.PI * 2); context.stroke(); if (lod >= 2) drawPremiumGlyph(context, factorGlyph(placement, factorLabel), point.x, point.y, radius * (placement.depth === 3 ? .85 : .62), accent);
          if (factualBinding && lod >= 2) {
            const badgeX = point.x + radius * .72; const badgeY = point.y - radius * .72;
            context.fillStyle = factualBinding.status === "CONNECTED" ? "#55e7bc" : factualBinding.status === "SOURCE_IDENTIFIED" ? "#f0bd64" : "rgba(126,161,170,.5)";
            context.strokeStyle = "rgba(2,18,24,.96)"; context.lineWidth = 2.2; context.beginPath(); context.arc(badgeX, badgeY, factualBinding.status === "CONNECTED" ? 4.2 : 3.1, 0, Math.PI * 2); context.fill(); context.stroke();
          }
          context.restore();
        }
        const focusHasChildren = Boolean(focusPlacement && (model.childrenByPlacement[focusPlacement.id]?.length ?? 0) > 0);
        const suppressFocusAncestorLabel = Boolean(focusHasChildren && placement.id === focusPlacement?.parentPlacementId);
        if (emphasized && lod >= 1 && !suppressFocusAncestorLabel) {
          const compactValue = compactPersistentValue(factualBinding?.status === "CONNECTED" ? factualBinding.displayValue : undefined); const label = compactValue ? `${factorLabel} · ${compactValue}` : factorLabel; const fontSize = placement.depth === 0 ? 13 : placement.depth === 1 ? 12 : 11; context.font = `${placement.depth < 2 ? 750 : 650} ${fontSize}px Inter, system-ui, sans-serif`; const textWidth = Math.min(226, context.measureText(label).width + 18);
          let labelX = point.x; let labelY = point.y + radius + 17; let anchorX: number | undefined; let anchorY: number | undefined; let labelSide: "left" | "right" | "top" | "bottom" | undefined;
          const parent = placement.parentPlacementId ? model.placements[placement.parentPlacementId] : undefined;
          if (parent && placement.depth >= 2) {
            const parentPoint = project(parent, camera, viewport, width, height); const dx = point.x - parentPoint.x; const dy = point.y - parentPoint.y; const distance = Math.max(1, Math.hypot(dx, dy)); const tangent = placement.order % 2 ? -6 : 6;
            labelX = point.x + (dx / distance) * (radius + 15) + (-dy / distance) * tangent;
            labelY = point.y + (dy / distance) * (radius + 15) + (dx / distance) * tangent;
            const focused = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
            const focusedExactTenChild = Boolean(focused && focused.depth < 3 && placement.parentPlacementId === focused.id && placement.depth === focused.depth + 1);
            if (focusedExactTenChild) {
              const radialX = dx / distance; const radialY = dy / distance; const horizontal = Math.abs(radialX) >= .18;
              labelSide = horizontal ? radialX < 0 ? "left" : "right" : radialY < 0 ? "top" : "bottom";
              if (labelSide === "left" || labelSide === "right") {
                const direction = labelSide === "left" ? -1 : 1;
                labelX = labelSide === "left" ? 14 + textWidth / 2 : width - 14 - textWidth / 2; labelY = point.y;
                anchorX = point.x + direction * (radius + 3); anchorY = point.y;
              } else {
                const direction = labelSide === "top" ? -1 : 1;
                labelX = point.x; labelY = labelSide === "top" ? 25 : height - 25;
                anchorX = point.x; anchorY = point.y + direction * (radius + 3);
              }
            }
          }
          const focusedExactTenChild = Boolean(focusPlacement && focusPlacement.depth < 3 && placement.parentPlacementId === focusPlacement.id && placement.depth === focusPlacement.depth + 1);
          labelCandidates.push({ id: placement.id, text: label, x: labelX, y: labelY, priority: placement.depth === 0 ? 100 : isSelected ? 90 : placement.depth === 1 ? 70 : placement.depth === 2 ? 50 : 20, width: textWidth, height: 22, accent, anchorX, anchorY, required: focusedExactTenChild, side: labelSide, opacity: Math.max(.08, semanticAlpha, selectedPath.has(placement.id) ? .7 : 0) });
        }
        context.globalAlpha = 1;
      }
      const labels = resolvePremiumLabels(labelCandidates, width, height);
      for (const label of labels) { context.save(); context.globalAlpha = label.opacity ?? 1; if (label.anchorX !== undefined && label.anchorY !== undefined) { const targetX = label.side === "left" ? label.left + label.width : label.side === "right" ? label.left : label.x; const targetY = label.side === "top" ? label.top + label.height : label.side === "bottom" ? label.top : label.y; context.strokeStyle = blendPremiumColor(label.accent, label.accent, 1, .3); context.lineWidth = .8; context.beginPath(); context.moveTo(label.anchorX, label.anchorY); context.lineTo(targetX, targetY); context.stroke(); } context.fillStyle = "rgba(2,16,22,.9)"; context.strokeStyle = blendPremiumColor(label.accent, label.accent, 1, .3); context.lineWidth = 1; context.beginPath(); context.roundRect(label.left, label.top, label.width, label.height, 6); context.fill(); context.stroke(); context.fillStyle = label.id === selectedPlacementId ? "#f4fffc" : blendPremiumColor("#d9eeeb", label.accent, .28, 1); context.font = `${label.priority >= 70 ? 750 : 650} ${label.priority >= 70 ? 12 : 11}px Inter, system-ui, sans-serif`; context.textAlign = "center"; context.textBaseline = "middle"; context.fillText(label.text, label.x, label.y, label.width - 12); context.restore(); }

      const elapsed = performance.now() - started;
      if (frameCount === 0) host.dataset.firstDrawMs = (performance.now() - mountedAtRef.current).toFixed(3);
      frameCount += 1; accumulated += elapsed; frameSamples.push(elapsed);
      if (frameCount === 30 || (reducedMotion && frameCount === 1)) {
        const ordered = [...frameSamples].sort((a, b) => a - b); const meanFrameMs = accumulated / frameCount; const medianFrameMs = ordered[Math.floor(ordered.length / 2)]; const p95FrameMs = ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * .95) - 1)]; const mode = fullWorld ? "FULL_WORLD_LOD" : selectedPlacementId ? "FOCUS_LOD" : "OVERVIEW_LOD";
        window.__AUXSAYS_PERSISTENT_WORLD_METRICS__ = { placementCount: placements.length, relationshipCount: hierarchy.length + influence.length, meanFrameMs, medianFrameMs, p95FrameMs, mode, semanticLabelCount: labels.length };
        host.dataset.meanFrameMs = meanFrameMs.toFixed(3); host.dataset.medianFrameMs = medianFrameMs.toFixed(3); host.dataset.p95FrameMs = p95FrameMs.toFixed(3); host.dataset.performanceMode = mode; host.dataset.semanticLabelCount = labels.length.toString();
      }
      if (!reducedMotion) frame = requestAnimationFrame(draw);
    };
    invalidateRef.current = () => { if (reducedMotion) draw(performance.now()); }; draw(performance.now());
    return () => { observer.disconnect(); cancelAnimationFrame(frame); invalidateRef.current = () => undefined; };
  }, [factualBindings, fullWorld, model, reducedMotion, selectedPath, selectedPlacementId, semantic, semanticSet, traceMode]);

  function hitTest(event: { clientX: number; clientY: number }) {
    const host = hostRef.current; if (!host) return null; const bounds = host.getBoundingClientRect(); const camera = cameraRef.current; let best: { id: string; distance: number } | null = null;
    for (const id of semantic) { const placement = model.placements[id]; const point = project(placement, camera, viewportRef.current, bounds.width, bounds.height); const lod = resolvePersistentLod(placement.depth, camera.scale * viewportRef.current.zoom, true); const radius = Math.max(24, premiumRadius(placement, lod) + 8); const distance = Math.hypot(event.clientX - bounds.left - point.x, event.clientY - bounds.top - point.y); if (distance <= radius && (!best || distance < best.distance)) best = { id, distance }; }
    return best?.id ?? null;
  }
  function updateViewport(next: Viewport) { viewportRef.current = next; const host = hostRef.current; if (host) { host.dataset.viewportZoom = next.zoom.toFixed(3); host.dataset.viewportPanX = Math.round(next.panX).toString(); host.dataset.viewportPanY = Math.round(next.panY).toString(); } invalidateRef.current(); }

  return <div ref={hostRef} className="sm-pw-surface sm-pw-surface--premium" role="application" aria-label="Persistent Employment influence world" data-world-id={model.worldId} data-graph-snapshot-id={model.graphSnapshotId} data-layout-version={model.layoutVersion} data-topology-fingerprint={model.topologyFingerprint} data-resident-placement-count={model.coverage.placementCount} data-resident-relationship-count={model.coverage.hierarchyRelationshipCount + model.coverage.syntheticInfluenceCount} data-semantic-node-count={semantic.length} data-factual-binding-count={Object.values(factualBindings).filter((binding) => binding.status === "CONNECTED").length} data-lod-mode={fullWorld ? "FULL_WORLD_DENSITY" : selectedPlacementId ? "FOCUS" : "OVERVIEW"} data-trace-mode={traceMode} data-selected-placement-id={selectedPlacementId ?? ""} data-viewport-zoom="1.000" data-viewport-pan-x="0" data-viewport-pan-y="0" data-glint-period-ms="2500" data-glint-trail="0.085" data-hovered-placement-id={hoveredId ?? ""} onWheel={(event) => {
    const started = performance.now(); event.preventDefault(); const bounds = event.currentTarget.getBoundingClientRect(); const current = viewportRef.current; const zoom = Math.max(.55, Math.min(3.25, current.zoom * Math.exp(-event.deltaY * .0014))); const ratio = zoom / current.zoom; const cursorX = event.clientX - bounds.left - bounds.width / 2; const cursorY = event.clientY - bounds.top - bounds.height / 2; updateViewport({ zoom, panX: cursorX - (cursorX - current.panX) * ratio, panY: cursorY - (cursorY - current.panY) * ratio }); event.currentTarget.dataset.wheelHandlerMs = (performance.now() - started).toFixed(3);
  }} onPointerDown={(event) => { if (event.button !== 1) return; event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); const current = viewportRef.current; panRef.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, panX: current.panX, panY: current.panY, moved: false }; }} onPointerMove={(event) => {
    const bounds = event.currentTarget.getBoundingClientRect(); pointerRef.current = { x: event.clientX - bounds.left, y: event.clientY - bounds.top }; const pan = panRef.current;
    if (pan?.pointerId === event.pointerId) { const dx = event.clientX - pan.startX; const dy = event.clientY - pan.startY; pan.moved ||= Math.hypot(dx, dy) > 3; suppressClickRef.current = pan.moved; updateViewport({ ...viewportRef.current, panX: pan.panX + dx, panY: pan.panY + dy }); return; }
    const started = performance.now(); const hit = hitTest(event); setHoveredId(hit); if (hit) { event.currentTarget.style.setProperty("--pw-hover-x", `${Math.max(14, Math.min(bounds.width - 304, pointerRef.current.x + 18))}px`); event.currentTarget.style.setProperty("--pw-hover-y", `${Math.max(14, Math.min(bounds.height - 246, pointerRef.current.y + 18))}px`); } event.currentTarget.dataset.hoverHitTestMs = (performance.now() - started).toFixed(3); invalidateRef.current();
  }} onPointerUp={(event) => { if (panRef.current?.pointerId === event.pointerId) { event.currentTarget.releasePointerCapture(event.pointerId); panRef.current = null; } }} onPointerCancel={() => { panRef.current = null; }} onPointerLeave={() => { if (!panRef.current) setHoveredId(null); }} onMouseDown={(event) => { if (event.button === 1) event.preventDefault(); }} onAuxClick={(event) => { if (event.button === 1) event.preventDefault(); }} onDoubleClick={(event) => { if (!hitTest(event)) onReset(); }} onClick={(event) => { if (suppressClickRef.current) { suppressClickRef.current = false; return; } const id = hitTest(event); if (id) onSelect(id); }}>
    <canvas ref={canvasRef} role="img" aria-label="All 1,111 fixture placements remain resident; premium visual detail and labels are bounded to the current exact-ten neighborhood." />
    <aside className="sm-pw-hover-card" role="tooltip" aria-hidden={!hoveredPlacement} data-visible={Boolean(hoveredPlacement)}>
      {hoveredPlacement && hoveredFactor && <><header><span>{hoveredPlacement.depth === 1 ? "System" : hoveredPlacement.depth === 2 ? "Factor" : hoveredPlacement.depth === 0 ? "Outcome" : "Supporting factor"}</span><strong>{persistentWorldPlacementLabel(model, hoveredPlacement)}</strong>{hoveredValue && <b>{hoveredValue}</b>}</header><dl><div><dt>Purpose</dt><dd>{hoverPurpose(model, hoveredPlacement)}</dd></div><div><dt>Tracks</dt><dd>{hoveredSource?.summary ?? hoveredFactor.definition}</dd></div><div><dt>Why</dt><dd>{hoverWhy(model, hoveredPlacement)}</dd></div></dl><small>{hoveredBinding?.status === "CONNECTED" ? `${hoveredBinding.validTime} · ${hoveredBinding.provider} · click for evidence` : hoveredBinding?.status === "SOURCE_ENABLED_PENDING_ACCEPTANCE" ? "Collector enabled · acceptance pending" : hoveredBinding?.status === "BLOCKED" ? "Official path identified · retrieval blocked" : "Click for full details"}</small></>}
    </aside>
    <p className="sm-sr-only">Use the structured factor controls following the world to navigate without relying on position, color, hover, or motion.</p>
  </div>;
}

declare global { interface Window { __AUXSAYS_PERSISTENT_WORLD_METRICS__?: { placementCount: number; relationshipCount: number; meanFrameMs: number; medianFrameMs: number; p95FrameMs: number; mode: string; semanticLabelCount: number }; } }
