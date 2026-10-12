// Tests for the product-history table sort comparators.
// Run: node --test auxsays/assets/js/patch-table-sort.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { compareVersion, evidenceRank, rowComparator } from './patch-table-sort.mjs';

const sortStr = (arr, cmp) => [...arr].sort(cmp);
const lt = (a, b) => assert.ok(compareVersion(a, b) < 0, `${a} should sort before ${b}`);

test('version: natural numeric order, not lexical', () => {
  lt('1.9', '1.10');
  lt('26.9', '26.10');
  lt('2603', '2607');
  lt('0.16.4', '0.19.3');            // ComfyUI two-digit minors
  lt('31.1.2', '32.0.0');            // OBS
  lt('20.2', '20.3');                // DaVinci
});

test('version: zero-padded segments compare numerically', () => {
  lt('26.001.21529', '26.001.21563');
  lt('24.002.20736', '24.002.20933');
  lt('20.006.20034', '20.009.20063'); // middle segment 006 < 009
});

test('version: unequal segment counts, shorter prefix first', () => {
  lt('19', '19.0.1');
  lt('20.2', '20.2.1');
  lt('21', '21.0');
  lt('21.0', '21.0.1');
});

test('version: alphanumeric Windows YYHN order', () => {
  lt('23H2', '24H2');
  lt('24H2', '25H2');
  lt('25H2', '26H1');
  const sorted = sortStr(['26H1', '23H2', '25H2', '24H2'], compareVersion);
  assert.deepEqual(sorted, ['23H2', '24H2', '25H2', '26H1']);
});

test('version: embedded-text values are deterministic and stable (no throw)', () => {
  const a = compareVersion('21 Public Beta 1', '21.0.1');
  const b = compareVersion('21.0.1', '21 Public Beta 1');
  assert.equal(Math.sign(a), -Math.sign(b));     // antisymmetric
  assert.equal(compareVersion('21 Public Beta 1', '21 Public Beta 1'), 0);
});

test('version: total order over a mixed real product set', () => {
  const input = ['20.3.3', '19.1', '21.0.1', '20', '19', '18.6.6', '21', '20.2', '21.0'];
  const sorted = sortStr(input, compareVersion);
  // strictly non-decreasing under the comparator
  for (let i = 1; i < sorted.length; i += 1) {
    assert.ok(compareVersion(sorted[i - 1], sorted[i]) <= 0, `${sorted[i - 1]} !<= ${sorted[i]}`);
  }
});

test('evidence: report-count tiering matches the locked thresholds', () => {
  const cases = [[0, 0], [1, 1], [7, 1], [8, 2], [24, 2], [25, 3], [32, 3], [33, 4], [79, 4], [1000, 4]];
  cases.forEach(([n, rank]) => assert.equal(evidenceRank(n), rank, `${n} -> ${rank}`));
  assert.equal(evidenceRank('not-a-number'), 0);
});

test('rowComparator: numeric key with direction + deterministic date/version tiebreak', () => {
  const row = (date, version, reports) => ({ dataset: { date, version, reports } });
  const rows = [
    row('2026-05-01T00:00:00Z', '2.0', '5'),
    row('2026-05-01T00:00:00Z', '2.10', '5'), // same reports + same date -> version tiebreak
    row('2026-04-01T00:00:00Z', '1.0', '9'),
  ];
  const byReportsDesc = [...rows].sort(rowComparator('reports', 'num', 'desc'));
  assert.equal(byReportsDesc[0].dataset.reports, '9'); // highest reports first
  // the two 5-report rows keep newest-date-then-version order (2.0 before 2.10)
  assert.equal(byReportsDesc[1].dataset.version, '2.0');
  assert.equal(byReportsDesc[2].dataset.version, '2.10');
});

test('rowComparator: version key uses the natural comparator', () => {
  const row = (version) => ({ dataset: { version, date: '2026-01-01T00:00:00Z' } });
  const sorted = [row('1.10'), row('1.9'), row('1.2')].sort(rowComparator('version', 'version', 'asc'));
  assert.deepEqual(sorted.map((r) => r.dataset.version), ['1.2', '1.9', '1.10']);
});

test('rowComparator: date key sorts ISO strings chronologically', () => {
  const row = (date, version) => ({ dataset: { date, version } });
  const sorted = [row('2025-11-20T00:00:00Z', 'a'), row('2026-07-01T00:00:00Z', 'b'), row('2026-01-30T00:00:00Z', 'c')]
    .sort(rowComparator('date', 'date', 'desc'));
  assert.deepEqual(sorted.map((r) => r.dataset.date.slice(0, 10)), ['2026-07-01', '2026-01-30', '2025-11-20']);
});

test('verdict: this module owns NO verdict vocabulary (AUX-008)', async () => {
  // The risk order lives in lib/patch_decision.py, mirrored for Liquid in
  // _data/patch_verdicts.yml. A copy here would be a third one, free to drift -- the retired copy
  // already listed a label the Python vocabulary did not have.
  const mod = await import('./patch-table-sort.mjs');
  assert.equal(mod.verdictRank, undefined, 'verdictRank must stay retired');
  assert.equal(mod.VERDICT_ORDER, undefined, 'VERDICT_ORDER must stay retired');
  const src = await (await import('node:fs/promises')).readFile(
    new URL('./patch-table-sort.mjs', import.meta.url), 'utf8');
  ['AVOID', 'TEST FIRST', 'MANUAL WATCH', 'OFFICIAL ONLY'].forEach((label) => {
    assert.equal(src.includes(`'${label}'`), false, `${label} must not be a literal in this module`);
  });
});

test('verdict: the column sorts the server-emitted numeric rank, not text', () => {
  // Proves the retirement is safe: ordering comes from data-verdict-rank as a number.
  const row = (rank) => ({ dataset: { verdictRank: String(rank), date: '2026-01-01', version: '1.0' } });
  const cmp = rowComparator('verdict-rank', 'num', 'asc');
  assert.ok(cmp(row(0), row(1)) < 0, 'AVOID rank sorts before WAIT rank');
  assert.ok(cmp(row(7), row(99)) < 0, 'known ranks sort before unknown');
  assert.equal(cmp(row(2), row(2)), 0, 'equal ranks tie, then fall to the date/version tiebreak');
});

