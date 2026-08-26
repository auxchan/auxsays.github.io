import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { evidenceForFactor, laborMarketHierarchy, observationForFactor } from "../../data/laborMarketReadModel";
import type { StructuralSurfaceModel, StructuralSurfaceNode } from "../../data/motionQaReadModel";
import type { LaborMarketCanonicalFactor } from "../../data/publicSnapshotTypes";
import { FreshnessLabel, SourceEvidenceLink } from "../../shared/Semantic";
import { CanvasStructuralSurface } from "../motion/CanvasStructuralSurface";
import { resolveSpatialViewport } from "../motion/spatialNavigation";
import { StructuralNodeIcon } from "../motion/StructuralNodeIcon";
import { resolveStructuralNodeVisual } from "../motion/structuralVisualLanguage";
import "../motion/motionRenderer.css";
import type { ViewProps } from "../viewProps";

const laborPortrait = {
  imageUrl: "/systems-monitor/__local-review/media/employment-exposure-public-domain.jpg",
  alt: "Warehouse employees preparing packages for shipment at an industrial depot.",
  sourcePage: "https://commons.wikimedia.org/wiki/File:Warehouse_workers_prepare_packages_for_shipment_at_Sharpe_Army_Depot_-_DPLA_-_414220df83b823977c05c01a4b6b4106.jpeg",
  license: "PUBLIC_DOMAIN" as const,
  credit: "U.S. Department of Defense / National Archives"
};

const noContextFactors: [] = [];
const noEdges = new Set<string>();

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return reduced;
}

function createStructuralModel(factors: LaborMarketCanonicalFactor[]): StructuralSurfaceModel {
  const center: StructuralSurfaceNode = {
    id: "outcome:labor-market-state", label: "Labor Market", overviewLabel: "Labor Market", detailLabel: "U.S. Labor Market", kind: "LABOR_OUTCOME", displayRank: 1, currentState: "SIGNAL_READY", derivationRef: "auxsays.workstream1.factorHierarchy",
    insight: { definition: "The national system connecting employment, unemployment, participation, hiring, turnover, hours, and earnings.", tracks: "Ten approved labor-market factors without treating hierarchy placement as economic causality.", impact: "Together these readings explain how widely work is available, used, entered, and left." },
    portrait: laborPortrait, x: 520, y: 310
  };
  const nodes: StructuralSurfaceNode[] = factors.map((factor, index) => ({
    id: factor.id, label: factor.label, overviewLabel: factor.label, detailLabel: factor.label, kind: "LABOR_FACTOR", displayRank: index + 2, currentState: factor.availability === "populated" ? "SIGNAL_READY" : "IDLE", derivationRef: factor.metricRef ?? `placement:labor-market:${factor.slug}`,
    insight: { definition: factor.definition, tracks: factor.tracks, impact: factor.impact }, portrait: laborPortrait, x: 520, y: 310
  }));
  return {
    centerNodeId: center.id,
    nodes: [center, ...nodes],
    relationships: factors.map((factor) => ({ id: `hierarchy:labor-market:${factor.slug}`, from: center.id, to: factor.id, plainLanguage: `${factor.label} is an approved Labor Market hierarchy placement. This tether does not claim causality.`, relationshipClass: "HIERARCHY" as const }))
  };
}

