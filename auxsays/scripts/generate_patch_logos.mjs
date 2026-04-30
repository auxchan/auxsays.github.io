import fs from 'node:fs';
import path from 'node:path';
import * as yaml from 'js-yaml';
import * as simpleIcons from 'simple-icons';

const root = process.cwd();
const mapPath = path.join(root, '_data', 'patch_logo_slugs.json');
const productsPath = path.join(root, '_data', 'patch_products.yml');
const companiesPath = path.join(root, '_data', 'patch_companies.yml');
const outputDir = path.join(root, 'assets', 'img', 'patch-logos');
const reportPath = path.join(root, 'assets', 'img', 'patch-logos', '_generation-report.json');

const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const escapeXml = (value) => String(value || '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');
const unique = (values) => [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))];

function loadJson(pathValue, fallback = {}) {
  if (!fs.existsSync(pathValue)) return fallback;
  return JSON.parse(fs.readFileSync(pathValue, 'utf8'));
}

function loadYaml(pathValue, fallback = []) {
  if (!fs.existsSync(pathValue)) return fallback;
  const parsed = yaml.load(fs.readFileSync(pathValue, 'utf8'));
  return parsed ?? fallback;
}

function logoBasename(logoPath) {
  const value = String(logoPath || '').trim();
  if (!value) return '';
  return path.basename(value).replace(/\.svg$/i, '');
}

function tokenCandidates(value) {
  const raw = String(value || '').trim();
  if (!raw) return [];
  const compact = raw.replace(/[^a-zA-Z0-9]/g, '');
  const words = raw.split(/[^a-zA-Z0-9]+/).filter(Boolean);
  return unique([raw, compact, words.join(''), ...words]);
}

function addLogoTarget(targets, id, candidates, metadata = {}) {
  const cleanId = String(id || '').trim();
  if (!cleanId) return;
  const current = targets.get(cleanId) || { candidates: [], metadata: {} };
  targets.set(cleanId, {
    candidates: unique([...current.candidates, ...candidates]),
    metadata: { ...current.metadata, ...metadata }
  });
}

function mappedCandidates(slugMap, key) {
  const value = slugMap[key];
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function buildLogoTargets(slugMap, products, companies) {
  const targets = new Map();

  for (const [id, candidates] of Object.entries(slugMap)) {
    addLogoTarget(targets, id, Array.isArray(candidates) ? candidates : [candidates], { source: 'slug_map' });
  }

  for (const company of companies) {
    if (!company || typeof company !== 'object') continue;
    const id = company.id || company.company_id;
    const logoId = logoBasename(company.logo_path) || id;
    const candidates = unique([
      ...mappedCandidates(slugMap, id),
      ...mappedCandidates(slugMap, logoId),
      ...tokenCandidates(id),
      ...tokenCandidates(logoId),
      ...tokenCandidates(company.company_name),
      ...tokenCandidates(company.logo_label),
      ...tokenCandidates(company.badge_text)
    ]);
    addLogoTarget(targets, logoId, candidates, { source: 'company_data', company_id: id, company_name: company.company_name });
    if (id && id !== logoId) addLogoTarget(targets, id, candidates, { source: 'company_data_alias', company_id: id, company_name: company.company_name });
  }

  for (const product of products) {
    if (!product || typeof product !== 'object') continue;
    const id = product.product_id || product.id || product.source_id;
    const logoId = logoBasename(product.logo_path) || id;
    const candidates = unique([
      ...mappedCandidates(slugMap, id),
      ...mappedCandidates(slugMap, logoId),
      ...tokenCandidates(id),
      ...tokenCandidates(logoId),
      ...tokenCandidates(product.product_name),
      ...tokenCandidates(product.logo_label),
      ...tokenCandidates(product.company_name),
      ...tokenCandidates(product.badge_text)
    ]);
    addLogoTarget(targets, logoId, candidates, { source: 'product_data', product_id: id, product_name: product.product_name });
    if (id && id !== logoId) addLogoTarget(targets, id, candidates, { source: 'product_data_alias', product_id: id, product_name: product.product_name });
  }

  return targets;
}

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
  return { r: parseInt(clean.slice(0, 2), 16), g: parseInt(clean.slice(2, 4), 16), b: parseInt(clean.slice(4, 6), 16) };
}

