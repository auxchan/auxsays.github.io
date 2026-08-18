import { useMemo, useState } from "react";
import type { FixtureVariant, NavigationNode, PrimaryView, PublicSnapshot } from "../data/publicSnapshotTypes";
import { breadcrumbNodes, type RouteState } from "../state/routeSchema";
import { FixtureNotice, FreshnessLabel } from "../shared/Semantic";

export function PrimaryViewSwitcher({ view, onChange }: { view: PrimaryView; onChange: (view: PrimaryView) => void }) {
  const views: Array<[PrimaryView, string, string]> = [
    ["summary", "Summary", "Current state and context"],
    ["verified", "Verified Data", "Evidence and provenance"],
    ["outlook", "Outlook", "Synthetic forecast ranges"]
  ];
  return <nav className="sm-view-switcher" aria-label="Systems Monitor views">{views.map(([id, label, detail]) => <button key={id} type="button" aria-current={view === id ? "page" : undefined} className={view === id ? "is-active" : ""} onClick={() => onChange(id)}><strong>{label}</strong><span>{detail}</span></button>)}</nav>;
}

export function SystemRail({ systems, selected, onSelect }: { systems: NavigationNode[]; selected: string; onSelect: (slug: string) => void }) {
  return <aside className="sm-system-rail" aria-label="Core synthetic systems"><span className="sm-eyebrow">10 core systems</span><ol>{systems.map((system) => <li key={system.id}><button type="button" className={selected === system.slug ? "is-selected" : ""} aria-current={selected === system.slug ? "true" : undefined} onClick={() => onSelect(system.slug)}><span>{String(system.rank).padStart(2, "0")}</span>{system.label.replace("SYNTHETIC TEST ", "")}</button></li>)}</ol></aside>;
}

