#!/usr/bin/env python3
"""The patch detail page answers the decision BEFORE it explains uncounted evidence.

Two live defects motivated this suite, and nothing in PR-time CI covered either of them.

ORDER. `_layouts/aux-update.html` rendered the evidence-freshness caveat, the Level-2
update-linked card and the Level-3 recent-reports card BETWEEN the evidence summary and the
AUXSAYS verdict. On a zero-confirmed page a reader met, in order: a methodology warning, reports
that do not count, the explanation of why they do not count, and only then the answer to the
question the page exists for. AUXSAYS answers "should I install this update, wait, or avoid it?",
so the decision leads and its audit trail follows.

THEME. Those same cards were styled through an `--aux-*` custom-property namespace that was never
defined anywhere in the stylesheet, so every `var(--aux-…, fallback)` resolved to a hardcoded
LIGHT-THEME fallback on a dark page. `.update-linked-card` painted
`background: var(--aux-surface-muted, #fafafb)` -- measured in Chromium as rgb(250,250,251), a
near-white card -- and the text inside it either took `var(--aux-text-muted, #63636d)` dark grey or,
for the tokens written with no fallback at all, had its colour declaration dropped and inherited
`--text-0` (#ece7dd) against that near-white, about 1.18:1.

The theme half has a second trap worth pinning: the stylesheet's first `:root` rule contains a
missing semicolon at `--radius-xl: 28px@font-face {`, which swallows the following ~900 lines into
that custom property's VALUE. Definitions placed anywhere inside the swallowed region parse without
error and have no effect -- the first attempt at this fix landed there and was inert. So it is not
enough for the tokens to be defined; they must be defined ABOVE the splice.

Static and offline: this parses the layout source and the stylesheet. No Jekyll, no browser.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_page_hierarchy.py
"""
from __future__ import annotations

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

LAYOUT_PATH = _AUX / "_layouts" / "aux-update.html"
CSS_PATH = _AUX / "assets" / "css" / "auxsays-custom.css"
LAYOUT = LAYOUT_PATH.read_text(encoding="utf-8")
# Liquid comments never render. An assertion of the form "this sentence must not appear" has to
# read the EMITTING markup only -- otherwise a comment that documents the sentence being removed
# (which is exactly how this repair is documented) makes the check fail forever.
LAYOUT_EMITTED = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "",
                        LAYOUT, flags=re.S)
CSS = CSS_PATH.read_text(encoding="utf-8")

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


def strip_css_comments(text: str) -> str:
    """Blank comments while preserving every newline, so offsets still map to real line numbers."""
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def live_root_span(css: str) -> tuple[int, int]:
    """(start, end) offsets of the region of the first `:root` rule the CSS parser really enters.

    Returns the span from the rule's opening brace to the first point where a declaration value
    swallows the rest -- i.e. everything a custom property defined here would actually reach.
    """
    body = strip_css_comments(css)
    open_i = body.index("{", body.index(":root"))
    # Where does a declaration value start consuming whole blocks? Walk declarations from the top;
    # the first one whose value contains an unbalanced '{' swallows everything after it.
    i = open_i + 1
    while i < len(body):
        semi = body.find(";", i)
        brace = body.find("{", i)
        close = body.find("}", i)
        if semi != -1 and (brace == -1 or semi < brace) and (close == -1 or semi < close):
            i = semi + 1
            continue
        # A '{' before the next ';' means this declaration's value opens a block: dead from here.
        return open_i, (brace if brace != -1 else len(body))
    return open_i, len(body)


def block_index(marker: str) -> int:
    """Position of a block in the layout source, asserted to be unique enough to be meaningful."""
    return LAYOUT.index(marker)


def at(marker: str) -> int:
    """Offset of `marker` in the EMITTING markup, or -1 when absent.

    Never raises. An ordering check whose needle has been deleted must fail that one check; using
    `str.index` there aborts the module and silently takes every later assertion with it, which
    reads as a crash rather than as the coverage loss it actually is.
    """
    return LAYOUT_EMITTED.find(marker)


# --------------------------------------------------------------- real Liquid render of both boxes

CARD_SENTENCE = "This is a verified report sample, not live consensus telemetry."
ASIDE_CLAUSE = "Report counts are preserved from structured evidence and are not live telemetry."

