import {
  acceptedLayoffsHistoryFreshness,
  layoffsAcceptedFactorSummaries,
  LAYOFFS_ACCEPTED_HISTORY_AS_OF,
  LAYOFFS_ACCEPTED_OBSERVATION_COUNT,
  LAYOFFS_DOL_ACQUISITION_STATUS,
  LAYOFFS_DOL_PRIMARY_FRESHNESS,
  LAYOFFS_DOL_SOURCE_FRESHNESS,
  type LayoffsAcceptedSeriesSummary,
} from "../../data/layoffsAcceptedHistoryReadModel";
import { StructuralNodeIcon } from "../motion/StructuralNodeIcon";
import type { StructuralNodeSymbol } from "../motion/structuralVisualLanguage";
import "./layoffsLevel4Qa.css";

const factorLabels: Readonly<Record<string, string>> = Object.freeze({
  "factor:canonical:layoffs-and-discharges": "Layoffs and Discharges",
  "factor:canonical:job-openings-rate": "Job Openings Rate",
  "factor:canonical:hires-rate": "Hires Rate",
  "factor:canonical:permanent-job-losers": "Permanent Job Losers",
  "factor:canonical:temporary-layoffs": "Temporary Layoffs",
  "factor:canonical:average-weekly-hours": "Average Weekly Hours",
  "factor:canonical:temporary-help-employment": "Temporary Help Employment",
  "factor:canonical:initial-claims": "Initial Claims",
  "factor:canonical:gross-job-losses": "Gross Job Losses",
  "factor:canonical:establishment-contractions": "Establishment Contractions",
  "factor:canonical:establishment-closures": "Establishment Closures",
  "factor:canonical:establishment-deaths": "Establishment Deaths",
});

const factorOrder = Object.keys(factorLabels);

function displayDelta(series: LayoffsAcceptedSeriesSummary) {
  if (series.absoluteDelta === undefined) return "No prior compatible accepted period";
  const sign = series.absoluteDelta > 0 ? "+" : "";
  const relative = series.relativeDeltaPercent === undefined
    ? ""
    : ` · ${series.relativeDeltaPercent > 0 ? "+" : ""}${series.relativeDeltaPercent.toFixed(2)}%`;
  return `${sign}${series.absoluteDelta.toLocaleString("en-US")} ${series.unit}${relative}`;
}

const factorSymbols: Readonly<Record<string, StructuralNodeSymbol>> = Object.freeze({
  "factor:canonical:layoffs-and-discharges": "separations", "factor:canonical:job-openings-rate": "openings",
  "factor:canonical:hires-rate": "hire", "factor:canonical:permanent-job-losers": "unemployment",
  "factor:canonical:temporary-layoffs": "unemployment", "factor:canonical:average-weekly-hours": "clock",
  "factor:canonical:temporary-help-employment": "people", "factor:canonical:initial-claims": "claims",
  "factor:canonical:gross-job-losses": "factory", "factor:canonical:establishment-contractions": "factory",
  "factor:canonical:establishment-closures": "factory", "factor:canonical:establishment-deaths": "factory",
});

const hierarchyPlacement: Readonly<Record<string, string>> = Object.freeze({
  "factor:canonical:gross-job-losses": "Layoffs & Job Destruction › Gross Job Losses",
  "factor:canonical:establishment-contractions": "Layoffs & Job Destruction › Gross Job Losses › Establishment Contractions",
  "factor:canonical:establishment-closures": "Layoffs & Job Destruction › Gross Job Losses › Establishment Closures",
  "factor:canonical:establishment-deaths": "Layoffs & Job Destruction › Firm Death / Shutdown Stress › Establishment Deaths",
});