export function ContextBreadcrumbs({ snapshot, route, onPath }: { snapshot: PublicSnapshot; route: RouteState; onPath: (path: string[]) => void }) {
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

function collectNodes(snapshot: PublicSnapshot): SearchResult[] {
  const results: SearchResult[] = [];
  function walk(node: NavigationNode, system: string, path: string[]) {
    results.push({ id: node.id, label: node.label, type: path.length ? "indicator/factor" : "system", context: [system, ...path].join(" / "), state: "OBS / CALC available", freshness: "current fixture", view: "summary", system, path });
    node.children?.forEach((child) => walk(child, system, [...path, child.slug]));
  }
  snapshot.systems.forEach((system) => walk(system, system.slug, []));
  Object.values(snapshot.sources).forEach((source) => results.push({ id: source.sourceId, label: source.provider, type: "source", context: source.dataset, state: "OBS evidence", freshness: source.freshness, view: "verified" }));
  snapshot.events.forEach((event) => results.push({ id: event.id, label: event.label, type: "event", context: "Synthetic event context", state: event.stateType, freshness: "fixture time", view: "summary" }));
  snapshot.outlook.industries.forEach((item) => results.push({ id: item.id, label: item.label, type: "industry", context: "Human-capital ranking", state: "FCST", freshness: "fixture snapshot", view: "outlook" }));
  snapshot.outlook.occupations.forEach((item) => results.push({ id: item.id, label: item.label, type: "occupation", context: "Expected actual hiring/openings", state: "FCST", freshness: "fixture snapshot", view: "outlook" }));
  results.push({ id: "fixture-commodity-alpha", label: "SYNTHETIC TEST COMMODITY ALPHA", type: "commodity", context: "Fixture search-only entity", state: "OBS", freshness: "current fixture", view: "verified" });
  results.push({ id: "fixture-company-alpha", label: "SYNTHETIC TEST COMPANY ALPHA", type: "company", context: "Fixture search-only entity", state: "CALC", freshness: "current fixture", view: "summary" });
  results.push({ id: "fixture-facility-alpha", label: "SYNTHETIC TEST FACILITY ALPHA", type: "facility", context: "Fixture search-only entity", state: "OBS", freshness: "delayed fixture", view: "verified" });
  results.push({ id: "fixture-geo-alpha", label: "SYNTHETIC TEST GEOGRAPHY ALPHA", type: "geography", context: "Fixture-supported geography", state: "OBS", freshness: "current fixture", view: "verified" });
  return results;
}

export function ExploreSearch({ snapshot, onSelect }: { snapshot: PublicSnapshot; onSelect: (result: SearchResult) => void }) {
  const [query, setQuery] = useState("");
  const all = useMemo(() => collectNodes(snapshot), [snapshot]);
  const results = query.trim().length < 2 ? [] : all.filter((item) => `${item.label} ${item.type} ${item.context}`.toLowerCase().includes(query.toLowerCase())).slice(0, 8);
  return <div className="sm-search"><label htmlFor="systems-monitor-search">Explore synthetic entities</label><div><input id="systems-monitor-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search systems, sources, occupations…" autoComplete="off" /><kbd>/</kbd></div>{results.length > 0 && <ul aria-label="Search results">{results.map((result) => <li key={result.id}><button type="button" onClick={() => { onSelect(result); setQuery(""); }}><strong>{result.label}</strong><span>{result.type} · {result.context}</span><small>{result.state} · {result.freshness} · {result.view} available</small></button></li>)}</ul>}</div>;
}

export function SystemHealthSummary({ snapshot, variant, setVariant }: { snapshot: PublicSnapshot; variant: FixtureVariant; setVariant: (variant: FixtureVariant) => void }) {
  const sources = Object.values(snapshot.sources);
  return <section className="sm-health" aria-labelledby="sm-health-title"><div><span className="sm-eyebrow">System heartbeat</span><h2 id="sm-health-title">State current <span>Fixture evaluated</span></h2></div><dl><div><dt>Evaluated</dt><dd>{snapshot.snapshot.evaluatedAt}</dd></div><div><dt>Sources current</dt><dd>{sources.filter((source) => source.freshness === "current").length} / {sources.length}</dd></div><div><dt>New observations</dt><dd>1 synthetic record</dd></div><div><dt>Material changes</dt><dd>1 fixture change</dd></div><div><dt>Next expected release</dt><dd>{sources[0].nextExpectedReleaseAt}</dd></div></dl><div className="sm-source-pulse">{sources.map((source) => <span key={source.sourceId}><FreshnessLabel state={source.freshness} /> {source.dataset}</span>)}</div><label className="sm-variant-control">Fixture state lab<select value={variant} onChange={(event) => setVariant(event.target.value as FixtureVariant)}>{snapshot.extensions["auxsays.phase2.fixtureVariants"].map((item) => <option value={item} key={item}>{item}</option>)}</select></label></section>;
}

export function AppShell({ children, snapshot, route, navigate, variant, setVariant }: {
  children: React.ReactNode;
  snapshot: PublicSnapshot;
  route: RouteState;
  navigate: (next: RouteState | ((current: RouteState) => RouteState), replace?: boolean) => void;
  variant: FixtureVariant;
  setVariant: (variant: FixtureVariant) => void;
}) {
  return <div className="sm-app-shell"><a className="sm-skip" href="#systems-monitor-content">Skip to analysis</a><FixtureNotice /><header className="sm-product-header"><div><a className="sm-parent-brand" href="/">AUXSAYS <span>/ U.S. Systems Monitor</span></a><p>Evidence-led system context and synthetic predictive UI proof.</p></div><ExploreSearch snapshot={snapshot} onSelect={(result) => navigate((current) => ({ ...current, view: result.view, system: result.system ?? current.system, path: result.path ?? [] }))} /></header><PrimaryViewSwitcher view={route.view} onChange={(view) => navigate((current) => ({ ...current, view, horizon: view === "outlook" ? current.horizon : "current-year", scenario: view === "outlook" ? current.scenario : "baseline" }))} /><ContextBreadcrumbs snapshot={snapshot} route={route} onPath={(path) => navigate((current) => ({ ...current, path }))} />{route.notice && <p className="sm-route-notice" role="status">{route.notice}</p>}<SystemHealthSummary snapshot={snapshot} variant={variant} setVariant={setVariant} /><div className="sm-workspace"><SystemRail systems={snapshot.systems} selected={route.system} onSelect={(system) => navigate((current) => ({ ...current, system, path: [] }))} /><main id="systems-monitor-content" className="sm-view-region" tabIndex={-1}>{children}</main></div></div>;
}
