import type { MotionQaNode } from "../../data/motionQaReadModel";
import { projectNode, type StructuralCamera } from "./structuralRenderer";

export interface StructuralContextFactor {
  id: string;
  parentNodeId: string;
  label: string;
  slot: -1 | 1;
  depthOffset: number;
  insight: {
    definition: string;
    tracks: string;
    impact: string;
    relation: string;
  };
}

export interface PositionedStructuralContextFactor extends StructuralContextFactor {
  x: number;
  y: number;
  parentX: number;
  parentY: number;
  visualDepth: number;
}

export const structuralContextFactors: StructuralContextFactor[] = [
  { id: "context-domestic-output", parentNodeId: "fixture-origin", label: "Domestic output", slot: -1, depthOffset: 2, insight: { definition: "Supply produced inside the domestic economy.", tracks: "How much usable domestic production can enter this supply stream.", impact: "More domestic output can reduce reliance on outside supply; less can tighten availability.", relation: "It helps determine how much supply begins inside the system." } },
  { id: "context-import-flow", parentNodeId: "fixture-origin", label: "Import flow", slot: 1, depthOffset: 3, insight: { definition: "Supply arriving from producers outside the domestic economy.", tracks: "The volume and continuity of inbound supply.", impact: "Imports can fill domestic gaps while adding exposure to external disruptions.", relation: "It combines with domestic output to shape total available supply." } },
  { id: "context-utilization", parentNodeId: "fixture-producer", label: "Refinery utilization", slot: -1, depthOffset: 2, insight: { definition: "The share of available refining capacity currently in use.", tracks: "How intensely the production system is operating relative to its usable capacity.", impact: "High utilization can support output but leaves less room to absorb interruptions or demand spikes.", relation: "It indicates how much production room Petroleum Refining is already using." } },
  { id: "context-maintenance", parentNodeId: "fixture-producer", label: "Maintenance capacity", slot: 1, depthOffset: 4, insight: { definition: "Production capacity unavailable because equipment is being serviced or repaired.", tracks: "How much operating room is temporarily offline and how quickly it may return.", impact: "Maintenance protects reliability but can temporarily reduce near-term production flexibility.", relation: "It limits the capacity Petroleum Refining can use at a given moment." } },
  { id: "context-inventory", parentNodeId: "fixture-buffer", label: "Inventory level", slot: -1, depthOffset: 2, insight: { definition: "The amount of product physically held in storage.", tracks: "How much stock is available to bridge differences between production and use.", impact: "Larger inventories can cushion interruptions; thin inventories can transmit pressure faster.", relation: "It shows how much material the storage buffer currently holds." } },
  { id: "context-headroom", parentNodeId: "fixture-buffer", label: "Storage headroom", slot: 1, depthOffset: 4, insight: { definition: "The unused space remaining in the storage system.", tracks: "How much additional product storage can still accept.", impact: "More headroom can absorb excess output; little headroom can force production or routing changes.", relation: "It shows how much additional pressure Product Storage Capacity can absorb." } },
  { id: "context-power-cost", parentNodeId: "fixture-branch-a", label: "Power cost", slot: -1, depthOffset: 3, insight: { definition: "The cost of electricity needed to operate the system.", tracks: "The price pressure attached to energy-intensive operations.", impact: "Higher power costs can raise operating pressure and alter which activities remain economical.", relation: "It is one cost channel inside Electric Utilities." } },
  { id: "context-grid-reliability", parentNodeId: "fixture-branch-a", label: "Grid reliability", slot: 1, depthOffset: 5, insight: { definition: "The ability of the power system to deliver electricity consistently.", tracks: "Continuity, interruption risk, and the dependability of electric service.", impact: "Reliable power supports steady operation; interruptions can constrain many connected activities at once.", relation: "It describes whether Electric Utilities can deliver the power the network expects." } },
  { id: "context-output-mix", parentNodeId: "fixture-branch-b", label: "Output mix", slot: -1, depthOffset: 3, insight: { definition: "The combination of products coming out of the production system.", tracks: "Which products are being produced and their relative balance.", impact: "A mix that does not match demand can create shortages in one product and excess in another.", relation: "It describes what the Fuel Supply branch is actually providing." } },
  { id: "context-product-stocks", parentNodeId: "fixture-branch-b", label: "Product stocks", slot: 1, depthOffset: 5, insight: { definition: "Finished products available for distribution or use.", tracks: "The ready inventory of products after production.", impact: "Healthy stocks can smooth short disruptions; low stocks leave less protection against demand changes.", relation: "It measures the immediate cushion inside Fuel Supply." } },
  { id: "context-terminal-flow", parentNodeId: "fixture-junction", label: "Terminal flow", slot: -1, depthOffset: 2, insight: { definition: "The movement of product through transfer and distribution terminals.", tracks: "How quickly material enters, moves through, and exits key handoff points.", impact: "Congested terminals can slow an otherwise healthy network; spare flow room can keep it moving.", relation: "It is one of the physical handoffs managed by the Distribution Network." } },
  { id: "context-pipeline-room", parentNodeId: "fixture-junction", label: "Pipeline capacity", slot: 1, depthOffset: 4, insight: { definition: "The unused throughput available in connected pipelines.", tracks: "How much additional volume the pipeline network can carry.", impact: "Available capacity supports rerouting and growth; constrained capacity can become a bottleneck.", relation: "It defines one major transport limit inside the Distribution Network." } },
  { id: "context-rail-throughput", parentNodeId: "fixture-transport", label: "Rail throughput", slot: -1, depthOffset: 2, insight: { definition: "The volume the rail system can move through the network.", tracks: "Rail movement capacity, continuity, and the pace of completed shipments.", impact: "Strong rail throughput expands routing options; congestion can delay upstream and downstream activity.", relation: "It is one of the transport channels inside Freight Transportation." } },
  { id: "context-truck-capacity", parentNodeId: "fixture-transport", label: "Truck capacity", slot: 1, depthOffset: 4, insight: { definition: "The road-freight equipment and operating room available for shipments.", tracks: "How much trucking volume can be accepted and delivered.", impact: "Available trucks support flexible delivery; tight capacity can raise delays and costs.", relation: "It is the flexible last-mile and regional channel inside Freight Transportation." } },
  { id: "context-new-orders", parentNodeId: "fixture-downstream", label: "New orders", slot: -1, depthOffset: 2, insight: { definition: "Fresh commitments for future industrial production or delivery.", tracks: "The incoming flow of customer demand before it becomes completed output.", impact: "Rising orders can pull activity forward; falling orders can signal weaker future workload.", relation: "It is an early demand signal feeding Industrial Demand." } },
  { id: "context-capacity-use", parentNodeId: "fixture-downstream", label: "Capacity use", slot: 1, depthOffset: 4, insight: { definition: "The share of industrial production capability currently being used.", tracks: "How heavily industrial facilities are operating relative to available capacity.", impact: "High use can support expansion but reduce spare room; low use can indicate slack.", relation: "It shows how much room industry has to respond to additional demand." } },
  { id: "context-hours-worked", parentNodeId: "fixture-employment", label: "Hours worked", slot: -1, depthOffset: 2, insight: { definition: "The amount of labor time employers are currently using.", tracks: "Changes in scheduled and completed work hours.", impact: "Hours can adjust before headcount, making them a useful view of changing labor use.", relation: "It shows how intensively the existing workforce is being used." } },
  { id: "context-hiring-demand", parentNodeId: "fixture-employment", label: "Hiring demand", slot: 1, depthOffset: 3, insight: { definition: "Employer interest in adding workers.", tracks: "The need and willingness to recruit additional labor.", impact: "Stronger hiring demand can support job growth; weaker demand can reduce opportunities.", relation: "It shows the pull for additional workers inside Employment." } }
];

