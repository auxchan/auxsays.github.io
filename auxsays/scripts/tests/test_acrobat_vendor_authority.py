#!/usr/bin/env python3
"""Adobe official information must not be counted as user consensus.

Adobe publishes its own release announcements as ordinary Adobe Community threads. Three rows titled
"Adobe Acrobat and Reader DC - June 2021 Update Release" were counted as user bug reports.

The authority test is TITLE-anchored and reads nothing else. That is the load-bearing safety
property, and A4 pins it directly: a title is short and is stored whole, so what the rule sees in
production is exactly what the corpus lets us audit, whereas the body is truncated to 280 chars in
storage but ~6000 at collection -- an ~18x gap that makes any body rule unvalidatable here. A
Problem/Solution support-document rule was built and rejected for exactly that reason; A6 pins the
decision so it is not silently reintroduced.

Every fixture marked CORPUS is verbatim from auxsays/_data/consensus_evidence.yml. A guard validated
only against probes its author wrote proves nothing.

Offline: no network, no repo writes.
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402

from patch_collectors import adobe_acrobat_community as ac  # noqa: E402
from patch_collectors.base import PatchRecord  # noqa: E402

P = "adobe-acrobat-pro"
VER = "26.001.21563"
CAPTURED = "2026-06-02T00:00:00Z"
THREAD = "https://community.adobe.com/t5/acrobat-discussions/some-thread/td-p/1234567"
REC_P = PatchRecord(P, VER, Path(f"2026-05-18-{P}-26-001-21563.md"), "2026-05-18T00:00:00Z", "current", "Adobe Acrobat Pro")

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def authority(title: str, body: str = "") -> str:
    return ac.acrobat_vendor_authority(title, body)


ANNOUNCE_TITLE = "Adobe Acrobat and Reader DC – June 2021 Update Release"  # CORPUS

# CORPUS titles of genuine member reports that must survive untouched.
GENUINE = [
    "“Update failed” manually trying to check for updates in 64-bit Adobe Acrobat Reader Document Cloud",
    "'Not Responding' After upgrade. Adobe Acrobat Reader DC - 19.012.20040 upgrading to 19.021.20047",
    "19.021.20058 update fails on Mac",
    "AIP plugin for Adobe Acrobat Reader not installing",
    "AcroRd32.exe Not closing on Xenapp Terminal Server",
    "Acrobat Freezes when combining PDF and Word",
    "Acrobat Pro 2017 Mac Install Issues",
    "Acrobat Pro DC - Installation Failed (Windows 10)",
    "Acrobat Pro DC Stops Responding when opened.",
    "Acrobat Pro DC crashes when processing digital signatures",
    "Acrobat Pro DC installation failure || Error: Exit Code 7|| Mac OS Sierra",
    "Acrobat Pro DC reinstall fails",
    "Acrobat Pro keeps crashing while editing a document",
    "Acrobat Reader Crashes when view on internet explorer",
    # The closest non-official call in the corpus: a genuine report with exactly ONE first-person
    # token. Any pronoun-density rule destroys it; this rule must not depend on pronouns at all.
    "Editing an annotation or comment changes the username on Acrobat Pro Desktop versions",
]

# CORPUS member prose carrying a literal "problem:" mid-sentence. These are COUNTED rows today (all
# DaVinci, so no Acrobat rule reaches them) and they are why the support-document rule was rejected:
# the label is ordinary English, not a document structure.
CORPUS_MEMBER_PROBLEM_PROSE = [
    "Here's the problem: When Render Cache -> User is enabled",
    "keep running into a problem: I'm getting the \"No frame available for MediaOut1\" error",
    "have the following problem: when I write text in Affinity 3",
]


def run() -> int:
    print("=" * 96)
    print("A1  the June 2021 release announcement is refused")
    print("=" * 96)
    check("A1.1 announcement title -> vendor_release_announcement",
          authority(ANNOUNCE_TITLE) == "vendor_release_announcement", authority(ANNOUNCE_TITLE))
    for variant in ("Acrobat DC – May 2020 Update Release",
                    "Acrobat Reader release notes for 21.005",
                    "Announcing Acrobat 2020 availability",
                    "Acrobat 24 is now available"):
        check(f"A1.2 announcement shape refused: {variant[:44]!r}", bool(authority(variant)), variant)

    print()
    print("=" * 96)
    print("A2  genuine member reports survive (CORPUS titles)")
    print("=" * 96)
    kept = [t for t in GENUINE if authority(t, "Acrobat crashes after the update, error 1603.") == ""]
    check(f"A2.1 all {len(GENUINE)} corpus titles kept", len(kept) == len(GENUINE),
          f"lost: {[t for t in GENUINE if t not in kept]}")

    print()
    print("=" * 96)
    print("A3  title-anchored: a member may DISCUSS a release without becoming one")
    print("=" * 96)
    check("A3.1 'update release' in the BODY does not refuse",
          authority("Acrobat crashes after updating", "Ever since the June 2021 update release my Acrobat crashes.") == "")
    check("A3.2 'announcement' in the BODY does not refuse",
          authority("Acrobat Pro DC will not launch", "I saw the announcement and installed it; now it will not launch.") == "")
    check("A3.3 a member asking ABOUT release notes is still not an announcement",
          authority("Where do I find what changed", "Are there release notes for this build?") == "")

    print()
    print("=" * 96)
    print("A4  the rule reads the TITLE ONLY -- the property that makes it auditable")
    print("=" * 96)
    # If the body were consulted, this rule could not be validated: production passes ~6000 chars
    # while the corpus stores 280, so a body rule is measured against ~5% of its real input.
    hostile_body = ("update release release notes what's new announcing announcement "
                    "is now available new release " * 40)
    check("A4.1 every announcement token in a 6000-char body changes nothing",
          authority("Acrobat Pro DC crashes on launch", hostile_body) == "",
          authority("Acrobat Pro DC crashes on launch", hostile_body))
    check("A4.2 body is irrelevant: same verdict for empty and hostile body",
          authority("Acrobat Pro DC crashes on launch", "") == authority("Acrobat Pro DC crashes on launch", hostile_body))
    check("A4.3 refusal is driven by the title alone",
          authority(ANNOUNCE_TITLE, "") == "vendor_release_announcement")
    src = (ROOT / "scripts" / "patch_collectors" / "adobe_acrobat_community.py").read_text(encoding="utf-8")
    fn = src.split("def acrobat_vendor_authority", 1)[1].split("\ndef ", 1)[0]
    check("A4.4 the function body never reads its `text` argument",
          "text" not in fn.split('"""')[2] if fn.count('"""') >= 2 else False,
          "text is referenced in code, not just the docstring")

    print()
    print("=" * 96)
    print("A5  failure words must NOT cancel the refusal  (the original defect mechanism)")
    print("=" * 96)
    fixes = ("This release fixes a crash on launch, an error when saving, corrupt output in "
             "Distiller and a freeze in the comment pane.")
    check("A5.1 announcement full of failure words is still refused",
          authority(ANNOUNCE_TITLE, fixes) == "vendor_release_announcement", authority(ANNOUNCE_TITLE, fixes))
    check("A5.2 sanity: those failure words DO satisfy the old cancellation path",
          bool(ac._GENUINE_FAILURE_RE.search(fixes.lower())))

    print()
    print("=" * 96)
    print("A6  the support-document rule stays OUT (rejected, not forgotten)")
    print("=" * 96)
    check("A6.1 no Problem/Solution regex is defined", not hasattr(ac, "ACROBAT_SUPPORT_DOC_RE"))
    check("A6.2 no vendor_support_document verdict is reachable",
          "vendor_support_document" not in fn)
    for prose in CORPUS_MEMBER_PROBLEM_PROSE:
        body = f"Acrobat Pro {VER} is broken. {prose} Solution: reinstall it."
        check(f"A6.3 corpus member prose not refused: {prose[:40]!r}",
              authority("Acrobat Pro DC will not print", body) == "")
    check("A6.4 the rejection is documented at the code site",
          "NOT IMPLEMENTED, deliberately" in src and "1288217" in src)

    print()
    print("=" * 96)
    print("A7  the acceptance GATE fires end-to-end (not just the predicate)")
    print("=" * 96)
    body = f"Adobe Acrobat Pro {VER} crashes on launch after this update."
    ann = ac.row_from_candidate(P, REC_P, {
        "report_title": "Adobe Acrobat Pro DC - June 2021 Update Release", "report_text": body,
        "source_url": THREAD, "source_date": "2026-06-01",
        "source_type": ac.ADOBE_COMMUNITY_SOURCE_TYPE}, CAPTURED)
    check("A7.1 announcement row counted=False", ann.get("counted") is False, str(ann.get("counted")))
    check("A7.2 reason is specific, not 'not_a_real_issue_report'",
          ann.get("exclusion_reason") == "vendor_release_announcement", str(ann.get("exclusion_reason")))
    ok = ac.row_from_candidate(P, REC_P, {
        "report_title": "Acrobat Pro keeps crashing while editing a document", "report_text": body,
        "source_url": THREAD, "source_date": "2026-06-01",
        "source_type": ac.ADOBE_COMMUNITY_SOURCE_TYPE}, CAPTURED)
    check("A7.3 a genuine report still counts through the same gate",
          ok.get("counted") is True, str(ok.get("exclusion_reason")))
    # A member thread whose helper answers with a solution: the rejected rule refused this
    # end-to-end. It must count.
    helped = ac.row_from_candidate(P, REC_P, {
        "report_title": "Acrobat Pro will not print since the update",
        "report_text": (f"Problem: every PDF I print comes out blank since Adobe Acrobat Pro {VER} "
                        "installed itself. Re: Solution: roll back the printer driver. "
                        "Thanks, that worked, still a regression though."),
        "source_url": THREAD, "source_date": "2026-06-01",
        "source_type": ac.ADOBE_COMMUNITY_SOURCE_TYPE}, CAPTURED)
    check("A7.4 member thread + helper's solution still counts",
          helped.get("counted") is True, str(helped.get("exclusion_reason")))

    print()
    print("=" * 96)
    print("A8  live corpus: catches every known vendor row, zero false positives")
    print("=" * 96)
    doc_y = yaml.safe_load((ROOT / "_data" / "consensus_evidence.yml").read_text(encoding="utf-8")) or {}
    rows = [r for r in (doc_y.get("evidence") or []) if str(r.get("product_id", "")).startswith("adobe-acrobat")]
    official_threads = {"1260523"}

    def thread_id(r: dict) -> str:
        m = re.search(r"-(\d{6,})(?:$|[/?#])", str(r.get("source_url") or ""))
        return m.group(1) if m else ""

    flagged = [r for r in rows
               if authority(str(r.get("report_title") or ""), str(r.get("report_text_excerpt") or ""))]
    fp = [r for r in flagged if thread_id(r) not in official_threads]
    missed = [r for r in rows if thread_id(r) in official_threads and r not in flagged]
    check(f"A8.1 zero false positives over {len(rows)} stored Acrobat rows", not fp,
          str([(r.get("report_title"), thread_id(r)) for r in fp][:4]))
    check("A8.2 every known vendor row is caught", not missed,
          str([(r.get("report_title"), thread_id(r)) for r in missed]))
    check("A8.3 flagged set == known vendor set",
          {thread_id(r) for r in flagged} == official_threads,
          str({thread_id(r) for r in flagged}))
    # Titles are stored WHOLE, so unlike a body rule this scan sees the rule's real input.
    longest = max((len(str(r.get("report_title") or "")) for r in rows), default=0)
    check("A8.4 titles are short enough to be stored untruncated", longest < 280, str(longest))
    # The one vendor support document that is knowingly still counted.
    still = [r for r in rows if thread_id(r) == "1288217" and r.get("counted") is True]
    check("A8.5 the known support document is still counted (documented gap)", len(still) == 1, str(len(still)))

    print()
    print("=" * 96)
    print("A9  determinism and containment")
    print("=" * 96)
    check("A9.1 repeated calls are identical",
          len({authority(ANNOUNCE_TITLE, "x") for _ in range(50)}) == 1)
    check("A9.2 None-safe", authority(None, None) == "")  # type: ignore[arg-type]
    check("A9.3 empty-safe", authority("", "") == "")
    base_src = (ROOT / "scripts" / "patch_collectors" / "base.py").read_text(encoding="utf-8")
    check("A9.4 shared matcher carries no Acrobat vendor logic",
          "acrobat_vendor_authority" not in base_src)
    for other in ("davinci.py", "adobe_premiere.py", "microsoft_powerpoint.py"):
        pth = ROOT / "scripts" / "patch_collectors" / other
        if pth.exists():
            check(f"A9.5 {other} unaffected", "acrobat_vendor_authority" not in pth.read_text(encoding="utf-8"))

    print()
    print("=" * 96)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 96)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
