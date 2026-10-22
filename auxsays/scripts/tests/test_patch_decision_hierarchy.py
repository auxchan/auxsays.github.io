#!/usr/bin/env python3
"""The patch page answers the decision before it explains the evidence.

AUXSAYS exists to answer one question -- should I install this update, wait, test it, or avoid
it? -- and the page that answers it used to emit, in order: identity, a community-sentiment word
on a three-zone graph, the AUXSAYS verdict, and then a full collection-telemetry card. Measured on
a 390x844 phone before this change, the verdict word sat 170px BELOW the fold while the only
categorical word above it was the raw sample sentiment. Those are different axes: on 217 records
they point in opposite directions, and nothing on the page said so.

WHAT WAVE A CHANGED, and what each of these checks protects:

  ORDER. The decision box now precedes the community-evidence card (A1). Nothing else about the
  decision moved: the label still comes from the one authority in lib/patch_decision.py, mirrored
  for Liquid in _data/patch_verdicts.yml, and A3/A17 refuse a second ladder.

  AXES. The evidence card's lead-in is "Community signal", not "Evidence summary" (A2), and the
  sample's strength carries its own label (A7). The values are untouched -- this is about a reader
  not parsing a sentiment word under a verdict as a competing recommendation.

  GRAPH. The three-zone scale renders only where counted reports exist (A4/A6). On a zero-report
  record it drew a bar, a marker and a caption restating the "0 confirmed patch-specific community
  reports" line directly above it, on 1,073 of 1,292 records. The honesty STATEMENT survives that
  removal (A5) -- dropping the bar was about height, dropping the sentence would have been about
  honesty, and the first attempt at this did drop it until C1.7 in the sample-honesty suite caught
  it.

  MONITORING. The hero carries a one-line status and the full card moved to a #monitoring
  disclosure (A9). Both render the SAME derived `mon_status` from monitoring-status.html, which is
  the monitoring authority: A8 refuses a second derivation anywhere outside that include, and A10
  refuses a treatment that would make a blocked or stale collection anything less than visible
  words.

  REASONING. The issue sentence is suppressed only when every subject it names is already in the
  decision body (A11), and survives whenever it names one the body omits (A12/A13). Measured over
  the rendered corpus: 66 suppressed, 153 kept, 0 misclassified. Those COUNTS are deliberately not
  asserted -- scheduled collectors move them -- so the fixtures below pin the semantics instead.

WHAT WAVE A DID NOT DO, and these refuse to let it drift into:
  A14/A15 keep the security-sensitive and official-additions paths. Both are sparsely populated
  (0 and 1 records today) and sparse is not dead: one populated record proves a live producer
  contract, and the security path intersects deferred AUX-005 work.
  A16 refuses to publish `status_events`. Its SHAPE fits the History block exactly (at|label|note
  on all 3,305 events), which is the trap -- its CONTENT is internal pipeline state: 1,290 "record
  initialized", 720 "User report count updated to N". History stays hidden until a producer writes
  a public-safe event stream.

Needs ruby + the liquid gem. Without them L1 fails and the render checks fail with it rather than
skipping, like the other rendering suites here.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_decision_hierarchy.py
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
MON_PATH = _AUX / "_includes" / "monitoring-status.html"
CSS_PATH = _AUX / "assets" / "css" / "auxsays-custom.css"
DATA_DIR = _AUX / "_data"

LAYOUT = LAYOUT_PATH.read_text(encoding="utf-8")
MON = MON_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")
COMMENT_RE = re.compile(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", re.S)
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
# Comments explain the defects by name, so every "must not appear" assertion reads EMITTING markup.
LAYOUT_EMITTED = COMMENT_RE.sub("", LAYOUT)
MON_EMITTED = COMMENT_RE.sub("", MON)

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


# --------------------------------------------------------------------------- ruby bridge

_DRIVER = r"""
require 'liquid'
require 'json'
module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def markdownify(i) = i.to_s
  def date_to_string(i) = i.to_s
  def date_to_long_string(i) = i.to_s
  def number_with_delimiter(i) = i.to_s
end
Liquid::Template.register_filter(Shims)

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
    path += ".html" unless File.exist?(path)
    return "" unless File.exist?(path)
    vals = {}
    @params.each do |k, v|
      vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v]
    end
    partial = (context.registers[:cache] ||= {})[path] ||=
      Liquid::Template.parse(File.read(path, encoding: "utf-8").sub(/\A---\n.*?\n---\n/m, ""))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)

payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload["template"])
out = {}
payload["cases"].each do |name, page|
  begin
    out[name] = tpl.render!({ "site" => payload["site"], "page" => page, "content" => "" },
                            registers: { include_root: payload["includes"] })
  rescue => e
    out[name] = "<<ERR: #{e.class}: #{e.message}>>"
  end
