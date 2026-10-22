import type { PersistentWorldPlacement, PersistentWorldReadModel } from "../../data/persistentWorldModel";

export const PERSISTENT_PRESENTATION_LAYOUT_VERSION = "employment-spatial-presentation-1.1.0";
export const PERSISTENT_PROJECTION_VERSION = "perspective-depth-1.1.0";

export type PersistentDepthBand = "far" | "mid" | "near";

export interface PersistentSpatialCamera {
  x: number;
  y: number;
  z: number;
  scale: number;
  rotation: number;
  pitch: number;
  yaw: number;
}

export interface PersistentSpatialViewport { zoom: number; panX: number; panY: number }

export interface PersistentProjectedPlacement {
  x: number;
  y: number;
  cameraDepth: number;
  perspectiveScale: number;
  opacity: number;
  band: PersistentDepthBand;
}

export interface PersistentWorldSpatialLayout {
  version: typeof PERSISTENT_PRESENTATION_LAYOUT_VERSION;
  projectionVersion: typeof PERSISTENT_PROJECTION_VERSION;
  zByPlacementId: Readonly<Record<string, number>>;
  fingerprint: string;
}

function fnv1a32(value: string) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function signedHash(value: string, salt: string) {
  const raw = Number.parseInt(fnv1a32(`${salt}|${value}`), 16) / 0xffffffff;
  return raw * 2 - 1;
}

function rounded(value: number) {
  return Number(value.toFixed(3));
}

/** Presentation-only depth. It never expresses importance, confidence, severity, or causal strength. */
export function createPersistentWorldSpatialLayout(model: PersistentWorldReadModel): PersistentWorldSpatialLayout {
  const zByPlacementId: Record<string, number> = {};
  const placements = Object.values(model.placements).sort((left, right) => left.depth - right.depth || left.id.localeCompare(right.id));
  for (const placement of placements) {
    const sectorPhase = Math.PI * 2 * Math.max(0, placement.sector) / 10;
    const slotPhase = Math.PI * 2 * Math.max(0, placement.order - 1) / 10;
    const parent = placement.parentPlacementId ? model.placements[placement.parentPlacementId] : undefined;
    const parentZ = parent ? zByPlacementId[parent.id] ?? 0 : 0;
    let z = 0;
    if (placement.depth === 1) z = 220 * Math.sin(sectorPhase + .35) + 42 * signedHash(placement.id, "l1");
    else if (placement.depth === 2) z = parentZ + 150 * Math.sin(slotPhase + .41 * sectorPhase) + 28 * signedHash(placement.id, "l2");
    else if (placement.depth === 3) z = parentZ + 90 * Math.sin(slotPhase + .37 * (parent?.order ?? 0) + .19 * sectorPhase) + 18 * signedHash(placement.id, "l3");
    zByPlacementId[placement.id] = rounded(z);
  }
  const serialized = Object.keys(zByPlacementId).sort().map((id) => `${id}|${zByPlacementId[id].toFixed(3)}`).join("\n");
  const fingerprint = `fnv1a32:${fnv1a32(`${PERSISTENT_PRESENTATION_LAYOUT_VERSION}\n${PERSISTENT_PROJECTION_VERSION}\n${model.topologyFingerprint}\n${serialized}`)}`;
  return Object.freeze({
    version: PERSISTENT_PRESENTATION_LAYOUT_VERSION,
    projectionVersion: PERSISTENT_PROJECTION_VERSION,
    zByPlacementId: Object.freeze(zByPlacementId),
    fingerprint
  });
}

export function projectPersistentPlacement(
  placement: Pick<PersistentWorldPlacement, "x" | "y" | "id">,
  z: number,
  camera: PersistentSpatialCamera,
  viewport: PersistentSpatialViewport,
  width: number,
  height: number
): PersistentProjectedPlacement {
  return createPersistentProjector(camera, viewport, width, height)(placement, z);
}

/** Precomputes camera trigonometry once for a frame or hit-test batch. */
export function createPersistentProjector(camera: PersistentSpatialCamera, viewport: PersistentSpatialViewport, width: number, height: number) {
  const cosRotation = Math.cos(camera.rotation);
  const sinRotation = Math.sin(camera.rotation);
  const cosYaw = Math.cos(camera.yaw);
  const sinYaw = Math.sin(camera.yaw);
  const cosPitch = Math.cos(camera.pitch);
  const sinPitch = Math.sin(camera.pitch);
  const scale = camera.scale * viewport.zoom;
  return (placement: Pick<PersistentWorldPlacement, "x" | "y" | "id">, z: number): PersistentProjectedPlacement => {
    const dx = placement.x - camera.x; const dy = placement.y - camera.y; const dz = z - camera.z;
    const rotatedX = dx * cosRotation - dy * sinRotation; const rotatedY = dx * sinRotation + dy * cosRotation;
    const yawX = rotatedX * cosYaw - dz * sinYaw; const yawZ = rotatedX * sinYaw + dz * cosYaw;
    const pitchY = rotatedY * cosPitch - yawZ * sinPitch; const cameraDepth = rotatedY * sinPitch + yawZ * cosPitch;
    const perspectiveScale = Math.max(.7, Math.min(1.36, 1200 / (1200 - cameraDepth)));
    const band: PersistentDepthBand = cameraDepth < -110 ? "far" : cameraDepth > 110 ? "near" : "mid";
    return {
      x: width / 2 + yawX * scale * perspectiveScale + viewport.panX,
      y: height / 2 + pitchY * scale * perspectiveScale + viewport.panY,
      cameraDepth, perspectiveScale,
      opacity: band === "far" ? .46 : band === "mid" ? .78 : 1,
      band
    };
  };
}