# render! rather than render, so a Liquid error RAISES instead of being embedded in the output where
# a "the sentence is absent" assertion would read straight past it and pass.
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
out = {}
payload['cases'].each do |name, vars|
  out[name] = tpl.render!('site' => payload['site'], 'page' => vars, 'content' => '')
end
print JSON.generate(out)
"""


def count_framing(html: str) -> int:
    """How many times the sample qualifier reaches the reader on this page."""
    return html.count(CARD_SENTENCE) + html.count(ASIDE_CLAUSE)


def aside_of(html: str):
    m = re.search(r'<aside class="update-evidence-freshness-notice".*?</aside>', html, re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0))).strip() if m else None


def html_excerpt(html: str) -> str:
    card = re.search(r'<p class="consensus-chart-meta consensus-sample-note">(.*?)</p>', html, re.S)
    return f"card={'yes' if card else 'no'} aside={aside_of(html)!r}"


def _page(**over) -> dict:
    """A minimal but REAL page hash: every field the gate block reads, and nothing it does not."""
    base = {
        "product_id": "obs-studio", "update_version": "31.0.4", "target_build": "",
        "update_product": "OBS Studio", "update_consensus_label": "Negative",
        "update_published_at": "2025-06-27T00:00:00Z",
        "update_source_url": "https://example.test/notes",
        "consensus_collection_status": "pilot_initial_sample",
        "evidence_state": "pilot_sample",
        "update_report_count": 1,
        "confirmed_patch_specific_report_count": 1,
        # source_type must also appear in a method-health row for that row to count
        "accepted_report_sources": [{"source_type": "forum_thread"}],
        "evidence_last_checked": "2026-01-01T00:00:00Z",   # deliberately ancient => stale
    }
    base.update(over)
    return base


FRESH = "2099-01-01T00:00:00Z"   # far future => never stale, whatever the build clock says


def render_gate_matrix():
    """Render the WHOLE layout over one case per gate branch. Returns (liquid_ok, cases).

    The case list is built and RETURNED even when ruby is missing, with each `_rendered` carrying the
    reason instead of HTML. Two things follow, both deliberate. The suite emits the same number of
    checks in every environment, so a missing tool cannot present itself as CHECK COUNT DRIFT against
    the governed manifest. And every case still runs its L0 render-success assertion, which fails
    with the real cause -- rather than the six of ten cases that would otherwise pass quietly,
    because "the sentence is absent" is trivially true of output that was never produced.
    """
    src = LAYOUT.split("---", 2)[-1]          # drop the `layout: aux-base` front matter
    # Strip the two include tags. L2 asserts neither include emits an equivalent sentence, so this
    # can neither hide an occurrence nor invent one -- it only removes the need for a file system.
    src = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", src, flags=re.S)

    def health(status: str) -> dict:
        return {"methods": [{"product_id": "obs-studio", "update_version": "31.0.4",
                             "target_build": "", "source_type": "forum_thread", "status": status}]}

    healthy = health("success")
    # `official` is not a curiosity: consensus_collection_status is deferred_official_only on 942 of
    # the 1141 shipped records, i.e. 83% of the corpus, and a pilot-only matrix would never touch it.
    official = {"consensus_collection_status": "deferred_official_only", "evidence_state": None}
    cases = [
        # name,                 page,                                            health,   expect
        ("fresh+healthy",       _page(evidence_last_checked=FRESH),              healthy,  1),
        ("stale-only",          _page(),                                         healthy,  1),
        ("fresh+blocked",       _page(evidence_last_checked=FRESH),              health("blocked"), 1),
        ("stale+blocked",       _page(),                                         health("blocked"), 1),
        ("fresh+degraded",      _page(evidence_last_checked=FRESH),              health("partial"), 1),
        # report_count 0 with confirmed 4: the card's gate is false, so the aside must restore it.
        ("divergence",          _page(update_report_count=0,
                                      confirmed_patch_specific_report_count=4),  healthy,  1),
        # mature consensus needs no sample qualifier, and the aside is not a pilot box
        ("live consensus",      _page(update_report_count=5,
                                      confirmed_patch_specific_report_count=5,
                                      consensus_collection_status="live_consensus",
                                      evidence_state="live"),                    healthy,  0),
        ("no reports at all",   _page(update_report_count=0,
                                      confirmed_patch_specific_report_count=0),  healthy,  0),
        # the 83% class: no aside (not pilot), so the card is the only owner and must carry it alone
        ("official+reports",    _page(**official),                               healthy,  1),
        # THE DOCUMENTED BLIND SPOT, pinned deliberately. A non-pilot record whose bearing count
        # exceeds its report count states the qualifier NOWHERE: the card's gate is false and there
        # is no aside to restore it into. aux-update.html says so in as many words; if the card's
        # gate is ever widened this case flips to 1 and forces that comment to be updated with it.
        ("official+divergence", _page(update_report_count=0,
                                      confirmed_patch_specific_report_count=4,
                                      **official),                               healthy,  0),
    ]

    ruby = shutil.which("ruby")
    if not ruby:
        return False, [(n, dict(p, _rendered="<<RENDER FAILED: ruby is not on PATH>>"), e)
                       for n, p, _h, e in cases]

    out = []
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        for name, page, hp, expect in cases:
            payload = Path(td) / "p.json"
            payload.write_text(json.dumps({
                "template": src,
                "site": {"time": "2026-09-09T00:00:00Z", "data": {"evidence_method_health": hp}},
                "cases": {name: page},
            }), encoding="utf-8")
            proc = subprocess.run([ruby, str(script), str(payload)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            page = dict(page)
            if proc.returncode != 0:
                page["_rendered"] = f"<<RENDER FAILED: {(proc.stderr or '')[-300:]}>>"
            else:
                page["_rendered"] = json.loads(proc.stdout)[name]
            out.append((name, page, expect))
    return True, out


def run() -> int:
    print("=" * 78)
    print("Patch detail page: the decision leads, uncounted context follows, theme is native")
    print("=" * 78)

    # ---------- H: information hierarchy ----------
    print("\n[H] the AUXSAYS verdict precedes every uncounted-evidence block")
    identity = block_index('<h1 class="update-title"')
    summary = block_index('class="update-verdict-card update-verdict-card--clean update-evidence-card"')
    verdict = block_index('<div id="verdict"')
    monitoring = block_index("{% include monitoring-status.html")
    freshness = block_index("{% if show_report_freshness_notice %}")
    tier2 = block_index('<section class="update-linked-card"')
    tier3 = block_index('<section class="recent-reports-card"')

    check("H1 patch identity comes first", identity < summary,
          f"identity@{identity} summary@{summary}")
    check("H2 the evidence summary precedes the verdict", summary < verdict,
          f"summary@{summary} verdict@{verdict}")
    # THE DEFECT. Each of these three was above the verdict.
    check("H3 the verdict precedes the evidence-freshness caveat", verdict < freshness,
          f"verdict@{verdict} freshness@{freshness}")
    check("H4 the verdict precedes the Level-2 update-linked card", verdict < tier2,
          f"verdict@{verdict} tier2@{tier2}")
    check("H5 the verdict precedes the Level-3 recent-reports card", verdict < tier3,
          f"verdict@{verdict} tier3@{tier3}")
    check("H6 community monitoring precedes the uncounted context",
          monitoring < min(freshness, tier2, tier3),
          f"monitoring@{monitoring} first-context@{min(freshness, tier2, tier3)}")
    check("H7 Level 2 still precedes Level 3 (counted-adjacent before pure context)",
          tier2 < tier3, f"tier2@{tier2} tier3@{tier3}")

    # The monitoring include must stay BELOW the verdict for a second, non-obvious reason:
    # test_consensus_sample_honesty.py renders "the layout up to its first {% include %}" and
    # would lose the verdict box from its render window entirely.
    first_include = LAYOUT.index("{% include ")
    check("H8 the verdict is inside the first-include render window other suites rely on",
          verdict < first_include, f"verdict@{verdict} first_include@{first_include}")

    # ---------- O: confirmed evidence outranks non-counting context ----------
    print("\n[O] the confirmed source list precedes the uncounted context")
    sources = block_index('<details id="user-reports-sources"')
    grid = block_index('<section class="update-content-grid">')
    ctx_wrapper = block_index('<div class="update-order-context">')
    check("O1 the context block lives INSIDE the content grid", grid < ctx_wrapper,
          f"grid@{grid} context@{ctx_wrapper}")
    check("O2 the confirmed source list precedes the context block in the DOM",
          sources < ctx_wrapper, f"sources@{sources} context@{ctx_wrapper}")
    check("O3 all three context blocks are inside that wrapper",
          ctx_wrapper < freshness and ctx_wrapper < tier2 and ctx_wrapper < tier3,
          f"wrapper@{ctx_wrapper} freshness@{freshness} t2@{tier2} t3@{tier3}")
    # DOM order is not enough: this grid's visual order comes from CSS `order`, so the context
    # wrapper must carry a HIGHER order than the confirmed sources card or it would render above it
    # regardless of markup position. That is the whole reason the class exists.
    def order_of(cls):
        m = re.findall(r"\." + re.escape(cls) + r"\s*\{\s*order:\s*(\d+)\s*;\s*\}", CSS)
        return int(m[-1]) if m else None      # last definition wins in the cascade
    o_sources, o_context = order_of("update-order-sources"), order_of("update-order-context")
    o_history = order_of("update-order-history")
    check("O4 .update-order-context is defined in CSS", o_context is not None, str(o_context))
    check("O5 its order is HIGHER than the confirmed sources card",
          o_sources is not None and o_context > o_sources, f"sources={o_sources} context={o_context}")
    check("O6 ...and higher than history, so context is genuinely last",
          o_history is not None and o_context > o_history, f"history={o_history} context={o_context}")
    check("O7 the context wrapper actually carries that class",
          'class="update-order-context"' in LAYOUT)
    # The relocation must not have disturbed the in-page anchors.
    for anchor_id in ("user-reports-sources", "official-patch-notes", "technical-details",
                      "history", "verdict"):
        check(f"O8 anchor #{anchor_id} still exists", f'id="{anchor_id}"' in LAYOUT)
    check("O9 the nav still links the confirmed sources anchor",
          '<a href="#user-reports-sources">' in LAYOUT)

    # ---------- F: the freshness notice claims only what fired ----------
    print("\n[F] the freshness notice distinguishes stale from degraded from blocked")
    check("F1 blocked and degraded are tracked as separate flags",
          "assign method_health_blocked = false" in LAYOUT
          and "assign method_health_degraded = false" in LAYOUT)
    check("F2 the blocked/broken split matches the monitoring card's own vocabulary",
          "{% capture blocked_status_tokens %}|blocked|broken|{% endcapture %}" in LAYOUT)
    check("F3 the notice text is derived, not hardcoded",
          "{{ freshness_headline }}" in LAYOUT and "{{ freshness_detail }}" in LAYOUT)
    check("F4 a stale-only page says collection is healthy, not blocked",
          "Collection itself is reporting healthy." in LAYOUT)
    check("F5 a blocked page says blocked", "Collection blocked." in LAYOUT)
    check("F6 a degraded page says degraded", "Collection degraded." in LAYOUT)
    # THE DEFECT: this exact sentence asserted blocked/pending collection on every page that
    # rendered the notice, including 10 whose methods were all success/no_results/disabled.
    check("F7 the old unconditional blocked-or-pending claim no longer RENDERS",
          "Some collection methods are currently blocked or pending." not in LAYOUT_EMITTED,
          "still present in emitting markup")
    # DEDUPLICATION. The evidence-summary card already says "This is a verified report sample, not
    # live consensus telemetry." and prints the staleness date; the aside said the same thing again
    # one screen below the verdict. #114 moved the aside without deduplicating it. The card owns the
    # qualifier now -- it is the box carrying the count the qualifier qualifies -- and the aside
    # restores the clause ONLY when the card's own gate (`report_count > 0`) did not fire. That is a
    # flag rather than an assumption, because `report_bearing_count` can exceed `report_count`.
    check("F8 the aside no longer repeats the card's sample framing unconditionally",
          "{% unless sample_framing_shown %} Report counts are preserved from structured "
          "evidence and are not live telemetry.{% endunless %}" in LAYOUT_EMITTED)
    # The flag mirrors the card's gate rather than being set inside the card, because
    # test_consensus_sample_honesty regex-excises that block verbatim to build its pre-fix control.
    # Mirroring means the condition is written twice, so pin the two copies to the same text here --
    # otherwise the card could stop emitting the sentence while the aside still believes it did.
    CARD_GATE = "{% if consensus_established == false and report_count > 0 %}"
    check("F9 the flag is set by the card's OWN gate, written identically",
          LAYOUT_EMITTED.count(
              CARD_GATE + "{% assign sample_framing_shown = true %}{% endif %}") == 1
          and LAYOUT_EMITTED.count(CARD_GATE) == 2,
          f"gate occurrences={LAYOUT_EMITTED.count(CARD_GATE)}")
    check("F9b ...and the second occurrence is the card that actually prints the sentence",
          at(CARD_GATE + '\n          <p class="consensus-chart-meta consensus-sample-note">') > -1)
    # `at` and not `.index`, deliberately: a missing needle must fail THIS check, not raise and take
    # the other 78 assertions of the suite down with it.
    o_init = at("{% assign sample_framing_shown = false %}")
    o_set = at("{% assign sample_framing_shown = true %}")
    o_use = at("{% unless sample_framing_shown %}")
    check("F10 the flag is initialised false before either box renders",
          -1 < o_init < o_set < o_use, f"init={o_init} set={o_set} use={o_use}")
    check("F11 the aside's heading is the derived state, not a second 'verified report sample' label",
          "<strong>{{ freshness_headline }}</strong>" in LAYOUT_EMITTED
          and "Verified report sample" not in LAYOUT_EMITTED)

    # F12 -- THE LEAK THE FIRST DRAFT LEFT BEHIND. Deduplicating only the clause inside the unless
    # guard was not enough: `freshness_detail` is interpolated BEFORE that guard opens, so any
    # wording put in it renders unconditionally. The first draft's stale-only detail read "This
    # report sample has not been revalidated recently", which returned "report sample" to the aside
    # on 93 of the pages whose card was already saying it -- the same defect, one noun quieter.
    # The aside may describe freshness and collection health; naming what the evidence IS is the
    # card's job. Assert over the DERIVED strings, which is where the wording actually lives.
    detail_literals = re.findall(r"\{%\s*assign\s+freshness_detail\s*=\s*'([^']*)'\s*%\}",
                                 LAYOUT_EMITTED)
    detail_literals += re.findall(r"\{%\s*capture\s+freshness_detail\s*%\}(.*?)\{%\s*endcapture\s*%\}",
                                  LAYOUT_EMITTED, re.S)
    check("F12a the aside's detail strings were actually found", len(detail_literals) >= 4,
          f"found {len(detail_literals)}: {detail_literals}")
    leaky = [d for d in detail_literals if "sample" in d.lower()]
    check("F12b no aside detail string re-names the sample", not leaky, str(leaky))
    check("F12c ...and the headlines do not either",
          not [h for h in re.findall(r"\{%\s*assign\s+freshness_headline\s*=\s*'([^']*)'\s*%\}",
                                     LAYOUT_EMITTED) if "sample" in h.lower()])

    # F13 -- the mirror is only sound while the variables it mirrors hold still. F9 pins the two
    # gate copies as TEXT; that is satisfied by a layout in which something reassigns report_count
    # or consensus_established between them, which would desynchronise the flag from the card with
    # every other check still green. Assert the DATAFLOW, not just the spelling.
    span = LAYOUT_EMITTED[o_set:at(CARD_GATE + '\n          <p class="consensus-chart-meta')]
    # Every writing form, not just `assign`: a capture or an increment rebinds the same name and
    # would desynchronise the mirror just as effectively, with F9's text check still green.
    reassigned = [v for v in ("report_count", "consensus_established", "report_bearing_count")
                  if re.search(r"\{%\s*(?:assign|capture|increment|decrement)\s+" + v + r"\b", span)]
    check("F13 no gate variable is reassigned between the mirror and the card",
          o_set > -1 and not reassigned, f"reassigned in span: {reassigned}")

    # ---------- L: the two boxes, RENDERED together ----------
    # Everything above is string matching over the template source. That could not have caught the
    # F12 leak, and it cannot observe the one property this repair exists to guarantee: how many
    # times the sample qualifier reaches a READER on one page.
    #
    # No existing suite could either. test_consensus_sample_honesty renders the real template, but
    # `consensus_block()` slices it at the first include tag -- and the freshness aside lives ~170
    # lines BELOW that cut, so the card and the aside had never been rendered in the same pass
    # anywhere in CI. "At most once per page" was argued, never observed.
    #
    # This renders the WHOLE layout through the real Liquid gem, over a matrix that walks every gate
    # branch, and counts occurrences in the emitted HTML. The two includes are stripped rather than
    # resolved -- L2 proves that is sound by asserting neither of them emits an equivalent sentence,
    # so removing them cannot hide or invent one.
    print("\n[L] the sample qualifier is rendered at most once per page, and once where required")
    liquid_ok, cases = render_gate_matrix()
    check("L1 the liquid gem is available, so these assertions run for real", liquid_ok,
          "install liquid 4.0.4; CI does this explicitly and must not skip these silently")

    include_prose = []
    for inc in sorted((_AUX / "_includes").glob("*.html")):
        emitted = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "",
                         inc.read_text(encoding="utf-8"), flags=re.S).lower()
        if "report sample" in emitted or "live telemetry" in emitted:
            include_prose.append(inc.name)
    check("L2 no include emits an equivalent sentence, so stripping them is sound",
          not include_prose, str(include_prose))

    for name, page, expect in cases:
        html = page["_rendered"]
        # L0 FIRST, and per case. Every assertion below is of the form "this sentence is/is not in
        # the output", and all of them are trivially satisfiable by output that does not exist. A
        # missing gem made six of these ten cases pass silently; this makes the render itself the
        # thing under test before its content is judged.
        rendered = "RENDER FAILED" not in html
        check(f"L0 {name}: the render actually produced HTML", rendered, html[:200])
        if not rendered:
            continue
        n = count_framing(html)
        check(f"L3 {name}: qualifier renders at most once (got {n})", n <= 1, html_excerpt(html))
        if expect == 1:
            check(f"L4 {name}: report-bearing page states it exactly once (got {n})", n == 1,
                  html_excerpt(html))
        else:
            check(f"L4 {name}: qualifier correctly absent (got {n})", n == 0, html_excerpt(html))
        aside = aside_of(html)
        check(f"L5 {name}: the aside never re-names the sample",
              aside is None or "sample" not in aside.lower(), str(aside))

    # THE RESTORE PATH IS REACHABLE. Without this the unless body would be unobservable dead code on
    # the whole corpus -- present in the source, provably emitted by nothing, which is exactly the
    # vacuous-guard trap this repo keeps re-learning. The divergence case (report_count 0,
    # confirmed 4) suppresses the card and forces the aside to carry it.
    div = next(p for n, p, _ in cases if n == "divergence")
    check("L6 the divergence case really does suppress the card",
          "RENDER FAILED" not in div["_rendered"]
          and "not live consensus telemetry" not in div["_rendered"])
    check("L7 ...and the aside really does restore the qualifier",
          "are not live telemetry" in div["_rendered"], html_excerpt(div["_rendered"]))

    # ---------- P: Acrobat prose ----------
    print("\n[P] no machine enum or duplicated identity reaches the reader")
    check("P1 the Why-linked line is derived rather than printed raw",
          "{{ r_why | escape }}" in LAYOUT and "{{ r.update_link_reason | escape }}" not in LAYOUT)
    check("P2 the known enum is mapped to prose",
          "'update_named_as_cause'" in LAYOUT
          and "Reporter names an update as the cause." in LAYOUT)
    check("P3 an unsupported Why-linked line is omitted, not rendered empty",
          "{% if r_why != '' %}" in LAYOUT)
    check("P4 the release-window line collapses a duplicated version/build",
          "{%- if r.window_build == r.window_version -%}" in LAYOUT)
    check("P5 ...and no longer prints both slots unconditionally",
          "the {{ r.window_version }} / Build {{ r.window_build }} release window" not in LAYOUT)

    # ---------- C: the context blocks stay honest ----------
    print("\n[C] moving the context blocks did not weaken what they say")
    check("C1 Level 2 still states the exact build is unresolved",
          "Exact build" in LAYOUT and "update-linked-item__build" in LAYOUT)
    check("C2 Level 3 still states it is not attributed to this update",
          "Not attributed to this update." in LAYOUT)
    check("C3 Level 3 still names the release window it was reported during",
          "release window" in LAYOUT)
    # The "not live telemetry" qualifier was NOT deleted from the page -- it moved to a single owner.
    # Assert it survives in the evidence-summary card, which is where it is now stated.
    check("C4 the sample/telemetry qualifier survives, owned by the evidence-summary card",
          "This is a verified report sample, not live consensus telemetry." in LAYOUT_EMITTED
          and LAYOUT_EMITTED.count(
              "This is a verified report sample, not live consensus telemetry.") == 1)
    o_note = at('class="consensus-chart-meta consensus-sample-note"')
    o_verdict = at('id="verdict"')
    o_aside = at('class="update-evidence-freshness-notice"')
    check("C4b ...inside the evidence card, above the verdict",
          -1 < o_note < o_verdict < o_aside,
          f"note={o_note} verdict={o_verdict} aside={o_aside}")
    check("C4c the card still prints the staleness date next to it",
          "Last evidence checked: {{ evidence_checked_label }}" in LAYOUT_EMITTED)
    check("C5 the freshness caveat renders exactly once",
          LAYOUT_EMITTED.count("Evidence freshness needs revalidation") == 1,
          str(LAYOUT_EMITTED.count("Evidence freshness needs revalidation")))

    # ---------- T: no light-theme leak on a dark page ----------
    print("\n[T] every --aux-* token resolves to a dark-theme value, in the LIVE cascade")
    body = strip_css_comments(CSS)
    used = set(re.findall(r"var\(\s*(--[a-z0-9-]+)", body))
    defined = set(re.findall(r"(?m)^\s*(--[a-z0-9-]+)\s*:", body))
    aux_used = {t for t in used if t.startswith("--aux-")}
    check("T1 the --aux-* namespace is actually used by the stylesheet", len(aux_used) >= 7,
          str(sorted(aux_used)))
    check("T2 no --aux-* token is left undefined", not (aux_used - defined),
          str(sorted(aux_used - defined)))

    lo, hi = live_root_span(CSS)
    for token in sorted(aux_used):
        m = re.search(r"(?m)^\s*" + re.escape(token) + r"\s*:", body)
        pos = m.start() if m else -1
        check(f"T3 {token} is defined in the LIVE part of :root",
              pos != -1 and lo < pos < hi,
              f"offset {pos}, live window {lo}..{hi} -- a definition past the "
              f"`--radius-xl: 28px@font-face {{` splice parses but never applies")

    # Fallbacks are allowed to remain in the declarations, but they must never be the thing that
    # renders. Pin that no patch-page evidence selector carries a light literal as its own value.
    for selector, prop in (
        (".update-linked-card", "background"),
        (".recent-reports-card", "background"),
    ):
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", body)
        decl = m.group(1) if m else ""
        light = re.findall(r"#(?:fff|ffffff|fafafb|f7f7f8|f5f5f5)\b", decl, re.I)
        check(f"T4 {selector} does not paint a light literal {prop}", not light, decl.strip()[:110])

    # ---------- Z: the zero-confirmed page is intentional, not broken ----------
    print("\n[Z] a page with zero confirmed reports still reads as a decision")
    check("Z1 the evidence summary states the zero case explicitly",
          "0 confirmed patch-specific community reports" in LAYOUT)
    check("Z2 the Level-2 card only renders when its FILTERED row count is non-zero",
          "{% if t2_count > 0 %}" in LAYOUT)
    check("Z3 the Level-3 card only renders when its FILTERED row count is non-zero",
          "{% if l3_count > 0 %}" in LAYOUT)
    check("Z4 the verdict box is unconditional, so no page can render without a decision",
          not re.search(r"\{%\s*if[^%]*%\}\s*<div id=\"verdict\"", LAYOUT))

    # ---------- S: the tier data resolution stayed together ----------
    print("\n[S] the reorder did not split the shared tier-source resolver")
    # l3_src and t2_build are assigned in the Level-2 preamble and consumed by the Level-3 key.
    # If a future edit moves one card without the other, Level 3 silently vanishes on every page
    # -- and an Acrobat page would read PowerPoint's data file. Pin that they travel together.
    l3_src_assign = LAYOUT.index("assign l3_src = site.data.recent_powerpoint_reports")
    t2_build_assign = LAYOUT.index("assign t2_build = page.target_build")
    l3_key_use = LAYOUT.index("capture l3_key")
    check("S1 l3_src is assigned before the Level-3 key consumes it",
          l3_src_assign < l3_key_use, f"{l3_src_assign} < {l3_key_use}")
    check("S2 t2_build is assigned before the Level-3 key consumes it",
          t2_build_assign < l3_key_use, f"{t2_build_assign} < {l3_key_use}")
    check("S3 the Acrobat branch resolves BOTH tier data files together",
          "assign l3_src = site.data.recent_acrobat_reports" in LAYOUT
          and "assign t2_all = site.data.acrobat_update_linked_evidence" in LAYOUT)

    # ---------- R: practical recommendations reach the reader ----------
    print("\n[R] practical_recommendations render under the verdict, de-duplicated")
    # The field was consumed ONLY by the fallback that substitutes item one into an empty decision
    # body -- and the producer writes body and list in the same dict literal while the retraction
    # removes them together, so an empty body with a populated list cannot occur. Measured over all
    # 1125 records: 75 carry the field and the fallback fires on 0. It rendered on no page at all.
    rec_block = LAYOUT_EMITTED.index('update-decision-actions__list')
    verdict_at = LAYOUT_EMITTED.index('<div id="verdict"')
    reasoning_at = LAYOUT_EMITTED.index('update-decision-reasoning')
    check("R1 the list is rendered, not just item one",
          "for rec in page.practical_recommendations" in LAYOUT_EMITTED,
          "only the `| first` fallback consumes the field")
    check("R2 it sits with the primary decision content, not in methodology or context",
          verdict_at < rec_block < reasoning_at,
          f"verdict@{verdict_at} block@{rec_block} reasoning@{reasoning_at}")
    check("R3 the block is gated on survivors, so a record without recommendations renders nothing",
          "if rec_rendered > 0" in LAYOUT_EMITTED)
    check("R4 an item duplicating the verdict body is dropped, in both directions",
          "rec_body_probe contains rec_probe" in LAYOUT_EMITTED
          and "rec_probe contains rec_body_probe" in LAYOUT_EMITTED)
    # Byte-exact comparison missed a verdict body repeated verbatim as a bullet when the two
    # differed only by a smart apostrophe, a double space or a trailing period.
    for token in ("replace: '’', \"'\"", "replace: '.', ''", "replace: '  ', ' '"):
        check(f"R4 the comparison is normalised ({token})", token in LAYOUT_EMITTED,
              "an unnormalised compare lets a verbatim repeat through")
    # The real restatements are not whole-string copies: a DaVinci body ends "...or test on copied
    # projects." and its bullet opens "Test on copied projects before moving client work...".
    # Measured over all 226 items: whole-string containment catches 0, the four-word prefix 24.
    check("R4 a four-word prefix already present in the body is dropped",
          "rec_probe | split: ' ' | slice: 0, 4 | join: ' '" in LAYOUT_EMITTED
          and "rec_body_probe contains rec_prefix" in LAYOUT_EMITTED,
          "whole-string containment alone drops nothing on the real corpus")
    check("R5 empty items are skipped", "if rec_text == ''" in LAYOUT_EMITTED)
    check("R6 an item repeated inside one list is shown once",
          "rec_seen contains rec_key" in LAYOUT_EMITTED)
    check("R7 recommendation text is escaped", "rec_text | escape" in LAYOUT_EMITTED)
    check("R8 the fallback that substitutes item one is preserved, so dedupe covers it",
          "page.practical_recommendations | first" in LAYOUT_EMITTED)
    for cls in ("update-decision-actions", "update-decision-actions__list"):
        check(f"R9 {cls} is styled rather than left to browser defaults",
              f".{cls} {{" in CSS, "no rule; the list would render unstyled in the verdict box")
    # The block renders INSIDE .update-decision-box__header, whose `p` rule is (0,1,1) and sets
    # color / font-weight / margin. A bare `.update-decision-actions__label` is (0,1,0) and loses
    # regardless of source order: measured in a browser, the muted colour, the 700 weight and both
    # margins were all inert. A string-presence check cannot see that, so pin the SCOPING.
    check("R9 the label selector outranks .update-decision-box__header p",
          ".update-decision-box__header .update-decision-actions__label {" in CSS
          and ".update-decision-actions__label {" not in CSS.replace(
              ".update-decision-box__header .update-decision-actions__label {", ""),
          "an unscoped label rule loses the cascade inside the verdict header")
    check("R10 the styling uses existing tokens only",
          "var(--aux-text-muted)" in CSS.split(
              ".update-decision-box__header .update-decision-actions__label {")[1][:400]
          and "var(--text-1)" in CSS.split(".update-decision-actions__list li {")[1][:300],
          "a parallel colour system was introduced")

    print()
    print("=" * 78)
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
