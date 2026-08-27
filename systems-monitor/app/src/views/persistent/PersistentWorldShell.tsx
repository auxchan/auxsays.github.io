import { useEffect, useMemo, useRef, useState } from "react";
import { createPersistentWorld, persistentWorldPath, type PersistentWorldPlacement } from "../../data/persistentWorldModel";
import { PersistentWorldSurface } from "./PersistentWorldSurface";
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
  return model.factors[placement.canonicalFactorId].label;
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
  const reducedMotion = useReducedMotion();
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(() => selectionFromHash(model));
  const [fullWorld, setFullWorld] = useState(false);
  const [resetVersion, setResetVersion] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenFallback, setFullscreenFallback] = useState(false);
  const selected = selectedId ? model.placements[selectedId] : undefined;
  const factor = selected ? model.factors[selected.canonicalFactorId] : undefined;
  const path = useMemo(() => persistentWorldPath(model, selectedId), [model, selectedId]);
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
    setResetVersion((current) => current + 1);
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
        <div><span>Persistent world R&amp;D</span><strong>{factor?.label ?? "Employment influence systems"}</strong></div>
        <div className="sm-pw-header__facts"><span>1,111 placements resident</span><span>3,110 fixture relationships resident</span><span>Human QA pending</span></div>
      </header>
      <nav className="sm-pw-breadcrumbs" aria-label="Persistent world exploration history">
        <button type="button" aria-current={!selected ? "location" : undefined} onClick={() => navigate(null)}>Employment outcome</button>
        {path.filter((item) => item.depth > 0).map((item) => <span key={item.id}><i aria-hidden="true">›</i><button type="button" aria-current={item.id === selectedId ? "location" : undefined} onClick={() => navigate(item.id)}>{placementLabel(model, item)}</button></span>)}
      </nav>
      <div ref={workspaceRef} className={`sm-pw-workspace ${selected ? "has-inspector" : ""} ${fullscreenFallback ? "is-fullscreen-fallback" : ""}`} data-fullscreen={fullscreenActive}>
        <aside className={`sm-pw-inspector ${selected ? "is-open" : ""}`} aria-label="Persistent world factor details" aria-hidden={!selected}>
          {selected && factor && <div>
            <header><span>{selected.depth === 1 ? "Master-defined driver system" : selected.depth === 2 ? "Level-2 review candidate" : "Synthetic renderer detail"}</span><button type="button" aria-label="Close factor details" onClick={() => navigate(null)}>×</button><h2>{factor.label}</h2></header>
            <p>{factor.definition}</p>
            <section><h3>What it tracks</h3><p>{selected.depth === 1 ? "A major upstream system the Master identifies as relevant to employment and unemployment outcomes." : selected.depth === 2 ? `A defensible candidate component inside ${placementLabel(model, model.placements[selected.parentPlacementId!])}. It remains subject to taxonomy and source review.` : "Rendering capacity, navigation persistence, camera travel, and label LOD only. It does not describe a real economic factor."}</p></section>
            <section><h3>Evidence posture</h3><dl><div><dt>Identity</dt><dd>{factor.evidencePosture}</dd></div><div><dt>Source family</dt><dd>{factor.sourceFamily}</dd></div><div><dt>Relationship status</dt><dd>TEST_FIXTURE · never accepted</dd></div></dl></section>
            <section><h3>Why the next ten are here</h3><p>{selected.depth < 2 ? "They form the bounded exact-ten navigation neighborhood for this review candidate. Placement communicates organization only—not causality, weight, or propagation." : selected.depth === 2 ? "They are deterministic Level-3 stress records proving the renderer can retain and revisit a deep world without fabricating factual economic coverage." : "This record has no factual children."}</p></section>
          </div>}
        </aside>
        <PersistentWorldSurface model={model} selectedPlacementId={selectedId} fullWorld={fullWorld} reducedMotion={reducedMotion} resetVersion={resetVersion} onSelect={navigate} onReset={resetWorld} />
        <div className="sm-pw-controls" aria-label="Persistent world view controls">
          <button type="button" onClick={resetWorld}>Reset</button>
          <button type="button" aria-pressed={fullWorld} onClick={() => setFullWorld((current) => !current)}>{fullWorld ? "Normal overview" : "Full-world view"}</button>
          <button type="button" aria-label={fullscreenActive ? "Exit full screen" : "Enter full screen"} aria-pressed={fullscreenActive} onClick={() => void toggleFullscreen()}><span aria-hidden="true">⛶</span> {fullscreenActive ? "Exit" : "Full screen"}</button>
        </div>
      </div>
      <div className="sm-pw-status" role="status">
        <div><strong>{fullWorld ? "Full-world density LOD" : selected ? `Depth ${selected.depth} focus` : "Outcome + 10 driver systems"}</strong><span>The world stays fixed; only camera, detail, emphasis, and inspector context change.</span></div>
        <div><strong>{model.topologyFingerprint}</strong><span>Topology/layout fingerprint</span></div>
      </div>
    </section>

    <section className="sm-pw-access" aria-labelledby="pw-access-title">
      <div><span>{selected ? "Current exact-ten neighborhood" : "Master-defined Level-1 systems"}</span><h2 id="pw-access-title">Explore without relying on the map</h2><p>These controls expose the same bounded hierarchy by keyboard and touch. Hierarchy tethers do not claim causality.</p></div>
      <ol>{visibleChoiceIds.map((id, index) => {
        const placement = model.placements[id]; const item = model.factors[placement.canonicalFactorId];
        return <li key={id}><button type="button" onClick={() => navigate(id)} aria-current={id === selectedId ? "true" : undefined}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item.label}</strong><small>{item.evidencePosture === "TEST_FIXTURE" ? "Synthetic renderer record" : item.evidencePosture === "CANDIDATE" ? "Review candidate" : "Master-defined system"}</small></button></li>;
      })}</ol>
    </section>

    <aside className="sm-pw-factual-boundary" role="note"><div><strong>Factual labor readings remain separate</strong><p>The six accepted BLS/DOL observations are unchanged and inspectable in Workstream‑1A. They are measurements—not synthetic influence edges in this fixture world.</p></div><a href="/systems-monitor/#workstream1a">Open factual Labor Market</a></aside>
  </div>;
}