end
print JSON.generate(out)
"""


def site_payload() -> dict:
    import yaml
    data = {}
    for f in sorted(DATA_DIR.glob("*.yml")):
        try:
            data[f.stem] = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"time": "2026-10-14T00:00:00Z", "title": "AUXSAYS",
            "url": "https://auxsays.com", "data": data}


def run_liquid(cases: dict, template: str | None = None) -> tuple[bool, dict]:
    """Render the SHIPPED layout. A missing ruby is a FAIL, never a skip."""
    ruby = shutil.which("ruby")
    if not ruby:
        return False, {}
    tmp = Path(tempfile.mkdtemp(prefix="auxsays-waveA-"))
    try:
        script = tmp / "d.rb"
        script.write_text(_DRIVER, encoding="utf-8")
        payload = tmp / "p.json"
        payload.write_text(json.dumps({
            "template": FRONT_MATTER_RE.sub("", template if template is not None else LAYOUT),
            "cases": cases, "site": site_payload(),
            "includes": str(_AUX / "_includes"),
        }), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)],
                              capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0 or not proc.stdout.strip():
            return False, {"_stderr": (proc.stderr or "")[:500]}
        return True, json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        return False, {"_stderr": repr(exc)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TAGS = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def visible(html: str) -> str:
    return WS.sub(" ", TAGS.sub(" ", html)).strip()


def page(**over) -> dict:
    """A minimal but REAL page payload; overrides drive each fixture."""
    base = {
        "product_id": "obs-studio", "company_id": "obs-project",
        "update_product": "OBS Studio", "update_version": "32.1.2",
        "update_detail_title": "OBS Studio 32.1.2",
        "update_published_at": "2026-04-21T00:00:00Z",
        "update_report_count": 0,
        "evidence_state": "Official source only",
        "update_source_url": "https://example.test/notes",
        "update_source_name": "OBS Project",
    }
    base.update(over)
    return base


# Fixtures A-F pin the issue-sentence rule by SEMANTICS, not by today's corpus counts.
BODY_EXACT = "Current reports mention audio routing and capture-source failures."
BODY_GENERIC = "Hold this build off production systems while reports settle."
BODY_PARTIAL = "Current reports mention audio routing."
BODY_TWO = "Current reports mention audio routing and capture-source failures."


def ev(*issues):
    """evidence_samples shaped as the layout reads them, one issue per sample."""
    return [{"issue": i, "source_url": "https://e.test/%d" % n, "source_name": "src",
             "source_title": "report %d" % n} for n, i in enumerate(issues)]


DEDUP_CASES = {
    # A: every subject already in the body -> suppressed
    "A_exact": page(update_report_count=4, update_decision_body=BODY_EXACT,
                    evidence_samples=ev("audio routing", "capture-source failures")),
    # B: body names no subject -> retained
    "B_generic": page(update_report_count=4, update_decision_body=BODY_GENERIC,
                      evidence_samples=ev("audio routing", "capture-source failures")),
    # C: body names one of two -> retained, because the second adds information
    "C_partial": page(update_report_count=4, update_decision_body=BODY_PARTIAL,
                      evidence_samples=ev("audio routing", "capture-source failures")),
    # D: body names two of three -> retained
    "D_three": page(update_report_count=6, update_decision_body=BODY_TWO,
                    evidence_samples=ev("audio routing", "capture-source failures",
                                        "render/export failures")),
    # E: same subjects, different order -> suppressed; order is not information
    "E_order": page(update_report_count=4, update_decision_body=BODY_EXACT,
                    evidence_samples=ev("capture-source failures", "audio routing")),
    # F: no cluster at all -> no "Current reports mention" sentence
    "F_empty": page(update_report_count=4, update_decision_body=BODY_GENERIC,
                    evidence_samples=[]),
    # the theme suffix the producer appends is internal taxonomy, not an added subject
    "G_theme": page(update_report_count=4, update_decision_body=BODY_EXACT,
                    evidence_samples=ev("audio routing in audio", "capture-source failures in capture")),
}

# Collection Health must not depend on technical metadata. `technical_details_renderable` is true
# when a record has a checksum, a file size, a source-checked date, an official-notes-checked date
# OR a release date -- and nearly every record has a release date, which is exactly what hid the
# defect this fixture exists for. The hero's compact line and the section nav both emit
# href="#monitoring" unconditionally, so a record with none of those fields got two links to an id
# that did not exist and no reachable audit trail.
NO_TECH = {
    "update_published_at": "", "patch_file_size": "", "official_checksums_body": "",
    "source_last_checked": "", "official_body_last_checked": "",
}

STATE_CASES = {
    # every input to technical_details_renderable blanked
    "no_technical_details": page(update_report_count=2, update_consensus_label="Negative",
                                 evidence_samples=ev("audio routing"), **NO_TECH),
    # the same record WITH technical metadata, to prove the fix did not duplicate monitoring
    "with_technical_details": page(update_report_count=2, update_consensus_label="Negative",
                                   evidence_samples=ev("audio routing"),
                                   patch_file_size="150 MB",
                                   source_last_checked="2026-10-01T00:00:00Z"),
    "zero_reports": page(update_report_count=0),
    "one_report": page(update_report_count=1, update_consensus_label="Negative",
                       evidence_samples=ev("audio routing")),
    "high_evidence": page(update_report_count=107, update_consensus_label="Negative",
                          evidence_state="consensus_live", evidence_samples=ev("audio routing")),
    "degraded_monitoring": page(update_report_count=3, update_consensus_label="Negative",
                                evidence_samples=ev("audio routing")),
}


# The issue sentence must be located as an ELEMENT. Searching the page for the phrase
# "Current reports mention" matches the DECISION BODY too -- four products' bodies open with
# exactly those words, which is the whole reason this de-duplication exists. A substring test
# therefore reports "not suppressed" on every record where the rule fired correctly, and passes
# for the wrong reason on records where the body happens to carry the phrase.
ISSUE_P = re.compile(r"<p>Current reports mention ([^<]*)\.</p>")


def issue_sentence(html: str) -> str | None:
    """The rendered issue-cluster sentence, or None when the rule suppressed it."""
    m = ISSUE_P.search(html or "")
    return m.group(1) if m else None
NOT_ESTABLISHED = "Community consensus not established"
SCALE = "consensus-scale-labels"


def run() -> int:
    # ---- static contract on the shipped source -------------------------------------
    v_at = LAYOUT_EMITTED.find('id="verdict"')
    e_at = LAYOUT_EMITTED.find("update-evidence-card")
    check("A1 the verdict markup precedes the community-evidence markup",
          -1 < v_at < e_at, f"verdict@{v_at} evidence@{e_at}")

    check("A2 the evidence card is labelled 'Community signal', not a second verdict",
          "<strong>Community signal:</strong>" in LAYOUT_EMITTED
          and "<strong>Evidence summary:</strong>" not in LAYOUT_EMITTED,
          "a sentiment word under the verdict must not read as another recommendation")

    check("A3 the published verdict still comes from the stored decision label",
          "{{ decision_label }}" in LAYOUT_EMITTED
          and "site.data.patch_verdicts" in LAYOUT_EMITTED,
          "the label must stay the authority's, not be recomputed here")

    # A17: no second ladder. The canonical order lives in patch_decision.py / patch_verdicts.yml;
    # a layout that enumerates verdict words in priority order is a competing ranking.
    ladder = re.findall(r"AVOID|SAFE ENOUGH|TEST FIRST", LAYOUT_EMITTED)
    check("A17 the layout introduces no second verdict ladder",
          len(ladder) == 0,
          f"verdict words hardcoded in emitting markup: {sorted(set(ladder))}")

    check("A8 only monitoring-status.html derives the monitoring state",
          "mon_status" not in LAYOUT_EMITTED and "mon_status =" in MON_EMITTED,
          "a second derivation lets the hero and the audit card disagree")

    check("A9 the full monitoring card is still reachable, in a disclosure",
          'id="monitoring"' in LAYOUT_EMITTED
          and "monitoring-status.html mode='full'" in LAYOUT_EMITTED
          and 'href="#monitoring"' in LAYOUT_EMITTED,
          "moving the audit trail must not remove it")

    check("A10 a degraded collection state stays visible without colour",
          "MONITORING DEGRADED" in MON_EMITTED and "COLLECTION BLOCKED" in MON_EMITTED
          and "update-monitoring-compact--monitoring-degraded" in CSS,
          "the state is carried as words; the border only reinforces it")

    check("A14 security-sensitive support remains in the layout",
          "security_sensitive" in LAYOUT, "sparse is not dead; AUX-005 depends on this path")
    check("A15 structured official additions/fixes support remains",
          "official_additions" in LAYOUT and "official_fixes" in LAYOUT,
          "one populated record still proves a live producer contract")
    check("A16 internal status_events are not rendered as public History",
          not re.search(r"page\.status_events", LAYOUT_EMITTED),
          "61% of those events are ingestion/collector state and must not reach a reader")

    # ---- rendered behaviour ---------------------------------------------------------
    print()
    ok, out = run_liquid({**DEDUP_CASES, **STATE_CASES})
    check("L1 the liquid gem is available, so the render checks run for real", ok,
          str(out.get("_stderr", ""))[:300])
    errs = {k: v[:200] for k, v in out.items() if isinstance(v, str) and v.startswith("<<ERR")}
    check("L2 every fixture renders without error", ok and not errs, str(errs)[:400])

    def t(name):
        return visible(out.get(name, "")) if ok else ""

    # A11/A12/A13 -- the de-duplication semantics, pinned by fixture not by corpus count
    def iss(name):
        return issue_sentence(out.get(name, "")) if ok else "<unrendered>"

    check("A11 CASE A: every subject already in the body suppresses the sentence",
          iss("A_exact") is None, repr(iss("A_exact")))
    check("A12 CASE B: a generic body keeps the issue sentence",
          (iss("B_generic") or "").find("audio routing") >= 0, repr(iss("B_generic")))
    check("A12b CASE C: a body naming ONE of two subjects keeps the sentence",
          (iss("C_partial") or "").find("capture-source failures") >= 0,
          "suppressing here would lose a subject the reader never saw: "
          + repr(iss("C_partial")))
    check("A13 CASE D: a body naming two of three subjects keeps the sentence",
          (iss("D_three") or "").find("render/export failures") >= 0, repr(iss("D_three")))
    check("A13b CASE E: the same subjects in a different order still suppress",
          iss("E_order") is None, "order is not information: " + repr(iss("E_order")))
    check("A13c CASE F: an empty cluster renders no issue sentence at all",
          iss("F_empty") is None, repr(iss("F_empty")))
    check("A13d the producer's theme suffix is not mistaken for an added subject",
          iss("G_theme") is None,
          "'audio routing in audio' names the same subject as 'audio routing': "
          + repr(iss("G_theme")))

    # A4/A5/A6/A7 -- the graph and the honesty statement
    check("A4 a zero-report page renders no sentiment-position graph",
          SCALE not in out.get("zero_reports", "") if ok else False)
    check("A5 a zero-report page still states that consensus is not established",
          NOT_ESTABLISHED in t("zero_reports"), t("zero_reports")[:200])
    check("A6 a report-bearing page keeps the community graph",
          SCALE in out.get("high_evidence", "") if ok else False)
    check("A7 a report-bearing page carries an explicit evidence strength",
          "Evidence strength:" in t("high_evidence")
          and "Evidence strength:" not in t("zero_reports"),
          "strength is a property of a sample; with no sample there is none to state")

    # ---- A9b: Collection Health is independent of Technical Details ------------------
    #
    # A9 above proves the three strings EXIST in the source. That is not the property: it says
    # nothing about whether they coexist in the branch where technical metadata is absent, which
    # is precisely where they did not. These assertions drive the rendered document instead.
    nt = out.get("no_technical_details", "") if ok else ""
    wt = out.get("with_technical_details", "") if ok else ""

    check("A9b a record with NO technical metadata still renders compact monitoring",
          "update-monitoring-compact" in nt)
    check("A9c ...and still links to the collection detail",
          'href="#monitoring"' in nt)
    check("A9d ...and the link has a target in the SAME rendered document",
          'id="monitoring"' in nt,
          "two links to an id that does not exist, and no reachable audit trail")
    check("A9e ...and the full monitoring card renders inside that disclosure",
          "update-monitoring-card" in nt and "Healthy sources" in nt,
          "the disclosure must carry the audit trail, not just the id")
    check("A9f ...while Technical Details correctly does NOT render",
          'id="technical-details"' not in nt,
          "the gate itself must still work; this fixture blanks every input to it")

    check("A9g a record WITH technical metadata renders both, and monitoring exactly once",
          wt.count('id="monitoring"') == 1 and 'id="technical-details"' in wt,
          f"monitoring ids={wt.count('id=' + chr(34) + 'monitoring' + chr(34))}")

    # Every anchor must resolve, in every rendered fixture -- behaviourally, not by grep.
    dangling = []
    for name, html in (out.items() if ok else []):
        if not isinstance(html, str) or html.startswith("<<ERR"):
            continue
        for frag in set(re.findall(r'href="#([a-z-]+)"', html)):
            if ('id="%s"' % frag) not in html:
                dangling.append((name, frag))
    check("A9h every in-page anchor resolves to an id in the same document",
          ok and not dangling, f"dangling: {dangling[:6]}")

    # the compact line is present and does not restate the count the card already gives
    check("A8b the hero carries the compact monitoring line, not the full card",
          "update-monitoring-compact" in out.get("zero_reports", "")
          if ok else False)
    check("A8c the compact line does not restate the report count",
          ok and not re.search(r"update-monitoring-compact__detail\"[^>]*>\s*\d+ accepted",
                               out.get("high_evidence", "")),
          "the evidence card directly above already states it")

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
