import { describe, expect, it } from "vitest";
import {
  createPersistentWorld,
  persistentWorldFingerprint,
  persistentWorldSemanticFingerprint,
  persistentWorldPath,
  persistentWorldPlacementLabel
} from "../src/data/persistentWorldModel";
import {
  persistentWorldFactualBinding,
  persistentWorldFactualBindingForFactor
} from "../src/data/persistentWorldFactualBindings";
import { persistentWorldCandidateSourceProfile } from "../src/data/persistentWorldSourceCatalog";
import {
  persistentWorldGraphNodeLabel,
  persistentWorldPublicRelationshipVisible,
  persistentWorldSemanticIds,
  persistentWorldTargetCamera
} from "../src/views/persistent/PremiumPersistentWorldSurface";
import { persistentWorldUpSelection } from "../src/views/persistent/PersistentWorldShell";
import {
  createPersistentWorldSpatialLayout,
  projectPersistentPlacement
} from "../src/views/persistent/persistentWorldSpatialLayout";
import { buildPersistentWorldSearchIndex } from "../src/views/persistent/persistentWorldSearch";

const WIDTH = 1280;
const HEIGHT = 760;
const model = createPersistentWorld();
const spatial = createPersistentWorldSpatialLayout(model);
const level3Parents = Object.values(model.placements)
  .filter((placement) => placement.depth === 2)
  .sort((left, right) => left.id.localeCompare(right.id));

const approvedLevel3Matrix: Readonly<Record<string, readonly string[]>> = {
  "Output & Growth": ["Real GDP Growth", "Gross Domestic Income", "Industrial Production", "Capacity Utilization", "Real Final Sales", "Manufacturing Output", "Services Output", "Construction Activity", "Business Formation", "Regional Output Breadth"],
  "Consumer Demand": ["Real Personal Consumption", "Retail Sales", "Services Spending", "Disposable Personal Income", "Real Wage Purchasing Power", "Consumer Credit", "Household Saving", "Consumer Sentiment", "Durable Goods Demand", "Housing-Related Spending"],
  "Employer Labor Demand": ["Job Openings", "Hires", "Average Weekly Hours", "Temporary Help Employment", "Overtime Hours", "Hiring Plans", "Vacancy Duration", "Recruiting Intensity", "Gross Job Gains", "Labor Demand Breadth"],
  "Layoffs & Job Destruction": ["Layoffs & Discharges", "Initial UI Claims", "Continued Claims / Insured Unemployment", "Permanent Job Losers", "Temporary Layoffs", "Gross Job Losses", "Establishment Death / Closure Losses", "Firm Death / Shutdown Stress", "Industry Payroll Contraction", "Business Failure / Bankruptcy Stress"],
  "Business Investment": ["Equipment Investment", "Structures Investment", "Intellectual Property Investment", "Core Capital Goods Orders", "Capital Goods Shipments", "Private Construction", "Inventory Investment", "Business Applications", "Manufacturing Backlogs", "Investment Intentions"],
  "Rates & Credit": ["Policy Rate", "Treasury Yield Curve", "Corporate Bond Spreads", "Bank Lending Standards", "Commercial Loan Growth", "Consumer Credit Growth", "Mortgage Rates", "Small-Business Credit", "Delinquency Pressure", "Financial Conditions"],
  "Labor Costs & Wages": ["Average Hourly Earnings", "Employment Cost Index", "Benefits Cost", "Unit Labor Costs", "Real Hourly Compensation", "Wage Growth Breadth", "Production Worker Earnings", "Overtime Pay", "Compensation per Hour", "Wage-Price Pressure"],
  "Productivity & Automation": ["Labor Productivity", "Multifactor Productivity", "Output per Hour", "Capital Deepening", "Software Investment", "Robotics Adoption", "AI-Related Investment", "Process Automation", "Research and Development", "Technology Diffusion"],
  "Labor Supply": ["Labor-Force Participation", "Employment-Population Ratio", "Working-Age Population", "Prime-Age Participation", "Migration and Immigration", "Educational Attainment", "Skills Availability", "Retirement Flows", "Caregiving Constraints", "Geographic Mobility"],
  "Policy, Trade & External Shocks": ["Fiscal Policy", "Trade Volumes", "Tariffs and Restrictions", "Energy Supply", "Food and Agriculture Supply", "Weather Disruption", "Public Health Disruption", "Geopolitical Risk", "Transportation Bottlenecks", "Regulatory Change"]
};

