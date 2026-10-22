#!/usr/bin/env python3
"""Same-author context may complete a report; it must never invent or transfer a failure.

Learn Q&A threads follow one shape: the reporter describes what broke, a responder asks for the
build, and the SAME person answers in a comment. Attribution was previously scoped by segment_key,
so a reporter's own later post counted as a stranger's and the build was discarded. Scoping is now
by author_id.

Widening attribution is exactly the kind of change that quietly turns every build a person mentions
into a failing build, so the boundaries are mutation-proved here rather than assumed.

Offline: every thread is a fixture. No network, no repo writes.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import context_resolution as cr  # noqa: E402
from lib.source_segments import (  # noqa: E402
    SEGMENT_ANSWER, SEGMENT_COMMENT, SEGMENT_QUESTION, SourceSegment, ThreadSegments, PARSE_OK,
)

PASS = FAIL = 0
FAILURES: list[str] = []

THREAD = "https://learn.microsoft.com/en-us/answers/questions/9000001/powerpoint-crash"
AUTHOR_A = "aaaaaaaa-1111-2222-3333-444444444444"
AUTHOR_B = "bbbbbbbb-5555-6666-7777-888888888888"
MODERATOR = "cccccccc-9999-0000-1111-222222222222"


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def seg(kind: str, sid: str, text: str, author: str, date: str = "2026-08-05T00:00:00Z") -> SourceSegment:
    return SourceSegment(
        thread_url=THREAD, segment_type=kind, segment_id=sid,
        segment_url=f"{THREAD}#{kind}-{sid}", segment_text=text,
        author_name="", author_id=author, author_role="", segment_date=date,
    )


def thread(*segments: SourceSegment) -> ThreadSegments:
    t = ThreadSegments(thread_url=THREAD, thread_id="9000001", parse_status=PARSE_OK)
    t.segments = list(segments)
    return t


def resolve(t: ThreadSegments, reason: str = "missing_exact_build") -> cr.ResolutionOutcome:
    """Resolve the QUESTION segment of a fixture thread through the real production entry point."""
    candidate = {"source_url": THREAD, "report_text": "", "source_date": "2026-08-05"}
    budget = cr.ResolutionBudget()
    budget.threads[THREAD] = (t, "ok")
    return cr.resolve_candidate(candidate, reason, fetch_thread=lambda u: ("", "ok"), budget=budget)


def run() -> int:
    print("=" * 96)
    print("C1  reporter's own rollback build never becomes a second failure")
    print("=" * 96)
    t = thread(
        seg(SEGMENT_QUESTION, "9000001", "PowerPoint crashes on save since the update.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c1", "I am on Build 20228.20124 and it crashes every time.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c2", "I rolled back to Build 20228.20154 and it works fine now.", AUTHOR_A),
    )
    out = resolve(t)
    check("C1.1 the CURRENT failing build resolves, not the rollback",
          out.resolved_build == "20228.20124", f"{out.resolution_result}/{out.resolved_build}")
    check("C1.2 the rollback build never becomes the resolved build",
          out.resolved_build != "20228.20154", out.resolved_build)
    check("C1.3 exactly one build is selected, not two",
          out.resolved_build in ("20228.20124", ""), out.resolved_build)

    print()
    print("=" * 96)
    print("C2  a build the reporter says WORKS is not negative evidence")
    print("=" * 96)
    t = thread(
        seg(SEGMENT_QUESTION, "9000001", "PowerPoint export is broken for me.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c1", "Build 20228.20124 is the one that fails.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c2", "Build 20228.20190 works correctly, no problem there.", AUTHOR_A),
    )
    out = resolve(t)
    # "works correctly, no problem there" states no ROLE the classifier recognises, so the second
    # build is `ambiguous` and selection refuses with `unclassified_build_present`. That refusal is
    # the veto-only doctrine working as designed: with an unclassified build on the table, choosing
    # between them would be inference. The invariant is that the WORKING build is never attributed,
    # not that a build must always be produced.
    check("C2.1 an unclassified second build causes refusal, never a guess",
          out.resolved_build in ("", "20228.20124"), f"{out.resolution_result}/{out.resolved_build}")
    check("C2.2 the working build is NOT attributed", out.resolved_build != "20228.20190",
          out.resolved_build)
    # And when the reporter DOES state the role, the mechanism resolves rather than over-refusing.
    t2 = thread(
        seg(SEGMENT_QUESTION, "9000001", "PowerPoint export is broken for me.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c1", "Build 20228.20124 is the one that fails.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c2", "I rolled back to Build 20228.20190 and it works fine.", AUTHOR_A),
    )
    out2 = resolve(t2)
    check("C2.3 a stated rollback resolves the failing build from the reporter's own comments",
          out2.resolved_build == "20228.20124", f"{out2.resolution_result}/{out2.resolved_build}")
    check("C2.4 the stated rollback build is still not the resolved build",
          out2.resolved_build != "20228.20190", out2.resolved_build)

    print()
    print("=" * 96)
    print("C3/C4  a build stated by anyone else is never borrowed")
    print("=" * 96)
    t = thread(
        seg(SEGMENT_QUESTION, "9000001", "PowerPoint crashes on save since the update.", AUTHOR_A),
        seg(SEGMENT_ANSWER, "a1", "You are probably on Build 20228.20124.", MODERATOR),
    )
    out = resolve(t)
    check("C3.1 a moderator's build is not borrowed", not out.explicit_build_found,
          f"{out.resolution_result}/{out.resolved_build}")
    check("C3.2 the refusal is reported, not silent",
          out.resolution_result == cr.CROSS_SEGMENT_BUILD_IGNORED
          and "20228.20124" in out.cross_segment_builds, out.resolution_result)

    t = thread(
        seg(SEGMENT_QUESTION, "9000001", "PowerPoint crashes on save since the update.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c1", "Same here, I'm on Build 20228.20158.", AUTHOR_B),
    )
    out = resolve(t)
    check("C4.1 another user's build is not borrowed", not out.explicit_build_found,
          f"{out.resolution_result}/{out.resolved_build}")
    check("C4.2 it is reported as cross-segment", "20228.20158" in out.cross_segment_builds,
          str(out.cross_segment_builds))

    print()
    print("=" * 96)
    print("C5  unidentifiable authorship fails closed")
    print("=" * 96)
    t = thread(
        seg(SEGMENT_QUESTION, "9000001", "PowerPoint crashes on save since the update.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c1", "It is Build 20228.20124.", ""),
    )
    out = resolve(t)
    check("C5.1 an author-less segment cannot enrich the reporter", not out.explicit_build_found,
          f"{out.resolution_result}/{out.resolved_build}")
    check("C5.2 and is still reported as elsewhere", "20228.20124" in out.cross_segment_builds,
          str(out.cross_segment_builds))
    # The origin segment itself having no author must not make every stranger "the same author".
    t = thread(
        seg(SEGMENT_QUESTION, "9000001", "PowerPoint crashes on save.", ""),
        seg(SEGMENT_COMMENT, "c1", "It is Build 20228.20124.", AUTHOR_B),
    )
    out = resolve(t)
    check("C5.3 an author-less REPORTER does not match every other author",
          not out.explicit_build_found, f"{out.resolution_result}/{out.resolved_build}")

    print()
    print("=" * 96)
    print("C6  one person's thread is one report, however often they restate the build")
    print("=" * 96)
    t = thread(
        seg(SEGMENT_QUESTION, "9000001", "PowerPoint crashes on save since the update.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c1", "I am on Build 20228.20124.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c2", "Still broken on Build 20228.20124 after a repair.", AUTHOR_A),
        seg(SEGMENT_COMMENT, "c3", "Confirming again: Build 20228.20124.", AUTHOR_A),
    )
    out = resolve(t)
    check("C6.1 the repeated build resolves once", out.resolved_build == "20228.20124",
          f"{out.resolution_result}/{out.resolved_build}")
    check("C6.2 repetition is not conflict", out.resolution_result == cr.RESOLVED_EXACT_BUILD,
          out.resolution_result)

    print()
    print("=" * 96)
    print("C7  the release-date gate still decides, resolution does not bypass it")
    print("=" * 96)
    # Resolution supplies identity only; the acceptance authority owns the date gate. Prove the
    # authority still refuses a pre-release report even when the build resolved perfectly.
    from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
    from patch_collectors.base import PatchRecord  # noqa: E402
    rec_path = ROOT / "updates" / "generated" / "2026-07-29-microsoft-powerpoint-2607-20228-20124.md"
    if rec_path.exists():
        record = PatchRecord("microsoft-powerpoint", "2607", rec_path, "2026-07-29T00:00:00Z",
                             "current", "Microsoft PowerPoint")
        target = ppt.record_target(record)
        early = {
            "source_type": "microsoft_learn_qna", "source_name": "Microsoft Learn Q&A",
            "source_url": THREAD, "parent_title": "PowerPoint crash",
            "report_title": "PowerPoint crashes on save",
            "report_text": "PowerPoint Version 2607 Build 20228.20124 crashes on save every time.",
            "source_date": "2026-07-01",  # BEFORE the 2026-07-29 release
        }
        row = ppt.row_from_candidate(record, target, early, "2026-08-29T00:00:00Z")
        check("C7.1 a pre-release report is refused even with a perfect build",
              row.get("counted") is False
              and row.get("exclusion_reason") == "date_before_release_or_undated",
              f"{row.get('counted')}/{row.get('exclusion_reason')}")
        late = {**early, "source_date": "2026-08-06"}
        row = ppt.row_from_candidate(record, target, late, "2026-08-29T00:00:00Z")
        check("C7.2 the same report after release is accepted",
              row.get("counted") is True, str(row.get("exclusion_reason")))
    else:
        check("C7 record fixture present", False, f"missing {rec_path}")

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
