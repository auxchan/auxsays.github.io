#!/usr/bin/env python3
"""The homepage stays small, and its Patch Signals are the ones the old ranking chose (GROWTH-1A).

WHY IT EXISTS. The homepage picked one "Patch Signal" per product with a loop nested inside a
loop over the whole patch collection, and every inner pass printed its own indentation. On the
1,426 visible records that made the live homepage 124,107,478 bytes (1.3 MB gzipped), almost all
of it blank space, with the first signal link at byte 4,079,213. Search crawlers stop reading a
page's HTML at 2 MB, so they never saw one signal. The selection now groups the records once and
scores each group once, inside a capture that prints nothing.

WHAT IS PINNED HERE.
  [H] the render bridge: ruby and the liquid gem are present (a missing gem FAILS, never skips),
      and the hand-registered Jekyll filters behave as jekyll-4.4.1's do on probes that matter
      here (group_by_exp over a filter chain, first-appearance group order, push, nil-first sort).
  [P] parity with a REFERENCE ORACLE: the old nested loop, frozen verbatim from origin/main
      01734ea6 in fixtures/homepage_signals/nested_loop_reference.liquid, and the shipped
      selection are rendered over the same records -- synthetic corpora that reach every
      ranking branch (featured, report, official issue, known issue, certified live and pilot
      rungs, an exact score tie, identity fallbacks and case folding, archived and hidden
      records, the 10-row limit, the empty state) and the real record corpus -- and must emit
      the same rows: destination, product id and title, in the same order. (The words printed
      beside the title changed in GROWTH-1C and are held by [V], not by the frozen loop.)
  [B] the size budget at the real corpus size: the whole homepage (aux-home inside aux-base)
      renders under HOME_BYTE_CEILING with the first signal inside the first 50 KB, and the
      layout keeps no loop over the patch list nested inside another.
  [I] the product identity is written twice (grouping and display) and the two are identical.
  [D] Direction A: one h1 asking the patch question, a heading outline that never skips a level,
      the hero's entrances, one link to every product tracker that has records (derived from the
      records, not typed), the signals in the main column ahead of everything else, the primary
      nav keeping every route, and no certainty word in the copy written around the signal rows.
  [V] GROWTH-1C: each row prints its patch page's OWN verdict and evidence state. The patch page's
      rung and decision ladder live in _includes/patch-evidence-state.html and patch-decision.html,
      which aux-update.html and this homepage both render; the shipped patch page and the homepage
      are rendered over the same records (every ladder branch: stored, legacy, refused, derived,
      the official-only rescue, nothing captured, certified and uncertified live) and must agree,
      with the expected words written out. No row prints the stored sentiment
      (update_consensus_label), counted reports read "N user reports counted for this release",
      and neither layout keeps a verdict or evidence-state decision of its own.
  [T] GROWTH-1C: each product tracker names, inside its one link, the source its updates come from
      (the product's own source_label); and every signal row sits under a tracker the page links.

Needs ruby + the liquid gem (CI installs liquid 4.0.4); without them the render checks FAIL.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_homepage_signals.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import traceback
from html.parser import HTMLParser
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_LAYOUTS = _AUX / "_layouts"
_INCLUDES = _AUX / "_includes"
HOME_LAYOUT = _LAYOUTS / "aux-home.html"
BASE_LAYOUT = _LAYOUTS / "aux-base.html"
REFERENCE = Path(__file__).resolve().parent / "fixtures" / "homepage_signals" / "nested_loop_reference.liquid"
REFERENCE_SHA256 = "f7232be0faefea8ddf27eab11eaa04653da42f7cf42aeaee83d935cde5e10025"

# Google stops reading a page's HTML after 2 MB; the GROWTH-1A contract is under 200 KB. The real
# build emits jekyll-seo-tag output that this bridge stubs, so the bridge keeps SEO_ALLOWANCE spare.
HOME_BYTE_CEILING = 200_000
SEO_ALLOWANCE = 8_000
FIRST_SIGNAL_CEILING = 50_000
FIXED_TIME = "2026-11-06T12:00:00Z"

BLOCK_START = "{% assign all_update_pages"
BLOCK_END = "{% if home_patch_count == 0 %}"
COMMENT_RE = re.compile(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", re.S)
IDENTITY_RE = re.compile(r"item\.product_id \| default: item\.update_brand_id \| default: "
                         r"item\.update_product \| default: item\.url \| downcase(?: \| replace: '[^']*', '[^']*')+")

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
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


# ------------------------------------------------------------------------------- liquid bridge
# Jekyll is not installed in CI; the liquid gem is. The Jekyll-only filters these layouts use are
# registered by hand below, ported from jekyll-4.4.1 (lib/jekyll/filters.rb and
# filters/grouping_filters.rb, MIT) with item_property reduced to the Hash case this bridge feeds.
_DRIVER = r"""
require 'liquid'
require 'json'
require 'time'

Liquid::Template.error_mode = :warn

module JekyllPorts
  INTEGER_LIKE = /\A\s*-?\d+\s*\z/
  FLOAT_LIKE = /\A\s*-?(?:\d+\.?\d*|\.\d+)\s*\z/

  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def absolute_url(i) = "https://auxsays.com/" + i.to_s.sub(%r{\A/}, "")

  def where(input, property, value)
    return input if !property || value.is_a?(Array) || value.is_a?(Hash)
    return input unless input.respond_to?(:select)
    input = input.values if input.is_a?(Hash)
    input.select { |object| jk_compare(jk_prop(object, property), value) }.to_a
  end

  def where_exp(input, variable, expression)
    return input unless input.respond_to?(:select)
    input = input.values if input.is_a?(Hash)
    condition = jk_parse_condition(expression)
    @context.stack do
      input.select do |object|
        @context[variable] = object
        condition.evaluate(@context)
      end
    end || []
  end

  def group_by_exp(input, variable, expression)
    return input unless input.respond_to?(:group_by)
    parsed_expr = Liquid::Variable.new(expression, Liquid::ParseContext.new)
    @context.stack do
      groups = input.group_by do |item|
        @context[variable] = item
        parsed_expr.render(@context)
      end
      groups.each_with_object([]) do |item, array|
        array << { "name" => item.first, "items" => item.last, "size" => item.last.size }
      end
    end
  end

  def group_by(input, property)
    return input unless input.respond_to?(:group_by)
    groups = input.group_by { |item| jk_prop(item, property).to_s }
    groups.each_with_object([]) do |item, array|
      array << { "name" => item.first, "items" => item.last, "size" => item.last.size }
    end
  end

  def push(array, input)
    return array unless array.is_a?(Array)
    new_ary = array.dup
    new_ary.push(input)
    new_ary
  end

  def sort(input, property = nil, nils = "first")
    raise ArgumentError, "Cannot sort a null object." if input.nil?
    return input.sort if property.nil?
    order = nils == "last" ? 1 : -1
    input.map { |item| [jk_sort_value(jk_prop(item, property)), item] }
      .sort! do |a_info, b_info|
        a_property = a_info.first
        b_property = b_info.first
        if !a_property.nil? && b_property.nil?
          - order
        elsif a_property.nil? && !b_property.nil?
          + order
        else
          a_property <=> b_property || a_property.to_s <=> b_property.to_s
        end
      end
      .map!(&:last)
  end

  private

  def jk_prop(item, property)
    item.respond_to?(:[]) && !item.is_a?(String) ? item[property.to_s] : nil
  end

  def jk_sort_value(value)
    s = value.to_s
    return value.to_i if INTEGER_LIKE.match?(s)
    return value.to_f if FLOAT_LIKE.match?(s)
    value
  end

  def jk_compare(property, target)
    case target
    when NilClass
      return true if property.nil?
    else
      target = target.to_s
      if property.is_a? String
        return true if property == target
      else
        Array(property).each { |prop| return true if prop.to_s == target }
      end
    end
    false
  end

  def jk_parse_condition(exp)
    parser = Liquid::Parser.new(exp)
    condition = jk_parse_binary_comparison(parser)
    parser.consume(:end_of_string)
    condition
  end

  def jk_parse_binary_comparison(parser)
    condition = jk_parse_comparison(parser)
    first_condition = condition
    while (binary_operator = parser.id?("and") || parser.id?("or"))
      child_condition = jk_parse_comparison(parser)
      condition.send(binary_operator, child_condition)
      condition = child_condition
    end
    first_condition
  end

  def jk_parse_comparison(parser)
    left_operand = Liquid::Expression.parse(parser.expression)
    operator = parser.consume?(:comparison)
    return Liquid::Condition.new(left_operand) unless operator
    Liquid::Condition.new(left_operand, operator, Liquid::Expression.parse(parser.expression))
  end
