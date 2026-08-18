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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function validateSnapshotMetadata(candidate: PublicSnapshot) {
  assert(isRecord(candidate.snapshot), "snapshot metadata is required");
  assert(typeof candidate.snapshot.id === "string" && candidate.snapshot.id.length > 0, "snapshot.id is required");
  assert(typeof candidate.snapshot.sourceSnapshotId === "string" && candidate.snapshot.sourceSnapshotId.length > 0, "snapshot.sourceSnapshotId is required");
  for (const field of ["evaluatedAt", "generatedAt", "publishedAt", "asOf"] as const) {
    assert(isIsoTime(candidate.snapshot[field]), `snapshot.${field} must be ISO time`);
  }
}

function validateFactual(candidate: PublicSnapshot) {
  assert(candidate.snapshot.id.startsWith("factual-"), "factual snapshot ID must be factual-namespaced");
  assert(Array.isArray(candidate.systems) && candidate.systems.length > 0, "factual systems are required");
  assert(isRecord(candidate.sources) && Object.keys(candidate.sources).length > 0, "factual sources are required");
  assert(Array.isArray(candidate.events) && candidate.events.length === 0, "factual first slice cannot contain events");
  const metrics = candidate.extensions?.["auxsays.phase2.metrics"];
  assert(Array.isArray(metrics) && metrics.length === 6, "factual first slice requires six observations");
  assert(metrics.every((metric) => metric.stateType === "OBS"), "factual first slice permits OBS only");
  assert(candidate.outlook?.status === "unavailable_not_yet_supported", "factual Outlook must be explicitly unavailable");
  assert(Array.isArray(candidate.outlook.horizons) && candidate.outlook.horizons.length === 0, "factual first slice cannot carry forecast horizons");
  assert(candidate.outlook.forecasts.length === 0 && candidate.outlook.industries.length === 0 && candidate.outlook.occupations.length === 0 && candidate.outlook.demandAllocation.length === 0, "factual first slice cannot contain Outlook or ranking claims");
  assert(candidate.extensions["auxsays.phase2.fixtureVariants"].length === 0, "factual snapshot cannot contain fixture variants");
  const provenance = candidate.extensions["auxsays.phase3.provenance"];
  assert(isRecord(provenance) && Object.keys(provenance).length > 0, "deduplicated factual provenance is required");
  for (const [sourceId, source] of Object.entries(candidate.sources)) {
    assert(source.sourceId === sourceId, `source key mismatch for ${sourceId}`);
    assert(source.publicDisplayAllowed === true && !source.provider.startsWith("SYNTHETIC TEST"), "factual sources must be rights-cleared original authorities");
    assert(typeof source.observationTime === "string" && source.observationTime.length > 0, `source ${sourceId} observationTime is required`);
    for (const field of ["publishedAt", "retrievedAt", "freshnessEvaluatedAt"] as const) {
      assert(isIsoTime(source[field]), `source ${sourceId}.${field} must be ISO time`);
    }
  }
  for (const metric of metrics) {
    assert(typeof metric.id === "string" && typeof metric.validTime === "string", "factual metric identity and validTime are required");
    assert(Number.isFinite(metric.value) && typeof metric.displayValue === "string" && typeof metric.unit === "string", `metric ${metric.id} value fields are invalid`);
    assert(Array.isArray(metric.sourceRefs) && metric.sourceRefs.length > 0, `metric ${metric.id} sourceRefs are required`);
    assert(Array.isArray(metric.provenanceRefs) && metric.provenanceRefs.length > 0, `metric ${metric.id} provenanceRefs are required`);
    assert(metric.sourceRefs.every((reference) => reference in candidate.sources), `metric ${metric.id} has malformed sourceRefs`);
    assert(metric.provenanceRefs.every((reference) => reference in provenance), `metric ${metric.id} has malformed provenanceRefs`);
  }
  for (const [provenanceId, record] of Object.entries(provenance)) {
    assert(record.id === provenanceId, `provenance key mismatch for ${provenanceId}`);
    assert(record.sourceId in candidate.sources, `provenance ${provenanceId} has invalid sourceId`);
    assert(Array.isArray(record.seriesIds) && record.seriesIds.length > 0 && record.seriesIds.every((seriesId) => typeof seriesId === "string" && seriesId.length > 0), `provenance ${provenanceId} requires exact series IDs`);
    assert(/^https:\/\//.test(record.evidenceUrl), `provenance ${provenanceId} evidence URL is invalid`);
    assert(/^[a-f0-9]{64}$/i.test(record.artifactSha256), `provenance ${provenanceId} artifact hash is invalid`);
    for (const field of ["publishedAt", "retrievedAt", "acceptedAt"] as const) {
      assert(isIsoTime(record[field]), `provenance ${provenanceId}.${field} must be ISO time`);
    }
    assert(Date.parse(record.publishedAt) <= Date.parse(record.retrievedAt) && Date.parse(record.retrievedAt) <= Date.parse(record.acceptedAt), `provenance ${provenanceId} has impossible temporal ordering`);
  }
  const serialized = JSON.stringify(candidate).toLowerCase();
  assert(!serialized.includes("synthetic test"), "factual snapshot contains fixture claims");
}

export function validatePublicSnapshot(value: unknown): PublicSnapshot {
  assert(value && typeof value === "object", "envelope must be an object");
  const candidate = value as PublicSnapshot;
  assert(candidate.schemaVersion === "1.0.0", "unsupported schemaVersion");
  assert(candidate.contractVersion === "1.0.0", "unsupported contractVersion");
  validateSnapshotMetadata(candidate);
  assert(candidate.snapshot?.publicationClass === "fixture" || candidate.snapshot?.publicationClass === "factual", "publicationClass must be fixture or factual");
  assert(!containsForbiddenFixtureFlag(candidate), "public isFixture field is prohibited");
  if (candidate.snapshot.publicationClass === "factual") {
    validateFactual(candidate);
    return candidate;
  }
  assert(candidate.snapshot.id.startsWith("fixture-"), "snapshot ID must be fixture-namespaced");
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