function SeriesQa({ series }: { series: LayoffsAcceptedSeriesSummary }) {
  const fallback = series.sourceId === "dol-ui-claims" && LAYOFFS_DOL_ACQUISITION_STATUS === "SUCCESS_WITH_PRIMARY_STALE";
  const stale = series.sourceId === "dol-ui-claims" && LAYOFFS_DOL_SOURCE_FRESHNESS.status === "STALE";
  const comparable = Boolean(series.previous && series.previousDisplay !== undefined && series.direction && series.directionGlyph);
  return <article className="sm-l4qa-series" data-source-state={fallback ? "fallback" : stale ? "stale" : "accepted-history"}>
    <header>
      <div><span>{series.seriesLabel}</span><code>{series.sourceSeriesId}</code></div>
      <strong>{fallback ? "CURRENT · OFFICIAL FALLBACK" : stale ? "ACCEPTED HISTORICAL DATA" : "ACCEPTED DESCRIPTIVE HISTORY"}</strong>
    </header>
    {fallback && <p className="sm-l4qa-fallback"><b>Primary XML: STALE through {LAYOFFS_DOL_PRIMARY_FRESHNESS.newestObservationPeriod}.</b> Current accepted value is from the official DOL weekly release fallback through {LAYOFFS_DOL_SOURCE_FRESHNESS.newestObservationPeriod}.</p>}
    {stale && <p className="sm-l4qa-stale"><b>Current source state: STALE.</b> The accepted value below remains valid history, but it is not presented as the current national reading.</p>}
    <dl className="sm-l4qa-facts">
      <div><dt>{stale ? "Newest accepted historical value" : "Current accepted value"}</dt><dd>{series.currentDisplay}</dd></div>
      <div><dt>Observation period</dt><dd>{series.current.validTime}</dd></div>
      <div><dt>Previous comparable value</dt><dd>{comparable ? series.previousDisplay : "Unavailable"}{series.previous && <small>{series.previous.validTime}</small>}</dd></div>
      <div><dt>Factual direction</dt><dd>{comparable ? <>{series.directionGlyph} {series.direction!.toLowerCase()}</> : "Not yet comparable"}<small>{displayDelta(series)}</small></dd></div>
      <div><dt>History / source state</dt><dd>{acceptedLayoffsHistoryFreshness(series.sourceId)}</dd></div>
      <div><dt>Revision status</dt><dd>{stale ? `accepted artifact: ${series.current.sourceRevisionStatus.replaceAll("_", " ")}` : series.current.sourceRevisionStatus.replaceAll("_", " ")}<small>{stale ? "Current-release classification unavailable; structured source stale" : `${series.revisionChainCount} accepted revision chain${series.revisionChainCount === 1 ? "" : "s"}`}</small></dd></div>
      <div><dt>Source</dt><dd>{series.provider}<small>{series.dataset}</small></dd></div>
      <div><dt>Evidence status</dt><dd>Accepted evidence<small>CURRENT_REVISED_HISTORY</small></dd></div>
    </dl>
    <details className="sm-l4qa-history">
      <summary>Historical series · {series.acceptedPeriodCount} comparable periods</summary>
      <ol>{series.history.map((row) => <li key={row.observationId}><time>{row.validTime}</time><span>{Number(row.value).toLocaleString("en-US")} {row.unit}</span><small>{row.sourceRevisionStatus.replaceAll("_", " ")}</small></li>)}</ol>
    </details>
    {series.revisions.length > 0 && <details className="sm-l4qa-revisions">
      <summary>Accepted revision evidence · {series.revisions.length}</summary>
      <ul>{series.revisions.map(({ current, previous }) => <li key={current.observationId}><span>{current.validTime}</span><strong>{Number(previous.value).toLocaleString("en-US")} → {Number(current.value).toLocaleString("en-US")} {current.unit}</strong><small>revision {previous.revisionNumber} → revision {current.revisionNumber}</small></li>)}</ul>
    </details>}
    <details className="sm-l4qa-deep">
      <summary>Methodology and evidence</summary>
      <dl><div><dt>Accepted at</dt><dd>{series.current.acceptedTime}</dd></div><div><dt>Retrieved</dt><dd>{series.current.retrievedTime}</dd></div><div><dt>{stale ? "Recorded legacy acquisition marker" : "Release identity"}</dt><dd><code>{series.current.releaseId}</code>{stale && <small>Accepted before the report-run-date identity repair</small>}</dd></div><div><dt>Publication-time basis</dt><dd>{series.current.publicationTimeKind.replaceAll("_", " ")}</dd></div></dl>
      <nav aria-label={`${series.seriesLabel} evidence links`}><a href={series.current.evidenceUrl} target="_blank" rel="noreferrer">Original evidence</a><a href={series.current.methodologyUrl} target="_blank" rel="noreferrer">Official methodology</a><a href={series.current.provenanceUrl} target="_blank" rel="noreferrer">Acquisition provenance</a></nav>
    </details>
  </article>;
}

export function LayoffsLevel4QaView() {
  const ordered = [...layoffsAcceptedFactorSummaries].sort((left, right) => factorOrder.indexOf(left.canonicalFactorId) - factorOrder.indexOf(right.canonicalFactorId));
  return <div className="sm-l4qa" data-human-qa="PENDING">
    <header className="sm-l4qa-hero"><div><span>Layoffs Level-4</span><h1>Accepted-history Human QA</h1><p>Verify factual identity, values, periods, comparisons, revisions, freshness, and source evidence. This surface is limited to factual source QA.</p></div><dl><div><dt>Human QA</dt><dd>PENDING</dd></div><div><dt>Canonical factors</dt><dd>{ordered.length}</dd></div><div><dt>Exact series</dt><dd>{ordered.reduce((count, factor) => count + factor.series.length, 0)}</dd></div><div><dt>Accepted observations</dt><dd>{LAYOFFS_ACCEPTED_OBSERVATION_COUNT}</dd></div></dl></header>
    <aside className="sm-l4qa-boundary"><strong>Review boundary</strong><span>Node titles remain identity-only. Historical acceptance does not establish a live reading when the current structured source is stale.</span><small>Accepted-history artifact generated {LAYOFFS_ACCEPTED_HISTORY_AS_OF}</small></aside>
    <main className="sm-l4qa-grid">{ordered.map((factor, index) => <section key={factor.canonicalFactorId} className="sm-l4qa-factor" aria-labelledby={`l4qa-factor-${index}`}>
      <header><span className="sm-l4qa-factor-icon"><StructuralNodeIcon symbol={factorSymbols[factor.canonicalFactorId] ?? "labor-market"} /></span><div><small>{String(index + 1).padStart(2, "0")} / {String(ordered.length).padStart(2, "0")}</small><h2 id={`l4qa-factor-${index}`}>{factorLabels[factor.canonicalFactorId] ?? factor.canonicalFactorId}</h2><code>{factor.canonicalFactorId}</code><em>{hierarchyPlacement[factor.canonicalFactorId] ?? `Layoffs & Job Destruction › ${factorLabels[factor.canonicalFactorId] ?? factor.canonicalFactorId}`}</em></div><b>{factor.series.length} exact series</b></header>
      <div>{factor.series.map((series) => <SeriesQa key={series.sourceSeriesId} series={series} />)}</div>
    </section>)}</main>
  </div>;
}
