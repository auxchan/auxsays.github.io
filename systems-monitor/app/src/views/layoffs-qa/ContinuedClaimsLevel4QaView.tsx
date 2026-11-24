import {
  acceptedLayoffsHistoryFreshness,
  displayAcceptedLayoffsValue,
  type LayoffsAcceptedSeriesSummary,
} from "../../data/layoffsAcceptedHistoryReadModel";
import {
  CONTINUED_CLAIMS_ACCEPTED_HISTORY_REUSE_RECORDS,
  CONTINUED_CLAIMS_ACCEPTED_STRUCTURAL_RELATIONSHIPS,
  CONTINUED_CLAIMS_FORECASTING,
  CONTINUED_CLAIMS_GATE_B,
  CONTINUED_CLAIMS_HUMAN_QA,
  CONTINUED_CLAIMS_PARENT_BOUNDARY,
  CONTINUED_CLAIMS_PARENT_LABEL,
  CONTINUED_CLAIMS_REVIEW_STATE,
  CONTINUED_CLAIMS_UNEXPLAINED_RENDERER_FIXTURES,
  continuedClaimsParentObservations,
  continuedClaimsProductionPlacements,
  type ContinuedClaimsProductionPlacement,
} from "../../data/continuedClaimsReadModel";
import { StructuralNodeIcon } from "../motion/StructuralNodeIcon";
import type { StructuralNodeSymbol } from "../motion/structuralVisualLanguage";
import "./layoffsLevel4Qa.css";

const factorSymbols: Readonly<Record<string, StructuralNodeSymbol>> = Object.freeze({
  "factor:canonical:initial-claims": "claims",
  "factor:canonical:hires-rate": "hire",
  "factor:canonical:job-openings-rate": "openings",
  "factor:canonical:total-nonfarm-payroll-change": "briefcase",
  "factor:canonical:temporary-help-employment": "people",
  "factor:canonical:average-weekly-hours": "clock",
  "factor:canonical:business-formations-within-4-quarters": "factory",
  "factor:canonical:real-gdp-growth": "ratio",
  "factor:canonical:real-personal-consumption-expenditures-growth": "people",
  "factor:canonical:state-level-payroll-growth-breadth": "labor-market",
});

function recordCount(series: LayoffsAcceptedSeriesSummary) {
  return series.history.length + series.revisionChainCount;
}

function PlacementPaths({ row }: { row: ContinuedClaimsProductionPlacement }) {
  return <details className="sm-l4qa-placements"><summary>Canonical reuse · {row.placementPaths.length} placement{row.placementPaths.length === 1 ? "" : "s"}</summary><ul>{row.placementPaths.map((path) => <li key={path}>{path}</li>)}</ul></details>;
}

function AcceptedSeries({ series }: { series: LayoffsAcceptedSeriesSummary }) {
  return <article className="sm-l4qa-series" data-source-state="accepted">
    <header><div><span>{series.seriesLabel}</span><code>{series.sourceSeriesId}</code></div><strong>ACCEPTED OBSERVATION</strong></header>
    <dl className="sm-l4qa-facts">
      <div><dt>Current accepted value</dt><dd>{series.currentDisplay}<small>{series.current.validTime}</small></dd></div>
      <div><dt>Accepted records</dt><dd>{recordCount(series)}<small>{series.acceptedPeriodCount} distinct periods</small></dd></div>
      <div><dt>History state</dt><dd>{acceptedLayoffsHistoryFreshness(series.sourceId)}<small>{series.current.sourceRevisionStatus.replaceAll("_", " ")}</small></dd></div>
      <div><dt>Source</dt><dd>{series.provider}<small>{series.dataset}</small></dd></div>
    </dl>
    <details className="sm-l4qa-history"><summary>Recent accepted history</summary><ol>{series.recentHistory.map((historyRow) => <li key={historyRow.observationId}><time>{historyRow.validTime}</time><span>{displayAcceptedLayoffsValue(historyRow.value, historyRow.unit)}</span><small>{historyRow.sourceRevisionStatus.replaceAll("_", " ")}</small></li>)}</ol></details>
  </article>;
}

