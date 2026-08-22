import { useMemo, useState } from "react";
import type { FixtureVariant, NavigationNode, PrimaryView, SnapshotViewModel } from "../data/publicSnapshotTypes";
import type { Phase4bReadModel } from "../data/phase4bReadModel";
import { breadcrumbNodes, type RouteState } from "../state/routeSchema";
import { FactualCandidateNotice, FixtureNotice, FreshnessLabel } from "../shared/Semantic";

export function PrimaryViewSwitcher({ view, onChange }: { view: PrimaryView; onChange: (view: PrimaryView) => void }) {
  const views: Array<[PrimaryView, string]> = [
    ["summary", "Summary"],
    ["verified", "Verified Data"],
    ["outlook", "Outlook"]
  ];
  return <nav className="sm-view-switcher" aria-label="Systems Monitor views">{views.map(([id, label]) => <button key={id} type="button" aria-current={view === id ? "page" : undefined} className={view === id ? "is-active" : ""} onClick={() => onChange(id)}><strong>{label}</strong></button>)}</nav>;
}

export function SystemRail({ systems, selected, onSelect, factual = false }: { systems: NavigationNode[]; selected: string; onSelect: (slug: string) => void; factual?: boolean }) {
  return <aside className="sm-system-rail" aria-label={factual ? "Factual systems" : "Core synthetic systems"}><span className="sm-eyebrow">{factual ? "Factual first slice" : "10 core systems"}</span><ol>{systems.map((system) => <li key={system.id}><button type="button" className={selected === system.slug ? "is-selected" : ""} aria-current={selected === system.slug ? "true" : undefined} onClick={() => onSelect(system.slug)}><span>{String(system.rank).padStart(2, "0")}</span>{system.label.replace("SYNTHETIC TEST ", "")}</button></li>)}</ol></aside>;
}

export function ContextBreadcrumbs({ snapshot, route, onPath }: { snapshot: SnapshotViewModel; route: RouteState; onPath: (path: string[]) => void }) {
  const nodes = breadcrumbNodes(snapshot, route);
  return <nav className="sm-breadcrumbs" aria-label="Selected hierarchy"><ol><li><button type="button" onClick={() => onPath([])}>Systems</button></li>{nodes.map((node, index) => <li key={node.id}><span aria-hidden="true">/</span><button type="button" aria-current={index === nodes.length - 1 ? "page" : undefined} onClick={() => onPath(index === 0 ? [] : route.path.slice(0, index))}>{node.label.replace("SYNTHETIC TEST ", "")}</button></li>)}</ol></nav>;
}

interface SearchResult {
  id: string;
  label: string;
  type: string;
  context: string;
  state: string;
  freshness: string;
  view: PrimaryView;
  system?: string;
  path?: string[];
}

function collectNodes(snapshot: SnapshotViewModel): SearchResult[] {
  const results: SearchResult[] = [];
  const factual = snapshot.snapshot.publicationClass === "factual";
  function walk(node: NavigationNode, system: string, path: string[]) {
    results.push({ id: node.id, label: node.label, type: path.length ? "indicator/factor" : "system", context: [system, ...path].join(" / "), state: factual ? "OBS available" : "OBS / CALC available", freshness: factual ? "local factual candidate" : "current fixture", view: "summary", system, path });
    node.children?.forEach((child) => walk(child, system, [...path, child.slug]));
  }
  snapshot.systems.forEach((system) => walk(system, system.slug, []));
  Object.values(snapshot.sources).forEach((source) => results.push({ id: source.sourceId, label: source.provider, type: "source", context: source.dataset, state: "OBS evidence", freshness: source.freshness, view: "verified" }));
  snapshot.events.forEach((event) => results.push({ id: event.id, label: event.label, type: "event", context: "Synthetic event context", state: event.stateType, freshness: "fixture time", view: "summary" }));
  snapshot.outlook.industries.forEach((item) => results.push({ id: item.id, label: item.label, type: "industry", context: "Human-capital ranking", state: "FCST", freshness: "fixture snapshot", view: "outlook" }));
  snapshot.outlook.occupations.forEach((item) => results.push({ id: item.id, label: item.label, type: "occupation", context: "Expected actual hiring/openings", state: "FCST", freshness: "fixture snapshot", view: "outlook" }));
  if (!factual) {
    results.push({ id: "fixture-commodity-alpha", label: "SYNTHETIC TEST COMMODITY ALPHA", type: "commodity", context: "Fixture search-only entity", state: "OBS", freshness: "current fixture", view: "verified" });
    results.push({ id: "fixture-company-alpha", label: "SYNTHETIC TEST COMPANY ALPHA", type: "company", context: "Fixture search-only entity", state: "CALC", freshness: "current fixture", view: "summary" });
    results.push({ id: "fixture-facility-alpha", label: "SYNTHETIC TEST FACILITY ALPHA", type: "facility", context: "Fixture search-only entity", state: "OBS", freshness: "delayed fixture", view: "verified" });
    results.push({ id: "fixture-geo-alpha", label: "SYNTHETIC TEST GEOGRAPHY ALPHA", type: "geography", context: "Fixture-supported geography", state: "OBS", freshness: "current fixture", view: "verified" });
  }
  return results;
}

