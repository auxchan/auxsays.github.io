import productionDocument from "../../../data/production/systems-monitor-production.json";

interface ProductionDocument {
  schemaVersion: string;
  generatedAt: string;
  factualSnapshot: unknown;
  acceptedHistory: unknown;
  calculations: Record<string, unknown>;
  automation: {
    heartbeat: string;
    sourceChecks: Record<string, { lastSuccessfulCheck: string; health: string; reason: string; latestOfficialPeriod: string | null; newerExpectedReleaseOverdue: boolean }>;
    sourceDiagnostics?: Record<string, unknown>;
  };
}

const production = productionDocument as ProductionDocument;
if (production.schemaVersion !== "systems-monitor-production-1.0.0") {
  throw new Error("Unsupported Systems Monitor production-data schema");
}

export const productionFactualSnapshot = production.factualSnapshot;
export const productionAcceptedHistory = production.acceptedHistory;
export const productionSourceChecks = Object.freeze(production.automation.sourceChecks);
export const productionSourceDiagnostics = Object.freeze(production.automation.sourceDiagnostics ?? {});
export const productionCalculations = Object.freeze(production.calculations);
export const PRODUCTION_DATA_GENERATED_AT = production.generatedAt;
export const PRODUCTION_DATA_HEARTBEAT = production.automation.heartbeat;
