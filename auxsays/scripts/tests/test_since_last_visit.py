#!/usr/bin/env python3
"""My Patch Stack "Since your last visit" (R3-RET): what a returning reader is told changed.

WHAT THIS COVERS. The block is filled in the browser from two things only: the payload my-stack.md
builds and a snapshot THIS browser stored on its last visit (`auxsays.stackVisits.v1`). This suite
renders the shipped page with the Liquid gem and runs the shipped JavaScript under node, unchanged:

  [L] the payload names each product's Atom feed by its front matter (never a built path) and the
      page carries a hidden block with the feed of every product; without feed pages, no feed links.
  [N] no storage, a throwing accessor and malformed values mean no block and no error; a first visit
      shows nothing and stores a snapshot; a reload inside the same visit keeps the same baseline.
  [V] a second visit lists the records new since the baseline and the verdicts that changed, by
      identity (patch-page path), never by array position; every verdict it prints is the one the
      authority gives that record, i.e. the text its own patch page prints; a record re-entering the
      bounded window from below and a product watched since are not announced; stored text is escaped.
  [F] the block links each watched product's feed and the feed of every product.
  [H] the homepage findings section links the feed of every product (only where a feed page exists)
      and My Patch Stack.
  [X] nothing in the feature sends anything: no fetch, beacon, cookie or analytics call.

Deterministic and offline. Reads the repo; writes only inside a temp dir. Needs ruby + liquid and node.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_since_last_visit.py
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_patch_stack_dashboard as stack  # noqa: E402  (its render harness and the authority's verdicts)

AUX = stack.AUX
JS = stack.JS
HOME_FINDINGS = AUX / "_includes" / "home-findings.html"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


def feed_pages() -> list[dict]:
    """Every shipped feed page, as `site.pages` presents it: its front matter plus its url."""
    out = []
    for path in sorted((AUX / "updates").rglob("feed.xml")):
        fm = stack.front_matter(path)
        if fm.get("layout") != "aux-patch-atom":
            continue
        fm["url"] = fm.get("permalink", "")
        out.append(fm)
    return out


def render(records: list[dict], products: list[dict], extra_pages: list[dict]) -> str:
    ok, page = stack.render_page(records + extra_pages, products)
    return page if ok else ""


def payload_of(page: str) -> list[dict]:
    m = re.search(r'<script type="application/json" id="patch-stack-data">(.*?)</script>', page, re.S)
    try:
        return json.loads(m.group(1)) if m else []
    except json.JSONDecodeError:
        return []


_LIQUID_RB = """
require 'json'
require 'liquid'
payload = JSON.parse(File.read(ARGV[0]))
print Liquid::Template.parse(payload['template']).render!('site' => payload['site'])
"""


def render_snippet(template: str, site: dict) -> str:
    ruby = shutil.which("ruby")
    if not ruby:
        return "<<no ruby>>"
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "r.rb"
        script.write_text(_LIQUID_RB, encoding="utf-8")
        data = Path(td) / "p.json"
        data.write_text(json.dumps({"template": template, "site": site}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(data)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
    return proc.stdout if proc.returncode == 0 else "<<render failed: " + (proc.stderr or "")[-300:] + ">>"


# ---------------------------------------------------------------- the shipped JavaScript, under node

_PROBE = r"""
const PRODUCT_ID_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;
class CustomEvent { constructor(t, o) { this.type = t; this.detail = o && o.detail; } }
const CODE = __CODE__;
const SCENARIOS = __SCENARIOS__;
const realNow = Date.now;
let carried = {};
const results = SCENARIOS.map((cfg) => {
  const store = cfg.store === 'carry' ? Object.assign({}, carried) : Object.assign({}, cfg.store || {});
  let win;
  if (cfg.mode === 'absent') win = {};
  else if (cfg.mode === 'throws') win = { localStorage: {
    getItem() { throw new Error('SecurityError'); }, setItem() { throw new Error('QuotaExceededError'); } } };
  else win = { localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } } };
  const panel = { hidden: true, dataset: { feedAll: cfg.feedAll || '' } };
  const body = { innerHTML: '' };
  const doc = {
    querySelector: (sel) => (sel === '[data-stack-since]' ? panel : (sel === '[data-stack-since-body]' ? body : null)),
    dispatchEvent() {},
  };
  Date.now = () => cfg.now;
  let error = '';
  try {
    const api = (new Function('window', 'document', 'PRODUCT_ID_RE', 'CustomEvent',
      CODE + '\nreturn { renderSince };'))(win, doc, PRODUCT_ID_RE, CustomEvent);
    api.renderSince(cfg.watched);
  } catch (e) {
    error = String((e && e.stack) || e);
  }
  Date.now = realNow;
  carried = store;
  return { hidden: panel.hidden, html: body.innerHTML, store, error };
});
console.log(JSON.stringify(results));
"""


def shipped_code() -> tuple[str, str]:
    """(code the probe evaluates, the since region alone) -- slices of auxsays.js as shipped."""
    src = JS.read_text(encoding="utf-8")
    installed_block = src[src.index("const INSTALLED_KEY"):src.index("const paintInstalledControls")]
    stack_block = src[src.index("    const esc = (value)"):src.index("    const renderStack = () => {")]
    wiring = src[src.index("    // Since your last visit (defined"):src.index(
        "    document.addEventListener('click', (event) => {\n      const setter")]
    region = src[src.index("// SINCE YOUR LAST VISIT (R3-RET) -- BEGIN"):src.index("// SINCE YOUR LAST VISIT (R3-RET) -- END")]
    return installed_block + "\n" + stack_block + "\n" + wiring, region + wiring


def run_probe(scenarios: list[dict]) -> list[dict] | None:
    node = shutil.which("node")
    if not node:
        return None
    code, _region = shipped_code()
    probe = _PROBE.replace("__CODE__", json.dumps(code)).replace("__SCENARIOS__", json.dumps(scenarios))
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "since_probe.js"
        path.write_text(probe, encoding="utf-8")
        res = subprocess.run([node, str(path)], capture_output=True, text=True, encoding="utf-8",
                             cwd=str(stack._REPO), timeout=120)
    if res.returncode != 0:
        raise AssertionError("since probe failed: " + (res.stderr or "")[-600:])
    return json.loads(res.stdout.strip().splitlines()[-1])


ROW_RE = re.compile(r'<li class="patch-stack-since__item" data-since-kind="(new|changed)" data-since-href="([^"]*)">(.*?)</li>', re.S)
WORD_RE = re.compile(r'<span class="patch-verdict patch-verdict--rank-?\d+">(.*?)</span>(?: <span class="patch-verdict-scope">(.*?)</span>)?', re.S)


def rows_of(markup: str) -> list[tuple[str, str, str]]:
    return ROW_RE.findall(markup or "")


def snapshot(entries: list[dict]) -> dict:
    """What the page stores for these products, restated here from the payload."""
    return {e["id"]: [[r[3], r[5], r[12], r[2]] for r in e.get("recs", [])[:24]] for e in entries}


def store_with(t: float, s: dict, prev: dict | None = None) -> dict:
    return {"auxsays.stackVisits.v1": json.dumps({"prev": prev, "cur": {"t": t, "s": s}})}


# ---------------------------------------------------------------- the suite

def run() -> int:
    print("=" * 78)
    print("MY PATCH STACK -- since your last visit")
    print("=" * 78)

    records = stack.load_records()
    products = stack.load_products()
    feeds = feed_pages()
    by_url = {r["url"]: r for r in records}

    print("\n[L] the rendered page")
    page = render(records, products, feeds)
    entries = payload_of(page)
    check("L1 the shipped page renders with its payload", bool(entries), page[:200])
    product_feed = {f["feed_product_id"]: f["url"] for f in feeds if f.get("feed_product_id")}
    wrong = [(e["id"], e.get("feed"), product_feed.get(e["id"], "")) for e in entries
             if e.get("feed", None) != product_feed.get(e["id"], "")]
    check("L2 every product's feed is its feed page's url, and '' where it has none", entries and not wrong,
          str(wrong[:3]))
    check("L3 most tracked products have a feed to subscribe to",
          sum(1 for e in entries if e.get("feed")) >= max(1, len(entries) // 2),
          f"{sum(1 for e in entries if e.get('feed'))} of {len(entries)}")
    all_feed = next((f["url"] for f in feeds if f.get("feed_scope") == "all"), "")
    sec = re.search(r'<section class="panel patch-stack-since" data-stack-since data-feed-all="([^"]*)"'
                    r' aria-labelledby="stack-since-title" hidden>', page)
    check("L4 the block ships hidden, carrying the feed of every product", bool(sec) and bool(all_feed)
          and sec.group(1) == all_feed, (sec.group(1) if sec else "no block") + " vs " + all_feed)
    order = [page.find(s) for s in ("data-stack-since ", "data-stack-empty", "data-stack-body")]
    check("L5 it sits above the empty state and the product grids", -1 not in order and order == sorted(order),
          str(order))
    bare = payload_of(render(records, products, []))
    bare_sec = re.search(r'data-stack-since data-feed-all="([^"]*)"', render(records, products, []))
    check("L6 without feed pages there is no feed to link: no constructed path",
          bare and all(e.get("feed") == "" for e in bare) and bare_sec and bare_sec.group(1) == "",
          str([e.get("feed") for e in bare[:3]]))

    # Two products with enough history to change, from the real payload.
    usable = [e for e in entries if len(e.get("recs", [])) >= 4]
    a = usable[0] if usable else {"id": "none", "recs": []}
    b = usable[1] if len(usable) > 1 else {"id": "none2", "recs": []}
    # A product whose two oldest window records have different dates, for the window-churn case.
    churn = next((e for e in usable if e["recs"][-1][2] < e["recs"][-2][2]), a)
    now = 1_790_000_000_000
    day = 86_400_000

    base_a = snapshot([a])[a["id"]][2:]                      # the two newest records were not there yet
    base_b = snapshot([b])[b["id"]]
    flip_from = "SAFE ENOUGH" if b["recs"][1][5] != "SAFE ENOUGH" else "WAIT"
    base_b[1] = [base_b[1][0], flip_from, "", base_b[1][3]]  # this browser was shown another verdict
    second = {a["id"]: base_a, b["id"]: base_b}
    churn_base = {churn["id"]: snapshot([churn])[churn["id"]][:-1]}
    hostile = {a["id"]: [[r[0], '<img src=x onerror=alert(1)>', '', r[3]] if i == 3 else r
                         for i, r in enumerate(snapshot([a])[a["id"]])]}

    scenarios = [
        {"name": "absent", "mode": "absent", "now": now, "watched": [a, b], "feedAll": all_feed},
        {"name": "throws", "mode": "throws", "now": now, "watched": [a, b], "feedAll": all_feed},
        {"name": "first", "mode": "ok", "store": {}, "now": now, "watched": [a, b], "feedAll": all_feed},
        {"name": "reload", "mode": "ok", "store": "carry", "now": now + 10 * 60_000, "watched": [a, b], "feedAll": all_feed},
        {"name": "second", "mode": "ok", "store": store_with(now - 2 * day, second), "now": now,
         "watched": [a, b], "feedAll": all_feed},
        {"name": "same-visit", "mode": "ok", "store": "carry", "now": now + 5 * 60_000, "watched": [a, b], "feedAll": all_feed},
        {"name": "nothing", "mode": "ok", "store": store_with(now - 2 * day, snapshot([a, b])), "now": now,
         "watched": [a, b], "feedAll": all_feed},
        {"name": "corrupt-json", "mode": "ok", "store": {"auxsays.stackVisits.v1": "{not json"}, "now": now, "watched": [a]},
        {"name": "corrupt-array", "mode": "ok", "store": {"auxsays.stackVisits.v1": "[]"}, "now": now, "watched": [a]},
        {"name": "corrupt-shape", "mode": "ok", "store": {"auxsays.stackVisits.v1": json.dumps(
            {"cur": {"t": "yesterday", "s": {a["id"]: "x"}}, "prev": {"t": 5, "s": []}})}, "now": now, "watched": [a]},
        {"name": "churn", "mode": "ok", "store": store_with(now - 2 * day, churn_base), "now": now, "watched": [churn]},
        {"name": "watched-since", "mode": "ok", "store": store_with(now - 2 * day, {a["id"]: snapshot([a])[a["id"]]}),
         "now": now, "watched": [a, b], "feedAll": all_feed},
        {"name": "hostile", "mode": "ok", "store": store_with(now - 2 * day, hostile), "now": now, "watched": [a]},
        {"name": "unwatched", "mode": "ok", "store": store_with(now - 2 * day, second), "now": now, "watched": []},
    ]
    print("\n[N] storage: absent, throwing, malformed, first visit, reload")
    results = run_probe(scenarios)
    check("N0 a JavaScript runtime runs the shipped code", results is not None, "node not on PATH")
    res = {s["name"]: r for s, r in zip(scenarios, results or [])}
    empty = {"hidden": False, "html": "x", "store": {}, "error": "not run"}

    def r(name: str) -> dict:
        return res.get(name, empty)

    check("N1 no storage at all: no block, no error", r("absent")["hidden"] and r("absent")["html"] == ""
          and not r("absent")["error"], r("absent")["error"][:200])
    check("N2 a throwing accessor (read and write): no block, no error", r("throws")["hidden"]
          and r("throws")["html"] == "" and not r("throws")["error"], r("throws")["error"][:200])
    check("N3 malformed values (bad JSON, an array, wrong shapes): no block, no error",
          all(r(n)["hidden"] and not r(n)["error"] for n in ("corrupt-json", "corrupt-array", "corrupt-shape")),
          str([r(n)["error"][:80] for n in ("corrupt-json", "corrupt-array", "corrupt-shape")]))
    first_store = json.loads(r("first")["store"].get("auxsays.stackVisits.v1", "{}") or "{}")
    check("N4 a first visit shows nothing and stores this visit's snapshot",
          r("first")["hidden"] and not r("first")["error"] and first_store.get("prev") is None
          and (first_store.get("cur") or {}).get("t") == now
          and (first_store.get("cur") or {}).get("s") == snapshot([a, b]), json.dumps(first_store)[:200])
    check("N5 a reload inside the same visit still has no earlier visit to compare with",
          r("reload")["hidden"] and not r("reload")["error"])
    check("N6 a list with nothing watched shows no block", r("unwatched")["hidden"] and not r("unwatched")["error"])

    print("\n[V] a second visit")
    sec_rows = rows_of(r("second")["html"])
    new_hrefs = {h for k, h, _ in sec_rows if k == "new"}
    changed = [(h, inner) for k, h, inner in sec_rows if k == "changed"]
    check("V1 a second visit shows the block", not r("second")["hidden"] and not r("second")["error"],
          r("second")["error"][:200])
    check("V2 the records absent from the baseline are listed as new, and only those",
          new_hrefs == {a["recs"][0][3], a["recs"][1][3]}, str(sorted(new_hrefs)))
    check("V3 the record whose verdict this browser saw differently is listed as changed, with what it saw",
          [h for h, _ in changed] == [b["recs"][1][3]] and changed and f"was {flip_from}" in changed[0][1],
          str(changed)[:300])
    mismatch = []
    for kind, href, inner in sec_rows:
        m = WORD_RE.search(inner)
        rec = by_url.get(href)
        if not m or rec is None:
            mismatch.append((href, "unparsed" if not m else "no record"))
            continue
        verdict, qualifier = stack.expected_phrase(rec)
        shown = (html.unescape(m.group(1)), html.unescape(m.group(2) or ""))
        if shown != (verdict, qualifier or ""):
            mismatch.append((href, shown, (verdict, qualifier)))
    check("V4 every verdict the block prints is the authority's for that record (its page's verdict)",
          sec_rows and not mismatch, str(mismatch[:3]))
    check("V5 the summary counts what is listed", "2 new patch records and 1 verdict change across 2 of your products"
          in r("second")["html"], r("second")["html"][:300])
    check("V6 a reload in the same visit keeps the baseline: the same changes, not cleared",
          rows_of(r("same-visit")["html"]) == sec_rows and not r("same-visit")["hidden"])
    check("V7 nothing changed: the block says so, with no rows",
          not r("nothing")["hidden"] and "data-since-nothing" in r("nothing")["html"]
          and not rows_of(r("nothing")["html"]))
    check("V8 a record re-entering the window from below is not announced as new",
          churn["recs"][-1][3] not in {h for _, h, _ in rows_of(r("churn")["html"])}, churn["id"])
    check("V9 a product watched since the last visit is not announced at all",
          not any(h.startswith("/") and by_url.get(h, {}).get("product_id") == b["id"]
                  for _, h, _ in rows_of(r("watched-since")["html"])), b["id"])
    check("V10 stored text is escaped, never markup", "<img" not in r("hostile")["html"]
          and "&lt;img" in r("hostile")["html"], r("hostile")["html"][:300])
    when = re.search(r'Your last visit in this browser: <time datetime="([^"]+)">', r("second")["html"])
    last_day = datetime.fromtimestamp((now - 2 * day) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    check("V11 the block says when the last visit was", bool(when) and when.group(1).startswith(last_day),
          when.group(1) if when else "")

    print("\n[F] the way back without a visit")
    feed_links = re.findall(r'<a href="([^"]*)" data-since-feed>', r("second")["html"])
    want = [e["feed"] for e in (a, b) if e.get("feed")]
    check("F1 each watched product's own feed is linked", sorted(feed_links) == sorted(want), str(feed_links))
    check("F2 the feed of every product is linked", f'<a href="{all_feed}" data-since-feed-all>' in r("second")["html"])
    check("F3 the feeds are offered even when nothing changed", "data-since-feed" in r("nothing")["html"])

    print("\n[H] the homepage")
    tpl = HOME_FINDINGS.read_text(encoding="utf-8")
    start = tpl.index("{%- comment -%} R3-RET: the way back.")
    end = tpl.index("</section>", start)
    snippet = tpl[start:end]
    with_feed = render_snippet(snippet, {"pages": feeds})
    without = render_snippet(snippet, {"pages": []})
    check("H1 the findings section links the feed of every product",
          f'<a href="{all_feed}">Atom feed of every product</a>' in with_feed, with_feed[:300])
    check("H2 and My Patch Stack", '<a href="/updates/my-stack/">My Patch Stack</a>' in with_feed, with_feed[:300])
    check("H3 without a feed page it links no feed, and still links My Patch Stack",
          "feed" not in without.lower().replace("findings-follow", "") and "My Patch Stack" in without, without[:300])

    print("\n[X] nothing is sent")
    _code, region = shipped_code()
    banned = [t for t in ("fetch(", "XMLHttpRequest", "sendBeacon", "document.cookie", "gtag", "dataLayer", "navigator.")
              if t in region]
    check("X1 the feature makes no request and touches no cookie or analytics", not banned, str(banned))

    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
