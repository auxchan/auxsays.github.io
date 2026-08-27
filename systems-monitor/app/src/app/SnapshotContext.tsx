import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { validatePublicationCandidate, validatePublicSnapshot } from "../data/validatePublicSnapshot";
import type { FixtureVariant, SnapshotViewModel } from "../data/publicSnapshotTypes";
import { createCandidateViewModel, createSnapshotViewModel } from "../data/snapshotViewModelFactory";
import { validatePhase4bReadModel, type Phase4bReadModel } from "../data/phase4bReadModel";
import { validateMotionQaReadModel, type MotionQaReadModel } from "../data/motionQaReadModel";
import { phase2Fixture } from "../fixtures/phase2Fixture";
import activeFactualSnapshot from "../../../data/review/local-active-pdi-test-snapshot.json";

interface SnapshotContextValue {
  snapshot: SnapshotViewModel;
  phase4b?: Phase4bReadModel;
  motionQa?: MotionQaReadModel;
  variant: FixtureVariant;
  setVariant: (variant: FixtureVariant) => void;
}

const SnapshotContext = createContext<SnapshotContextValue | null>(null);

export function SnapshotProvider({ children }: { children: React.ReactNode }) {
  const [routeHash, setRouteHash] = useState(() => window.location.hash);
  useEffect(() => {
    const update = () => setRouteHash(window.location.hash);
    window.addEventListener("hashchange", update);
    window.addEventListener("popstate", update);
    return () => { window.removeEventListener("hashchange", update); window.removeEventListener("popstate", update); };
  }, []);
  const workstream1aReview = routeHash === "#workstream1a";
  const persistentWorldReview = import.meta.env.DEV && routeHash.startsWith("#persistent-world");
  const snapshot = useMemo(() => {
    const storedCandidate = import.meta.env.DEV && !workstream1aReview && !persistentWorldReview ? window.localStorage.getItem("auxsays.localFactualCandidate") : null;
    const localCandidate = workstream1aReview || persistentWorldReview ? undefined : window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__ ?? (storedCandidate ? JSON.parse(storedCandidate) : undefined);
    if (localCandidate && typeof localCandidate === "object" && "artifactType" in localCandidate) {
      return createCandidateViewModel(validatePublicationCandidate(localCandidate));
    }
    const defaultSnapshot = persistentWorldReview || (import.meta.env.MODE === "test" && !workstream1aReview) ? phase2Fixture : activeFactualSnapshot;
    return createSnapshotViewModel(validatePublicSnapshot((localCandidate ?? defaultSnapshot) as unknown));
  }, [persistentWorldReview, workstream1aReview]);
  const phase4b = useMemo(() => {
    if (!import.meta.env.DEV || workstream1aReview || persistentWorldReview) return undefined;
    const stored = window.localStorage.getItem("auxsays.localPhase4bState");
    return stored ? validatePhase4bReadModel(JSON.parse(stored)) : undefined;
  }, [persistentWorldReview, workstream1aReview]);
  const motionQa = useMemo(() => {
    if (!import.meta.env.DEV || workstream1aReview || persistentWorldReview) return undefined;
    const stored = window.localStorage.getItem("auxsays.localMotionQaState");
    return stored ? validateMotionQaReadModel(JSON.parse(stored)) : undefined;
  }, [persistentWorldReview, workstream1aReview]);
  const [variant, setVariant] = useState<FixtureVariant>("normal");
  return <SnapshotContext.Provider value={{ snapshot, phase4b, motionQa, variant, setVariant }}>{children}</SnapshotContext.Provider>;
}

export function useSnapshot() {
  const value = useContext(SnapshotContext);
  if (!value) throw new Error("SnapshotProvider is required");
  return value;
}