function childrenOf(parentId: string) {
  return model.childrenByPlacement[parentId].map((id) => model.placements[id]);
}

describe("Level-3 framework acceptance machine gate", () => {
  it("matches the independently frozen approved Level-3 parent matrix", () => {
    expect(Object.keys(approvedLevel3Matrix)).toHaveLength(10);
    for (const level1Id of model.childrenByPlacement[model.outcomePlacementId]) {
      const level1 = model.placements[level1Id];
      const level1Label = persistentWorldPlacementLabel(model, level1);
      const actual = model.childrenByPlacement[level1.id].map((id) => persistentWorldPlacementLabel(model, model.placements[id]));
      expect(actual, level1Label).toEqual(approvedLevel3Matrix[level1Label]);
    }
  });

  it("separates immutable topology identity from semantic and governance identity", () => {
    expect(model.topologyFingerprint).toBe("fnv1a32:88684cdb");
    expect(model.semanticFingerprint).toBe(persistentWorldSemanticFingerprint(model));
    const mutable = structuredClone(model);
    const target = level3Parents[0];
    mutable.factors[target.canonicalFactorId].label = `${mutable.factors[target.canonicalFactorId].label} changed`;
    expect(persistentWorldFingerprint(mutable)).toBe(model.topologyFingerprint);
    expect(persistentWorldSemanticFingerprint(mutable)).not.toBe(model.semanticFingerprint);
    const governanceMutation = structuredClone(model);
    const edge = Object.values(governanceMutation.relationships)[0];
    edge.publicationEligibility = "NEVER_ACCEPTED_NEVER_PUBLISHED";
    (governanceMutation.childrenByPlacement[target.parentPlacementId!] as string[]).reverse();
    expect(persistentWorldFingerprint(governanceMutation)).toBe(model.topologyFingerprint);
    expect(persistentWorldSemanticFingerprint(governanceMutation)).not.toBe(model.semanticFingerprint);
  });

  it("certifies all 100 named parents as stable exact-ten semantic records", () => {
    expect(level3Parents).toHaveLength(100);
    expect(new Set(level3Parents.map((parent) => parent.id))).toHaveLength(100);
    expect(new Set(level3Parents.map((parent) => parent.canonicalFactorId))).toHaveLength(100);

    for (const parent of level3Parents) {
      const factor = model.factors[parent.canonicalFactorId];
      const level1 = model.placements[parent.parentPlacementId!];
      const children = childrenOf(parent.id);
      const profile = persistentWorldCandidateSourceProfile(persistentWorldPlacementLabel(model, parent))
        ?? persistentWorldCandidateSourceProfile(factor.label);

      expect(level1.depth, parent.id).toBe(1);
      expect(level1.sector, parent.id).toBe(parent.sector);
      expect(factor.label.trim(), parent.id).not.toBe("");
      expect(factor.definition.trim(), parent.id).not.toBe("");
      expect(factor.sourceFamily.trim(), parent.id).not.toBe("");
      expect(profile, parent.id).toBeDefined();
      expect(["CANDIDATE_DATASET", "DERIVATION_REQUIRED"], parent.id).toContain(profile!.readiness);
      expect(profile!.authority.trim(), parent.id).not.toBe("");
      expect(profile!.dataset.trim(), parent.id).not.toBe("");
      expect(profile!.evidenceUrl, parent.id).toMatch(/^https:\/\//);
      expect(children, parent.id).toHaveLength(10);
      expect(new Set(children.map((child) => child.id)), parent.id).toHaveLength(10);
      expect(children.every((child) => child.depth === 3 && child.parentPlacementId === parent.id), parent.id).toBe(true);
      expect(children.map((child) => child.order), parent.id).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
      expect(persistentWorldGraphNodeLabel(model, parent), parent.id).toBe(persistentWorldPlacementLabel(model, parent));
      expect(persistentWorldUpSelection(model, children[0].id), parent.id).toBe(parent.id);
      expect(persistentWorldPath(model, children[9].id).map((entry) => entry.id).at(-2), parent.id).toBe(parent.id);
    }
  });

  it("certifies the immutable exact-ten handoff and search identity for all parents", () => {
    const before = persistentWorldFingerprint(model);
    const placementIds = Object.keys(model.placements).sort();
    const relationshipIds = Object.keys(model.relationships).sort();
    const index = buildPersistentWorldSearchIndex(model);
    const indexedByPlacement = new Map(index.map((entry) => [entry.placementId, entry]));

    for (const parent of level3Parents) {
      const expected = [model.placements[parent.parentPlacementId!].id, parent.id, ...model.childrenByPlacement[parent.id]];
      expect(persistentWorldSemanticIds(model, parent.id), parent.id).toEqual(expected);
      expect(indexedByPlacement.get(parent.id)?.canonicalFactorId, parent.id).toBe(parent.canonicalFactorId);
      expect(indexedByPlacement.get(parent.id)?.pathLabels.at(-1), parent.id).toBe(persistentWorldPlacementLabel(model, parent));
      for (const childId of model.childrenByPlacement[parent.id]) {
        expect(indexedByPlacement.get(childId)?.placementId, childId).toBe(childId);
        expect(indexedByPlacement.get(childId)?.pathLabels.at(-2), childId).toBe(persistentWorldPlacementLabel(model, parent));
      }
      expect(persistentWorldFingerprint(model), parent.id).toBe(before);
    }

    expect(Object.keys(model.placements).sort()).toEqual(placementIds);
    expect(Object.keys(model.relationships).sort()).toEqual(relationshipIds);
    expect(before).toBe("fnv1a32:88684cdb");
  });

  it.each(["TOP_DOWN", "CINEMATIC_2_5D"] as const)("fits all 100 exact-ten neighborhoods in %s", (viewMode) => {
    for (const parent of level3Parents) {
      const camera = persistentWorldTargetCamera(model, parent.id, false, viewMode, WIDTH, HEIGHT, spatial);
      const neighborhood = [parent, ...childrenOf(parent.id)];
      const projected = neighborhood.map((placement) => projectPersistentPlacement(
        placement,
        viewMode === "CINEMATIC_2_5D" ? spatial.zByPlacementId[placement.id] : 0,
        camera,
        { zoom: 1, panX: 0, panY: 0 },
        WIDTH,
        HEIGHT
      ));

      expect(projected, parent.id).toHaveLength(11);
      expect(projected.every((point) => Number.isFinite(point.x) && Number.isFinite(point.y)), parent.id).toBe(true);
      expect(projected.every((point) => point.x >= 36 && point.x <= WIDTH - 36), parent.id).toBe(true);
      expect(projected.every((point) => point.y >= 36 && point.y <= HEIGHT - 36), parent.id).toBe(true);
      expect(Math.max(...projected.map((point) => point.perspectiveScale)), parent.id).toBeLessThanOrEqual(1.36);
      expect(Math.min(...projected.map((point) => point.perspectiveScale)), parent.id).toBeGreaterThanOrEqual(.7);
    }
  });

  it("certifies connector authority for every parent without accepting a relationship", () => {
    const publicHierarchy = Object.values(model.relationships).filter((edge) => persistentWorldPublicRelationshipVisible(model, edge));
    expect(model.coverage.acceptedRelationshipCount).toBe(0);
    expect(model.coverage.factualRelationshipCount).toBe(0);
    expect(publicHierarchy).toHaveLength(1110);

    for (const parent of level3Parents) {
      const path = new Set(persistentWorldPath(model, parent.id).map((entry) => entry.id));
      const childIds = new Set(model.childrenByPlacement[parent.id]);
      const focusEdges = publicHierarchy.filter((edge) =>
        (path.has(edge.fromPlacementId) && path.has(edge.toPlacementId))
        || (edge.fromPlacementId === parent.id && childIds.has(edge.toPlacementId))
      );
      expect(focusEdges.filter((edge) => edge.fromPlacementId === parent.id), parent.id).toHaveLength(10);
      expect(focusEdges, parent.id).toHaveLength(12);
      expect(focusEdges.every((edge) => edge.relationshipClass === "HIERARCHY_TETHER"), parent.id).toBe(true);
      expect(focusEdges.every((edge) => edge.status === "TEST_FIXTURE"), parent.id).toBe(true);
      expect(focusEdges.every((edge) => edge.publicationEligibility === "NEVER_ACCEPTED_NEVER_PUBLISHED"), parent.id).toBe(true);
    }
  });

  it("keeps all 100 inspector identities and source postures node-specific", () => {
    const seen = new Set<string>();
    for (const parent of level3Parents) {
      const factor = model.factors[parent.canonicalFactorId];
      const label = persistentWorldPlacementLabel(model, parent);
      const profile = persistentWorldCandidateSourceProfile(label) ?? persistentWorldCandidateSourceProfile(factor.label);
      expect(seen.has(parent.canonicalFactorId), parent.id).toBe(false);
      seen.add(parent.canonicalFactorId);
      expect(label, parent.id).toBeTruthy();
      expect(factor.definition, parent.id).toBeTruthy();
      expect(profile?.summary, parent.id).toBeTruthy();
      expect(profile?.registrationState, parent.id).toMatch(/CANDIDATE_NOT_REGISTERED|SOURCE_DESIGN_REQUIRED/);
      expect(persistentWorldUpSelection(model, parent.id), parent.id).toBe(parent.parentPlacementId);
    }
    expect(seen).toHaveLength(100);
  });

  it("regression-locks the four accepted bindings and three source-identified records", () => {
    const expectedConnected = [
      ["Labor-Force Participation", "LNS11300000", "61.4 percent"],
      ["Initial Claims", "DOL-UI-SA-INITIAL", "209,000 claims"],
      ["Job Openings", "JTS000000000000000JOL", "7,359 thousands"],
      ["Hires", "JTS000000000000000HIL", "5,348 thousands"]
    ] as const;
    for (const [label, seriesId, displayValue] of expectedConnected) {
      const placement = level3Parents.find((item) => persistentWorldPlacementLabel(model, item) === label)
        ?? level3Parents.find((item) => model.factors[item.canonicalFactorId].label === label);
      expect(placement, label).toBeDefined();
      const binding = persistentWorldFactualBindingForFactor(placement!.canonicalFactorId, label);
      expect(binding.status, label).toBe("CONNECTED");
      expect(binding.seriesId, label).toBe(seriesId);
      expect(binding.displayValue, label).toBe(displayValue);
      expect(binding.validTime, label).toBeTruthy();
      expect(binding.provider, label).toBeTruthy();
      expect(binding.evidenceUrl, label).toMatch(/^https:\/\//);
      expect(binding.methodologyUrl, label).toMatch(/^https:\/\//);
      expect(binding.acquisitionProvenanceUrl, label).toMatch(/^https:\/\//);
      expect(binding.freshness, label).toBeTruthy();
    }

    for (const [label, candidateSeriesId] of [
      ["Average Weekly Hours", "CES0500000002"],
      ["Average Hourly Earnings", "CES0500000003"],
      ["Employment-Population Ratio", "LNS12300000"]
    ] as const) {
      expect(persistentWorldFactualBinding(label), label).toMatchObject({ status: "SOURCE_IDENTIFIED", candidateSeriesId });
      expect(persistentWorldFactualBinding(label).displayValue, label).toBeUndefined();
    }
  });

  it("mutation-proves all 900 fixtures remain non-factual and non-authoritative", () => {
    const fixtures = Object.values(model.placements).filter((placement) => model.factors[placement.canonicalFactorId].evidencePosture === "TEST_FIXTURE");
    expect(fixtures).toHaveLength(900);
    for (const fixture of fixtures) {
      const factor = model.factors[fixture.canonicalFactorId];
      expect(persistentWorldFactualBindingForFactor(fixture.canonicalFactorId, factor.label), fixture.id).toEqual({ status: "FIXTURE_ONLY", label: factor.label });
      const parentEdge = model.relationships[`hierarchy:${fixture.parentPlacementId}:${fixture.id}`];
      expect(parentEdge.status, fixture.id).toBe("TEST_FIXTURE");
      expect(parentEdge.evidenceClass, fixture.id).toBe("SYNTHETIC");
      expect(parentEdge.publicationEligibility, fixture.id).toBe("NEVER_ACCEPTED_NEVER_PUBLISHED");
    }
    expect(JSON.stringify(model)).not.toContain('"status":"ACCEPTED"');
    expect(JSON.stringify(model)).not.toContain('"publicationClass":"factual"');
  });
});
