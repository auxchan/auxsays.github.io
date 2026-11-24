#!/usr/bin/env python3
"""The per-product patch verdict Atom feeds and their autodiscovery links (P8).

WHAT IS PINNED, rendered from the SHIPPED templates with the Liquid gem (ruby + liquid 4.0.4 required;
their absence is a failure, never a skip):

  [F] _includes/patch-atom-feed.html over a synthetic site: valid Atom (parsed, Atom namespace, every
      required element, RFC 3339 dates); only that product's update_entry pages, newest release first,
      archived and feed_hidden pages left out, the limit honoured; the verdict, scope and line are the
      verdict gate's (a malformed projection row prints "no verdict yet", a stored quick_verdict never
      prints); an entry's date is its stored record_last_updated, else its release date, and a record with
      neither readable is left out rather than dated now; the feed's date is its newest entry's; the
      subtitle says there is no verdict-change history; entry ids are the clean page URL, links carry the
      feed's utm tags.
  [L] _layouts/aux-patch-atom.html renders a product stub and the every-product stub into those feeds,
      and a stub with neither field prints nothing.
  [S] the stubs: one per product tracker (every aux-patch-product page), each naming its tracker's own
      product id, page and URL; one every-product feed; no two feeds at one URL; none in the sitemap.
  [A] aux-base.html's autodiscovery block: product, version and patch pages name their product's feed
      and the every-product feed; the homepage and the Patch Feed name the every-product feed; any other
      page names none; no feed page in the build, no link.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_atom_feeds.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path
from xml.etree import ElementTree

import yaml

_REPO = Path(__file__).resolve().parents[3]
AUX = _REPO / "auxsays"
INCLUDES = AUX / "_includes"
FEED_INCLUDE = INCLUDES / "patch-atom-feed.html"
FEED_LAYOUT = AUX / "_layouts" / "aux-patch-atom.html"
BASE_LAYOUT = AUX / "_layouts" / "aux-base.html"
ATOM = "{http://www.w3.org/2005/Atom}"
ORIGIN = "https://auxsays.com"
NOW = "2026-11-24T08:00:00Z"
RFC3339 = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}\Z")
UTM = "?utm_source=feed&utm_medium=rss"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + detail[:600])
        _ERRORS.append(label)


# --------------------------------------------------------------------------- ruby bridge (shipped templates)

_DRIVER = r"""
require 'liquid'
require 'json'
module Shims
  def absolute_url(i) = "https://auxsays.com/" + i.to_s.sub(%r{\A/}, "")
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def xml_escape(i) = i.to_s.encode(xml: :attr).gsub(/\A"|"\z/, "")
  def where(input, property, value)
    input = input.values if input.is_a?(Hash)
    return input unless input.respond_to?(:select)
    input.select { |item| item.is_a?(Hash) && item[property].to_s == value.to_s }
  end
  # Jekyll's sort: nils first, then ascending.
  def sort(input, property = nil)
    return input unless input.respond_to?(:partition)
    nils, rest = input.partition { |i| i.is_a?(Hash) && i[property].nil? }
    nils + rest.sort_by { |i| i[property].to_s }
  end
