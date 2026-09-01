import { useEffect, useMemo, useRef, useState } from "react";
import { persistentWorldPlacementLabel, type PersistentWorldPlacement, type PersistentWorldReadModel } from "../../data/persistentWorldModel";
import type { PersistentWorldFactualBinding } from "../../data/persistentWorldFactualBindings";
import { persistentWorldCandidateSourceProfile } from "../../data/persistentWorldSourceCatalog";
import {
  PERSISTENT_GLINT_TRAIL, blendPremiumColor, compactPersistentValue, drawPremiumGlyph,
  createPersistentCameraTransition, easePremiumHover, factorGlyph, persistentAmbientEdges, persistentGlintProgress, pointOnCubic, premiumCurveRoute,
  persistentFocusRotation, persistentPlacementAccent, premiumRadius, resolvePersistentLod, resolvePremiumLabels, traceCubic,
  samplePersistentCameraTransition, type LabelCandidate, type PersistentCameraPose, type PersistentCameraTransition, type PersistentCameraVelocity, type Point
} from "./persistentWorldVisuals";
import { createPersistentProjector, createPersistentWorldSpatialLayout, type PersistentProjectedPlacement } from "./persistentWorldSpatialLayout";

type Camera = PersistentCameraPose;
export type PersistentWorldViewMode = "TOP_DOWN" | "CINEMATIC_2_5D";
interface Viewport { zoom: number; panX: number; panY: number }
interface OrbitDrag { pointerId: number; startX: number; startY: number; lastX: number; lastAt: number; startAngle: number; moved: boolean }
interface Props {
  model: PersistentWorldReadModel;
  factualBindings: Readonly<Record<string, PersistentWorldFactualBinding>>;
  selectedPlacementId: string | null;
  fullWorld: boolean;
  viewMode: PersistentWorldViewMode;
  traceMode: boolean;
  reducedMotion: boolean;
  resetVersion: number;
  routePulseVersion: number;
  publicBeta?: boolean;
  onSelect: (placementId: string) => void;
  onNavigateParent: () => void;
  onReset: () => void;
}

export type PersistentWorldDoubleClickAction = "UP_ONE_LEVEL" | "RESET" | "NONE";

export function persistentWorldDoubleClickAction(hitPlacementId: string | null, parentPlacementId: string | null): PersistentWorldDoubleClickAction {
  if (!hitPlacementId) return "RESET";
  if (parentPlacementId && hitPlacementId === parentPlacementId) return "UP_ONE_LEVEL";
  return "NONE";
}

export function persistentWorldPublicPlacementVisible(model: PersistentWorldReadModel, placementId: string) {
  return Boolean(model.placements[placementId]);
}

export function persistentWorldPublicRelationshipVisible(model: PersistentWorldReadModel, relationship: PersistentWorldReadModel["relationships"][string]) {
  return relationship.relationshipClass === "HIERARCHY_TETHER"
    && persistentWorldPublicPlacementVisible(model, relationship.fromPlacementId)
    && persistentWorldPublicPlacementVisible(model, relationship.toPlacementId);
}

/** Keeps rapid camera retargets continuous while bounding carried momentum and lateral travel. */
export function polishPersistentCameraTransition(transition: PersistentCameraTransition): PersistentCameraTransition {
  const planarDistance = Math.hypot(transition.to.x - transition.from.x, transition.to.y - transition.from.y);
  const averagePlanarSpeed = planarDistance / Math.max(1, transition.durationMs);
  const maxPlanarCarry = Math.min(.2, Math.max(.018, averagePlanarSpeed * .58));
  const carriedPlanarSpeed = Math.hypot(transition.velocity.x, transition.velocity.y);
  const carryScale = carriedPlanarSpeed > maxPlanarCarry ? maxPlanarCarry / carriedPlanarSpeed : 1;
  const zDistance = Math.abs(transition.to.z - transition.from.z);
  const logScaleDistance = Math.abs(Math.log(Math.max(.001, transition.to.scale) / Math.max(.001, transition.from.scale)));
  const maxZCarry = Math.min(.11, Math.max(.008, zDistance / Math.max(1, transition.durationMs) * .62));
  const maxScaleCarry = Math.min(.00065, Math.max(.00008, logScaleDistance / Math.max(1, transition.durationMs) * .52));
  return {
    ...transition,
    durationMs: Math.max(740, Math.min(1020, 740 + planarDistance * .11 + logScaleDistance * 135)),
    arc: Math.sign(transition.arc || 1) * Math.min(26, planarDistance * .045),
    orbit: Math.sign(transition.orbit || 1) * Math.min(.016, planarDistance / 24000),
    velocity: {
      x: transition.velocity.x * carryScale,
      y: transition.velocity.y * carryScale,
      z: Math.max(-maxZCarry, Math.min(maxZCarry, transition.velocity.z)),
      logScale: Math.max(-maxScaleCarry, Math.min(maxScaleCarry, transition.velocity.logScale)),
      rotation: Math.max(-.00055, Math.min(.00055, transition.velocity.rotation)),
      pitch: Math.max(-.00022, Math.min(.00022, transition.velocity.pitch)),
      yaw: Math.max(-.00022, Math.min(.00022, transition.velocity.yaw))
    }
  };
}

export function persistentWorldGraphNodeLabel(model: PersistentWorldReadModel, placement: PersistentWorldPlacement) {
  return persistentWorldPlacementLabel(model, placement);
}

export function persistentWorldEdgeTransitionAlpha(currentEdge: boolean, previousEdge: boolean, progress: number) {
  return Math.min(1, (currentEdge ? progress * 1.8 : 0) + (previousEdge ? Math.max(0, 1 - progress * 2.5) : 0));
}

const MAX_ORBIT_VELOCITY = .00115;

function normalizeOrbitAngle(angle: number) {
  return Math.atan2(Math.sin(angle), Math.cos(angle));
}

/** Horizontal blank-space dragging rotates the presentation only; the cinematic view is deliberately less sensitive. */
export function persistentWorldOrbitAngle(startAngle: number, horizontalPixels: number, viewMode: PersistentWorldViewMode, pitch = 0) {
  const cinematicCompensation = viewMode === "CINEMATIC_2_5D" ? Math.max(.62, Math.min(.76, Math.cos(Math.abs(pitch)) * .9)) : 1;
  return normalizeOrbitAngle(startAngle + horizontalPixels * .00215 * cinematicCompensation);
}

export function persistentWorldOrbitVelocity(horizontalPixels: number, elapsedMs: number, viewMode: PersistentWorldViewMode, pitch = 0) {
  const angle = persistentWorldOrbitAngle(0, horizontalPixels, viewMode, pitch);
  return Math.max(-MAX_ORBIT_VELOCITY, Math.min(MAX_ORBIT_VELOCITY, angle / Math.max(8, elapsedMs)));
}

