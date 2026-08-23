export const motionOutcomes = ["TRANSMITTED", "DELAYED", "PARTIALLY_ABSORBED", "ABSORBED", "BLOCKED", "AMPLIFIED", "UNKNOWN"] as const;
export type MotionOutcome = typeof motionOutcomes[number];

export interface MotionQaNode {
  id: string;
  label: string;
  overviewLabel: string;
  detailLabel: string;
  kind: string;
  displayRank: number;
  currentState: string;
  derivationRef: string;
  insight: { definition: string; tracks: string; impact: string };
  x: number;
  y: number;
}

export interface MotionQaRelationship {
  id: string;
  from: string;
  to: string;
  outcome: MotionOutcome;
  mechanism: string;
  plainLanguage: string;
  evidenceClass: "TEST_FIXTURE";
  originId: string;
  commonCauseId: string | null;
  derivationRef: string;
  status: "TEST_FIXTURE";
  stopReason: string | null;
}

export interface MotionQaPath {
  id: string;
  label: string;
  originId: string;
  commonCauseId: string | null;
  steps: string[][];
  stopReason: string;
}

export interface MotionQaReadModel {
  schemaVersion: "phase4-motion-qa-read-model-1.0.0";
  publicationClass: "fixture";
  fixtureType: "TEST_FIXTURE";
  activationStatus: "DEVELOPMENT_ONLY_MOTION_QA";
  candidateEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED";
  title: string;
  coverage: { scope: "MOTION_QA_ONLY"; nodeCount: number; relationshipCount: number; factualRelationshipCount: 0; acceptedRelationshipCount: 0 };
  sourceHealth: Record<string, string>;
  humanMotionQa: "PENDING";
  gateBStatus: "OPEN_UNCHANGED";
  phase5Status: "LOCKED";
  nodes: MotionQaNode[];
  relationships: MotionQaRelationship[];
  paths: MotionQaPath[];
  derivations: Array<{ id: string; claimClass: "TEST_FIXTURE"; description: string }>;
}

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object`);
  return value as Record<string, unknown>;
}

function string(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be non-empty text`);
  return value;
}

function array(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  return value;
}

