import { useCallback, useEffect, useState } from "react";
import type { SnapshotViewModel } from "../data/publicSnapshotTypes";
import { parseRoute, serializeRoute, type RouteState } from "./routeSchema";

export function useRouteState(snapshot: SnapshotViewModel) {
  const initial = parseRoute(window.location.search, snapshot);
  const [route, setRoute] = useState<RouteState>(initial.state);

  useEffect(() => {
    if (window.location.search !== initial.canonicalSearch) {
      window.history.replaceState(null, "", `${window.location.pathname}${initial.canonicalSearch}${window.location.hash}`);
    }
  }, []);

  useEffect(() => {
    const onPopState = () => {
      const parsed = parseRoute(window.location.search, snapshot);
      setRoute(parsed.state);
      window.requestAnimationFrame(() => document.querySelector<HTMLElement>("[data-route-heading]")?.focus());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [snapshot]);

  const navigate = useCallback((next: RouteState | ((current: RouteState) => RouteState), replace = false) => {
    setRoute((current) => {
      const candidate = typeof next === "function" ? next(current) : next;
      const canonical = parseRoute(serializeRoute(candidate, snapshot), snapshot);
      const method = replace ? "replaceState" : "pushState";
      window.history[method](null, "", `${window.location.pathname}${canonical.canonicalSearch}${window.location.hash}`);
      window.requestAnimationFrame(() => document.querySelector<HTMLElement>("[data-route-heading]")?.focus());
      return canonical.state;
    });
  }, [snapshot]);

  return { route, navigate };
}