end
Liquid::Template.register_filter(Shims)
class JekyllInclude < Liquid::Tag
  SYNTAX = /([\w.\/-]+)((\s+\w+\s*=\s*(?:"[^"]*"|'[^']*'|[\w.\[\]\/-]+))*)/
  def initialize(name, markup, tokens)
    super
    m = markup.strip.match(SYNTAX) or raise Liquid::SyntaxError, "bad include: #{markup}"
    @file = m[1]
    @params = {}
    (m[2] || "").scan(/(\w+)\s*=\s*("[^"]*"|'[^']*'|[\w.\[\]\/-]+)/) { |k, v| @params[k] = v }
  end
  def render(context)
    path = File.join(context.registers[:include_root], @file)
    raise Liquid::Error, "missing include #{@file}" unless File.exist?(path)
    vals = {}
    @params.each { |k, v| vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v] }
    partial = (context.registers[:cache] ||= {})[path] ||=
      Liquid::Template.parse(File.read(path, encoding: "utf-8"))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
out = {}
payload["cases"].each do |name, c|
  begin
    tpl = Liquid::Template.parse(c["template"])
    out[name] = tpl.render!({ "site" => c["site"], "page" => c["page"] },
                            registers: { include_root: payload["includes"] })
  rescue => e
    out[name] = "<<ERR #{e.class}: #{e.message}>>"
  end
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""


def render_cases(cases: dict) -> dict | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script, payload, out = Path(td) / "d.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_DRIVER, encoding="utf-8")
        payload.write_text(json.dumps({"cases": cases, "includes": str(INCLUDES)}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- the synthetic site

def rec(name: str, product: str = "tool", **fields) -> dict:
    base = {"url": f"/u/{product}/{name}/", "layout": "aux-update", "update_entry": True, "company_id": "acme",
            "product_id": product, "update_product": "Tool", "update_version": name,
            "update_detail_title": f"Tool {name}", "update_report_count": 0}
    base.update(fields)
    return base


def site() -> dict:
    pages = [
        # newest release first: r5 (Nov 20) .. r1 (Nov 1); archived / hidden ones are newer still
        rec("r5", update_published_at="2026-11-20T10:00:00Z", record_last_updated="2026-11-23T09:30:00Z",
            update_report_count=4, quick_verdict="AVOID: a stored label that must never print"),
        rec("r4", update_published_at="2026-11-15T00:00:00Z", record_last_updated="2026-11-16T00:00:00Z",
            update_report_count=1),
        rec("r3", update_published_at="2026-11-10T00:00:00Z"),                    # no record_last_updated
        rec("r2", update_published_at="2026-11-05T00:00:00Z", record_last_updated="2026-11-06T00:00:00Z"),
        rec("r1", update_published_at="2026-11-01T00:00:00Z", record_last_updated="2026-11-02T00:00:00Z"),
        rec("rf", update_published_at="2026-10-30T00:00:00Z", record_last_updated="2099-01-01T00:00:00Z"),  # stamp later than the build
        rec("bad", update_published_at="soon", record_last_updated="2026-13-45T00:00:00Z"),  # no readable date
        rec("future", update_published_at="2099-01-01T00:00:00Z"),                # later than the build
        rec("gone", update_published_at="2026-11-22T00:00:00Z", update_status="archived"),
        rec("hidden", update_published_at="2026-11-21T00:00:00Z", feed_hidden=True),
        rec("x1", product="other", update_product="Other", update_detail_title="Other x1",
            update_published_at="2026-11-23T00:00:00Z", record_last_updated="2026-11-23T12:00:00Z"),
        {"url": "/u/tool/", "layout": "aux-patch-product", "product_id": "tool"},     # not an update_entry
        {"url": "/u/tool/feed.xml", "layout": "aux-patch-atom", "feed_product_id": "tool",
         "feed_alternate": "/u/tool/", "feed_limit": 3},
        {"url": "/updates/feed.xml", "layout": "aux-patch-atom", "feed_scope": "all", "feed_limit": 50},
    ]
    projection = {"pages": {
        "tool|r5|": {"verdict": "WAIT", "scope": "if you use the X plugin", "body": "Two users report X crashes.",
                     "reason_code": "", "label": ""},
        "tool|r4|": {"verdict": "WAIT", "scope": "", "body": "A WAIT with no scope the gate must refuse.",
                     "reason_code": "", "label": ""},
        "other|x1|": {"verdict": "SECURITY UPDATE", "scope": "", "body": "Install it: it fixes a vulnerability.",
                      "reason_code": "", "label": ""},
    }}
    return {"time": NOW, "pages": pages,
            "data": {"verdict_projection": projection,
                     "patch_products": [{"id": "tool", "product_name": "Tool & Co"}]}}


def feed_case(product: str, limit: int, s: dict | None = None) -> dict:
    tpl = (f"{{% include patch-atom-feed.html product_id='{product}' limit={limit} title_name='Tool' "
           f"alternate='/u/tool/' %}}")
    return {"template": tpl, "site": s or site(), "page": {"url": "/u/tool/feed.xml"}}


def parse(xml: str):
    try:
        return ElementTree.fromstring(xml.encode("utf-8"))
    except ElementTree.ParseError:
        return None


def entries(root) -> list[dict]:
    out = []
    for e in root.findall(f"{ATOM}entry"):
        link = e.find(f"{ATOM}link")
        cat = e.find(f"{ATOM}category")
        out.append({"id": e.findtext(f"{ATOM}id"), "title": e.findtext(f"{ATOM}title"),
                    "href": link.get("href") if link is not None else None,
                    "rel": link.get("rel") if link is not None else None,
                    "updated": e.findtext(f"{ATOM}updated"), "published": e.findtext(f"{ATOM}published"),
                    "summary": e.findtext(f"{ATOM}summary") or "", "category": cat.get("term") if cat is not None else None})
    return out


def is_valid_atom(xml: str) -> tuple[bool, str]:
    """RFC 4287's required elements, checked with a parser."""
    if not xml.startswith('<?xml version="1.0" encoding="utf-8"?>'):
        return False, "no XML declaration first: " + xml[:60]
    root = parse(xml)
    if root is None:
        return False, "does not parse"
    if root.tag != f"{ATOM}feed":
        return False, f"root is {root.tag}"
    for tag in ("id", "title", "updated"):
        if len(root.findall(f"{ATOM}{tag}")) != 1:
            return False, f"feed needs exactly one {tag}"
    if not RFC3339.match(root.findtext(f"{ATOM}updated") or ""):
        return False, "feed updated is not RFC 3339"
    if root.find(f"{ATOM}author/{ATOM}name") is None:
        return False, "no feed author"
    if not [l for l in root.findall(f"{ATOM}link") if l.get("rel") == "self"]:
        return False, "no self link"
    for e in root.findall(f"{ATOM}entry"):
        for tag in ("id", "title", "updated"):
            if len(e.findall(f"{ATOM}{tag}")) != 1:
                return False, f"entry needs exactly one {tag}"
        if not RFC3339.match(e.findtext(f"{ATOM}updated") or ""):
            return False, "entry updated is not RFC 3339"
        if e.find(f"{ATOM}summary") is None and e.find(f"{ATOM}content") is None:
            return False, "entry has neither summary nor content"
    return True, ""


# --------------------------------------------------------------------------- [F] [L] the feed renders

def section_f() -> None:
    print("\n[F] the feed include, rendered with the Liquid gem")
    empty_site = site()
    empty_site["pages"] = [p for p in empty_site["pages"] if not p.get("update_entry")]
    cases = {"tool": feed_case("tool", 50), "tool_cap": feed_case("tool", 2), "all": feed_case("", 50),
             "empty": feed_case("tool", 20, empty_site)}
    out = render_cases(cases)
    if out is None or "__error__" in out or any(str(v).startswith("<<ERR") for v in out.values()):
        check("F1 the shipped feed include renders under the Liquid gem", False, str(out)[:600])
        return
    ok = {k: is_valid_atom(v) for k, v in out.items()}
    check("F1 every rendering is valid Atom: declaration first, parsed, the Atom namespace, one id/title/"
          "updated, an author and a self link on the feed, one id/title/updated and a summary per entry, "
          "RFC 3339 dates", all(v[0] for v in ok.values()), str({k: v[1] for k, v in ok.items() if not v[0]}))
    if not all(v[0] for v in ok.values()):
        return
    tool, cap, every = (entries(parse(out[k])) for k in ("tool", "tool_cap", "all"))
    ids = [e["id"].replace(ORIGIN, "") for e in tool]
    check("F2 a product feed lists only that product's update_entry pages, newest release first, without "
          "archived, feed_hidden, undated or future-dated pages",
          ids == ["/u/tool/r5/", "/u/tool/r4/", "/u/tool/r3/", "/u/tool/r2/", "/u/tool/r1/", "/u/tool/rf/"], str(ids))
    check("F3 the limit is honoured, and counts only listed entries",
          [e["id"].replace(ORIGIN, "") for e in cap] == ["/u/tool/r5/", "/u/tool/r4/"], str([e["id"] for e in cap]))
    check("F4 the every-product feed holds every product's pages, newest release first",
          [e["id"].replace(ORIGIN, "") for e in every][:2] == ["/u/other/x1/", "/u/tool/r5/"] and len(every) == 7,
          str([e["id"] for e in every]))
    by = {e["id"].replace(ORIGIN, ""): e for e in every}
    r5, r4, r3, x1, rf = (by[k] for k in ("/u/tool/r5/", "/u/tool/r4/", "/u/tool/r3/", "/u/other/x1/", "/u/tool/rf/"))
    check("F5 the verdict is the gate's: a scoped WAIT row prints its verdict, scope and line",
          r5["title"] == "Tool r5: WAIT if you use the X plugin" and r5["category"] == "WAIT"
          and r5["summary"].startswith("AUXSAYS verdict: WAIT if you use the X plugin. Two users report X crashes.")
          and "AVOID" not in r5["summary"] and "stored label" not in r5["summary"], json.dumps(r5))
    check("F6 a row the gate refuses (a WAIT with no scope) prints no verdict yet, with the gate's line for "
          "its one report; an official verdict prints with no scope",
          r4["title"] == "Tool r4: no verdict yet" and r4["category"] == "INSUFFICIENT DATA"
          and r4["summary"].startswith("No verdict yet: one user report is matched")
          and "WAIT" not in r4["summary"] and x1["title"] == "Other x1: SECURITY UPDATE"
          and x1["summary"].startswith("AUXSAYS verdict: SECURITY UPDATE. Install it"), json.dumps([r4, x1]))
    check("F7 a zero-report page says no verdict yet and that no report is counted, never a safety claim",
          r3["title"] == "Tool r3: no verdict yet"
          and r3["summary"] == "No verdict yet. No user reports have been counted for this update yet, so there is "
                               "no AUXSAYS verdict. Released Nov 10, 2026.", json.dumps(r3))
    check("F8 an entry's date is its record_last_updated, else (absent, or later than the build) its release "
          "date; published is the release date",
          r5["updated"] == "2026-11-23T09:30:00+00:00" and r5["published"] == "2026-11-20T10:00:00+00:00"
          and r3["updated"] == "2026-11-10T00:00:00+00:00" and rf["updated"] == "2026-10-30T00:00:00+00:00",
          json.dumps([r5, r3, rf]))
    root_tool, root_empty = parse(out["tool"]), parse(out["empty"])
    sub_tool = root_tool.findtext(f"{ATOM}subtitle") or ""
    check("F9 the feed's date is its newest entry's, never the build time while it has entries; an empty "
          "feed (valid, no entry) says no page is listed",
          root_tool.findtext(f"{ATOM}updated") == "2026-11-23T09:30:00+00:00"
          and not root_empty.findall(f"{ATOM}entry")
          and "No patch page is listed" in (root_empty.findtext(f"{ATOM}subtitle") or "")
          and "No patch page is listed" not in sub_tool, root_tool.findtext(f"{ATOM}updated") or "")
    check("F10 the subtitle says an entry is the current verdict, not a change, and that no verdict-change "
          "history is kept", "no history of verdict changes" in sub_tool and "not a change" in sub_tool, sub_tool)
    check("F11 an entry's id is the clean page URL; its link is the page with the feed's utm tags",
          r5["id"] == ORIGIN + "/u/tool/r5/" and r5["href"] == ORIGIN + "/u/tool/r5/" + UTM
          and r5["rel"] == "alternate" and all(e["href"].endswith(UTM) for e in every), json.dumps(r5))
    raw = out["tool"]
    check("F12 text is XML-escaped (a product name with '&' parses and round-trips)",
          "&amp;" not in (root_tool.findtext(f"{ATOM}title") or "")
          and "utm_source=feed&amp;utm_medium=rss" in raw, raw[:300])


def section_l() -> None:
    print("\n[L] the feed layout, rendered from a stub's front matter")
    layout = FEED_LAYOUT.read_text(encoding="utf-8")
    s = site()
    cases = {
        "product": {"template": layout, "site": s, "page": {"url": "/u/tool/feed.xml", "feed_product_id": "tool",
                                                              "feed_alternate": "/u/tool/", "feed_limit": 3}},
        "all": {"template": layout, "site": s, "page": {"url": "/updates/feed.xml", "feed_scope": "all",
                                                          "feed_limit": 50}},
        "neither": {"template": layout, "site": s, "page": {"url": "/x/feed.xml"}},
    }
    out = render_cases(cases)
    if out is None or "__error__" in out or any(str(v).startswith("<<ERR") for v in out.values()):
        check("L1 the shipped feed layout renders under the Liquid gem", False, str(out)[:600])
        return
    prod, every = parse(out["product"]), parse(out["all"])
    check("L1 a product stub renders that product's feed (its pages only): its name from the catalog, its own URL as id and "
          "self, its tracker as alternate, its limit",
          prod is not None and is_valid_atom(out["product"])[0]
          and prod.findtext(f"{ATOM}title") == "AUXSAYS patch verdicts: Tool & Co"
          and prod.findtext(f"{ATOM}id") == ORIGIN + "/u/tool/feed.xml"
          and [l.get("href") for l in prod.findall(f"{ATOM}link") if l.get("rel") == "alternate"] == [ORIGIN + "/u/tool/"]
          and len(prod.findall(f"{ATOM}entry")) == 3
          and all((e.findtext(f"{ATOM}id") or "").startswith(ORIGIN + "/u/tool/") for e in prod.findall(f"{ATOM}entry")),
          out["product"][:400])
    check("L2 the every-product stub renders every product's feed, linked to the Patch Feed",
          every is not None and is_valid_atom(out["all"])[0] and len(every.findall(f"{ATOM}entry")) == 7
          and [l.get("href") for l in every.findall(f"{ATOM}link") if l.get("rel") == "alternate"] == [ORIGIN + "/updates/"],
          out["all"][:400])
    check("L3 a stub with neither a product nor the every-product scope prints nothing", out["neither"].strip() == "",
          out["neither"][:200])


# --------------------------------------------------------------------------- [S] the stubs

def front(path: Path) -> dict:
    m = re.match(r"---\r?\n(.*?)\r?\n---", path.read_text(encoding="utf-8"), re.S)
    return yaml.safe_load(m.group(1)) if m else {}


def section_s() -> None:
    print("\n[S] one feed per product tracker, and one for every product")
    trackers = {}
    for idx in sorted((AUX / "updates").rglob("index.md")):
        fm = front(idx)
        if fm.get("layout") == "aux-patch-product":
            trackers[str(fm.get("product_id"))] = (idx, fm)
    stubs = {}
    every = []
    urls = []
    for path in sorted(AUX.rglob("*.xml")):
        if "_site" in path.parts or "node_modules" in path.parts:
            continue
        fm = front(path)
        if fm.get("layout") != "aux-patch-atom":
            continue
        urls.append(fm.get("permalink"))
        if fm.get("feed_scope") == "all":
            every.append((path, fm))
        else:
            stubs.setdefault(str(fm.get("feed_product_id")), []).append((path, fm))
    check(f"S1 every product tracker has exactly one feed, and every feed belongs to a tracker "
          f"({len(trackers)} trackers)",
          len(trackers) > 0 and sorted(stubs) == sorted(trackers) and all(len(v) == 1 for v in stubs.values()),
          f"missing={sorted(set(trackers) - set(stubs))} orphan={sorted(set(stubs) - set(trackers))}")
    wrong = []
    for pid, (idx, fm) in trackers.items():
        for path, sfm in stubs.get(pid, []):
            perm = fm.get("permalink")
            if (sfm.get("feed_alternate") != perm or sfm.get("permalink") != f"{perm}feed.xml"
                    or path.parent != idx.parent or not isinstance(sfm.get("feed_limit"), int)
                    or sfm.get("sitemap") is not False):
                wrong.append(pid)
    check("S2 each product feed sits beside its tracker, at the tracker's URL + feed.xml, links back to it, "
          "has a numeric limit and is kept out of the sitemap", not wrong, str(wrong))
    check("S3 exactly one every-product feed, at /updates/feed.xml, kept out of the sitemap; no two feeds share "
          "a URL", len(every) == 1 and every[0][1].get("permalink") == "/updates/feed.xml"
          and every[0][1].get("sitemap") is False and len(urls) == len(set(urls)), str(every))
    theme_feed = AUX / "feed.xml"
    check("S4 the theme's /feed.xml (posts) is not shadowed: no repository file claims that URL",
          not theme_feed.exists() and "/feed.xml" not in urls, "")


# --------------------------------------------------------------------------- [A] autodiscovery

def autodiscovery_block() -> str:
    text = BASE_LAYOUT.read_text(encoding="utf-8")
    start = text.find("{%- comment -%}\n      FEED AUTODISCOVERY")
    end = text.find("{%- comment -%} END FEED AUTODISCOVERY")
    return text[start:end] if start >= 0 and end > start else ""


def section_a() -> None:
    print("\n[A] feed autodiscovery in aux-base.html")
    block = autodiscovery_block()
    if not block:
        check("A1 aux-base.html carries the marked autodiscovery block", False, "markers not found")
        return
    s = site()
    no_feeds = site()
    no_feeds["pages"] = [p for p in no_feeds["pages"] if p.get("layout") != "aux-patch-atom"]
    pages = {
        "product": {"layout": "aux-patch-product", "product_id": "tool"},
        "version": {"layout": "aux-patch-version", "product_id": "tool"},
        "patch": {"layout": "aux-update", "product_id": "tool"},
        "patch_nofeed": {"layout": "aux-update", "product_id": "other"},
        "home": {"layout": "aux-home"},
        "patchfeed": {"layout": "aux-updates"},
        "article": {"layout": "aux-post", "product_id": "tool"},
    }
    cases = {k: {"template": block, "site": s, "page": v} for k, v in pages.items()}
    cases["patch_nosite"] = {"template": block, "site": no_feeds, "page": pages["patch"]}
    out = render_cases(cases)
    if out is None or "__error__" in out or any(str(v).startswith("<<ERR") for v in out.values()):
        check("A1 the autodiscovery block renders under the Liquid gem", False, str(out)[:600])
        return

    def links(html: str) -> list[tuple[str, str]]:
        return [(m.group(2), m.group(1)) for m in re.finditer(
            r'<link rel="alternate" type="application/atom\+xml" title="([^"]*)" href="([^"]*)">', html)]

    product_link = (ORIGIN + "/u/tool/feed.xml", "Tool &amp; Co patch verdicts (Atom)")
    all_link = (ORIGIN + "/updates/feed.xml", "AUXSAYS patch verdicts, every product (Atom)")
    check("A1 a product tracker, a version tracker and a patch page name their product's feed (by its catalog "
          "name) and the every-product feed",
          all(links(out[k]) == [product_link, all_link] for k in ("product", "version", "patch")),
          str({k: links(out[k]) for k in ("product", "version", "patch")}))
    check("A2 the homepage and the Patch Feed name the every-product feed only; a patch page whose product has "
          "no feed page names only the every-product feed",
          links(out["home"]) == [all_link] and links(out["patchfeed"]) == [all_link]
          and links(out["patch_nofeed"]) == [all_link], str([links(out[k]) for k in ("home", "patchfeed", "patch_nofeed")]))
    check("A3 any other page names no feed, and with no feed page in the build no page names one",
          links(out["article"]) == [] and links(out["patch_nosite"]) == [] and "<link" not in out["article"],
          str([out["article"][:200], out["patch_nosite"][:200]]))


def run() -> int:
    section_f()
    section_l()
    section_s()
    section_a()
    print()
    print("=" * 96)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed checks:")
        for e in _ERRORS:
            print(f"  - {e}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
