import type { MotionOutcome, MotionQaRelationship, StructuralSurfaceModel, StructuralSurfaceNode, StructuralSurfaceRelationship } from "../../data/motionQaReadModel";
import { resolveStructuralNodeVisual, type StructuralNodeSymbol } from "./structuralVisualLanguage";

export interface StructuralCamera {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export interface StructuralViewportTransform {
  zoom: number;
  panX: number;
  panY: number;
}

export const MIN_STRUCTURAL_ZOOM = 0.7;
export const MAX_STRUCTURAL_ZOOM = 2.4;
export const CONNECTOR_GLINT_PERIOD_MS = 2500;
export const STRUCTURAL_CAMERA_TRANSITION_MS = 760;
export const STRUCTURAL_PARTICLES_PER_NODE = 8;

export interface StructuralDepthVisual {
  scale: number;
  opacity: number;
}

export interface SpringParallaxState {
  position: Point;
  velocity: Point;
}

export function easeConnectorHover(current: number, target: number, elapsedMs: number, reducedMotion = false) {
  if (reducedMotion) return target;
  const safeElapsed = Math.max(0, elapsedMs);
  const blend = 1 - Math.exp(-safeElapsed / 180);
  return current + (target - current) * blend;
}

export function blendConnectorColor(from: string, to: string, progress: number, alpha = 1) {
  const read = (value: string) => {
    const match = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(value);
    return match ? [Number.parseInt(match[1], 16), Number.parseInt(match[2], 16), Number.parseInt(match[3], 16)] : [117, 201, 189];
  };
  const start = read(from);
  const end = read(to);
  const amount = Math.max(0, Math.min(1, progress));
  const channels = start.map((channel, index) => Math.round(channel + (end[index] - channel) * amount));
  const opacity = Math.max(0, Math.min(1, alpha));
  return opacity < 1 ? `rgba(${channels[0]}, ${channels[1]}, ${channels[2]}, ${opacity})` : `rgb(${channels[0]}, ${channels[1]}, ${channels[2]})`;
}

export function connectorGlintProgress(nowMs: number, edgeIndex: number) {
  return ((nowMs / CONNECTOR_GLINT_PERIOD_MS) + edgeIndex * 0.137) % 1;
}

export function resolveStructuralDepths(model: StructuralSurfaceModel, focusNodeId: string | null = null) {
  const nodeIds = new Set(model.nodes.map((node) => node.id));
  const adjacency = new Map(model.nodes.map((node) => [node.id, [] as string[]]));
  const inbound = new Set<string>();
  for (const edge of model.relationships) {
    if (!nodeIds.has(edge.from) || !nodeIds.has(edge.to)) continue;
    if (!focusNodeId && edge.outcome && ["BLOCKED", "ABSORBED", "UNKNOWN"].includes(edge.outcome)) continue;
    adjacency.get(edge.from)!.push(edge.to);
    inbound.add(edge.to);
    if (focusNodeId) adjacency.get(edge.to)!.push(edge.from);
  }
  const origins = focusNodeId && nodeIds.has(focusNodeId)
    ? [focusNodeId]
    : model.nodes.filter((node) => !inbound.has(node.id)).sort((left, right) => left.displayRank - right.displayRank).map((node) => node.id);
  if (!origins.length && model.nodes.length) origins.push([...model.nodes].sort((left, right) => left.displayRank - right.displayRank)[0].id);
  const depths = new Map<string, number>();
  const queue = origins.map((nodeId) => ({ nodeId, depth: 0 }));
  while (queue.length) {
    const current = queue.shift()!;
    if ((depths.get(current.nodeId) ?? Number.POSITIVE_INFINITY) <= current.depth) continue;
    depths.set(current.nodeId, current.depth);
    for (const nextId of adjacency.get(current.nodeId) ?? []) queue.push({ nodeId: nextId, depth: Math.min(10, current.depth + 1) });
  }
  model.nodes.forEach((node) => { if (!depths.has(node.id)) depths.set(node.id, Math.min(10, Math.max(1, node.displayRank - 1))); });
  return depths;
}

export function resolveStructuralDepthVisual(depth: number, emphasized = false): StructuralDepthVisual {
  if (emphasized) return { scale: 1, opacity: 1 };
  const bounded = Math.max(0, Math.min(10, depth));
  return {
    scale: Math.max(0.72, 1 - bounded * 0.038),
    opacity: Math.max(0.46, 0.92 - bounded * 0.052)
  };
}

export function stepSpringParallax(current: SpringParallaxState, target: Point, elapsedMs: number, reducedMotion = false): SpringParallaxState {
  if (reducedMotion) return { position: { x: 0, y: 0 }, velocity: { x: 0, y: 0 } };
  const elapsed = Math.max(0, Math.min(50, elapsedMs)) / 1000;
  const stiffness = 110;
  const damping = Math.exp(-12.5 * elapsed);
  const velocity = {
    x: (current.velocity.x + (target.x - current.position.x) * stiffness * elapsed) * damping,
    y: (current.velocity.y + (target.y - current.position.y) * stiffness * elapsed) * damping
  };
  return {
    position: { x: current.position.x + velocity.x * elapsed, y: current.position.y + velocity.y * elapsed },
    velocity
  };
}

export interface StructuralRenderState {
  model: StructuralSurfaceModel;
  currentEdges: MotionQaRelationship[];
  completedEdgeIds: Set<string>;
  pathEdgeIds: Set<string>;
  nodeStates: Map<string, string>;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  viewportTransform: StructuralViewportTransform;
  cameraFocusNodeId: string | null;
  focusDepth: number;
  visibleNodeIds: Set<string>;
  visibleRelationshipIds: Set<string>;
  traceMode: boolean;
  reducedMotion: boolean;
  elapsedMs: number;
  nowMs: number;
  reconciliationTargetId: string | null;
  commonOriginNodeId: string | null;
  centerNodeId: string;
  parallaxTarget: Point;
}

export interface StructuralRenderer {
  resize(width: number, height: number, density: number): void;
  render(state: StructuralRenderState): void;
  destroy(): void;
}

export interface Point {
  x: number;
  y: number;
}

const DESIGN_WIDTH = 1000;
const DESIGN_HEIGHT = 620;

const outcomeColors: Record<MotionOutcome, string> = {
  TRANSMITTED: "#84f1d5",
  DELAYED: "#efbc69",
  PARTIALLY_ABSORBED: "#79d8c7",
  ABSORBED: "#a9bbc2",
  BLOCKED: "#ff7d77",
  AMPLIFIED: "#ffd07a",
  UNKNOWN: "#8196a2"
};

export function createStructuralCamera(width: number, height: number, selected?: StructuralSurfaceNode, focusDepth = 0): StructuralCamera {
  const baseScale = Math.min((width - 52) / DESIGN_WIDTH, (height - 44) / DESIGN_HEIGHT);
  const scale = baseScale * (selected ? Math.min(1.82, 1.64 + Math.max(0, focusDepth - 1) * 0.08) : 1);
  if (selected) {
    return {
      scale,
      offsetX: width * 0.5 - selected.x * scale,
      offsetY: height * 0.48 - selected.y * scale
    };
  }
  return {
    scale,
    offsetX: (width - DESIGN_WIDTH * scale) / 2,
    offsetY: (height - DESIGN_HEIGHT * scale) / 2
  };
}

export function interpolateCamera(from: StructuralCamera, to: StructuralCamera, progress: number): StructuralCamera {
  const clamped = Math.max(0, Math.min(1, progress));
  const eased = clamped * clamped * (3 - 2 * clamped);
  const deltaX = to.offsetX - from.offsetX;
  const deltaY = to.offsetY - from.offsetY;
  const distance = Math.hypot(deltaX, deltaY);
  const arc = Math.sin(Math.PI * clamped) * Math.min(34, distance * 0.055);
  const normalX = distance ? -deltaY / distance : 0;
  const normalY = distance ? deltaX / distance : 0;
  return {
    scale: from.scale + (to.scale - from.scale) * eased,
    offsetX: from.offsetX + deltaX * eased + normalX * arc,
    offsetY: from.offsetY + deltaY * eased + normalY * arc
  };
}

export function projectNode(node: StructuralSurfaceNode, camera: StructuralCamera): Point {
  return { x: camera.offsetX + node.x * camera.scale, y: camera.offsetY + node.y * camera.scale };
}

export function applyStructuralViewport(camera: StructuralCamera, width: number, height: number, viewport: StructuralViewportTransform): StructuralCamera {
  const centerX = width / 2;
  const centerY = height / 2;
  return {
    scale: camera.scale * viewport.zoom,
    offsetX: centerX + (camera.offsetX - centerX) * viewport.zoom + viewport.panX,
    offsetY: centerY + (camera.offsetY - centerY) * viewport.zoom + viewport.panY
  };
}

export function zoomStructuralViewportAt(viewport: StructuralViewportTransform, x: number, y: number, width: number, height: number, factor: number): StructuralViewportTransform {
  const zoom = Math.max(MIN_STRUCTURAL_ZOOM, Math.min(MAX_STRUCTURAL_ZOOM, viewport.zoom * factor));
  const ratio = zoom / viewport.zoom;
  const centerX = width / 2;
  const centerY = height / 2;
  return {
    zoom,
    panX: x - centerX - (x - centerX - viewport.panX) * ratio,
    panY: y - centerY - (y - centerY - viewport.panY) * ratio
  };
}

export function sampleRelationship(edge: StructuralSurfaceRelationship, nodes: Map<string, StructuralSurfaceNode>, count = 64): Point[] {
  const from = nodes.get(edge.from)!;
  const to = nodes.get(edge.to)!;
  const midpoint = (from.x + to.x) / 2;
  return Array.from({ length: count + 1 }, (_, index) => {
    const t = index / count;
    const inverse = 1 - t;
    return {
      x: inverse ** 3 * from.x + 3 * inverse ** 2 * t * midpoint + 3 * inverse * t ** 2 * midpoint + t ** 3 * to.x,
      y: inverse ** 3 * from.y + 3 * inverse ** 2 * t * from.y + 3 * inverse * t ** 2 * to.y + t ** 3 * to.y
    };
  });
}

export function outcomeTravel(outcome: MotionOutcome, rawProgress: number) {
  const progress = Math.max(0, Math.min(1, rawProgress));
  if (outcome === "BLOCKED") return progress * 0.76;
  if (outcome === "ABSORBED") return progress * 0.7;
  if (outcome === "UNKNOWN") return progress * 0.58;
  if (outcome === "DELAYED") {
    if (progress < 0.48) return progress * 1.08;
    if (progress < 0.8) return 0.52;
    return 0.52 + ((progress - 0.8) / 0.2) * 0.48;
  }
  return progress;
}

function tracePoints(context: CanvasRenderingContext2D, points: Point[], start = 0, end = 1) {
  const first = Math.max(0, Math.floor(start * (points.length - 1)));
  const last = Math.min(points.length - 1, Math.ceil(end * (points.length - 1)));
  if (last <= first) return;
  context.beginPath();
  context.moveTo(points[first].x, points[first].y);
  for (let index = first + 1; index <= last; index += 1) context.lineTo(points[index].x, points[index].y);
}

function pointAt(points: Point[], progress: number) {
  const index = Math.max(0, Math.min(points.length - 1, Math.round(progress * (points.length - 1))));
  return points[index];
}

function tangentAt(points: Point[], progress: number) {
  const index = Math.max(1, Math.min(points.length - 2, Math.round(progress * (points.length - 1))));
  return Math.atan2(points[index + 1].y - points[index - 1].y, points[index + 1].x - points[index - 1].x);
}

function drawArrow(context: CanvasRenderingContext2D, points: Point[], progress: number, color: string, alpha: number) {
  const point = pointAt(points, progress);
  const angle = tangentAt(points, progress);
  context.save();
  context.translate(point.x, point.y);
  context.rotate(angle);
  context.globalAlpha = alpha;
  context.fillStyle = color;
  context.beginPath();
  context.moveTo(9, 0);
  context.lineTo(-5, -4.5);
  context.lineTo(-2, 0);
  context.lineTo(-5, 4.5);
  context.closePath();
  context.fill();
  context.restore();
}

function drawOutcomeMarker(context: CanvasRenderingContext2D, points: Point[], edge: MotionQaRelationship, phase: number) {
  const travel = outcomeTravel(edge.outcome, 1);
  const point = pointAt(points, travel);
  const angle = tangentAt(points, travel);
  const pulse = 0.5 + Math.sin(phase * Math.PI * 2) * 0.5;
  context.save();
  context.translate(point.x, point.y);
  context.rotate(angle);
  context.strokeStyle = outcomeColors[edge.outcome];
  context.fillStyle = outcomeColors[edge.outcome];
  context.lineWidth = 2;
  context.shadowColor = outcomeColors[edge.outcome];
  context.shadowBlur = 12 + pulse * 8;
  if (edge.outcome === "BLOCKED") {
    context.beginPath(); context.moveTo(0, -19); context.lineTo(0, 19); context.stroke();
    context.beginPath(); context.moveTo(7, -14); context.lineTo(7, 14); context.stroke();
  } else if (edge.outcome === "ABSORBED") {
    context.globalAlpha = 0.7;
    context.beginPath(); context.arc(0, 0, 18 - pulse * 3, 0, Math.PI * 2); context.stroke();
    context.beginPath(); context.arc(0, 0, 9 - pulse * 2, 0, Math.PI * 2); context.stroke();
    context.beginPath(); context.arc(0, 0, 3, 0, Math.PI * 2); context.fill();
  } else if (edge.outcome === "PARTIALLY_ABSORBED") {
    context.globalAlpha = 0.78;
    context.beginPath(); context.arc(0, 0, 10 + pulse * 3, -Math.PI / 2, Math.PI / 2); context.stroke();
    context.beginPath(); context.arc(1, 0, 3.5, 0, Math.PI * 2); context.fill();
  } else if (edge.outcome === "DELAYED") {
    context.globalAlpha = 0.8;
    context.beginPath(); context.arc(0, 0, 11 + pulse * 4, 0, Math.PI * 2); context.stroke();
    context.beginPath(); context.moveTo(-5, -11); context.lineTo(-5, 11); context.moveTo(5, -11); context.lineTo(5, 11); context.stroke();
  } else if (edge.outcome === "AMPLIFIED") {
    context.globalAlpha = 0.85;
    for (let offset = -8; offset <= 8; offset += 8) {
      context.beginPath(); context.moveTo(offset - 6, -8); context.lineTo(offset + 4, 0); context.lineTo(offset - 6, 8); context.stroke();
    }
  } else if (edge.outcome === "UNKNOWN") {
    context.setLineDash([3, 4]);
    context.beginPath(); context.arc(0, 0, 14, -Math.PI * 0.9, Math.PI * 0.7); context.stroke();
  }
  context.restore();
}

function roundedRect(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
}

function drawNodeSymbol(context: CanvasRenderingContext2D, symbol: StructuralNodeSymbol, accent: string) {
  context.save();
  context.strokeStyle = accent;
  context.fillStyle = accent;
  context.lineWidth = 1.65;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.globalAlpha = 0.94;
  context.beginPath();
  if (symbol === "drop") {
    context.moveTo(0, -7); context.bezierCurveTo(6, -1, 7, 4, 0, 8); context.bezierCurveTo(-7, 4, -6, -1, 0, -7); context.stroke();
  } else if (symbol === "refinery") {
    context.moveTo(-8, 8); context.lineTo(-8, -4); context.lineTo(-3, -4); context.lineTo(-3, 8); context.moveTo(1, 8); context.lineTo(1, -8); context.lineTo(6, -8); context.lineTo(6, 8); context.moveTo(-10, 8); context.lineTo(9, 8); context.stroke();
  } else if (symbol === "tank") {
    context.ellipse(0, -6, 8, 3, 0, 0, Math.PI * 2); context.moveTo(-8, -6); context.lineTo(-8, 6); context.ellipse(0, 6, 8, 3, 0, 0, Math.PI); context.moveTo(8, -6); context.lineTo(8, 6); context.stroke();
  } else if (symbol === "bolt") {
    context.moveTo(2, -9); context.lineTo(-5, 1); context.lineTo(0, 1); context.lineTo(-2, 9); context.lineTo(6, -2); context.lineTo(1, -2); context.closePath(); context.stroke();
  } else if (symbol === "flame") {
    context.moveTo(1, -9); context.bezierCurveTo(7, -2, 7, 5, 0, 9); context.bezierCurveTo(-7, 5, -5, -1, -1, -5); context.bezierCurveTo(-1, -1, 2, 1, 3, 4); context.stroke();
  } else if (symbol === "split") {
    context.moveTo(-8, 0); context.lineTo(-1, 0); context.moveTo(-1, 0); context.lineTo(6, -7); context.moveTo(-1, 0); context.lineTo(6, 7); context.moveTo(6, -7); context.lineTo(3, -7); context.moveTo(6, -7); context.lineTo(6, -4); context.moveTo(6, 7); context.lineTo(3, 7); context.moveTo(6, 7); context.lineTo(6, 4); context.stroke();
  } else if (symbol === "freight") {
    context.rect(-9, -5, 12, 9); context.moveTo(3, -2); context.lineTo(7, -2); context.lineTo(10, 2); context.lineTo(10, 4); context.lineTo(3, 4); context.moveTo(-6, 7); context.arc(-6, 5, 2, 0, Math.PI * 2); context.moveTo(9, 7); context.arc(7, 5, 2, 0, Math.PI * 2); context.stroke();
  } else if (symbol === "factory") {
    context.moveTo(-9, 8); context.lineTo(-9, -3); context.lineTo(-3, 1); context.lineTo(-3, -3); context.lineTo(3, 1); context.lineTo(3, -8); context.lineTo(8, -8); context.lineTo(8, 8); context.closePath(); context.moveTo(-5, 5); context.lineTo(-5, 3); context.moveTo(0, 5); context.lineTo(0, 3); context.stroke();
  } else if (symbol === "people") {
    context.moveTo(-5, -7); context.arc(-5, -5, 2, 0, Math.PI * 2); context.moveTo(5, -7); context.arc(5, -5, 2, 0, Math.PI * 2); context.moveTo(-9, 8); context.bezierCurveTo(-9, 1, -1, 1, -1, 8); context.moveTo(1, 8); context.bezierCurveTo(1, 1, 9, 1, 9, 8); context.stroke();
  } else if (symbol === "labor-market") {
    context.arc(0, 0, 3, 0, Math.PI * 2); context.moveTo(-5, -8); context.arc(-7, -8, 2, 0, Math.PI * 2); context.moveTo(9, -8); context.arc(7, -8, 2, 0, Math.PI * 2); context.moveTo(2, 9); context.arc(0, 9, 2, 0, Math.PI * 2); context.moveTo(-5.5, -6.5); context.lineTo(-2, -2); context.moveTo(5.5, -6.5); context.lineTo(2, -2); context.moveTo(0, 3); context.lineTo(0, 7); context.stroke();
  } else if (symbol === "briefcase") {
    context.rect(-9, -4, 18, 12); context.moveTo(-4, -4); context.lineTo(-4, -8); context.lineTo(4, -8); context.lineTo(4, -4); context.moveTo(-9, 1); context.lineTo(9, 1); context.stroke();
  } else if (symbol === "unemployment") {
    context.arc(0, -5, 3, 0, Math.PI * 2); context.moveTo(-7, 8); context.bezierCurveTo(-7, 0, 7, 0, 7, 8); context.moveTo(-9, -1); context.lineTo(-4, -1); context.stroke();
  } else if (symbol === "participation") {
    context.arc(-6, -6, 2, 0, Math.PI * 2); context.moveTo(2, -7); context.arc(0, -7, 2, 0, Math.PI * 2); context.moveTo(8, -6); context.arc(6, -6, 2, 0, Math.PI * 2); context.moveTo(-6, -2); context.lineTo(-6, 7); context.moveTo(0, -3); context.lineTo(0, 8); context.moveTo(6, -2); context.lineTo(6, 7); context.moveTo(-9, 1); context.lineTo(-3, 1); context.moveTo(-3, 0); context.lineTo(3, 0); context.moveTo(3, 1); context.lineTo(9, 1); context.moveTo(-8, 9); context.lineTo(8, 9); context.stroke();
  } else if (symbol === "claims") {
    context.rect(-7, -9, 14, 18); context.moveTo(-4, -4); context.lineTo(4, -4); context.moveTo(-4, 0); context.lineTo(4, 0); context.moveTo(-4, 4); context.lineTo(2, 4); context.stroke();
  } else if (symbol === "openings") {
    context.rect(-7, -9, 14, 18); context.moveTo(2, 0); context.arc(1, 0, 1, 0, Math.PI * 2); context.stroke();
  } else if (symbol === "hire") {
    context.arc(-3, -5, 3, 0, Math.PI * 2); context.moveTo(-9, 8); context.bezierCurveTo(-9, 0, 3, 0, 3, 8); context.moveTo(5, -2); context.lineTo(5, 6); context.moveTo(1, 2); context.lineTo(9, 2); context.stroke();
  } else if (symbol === "clock") {
    context.arc(0, 0, 9, 0, Math.PI * 2); context.moveTo(0, -5); context.lineTo(0, 1); context.lineTo(5, 4); context.stroke();
  } else if (symbol === "earnings") {
    context.arc(0, 0, 9, 0, Math.PI * 2); context.moveTo(3, -5); context.bezierCurveTo(-5, -8, -5, -1, 1, 0); context.bezierCurveTo(7, 1, 5, 8, -3, 6); context.moveTo(0, -8); context.lineTo(0, 8); context.stroke();
  } else if (symbol === "separations") {
    context.moveTo(-9, 0); context.lineTo(-1, 0); context.moveTo(-1, 0); context.lineTo(7, -7); context.moveTo(-1, 0); context.lineTo(7, 7); context.moveTo(7, -7); context.lineTo(3, -7); context.moveTo(7, -7); context.lineTo(7, -3); context.moveTo(7, 7); context.lineTo(3, 7); context.moveTo(7, 7); context.lineTo(7, 3); context.stroke();
  } else if (symbol === "ratio") {
    context.arc(-5, -5, 3, 0, Math.PI * 2); context.moveTo(8, 5); context.arc(5, 5, 3, 0, Math.PI * 2); context.moveTo(-7, 8); context.lineTo(7, -8); context.stroke();
  } else {
    context.arc(0, 0, 7, 0, Math.PI * 2); context.moveTo(-7, 0); context.lineTo(7, 0); context.moveTo(0, -7); context.lineTo(0, 7); context.stroke();
  }
  context.restore();
}

function drawNodeShape(context: CanvasRenderingContext2D, node: StructuralSurfaceNode, state: string, selected: boolean, hovered: boolean, phase: number, depthVisual: StructuralDepthVisual) {
  const active = state !== "IDLE" && state !== "SIGNAL_READY";
  const visual = resolveStructuralNodeVisual(node);
  const pulse = 0.5 + Math.sin(phase * Math.PI * 2) * 0.5;
  context.save();
  context.translate(node.x, node.y);
  context.scale(depthVisual.scale, depthVisual.scale);
  if (selected) context.scale(1.13, 1.13);
  else if (hovered) context.scale(1.06, 1.06);
  context.globalAlpha = depthVisual.opacity;
  if (selected || hovered || active) {
    context.strokeStyle = selected ? "#f3fff9" : hovered ? visual.accent : state === "DELAYING" ? "#efbc69" : state === "AMPLIFYING" ? "#ffd07a" : visual.accent;
    context.lineWidth = selected ? 2.2 : hovered ? 1.8 : 1.5;
    context.shadowColor = context.strokeStyle;
    context.shadowBlur = selected ? 28 : hovered ? 19 : 16 + pulse * 8;
    context.beginPath(); context.arc(0, 0, selected ? 40 : hovered ? 35 : 33 + pulse * 3, 0, Math.PI * 2); context.stroke();
  }
  context.shadowBlur = 0;
  context.fillStyle = active || hovered || selected ? visual.fill : "#0d202a";
  context.strokeStyle = active || hovered || selected ? visual.accent : `${visual.accent}99`;
  context.lineWidth = 1.7;
  if (node.kind === "INPUT") {
    context.beginPath(); context.arc(0, 0, 18, 0, Math.PI * 2); context.fill(); context.stroke();
  } else if (node.kind === "INDUSTRY") {
    roundedRect(context, -22, -22, 44, 44, 13); context.fill(); context.stroke();
  } else if (node.kind === "BUFFER") {
    roundedRect(context, -21, -28, 42, 56, 15); context.fill(); context.stroke();
    context.save(); roundedRect(context, -15, -22, 30, 44, 10); context.clip();
    context.fillStyle = active ? "rgba(121,231,206,.58)" : "rgba(94,130,143,.28)";
    const fillY = active ? -3 - pulse * 4 : 9;
    context.fillRect(-15, fillY, 30, 29); context.restore();
  } else if (node.kind === "TRANSFER") {
    if (visual.symbol === "freight") roundedRect(context, -25, -19, 50, 38, 13);
    else roundedRect(context, -21, -21, 42, 42, 14);
    context.fill(); context.stroke();
  } else if (node.kind === "HUMAN_CAPITAL") {
    roundedRect(context, -29, -20, 58, 40, 18); context.fill(); context.stroke();
  } else {
    context.beginPath(); context.arc(0, 0, 21, 0, Math.PI * 2); context.fill(); context.stroke();
  }
  drawNodeSymbol(context, visual.symbol, visual.accent);
  context.restore();
}

function seededUnit(seed: string) {
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) hash = Math.imul(hash ^ seed.charCodeAt(index), 16777619);
  return (hash >>> 0) / 4294967295;
}

