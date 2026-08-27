import type { PersistentWorldDepth, PersistentWorldPlacement } from "../../data/persistentWorldModel";

export interface Point { x: number; y: number }
export interface CubicRoute { start: Point; control1: Point; control2: Point; end: Point }
export interface LabelCandidate { id: string; text: string; x: number; y: number; priority: number; width: number; height: number; accent: string; anchorX?: number; anchorY?: number; required?: boolean }
export interface ResolvedLabel extends LabelCandidate { left: number; top: number }

export const PERSISTENT_GLINT_PERIOD_MS = 2500;
export const PERSISTENT_GLINT_TRAIL = 0.085;
export const PERSISTENT_SECTOR_COLORS = ["#6fe4d0", "#59bff5", "#7d9cff", "#ef7f84", "#f0ae54", "#d8ca69", "#e685c4", "#a68cf0", "#66d0a4", "#f18d67"] as const;

function hexToRgb(value: string) {
  const match = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(value);
  return match ? [Number.parseInt(match[1], 16), Number.parseInt(match[2], 16), Number.parseInt(match[3], 16)] : [111, 228, 208];
}

function rgbToHsl([red, green, blue]: number[]) {
  const r = red / 255; const g = green / 255; const b = blue / 255;
  const max = Math.max(r, g, b); const min = Math.min(r, g, b); const delta = max - min;
  let hue = 0;
  if (delta) {
    if (max === r) hue = 60 * (((g - b) / delta) % 6);
    else if (max === g) hue = 60 * ((b - r) / delta + 2);
    else hue = 60 * ((r - g) / delta + 4);
  }
  const lightness = (max + min) / 2;
  const saturation = delta ? delta / (1 - Math.abs(2 * lightness - 1)) : 0;
  return { hue: (hue + 360) % 360, saturation: saturation * 100, lightness: lightness * 100 };
}

function hslToHex(hue: number, saturation: number, lightness: number) {
  const s = saturation / 100; const l = lightness / 100;
  const chroma = (1 - Math.abs(2 * l - 1)) * s; const section = ((hue % 360) + 360) % 360 / 60; const x = chroma * (1 - Math.abs((section % 2) - 1));
  const [red, green, blue] = section < 1 ? [chroma, x, 0] : section < 2 ? [x, chroma, 0] : section < 3 ? [0, chroma, x] : section < 4 ? [0, x, chroma] : section < 5 ? [x, 0, chroma] : [chroma, 0, x];
  const match = l - chroma / 2;
  return `#${[red, green, blue].map((channel) => Math.round((channel + match) * 255).toString(16).padStart(2, "0")).join("")}`;
}

/** Keeps children in one parent palette while making ten converging routes distinguishable. */
export function persistentPlacementAccent(placement: Pick<PersistentWorldPlacement, "depth" | "order" | "sector">) {
  if (placement.depth === 0) return "#f08acb";
  const base = PERSISTENT_SECTOR_COLORS[Math.max(0, placement.sector)] ?? PERSISTENT_SECTOR_COLORS[0];
  if (placement.depth === 1) return base;
  const hsl = rgbToHsl(hexToRgb(base));
  const offset = (placement.order - 5.5) * 4.8;
  const lightness = Math.max(48, Math.min(73, hsl.lightness + ((placement.order % 3) - 1) * 4));
  return hslToHex((hsl.hue + offset + 360) % 360, Math.max(48, hsl.saturation), lightness);
}

function stableHash(value: string) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

export function premiumCurveRoute(id: string, start: Point, end: Point, quiet = false): CubicRoute {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const distance = Math.max(1, Math.hypot(dx, dy));
  const nx = -dy / distance;
  const ny = dx / distance;
  const sign = stableHash(id) % 2 ? 1 : -1;
  const bend = Math.min(quiet ? 18 : 34, distance * (quiet ? 0.065 : 0.115)) * sign;
  return {
    start,
    control1: { x: start.x + dx * .33 + nx * bend, y: start.y + dy * .33 + ny * bend },
    control2: { x: start.x + dx * .67 + nx * bend, y: start.y + dy * .67 + ny * bend },
    end
  };
}

export function pointOnCubic(route: CubicRoute, rawProgress: number): Point {
  const t = Math.max(0, Math.min(1, rawProgress));
  const inverse = 1 - t;
  return {
    x: inverse ** 3 * route.start.x + 3 * inverse ** 2 * t * route.control1.x + 3 * inverse * t ** 2 * route.control2.x + t ** 3 * route.end.x,
    y: inverse ** 3 * route.start.y + 3 * inverse ** 2 * t * route.control1.y + 3 * inverse * t ** 2 * route.control2.y + t ** 3 * route.end.y
  };
}

