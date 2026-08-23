import type { MotionQaNode } from "../../data/motionQaReadModel";

export type StructuralNodeSymbol = "drop" | "refinery" | "tank" | "bolt" | "flame" | "split" | "freight" | "factory" | "people" | "system";

export interface StructuralNodeVisual {
  accent: string;
  fill: string;
  role: "SOURCE" | "PRODUCTION" | "BUFFER" | "INFRASTRUCTURE" | "DEMAND" | "HUMAN";
  symbol: StructuralNodeSymbol;
}

const visuals: Record<string, StructuralNodeVisual> = {
  "fixture-origin": { accent: "#67d9e6", fill: "#12343c", role: "SOURCE", symbol: "drop" },
  "fixture-producer": { accent: "#f0b768", fill: "#35291d", role: "PRODUCTION", symbol: "refinery" },
  "fixture-buffer": { accent: "#ad9cff", fill: "#292641", role: "BUFFER", symbol: "tank" },
  "fixture-branch-a": { accent: "#78aaff", fill: "#1d2e48", role: "INFRASTRUCTURE", symbol: "bolt" },
  "fixture-branch-b": { accent: "#67d9e6", fill: "#12343c", role: "SOURCE", symbol: "flame" },
  "fixture-junction": { accent: "#66d6bb", fill: "#16372f", role: "INFRASTRUCTURE", symbol: "split" },
  "fixture-transport": { accent: "#78aaff", fill: "#1d2e48", role: "INFRASTRUCTURE", symbol: "freight" },
  "fixture-downstream": { accent: "#f08d79", fill: "#3b2422", role: "DEMAND", symbol: "factory" },
  "fixture-employment": { accent: "#e998d2", fill: "#3b2437", role: "HUMAN", symbol: "people" }
};

const fallbackByKind: Record<string, StructuralNodeVisual> = {
  INPUT: visuals["fixture-origin"],
  INDUSTRY: visuals["fixture-producer"],
  BUFFER: visuals["fixture-buffer"],
  TRANSFER: visuals["fixture-junction"],
  HUMAN_CAPITAL: visuals["fixture-employment"]
};

export function resolveStructuralNodeVisual(node: MotionQaNode): StructuralNodeVisual {
  return visuals[node.id] ?? fallbackByKind[node.kind] ?? { accent: "#83a5af", fill: "#152832", role: "INFRASTRUCTURE", symbol: "system" };
}
