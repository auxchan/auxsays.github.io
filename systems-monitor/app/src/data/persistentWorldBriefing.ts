import type { PersistentWorldFactualBinding, PersistentWorldBindingStatus } from "./persistentWorldFactualBindings";
import { persistentWorldPlacementLabel, type PersistentWorldReadModel } from "./persistentWorldModel";
import type { PersistentChangeNotice } from "./persistentWorldTemporalReadModel";

export type PersistentChangeScope = "BRANCH" | "ALL";

export interface PersistentCoverageSummary {
  scopeLabel: string;
  totalFactors: number;
  acceptedReadingFactors: number;
  acceptedHistoryFactors: number;
  comparableHistoryFactors: number;
  sourceIdentifiedFactors: number;
  pendingFactors: number;
  blockedFactors: number;
  configurationPendingFactors: number;
}

const bindingPriority: Readonly<Record<PersistentWorldBindingStatus, number>> = Object.freeze({
  CONNECTED: 6,
  SOURCE_ENABLED_PENDING_ACCEPTANCE: 5,
  SOURCE_IDENTIFIED: 4,
  BLOCKED: 3,
  UNMAPPED: 2,
  FIXTURE_ONLY: 1,
});

function noticeTimestamp(notice: PersistentChangeNotice) {
  return Date.parse(notice.officialPublishedAt ?? notice.knownAt);
}

export function sortPersistentNotices(notices: readonly PersistentChangeNotice[]) {
  return [...notices].sort((left, right) => noticeTimestamp(right) - noticeTimestamp(left) || left.id.localeCompare(right.id));
}

export function persistentWorldBranchRootId(model: PersistentWorldReadModel, selectedId: string | null) {
  let placement = selectedId ? model.placements[selectedId] : undefined;
  while (placement && placement.depth > 1) placement = placement.parentPlacementId ? model.placements[placement.parentPlacementId] : undefined;
  return placement?.depth === 1 ? placement.id : null;
}

export function persistentWorldPlacementInBranch(model: PersistentWorldReadModel, placementId: string, branchId: string) {
  let placement: (typeof model.placements)[string] | undefined = model.placements[placementId];
  while (placement) {
    if (placement.id === branchId) return true;
    placement = placement.parentPlacementId ? model.placements[placement.parentPlacementId] : undefined;
  }
  return false;
}

export function persistentChangesForScope(
  notices: readonly PersistentChangeNotice[],
  model: PersistentWorldReadModel,
  branchId: string | null,
  scope: PersistentChangeScope,
) {
  if (scope === "ALL" || !branchId) return sortPersistentNotices(notices);
  return sortPersistentNotices(notices.filter((notice) => persistentWorldPlacementInBranch(model, notice.placementId, branchId)));
}

export function persistentVerifiedMovements(notices: readonly PersistentChangeNotice[], limit = 3) {
  return sortPersistentNotices(notices.filter((notice) =>
    notice.kind === "NEW_OFFICIAL_OBSERVATION"
    && !notice.sourceHealthOnly
    && notice.currentDisplay !== undefined
    && notice.previousDisplay !== undefined
    && notice.absoluteDelta !== undefined
    && notice.absoluteDeltaDisplay !== undefined
    && notice.direction !== undefined
    && notice.validTime !== undefined
  )).slice(0, limit);
}

export function persistentSourceHealthExceptions(notices: readonly PersistentChangeNotice[]) {
  return sortPersistentNotices(notices.filter((notice) => notice.sourceHealthOnly));
}

export function persistentChangePresentationLabel(notice: PersistentChangeNotice) {
  if (notice.sourceHealthOnly) return "Operational source exception";
  if (notice.kind === "REVISION") return "Accepted factual revision · interpretation not yet governed";
  if (notice.previousDisplay !== undefined && notice.absoluteDelta !== undefined) return "Direction verified · interpretation not yet governed";
  return "Not enough comparable history yet";
}

export function persistentBindingPresentationLabel(binding: PersistentWorldFactualBinding | undefined) {
  if (!binding) return "Verified reading not yet available";
  if (binding.status === "CONNECTED") {
    return binding.temporalHistory?.primary.previous
      ? "Direction verified · interpretation not yet governed"
      : "Not enough comparable history yet";
  }
  if (binding.status === "SOURCE_IDENTIFIED") return "Source identified · verified reading not yet available";
  if (binding.status === "SOURCE_ENABLED_PENDING_ACCEPTANCE") return "Source adapter available · acceptance pending";
  if (binding.status === "BLOCKED") return "Source currently blocked";
  if (binding.status === "FIXTURE_ONLY") return "Configuration pending · not factual";
  return "Verified reading not yet available";
}

export function persistentCoverageSummary(
  model: PersistentWorldReadModel,
  bindings: Readonly<Record<string, PersistentWorldFactualBinding>>,
  branchId: string | null,
): PersistentCoverageSummary {
  const placements = Object.values(model.placements).filter((placement) => placement.depth > 0 && (!branchId || persistentWorldPlacementInBranch(model, placement.id, branchId)));
  const bestByFactor = new Map<string, PersistentWorldFactualBinding>();
  for (const placement of placements) {
    const binding = bindings[placement.id];
    if (!binding) continue;
    const current = bestByFactor.get(placement.canonicalFactorId);
    if (!current || bindingPriority[binding.status] > bindingPriority[current.status]) bestByFactor.set(placement.canonicalFactorId, binding);
  }
  const unique = [...bestByFactor.values()];
  const count = (status: PersistentWorldBindingStatus) => unique.filter((binding) => binding.status === status).length;
  return {
    scopeLabel: branchId ? persistentWorldPlacementLabel(model, model.placements[branchId]) : "All systems",
    totalFactors: bestByFactor.size,
    acceptedReadingFactors: count("CONNECTED"),
    acceptedHistoryFactors: unique.filter((binding) => binding.status === "CONNECTED" && binding.temporalHistory).length,
    comparableHistoryFactors: unique.filter((binding) => binding.status === "CONNECTED" && binding.temporalHistory?.series.some((series) => series.previous)).length,
    sourceIdentifiedFactors: count("SOURCE_IDENTIFIED"),
    pendingFactors: count("SOURCE_ENABLED_PENDING_ACCEPTANCE"),
    blockedFactors: count("BLOCKED"),
    configurationPendingFactors: count("FIXTURE_ONLY") + count("UNMAPPED"),
  };
}