function drawDepthField(context: CanvasRenderingContext2D, nodes: StructuralSurfaceNode[], depths: Map<string, number>, nowMs: number, parallax: Point, reducedMotion: boolean) {
  for (const node of nodes) {
    const visual = resolveStructuralNodeVisual(node);
    const structuralDepth = depths.get(node.id) ?? 0;
    context.save();
    context.fillStyle = visual.accent;
    context.shadowColor = visual.accent;
    context.strokeStyle = visual.accent;
    context.lineWidth = 0.65;
    context.globalAlpha = Math.max(0.03, 0.075 - structuralDepth * 0.004);
    context.beginPath();
    context.ellipse(node.x + parallax.x * 5, node.y + parallax.y * 3.5, 72, 36, -0.18, 0, Math.PI * 2);
    context.stroke();
    for (let index = 0; index < STRUCTURAL_PARTICLES_PER_NODE; index += 1) {
      const seed = `${node.id}:${index}`;
      const layer = Math.min(10, Math.max(2, structuralDepth + 2 + Math.floor(seededUnit(`${seed}:layer`) * 7)));
      const baseAngle = seededUnit(`${seed}:angle`) * Math.PI * 2;
      const drift = reducedMotion ? 0 : nowMs * (0.000018 + seededUnit(`${seed}:speed`) * 0.000025) * (index % 2 ? -1 : 1);
      const radius = 38 + seededUnit(`${seed}:radius`) * 124;
      const x = node.x + Math.cos(baseAngle + drift) * radius + parallax.x * layer * 3.8;
      const y = node.y + Math.sin(baseAngle + drift) * radius * 0.58 + parallax.y * layer * 2.9;
      const particleRadius = Math.max(0.8, 2.2 - layer * 0.105);
      context.globalAlpha = Math.max(0.065, 0.18 - layer * 0.01);
      context.shadowBlur = Math.max(3, 10 - layer * 0.5);
      context.beginPath();
      context.arc(x, y, particleRadius, 0, Math.PI * 2);
      context.fill();
    }
    context.restore();
  }
}

