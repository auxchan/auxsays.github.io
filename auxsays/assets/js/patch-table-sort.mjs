// patch-table-sort.mjs
// Client-side sorting for the product-history patch tables (Recent + each archived year).
// Progressive enhancement only: the server renders every table newest-first and every record
// link is a normal crawlable anchor, so the page is fully usable with this module disabled.
//
// The runtime sorts EXACTLY the values the server emitted as row data-* attributes
// (data-date / data-version / data-verdict-rank / data-reports / data-evidence-rank). It never
// reinterprets verdict text, never creates/fetches/reveals links, and never turns a row into a
// fake interactive element. The pure comparators below are exported for the node test; the
// verdict/evidence rank maps are the canonical reference that the Liquid emitter mirrors.

const _collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

// Natural version order: numeric-aware collation (1.9 < 1.10, 26.9 < 26.10, zero-padded
// segments, 23H2 < 24H2), with a deterministic lexical tiebreak so it is total and stable.
export function compareVersion(a, b) {
  a = String(a == null ? '' : a);
  b = String(b == null ? '' : b);
  const c = _collator.compare(a, b);
  return c !== 0 ? c : (a < b ? -1 : a > b ? 1 : 0);
}

// NO VERDICT VOCABULARY HERE, deliberately (AUX-008). This module used to carry VERDICT_ORDER and
// verdictRank(): a third copy of the risk order, in a browser module, classifying verdict TEXT by
// substring. It was unreachable at runtime -- the Verdict column is declared
// `data-sort-key="verdict-rank" data-sort-type="num"` and the comparator reads the server-emitted
// data-verdict-rank -- so the only caller was its own unit test, while the copy was free to
// disagree with the authority. It already did: it listed bare 'SAFE ENOUGH', which the Python
// vocabulary did not contain at all.
//
// The order now lives in one server-side authority, mirrored for the templates and pinned by
// its own regression suite. The rank arrives here as a number, already decided.

// evidenceRank() was removed here: it had no runtime caller (the Evidence column sorts on a
// server-emitted numeric attribute) and it published the exact tier thresholds in a browser
// module. The thresholds live server-side with their own regression suite.

function numCompare(a, b) {
  const x = parseFloat(a);
  const y = parseFloat(b);
  return (Number.isFinite(x) ? x : -Infinity) - (Number.isFinite(y) ? y : -Infinity);
}

function toCamel(key) {
  return key.replace(/-([a-z])/g, (_m, c) => c.toUpperCase());
}

// Row comparator over the emitted data-* keys, with a deterministic tiebreak
// (newest date, then natural version) so ordering is total regardless of the active column.
export function rowComparator(key, type, dir) {
  const sign = dir === 'desc' ? -1 : 1;
  const camel = toCamel(key);
  return (ra, rb) => {
    const va = ra.dataset[camel] == null ? '' : ra.dataset[camel];
    const vb = rb.dataset[camel] == null ? '' : rb.dataset[camel];
    let r;
    if (type === 'version') r = compareVersion(va, vb);
    else if (type === 'num') r = numCompare(va, vb);
    else if (type === 'text') r = _collator.compare(String(va), String(vb)); // Product: natural text
    else r = va < vb ? -1 : va > vb ? 1 : 0; // date: ISO strings sort lexically == chronologically
    if (r !== 0) return r * sign;
    const da = ra.dataset.date || '';
    const db = rb.dataset.date || '';
    if (da !== db) return da < db ? 1 : -1; // newest first
    return compareVersion(ra.dataset.version || '', rb.dataset.version || '');
  };
}

export function initPatchTables(root) {
  const scope = root || document;
  const tables = Array.from(scope.querySelectorAll('[data-patch-table]'));
  if (!tables.length) return;

  // Sortable columns are derived from the ACTUAL header buttons, so the same module drives both
  // the product table and the vendor table (which adds a Product column) with no hardcoded list.
  const columns = Array.from(tables[0].querySelectorAll('thead [data-sort-key]')).map((b) => ({
    key: b.dataset.sortKey,
    type: b.dataset.sortType || 'text',
    label: (b.textContent || '').trim(),
  }));
  if (!columns.length) return;

  const state = { key: 'date', dir: 'desc' }; // matches the server-rendered newest-first order
  let mobileSelect = null;
  let mobileDirBtn = null;

  const sortAll = () => {
    const col = columns.find((c) => c.key === state.key) || columns[0];
    const cmp = rowComparator(col.key, col.type, state.dir);
    tables.forEach((table) => {
      const tbody = table.tBodies[0];
      if (tbody) {
        const rows = Array.from(tbody.rows).sort(cmp);
        const frag = document.createDocumentFragment();
        rows.forEach((r) => frag.appendChild(r));
        tbody.appendChild(frag);
      }
      Array.from(table.querySelectorAll('thead th')).forEach((th) => {
        const btn = th.querySelector('[data-sort-key]');
        if (!btn) { th.removeAttribute('aria-sort'); return; }
        th.setAttribute('aria-sort', btn.dataset.sortKey === state.key
          ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none');
      });
    });
    if (mobileSelect) mobileSelect.value = state.key;
    if (mobileDirBtn) {
      mobileDirBtn.dataset.dir = state.dir;
      mobileDirBtn.setAttribute('aria-label', 'Sort direction: ' + (state.dir === 'asc' ? 'ascending' : 'descending'));
    }
  };

  const setSort = (key, explicitDir) => {
    if (explicitDir) { state.key = key; state.dir = explicitDir; }
    else if (state.key === key) { state.dir = state.dir === 'asc' ? 'desc' : 'asc'; }
    else { state.key = key; state.dir = 'asc'; }
    sortAll();
  };

  // Desktop: every table shares the same header keys, so any header sorts all tables.
  tables.forEach((table) => {
    Array.from(table.querySelectorAll('thead [data-sort-key]')).forEach((btn) => {
      btn.addEventListener('click', () => setSort(btn.dataset.sortKey));
    });
  });

  // Mobile: one compact "Sort by" control that drives the SAME sort function (no separate logic).
  const firstHistory = scope.querySelector('.patch-history');
  if (firstHistory) {
    const bar = document.createElement('div');
    bar.className = 'patch-sort-mobile';
    const lab = document.createElement('label');
    lab.className = 'patch-sort-mobile__label';
    lab.append('Sort by ');
    mobileSelect = document.createElement('select');
    mobileSelect.className = 'patch-sort-mobile__select';
    columns.forEach((c) => {
      const o = document.createElement('option');
      o.value = c.key; o.textContent = c.label;
      mobileSelect.appendChild(o);
    });
    lab.appendChild(mobileSelect);
    mobileDirBtn = document.createElement('button');
    mobileDirBtn.type = 'button';
    mobileDirBtn.className = 'patch-sort-mobile__dir';
    mobileDirBtn.dataset.dir = state.dir;
    mobileSelect.addEventListener('change', () => setSort(mobileSelect.value, state.dir));
    mobileDirBtn.addEventListener('click', () => setSort(state.key, state.dir === 'asc' ? 'desc' : 'asc'));
    bar.appendChild(lab);
    bar.appendChild(mobileDirBtn);
    const title = firstHistory.querySelector('.patch-group-title');
    if (title && title.nextSibling) firstHistory.insertBefore(bar, title.nextSibling);
    else firstHistory.appendChild(bar);
  }

  sortAll(); // establish initial aria-sort state (date, descending)
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initPatchTables());
  } else {
    initPatchTables();
  }
}