export function contextFactorsForNode(nodeId: string) {
  return structuralContextFactors.filter((factor) => factor.parentNodeId === nodeId);
}

export function layoutStructuralContextFactors(nodes: MotionQaNode[], camera: StructuralCamera, depths: Map<string, number>, visibleNodeIds: Set<string>) {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  return structuralContextFactors.flatMap((factor): PositionedStructuralContextFactor[] => {
    const parent = nodeMap.get(factor.parentNodeId);
    if (!parent || !visibleNodeIds.has(parent.id)) return [];
    const deltaX = parent.x - 520;
    const deltaY = parent.y - 310;
    const distance = Math.hypot(deltaX, deltaY);
    const outwardX = distance < 1 ? 0 : deltaX / distance;
    const outwardY = distance < 1 ? 1 : deltaY / distance;
    const tangentX = -outwardY;
    const tangentY = outwardX;
    const factorX = parent.x + outwardX * 88 + tangentX * factor.slot * 42;
    const factorY = parent.y + outwardY * 88 + tangentY * factor.slot * 42;
    const parentPoint = projectNode(parent, camera);
    const factorPoint = projectNode({ ...parent, x: factorX, y: factorY }, camera);
    return [{ ...factor, x: factorPoint.x, y: factorPoint.y, parentX: parentPoint.x, parentY: parentPoint.y, visualDepth: Math.min(10, (depths.get(parent.id) ?? 0) + factor.depthOffset) }];
  });
}
