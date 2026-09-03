import blsDolRegistry from "../../../data/config/layoffs/sources_bls_dol.json";
import censusRegistry from "../../../data/config/layoffs/sources_census.json";
import contextRegistry from "../../../data/config/layoffs/sources_bea_fed_courts.json";
import claimClassRegistry from "../../../data/config/layoffs/level4_claim_classes.json";
import { layoffsBranchTaxonomy, layoffsCanonicalFactorId } from "./layoffsBranchTaxonomy";

export type LayoffsSourceActivationState = "ACCEPTED" | "SOURCE_ENABLED_PENDING_ACCEPTANCE" | "SOURCE_IDENTIFIED" | "BLOCKED";
export type LayoffsClaimClass = "A_DIRECT_OBS" | "B_CALC" | "C_EVENT_OR_STRUCTURAL" | "D_TAXONOMY_OR_SOURCE_PROBLEM";

export interface LayoffsClaimClassification {
  canonicalFactorId: string;
  claimClass: LayoffsClaimClass;
  rationale: string;
  sourceRefs: readonly string[];
}

export interface LayoffsSourceSeries {
  sourceId: string;
  seriesId: string;
  label: string;
  unit: string;
  cadence: string;
  adjustment: string;
  evidenceUrl: string;
  methodologyUrl?: string;
}

export interface LayoffsFactorSourceState {
  canonicalFactorId: string;
  activationState: LayoffsSourceActivationState;
  series: readonly LayoffsSourceSeries[];
  claimClassification?: LayoffsClaimClassification;
  blockedReason?: string;
}

const canonicalBySlug = new Map<string, string>();
for (const group of layoffsBranchTaxonomy) {
  canonicalBySlug.set(group.id, layoffsCanonicalFactorId(group.label));
  for (const item of group.placements) {
    const slug = item.canonicalFactorId.replace("factor:canonical:", "");
    canonicalBySlug.set(slug, item.canonicalFactorId);
  }
}

const configuredAliases: Readonly<Record<string, string>> = Object.freeze({
  "layoffs-discharges-level": "layoffs-and-discharges",
  "layoffs-discharges-rate": "layoffs-and-discharges",
  "initial-ui-claims": "initial-claims",
  "continued-ui-claims": "continued-claims-insured-unemployment",
  "insured-unemployment-rate": "continued-claims-insured-unemployment",
  "closing-establishment-losses": "establishment-closures",
  "establishment-death-job-losses": "establishment-deaths",
  "bds-job-destruction": "gross-job-losses",
  "bds-job-destruction-continuers": "establishment-contractions",
  "bds-job-destruction-deaths": "establishment-closures",
  "bds-establishment-exits": "establishment-deaths",
  "bds-firm-deaths": "firm-deaths",
  "bds-firm-death-establishments": "firm-age-size-vulnerability",
  "bds-firm-death-employment": "firm-death-shutdown-stress",
  "business-formations-four-quarters": "business-formation"
});

function canonicalId(configured: string) {
  const slug = configured.replace(/^factor:(canonical:)?/, "");
  const canonicalSlug = configuredAliases[slug] ?? slug;
  return canonicalBySlug.get(canonicalSlug) ?? `factor:canonical:${canonicalSlug}`;
}

const mutable = new Map<string, { activationState: LayoffsSourceActivationState; series: LayoffsSourceSeries[]; blockedReason?: string }>();

const claimClassifications = new Map<string, LayoffsClaimClassification>(claimClassRegistry.factors.map((row) => [
  row.canonicalFactorId,
  Object.freeze({
    canonicalFactorId: row.canonicalFactorId,
    claimClass: row.claimClass as LayoffsClaimClass,
    rationale: row.rationale,
    sourceRefs: Object.freeze([...row.sourceRefs])
  })
]));

for (const group of layoffsBranchTaxonomy) {
  mutable.set(layoffsCanonicalFactorId(group.label), { activationState: "SOURCE_IDENTIFIED", series: [] });
  for (const item of group.placements) mutable.set(item.canonicalFactorId, { activationState: "SOURCE_IDENTIFIED", series: [] });
}

