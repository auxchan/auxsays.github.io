import type { StructuralSurfaceNode } from "../../data/motionQaReadModel";

export type StructuralNodeSymbol = "drop" | "refinery" | "tank" | "bolt" | "flame" | "split" | "freight" | "factory" | "people" | "system" | "briefcase" | "unemployment" | "participation" | "claims" | "openings" | "hire" | "clock" | "earnings" | "separations" | "ratio";

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
  "fixture-employment": { accent: "#e998d2", fill: "#3b2437", role: "HUMAN", symbol: "people" },
  "outcome:labor-market-state": { accent: "#e998d2", fill: "#3b2437", role: "HUMAN", symbol: "people" },
  "factor:payroll-employment": { accent: "#82efd5", fill: "#173a35", role: "HUMAN", symbol: "briefcase" },
  "factor:u3-unemployment": { accent: "#f08d79", fill: "#3b2422", role: "HUMAN", symbol: "unemployment" },
  "factor:labor-force-participation": { accent: "#78aaff", fill: "#1d2e48", role: "HUMAN", symbol: "participation" },
  "factor:initial-claims": { accent: "#efbc69", fill: "#392d1d", role: "HUMAN", symbol: "claims" },
  "factor:job-openings": { accent: "#ad9cff", fill: "#292641", role: "DEMAND", symbol: "openings" },
  "factor:hires": { accent: "#66d6bb", fill: "#16372f", role: "HUMAN", symbol: "hire" },
  "factor:average-weekly-hours": { accent: "#67d9e6", fill: "#12343c", role: "HUMAN", symbol: "clock" },
  "factor:average-hourly-earnings": { accent: "#f3c476", fill: "#382d1e", role: "HUMAN", symbol: "earnings" },
  "factor:total-separations": { accent: "#e998d2", fill: "#3b2437", role: "HUMAN", symbol: "separations" },
  "factor:employment-population-ratio": { accent: "#8ecdc5", fill: "#183633", role: "HUMAN", symbol: "ratio" }
};

const fallbackByKind: Record<string, StructuralNodeVisual> = {
  INPUT: visuals["fixture-origin"],
  INDUSTRY: visuals["fixture-producer"],
  BUFFER: visuals["fixture-buffer"],
  TRANSFER: visuals["fixture-junction"],
  HUMAN_CAPITAL: visuals["fixture-employment"]
};

export function resolveStructuralNodeVisual(node: StructuralSurfaceNode): StructuralNodeVisual {
  return visuals[node.id] ?? fallbackByKind[node.kind] ?? { accent: "#83a5af", fill: "#152832", role: "INFRASTRUCTURE", symbol: "system" };
}