export function traceCubic(context: CanvasRenderingContext2D, route: CubicRoute) {
  context.beginPath();
  context.moveTo(route.start.x, route.start.y);
  context.bezierCurveTo(route.control1.x, route.control1.y, route.control2.x, route.control2.y, route.end.x, route.end.y);
}

export function persistentGlintProgress(nowMs: number, edgeId: string) {
  return ((nowMs / PERSISTENT_GLINT_PERIOD_MS) + (stableHash(edgeId) % 997) / 997) % 1;
}

export function easePremiumHover(current: number, target: number, elapsedMs: number, reducedMotion = false) {
  if (reducedMotion) return target;
  return current + (target - current) * (1 - Math.exp(-Math.max(0, elapsedMs) / 180));
}

export function blendPremiumColor(from: string, to: string, progress: number, alpha = 1) {
  const read = (value: string) => {
    const match = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(value);
    return match ? [Number.parseInt(match[1], 16), Number.parseInt(match[2], 16), Number.parseInt(match[3], 16)] : [111, 228, 208];
  };
  const start = read(from);
  const end = read(to);
  const amount = Math.max(0, Math.min(1, progress));
  const channels = start.map((channel, index) => Math.round(channel + (end[index] - channel) * amount));
  return `rgba(${channels[0]}, ${channels[1]}, ${channels[2]}, ${Math.max(0, Math.min(1, alpha))})`;
}

export function resolvePersistentLod(depth: PersistentWorldDepth, effectiveScale: number, semantic: boolean) {
  if (!semantic) return 0;
  if (depth === 0) return 3;
  if (depth === 1) return effectiveScale >= .28 ? 3 : 2;
  if (depth === 2) return effectiveScale >= .9 ? 3 : effectiveScale >= .48 ? 2 : 1;
  return effectiveScale >= 1.55 ? 2 : effectiveScale >= 1.3 ? 1 : 0;
}

export function resolvePremiumLabels(candidates: readonly LabelCandidate[], width: number, height: number) {
  const accepted: ResolvedLabel[] = [];
  for (const candidate of [...candidates].sort((left, right) => right.priority - left.priority || left.id.localeCompare(right.id))) {
    const attempts = candidate.required ? [[0,0],[0,-26],[0,26],[-28,0],[28,0],[-28,-26],[28,26],[-56,0],[56,0],[0,-52],[0,52],[-56,-26],[56,26],[-84,0],[84,0],[0,-78],[0,78]] : [[0,0]];
    for (const [offsetX, offsetY] of attempts) {
      const rawX = candidate.x + offsetX; const rawY = candidate.y + offsetY;
      const x = candidate.required ? Math.max(8 + candidate.width / 2, Math.min(width - 8 - candidate.width / 2, rawX)) : rawX;
      const y = candidate.required ? Math.max(8 + candidate.height / 2, Math.min(height - 8 - candidate.height / 2, rawY)) : rawY;
      const resolved = { ...candidate, x, y, left: x - candidate.width / 2, top: y - candidate.height / 2 };
      if (resolved.left < 8 || resolved.top < 8 || resolved.left + resolved.width > width - 8 || resolved.top + resolved.height > height - 8) continue;
      const collides = accepted.some((item) => resolved.left < item.left + item.width + 8 && resolved.left + resolved.width + 8 > item.left && resolved.top < item.top + item.height + 6 && resolved.top + resolved.height + 6 > item.top);
      if (!collides) { accepted.push(resolved); break; }
    }
  }
  return accepted;
}

export function premiumRadius(placement: PersistentWorldPlacement, lod: number) {
  if (placement.depth === 0) return 31;
  if (placement.depth === 1) return lod >= 3 ? 24 : 18;
  if (placement.depth === 2) return lod >= 3 ? 19 : lod === 2 ? 14 : 8;
  return lod >= 2 ? 18 : lod === 1 ? 7.5 : 1.35;
}

const fixtureDetailGlyphs = ["detail-1", "detail-2", "detail-3", "detail-4", "detail-5", "detail-6", "detail-7", "detail-8", "detail-9", "detail-10"] as const;

