/**
 * My Installed Versions: storage and the comparison state machine.
 *
 * Executes the SHIPPED helpers sliced out of assets/js/auxsays.js against a stubbed window, so a
 * change to the production source changes what this tests.
 *
 * Node, like the other .mjs suites here, and classified the same way in the governed manifest.
 *
 * Run: node auxsays/assets/js/installed-versions.test.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, 'auxsays.js'), 'utf8');

const start = source.indexOf("const INSTALLED_KEY");
const end = source.indexOf("const paintInstalledControls");
if (start < 0 || end < 0 || end <= start) {
  console.error('FAIL: could not locate the installed-versions block in auxsays.js.');
  process.exit(2);
}
const block = source.slice(start, end);

let pass = 0;
let fail = 0;
const check = (label, condition, detail = '') => {
  if (condition) { pass += 1; console.log(`  PASS  ${label}`); }
  else { fail += 1; console.log(`  FAIL  ${label}${detail ? `  --  ${detail}` : ''}`); }
};

const build = (store) => {
  const events = [];
  const fakeWindow = { localStorage: store };
  const fakeDocument = { dispatchEvent: (e) => events.push(e) };
  // eslint-disable-next-line no-new-func
  const factory = new Function('window', 'document', 'CustomEvent', 'PRODUCT_ID_RE', `${block}
    return { readInstalled, writeInstalled, setInstalled, installedState, parallelLines, PATH_LIMIT };`);
  const api = factory(fakeWindow, fakeDocument, class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } },
    /^[a-z0-9][a-z0-9-]{0,63}$/);
  return { ...api, events };
};

const memoryStore = (initial) => {
  let value = initial;
  return { getItem: () => value, setItem: (_k, v) => { value = v; }, read: () => value };
};
const hostileStore = () => ({
  getItem: () => { throw new Error('blocked'); },
  setItem: () => { throw new Error('blocked'); },
});

// A product as the page payload describes it. rec = [version, build, date, url, beta]
const OBS = {
  id: 'obs-studio',
  recs: [
    ['32.2.2', '', '2026-08-14', '/updates/obs/32-2-2/', 0],
    ['32.2.1', '', '2026-07-24', '/updates/obs/32-2-1/', 0],
    ['32.1.2', '', '2026-04-21', '/updates/obs/32-1-2/', 0],
  ],
  more: 0,
};
const DAVINCI = {
  id: 'blackmagic-davinci',
  recs: [
    ['21.1', '', '2026-09-08', '/updates/dv/21-1/', 0],
    ['21 Public Beta 1', '', '2026-04-14', '/updates/dv/21-beta/', 1],
    ['21', '', '2026-04-14', '/updates/dv/21/', 0],
    ['20.2', '', '2026-01-10', '/updates/dv/20-2/', 0],
  ],
  more: 0,
};
// The case C3 is about: the ONLY newer record is a beta. Kept separate from DAVINCI, whose newest
// record is stable -- sharing one fixture silently changed C3's premise.
const BETA_TOP = {
  id: 'beta-top',
  recs: [
    ['21 Public Beta 1', '', '2026-04-14', '/updates/dv/21-beta/', 1],
    ['21', '', '2026-04-14', '/updates/dv/21/', 0],
  ],
  more: 0,
};
// Shaped like the real window: three servicing lines co-published on one date, and a line that
// stops and restarts further down. A three-record fixture with distinct dates looked sequential,
// which is the one thing Windows is not -- and no check could have told the difference.
const WINDOWS = {
  id: 'microsoft-windows-11',
  recs: [
    ['26H1', '28000.2956', '2026-09-22', '/updates/w/26h1-28000-2956/', 0],
    ['25H2', '26200.9550', '2026-09-22', '/updates/w/25h2-26200-9550/', 0],
    ['24H2', '26100.9550', '2026-09-22', '/updates/w/24h2-26100-9550/', 0],
    ['26H1', '28000.2954', '2026-09-08', '/updates/w/26h1-28000-2954/', 0],
    ['25H2', '26200.9445', '2026-09-08', '/updates/w/25h2-26200-9445/', 0],
  ],
  more: 0,
};

// Build-aware and SEQUENTIAL: versions run one after another, none of them restarting. The rule
// that protects Windows must leave this chronology alone.
const POWERPOINT = {
  id: 'microsoft-powerpoint',
  recs: [
    ['2609', '19231.20000', '2026-09-20', '/updates/pp/2609/', 0],
    ['2608', '19127.20100', '2026-08-18', '/updates/pp/2608/', 0],
    ['2607', '19029.20136', '2026-07-15', '/updates/pp/2607/', 0],
  ],
  more: 0,
};

console.log('='.repeat(70));
console.log('MY INSTALLED VERSIONS -- storage and comparison states');
console.log('='.repeat(70));

// V1: set stores a real patch identity, keyed by product.
{
  const store = memoryStore(null);
  const api = build(store);
  api.setInstalled('obs-studio', { v: '32.1.2', b: '', d: '2026-04-21', u: '/updates/obs/32-1-2/' });
  const saved = JSON.parse(store.read());
  check('V1 set stores version, build, date and url under the product id',
    saved['obs-studio'].v === '32.1.2' && saved['obs-studio'].u === '/updates/obs/32-1-2/',
    store.read());
}

// V2: reload -- a fresh reader over the same storage returns the same entry.
{
  const store = memoryStore('{"obs-studio":{"v":"32.1.2","b":"","d":"2026-04-21","u":"/updates/obs/32-1-2/"}}');
  check('V2 the entry survives a reload', build(store).readInstalled()['obs-studio'].v === '32.1.2');
}

// V3: change replaces rather than accumulating.
{
  const store = memoryStore('{"obs-studio":{"v":"32.1.2","b":"","d":"2026-04-21","u":"/updates/obs/32-1-2/"}}');
  const api = build(store);
  api.setInstalled('obs-studio', { v: '32.2.2', b: '', d: '2026-08-14', u: '/updates/obs/32-2-2/' });
  const saved = JSON.parse(store.read());
  check('V3 change replaces the entry, one per product',
    Object.keys(saved).length === 1 && saved['obs-studio'].v === '32.2.2', store.read());
}

// V4: clear removes only that product.
{
  const store = memoryStore('{"obs-studio":{"v":"32.1.2","u":"/a/"},"blackmagic-davinci":{"v":"21","u":"/b/"}}');
  const api = build(store);
  api.setInstalled('obs-studio', null);
  const saved = JSON.parse(store.read());
  check('V4 clear removes only that product',
    !saved['obs-studio'] && saved['blackmagic-davinci'].v === '21', store.read());
}

// V5: malformed storage fails safe.
{
  for (const bad of ['[]', 'null', 'not json', '{"obs-studio":"just a string"}', '{"obs-studio":{}}',
    '{"BAD ID":{"v":"1"}}', '{"obs-studio":{"v":""}}']) {
    const api = build(memoryStore(bad));
    let threw = false;
    let keys = ['x'];
    try { keys = Object.keys(api.readInstalled()); } catch (e) { threw = true; }
    check(`V5 malformed storage ${JSON.stringify(bad).slice(0, 26)} reads empty, no throw`,
      !threw && keys.length === 0, JSON.stringify(keys));
  }
}

// V6: a non-site url is refused, so a stored entry can never become a live off-site link.
{
  const api = build(memoryStore('{"obs-studio":{"v":"32.1.2","u":"javascript:alert(1)"}}'));
  check('V6 a non-path url is dropped', api.readInstalled()['obs-studio'].u === '');
}

// V7: storage unavailable degrades quietly.
{
  const api = build(hostileStore());
  let threw = false;
  try { api.readInstalled(); api.setInstalled('obs-studio', { v: '1', u: '/a/' }); } catch (e) { threw = true; }
  check('V7 unavailable storage fails soft', !threw);
}

// --- the comparison states -------------------------------------------------------------------

const state = (entry, product) => build(memoryStore(null)).installedState(entry, product).state;

check('C1 the newest tracked release is CURRENT',
  state({ v: '32.2.2', b: '', d: '2026-08-14' }, OBS) === 'CURRENT');

check('C2 an older release of the same product is UPDATE AVAILABLE',
  state({ v: '32.1.2', b: '', d: '2026-04-21' }, OBS) === 'UPDATE AVAILABLE');

// The whole point of the conservative states: a stable reader must not be told that a newer BETA
// is an update to install.
check('C3 a stable reader whose ONLY newer record is a BETA gets NEWER TRACKED VERSION EXISTS',
  state({ v: '21', b: '', d: '2026-04-14' }, BETA_TOP) === 'NEWER TRACKED VERSION EXISTS');

check('C4 a beta reader is never told UPDATE AVAILABLE',
  state({ v: '21 Public Beta 1', b: '', d: '2026-04-14' }, DAVINCI) === 'NEWER TRACKED VERSION EXISTS');

// A newer BETA must not veto a newer STABLE. Vetoing made the states non-monotonic: 20.3.3 read
// UPDATE AVAILABLE while 20.3.2, further behind, did not, because a beta sat between them.
check('C4b a stable reader with a newer STABLE above a beta still gets UPDATE AVAILABLE',
  state({ v: '20.2', b: '', d: '2026-01-10' }, DAVINCI) === 'UPDATE AVAILABLE');

{
  const target = build(memoryStore(null))
    .installedState({ v: '20.2', b: '', d: '2026-01-10' }, DAVINCI).latest;
  check('C4c and the release it points at is the STABLE one, never the beta',
    target && target[0] === '21.1' && target[4] === 0, JSON.stringify(target));
}

// Being further behind must never produce a WEAKER statement than being closer.
{
  const order = ['21 Public Beta 1', '21', '20.2'];
  const states = order.map((v) => state({ v, b: '', d: '2020-01-01' }, DAVINCI));
  check('C4d the states are monotonic as the reader falls further behind',
    states[1] === 'UPDATE AVAILABLE' && states[2] === 'UPDATE AVAILABLE', JSON.stringify(states));
}

// Build-aware identity: 26H1 is a different servicing train, not an update to 25H2.
check('C5 a newer build of the SAME Windows version is UPDATE AVAILABLE',
  state({ v: '25H2', b: '26200.9445', d: '2026-09-08' }, WINDOWS) === 'UPDATE AVAILABLE');

check('C6 a newer Windows TRAIN is only NEWER TRACKED VERSION EXISTS',
  state({ v: '25H2', b: '26200.9550', d: '2026-09-14' }, WINDOWS) === 'NEWER TRACKED VERSION EXISTS');

check('C7 the build distinguishes two records that share a version',
  state({ v: '25H2', b: '26200.9550', d: '2026-09-14' }, WINDOWS) !== 'CURRENT'
  && state({ v: '26H1', b: '28000.2956', d: '2026-09-22' }, WINDOWS) === 'CURRENT');

// A record that has gone from the tracked window, but should have been in it.
check('C8 an identity missing from the covered window is NO LONGER TRACKED',
  state({ v: '32.9.9', b: '', d: '2026-06-01' }, OBS) === 'INSTALLED VERSION NO LONGER TRACKED');

// Older than everything published -- simply older, not vanished. Saying it vanished would be a
// confident wrong answer.
check('C9 an identity older than the window is not called untracked',
  state({ v: '27.0.0', b: '', d: '2020-01-01' }, OBS) === 'NEWER TRACKED VERSION EXISTS');

check('C10 a product with a single tracked record is CURRENT, never an error',
  state({ v: '1.0', b: '', d: '2026-01-01' },
    { id: 'solo', recs: [['1.0', '', '2026-01-01', '/x/', 0]], more: 0 }) === 'CURRENT');

// No records at all: there is nothing to compare against, so there is nothing to claim. The
// first version of this check ended in `|| true`, which made it assert nothing.
check('C11 a product with no tracked records yields no state at all',
  state({ v: '1.0', b: '', d: '2026-01-01' }, { id: 'empty', recs: [], more: 0 }) === '');

{
  let threw = false;
  try { build(memoryStore(null)).installedState(null, OBS); } catch (e) { threw = true; }
  check('C12 no installed entry yields no state and does not throw', !threw);
}

// --- the upgrade path ---------------------------------------------------------------------------
//
// The chronology comes from the SAME call that produced the state and the target, so these check
// what that one authority hands the renderer.

const plan = (entry, product) => build(memoryStore(null)).installedState(entry, product);
const versionsIn = (steps) => (steps || []).map((step) => step.rec[0]);

check('P1 the newest release offers no path at all',
  plan({ v: '32.2.2', b: '', d: '2026-08-14' }, OBS).pathKind === '');

{
  const info = plan({ v: '32.2.1', b: '', d: '2026-07-24' }, OBS);
  check('P2 one release behind gives a one-step path that ends at the target',
    info.pathKind === 'upgrade' && info.path.length === 1
    && info.path[0].rec === info.latest, JSON.stringify(versionsIn(info.path)));
}

{
  const info = plan({ v: '32.1.2', b: '', d: '2026-04-21' }, OBS);
  check('P3 several releases behind gives the chain in publication order, oldest first',
    info.pathKind === 'upgrade'
    && JSON.stringify(versionsIn(info.path)) === JSON.stringify(['32.2.1', '32.2.2'])
    && info.path[info.path.length - 1].rec === info.latest, JSON.stringify(versionsIn(info.path)));
}

{
  // 20.2 -> 21.1 with `21 Public Beta 1` sitting in between.
  const info = plan({ v: '20.2', b: '', d: '2026-01-10' }, DAVINCI);
  check('P4 a preview release between two stables is not a step on the path',
    info.pathKind === 'upgrade'
    && versionsIn(info.path).every((v) => !String(v).toLowerCase().includes('beta'))
    && info.omittedBetas === 1, JSON.stringify(versionsIn(info.path)) + ' betas=' + info.omittedBetas);
}

check('P5 when only a preview is newer there is no upgrade path, only newer releases',
  plan({ v: '21', b: '', d: '2026-04-14' }, BETA_TOP).pathKind === 'newer');

{
  const info = plan({ v: '25H2', b: '26200.9445', d: '2026-09-08' }, WINDOWS);
  check('P6 a Windows upgrade path holds only the reader OWN servicing line',
    info.pathKind === 'upgrade'
    && versionsIn(info.path).every((v) => v === '25H2')
    && info.path[info.path.length - 1].rec === info.latest,
    JSON.stringify(versionsIn(info.path)));
  check('P7 and the target it ends at is labelled as the line, not as the newest tracked',
    info.latestScope === 'line' && info.latest[0] === '25H2');
}

{
  // Newest build of 25H2. What is left is 26H1 -- a different line, not a next step.
  const info = plan({ v: '25H2', b: '26200.9550', d: '2026-09-22' }, WINDOWS);
  check('P8 releases on other servicing lines are never rendered as one sequence',
    info.pathKind === 'newer' && info.parallel === true && info.path.length === 0
    && info.lines.length > 0, JSON.stringify({ kind: info.pathKind, path: info.path.length }));
  check('P9 they are grouped by line, and each group holds exactly one line',
    info.lines.every((line) => line.steps.every((step) => step.rec[0] === line.version)),
    JSON.stringify(info.lines.map((l) => l.version)));
}

check('P10 the parallel-line rule fires for interleaved lines',
  build(memoryStore(null)).parallelLines(WINDOWS.recs) === true);
// The discriminator cannot be build-awareness: PowerPoint has builds too and IS a sequence.
check('P11 and leaves a build-aware product whose versions run in order alone',
  build(memoryStore(null)).parallelLines(POWERPOINT.recs) === false);
check('P12 a build-aware sequential product still gets a real upgrade path',
  JSON.stringify(versionsIn(plan({ v: '2607', b: '19029.20136', d: '2026-07-15' }, POWERPOINT).path))
  === JSON.stringify(['2608', '2609']));

{
  const info = plan({ v: '30.0.0', b: '', d: '2020-01-01' }, OBS);
  check('P13 a release older than the listed window says so rather than claiming a full run',
    info.pathKind === 'newer' && info.truncatedStart === true);
}
check('P14 a release that vanished from the window offers no path to walk',
  plan({ v: '32.9.9', b: '', d: '2026-06-01' }, OBS).pathKind === '');

{
  // Two releases published the same day. The repo records no order between them, so neither may be
  // presented as the step after the other.
  const TIED = { id: 'tied', recs: [
    ['3.2', '', '2026-05-01', '/x/3-2/', 0],
    ['3.1', '', '2026-05-01', '/x/3-1/', 0],
    ['3.0', '', '2026-04-01', '/x/3-0/', 0],
  ], more: 0 };
  const info = plan({ v: '3.0', b: '', d: '2026-04-01' }, TIED);
  check('P15 a tied publication date inside the path is flagged, not smoothed over',
    info.path.length === 2 && info.path[0].tied === false && info.path[1].tied === true,
    JSON.stringify(info.path.map((s) => [s.rec[0], s.tied])));
  // The collision that actually happens: the reader sits in the tied group themselves.
  const mine = plan({ v: '3.1', b: '', d: '2026-05-01' }, TIED);
  check('P16 and the tie between the reader and the first step is flagged too',
    mine.path.length === 1 && mine.path[0].tied === true,
    JSON.stringify(mine.path.map((s) => [s.rec[0], s.tied])));
}

{
  const many = [];
  for (let i = 20; i >= 0; i -= 1) {
    const day = String(i + 1).padStart(2, '0');
    many.push([`1.${i}`, '', `2026-03-${day}`, `/m/1-${i}/`, 0]);
  }
  const BIG = { id: 'big', recs: many, more: 7 };
  const api = build(memoryStore(null));
  const info = api.installedState({ v: '1.0', b: '', d: '2026-03-01' }, BIG);
  check('P17 a long run is bounded and says how many it did not show',
    info.path.length === api.PATH_LIMIT && info.hidden === 20 - api.PATH_LIMIT,
    `shown=${info.path.length} hidden=${info.hidden}`);
  check('P18 the releases it keeps are the ones nearest the target',
    info.path[info.path.length - 1].rec === info.latest,
    JSON.stringify(versionsIn(info.path)));
}

{
  const info = plan({ v: '32.1.2', b: '', d: '2026-04-21' }, OBS);
  check('P19 the reader own release is never a step on their own path',
    !info.path.some((step) => step.rec[0] === '32.1.2'));
  check('P20 every step is the payload record itself, so no field is re-derived',
    info.path.every((step) => OBS.recs.indexOf(step.rec) >= 0));
}

console.log();
console.log('='.repeat(70));
console.log(`Results: ${pass}/${pass + fail} passed, ${fail} failed`);
console.log('='.repeat(70));
process.exit(fail ? 1 : 0);
