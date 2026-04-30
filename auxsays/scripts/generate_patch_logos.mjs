import fs from 'node:fs';
import path from 'node:path';
import * as yaml from 'js-yaml';
import * as simpleIcons from 'simple-icons';

const root = process.cwd();
const registryPath = path.join(root, '_data', 'patch_logo_sources.yml');
const productsPath = path.join(root, '_data', 'patch_products.yml');
const companiesPath = path.join(root, '_data', 'patch_companies.yml');
const outputDir = path.join(root, 'assets', 'img', 'patch-logos');
const reportPath = path.join(outputDir, '_generation-report.json');

const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const escapeXml = (value) => String(value || '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');
const unique = (values) => [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))];

function readYaml(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
  return yaml.load(fs.readFileSync(filePath, 'utf8')) ?? fallback;
}

function loadRegistry() {
  const parsed = readYaml(registryPath, {});
  if (!parsed || typeof parsed !== 'object' || !parsed.logos || typeof parsed.logos !== 'object') {
    throw new Error(`Logo registry is missing a top-level "logos" object: ${registryPath}`);
  }
  return parsed.logos;
}

function loadIconIndex() {
  const bySlug = new Map();
  Object.values(simpleIcons).forEach((icon) => {
    if (!icon || !icon.slug || !icon.path) return;
    bySlug.set(normalize(icon.slug), icon);
  });
  return bySlug;
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
  const tileBackground = '#101A20';
  return contrastRatio(brandHex, tileBackground) >= 2.35 ? brandHex : '#F4EFE4';
}

function iconSvg(icon, id) {
  const title = escapeXml(icon.title || id);
  const fill = chooseIconFill(icon);
  return `<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${title} logo" viewBox="0 0 24 24" width="24" height="24">\n  <title>${title}</title>\n  <path fill="${fill}" d="${icon.path}"/>\n</svg>\n`;
}

