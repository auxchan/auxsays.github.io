import { Component, Suspense, lazy } from "react";
import { useSnapshot } from "./SnapshotContext";
import { AppShell } from "../shell/AppShell";
import { ErrorState, LoadingState, DegradedState } from "../shared/States";
import { useRouteState } from "../state/useRouteState";

const SummaryView = lazy(() => import("../views/summary/SummaryView"));
const VerifiedDataView = lazy(() => import("../views/verified/VerifiedDataView"));
const OutlookView = lazy(() => import("../views/outlook/OutlookView"));
const MotionQaHarness = lazy(() => import("../views/motion/MotionQaHarness").then((module) => ({ default: module.MotionQaHarness })));

class AppErrorBoundary extends Component<{ children: React.ReactNode }, { error: Error | null }> {
  state = { error: null } as { error: Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() { return this.state.error ? <ErrorState title="Systems Monitor data validation failed" detail={this.state.error.message} /> : this.props.children; }
}

function ValidatedApp() {
  const { snapshot, phase4b, motionQa, variant, setVariant } = useSnapshot();
  const { route, navigate } = useRouteState(snapshot);
  if (variant === "loading") return <LoadingState />;
  if (variant === "snapshot-unavailable") return <ErrorState />;
  const view = motionQa
    ? <MotionQaHarness model={motionQa} route={route} />
    : route.view === "verified"
    ? <VerifiedDataView snapshot={snapshot} phase4b={phase4b} route={route} navigate={navigate} variant={variant} />
    : route.view === "outlook"
      ? <OutlookView snapshot={snapshot} phase4b={phase4b} route={route} navigate={navigate} variant={variant} />
      : <SummaryView snapshot={snapshot} phase4b={phase4b} route={route} navigate={navigate} variant={variant} />;
  return <AppShell snapshot={snapshot} phase4b={phase4b} motionQa={motionQa} route={route} navigate={navigate} variant={variant} setVariant={setVariant}><DegradedState variant={variant} /><Suspense fallback={<LoadingState />}>{view}</Suspense></AppShell>;
}

export function SystemsMonitorApp() {
  return <AppErrorBoundary><ValidatedApp /></AppErrorBoundary>;
}