export function ExploreSearch({ snapshot, onSelect }: { snapshot: SnapshotViewModel; onSelect: (result: SearchResult) => void }) {
  const [query, setQuery] = useState("");
  const all = useMemo(() => collectNodes(snapshot), [snapshot]);
  const results = query.trim().length < 2 ? [] : all.filter((item) => `${item.label} ${item.type} ${item.context}`.toLowerCase().includes(query.toLowerCase())).slice(0, 8);
  return <div className="sm-search"><label htmlFor="systems-monitor-search">{snapshot.snapshot.publicationClass === "factual" ? "Explore factual observations" : "Explore synthetic entities"}</label><div><input id="systems-monitor-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search systems, sources, occupations…" autoComplete="off" /><kbd>/</kbd></div>{results.length > 0 && <ul aria-label="Search results">{results.map((result) => <li key={result.id}><button type="button" onClick={() => { onSelect(result); setQuery(""); }}><strong>{result.label}</strong><span>{result.type} · {result.context}</span><small>{result.state} · {result.freshness} · {result.view} available</small></button></li>)}</ul>}</div>;
}

export function SystemHealthSummary({ snapshot, phase4b, variant, setVariant }: { snapshot: SnapshotViewModel; phase4b?: Phase4bReadModel; variant: FixtureVariant; setVariant: (variant: FixtureVariant) => void }) {
  const sources = Object.values(snapshot.sources);
  const factual = snapshot.snapshot.publicationClass === "factual";
  const observationCount = phase4b?.observations.length ?? snapshot.extensions["auxsays.phase2.metrics"].length;
  return <section className="sm-health" aria-labelledby="sm-health-title">
    <div><span className="sm-eyebrow">System heartbeat</span><h2 id="sm-health-title">State current <span>{phase4b ? "Phase-4B local checkpoint" : factual ? "Local factual candidate evaluated" : "Fixture evaluated"}</span></h2></div>
    <details className="sm-health-details" open><summary>System context details</summary><dl><div><dt>Evaluated</dt><dd>{snapshot.snapshot.evaluatedAt}</dd></div><div><dt>Sources current</dt><dd>{sources.filter((source) => source.freshness === "current").length} / {sources.length}</dd></div><div><dt>Observations</dt><dd>{factual ? `${observationCount} factual OBS records` : "1 synthetic record"}</dd></div><div><dt>Activation</dt><dd>{factual ? "Local review only" : "Fixture only"}</dd></div>{phase4b ? <div><dt>Structural state</dt><dd>{phase4b.acceptedRelationships.length} accepted paths · {phase4b.structuralCalculations.length} CALC</dd></div> : <div><dt>Next expected release</dt><dd>{sources[0].nextExpectedReleaseAt}</dd></div>}</dl><div className="sm-source-pulse">{phase4b ? <span><span className="sm-status-dot sm-status-dot--pending" aria-hidden="true" /> BEA structural acceptance pending</span> : sources.map((source) => <span key={source.sourceId}><FreshnessLabel state={source.freshness} /> {source.dataset}</span>)}</div></details>
    {!factual && <label className="sm-variant-control">Fixture state lab<select value={variant} onChange={(event) => setVariant(event.target.value as FixtureVariant)}>{snapshot.extensions["auxsays.phase2.fixtureVariants"].map((item) => <option value={item} key={item}>{item}</option>)}</select></label>}
  </section>;
}

export function AppShell({ children, snapshot, phase4b, route, navigate, variant, setVariant }: {
  children: React.ReactNode;
  snapshot: SnapshotViewModel;
  phase4b?: Phase4bReadModel;
  route: RouteState;
  navigate: (next: RouteState | ((current: RouteState) => RouteState), replace?: boolean) => void;
  variant: FixtureVariant;
  setVariant: (variant: FixtureVariant) => void;
}) {
  const factual = snapshot.snapshot.publicationClass === "factual";
  return <div className="sm-app-shell"><a className="sm-skip" href="#systems-monitor-content">Skip to analysis</a>{factual ? <FactualCandidateNotice /> : <FixtureNotice />}<header className="sm-product-header"><div><a className="sm-parent-brand" href="/">AUXSAYS <span>/ U.S. Systems Monitor</span></a></div><ExploreSearch snapshot={snapshot} onSelect={(result) => navigate((current) => ({ ...current, view: result.view, system: result.system ?? current.system, path: result.path ?? [] }))} /></header><PrimaryViewSwitcher view={route.view} onChange={(view) => navigate((current) => ({ ...current, view, horizon: view === "outlook" ? current.horizon : "current-year", scenario: view === "outlook" ? current.scenario : "baseline" }))} /><ContextBreadcrumbs snapshot={snapshot} route={route} onPath={(path) => navigate((current) => ({ ...current, path }))} />{route.notice && <p className="sm-route-notice" role="status">{route.notice}</p>}<SystemHealthSummary snapshot={snapshot} phase4b={phase4b} variant={variant} setVariant={setVariant} /><div className="sm-workspace"><SystemRail systems={snapshot.systems} selected={route.system} factual={factual} onSelect={(system) => navigate((current) => ({ ...current, system, path: [] }))} /><main id="systems-monitor-content" className="sm-view-region" tabIndex={-1}>{children}</main></div></div>;
}