function drawConcentricOrbitGuides(context: CanvasRenderingContext2D, nodes: StructuralSurfaceNode[], centerNodeId: string, selectedNodeId: string | null, traceMode: boolean) {
  if (selectedNodeId || traceMode) return;
  const center = nodes.find((node) => node.id === centerNodeId);
  const orbitNodes = nodes.filter((node) => node.id !== centerNodeId);
  if (!center || orbitNodes.length < 3) return;
  const radius = orbitNodes.reduce((sum, node) => sum + Math.hypot(node.x - center.x, node.y - center.y), 0) / orbitNodes.length;

  context.save();
  const glow = context.createRadialGradient(center.x, center.y, 18, center.x, center.y, radius * 1.48);
  glow.addColorStop(0, "rgba(225,117,190,.075)");
  glow.addColorStop(0.34, "rgba(107,231,205,.018)");
  glow.addColorStop(0.68, "rgba(107,231,205,.026)");
  glow.addColorStop(1, "rgba(107,231,205,0)");
  context.fillStyle = glow;
  context.beginPath();
  context.arc(center.x, center.y, radius * 1.48, 0, Math.PI * 2);
  context.fill();

  context.lineWidth = 0.75;
  for (const node of orbitNodes) {
    context.strokeStyle = "rgba(126,202,196,.045)";
    context.setLineDash([2, 9]);
    context.beginPath();
    context.moveTo(center.x, center.y);
    context.lineTo(node.x, node.y);
    context.stroke();
  }

  context.setLineDash([]);
  context.strokeStyle = "rgba(126,225,209,.085)";
  context.lineWidth = 1;
  context.beginPath();
  context.arc(center.x, center.y, radius, 0, Math.PI * 2);
  context.stroke();

  context.setLineDash([2, 7]);
  context.strokeStyle = "rgba(126,225,209,.045)";
  context.beginPath();
  context.arc(center.x, center.y, Math.hypot(radius + 88, 54), 0, Math.PI * 2);
  context.stroke();

  context.setLineDash([]);
  context.strokeStyle = "rgba(225,117,190,.14)";
  context.beginPath();
  context.arc(center.x, center.y, 64, 0, Math.PI * 2);
  context.stroke();
  context.restore();
}

