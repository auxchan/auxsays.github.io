#!/usr/bin/env python3
"""The paged Patch Feed (G36-02): its byte budget, its crawlable catalogue, and the deploy gate.

WHY. /updates/ printed every tracked patch as a full card on one page: 1,535 cards and 4,295,549
bytes on 2026-11-10. Googlebot reads the first 2 MB of an HTML response, so 819 of the feed's patch
links and its whole archive were past what it reads. The feed is now paged: updates/index.md sets the
page size, _plugins/patch_feed_pages.rb adds /updates/page/2/ onward, _layouts/aux-updates.html
slices one ordered list and links every page with plain anchors, and assets/js/auxsays.js brings the
other pages' cards in when a visitor searches, filters or sorts. scripts/ci/verify_feed_discovery.py
refuses a deploy whose feed is over budget or whose patch pages a crawler cannot reach.

  [V] the gate, run as a subprocess over synthetic built sites: a clean site passes, and each way the
      catalogue can be lost (over budget, unlinked, linked only through script or past 2 MB, on two
      pages, a pager link to nothing, an orphan page, an empty page, unreachable or too deep) fails
      with its own code.
  [L] the SHIPPED paging block of the layout, rendered with the Liquid gem: for every page size and
      record mix the pages partition the ordered list exactly (no record lost, none twice, order kept),
      and the archive section is hidden exactly where a page holds no archived record.
  [G] the SHIPPED generator, run under stub Jekyll classes: it makes exactly the pages the layout
      expects, from the same predicate, with self permalinks and distinct titles, and refuses a
      missing or non-positive page size; it ranks the records newest first with ties broken by
      permalink, whatever order the site lists them in; and it stamps every page with a digest of
      the feed's cards, which a rebuild of the same records keeps and one more record changes.
  [J] the SHIPPED catalogue functions of assets/js/auxsays.js, run under node: the pager's links give
      the pages to fetch in page order and this page's place among them (from pages 1, 2, 8, 10 and
      16); from every page the catalogue is held in the build's one order (so a stable sort breaks
      ties the same way from page 8 as from page 1), each patch is held once with this page's own
      card winning, a page from another feed is fetched once more past the cache and otherwise
      refused, and each outcome shows as it should ('mixed': the pager and the mixed note).
  [W] the wiring: the deploy runs the gate between the build and the upload; the generator runs
      before jekyll-sitemap; the layout lists the records in the generator's order; the pager is
      anchors and carries the feed's stamp; the loader adopts only the feed's own cards, in feed
      order, and stays on this page when the feeds differ.

Needs ruby + the liquid gem for [L] and [G] (the CI job installs it) and node for [J]; without them
those checks do not run and the governed count fails the build. Offline; writes only inside a temp dir.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_feed_discovery.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
VERIFY = _AUX / "scripts" / "ci" / "verify_feed_discovery.py"
LAYOUT = _AUX / "_layouts" / "aux-updates.html"
PLUGIN = _AUX / "_plugins" / "patch_feed_pages.rb"
FEED_INDEX = _AUX / "updates" / "index.md"
JS = _AUX / "assets" / "js" / "auxsays.js"
PAGES_YML = _REPO / ".github" / "workflows" / "pages.yml"

sys.path.insert(0, str(_AUX / "scripts"))
from ci import verify_feed_discovery as vfd  # noqa: E402

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


# ---------------------------------------------------------------- [V] the gate over synthetic sites

HEAD = '<!doctype html><html><head><title>t</title></head>'


def page(body_class: str, inner: str) -> str:
    return f'{HEAD}<body class="aux-page {body_class}">{inner}</body></html>'


def card(url: str, kind: str = "current") -> str:
    cls = "panel patch-card" + (" patch-card--archived" if kind == "archived" else "")
    return (f'<article class="{cls}" data-kind="{kind}"><a class="patch-identity" href="{url}">x</a>'
            f'<h2><a href="{url}">x</a></h2></article>')


def stamp_of(feed: list[list[str]]) -> str:
    """The feed's stamp for these pages, computed here (not with the gate's own function): the SHA-256
    of one line per card, "<page> <link>", page 1 first."""
    lines = [f"{n} {u}\n" for n, urls in enumerate(feed, start=1) for u in urls]
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def pager(n: int, current: int, build: str | None) -> str:
    items = []
    for i in range(1, n + 1):
        href = "/updates/" if i == 1 else f"/updates/page/{i}/"
        cur = ' aria-current="page"' if i == current else ""
        items.append(f'<li><a class="patch-chip" href="{href}" data-feed-page-link="{i}"{cur}>{i}</a></li>')
    stamp = "" if build is None else f' data-feed-build="{build}"'
    return f'<nav data-feed-pages data-feed-total="0"{stamp}><ol>{"".join(items)}</ol></nav>'


def build_site(root: Path, *, patches: list[str], feed: list[list[str]], hubs: dict | None = None,
               home_links: list[str] | None = None, pager_html=None, extra: dict | None = None,
               hidden: list[str] | None = None, pad: dict | None = None,
               fronts: dict[str, str] | None = None) -> Path:
    """A minimal built site: / , /updates/ (+ /updates/page/N/), hub pages and patch pages."""
    site = root / "_site"
    src = root / "src"
    shutil.rmtree(root, ignore_errors=True)
    site.mkdir(parents=True)
    (src / "updates" / "generated").mkdir(parents=True)

    def write(url: str, html: str) -> None:
        f = site / url.lstrip("/") / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html, encoding="utf-8")

    hubs = hubs if hubs is not None else {"/updates/v/p/": patches}
    links = home_links if home_links is not None else ["/updates/"] + list(hubs)
    write("/", page("aux-home", "".join(f'<a href="{u}">h</a>' for u in links)))
    for hub, urls in hubs.items():
        write(hub, page("aux-patch-product", "".join(f'<a href="{u}">r</a>' for u in urls)))
    for u in patches:
        write(u, page("aux-update", "<h1>patch</h1>"))
    n = len(feed)
    for i, urls in enumerate(feed, start=1):
        url = "/updates/" if i == 1 else f"/updates/page/{i}/"
        nav = pager_html(n, i) if pager_html else pager(n, i, stamp_of(feed))
        body = "".join(card(u) for u in urls) + (nav if n > 1 else "")
        if pad and url in pad:
            before, after = pad[url]
            body = ("x" * before) + body + ("<!--" + "y" * after + "-->")
        write(url, page("aux-updates", body))
    for url, html in (extra or {}).items():
        write(url, html)
    for i, u in enumerate(hidden or []):
        (src / "updates" / "generated" / f"h{i}.md").write_text(
            f"---\nlayout: aux-update\npermalink: {u}\nupdate_entry: true\nfeed_hidden: true\n---\n", encoding="utf-8")
    # A record whose feed_hidden is written some other way (false, a quoted "true"): the YAML literal.
    for i, (u, literal) in enumerate((fronts or {}).items()):
        (src / "updates" / "generated" / f"f{i}.md").write_text(
            f"---\nlayout: aux-update\npermalink: {u}\nupdate_entry: true\nfeed_hidden: {literal}\n---\n", encoding="utf-8")
    return site


def run_gate(site: Path) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, "-I", str(VERIFY), "--site", str(site), "--source", str(site.parent / "src")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return proc.returncode, proc.stdout + proc.stderr


def check_gate(tmp: Path) -> None:
    print("\n[V] the gate over synthetic built sites")
    P = [f"/updates/v/p/{i}/" for i in range(1, 8)]
    base = dict(patches=P, feed=[P[:3], P[3:6], P[6:]])
    good = stamp_of(base["feed"])

    rc, out = run_gate(build_site(tmp / "v1", **base))
    check("V1 a paged feed that links every patch page once, within budget, passes", rc == 0, out[-300:])
    check("V1b it reports the governed figures (pages, patch pages, linked, reached, max hops)",
          "feed pages 3;" in out and "patch pages 7;" in out and "linked by the feed 7" in out
          and "reached from / 7 within 3 hops (max 2)" in out, out[-300:])

    budget = vfd.FEED_PAGE_BUDGET_BYTES
    site = build_site(tmp / "v2", **base)
    f = site / "updates" / "page" / "2" / "index.html"
    f.write_text(f.read_text(encoding="utf-8") + "<!--" + "z" * (budget - f.stat().st_size - 7) + "-->",
                 encoding="utf-8")
    exact = f.stat().st_size
    rc_at, out_at = run_gate(site)
    f.write_text(f.read_text(encoding="utf-8") + "z", encoding="utf-8")
    rc_over, out_over = run_gate(site)
    check("V2 a feed page at exactly the budget passes", exact == budget and rc_at == 0, f"{exact} {out_at[-200:]}")
    check("V3 one byte over the budget fails BUDGET for that page",
          rc_over == 1 and f"BUDGET /updates/page/2/ is {budget + 1:,} bytes" in out_over, out_over[-300:])

    rc, out = run_gate(build_site(tmp / "v4", patches=P, feed=[P[:3], P[3:5], P[6:]]))
    check("V4 a patch page no feed page links fails COVERAGE (listed but unlinked)",
          rc == 1 and f"COVERAGE {P[5]} is listed by the feed but no feed page links it" in out, out[-300:])

    rc, out = run_gate(build_site(tmp / "v5", patches=P, feed=[P[:3], P[3:6], P[6:]],
                                  pager_html=lambda n, cur: "<nav data-feed-pages>" + "".join(
                                      f'<button data-href="/updates/page/{i}/">{i}</button>' for i in range(2, n + 1)) + "</nav>"))
    check("V5 a pager made of script-only buttons leaves its pages orphaned and their patches unlinked",
          rc == 1 and "PAGER /updates/page/2/ is built but no feed page links it" in out
          and f"COVERAGE {P[3]} is listed by the feed but no feed page links it" in out, out[-400:])

    site = build_site(tmp / "v6", patches=P, feed=[P[:3], P[3:6], P[6:]],
                      pad={"/updates/page/3/": (vfd.CRAWL_WINDOW_BYTES, 0)})
    rc, out = run_gate(site)
    check("V6 a card link past the 2 MB crawl window does not count: COVERAGE fails for it",
          rc == 1 and f"COVERAGE {P[6]} is listed by the feed but no feed page links it" in out, out[-400:])

    rc, out = run_gate(build_site(tmp / "v7", patches=P, feed=[P[:4], P[3:6], P[6:]]))
    check("V7 a patch page on two feed pages fails COVERAGE (slices overlap)",
          rc == 1 and f"COVERAGE {P[3]} is on 2 feed pages" in out, out[-300:])

    rc, out = run_gate(build_site(tmp / "v8", **base, pager_html=lambda n, cur: pager(n + 1, cur, good)))
    check("V8 a pager link to a page that was not built fails PAGER",
          rc == 1 and "PAGER /updates/ links /updates/page/4/, which is not a built page" in out, out[-300:])

    site = build_site(tmp / "v9", **base, extra={"/updates/page/9/": page("aux-updates", card(P[0]))})
    rc, out = run_gate(site)
    check("V9 a built feed page no pager links fails PAGER (orphan)",
          rc == 1 and "PAGER /updates/page/9/ is built but no feed page links it" in out, out[-300:])

    rc, out = run_gate(build_site(tmp / "v10", patches=P, feed=[P[:3], P[3:7], []]))
    check("V10 a feed page with no patch card fails COVERAGE", rc == 1 and "COVERAGE /updates/page/3/ carries no patch card" in out,
          out[-300:])

    hid = "/updates/v/p/hidden/"
    rc, out = run_gate(build_site(tmp / "v11", patches=P + [hid], feed=[P[:3], P[3:6], P[6:]],
                                  hubs={"/updates/v/p/": P + [hid]}, hidden=[hid]))
    check("V11 a feed_hidden record is not required on the feed (and still reached through its tracker)",
          rc == 0 and "feed-hidden 1;" in out, out[-300:])

    # Only `feed_hidden: true` exempts a record. The layout lists `false` and the quoted string "true"
    # (its where_exp is `!= true`), and so does the generator, so either one left unlinked is lost.
    off, quoted = "/updates/v/p/off/", "/updates/v/p/quoted/"
    rc, out = run_gate(build_site(tmp / "v11b", patches=P + [off, quoted], feed=[P[:3], P[3:6], P[6:]],
                                  hubs={"/updates/v/p/": P + [off, quoted]},
                                  fronts={off: "false", quoted: '"true"'}))
    check('V11b a record with feed_hidden: false, or the string "true", that no feed page links fails COVERAGE',
          rc == 1 and f"COVERAGE {off} is listed by the feed but no feed page links it" in out
          and f"COVERAGE {quoted} is listed by the feed but no feed page links it" in out
          and "feed-hidden 0;" in out, out[-400:])

    rc, out = run_gate(build_site(tmp / "v12", patches=P + [hid], feed=[P[:3], P[3:6], P[6:]], hidden=[hid],
                                  hubs={"/updates/v/p/": P}))
    check("V12 a patch page no crawlable link reaches fails REACH, even when the feed may omit it",
          rc == 1 and f"REACH {hid} is not reached from / within 3 crawlable hops" in out
          and "COVERAGE" not in out, out[-300:])

    deep = {"/updates/a/": ["/updates/b/"], "/updates/b/": ["/updates/c/"], "/updates/c/": [hid]}
    rc, out = run_gate(build_site(tmp / "v13", patches=P + [hid], feed=[P[:3], P[3:6], P[6:]], hidden=[hid],
                                  hubs={"/updates/v/p/": P, **deep}, home_links=["/updates/", "/updates/v/p/", "/updates/a/"]))
    check("V13 a patch page four hops from / fails REACH (the bound is three)",
          rc == 1 and f"REACH {hid} is not reached from / within 3 crawlable hops" in out, out[-300:])
    deep3 = {"/updates/a/": ["/updates/b/"], "/updates/b/": [hid]}
    rc, out = run_gate(build_site(tmp / "v14", patches=P + [hid], feed=[P[:3], P[3:6], P[6:]], hidden=[hid],
                                  hubs={"/updates/v/p/": P, **deep3}, home_links=["/updates/", "/updates/v/p/", "/updates/a/"]))
    check("V14 ... and three hops passes, reporting max 3", rc == 0 and "(max 3)" in out, out[-300:])

    site = build_site(tmp / "v15", **base)
    p1 = site / "updates" / "index.html"
    p1.write_text(p1.read_text(encoding="utf-8").replace("</body>", card("/updates/v/") + "</body>"), encoding="utf-8")
    rc, out = run_gate(site)
    check("V15 a feed card that links something other than a patch page fails COVERAGE",
          rc == 1 and "COVERAGE a feed card on /updates/ links /updates/v/, which is not a patch page" in out, out[-300:])

    empty = tmp / "v16" / "_site"
    empty.mkdir(parents=True)
    rc, out = run_gate(empty)
    check("V16 a site with no homepage or feed is unusable (exit 2), never a pass", rc == 2, out[-200:])

    one = build_site(tmp / "v17", patches=P, feed=[P])
    rc, out = run_gate(one)
    check("V17 a single-page feed (no pager) under budget is clean", rc == 0 and "feed pages 1;" in out, out[-200:])

    rc, out = run_gate(build_site(tmp / "v18", **base, pager_html=lambda n, cur: pager(n, cur, None if cur == 2 else good)))
    check("V18 a feed page whose pager carries no build stamp fails STAMP (the controls would search it alone)",
          rc == 1 and "STAMP /updates/page/2/ has no build stamp on its pager" in out
          and "STAMP /updates/ " not in out and "STAMP /updates/page/3/" not in out, out[-300:])
    rc, out = run_gate(build_site(tmp / "v19", **base, pager_html=lambda n, cur: pager(n, cur, "b0" if cur == 3 else good)))
    check("V19 feed pages stamped by two builds fail STAMP",
          rc == 1 and f"STAMP /updates/page/3/ is stamped 'b0' but /updates/ '{good}'" in out
          and "STAMP /updates/page/2/" not in out, out[-300:])
    # One stamp on every page, but not the feed's own: a build time, or the digest of the feed before
    # its last record. Either would send every search back to its own page after a rebuild.
    clock = "2026-11-10T19:26:53.123456789+0000"
    earlier = stamp_of([P[:3], P[3:6], P[6:6]])
    rc_t, out_t = run_gate(build_site(tmp / "v20", **base, pager_html=lambda n, cur: pager(n, cur, clock)))
    rc_e, out_e = run_gate(build_site(tmp / "v20e", **base, pager_html=lambda n, cur: pager(n, cur, earlier)))
    check("V20 a stamp that is not the digest of the feed's own cards fails STAMP (a build time; the feed before "
          "its last record), and the gate's digest is the one computed here",
          rc_t == 1 and f"STAMP /updates/ is stamped '{clock}' but its feed's cards give '{good}'" in out_t
          and rc_e == 1 and f"STAMP /updates/ is stamped '{earlier}' but its feed's cards give '{good}'" in out_e
          and vfd.feed_stamp(base["feed"]) == good, out_t[-300:] + out_e[-300:])


# ---------------------------------------------------------------- [L] the shipped paging block, in Liquid

_LIQUID_RB = r"""
require 'liquid'
require 'json'
# Jekyll's where_exp, as jekyll-4.4.1 implements it (filters.rb parse_condition), so the shipped
# expression is evaluated by the same grammar rather than a stand-in.
module JekyllShims
  def where_exp(input, variable, expression)
    return input unless input.respond_to?(:select)
    condition = parse_condition(expression)
    @context.stack do
      input.select do |object|
        @context[variable] = object
        condition.evaluate(@context)
      end
    end || []
  end
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  private
  def parse_condition(exp)
    parser = Liquid::Parser.new(exp)
    condition = parse_binary_comparison(parser)
    parser.consume(:end_of_string)
    condition
  end
  def parse_binary_comparison(parser)
    condition = parse_comparison(parser)
    first_condition = condition
    while (binary_operator = parser.id?("and") || parser.id?("or"))
      child_condition = parse_comparison(parser)
      condition.send(binary_operator, child_condition)
      condition = child_condition
    end
    first_condition
  end
  def parse_comparison(parser)
    left_operand = Liquid::Expression.parse(parser.expression)
    operator = parser.consume?(:comparison)
    return Liquid::Condition.new(left_operand) unless operator
    Liquid::Condition.new(left_operand, operator, Liquid::Expression.parse(parser.expression))
  end
