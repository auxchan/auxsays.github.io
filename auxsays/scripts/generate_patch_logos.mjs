import fs from 'node:fs';
import path from 'node:path';
import * as simpleIcons from 'simple-icons';

const root = process.cwd();
const mapPath = path.join(root, '_data', 'patch_logo_slugs.json');
const outputDir = path.join(root, 'assets', 'img', 'patch-logos');
const reportPath = path.join(root, 'assets', 'img', 'patch-logos', '_generation-report.json');

const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const escapeXml = (value) => String(value || '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

function loadIconIndex() {
  const bySlug = new Map();
  const byTitle = new Map();

  Object.values(simpleIcons).forEach((icon) => {
    if (!icon || !icon.slug || !icon.path) return;
    bySlug.set(normalize(icon.slug), icon);
    byTitle.set(normalize(icon.title), icon);
  });

  return { bySlug, byTitle };
}

function findIcon(candidates, index) {
  for (const candidate of candidates) {
    const key = normalize(candidate);
    if (!key) continue;
    if (index.bySlug.has(key)) return { icon: index.bySlug.get(key), matched: candidate };
    if (index.byTitle.has(key)) return { icon: index.byTitle.get(key), matched: candidate };
  }
  return null;
}

function hexToRgb(hex) {
  const clean = String(hex || '').replace('#', '');
  if (!/^[0-9a-f]{6}$/i.test(clean)) return null;
  return {
    r: parseInt(clean.slice(0, 2), 16),
    g: parseInt(clean.slice(2, 4), 16),
    b: parseInt(clean.slice(4, 6), 16)
  };
}

function channelToLinear(value) {
  const normalized = value / 255;
  return normalized <= 0.03928
    ? normalized / 12.92
    : Math.pow((normalized + 0.055) / 1.055, 2.4);
}

function relativeLuminance(rgb) {
  return (
    0.2126 * channelToLinear(rgb.r) +
    0.7152 * channelToLinear(rgb.g) +
    0.0722 * channelToLinear(rgb.b)
  );
}

function contrastRatio(hexA, hexB) {
  const rgbA = hexToRgb(hexA);
  const rgbB = hexToRgb(hexB);
  if (!rgbA || !rgbB) return 0;
  const lumA = relativeLuminance(rgbA);
  const lumB = relativeLuminance(rgbB);
  const lighter = Math.max(lumA, lumB);
  const darker = Math.min(lumA, lumB);
  return (lighter + 0.05) / (darker + 0.05);
}

function chooseIconFill(icon) {
  const brandHex = /^[0-9a-f]{6}$/i.test(icon.hex || '') ? `#${icon.hex}` : '#F4EFE4';

  // Logo tiles sit on a dark teal/black badge. Preserve brand color when it scans well,
  // but convert very dark/low-contrast brand fills to warm white so they remain legible.
  const tileBackground = '#101A20';
  const contrast = contrastRatio(brandHex, tileBackground);
  return contrast >= 2.35 ? brandHex : '#F4EFE4';
}

function iconSvg(icon, id) {
  const title = escapeXml(icon.title || id);
  const fill = chooseIconFill(icon);
  return `<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${title} logo" viewBox="0 0 24 24" width="24" height="24">
  <title>${title}</title>
  <path fill="${fill}" d="${icon.path}"/>
</svg>
`;
}

function main() {
  if (!fs.existsSync(mapPath)) {
    console.error(`Logo slug map not found: ${mapPath}`);
    process.exit(1);
  }

  fs.mkdirSync(outputDir, { recursive: true });
  const slugMap = JSON.parse(fs.readFileSync(mapPath, 'utf8'));
  const index = loadIconIndex();
  const report = {
    generated_at: new Date().toISOString(),
    generated: [],
    fallback_kept: []
  };

  for (const [id, candidates] of Object.entries(slugMap)) {
    const candidateList = Array.isArray(candidates) ? candidates : [candidates];
    const found = findIcon(candidateList, index);
    const outPath = path.join(outputDir, `${id}.svg`);

    if (!found) {
      report.fallback_kept.push({ id, candidates: candidateList, reason: 'No Simple Icons match found' });
      if (!fs.existsSync(outPath)) {
        fs.writeFileSync(outPath, `<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeXml(id)} logo" viewBox="0 0 96 40" width="96" height="40">
  <rect x="1" y="1" width="94" height="38" rx="10" fill="#101A20" stroke="#29444D"/>
  <text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle" fill="#F4EFE4" font-family="Inter, Arial, Helvetica, sans-serif" font-size="12" font-weight="800">${escapeXml(id.slice(0, 12))}</text>
</svg>
`, 'utf8');
      }
      continue;
    }

    fs.writeFileSync(outPath, iconSvg(found.icon, id), 'utf8');
    report.generated.push({ id, matched_slug_or_title: found.matched, simple_icons_title: found.icon.title, source_hex: found.icon.hex, rendered_fill: chooseIconFill(found.icon) });
  }

  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
  console.log(`Generated ${report.generated.length} Simple Icons logo(s).`);
  if (report.fallback_kept.length) {
    console.log(`Kept ${report.fallback_kept.length} fallback logo(s). See ${reportPath}`);
  }
}

main();
