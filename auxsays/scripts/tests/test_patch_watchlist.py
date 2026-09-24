#!/usr/bin/env python3
"""My Patch Watchlist: the surfaces, the accessible state, and the semantic collision it resolved.

WHAT THIS COVERS. The watchlist is local-first, so its storage behaviour is proven by
`auxsays/assets/js/patch-watchlist.test.mjs`, which executes the shipped helpers out of
auxsays.js against a stubbed window (13 checks). That suite is Node, and this job installs no Node
toolchain, so it is classified with the other .mjs suites. What runs HERE is everything a Python +
Liquid job can prove for real:

  [R] the patch page really renders a watch control bound to `page.product_id` -- a live Liquid
      render of the shipped layout, not a look at the template text, so the binding is proven.
  [M] the product page, the feed controls, the two distinct empty states and the discovery-card
      watch affordance exist with the attributes they need, parsed as HTML rather than grepped.
  [A] every control carries an accessible state and a product-bearing name.
  [C] the collision is gone: the site's coverage TIER no longer calls itself "Watchlist", so one
      word no longer means both the site's classification and the visitor's own selection.

Deterministic and offline. Reads the repo; writes only inside a temp dir.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_watchlist.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from html.parser import HTMLParser
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
LAYOUTS = _REPO / "auxsays" / "_layouts"
ASSETS = _REPO / "auxsays" / "assets"

UPDATE_LAYOUT = LAYOUTS / "aux-update.html"
FEED_LAYOUT = LAYOUTS / "aux-updates.html"
PRODUCT_LAYOUT = LAYOUTS / "aux-patch-product.html"
HOME_LAYOUT = LAYOUTS / "aux-home.html"
JS = ASSETS / "js" / "auxsays.js"
CSS = ASSETS / "css" / "auxsays-custom.css"

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


class TagCollector(HTMLParser):
    """Collects (tag, attrs-dict) for every element, so assertions read attributes, not substrings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, {k: (v or "") for k, v in attrs}))


def parse(path: Path) -> list[tuple[str, dict]]:
    collector = TagCollector()
    collector.feed(path.read_text(encoding="utf-8"))
    return collector.elements


def with_attr(elements, attr: str):
    return [(tag, a) for tag, a in elements if attr in a]


# ---------------------------------------------------------------- [R] a real render

_RENDER_RB = """
require 'liquid'
require 'json'

module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def markdownify(i) = i.to_s
end
Liquid::Template.register_filter(Shims)

payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
print tpl.render!('site' => payload['site'], 'page' => payload['page'], 'content' => '')
"""


