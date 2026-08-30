import type {
  ForecastRecord,
  MetricRecord,
  PublicNavigationNode,
  PublicSnapshot,
  RankedHumanCapitalItem,
  StateType
} from "../data/publicSnapshotTypes";

const allViews = ["summary", "verified", "outlook"] as const;

function rankedNode(prefix: string, rank: number, depth: number): PublicNavigationNode {
  const boundary = depth === 1 && rank >= 10;
  return {
    id: `fixture-${prefix}-${rank}`,
    slug: `fixture-${prefix}-${rank}`,
    label: `SYNTHETIC TEST ${prefix.toUpperCase()} ${String(rank).padStart(2, "0")}`,
    rank,
    priorRank: rank === 3 ? 5 : rank,
    rankState: boundary ? "near-tie" : rank === 3 ? "changed" : "stable",
    nearTie: boundary,
    nearCutoff: depth === 1 && rank === 11,
    stateSummaryRefs: [rank % 2 === 0 ? "fixture-metric-calc" : "fixture-metric-obs"],
    childRefs: [],
    availableViews: [...allViews]
  };
}

const levelThree = Array.from({ length: 10 }, (_, index) =>
  rankedNode("factor", index + 1, 2)
);

const levelTwo = Array.from({ length: 11 }, (_, index) => {
  const node = rankedNode("driver", index + 1, 1);
  if (index === 0) node.childRefs = levelThree.map((child) => child.id);
  return node;
});

const systems: PublicNavigationNode[] = Array.from({ length: 10 }, (_, index) => {
  const node = rankedNode("system", index + 1, 0);
  if (index === 0) node.childRefs = levelTwo.map((child) => child.id);
  return node;
});

const navigationNodes = Object.fromEntries(
  [...levelTwo, ...levelThree].map((node) => [node.id, node])
);

const periods = ["P-5", "P-4", "P-3", "P-2", "P-1", "P0"];

function series(start: number, step: number) {
  return periods.map((period, index) => ({
    period,
    displayPeriod: `Synthetic period ${index + 1}`,
    value: start + index * step
  }));
}

const metrics: MetricRecord[] = [
  {
    id: "fixture-metric-obs",
    stateType: "OBS",
    label: "SYNTHETIC TEST observed signal",
    value: 64,
    displayValue: "64 synthetic-index-points",
    unit: "synthetic-index-points",
    validTime: "2000-01-01T00:00:00Z",
    sourceRefs: ["fixture-source-current"],
    provenanceRefs: ["fixture-provenance-observed"],
    direction: "up",
    series: series(48, 3)
  },
  {
    id: "fixture-metric-calc",
    stateType: "CALC",
    label: "SYNTHETIC TEST calculated state",
    value: 51,
    displayValue: "51 synthetic-index-points",
    unit: "synthetic-index-points",
    validTime: "2000-01-01T00:00:00Z",
    sourceRefs: ["fixture-source-current"],
    provenanceRefs: ["fixture-provenance-calculated"],
    direction: "flat",
    method: "SYNTHETIC TEST deterministic transform v1",
    series: series(55, -1)
  }
];

function forecast(
  horizon: ForecastRecord["horizon"],
  stateType: ForecastRecord["stateType"],
  scenario: string,
  offset: number
): ForecastRecord {
  return {
    id: `fixture-forecast-${horizon}-${scenario}`,
    stateType,
    label: `SYNTHETIC TEST ${horizon} ${scenario} range`,
    horizon,
    scenario,
    forecastOrigin: "2000-01-01T00:00:00Z",
    validTime: `fixture-window-${horizon}`,
    range: [42 + offset, 58 + offset],
    displayRange: `${42 + offset}–${58 + offset} synthetic-index-points`,
    unit: "synthetic-index-points",
    sourceRefs: ["fixture-source-current", "fixture-source-delayed"],
    evidence: {
      dataCoverage: "SYNTHETIC TEST coverage: bounded",
      relationshipEvidence: "SYNTHETIC TEST mix of measured and modeled relationships",
      historicalModelSkill: "SYNTHETIC TEST skill state — not production-evaluated",
      regimeStability: "SYNTHETIC TEST regime stability: mixed",
      sourceSupport: "Two synthetic sources",
      measuredVsModeled: "One direct measure; two modeled test links"
    },
    positivePressures: ["SYNTHETIC TEST pressure alpha", "SYNTHETIC TEST pressure beta"],
    offsets: ["SYNTHETIC TEST offset gamma", "SYNTHETIC TEST constraint delta"],
    assumptions: scenario === "baseline" ? ["SYNTHETIC TEST baseline assumption"] : ["SYNTHETIC TEST scenario assumption"],
    whatWouldChangeOurMind: [
      "A synthetic source revision reverses the test direction",
      "Modeled test relationship evidence becomes insufficient"
    ],
    changeAttribution: "SYNTHETIC TEST prior-range change: source revision plus offset update",
    series: periods.slice(3).map((period, index) => ({
      period,
      displayPeriod: `Synthetic forecast period ${index + 1}`,
      value: 48 + offset + index * 2,
      rangeLow: 42 + offset + index,
      rangeHigh: 56 + offset + index * 2
    }))
  };
}

