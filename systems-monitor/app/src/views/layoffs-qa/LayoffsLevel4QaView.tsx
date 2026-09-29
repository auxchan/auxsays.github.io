import {
  acceptedLayoffsHistoryFreshness,
  displayAcceptedLayoffsValue,
  type LayoffsAcceptedSeriesSummary,
} from "../../data/layoffsAcceptedHistoryReadModel";
import {
  initialUiClaimsProductionPlacements,
  INITIAL_UI_CLAIMS_ACCEPTED_STRUCTURAL_RELATIONSHIPS,
  INITIAL_UI_CLAIMS_FORECASTING,
  INITIAL_UI_CLAIMS_GATE_B,
  INITIAL_UI_CLAIMS_HUMAN_QA,
  INITIAL_UI_CLAIMS_UNEXPLAINED_RENDERER_FIXTURES,
  type InitialUiClaimsProductionPlacement,
} from "../../data/initialUiClaimsReadModel";
import { StructuralNodeIcon } from "../motion/StructuralNodeIcon";
import type { StructuralNodeSymbol } from "../motion/structuralVisualLanguage";
import "./layoffsLevel4Qa.css";

const factorSymbols: Readonly<Record<string, StructuralNodeSymbol>> = Object.freeze({
  "factor:canonical:layoffs-and-discharges": "separations",
  "factor:canonical:temporary-layoffs": "unemployment",
  "factor:canonical:permanent-job-losers": "unemployment",
  "factor:canonical:payroll-contraction-breadth": "people",
  "factor:canonical:gross-job-losses": "factory",
  "factor:canonical:jobs-lost-at-establishment-deaths": "factory",
  "factor:canonical:business-bankruptcy-filings-12-month-total": "factory",
  "factor:canonical:real-output-growth": "ratio",
  "factor:canonical:real-personal-consumption-expenditures-growth": "ratio",
  "factor:canonical:fema-disaster-declaration": "system",
});

function displayDelta(series: LayoffsAcceptedSeriesSummary) {
  if (series.absoluteDelta === undefined) return "No prior compatible accepted period";
  const sign = series.absoluteDelta > 0 ? "+" : "";
  if (series.unit === "percent") return `${sign}${series.absoluteDelta.toLocaleString("en-US")} pp`;
  if (series.unit === "thousands of persons") return `${sign}${(series.absoluteDelta * 1_000).toLocaleString("en-US")} people`;
  if (series.unit === "thousands of jobs") return `${sign}${(series.absoluteDelta * 1_000).toLocaleString("en-US")} jobs`;
  return `${sign}${series.absoluteDelta.toLocaleString("en-US")} ${series.unit}`;
}

function FactorPlacements({ row }: { row: InitialUiClaimsProductionPlacement }) {
  return <details className="sm-l4qa-placements">
    <summary>Canonical reuse · {row.placementPaths.length} placement{row.placementPaths.length === 1 ? "" : "s"}</summary>
    <ul>{row.placementPaths.map((path) => <li key={path}>{path}</li>)}</ul>
  </details>;
}

function SeriesQa({ series }: { series: LayoffsAcceptedSeriesSummary }) {
  const comparable = Boolean(series.previous && series.previousDisplay !== undefined && series.direction && series.directionGlyph);
  return <article className="sm-l4qa-series" data-source-state="accepted-history">
    <header>
      <div><span>{series.seriesLabel}</span><code>{series.sourceSeriesId}</code></div>
      <strong>ACCEPTED OBSERVATION</strong>
    </header>
    <dl className="sm-l4qa-facts">
      <div><dt>Latest accepted value</dt><dd>{series.currentDisplay}</dd></div>
      <div><dt>Observation period</dt><dd>{series.current.validTime}</dd></div>
      <div><dt>Comparable prior observation</dt><dd>{comparable ? series.previousDisplay : "Not yet available"}{series.previous && <small>{series.previous.validTime}</small>}</dd></div>
      <div><dt>Factual direction</dt><dd>{comparable ? <>{series.directionGlyph} {series.direction!.toLowerCase()}</> : "Not yet comparable"}<small>{displayDelta(series)}</small></dd></div>
      <div><dt>History state</dt><dd>{acceptedLayoffsHistoryFreshness(series.sourceId)}<small>CURRENT_REVISED_HISTORY</small></dd></div>
      <div><dt>Revision status</dt><dd>{series.current.sourceRevisionStatus.replaceAll("_", " ")}<small>{series.revisionChainCount} accepted revision chain{series.revisionChainCount === 1 ? "" : "s"}</small></dd></div>
      <div><dt>Source</dt><dd>{series.provider}<small>{series.dataset}</small></dd></div>
      <div><dt>Forecast-history eligibility</dt><dd>Not eligible<small>Descriptive history only</small></dd></div>
    </dl>
    <details className="sm-l4qa-history">
      <summary>Accepted history · {series.acceptedPeriodCount} period{series.acceptedPeriodCount === 1 ? "" : "s"}</summary>
      <ol>{series.recentHistory.map((historyRow) => <li key={historyRow.observationId}><time>{historyRow.validTime}</time><span>{displayAcceptedLayoffsValue(historyRow.value, historyRow.unit)}</span><small>{historyRow.sourceRevisionStatus.replaceAll("_", " ")}</small></li>)}</ol>
    </details>
    <details className="sm-l4qa-deep">
      <summary>Methodology and evidence</summary>
      <dl><div><dt>Accepted at</dt><dd>{series.current.acceptedTime}</dd></div><div><dt>Retrieved</dt><dd>{series.current.retrievedTime}</dd></div><div><dt>Release identity</dt><dd><code>{series.current.releaseId}</code></dd></div><div><dt>Publication-time basis</dt><dd>{series.current.publicationTimeKind.replaceAll("_", " ")}</dd></div></dl>
      <nav aria-label={`${series.seriesLabel} evidence links`}><a href={series.current.evidenceUrl} target="_blank" rel="noreferrer">Original evidence</a><a href={series.current.methodologyUrl} target="_blank" rel="noreferrer">Official methodology</a><a href={series.current.provenanceUrl} target="_blank" rel="noreferrer">Acquisition provenance</a></nav>
    </details>
  </article>;
}