function placeholderSvg(id, reason) {
  const label = escapeXml(String(id || '').split(/[^a-zA-Z0-9]+/).filter(Boolean).slice(0, 3).map((word) => word[0]).join('').toUpperCase() || 'AUX');
  const aria = escapeXml(`${id} logo unavailable: ${reason}`);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="${aria}">\n  <rect x="6" y="6" width="116" height="116" rx="24" fill="#101A20" stroke="#29444D" stroke-width="2"/>\n  <path d="M25 31h78M25 97h78" stroke="#36E7F7" stroke-width="3" stroke-linecap="round" opacity="0.55"/>\n  <text x="64" y="73" text-anchor="middle" font-family="Inter, Arial, Helvetica, sans-serif" font-size="30" font-weight="850" fill="#9DF7FF" letter-spacing="1">${label}</text>\n</svg>\n`;
}

function slugsFromEntry(entry) {
  if (Array.isArray(entry.slugs)) return unique(entry.slugs);
  if (entry.slug) return unique([entry.slug]);
  return [];
}

function writeLogo(id, svg) {
  fs.writeFileSync(path.join(outputDir, `${id}.svg`), svg, 'utf8');
}

function resolveLogo(id, registry, iconIndex, cache, stack = []) {
  if (cache.has(id)) return cache.get(id);
  if (stack.includes(id)) {
    const result = { ok: false, type: 'cycle', reason: `Alias cycle detected: ${[...stack, id].join(' -> ')}` };
    cache.set(id, result);
    return result;
  }

  const entry = registry[id];
  if (!entry) {
    const result = { ok: false, type: 'missing_registry', reason: 'No approved logo registry entry' };
    cache.set(id, result);
    return result;
  }

  const type = String(entry.type || '').trim();

  if (type === 'manual') {
    const outPath = path.join(outputDir, `${id}.svg`);
    if (fs.existsSync(outPath)) {
      const result = { ok: true, type: 'manual', svg: fs.readFileSync(outPath, 'utf8'), source: 'committed_manual_asset', note: entry.note || '' };
      cache.set(id, result);
      return result;
    }
    const result = { ok: false, type: 'manual_missing', reason: 'Manual logo configured but committed SVG file is missing' };
    cache.set(id, result);
    return result;
  }

  if (type === 'alias') {
    const target = String(entry.target || '').trim();
    if (!target) {
      const result = { ok: false, type: 'bad_alias', reason: 'Alias entry has no target' };
      cache.set(id, result);
      return result;
    }
    const targetResult = resolveLogo(target, registry, iconIndex, cache, [...stack, id]);
    const result = targetResult.ok
      ? { ...targetResult, type: 'alias', alias_target: target }
      : { ok: false, type: 'alias_unresolved', reason: `Alias target ${target} failed: ${targetResult.reason || targetResult.type}` };
    cache.set(id, result);
    return result;
  }

  if (type === 'simple_icons') {
    const slugs = slugsFromEntry(entry);
    for (const slug of slugs) {
      const icon = iconIndex.get(normalize(slug));
      if (!icon) continue;
      const result = {
        ok: true,
        type: 'simple_icons',
        svg: iconSvg(icon, id),
        matched_slug: slug,
        simple_icons_title: icon.title,
        source_hex: icon.hex,
        rendered_fill: chooseIconFill(icon)
      };
      cache.set(id, result);
      return result;
    }
    const result = { ok: false, type: 'simple_icons_missing', reason: `No exact Simple Icons match for approved slug(s): ${slugs.join(', ')}` };
    cache.set(id, result);
    return result;
  }

  const result = { ok: false, type: 'unknown_source_type', reason: `Unsupported logo source type: ${type || '(blank)'}` };
  cache.set(id, result);
  return result;
}

function logoIdsFromData() {
  const ids = new Set();
  const addId = (value) => {
    const clean = String(value || '').trim();
    if (clean) ids.add(clean);
  };

  const products = readYaml(productsPath, []);
  const companies = readYaml(companiesPath, []);

  if (Array.isArray(products)) {
    for (const product of products) {
      if (!product || typeof product !== 'object') continue;
      addId(product.id || product.product_id || product.source_id);
    }
  }

  if (Array.isArray(companies)) {
    for (const company of companies) {
      if (!company || typeof company !== 'object') continue;
      addId(company.id || company.company_id);
    }
  }

  return ids;
}

function main() {
  fs.mkdirSync(outputDir, { recursive: true });

  const registry = loadRegistry();
  const iconIndex = loadIconIndex();
  const cache = new Map();
  const dataIds = logoIdsFromData();
  const registryIds = new Set(Object.keys(registry));
  const targetIds = [...new Set([...dataIds, ...registryIds])].sort((a, b) => a.localeCompare(b));

  const report = {
    generated_at: new Date().toISOString(),
    policy: 'explicit-approved-logo-registry-only',
    registry_path: '_data/patch_logo_sources.yml',
    target_count: targetIds.length,
    generated: [],
    manual: [],
    aliases: [],
    placeholders: [],
    missing_registry: []
  };

  for (const id of targetIds) {
    const result = resolveLogo(id, registry, iconIndex, cache);

    if (result.ok) {
      writeLogo(id, result.svg);
      if (result.type === 'manual') {
        report.manual.push({ id, note: result.note || '' });
      } else if (result.type === 'alias') {
        report.aliases.push({ id, target: result.alias_target });
      } else {
        report.generated.push({
          id,
          source: 'simple_icons',
          matched_slug: result.matched_slug,
          simple_icons_title: result.simple_icons_title,
          source_hex: result.source_hex,
          rendered_fill: result.rendered_fill
        });
      }
      continue;
    }

    const svg = placeholderSvg(id, result.reason || result.type);
    writeLogo(id, svg);
    const item = { id, type: result.type, reason: result.reason || result.type };
    if (result.type === 'missing_registry') report.missing_registry.push(item);
    else report.placeholders.push(item);
  }

  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
  console.log(`Logo policy: ${report.policy}`);
  console.log(`Generated ${report.generated.length} approved Simple Icons logo(s).`);
  console.log(`Generated ${report.aliases.length} approved alias logo(s).`);
  console.log(`Preserved ${report.manual.length} manual logo(s).`);
  console.log(`Wrote ${report.placeholders.length + report.missing_registry.length} placeholder logo(s) for unmapped/missing entries.`);
  if (report.missing_registry.length) {
    console.warn(`WARNING: ${report.missing_registry.length} product/company ID(s) lack approved logo registry entries. See ${reportPath}`);
  }
}

main();