export class CanvasStructuralRenderer implements StructuralRenderer {
  private readonly canvas: HTMLCanvasElement;
  private readonly context: CanvasRenderingContext2D;
  private width = 1;
  private height = 1;
  private density = 1;
  private camera: StructuralCamera | null = null;
  private cameraFrom: StructuralCamera | null = null;
  private cameraTarget: StructuralCamera | null = null;
  private cameraKey = "";
  private cameraStartedAt = 0;
  private layoutCurrent: Map<string, Point> | null = null;
  private layoutFrom: Map<string, Point> | null = null;
  private layoutTarget: Map<string, Point> | null = null;
  private layoutKey = "";
  private layoutStartedAt = 0;
  private readonly hoverVisuals = new Map<string, { alpha: number; emphasis: number; accent: string }>();
  private lastRenderAt = 0;
  private parallax: SpringParallaxState = { position: { x: 0, y: 0 }, velocity: { x: 0, y: 0 } };

  constructor(canvas: HTMLCanvasElement, context: CanvasRenderingContext2D) {
    this.canvas = canvas;
    this.context = context;
  }

  resize(width: number, height: number, density: number) {
    this.width = Math.max(1, width);
    this.height = Math.max(1, height);
    this.density = Math.min(2, Math.max(1, density));
    this.canvas.width = Math.round(this.width * this.density);
    this.canvas.height = Math.round(this.height * this.density);
  }

