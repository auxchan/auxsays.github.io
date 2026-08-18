import type { FixtureVariant, PublicSnapshot } from "../data/publicSnapshotTypes";
import type { RouteState } from "../state/routeSchema";

export interface ViewProps {
  snapshot: PublicSnapshot;
  route: RouteState;
  navigate: (next: RouteState | ((current: RouteState) => RouteState), replace?: boolean) => void;
  variant: FixtureVariant;
}
