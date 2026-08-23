import type { MotionQaNode, MotionQaReadModel, MotionQaRelationship } from "../../data/motionQaReadModel";
import type { Point, StructuralCamera } from "./structuralRenderer";
import { projectNode } from "./structuralRenderer";

export const MAX_VISIBLE_RELATIONSHIPS = 10;

export interface SpatialViewport {
  focusNodeId: string | null;
  visibleNodeIds: Set<string>;
  visibleRelationshipIds: Set<string>;
  availableRelationshipCount: number;
  additionalRelationshipCount: number;
}

export type LabelPriority = "PRIMARY" | "CONTEXT" | "DETAIL";
export type LabelSide = "below" | "above" | "right" | "left";

export interface SpatialLabelPlacement {
  nodeId: string;
  text: string;
  priority: LabelPriority;
  side: LabelSide;
  x: number;
  y: number;
  width: number;
  height: number;
  suppressed: boolean;
}

interface LabelLayoutOptions {
  nodes: MotionQaNode[];
  camera: StructuralCamera;
  width: number;
  height: number;
  focusDepth: number;
  selectedNodeId: string | null;
  visibleNodeIds: Set<string>;
  traceNodeIds: Set<string>;
}

const relationshipKey = (edge: MotionQaRelationship, nodes: Map<string, MotionQaNode>) => {
  const endpoint = nodes.get(edge.to)?.displayRank ?? nodes.get(edge.from)?.displayRank ?? Number.MAX_SAFE_INTEGER;
  return `${String(endpoint).padStart(4, "0")}:${edge.id}`;
};

export function resolveSpatialViewport(model: MotionQaReadModel, focusNodeId: string | null, preferredEdgeIds: Set<string>, limit = MAX_VISIBLE_RELATIONSHIPS): SpatialViewport {
  const nodes = new Map(model.nodes.map((node) => [node.id, node]));
  const boundedLimit = Math.max(1, limit);
  const candidates = focusNodeId
    ? model.relationships.filter((edge) => preferredEdgeIds.has(edge.id) || edge.from === focusNodeId || edge.to === focusNodeId)
    : model.relationships;
  const ranked = [...candidates].sort((left, right) => {
    const preferredDelta = Number(preferredEdgeIds.has(right.id)) - Number(preferredEdgeIds.has(left.id));
    return preferredDelta || relationshipKey(left, nodes).localeCompare(relationshipKey(right, nodes));
  });
  const selected = ranked.slice(0, boundedLimit);
  const visibleNodeIds = new Set<string>();
  if (focusNodeId) visibleNodeIds.add(focusNodeId);
  selected.forEach((edge) => { visibleNodeIds.add(edge.from); visibleNodeIds.add(edge.to); });
  if (!focusNodeId) {
    model.nodes
      .slice()
      .sort((left, right) => left.displayRank - right.displayRank || left.id.localeCompare(right.id))
      .slice(0, 10)
      .forEach((node) => visibleNodeIds.add(node.id));
  }
  return {
    focusNodeId,
    visibleNodeIds,
    visibleRelationshipIds: new Set(selected.map((edge) => edge.id)),
    availableRelationshipCount: candidates.length,
    additionalRelationshipCount: Math.max(0, candidates.length - selected.length)
  };
}

export function nodeLabelAtDepth(node: MotionQaNode, focusDepth: number, selected: boolean) {
  if (focusDepth === 0) return node.overviewLabel;
  if (focusDepth > 1 && selected) return node.detailLabel;
  return node.label;
}

function sidePositions(count: number, side: "upstream" | "downstream") {
  if (!count) return [];
  const x = side === "upstream" ? 272 : 728;
  const spacing = count <= 3 ? 142 : count === 4 ? 112 : 88;
  return Array.from({ length: count }, (_, index) => ({ x, y: 310 + (index - (count - 1) / 2) * spacing }));
}

export function layoutSpatialNodes(model: MotionQaReadModel, viewport: SpatialViewport): MotionQaNode[] {
  if (!viewport.focusNodeId) return model.nodes.map((node) => ({ ...node }));
  const relationships = model.relationships.filter((edge) => viewport.visibleRelationshipIds.has(edge.id));
  const upstreamIds = [...new Set(relationships.filter((edge) => edge.to === viewport.focusNodeId).map((edge) => edge.from))];
  const downstreamIds = [...new Set(relationships.filter((edge) => edge.from === viewport.focusNodeId).map((edge) => edge.to))];
  const rank = (left: string, right: string) => {
    const leftNode = model.nodes.find((node) => node.id === left);
    const rightNode = model.nodes.find((node) => node.id === right);
    return (leftNode?.displayRank ?? 999) - (rightNode?.displayRank ?? 999) || left.localeCompare(right);
  };
  upstreamIds.sort(rank); downstreamIds.sort(rank);
  const positions = new Map<string, Point>([[viewport.focusNodeId, { x: 500, y: 310 }]]);
  sidePositions(upstreamIds.length, "upstream").forEach((position, index) => positions.set(upstreamIds[index], position));
  sidePositions(downstreamIds.length, "downstream").forEach((position, index) => positions.set(downstreamIds[index], position));
  return model.nodes.map((node) => ({ ...node, ...(positions.get(node.id) ?? {}) }));
}