const industries: RankedHumanCapitalItem[] = Array.from({ length: 10 }, (_, index) => ({
  id: `fixture-industry-${index + 1}`,
  label: `SYNTHETIC TEST INDUSTRY ${String(index + 1).padStart(2, "0")}`,
  rank: index + 1,
  priorRank: index === 2 ? 5 : index + 1,
  displayValue: `${90 - index * 4} synthetic human-capital requirement points`,
  nearTie: index === 8 || index === 9,
  nearCutoff: index === 9
}));

const occupations: RankedHumanCapitalItem[] = Array.from({ length: 11 }, (_, index) => ({
  id: `fixture-occupation-${index + 1}`,
  label: index === 0 ? "SYNTHETIC TEST OCCUPATION ALPHA" : `SYNTHETIC TEST OCCUPATION ${String(index + 1).padStart(2, "0")}`,
  rank: index + 1,
  priorRank: index === 3 ? 7 : index + 1,
  displayValue: `${120 - index * 5} synthetic expected-opening units`,
  nearTie: index === 9 || index === 10,
  nearCutoff: index === 10
}));

export const phase2Fixture: PublicSnapshot = {
  schemaVersion: "1.0.0",
  contractVersion: "1.0.0",
  snapshot: {
    id: "fixture-phase2-ui-shell",
    evaluatedAt: "2000-01-02T00:00:00Z",
    generatedAt: "2000-01-02T00:01:00Z",
    publishedAt: "2000-01-02T00:05:00Z",
    asOf: "2000-01-01T23:59:59Z",
    sourceSnapshotId: "fixture-sources-phase2-001",
    publicationClass: "fixture"
  },
  systems,
  sources: {
    "fixture-source-current": {
      sourceId: "fixture-source-current",
      provider: "SYNTHETIC TEST PROVIDER — NOT A SOURCE",
      dataset: "SYNTHETIC TEST MONTHLY SERIES",
      authorityTier: "fixture-only",
      methodologyUrl: "https://auxsays.com/systems-monitor/",
      observationTime: "2000-01-01T00:00:00Z",
      publishedAt: "2000-01-01T06:00:00Z",
      retrievedAt: "2000-01-01T08:00:00Z",
      freshnessEvaluatedAt: "2000-01-02T00:00:00Z",
      nextExpectedReleaseAt: "2000-02-01T06:00:00Z",
      freshness: "current",
      freshnessReason: "Fixture monthly cadence remains inside its synthetic release window.",
      revision: "fixture revision 1",
      vintage: "fixture vintage 2000-01",
      publicDisplayAllowed: true,
      attributionRequired: true
    },
    "fixture-source-delayed": {
      sourceId: "fixture-source-delayed",
      provider: "SYNTHETIC TEST PROVIDER DELAYED — NOT A SOURCE",
      dataset: "SYNTHETIC TEST DELAYED SERIES",
      authorityTier: "fixture-only",
      methodologyUrl: "https://auxsays.com/systems-monitor/",
      observationTime: "2000-01-01T00:00:00Z",
      publishedAt: "2000-01-01T06:00:00Z",
      retrievedAt: "2000-01-01T08:00:00Z",
      freshnessEvaluatedAt: "2000-02-02T00:00:00Z",
      nextExpectedReleaseAt: "2000-02-01T06:00:00Z",
      freshness: "delayed",
      freshnessReason: "Fixture expected release has passed; no substitute conclusion is produced.",
      revision: "fixture revision pending",
      vintage: "fixture vintage 2000-01",
      publicDisplayAllowed: true,
      attributionRequired: true
    },
    "fixture-source-stale": {
      sourceId: "fixture-source-stale",
      provider: "SYNTHETIC TEST PROVIDER STALE — NOT A SOURCE",
      dataset: "SYNTHETIC TEST STALE SERIES",
      authorityTier: "fixture-only",
      methodologyUrl: "https://auxsays.com/systems-monitor/",
      observationTime: "1999-10-01T00:00:00Z",
      publishedAt: "1999-10-01T06:00:00Z",
      retrievedAt: "1999-10-01T08:00:00Z",
      freshnessEvaluatedAt: "2000-02-02T00:00:00Z",
      nextExpectedReleaseAt: "1999-11-01T06:00:00Z",
      freshness: "stale",
      freshnessReason: "Fixture evaluation is beyond the declared synthetic cadence.",
      revision: "fixture revision unavailable",
      vintage: "fixture vintage 1999-10",
      publicDisplayAllowed: true,
      attributionRequired: true
    }
  },
  events: [
    {
      id: "fixture-event-alpha",
      label: "SYNTHETIC TEST EVENT ALPHA — NOT A REAL EVENT",
      stateType: "OBS" as StateType,
      validTime: "2000-01-01T12:00:00Z",
      sourceRefs: ["fixture-source-current"]
    }
  ],
  outlook: {
    horizons: [
      { id: "current-year", label: "Current Year" },
      { id: "next-year", label: "Next Year" },
      { id: "plus-3-years", label: "+3 Years" }
    ],
    forecasts: [
      forecast("current-year", "FCST", "baseline", 0),
      forecast("next-year", "FCST", "baseline", 3),
      forecast("plus-3-years", "FCST", "baseline", 6),
      forecast("current-year", "SCEN", "fixture-scenario-alpha", -4),
      forecast("next-year", "SCEN", "fixture-scenario-alpha", -2),
      forecast("plus-3-years", "SCEN", "fixture-scenario-alpha", 0)
    ],
    industries,
    occupations,
    demandAllocation: [
      {
        id: "fixture-demand-allocation",
        label: "SYNTHETIC TEST demand redistribution",
        allocationType: "final-demand allocation share",
        stateType: "CALC",
        displayValue: "52 synthetic allocation points",
        changeLabel: "+3 synthetic points versus prior fixture",
        sourceRefs: ["fixture-source-current"]
      },
      {
        id: "fixture-constrained-allocation",
        label: "SYNTHETIC TEST constrained allocation",
        allocationType: "constrained resource allocation share",
        stateType: "SCEN",
        displayValue: "41 synthetic allocation points",
        changeLabel: "Scenario-only redistribution",
        sourceRefs: ["fixture-source-delayed"]
      }
    ]
  },
  extensions: {
    "auxsays.phase2.metrics": metrics,
    "auxsays.phase2.trace": {
      nodes: [
        { id: "trace-source", label: "SYNTHETIC TEST observed input", stateType: "OBS" },
        { id: "trace-calc", label: "SYNTHETIC TEST calculated state", stateType: "CALC" },
        { id: "trace-factor", label: "SYNTHETIC TEST modeled factor", stateType: "CALC" },
        { id: "trace-forecast", label: "SYNTHETIC TEST forecast range", stateType: "FCST" },
        { id: "trace-scenario", label: "SYNTHETIC TEST scenario offset", stateType: "SCEN" },
        { id: "trace-hypothesis", label: "SYNTHETIC TEST hypothesis candidate", stateType: "CALC" }
      ],
      edges: [
        { id: "edge-direct", from: "trace-source", to: "trace-calc", classification: "Direct", direction: "positive", lag: "same synthetic period", evidenceStrength: "fixture direct record", provenanceRef: "fixture-source-current", description: "Direct transformation of the synthetic observed input." },
        { id: "edge-statistical", from: "trace-calc", to: "trace-factor", classification: "Statistical", direction: "positive", lag: "one synthetic period", evidenceStrength: "fixture statistical test", provenanceRef: "fixture-source-current", description: "Statistical association in the synthetic fixture." },
        { id: "edge-modeled", from: "trace-factor", to: "trace-forecast", classification: "Modeled", direction: "positive", lag: "selected horizon", evidenceStrength: "fixture model-only", provenanceRef: "fixture-source-current", description: "Modeled link to the synthetic forecast range." },
        { id: "edge-scenario", from: "trace-scenario", to: "trace-forecast", classification: "Modeled", direction: "offsetting", lag: "selected horizon", evidenceStrength: "fixture scenario assumption", provenanceRef: "fixture-source-delayed", description: "Offsetting scenario path; not observed evidence." },
        { id: "edge-hypothesis", from: "trace-hypothesis", to: "trace-factor", classification: "Hypothesis", direction: "negative", lag: "unknown fixture lag", evidenceStrength: "unconfirmed fixture candidate", provenanceRef: "fixture-source-delayed", description: "Hypothesis-only relationship; never presented as accepted causality." }
      ]
    },
    "auxsays.phase2.fixtureVariants": [
      "normal", "loading", "delayed", "stale", "insufficient-evidence",
      "forecast-unavailable", "high-disagreement", "partial-payload", "snapshot-unavailable"
    ],
    "auxsays.phase2.geographies": [
      { id: "fixture-us", label: "SYNTHETIC TEST geography — national" },
      { id: "fixture-region-alpha", label: "SYNTHETIC TEST geography — region alpha" }
    ],
    "auxsays.phase2.ranges": [
      { id: "fixture-6-period", label: "6 synthetic periods" },
      { id: "fixture-3-period", label: "3 synthetic periods" }
    ],
    "auxsays.phase2.navigationNodes": navigationNodes
  }
};