function PendingQa({ row }: { row: InitialUiClaimsProductionPlacement }) {
  const event = row.claimClass === "C_EVENT_OR_STRUCTURAL";
  return <article className="sm-l4qa-series sm-l4qa-disposition" data-source-state={event ? "event" : row.productionDisposition === "BLOCKED_CREDENTIAL" ? "blocked" : "pending"}>
    <header><div><span>{event ? "Official event source" : "Production state"}</span><code>{row.selectors.join(" · ") || "Selector set pending final methodology"}</code></div><strong>{row.productionDisposition.replaceAll("_", " ")}</strong></header>
    {event && <p className="sm-l4qa-event-boundary">This is an official declaration event with geography and time context. It is not a scalar reading and does not evaluate any downstream outcome.</p>}
    <dl className="sm-l4qa-facts">
      <div><dt>Evidence class</dt><dd>{row.claimClass.replaceAll("_", " ")}</dd></div>
      <div><dt>Official source</dt><dd>{row.sourceIds.join(", ")}</dd></div>
      <div><dt>History state</dt><dd>{row.acceptedHistoryState.replaceAll("_", " ")}</dd></div>
      <div><dt>Current blocker</dt><dd>{row.blocker ?? "None"}</dd></div>
    </dl>
  </article>;
}

export function LayoffsLevel4QaView() {
  const acceptedPlacements = initialUiClaimsProductionPlacements.filter((row) => row.productionDisposition === "ACCEPTED_OBSERVATION");
  const acceptedObservations = acceptedPlacements.reduce((total, row) => total + (row.acceptedHistory?.series.reduce((sum, series) => sum + series.history.length + series.revisionChainCount, 0) ?? 0), 0);
  return <div className="sm-l4qa" data-human-qa={INITIAL_UI_CLAIMS_HUMAN_QA} data-unexplained-renderer-fixtures={INITIAL_UI_CLAIMS_UNEXPLAINED_RENDERER_FIXTURES}>
    <header className="sm-l4qa-hero"><div><span>Initial UI Claims · exact ten</span><h1>Production-state Human QA</h1><p>Review all ten identities, canonical reuse, evidence classes, accepted descriptive history, explicit blockers, calculation calibration state, and FEMA event semantics.</p></div><dl><div><dt>Human QA</dt><dd>{INITIAL_UI_CLAIMS_HUMAN_QA}</dd></div><div><dt>Placements</dt><dd>{initialUiClaimsProductionPlacements.length}</dd></div><div><dt>Accepted factors</dt><dd>{acceptedPlacements.length}</dd></div><div><dt>Accepted records</dt><dd>{acceptedObservations}</dd></div></dl></header>
    <aside className="sm-l4qa-boundary"><strong>Scientific boundary</strong><span>Hierarchy is navigation only. Accepted structural relationships: {INITIAL_UI_CLAIMS_ACCEPTED_STRUCTURAL_RELATIONSHIPS}. Gate B: {INITIAL_UI_CLAIMS_GATE_B}. Forecasting: {INITIAL_UI_CLAIMS_FORECASTING.replaceAll("_", " ")}.</span><small>Unexplained renderer fixtures: {INITIAL_UI_CLAIMS_UNEXPLAINED_RENDERER_FIXTURES}</small></aside>
    <main className="sm-l4qa-grid">{initialUiClaimsProductionPlacements.map((row) => <section key={row.placementId} className="sm-l4qa-factor" aria-labelledby={`l4qa-factor-${row.order}`} data-disposition={row.productionDisposition} data-claim-class={row.claimClass}>
      <header><span className="sm-l4qa-factor-icon"><StructuralNodeIcon symbol={factorSymbols[row.canonicalFactorId] ?? "labor-market"} /></span><div><small>{String(row.order).padStart(2, "0")} / 10</small><h2 id={`l4qa-factor-${row.order}`}>{row.label}</h2><code>{row.canonicalFactorId}</code><FactorPlacements row={row} /></div><b>{row.productionDisposition.replaceAll("_", " ")}</b></header>
      <div>{row.acceptedHistory ? row.acceptedHistory.series.map((series) => <SeriesQa key={series.sourceSeriesId} series={series} />) : <PendingQa row={row} />}</div>
    </section>)}</main>
  </div>;
}
