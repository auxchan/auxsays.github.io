import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const reportPath = path.join(root, 'assets', 'img', 'patch-logos', '_generation-report.json');

const report = {
  generated_at: new Date().toISOString(),
  mode: 'disabled',
  reason: 'Logo generation is disabled. AUXSAYS uses curated official/reusable logo assets or explicit remote official logo URLs from product/company data.',
  generated: [],
  overwritten: []
};

fs.mkdirSync(path.dirname(reportPath), { recursive: true });
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
console.log('Patch logo generation disabled; using curated product/company logo_path values.');
