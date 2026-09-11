import { describe, expect, it } from "vitest";
import taxonomyRegistry from "../../data/config/layoffs/taxonomy.json";
import claimClassRegistry from "../../data/config/layoffs/level4_claim_classes.json";
import { LAYOFFS_CLASSIFIED_LEVEL4_FACTOR_COUNT, layoffsFactorSourceState, layoffsFactorSourceStates } from "../src/data/layoffsBranchReadModel";
import { layoffsBranchTaxonomy } from "../src/data/layoffsBranchTaxonomy";
import { createPersistentWorld, persistentWorldPlacementLabel, persistentWorldResolvePlacementId } from "../src/data/persistentWorldModel";

describe("Layoffs & Job Destruction canonical hierarchy", () => {
  it("keeps the cross-runtime JSON registry aligned with the TypeScript registry", () => {
    expect(taxonomyRegistry.schemaVersion).toBe("layoffs-branch-taxonomy-1.0.0");
    expect(taxonomyRegistry.groups).toHaveLength(10);
    expect(taxonomyRegistry.groups.every((group) => group.placements.length === 10)).toBe(true);
    expect(taxonomyRegistry.groups.map((group) => ({
      id: group.id,
      label: group.label,
      placements: group.placements.map((placement) => ({ label: placement.label, canonicalFactorId: placement.canonicalFactorId }))
    }))).toEqual(layoffsBranchTaxonomy.map((group) => ({
      id: group.id,
      label: group.label,
      placements: group.placements.map((placement) => ({ label: placement.label, canonicalFactorId: placement.canonicalFactorId }))
    })));
  });

  it("installs the frozen exact-ten Level-2 and 10×10 Level-3 placements", () => {
    const model = createPersistentWorld();
    const branch = model.placements["placement:layoffs-job-destruction"];
    const level2 = model.childrenByPlacement[branch.id].map((id) => model.placements[id]);

    expect(layoffsBranchTaxonomy).toHaveLength(10);
    expect(layoffsBranchTaxonomy.every((group) => group.placements.length === 10)).toBe(true);
    expect(level2).toHaveLength(10);
    expect(level2.map((placement) => persistentWorldPlacementLabel(model, placement))).toEqual(layoffsBranchTaxonomy.map((group) => group.label));

    level2.forEach((placement, index) => {
      const children = model.childrenByPlacement[placement.id].map((id) => model.placements[id]);
      expect(children).toHaveLength(10);
      expect(children.map((child) => persistentWorldPlacementLabel(model, child))).toEqual(layoffsBranchTaxonomy[index].placements.map((candidate) => candidate.label));
      expect(children.every((child) => model.factors[child.canonicalFactorId].evidencePosture === "CANDIDATE")).toBe(true);
    });
  });

  it("contains no Renderer fixture factor labels in the factual-branch candidate hierarchy", () => {
    const model = createPersistentWorld();
    const branch = model.placements["placement:layoffs-job-destruction"];
    const branchPlacements = model.childrenByPlacement[branch.id].flatMap((level2Id) => [
      model.placements[level2Id],
      ...model.childrenByPlacement[level2Id].map((level3Id) => model.placements[level3Id])
    ]);

    expect(branchPlacements).toHaveLength(110);
    expect(branchPlacements.map((placement) => persistentWorldPlacementLabel(model, placement)).join("\n")).not.toMatch(/Renderer fixture/i);
    expect(branchPlacements.every((placement) => !placement.canonicalFactorId.startsWith("fixture-factor:"))).toBe(true);
    expect(branchPlacements.every((placement) => !placement.id.startsWith("fixture-placement:"))).toBe(true);
  });

  it("reuses one canonical factor for repeated placements and preserves the fixed topology", () => {
    const model = createPersistentWorld();
    const branch = model.placements["placement:layoffs-job-destruction"];
    const level3 = model.childrenByPlacement[branch.id].flatMap((level2Id) => model.childrenByPlacement[level2Id].map((level3Id) => model.placements[level3Id]));
    const placementsNamed = (label: string) => level3.filter((placement) => persistentWorldPlacementLabel(model, placement) === label);

    const realOutput = placementsNamed("Real Output Growth");
    expect(realOutput).toHaveLength(6);
    expect(new Set(realOutput.map((placement) => placement.canonicalFactorId))).toEqual(new Set(["factor:canonical:real-output-growth"]));

    const lendingStandards = placementsNamed("C&I Lending Standards");
    expect(lendingStandards).toHaveLength(5);
    expect(new Set(lendingStandards.map((placement) => placement.canonicalFactorId))).toEqual(new Set(["factor:canonical:candi-lending-standards"]));

    const corporateProfits = placementsNamed("Corporate Profits");
    const corporateProfitability = placementsNamed("Corporate Profitability");
    expect(corporateProfits).toHaveLength(4);
    expect(corporateProfitability).toHaveLength(2);
    expect(new Set(corporateProfits.map((placement) => placement.canonicalFactorId))).toEqual(new Set(["factor:canonical:corporate-profits"]));
    expect(new Set(corporateProfitability.map((placement) => placement.canonicalFactorId))).toEqual(new Set(["factor:canonical:corporate-profitability"]));

    const closingLoss = placementsNamed("Closing Establishment Losses");
    const establishmentClosures = placementsNamed("Establishment Closures");
    expect(new Set([...closingLoss, ...establishmentClosures].map((placement) => placement.canonicalFactorId))).toEqual(new Set(["factor:canonical:establishment-closures"]));

    expect(model.layoutVersion).toBe("employment-sectors-1.1.0");
    expect(model.topologyFingerprint).toBe("fnv1a32:88684cdb");
    expect(persistentWorldResolvePlacementId(model, "fixture-placement:layoffs-job-destruction:01:01")).toBe("placement:layoffs-job-destruction:layoffs-and-discharges:real-output-growth");
  });

  it("classifies all 64 canonical Level-4 factors without promoting observations or relationships", () => {
    const canonicalFactors = new Set(taxonomyRegistry.groups.flatMap((group) => group.placements.map((placement) => placement.canonicalFactorId)));
    const allowedClasses = new Set(["A_DIRECT_OBS", "B_CALC", "C_EVENT_OR_STRUCTURAL", "D_TAXONOMY_OR_SOURCE_PROBLEM"]);
    const counts = Object.fromEntries([...allowedClasses].map((claimClass) => [claimClass, claimClassRegistry.factors.filter((row) => row.claimClass === claimClass).length]));

    expect(claimClassRegistry.authority).toBe("GOVERNED_FACTOR_CLASSIFICATION");
    expect(claimClassRegistry.observationPromotionAuthority).toBe("NONE");
    expect(claimClassRegistry.relationshipPromotionAuthority).toBe("NONE");
    expect(claimClassRegistry.factors).toHaveLength(64);
    expect(new Set(claimClassRegistry.factors.map((row) => row.canonicalFactorId))).toEqual(canonicalFactors);
    expect(counts).toEqual({ A_DIRECT_OBS: 38, B_CALC: 12, C_EVENT_OR_STRUCTURAL: 5, D_TAXONOMY_OR_SOURCE_PROBLEM: 9 });
    expect(LAYOFFS_CLASSIFIED_LEVEL4_FACTOR_COUNT).toBe(64);

    claimClassRegistry.factors.forEach((row) => {
      expect(canonicalFactors.has(row.canonicalFactorId), row.canonicalFactorId).toBe(true);
      expect(allowedClasses.has(row.claimClass), row.canonicalFactorId).toBe(true);
      expect(row.sourceRefs.length, row.canonicalFactorId).toBeGreaterThan(0);
      expect(layoffsFactorSourceState(row.canonicalFactorId)?.claimClassification).toMatchObject({
        canonicalFactorId: row.canonicalFactorId,
        claimClass: row.claimClass,
        rationale: row.rationale
      });
    });
  });

  it("canonicalizes the legacy plural business-formations source identity without adding a source-only node", () => {
    expect(Object.keys(layoffsFactorSourceStates)).toHaveLength(76);
    expect(layoffsFactorSourceState("factor:canonical:business-formations")).toBeUndefined();
    expect(layoffsFactorSourceState("factor:canonical:business-formation")?.series).toEqual(
      expect.arrayContaining([expect.objectContaining({ sourceId: "census-bfs", seriesId: "BFS:T:BF_BF4Q:SA" })])
    );
  });
});