end
Liquid::Template.register_filter(JekyllPorts)

# Jekyll's include tag, not Liquid's: the filename carries a dot and params arrive as key=value.
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
    raise Liquid::FileSystemError, "missing include #{@file}" unless File.exist?(path)
    vals = {}
    @params.each do |k, v|
      vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v]
    end
    partial = (context.registers[:cache] ||= {})[path] ||=
      Liquid::Template.parse(File.read(path, encoding: "utf-8"))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)

# jekyll-seo-tag is a plugin. Stubbed; HOME_BYTE_CEILING keeps an allowance for its real output.
class SeoStub < Liquid::Tag
  def render(_ctx) = ""
end
Liquid::Template.register_tag("seo", SeoStub)

payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
corpora = payload["corpora"]
out = {}
payload["jobs"].each do |name, job|
  started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
  begin
    site = job["site"].merge("pages" => corpora.fetch(job["corpus"]))
    vars = { "site" => site, "page" => job["page"] || {} }
    regs = { include_root: payload["includes"] }
    html = Liquid::Template.parse(job["template"]).render!(vars, registers: regs)
    if job["base"]
      html = Liquid::Template.parse(job["base"]).render!(vars.merge("content" => html), registers: regs)
    end
    out[name] = { "html" => html }
  rescue => e
    out[name] = { "html" => "<<ERR: #{e.class}: #{e.message}>>" }
  end
  out[name]["seconds"] = Process.clock_gettime(Process::CLOCK_MONOTONIC) - started
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""


