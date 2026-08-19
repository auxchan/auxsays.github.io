import type { FreshnessState, StateType } from "../data/publicSnapshotTypes";

export function DataStateLabel({ state }: { state: StateType }) {
  const meanings: Record<StateType, string> = {
    OBS: "Observed",
    CALC: "Calculated",
    FCST: "Forecast",
    SCEN: "Scenario"
  };
  return <span className={`sm-state sm-state--${state.toLowerCase()}`} title={meanings[state]}><span aria-hidden="true">{state === "OBS" ? "●" : state === "CALC" ? "◆" : state === "FCST" ? "▲" : "◇"}</span> {state}</span>;
}

export function FreshnessLabel({ state }: { state: FreshnessState }) {
  return <span className={`sm-freshness sm-freshness--${state}`}><span aria-hidden="true">{state === "current" ? "✓" : state === "delayed" ? "△" : "!"}</span> {state}</span>;
}

function allowlistedUrl(value: string): string | null {
  try {
    const url = new URL(value, "https://auxsays.com");
    const host = url.hostname.toLowerCase();
    const allowed = host === "auxsays.com" || host.endsWith(".bls.gov") || host === "bls.gov" || host.endsWith(".dol.gov") || host === "dol.gov" || host.endsWith(".doleta.gov") || host === "doleta.gov";
    if (url.protocol !== "https:" || !allowed || url.username || url.password) return null;
    return url.toString();
  } catch {
    return null;
  }
}

export function SourceEvidenceLink({ href, children }: { href: string; children: React.ReactNode }) {
  const safeHref = allowlistedUrl(href);
  if (!safeHref) return <span>{children} (link unavailable)</span>;
  return <a href={safeHref}>{children}</a>;
}

export function FixtureNotice({ compact = false }: { compact?: boolean }) {
  return <div className={compact ? "sm-fixture-notice sm-fixture-notice--compact" : "sm-fixture-notice"} role="note"><strong>SYNTHETIC TEST DATA</strong><span>NOT A PUBLIC CLAIM</span></div>;
}

export function FactualCandidateNotice({ compact = false }: { compact?: boolean }) {
  return <div className={compact ? "sm-fixture-notice sm-fixture-notice--compact" : "sm-fixture-notice"} role="note"><strong>LOCAL FACTUAL CANDIDATE</strong><span>NOT PUBLICLY ACTIVATED · HUMAN QA ROUND 2 PENDING</span></div>;
}
