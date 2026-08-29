import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { createPersistentWorld, persistentWorldPath, persistentWorldPlacementLabel, type PersistentWorldPlacement } from "../../data/persistentWorldModel";
import { persistentWorldFactualBindingForFactor } from "../../data/persistentWorldFactualBindings";
import { PERSISTENT_WORLD_PROFILED_FACTOR_COUNT, persistentWorldCandidateSourceProfile } from "../../data/persistentWorldSourceCatalog";
import { LAYOFFS_BLOCKED_FACTOR_COUNT, LAYOFFS_SOURCE_ENABLED_FACTOR_COUNT } from "../../data/layoffsBranchReadModel";
import { PERSISTENT_ACCEPTED_IMPACT_COUNT, persistentChangesForWindow, type PersistentChangeNotice, type PersistentTimeWindow } from "../../data/persistentWorldTemporalReadModel";
import { StructuralNodeIcon } from "../motion/StructuralNodeIcon";
import type { StructuralNodeSymbol } from "../motion/structuralVisualLanguage";
import { PremiumPersistentWorldSurface as PersistentWorldSurface } from "./PremiumPersistentWorldSurface";
import { persistentWorldMediaFor } from "./persistentWorldMedia";
import { compactPersistentValue, factorGlyph, persistentPlacementAccent } from "./persistentWorldVisuals";
import "./persistentWorld.css";

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

function selectionFromHash(model: ReturnType<typeof createPersistentWorld>) {
  const prefix = "#persistent-world/";
  if (!window.location.hash.startsWith(prefix)) return null;
  const id = decodeURIComponent(window.location.hash.slice(prefix.length));
  return model.placements[id] ? id : null;
}

function placementLabel(model: ReturnType<typeof createPersistentWorld>, placement: PersistentWorldPlacement) {
  return persistentWorldPlacementLabel(model, placement);
}

export function persistentWorldUpSelection(model: ReturnType<typeof createPersistentWorld>, selectedId: string | null) {
  if (!selectedId) return null;
  const parentId = model.placements[selectedId]?.parentPlacementId;
  if (!parentId || parentId === model.outcomePlacementId) return null;
  return parentId;
}

function panelSymbol(glyph: string): StructuralNodeSymbol {
  const baseGlyph = glyph.split("@")[0];
  const symbols: Record<string, StructuralNodeSymbol> = {
    network: "labor-market", growth: "factory", consumer: "people", demand: "people", layoffs: "separations", investment: "factory", rates: "earnings", wages: "earnings", automation: "system", supply: "participation", shocks: "bolt",
    claims: "claims", openings: "openings", hire: "hire", clock: "clock", participation: "participation", freight: "freight",
    ratio: "participation", population: "people", "prime-age": "participation", migration: "freight", education: "system", skills: "system", retirement: "people", caregiving: "people", mobility: "freight"
  };
  return symbols[baseGlyph] ?? "system";
}

