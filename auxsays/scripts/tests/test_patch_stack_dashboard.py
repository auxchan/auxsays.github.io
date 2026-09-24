#!/usr/bin/env python3
"""My Patch Stack: the pre-rendered payload, the record it picks, and the page skeleton.

WHAT THIS COVERS. The dashboard is a static page plus a client renderer. This suite renders the
SHIPPED page with Liquid and checks the half that Jekyll owns:

  [P] the payload is valid JSON, bounded, and carries exactly the fields the cards show -- not a
      dump of 1,200 records.
  [R] the record chosen for each product is the newest dated non-archived one, computed
      independently here from the corpus, and its verdict matches the shared derivation in
      `_includes/patch-table-row.html` (including the official-only-at-zero-reports override).
  [S] the skeleton: empty state with a route out of it, both sections, the cautious default
      wording, heading hierarchy, and the `[hidden]` display guards that a previous sprint learned
      to need.
  [E] the entry points from the Patch Feed and the homepage.

The client rendering (cards appear, unwatch removes one immediately) is proven on the deployed
site during delivery; the watchlist storage contract it reuses is proven by
`auxsays/assets/js/patch-watchlist.test.mjs`.

Deterministic and offline. Reads the repo; writes only inside a temp dir.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_stack_dashboard.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
AUX = _REPO / "auxsays"
PAGE = AUX / "updates" / "my-stack.md"
FEED = AUX / "_layouts" / "aux-updates.html"
HOME = AUX / "_layouts" / "aux-home.html"
JS = AUX / "assets" / "js" / "auxsays.js"
CSS = AUX / "assets" / "css" / "auxsays-custom.css"
GENERATED = AUX / "updates" / "generated"
PRODUCTS = AUX / "_data" / "patch_products.yml"

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


# ---------------------------------------------------------------- rendering the shipped page

_RENDER_RB = """
require 'liquid'
require 'json'

module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\\A/}, "")
  def jsonify(i) = JSON.generate(i)
end
Liquid::Template.register_filter(Shims)

payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
print tpl.render!('site' => payload['site'])
"""


def front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    body = text.split("---", 2)[1]
    data: dict = {}
    for line in body.splitlines():
        m = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if m:
            data[m.group(1)] = m.group(2).strip().strip("'\"")
    return data


def load_records() -> list[dict]:
    """Every generated record, as the page's `site.pages | where: update_entry` would see them."""
    import yaml
    out = []
    for path in sorted(GENERATED.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        try:
            data = yaml.safe_load(text.split("---", 2)[1])
        except Exception:                                    # noqa: BLE001 - a bad record is not this suite's subject
            continue
        if not isinstance(data, dict) or not data.get("update_entry"):
            continue
        data["url"] = str(data.get("permalink") or "")
        out.append(data)
    return out


def load_products() -> list[dict]:
    import yaml
    return yaml.safe_load(PRODUCTS.read_text(encoding="utf-8")) or []


def render_page(records: list[dict], products: list[dict]) -> tuple[bool, str]:
    src = PAGE.read_text(encoding="utf-8").split("---", 2)[-1]
    # The monitoring status arrives from a Jekyll include, whose parameterised syntax core Liquid
    # cannot parse. Stripping it leaves `mon` empty here; that field is the include's to own.
    src = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", src, flags=re.S)
    ruby = shutil.which("ruby")
    if not ruby:
        return False, "<<RENDER FAILED: ruby is not on PATH>>"
    site = {"data": {"patch_products": products}, "pages": records}
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload = Path(td) / "p.json"
        payload.write_text(json.dumps({"template": src, "site": site}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
    if proc.returncode != 0:
        return True, f"<<RENDER FAILED: {(proc.stderr or '')[-400:]}>>"
    return True, proc.stdout


# ---------------------------------------------------------------- the independent expectation

def ordered_records(records: list[dict]) -> list[dict]:
    """The page's own input order: sorted by publish date, then reversed -- newest first.

    Mirrored exactly rather than re-derived with `max`, because two Windows records share a publish
    date and `max` breaks that tie by iteration order while the page breaks it by sort order. A tie
    has no right answer; what matters is that the test measures the rule the page states.
    """
    return list(reversed(sorted(records, key=lambda r: str(r.get("update_published_at") or ""))))


def expected_choices(ordered: list[dict], product_id: str) -> list[dict]:
    """EVERY record that satisfies "newest dated, non-archived" for this product.

    Usually one. Two Windows records share a publish date, and the rule does not break that tie --
    Ruby's sort is unstable where Python's is stable, so demanding one specific winner would be
    testing an accident rather than the rule. Either is a correct answer; a third record is not.
    """
    candidates = [r for r in ordered
                  if r.get("product_id") == product_id
                  and r.get("update_published_at")
                  and str(r.get("update_status") or "") != "archived"]
    if not candidates:
        return []
    newest = max(str(r.get("update_published_at") or "") for r in candidates)
    return [r for r in candidates if str(r.get("update_published_at") or "") == newest]


def expected_verdict(rec: dict) -> str:
    """The shared derivation from `_includes/patch-table-row.html`, in the same order."""
    label = str(rec.get("update_decision_label") or "").strip()
    summary = str(rec.get("update_consensus_summary") or "")
    quick = str(rec.get("quick_verdict") or "")
    if not label and ":" in summary:
        label = summary.split(":", 1)[0].strip()
    elif not label and ":" in quick:
        label = quick.split(":", 1)[0].strip()
    elif not label:
        label = "INSUFFICIENT DATA"
    count = int(rec.get("update_report_count") or 0)
    official_only = (rec.get("evidence_state") == "official_only"
                     or rec.get("evidence_state_label") == "Official source only")
    if official_only and count == 0:
        label = "INSUFFICIENT DATA"
    return label


class TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, {k: (v or "") for k, v in attrs}))


def parse_html(text: str) -> list[tuple[str, dict]]:
    c = TagCollector()
    c.feed(text)
    return c.elements


# ---------------------------------------------------------------- the suite

def run() -> int:
    print("=" * 78)
    print("MY PATCH STACK -- payload, record selection, skeleton")
    print("=" * 78)

    fm = front_matter(PAGE)
    print("\n[P] the pre-rendered payload")
    check("P0 the route is /updates/my-stack/", fm.get("permalink") == "/updates/my-stack/",
          repr(fm.get("permalink")))

    records = load_records()
    products = load_products()
    liquid_ok, html = render_page(records, products)
    check("P1 the liquid gem is available, so the page is really rendered", liquid_ok,
          "install liquid 4.0.4; CI does this explicitly and must not skip it silently")

    payload_match = re.search(r'<script type="application/json" id="patch-stack-data">(.*?)</script>',
                              html, re.S)
    check("P2 the page embeds a payload script", bool(payload_match), html[:200])
    entries: list[dict] = []
    if payload_match:
        try:
            entries = json.loads(payload_match.group(1))
        except json.JSONDecodeError as exc:
            check("P3 the payload is valid JSON", False, str(exc))
        else:
            check("P3 the payload is valid JSON", True)
    check("P4 the payload has one entry per tracked product",
          len(entries) == len(products), f"{len(entries)} entries vs {len(products)} products")

    allowed = {"id", "name", "hist", "href", "ver", "date", "verdict", "rank", "ev", "n",
               "checked", "mon", "oa", "os"}
    extra = sorted({k for e in entries for k in e} - allowed)
    check("P5 the payload carries only dashboard fields, not whole records", not extra, str(extra))

    id_re = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
    bad_ids = [e.get("id") for e in entries if not id_re.match(str(e.get("id") or ""))]
    check("P6 every payload id satisfies the watchlist id contract", not bad_ids, str(bad_ids[:4]))

    with_records = [e for e in entries if e.get("href")]
    check("P7 products with records carry a patch to show", len(with_records) >= 5,
          f"{len(with_records)} entries with a record")

    print("\n[R] the record it picked, and the verdict it shows")
    by_id = {e["id"]: e for e in entries if e.get("id")}
    ordered = ordered_records(records)
    wrong_record, wrong_verdict = [], []
    for product in products:
        pid = str(product.get("id") or product.get("product_id") or "")
        wants = expected_choices(ordered, pid)
        got = by_id.get(pid)
        if got is None:
            continue
        if not wants:
            if got.get("href"):
                wrong_record.append(f"{pid}: showed a record where none qualifies")
            continue
        match = next((w for w in wants if str(w.get("url") or "") == str(got.get("href") or "")), None)
        if match is None:
            wrong_record.append(f"{pid}: {got.get('href')} not among {[w.get('url') for w in wants]}")
            continue
        if str(got.get("verdict") or "") != expected_verdict(match):
            wrong_verdict.append(f"{pid}: {got.get('verdict')!r} != {expected_verdict(match)!r}")
    check(f"R1 each product shows its newest dated non-archived record ({len(products)} products)",
          not wrong_record, "; ".join(wrong_record[:3]))
    check("R2 the verdict matches the shared patch-table derivation",
          not wrong_verdict, "; ".join(wrong_verdict[:3]))

    archived_shown = [e["id"] for e in with_records
                      if any(r.get("permalink") == e["href"] and r.get("update_status") == "archived"
                             for r in records)]
    check("R3 no card points at an archived record", not archived_shown, str(archived_shown[:3]))

    print("\n[S] the page skeleton")
    elements = parse_html(html)
    attrs_present = {a for _t, at in elements for a in at}
    for needed in ("data-stack-empty", "data-stack-body", "data-stack-attention-grid",
                   "data-stack-all-grid", "data-stack-strip", "data-stack-chooser-tags"):
        check(f"S1 the page provides {needed}", needed in attrs_present)

    check("S2 the empty state routes the reader to the Patch Feed",
          any(t == "a" and a.get("href", "").endswith("/updates/") for t, a in elements))
    flat = re.sub(r"\s+", " ", html)
    check("S3 the cautious default wording is present",
          "Nothing in your watched stack currently requires elevated attention." in flat)

    headings = [t for t, _a in elements if t in ("h1", "h2", "h3")]
    check("S4 heading hierarchy starts at h1 and does not skip to h3",
          headings and headings[0] == "h1" and "h2" in headings,
          str(headings[:6]))

    # The lesson from the watchlist sprint: a component that ships `hidden` AND declares its own
    # display beats the UA sheet and renders for everyone.
    css = CSS.read_text(encoding="utf-8")
    hidden_classes = set()
    for _t, a in elements:
        if "hidden" in a:
            hidden_classes.update(c for c in a.get("class", "").split() if c.startswith("patch-stack"))
    unguarded = [c for c in sorted(hidden_classes)
                 if re.search(rf"\.{re.escape(c)}\b[^{{}}]*\{{[^}}]*\bdisplay\s*:", css)
                 and not re.search(rf"\.{re.escape(c)}\[hidden\]", css)]
    check(f"S5 hidden-by-default sections stay hidden ({len(hidden_classes)} checked)",
          not unguarded, f"declare display with no [hidden] override: {unguarded}")

    print("\n[E] the entry points and the shared watchlist API")
    feed = FEED.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    check("E1 the Patch Feed offers a route into My Patch Stack", "/updates/my-stack/" in feed)
    check("E2 the feed route is a link, not another filter chip",
          'class="patch-stack-link"' in feed and 'data-priority="my-stack"' not in feed)
    check("E3 the homepage offers one compact entry point", "/updates/my-stack/" in home)

    js = JS.read_text(encoding="utf-8")
    stack_block = js.split("patch-stack-data", 1)[1].split("Patch Feed controls", 1)[0]
    check("E4 unwatch reuses the shared watch control contract",
          'data-watch-product="${esc(entry.id)}"' in js)
    check("E5 the dashboard reuses the watchlist reader rather than re-validating ids",
          "readWatchlist()" in stack_block)
    check("E6 unknown stored ids simply have no card",
          ".filter(Boolean)" in stack_block)

    # The change event is dispatched SYNCHRONOUSLY. A listener that repaints by calling the
    # broadcasting helper re-enters itself until the stack overflows -- which is exactly what the
    # first version of this dashboard did on every unwatch.
    listener = stack_block.split("addEventListener('auxsays:watchlist-change'", 1)
    check("E7 the dashboard repaints without re-broadcasting the change event",
          len(listener) == 2 and "syncWatchControls()" not in listener[1],
          "the listener calls the broadcasting helper and will recurse")

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
