#!/usr/bin/env python3
"""Windows acceptance: `identity_not_the_subject` (AUX-067, C1b).

Offline and deterministic. Fixtures: tests/fixtures/windows_c1b/c1b_rows.json holds the stored
title / excerpt / matched-identity fields of the eight confirmed false acceptances and of the one
legitimate row the rule must keep, plus tests/fixtures/elevenforum/ for thread 50506. Nothing here
reads or writes `_data`, a record or the evidence store.

    A  the eight confirmed false acceptances are rejected, each for the right reason
    B  row 51 ("build 26200.8875+") is kept by the affected-range exception, and the exception is
       exactly as narrow as documented (marker, same train, at or below the target, no remedy wording)
    C  synthetic shapes: M1 / M3 rejected; M4 / M5 / M6 / M7 kept; M2 and a train-only title are the
       documented residuals the rule does not claim to close
    D  everything the rule must NOT touch: KB + train identity, target build or KB in the title,
       no competing token, and the date / release / identity gates that run before it
    E  the rule's position and vocabulary, and the end-to-end row shape through evaluate_candidates
    F  thread 50506 re-run against the new authority (AUX-063)

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_windows_identity_not_the_subject.py
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from patch_collectors import elevenforum_source as ef  # noqa: E402
from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors.base import PatchRecord, WINDOWS_PRODUCT_ID  # noqa: E402

FIX = _SCRIPTS / "tests" / "fixtures"
REASON = "identity_not_the_subject"
NEWLINE = chr(10)
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
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


T25 = {"target_feature_version": "25H2", "target_kb": "KB5127648", "target_os_build": "26200.9711",
       "target_release_date": "2026-10-13T00:00:00Z", "update_version": "25H2"}
T26 = {"target_feature_version": "26H2", "target_kb": "KB5127648", "target_os_build": "26300.9711",
       "target_release_date": "2026-10-13T00:00:00Z", "update_version": "26H2"}
T25_8894 = {"target_feature_version": "25H2", "target_kb": "KB5121767", "target_os_build": "26200.8894",
            "target_release_date": "2026-07-18T00:00:00Z", "update_version": "25H2"}
URL = "https://learn.microsoft.com/en-us/answers/questions/6000001/some-question"


def replay(target: dict, title: str, body: str, date: str = "2026-10-30", url: str = URL) -> str | None:
    """The authority exactly as `row_from_candidate` drives it: identity is matched against the
    joined title + body, and the title is what the rule sees."""
    text = " ".join([title, title, body])
    kb = target["target_kb"] if mw._has_exact(text, target["target_kb"]) else ""
    build = target["target_os_build"] if mw._has_exact(text, target["target_os_build"]) else ""
    feature = target["target_feature_version"] if mw._has_exact(text, target["target_feature_version"]) else ""
    return mw.windows_learn_qna_reason(target, url, date, text, title, kb, build, feature)


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Windows acceptance: identity_not_the_subject (AUX-067)")
    print("=" * 78)

    rows = json.loads((FIX / "windows_c1b" / "c1b_rows.json").read_text(encoding="utf-8"))
    check("A0 the fixture holds the nine recorded rows (eight false acceptances + row 51)", len(rows) == 9)
    false_rows = [r for r in rows if "5957946" not in r["id"]]
    row51 = [r for r in rows if "5957946" in r["id"]]

    # ---------------------------------------------------------------- A. the eight false acceptances
    expect_ids = {"5973207": "25H2 26200.9168", "5989625": "25H2 26200.9278", "5987983": "25H2 26200.9168",
                  "5885634": "25H2 26200.8328", "5897669": "25H2 26200.8246", "6006784": "25H2 26200.9457",
                  "6012710": "25H2 26200.9457", "6055182": "26H2 26300.9711"}
    seen = {}
    # The stored excerpt is capped at 280 characters, so for some rows the attribution clause that the
    # full body carried is cut off. COMPLETION stands in for that remainder, so the whole authority is
    # exercised on the text the live collector saw rather than on the truncation.
    completion = " This started after installing the update."
    for r in false_rows:
        qid = next(k for k in expect_ids if k in r["id"])
        title = r["report_title"] or ""
        text = " ".join([r["parent_title"] or "", title, r["report_text_excerpt"] or ""]).strip()
        args = (r["target"], r["source_url"], str(r["source_date"])[:10])
        ids = (r["matched_kb"] or "", r["matched_os_build"] or "", r["matched_feature_version"] or "")
        stored = mw.windows_learn_qna_reason(*args, text, title, *ids)
        completed = mw.windows_learn_qna_reason(*args, text + completion, title, *ids)
        seen[qid] = completed
        check(f"A {qid} ({expect_ids[qid]}): the rule fires on the stored title and matched identity",
              mw.identity_not_the_subject(r["target"], title, ids[0], ids[1]) is True)
        check(f"A {qid}: the whole authority does not count the stored excerpt ({stored})", stored is not None)
        check(f"A {qid}: with the truncated attribution clause restored it is rejected as {REASON}, not counted", completed == REASON, str(completed))
        check(f"A {qid}: it is a build-only identity whose title names a competing KB or build, and neither of its own",
              bool(r["matched_os_build"]) and not r["matched_kb"]
              and not mw._has_exact(title, r["target"]["target_os_build"])
              and not mw._has_exact(title, r["target"]["target_kb"])
              and bool(mw._other_kbs(title, r["target"]["target_kb"])
                       or mw._other_builds(title, r["target"]["target_os_build"])))
    check("A9 all eight distinct reports are covered", sorted(seen) == sorted(expect_ids) and len(seen) == 8)
    r41 = next(r for r in false_rows if "5987983" in r["id"])
    check("A10 row 41 is an OFFICE build: the foreign-product veto lets it through, this rule does not",
          not mw.foreign_product_subject(r41["report_title"], "", r41["matched_os_build"])
          and "16.0.20326.20100" in r41["report_title"])
    r452 = next(r for r in false_rows if "6012710" in r["id"])
    check("A11 row 452's 1000.26100.1.0 is not read as a build; it is rejected for its KB, not for that string",
          not mw.BUILD_TOKEN_RE.findall(r452["report_title"]) and "KB5007651" in r452["report_title"])

    # ---------------------------------------------------------------- B. row 51 and the exception
    r51 = row51[0]
    text51 = " ".join([r51["parent_title"] or "", r51["report_title"] or "", r51["report_text_excerpt"] or ""])
    got51 = mw.windows_learn_qna_reason(
        r51["target"], r51["source_url"], str(r51["source_date"])[:10], text51 + completion, r51["report_title"],
        r51["matched_kb"] or "", r51["matched_os_build"] or "", r51["matched_feature_version"] or "")
    check("B1 row 51 (25H2 26200.8894, 'build 26200.8875+') is KEPT by the authority", got51 is None, str(got51))
    check("B2 it is kept by the EXCEPTION alone: the rule's three other conditions all hold for it",
          bool(r51["matched_os_build"]) and not r51["matched_kb"]
          and not mw._has_exact(r51["report_title"], r51["target"]["target_os_build"])
          and bool(mw._other_builds(r51["report_title"], r51["target"]["target_os_build"]))
          and mw.title_states_affected_range(r51["report_title"], r51["target"]["target_os_build"]))
    check("B3 the exception does not rescue the eight: none of their titles states an affected range",
          not any(mw.title_states_affected_range(r["report_title"], r["target"]["target_os_build"]) for r in false_rows))

    rng = mw.title_states_affected_range
    check("B4 '+' written against a same-train build at or below the target is a range",
          rng("Checkbox bug after update (build 26200.8875+)", "26200.8894"))
    check("B5 'and later' and 'or later' are ranges", rng("Bug on 26200.8875 and later", "26200.8894")
          and rng("Bug on 26200.8875 or later", "26200.8894"))
    check("B6 the target build itself, open-ended, is a range", rng("Bug on 26200.8894+", "26200.8894"))
    check("B7 a range that starts ABOVE the target is not", not rng("Bug on 26200.8900+", "26200.8894"))
    check("B8 a range on ANOTHER train is not", not rng("Bug on 26100.8875+", "26200.8894"))
    check("B9 a bare older build mention is not a range (no 'any older build counts')",
          not rng("Bug after 26200.8875", "26200.8894") and not rng("Regression since 26200.8875 update", "26200.8894"))
    check("B10 a closed range or a 'before' is not an open-ended one",
          not rng("Bug between 26200.8875 and 26200.8900", "26200.8894") and not rng("Fine before 26200.8875", "26200.8894"))
    check("B11 remedy wording withholds the exception: 'fixed in 26200.8875+' names a fix, not a defect",
          not rng("Printing fixed in 26200.8875+", "26200.8894") and not rng("Resolved on build 26200.8875 and later", "26200.8894"))
    check("B12 a malformed target build never produces an exception",
          not rng("Bug on 26200.8875+", "") and not rng("Bug on 26200.8875+", "26200") and not rng("Bug on 26200.8875+", "x.y"))
    check("B13 the marker must sit against the build: '+' elsewhere in the title is not one",
          not rng("C++ app crash after 26200.8875 update", "26200.8894"))

    # ---------------------------------------------------------------- C. synthetic shapes (M1..M7)
    m1 = replay(T25, "Win11 26H2 (KB5121794) boot BSOD after update",
                "Win11 Home 25H2 26200.9711 (current). Issue on 26H2 / KB5121794. Removing KB5121794 fixed it, BSOD gone.")
    check("C1 M1: baseline build in the body, another KB as the title's subject -> rejected", m1 == REASON, str(m1))
    m3 = replay(T25, "KB5101650 install fails with 0x800f0920",
                "My OS build is 26200.9711. KB5101650 fails to install, error 0x800f0920 every time.")
    check("C2 M3: another KB failing, the target build only as the author's own build -> rejected", m3 == REASON, str(m3))
    m4 = replay(T25, "KB5127648 (26200.9711) breaks printing", "After installing the update my printer stopped working.")
    check("C3 M4: the target build and KB in the title -> kept", m4 is None, str(m4))
    m5 = replay(T25, "Windows 11 24H2 and 25H2 audio broken after update",
                "Since the update on 25H2 build 26200.9711 there is no sound. Uninstalling the update fixed it.")
    check("C4 M5: a multi-train title with no competing KB or build, target build in the body -> kept", m5 is None, str(m5))
    m6 = replay(T25, "BT dropout regression between 26200.9457 and 26200.9711", "Bluetooth drops since the update, worked on 26200.9457.")
    check("C5 M6: a regression between two builds, the target named in the title -> kept", m6 is None, str(m6))
    m7 = replay(T25, "KB5121003 and KB5127648 fail to install", "KB5127648 (26200.9711) fails to install with 0x80070306 on 25H2.")
    check("C6 M7: another KB in the title but the target KB named too -> kept", m7 is None, str(m7))
    m2 = replay(T25, "Blue screen on startup after update",
                "I am on 25H2 26200.9711 (current). Blue screen every morning since the update, removing the update fixed it.")
    check("C7 RESIDUAL M2: a baseline mention with no competing token in the title is NOT closed (documented, not claimed)",
          m2 is None, str(m2))
    m1_train = replay(T25, "Win11 26H2 boot BSOD after update",
                      "Win11 Home 25H2 26200.9711 (current). Issue on 26H2 / KB5121794. Removing KB5121794 fixed it, BSOD gone.")
    check("C8 RESIDUAL: a TRAIN-only title (no competing KB or build) is not rejected; the broader train variant is out of scope",
          m1_train is None, str(m1_train))
    e = replay(T26, "KB5127936 breaks Xbox 360 Wireless Controller in all games",
               "After installing KB5127936 my Xbox controller fails. I am on 26H2 26300.9711 and it stopped working after the update.")
    check("C9 a title naming ANOTHER KB with the record's build only in the body is rejected on the 26H2 record too", e == REASON, str(e))

    # ---------------------------------------------------------------- D. what must not change
    kbt = replay(T25, "KB5127648 breaks printing on 25H2", "After installing KB5127648 the printer stopped. Uninstalling the update fixed it.")
    check("D1 KB + feature-train identity is untouched (no build named at all)", kbt is None, str(kbt))
    kbt2 = replay(T25, "KB5121003 and KB5127648 fail to install on 25H2", "KB5127648 fails to install with 0x80070306 on 25H2.")
    check("D2 a KB match is never rejected by this rule, whatever else the title names", kbt2 is None, str(kbt2))
    both = replay(T25, "Printing broken on 26200.9457 and 26200.9711", "After the update printing is broken, uninstalling the update fixed it.")
    check("D3 the target build in the title preserves acceptance even beside a competing build", both is None, str(both))
    plain = replay(T25, "Printer stopped working after the update",
                   "Since the update on 26200.9711 my printer stopped working. Uninstalling the update fixed it.")
    check("D4 a title with no competing token is untouched", plain is None, str(plain))
    early = replay(T25, "KB5101650 install fails 0x800f0920", "On 26200.9711. KB5101650 fails to install, error 0x800f0920.", date="2026-10-01")
    check("D5 the date gate still answers first: a report dated before the release is date_before_release", early == "date_before_release", str(early))
    offrec = replay({**T25, "target_os_build": "26200.9999"}, "KB5101650 install fails 0x800f0920",
                    "On 26200.9711. KB5101650 fails to install, error 0x800f0920.")
    check("D6 an identity that is not the record's build or KB never reaches the rule (wrong_kb_for_current_patch)",
          offrec == "wrong_kb_for_current_patch", str(offrec))
    gen = replay(T25, "KB5101650 question", "My build is 26200.9711. What does this KB do?")
    check("D7 the concrete-issue gate still answers first", gen == "generic_support_request", str(gen))
    stale = mw.windows_learn_qna_reason(T25, URL, "2026-10-30", "KB5101650 install fails 0x800f0920 on 26200.9711 25H2",
                                        "KB5101650 install fails 0x800f0920", "", "26200.9711", "25H2")
    check("D8 called directly with a build-only identity the rule fires; the same call with the KB matched does not",
          stale == REASON and mw.windows_learn_qna_reason(
              T25, URL, "2026-10-30", "KB5101650 install fails 0x800f0920 on 26200.9711 25H2 KB5127648",
              "KB5101650 install fails 0x800f0920", "KB5127648", "26200.9711", "25H2") is None)

    direct = mw.identity_not_the_subject(T25, "KB5101650 fails; also see KB5127648", "", "26200.9711")
    check("D9 called directly, the target KB in the title protects a build-only identity on its own",
          direct is False and mw.identity_not_the_subject(T25, "KB5101650 fails", "", "26200.9711") is True)

    spam = replay(T25, "Very strange Windows 11 MCT .ISO 26200.8653",
                  "This thread was rejected by the system as spam. Build 26200.9711 crashes when I create the MCT ISO.")
    check("D10 an existing, more specific rejection keeps its reason: a spam/meta post with a competing build in the title",
          spam == "meta_or_spam_report", str(spam))
    specs = replay(T25, "My PC crashes randomly KB5101650", "My PC crashes. Windows 11 25H2, OS Build 26200.9711 installed.")
    check("D11 a system-spec rejection keeps its reason when the title also names another KB", specs == "build_only_in_system_specs", str(specs))
    feat = replay(T25, "Does this mean KB5101650 is disabled",
                  "Windows 11 25H2 26200.9711. The toggle is greyed out and the app crashes. Does this mean it is disabled?")
    check("D12 a feature-question rejection keeps its reason when the title also names another KB",
          feat == "feature_question_not_regression", str(feat))

    # ---------------------------------------------------------------- E. position, vocabulary, row shape
    src = (_SCRIPTS / "patch_collectors" / "microsoft_windows.py").read_text(encoding="utf-8")
    body = src.split("def windows_learn_qna_reason(", 1)[1].split("def row_from_candidate(", 1)[0]
    gate_at, rule_at = body.find("windows_identity_gate(gate_row, target)"), body.find("identity_not_the_subject(target")
    intent_at = body.find("windows_intent_reason(report_text")
    check("E1 the rule sits after the identity gate AND after the intent filter, so it only ever turns an acceptance into a rejection",
          0 <= gate_at < intent_at < rule_at, f"gate {gate_at}, intent {intent_at}, rule {rule_at}")
    check("E2 it returns the new exclusion reason string", f'return "{REASON}"' in body)
    check("E3 it is not applied in windows_intent_reason (the role rules there are untouched)",
          "identity_not_the_subject" not in src.split("def windows_intent_reason(", 1)[1].split("def identity_basis(", 1)[0])
    check("E4 the rule is a function of the TITLE only: the body text is not a parameter",
          list(mw.identity_not_the_subject.__code__.co_varnames[:4]) == ["target", "report_title", "matched_kb", "matched_os_build"])
    rec25 = PatchRecord(WINDOWS_PRODUCT_ID, "25H2", Path("synthetic-25h2.md"), "2026-10-13T00:00:00Z", "current", "Windows 11", "26200.9711")
    cands = [
        {"source_type": "microsoft_learn_qna", "source_name": "Microsoft Learn Q&A",
         "source_url": "https://learn.microsoft.com/en-us/answers/questions/6000002/kb5101650-fails",
         "parent_title": "KB5101650 install fails with 0x800f0920", "report_title": "KB5101650 install fails with 0x800f0920",
         "report_text": "My OS build is 26200.9711. KB5101650 fails to install, error 0x800f0920 every time.",
         "source_date": "2026-10-30"},
        {"source_type": "microsoft_learn_qna", "source_name": "Microsoft Learn Q&A",
         "source_url": "https://learn.microsoft.com/en-us/answers/questions/6000003/printing",
         "parent_title": "Printer stopped working after the update", "report_title": "Printer stopped working after the update",
         "report_text": "Since the update on 26200.9711 my printer stopped working. Uninstalling the update fixed it.",
         "source_date": "2026-10-30"},
    ]
    accepted, rejected = mw.evaluate_candidates(rec25, T25, cands, "2026-11-04T00:00:00Z")
    rej = rejected[0] if rejected else {}
    check("E5 end to end: the foreign-subject row is stored uncounted with the new reason and no target_build",
          len(rejected) == 1 and rej.get("counted") is False and rej.get("exclusion_reason") == REASON
          and rej.get("target_build") == "" and rej.get("evidence_valid_for_current_patch") is False
          and rej.get("matched_os_build") == "26200.9711")
    check("E6 end to end: its sibling with no competing token is still counted on the build",
          len(accepted) == 1 and accepted[0]["counted"] is True and accepted[0]["target_build"] == "26200.9711")

    # ---------------------------------------------------------------- F. thread 50506 (AUX-063)
    def parse(tid: str) -> dict:
        page = (FIX / "elevenforum" / f"thread_{tid}.html").read_text(encoding="utf-8")
        cand, why = ef.parse_thread(f"https://www.elevenforum.com/t/x.{tid}/", page, today="2026-11-04")
        assert cand, why
        return cand
    rec26 = PatchRecord(WINDOWS_PRODUCT_ID, "26H2", Path("synthetic-26h2.md"), "2026-10-13T00:00:00Z", "current", "Windows 11", "26300.9711")
    t50506, t50447 = parse("50506"), parse("50447")
    claims: dict = {}
    got50506: dict[str, tuple[bool, object]] = {}
    got50447: dict[str, bool] = {}
    for rec, tgt in ((rec26, T26), (rec25, T25)):
        acc, rej_rows = mw.evaluate_candidates(rec, tgt, [t50506, t50447], "2026-11-04T00:00:00Z", claims)
        for row in acc + rej_rows:
            if row["source_url"].endswith(".50506"):
                got50506[rec.update_version] = (row["counted"], row["exclusion_reason"])
            else:
                got50447[rec.update_version] = row["counted"]
    check("F1 thread 50506's title names KB5121794 (26H2) and never the 25H2 build or KB",
          "KB5121794" in t50506["report_title"] and "26200.9711" not in t50506["report_title"]
          and "KB5127648" not in t50506["report_title"])
    check("F2 25H2 26200.9711: 50506 is REJECTED as identity_not_the_subject (the baseline-build misattribution)",
          got50506.get("25H2") == (False, REASON), str(got50506.get("25H2")))
    check("F3 the 25H2 row was a build-only identity: the reporter's current baseline, not the defect",
          "25H2 26200.9711 (current)" in t50506["report_text"] and "Issue on 26H2" in t50506["report_text"])
    check("F4 26H2 26300.9711: 50506 is not accepted there either (no build or KB of that record is named)",
          got50506.get("26H2", (None,))[0] is False, str(got50506.get("26H2")))
    check("F5 50506 is accepted on NO record", not any(v[0] for v in got50506.values()))
    check("F6 the clean case, thread 50447 (KB5127648 on 26H2), is still accepted exactly once, on 26H2",
          got50447.get("26H2") is True and got50447.get("25H2") is False)

    print()
    print("=" * 78)
    for err in _ERRORS:
        print(f"  - {err}")
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
