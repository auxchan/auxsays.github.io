import type { FixtureVariant, SnapshotViewModel } from "../data/publicSnapshotTypes";
import type { RouteState } from "../state/routeSchema";

export interface ViewProps {
  snapshot: SnapshotViewModel;
  route: RouteState;
  navigate: (next: RouteState | ((current: RouteState) => RouteState), replace?: boolean) => void;
  variant: FixtureVariant;
}