export function factorGlyph(placement: PersistentWorldPlacement, label = "") {
  if (placement.depth === 0) return "network";
  if (placement.depth === 3) return fixtureDetailGlyphs[Math.max(0, placement.order - 1)] ?? "detail-1";
  if (placement.depth === 1) return ["growth", "consumer", "demand", "layoffs", "investment", "rates", "wages", "automation", "supply", "shocks"][Math.max(0, placement.sector)] ?? "detail-1";
  const text = label.toLowerCase();
  let glyph: string;
  if (/employment-population/.test(text)) glyph = "ratio";
  else if (/working-age population/.test(text)) glyph = "population";
  else if (/prime-age participation/.test(text)) glyph = "prime-age";
  else if (/migration|immigration/.test(text)) glyph = "migration";
  else if (/educational attainment/.test(text)) glyph = "education";
  else if (/skill/.test(text)) glyph = "skills";
  else if (/retirement/.test(text)) glyph = "retirement";
  else if (/caregiving/.test(text)) glyph = "caregiving";
  else if (/geographic mobility/.test(text)) glyph = "mobility";
  else if (/claim|filing|document|regulat|fiscal/.test(text)) glyph = "claims";
  else if (/opening|vacancy/.test(text)) glyph = "openings";
  else if (/hire|recruit/.test(text)) glyph = "hire";
  else if (/hour|duration|temporary|time/.test(text)) glyph = "clock";
  else if (/wage|earning|income|pay|cost|compensation/.test(text)) glyph = "wages";
  else if (/rate|credit|yield|spread|financial|mortgage|delinquen|saving/.test(text)) glyph = "rates";
  else if (/layoff|loss|closing|separation|contraction/.test(text)) glyph = "layoffs";
  else if (/participation|population|worker/.test(text)) glyph = "participation";
  else if (/trade|tariff|transport|freight|bottleneck|shipment/.test(text)) glyph = "freight";
  else if (/energy|fuel|weather|health|geopolitical|risk|shock/.test(text)) glyph = "shocks";
  else if (/retail|consumer|spending|sentiment|demand/.test(text)) glyph = "consumer";
  else if (/automation|robot|software|technology|research|productivity/.test(text)) glyph = "automation";
  else if (/investment|capital|construction|business|inventory/.test(text)) glyph = "investment";
  else if (/production|output|capacity|sales|growth|activity/.test(text)) glyph = "growth";
  else glyph = ["growth", "consumer", "demand", "layoffs", "investment", "rates", "wages", "automation", "supply", "shocks"][Math.max(0, placement.sector)] ?? "detail-1";
  return `${glyph}@${placement.order}`;
}

