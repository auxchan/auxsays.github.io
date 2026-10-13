import productionDocument from "../../../data/config/layoffs/continued_claims_production.json";
import { acceptedLayoffsHistoryForFactor, type LayoffsAcceptedFactorSummary } from "./layoffsAcceptedHistoryReadModel";
import { layoffsFactorSourceState, type LayoffsFactorSourceState } from "./layoffsBranchReadModel";
import { layoffsBranchTaxonomy } from "./layoffsBranchTaxonomy";

export type ContinuedClaimsClass = "A_DIRECT_OBS" | "B_GOVERNED_CALC" | "D_TAXONOMY_OR_SOURCE_PROBLEM";
export type ContinuedClaimsDisposition =
  | "ACCEPTED_OBSERVATION"
  | "GOVERNED_CALC_METHOD_APPROVED_INPUT_HISTORY_PENDING"
  | "SOURCE_IDENTIFIED_PENDING_ACCEPTANCE"
  | "BLOCKED_CREDENTIAL"
  ;

export interface ContinuedClaimsParentObservation {
  order: number;
  canonicalObservationId: string;
  label: string;
  sourceId: string;
  selector: string;
  xmlPath: string;
  unit: string;
  frequency: string;
  geography: string;
  seasonalAdjustment: string;
  validTime: string;
  revisionBehavior: string;
  productionDisposition: "SOURCE_ENABLED_PENDING_ACCEPTANCE";
  acceptedHistoryRecords: number;
}

export interface ContinuedClaimsProductionPlacement {
  order: number;
  placementId: string;
  label: string;
  canonicalFactorId: string;
  claimClass: ContinuedClaimsClass;
  productionDisposition: ContinuedClaimsDisposition;
  sourceIds: readonly string[];
  selectors: readonly string[];
  acceptedHistoryState: string;
  expectedAcceptedHistoryRecords: number;
  blocker: string | null;
  recommendation: string | null;
  placementPaths: readonly string[];
  sourceState?: LayoffsFactorSourceState;
  acceptedHistory?: LayoffsAcceptedFactorSummary;
}

const continuedGroup = layoffsBranchTaxonomy.find((group) => group.id === "continued-claims-insured-unemployment");
if (!continuedGroup || continuedGroup.placements.length !== 10) throw new Error("Continued Claims exact-ten taxonomy is unavailable");

function placementPaths(canonicalFactorId: string) {
  return layoffsBranchTaxonomy.flatMap((group) => group.placements
    .filter((candidate) => candidate.canonicalFactorId === canonicalFactorId)
    .map((candidate) => `Layoffs & Job Destruction › ${group.label} › ${candidate.label}`));
}

function acceptedRecordCount(history: LayoffsAcceptedFactorSummary | undefined) {
  return history?.series.reduce((total, series) => total + series.history.length + series.revisionChainCount, 0) ?? 0;
}

export const continuedClaimsParentObservations: readonly ContinuedClaimsParentObservation[] = Object.freeze(
  productionDocument.parentObservations.map((row) => Object.freeze({
    ...row,
    productionDisposition: row.productionDisposition as "SOURCE_ENABLED_PENDING_ACCEPTANCE",
  })),
);

export const continuedClaimsProductionPlacements: readonly ContinuedClaimsProductionPlacement[] = Object.freeze(
  productionDocument.placements.map((row, index) => {
    const taxonomyPlacement = continuedGroup.placements[index];
    if (row.order !== index + 1 || row.label !== taxonomyPlacement.label || row.canonicalFactorId !== taxonomyPlacement.canonicalFactorId || row.placementId !== `placement:layoffs-job-destruction:${continuedGroup.id}:${taxonomyPlacement.placementSlug}`) {
      throw new Error(`Continued Claims production registry diverged at placement ${index + 1}`);
    }
    const acceptedHistory = acceptedLayoffsHistoryForFactor(row.canonicalFactorId);
    if (acceptedRecordCount(acceptedHistory) !== row.expectedAcceptedHistoryRecords) {
      throw new Error(`Continued Claims accepted-history reuse diverged for ${row.canonicalFactorId}`);
    }
    return Object.freeze({
      ...row,
      claimClass: row.claimClass as ContinuedClaimsClass,
      productionDisposition: row.productionDisposition as ContinuedClaimsDisposition,
      sourceIds: Object.freeze([...row.sourceIds]),
      selectors: Object.freeze([...row.selectors]),
      placementPaths: Object.freeze(placementPaths(row.canonicalFactorId)),
      sourceState: layoffsFactorSourceState(row.canonicalFactorId),
      acceptedHistory,
    });
  }),
);

export const CONTINUED_CLAIMS_PARENT_LABEL = productionDocument.parentLabel;
export const CONTINUED_CLAIMS_PARENT_IDENTITY = productionDocument.parentIdentityResolution;
export const CONTINUED_CLAIMS_PARENT_BOUNDARY = productionDocument.parentIdentityBoundary;
export const CONTINUED_CLAIMS_HUMAN_QA = productionDocument.humanQa;
export const CONTINUED_CLAIMS_REVIEW_STATE = productionDocument.reviewState;
export const CONTINUED_CLAIMS_ACCEPTED_HISTORY_REUSE_RECORDS = productionDocument.acceptedHistoryReuseRecords;
export const CONTINUED_CLAIMS_UNEXPLAINED_RENDERER_FIXTURES = productionDocument.unexplainedRendererFixtures;
export const CONTINUED_CLAIMS_ACCEPTED_STRUCTURAL_RELATIONSHIPS = productionDocument.acceptedStructuralRelationships;
export const CONTINUED_CLAIMS_GATE_B = productionDocument.gateB;
export const CONTINUED_CLAIMS_FORECASTING = productionDocument.forecasting;
