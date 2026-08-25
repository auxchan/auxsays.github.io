import type { CSSProperties } from "react";
import { evidenceForFactor, laborMarketHierarchy, observationForFactor } from "../../data/laborMarketReadModel";
import type { LaborMarketCanonicalFactor } from "../../data/publicSnapshotTypes";
import { FreshnessLabel, SourceEvidenceLink } from "../../shared/Semantic";
import type { ViewProps } from "../viewProps";

function factorStyle(index: number, total: number): CSSProperties {
  const angle = -Math.PI / 2 + (index / total) * Math.PI * 2;
  return {
    "--labor-x": `${50 + Math.cos(angle) * 41}%`,
    "--labor-y": `${50 + Math.sin(angle) * 40}%`,
    "--labor-delay": `${index * 35}ms`
  } as CSSProperties;
}

function seriesLabel(factor: LaborMarketCanonicalFactor) {
  return factor.candidateSeriesId ?? "Machine acquisition identity pending deterministic reconciliation";
}

export function LaborMarketShell({ snapshot, route, navigate }: ViewProps) {
  const hierarchy = laborMarketHierarchy(snapshot);
  const factors = hierarchy.placements.map((placement) => hierarchy.canonicalFactors[placement.canonicalFactorId]);
  const selectedSlug = route.path.at(-1);
  const selectedFactor = selectedSlug ? factors.find((factor) => factor.slug === selectedSlug) : undefined;
  const selectedObservation = selectedFactor ? observationForFactor(snapshot, selectedFactor) : undefined;
  const selectedEvidence = selectedFactor ? evidenceForFactor(snapshot, selectedFactor) : {};

  function selectFactor(factor: LaborMarketCanonicalFactor) {
    navigate((current) => ({ ...current, path: [factor.slug] }));
  }

  function resetFocus() {
    navigate((current) => ({ ...current, path: [] }));
  }

  return <div className="sm-view sm-labor-shell">
    <header className="sm-labor-header">
      <div><span className="sm-eyebrow">United States · Official observations</span><h1 data-route-heading tabIndex={-1}>Labor Market</h1></div>
      <div className="sm-labor-coverage" aria-label={`${hierarchy.taxonomy.defined} of 10 factors defined; ${hierarchy.dataCoverage.populated} of 10 currently populated`}>
        <span><strong>{hierarchy.taxonomy.defined}/10</strong> factors defined</span>
        <span><strong>{hierarchy.dataCoverage.populated}/10</strong> currently populated</span>
      </div>
    </header>

    <p className="sm-labor-context">Select a factor to inspect its current official observation and original evidence. Quiet tethers show hierarchy only—not causality.</p>

    <div className={`sm-labor-workbench ${selectedFactor ? "has-inspector" : ""}`}>
      {selectedFactor && <aside className="sm-labor-inspector" aria-label={`${selectedFactor.label} details`} aria-live="polite">
        <div className="sm-labor-inspector__head"><div><span>{selectedFactor.availability === "populated" ? "Current official observation" : "Approved factor"}</span><h2>{selectedFactor.label}</h2></div><button type="button" onClick={resetFocus} aria-label="Close factor details">×</button></div>
        <section><h3>At a glance</h3><p>{selectedFactor.definition}</p><dl><div><dt>What it tracks</dt><dd>{selectedFactor.tracks}</dd></div><div><dt>Why it matters</dt><dd>{selectedFactor.impact}</dd></div></dl></section>
        {selectedObservation && selectedEvidence.source ? <>
          <section className="sm-labor-reading"><span>Latest accepted value</span><strong>{selectedObservation.displayValue}</strong><p>Represented period: {selectedObservation.validTime}</p><FreshnessLabel state={selectedEvidence.source.freshness} /></section>
          <section><h3>Evidence</h3><dl><div><dt>Claim class</dt><dd>Official observation</dd></div><div><dt>Publisher</dt><dd>{selectedEvidence.source.provider}</dd></div><div><dt>Series / source identity</dt><dd>{selectedObservation.sourceSeriesIds?.[0]}</dd></div><div><dt>Revision</dt><dd>{selectedEvidence.source.revision}</dd></div></dl><div className="sm-labor-evidence-actions">{selectedEvidence.evidenceUrl && <SourceEvidenceLink href={selectedEvidence.evidenceUrl}>Open original evidence</SourceEvidenceLink>}<SourceEvidenceLink href={selectedEvidence.source.methodologyUrl}>View methodology</SourceEvidenceLink></div></section>
          <details className="sm-labor-timing"><summary>Publication and provenance times</summary><dl><div><dt>Published</dt><dd>{selectedEvidence.source.publishedAt}</dd></div><div><dt>Retrieved</dt><dd>{selectedEvidence.source.retrievedAt}</dd></div><div><dt>Accepted</dt><dd>{selectedEvidence.provenance?.acceptedAt ?? "Not provided"}</dd></div><div><dt>Snapshot</dt><dd>{snapshot.snapshot.id}</dd></div></dl></details>
        </> : <section className="sm-labor-unavailable" role="status"><span>Current data not yet enabled</span><p>AUXSAYS has approved this factor's place in the Labor Market taxonomy, but no accepted current observation is enabled for it yet.</p><dl><div><dt>Candidate source identity</dt><dd>{seriesLabel(selectedFactor)}</dd></div><div><dt>Analytical state</dt><dd>Not assigned while current data is unavailable</dd></div></dl></section>}
      </aside>}

      <section className="sm-labor-orbit" aria-label="Labor Market factor map" data-hierarchy-relationship="navigation-only" onDoubleClick={(event) => { if (!(event.target as HTMLElement).closest("button, a, summary")) resetFocus(); }}>
        <svg className="sm-labor-tethers" viewBox="0 0 100 100" aria-hidden="true">{factors.map((factor, index) => {
          const angle = -Math.PI / 2 + (index / factors.length) * Math.PI * 2;
          return <line key={factor.id} x1="50" y1="50" x2={50 + Math.cos(angle) * 41} y2={50 + Math.sin(angle) * 40} />;
        })}</svg>
        <button type="button" className="sm-labor-core" onClick={resetFocus} aria-label="Labor Market overview"><span>Labor Market</span><strong>{hierarchy.dataCoverage.populated} live readings</strong><small>10 approved factors</small></button>
        <div className="sm-labor-factor-layer">{factors.map((factor, index) => {
          const observation = observationForFactor(snapshot, factor);
          const selected = factor.id === selectedFactor?.id;
          return <button type="button" key={factor.id} style={factorStyle(index, factors.length)} className={`${observation ? "is-populated" : "is-unavailable"} ${selected ? "is-selected" : ""}`} aria-pressed={selected} aria-label={`${factor.label}. ${observation ? `${observation.displayValue}, represented period ${observation.validTime}` : "Current data not yet enabled"}. Open details.`} onClick={() => selectFactor(factor)}>
            <i aria-hidden="true" />
            <span>{factor.label}</span>
            {observation ? <><strong>{observation.displayValue}</strong><small>{observation.validTime}</small></> : <small>Data not yet enabled</small>}
          </button>;
        })}</div>
        <p className="sm-sr-only">Labor Market contains exactly ten approved hierarchy placements. Six have accepted current observations and four are not yet enabled. Tethers express parent-child navigation only and do not express economic dependency or causality.</p>
      </section>
    </div>
  </div>;
}
