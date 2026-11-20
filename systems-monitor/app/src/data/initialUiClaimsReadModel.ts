import productionDocument from "../../../data/config/layoffs/initial_ui_claims_production.json";
import { acceptedLayoffsHistoryForFactor, type LayoffsAcceptedFactorSummary } from "./layoffsAcceptedHistoryReadModel";
import { layoffsFactorSourceState, type LayoffsFactorSourceState } from "./layoffsBranchReadModel";
import { layoffsBranchTaxonomy } from "./layoffsBranchTaxonomy";

export type InitialUiClaimsClass = "A_DIRECT_OBS" | "B_GOVERNED_CALC" | "C_EVENT_OR_STRUCTURAL";
export type InitialUiClaimsDisposition = "ACCEPTED_OBSERVATION" | "GOVERNED_CALC_METHOD_APPROVED_INPUT_HISTORY_PENDING" | "SOURCE_IDENTIFIED_PENDING_ACCEPTANCE" | "BLOCKED_CREDENTIAL" | "EVENT_OR_STRUCTURAL_FACTOR";

export interface InitialUiClaimsProductionPlacement {
  order: number;
  placementId: string;
  label: string;
  canonicalFactorId: string;
  claimClass: InitialUiClaimsClass;
  productionDisposition: InitialUiClaimsDisposition;
  sourceIds: readonly string[];
  selectors: readonly string[];
  acceptedHistoryState: string;
  methodologyVersion?: string;
  universeVersion?: string;
  coveragePolicy?: string;
  acceptedInputSeries?: number;
  calculatedHistoryDepth?: number;
  blocker: string | null;
  placementPaths: readonly string[];
  sourceState?: LayoffsFactorSourceState;
  acceptedHistory?: LayoffsAcceptedFactorSummary;
}

const initialGroup = layoffsBranchTaxonomy.find((group) => group.id === "initial-ui-claims");
if (!initialGroup || initialGroup.placements.length !== 10) throw new Error("Initial UI Claims exact-ten taxonomy is unavailable");

function placementPaths(canonicalFactorId: string) {
  return layoffsBranchTaxonomy.flatMap((group) => group.placements
    .filter((candidate) => candidate.canonicalFactorId === canonicalFactorId)
    .map((candidate) => `Layoffs & Job Destruction › ${group.label} › ${candidate.label}`));
}

export const initialUiClaimsProductionPlacements: readonly InitialUiClaimsProductionPlacement[] = Object.freeze(
  productionDocument.placements.map((row, index) => {
    const taxonomyPlacement = initialGroup.placements[index];
    if (row.order !== index + 1 || row.label !== taxonomyPlacement.label || row.canonicalFactorId !== taxonomyPlacement.canonicalFactorId) {
      throw new Error(`Initial UI Claims production registry diverged at placement ${index + 1}`);
    }
    return Object.freeze({
      ...row,
      claimClass: row.claimClass as InitialUiClaimsClass,
      productionDisposition: row.productionDisposition as InitialUiClaimsDisposition,
      sourceIds: Object.freeze([...row.sourceIds]),
      selectors: Object.freeze([...row.selectors]),
      placementPaths: Object.freeze(placementPaths(row.canonicalFactorId)),
      sourceState: layoffsFactorSourceState(row.canonicalFactorId),
      acceptedHistory: acceptedLayoffsHistoryForFactor(row.canonicalFactorId),
    });
  }),
);

export const INITIAL_UI_CLAIMS_HUMAN_QA = productionDocument.humanQa;
export const INITIAL_UI_CLAIMS_UNEXPLAINED_RENDERER_FIXTURES = productionDocument.unexplainedRendererFixtures;
export const INITIAL_UI_CLAIMS_ACCEPTED_STRUCTURAL_RELATIONSHIPS = productionDocument.acceptedStructuralRelationships;
export const INITIAL_UI_CLAIMS_GATE_B = productionDocument.gateB;
export const INITIAL_UI_CLAIMS_FORECASTING = productionDocument.forecasting;