function PendingState({ row }: { row: ContinuedClaimsProductionPlacement }) {
  const blocked = row.productionDisposition === "BLOCKED_CREDENTIAL";
  return <article className="sm-l4qa-series sm-l4qa-disposition" data-source-state={blocked ? "blocked" : "pending"}>
    <header><div><span>Governed production state</span><code>{row.selectors.join(" · ") || "No governed selector"}</code></div><strong>{row.productionDisposition.replaceAll("_", " ")}</strong></header>
    <dl className="sm-l4qa-facts">
      <div><dt>Evidence class</dt><dd>{row.claimClass.replaceAll("_", " ")}</dd></div>
      <div><dt>Official source</dt><dd>{row.sourceIds.join(", ") || "Not selected"}</dd></div>
      <div><dt>History state</dt><dd>{row.acceptedHistoryState.replaceAll("_", " ")}</dd></div>
      <div><dt>Current blocker</dt><dd>{row.blocker}</dd></div>
    </dl>
    {row.recommendation && <p className="sm-l4qa-recommendation"><strong>Decision required:</strong> {row.recommendation}</p>}
  </article>;
}

export function ContinuedClaimsLevel4QaView() {
  const acceptedPlacements = continuedClaimsProductionPlacements.filter((row) => row.productionDisposition === "ACCEPTED_OBSERVATION");
  return <div className="sm-l4qa" data-human-qa={CONTINUED_CLAIMS_HUMAN_QA} data-unexplained-renderer-fixtures={CONTINUED_CLAIMS_UNEXPLAINED_RENDERER_FIXTURES}>
    <header className="sm-l4qa-hero"><div><span>{CONTINUED_CLAIMS_PARENT_LABEL} · exact ten</span><h1>Production-state Human QA</h1><p>Review the parent identity, both distinct DOL observations, five reused accepted histories, and every governed pending or blocked child state.</p><a className="sm-l4qa-node-link" href="/systems-monitor/#persistent-world/placement%3Alayoffs-job-destruction%3Acontinued-claims-insured-unemployment">Open the node interface</a></div><dl><div><dt>Human QA</dt><dd>{CONTINUED_CLAIMS_HUMAN_QA}</dd></div><div><dt>Placements</dt><dd>{continuedClaimsProductionPlacements.length}</dd></div><div><dt>Accepted factors</dt><dd>{acceptedPlacements.length}</dd></div><div><dt>Reused records</dt><dd>{CONTINUED_CLAIMS_ACCEPTED_HISTORY_REUSE_RECORDS}</dd></div></dl></header>
    <aside className="sm-l4qa-boundary"><strong>Scientific boundary</strong><span>Hierarchy is navigation only. Accepted structural relationships: {CONTINUED_CLAIMS_ACCEPTED_STRUCTURAL_RELATIONSHIPS}. Gate B: {CONTINUED_CLAIMS_GATE_B}. Forecasting: {CONTINUED_CLAIMS_FORECASTING.replaceAll("_", " ")}.</span><small>{CONTINUED_CLAIMS_REVIEW_STATE.replaceAll("_", " ")}</small></aside>
    <section className="sm-l4qa-parent" aria-labelledby="continued-claims-parent-title">
      <header><div><span>Parent outcome resolution</span><h2 id="continued-claims-parent-title">Two observations, never one scalar</h2><p>{CONTINUED_CLAIMS_PARENT_BOUNDARY}</p></div><b>SOURCE ENABLED · ACCEPTANCE PENDING</b></header>
      <div className="sm-l4qa-parent-grid">{continuedClaimsParentObservations.map((observation) => <article key={observation.selector}>
        <span>{String(observation.order).padStart(2, "0")} / 02</span><h3>{observation.label}</h3><strong>{observation.unit}</strong><code>{observation.selector} · {observation.xmlPath}</code>
        <dl><div><dt>Cadence</dt><dd>{observation.frequency}</dd></div><div><dt>Coverage</dt><dd>{observation.geography}</dd></div><div><dt>Adjustment</dt><dd>{observation.seasonalAdjustment}</dd></div><div><dt>Accepted history</dt><dd>{observation.acceptedHistoryRecords} records</dd></div></dl>
      </article>)}</div>
    </section>
    <main className="sm-l4qa-grid">{continuedClaimsProductionPlacements.map((row) => <section key={row.placementId} className="sm-l4qa-factor" aria-labelledby={`continued-claims-factor-${row.order}`} data-disposition={row.productionDisposition} data-claim-class={row.claimClass}>
      <header><span className="sm-l4qa-factor-icon"><StructuralNodeIcon symbol={factorSymbols[row.canonicalFactorId] ?? "labor-market"} /></span><div><small>{String(row.order).padStart(2, "0")} / 10</small><h2 id={`continued-claims-factor-${row.order}`}>{row.label}</h2><code>{row.canonicalFactorId}</code><PlacementPaths row={row} /></div><b>{row.productionDisposition.replaceAll("_", " ")}</b></header>
      <div>{row.acceptedHistory ? row.acceptedHistory.series.map((series) => <AcceptedSeries key={series.sourceSeriesId} series={series} />) : <PendingState row={row} />}</div>
    </section>)}</main>
  </div>;
}
