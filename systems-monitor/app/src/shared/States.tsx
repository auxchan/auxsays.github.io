export function LoadingState() {
  return <section className="sm-state-panel" role="status" aria-live="polite"><span className="sm-loading-mark" aria-hidden="true" /><h2>Loading Systems Monitor data</h2><p>No placeholder values are displayed while the contract-valid snapshot is checked.</p></section>;
}

export function ErrorState({ title = "Snapshot unavailable", detail = "The synthetic fixture could not be activated. No substitute conclusion is shown.", fixtureDisclosure = true }: { title?: string; detail?: string; fixtureDisclosure?: boolean }) {
  return <section className="sm-state-panel sm-state-panel--error" role="alert"><h2>{title}</h2><p>{detail}</p>{fixtureDisclosure && <strong>SYNTHETIC TEST DATA — NOT A PUBLIC CLAIM</strong>}</section>;
}

export function DegradedState({ variant }: { variant: string }) {
  const messages: Record<string, [string, string]> = {
    delayed: ["Source delayed", "A synthetic expected release has passed. Existing fixture context remains visible without a new conclusion."],
    stale: ["Source stale", "A synthetic source exceeded its declared cadence. No extrapolated value is substituted."],
    "insufficient-evidence": ["Insufficient evidence", "The fixture intentionally withholds a conclusion until evidence requirements are met."],
    "forecast-unavailable": ["Forecast unavailable", "No forecast is displayed for this test state."],
    "high-disagreement": ["High model disagreement", "The synthetic fixture preserves disagreement instead of averaging it away."],
    "partial-payload": ["Partial payload", "Available modules remain visible; unavailable modules are explicitly identified."]
  };
  const message = messages[variant];
  if (!message) return null;
  return <aside className="sm-degraded" role="status"><strong>{message[0]}</strong><span>{message[1]}</span></aside>;
}
