/**
 * My Patch Watchlist: the storage contract.
 *
 * Executes the SHIPPED helpers out of assets/js/auxsays.js rather than a copy of them. The block
 * is sliced from the real file and run against a stubbed window, so a change to the production
 * source changes what this tests. A copy would pass forever while the page broke.
 *
 * Node, like the other .mjs suites here, and classified the same way in the governed manifest:
 * this job installs no Node toolchain, and wiring one for a watchlist was out of scope.
 *
 * Run: node auxsays/assets/js/patch-watchlist.test.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, 'auxsays.js'), 'utf8');

// Slice the shipped block: from the storage key through the end of setWatched.
const start = source.indexOf("const WATCHLIST_KEY");
const endMarker = "const watchToggles =";
const end = source.indexOf(endMarker);
if (start < 0 || end < 0 || end <= start) {
  console.error("FAIL: could not locate the watchlist block in auxsays.js -- the source moved.");
  process.exit(2);
}
const block = source.slice(start, end);

let pass = 0;
let fail = 0;
const check = (label, condition, detail = "") => {
  if (condition) { pass += 1; console.log(`  PASS  ${label}`); }
  else { fail += 1; console.log(`  FAIL  ${label}${detail ? `  --  ${detail}` : ""}`); }
};

/** Build the helpers over a fresh fake localStorage. */
const build = (backing) => {
  const store = backing;
  const fakeWindow = { localStorage: store };
  // eslint-disable-next-line no-new-func
  const factory = new Function("window", `${block}\n return { readWatchlist, writeWatchlist, setWatched, isWatched, watchlistCount };`);
  return factory(fakeWindow);
};

const memoryStore = (initial) => {
  let value = initial;
  return {
    getItem: () => value,
    setItem: (_k, v) => { value = v; },
    read: () => value,
  };
};

const hostileStore = () => ({
  getItem: () => { throw new Error("storage disabled"); },
  setItem: () => { throw new Error("storage disabled"); },
});

console.log("=".repeat(70));
console.log("MY PATCH WATCHLIST -- storage contract");
console.log("=".repeat(70));

// S1: a watch stores the canonical product id and nothing else.
{
  const store = memoryStore(null);
  const api = build(store);
  api.setWatched("obs-studio", true);
  check("S1 watch stores the canonical product_id", store.read() === '["obs-studio"]', store.read());
}

// S2: unwatch removes it.
{
  const store = memoryStore('["obs-studio","blackmagic-davinci"]');
  const api = build(store);
  api.setWatched("obs-studio", false);
  check("S2 unwatch removes only that id", store.read() === '["blackmagic-davinci"]', store.read());
}

// S3: watching twice cannot duplicate storage.
{
  const store = memoryStore(null);
  const api = build(store);
  api.setWatched("obs-studio", true);
  api.setWatched("obs-studio", true);
  check("S3 a repeated watch does not duplicate", store.read() === '["obs-studio"]', store.read());
}

// S4: a list that already contains duplicates is de-duplicated on read.
{
  const api = build(memoryStore('["obs-studio","obs-studio","OBS-Studio"]'));
  check("S4 duplicates in stored data collapse on read", api.readWatchlist().size === 1);
}

// S5: malformed storage fails safe rather than throwing.
{
  for (const bad of ['{"not":"an array"}', "not json at all", "[1,2,3]", "null", "[]"]) {
    const api = build(memoryStore(bad));
    let threw = false;
    let size = -1;
    try { size = api.readWatchlist().size; } catch (error) { threw = true; }
    check(`S5 malformed storage ${JSON.stringify(bad).slice(0, 22)} reads as empty, no throw`, !threw && size === 0);
  }
}

// S6: entries that are not product-id shaped are ignored.
{
  const api = build(memoryStore('["obs-studio","../../etc/passwd","<script>","",  "OK-Fine"]'));
  const ids = api.readWatchlist();
  check("S6 non-slug entries are ignored", ids.size === 2 && ids.has("obs-studio") && ids.has("ok-fine"),
    JSON.stringify(Array.from(ids)));
}

// S7: storage being unavailable degrades quietly instead of breaking the page.
{
  const api = build(hostileStore());
  let threw = false;
  let size = -1;
  try {
    size = api.readWatchlist().size;
    api.setWatched("obs-studio", true);
  } catch (error) { threw = true; }
  check("S7 unavailable storage fails soft", !threw && size === 0);
}

// S8: a malformed id is refused rather than written.
{
  const store = memoryStore(null);
  const api = build(store);
  const accepted = api.setWatched("not a product id!", true);
  check("S8 an invalid id is never written", accepted === false && store.read() === null, String(store.read()));
}

// S9: ids are stored case-normalised, so one product cannot appear twice.
{
  const store = memoryStore(null);
  const api = build(store);
  api.setWatched("OBS-Studio", true);
  api.setWatched("obs-studio", true);
  check("S9 ids are case-normalised to one entry", store.read() === '["obs-studio"]', store.read());
}

console.log();
console.log("=".repeat(70));
console.log(`Results: ${pass}/${pass + fail} passed, ${fail} failed`);
console.log("=".repeat(70));
process.exit(fail ? 1 : 0);