def render(jobs: dict, corpora: dict, timeout: int = 900) -> dict:
    """{name: {"html", "seconds"}}. Each job: template, site, corpus name, optional base/page.
    A missing ruby/gem yields an error string per job, so every check runs and fails."""
    ruby = shutil.which("ruby")
    if not ruby:
        return {name: {"html": "<<ERR: ruby is not on PATH>>", "seconds": 0} for name in jobs}
    with tempfile.TemporaryDirectory(prefix="auxsays-home-") as td:
        script, payload, result = Path(td) / "d.rb", Path(td) / "p.json", Path(td) / "r.json"
        script.write_text(_DRIVER, encoding="utf-8")
        payload.write_text(json.dumps({"jobs": jobs, "corpora": corpora, "includes": str(_INCLUDES)},
                                      default=str), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(result)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode != 0 or not result.exists():
            err = f"<<ERR: exit {proc.returncode}: {(proc.stderr or '')[-400:]}>>"
            return {name: {"html": err, "seconds": 0} for name in jobs}
        return json.loads(result.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------- inputs
def body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("---", 2)[2] if text.startswith("---") else text


def shipped_block() -> str:
    src = body(HOME_LAYOUT)
    start, end = src.find(BLOCK_START), src.find(BLOCK_END)
    if start < 0 or end < start:
        raise AssertionError("aux-home.html no longer carries the Patch Signals block markers")
    return src[start:end]


def reference_block() -> str:
    return REFERENCE.read_text(encoding="utf-8")


TRAILER = "{% if home_patch_count == 0 %}<p data-empty-state>EMPTY</p>{% endif %}"


# Jekyll's own front-matter boundary (Document::YAML_FRONT_MATTER_REGEXP): the block ends at a line
# that is exactly --- or ..., so a record whose release notes contain "---" is still read whole.
# Splitting on the first two "---" instead silently dropped 9 real records.
FRONT_MATTER = re.compile(r"\A---\s*\r?\n(.*?\r?\n?)^(?:---|\.\.\.)\s*$", re.S | re.M)


def load_front_matter(path: Path) -> dict | None:
    match = FRONT_MATTER.match(path.read_text(encoding="utf-8", errors="replace"))
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except Exception:  # noqa: BLE001 -- a page Jekyll would also reject is not a patch record
        return None
    return data if isinstance(data, dict) else None


def real_corpus() -> list[dict]:
    """Every page Jekyll would treat as a patch record, with the url its permalink gives it."""
    pages = []
    skip = {"_site", "node_modules", "_layouts", "_includes", "_posts", "_data", "scripts", "tools", "vendor"}
    for path in sorted(list(_AUX.rglob("*.md")) + list(_AUX.rglob("*.html"))):
        if skip & set(path.relative_to(_AUX).parts):
            continue
        fm = load_front_matter(path)
        if fm and fm.get("update_entry") is True and fm.get("permalink"):
            fm["url"] = fm["permalink"]
            pages.append(fm)
    return pages


def real_site() -> dict:
    config = yaml.safe_load((_AUX / "_config.yml").read_text(encoding="utf-8"))
    data = {"home": json.loads((_AUX / "_data" / "home.json").read_text(encoding="utf-8")),
            "patch_products": yaml.safe_load((_AUX / "_data" / "patch_products.yml").read_text(encoding="utf-8")),
            "patch_verdicts": yaml.safe_load((_AUX / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8"))}
    posts = []
    for path in sorted((_AUX / "_posts").glob("*.md"), reverse=True):
        fm = load_front_matter(path) or {}
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)
        fm.setdefault("date", path.stem[:10])
        fm["url"] = f"/articles/{slug}/"
        posts.append(fm)
    return {"title": config.get("title"), "tagline": config.get("tagline"), "time": FIXED_TIME,
            "data": data, "posts": posts}


# ------------------------------------------------------------------------------- synthetic corpora
DAY = 86_400


def iso(epoch: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


BASE_T = 1_790_000_000  # 2026-09-21


def rec(slug: str, t: int | None, **fields) -> dict:
    page = {"layout": "aux-update", "update_entry": True, "url": f"/updates/t/{slug}/",
            "title": f"Title {slug}", "update_feed_title": f"Feed {slug}", "update_status": "current",
            "evidence_state": "official_only", "intelligence_stage": "official_live",
            "update_report_count": 0, "confirmed_patch_specific_report_count": 0}
    if t is not None:
        page["update_published_at"] = iso(t)
    page.update(fields)
    return page


def ranking_corpus() -> list[dict]:
    t = BASE_T
    reports = {"update_report_count": 3, "evidence_state": "pilot_sample", "intelligence_stage": "pilot",
               "update_consensus_label": "Negative"}
    return [
        # featured beats newer and stronger records of the same product
        rec("a-new-official", t - 1 * DAY, product_id="prod-a"),
        rec("a-reports", t - 2 * DAY, product_id="prod-a", **reports),
        rec("a-featured", t - 30 * DAY, product_id="prod-a", homepage_featured=True),
        # report signal (+250000) beats a known issue (+200000) only when they are close in time
        rec("b-known-new", t - 3 * DAY, product_id="prod-b", known_issues_present="yes"),
        rec("b-reports-close", t - 3 * DAY - 40_000, product_id="prod-b", update_report_count=2),
        rec("c-known-new", t - 4 * DAY, product_id="prod-c", known_issues_present=True),
        rec("c-reports-far", t - 9 * DAY, product_id="prod-c", confirmed_patch_specific_report_count=4),
        # official Microsoft issue (+220000) and safeguard holds
        rec("d-official", t - 5 * DAY, product_id="prod-d", official_active_issue_count=2,
            official_safeguard_hold_count=1),
        rec("d-plain-newer", t - 5 * DAY + 1000, product_id="prod-d"),
        # certified live (rank 2) vs pilot (rank 1) vs an uncertified live claim (ranks as pilot)
        # (live: +300000 rank +250000 reports +50000 stage -100000 age = +500000 > pilot's +450000;
        #  uncertified it ranks as pilot: +350000 < +450000)
        rec("e-live", t - 6 * DAY - 100_000, product_id="prod-e", evidence_state="consensus_live",
            intelligence_stage="consensus_live", update_report_count=9),
        rec("e-pilot", t - 6 * DAY, product_id="prod-e", **reports),
        rec("f-claim-uncertified", t - 7 * DAY - 100_000, product_id="prod-f",
            consensus_collection_status="consensus_live", update_report_count=5),
        rec("f-pilot", t - 7 * DAY, product_id="prod-f", **reports),
        # an EXACT score tie with distinct dates: newer by 50000 s vs older + pilot stage (+50000).
        # The strict greater-than keeps the first in feed order (the newer one).
        rec("g-tie-newer", t - 8 * DAY, product_id="prod-g", update_report_count=1),
        rec("g-tie-older-pilot", t - 8 * DAY - 50_000, product_id="prod-g", update_report_count=1,
            intelligence_stage="pilot"),
        # excluded populations
        rec("l-archived", t, product_id="prod-l", update_status="archived", homepage_featured=True),
        rec("m-hidden", t, product_id="prod-m", feed_hidden=True, **reports),
        rec("n-not-entry", t, product_id="prod-n", update_entry=False, **reports),
        # nothing meaningful at all: no row for this product
        rec("o-official-1", t - 1, product_id="prod-o"),
        rec("o-official-2", t - 2, product_id="prod-o"),
    ]


def fallback_corpus() -> list[dict]:
    """Identity fallbacks, case folding, a missing date, an older winner and YAML-string values."""
    t = BASE_T
    reports = {"update_report_count": 3, "evidence_state": "pilot_sample", "intelligence_stage": "pilot",
               "update_consensus_label": "Negative"}
    return [
        # identity fallbacks and case folding
        rec("h-brand", t - 10 * DAY, update_brand_id="Brand-H", **reports),
        rec("h-brand-lower", t - 10 * DAY - 10, update_brand_id="brand-h", update_report_count=7),
        rec("i-product-name", t - 11 * DAY, update_product="Product I Name", **reports),
        rec("j-url-only", t - 12 * DAY, **reports),
        rec("k-mixed-case", t - 13 * DAY, product_id="PROD-K", **reports),
        rec("k-lower", t - 13 * DAY + 5, product_id="prod-k"),
        # no update_published_at: sorts to the end of the feed, timestamp falls back
        rec("p-no-date", None, product_id="prod-p", record_last_updated=iso(t - 2 * DAY), **reports),
        # the winner is an OLDER record, so its row sits at the older record's feed position
        rec("q-newest-plain", t + DAY, product_id="prod-q"),
        rec("q-old-reports", t - 40 * DAY, product_id="prod-q", **reports),
        # string-valued counts and booleans as YAML can produce them
        rec("r-strings", t - 14 * DAY, product_id="prod-r", update_report_count="6",
            known_issues_present="true"),
    ]


def limit_corpus() -> list[dict]:
    """Fourteen products with a signal each: only the first 10 in feed order are shown."""
    out = []
    for i in range(14):
        out.append(rec(f"lim-{i:02d}-plain", BASE_T - i * DAY + 500, product_id=f"lim-{i:02d}"))
        out.append(rec(f"lim-{i:02d}-reports", BASE_T - i * DAY, product_id=f"lim-{i:02d}",
                       update_report_count=i + 1))
    return out


def empty_corpus() -> list[dict]:
    return [rec(f"z-{i}", BASE_T - i * DAY, product_id=f"zz-{i % 3}") for i in range(9)]


LIVE_URLS = {"urls": ["/updates/t/e-live/"]}


# ------------------------------------------------------------------------------- row extraction
class Rows(HTMLParser):
    """Signal rows: destination, product id, and the text of each part the row prints."""

    PARTS = {"strong": "title", "data-home-verdict": "verdict", "data-home-evidence-state": "state"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self.depth = 0
        self.empty = False
        self._part: list[tuple[str, str]] = []  # (part, closing tag) while inside a named part

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-empty-state" in a:
            self.empty = True
        if tag == "a" and "data-home-patch-signal" in a:
            self.rows.append({"href": a.get("href"), "pid": a.get("data-product-id"), "text": [],
                              "title": [], "verdict": [], "state": [], "dot": None})
            self.depth = 1
            return
        if tag == "a" and self.depth:
            self.depth += 1
        if not self.depth or not self.rows:
            return
        cls = a.get("class") or ""
        if tag == "span" and "home-patch-dot" in cls.split():
            self.rows[-1]["dot"] = cls
        part = "title" if tag == "strong" else next((v for k, v in self.PARTS.items() if k in a), None)
        if part:
            self._part.append((part, tag))

    def handle_endtag(self, tag):
        if self._part and self._part[-1][1] == tag:
            self._part.pop()
        if tag == "a" and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and self.rows:
            self.rows[-1]["text"].append(data)
            for part, _tag in self._part:
                self.rows[-1][part].append(data)


def _norm(parts) -> str:
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def row_details(html: str) -> list[dict]:
    p = Rows()
    p.feed(html)
    return [{k: (_norm(v) if isinstance(v, list) else v) for k, v in r.items()} for r in p.rows]


def rows_of(html: str) -> tuple[list[tuple], bool]:
    """(destination, product id, title) per row: what the SELECTION decides. The words printed
    beside the title are GROWTH-1C's and are held by [V], not by the frozen loop."""
    p = Rows()
    p.feed(html)
    return [(r["href"], r["pid"], _norm(r["title"])) for r in p.rows], p.empty


# ------------------------------------------------------------------------------- sections
def section_h(out: dict) -> None:
    print("\n[H] the render bridge and its Jekyll filter ports")
    check("H1 ruby is on PATH (the render checks fail without it, they never skip)", shutil.which("ruby") is not None)
    probe = out.get("probe", {}).get("html", "<<missing>>")
    check("H2 the liquid gem renders the probe", not probe.startswith("<<ERR"), probe[:300])
    check("H3 group_by_exp evaluates a filter chain and keeps first-appearance group order",
          "[b:2|a:1|c-d:1]" in probe, probe[:300])
    check("H4 push appends without mutating, and sort puts nil keys first like Jekyll",
          "[push:x,y|orig:x]" in probe and "[sort:nil,1,3]" in probe, probe[:300])
    check("H5 the reference oracle is the frozen origin/main 01734ea6 loop, byte for byte",
          _sha256(REFERENCE) == REFERENCE_SHA256, _sha256(REFERENCE))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


PARITY_CASES = {
    # name: (corpus, live_eligibility or None, expected row count)
    "ranking": ("ranking", LIVE_URLS, 7),
    "ranking without projection": ("ranking", None, 7),
    "fallbacks": ("fallbacks", None, 7),
    "limit": ("limit", None, 10),
    "empty": ("empty", None, 0),
}


def reference_scoring_probe() -> str:
    """The reference's OWN per-record scoring, run once per record (linear, unlike the loop it came
    from): its feed assigns, its candidate identity line and its scoring body, verbatim from the
    frozen fixture, printing what the old selection compared. Python then applies the old loop's
    selection rule (`oracle_rows`), which is the only part this change rewrote."""
    lines = reference_block().split("\n")
    feed, identity, scoring = lines[0:2], lines[27], lines[29:90]
    assert "assign update_pages" in feed[1] and "candidate_product_identity =" in identity, "fixture moved"
    assert "candidate_update_report_count" in scoring[0] and scoring[-1].strip() == "{% endif %}", "fixture moved"
    return "\n".join(feed + ["{% for candidate in update_pages %}", identity] + scoring + [
        "@@ROW {{ candidate.url }}\t{{ candidate_product_identity }}\t{{ candidate_is_meaningful }}\t"
        "{% if candidate_is_meaningful == true %}{{ candidate_score }}{% else %}0{% endif %}",
        "{% endfor %}"])


def oracle_rows(probe_html: str, limit: int = 10) -> list[tuple]:
    """The old nested loop's selection, stated directly: for each record in feed order whose
    product has not produced a row, scan that product for the FIRST record with the strictly
    highest score among meaningful records (initial best 0), and emit the row if this record is
    it and fewer than `limit` rows exist."""
    records = []
    for line in probe_html.split("\n"):
        if line.startswith("@@ROW "):
            url, ident, meaningful, score = line[6:].split("\t")
            records.append((url, ident, meaningful == "true", float(score)))
    best: dict = {}
    for url, ident, meaningful, score in records:
        if meaningful and score > best.get(ident, (0.0, ""))[0]:
            best[ident] = (score, url)
    rows, seen = [], set()
    for url, ident, _m, _s in records:
        if ident in seen:
            continue
        if ident in best and best[ident][1] == url and len(rows) < limit:
            rows.append((url, ident))
            seen.add(ident)
    return rows


def section_p(out: dict, real_count: int) -> None:
    print("\n[P] parity with the reference oracle (the old nested loop, frozen)")
    for name, (_corpus, _live, expected) in PARITY_CASES.items():
        new_html = out.get(f"new:{name}", {}).get("html", "<<missing>>")
        old_html = out.get(f"old:{name}", {}).get("html", "<<missing>>")
        new_rows, new_empty = rows_of(new_html)
        old_rows, old_empty = rows_of(old_html)
        ok_render = not new_html.startswith("<<ERR") and not old_html.startswith("<<ERR")
        check(f"P {name}: both selections render", ok_render, new_html[:200] + " / " + old_html[:200])
        check(f"P {name}: identical rows, order, destinations, product ids and titles ({len(new_rows)} rows)",
              ok_render and new_rows == old_rows and new_empty == old_empty,
              f"new={new_rows[:4]} old={old_rows[:4]}")
        check(f"P {name}: the corpus reaches the case it was built for ({expected} rows"
              f"{', empty state' if expected == 0 else ''})",
              len(new_rows) == expected and (expected > 0 or new_empty), f"{len(new_rows)} rows")
        probe = out.get(f"probe:{name}", {}).get("html", "<<missing>>")
        check(f"P {name}: the per-record oracle agrees with the frozen loop it was taken from",
              oracle_rows(probe) == [(h, pid) for h, pid, _t in old_rows] and not probe.startswith("<<ERR"),
              f"oracle={oracle_rows(probe)[:4]}")

    rows, _ = rows_of(out.get("new:ranking", {}).get("html", ""))
    hrefs = [h for h, _pid, _t in rows]
    pids = [pid for _h, pid, _t in rows]
    check("P branch: featured beats newer and stronger records", "/updates/t/a-featured/" in hrefs, str(hrefs))
    check("P branch: an exact score tie keeps the first record in feed order",
          "/updates/t/g-tie-newer/" in hrefs and "/updates/t/g-tie-older-pilot/" not in hrefs, str(hrefs))
    check("P branch: a certified live claim outranks a newer pilot record", "/updates/t/e-live/" in hrefs, str(hrefs))
    check("P branch: an uncertified live claim ranks as the pilot record it renders as",
          "/updates/t/f-pilot/" in hrefs, str(hrefs))
    check("P branch: a report signal beats a known issue only when they are close in time",
          "/updates/t/b-reports-close/" in hrefs and "/updates/t/c-known-new/" in hrefs, str(hrefs))
    check("P branch: an official Microsoft issue makes an otherwise plain record the signal",
          "/updates/t/d-official/" in hrefs, str(hrefs))
    check("P branch: a product with nothing meaningful gets no row", "prod-o" not in pids, str(pids))
    fb, _ = rows_of(out.get("new:fallbacks", {}).get("html", ""))
    fb_h = [h for h, _pid, _t in fb]
    fb_p = [pid for _h, pid, _t in fb]
    check("P branch: identities fall back brand -> product name -> url and fold case and spaces",
          fb_p.count("brand-h") == 1 and "product-i-name" in fb_p and "-updates-t-j-url-only-" in fb_p
          and fb_p.count("prod-k") == 1 and "PROD-K" not in fb_p, str(fb_p))
    check("P branch: an older winner sits at its own feed position; a dateless record falls back and sorts last",
          fb_h.index("/updates/t/q-old-reports/") > fb_h.index("/updates/t/r-strings/")
          and fb_h[-1] == "/updates/t/p-no-date/", str(fb_h))
    check("P branch: archived, hidden and non-entry records never surface",
          not {"/updates/t/l-archived/", "/updates/t/m-hidden/", "/updates/t/n-not-entry/"} & set(hrefs), str(hrefs))
    rows_np, _ = rows_of(out.get("new:ranking without projection", {}).get("html", ""))
    check("P branch: without the deploy projection the live claim ranks as pilot and loses",
          "/updates/t/e-pilot/" in [h for h, _p, _t in rows_np], str([h for h, _p, _t in rows_np]))
    lim, _ = rows_of(out.get("new:limit", {}).get("html", ""))
    check("P branch: the limit keeps the first 10 products in feed order",
          [pid for _h, pid, _t in lim] == [f"lim-{i:02d}" for i in range(10)], str([pid for _h, pid, _t in lim]))

    real_html = out.get("new:real", {}).get("html", "<<missing>>")
    real_rows, _ = rows_of(real_html)
    real_probe = out.get("probe:real", {}).get("html", "<<missing>>")
    expected = oracle_rows(real_probe)
    check(f"P real corpus ({real_count} records): the shipped selection renders 1..10 rows ({len(real_rows)})",
          1 <= len(real_rows) <= 10 and not real_html.startswith("<<ERR"), real_html[:200])
    check("P real corpus: the rows equal the reference oracle's, in order",
          bool(expected) and [(h, pid) for h, pid, _t in real_rows] == expected,
          f"shipped={[(h, pid) for h, pid, _t in real_rows][:3]} oracle={expected[:3]}")


def section_b(out: dict) -> None:
    print("\n[B] the homepage size budget at the real corpus size")
    page = out.get("page:real", {})
    html = page.get("html", "<<missing>>")
    size = len(html.encode("utf-8"))
    check("B1 the full homepage renders (aux-home inside aux-base, real records)", not html.startswith("<<ERR"),
          html[:300])
    check(f"B2 the homepage is under {HOME_BYTE_CEILING:,} bytes with {SEO_ALLOWANCE:,} spare for the SEO tag "
          f"(rendered {size:,})", size + SEO_ALLOWANCE < HOME_BYTE_CEILING and not html.startswith("<<ERR"))
    at = html.find("data-home-patch-signal")
    check(f"B3 the first signal link is inside the first {FIRST_SIGNAL_CEILING:,} bytes (at {at:,})",
          0 <= at < FIRST_SIGNAL_CEILING)
    emitted = COMMENT_RE.sub("", body(HOME_LAYOUT))
    nested = _nested_update_loops(emitted)
    check("B4 the layout keeps no loop over the patch list nested inside another", not nested, str(nested))


def _nested_update_loops(src: str) -> list[str]:
    """Loops whose collection is update_pages / all_update_pages / site.pages, opened while another
    such loop is still open."""
    stack: list[str] = []
    found: list[str] = []
    for m in re.finditer(r"\{%-?\s*(for\s+\w+\s+in\s+([\w.]+)|endfor)\b[^%]*-?%\}", src):
        if m.group(1) == "endfor":
            if stack:
                stack.pop()
            continue
        coll = m.group(2)
        big = coll in {"update_pages", "all_update_pages", "site.pages"}
        if big and any(stack):
            found.append(m.group(0))
        stack.append(coll if big else "")
    return found


def section_i() -> None:
    print("\n[I] the product identity is one expression, written twice")
    src = COMMENT_RE.sub("", body(HOME_LAYOUT))
    found = IDENTITY_RE.findall(src)
    check("I1 the identity expression appears exactly twice (grouping and display)", len(found) == 2, str(len(found)))
    check("I2 ...and both copies are character-identical", len(set(found)) == 1, str(set(found)))
    check("I3 the grouping uses it inside group_by_exp", re.search(r"group_by_exp: \"item\", \"" + IDENTITY_RE.pattern,
                                                                     src) is not None)


# ------------------------------------------------------------------------------- [D] Direction A
QUESTION = "Should you install this update?"
NO_CERTAINTY = re.compile(r"\b(verified|certified|confirmed|guarantee[ds]?|safe to install|proven)\b", re.I)
PRIMARY_NAV = [("/", "Home"), ("/updates/", "Patch Feed"), ("/systems-monitor/", "Systems Monitor"),
               ("/articles/", "Articles"), ("/about/", "About Aux")]


class Outline(HTMLParser):
    """Headings (level, text) and links (href, text, attrs, inside <nav aria-label=Primary>)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[list] = []
        self.links: list[list] = []
        self._h = None
        self._a: list[int] = []
        self._primary = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "nav" and a.get("aria-label") == "Primary":
            self._primary = 1
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append([int(tag[1]), []])
            self._h = self.headings[-1]
        if tag == "a":
            self.links.append([a.get("href"), [], a, bool(self._primary)])
            self._a.append(len(self.links) - 1)

    def handle_endtag(self, tag):
        if tag == "nav" and self._primary:
            self._primary = 0
        if re.fullmatch(r"h[1-6]", tag):
            self._h = None
        if tag == "a" and self._a:
            self._a.pop()

    def handle_data(self, data):
        if self._h is not None:
            self._h[1].append(data)
        for i in self._a:
            self.links[i][1].append(data)


def product_pages() -> set[str]:
    out = set()
    for path in sorted(_AUX.joinpath("updates").rglob("index.md")):
        fm = load_front_matter(path) or {}
        if fm.get("layout") == "aux-patch-product" and fm.get("permalink"):
            out.add(fm["permalink"])
    return out


def expected_trackers(real: list[dict]) -> list[str]:
    """Product tracker urls the homepage must link: every product with at least one record."""
    products = yaml.safe_load((_AUX / "_data" / "patch_products.yml").read_text(encoding="utf-8"))
    with_records = {str(p.get("product_id")) for p in real}
    return [p["product_url"] for p in products if p.get("id") in with_records]


def section_d(out: dict, real: list[dict]) -> None:
    print("\n[D] Direction A: patch decisions first, every product tracker one click away")
    html = out.get("page:real", {}).get("html", "")
    o = Outline()
    o.feed(html)
    norm = lambda parts: re.sub(r"\s+", " ", "".join(parts)).strip()  # noqa: E731
    h1 = [norm(t) for lvl, t in o.headings if lvl == 1]
    check("D1 exactly one h1, and it asks the patch question", h1 == [QUESTION], str(h1))
    levels = [lvl for lvl, _t in o.headings]
    jumps = [(a, b) for a, b in zip(levels, levels[1:]) if b > a + 1]
    check(f"D2 the heading outline never skips a level ({len(levels)} headings)", levels[:1] == [1] and not jumps,
          f"levels={levels}")
    h2 = [norm(t) for lvl, t in o.headings if lvl == 2]
    want_h2 = ["Tracked software", "Latest patch signals", "U.S. Systems Monitor", "Core Coverage", "Recent Articles"]
    check("D3 the sections are real headings: trackers, signals, then everything else", h2 == want_h2, str(h2))

    links = [(h, norm(t), a, primary) for h, t, a, primary in o.links]
    pos = {m: html.find(m) for m in ("<h1", 'class="home-tracker-link"', "data-home-patch-signal", 'id="home-also-title"',
                                     'id="home-monitor-title"', 'id="home-coverage-title"', 'id="home-articles-title"')}
    order = list(pos.values())
    check("D4 document order: question, trackers, signals, then Systems Monitor, coverage and articles",
          all(v >= 0 for v in order) and order == sorted(order), str(pos))
    hero = html[pos["<h1"]:pos['class="home-tracker-link"']] if min(order) >= 0 else ""
    check("D5 the hero's entrances lead to the Patch Feed, My Patch Stack and the methodology",
          all(f'href="{u}"' in hero for u in ("/updates/", "/updates/my-stack/", "/updates/methodology/")), hero[-600:])

    trackers = [h for h, _t, a, _p in links if "data-home-tracker" in a]
    want = expected_trackers(real)
    check(f"D6 one link per product with records ({len(trackers)} links, {len(want)} products with records)",
          sorted(trackers) == sorted(want) and len(set(trackers)) == len(trackers) and len(want) >= 1,
          f"missing={sorted(set(want) - set(trackers))} extra={sorted(set(trackers) - set(want))}")
    pages = product_pages()
    check("D7 every tracker link is a product page that exists", bool(trackers) and set(trackers) <= pages,
          str(sorted(set(trackers) - pages)))
    lead = ["/updates/microsoft/microsoft-windows-11/", "/updates/obs-project/obs-studio/",
            "/updates/adobe/adobe-premiere-pro/", "/updates/adobe/adobe-acrobat-pro/",
            "/updates/adobe/adobe-acrobat-reader/", "/updates/microsoft/microsoft-teams/",
            "/updates/microsoft/microsoft-powerpoint/", "/updates/blackmagic-design/blackmagic-davinci/"]
    lead_present = [u for u in lead if u in want]
    rest = [u for u in want if u not in lead]
    check("D8 the products the hero names come first, the rest follow in data order",
          trackers == lead_present + rest, str(trackers))

    primary = [(h, t) for h, t, _a, p in links if p]
    check("D9 the primary nav keeps every route, patch work right after Home", primary == PRIMARY_NAV, str(primary))
    check("D10 Systems Monitor and Articles stay reachable from the page body too",
          any(h == "/systems-monitor/" and not p for h, _t, _a, p in links)
          and any(h.startswith("/articles/") and not p for h, _t, _a, p in links))
    # The words inside the signal rows are held by [V]; the copy written around them claims no certainty.
    written = re.sub(r"<a [^>]*data-home-patch-signal.*?</a>", "", html, flags=re.S)
    visible = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", "", written, flags=re.S))
    hits = sorted(set(m.group(0).lower() for m in NO_CERTAINTY.finditer(visible)))
    check("D11 the homepage copy outside the signal rows claims no certainty (verified, confirmed, ...)",
          not hits, str(hits))
    signals_at = html.find("data-home-signal-list")
    column_at = html.find('class="home-signals-column"')
    check("D12 the signal list sits in the main column of the first dashboard, not an aside",
          0 <= column_at < signals_at < pos['id="home-also-title"'], f"column={column_at} list={signals_at}")


# ------------------------------------------------------------------------------- [V] verdict rows
UPDATE_LAYOUT = _LAYOUTS / "aux-update.html"
STATE_INCLUDE = _INCLUDES / "patch-evidence-state.html"
DECISION_INCLUDE = _INCLUDES / "patch-decision.html"
TRACKER_INCLUDE = _INCLUDES / "home-tracker-item.html"
VERDICTS = yaml.safe_load((_AUX / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8"))
PAGE_HEAD_END = "{% assign summary_text"
VERDICT_PROBE = "@@VERDICT[{{ decision_label }}|{{ evidence_state }}|{{ evidence_state_class }}]"
NOTES = "https://vendor.test/release-notes"
SENTIMENT = {"update_consensus_label": "Negative", "community_reaction": "Positive", "current_consensus": "Mixed"}
PILOT = {"evidence_state": "pilot_sample", "intelligence_stage": "pilot"}

# name: (record fields, verdict the patch page prints, its evidence state, its box class).
# Every record is featured and is its own product, so each one is a homepage row. The expected words
# are written out so the page and the row cannot be wrong together.
# GROWTH-3: a STORED label no longer decides the verdict anywhere -- the shared gate decides it from
# the record's facts and the two reviewed fact files -- so every case whose only input is a stored
# WAIT / TEST FIRST now prints INSUFFICIENT DATA on the page AND on the row. Three cases carry the
# facts that do decide: Microsoft's security classification, a supported reason entry (the deploy's
# verdict projection gives it a row), and the same entry with one cited report no longer counted (the
# authority gives no row, so it must fail closed).
REASON_URLS = ["https://reports.test/r1", "https://reports.test/r2"]
VERDICT_FACTS = {
    "verdict_reasons": {"schema_version": 1, "entries": [{
        "id": "v-reasoned:1.0:install", "product_id": "v-reasoned", "update_version": "1.0",
        "verdict": "TEST FIRST", "reason_class": "corroborated_install_problem", "scope": "when installing it",
        "reason": "Two users independently report that installing it fails.",
        "evidence": [{"id": "r1", "source_url": REASON_URLS[0]}, {"id": "r2", "source_url": REASON_URLS[1]}],
        "new_in_this_version": False, "reviewed_at": "2026-11-10", "basis": "test"}, {
        "id": "v-reason-withdrawn:1.0:install", "product_id": "v-reason-withdrawn", "update_version": "1.0",
        "verdict": "TEST FIRST", "reason_class": "corroborated_install_problem", "scope": "when installing it",
        "reason": "Two users independently report that installing it fails.",
        "evidence": [{"id": "r1", "source_url": REASON_URLS[0]}, {"id": "r2", "source_url": REASON_URLS[1]}],
        "new_in_this_version": False, "reviewed_at": "2026-11-10", "basis": "test"}]},
    "patch_lifecycle": {"schema_version": 1, "entries": []},
}


def _verdict_projection() -> dict:
    """The projection a deploy would build for these cases: lib/verdict_projection over the cases'
    COUNTED rows. The gate prints only this; it never reads the reason file (review 1, D2). The
    withdrawn case has one of its two cited rows counted, so the authority gives it no row."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lib import verdict_projection  # noqa: PLC0415
    rows = [{"id": "r1", "source_url": REASON_URLS[0], "report_text_excerpt": "Installing it fails at 40%."},
            {"id": "r2", "source_url": REASON_URLS[1], "report_text_excerpt": "The installer stops with an error."}]
    pages = [{"product_id": f"v-{n}", "update_version": "1.0", "update_report_count": c,
              "permalink": f"/updates/t/v-{n}/"} for n, c in (("reasoned", 2), ("reason-withdrawn", 1))]
    counted = {("v-reasoned", "1.0", ""): rows, ("v-reason-withdrawn", "1.0", ""): rows[:1]}
    return verdict_projection.project(pages, counted, VERDICT_FACTS["verdict_reasons"]["entries"], [])[0]


VERDICT_FACTS["verdict_projection"] = _verdict_projection()
ROW_SCOPE = {"reasoned": "when installing it"}
VERDICT_CASES = {
    "stored-wait": (dict(update_decision_label="WAIT", update_report_count=5, **PILOT, **SENTIMENT),
                    "INSUFFICIENT DATA", "Verified reports", "pilot"),
    "test-first": (dict(update_decision_label="TEST FIRST", update_report_count=1, **PILOT),
                   "INSUFFICIENT DATA", "Verified reports", "pilot"),
    "legacy-phrase": (dict(update_decision_label="WAIT for production systems", update_report_count=4, **PILOT),
                      "INSUFFICIENT DATA", "Verified reports", "pilot"),
    "refused-label": (dict(update_decision_label="SHIP IT", update_report_count=4, **PILOT),
                      "INSUFFICIENT DATA", "Verified reports", "pilot"),
    "from-summary": (dict(update_decision_label="", update_consensus_summary="TEST FIRST: early reports",
                          update_report_count=2, **PILOT), "INSUFFICIENT DATA", "Verified reports", "pilot"),
    "from-quick-verdict": (dict(update_decision_label="", update_consensus_summary="", quick_verdict="WAIT: hold off",
                                update_report_count=2, **PILOT), "INSUFFICIENT DATA", "Verified reports", "pilot"),
    "official-rescue": (dict(update_decision_label="WAIT", update_source_url=NOTES, official_active_issue_count=1,
                             **SENTIMENT), "INSUFFICIENT DATA", "Official source only", "official"),
    "security-rescue": (dict(update_decision_label="", update_security_sensitive=True,
                             official_patch_notes_body="Security fixes.", official_safeguard_hold_count=1),
                        "INSUFFICIENT DATA", "Official source only", "official"),
    # Nothing official was captured, so the page's own rung says Insufficient data -- not the stored
    # official_only the maturity contract alone would print -- and the stored WAIT is not rescued.
    "nothing-captured": (dict(update_decision_label="WAIT", known_issues_present=True),
                         "INSUFFICIENT DATA", "Insufficient data", "insufficient"),
    "certified-live": (dict(update_decision_label="WAIT", update_report_count=9, evidence_state="consensus_live",
                            intelligence_stage="consensus_live"), "INSUFFICIENT DATA", "Live consensus", "live"),
    "uncertified-live": (dict(update_decision_label="TEST FIRST", update_report_count=6,
                              consensus_collection_status="consensus_live"), "INSUFFICIENT DATA", "Verified reports", "pilot"),
    "reasoned": (dict(update_decision_label="", update_version="1.0", update_report_count=2, **PILOT,
                      accepted_report_sources=[{"source_url": u} for u in REASON_URLS]),
                 "TEST FIRST", "Verified reports", "pilot"),
    "reason-withdrawn": (dict(update_decision_label="TEST FIRST", update_version="1.0", update_report_count=1, **PILOT,
                              accepted_report_sources=[{"source_url": REASON_URLS[0]}]),
                         "INSUFFICIENT DATA", "Verified reports", "pilot"),
    "security": (dict(update_decision_label="WAIT", update_type="2026-01 B", update_report_count=3, **PILOT,
                      product_id="microsoft-windows-11"), "SECURITY UPDATE", "Verified reports", "pilot"),
}
VERDICT_LIVE = {"urls": ["/updates/t/v-certified-live/"]}


def verdict_records() -> list[list[dict]]:
    """The cases as homepage corpora of at most 10 products each (the row limit)."""
    recs = [rec(f"v-{name}", BASE_T - i * DAY, **{"product_id": f"v-{name}", "homepage_featured": True, **fields})
            for i, (name, (fields, _v, _s, _c)) in enumerate(VERDICT_CASES.items())]
    return [recs[:7], recs[7:]]


def page_head() -> str:
    src = body(UPDATE_LAYOUT)
    end = src.find(PAGE_HEAD_END)
    if end < 0:
        raise AssertionError("aux-update.html no longer carries the summary_text marker after its verdict")
    return src[:end] + VERDICT_PROBE


def page_verdict(html: str) -> tuple | None:
    m = re.search(r"@@VERDICT\[(.*?)\|(.*?)\|(.*?)\]", html)
    return m.groups() if m else None


def section_v(out: dict) -> None:
    print("\n[V] each signal row prints its patch page's own verdict and evidence state")
    rows = {}
    for i in range(2):
        for r in row_details(out.get(f"verdict:home:{i}", {}).get("html", "")):
            rows[r["href"]] = r
    pages, rendered, wrong_page, wrong_row, wrong_state = {}, True, [], [], []
    for name, (_f, verdict, state, cls) in VERDICT_CASES.items():
        html = out.get(f"verdict:page:{name}", {}).get("html", "<<missing>>")
        rendered = rendered and not html.startswith("<<ERR")
        got = page_verdict(html)
        pages[name] = got
        if got != (verdict, state, cls):
            wrong_page.append((name, got))
        row = rows.get(f"/updates/t/v-{name}/")
        scope = ROW_SCOPE.get(name, "")
        if not row or row["verdict"] != f"Verdict: {verdict}" + (f" {scope}" if scope else ""):
            wrong_row.append((name, row and row["verdict"]))
        if not row or row["state"] != state or (row["dot"] or "").split()[-1:] != [f"home-patch-dot--{cls}"]:
            wrong_state.append((name, row and (row["state"], row["dot"])))
    n = len(VERDICT_CASES)
    check(f"V1 the shipped patch page renders each case's verdict and evidence state ({n} cases)",
          rendered and not wrong_page, str(wrong_page)[:600])
    check(f"V2 every homepage row prints the verdict its patch page prints ({len(rows)} rows)",
          len(rows) == n and not wrong_row, str(wrong_row)[:600])
    check("V3 ...and the page's evidence state, with the dot in that state's class",
          len(rows) == n and not wrong_state, str(wrong_state)[:600])

    texts = [r["text"] for r in rows.values()]
    sentiment = sorted({w for t in texts for w in ("Negative", "Positive", "Mixed") if w in t})
    home = COMMENT_RE.sub("", body(HOME_LAYOUT))
    legacy = [f for f in ("update_consensus_label", "community_reaction", "current_consensus", "consensus_key")
              if f in home]
    check("V4 no row prints the stored sentiment, and the homepage no longer reads it",
          len(texts) == n and not sentiment and not legacy, f"printed={sentiment} read={legacy}")

    counted = {name: rows.get(f"/updates/t/v-{name}/", {}).get("text", "") for name in ("stored-wait", "test-first")}
    real_html = out.get("page:real", {}).get("html", "")
    causal = re.compile(r"\b(confirmed|caused|causes|broke|breaks|due to|because of)\b", re.I)
    check("V5 counted reports read 'N user reports counted for this release' (singular at 1)",
          "• 5 user reports counted for this release" in counted["stored-wait"]
          and "• 1 user report counted for this release" in counted["test-first"], str(counted))
    real_rows = row_details(real_html)
    hits = sorted({m.group(0).lower() for r in real_rows + list(rows.values()) for m in causal.finditer(r["text"])})
    check("V6 no row on the real or synthetic homepage claims confirmation or causation, and the old phrase is gone",
          bool(real_rows) and not hits and "confirmed community report" not in real_html, str(hits))

    inc = re.findall(r"\{%-?\s*include\s+(patch-evidence-state|patch-decision)\.html\s+record=(\w+)\s*-?%\}", home)
    capture = re.search(r"\{%-?\s*capture\s+\w+\s*-?%\}\{% include patch-evidence-state\.html record=item %\}"
                        r"\{% include patch-decision\.html record=item %\}\{%-?\s*endcapture\s*-?%\}", home)
    check("V7 the homepage renders the verdict through the patch page's two includes, once, inside a capture",
          sorted(inc) == [("patch-decision", "item"), ("patch-evidence-state", "item")] and capture is not None,
          str(inc))
    own = [t for t in ("update_decision_label", "update_consensus_summary", "quick_verdict", "patch_verdicts",
                       "'INSUFFICIENT DATA'", "'Official source only'", "'Verified reports'", "'Live consensus'",
                       "assign decision_label", "assign evidence_state") if t in home]
    check("V8 the homepage decides no verdict or evidence state of its own (no ladder input, word or assignment)",
          not own, str(own))
    upd = COMMENT_RE.sub("", body(UPDATE_LAYOUT))
    upd_inc = re.findall(r"\{%-?\s*include\s+(patch-evidence-state|patch-decision)\.html\s+record=(\w+)\s*-?%\}", upd)
    upd_own = [t for t in ("assign decision_label", "assign evidence_state", "assign official_captured",
                           "update_consensus_summary", "verdict_vocab") if t in upd]
    check("V9 the patch page decides through the same two includes, once each, and keeps no copy of either",
          sorted(upd_inc) == [("patch-decision", "page"), ("patch-evidence-state", "page")] and not upd_own,
          f"includes={upd_inc} own={upd_own}")
    page_lines = [ln.strip() for ln in upd.split("\n")]
    want = ["{% assign report_count = page.update_report_count | default: 0 | plus: 0 %}",
            "{% assign confirmed_report_count = page.confirmed_patch_specific_report_count | default: report_count | plus: 0 %}",
            "{% assign report_bearing_count = report_count %}",
            "{% if report_bearing_count == 0 and confirmed_report_count > 0 %}{% assign report_bearing_count = confirmed_report_count %}{% endif %}"]
    home_lines = [ln.strip() for ln in home.split("\n")]
    missing = [w for w in want if w not in page_lines or w.replace("page.", "item.") not in home_lines]
    check("V10 the counts the decision reads are set on the homepage by the patch page's own lines (page as item)",
          not missing, str(missing))
    silent = {k: out.get(f"verdict:silent:{k}", {}).get("html", "<<missing>>") for k in ("state", "decision")}
    check("V11 both includes print nothing but whitespace, so no stray text reaches a patch page",
          all(v.startswith("[") and v.endswith("]") and not v[1:-1].strip() for v in silent.values()),
          str({k: v[:120] for k, v in silent.items()}))


def section_t(out: dict, real: list[dict]) -> None:
    print("\n[T] each product tracker says where its updates come from")
    html = out.get("page:real", {}).get("html", "")
    products = {p["product_url"]: p for p in yaml.safe_load((_AUX / "_data" / "patch_products.yml")
                                                           .read_text(encoding="utf-8"))}
    items = re.findall(r'<li class="home-tracker-item">(.*?)</li>', html, re.S)
    chip = re.compile(r'<a class="home-tracker-link" href="([^"]+)" data-home-tracker><span class="home-tracker-name">'
                      r'([^<]*)</span><span class="home-tracker-desc" data-home-tracker-desc>([^<]*)</span></a>')
    wrong, outside = [], []
    for item in items:
        m = chip.fullmatch(item.strip())
        if not m:
            outside.append(item.strip()[:160])
            continue
        product = products.get(m.group(1)) or {}
        if m.group(2) != product.get("product_name") or m.group(3) != str(product.get("source_label") or "").strip():
            wrong.append(m.groups())
    want = expected_trackers(real)
    check(f"T1 every tracker names its product and, under it, the source_label the product data gives it "
          f"({len(items)} trackers)", len(items) == len(want) and not wrong and not outside, str(wrong)[:400])
    check("T2 ...inside the one link to the product page, so it adds no second target and no text outside it",
          bool(items) and not outside, str(outside)[:300])
    none = out.get("tracker:no-source", {}).get("html", "<<missing>>")
    check("T3 a product with no source_label shows its name alone, rather than an invented line",
          re.fullmatch(r'<a class="home-tracker-link" href="/updates/x/x/" data-home-tracker>'
                       r'<span class="home-tracker-name">X</span></a>', none.strip()) is not None, none[:300])
    rows = [r["href"] for r in row_details(html)]
    trackers = re.findall(r'<a class="home-tracker-link" href="([^"]+)"', html)
    orphans = [h for h in rows if not any(h.startswith(t) and h != t for t in trackers)]
    check("T4 every signal row's patch page sits under a product tracker the homepage links "
          "(home -> product -> exact patch)", bool(rows) and not orphans, str(orphans))


def verdict_jobs() -> tuple[dict, dict]:
    """Render jobs and corpora for [V] and [T]."""
    site = {"data": {"patch_verdicts": VERDICTS, "live_eligibility": VERDICT_LIVE, **VERDICT_FACTS},
            "time": FIXED_TIME}
    jobs, corpora = {}, {}
    block = shipped_block() + TRAILER
    for i, recs in enumerate(verdict_records()):
        corpora[f"verdict:{i}"] = recs
        jobs[f"verdict:home:{i}"] = {"template": block, "corpus": f"verdict:{i}", "site": site}
    head = page_head()
    for i, recs in enumerate(verdict_records()):
        for r in recs:
            name = r["url"].split("/")[-2][2:]
            jobs[f"verdict:page:{name}"] = {"template": head, "corpus": "none", "site": site, "page": r}
    some = verdict_records()[0][0]
    jobs["verdict:silent:state"] = {"template": "[{% include patch-evidence-state.html record=page %}]",
                                    "corpus": "none", "site": site, "page": some}
    jobs["verdict:silent:decision"] = {
        "template": "{% capture pre %}{% include patch-evidence-state.html record=page %}{% endcapture %}"
                    "{% assign report_count = 5 %}{% assign report_bearing_count = 5 %}"
                    "[{% include patch-decision.html record=page %}]",
        "corpus": "none", "site": site, "page": some}
    jobs["tracker:no-source"] = {"template": "{% include home-tracker-item.html tracker=page %}", "corpus": "none",
                                 "site": site, "page": {"id": "x", "product_name": "X", "product_url": "/updates/x/x/"}}
    return jobs, corpora


PROBE = ("{% assign g = list | group_by_exp: \"x\", \"x.k | downcase | replace: ' ', '-'\" %}"
         "[{% for e in g %}{{ e.name }}:{{ e.size }}{% unless forloop.last %}|{% endunless %}{% endfor %}]"
         "{% assign one = 'x' | split: ',' %}{% assign two = one | push: 'y' %}"
         "[push:{{ two | join: ',' }}|orig:{{ one | join: ',' }}]"
         "{% assign s = nums | sort: 'n' %}[sort:{% for e in s %}{{ e.n | default: 'nil' }}"
         "{% unless forloop.last %},{% endunless %}{% endfor %}]")


def main() -> int:
    started = time.time()
    real = real_corpus()
    corpora = {"real": real, "ranking": ranking_corpus(), "fallbacks": fallback_corpus(),
               "limit": limit_corpus(), "empty": empty_corpus(),
               "none": []}
    jobs: dict = {"probe": {"template": "{% assign list = page.list %}{% assign nums = page.nums %}" + PROBE,
                            "corpus": "none", "site": {},
                            "page": {"list": [{"k": "B"}, {"k": "a"}, {"k": "b"}, {"k": "C D"}],
                                     "nums": [{"n": 3}, {"n": None}, {"n": 1}]}}}
    new_block, old_block, scoring = shipped_block(), reference_block(), reference_scoring_probe()
    for name, (corpus, live, _expected) in PARITY_CASES.items():
        site = {"data": {"live_eligibility": live} if live else {}, "time": FIXED_TIME}
        jobs[f"new:{name}"] = {"template": new_block + TRAILER, "corpus": corpus, "site": site}
        jobs[f"old:{name}"] = {"template": old_block + TRAILER, "corpus": corpus, "site": site}
        jobs[f"probe:{name}"] = {"template": scoring, "corpus": corpus, "site": site}
    # The frozen loop itself is NOT run over the real records: that render IS the 124 MB page (about
    # 35 s here). The real corpus is held to the oracle through the reference's own per-record
    # scoring instead, and the oracle is held to the frozen loop on every synthetic corpus above.
    plain = {"data": {}, "time": FIXED_TIME}
    jobs["new:real"] = {"template": new_block + TRAILER, "corpus": "real", "site": plain}
    jobs["probe:real"] = {"template": scoring, "corpus": "real", "site": plain}
    jobs["page:real"] = {"template": body(HOME_LAYOUT), "base": body(BASE_LAYOUT), "corpus": "real",
                         "site": real_site(), "page": {"layout": "aux-home", "url": "/", "title": "Home"}}
    v_jobs, v_corpora = verdict_jobs()
    jobs.update(v_jobs)
    corpora.update(v_corpora)
    out = render(jobs, corpora)

    section_h(out)
    section_p(out, len(real))
    section_b(out)
    section_i()
    section_d(out, real)
    section_v(out)
    section_t(out, real)
    print("\n  (render seconds: " + ", ".join(f"{k}={v.get('seconds', 0):.1f}" for k, v in out.items())
          + f"; total {time.time() - started:.1f}s)")
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
