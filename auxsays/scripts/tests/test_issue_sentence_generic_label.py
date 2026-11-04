#!/usr/bin/env python3
"""AUX-061: the patch page may not present the fallback bucket "general workflow reports" as an issue.

`_public_issue_bucket` files a report under "general workflow reports" when it recognises no theme.
That label means "no theme", not "a reported issue", yet the "Current reports mention ..." line in
auxsays/_layouts/aux-update.html listed it next to real issues. The template now drops it from BOTH
inputs of the issue cluster (`page.evidence_samples`, then the `page.complaint_themes` fallback) by an
exact match on the stripped, lower-cased label, keeps the three-label limit on the labels that remain,
and falls back to the truthful "User reports are present" line when nothing specific remains.

These render the REAL shipped Liquid layout with the liquid gem. They SKIP the render assertions when
Ruby/liquid is unavailable (CI installs the gem, so they run there for real). The static locks always run.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_issue_sentence_generic_label.py
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
LAYOUT = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
MATURITY_INCLUDE = (_AUX / "_includes" / "maturity-state.html").read_text(encoding="utf-8")
MATURITY_TAG = re.compile(r"\{%-?\s*include\s+maturity-state\.html\s+record=([\w.]+)\s*-?%\}")

GENERIC = "general workflow reports"
FALLBACK_MSG = "User reports are present; review the source list before updating critical work."

_PASS = 0
_FAIL = 0
_FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


_RENDER_SCRIPT = """
require 'liquid'
require 'json'
payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
print tpl.render!(payload['vars'])
"""


def layout_block(text: str = LAYOUT) -> str:
    """Front-matter end .. before the first non-maturity include (holds the whole reasoning block)."""
    expanded = MATURITY_TAG.sub(lambda m: MATURITY_INCLUDE.replace("include.record", m.group(1)), text)
    lines = expanded.split("\n")
    end = next((i for i, line in enumerate(lines) if "{% include" in line), len(lines))
    return "\n".join(lines[3:end])


def render(page: dict, template: str | None = None) -> str | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_SCRIPT, encoding="utf-8")
        payload = Path(td) / "payload.json"
        payload.write_text(json.dumps({"template": template or layout_block(),
                                       "vars": {"page": page, "site": {}}}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            print(proc.stderr[-400:])
            return None
        return proc.stdout


def page(count: int = 3, samples=None, themes=None, body: str | None = None) -> dict:
    p = {
        "update_report_count": count,
        "confirmed_patch_specific_report_count": count,
        "update_consensus_label": "Negative",
        "consensus_collection_status": "pilot_initial_sample",
        "evidence_state": "pilot_sample" if count else "official_only",
        "official_source_captured": True,
        "update_published_at": "2026-07-29T00:00:00Z",
        "evidence_last_checked": "2026-08-30T07:17:03Z",
        "update_product": "OBS Studio",
        "update_version": "99.0.0",
        "url": "/updates/obs-project/obs-studio/99-0-0/",
    }
    if samples is not None:
        p["evidence_samples"] = [{"issue": s} for s in samples]
    if themes is not None:
        p["complaint_themes"] = [{"theme": t} for t in themes]
    if body is not None:
        p["update_decision_body"] = body
    return p


def reasoning(p: dict) -> str | None:
    out = render(p)
    if out is None:
        return None
    m = re.search(r'<div class="update-decision-reasoning">(.*?)</div>', out, re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split()) if m else ""


def issue_line(r: str) -> str | None:
    m = re.search(r"Current reports mention (.*?)\.(?: |$)", r)
    return m.group(1) if m else None


def well_formed(r: str) -> bool:
    """No empty sentence, doubled punctuation, stray comma or dangling lead-in."""
    return not re.search(r"mention\s*\.|,\s*,|\.\.|,\s*\.|mention\s*,|mention$|\s,|mention\s+and\b", r)


def run() -> int:
    print("[A] static locks")
    check("template defines the exact generic label once", LAYOUT.count("assign issue_generic_label = 'general workflow reports'") == 1)
    check("both inputs compare the normalised label for exact inequality",
          LAYOUT.count("issue_label_norm != issue_generic_label") == 2)
    check("no substring exclusion of the generic label (no 'contains' on it)",
          "contains issue_generic_label" not in LAYOUT and "contains 'general workflow" not in LAYOUT)
    check("normalisation is downcase + strip",
          "assign issue_label_norm = issue_label | downcase | strip" in LAYOUT)
    check("existing truthful fallback message is still in the template", FALLBACK_MSG in LAYOUT)
    check("nearby comment no longer calls the generic bucket real information",
          '"general workflow reports" on the DaVinci records' not in LAYOUT)

    if shutil.which("ruby") is None or render(page(0)) is None:
        print("  SKIP  render assertions (ruby/liquid unavailable)")
        return _summary()

    print("[B] only the generic label -> truthful fallback message")
    r = reasoning(page(samples=[GENERIC]))
    check("evidence_samples only generic: no 'Current reports mention'", r is not None and "Current reports mention" not in r, r or "")
    check("evidence_samples only generic: fallback message shown", r is not None and FALLBACK_MSG in r, r or "")
    check("generic label not shown anywhere", r is not None and GENERIC not in r.lower(), r or "")
    r = reasoning(page(samples=[GENERIC, GENERIC.upper(), "  General Workflow Reports  "]))
    check("case and whitespace variants are also removed", r is not None and "Current reports mention" not in r and FALLBACK_MSG in r, r or "")
    r = reasoning(page(samples=[", " + GENERIC]))
    check("leading comma variant is also removed", r is not None and "Current reports mention" not in r and FALLBACK_MSG in r, r or "")

    print("[C] generic label followed by / mixed with specific issues")
    r = reasoning(page(samples=[GENERIC, "capture-source issues in camera source workflow"]))
    check("generic dropped, specific kept",
          r is not None and issue_line(r) == "capture-source issues in camera source workflow", r or "")
    r = reasoning(page(samples=["audio mixer or routing issues in audio mixer UI", GENERIC, "capture-source issues"]))
    check("order of the specific labels is preserved",
          r is not None and issue_line(r) == "audio mixer or routing issues in audio mixer UI, capture-source issues", r or "")
    check("mixed output is well formed", r is not None and well_formed(r), r or "")

    print("[D] a fourth label takes the freed slot; limit stays three")
    r = reasoning(page(samples=["alpha problems", GENERIC, "beta problems", "gamma problems", "delta problems"]))
    check("three-label limit kept after the filter", r is not None and issue_line(r) == "alpha problems, beta problems, gamma problems", r or "")
    r = reasoning(page(samples=["alpha problems", "beta problems", "gamma problems", "delta problems"]))
    check("three valid labels: unchanged, only three shown", r is not None and issue_line(r) == "alpha problems, beta problems, gamma problems", r or "")

    print("[E] exact match only: a specific label containing the words survives")
    label = "general workflow reports of sync failures in cloud sync"
    r = reasoning(page(samples=[label]))
    check("longer label containing the phrase is kept", r is not None and issue_line(r) == label, r or "")
    r = reasoning(page(samples=["workflow reports"]))
    check("shorter label is kept", r is not None and issue_line(r) == "workflow reports", r or "")

    print("[F] complaint_themes path")
    r = reasoning(page(themes=[GENERIC]))
    check("complaint_themes only generic: fallback message", r is not None and "Current reports mention" not in r and FALLBACK_MSG in r, r or "")
    r = reasoning(page(themes=[GENERIC, "login failures"]))
    check("complaint_themes generic + specific: specific kept", r is not None and issue_line(r) == "login failures", r or "")
    r = reasoning(page(samples=[GENERIC], themes=["login failures", GENERIC, "sync delays"]))
    check("generic-only evidence_samples falls through to filtered complaint_themes",
          r is not None and issue_line(r) == "login failures, sync delays", r or "")
    r = reasoning(page(samples=["capture-source issues"], themes=["login failures"]))
    check("evidence_samples still wins over complaint_themes", r is not None and issue_line(r) == "capture-source issues", r or "")

    print("[G] zero reports and no labels")
    r = reasoning(page(count=0, samples=[GENERIC]))
    check("zero reports: no issue sentence and no fallback message", r is not None and "Current reports mention" not in r and FALLBACK_MSG not in r, r or "")
    r = reasoning(page(count=2))
    check("reports but no labels: fallback message", r is not None and FALLBACK_MSG in r and "Current reports mention" not in r, r or "")

    print("[H] decision-body de-duplication is unchanged")
    body = "Current reports mention capture-source issues."
    r = reasoning(page(samples=["capture-source issues in camera source workflow"], body=body))
    check("specific subject already in body: sentence not repeated",
          r is not None and "Current reports mention capture-source issues in camera" not in r, r or "")
    r = reasoning(page(samples=["capture-source issues in camera source workflow", "audio mixer or routing issues"], body=body))
    check("a subject the body omits keeps the sentence",
          r is not None and issue_line(r) == "capture-source issues in camera source workflow, audio mixer or routing issues", r or "")
    r = reasoning(page(samples=[GENERIC, "capture-source issues in camera source workflow"], body=body))
    check("generic does not count as a 'missing subject' that would keep a redundant sentence",
          r is not None and GENERIC not in r.lower() and "Current reports mention capture-source issues in camera" not in r, r or "")

    print("[I] well-formedness across all cases")
    cases = [page(samples=[GENERIC]), page(themes=[GENERIC]), page(samples=[GENERIC, "a problems", GENERIC, "b problems"]),
             page(samples=["a problems", "b problems", "c problems"]), page(count=0), page(count=1)]
    outs = [reasoning(c) for c in cases]
    check("no empty sentence, doubled punctuation or stray comma in any case",
          all(o is not None and well_formed(o) for o in outs), " | ".join(o or "None" for o in outs))
    check("no empty reasoning paragraph when reports exist",
          all((o or "").strip() for o, c in zip(outs, cases) if c["update_report_count"] > 0))

    print("[J] non-vacuity: the pre-fix template shows the defect")
    pre = LAYOUT.replace("issue_label != '' and issue_label_norm != issue_generic_label", "issue_label != ''")
    out = render(page(samples=[GENERIC, "capture-source issues"]), layout_block(pre))
    m = re.search(r'<div class="update-decision-reasoning">(.*?)</div>', out or "", re.S)
    txt = " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split()) if m else ""
    check("with the filter removed the generic label is listed", GENERIC in txt, txt)
    return _summary()


def _summary() -> int:
    print(f"\n{_PASS} passed, {_FAIL} failed")
    if _FAILURES:
        for f in _FAILURES:
            print(f"  FAILED: {f}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
