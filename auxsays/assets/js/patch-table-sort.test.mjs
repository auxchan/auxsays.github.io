// Tests for the product-history table sort comparators.
// Run: node --test auxsays/assets/js/patch-table-sort.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { compareVersion, verdictRank, evidenceRank, rowComparator, VERDICT_ORDER } from './patch-table-sort.mjs';

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

test('verdict: every allowed category maps to its risk index', () => {
  VERDICT_ORDER.forEach((label, i) => assert.equal(verdictRank(label), i, `${label} -> ${i}`));
  assert.deepEqual(VERDICT_ORDER.length, 8);
});

test('verdict: real suffix-bearing / cased forms normalise to the leading category', () => {
  assert.equal(verdictRank('AVOID for production'), 0);
  assert.equal(verdictRank('WAIT for production systems'), 1);
  assert.equal(verdictRank('TEST FIRST'), 2);
  assert.equal(verdictRank('SAFE ENOUGH to test'), 4);
  assert.equal(verdictRank('Insufficient data'), 6);     // case-insensitive
  assert.equal(verdictRank('SECURITY UPDATE'), 3);
  assert.equal(verdictRank('OFFICIAL ONLY'), 5);
  assert.equal(verdictRank('MANUAL WATCH'), 7);
  // A compound label normalises to its highest-priority (lowest-rank) category, deterministically.
  assert.equal(verdictRank('SECURITY UPDATE, TEST FIRST'), 2);
});

test('verdict: unknown / empty values sort last (99) but remain classified', () => {
  assert.equal(verdictRank('something weird'), 99);
  assert.equal(verdictRank(''), 99);
  assert.equal(verdictRank(null), 99);
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