def render_patch_page(product_id: str, product_name: str) -> tuple[bool, str]:
    """Render the SHIPPED patch layout so the product binding is proven, not assumed."""
    src = UPDATE_LAYOUT.read_text(encoding="utf-8").split("---", 2)[-1]
    src = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", src, flags=re.S)
    ruby = shutil.which("ruby")
    if not ruby:
        return False, "<<RENDER FAILED: ruby is not on PATH>>"
    page = {
        "product_id": product_id,
        "update_product": product_name,
        "update_version": "31.0.4",
        "update_published_at": "2026-06-27T00:00:00Z",
        "update_report_count": 1,
        "evidence_state": "pilot_sample",
        "update_decision_label": "TEST FIRST",
        "quick_verdict": "TEST FIRST: OBS Studio 31.0.4 has 1 user report found.",
    }
    site = {"time": "2026-09-23T00:00:00Z",
            "data": {"patch_products": [{"id": product_id, "product_name": product_name}],
                     "evidence_method_health": {}}}
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload = Path(td) / "p.json"
        payload.write_text(json.dumps({"template": src, "site": site, "page": page}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
    if proc.returncode != 0:
        return True, f"<<RENDER FAILED: {(proc.stderr or '')[-300:]}>>"
    return True, proc.stdout


def check_render() -> None:
    liquid_ok, html = render_patch_page("obs-studio", "OBS Studio")
    check("R1 the liquid gem is available, so this render is real", liquid_ok,
          "install liquid 4.0.4; CI does this explicitly and must not skip it silently")
    collector = TagCollector()
    collector.feed(html)
    controls = with_attr(collector.elements, "data-watch-product")
    check("R2 the patch page renders a watch control", len(controls) == 1,
          f"found {len(controls)}; render head: {html[:160]!r}")
    if not controls:
        return
    attrs = controls[0][1]
    # The whole point: a patch page watches the PRODUCT, not this one historical build.
    check("R3 it is bound to the canonical product_id, not the patch version",
          attrs.get("data-watch-product") == "obs-studio", repr(attrs.get("data-watch-product")))
    check("R4 it starts unpressed", attrs.get("aria-pressed") == "false", repr(attrs.get("aria-pressed")))
    check("R5 its accessible name carries the product",
          "OBS Studio" in attrs.get("aria-label", ""), repr(attrs.get("aria-label")))
    check("R6 it is a real button, so it is keyboard operable without extra wiring",
          controls[0][0] == "button" and attrs.get("type") == "button", repr(controls[0][0]))


# ---------------------------------------------------------------- [M] the other surfaces

def check_surfaces() -> None:
    product = parse(PRODUCT_LAYOUT)
    product_controls = with_attr(product, "data-watch-product")
    check("M1 the product page carries a watch control", len(product_controls) == 1,
          f"found {len(product_controls)}")
    if product_controls:
        attrs = product_controls[0][1]
        check("M2 the product control binds page.product_id",
              "page.product_id" in attrs.get("data-watch-product", ""), repr(attrs.get("data-watch-product")))
        check("M3 the product control declares an accessible pressed state",
              attrs.get("aria-pressed") == "false")

    feed = parse(FEED_LAYOUT)
    chips = with_attr(feed, "data-watchlist-filter")
    check("M4 the feed has a My Watchlist filter chip", len(chips) == 1, f"found {len(chips)}")
    if chips:
        check("M5 the filter chip is a toggle with a pressed state",
              chips[0][1].get("aria-pressed") == "false", repr(chips[0][1].get("aria-pressed")))
    check("M6 the feed shows a live watch count", len(with_attr(feed, "data-watchlist-count")) >= 1)
    check("M7 the feed offers a way to clear the list",
          any(a.get("data-watchlist-action") == "clear" for _t, a in feed))

    # Two silences, two answers: "you have chosen nothing" and "nothing is happening to yours".
    empties = {a.get("data-watchlist-empty") for _t, a in feed if "data-watchlist-empty" in a}
    check("M8 the two empty states are distinct", empties == {"none-watched", "no-matches"},
          repr(sorted(e for e in empties if e)))

    tags = with_attr(feed, "data-watch-product")
    check("M9 discovery cards expose product-level watch controls", len(tags) >= 1, f"found {len(tags)}")
    if tags:
        check("M10 the discovery control binds a product id, not a company or a slug",
              "product.id" in tags[0][1].get("data-watch-product", ""),
              repr(tags[0][1].get("data-watch-product")))

    home = parse(HOME_LAYOUT)
    signals = [a for _t, a in home if "data-home-patch-signal" in a]
    check("M11 homepage signals carry a product id to match against",
          bool(signals) and all("data-product-id" in a for a in signals), f"{len(signals)} signals")
    check("M12 the homepage has a watchlist note element, hidden by default",
          any("data-home-watchlist-note" in a and "hidden" in a for _t, a in home))


# ---------------------------------------------------------------- [A] accessibility + [C] collision

def check_accessibility_and_collision() -> None:
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    check("A1 every watch control is given an accessible pressed state in JS",
          "setAttribute('aria-pressed'" in js)
    check("A2 the accessible name is rewritten with the product name",
          "aria-label" in js and "Watching ${name}" in js)
    check("A3 focus is visible on both watch affordances",
          ".patch-watch-toggle:focus-visible" in css and ".patch-watch-tag:focus-visible" in css)
    # Colour alone must not carry the state.
    check("A4 the watched state is shown by a mark, not only by colour",
          ".patch-watch-toggle.is-watching .patch-watch-toggle__mark::after" in css)
    check("A5 the control is usable on small screens",
          "@media (max-width: 640px)" in css and ".patch-watch-toggle { width: 100%" in css)

    # THE COLLISION. `edge` is a coverage tier; it used to display as "Watchlist", which is now the
    # visitor's own list. One word cannot mean both.
    ui_files = [FEED_LAYOUT, JS, CSS, LAYOUTS / "aux-patch-company.html"]
    offenders = []
    for path in ui_files:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"watchlist", text, flags=re.I):
            line = text[:match.start()].count("\n") + 1
            context = text.splitlines()[line - 1]
            # The visitor-facing feature is allowed to say watchlist; the coverage tier is not.
            if re.search(r"data-priority=\"watchlist\"|normalized_priority = 'watchlist'|"
                         r"priority-label--watchlist|lane === 'edge'\) return 'watchlist'", context):
                offenders.append(f"{path.name}:{line}")
    check("C1 the coverage tier no longer calls itself Watchlist", not offenders, "; ".join(offenders))

    check("C2 the tier has a truthful name instead",
          "data-priority=\"emerging\"" in FEED_LAYOUT.read_text(encoding="utf-8")
          and "return 'emerging'" in js)
    check("C3 the tier rename is complete across JS ranking, layout and CSS",
          "emerging: 1" in js and "patch-priority-label--emerging" in css)

    # Storage contract, declared where the feature lives.
    check("K1 the storage key is versioned",
          "auxsays.patchWatchlist.v1" in js)
    check("K2 only product ids are stored -- no records, no URLs",
          "JSON.stringify(Array.from(ids).sort())" in js)
    check("K3 reads are guarded against unavailable storage",
          js.count("catch (error)") >= 3)

    # ---- the three defects a browser found that attribute-presence checks could not ----

    # G1: the gate must sit in the PATCH-card predicate. It was first written into the company
    # DISCOVERY predicate, where `productId` is not even in scope: the filter silently did nothing
    # and the discovery grid threw. Both functions end in a near-identical return, which is exactly
    # why "the code contains the term" was not good enough.
    def body(name: str) -> str:
        start = js.find(f"const {name} = (card, query) => {{")
        if start < 0:
            return ""
        end = js.find("\n    };", start)
        return js[start:end] if end > start else js[start:]

    update_body = body("matchesUpdateFilters")
    company_body = body("matchesCompanyFilters")
    check("G1 the watchlist gate is in the patch-card predicate",
          bool(update_body) and "watchlistOnly" in update_body, "matchesUpdateFilters has no gate")
    check("G2 the discovery-card predicate is NOT gated by the watchlist",
          bool(company_body) and "watchlistOnly" not in company_body,
          "company cards are the only place to ADD products; filtering them empties the grid")

    # G3: an author `display` beats the UA sheet's `[hidden] { display: none }`. Both new
    # components ship hidden AND declare display, so both rendered for every visitor until an
    # explicit override was added.
    hidden_components = []
    for path in (FEED_LAYOUT, HOME_LAYOUT):
        for _tag, attrs in parse(path):
            if "hidden" not in attrs:
                continue
            for cls in attrs.get("class", "").split():
                if cls.startswith("patch-watchlist") or cls.startswith("home-watchlist"):
                    hidden_components.append(cls)
    unguarded = []
    for cls in sorted(set(hidden_components)):
        declares_display = re.search(rf"\.{re.escape(cls)}\b[^{{}}]*\{{[^}}]*\bdisplay\s*:", css)
        has_override = re.search(rf"\.{re.escape(cls)}\[hidden\]", css)
        if declares_display and not has_override:
            unguarded.append(cls)
    check(f"G3 hidden-by-default components stay hidden ({len(set(hidden_components))} checked)",
          not unguarded, f"declare display with no [hidden] override: {unguarded}")

    # G4: a pre-existing rule drops empty spans inside the discovery tags, which silently killed
    # the watched/unwatched mark there and left the state carried by colour alone.
    # Presence is not enough -- it has to WIN. The first attempt at this fix shipped a rule that
    # existed and still lost: `.patch-source-tags span:empty` is (0,2,1) because `:empty` counts as
    # a class, so a (0,2,0) selector loses even with !important on both sides.
    def specificity(selector: str) -> tuple[int, int, int]:
        sel = selector.strip()
        ids = len(re.findall(r"#[\w-]+", sel))
        classes = len(re.findall(r"\.[\w-]+", sel)) + len(re.findall(r"(?<!:):(?!:)[\w-]+", sel))
        # Strip every id/class/pseudo/attribute token FIRST; whatever bare words remain are element
        # types. Counting them in place matches fragments inside class names and inflates the type
        # column, which silently made this comparison always true.
        rest = re.sub(r"[#.][\w-]+|::?[\w-]+(?:\([^)]*\))?|\[[^\]]*\]", " ", sel)
        types = len(re.findall(r"\b[a-z][\w-]*\b", rest))
        return (ids, classes, types)

    # Comments must go first, or prose inside them is counted as type selectors and every rule
    # "wins" -- which made the first version of this check pass for the losing selector too.
    bare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = [(sel.split("}")[-1].strip(), decl)
             for sel, decl in re.findall(r"([^{}]*)\{([^}]*)\}", bare)]
    killer = next((s for s, d in rules
                   if ".patch-source-tags" in s and ":empty" in s and re.search(r"display\s*:\s*none", d)), "")
    winner = next((s for s, d in rules
                   if "patch-watch-tag__mark" in s and re.search(r"display\s*:\s*block", d)), "")
    if not killer:
        check("G4 the discovery state mark is not suppressed", True)
    else:
        killer_spec = max(specificity(p) for p in killer.split(",") if ":empty" in p)
        winner_spec = max((specificity(p) for p in winner.split(",") if "__mark" in p), default=(0, 0, 0))
        check("G4 the state mark's rule OUT-SPECIFIES the empty-span rule",
              winner_spec > killer_spec,
              f"mark {winner_spec} vs killer {killer_spec} -- a rule that merely exists still loses")

    # G5: the stylesheet still parses. Writing the G4 comment above spliced prose OUTSIDE a comment
    # -- the same shape as the `--radius-xl: 28px@font-face {` damage this repo has seen before, and
    # the kind of thing a browser silently recovers from while the next rule disappears.
    check("G5 stylesheet comments are balanced",
          css.count("/*") == css.count("*/"), f"{css.count('/*')} opens vs {css.count('*/')} closes")
    stray = [ln.strip() for ln in bare.splitlines()
             if ln.strip() and not re.search(r"[{};@]", ln) and not re.match(r"^[.#\w\[:>,&*-]", ln.strip())]
    check("G5 no content sits outside a rule or a comment", not stray, "; ".join(stray[:3]))


def run() -> int:
    print("=" * 78)
    print("MY PATCH WATCHLIST -- surfaces, accessible state, semantic collision")
    print("=" * 78)
    print("\n[R] a real Liquid render of the shipped patch layout")
    check_render()
    print("\n[M] product page, feed controls, empty states, discovery cards, homepage")
    check_surfaces()
    print("\n[A]/[C]/[K] accessibility, the resolved collision, the storage contract")
    check_accessibility_and_collision()
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
