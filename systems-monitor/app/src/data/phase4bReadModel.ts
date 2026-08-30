export interface Phase4bObservation {
  id: string;
  label: string;
  value: string;
  unit: string;
  period: string;
  stateType: "OBS";
  authority: string;
  seriesId: string;
  evidenceUrl: string;
  methodologyUrl: string;
  acquisitionProvenanceUrl: string;
}

export interface Phase4bReadModel {
  schemaVersion: "phase4b-master-read-model-0.1.0";
  activationStatus: "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED";
  structuralCoverageState: string;
  coverageWarning: string;
  coveredCodes: string[];
  acceptedRelationships: unknown[];
  structuralCalculations: unknown[];
  claimClassesPresent: string[];
  claimClassesAbsent: string[];
  gateBStatus: string;
  humanPhase4bQa: string;
  phase5Status: string;
  sourceHealth: Record<string, string>;
  observations: Phase4bObservation[];
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object`);
  return value as Record<string, unknown>;
}

function text(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim() === "") throw new Error(`${label} must be non-empty text`);
  return value;
}

function list(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  return value;
}

function observation(value: unknown, index: number): Phase4bObservation {
  const item = record(value, `currentObservations[${index}]`);
  const snake = "state_type" in item;
  const stateType = text(item[snake ? "state_type" : "stateType"], `currentObservations[${index}].stateType`);
  if (stateType !== "OBS") throw new Error("Phase-4B local checkpoint accepts OBS records only");
  return {
    id: text(item[snake ? "state_id" : "stateId"], `currentObservations[${index}].id`),
    label: text(item.label, `currentObservations[${index}].label`),
    value: text(item.value, `currentObservations[${index}].value`),
    unit: text(item.unit, `currentObservations[${index}].unit`),
    period: text(item[snake ? "valid_time" : "observationPeriod"], `currentObservations[${index}].period`),
    stateType: "OBS",
    authority: text(item.authority ?? "U.S. Bureau of Labor Statistics", `currentObservations[${index}].authority`),
    seriesId: text(item[snake ? "series_id" : "seriesId"], `currentObservations[${index}].seriesId`),
    evidenceUrl: text(item[snake ? "evidence_url" : "evidenceUrl"], `currentObservations[${index}].evidenceUrl`),
    methodologyUrl: text(item[snake ? "methodology_url" : "methodologyUrl"], `currentObservations[${index}].methodologyUrl`),
    acquisitionProvenanceUrl: text(item[snake ? "acquisition_provenance_url" : "acquisitionProvenanceUrl"], `currentObservations[${index}].acquisitionProvenanceUrl`)
  };
}

export function validatePhase4bReadModel(value: unknown): Phase4bReadModel {
  const model = record(value, "Phase-4B read model");
  const schemaVersion = text(model.schemaVersion, "schemaVersion");
  const activationStatus = text(model.activationStatus, "activationStatus");
  if (schemaVersion !== "phase4b-master-read-model-0.1.0") throw new Error("Unsupported Phase-4B read-model schema");
  if (activationStatus !== "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED") throw new Error("Phase-4B checkpoint must remain local review only");
  const gateBStatus = text(model.gateBStatus, "gateBStatus");
  const coverage = text(model.structuralCoverageState, "structuralCoverageState");
  if (coverage === "BOUNDED_STRUCTURAL_PROOF" && gateBStatus !== "PASS") {
    throw new Error("Incomplete Gate B cannot be presented as bounded structural proof");
  }
  const acceptedRelationships = list(model.acceptedRelationships, "acceptedRelationships");
  const structuralCalculations = list(model.structuralCalculations, "structuralCalculations");
  const claimClassesPresent = list(model.claimClassesPresent, "claimClassesPresent").map((item) => text(item, "claimClassesPresent item"));
  const claimClassesAbsent = list(model.claimClassesAbsent, "claimClassesAbsent").map((item) => text(item, "claimClassesAbsent item"));
  if (!claimClassesPresent.includes("OBS") || !claimClassesAbsent.includes("FCST") || !claimClassesAbsent.includes("SCEN")) {
    throw new Error("Phase-4B checkpoint claim classes are inconsistent");
  }
  if (structuralCalculations.length > 0 && !claimClassesPresent.includes("CALC")) {
    throw new Error("Structural calculations must be identified as CALC");
  }
  const sourceHealth = record(model.sourceHealth, "sourceHealth");
  return {
    schemaVersion,
    activationStatus,
    structuralCoverageState: coverage,
    coverageWarning: text(model.coverageWarning, "coverageWarning"),
    coveredCodes: list(model.coveredCodes, "coveredCodes").map((item) => text(item, "coveredCodes item")),
    acceptedRelationships,
    structuralCalculations,
    claimClassesPresent,
    claimClassesAbsent,
    gateBStatus,
    humanPhase4bQa: text(model.humanPhase4bQa, "humanPhase4bQa"),
    phase5Status: text(model.phase5Status, "phase5Status"),
    sourceHealth: Object.fromEntries(Object.entries(sourceHealth).map(([key, item]) => [key, text(item, `sourceHealth.${key}`)])),
    observations: list(model.currentObservations, "currentObservations").map(observation)
  };
}
