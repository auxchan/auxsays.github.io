import { createContext, useContext, useMemo, useState } from "react";
import { validatePublicSnapshot } from "../data/validatePublicSnapshot";
import type { FixtureVariant, PublicSnapshot } from "../data/publicSnapshotTypes";
import { phase2Fixture } from "../fixtures/phase2Fixture";
import { adaptLocalFactualCandidate } from "../data/factualSnapshotAdapter";

interface SnapshotContextValue {
  snapshot: PublicSnapshot;
  variant: FixtureVariant;
  setVariant: (variant: FixtureVariant) => void;
}

const SnapshotContext = createContext<SnapshotContextValue | null>(null);

export function SnapshotProvider({ children }: { children: React.ReactNode }) {
  const snapshot = useMemo(() => {
    const storedCandidate = import.meta.env.DEV ? window.localStorage.getItem("auxsays.localFactualCandidate") : null;
    const localCandidate = window.__AUXSAYS_LOCAL_FACTUAL_SNAPSHOT__ ?? (storedCandidate ? JSON.parse(storedCandidate) : undefined);
    return validatePublicSnapshot(localCandidate ? adaptLocalFactualCandidate(localCandidate) : phase2Fixture);
  }, []);
  const [variant, setVariant] = useState<FixtureVariant>("normal");
  return <SnapshotContext.Provider value={{ snapshot, variant, setVariant }}>{children}</SnapshotContext.Provider>;
}

export function useSnapshot() {
  const value = useContext(SnapshotContext);
  if (!value) throw new Error("SnapshotProvider is required");
  return value;
}
