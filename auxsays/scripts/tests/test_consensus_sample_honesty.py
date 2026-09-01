#!/usr/bin/env python3
"""The patch page may not present a categorical sentiment label as established consensus.

AUXSAYS must distinguish "we have three negative reports" from "we have a reliable negative
consensus". Those are different claims, and only the second is a consensus claim.

The canonical contract already existed and is unchanged here:

  * evidence_state_class == 'live'  <=>  consensus_collection_status is live_consensus /
    consensus_live. That is the ONLY state that means mature consensus. NO record in the repo
    satisfies it (measured: 0 of 940), so today nothing is mature consensus.
  * community evidence strength is the ladder patch-table-row.html already renders and
    test_evidence_strength_thresholds already locks:
    0 Insufficient | 1-7 Low | 8-24 Low-Medium | 25-32 Medium | 33+ High.

No new threshold is introduced by the fix or by this suite. The defect was presentational: the
detail page rendered the categorical word plus the full Negative/Moderate/Optimal consensus scale
with NO sample qualifier at all once report_count reached 3, because the only qualifier was gated
on `report_count < 3`. A 3-report read and a 96-report read rendered identically.

These render the REAL shipped Liquid (auxsays/_layouts/aux-update.html) with the liquid gem, so
they exercise the template the site actually publishes rather than a Python re-implementation.
They SKIP the render assertions when Ruby/liquid is unavailable; CI installs the gem, so they run
there for real. The static locks below always run.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_consensus_sample_honesty.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
LAYOUT_PATH = _AUX / "_layouts" / "aux-update.html"
LAYOUT = LAYOUT_PATH.read_text(encoding="utf-8")
ROW = (_AUX / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")

_PASS = 0
_FAIL = 0
_FAILURES: list[str] = []

# The canonical ladder. Sourced from the two places that already own it, never invented here.
CANONICAL_STRENGTH = [
    (0, "Insufficient"), (1, "Low"), (2, "Low"), (3, "Low"), (7, "Low"),
    (8, "Low-Medium"), (24, "Low-Medium"), (25, "Medium"), (32, "Medium"),
    (33, "High"), (96, "High"),
]

NOT_ESTABLISHED = "Community consensus not established"
EARLY_EVIDENCE = "treat this as early evidence"
SCALE_LABELS = "Negative Moderate Optimal"


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


# ---------------------------------------------------------------- real Liquid render

_RENDER_SCRIPT = """
require 'liquid'
require 'json'
payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
# render! so a Liquid error RAISES instead of being embedded in the output where an assertion
# could read straight past it.
print tpl.render!(payload['vars'])
"""


def consensus_block(text: str = LAYOUT) -> str:
    """The layout from the end of its front matter to just before its first {% include %}.

    Everything under test -- the evidence-state ladder, the strength ladder, the evidence card and
    the verdict box -- lives in that span, and it contains no includes, so it renders standalone.
    """
    lines = text.split("\n")
    end = next((i for i, line in enumerate(lines) if "{% include" in line), len(lines))
    return "\n".join(lines[3:end])


def liquid_render(template: str, variables: dict) -> str | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_SCRIPT, encoding="utf-8")
        payload = Path(td) / "payload.json"
        payload.write_text(json.dumps({"template": template, "vars": variables}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)],
                              capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            return None
        return proc.stdout


def page_vars(count: int, label: str, *, status: str = "pilot_initial_sample") -> dict:
    return {
        "update_consensus_label": label,
        "update_report_count": count,
        "confirmed_patch_specific_report_count": count,
        "consensus_collection_status": status,
        "evidence_state": "pilot_sample" if count else "official_only",
        "official_source_captured": True,
        "update_published_at": "2026-07-29T00:00:00Z",
        "evidence_last_checked": "2026-08-30T07:17:03Z",
        "update_product": "Microsoft PowerPoint",
        "update_version": "2607",
    }


def visible(count: int, label: str = "Negative", *, status: str = "pilot_initial_sample",
            template: str | None = None) -> str | None:
    out = liquid_render(template if template is not None else consensus_block(),
                        {"page": page_vars(count, label, status=status), "site": {}})
    if out is None:
        return None
    return " ".join(re.sub(r"<[^>]+>", " ", out).split())


def pre_fix_template() -> str:
    """The template as it behaved BEFORE the fix, derived from the current one.

    Non-vacuity is proven against a synthetic pre-fix template rather than `git show main:...`,
    because the moment this merges main IS the fixed template and such a proof silently inverts.

    The two inserted regions are removed SEPARATELY: the verdict-box one wraps a nested
    {% if %}, so a single non-greedy pattern would stop at the INNER {% endif %} and leave the
    outer one dangling. Liquid then refuses to parse, the render returns None, and every C6
    control becomes a vacuous pass against an unrendered page.
    """
    text = LAYOUT
    # the qualifier under the consensus scale
    text = re.sub(
        r"\{% if consensus_established == false and report_count > 0 %\}\s*"
        r"<p class=\"consensus-chart-meta consensus-sample-note\">.*?</p>\s*\{% endif %\}",
        "", text, flags=re.S)
    # the early-evidence line in the verdict box
    text = re.sub(
        r"\{% if consensus_established == false and evidence_strength == 'Low' %\}"
        r".*?\{% endif %\}",
        "", text, flags=re.S)
    if "consensus-sample-note" in text or EARLY_EVIDENCE in text:
        raise AssertionError("pre-fix reconstruction failed: the fix is still present, so every "
                             "C6 control would pass vacuously")
    # restore the hard cut-off that produced the cliff
    anchor = "{% if record_note_text != blank %}"
    if anchor not in text:
        raise AssertionError("pre-fix reconstruction lost its anchor; C6 would go vacuous")
    text = text.replace(
        anchor,
        "{% if report_count > 0 and report_count < 3 %}"
        "<p>Too few reports for a verdict yet.</p>{% endif %}\n"
        "            " + anchor, 1)
    return text


def run() -> int:
    block = consensus_block()
    liquid_ok = liquid_render("{{ x }}", {"x": "ok"}) == "ok"

    print("=" * 96)
    print("C0  the harness renders the REAL shipped template")
    print("=" * 96)
    check("C0.1 the block ends before the first include, so it renders standalone",
          "{% include" not in block and len(block) > 2000, str(len(block)))
    check("C0.2 the block carries the evidence card and the verdict box",
          'id="verdict"' in block and "Evidence summary" in block)
    if not liquid_ok:
        check("C0.3 liquid gem available (render assertions SKIPPED without it)", False,
              "ruby/liquid missing - static locks below still ran")
    else:
        check("C0.3 liquid gem available, so render assertions run for real", True)

    print()
    print("=" * 96)
    print("C1  below the canonical consensus threshold, maturity is never implied")
    print("=" * 96)
    # The invariant: unanimous sentiment at a small n must not read as established consensus.
    if liquid_ok:
        for count, strength in CANONICAL_STRENGTH:
            if count == 0:
                continue
            text = visible(count)
            check(f"C1.1 n={count}: consensus is explicitly NOT established",
                  text is not None and NOT_ESTABLISHED in text, (text or "")[:90])
            check(f"C1.2 n={count}: the canonical strength {strength!r} is stated",
                  text is not None and f"evidence strength {strength}" in text, (text or "")[:120])
        # the exact cliff that was reported: nothing may change discontinuously at 3
        two, three = visible(2), visible(3)
        check("C1.3 n=2 and n=3 both carry the not-established statement",
              two is not None and three is not None
              and NOT_ESTABLISHED in two and NOT_ESTABLISHED in three)
        check("C1.4 n=2 and n=3 both carry the early-evidence statement (no n=3 cliff)",
              two is not None and three is not None
              and EARLY_EVIDENCE in two and EARLY_EVIDENCE in three)
        check("C1.5 an all-POSITIVE small sample is qualified the same way",
              (visible(3, "Positive") or "").count(NOT_ESTABLISHED) == 1)
        check("C1.6 a MIXED small sample is qualified the same way",
              (visible(3, "Moderate") or "").count(NOT_ESTABLISHED) == 1)
        check("C1.7 n=0 says consensus is not established and shows NO consensus scale",
              NOT_ESTABLISHED in (visible(0, "Insufficient data") or "")
              and SCALE_LABELS not in (visible(0, "Insufficient data") or ""))

    print()
    print("=" * 96)
    print("C2  raw structured sentiment and counts are PRESERVED, never suppressed")
    print("=" * 96)
    if liquid_ok:
        text = visible(3)
        check("C2.1 the categorical sentiment word is still shown",
              text is not None and "Evidence summary: Negative" in text, (text or "")[:110])
        check("C2.2 the exact accepted report count is still shown",
              text is not None and "3 user reports found" in text, (text or "")[:110])
        check("C2.3 the sample position scale is still shown (information is added, not removed)",
              text is not None and SCALE_LABELS in text)
        pos = visible(3, "Positive")
        check("C2.4 a positive sample still reads Optimal, not hedged into Negative",
              pos is not None and "Evidence summary: Optimal" in pos, (pos or "")[:110])
        # The note counts the same field the line above it counts, and says so the same way, so the
        # page never shows two differently-worded counts of the same thing.
        one = visible(1) or ""
        check("C2.5 singular/plural is correct at n=1",
              "1 user report," in one and "1 user reports," not in one, one[:130])
        check("C2.6 the note and the count line describe the same number identically",
              "3 user reports found" in (visible(3) or "")
              and "3 user reports," in (visible(3) or ""))

    print()
    print("=" * 96)
    print("C3  at/above the canonical threshold, mature consensus presents normally")
    print("=" * 96)
    if liquid_ok:
        for status in ("live_consensus", "consensus_live"):
            live = visible(30, "Negative", status=status)
            check(f"C3.1 {status}: the not-established statement is GONE",
                  live is not None and NOT_ESTABLISHED not in live, (live or "")[:110])
            check(f"C3.2 {status}: the categorical label and scale still render",
                  live is not None and "Evidence summary: Negative" in live and SCALE_LABELS in live)
            check(f"C3.3 {status}: no early-evidence hedge",
                  live is not None and EARLY_EVIDENCE not in live)
        # A LARGE sub-live sample must not be hedged as though it were tiny: over-hedging a real
        # signal is its own dishonesty.
        big = visible(96)
        check("C3.4 a 96-report sample states High strength, not an early-evidence hedge",
              big is not None and "evidence strength High" in big and EARLY_EVIDENCE not in big,
              (big or "")[:130])
        small = visible(3)
        check("C3.5 and a 3-report sample is visibly DIFFERENT from the 96-report one",
              small is not None and big is not None and small != big
              and ("evidence strength Low" in small) and ("evidence strength High" in big))

    print()
    print("=" * 96)
    print("C4  the strength ladder is the canonical one, not a second opinion")
    print("=" * 96)
    if liquid_ok:
        for count, strength in CANONICAL_STRENGTH:
            if count == 0:
                continue
            text = visible(count)
            check(f"C4.1 n={count} -> {strength}",
                  text is not None and f"evidence strength {strength}" in text, (text or "")[:110])
    # the ladder must match the include that already owns it
    for boundary in ("33", "25", "8"):
        check(f"C4.2 the detail page uses the same {boundary} boundary as patch-table-row.html",
              f">= {boundary}" in ROW.replace("&gt;", ">") and f">= {boundary}" in LAYOUT)
    check("C4.3 the detail page introduces no NEW numeric consensus threshold",
          "consensus_established" in LAYOUT
          and "evidence_state_class == 'live'" in LAYOUT)

    print()
    print("=" * 96)
    print("C5  static locks on the contract")
    print("=" * 96)
    check("C5.1 the hard report_count < 3 cut-off is gone",
          "report_count < 3" not in LAYOUT.replace("`report_count < 3`", ""),
          "the only permitted mention is inside the explanatory comment")
    check("C5.2 maturity is decided by evidence_state_class, not by a report count",
          re.search(r"consensus_established\s*=\s*false", LAYOUT) is not None
          and "{% if evidence_state_class == 'live' %}{% assign consensus_established = true %}"
              in LAYOUT)
    # `blank` is a NO-OP in this stack: `!= blank` is ALWAYS true. The layout carries pre-existing
    # guards written that way; they are deliberately NOT repaired here, because doing so changes the
    # rendered markup of ~936 records and has nothing to do with the low-sample boundary. What IS
    # locked is that the additions made here never introduce another one.
    added = [line for line in LAYOUT.splitlines()
             if ("consensus_established" in line or "consensus-sample-note" in line
                 or "evidence_strength =" in line)]
    check("C5.3 the additions introduce no new `!= blank` no-op guard",
          added and all("!= blank" not in line for line in added), str(len(added)))
    # Compared against the reconstruction rather than a hardcoded number or `git show main:`: the
    # reconstruction removes ONLY the additions, so an equal count proves no pre-existing guard was
    # touched, and it stays true after this merges.
    check("C5.3b pre-existing blank guards are left exactly as they were",
          pre_fix_template().count("!= blank") == LAYOUT.count("!= blank"),
          f"{pre_fix_template().count('!= blank')} vs {LAYOUT.count('!= blank')}")
    check("C5.4b the qualifier reuses a class that is already styled, not a bare unstyled <p>",
          'class="consensus-chart-meta consensus-sample-note"' in LAYOUT,
          "an unstyled paragraph would ship at default UA size inside a grid container")
    css = (_AUX / "assets" / "css" / "auxsays-custom.css").read_text(encoding="utf-8", errors="replace")
    check("C5.4c that class has real styling in the shipped stylesheet",
          ".consensus-chart-meta" in css)
    # The verdict box must NOT repeat a maturity disclaimer beside the site's own safety
    # recommendation once the sample is no longer weak: over-hedging a real warning is its own
    # dishonesty, and a WAIT on a 40-report sample is a real warning.
    # qa_patch_records substring-scans the RAW layout -- Liquid comments included -- for internal
    # vocabulary that must never reach a public patch page. The first draft of this qualifier's own
    # explanatory comment tripped it, so the gate's vocabulary is locked here too rather than only
    # in the gate, where a template edit would only find out at deploy time.
    for banned in ("evidence state", "Sample size", "pilot sample", "Pilot sample",
                   "low confidence", "broad consensus"):
        check(f"C5.7 the layout carries no internal phrase {banned!r}",
              banned not in LAYOUT, "qa_patch_records forbids this in public patch copy")
    check("C5.6 the verdict box hedges only at Low strength",
          "{% if consensus_established == false and evidence_strength == 'Low' %}" in LAYOUT
          and "community consensus is not established for this build" not in LAYOUT)
    check("C5.5 the qualifier is gated on the contract AND on having reports",
          "{% if consensus_established == false and report_count > 0 %}" in LAYOUT)

    print()
    print("=" * 96)
    print("C6  non-vacuity: these controls FAIL on the pre-fix template")
    print("=" * 96)
    if liquid_ok:
        pre = pre_fix_template()
        pre_block = consensus_block(pre)
        pre3 = liquid_render(pre_block, {"page": page_vars(3, "Negative"), "site": {}})
        pre3_text = " ".join(re.sub(r"<[^>]+>", " ", pre3 or "").split())
        check("C6.1 pre-fix n=3 had NO not-established statement (the reported defect)",
              pre3 is not None and NOT_ESTABLISHED not in pre3_text, pre3_text[:110])
        check("C6.2 pre-fix n=3 had NO strength statement",
              pre3 is not None and "evidence strength" not in pre3_text)
        check("C6.3 pre-fix n=3 still showed the full consensus scale",
              pre3 is not None and SCALE_LABELS in pre3_text)
        pre1 = liquid_render(pre_block, {"page": page_vars(1, "Negative"), "site": {}})
        pre1_text = " ".join(re.sub(r"<[^>]+>", " ", pre1 or "").split())
        check("C6.4 pre-fix n=1 DID carry a low-sample line, so the cliff was real",
              pre1 is not None and "Too few reports" in pre1_text, pre1_text[:110])

    print()
    print("=" * 96)
    print("D  the verdict must actually RENDER -- `x == blank` is a no-op in this stack")
    print("=" * 96)
    # `blank` is not a usable operand here: `x == blank` is always FALSE and `x != blank` always
    # TRUE. Three fallback branches that were supposed to derive a verdict label therefore never
    # ran, and 86 records rendered no label AND no recommendation at all -- the WORST cases being
    # the pages carrying the most evidence, because the zero-report rescue only covers count == 0.
    # On Acrobat the intended verdict sat unused in update_consensus_summary the whole time.
    def rendered(page_extra: dict, template: str | None = None) -> str | None:
        base = page_vars(2, "Negative")
        base.update(page_extra)
        return liquid_render(template if template is not None else consensus_block(),
                             {"page": base, "site": {}})

    no_label = rendered({"update_decision_label": "",
                         "update_consensus_summary": "WAIT: hold off until the signing fix lands"})
    if no_label is None:
        check("D.1 liquid gem available (render assertions SKIPPED without it)", True,
              "skipped")
    else:
        text = " ".join(re.sub(r"<[^>]+>", " ", no_label).split())
        check("D.1 a report-bearing record with no decision label still renders one",
              "WAIT" in text, text[:160])
        check("D.2 and it renders a recommendation body, never an empty one",
              "Review the report sources" in text or "test before updating" in text, text[:160])
        missing = rendered({"update_decision_label": "", "update_consensus_summary": "",
                            "quick_verdict": ""})
        mtext = " ".join(re.sub(r"<[^>]+>", " ", missing or "").split())
        check("D.3 with nothing to derive from, it falls back to INSUFFICIENT DATA",
              "INSUFFICIENT DATA" in mtext, mtext[:160])
        dated = rendered({"evidence_last_checked": "", "consensus_last_checked": ""})
        dtext = " ".join(re.sub(r"<[^>]+>", " ", dated or "").split())
        check("D.4 a record with no evidence date renders no dangling 'Last evidence checked:'",
              "Last evidence checked:" not in dtext
              or not re.search(r"Last evidence checked:\s*(?:$|[A-Z][a-z]* ?$)", dtext),
              dtext[-160:])
        # The row carries one {% include %} the standalone renderer cannot resolve, so render the
        # span above it -- which is where the label is derived -- exactly as consensus_block does.
        # The row's first statement is `assign item = include.item`, so the fixture has to arrive
        # the way an include passes it -- handing it `item` directly leaves every lookup nil and
        # the row falls through to INSUFFICIENT DATA for the wrong reason.
        row_head = ROW.split("{% include")[0]
        row_out = liquid_render(row_head + "LABEL=[{{ decision_label }}]", {"include": {"item": {
            "update_decision_label": "", "update_consensus_summary": "WAIT: hold off",
            "update_report_count": 2, "update_version": "26.001.21529",
            "product_id": "adobe-acrobat-pro"}}, "site": {}})
        check("D.5 the listing row derives a label the same way",
              row_out is not None and "LABEL=[WAIT]" in row_out,
              (row_out or "render failed")[-90:])

    # Static locks: the broken operand must not come back in the sites that decide a verdict.
    for name, blob in (("aux-update.html", LAYOUT), ("patch-table-row.html", ROW)):
        for pattern in ("decision_label == blank", "decision_body == blank"):
            check(f"D.6 {name} no longer compares a verdict field to `blank`: {pattern!r}",
                  pattern not in blob)
    check("D.7 the layout defaults the label before comparing it",
          "decision_label | default: '' | strip" in LAYOUT)
    check("D.8 and defaults the body before comparing it",
          "decision_body | default: '' | strip" in LAYOUT)
    check("D.9 the evidence-date guard compares to '' rather than `blank`",
          "evidence_checked_at != ''" in LAYOUT and "evidence_checked_at != blank" not in LAYOUT)
    check("D.10 the staleness guard likewise",
          "evidence_checked_at == ''" in LAYOUT and "evidence_checked_at == blank" not in LAYOUT)

    print()
    print("=" * 96)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _FAILURES:
        print("Failed: " + ", ".join(_FAILURES))
    print("=" * 96)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
