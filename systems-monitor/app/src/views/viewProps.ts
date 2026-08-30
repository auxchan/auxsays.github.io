import type { FixtureVariant, SnapshotViewModel } from "../data/publicSnapshotTypes";
import type { Phase4bReadModel } from "../data/phase4bReadModel";
import type { RouteState } from "../state/routeSchema";

export interface ViewProps {
  snapshot: SnapshotViewModel;
  phase4b?: Phase4bReadModel;
  route: RouteState;
  navigate: (next: RouteState | ((current: RouteState) => RouteState), replace?: boolean) => void;
  variant: FixtureVariant;
}
