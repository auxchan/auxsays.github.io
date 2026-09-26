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
    return { readInstalled, writeInstalled, setInstalled, installedState };`);
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
const WINDOWS = {
  id: 'microsoft-windows-11',
  recs: [
    ['26H1', '28000.2956', '2026-09-22', '/updates/w/26h1-28000-2956/', 0],
    ['25H2', '26200.9550', '2026-09-14', '/updates/w/25h2-26200-9550/', 0],
    ['25H2', '26200.9445', '2026-09-08', '/updates/w/25h2-26200-9445/', 0],
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

console.log();
console.log('='.repeat(70));
console.log(`Results: ${pass}/${pass + fail} passed, ${fail} failed`);
console.log('='.repeat(70));
process.exit(fail ? 1 : 0);