  render(state: StructuralRenderState) {
    const context = this.context;
    const frameElapsed = this.lastRenderAt ? state.nowMs - this.lastRenderAt : 16.67;
    this.lastRenderAt = state.nowMs;
    this.parallax = stepSpringParallax(this.parallax, state.parallaxTarget, frameElapsed, state.reducedMotion);
    const targetPositions = new Map(state.model.nodes.map((node) => [node.id, { x: node.x, y: node.y }]));
    const nextLayoutKey = `${state.selectedNodeId ?? "overview"}:${state.focusDepth}:${[...state.visibleRelationshipIds].sort().join(",")}`;
    if (!this.layoutCurrent) this.layoutCurrent = targetPositions;
    if (nextLayoutKey !== this.layoutKey) {
      this.layoutFrom = new Map(this.layoutCurrent);
      this.layoutTarget = targetPositions;
      this.layoutStartedAt = state.nowMs;
      this.layoutKey = nextLayoutKey;
    }
    const layoutProgress = state.reducedMotion ? 1 : Math.max(0, Math.min(1, (state.nowMs - this.layoutStartedAt) / 520));
    const layoutEased = 1 - (1 - layoutProgress) ** 3;
    this.layoutCurrent = new Map(state.model.nodes.map((node) => {
      const from = this.layoutFrom?.get(node.id) ?? targetPositions.get(node.id)!;
      const to = this.layoutTarget?.get(node.id) ?? targetPositions.get(node.id)!;
      return [node.id, { x: from.x + (to.x - from.x) * layoutEased, y: from.y + (to.y - from.y) * layoutEased }];
    }));
    const renderNodes = state.model.nodes.map((node) => ({ ...node, ...this.layoutCurrent!.get(node.id)! }));
    const nodes = new Map(renderNodes.map((node) => [node.id, node]));
    const selectedTarget = state.cameraFocusNodeId ? state.model.nodes.find((node) => node.id === state.cameraFocusNodeId) : undefined;
    const targetCamera = createStructuralCamera(this.width, this.height, selectedTarget, state.focusDepth);
    const nextCameraKey = `${state.selectedNodeId ?? "overview"}:${state.focusDepth}:${Math.round(this.width)}:${Math.round(this.height)}`;
    if (!this.camera) this.camera = targetCamera;
    if (nextCameraKey !== this.cameraKey) {
      this.cameraFrom = this.camera;
      this.cameraTarget = targetCamera;
      this.cameraStartedAt = state.nowMs;
      this.cameraKey = nextCameraKey;
    }
    const cameraProgress = state.reducedMotion ? 1 : (state.nowMs - this.cameraStartedAt) / STRUCTURAL_CAMERA_TRANSITION_MS;
    this.camera = state.reducedMotion || !this.cameraFrom || !this.cameraTarget ? targetCamera : interpolateCamera(this.cameraFrom, this.cameraTarget, cameraProgress);
    const camera = applyStructuralViewport(this.camera, this.width, this.height, state.viewportTransform);
    const rawProgress = state.reducedMotion ? 1 : Math.min(1, state.elapsedMs / 680);
    const phase = state.reducedMotion ? 0.35 : (state.elapsedMs % 1800) / 1800;

    context.setTransform(this.density, 0, 0, this.density, 0, 0);
    context.clearRect(0, 0, this.width, this.height);
    const backdrop = context.createRadialGradient(this.width * 0.54, this.height * 0.46, 0, this.width * 0.54, this.height * 0.46, this.width * 0.72);
    backdrop.addColorStop(0, "#0b2530"); backdrop.addColorStop(0.48, "#071821"); backdrop.addColorStop(1, "#041018");
    context.fillStyle = backdrop; context.fillRect(0, 0, this.width, this.height);
    context.strokeStyle = "rgba(116,178,187,.045)"; context.lineWidth = 1;
    for (let x = 24; x < this.width; x += 48) { context.beginPath(); context.moveTo(x, 0); context.lineTo(x, this.height); context.stroke(); }
    for (let y = 24; y < this.height; y += 48) { context.beginPath(); context.moveTo(0, y); context.lineTo(this.width, y); context.stroke(); }
    const vignette = context.createLinearGradient(0, 0, this.width, this.height);
    vignette.addColorStop(0, "rgba(4,12,18,.3)"); vignette.addColorStop(0.5, "rgba(4,12,18,0)"); vignette.addColorStop(1, "rgba(4,12,18,.55)");
    context.fillStyle = vignette; context.fillRect(0, 0, this.width, this.height);

    context.save();
    context.translate(camera.offsetX, camera.offsetY);
    context.scale(camera.scale, camera.scale);

    const structuralDepths = resolveStructuralDepths(state.model, state.traceMode ? null : state.selectedNodeId);
    drawConcentricOrbitGuides(context, renderNodes, state.centerNodeId, state.selectedNodeId, state.traceMode);
    drawDepthField(context, renderNodes, structuralDepths, state.nowMs, this.parallax.position, state.reducedMotion);

    if (state.traceMode) this.hoverVisuals.clear();
    for (const [edgeIndex, edge] of state.model.relationships.entries()) {
      if (!state.visibleRelationshipIds.has(edge.id)) continue;
      const points = sampleRelationship(edge, nodes);
      const isPath = state.pathEdgeIds.has(edge.id);
      const isComplete = state.completedEdgeIds.has(edge.id);
      const edgeDepth = ((structuralDepths.get(edge.from) ?? 0) + (structuralDepths.get(edge.to) ?? 0)) / 2;
      const edgeDepthVisual = resolveStructuralDepthVisual(edgeDepth, isPath || isComplete);
      const isHoverRelated = !state.hoveredNodeId || edge.from === state.hoveredNodeId || edge.to === state.hoveredNodeId;
      const hoveredNode = state.hoveredNodeId ? nodes.get(state.hoveredNodeId) : undefined;
      const previousHover = this.hoverVisuals.get(edge.id) ?? { alpha: 0.34, emphasis: 0, accent: "#75c9bd" };
      const targetHover = state.hoveredNodeId ? { alpha: isHoverRelated ? 0.34 : 0.07, emphasis: isHoverRelated ? 1 : 0 } : { alpha: 0.34, emphasis: 0 };
      const hoverVisual = state.traceMode ? previousHover : {
        alpha: easeConnectorHover(previousHover.alpha, targetHover.alpha, frameElapsed, state.reducedMotion),
        emphasis: easeConnectorHover(previousHover.emphasis, targetHover.emphasis, frameElapsed, state.reducedMotion),
        accent: hoveredNode && isHoverRelated ? resolveStructuralNodeVisual(hoveredNode).accent : previousHover.accent
      };
      if (!state.traceMode) this.hoverVisuals.set(edge.id, hoverVisual);
      const alpha = (state.traceMode ? (isPath ? 0.6 : 0.04) : hoverVisual.alpha) * edgeDepthVisual.opacity;
      const primaryColor = blendConnectorColor("#568491", hoverVisual.accent, hoverVisual.emphasis, alpha);
      const innerColor = blendConnectorColor("#7eaab4", hoverVisual.accent, hoverVisual.emphasis, alpha * 1.25);
      const arrowColor = blendConnectorColor("#486a75", hoverVisual.accent, hoverVisual.emphasis);
      const glintColor = blendConnectorColor("#75c9bd", hoverVisual.accent, hoverVisual.emphasis);
      tracePoints(context, points);
      context.strokeStyle = isComplete ? "rgba(105,198,178,.55)" : primaryColor;
      const hierarchyTether = edge.relationshipClass === "HIERARCHY";
      context.lineWidth = isPath ? 8 : ((hierarchyTether ? 2.8 : 5) + hoverVisual.emphasis * 1.5) * edgeDepthVisual.scale;
      context.lineCap = "round";
      context.stroke();
      tracePoints(context, points);
      context.strokeStyle = isComplete ? "rgba(146,237,215,.52)" : innerColor;
      context.lineWidth = 1.15;
      context.stroke();
      if (!hierarchyTether && (isPath || !state.traceMode)) drawArrow(context, points, 0.9, isPath ? "#719d9f" : arrowColor, isPath ? 0.68 : 0.36 + hoverVisual.emphasis * 0.34);
      if (!state.traceMode && !state.reducedMotion) {
        const glint = connectorGlintProgress(state.nowMs, edgeIndex);
        const start = Math.max(0, glint - 0.08);
        context.save();
        context.lineCap = "round";
        context.shadowColor = glintColor;
        context.shadowBlur = 7 + hoverVisual.emphasis * 8;
        context.globalAlpha = 0.3 + hoverVisual.emphasis * 0.58;
        context.strokeStyle = glintColor;
        context.lineWidth = 1.7 + hoverVisual.emphasis * 1.5;
        tracePoints(context, points, start, glint);
        context.stroke();
        context.restore();
      }
    }

    for (const edge of state.currentEdges) {
      if (!state.visibleRelationshipIds.has(edge.id)) continue;
      const points = sampleRelationship(edge, nodes);
      const travel = outcomeTravel(edge.outcome, rawProgress);
      const color = outcomeColors[edge.outcome];
      const from = nodes.get(edge.from)!;
      const to = nodes.get(edge.to)!;
      const gradient = context.createLinearGradient(from.x, from.y, to.x, to.y);
      gradient.addColorStop(0, "rgba(132,241,213,.45)"); gradient.addColorStop(0.55, color); gradient.addColorStop(1, color);
      context.save();
      context.lineCap = "round";
      context.shadowColor = color;
      context.shadowBlur = edge.outcome === "AMPLIFIED" ? 26 : 17;
      if (edge.outcome === "PARTIALLY_ABSORBED") {
        tracePoints(context, points, 0, Math.min(travel, 0.67)); context.strokeStyle = gradient; context.lineWidth = 10; context.globalAlpha = 0.88; context.stroke();
        if (travel > 0.67) { tracePoints(context, points, 0.67, travel); context.lineWidth = 3.3; context.globalAlpha = 1; context.stroke(); }
      } else if (edge.outcome === "AMPLIFIED") {
        tracePoints(context, points, 0, Math.min(travel, 0.54)); context.strokeStyle = gradient; context.lineWidth = 4.5; context.stroke();
        if (travel > 0.54) { tracePoints(context, points, 0.54, travel); context.strokeStyle = gradient; context.lineWidth = 8.5 + phase * 2; context.stroke(); }
      } else {
        tracePoints(context, points, 0, travel); context.strokeStyle = gradient; context.lineWidth = edge.outcome === "BLOCKED" ? 6 : edge.outcome === "ABSORBED" ? 8 - rawProgress * 5 : 5.5; context.globalAlpha = edge.outcome === "UNKNOWN" ? 0.58 : 0.96; context.stroke();
      }
      context.restore();
      if (rawProgress > 0.38) drawOutcomeMarker(context, points, edge, phase);
      if (!["BLOCKED", "ABSORBED", "UNKNOWN"].includes(edge.outcome)) drawArrow(context, points, Math.max(0.15, Math.min(0.95, travel)), color, 0.92);
    }

    if (state.traceMode && state.commonOriginNodeId && state.visibleNodeIds.has(state.commonOriginNodeId)) {
      const origin = nodes.get(state.commonOriginNodeId)!;
      context.save(); context.translate(origin.x, origin.y); context.strokeStyle = "rgba(137,246,220,.72)"; context.lineWidth = 1.5; context.setLineDash([2, 5]); context.beginPath(); context.arc(0, 0, 43 + phase * 3, 0, Math.PI * 2); context.stroke(); context.restore();
    }
    if (state.traceMode && state.reconciliationTargetId && state.visibleNodeIds.has(state.reconciliationTargetId)) {
      const target = nodes.get(state.reconciliationTargetId)!;
      context.save(); context.translate(target.x, target.y); context.strokeStyle = "rgba(255,208,122,.85)"; context.lineWidth = 2; context.beginPath(); context.arc(0, 0, 42 - phase * 5, 0, Math.PI * 2); context.stroke(); context.restore();
    }

    const pathNodes = new Set(state.model.relationships.filter((edge) => state.pathEdgeIds.has(edge.id)).flatMap((edge) => [edge.from, edge.to]));
    for (const node of renderNodes) {
      if (!state.visibleNodeIds.has(node.id)) continue;
      const visible = !state.traceMode || pathNodes.has(node.id) || state.selectedNodeId === node.id;
      if (!visible) continue;
      const emphasized = state.selectedNodeId === node.id || state.hoveredNodeId === node.id || (!state.selectedNodeId && node.id === state.centerNodeId) || (state.traceMode && pathNodes.has(node.id));
      const depthVisual = resolveStructuralDepthVisual(structuralDepths.get(node.id) ?? 0, emphasized);
      drawNodeShape(context, node, state.nodeStates.get(node.id) ?? "IDLE", state.selectedNodeId === node.id, state.hoveredNodeId === node.id, phase, depthVisual);
    }
    context.restore();
  }

  destroy() {
    this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
}