export function drawPremiumGlyph(context: CanvasRenderingContext2D, glyph: string, x: number, y: number, radius: number, color: string) {
  const variant = Number(glyph.split("@")[1] ?? 0);
  glyph = glyph.split("@")[0];
  const scale = radius / 20;
  context.save();
  context.translate(x, y);
  context.scale(scale, scale);
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = glyph.startsWith("detail-") ? 2.6 : 1.8;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.beginPath();
  if (glyph === "network") {
    [[0,0],[-8,-7],[8,-7],[0,9]].forEach(([px,py], index) => { context.moveTo(index ? 0 : px, index ? 0 : py); if (index) context.lineTo(px,py); });
    context.stroke();
    [[0,0],[-8,-7],[8,-7],[0,9]].forEach(([px,py]) => { context.beginPath(); context.arc(px,py,2.4,0,Math.PI*2); context.fill(); });
  } else if (glyph === "growth") {
    context.moveTo(-9,7); context.lineTo(-3,1); context.lineTo(2,4); context.lineTo(9,-7); context.moveTo(4,-7); context.lineTo(9,-7); context.lineTo(9,-2); context.stroke();
  } else if (glyph === "consumer") {
    context.moveTo(-9,-5); context.lineTo(-6,6); context.lineTo(7,6); context.lineTo(9,-4); context.closePath(); context.moveTo(-4,-6); context.quadraticCurveTo(0,-12,4,-6); context.stroke();
  } else if (glyph === "demand") {
    context.arc(-5,-4,3,0,Math.PI*2); context.moveTo(1,-4); context.arc(4,-4,3,0,Math.PI*2); context.moveTo(-10,9); context.quadraticCurveTo(-5,1,0,9); context.moveTo(0,9); context.quadraticCurveTo(5,1,10,9); context.stroke();
  } else if (glyph === "layoffs") {
    context.moveTo(-10,-6); context.lineTo(-3,1); context.lineTo(2,-4); context.lineTo(9,8); context.moveTo(-10,8); context.lineTo(10,8); context.stroke();
  } else if (glyph === "investment") {
    context.rect(-9,-8,18,16); context.moveTo(-5,5); context.lineTo(-5,0); context.moveTo(0,5); context.lineTo(0,-4); context.moveTo(5,5); context.lineTo(5,-7); context.stroke();
  } else if (glyph === "rates") {
    context.arc(-5,-5,3,0,Math.PI*2); context.moveTo(-7,8); context.lineTo(7,-8); context.moveTo(5,5); context.arc(5,5,3,0,Math.PI*2); context.stroke();
  } else if (glyph === "wages") {
    context.arc(0,0,9,0,Math.PI*2); context.moveTo(3,-5); context.quadraticCurveTo(-5,-8,-5,-2); context.quadraticCurveTo(-5,2,3,2); context.quadraticCurveTo(7,4,2,7); context.stroke();
  } else if (glyph === "automation") {
    context.rect(-8,-7,16,14); context.moveTo(-3,-1); context.arc(-3,-1,1,0,Math.PI*2); context.moveTo(4,-1); context.arc(3,-1,1,0,Math.PI*2); context.moveTo(-4,4); context.lineTo(4,4); context.moveTo(0,-10); context.lineTo(0,-7); context.stroke();
  } else if (glyph === "supply") {
    context.arc(0,-5,4,0,Math.PI*2); context.moveTo(-9,9); context.quadraticCurveTo(-8,0,0,0); context.quadraticCurveTo(8,0,9,9); context.stroke();
  } else if (glyph === "shocks") {
    context.moveTo(1,-10); context.lineTo(-6,1); context.lineTo(0,1); context.lineTo(-2,10); context.lineTo(7,-2); context.lineTo(1,-2); context.closePath(); context.stroke();
  } else if (glyph === "claims") {
    context.moveTo(-7,-10); context.lineTo(4,-10); context.lineTo(8,-6); context.lineTo(8,10); context.lineTo(-7,10); context.closePath(); context.moveTo(4,-10); context.lineTo(4,-5); context.lineTo(8,-5); context.moveTo(-3,-1); context.lineTo(4,-1); context.moveTo(-3,4); context.lineTo(3,4); context.stroke();
  } else if (glyph === "openings") {
    context.rect(-7,-10,13,20); context.moveTo(6,0); context.lineTo(10,0); context.moveTo(3,0); context.arc(2,0,1,0,Math.PI*2); context.fill(); context.stroke();
  } else if (glyph === "hire") {
    context.arc(-3,-5,4,0,Math.PI*2); context.moveTo(-10,10); context.quadraticCurveTo(-9,1,-3,1); context.quadraticCurveTo(3,1,4,10); context.moveTo(7,-2); context.lineTo(7,6); context.moveTo(3,2); context.lineTo(11,2); context.stroke();
  } else if (glyph === "clock") {
    context.arc(0,0,10,0,Math.PI*2); context.moveTo(0,-6); context.lineTo(0,1); context.lineTo(6,4); context.stroke();
  } else if (glyph === "participation") {
    [-7,0,7].forEach((px) => { context.moveTo(px,-7); context.arc(px,-7,2.4,0,Math.PI*2); context.moveTo(px,-3); context.lineTo(px,8); }); context.moveTo(-11,2); context.lineTo(11,2); context.stroke();
  } else if (glyph === "ratio") {
    context.arc(-5,-4,3,0,Math.PI*2); context.moveTo(-10,8); context.quadraticCurveTo(-9,1,-5,1); context.quadraticCurveTo(-1,1,0,8); context.moveTo(3,-8); context.lineTo(8,-8); context.moveTo(3,0); context.lineTo(8,0); context.moveTo(3,8); context.lineTo(8,8); context.stroke();
  } else if (glyph === "population") {
    context.arc(0,-6,3.5,0,Math.PI*2); context.moveTo(-7,8); context.quadraticCurveTo(-6,0,0,0); context.quadraticCurveTo(6,0,7,8); context.moveTo(-11,8); context.lineTo(11,8); context.stroke();
  } else if (glyph === "prime-age") {
    context.arc(0,0,9,0,Math.PI*2); context.moveTo(0,-9); context.lineTo(0,-12); context.moveTo(0,9); context.lineTo(0,12); context.moveTo(-9,0); context.lineTo(-12,0); context.moveTo(9,0); context.lineTo(12,0); context.moveTo(-3,2); context.lineTo(0,-3); context.lineTo(3,2); context.stroke();
  } else if (glyph === "migration") {
    context.moveTo(-11,-4); context.lineTo(5,-4); context.moveTo(1,-8); context.lineTo(6,-4); context.lineTo(1,0); context.moveTo(11,5); context.lineTo(-5,5); context.moveTo(-1,1); context.lineTo(-6,5); context.lineTo(-1,9); context.stroke();
  } else if (glyph === "education") {
    context.moveTo(-11,-3); context.lineTo(0,-9); context.lineTo(11,-3); context.lineTo(0,3); context.closePath(); context.moveTo(-7,0); context.lineTo(-7,6); context.quadraticCurveTo(0,11,7,6); context.lineTo(7,0); context.stroke();
  } else if (glyph === "skills") {
    context.moveTo(-10,7); context.lineTo(-3,0); context.lineTo(1,4); context.lineTo(10,-6); context.moveTo(-8,-8); context.lineTo(-3,-3); context.moveTo(4,5); context.lineTo(9,10); context.stroke();
  } else if (glyph === "retirement") {
    context.arc(-2,-5,4,0,Math.PI*2); context.moveTo(-8,10); context.quadraticCurveTo(-7,1,-2,1); context.quadraticCurveTo(3,1,4,10); context.moveTo(8,-9); context.arc(8,-9,2,0,Math.PI*2); context.moveTo(8,-5); context.lineTo(8,8); context.stroke();
  } else if (glyph === "caregiving") {
    context.arc(-5,-5,3,0,Math.PI*2); context.moveTo(5,-5); context.arc(5,-5,3,0,Math.PI*2); context.moveTo(-10,9); context.quadraticCurveTo(-8,0,-4,2); context.quadraticCurveTo(0,6,4,2); context.quadraticCurveTo(8,0,10,9); context.stroke();
  } else if (glyph === "mobility") {
    context.moveTo(-10,0); context.lineTo(8,0); context.moveTo(4,-4); context.lineTo(9,0); context.lineTo(4,4); context.moveTo(-5,-8); context.arc(-5,-8,2,0,Math.PI*2); context.moveTo(-5,-5); context.lineTo(-5,8); context.stroke();
  } else if (glyph === "freight") {
    context.rect(-10,-7,12,11); context.moveTo(2,-2); context.lineTo(7,-2); context.lineTo(10,1); context.lineTo(10,4); context.lineTo(2,4); context.moveTo(-7,4); context.arc(-6,7,3,Math.PI,Math.PI*2); context.moveTo(5,4); context.arc(6,7,3,Math.PI,Math.PI*2); context.stroke();
  } else if (glyph.startsWith("detail-")) {
    const variant = Number(glyph.slice(7));
    if (variant === 1) { context.moveTo(-8,0); context.lineTo(8,0); context.moveTo(0,-8); context.lineTo(0,8); }
    else if (variant === 2) { context.moveTo(0,-9); context.lineTo(9,0); context.lineTo(0,9); context.lineTo(-9,0); context.closePath(); }
    else if (variant === 3) { context.moveTo(0,-9); context.lineTo(9,8); context.lineTo(-9,8); context.closePath(); }
    else if (variant === 4) context.rect(-7,-7,14,14);
    else if (variant === 5) { context.arc(-5,0,3,0,Math.PI*2); context.moveTo(2,0); context.arc(5,0,3,0,Math.PI*2); context.moveTo(-2,0); context.lineTo(2,0); }
    else if (variant === 6) { context.moveTo(-7,-7); context.lineTo(7,7); context.moveTo(7,-7); context.lineTo(-7,7); }
    else if (variant === 7) { [-6,0,6].forEach((px, index) => { context.moveTo(px,8); context.lineTo(px,2-index*5); }); }
    else if (variant === 8) { context.moveTo(-9,-5); context.lineTo(0,5); context.lineTo(9,-5); context.moveTo(-9,2); context.lineTo(0,10); context.lineTo(9,2); }
    else if (variant === 9) { for (let index=0; index<=6; index+=1) { const angle=Math.PI/3*index; const px=Math.cos(angle)*8; const py=Math.sin(angle)*8; if (index) context.lineTo(px,py); else context.moveTo(px,py); } }
    else { context.arc(0,0,8,0,Math.PI*2); context.moveTo(-11,0); context.lineTo(11,0); context.moveTo(0,-11); context.lineTo(0,11); }
    context.stroke();
  } else {
    context.arc(0,0,3.2,0,Math.PI*2); context.stroke();
  }
  if (variant > 0 && !glyph.startsWith("detail-")) {
    const angle = ((variant - 1) / 10) * Math.PI * 2 - Math.PI / 2;
    const markerX = Math.cos(angle) * 12;
    const markerY = Math.sin(angle) * 12;
    context.fillStyle = color;
    context.beginPath();
    context.arc(markerX, markerY, variant > 5 ? 1.9 : 1.35, 0, Math.PI * 2);
    if (variant > 5) context.stroke(); else context.fill();
  }
  context.restore();
}
