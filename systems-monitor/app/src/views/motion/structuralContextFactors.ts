import type { MotionQaNode } from "../../data/motionQaReadModel";
import { projectNode, type StructuralCamera } from "./structuralRenderer";

export interface StructuralContextFactor {
  id: string;
  parentNodeId: string;
  label: string;
  offsetX: number;
  offsetY: number;
  depthOffset: number;
}

export interface PositionedStructuralContextFactor extends StructuralContextFactor {
  x: number;
  y: number;
  parentX: number;
  parentY: number;
  visualDepth: number;
}

export const structuralContextFactors: StructuralContextFactor[] = [
  { id: "context-domestic-output", parentNodeId: "fixture-origin", label: "Domestic output", offsetX: 42, offsetY: -46, depthOffset: 2 },
  { id: "context-import-flow", parentNodeId: "fixture-origin", label: "Import flow", offsetX: 42, offsetY: 46, depthOffset: 3 },
  { id: "context-utilization", parentNodeId: "fixture-producer", label: "Refinery utilization", offsetX: 0, offsetY: -58, depthOffset: 2 },
  { id: "context-maintenance", parentNodeId: "fixture-producer", label: "Maintenance capacity", offsetX: 0, offsetY: 58, depthOffset: 4 },
  { id: "context-inventory", parentNodeId: "fixture-buffer", label: "Inventory level", offsetX: -4, offsetY: -60, depthOffset: 2 },
  { id: "context-headroom", parentNodeId: "fixture-buffer", label: "Storage headroom", offsetX: -4, offsetY: 60, depthOffset: 4 },
  { id: "context-power-cost", parentNodeId: "fixture-branch-a", label: "Power cost", offsetX: -44, offsetY: -46, depthOffset: 3 },
  { id: "context-grid-reliability", parentNodeId: "fixture-branch-a", label: "Grid reliability", offsetX: 44, offsetY: -46, depthOffset: 5 },
  { id: "context-output-mix", parentNodeId: "fixture-branch-b", label: "Output mix", offsetX: -44, offsetY: 46, depthOffset: 3 },
  { id: "context-product-stocks", parentNodeId: "fixture-branch-b", label: "Product stocks", offsetX: 44, offsetY: 46, depthOffset: 5 },
  { id: "context-terminal-flow", parentNodeId: "fixture-junction", label: "Terminal flow", offsetX: 0, offsetY: -60, depthOffset: 2 },
  { id: "context-pipeline-room", parentNodeId: "fixture-junction", label: "Pipeline capacity", offsetX: 0, offsetY: 60, depthOffset: 4 },
  { id: "context-rail-throughput", parentNodeId: "fixture-transport", label: "Rail throughput", offsetX: 0, offsetY: -58, depthOffset: 2 },
  { id: "context-truck-capacity", parentNodeId: "fixture-transport", label: "Truck capacity", offsetX: 0, offsetY: 58, depthOffset: 4 },
  { id: "context-new-orders", parentNodeId: "fixture-downstream", label: "New orders", offsetX: -44, offsetY: -46, depthOffset: 2 },
  { id: "context-capacity-use", parentNodeId: "fixture-downstream", label: "Capacity use", offsetX: 44, offsetY: -46, depthOffset: 4 },
  { id: "context-hours-worked", parentNodeId: "fixture-employment", label: "Hours worked", offsetX: -44, offsetY: 46, depthOffset: 2 },
  { id: "context-hiring-demand", parentNodeId: "fixture-employment", label: "Hiring demand", offsetX: 44, offsetY: 46, depthOffset: 3 }
];

export function contextFactorsForNode(nodeId: string) {
  return structuralContextFactors.filter((factor) => factor.parentNodeId === nodeId);
}

export function layoutStructuralContextFactors(nodes: MotionQaNode[], camera: StructuralCamera, depths: Map<string, number>, visibleNodeIds: Set<string>) {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  return structuralContextFactors.flatMap((factor): PositionedStructuralContextFactor[] => {
    const parent = nodeMap.get(factor.parentNodeId);
    if (!parent || !visibleNodeIds.has(parent.id)) return [];
    const parentPoint = projectNode(parent, camera);
    const factorPoint = projectNode({ ...parent, x: parent.x + factor.offsetX, y: parent.y + factor.offsetY }, camera);
    return [{ ...factor, x: factorPoint.x, y: factorPoint.y, parentX: parentPoint.x, parentY: parentPoint.y, visualDepth: Math.min(10, (depths.get(parent.id) ?? 0) + factor.depthOffset) }];
  });
}
