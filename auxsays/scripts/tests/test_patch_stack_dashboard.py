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
  [UP] the upgrade path: every release in the window carries the verdict the SHARED derivation
      gives it (judged against an oracle written independently here from the corpus), the
      parallel-servicing-line rule separates Windows from PowerPoint without looking at
      build-awareness, and the payload still carries no release-note prose.

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
               "checked", "mon", "oa", "os", "recs", "more"}
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

    print()
    print("[IV] installed versions: the picker payload and the three integrations")
    RECORDS_CAP = 24
    # Fixed width, asserted EXACTLY. When the tuple grew from 5 to 11 for the upgrade path, three
    # checks below were gated on `len(rec) == 5` and quietly began measuring an empty list -- IV2
    # passed over nothing at all. An exact width is what turned that into a visible failure.
    REC_WIDTH = 11
    bad_shape, unsorted, over_cap, bad_more = [], [], [], []
    build_aware, beta_flagged = [], []
    for entry in entries:
        recs = entry.get("recs")
        if not isinstance(recs, list):
            bad_shape.append(f"{entry.get('id')}: recs is not a list")
            continue
        for rec in recs:
            if not (isinstance(rec, list) and len(rec) == REC_WIDTH
                    and isinstance(rec[0], str) and isinstance(rec[1], str)
                    and isinstance(rec[2], str) and isinstance(rec[3], str)
                    and rec[4] in (0, 1)
                    and isinstance(rec[5], str) and rec[5]
                    and isinstance(rec[6], int) and isinstance(rec[7], int)
                    and isinstance(rec[8], str) and isinstance(rec[9], int)
                    and rec[10] in (0, 1)):
                bad_shape.append(f"{entry.get('id')}: {rec!r}")
                break
        well_formed = [r for r in recs if isinstance(r, list) and len(r) == REC_WIDTH]
        dates = [r[2] for r in well_formed]
        if dates != sorted(dates, reverse=True):
            unsorted.append(str(entry.get("id")))
        if len(recs) > RECORDS_CAP:
            over_cap.append(f"{entry.get('id')}: {len(recs)}")
        if not isinstance(entry.get("more"), int) or entry.get("more") < 0:
            bad_more.append(f"{entry.get('id')}: {entry.get('more')!r}")
        if any(str(r[1] or "") for r in well_formed):
            build_aware.append(str(entry.get("id")))
        if any(r[4] == 1 for r in well_formed):
            beta_flagged.append(str(entry.get("id")))

    check("IV1 every picker record is [version, build, date, url, beta, verdict, rank, n, ev, oa, notes]",
          not bad_shape, "; ".join(bad_shape[:3]))
    check("IV2 picker records are newest-first", not unsorted, str(unsorted[:4]))
    check(f"IV3 the picker list is bounded at {RECORDS_CAP} per product",
          not over_cap, "; ".join(over_cap[:3]))
    check("IV4 `more` counts the records beyond the window", not bad_more, "; ".join(bad_more[:3]))

    # Windows identity is (version, build). Losing the build would collapse several cumulative
    # updates of one servicing train into a single indistinguishable entry.
    check("IV5 build-aware products keep their build in the picker identity",
          "microsoft-windows-11" in build_aware, str(build_aware))
    win = next((e for e in entries if e.get("id") == "microsoft-windows-11"), {})
    win_recs = [r for r in (win.get("recs") or []) if isinstance(r, list)]
    win_versions = {r[0] for r in win_recs}
    win_identities = {(r[0], r[1]) for r in win_recs}
    check("IV6 Windows records sharing a version stay distinct by build",
          len(win_identities) == len(win_recs) and len(win_versions) < len(win_recs),
          f"{len(win_recs)} records, {len(win_versions)} versions, {len(win_identities)} identities")

    # The beta flag is the only channel signal this repo has; it exists so a stable reader is never
    # told a newer beta is an update.
    check("IV7 the tracked beta release is flagged as beta",
          "blackmagic-davinci" in beta_flagged, str(beta_flagged))

    payload_bytes = len(payload_match.group(1)) if payload_match else 0
    check(f"IV8 the payload stays bounded ({payload_bytes} bytes)", payload_bytes < 120000,
          "a picker list must not become a dump of every record")

    # The three integrations.
    patch_layout = (AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    # The version attribute is ESCAPED: `update_version` is free text for several products
    # (Figma and GitHub carry changelog headlines there), so it reaches an HTML attribute
    # unsanitised otherwise. Pinning the escaped form keeps the escape from being dropped.
    check("IV9 the patch page can claim its own exact release, version escaped",
          'data-iv-here="{{ page.product_id }}"' in patch_layout
          and "data-iv-v=\"{{ page.update_version | escape }}\"" in patch_layout
          and "page.target_build" in patch_layout)
    row = (AUX / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
    check("IV10 history rows expose their record identity for the marker",
          'data-record-url="{{ item.url }}"' in row and 'data-record-product="{{ item.product_id }}"' in row)
    check("IV11 the strip counts versions set and newer releases",
          "data-stack-count-versions" in html and "data-stack-count-newer" in html)
    # The verdict on several of those releases is WAIT; counting them as required work would
    # contradict the card underneath.
    flat_all = re.sub(r"\s+", " ", html + js)
    check("IV12 nothing claims updates are required",
          "updates required" not in flat_all.lower())
    # The comparison is a RELATIONSHIP between two records. The verdict stays whatever the patch
    # record already says, so the installed-version logic must not contain a decision word at all:
    # being several releases behind is not itself advice to update.
    CONSERVATIVE = {"CURRENT", "UPDATE AVAILABLE", "NEWER TRACKED VERSION EXISTS",
                    "INSTALLED VERSION NO LONGER TRACKED"}
    iv_logic = js.split("const installedState", 1)[1].split("// My Patch Stack", 1)[0]
    declared = set(re.findall(r"'(" + "|".join(sorted(CONSERVATIVE, key=len, reverse=True)) + r")'", js))
    leaked = [w for w in ("WAIT", "TEST FIRST", "AVOID", "SAFE ENOUGH", "SECURITY UPDATE",
                          "MANUAL WATCH", "OFFICIAL ONLY")
              if w in iv_logic]
    check("IV13 the comparison uses only the four conservative states",
          declared == CONSERVATIVE, str(sorted(CONSERVATIVE - declared)))
    check("IV14 the installed-version logic contains no verdict word",
          not leaked, f"decision words found in installedState: {leaked}")
    # Live, UPDATE AVAILABLE read "A newer tracked release of this version exists." and the vague
    # state read "Newer tracked releases exist." -- the same sentence twice, so the reader could
    # see two different labels and no difference between them. The definite state is the only one
    # allowed to sound definite; the vague one has to say why it is vague.
    copy_block = js.split("const STATE_COPY", 1)[1].split("};", 1)[0]
    copy_map = dict(re.findall(r"'([A-Z ]+)': '([^']+)'", copy_block))
    check("IV15 every state explains itself in its own words",
          len(set(copy_map.values())) == len(CONSERVATIVE) == len(copy_map),
          f"{len(copy_map)} states, {len(set(copy_map.values()))} distinct sentences")
    vague = copy_map.get("NEWER TRACKED VERSION EXISTS", "")
    definite = copy_map.get("UPDATE AVAILABLE", "")
    check("IV16 the vague state says why it is vague rather than paraphrasing the definite one",
          "clear update" in vague and vague != definite and "stable" in definite,
          f"vague={vague!r} definite={definite!r}")

    # Every option button in a card carries the SAME data-iv-set (the product id), so restoring
    # focus by that attribute alone returned the first option in the list, not the one the reader
    # had just activated. The record identity is what tells the buttons apart.
    # Pin the LOOKUP, not the surrounding block: `dataset.ivV` and `querySelectorAll` both occur
    # elsewhere in the same listener, so a check over the whole block passes with the defect
    # restored. This slice is the target assignment itself.
    after = js.split("auxsays:installed-change", 1)[1]
    target_stmt = after.split("const target", 1)[1].split(";", 1)[0]
    identity = after.split("const target", 1)[0]
    check("IV17 focus returns to the option the reader activated, by record identity",
          "options.find" in target_stmt
          and "querySelector('[data-iv-set=" not in target_stmt
          and "dataset.ivV" in identity and "dataset.ivB" in identity,
          f"target chosen by: {target_stmt.strip()[:90]!r}")

    print()
    print("[UP] the upgrade path: per-release data, servicing lines, and what is NOT claimed")

    # The per-release verdict is the SAME derivation the card uses, now applied to every record in
    # the window. `expected_verdict` is written independently in Python straight from the corpus, so
    # this is the payload being judged from outside rather than agreeing with itself.
    by_url = {str(rec.get("url") or ""): rec for rec in records}
    RANKS = (("AVOID", 0), ("WAIT", 1), ("TEST FIRST", 2), ("SECURITY UPDATE", 3),
             ("SAFE ENOUGH", 4), ("OFFICIAL ONLY", 5), ("INSUFFICIENT DATA", 6), ("MANUAL WATCH", 7))
    # `aux-update.html` refuses to render a notes body that looks like scraped page furniture. The
    # flag has to refuse the same ones, or a panel claims notes exist where the page shows none.
    POLLUTION = ("showvotefeedback", "function(", "document.", "window.", "queryselector",
                 "content-rating-buttons")
    verdict_drift, count_drift, rank_drift, notes_drift = [], [], [], []
    reached = 0
    for entry in entries:
        for rec in (entry.get("recs") or []):
            source = by_url.get(rec[3])
            if source is None:
                continue
            reached += 1
            want = expected_verdict(source)
            if rec[5] != want:
                verdict_drift.append(f"{entry.get('id')} {rec[0]}: {rec[5]!r} != {want!r}")
            if rec[7] != int(source.get("update_report_count") or 0):
                count_drift.append(f"{entry.get('id')} {rec[0]}: {rec[7]}")
            want_rank, key = 99, str(rec[5]).upper()
            for token, value in RANKS:
                if token in key:
                    want_rank = value
                    break
            if rec[6] != want_rank:
                rank_drift.append(f"{entry.get('id')} {rec[0]}: {rec[6]} != {want_rank}")
            body = str(source.get("official_patch_notes_body") or "").strip()
            want_notes = 1 if (body and not any(t in body.lower() for t in POLLUTION)) else 0
            if rec[10] != want_notes:
                notes_drift.append(f"{entry.get('id')} {rec[0]}: {rec[10]} != {want_notes}")

    check("UP1 the per-release checks actually reached the records they judge",
          reached > 150, f"matched {reached} records to the corpus")
    check("UP2 every release carries the verdict the shared derivation gives it",
          not verdict_drift, "; ".join(verdict_drift[:3]))
    check("UP3 every release carries its own report count", not count_drift, "; ".join(count_drift[:3]))
    check("UP4 every release carries the rank its verdict maps to", not rank_drift, "; ".join(rank_drift[:3]))
    check("UP5 the official-notes flag uses the same pollution gate as the patch page",
          not notes_drift, "; ".join(notes_drift[:3]))

    def parallel_lines(recs: list) -> bool:
        """The rule `auxsays.js` uses, restated here over the rendered payload."""
        blocks: dict = {}
        prev = None
        for rec in recs:
            if rec[0] != prev:
                blocks[rec[0]] = blocks.get(rec[0], 0) + 1
            prev = rec[0]
        if any(n > 1 for n in blocks.values()):
            return True
        if not any(str(rec[1] or "") for rec in recs):
            return False
        seen: dict = {}
        for rec in recs:
            date = str(rec[2] or "")
            if not date:
                continue
            if date not in seen:
                seen[date] = rec[0]
            elif seen[date] != rec[0]:
                return True
        return False

    classified = {str(e.get("id")): parallel_lines(e.get("recs") or [])
                  for e in entries if e.get("recs")}
    check("UP6 Windows is recognised as running parallel servicing lines",
          classified.get("microsoft-windows-11") is True, str(sorted(classified)))
    # The discriminator cannot be build-awareness. PowerPoint is build-aware too, and its versions
    # run one after another -- grouping it by version would shatter a real chronology.
    check("UP7 PowerPoint is build-aware yet sequential, so its chronology survives the rule",
          "microsoft-powerpoint" in classified
          and classified.get("microsoft-powerpoint") is False,
          f"powerpoint={classified.get('microsoft-powerpoint')!r}")
    swept = sorted(k for k, v in classified.items() if v and k != "microsoft-windows-11")
    check("UP8 no other tracked product is swept into the parallel-line rule", not swept, str(swept))

    # Ordering inside one line is only safe because the corpus has no two releases of one version on
    # one date. If that ever changes, the per-line lists start asserting an order nobody recorded.
    intra = []
    for entry in entries:
        per_line: dict = {}
        for rec in (entry.get("recs") or []):
            per_line.setdefault(rec[0], []).append(rec[2])
        for version, dates in per_line.items():
            if len(dates) != len(set(dates)):
                intra.append(f"{entry.get('id')} {version}")
    check("UP9 inside one servicing line every release has a distinct date",
          not intra, "; ".join(intra[:3]))

    payload_text = payload_match.group(1) if payload_match else ""
    longest = max((len(str(rec[5])) + len(str(rec[8]))
                   for e in entries for rec in (e.get("recs") or [])), default=0)
    check("UP10 no release carries long-form text into the payload", longest <= 96, f"longest={longest}")
    # `</SCRIPT>` closes this element as surely as `</script>`; the tokenizer does not care about
    # case, and vendor prose reaches these strings.
    check("UP11 nothing in the payload can close the script element that holds it",
          payload_text and "</" not in payload_text, "a raw end-tag opener survived into the payload")
    check("UP12 the neutraliser is not limited to one spelling of the tag",
          "replace: '</', '<\\/'" in PAGE.read_text(encoding="utf-8"),
          "the page still replaces only the exact string </script>")

    path_fn = js.split("const pathHtml", 1)[1].split("const installedHtml", 1)[0]
    step_fn = js.split("const stepHtml", 1)[1].split("const pathHtml", 1)[0]
    check("UP13 the path renderer re-runs no part of the decision it renders",
          "installedState(" not in path_fn and "update_decision" not in path_fn,
          "the renderer is deciding something instead of rendering what it was given")
    check("UP14 each release in a path shows the verdict its own record carries",
          "rec[5]" in step_fn and "rec[6]" in step_fn)
    check("UP15 no aggregate is computed across the releases in a path",
          "reduce(" not in path_fn and "score" not in path_fn.lower()
          and "average" not in path_fn.lower())
    # GitHub publishes nine changelog entries on one day. Explaining the tie on every one of them
    # printed the same disclaimer eight times and buried the releases it was explaining.
    check("UP17 a run of same-date releases is explained once, not once per release",
          "runOpeners" in path_fn and "steps[index - 1].tied" in path_fn
          and "step.tied" not in step_fn,
          "the tie notice is still emitted per step")
    # WCAG 2.5.3. Every one of these controls repeats per card, so each needs the product in its
    # accessible name -- and that name has to START from the words printed on the control, or voice
    # control cannot act on what the reader can see.
    names = re.findall(r"aria-label=\"([^\"$]*)\$\{", js)
    check("UP18 each repeated control names its product without dropping its visible label",
          'aria-label="Clear version for ' in js
          and 'aria-label="Clear your saved version' not in js,
          str(names[:4]))
    limit = re.search(r"const PATH_LIMIT = (\d+)", js)
    check("UP16 the visible path is bounded and says how many it did not show",
          bool(limit) and 8 <= int(limit.group(1)) <= 12 and "hidden" in path_fn,
          f"PATH_LIMIT={limit.group(1) if limit else None}")

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