function FactorInsightPanel({ factor, node, snapshot, onClose }: { factor: LaborMarketCanonicalFactor | null; node: StructuralSurfaceNode | null; snapshot: ViewProps["snapshot"]; onClose: () => void }) {
  if (!factor || !node) return <aside className="sm-node-guide" aria-hidden="true" aria-label="Selected factor guide" />;
  const observation = observationForFactor(snapshot, factor);
  const evidence = evidenceForFactor(snapshot, factor);
  const visual = resolveStructuralNodeVisual(node);
  return <aside className="sm-node-guide is-open" aria-label={`${factor.label} details`} data-selected-node-id={factor.id} data-connected-count="1" style={{ "--guide-accent": visual.accent, "--guide-fill": visual.fill } as CSSProperties}>
    <div className="sm-node-guide__inner">
      <header className="sm-node-guide__header"><div><small>{observation ? "Current official observation" : "Approved factor · data pending"}</small><h2>{factor.label}</h2></div><button type="button" aria-label="Close factor guide" onClick={onClose}>×</button></header>
      <div className="sm-node-guide__portrait" data-factor-portrait={visual.symbol} data-has-photo="true"><span className="sm-node-guide__photo" role="img" aria-label={node.portrait.alt} style={{ "--guide-photo": `url(${node.portrait.imageUrl})` } as CSSProperties} /><span className="sm-node-guide__orbit sm-node-guide__orbit--outer" aria-hidden="true" /><span className="sm-node-guide__orbit sm-node-guide__orbit--inner" aria-hidden="true" /><span className="sm-node-guide__portrait-symbol"><StructuralNodeIcon symbol={visual.symbol} /></span><span className="sm-node-guide__portrait-label"><small>Labor Market factor</small><strong>{observation ? observation.displayValue : "Data not yet enabled"}</strong></span></div>
      <p className="sm-node-guide__definition">{factor.definition}</p>
      <section><h3>What it tracks</h3><p>{factor.tracks}</p></section><section><h3>Why it matters</h3><p>{factor.impact}</p></section>
      {observation && evidence.source ? <>
        <section className="sm-labor-factual-reading"><h3>Latest accepted reading</h3><strong>{observation.displayValue}</strong><p>Represented period: {observation.validTime}</p><FreshnessLabel state={evidence.source.freshness} /></section>
        <section><h3>Evidence</h3><dl><div><dt>Claim class</dt><dd>Official observation</dd></div><div><dt>Publisher</dt><dd>{evidence.source.provider}</dd></div><div><dt>Series / source</dt><dd>{observation.sourceSeriesIds?.[0]}</dd></div><div><dt>Revision</dt><dd>{evidence.source.revision}</dd></div></dl><div className="sm-labor-evidence-actions">{evidence.evidenceUrl && <SourceEvidenceLink href={evidence.evidenceUrl}>Open original evidence</SourceEvidenceLink>}<SourceEvidenceLink href={evidence.source.methodologyUrl}>View methodology</SourceEvidenceLink></div></section>
        <details className="sm-labor-timing"><summary>Publication and provenance times</summary><dl><div><dt>Published</dt><dd>{evidence.source.publishedAt}</dd></div><div><dt>Retrieved</dt><dd>{evidence.source.retrievedAt}</dd></div><div><dt>Accepted</dt><dd>{evidence.provenance?.acceptedAt ?? "Not provided"}</dd></div><div><dt>Snapshot</dt><dd>{snapshot.snapshot.id}</dd></div></dl></details>
      </> : <section className="sm-labor-unavailable" role="status"><h3>Current data</h3><strong>Data not yet enabled</strong><p>This factor has an approved taxonomy placement, but AUXSAYS has not enabled an accepted current observation for it.</p>{factor.candidateSeriesId && <dl><div><dt>Candidate source identity</dt><dd>{factor.candidateSeriesId}</dd></div></dl>}</section>}
      <section className="sm-node-guide__context-relation"><h3>Why this tether exists</h3><p>This is a parent-child navigation placement under Labor Market. It is not a dependency, propagation path, or causal claim.</p></section>
      <footer><span>Factual snapshot · local Human QA pending</span><a href={node.portrait.sourcePage} target="_blank" rel="noreferrer">Photo: {node.portrait.credit} · Public domain</a></footer>
    </div>
  </aside>;
}