export function validateMotionQaReadModel(value: unknown): MotionQaReadModel {
  const model = object(value, "Motion QA read model");
  if (model.schemaVersion !== "phase4-motion-qa-read-model-1.0.0" || model.publicationClass !== "fixture" || model.fixtureType !== "TEST_FIXTURE") throw new Error("Motion QA must remain an explicit TEST_FIXTURE");
  if (model.activationStatus !== "DEVELOPMENT_ONLY_MOTION_QA" || model.candidateEligibility !== "NEVER_ACCEPTED_NEVER_PUBLISHED") throw new Error("Motion QA fixture is not eligible for activation or publication");
  if (model.humanMotionQa !== "PENDING" || model.gateBStatus !== "OPEN_UNCHANGED" || model.phase5Status !== "LOCKED") throw new Error("Motion QA cannot change approval gates");
  const coverage = object(model.coverage, "coverage");
  if (coverage.scope !== "MOTION_QA_ONLY" || coverage.factualRelationshipCount !== 0 || coverage.acceptedRelationshipCount !== 0) throw new Error("Motion QA coverage cannot contain factual or accepted relationships");
  const nodes = array(model.nodes, "nodes").map((raw, index) => {
    const node = object(raw, `nodes[${index}]`);
    const x = Number(node.x); const y = Number(node.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) throw new Error("Motion QA node coordinates must be finite");
    const displayRank = Number(node.displayRank);
    if (!Number.isInteger(displayRank) || displayRank < 1) throw new Error("Motion QA node displayRank must be a positive integer");
    const insight = object(node.insight, "node.insight");
    return { id: string(node.id, "node.id"), label: string(node.label, "node.label"), overviewLabel: string(node.overviewLabel, "node.overviewLabel"), detailLabel: string(node.detailLabel, "node.detailLabel"), kind: string(node.kind, "node.kind"), displayRank, currentState: string(node.currentState, "node.currentState"), derivationRef: string(node.derivationRef, "node.derivationRef"), insight: { definition: string(insight.definition, "node.insight.definition"), tracks: string(insight.tracks, "node.insight.tracks"), impact: string(insight.impact, "node.insight.impact") }, x, y };
  });
  if (nodes.length < 6 || nodes.length > 10 || Number(coverage.nodeCount) !== nodes.length) throw new Error("Motion QA topology must contain 6–10 nodes");
  const nodeIds = new Set(nodes.map((node) => node.id));
  const allowedOutcomes = new Set<string>(motionOutcomes);
  const relationships = array(model.relationships, "relationships").map((raw, index) => {
    const edge = object(raw, `relationships[${index}]`);
    const outcome = string(edge.outcome, "relationship.outcome");
    if (edge.status !== "TEST_FIXTURE" || edge.evidenceClass !== "TEST_FIXTURE" || !allowedOutcomes.has(outcome)) throw new Error("Every Motion QA relationship must remain a supported TEST_FIXTURE outcome");
    const from = string(edge.from, "relationship.from"); const to = string(edge.to, "relationship.to");
    if (!nodeIds.has(from) || !nodeIds.has(to) || from === to) throw new Error("Motion QA relationship endpoints are invalid");
    return { id: string(edge.id, "relationship.id"), from, to, outcome: outcome as MotionOutcome, mechanism: string(edge.mechanism, "relationship.mechanism"), plainLanguage: string(edge.plainLanguage, "relationship.plainLanguage"), evidenceClass: "TEST_FIXTURE" as const, originId: string(edge.originId, "relationship.originId"), commonCauseId: edge.commonCauseId === null ? null : string(edge.commonCauseId, "relationship.commonCauseId"), derivationRef: string(edge.derivationRef, "relationship.derivationRef"), status: "TEST_FIXTURE" as const, stopReason: edge.stopReason === null ? null : string(edge.stopReason, "relationship.stopReason") };
  });
  if (relationships.length < 8 || relationships.length > 14 || Number(coverage.relationshipCount) !== relationships.length) throw new Error("Motion QA topology must contain 8–14 fixture relationships");
  const representedOutcomes = new Set(relationships.map((edge) => edge.outcome));
  if (motionOutcomes.some((outcome) => !representedOutcomes.has(outcome))) throw new Error("Motion QA fixture must exercise every governed transmission outcome");
  const edgeIds = new Set(relationships.map((edge) => edge.id));
  const paths = array(model.paths, "paths").map((raw, index) => {
    const path = object(raw, `paths[${index}]`);
    const steps = array(path.steps, "path.steps").map((rawStep) => array(rawStep, "path.step").map((edgeId) => string(edgeId, "path.edgeId")));
    if (!steps.length || steps.some((step) => !step.length || step.some((edgeId) => !edgeIds.has(edgeId)))) throw new Error("Motion QA path references an unavailable fixture relationship");
    return { id: string(path.id, "path.id"), label: string(path.label, "path.label"), originId: string(path.originId, "path.originId"), commonCauseId: path.commonCauseId === null ? null : string(path.commonCauseId, "path.commonCauseId"), steps, stopReason: string(path.stopReason, "path.stopReason") };
  });
  const derivations = array(model.derivations, "derivations").map((raw) => {
    const derivation = object(raw, "derivation");
    if (derivation.claimClass !== "TEST_FIXTURE") throw new Error("Motion QA derivations must remain TEST_FIXTURE");
    return { id: string(derivation.id, "derivation.id"), claimClass: "TEST_FIXTURE" as const, description: string(derivation.description, "derivation.description") };
  });
  return {
    schemaVersion: "phase4-motion-qa-read-model-1.0.0", publicationClass: "fixture", fixtureType: "TEST_FIXTURE", activationStatus: "DEVELOPMENT_ONLY_MOTION_QA", candidateEligibility: "NEVER_ACCEPTED_NEVER_PUBLISHED",
    title: string(model.title, "title"), coverage: { scope: "MOTION_QA_ONLY", nodeCount: nodes.length, relationshipCount: relationships.length, factualRelationshipCount: 0, acceptedRelationshipCount: 0 },
    sourceHealth: Object.fromEntries(Object.entries(object(model.sourceHealth, "sourceHealth")).map(([key, state]) => [key, string(state, `sourceHealth.${key}`)])), humanMotionQa: "PENDING", gateBStatus: "OPEN_UNCHANGED", phase5Status: "LOCKED", nodes, relationships, paths, derivations
  };
}
