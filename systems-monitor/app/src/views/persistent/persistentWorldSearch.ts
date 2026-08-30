import {
  persistentWorldPath,
  persistentWorldPlacementLabel,
  type PersistentWorldReadModel
} from "../../data/persistentWorldModel";
import { layoffsSearchAliasesForFactorId } from "../../data/layoffsBranchTaxonomy";

export interface PersistentWorldSearchEntry {
  readonly placementId: string;
  readonly canonicalFactorId: string;
  readonly label: string;
  readonly pathLabels: readonly string[];
  readonly pathText: string;
  readonly definition: string;
  readonly sourceFamily: string;
  readonly aliases: readonly string[];
  readonly depth: number;
  readonly evidencePosture: "MASTER_DEFINED" | "CANDIDATE" | "TEST_FIXTURE";
  readonly searchText: string;
}

const normalize = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

export function buildPersistentWorldSearchIndex(model: PersistentWorldReadModel): readonly PersistentWorldSearchEntry[] {
  return Object.values(model.placements).map((placement) => {
    const factor = model.factors[placement.canonicalFactorId];
    const label = persistentWorldPlacementLabel(model, placement);
    const pathLabels = persistentWorldPath(model, placement.id).map((item) => persistentWorldPlacementLabel(model, item));
    const pathText = pathLabels.join(" → ");
    const aliases = layoffsSearchAliasesForFactorId(placement.canonicalFactorId);
    return Object.freeze({
      placementId: placement.id,
      canonicalFactorId: placement.canonicalFactorId,
      label,
      pathLabels: Object.freeze(pathLabels),
      pathText,
      definition: factor.definition,
      sourceFamily: factor.sourceFamily,
      aliases: Object.freeze(aliases),
      depth: placement.depth,
      evidencePosture: factor.evidencePosture,
      searchText: normalize([label, factor.label, ...aliases, factor.definition, factor.sourceFamily, pathText].join(" "))
    });
  }).sort((left, right) => left.label.localeCompare(right.label) || left.pathText.localeCompare(right.pathText));
}

export function searchPersistentWorld(index: readonly PersistentWorldSearchEntry[], query: string, limit = 12) {
  const terms = normalize(query).split(" ").filter(Boolean);
  if (!terms.length) return [];
  return index.map((entry) => {
    if (!terms.every((term) => entry.searchText.includes(term))) return null;
    const label = normalize(entry.label);
    const score = terms.reduce((total, term) => total
      + (label === term ? 100 : 0)
      + (label.startsWith(term) ? 45 : 0)
      + (label.includes(term) ? 20 : 0)
      + (normalize(entry.sourceFamily).includes(term) ? 4 : 0), 0)
      + (entry.evidencePosture === "TEST_FIXTURE" ? -30 : 8)
      - entry.depth;
    return { entry, score };
  }).filter((item): item is { entry: PersistentWorldSearchEntry; score: number } => Boolean(item))
    .sort((left, right) => right.score - left.score || left.entry.pathText.localeCompare(right.entry.pathText))
    .slice(0, limit)
    .map((item) => item.entry);
}