function channelToLinear(value) {
  const normalized = value / 255;
  return normalized <= 0.03928 ? normalized / 12.92 : Math.pow((normalized + 0.055) / 1.055, 2.4);
}

function relativeLuminance(rgb) {
  return 0.2126 * channelToLinear(rgb.r) + 0.7152 * channelToLinear(rgb.g) + 0.0722 * channelToLinear(rgb.b);
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
  const tileBackground = '#101A20';
  return contrastRatio(brandHex, tileBackground) >= 2.35 ? brandHex : '#F4EFE4';
}

function iconSvg(icon, id) {
  const title = escapeXml(icon.title || id);
  const fill = chooseIconFill(icon);
  return `<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${title} logo" viewBox="0 0 24 24" width="24" height="24">\n  <title>${title}</title>\n  <path fill="${fill}" d="${icon.path}"/>\n</svg>\n`;
}

function fallbackLabel(id, metadata = {}) {
  const explicit = metadata.product_name || metadata.company_name || id;
  const words = String(explicit).split(/[^a-zA-Z0-9]+/).filter(Boolean);
  if (words.length >= 2) return words.slice(0, 3).map((word) => word[0]).join('').toUpperCase();
  return String(explicit).replace(/[^a-zA-Z0-9]/g, '').slice(0, 4).toUpperCase() || String(id).slice(0, 4).toUpperCase();
}

function fallbackSvg(id, metadata = {}) {
  const label = escapeXml(fallbackLabel(id, metadata));
  const aria = escapeXml(`${metadata.product_name || metadata.company_name || id} generated logo`);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="${aria}">\n  <rect x="6" y="6" width="116" height="116" rx="24" fill="#101A20" stroke="#29444D" stroke-width="2"/>\n  <path d="M25 31h78M25 97h78" stroke="#36E7F7" stroke-width="3" stroke-linecap="round" opacity="0.55"/>\n  <text x="64" y="73" text-anchor="middle" font-family="Inter, Arial, Helvetica, sans-serif" font-size="30" font-weight="850" fill="#9DF7FF" letter-spacing="1">${label}</text>\n</svg>\n`;
}

function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const slugMap = loadJson(mapPath, {});
  const products = loadYaml(productsPath, []);
  const companies = loadYaml(companiesPath, []);
  const index = loadIconIndex();
  const targets = buildLogoTargets(slugMap, products, companies);
  const report = { generated_at: new Date().toISOString(), source: 'patch_products.yml + patch_companies.yml + patch_logo_slugs.json overrides', target_count: targets.size, generated: [], fallbacks: [] };

  for (const [id, target] of [...targets.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const candidateList = unique(target.candidates);
    const found = findIcon(candidateList, index);
    const outPath = path.join(outputDir, `${id}.svg`);
    if (!found) {
      fs.writeFileSync(outPath, fallbackSvg(id, target.metadata), 'utf8');
      report.fallbacks.push({ id, candidates: candidateList, metadata: target.metadata, reason: 'No Simple Icons match found; generated AUX fallback badge' });
      continue;
    }
    fs.writeFileSync(outPath, iconSvg(found.icon, id), 'utf8');
    report.generated.push({ id, matched_slug_or_title: found.matched, simple_icons_title: found.icon.title, source_hex: found.icon.hex, rendered_fill: chooseIconFill(found.icon), metadata: target.metadata });
  }

  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
  console.log(`Generated ${report.generated.length} Simple Icons logo(s).`);
  console.log(`Generated ${report.fallbacks.length} AUX fallback badge(s).`);
  console.log(`Logo generation report: ${reportPath}`);
}

main();
