import type { PublicSnapshot, StateType } from "./publicSnapshotTypes";

const stateTypes = new Set<StateType>(["OBS", "CALC", "FCST", "SCEN"]);
const requiredHorizons = new Set(["current-year", "next-year", "plus-3-years"]);

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`Invalid public snapshot: ${message}`);
}

function containsForbiddenFixtureFlag(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  if (Object.prototype.hasOwnProperty.call(value, "isFixture")) return true;
  return Object.values(value).some(containsForbiddenFixtureFlag);
}

function isIsoTime(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

export function validatePublicSnapshot(value: unknown): PublicSnapshot {
  assert(value && typeof value === "object", "envelope must be an object");
  const candidate = value as PublicSnapshot;
  assert(candidate.schemaVersion === "1.0.0", "unsupported schemaVersion");
  assert(candidate.contractVersion === "1.0.0", "unsupported contractVersion");
  assert(candidate.snapshot?.publicationClass === "fixture" || candidate.snapshot?.publicationClass === "factual", "publicationClass must be fixture or factual");
  assert(!containsForbiddenFixtureFlag(candidate), "public isFixture field is prohibited");
  if (candidate.snapshot.publicationClass === "factual") {
    assert(candidate.snapshot.id.startsWith("factual-local-"), "factual snapshot must be local-review namespaced");
    const metrics = candidate.extensions?.["auxsays.phase2.metrics"];
    assert(Array.isArray(metrics) && metrics.length === 6, "factual first slice requires six observations");
    assert(metrics.every((metric) => metric.stateType === "OBS"), "factual first slice permits OBS only");
    assert(candidate.events.length === 0, "factual first slice cannot contain events");
    assert(candidate.outlook.forecasts.length === 0 && candidate.outlook.industries.length === 0 && candidate.outlook.occupations.length === 0 && candidate.outlook.demandAllocation.length === 0, "factual first slice cannot contain Outlook or ranking claims");
    assert(Object.values(candidate.sources).every((source) => source.publicDisplayAllowed && !source.provider.startsWith("SYNTHETIC TEST")), "factual sources must be rights-cleared original authorities");
    return candidate;
  }
  assert(candidate.snapshot.id.startsWith("fixture-"), "snapshot ID must be fixture-namespaced");
  for (const field of ["evaluatedAt", "generatedAt", "publishedAt", "asOf"] as const) {
    assert(isIsoTime(candidate.snapshot[field]), `snapshot.${field} must be ISO time`);
  }
  assert(candidate.systems.length === 10, "exactly ten top-level fixture systems required");
  assert(candidate.systems.every((system) => system.label.startsWith("SYNTHETIC TEST")), "system labels must be unmistakably synthetic");
  const firstChildren = candidate.systems[0]?.children ?? [];
  assert(firstChildren.length >= 11, "fixture requires Top 10 plus a View All boundary candidate");
  assert((firstChildren[0]?.children ?? []).length === 10, "fixture requires full 10 -> 10 -> 10 path");
  assert(firstChildren[9]?.nearTie === true && firstChildren[10]?.nearTie === true, "rank 10/11 near tie required");
  assert(firstChildren[10]?.nearCutoff === true, "rank 11 near-cutoff state required");
  const metrics = candidate.extensions?.["auxsays.phase2.metrics"];
  assert(Array.isArray(metrics) && metrics.length >= 2, "typed metrics required");
  assert(metrics.every((metric) => stateTypes.has(metric.stateType)), "every metric needs a valid stateType");
  const forecastStates = new Set(candidate.outlook.forecasts.map((item) => item.stateType));
  assert(forecastStates.has("FCST") && forecastStates.has("SCEN"), "FCST and SCEN records required");
  const horizons = new Set(candidate.outlook.horizons.map((item) => item.id));
  assert([...requiredHorizons].every((horizon) => horizons.has(horizon as never)), "all primary horizons required");
  assert(candidate.outlook.occupations.some((item) => item.label === "SYNTHETIC TEST OCCUPATION ALPHA"), "human-capital fixture required");
  assert(candidate.outlook.demandAllocation.length >= 2, "demand/allocation fixture required");
  const trace = candidate.extensions["auxsays.phase2.trace"];
  assert(trace.nodes.length <= 12 && trace.edges.length <= 16, "Trace exceeds approved bounds");
  const classes = new Set(trace.edges.map((edge) => edge.classification));
  assert(["Direct", "Statistical", "Modeled", "Hypothesis"].every((item) => classes.has(item as never)), "all relationship classes required");
  assert(Object.values(candidate.sources).every((source) => source.provider.startsWith("SYNTHETIC TEST")), "source providers must be synthetic");
  return candidate;
}

export function publicPayloadHasIndependentFixtureFlag(value: unknown): boolean {
  return containsForbiddenFixtureFlag(value);
}