export function decayPersistentWorldOrbitVelocity(velocity: number, elapsedMs: number) {
  const decayed = velocity * Math.exp(-Math.max(0, elapsedMs) / 430);
  return Math.abs(decayed) < .000008 ? 0 : decayed;
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

export function persistentWorldTargetCamera(model: PersistentWorldReadModel, selectedPlacementId: string | null, fullWorld: boolean, viewMode: PersistentWorldViewMode, viewportWidth = 980, viewportHeight = 720, spatial = createPersistentWorldSpatialLayout(model)): Camera {
  const selected = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
  const cinematic = viewMode === "CINEMATIC_2_5D";
  if (!selected || fullWorld) return { x: 0, y: 0, z: 0, scale: fullWorld ? .17 : OVERVIEW_SCALE, rotation: 0, pitch: cinematic ? fullWorld ? -.18 : -.14 : 0, yaw: cinematic ? fullWorld ? .06 : -.04 : 0 };
  const rotation = persistentFocusRotation(selected.sector) + (selected.depth >= 2 ? (selected.order - 5.5) * .008 : 0);
  const z = cinematic ? spatial.zByPlacementId[selected.id] ?? 0 : 0;
  const pitch = cinematic ? selected.depth === 1 ? .52 : selected.depth === 2 ? .68 : .78 : 0;
  const yaw = cinematic ? Math.max(-.42, Math.min(.42, (selected.sector - 4.5) * .056 + (selected.depth >= 2 ? (selected.order - 5.5) * .026 : 0))) : 0;
  if (selected.depth === 1) {
    const neighborhood = [selected, ...(model.childrenByPlacement[selected.id] ?? []).map((id) => model.placements[id])];
    const rotated = neighborhood.map((placement) => ({ x: placement.x * Math.cos(rotation) - placement.y * Math.sin(rotation), y: placement.x * Math.sin(rotation) + placement.y * Math.cos(rotation) }));
    const xs = rotated.map((placement) => placement.x); const ys = rotated.map((placement) => placement.y);
    const minX = Math.min(...xs); const maxX = Math.max(...xs); const minY = Math.min(...ys); const maxY = Math.max(...ys);
    const worldWidth = Math.max(1, maxX - minX); const worldHeight = Math.max(1, maxY - minY);
    const scale = Math.max(.72, Math.min(.95, (viewportWidth - Math.min(380, viewportWidth * .42)) / worldWidth, (viewportHeight - Math.min(250, viewportHeight * .35)) / worldHeight));
    const centerX = (minX + maxX) / 2; const centerY = (minY + maxY) / 2;
    return { x: centerX * Math.cos(rotation) + centerY * Math.sin(rotation), y: -centerX * Math.sin(rotation) + centerY * Math.cos(rotation), z, scale, rotation, pitch, yaw };
  }
  return { x: selected.x, y: selected.y, z, scale: selected.depth === 2 ? 1.72 : 2.7, rotation, pitch, yaw };
}

export function persistentWorldSemanticIds(model: PersistentWorldReadModel, selectedPlacementId: string | null) {
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

function drawBackground(context: CanvasRenderingContext2D, width: number, height: number, parallax: Point, momentum: Point, camera: Camera, viewMode: PersistentWorldViewMode) {
  context.fillStyle = "#041219"; context.fillRect(0, 0, width, height);
  const gradient = context.createRadialGradient(width * .5 + parallax.x, height * .48 + parallax.y, 20, width * .5, height * .5, Math.max(width, height) * .72);
  gradient.addColorStop(0, "rgba(27,111,117,.31)"); gradient.addColorStop(.45, "rgba(7,39,48,.18)"); gradient.addColorStop(1, "rgba(1,9,14,0)");
  context.fillStyle = gradient; context.fillRect(0, 0, width, height);
  context.strokeStyle = "rgba(76,148,156,.06)"; context.lineWidth = 1; context.beginPath();
  if (viewMode === "CINEMATIC_2_5D") {
    const vanishingX = width * .5 - camera.yaw * width * .72 + parallax.x * .08;
    const horizonY = Math.max(height * .16, Math.min(height * .48, height * .34 - camera.pitch * height * .42 + parallax.y * .035));
    for (let x = -width * .3; x <= width * 1.3; x += Math.max(54, width / 15)) { context.moveTo(vanishingX, horizonY); context.lineTo(x, height); }
    for (let index = 1; index <= 12; index += 1) { const t = index / 12; const y = horizonY + (height - horizonY) * t * t; context.moveTo(0, y); context.lineTo(width, y); }
  } else {
    const grid = 48;
    for (let x = ((parallax.x * .16) % grid) - grid; x < width + grid; x += grid) { context.moveTo(x, 0); context.lineTo(x, height); }
    for (let y = ((parallax.y * .16) % grid) - grid; y < height + grid; y += grid) { context.moveTo(0, y); context.lineTo(width, y); }
  }
  context.stroke();
  context.save(); context.translate(width / 2 + parallax.x * .22, height / 2 + parallax.y * .22);
  for (const radius of [Math.min(width, height) * .19, Math.min(width, height) * .34, Math.min(width, height) * .49]) {
    context.strokeStyle = `rgba(93,201,195,${radius < 200 ? .08 : .045})`; context.lineWidth = 1; context.setLineDash([3, 11]);
    const planeCompression = viewMode === "CINEMATIC_2_5D" ? Math.max(.32, .62 - Math.abs(camera.pitch) * .55) : .82;
    context.beginPath(); context.ellipse(0, 0, radius * 1.14, radius * planeCompression, viewMode === "CINEMATIC_2_5D" ? camera.yaw * .42 : -.08, 0, Math.PI * 2); context.stroke();
  }
  context.setLineDash([]); context.restore();
  for (let index = 0; index < 54; index += 1) {
    const layer = index % 3; const depth = [.22, .54, .92][layer];
    const x = ((index * 193 + 71) % Math.max(1, Math.round(width))) + parallax.x * depth + camera.yaw * 110 * depth;
    const y = ((index * 97 + 43) % Math.max(1, Math.round(height))) + parallax.y * depth + camera.pitch * 85 * depth;
    context.strokeStyle = `rgba(111,228,208,${.035 + depth * .085})`; context.fillStyle = `rgba(111,228,208,${.05 + depth * .11})`; context.lineWidth = Math.max(.4, depth * .72);
    if (Math.hypot(momentum.x, momentum.y) > 1.5) { context.beginPath(); context.moveTo(x - momentum.x * depth * .35, y - momentum.y * depth * .35); context.lineTo(x, y); context.stroke(); }
    context.beginPath(); context.arc(x, y, index % 7 === 0 ? .9 + depth * .7 : .35 + depth * .32, 0, Math.PI * 2); context.fill();
  }
  const vignette = context.createRadialGradient(width / 2, height / 2, Math.min(width, height) * .3, width / 2, height / 2, Math.max(width, height) * .7);
  vignette.addColorStop(0, "rgba(0,0,0,0)"); vignette.addColorStop(1, "rgba(0,5,9,.58)"); context.fillStyle = vignette; context.fillRect(0, 0, width, height);
}

function drawDimensionalNode(context: CanvasRenderingContext2D, point: PersistentProjectedPlacement, radius: number, accent: string, selected: boolean, hovered: boolean, emphasized: boolean, depth: number) {
  const lift = point.band === "near" ? 3 : point.band === "mid" ? 2 : 1;
  context.save();
  context.shadowColor = accent; context.shadowBlur = selected ? 24 : hovered ? 17 : emphasized ? 8 : 0;
  context.fillStyle = "rgba(0,7,12,.78)"; context.beginPath(); context.arc(point.x + lift, point.y + lift * 1.35, radius + 1.2, 0, Math.PI * 2); context.fill();
  context.fillStyle = depth === 0 ? "rgba(35,18,42,.97)" : point.band === "near" ? "rgba(8,38,46,.97)" : point.band === "far" ? "rgba(3,20,27,.98)" : "rgba(6,31,39,.97)";
  context.strokeStyle = blendPremiumColor(accent, "#ffffff", hovered ? .28 : .08, .94); context.lineWidth = depth === 0 ? 3.2 : 2;
  context.beginPath(); context.arc(point.x, point.y, radius + (hovered ? 2 : 0), 0, Math.PI * 2); context.fill(); context.stroke();
  context.shadowBlur = 0; context.strokeStyle = blendPremiumColor(accent, "#ffffff", .35, point.band === "far" ? .28 : .48); context.lineWidth = 1.15;
  context.beginPath(); context.arc(point.x, point.y, Math.max(1, radius - 2.5), Math.PI * 1.12, Math.PI * 1.82); context.stroke();
  context.strokeStyle = blendPremiumColor(accent, accent, 1, .2); context.lineWidth = 1; context.beginPath(); context.ellipse(point.x, point.y, radius * 1.75, radius * 1.18, .12 + point.cameraDepth * .00035, 0, Math.PI * 2); context.stroke();
  if (selected) { context.strokeStyle = blendPremiumColor(accent, "#ffffff", .18, .62); context.lineWidth = 1.2; context.beginPath(); context.arc(point.x, point.y, radius + 7, 0, Math.PI * 2); context.stroke(); }
  context.restore();
}

export function PremiumPersistentWorldSurface({ model, factualBindings, selectedPlacementId, fullWorld, viewMode, traceMode, reducedMotion, resetVersion, routePulseVersion, publicBeta = false, onSelect, onNavigateParent, onReset }: Props) {
  const spatialLayout = useMemo(() => createPersistentWorldSpatialLayout(model), [model]);
  const hostRef = useRef<HTMLDivElement>(null); const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraRef = useRef<Camera>(persistentWorldTargetCamera(model, selectedPlacementId, fullWorld, viewMode, 980, 720, spatialLayout));
  const cameraVelocityRef = useRef<PersistentCameraVelocity>({ x: 0, y: 0, z: 0, logScale: 0, rotation: 0, pitch: 0, yaw: 0 });
  const mountedAtRef = useRef(performance.now()); const viewportRef = useRef<Viewport>({ zoom: 1, panX: 0, panY: 0 });
  const panRef = useRef<{ pointerId: number; startX: number; startY: number; panX: number; panY: number; moved: boolean } | null>(null);
  const orbitDragRef = useRef<OrbitDrag | null>(null); const orbitAngleRef = useRef(0); const orbitVelocityRef = useRef(0);
  const suppressClickRef = useRef(false); const hoveredRef = useRef<string | null>(null); const hoverVisualsRef = useRef(new Map<string, number>());
  const pointerRef = useRef<Point>({ x: 0, y: 0 }); const invalidateRef = useRef<() => void>(() => undefined);
  const semanticHistoryRef = useRef<readonly string[]>([]); const cameraMomentumRef = useRef<Point>({ x: 0, y: 0 });
  const routePulseRef = useRef({ version: routePulseVersion, startedAt: performance.now() });
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const hoveredPlacement = hoveredId ? model.placements[hoveredId] : undefined;
  const hoveredFactor = hoveredPlacement ? model.factors[hoveredPlacement.canonicalFactorId] : undefined;
  const hoveredBinding = hoveredId ? factualBindings[hoveredId] : undefined;
  const hoveredSource = hoveredPlacement && hoveredPlacement.depth >= 2 && hoveredFactor ? persistentWorldCandidateSourceProfile(persistentWorldPlacementLabel(model, hoveredPlacement)) ?? persistentWorldCandidateSourceProfile(hoveredFactor.label) : undefined;
  const hoveredValue = compactPersistentValue(hoveredBinding?.status === "CONNECTED" ? hoveredBinding.displayValue : undefined);
  const isVisiblePlacement = (id: string) => !publicBeta || persistentWorldPublicPlacementVisible(model, id);
  const semantic = useMemo(() => persistentWorldSemanticIds(model, fullWorld ? null : selectedPlacementId).filter(isVisiblePlacement), [fullWorld, model, publicBeta, selectedPlacementId]); const semanticSet = useMemo(() => new Set(semantic), [semantic]);
  const selectedPath = useMemo(() => {
    const ids = new Set<string>(); let current = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
    while (current) { ids.add(current.id); current = current.parentPlacementId ? model.placements[current.parentPlacementId] : undefined; } return ids;
  }, [model, selectedPlacementId]);

  useEffect(() => { hoveredRef.current = hoveredId; invalidateRef.current(); }, [hoveredId]);
  useEffect(() => {
    routePulseRef.current = { version: routePulseVersion, startedAt: performance.now() };
    invalidateRef.current();
  }, [routePulseVersion]);
  useEffect(() => { if (hostRef.current) hostRef.current.dataset.viewMode = viewMode; }, [viewMode]);
  useEffect(() => {
    viewportRef.current = { zoom: 1, panX: 0, panY: 0 }; const host = hostRef.current;
    if (host) { host.dataset.viewportZoom = "1.000"; host.dataset.viewportPanX = "0"; host.dataset.viewportPanY = "0"; } invalidateRef.current();
  }, [fullWorld, resetVersion, selectedPlacementId]);
  useEffect(() => {
    orbitAngleRef.current = 0; orbitVelocityRef.current = 0; orbitDragRef.current = null; const host = hostRef.current;
    if (host) { host.dataset.orbitAngleDegrees = "0.0"; host.dataset.orbitDragState = "IDLE"; } invalidateRef.current();
  }, [resetVersion]);

  useEffect(() => {
    const host = hostRef.current; const canvas = canvasRef.current; const context = canvas?.getContext("2d", { alpha: false });
    if (!host || !canvas || !context) return;
    let frame = 0; let last = performance.now(); let frameCount = 0; let accumulated = 0; const frameSamples: number[] = [];
    const initialBounds = host.getBoundingClientRect();
    let destination = persistentWorldTargetCamera(model, selectedPlacementId, fullWorld, viewMode, initialBounds.width, initialBounds.height, spatialLayout); const cameraStarted = performance.now(); let cameraSettled = false;
    let cameraTransition = polishPersistentCameraTransition(createPersistentCameraTransition(cameraRef.current, destination, cameraStarted, `${viewMode}:${selectedPlacementId ?? (fullWorld ? "full-world" : "overview")}`, cameraVelocityRef.current));
    const previousSemantic = semanticHistoryRef.current.length ? semanticHistoryRef.current : semantic; semanticHistoryRef.current = semantic;
    const previousSemanticSet = new Set(previousSemantic); const transitionSemanticSet = new Set([...previousSemantic, ...semantic]);
    delete host.dataset.cameraSettleMs; if (reducedMotion) { cameraRef.current = destination; cameraVelocityRef.current = { x: 0, y: 0, z: 0, logScale: 0, rotation: 0, pitch: 0, yaw: 0 }; cameraMomentumRef.current = { x: 0, y: 0 }; }
    const resize = () => {
      const bounds = host.getBoundingClientRect(); const ratio = Math.min(2, window.devicePixelRatio || 1); destination = persistentWorldTargetCamera(model, selectedPlacementId, fullWorld, viewMode, bounds.width, bounds.height, spatialLayout); cameraTransition.to = destination;
      canvas.width = Math.max(1, Math.round(bounds.width * ratio)); canvas.height = Math.max(1, Math.round(bounds.height * ratio)); canvas.style.width = `${bounds.width}px`; canvas.style.height = `${bounds.height}px`; context.setTransform(ratio, 0, 0, ratio, 0, 0);
      if (reducedMotion) invalidateRef.current();
    };
    resize(); const observer = new ResizeObserver(resize); observer.observe(host);
    const placements = Object.values(model.placements).filter((placement) => isVisiblePlacement(placement.id));
    const hierarchy = Object.values(model.relationships).filter((edge) => publicBeta ? persistentWorldPublicRelationshipVisible(model, edge) : edge.relationshipClass === "HIERARCHY_TETHER");
    const influence = publicBeta ? [] : Object.values(model.relationships).filter((edge) => edge.relationshipClass === "SYNTHETIC_INFLUENCE");
    const focusedPlacementForEdges = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
    const focusedChildrenForEdges = new Set(focusedPlacementForEdges ? model.childrenByPlacement[focusedPlacementForEdges.id] ?? [] : []);
    const renderedPlacements = !focusedPlacementForEdges || fullWorld
      ? placements
      : focusedPlacementForEdges.depth === 1
        ? placements.filter((placement) => placement.depth <= 1 || placement.sector === focusedPlacementForEdges.sector)
        : placements.filter((placement) => transitionSemanticSet.has(placement.id) || selectedPath.has(placement.id));
    const highlightedEdges = hierarchy.filter((edge) => {
      if (!fullWorld && focusedPlacementForEdges) {
        const routeMainline = selectedPath.has(edge.fromPlacementId) && selectedPath.has(edge.toPlacementId);
        const directChild = edge.fromPlacementId === focusedPlacementForEdges.id && focusedChildrenForEdges.has(edge.toPlacementId);
        return routeMainline || directChild;
      }
      return transitionSemanticSet.has(edge.fromPlacementId) && transitionSemanticSet.has(edge.toPlacementId);
    });

    const draw = (now: number) => {
      const started = performance.now(); const elapsedMs = Math.min(48, Math.max(0, now - last)); const bounds = host.getBoundingClientRect(); const width = bounds.width; const height = bounds.height; const camera = cameraRef.current; const viewport = viewportRef.current;
      frame = 0;
      const priorCamera = { ...camera }; const transitionSample = reducedMotion ? { progress: 1, pose: destination, velocity: { x: 0, y: 0, z: 0, logScale: 0, rotation: 0, pitch: 0, yaw: 0 } } : samplePersistentCameraTransition(cameraTransition, now); Object.assign(camera, transitionSample.pose); cameraVelocityRef.current = transitionSample.velocity;
      if (!orbitDragRef.current && !reducedMotion && orbitVelocityRef.current !== 0) {
        orbitAngleRef.current = normalizeOrbitAngle(orbitAngleRef.current + orbitVelocityRef.current * elapsedMs);
        orbitVelocityRef.current = decayPersistentWorldOrbitVelocity(orbitVelocityRef.current, elapsedMs);
      }
      const targetMomentum = reducedMotion ? { x: 0, y: 0 } : { x: Math.max(-14, Math.min(14, (priorCamera.x - camera.x) * camera.scale * .72)), y: Math.max(-14, Math.min(14, (priorCamera.y - camera.y) * camera.scale * .72)) };
      const momentumEase = reducedMotion ? 1 : 1 - Math.exp(-elapsedMs / 86);
      cameraMomentumRef.current.x += (targetMomentum.x - cameraMomentumRef.current.x) * momentumEase; cameraMomentumRef.current.y += (targetMomentum.y - cameraMomentumRef.current.y) * momentumEase;
      const orbitCamera = { ...camera, rotation: camera.rotation + orbitAngleRef.current };
      host.dataset.cameraX = camera.x.toFixed(3); host.dataset.cameraY = camera.y.toFixed(3); host.dataset.cameraZ = camera.z.toFixed(3); host.dataset.cameraScale = camera.scale.toFixed(3); host.dataset.cameraRotationDegrees = (orbitCamera.rotation * 180 / Math.PI).toFixed(1); host.dataset.cameraPitchDegrees = (camera.pitch * 180 / Math.PI).toFixed(1); host.dataset.cameraYawDegrees = (camera.yaw * 180 / Math.PI).toFixed(1);
      host.dataset.orbitAngleDegrees = (orbitAngleRef.current * 180 / Math.PI).toFixed(1); host.dataset.orbitVelocity = orbitVelocityRef.current.toFixed(6);
      host.dataset.cameraTransitionProgress = transitionSample.progress.toFixed(3); host.dataset.cameraTransitionPhase = reducedMotion ? "REDUCED_MOTION" : transitionSample.progress < .28 ? "DOLLY_OUT" : transitionSample.progress < .82 ? "ORBITAL_TRAVEL" : transitionSample.progress < 1 ? "DOLLY_IN" : "SETTLED";
      if (!cameraSettled && transitionSample.progress >= 1) { cameraSettled = true; host.dataset.cameraSettleMs = (performance.now() - cameraStarted).toFixed(3); }
      last = now;
      const parallax = reducedMotion ? { x: 0, y: 0 } : { x: (pointerRef.current.x - width / 2) * .016 + cameraMomentumRef.current.x, y: (pointerRef.current.y - height / 2) * .016 + cameraMomentumRef.current.y };
      drawBackground(context, width, height, parallax, cameraMomentumRef.current, orbitCamera, viewMode);
      const projectFrame = createPersistentProjector(orbitCamera, viewport, width, height);
      const projected = new Map<string, PersistentProjectedPlacement>();
      for (const placement of renderedPlacements) projected.set(placement.id, projectFrame(placement, viewMode === "CINEMATIC_2_5D" ? spatialLayout.zByPlacementId[placement.id] ?? 0 : 0));
      const projectedAt = (id: string) => projected.get(id)!;

      const ambientHierarchy = selectedPlacementId && !fullWorld ? [] : persistentAmbientEdges(hierarchy, [...semanticSet], fullWorld);
      host.dataset.ambientHierarchyCount = ambientHierarchy.length.toString();
      context.lineWidth = .58; context.strokeStyle = fullWorld ? "rgba(93,176,176,.055)" : "rgba(93,176,176,.035)"; context.beginPath();
      for (const edge of ambientHierarchy) { const from = projectedAt(edge.fromPlacementId); const to = projectedAt(edge.toPlacementId); const route = premiumCurveRoute(edge.id, from, to, true); context.moveTo(route.start.x, route.start.y); context.bezierCurveTo(route.control1.x, route.control1.y, route.control2.x, route.control2.y, route.end.x, route.end.y); }
      context.stroke();
      if (fullWorld) { context.strokeStyle = "rgba(166,132,238,.024)"; context.lineWidth = .38; context.beginPath(); for (const edge of influence) { const from = projectedAt(edge.fromPlacementId); const to = projectedAt(edge.toPlacementId); context.moveTo(from.x, from.y); context.lineTo(to.x, to.y); } context.stroke(); }

      context.lineCap = "round"; const currentHovered = hoveredRef.current;
      const depthEdges = [...highlightedEdges].sort((left, right) => (projectedAt(left.fromPlacementId).cameraDepth + projectedAt(left.toPlacementId).cameraDepth) - (projectedAt(right.fromPlacementId).cameraDepth + projectedAt(right.toPlacementId).cameraDepth));
      let visiblePreviousEdgeCount = 0; let visibleCurrentEdgeCount = 0;
      for (const edge of depthEdges) {
        const fromPlacement = model.placements[edge.fromPlacementId]; const toPlacement = model.placements[edge.toPlacementId]; const from = projectedAt(edge.fromPlacementId); const to = projectedAt(edge.toPlacementId); const route = premiumCurveRoute(edge.id, from, to);
        const traceEdge = selectedPath.has(edge.fromPlacementId) && selectedPath.has(edge.toPlacementId);
        const currentEdge = traceEdge || (semanticSet.has(edge.fromPlacementId) && semanticSet.has(edge.toPlacementId)); const previousEdge = previousSemanticSet.has(edge.fromPlacementId) && previousSemanticSet.has(edge.toPlacementId); const transitionAlpha = persistentWorldEdgeTransitionAlpha(currentEdge, previousEdge, transitionSample.progress);
        const accent = persistentPlacementAccent(toPlacement); const incident = Boolean(currentHovered && (edge.fromPlacementId === currentHovered || edge.toPlacementId === currentHovered));
        const hoverAmount = easePremiumHover(hoverVisualsRef.current.get(edge.id) ?? 0, incident ? 1 : 0, elapsedMs, reducedMotion); hoverVisualsRef.current.set(edge.id, hoverAmount);
        const focused = selectedPlacementId ? model.placements[selectedPlacementId] : undefined; const denseFanEdge = Boolean(focused && focused.depth < 3 && (edge.fromPlacementId === focused.id || edge.toPlacementId === focused.id)); const railScale = denseFanEdge ? .64 : 1;
        const routePulse = reducedMotion || !traceEdge ? 0 : Math.max(0, 1 - (now - routePulseRef.current.startedAt) / 700);
        const depthAlpha = Math.min(from.opacity, to.opacity); const traceAlpha = (traceMode ? traceEdge ? 1 : .13 : 1) * transitionAlpha * depthAlpha;
        if (traceAlpha <= .012) continue;
        if (currentEdge) visibleCurrentEdgeCount += 1;
        if (previousEdge && !currentEdge) visiblePreviousEdgeCount += 1;
        const color = blendPremiumColor(AMBIENT_EDGE, accent, (denseFanEdge ? .76 : .52) + hoverAmount * (denseFanEdge ? .24 : .48), (currentHovered && !incident ? .24 : .9) * traceAlpha);
        context.save(); context.shadowColor = accent; context.shadowBlur = ((denseFanEdge ? 5 + hoverAmount * 8 : 8 + hoverAmount * 10) + routePulse * 7) * traceAlpha; context.strokeStyle = blendPremiumColor(AMBIENT_EDGE, accent, .45 + hoverAmount * .55, (.18 + hoverAmount * .18 + routePulse * .1) * traceAlpha); context.lineWidth = (8 + hoverAmount * 2 + routePulse * 1.4) * railScale; traceCubic(context, route); context.stroke();
        context.shadowBlur = 0; context.strokeStyle = color; context.lineWidth = (3.2 + hoverAmount * 1.2) * railScale; traceCubic(context, route); context.stroke(); context.strokeStyle = blendPremiumColor("#b8e1df", accent, .42 + hoverAmount * .58, .88 * traceAlpha); context.lineWidth = denseFanEdge ? .85 : 1.05; traceCubic(context, route); context.stroke(); context.restore();
        if (!reducedMotion && (!traceMode || traceEdge)) { const progress = persistentGlintProgress(now, edge.id); const trailStart = pointOnCubic(route, Math.max(0, progress - PERSISTENT_GLINT_TRAIL)); const trailEnd = pointOnCubic(route, progress); const gradient = context.createLinearGradient(trailStart.x, trailStart.y, trailEnd.x, trailEnd.y); gradient.addColorStop(0, blendPremiumColor(accent, accent, 1, 0)); gradient.addColorStop(1, blendPremiumColor("#ffffff", accent, .26, .98 * traceAlpha)); context.save(); context.strokeStyle = gradient; context.lineWidth = 3.1; context.shadowColor = accent; context.shadowBlur = 12 * traceAlpha; context.beginPath(); context.moveTo(trailStart.x, trailStart.y); context.lineTo(trailEnd.x, trailEnd.y); context.stroke(); context.restore(); }
      }
      host.dataset.visiblePreviousEdgeCount = visiblePreviousEdgeCount.toString();
      host.dataset.visibleCurrentEdgeCount = visibleCurrentEdgeCount.toString();

      const labelCandidates: LabelCandidate[] = []; const focusPlacement = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
      const farPlacements: PersistentWorldPlacement[] = []; const midPlacements: PersistentWorldPlacement[] = []; const nearPlacements: PersistentWorldPlacement[] = [];
      for (const placement of renderedPlacements) (projectedAt(placement.id).band === "far" ? farPlacements : projectedAt(placement.id).band === "near" ? nearPlacements : midPlacements).push(placement);
      const orderedPlacements = [...farPlacements, ...midPlacements, ...nearPlacements];
      for (const placement of orderedPlacements) {
        const point = projectedAt(placement.id); if (point.x < -42 || point.y < -42 || point.x > width + 42 || point.y > height + 42) continue;
        const factorLabel = persistentWorldGraphNodeLabel(model, placement); const factualBinding = factualBindings[placement.id];
        const semanticAlpha = Math.min(1, (semanticSet.has(placement.id) ? transitionSample.progress * 1.8 : 0) + (previousSemanticSet.has(placement.id) ? Math.max(0, 1 - transitionSample.progress * 2.5) : 0));
        if (!fullWorld && focusPlacement?.depth === 2 && !semanticSet.has(placement.id) && semanticAlpha <= .015) continue;
        const emphasized = semanticAlpha > .015 || selectedPath.has(placement.id); const sectorActive = isInSelectedSector(model, placement, selectedPlacementId); const effectiveScale = camera.scale * viewport.zoom * point.perspectiveScale; const lod = resolvePersistentLod(placement.depth, effectiveScale, emphasized); const radius = premiumRadius(placement, lod) * (.82 + point.perspectiveScale * .18);
        const accent = persistentPlacementAccent(placement); const isHovered = placement.id === currentHovered; const isSelected = placement.id === selectedPlacementId;
        context.globalAlpha = (emphasized ? Math.max(.08, semanticAlpha, selectedPath.has(placement.id) ? .7 : 0) : sectorActive ? (placement.depth === 3 ? .36 : .58) : (fullWorld ? .24 : .1)) * point.opacity;
        if (lod === 0) { context.fillStyle = accent; context.beginPath(); context.arc(point.x, point.y, Math.max(1, radius), 0, Math.PI * 2); context.fill(); }
        else {
          drawDimensionalNode(context, point, radius, accent, isSelected, isHovered, emphasized, placement.depth);
          context.save(); if (lod >= 2) drawPremiumGlyph(context, factorGlyph(placement, factorLabel), point.x, point.y, radius * (placement.depth === 3 ? .85 : .62), accent);
          if (factualBinding && lod >= 2) {
            const badgeX = point.x + radius * .72; const badgeY = point.y - radius * .72;
            context.fillStyle = factualBinding.status === "CONNECTED" ? "#55e7bc" : factualBinding.status === "SOURCE_IDENTIFIED" ? "#f0bd64" : "rgba(126,161,170,.5)";
            context.strokeStyle = "rgba(2,18,24,.96)"; context.lineWidth = 2.2; context.beginPath(); context.arc(badgeX, badgeY, factualBinding.status === "CONNECTED" ? 4.2 : 3.1, 0, Math.PI * 2); context.fill(); context.stroke();
          }
          context.restore();
        }
        if (emphasized && lod >= 1) {
          const label = factorLabel; const fontSize = placement.depth === 0 ? 13 : placement.depth === 1 ? 12 : 11; context.font = `${placement.depth < 2 ? 750 : 650} ${fontSize}px Inter, system-ui, sans-serif`; const textWidth = Math.min(226, context.measureText(label).width + 18);
          let labelX = point.x; let labelY = point.y + radius + 17; let anchorX: number | undefined; let anchorY: number | undefined; let labelSide: "left" | "right" | "top" | "bottom" | undefined;
          const parent = placement.parentPlacementId ? model.placements[placement.parentPlacementId] : undefined;
          if (parent && placement.depth >= 2) {
            const parentPoint = projectedAt(parent.id); const dx = point.x - parentPoint.x; const dy = point.y - parentPoint.y; const distance = Math.max(1, Math.hypot(dx, dy)); const tangent = placement.order % 2 ? -6 : 6;
            labelX = point.x + (dx / distance) * (radius + 15) + (-dy / distance) * tangent;
            labelY = point.y + (dy / distance) * (radius + 15) + (dx / distance) * tangent;
            const focused = selectedPlacementId ? model.placements[selectedPlacementId] : undefined;
            const focusedExactTenChild = Boolean(focused && focused.depth < 3 && placement.parentPlacementId === focused.id && placement.depth === focused.depth + 1);
            if (focusedExactTenChild && viewMode === "TOP_DOWN") {
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
          labelCandidates.push({ id: placement.id, text: label, x: labelX, y: labelY, priority: placement.depth === 0 ? 100 : isSelected ? 90 : placement.depth === 1 ? 70 : placement.depth === 2 ? 50 : 20, width: textWidth, height: 22, accent, anchorX, anchorY, required: focusedExactTenChild && viewMode === "TOP_DOWN", side: labelSide, opacity: Math.max(.08, semanticAlpha, selectedPath.has(placement.id) ? .7 : 0) * point.opacity });
        }
        context.globalAlpha = 1;
      }
      const labels = resolvePremiumLabels(labelCandidates, width, height).map((label) => ({ ...label, anchorX: undefined, anchorY: undefined }));
      host.dataset.labelLeaderCount = labels.filter((label) => label.anchorX !== undefined && label.anchorY !== undefined).length.toString();
      for (const label of labels) { context.save(); context.globalAlpha = label.opacity ?? 1; if (label.anchorX !== undefined && label.anchorY !== undefined) { const targetX = label.side === "left" ? label.left + label.width : label.side === "right" ? label.left : label.x; const targetY = label.side === "top" ? label.top + label.height : label.side === "bottom" ? label.top : label.y; context.strokeStyle = blendPremiumColor(label.accent, label.accent, 1, .3); context.lineWidth = .8; context.beginPath(); context.moveTo(label.anchorX, label.anchorY); context.lineTo(targetX, targetY); context.stroke(); } context.fillStyle = "rgba(2,16,22,.9)"; context.strokeStyle = blendPremiumColor(label.accent, label.accent, 1, .3); context.lineWidth = 1; context.beginPath(); context.roundRect(label.left, label.top, label.width, label.height, 6); context.fill(); context.stroke(); context.fillStyle = label.id === selectedPlacementId ? "#f4fffc" : blendPremiumColor("#d9eeeb", label.accent, .28, 1); context.font = `${label.priority >= 70 ? 750 : 650} ${label.priority >= 70 ? 12 : 11}px Inter, system-ui, sans-serif`; context.textAlign = "center"; context.textBaseline = "middle"; context.fillText(label.text, label.x, label.y, label.width - 12); context.restore(); }

      const elapsed = performance.now() - started;
      if (frameCount === 0) host.dataset.firstDrawMs = (performance.now() - mountedAtRef.current).toFixed(3);
      frameCount += 1; accumulated += elapsed; frameSamples.push(elapsed);
      if (frameCount === 30 || (reducedMotion && frameCount === 1)) {
        const ordered = [...frameSamples].sort((a, b) => a - b); const meanFrameMs = accumulated / frameCount; const medianFrameMs = ordered[Math.floor(ordered.length / 2)]; const p95FrameMs = ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * .95) - 1)]; const mode = fullWorld ? "FULL_WORLD_LOD" : selectedPlacementId ? "FOCUS_LOD" : "OVERVIEW_LOD";
        window.__AUXSAYS_PERSISTENT_WORLD_METRICS__ = { placementCount: placements.length, relationshipCount: hierarchy.length + influence.length, meanFrameMs, medianFrameMs, p95FrameMs, mode, semanticLabelCount: labels.length };
        host.dataset.meanFrameMs = meanFrameMs.toFixed(3); host.dataset.medianFrameMs = medianFrameMs.toFixed(3); host.dataset.p95FrameMs = p95FrameMs.toFixed(3); host.dataset.performanceMode = mode; host.dataset.semanticLabelCount = labels.length.toString();
      }
      const hoverAnimating = [...hoverVisualsRef.current.values()].some((value) => currentHovered ? value < .995 : value > .01);
      const routePulseActive = !reducedMotion && now - routePulseRef.current.startedAt < 700;
      host.dataset.routePulseState = routePulseActive ? "ACTIVE" : "IDLE";
      const orbitDrifting = !reducedMotion && Math.abs(orbitVelocityRef.current) > 0;
      if (!orbitDragRef.current) host.dataset.orbitDragState = orbitDrifting ? "DRIFTING" : "IDLE";
      const shouldContinue = !reducedMotion && (transitionSample.progress < 1 || Boolean(currentHovered) || hoverAnimating || traceMode || routePulseActive || orbitDrifting);
      host.dataset.renderLoopState = shouldContinue ? "ACTIVE" : "IDLE";
      if (shouldContinue) frame = requestAnimationFrame(draw);
    };
    invalidateRef.current = () => { if (reducedMotion) draw(performance.now()); else if (!frame) frame = requestAnimationFrame(draw); }; draw(performance.now());
    return () => { observer.disconnect(); cancelAnimationFrame(frame); invalidateRef.current = () => undefined; };
  }, [factualBindings, fullWorld, model, publicBeta, reducedMotion, selectedPath, selectedPlacementId, semantic, semanticSet, spatialLayout, traceMode, viewMode]);

  function hitTest(event: { clientX: number; clientY: number }) {
    const host = hostRef.current; if (!host) return null; const bounds = host.getBoundingClientRect(); const camera = cameraRef.current; let best: { id: string; score: number; depth: number } | null = null;
    const projectHit = createPersistentProjector({ ...camera, rotation: camera.rotation + orbitAngleRef.current }, viewportRef.current, bounds.width, bounds.height);
    for (const id of semantic) { const placement = model.placements[id]; const point = projectHit(placement, viewMode === "CINEMATIC_2_5D" ? spatialLayout.zByPlacementId[id] ?? 0 : 0); const lod = resolvePersistentLod(placement.depth, camera.scale * viewportRef.current.zoom * point.perspectiveScale, true); const radius = Math.max(24, premiumRadius(placement, lod) * point.perspectiveScale + 8); const distance = Math.hypot(event.clientX - bounds.left - point.x, event.clientY - bounds.top - point.y); const score = distance / radius; if (score <= 1 && (!best || score < best.score - .04 || (Math.abs(score - best.score) <= .04 && point.cameraDepth > best.depth))) best = { id, score, depth: point.cameraDepth }; }
    return best?.id ?? null;
  }
  function updateViewport(next: Viewport) { viewportRef.current = next; const host = hostRef.current; if (host) { host.dataset.viewportZoom = next.zoom.toFixed(3); host.dataset.viewportPanX = Math.round(next.panX).toString(); host.dataset.viewportPanY = Math.round(next.panY).toString(); } invalidateRef.current(); }

  const parentPlacementId = selectedPlacementId ? model.placements[selectedPlacementId]?.parentPlacementId : null;

  const connectedPlacements = Object.entries(factualBindings).filter(([, binding]) => binding.status === "CONNECTED");
  const connectedCanonicalFactors = new Set(connectedPlacements.map(([placementId]) => model.placements[placementId]?.canonicalFactorId).filter(Boolean)).size;
  useEffect(() => { if (hostRef.current) hostRef.current.dataset.reducedMotion = reducedMotion.toString(); }, [reducedMotion]);
  return <div ref={hostRef} className="sm-pw-surface sm-pw-surface--premium" role="application" tabIndex={0} aria-label="U.S. systems factor map" aria-keyshortcuts="Alt+ArrowLeft" data-world-id={model.worldId} data-graph-snapshot-id={model.graphSnapshotId} data-layout-version={model.layoutVersion} data-topology-fingerprint={model.topologyFingerprint} data-semantic-fingerprint={model.semanticFingerprint} data-presentation-layout-version={spatialLayout.version} data-projection-version={spatialLayout.projectionVersion} data-presentation-fingerprint={spatialLayout.fingerprint} data-resident-placement-count={model.coverage.placementCount} data-resident-relationship-count={model.coverage.hierarchyRelationshipCount + model.coverage.syntheticInfluenceCount} data-semantic-node-count={semantic.length} data-factual-binding-count={connectedPlacements.length} data-connected-placement-count={connectedPlacements.length} data-connected-canonical-factor-count={connectedCanonicalFactors} data-lod-mode={fullWorld ? "FULL_WORLD_DENSITY" : selectedPlacementId ? "FOCUS" : "OVERVIEW"} data-trace-mode={traceMode} data-route-pulse-version={routePulseVersion} data-selected-placement-id={selectedPlacementId ?? ""} data-parent-placement-id={parentPlacementId ?? ""} data-viewport-zoom="1.000" data-viewport-pan-x="0" data-viewport-pan-y="0" data-orbit-angle-degrees="0.0" data-orbit-velocity="0.000000" data-orbit-drag-state="IDLE" data-glint-period-ms="2500" data-glint-trail="0.085" data-hovered-placement-id={hoveredId ?? ""} onKeyDown={(event) => {
    if (event.altKey && event.key === "ArrowLeft" && selectedPlacementId) { event.preventDefault(); onNavigateParent(); }
  }} onWheel={(event) => {
    const started = performance.now(); event.preventDefault(); const bounds = event.currentTarget.getBoundingClientRect(); const current = viewportRef.current; const zoom = Math.max(.55, Math.min(3.25, current.zoom * Math.exp(-event.deltaY * .0014))); const ratio = zoom / current.zoom; const cursorX = event.clientX - bounds.left - bounds.width / 2; const cursorY = event.clientY - bounds.top - bounds.height / 2; updateViewport({ zoom, panX: cursorX - (cursorX - current.panX) * ratio, panY: cursorY - (cursorY - current.panY) * ratio }); event.currentTarget.dataset.wheelHandlerMs = (performance.now() - started).toFixed(3);
  }} onPointerDown={(event) => {
    if (event.button === 0 && event.target === canvasRef.current) {
      event.preventDefault(); suppressClickRef.current = false;
      if (!hitTest(event)) {
        event.currentTarget.setPointerCapture(event.pointerId); orbitVelocityRef.current = 0;
        orbitDragRef.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, lastX: event.clientX, lastAt: performance.now(), startAngle: orbitAngleRef.current, moved: false };
        event.currentTarget.dataset.orbitDragState = "DRAGGING"; setHoveredId(null); invalidateRef.current();
      }
      return;
    }
    if (event.button !== 1) return;
    event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); const current = viewportRef.current; panRef.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, panX: current.panX, panY: current.panY, moved: false };
  }} onPointerMove={(event) => {
    const bounds = event.currentTarget.getBoundingClientRect(); pointerRef.current = { x: event.clientX - bounds.left, y: event.clientY - bounds.top }; const pan = panRef.current;
    if (pan?.pointerId === event.pointerId) { const dx = event.clientX - pan.startX; const dy = event.clientY - pan.startY; pan.moved ||= Math.hypot(dx, dy) > 3; suppressClickRef.current = pan.moved; updateViewport({ ...viewportRef.current, panX: pan.panX + dx, panY: pan.panY + dy }); return; }
    const orbit = orbitDragRef.current;
    if (orbit?.pointerId === event.pointerId) {
      event.preventDefault(); const now = performance.now(); const totalX = event.clientX - orbit.startX; const totalY = event.clientY - orbit.startY;
      orbit.moved ||= Math.abs(totalX) > 4 && Math.abs(totalX) >= Math.abs(totalY) * .55; suppressClickRef.current = orbit.moved;
      if (orbit.moved) {
        orbitAngleRef.current = persistentWorldOrbitAngle(orbit.startAngle, totalX, viewMode, cameraRef.current.pitch);
        const sampledVelocity = reducedMotion ? 0 : persistentWorldOrbitVelocity(event.clientX - orbit.lastX, now - orbit.lastAt, viewMode, cameraRef.current.pitch);
        orbitVelocityRef.current += (sampledVelocity - orbitVelocityRef.current) * .58;
        orbit.lastX = event.clientX; orbit.lastAt = now; event.currentTarget.dataset.orbitAngleDegrees = (orbitAngleRef.current * 180 / Math.PI).toFixed(1); invalidateRef.current();
      }
      return;
    }
    const started = performance.now(); const hit = hitTest(event); setHoveredId(hit); if (hit) { event.currentTarget.style.setProperty("--pw-hover-x", `${Math.max(14, Math.min(bounds.width - 304, pointerRef.current.x + 18))}px`); event.currentTarget.style.setProperty("--pw-hover-y", `${Math.max(14, Math.min(bounds.height - 246, pointerRef.current.y + 18))}px`); } event.currentTarget.dataset.hoverHitTestMs = (performance.now() - started).toFixed(3); invalidateRef.current();
  }} onPointerUp={(event) => {
    if (panRef.current?.pointerId === event.pointerId) { event.currentTarget.releasePointerCapture(event.pointerId); panRef.current = null; }
    if (orbitDragRef.current?.pointerId === event.pointerId) { const moved = orbitDragRef.current.moved; event.currentTarget.releasePointerCapture(event.pointerId); orbitDragRef.current = null; if (!moved || reducedMotion) orbitVelocityRef.current = 0; event.currentTarget.dataset.orbitDragState = orbitVelocityRef.current ? "DRIFTING" : "IDLE"; invalidateRef.current(); }
  }} onPointerCancel={(event) => { panRef.current = null; orbitDragRef.current = null; orbitVelocityRef.current = 0; event.currentTarget.dataset.orbitDragState = "IDLE"; }} onPointerLeave={() => { if (!panRef.current && !orbitDragRef.current) setHoveredId(null); }} onMouseDown={(event) => { if ((event.button === 0 && event.target === canvasRef.current) || event.button === 1) event.preventDefault(); }} onAuxClick={(event) => { if (event.button === 1) event.preventDefault(); }} onDoubleClick={(event) => { const action = persistentWorldDoubleClickAction(hitTest(event), parentPlacementId); if (action === "UP_ONE_LEVEL") onNavigateParent(); else if (action === "RESET") onReset(); }} onClick={(event) => { if (event.detail > 1) return; if (suppressClickRef.current) { suppressClickRef.current = false; return; } const id = hitTest(event); if (id && id !== parentPlacementId) onSelect(id); }}>
    <canvas ref={canvasRef} role="img" aria-label={publicBeta
      ? "Reviewed factors and configuration-pending Level-4 nodes with hierarchy-only navigation connections, bounded to the current neighborhood."
      : "All 1,111 fixture placements remain resident; premium visual detail and labels are bounded to the current exact-ten neighborhood."} />
    <aside className="sm-pw-hover-card" role="tooltip" aria-hidden={!hoveredPlacement} data-visible={Boolean(hoveredPlacement)}>
      {hoveredPlacement && hoveredFactor && <><header><span>{hoveredPlacement.depth === 1 ? "System" : hoveredPlacement.depth === 2 ? "Factor" : hoveredPlacement.depth === 0 ? "Outcome" : "Supporting factor"}</span><strong>{persistentWorldPlacementLabel(model, hoveredPlacement)}</strong>{hoveredValue && <b>{hoveredValue}</b>}</header><dl><div><dt>Purpose</dt><dd>{hoverPurpose(model, hoveredPlacement)}</dd></div><div><dt>Tracks</dt><dd>{hoveredSource?.summary ?? hoveredFactor.definition}</dd></div><div><dt>Why</dt><dd>{hoverWhy(model, hoveredPlacement)}</dd></div></dl><small>{hoveredBinding?.status === "CONNECTED" ? `${hoveredBinding.validTime} · ${hoveredBinding.provider} · click for evidence` : hoveredBinding?.status === "SOURCE_ENABLED_PENDING_ACCEPTANCE" ? "Collector enabled · acceptance pending" : hoveredBinding?.status === "BLOCKED" ? "Official path identified · retrieval blocked" : "Click for full details"}</small></>}
    </aside>
    <p className="sm-sr-only">Use the structured factor controls following the world to navigate without relying on position, color, hover, or motion.</p>
  </div>;
}

declare global { interface Window { __AUXSAYS_PERSISTENT_WORLD_METRICS__?: { placementCount: number; relationshipCount: number; meanFrameMs: number; medianFrameMs: number; p95FrameMs: number; mode: string; semanticLabelCount: number }; } }
