import type { HorizonId, NavigationNode, PrimaryView, PublicSnapshot } from "../data/publicSnapshotTypes";

export interface RouteState {
  view: PrimaryView;
  system: string;
  path: string[];
  horizon: HorizonId;
  scenario: string;
  geo: string;
  range: string;
  notice?: string;
}

export const canonicalParameterOrder = ["view", "system", "path", "horizon", "scenario", "geo", "range"] as const;
const views = new Set<PrimaryView>(["summary", "verified", "outlook"]);

function defaultState(snapshot: PublicSnapshot): RouteState {
  return {
    view: "summary",
    system: snapshot.systems[0].slug,
    path: [],
    horizon: "current-year",
    scenario: "baseline",
    geo: snapshot.extensions["auxsays.phase2.geographies"][0].id,
    range: snapshot.extensions["auxsays.phase2.ranges"][0].id
  };
}

function childrenForPath(system: NavigationNode, path: string[]): { valid: string[]; truncated: boolean } {
  const valid: string[] = [];
  let children = system.children ?? [];
  for (const segment of path) {
    const next = children.find((node) => node.slug === segment);
    if (!next) return { valid, truncated: true };
    valid.push(segment);
    children = next.children ?? [];
  }
  return { valid, truncated: false };
}

export function parseRoute(search: string, snapshot: PublicSnapshot): { state: RouteState; canonicalSearch: string } {
  const defaults = defaultState(snapshot);
  const params = new URLSearchParams(search);
  const state: RouteState = { ...defaults };
  const notices: string[] = [];
  const unknownKeys = [...params.keys()].filter((key) => !canonicalParameterOrder.includes(key as never));
  if (unknownKeys.length) notices.push("Unsupported URL options were removed.");

  const requestedView = params.get("view");
  if (requestedView && views.has(requestedView as PrimaryView)) state.view = requestedView as PrimaryView;
  else if (requestedView) notices.push("Unknown view returned to Summary.");

  const requestedSystem = params.get("system");
  const selectedSystem = snapshot.systems.find((system) => system.slug === requestedSystem) ?? snapshot.systems[0];
  if (requestedSystem && selectedSystem.slug !== requestedSystem) notices.push("Requested system is unavailable; the default synthetic system is shown.");
  state.system = selectedSystem.slug;

  const requestedPath = (params.get("path") ?? "").split("/").filter(Boolean);
  const pathResult = childrenForPath(selectedSystem, requestedPath);
  state.path = pathResult.valid;
  if (pathResult.truncated) notices.push("The requested hierarchy path was truncated to its nearest available ancestor.");

  const geographies = snapshot.extensions["auxsays.phase2.geographies"].map((item) => item.id);
  const requestedGeo = params.get("geo");
  if (requestedGeo && geographies.includes(requestedGeo)) state.geo = requestedGeo;
  else if (requestedGeo) notices.push("Unsupported geography returned to the fixture default.");

  const ranges = snapshot.extensions["auxsays.phase2.ranges"].map((item) => item.id);
  const requestedRange = params.get("range");
  if (requestedRange && ranges.includes(requestedRange)) state.range = requestedRange;
  else if (requestedRange) notices.push("Unsupported range returned to the fixture default.");

  if (state.view === "outlook") {
    const horizons = snapshot.outlook.horizons.map((item) => item.id);
    const requestedHorizon = params.get("horizon");
    if (requestedHorizon && horizons.includes(requestedHorizon as HorizonId)) state.horizon = requestedHorizon as HorizonId;
    else if (requestedHorizon) notices.push("Unsupported horizon returned to Current Year.");
    const scenarios = new Set(snapshot.outlook.forecasts.map((item) => item.scenario));
    const requestedScenario = params.get("scenario");
    if (requestedScenario && scenarios.has(requestedScenario)) state.scenario = requestedScenario;
    else if (requestedScenario) notices.push("Unsupported scenario returned to baseline.");
  } else if (params.has("horizon") || params.has("scenario")) {
    notices.push("Outlook-only URL state was removed outside Outlook.");
  }

  if (notices.length) state.notice = notices.join(" ");
  return { state, canonicalSearch: serializeRoute(state, snapshot) };
}

export function serializeRoute(state: RouteState, snapshot: PublicSnapshot): string {
  const defaults = defaultState(snapshot);
  const params = new URLSearchParams();
  if (state.view !== defaults.view) params.set("view", state.view);
  if (state.system !== defaults.system) params.set("system", state.system);
  if (state.path.length) params.set("path", state.path.join("/"));
  if (state.view === "outlook") {
    if (state.horizon !== defaults.horizon) params.set("horizon", state.horizon);
    if (state.scenario !== defaults.scenario) params.set("scenario", state.scenario);
  }
  if (state.geo !== defaults.geo) params.set("geo", state.geo);
  if (state.range !== defaults.range) params.set("range", state.range);
  const value = params.toString();
  return value ? `?${value}` : "";
}

export function findSelectedNode(snapshot: PublicSnapshot, route: RouteState): NavigationNode {
  let node = snapshot.systems.find((system) => system.slug === route.system) ?? snapshot.systems[0];
  for (const segment of route.path) {
    node = node.children?.find((child) => child.slug === segment) ?? node;
  }
  return node;
}

export function breadcrumbNodes(snapshot: PublicSnapshot, route: RouteState): NavigationNode[] {
  const root = snapshot.systems.find((system) => system.slug === route.system) ?? snapshot.systems[0];
  const nodes = [root];
  let current = root;
  for (const segment of route.path) {
    const next = current.children?.find((child) => child.slug === segment);
    if (!next) break;
    nodes.push(next);
    current = next;
  }
  return nodes;
}