end
Liquid::Template.register_filter(JekyllShims)
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
tpl = Liquid::Template.parse(payload["template"])
out = {}
payload["cases"].each do |name, c|
  begin
    out[name] = tpl.render!({ "cur" => c["cur"], "arc" => c["arc"], "page" => c["page"] })
  rescue => e
    out[name] = "<<ERR #{e.class}: #{e.message}>>"
  end
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""


def paging_template(layout: str) -> str:
    """The layout's own paging block and loop headers, with a probe that prints what each page holds."""
    start = layout.index("{%- assign feed_archived_listed")
    end_marker = "{%- if feed_archive_limit < 0 -%}{%- assign feed_archive_limit = 0 -%}{%- endif -%}"
    block = layout[start:layout.index(end_marker) + len(end_marker)]
    cur_loop = re.search(r"\{% for item in current_pages[^%]*%\}", layout).group(0)
    arc_loop = re.search(r"\{% for item in feed_archived_listed[^%]*%\}", layout).group(0)
    wrap = re.search(r'id="patch-archive-wrap"(\{% if [^%]*%\} hidden\{% endif %\})>', layout).group(1)
    return ("{% assign current_pages = cur %}{% assign archived_pages = arc %}" + block
            + "@@{{ feed_pages }}|" + cur_loop + "{{ item.id }},{% endfor %}|" + arc_loop
            + "{{ item.id }},{% endfor %}|" + wrap.replace(" hidden", "HIDDEN") + "@@")


