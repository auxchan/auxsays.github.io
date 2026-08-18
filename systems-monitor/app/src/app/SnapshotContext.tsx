import { createContext, useContext, useMemo, useState } from "react";
import { validatePublicSnapshot } from "../data/validatePublicSnapshot";
import type { FixtureVariant, PublicSnapshot } from "../data/publicSnapshotTypes";
import { phase2Fixture } from "../fixtures/phase2Fixture";

interface SnapshotContextValue {
  snapshot: PublicSnapshot;
  variant: FixtureVariant;
  setVariant: (variant: FixtureVariant) => void;
}

const SnapshotContext = createContext<SnapshotContextValue | null>(null);

export function SnapshotProvider({ children }: { children: React.ReactNode }) {
  const snapshot = useMemo(() => validatePublicSnapshot(phase2Fixture), []);
  const [variant, setVariant] = useState<FixtureVariant>("normal");
  return <SnapshotContext.Provider value={{ snapshot, variant, setVariant }}>{children}</SnapshotContext.Provider>;
}

export function useSnapshot() {
  const value = useContext(SnapshotContext);
  if (!value) throw new Error("SnapshotProvider is required");
  return value;
}