export function LaborMarketShell({ snapshot, route, navigate }: ViewProps) {
  const reducedMotion = useReducedMotion();
  const hierarchy = laborMarketHierarchy(snapshot);
  const factors = useMemo(() => hierarchy.placements.map((placement) => hierarchy.canonicalFactors[placement.canonicalFactorId]), [hierarchy]);
  const model = useMemo(() => createStructuralModel(factors), [factors]);
  const selectedSlug = route.path.at(-1);
  const selectedFactor = selectedSlug ? factors.find((factor) => factor.slug === selectedSlug) ?? null : null;
  const selectedNode = selectedFactor ? model.nodes.find((node) => node.id === selectedFactor.id) ?? null : null;
  const viewport = useMemo(() => resolveSpatialViewport(model, selectedFactor?.id ?? null, noEdges), [model, selectedFactor?.id]);
  const nodeStates = useMemo(() => new Map(model.nodes.map((node) => [node.id, node.currentState])), [model.nodes]);
  const secondaryLabels = useMemo(() => new Map(model.nodes.map((node) => {
    if (node.id === model.centerNodeId) return [node.id, `${hierarchy.dataCoverage.populated} of 10 populated`];
    const factor = hierarchy.canonicalFactors[node.id];
    const observation = factor ? observationForFactor(snapshot, factor) : undefined;
    return [node.id, observation?.displayValue ?? "Data not enabled"];
  })), [model, hierarchy, snapshot]);
  const descriptions = useMemo(() => new Map(model.nodes.map((node) => {
    if (node.id === model.centerNodeId) return [node.id, `${hierarchy.taxonomy.defined} approved factors; ${hierarchy.dataCoverage.populated} official readings`];
    const factor = hierarchy.canonicalFactors[node.id];
    const observation = factor ? observationForFactor(snapshot, factor) : undefined;
    return [node.id, observation ? `${observation.displayValue}; represented period ${observation.validTime}` : "Current data not yet enabled"];
  })), [model, hierarchy, snapshot]);

  function reset() { navigate((current) => ({ ...current, path: [] })); }
  function selectNode(nodeId: string) { if (nodeId === model.centerNodeId) { reset(); return; } const factor = hierarchy.canonicalFactors[nodeId]; if (factor) navigate((current) => ({ ...current, path: [factor.slug] })); }

  return <div className="sm-motion-view sm-motion-view--renderer-rd sm-labor-structural-view"><h1 className="sm-sr-only" data-route-heading tabIndex={-1}>Labor Market</h1>
    <section className={`sm-viz-instrument ${selectedFactor ? "has-focus" : ""}`} aria-label="Factual Labor Market structural surface">
      <header className="sm-viz-instrument__header"><div><span>United States · factual Labor Market</span><strong>{selectedFactor?.label ?? "Labor Market overview"}</strong></div><div className="sm-viz-status"><span><i aria-hidden="true" />Official data</span><span>{hierarchy.taxonomy.defined}/10 factors · {hierarchy.dataCoverage.populated}/10 populated</span></div></header>
      <nav className="sm-viz-breadcrumbs" aria-label="Labor Market exploration history"><button type="button" aria-current={!selectedFactor ? "location" : undefined} onClick={reset}>Labor Market</button>{selectedFactor && <span><i aria-hidden="true">›</i><button type="button" aria-current="location">{selectedFactor.label}</button></span>}</nav>
      <div className="sm-viz-workspace has-guide"><FactorInsightPanel factor={selectedFactor} node={selectedNode} snapshot={snapshot} onClose={reset} /><CanvasStructuralSurface model={model} path={null} currentEdges={[]} completedEdgeIds={noEdges} pathEdgeIds={noEdges} nodeStates={nodeStates} selectedNodeId={selectedFactor?.id ?? null} selectedContextFactorId={null} focusDepth={selectedFactor ? 1 : 0} viewport={viewport} traceMode={false} reducedMotion={reducedMotion} reconciliationTargetId={null} contextFactors={noContextFactors} surfaceAriaLabel="Animated factual Labor Market map with ten approved factors around the Labor Market outcome" contextLayerAriaLabel="No Sub-B factors are enabled in Workstream 1A" nodeLayerAriaLabel="Factual Labor Market factors" relationshipDescription="Ten animated tethers express hierarchy navigation only and do not express economic causality." nodeSecondaryLabels={secondaryLabels} nodeDescriptions={descriptions} onSelectNode={selectNode} onSelectContextFactor={() => undefined} onReset={reset} /></div>
      <div className="sm-viz-readout sm-labor-hierarchy-readout"><p><strong>10/10 factors defined</strong> · 6 official readings · 4 data sources not yet enabled</p><span>Animated tethers show hierarchy only—not causality.</span></div>
    </section>
    <section className="sm-viz-console is-explore" aria-label="Labor Market surface controls"><div className="sm-viz-mode-lead"><p>Hover to preview · select to inspect · wheel to zoom · middle-drag to pan · double-click empty space to reset</p></div></section>
  </div>;
}
