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

import re
import sys
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
    check("F8 the invariant sentence renders exactly once",
          LAYOUT_EMITTED.count("are not live telemetry") == 1,
          str(LAYOUT_EMITTED.count("are not live telemetry")))

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
    check("C4 the freshness caveat still says report counts are not live telemetry",
          "not live telemetry" in LAYOUT)
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