interface Box { left: number; top: number; right: number; bottom: number }

const intersects = (left: Box, right: Box, gap = 7) => !(left.right + gap <= right.left || left.left >= right.right + gap || left.bottom + gap <= right.top || left.top >= right.bottom + gap);

function candidateBox(point: Point, side: LabelSide, width: number, height: number): Box {
  const offset = 31;
  if (side === "below") return { left: point.x - width / 2, top: point.y + offset, right: point.x + width / 2, bottom: point.y + offset + height };
  if (side === "above") return { left: point.x - width / 2, top: point.y - offset - height, right: point.x + width / 2, bottom: point.y - offset };
  if (side === "right") return { left: point.x + offset, top: point.y - height / 2, right: point.x + offset + width, bottom: point.y + height / 2 };
  return { left: point.x - offset - width, top: point.y - height / 2, right: point.x - offset, bottom: point.y + height / 2 };
}

function boxCenter(box: Box) {
  return { x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2 };
}

export function layoutSpatialLabels({ nodes, camera, width, height, focusDepth, selectedNodeId, visibleNodeIds, traceNodeIds }: LabelLayoutOptions): SpatialLabelPlacement[] {
  const priority = (node: MotionQaNode): LabelPriority => node.id === selectedNodeId ? "PRIMARY" : traceNodeIds.has(node.id) ? "CONTEXT" : "DETAIL";
  const ordered = nodes
    .filter((node) => visibleNodeIds.has(node.id))
    .sort((left, right) => {
      const order = { PRIMARY: 0, CONTEXT: 1, DETAIL: 2 };
      return order[priority(left)] - order[priority(right)] || left.displayRank - right.displayRank || left.id.localeCompare(right.id);
    });
  const occupied: Box[] = [];
  const nodeZones = ordered.map((node) => {
    const point = projectNode(node, camera);
    return { nodeId: node.id, box: { left: point.x - 25, top: point.y - 25, right: point.x + 25, bottom: point.y + 25 } };
  });
  return ordered.map((node) => {
    const point = projectNode(node, camera);
    const nodePriority = priority(node);
    const text = nodeLabelAtDepth(node, focusDepth, node.id === selectedNodeId);
    const labelWidth = Math.min(node.id === selectedNodeId ? 194 : 164, Math.max(68, text.length * 7.15 + 22));
    const labelHeight = node.id === selectedNodeId ? 31 : 26;
    const candidates: LabelSide[] = ["below", "above", "right", "left"];
    const chosen = candidates.map((side) => ({ side, box: candidateBox(point, side, labelWidth, labelHeight) })).find(({ box }) => {
      const inBounds = box.left >= 14 && box.right <= width - 14 && box.top >= 14 && box.bottom <= height - 14;
      const clearsNodes = nodeZones.every((zone) => zone.nodeId === node.id || !intersects(box, zone.box, 3));
      return inBounds && clearsNodes && occupied.every((placed) => !intersects(box, placed));
    });
    if (!chosen && nodePriority !== "PRIMARY") {
      return { nodeId: node.id, text, priority: nodePriority, side: "below", x: point.x, y: point.y + 31, width: labelWidth, height: labelHeight, suppressed: true };
    }
    const fallbackBox = chosen?.box ?? {
      left: Math.max(14, Math.min(width - 14 - labelWidth, point.x - labelWidth / 2)),
      top: Math.max(14, Math.min(height - 14 - labelHeight, point.y + 31)),
      right: 0,
      bottom: 0
    };
    if (!chosen) { fallbackBox.right = fallbackBox.left + labelWidth; fallbackBox.bottom = fallbackBox.top + labelHeight; }
    occupied.push(fallbackBox);
    const center = boxCenter(fallbackBox);
    return { nodeId: node.id, text, priority: nodePriority, side: chosen?.side ?? "below", x: center.x, y: center.y, width: labelWidth, height: labelHeight, suppressed: false };
  });
}

export function nextNodeInDirection(nodes: MotionQaNode[], visibleNodeIds: Set<string>, currentNodeId: string, key: "ArrowLeft" | "ArrowRight" | "ArrowUp" | "ArrowDown") {
  const current = nodes.find((node) => node.id === currentNodeId);
  if (!current) return null;
  const candidates = nodes.filter((node) => node.id !== currentNodeId && visibleNodeIds.has(node.id)).map((node) => {
    const dx = node.x - current.x;
    const dy = node.y - current.y;
    const forward = key === "ArrowLeft" ? -dx : key === "ArrowRight" ? dx : key === "ArrowUp" ? -dy : dy;
    const lateral = key === "ArrowLeft" || key === "ArrowRight" ? Math.abs(dy) : Math.abs(dx);
    return { node, forward, score: Math.hypot(dx, dy) + lateral * 0.65 };
  }).filter((candidate) => candidate.forward > 0).sort((left, right) => left.score - right.score || left.node.id.localeCompare(right.node.id));
  return candidates[0]?.node.id ?? null;
}