export function PersistentWorldShell() {
  const modelEvidence = useMemo(() => {
    const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory;
    const heapBefore = memory?.usedJSHeapSize;
    const started = performance.now();
    const model = createPersistentWorld();
    return { model, initializationMs: performance.now() - started, heapDeltaBytes: heapBefore === undefined ? null : Math.max(0, memory!.usedJSHeapSize - heapBefore) };
  }, []);
  const model = modelEvidence.model;
  const factualBindings = useMemo(() => Object.fromEntries(Object.values(model.placements).filter((placement) => placement.depth > 0).map((placement) => {
    const label = placementLabel(model, placement);
    return [placement.id, persistentWorldFactualBindingForFactor(placement.canonicalFactorId, label)];
  })), [model]);
  const connectedBindingCount = new Set(Object.values(model.placements).filter((placement) => factualBindings[placement.id]?.status === "CONNECTED").map((placement) => placement.canonicalFactorId)).size;
  const reducedMotion = useReducedMotion();
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(() => selectionFromHash(model));
  const [fullWorld, setFullWorld] = useState(false);
  const [traceMode, setTraceMode] = useState(false);
  const [resetVersion, setResetVersion] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenFallback, setFullscreenFallback] = useState(false);
  const [changeWindow, setChangeWindow] = useState<PersistentTimeWindow>("RECENT");
  const selected = selectedId ? model.placements[selectedId] : undefined;
  const factor = selected ? model.factors[selected.canonicalFactorId] : undefined;
  const selectedMedia = selected ? persistentWorldMediaFor(model, selected) : undefined;
  const selectedAccent = selected ? persistentPlacementAccent(selected) : "#6fe4d0";
  const selectedSymbol = selected && factor ? panelSymbol(factorGlyph(selected, factor.label)) : "system";
  const selectedBinding = selected ? factualBindings[selected.id] : undefined;
  const selectedCompactValue = compactPersistentValue(selectedBinding?.status === "CONNECTED" ? selectedBinding.displayValue : undefined);
  const selectedSourceProfile = selected && selected.depth >= 2 && factor ? persistentWorldCandidateSourceProfile(placementLabel(model, selected)) ?? persistentWorldCandidateSourceProfile(factor.label) : undefined;
  const path = useMemo(() => persistentWorldPath(model, selectedId), [model, selectedId]);
  const visibleChanges = useMemo(() => persistentChangesForWindow(changeWindow), [changeWindow]);
  const selectedChanges = useMemo(() => selected ? visibleChanges.filter((notice) => notice.placementId === selected.id) : [], [selected, visibleChanges]);
  const visibleChoiceIds = useMemo(() => {
    if (!selected) return model.childrenByPlacement[model.outcomePlacementId];
    const children = model.childrenByPlacement[selected.id] ?? [];
    if (children.length) return children;
    return selected.parentPlacementId ? model.childrenByPlacement[selected.parentPlacementId] ?? [] : [];
  }, [model, selected]);

  useEffect(() => {
    const restore = () => { setSelectedId(selectionFromHash(model)); setFullWorld(false); };
    window.addEventListener("popstate", restore);
    window.addEventListener("hashchange", restore);
    return () => { window.removeEventListener("popstate", restore); window.removeEventListener("hashchange", restore); };
  }, [model]);

  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === workspaceRef.current);
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, []);

  useEffect(() => {
    if (!fullscreenFallback) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setFullscreenFallback(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [fullscreenFallback]);

  function navigate(id: string | null) {
    setSelectedId(id);
    setFullWorld(false);
    const hash = id ? `#persistent-world/${encodeURIComponent(id)}` : "#persistent-world";
    window.history.pushState({ persistentWorldPlacementId: id }, "", `${window.location.pathname}${window.location.search}${hash}`);
  }

  function resetWorld() {
    navigate(null);
    setFullWorld(false);
    setTraceMode(false);
    setResetVersion((current) => current + 1);
  }

  function navigateUp() {
    if (!selected) return;
    navigate(persistentWorldUpSelection(model, selected.id));
  }

  function navigateToNotice(notice: PersistentChangeNotice) {
    navigate(notice.placementId === model.outcomePlacementId ? null : notice.placementId);
  }

  async function toggleFullscreen() {
    const workspace = workspaceRef.current;
    if (!workspace) return;
    if (fullscreenFallback) { setFullscreenFallback(false); return; }
    if (document.fullscreenElement) { await document.exitFullscreen(); return; }
    if (workspace.requestFullscreen) {
      try { await workspace.requestFullscreen(); return; } catch { /* use the contained fallback */ }
    }
    setFullscreenFallback(true);
  }

  const fullscreenActive = fullscreen || fullscreenFallback;

  return <div className="sm-pw-view">
    <h1 className="sm-sr-only" data-route-heading tabIndex={-1}>Persistent Employment Influence World</h1>
    <section className="sm-pw-instrument" aria-label="Persistent Employment influence world R&D" data-model-initialization-ms={modelEvidence.initializationMs.toFixed(3)} data-model-heap-delta-bytes={modelEvidence.heapDeltaBytes ?? "UNAVAILABLE"}>
      <header className="sm-pw-header">
        <div><span>Persistent world R&amp;D</span><strong>{selected ? placementLabel(model, selected) : "Employment influence systems"}</strong></div>
        <div className="sm-pw-header__facts"><span>{PERSISTENT_WORLD_PROFILED_FACTOR_COUNT} dataset paths cataloged</span><span>{connectedBindingCount} accepted branch {connectedBindingCount === 1 ? "reading" : "readings"}</span><span>{PERSISTENT_ACCEPTED_IMPACT_COUNT} governed connector signals</span><span>{LAYOFFS_SOURCE_ENABLED_FACTOR_COUNT} collectors enabled</span><span>{LAYOFFS_BLOCKED_FACTOR_COUNT} retrieval-blocked</span></div>
      </header>
      <nav className="sm-pw-breadcrumbs" aria-label="Persistent world exploration history">
        <button type="button" aria-current={!selected ? "location" : undefined} onClick={() => navigate(null)}>Employment outcome</button>
        {path.filter((item) => item.depth > 0).map((item) => <span key={item.id}><i aria-hidden="true">›</i><button type="button" aria-current={item.id === selectedId ? "location" : undefined} onClick={() => navigate(item.id)}>{placementLabel(model, item)}</button></span>)}
      </nav>
      <div ref={workspaceRef} className={`sm-pw-workspace ${selected ? "has-inspector" : ""} ${fullscreenFallback ? "is-fullscreen-fallback" : ""}`} data-fullscreen={fullscreenActive}>
        <aside className={`sm-pw-inspector ${selected ? "is-open" : ""}`} aria-label="Persistent world factor details" aria-hidden={!selected}>
          {selected && factor && <div key={selected.id} className="sm-pw-inspector__content">
            <header><span>{selected.depth === 1 ? "Master-defined driver system" : selected.depth === 2 ? "Level-2 review candidate" : "Level-3 reviewed factor"}</span><button type="button" aria-label="Close factor details" onClick={() => navigate(null)}>×</button><h2>{placementLabel(model, selected)}</h2>{selectedCompactValue && <div className="sm-pw-inspector__quick-reading"><strong>{selectedCompactValue}</strong><span>{selectedBinding?.validTime} · {selectedBinding?.provider}</span><a href="/systems-monitor/#workstream1a">Open factual record</a></div>}</header>
            {selectedMedia && <div className="sm-pw-inspector__portrait" style={{ "--pw-photo": `url(${selectedMedia.imageUrl})`, "--pw-accent": selectedAccent } as CSSProperties}>
              <span className="sm-pw-inspector__photo" role="img" aria-label={selectedMedia.alt} />
              <span className="sm-pw-inspector__portrait-icon" aria-hidden="true"><StructuralNodeIcon symbol={selectedSymbol} /></span>
              <span className="sm-pw-inspector__portrait-label"><small>Selected economic subject</small><strong>{selected.depth === 3 ? `Inside ${placementLabel(model, model.placements[selected.parentPlacementId!])}` : factor.evidencePosture.replaceAll("_", " ")}</strong></span>
            </div>}
            <p className="sm-pw-inspector__definition">{factor.definition}</p>
            <section><h3>What it tracks</h3><p>{selected.depth === 1 ? "A major upstream system the Master identifies as relevant to employment and unemployment outcomes." : selectedSourceProfile?.summary ?? `A reviewed economic factor inside ${placementLabel(model, model.placements[selected.parentPlacementId!])}. Its source, value, and relationships remain independently governed.`}</p></section>
            <section><h3>Why it matters</h3><p>{selected.depth === 1 ? "It organizes a major family of conditions that can help explain changes around employment, without asserting that every child directly causes jobs to rise or fall." : `It gives people a specific way to inspect one part of ${placementLabel(model, model.placements[selected.parentPlacementId!])}; hierarchy placement does not by itself prove causality, weight, or propagation.`}</p></section>
            <section className="sm-pw-inspector__change"><h3>What changed</h3>{selectedChanges.length ? selectedChanges.slice(0, 2).map((notice) => <article key={notice.id} data-impact={notice.impactClass}><span>{notice.sourceHealthOnly ? "SOURCE HEALTH" : notice.kind.replaceAll("_", " ")}</span><strong>{notice.headline}</strong><p>{notice.summary}</p><small>{notice.comparisonBasis}</small></article>) : <p>{factor.evidencePosture === "TEST_FIXTURE" ? "Fixture only — this renderer-capacity node has no observation history, live feed, or economic change signal." : "No accepted comparable change is available for this factor in the selected time window."}</p>}</section>
            {selectedBinding?.status === "CONNECTED" ? <section className="sm-pw-inspector__data-boundary is-connected"><h3>Latest accepted reading</h3><strong>{selectedCompactValue}</strong><p>{selectedBinding.validTime} · {selectedBinding.provider}<br /><code>{selectedBinding.seriesId}</code></p><div className="sm-pw-inspector__data-actions">{selectedBinding.evidenceUrl && <a href={selectedBinding.evidenceUrl} target="_blank" rel="noreferrer">Original evidence</a>}{selectedBinding.methodologyUrl && <a href={selectedBinding.methodologyUrl} target="_blank" rel="noreferrer">Methodology</a>}{selectedBinding.acquisitionProvenanceUrl && <a href={selectedBinding.acquisitionProvenanceUrl} target="_blank" rel="noreferrer">Acquisition record</a>}<a href="/systems-monitor/#workstream1a">Open factual record</a></div><small>Accepted local factual snapshot · {selectedBinding.freshness}</small></section>
              : selectedBinding?.status === "SOURCE_ENABLED_PENDING_ACCEPTANCE" ? <section className="sm-pw-inspector__data-boundary is-staged"><h3>Current data</h3><strong>Collector enabled · acceptance pending</strong><p>The official series can be retrieved and parsed, but no value is shown until rights, provenance, units, timing, revision, and publication acceptance pass.</p>{selectedBinding.candidateSeries?.map((series) => <div key={`${series.sourceId}:${series.seriesId}`}><code>{series.seriesId}</code><div className="sm-pw-inspector__data-actions"><a href={series.evidenceUrl} target="_blank" rel="noreferrer">Official evidence</a>{series.methodologyUrl && <a href={series.methodologyUrl} target="_blank" rel="noreferrer">Methodology</a>}</div></div>)}</section>
              : selectedBinding?.status === "BLOCKED" ? <section className="sm-pw-inspector__data-boundary is-design"><h3>Current data</h3><strong>Official path identified · retrieval blocked</strong><p>{selectedBinding.blockedReason ?? "A required credential or source decision is not yet available. No placeholder value is shown."}</p>{selectedBinding.candidateSeries?.map((series) => <div key={`${series.sourceId}:${series.seriesId}`}><code>{series.seriesId}</code><div className="sm-pw-inspector__data-actions"><a href={series.evidenceUrl} target="_blank" rel="noreferrer">Review official dataset</a></div></div>)}</section>
              : selectedBinding?.status === "SOURCE_IDENTIFIED" ? <section className="sm-pw-inspector__data-boundary is-staged"><h3>Current data</h3><strong>Official source identified</strong><p>Exact source intake or acceptance remains pending. No value is displayed until provenance and validation are complete.</p><code>{selectedBinding.candidateSeriesId}</code>{selectedSourceProfile && <dl><div><dt>Authority</dt><dd>{selectedSourceProfile.authority}</dd></div><div><dt>Dataset</dt><dd>{selectedSourceProfile.dataset}</dd></div><div><dt>Cadence</dt><dd>{selectedSourceProfile.cadence}</dd></div></dl>}<div className="sm-pw-inspector__data-actions">{selectedSourceProfile && <a href={selectedSourceProfile.evidenceUrl} target="_blank" rel="noreferrer">Review official dataset</a>}<a href="/systems-monitor/#workstream1a">Open factual Labor Market</a></div></section>
              : selectedSourceProfile?.readiness === "CANDIDATE_DATASET" ? <section className="sm-pw-inspector__data-boundary is-candidate"><h3>Candidate data path</h3><strong>{selectedSourceProfile.dataset}</strong><p>{selectedSourceProfile.summary}</p><dl><div><dt>Authority</dt><dd>{selectedSourceProfile.authority}</dd></div><div><dt>Expected cadence</dt><dd>{selectedSourceProfile.cadence}</dd></div><div><dt>Registration</dt><dd>Candidate · not enabled or accepted</dd></div></dl><div className="sm-pw-inspector__data-actions"><a href={selectedSourceProfile.evidenceUrl} target="_blank" rel="noreferrer">Review official dataset</a>{selectedSourceProfile.methodologyUrl && <a href={selectedSourceProfile.methodologyUrl} target="_blank" rel="noreferrer">Methodology</a>}</div><small>No current value is shown until source registration, rights, mapping, validation, and provenance acceptance pass.</small></section>
              : selectedSourceProfile?.readiness === "DERIVATION_REQUIRED" ? <section className="sm-pw-inspector__data-boundary is-design"><h3>Candidate data path</h3><strong>Derivation design required</strong><p>{selectedSourceProfile.summary}</p><dl><div><dt>Authority</dt><dd>{selectedSourceProfile.authority}</dd></div><div><dt>Registration</dt><dd>Source and calculation design pending</dd></div></dl><small>No single series is presented as the answer, and no placeholder value is shown.</small></section>
              : selectedBinding?.status === "FIXTURE_ONLY" ? <section className="sm-pw-inspector__data-boundary is-fixture"><h3>Evidence state</h3><strong>Fixture only · not factual</strong><p>This Level-4 renderer-capacity slot is connected to its parent by a hierarchy tether only. It has no official dataset, live value, accepted relationship, or temporal signal.</p></section>
              : selected.depth === 3 ? <section className="sm-pw-inspector__data-boundary"><h3>Current data</h3><strong>Source mapping under review</strong><p>This is a real candidate economic identity. AUXSAYS shows no value until an exact official dataset, parser, provenance, rights posture, and acceptance decision exist.</p></section>
              : selected.depth === 1 ? <section className="sm-pw-inspector__data-boundary"><h3>Current data</h3><strong>Aggregate system · multiple datasets</strong><p>Select one of the ten child factors to inspect its official dataset candidate, readiness state, and available factual reading.</p></section>
              : <section className="sm-pw-inspector__data-boundary"><h3>Current data</h3><strong>Dataset binding pending</strong><p>This placement has no accepted observation yet. AUXSAYS will not display a placeholder value or imply that a taxonomy node is a live feed.</p><a href="/systems-monitor/#workstream1a">Open factual Labor Market</a></section>}
            {selected.parentPlacementId && <section className="sm-pw-inspector__connector"><h3>How it connects</h3><dl><div><dt>Parent</dt><dd>{placementLabel(model, model.placements[selected.parentPlacementId])}</dd></div><div><dt>Map connector</dt><dd>Hierarchy tether · active</dd></div><div><dt>Meaning</dt><dd>Organization and drill-down only</dd></div><div><dt>Accepted structural relationship</dt><dd>None</dd></div></dl><p>A connector shows where this factor belongs. It does not claim causality, weight, or propagation.</p></section>}
            <section><h3>Evidence posture</h3><dl><div><dt>Identity</dt><dd>{factor.evidencePosture}</dd></div><div><dt>Source family</dt><dd>{factor.sourceFamily}</dd></div><div><dt>Relationship status</dt><dd>HIERARCHY ONLY · candidate relationships remain non-traversable</dd></div></dl></section>
            <section><h3>Why the next ten are here</h3><p>{selected.depth < 2 ? "They form the bounded exact-ten navigation neighborhood for this review candidate. Placement communicates organization only—not causality, weight, or propagation." : selected.depth === 2 ? "They are the reviewed connective-tissue factors for this branch. Repeated names reuse one canonical identity and one source/provenance state." : "This factor has no deeper hierarchy children in the current bounded branch."}</p></section>
            {selectedMedia && <footer className="sm-pw-inspector__credit"><span>Illustrative context only · not data evidence</span><a href={selectedMedia.sourcePage} target="_blank" rel="noreferrer">Photo: {selectedMedia.credit} · {selectedMedia.license === "CC0_1_0" ? "CC0 1.0" : "Public domain"}</a></footer>}
          </div>}
        </aside>
        <PersistentWorldSurface model={model} factualBindings={factualBindings} selectedPlacementId={selectedId} fullWorld={fullWorld} traceMode={traceMode} reducedMotion={reducedMotion} resetVersion={resetVersion} onSelect={navigate} onNavigateParent={navigateUp} onReset={resetWorld} />
        <div className="sm-pw-controls" aria-label="Persistent world view controls">
          <button type="button" disabled={!selected} onClick={navigateUp}>Up one level</button>
          <button type="button" onClick={resetWorld}>Reset</button>
          <button type="button" aria-pressed={fullWorld} onClick={() => setFullWorld((current) => !current)}>{fullWorld ? "Normal overview" : "Full-world view"}</button>
          <button type="button" aria-pressed={traceMode} disabled={!selected} onClick={() => setTraceMode((current) => !current)}>Trace</button>
          <button type="button" aria-label={fullscreenActive ? "Exit full screen" : "Enter full screen"} aria-pressed={fullscreenActive} onClick={() => void toggleFullscreen()}><span aria-hidden="true">⛶</span> {fullscreenActive ? "Exit" : "Full screen"}</button>
        </div>
      </div>
      <div className="sm-pw-status" role="status">
        <div><strong>{fullWorld ? "Full-world density LOD" : selected ? `Depth ${selected.depth} focus` : "Outcome + 10 driver systems"}</strong><span>The world stays fixed; only camera, detail, emphasis, and inspector context change.</span></div>
        <div><strong>{model.topologyFingerprint}</strong><span>Topology/layout fingerprint</span></div>
      </div>
    </section>

    <section className="sm-pw-changes" aria-labelledby="pw-changes-title">
      <header><div><span>Temporal intelligence</span><h2 id="pw-changes-title">What changed</h2><p>Accepted observations and operational source events are kept separate. No connector is colored supportive or adverse without an accepted relationship and governed destination-context rule.</p></div><div className="sm-pw-changes__filters" aria-label="Change history window">{(["RECENT", "24H", "7D", "30D", "90D", "1Y"] as const).map((window) => <button type="button" key={window} aria-pressed={changeWindow === window} onClick={() => setChangeWindow(window)}>{window === "RECENT" ? "Recent" : window.toLowerCase()}</button>)}</div></header>
      {visibleChanges.length ? <ol>{visibleChanges.map((notice) => <li key={notice.id} data-kind={notice.kind} data-impact={notice.impactClass}><button type="button" onClick={() => navigateToNotice(notice)}><span>{notice.sourceHealthOnly ? "Source health" : notice.impactClass}</span><strong>{notice.headline}</strong><p>{notice.summary}</p><small>{notice.validTime ? `${notice.validTime} · ` : ""}{notice.sourceLabel}</small></button>{notice.evidenceUrl && <a href={notice.evidenceUrl} target="_blank" rel="noreferrer">Original evidence</a>}</li>)}</ol> : <p className="sm-pw-changes__empty">No accepted change event occurred in this window.</p>}
    </section>

    <section className="sm-pw-access" aria-labelledby="pw-access-title">
      <div><span>{selected ? "Current exact-ten neighborhood" : "Master-defined Level-1 systems"}</span><h2 id="pw-access-title">Explore without relying on the map</h2><p>These controls expose the same bounded hierarchy by keyboard and touch. Hierarchy tethers do not claim causality.</p></div>
      <ol>{visibleChoiceIds.map((id, index) => {
        const placement = model.placements[id]; const item = model.factors[placement.canonicalFactorId]; const binding = factualBindings[id];
        return <li key={id}><button type="button" onClick={() => navigate(id)} aria-current={id === selectedId ? "true" : undefined}><span>{String(index + 1).padStart(2, "0")}</span><strong>{placementLabel(model, placement)}</strong><small>{binding?.status === "CONNECTED" ? "Accepted factual reading" : binding?.status === "SOURCE_ENABLED_PENDING_ACCEPTANCE" ? "Collector enabled · acceptance pending" : binding?.status === "BLOCKED" ? "Official path · retrieval blocked" : binding?.status === "FIXTURE_ONLY" ? "Fixture only · hierarchy tether" : item.evidencePosture === "CANDIDATE" ? "Source identified · no value" : "Master-defined system"}</small></button></li>;
      })}</ol>
    </section>

    <aside className="sm-pw-factual-boundary" role="note"><div><strong>Factual labor readings remain separate</strong><p>The six accepted BLS/DOL observations are unchanged and inspectable in Workstream‑1A. They are measurements—not synthetic influence edges in this fixture world.</p></div><a href="/systems-monitor/#workstream1a">Open factual Labor Market</a></aside>
  </div>;
}