for (const row of blsDolRegistry.series) {
  const id = canonicalId(row.canonical_factor);
  const state = mutable.get(id) ?? { activationState: "SOURCE_IDENTIFIED" as const, series: [] };
  state.series.push({ sourceId: row.source_id, seriesId: row.series_id, label: row.label, unit: row.unit, cadence: row.frequency, adjustment: row.seasonal_adjustment, evidenceUrl: row.human_evidence_url, methodologyUrl: row.methodology_url });
  state.activationState = row.activation_state === "ACCEPTED_EXISTING" ? "ACCEPTED" : "SOURCE_ENABLED_PENDING_ACCEPTANCE";
  mutable.set(id, state);
}

for (const source of censusRegistry.sources) {
  for (const row of source.series) {
    for (const placement of row.placement_candidates) {
      const id = canonicalId(`factor:${placement}`);
      const state = mutable.get(id) ?? { activationState: "SOURCE_IDENTIFIED" as const, series: [] };
      state.series.push({ sourceId: source.source_id, seriesId: row.source_series_id, label: row.label, unit: row.unit, cadence: source.cadence, adjustment: row.seasonal_adjustment, evidenceUrl: source.evidence_url, methodologyUrl: source.methodology_url });
      state.activationState = "BLOCKED";
      state.blockedReason = `Scheduled retrieval requires ${censusRegistry.credential_environment_variable}; values remain unavailable until retrieval, rights, and acceptance pass.`;
      mutable.set(id, state);
    }
  }
}

for (const source of contextRegistry.sources) {
  for (const row of source.series) {
    const id = canonicalId(row.canonical_factor);
    const state = mutable.get(id) ?? { activationState: "SOURCE_IDENTIFIED" as const, series: [] };
    state.series.push({
      sourceId: source.source_id,
      seriesId: row.source_series_id,
      label: row.label,
      unit: row.unit,
      cadence: source.cadence,
      adjustment: "not seasonally adjusted / rolling official table",
      evidenceUrl: source.evidence_url,
      methodologyUrl: source.methodology_url
    });
    state.activationState = "SOURCE_ENABLED_PENDING_ACCEPTANCE";
    state.blockedReason = source.blocked_reason;
    mutable.set(id, state);
  }
  for (const row of source.selector_candidates ?? []) {
    const id = canonicalId(row.canonical_factor);
    const state = mutable.get(id) ?? { activationState: "SOURCE_IDENTIFIED" as const, series: [] };
    state.series.push({
      sourceId: source.source_id,
      seriesId: `${source.source_id}:selector-pending`,
      label: row.required_decision,
      unit: "selector unresolved",
      cadence: source.cadence,
      adjustment: "pending exact official selector",
      evidenceUrl: source.evidence_url,
      methodologyUrl: source.methodology_url
    });
    state.activationState = "BLOCKED";
    state.blockedReason = source.blocked_reason;
    mutable.set(id, state);
  }
}

export const layoffsFactorSourceStates: Readonly<Record<string, LayoffsFactorSourceState>> = Object.freeze(Object.fromEntries([...mutable.entries()].map(([id, state]) => [id, Object.freeze({ canonicalFactorId: id, ...state, series: Object.freeze(state.series), claimClassification: claimClassifications.get(id) })])));

export function layoffsFactorSourceState(canonicalFactorId: string) {
  return layoffsFactorSourceStates[canonicalFactorId];
}

export const LAYOFFS_SOURCE_ENABLED_FACTOR_COUNT = Object.values(layoffsFactorSourceStates).filter((row) => row.activationState === "SOURCE_ENABLED_PENDING_ACCEPTANCE").length;
export const LAYOFFS_BLOCKED_FACTOR_COUNT = Object.values(layoffsFactorSourceStates).filter((row) => row.activationState === "BLOCKED").length;
export const LAYOFFS_CLASSIFIED_LEVEL4_FACTOR_COUNT = claimClassifications.size;
