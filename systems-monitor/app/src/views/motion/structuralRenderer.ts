import type { MotionOutcome, MotionQaNode, MotionQaReadModel, MotionQaRelationship } from "../../data/motionQaReadModel";

export interface StructuralCamera {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export interface StructuralRenderState {
  model: MotionQaReadModel;
  currentEdges: MotionQaRelationship[];
  completedEdgeIds: Set<string>;
  pathEdgeIds: Set<string>;
  nodeStates: Map<string, string>;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
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

export function createStructuralCamera(width: number, height: number, selected?: MotionQaNode, focusDepth = 0): StructuralCamera {
  const baseScale = Math.min((width - 52) / DESIGN_WIDTH, (height - 44) / DESIGN_HEIGHT);
  const scale = baseScale * (selected ? Math.min(1.3, 1.16 + Math.max(0, focusDepth - 1) * 0.06) : 1);
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
  const eased = 1 - (1 - clamped) ** 3;
  return {
    scale: from.scale + (to.scale - from.scale) * eased,
    offsetX: from.offsetX + (to.offsetX - from.offsetX) * eased,
    offsetY: from.offsetY + (to.offsetY - from.offsetY) * eased
  };
}

export function projectNode(node: MotionQaNode, camera: StructuralCamera): Point {
  return { x: camera.offsetX + node.x * camera.scale, y: camera.offsetY + node.y * camera.scale };
}

export function sampleRelationship(edge: MotionQaRelationship, nodes: Map<string, MotionQaNode>, count = 64): Point[] {
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

function drawNodeShape(context: CanvasRenderingContext2D, node: MotionQaNode, state: string, selected: boolean, hovered: boolean, phase: number) {
  const active = state !== "IDLE" && state !== "SIGNAL_READY";
  const pulse = 0.5 + Math.sin(phase * Math.PI * 2) * 0.5;
  context.save();
  context.translate(node.x, node.y);
  if (hovered) context.scale(1.06, 1.06);
  context.globalAlpha = 1;
  if (selected || hovered || active) {
    context.strokeStyle = selected ? "#a8ffe8" : hovered ? "#8ef4dc" : state === "DELAYING" ? "#efbc69" : state === "AMPLIFYING" ? "#ffd07a" : "#79e7ce";
    context.lineWidth = selected ? 2.2 : hovered ? 1.8 : 1.5;
    context.shadowColor = context.strokeStyle;
    context.shadowBlur = selected ? 28 : hovered ? 19 : 16 + pulse * 8;
    context.beginPath(); context.arc(0, 0, selected ? 40 : hovered ? 35 : 33 + pulse * 3, 0, Math.PI * 2); context.stroke();
  }
  context.shadowBlur = 0;
  context.fillStyle = active ? "#163b3a" : "#0d202a";
  context.strokeStyle = active ? "#76d9c5" : "#47636f";
  context.lineWidth = 1.7;
  if (node.kind === "INPUT") {
    context.beginPath(); context.arc(0, 0, 12, 0, Math.PI * 2); context.fill(); context.stroke();
  } else if (node.kind === "INDUSTRY") {
    roundedRect(context, -19, -19, 38, 38, 12); context.fill(); context.stroke();
  } else if (node.kind === "BUFFER") {
    roundedRect(context, -18, -25, 36, 50, 14); context.fill(); context.stroke();
    context.save(); roundedRect(context, -13, -20, 26, 40, 9); context.clip();
    context.fillStyle = active ? "rgba(121,231,206,.58)" : "rgba(94,130,143,.28)";
    const fillY = active ? -3 - pulse * 4 : 9;
    context.fillRect(-13, fillY, 26, 26); context.restore();
  } else if (node.kind === "TRANSFER") {
    roundedRect(context, -10, -25, 20, 50, 9); context.fill(); context.stroke();
  } else if (node.kind === "HUMAN_CAPITAL") {
    roundedRect(context, -25, -16, 50, 32, 16); context.fill(); context.stroke();
  } else {
    context.beginPath(); context.arc(0, 0, 18, 0, Math.PI * 2); context.fill(); context.stroke();
  }
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
    const cameraProgress = state.reducedMotion ? 1 : (state.nowMs - this.cameraStartedAt) / 520;
    this.camera = state.reducedMotion || !this.cameraFrom || !this.cameraTarget ? targetCamera : interpolateCamera(this.cameraFrom, this.cameraTarget, cameraProgress);
    const camera = this.camera;
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

    for (const edge of state.model.relationships) {
      if (!state.visibleRelationshipIds.has(edge.id)) continue;
      const points = sampleRelationship(edge, nodes);
      const isPath = state.pathEdgeIds.has(edge.id);
      const isComplete = state.completedEdgeIds.has(edge.id);
      const isHoverRelated = !state.hoveredNodeId || edge.from === state.hoveredNodeId || edge.to === state.hoveredNodeId;
      const alpha = state.traceMode ? (isPath ? 0.6 : 0.04) : isHoverRelated ? 0.34 : 0.07;
      tracePoints(context, points);
      context.strokeStyle = isComplete ? "rgba(105,198,178,.55)" : `rgba(86,132,145,${alpha})`;
      context.lineWidth = isPath ? 8 : isHoverRelated && state.hoveredNodeId ? 6.5 : 5;
      context.lineCap = "round";
      context.stroke();
      tracePoints(context, points);
      context.strokeStyle = isComplete ? "rgba(146,237,215,.52)" : `rgba(126,170,180,${alpha * 1.25})`;
      context.lineWidth = 1.15;
      context.stroke();
      if (isPath || !state.traceMode) drawArrow(context, points, 0.9, isPath ? "#719d9f" : isHoverRelated && state.hoveredNodeId ? "#79d8c7" : "#486a75", isPath ? 0.68 : isHoverRelated && state.hoveredNodeId ? 0.7 : 0.36);
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
      drawNodeShape(context, node, state.nodeStates.get(node.id) ?? "IDLE", state.selectedNodeId === node.id, state.hoveredNodeId === node.id, phase);
    }
    context.restore();
  }

  destroy() {
    this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
}
