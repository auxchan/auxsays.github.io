export type IsoTimestamp = string;

export type ReplayMode = "PUBLICLY_AVAILABLE_AS_OF" | "OPERATIONALLY_KNOWN_AS_OF";
export type ClaimClass = "OBS" | "CALC";
export type Cadence = "INTRADAY" | "DAILY" | "WEEKLY" | "MONTHLY" | "QUARTERLY" | "ANNUAL" | "IRREGULAR";
export type PublicationTimeProof = "PROVEN" | "UNKNOWN";
export type RevisionStatus = "ADVANCE" | "PRELIMINARY" | "REVISED" | "FINAL" | "NOT_APPLICABLE";

export interface TemporalInterval {
  start: IsoTimestamp;
  end?: IsoTimestamp;
}

export interface ObservationVersion {
  stateType: "OBS";
  observationId: string;
  factorId: string;
  sourceId: string;
  sourceNativeId: string;
  releaseId: string;
  objectHash: string;
  value: number;
  unit: string;
  seasonalAdjustment: string;
  geography: string;
  cadence: Cadence;
  validTime: TemporalInterval;
  officialPublishedAt?: IsoTimestamp;
  publicationTimeProof: PublicationTimeProof;
  retrievedAt: IsoTimestamp;
  acceptedAt?: IsoTimestamp;
  revisionStatus: RevisionStatus;
  analysisAllowed: boolean;
  provenanceRefs: readonly string[];
}

export type ChangeDirection = "INCREASE" | "DECREASE" | "UNCHANGED";
export type MaterialityState =
  | "NO_COMPARABLE_REFERENCE"
  | "IMMATERIAL"
  | "MATERIAL_INCREASE"
  | "MATERIAL_DECREASE"
  | "UNCHANGED";

export interface ChangeEvent {
  eventId: string;
  factorId: string;
  previousObservationId?: string;
  currentObservationId: string;
  direction: ChangeDirection;
  absoluteDelta?: number;
  relativeDeltaPercent?: number;
  materiality: MaterialityState;
  materialityProfileId: string;
  materialityProfileVersion: string;
  occurredAt: IsoTimestamp;
  knownAt: IsoTimestamp;
}

export function timestampMs(value: IsoTimestamp, field: string): number {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) throw new Error(`${field} must be a valid ISO timestamp`);
  return parsed;
}

export function assertNonEmpty(value: string, field: string): void {
  if (!value.trim()) throw new Error(`${field} must not be empty`);
}