def render_liquid(template: str, cases: dict) -> dict | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script, payload, out = Path(td) / "l.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_LIQUID_RB, encoding="utf-8")
        payload.write_text(json.dumps({"template": template, "cases": cases}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


def mixes() -> list[tuple[str, int, int, int, int]]:
    """(name, current, archived, archived-but-feed_hidden, page size)."""
    return [("live-shape", 1434, 101, 0, 100), ("exact-multiple", 200, 0, 0, 100), ("one-over", 100, 1, 0, 100),
            ("archive-only", 0, 7, 0, 3), ("boundary-in-archive", 5, 9, 2, 4), ("empty", 0, 0, 0, 100),
            ("size-1", 3, 2, 1, 1), ("hidden-current", 6, 3, 0, 4)]


def make_records(cur: int, arc: int, arc_hidden: int, cur_hidden: int = 0) -> tuple[list, list]:
    current = [{"id": f"c{i}", "update_status": "current"} for i in range(cur)]
    # A current record marked feed_hidden is dropped by current_pages' own where_exp in the layout,
    # which this harness does not run (it starts from current_pages), so it is not passed in.
    archived = [{"id": f"a{i}", "update_status": "archived", "feed_hidden": i < arc_hidden} for i in range(arc + arc_hidden)]
    return current, archived


def check_liquid() -> None:
    print("\n[L] the shipped paging block, rendered with Liquid")
    layout = LAYOUT.read_text(encoding="utf-8")
    try:
        template = paging_template(layout)
    except (ValueError, AttributeError) as exc:
        check("L0 the layout's paging block and loop headers are where the harness reads them", False, str(exc))
        return
    check("L0 the layout's paging block and loop headers are where the harness reads them", True)
    cases, expect = {}, {}
    for name, cur, arc, hid, size in mixes():
        current, archived = make_records(cur, arc, hid)
        listed = [r["id"] for r in current] + [r["id"] for r in archived if not r.get("feed_hidden")]
        pages = max((len(listed) + size - 1) // size, 1)
        expect[name] = (listed, pages)
        for n in range(1, pages + 2):
            cases[f"{name}#{n}"] = {"cur": current, "arc": archived, "page": {"feed_page_size": size, "feed_page": n}}
    out = render_liquid(template, cases)
    if out is None or "__error__" in out:
        check("L1 the paging block renders under the Liquid gem", False, str(out)[:300] if out else "ruby missing")
        return
    errs = {k: v for k, v in out.items() if v.startswith("<<ERR")}
    check("L1 the paging block renders under the Liquid gem", not errs, str(list(errs.items())[:2]))
    for name, cur, arc, hid, size in mixes():
        listed, pages = expect[name]
        seen, order, counts, hidden_ok, sizes = [], [], set(), True, []
        for n in range(1, pages + 1):
            m = re.search(r"@@(\d+)\|(.*?)\|(.*?)\|(.*?)@@", out[f"{name}#{n}"], re.S)
            if not m:
                hidden_ok = False
                continue
            counts.add(int(m.group(1)))
            ids = [x for x in (m.group(2) + m.group(3)).split(",") if x]
            seen.extend(ids)
            sizes.append(len(ids))
            has_arc = any(x for x in m.group(3).split(",") if x)
            hidden_ok &= (m.group(4) == "HIDDEN") == (not has_arc)
        beyond = re.search(r"@@\d+\|(.*?)\|(.*?)\|", out[f"{name}#{pages + 1}"], re.S)
        ok = (seen == listed and counts == {pages} and hidden_ok
              and all(s == size for s in sizes[:-1]) and (not listed or 1 <= sizes[-1] <= size)
              and beyond is not None and beyond.group(1) == "" and beyond.group(2) == "")
        check(f"L2 {name}: {len(listed)} listed records in {pages} page(s) of {size}: every record once, in order; "
              f"full pages but the last; archive hidden exactly where a page has none",
              ok, f"seen {len(seen)} vs {len(listed)}; counts {counts}; sizes {sizes[:5]}; hidden_ok {hidden_ok}")


# ---------------------------------------------------------------- [G] the shipped generator, stubbed Jekyll

_GEN_RB = r"""
require 'json'
module Jekyll
  class Generator
    def self.safe(v = nil) = (@safe = v)
    def self.priority(v = nil)
      @priority = v unless v.nil?
      @priority
    end
  end
  class PageWithoutAFile
    attr_accessor :data, :content
    attr_reader :dir, :name
    def initialize(_site, _base, dir, name)
      @dir = dir
      @name = name
      @data = {}
    end
    def url = data["permalink"]
  end
end
FakePage = Struct.new(:url, :data, :content)
FakeSite = Struct.new(:pages, :source)
load ARGV[0]
payload = JSON.parse(File.read(ARGV[1], encoding: "utf-8"))
out = { "priority" => Auxsays::PatchFeedPages.priority.to_s, "cases" => {} }
payload["cases"].each do |name, c|
  feed_data = { "layout" => "aux-updates", "title" => "Patch Feed", "permalink" => "/updates/" }
  feed_data["feed_page_size"] = c["size"] unless c["size"].nil?
  feed = FakePage.new(c["feed_url"] || "/updates/", feed_data, "BODY")
  records = c["records"].each_with_index.map { |d, i| FakePage.new(d.delete("_url") || "/r/#{i}/", d, "") }
  pages = [feed] + records
  site = FakeSite.new(pages, "/src")
  before = pages.size
  begin
    Auxsays::PatchFeedPages.new.generate(site)
    made = site.pages.drop(before).map do |p|
      { "url" => p.url, "dir" => p.dir, "name" => p.name, "title" => p.data["title"], "feed_page" => p.data["feed_page"],
        "layout" => p.data["layout"], "size" => p.data["feed_page_size"], "content" => p.content,
        "build" => p.data["feed_build"] }
    end
    ranked = records.select { |r| r.data.key?("feed_rank") }.sort_by { |r| r.data["feed_rank"] }.map(&:url)
    out["cases"][name] = { "made" => made, "first" => feed.data["feed_page"], "build" => feed.data["feed_build"],
                           "ranked" => ranked, "ranks" => records.map { |r| r.data["feed_rank"] } }
  rescue => e
    out["cases"][name] = { "error" => e.class.to_s }
  end
end
File.write(ARGV[2], JSON.generate(out), encoding: "utf-8")
"""


def run_generator(cases: dict) -> dict | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script, payload, out = Path(td) / "g.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_GEN_RB, encoding="utf-8")
        payload.write_text(json.dumps({"cases": cases}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(PLUGIN), str(payload), str(out)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


def check_generator() -> None:
    print("\n[G] the shipped generator under stub Jekyll classes")
    rec = lambda **kw: {"update_entry": True, **kw}  # noqa: E731
    live = [rec() for _ in range(1434)] + [rec(update_status="archived") for _ in range(101)]
    cases = {
        "live": {"size": 100, "records": live},
        "exact": {"size": 100, "records": [rec() for _ in range(200)]},
        "one-over": {"size": 100, "records": [rec() for _ in range(101)]},
        "none": {"size": 100, "records": []},
        "predicate": {"size": 1, "records": [rec(), rec(update_entry="true"), {"update_entry": False}, {"title": "x"},
                                             rec(feed_hidden=True), rec(feed_hidden="true"), rec(update_status="archived")]},
        "no-size": {"size": None, "records": [rec()]},
        "zero": {"size": 0, "records": [rec()]},
        "no-feed": {"size": 1, "records": [rec(), rec()], "feed_url": "/elsewhere/"},
    }
    # ORDER and STAMP. Twelve records published at one moment (the ties the layout used to leave to the
    # order the files were read), one newer, one with no date, one archived among the ties and one
    # hidden. The same records reach the generator in three orders.
    tie = "2026-09-08T00:00:00Z"
    ordered = ([("/u/new/", "2026-10-01T00:00:00Z", {})]
               + [(f"/u/t{k:02d}/", tie, {}) for k in range(12)]
               + [("/u/t05a/", tie, {"update_status": "archived"}), ("/u/old/", "2025-01-01T00:00:00.000Z", {}),
                  ("/u/old-hidden/", "2025-01-01T00:00:00.000Z", {"feed_hidden": True}), ("/u/undated/", None, {})])
    by_url = {u: (d, extra) for u, d, extra in ordered}
    expect_rank = ["/u/new/"] + sorted([u for u, d, _ in ordered if d == tie]) + sorted(["/u/old/", "/u/old-hidden/"]) + ["/u/undated/"]

    def recs(urls):
        out_ = []
        for u in urls:
            d, extra = by_url[u]
            r = rec(_url=u, **extra)
            if d is not None:
                r["update_published_at"] = d
            out_.append(r)
        return out_

    urls = [u for u, _, _ in ordered]
    rotated = urls[7:] + urls[:7]
    cases["order-a"] = {"size": 5, "records": recs(urls)}
    cases["order-b"] = {"size": 5, "records": recs(list(reversed(urls)))}
    cases["order-c"] = {"size": 5, "records": recs(rotated)}
    cases["order-size4"] = {"size": 4, "records": recs(urls)}
    by_url["/u/added/"] = (tie, {})
    cases["order-plus"] = {"size": 5, "records": recs(urls + ["/u/added/"])}
    listed = [u for u in expect_rank if u != "/u/old-hidden/"]
    feed_list = [u for u in listed if u != "/u/t05a/"] + ["/u/t05a/"]
    expect_pages = [feed_list[i:i + 5] for i in range(0, len(feed_list), 5)]
    expect_stamp = stamp_of(expect_pages)
    out = run_generator(cases)
    if out is None or "__error__" in out:
        check("G1 the generator loads and runs", False, str(out)[:300] if out else "ruby missing")
        return
    check("G1 the generator loads and runs", all("error" not in out["cases"][k] for k in ("live", "exact", "one-over", "none")),
          json.dumps(out["cases"])[:300])
    made = out["cases"]["live"]["made"]
    check("G2 1,535 listed records at 100 a page: pages 2..16 are made, page 1 is the feed itself",
          [m["feed_page"] for m in made] == list(range(2, 17)) and out["cases"]["live"]["first"] == 1, str(len(made)))
    check("G3 each made page is the feed page: same layout, same body, same size, its own self permalink",
          all(m["layout"] == "aux-updates" and m["content"] == "BODY" and m["size"] == 100
              and m["url"] == f"/updates/page/{m['feed_page']}/" and m["dir"] == f"updates/page/{m['feed_page']}"
              and m["name"] == "index.html" for m in made), json.dumps(made[:1]))
    check("G4 titles are distinct per page", len({m["title"] for m in made}) == len(made)
          and made[0]["title"] == "Patch Feed, page 2", str([m["title"] for m in made[:2]]))
    check("G5 an exact multiple makes no empty trailing page; one over makes one more; none makes none",
          len(out["cases"]["exact"]["made"]) == 1 and len(out["cases"]["one-over"]["made"]) == 1
          and out["cases"]["none"]["made"] == [], json.dumps({k: len(out["cases"][k]["made"]) for k in ("exact", "one-over", "none")}))
    # update_entry true and "true" count (Jekyll's where compares as text), false/absent do not;
    # feed_hidden: true is omitted, the string "true" is not (the layout's where_exp is `!= true`);
    # archived records count (they are on the feed, after the current ones). 4 listed at 1 a page =
    # pages 2..4; getting any one of the seven records wrong moves the count by one.
    check("G6 the generator counts what the layout lists: update_entry true, not feed_hidden true, archived included",
          len(out["cases"]["predicate"]["made"]) == 3, json.dumps(out["cases"]["predicate"]))
    check("G7 a missing or non-positive feed_page_size is refused, never defaulted",
          out["cases"]["no-size"].get("error") == "KeyError" and out["cases"]["zero"].get("error") == "ArgumentError",
          json.dumps({k: out["cases"][k] for k in ("no-size", "zero")}))
    check("G8 without the /updates/ feed page it makes nothing", out["cases"]["no-feed"].get("made") == [],
          json.dumps(out["cases"]["no-feed"]))
    check("G9 it runs before jekyll-sitemap (priority high; the sitemap generator is lowest)", out["priority"] == "high",
          out["priority"])
    oc = {k: out["cases"][k] for k in ("order-a", "order-b", "order-c", "order-size4", "order-plus")}
    check("G10 it ranks every record newest first, records published at the same moment by permalink, an undated one "
          "last, and gives the same ranks whatever order the site lists the pages in",
          all("error" not in v for v in oc.values())
          and all(oc[k].get("ranked") == expect_rank for k in ("order-a", "order-b", "order-c"))
          and sorted(oc["order-a"]["ranks"]) == list(range(len(expect_rank))),
          json.dumps({k: (v.get("ranked") or v)[:6] for k, v in oc.items()})[:400])
    builds = {k: [v.get("build")] + [m.get("build") for m in v.get("made", [])] for k, v in oc.items()}
    check("G11 every feed page carries one stamp, the digest of the feed's cards and pages (current then archived, "
          "hidden omitted), as the gate computes it; the same for the same records in any order; one more record, "
          "or another page size, changes it",
          all(len(set(builds[k])) == 1 and len(builds[k]) == 4 for k in ("order-a", "order-b", "order-c", "order-plus"))
          and {builds[k][0] for k in ("order-a", "order-b", "order-c")} == {expect_stamp}
          and vfd.feed_stamp(expect_pages) == expect_stamp
          and builds["order-plus"][0] not in (None, expect_stamp) and builds["order-size4"][0] not in (None, expect_stamp),
          json.dumps({k: v[:2] for k, v in builds.items()})[:400] + " expect " + expect_stamp)


# ---------------------------------------------------------------- [J] the shipped catalogue functions, under node

# Cards are stubs that answer the one query the shipped code asks of them (the headline link);
# `adopt` marks a copy, so "this page's own card wins" is checked on identity, not on the link.
_CATALOG_PROBE = r"""
const C = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const mk = (spec) => ({ ...spec, querySelector: (sel) => (sel === 'a.patch-identity' && spec.href != null
  ? { getAttribute: (name) => (name === 'href' ? spec.href : null) } : null) });
const adopt = (card) => ({ ...card, adopted: true });
const ids = (cards) => cards.map((c) => c.id + (c.adopted ? '' : '*'));
const assembleFrom = (pages, k) => {
  const built = pages.map((pg) => pg.map(mk));
  return assembleFeedCatalog(built[k], built.filter((_, i) => i !== k), k, adopt);
};
const out = {};
// The shipped company sort's comparator: stable, equal companies keep the held order.
const byCompany = (a, b) => (a.company || '').localeCompare(b.company || '');
out.order = C.order.map((_, k) => {
  const cat = assembleFrom(C.order, k);
  return { cards: cat.cards.map((c) => c.id), ahead: cat.ahead.map((c) => c.id), behind: cat.behind.map((c) => c.id),
           sorted: cat.cards.slice().sort(byCompany).map((c) => c.id) };
});
out.dupes = ids(assembleFrom(C.dupes.pages, C.dupes.own).cards);
out.stamps = C.stamps.map(([own, builds]) => feedPagesFromOtherBuilds(own, builds));
const runLoader = async (spec) => {
  const calls = [];
  const fetchPage = (at, cache) => {
    calls.push([at, cache]);
    const n = calls.filter(([a]) => a === at).length;
    const build = spec.builds[at][Math.min(n - 1, spec.builds[at].length - 1)];
    if (build === 'ERR') return Promise.reject(new Error('HTTP 503'));
    return Promise.resolve({ build, cards: [`p${at}#${n}`] });
  };
  try {
    const pages = await loadFeedPages(spec.builds.length, spec.own, fetchPage);
    return { calls, result: pages && pages.map((p) => p.cards[0]) };
  } catch (e) {
    return { calls, error: e.message };
  }
};
// The pager as the browser hands it over: one link per page (page 1 first), with a foreign one in front.
const pagerLinks = (n, current) => [{ origin: 'https://elsewhere.example', pathname: '/updates/page/2/', cur: false }]
  .concat(Array.from({ length: n }, (_, i) => ({
    origin: C.origin, pathname: i === 0 ? '/updates/' : `/updates/page/${i + 1}/`, cur: i + 1 === current })))
  .map((l) => ({ origin: l.origin, pathname: l.pathname, getAttribute: (name) => (name === 'aria-current' && l.cur ? 'page' : null) }));
out.plan = {};
out.planOrder = {};
for (const k of C.planFrom) {
  const plan = feedPagePlan(pagerLinks(C.planPages, k), C.origin);
  out.plan[k] = plan;
  // Every page's cards, fetched in the plan's order, assembled from page k.
  const pageOf = (url) => (url === `${C.origin}/updates/` ? 1 : Number(url.split('/page/')[1].split('/')[0]));
  const cards = (p) => [mk({ id: `p${p}a`, href: `/u/p${p}a/` }), mk({ id: `p${p}b`, href: `/u/p${p}b/` })];
  const cat = assembleFeedCatalog(cards(k), plan.urls.map((url) => cards(pageOf(url))), plan.before, adopt);
  out.planOrder[k] = cat.cards.map((c) => c.id);
}
const runCatalog = async (spec) => {
  const fetchPage = (at, cache) => {
    const n = (runCatalog.calls[at] = (runCatalog.calls[at] || 0) + 1);
    const build = spec.builds[at][Math.min(n - 1, spec.builds[at].length - 1)];
    if (build === 'ERR') return Promise.reject(new Error('HTTP 503'));
    return Promise.resolve({ build, cards: [mk({ id: `p${at + 1}`, href: `/u/p${at + 1}/` })] });
  };
  runCatalog.calls = {};
  const res = await loadFeedCatalog([mk({ id: 'own', href: '/u/own/' })], spec.builds.length, spec.before, spec.own, fetchPage, adopt);
  return { state: res.state, cards: res.catalog && res.catalog.cards.map((c) => c.id) };
};
out.view = {};
for (const state of ['page', 'loading', 'complete', 'failed', 'mixed']) {
  for (const wide of [true, false]) out.view[`${state}/${wide ? 'wide' : 'page'}`] = feedCatalogView(state, wide, 7, 1535);
}
(async () => {
  out.loader = {};
  for (const [name, spec] of Object.entries(C.loader)) out.loader[name] = await runLoader(spec);
  out.catalog = {};
  for (const [name, spec] of Object.entries(C.catalog)) out.catalog[name] = await runCatalog(spec);
  console.log(JSON.stringify(out));
})();
"""


def catalog_block(js: str) -> str:
    """The shipped catalogue functions (feedCardHref .. feedCatalogView), exactly as auxsays.js defines them."""
    start = js.index("const feedCardHref = ")
    end = js.index("// Patch Feed controls:")
    return js[start:end]


def run_catalog(cases: dict) -> dict | None:
    node = shutil.which("node")
    if not node:
        return None
    with tempfile.TemporaryDirectory() as td:
        script, payload = Path(td) / "c.js", Path(td) / "p.json"
        script.write_text(catalog_block(JS.read_text(encoding="utf-8")) + _CATALOG_PROBE, encoding="utf-8")
        payload.write_text(json.dumps(cases), encoding="utf-8")
        proc = subprocess.run([node, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0 or not proc.stdout.strip():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(proc.stdout.strip().splitlines()[-1])


def check_catalog() -> None:
    print("\n[J] the shipped catalogue functions, under node")
    # Four pages of the one build order. Companies tie ACROSS pages (adobe on 1, 2 and 4; obs on 1 and 3),
    # which is what a stable sort from a later page used to break the other way.
    co = ["adobe", "obs", "msft", "adobe", "msft", "msft", "obs", "adobe", "adobe", "msft", "obs", "adobe"]
    order = [[{"id": f"r{i}", "href": f"/u/r{i}/", "company": co[i]} for i in range(p * 3, p * 3 + 3)] for p in range(4)]
    build_order = [c["id"] for pg in order for c in pg]
    card = lambda i, h: {"id": i, "href": h}  # noqa: E731
    dupes = {"own": 1, "pages": [
        [card("A", "/u/a/"), card("X@1", "/u/x/"), card("B", "/u/b/")],
        [card("X@2", "/u/x/"), card("C", "/u/c/")],
        [card("Y@3", "/u/y/"), card("X@3", "/u/x/"), card("D", "/u/d/")],
        [card("Y@4", "/u/y/"), {"id": "N", "href": None}, card("E", "/u/e/")],
    ]}
    stamps = [["b2", ["b2", "b1", "", "b2"]], ["", ["", "b2"]], ["b2", ["b2", "b2"]]]
    loader = {
        "same": {"own": "b2", "builds": [["b2"], ["b2"], ["b2"]]},
        "stale-then-fresh": {"own": "b2", "builds": [["b2"], ["b1", "b2"], ["b2"]]},
        "stale-twice": {"own": "b2", "builds": [["b2"], ["b1", "b1"], ["b2"]]},
        "unstamped-page": {"own": "b2", "builds": [[""], ["b2"]]},
        "unstamped-self": {"own": "", "builds": [["b2"], ["b2"]]},
        "network": {"own": "b2", "builds": [["b2"], ["ERR"]]},
    }
    plan_from = [1, 2, 8, 10, 16]
    catalog = {
        "same": {"own": "b2", "before": 1, "builds": [["b2"], ["b2"], ["b2"]]},
        "stale-twice": {"own": "b2", "before": 1, "builds": [["b2"], ["b1", "b1"], ["b2"]]},
        "network": {"own": "b2", "before": 1, "builds": [["b2"], ["ERR"]]},
    }
    origin = "https://auxsays.com"
    try:
        out = run_catalog({"order": order, "dupes": dupes, "stamps": stamps, "loader": loader, "origin": origin,
                           "planPages": 16, "planFrom": plan_from, "catalog": catalog})
    except ValueError as exc:
        out = {"__error__": f"catalogue block not found: {exc}"}
    check("J0 node runs the shipped catalogue block (feedCardHref .. feedCatalogView)",
          out is not None and "__error__" not in out, str(out)[:300] if out else "node not on PATH")
    if out is None or "__error__" in out:
        return
    o = out["order"]
    check("J1 from each of the four pages the catalogue is held in the build's order: the earlier pages' cards "
          "ahead of this page's own, the later pages' after them",
          all(r["cards"] == build_order for r in o)
          and all(r["ahead"] == build_order[:3 * k] and r["behind"] == build_order[3 * k + 3:] for k, r in enumerate(o)),
          json.dumps([r["cards"] for r in o])[:300])
    check("J1b so a stable sort with ties across pages (Company) gives the same order from pages 2, 3 and 4 as from page 1",
          len({tuple(r["sorted"]) for r in o}) == 1 and o[0]["sorted"][:5] == ["r0", "r3", "r7", "r8", "r11"],
          json.dumps([r["sorted"][:6] for r in o]))
    check("J2 each patch is held once, by its link: this page's own card wins, then the first in feed order; "
          "a card with no link is kept",
          out["dupes"] == ["A", "B", "X@2*", "C*", "Y@3", "D", "N", "E"], json.dumps(out["dupes"]))
    check("J3 a fetched page counts as another build when its stamp differs from this page's, or either has none",
          out["stamps"] == [[1, 2], [0, 1], []], json.dumps(out["stamps"]))
    L = out["loader"]
    check("J4 pages of this page's build are each fetched once, through the browser cache, and used",
          L["same"].get("result") == ["p0#1", "p1#1", "p2#1"]
          and L["same"]["calls"] == [[0, "default"], [1, "default"], [2, "default"]], json.dumps(L["same"]))
    check("J5 a page from another build is fetched once more, past the cache (no-cache), and only that page; "
          "its fresh copy is used",
          L["stale-then-fresh"].get("result") == ["p0#1", "p1#2", "p2#1"]
          and L["stale-then-fresh"]["calls"][3:] == [[1, "no-cache"]], json.dumps(L["stale-then-fresh"]))
    check("J6 a page that still differs after that one retry, or a missing stamp on either side, leaves the controls "
          "on this page (null), never retried again",
          L["stale-twice"].get("result", "x") is None and L["stale-twice"]["calls"][3:] == [[1, "no-cache"]]
          and L["unstamped-page"].get("result", "x") is None and L["unstamped-page"]["calls"][2:] == [[0, "no-cache"]]
          and L["unstamped-self"].get("result", "x") is None
          and L["unstamped-self"]["calls"][2:] == [[0, "no-cache"], [1, "no-cache"]],
          json.dumps({k: L[k] for k in ("stale-twice", "unstamped-page", "unstamped-self")})[:400])
    check("J7 a page that fails to load rejects the load (the controls say the other pages could not be loaded)",
          L["network"].get("error") == "HTTP 503", json.dumps(L["network"]))
    page_url = lambda n: f"{origin}/updates/" if n == 1 else f"{origin}/updates/page/{n}/"  # noqa: E731
    plans = out["plan"]
    check("J8 the pager's links give, from pages 1, 2, 8, 10 and 16 of 16, every other page of this site in page order "
          "(10 after 9, not after 1), by origin and path, and how many of them come before this page",
          all(plans[str(k)] == {"urls": [page_url(n) for n in range(1, 17) if n != k], "before": k - 1} for k in plan_from),
          json.dumps({k: {"before": v["before"], "urls": [u.rsplit("/updates/", 1)[1] for u in v["urls"]][:11]}
                      for k, v in plans.items()})[:500])
    whole = [f"p{n}{s}" for n in range(1, 17) for s in "ab"]
    check("J8b so from each of those pages the catalogue is assembled in the build's one order",
          all(out["planOrder"][str(k)] == whole for k in plan_from),
          json.dumps({k: v[:6] for k, v in out["planOrder"].items()})[:400])
    cat = out["catalog"]
    check("J9 the loaded catalogue settles as 'complete' in feed order, as 'mixed' (no catalogue, not 'failed') when "
          "a page is still from another feed after its retry, and as 'failed' when a page cannot be loaded",
          cat["same"] == {"state": "complete", "cards": ["p1", "own", "p2", "p3"]}
          and cat["stale-twice"] == {"state": "mixed", "cards": None}
          and cat["network"] == {"state": "failed", "cards": None}, json.dumps(cat))
    v = out["view"]
    mixed_note = ("Showing matches from this page only: the feed was updated after this page loaded. "
                  "Reload to search every page.")
    failed_note = "Showing matches from this page only: the other pages of the feed could not be loaded."
    check("J10 a search on a 'mixed' feed shows the pager and the mixed note, not the failed note; 'failed' shows the "
          "pager and its own note; 'loading' and 'complete' hide the pager and count over every page; with no "
          "control engaged the pager shows and there is no note",
          v["mixed/wide"] == {"pagerHidden": False, "message": mixed_note}
          and v["failed/wide"] == {"pagerHidden": False, "message": failed_note}
          and v["loading/wide"] == {"pagerHidden": True, "message": "Searching all 1535 tracked patches\u2026"}
          and v["complete/wide"] == {"pagerHidden": True,
                                     "message": "7 of 1535 tracked patches match, from every page of the feed."}
          and all(v[f"{s}/page"] == {"pagerHidden": False, "message": ""}
                  for s in ("page", "loading", "complete", "failed", "mixed")), json.dumps(v)[:500])


# ---------------------------------------------------------------- [W] wiring, scoped to the statement

def check_wiring() -> None:
    print("\n[W] the wiring")
    yml = PAGES_YML.read_text(encoding="utf-8")
    build = yml.find("run: bundle exec jekyll build")
    gate = yml.find("run: python auxsays/scripts/ci/verify_feed_discovery.py --site auxsays/_site")
    upload = yml.find("uses: actions/upload-pages-artifact")
    check("W1 the deploy runs the gate on the built site, after the build and before the upload",
          0 <= build < gate < upload, f"{build} {gate} {upload}")
    fm = FEED_INDEX.read_text(encoding="utf-8").split("---", 2)[1]
    sizes = re.findall(r"^feed_page_size:\s*(\d+)\s*$", fm, re.M)
    check("W2 the page size is declared once, on the feed page, and keeps a page well inside the budget",
          len(sizes) == 1 and 1 <= int(sizes[0]) <= 150, str(sizes))
    layout = LAYOUT.read_text(encoding="utf-8")
    nav_at = layout.find('<nav class="panel patch-pagination"')
    nav = layout[nav_at:layout.find("</nav>", nav_at)] if nav_at >= 0 else ""
    check("W3 the pager is plain anchors: one <a href> per page, from 1 to feed_pages, and no script hook in place of href",
          "{%- for feed_n in (1..feed_pages) -%}" in nav and '<a class="patch-chip' in nav and 'href="{{ feed_href }}"' in nav
          and "data-href" not in nav and "onclick" not in nav and "<button" not in nav, nav[:200])
    check("W4 the pager is rendered whenever there is more than one page (not gated on script or on page 1)",
          "{% if feed_pages > 1 %}\n  <nav" in layout, "")
    js = JS.read_text(encoding="utf-8")
    plan_stmt = js.split("const feedPlan = ", 1)[1].split(";", 1)[0] if "const feedPlan = " in js else ""
    check("W5 the loader reads its pages from the pager's own links, same origin only (feedPagePlan, [J] J8)",
          plan_stmt == "feedPagePlan(feedPager ? Array.from(feedPager.querySelectorAll('a[data-feed-page-link]')) : [],"
                       "\n      window.location.origin)"
          and "const otherPageUrls = feedPlan.urls;" in js and "const pagesBefore = feedPlan.before;" in js, plan_stmt[:200])
    adopt = js.split("doc.querySelectorAll(", 1)[1].split(")", 1)[0] if "doc.querySelectorAll(" in js else ""
    check("W6 the loader adopts only the feed's cards (current and archive), never the radar or a whole page",
          adopt == "'#patch-feed .patch-card, #patch-archive-feed .patch-card'", adopt)
    scope = js.split("const inScope = ", 1)[1].split(";", 1)[0] if "const inScope = " in js else ""
    check("W7 with no control engaged only this page's own cards show; engaged, every page's do",
          scope == "catalogWide || card.dataset.feedImported !== 'true'", scope)
    default = js.split("const isDefaultView = ", 1)[1].split(";", 1)[0] if "const isDefaultView = " in js else ""
    check("W8 every control counts as engaged: search, category, type, company, software, My Watchlist and sort",
          all(t in default for t in ("!query", "currentFilter === 'all'", "currentLane === 'all'", "currentCompany === 'all'",
                                      "currentSoftware === 'all'", "!watchlistOnly", "currentSort === 'latest'")), default)
    stamp_attr = 'data-feed-build="{{ page.feed_build }}"'
    own_build = js.split("const ownBuild = ", 1)[1].split(";", 1)[0] if "const ownBuild = " in js else ""
    fetched = js.split("const fetchFeedPage = ", 1)[1].split("\n    });", 1)[0] if "const fetchFeedPage = " in js else ""
    check("W9 the pager carries the feed's stamp (the generator's digest, never the build time), and the loader "
          "compares this page's with each fetched page's",
          stamp_attr in nav and "site.time" not in nav and own_build == "feedPager?.dataset.feedBuild || ''"
          and "build: doc.querySelector('[data-feed-pages]')?.dataset.feedBuild || ''," in fetched,
          f"{stamp_attr in nav} {own_build!r} {fetched[-200:]!r}")
    load = js.split("const loadCatalog = () => {", 1)[1].split("\n    };", 1)[0] if "const loadCatalog = () => {" in js else ""
    before = js.split("const pagesBefore = ", 1)[1].split(";", 1)[0] if "const pagesBefore = " in js else ""
    check("W10 the loader holds the catalogue it assembled in feed order (DOM too), takes the state loadFeedCatalog "
          "settled on, and shows what feedCatalogView says for it",
          "loadFeedCatalog(allCards, otherPageUrls.length, pagesBefore, ownBuild, fetchFeedPage, adoptFeedCard)"
          ".then(({ state, catalog }) => {\n        if (catalog) {" in load
          and "home.insertBefore(lead, home.firstChild);" in load
          and "          allCards = catalog.cards;\n        }\n        catalogState = state;\n        schedulePatchFeed();" in load
          and "allCards.concat(" not in js and before == "feedPlan.before"
          and "const feedView = feedCatalogView(catalogState, catalogWide, visibleUpdates.length, feedTotal);" in js
          and "if (feedPager) feedPager.hidden = feedView.pagerHidden;" in js
          and "feedStatus.textContent = feedView.message;\n        feedStatus.hidden = !feedView.message;" in js
          and js.count("feedPager.hidden = ") == 1 and js.count("feedStatus.textContent = ") == 1, load[:300])
    sort_stmt = re.findall(r"\{% assign update_pages = [^%]*%\}", layout)
    check("W11 the feed lists the records in the generator's order (feed_rank: ties broken by permalink), not a sort "
          "on the date alone that leaves tied records to the order the files were read",
          sort_stmt == ['{% assign update_pages = site.pages | where: "update_entry", true | sort: "feed_rank" %}']
          and '{% assign current_pages = update_pages | where_exp: "item", "item.update_status != \'archived\' and '
              'item.feed_hidden != true" %}' in layout
          and '{% assign archived_pages = update_pages | where: "update_status", "archived" %}' in layout, str(sort_stmt))


def run() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        check_gate(tmp)
        check_liquid()
        check_generator()
        check_catalog()
        check_wiring()
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
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
