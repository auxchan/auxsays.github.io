#!/usr/bin/env python3
"""A version a report names as its FIX must not become evidence against that version.

THE DEFECT. Version-only lanes accept by containment: `collect_obs_reports.exact_version_re` and
`base.exact_version_match` ask only whether the version STRING occurs. So OBS issue #13716 --
"I downgraded to 32.1.2, which doesn't have this problem" -- was counted as a user report AGAINST
32.1.2, and #13689 -- "The only fix is to revert back to version 32.1.2" -- likewise. Seven such
associations were live in _data/consensus_evidence.yml, published in obs-studio's counts.

WHAT THIS IS NOT. Not a positive "prove affected" gate. Measured: 176 of 351 legitimate accepted
rows, and 164 of 188 OBS rows, name their version ONLY in the issue template's structured version
field, with the defect prose elsewhere. Requiring affected language near the identity would delete
about half the legitimate corpus to remove seven bad rows. `lib/target_outcome` therefore only ever
VETOES, and only on explicit contradictory language; silence keeps existing behaviour.

Each C-case below is a real shape from the live corpus, not an invented one.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_version_outcome_attribution.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

import collect_obs_reports as obs  # noqa: E402
from lib import target_outcome as to  # noqa: E402
from lib.normalize import split_front_matter  # noqa: E402

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


def issue(title: str, body: str) -> dict:
    return {"title": title, "body": body}


def template(version: str, extra: str = "") -> str:
    """An OBS issue-template body declaring `version` as the reporter's version."""
    return (f"### Operating System Info{NEWLINE}Windows 11{NEWLINE}"
            f"### OBS Studio Version{NEWLINE}{version}{NEWLINE}"
            f"### OBS Studio Version (Other){NEWLINE}_No response_{NEWLINE}"
            f"### Anything else we should know?{NEWLINE}{extra}{NEWLINE}")


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("A version named as the FIX is not evidence against that version")
    print("=" * 78)

    # ---------------- C1 / C2: the two live calibration cases ----------------
    print(NEWLINE + "[C1] OBS #13689 -- target is the rollback destination")
    i1 = issue("Version 32.2 broke NVENC encoder for legacy graphics cards",
               template("32.2.0", "The only fix is to revert back to version 32.1.2 as updating "
                                  "drivers does not fix the issue."))
    check("C1 32.1.2 is refused as a rollback target",
          obs.contradiction_reason(i1, "32.1.2") == "version_is_rollback_target",
          str(obs.contradiction_reason(i1, "32.1.2")))
    check("C1 32.2.0 -- the version it indicts -- is still accepted",
          obs.contradiction_reason(i1, "32.2.0") is None,
          str(obs.contradiction_reason(i1, "32.2.0")))

    print(NEWLINE + "[C2] OBS #13716 -- target explicitly lacks the problem")
    i2 = issue("OBS 32.2.1 fails to run on MacOS X 12.7.6 and closes immediately",
               template("32.2.1", "I downgraded to 32.1.2, which doesn't have this problem."))
    check("C2 32.1.2 is refused", obs.contradiction_reason(i2, "32.1.2") is not None,
          str(obs.contradiction_reason(i2, "32.1.2")))
    check("C2 32.2.1 is still accepted", obs.contradiction_reason(i2, "32.2.1") is None,
          str(obs.contradiction_reason(i2, "32.2.1")))

    # ---------------- C3 / C4: recall must not move ----------------
    print(NEWLINE + "[C3/C4] explicitly failing versions remain attributable")
    i3 = issue("OBS crashes on launch", template("32.2.2"))
    check("C3 the declared version is accepted with no prose cue at all",
          obs.contradiction_reason(i3, "32.2.2") is None, str(obs.contradiction_reason(i3, "32.2.2")))
    i4 = issue("Recording fails", "Since 32.2.2 recording fails every time.")
    check("C4 'Since X ... fails' still counts", obs.contradiction_reason(i4, "32.2.2") is None,
          str(obs.contradiction_reason(i4, "32.2.2")))
    i4b = issue("still broken", "This is still broken in 32.2.2.")
    check("C4 'still broken in X' still counts", obs.contradiction_reason(i4b, "32.2.2") is None,
          str(obs.contradiction_reason(i4b, "32.2.2")))

    # ---------------- C5: working comparison ----------------
    print(NEWLINE + "[C5] a working/failing contrast splits correctly")
    i5 = issue("QSV fails with MFX_ERR_NOT_FOUND in 32.2.0, works in 32.1.2", "")
    check("C5 the working side (32.1.2) is refused",
          obs.contradiction_reason(i5, "32.1.2") == "version_reported_working",
          str(obs.contradiction_reason(i5, "32.1.2")))
    check("C5 the failing side (32.2.0) is kept -- R2 stops `works` reaching across",
          obs.contradiction_reason(i5, "32.2.0") is None,
          str(obs.contradiction_reason(i5, "32.2.0")))

    # ---------------- C6: fixed target ----------------
    print(NEWLINE + "[C6] a fix announcement is not negative evidence")
    i6 = issue("Crash on save", template("32.2.1", "This was fixed in 32.2.3."))
    check("C6 32.2.3 is refused as the fixed-in target",
          obs.contradiction_reason(i6, "32.2.3") == "version_reported_fixed",
          str(obs.contradiction_reason(i6, "32.2.3")))

    # ---------------- C7: another participant ----------------
    print(NEWLINE + "[C7] another participant's version does not rewrite the author's")
    i7 = issue("Crash on start", template("32.2.1", "A colleague on 32.1.2 says it works for them."))
    check("C7 the author's declared version is untouched",
          obs.contradiction_reason(i7, "32.2.1") is None, str(obs.contradiction_reason(i7, "32.2.1")))
    check("C7 the other participant's working version is refused",
          obs.contradiction_reason(i7, "32.1.2") is not None,
          str(obs.contradiction_reason(i7, "32.1.2")))

    # ---------------- C8: multiple explicitly affected ----------------
    print(NEWLINE + "[C8] several explicitly affected versions each stay attributable")
    i8 = issue("display capture flickers",
               template("32.2.0", "OBS Studio: 32.1.2 (also tested 32.1.1 with the same behavior)"))
    for v in ("32.2.0", "32.1.2", "32.1.1"):
        check(f"C8 {v} remains countable", obs.contradiction_reason(i8, v) is None,
              f"{v} -> {obs.contradiction_reason(i8, v)}")
    i8b = issue("Image source lag", template("32.2.1", "OBS versions tested: 32.2.1 and 31.1.2. "
                                                       "The issue occurs in both versions."))
    check("C8 'the issue occurs in both versions' keeps the undeclared one",
          obs.contradiction_reason(i8b, "31.1.2") is None,
          str(obs.contradiction_reason(i8b, "31.1.2")))

    # ---------------- C9: ambiguous list -> unchanged behaviour ----------------
    print(NEWLINE + "[C9] a bare list with no outcome keeps today's behaviour")
    i9 = issue("Something is wrong", "I tried 32.1.2 and 32.2.2.")
    check("C9 neither version is vetoed (fail-safe toward existing evidence)",
          obs.contradiction_reason(i9, "32.1.2") is None
          and obs.contradiction_reason(i9, "32.2.2") is None,
          f"{obs.contradiction_reason(i9, '32.1.2')} / {obs.contradiction_reason(i9, '32.2.2')}")

    # ---------------- R1: declared field is authoritative ----------------
    print(NEWLINE + "[R1] the reporter's declared version is never vetoed")
    r1 = issue("Hang when renaming scene collection",
               template("32.1.2", "I cannot reproduce this reliably, no reproducer yet."))
    check("R1 'cannot reproduce' does not veto the DECLARED version",
          obs.contradiction_reason(r1, "32.1.2") is None,
          str(obs.contradiction_reason(r1, "32.1.2")))
    check("R1 declared_versions parses both template fields",
          obs.declared_versions(issue("t", template("32.1.2"))) == {"32.1.2"},
          str(obs.declared_versions(issue("t", template("32.1.2")))))

    # ---------------- C10: Candidate 1 / PowerPoint untouched ----------------
    print(NEWLINE + "[C10] PowerPoint's build-role authority is not involved")
    rec = _REPO / "auxsays" / "updates" / "generated" / "2026-07-23-microsoft-powerpoint-2607-20228-20110.md"
    check("C10 Candidate 1 record exists", rec.exists(), str(rec))
    if rec.exists():
        fr, _ = split_front_matter(rec.read_text(encoding="utf-8"))
        data = yaml.safe_load(fr) or {}
        check("C10 Candidate 1 is still 2607 / 20228.20110 with one counted report",
              str(data.get("update_version")) == "2607"
              and str(data.get("target_build")) == "20228.20110"
              and int(data.get("update_report_count") or 0) == 1,
              f"{data.get('update_version')}/{data.get('target_build')} "
              f"count={data.get('update_report_count')}")
    src = (_REPO / "auxsays" / "scripts" / "patch_collectors" / "microsoft_powerpoint.py").read_text(encoding="utf-8")
    check("C10 the PowerPoint collector does not import this veto",
          "target_outcome" not in src, "powerpoint now depends on the version veto")

    # ---------------- C11: Windows lane untouched ----------------
    print(NEWLINE + "[C11] the Windows cumulative-update identity gate is untouched")
    win = (_REPO / "auxsays" / "scripts" / "patch_collectors" / "microsoft_windows.py").read_text(encoding="utf-8")
    check("C11 the Windows collector does not import this veto",
          "target_outcome" not in win, "windows now depends on the version veto")
    base = (_REPO / "auxsays" / "scripts" / "patch_collectors" / "base.py").read_text(encoding="utf-8")
    check("C11 windows_identity_gate still exists in base",
          "def windows_identity_gate" in base, "gate missing")
    check("C11 shared exact_version_match is unchanged (no veto wired into base)",
          "target_outcome" not in base, "base.py now depends on the version veto")

    # ---------------- C12: one report, one row per patch ----------------
    print(NEWLINE + "[C12] the veto is per (report, version), never a global ban")
    i12 = issue("crash", template("32.2.1", "Also reproduced on 32.1.2 with the same behavior."))
    check("C12 a report may still be evidence for two versions it affects",
          obs.contradiction_reason(i12, "32.2.1") is None
          and obs.contradiction_reason(i12, "32.1.2") is None,
          f"{obs.contradiction_reason(i12, '32.2.1')} / {obs.contradiction_reason(i12, '32.1.2')}")
    check("C12 evidence_key still scopes dedupe by patch, so one row per version",
          obs.evidence_key({"product_id": "obs-studio", "update_version": "32.1.2", "id": "x"}, "id")
          != obs.evidence_key({"product_id": "obs-studio", "update_version": "32.2.1", "id": "x"}, "id"),
          "dedupe key is not patch-scoped")

    # ---------------- adversarial-review regressions ----------------
    # Every case below is a cue defect an adversarial review found in the first draft of
    # lib/target_outcome. Each one vetoed -- i.e. DELETED -- a legitimate affected report.
    print(NEWLINE + "[A] cue defects found in review; each deleted real evidence")
    for label, text, target in (
        ("'built X successfully' is a build report, not a health claim",
         "Built OBS Studio 32.2.1 successfully from source", "32.2.1"),
        ("'does not successfully start' is a defect",
         "32.2.0 does not successfully start", "32.2.0"),
        ("'still not fixed in X' is a defect", "This is still not fixed in 32.2.1.", "32.2.1"),
        ("'never fixed in X' is a defect", "The bug was never fixed in 32.2.1", "32.2.1"),
        ("a portage path segment ending in /work is not 'works'",
         "media-video/obs-studio-32.1.0/work/obs-studio-32.1.0/x", "32.1.0"),
        ("'stopped working in X' is a defect -- CONCRETE_ISSUE_TERMS says so too",
         "Plugin stopped working in 32.2.0 after update", "32.2.0"),
        ("'no longer works on X' is a defect", "Screen capture no longer works on 32.2.0", "32.2.0"),
        ("a driver revision must not hide the failure verb",
         "32.2.0 with driver 610.88 crashes at startup. The old setup works on this machine "
         "with 32.2.0.", "32.2.0"),
    ):
        check(f"A {label}", not to.classify_target_outcome(text, target).vetoes,
              str(to.classify_target_outcome(text, target)))
    check("A the polarity lookback stops at a clause boundary (obs #13692 stays vetoed)",
          to.classify_target_outcome(
              "CoreAudio fails to load. A 32.1.2 log on the same system, showing successful "
              "loading", "32.1.2").vetoes,
          "a statement about another version cancelled this one")

    # ---------------- inflection coverage ----------------
    # A live Windows title reads "Keeps Failing to Install and ROLLS BACK to 26200.9168" -- the
    # target is the working build the machine fell back to, and the original cue set missed it.
    # The gap was systematic, not one word: a report written about the MACHINE ("it rolls back")
    # rather than the author ("I rolled back") is the natural voice for install-failure reports.
    print(NEWLINE + "[I] rollback verbs are matched in the third person too")
    for verb in ("rolls back to", "rolled back to", "rolling back to", "roll back to",
                 "reverts to", "reverted to", "downgrades to", "downgraded to",
                 "goes back to", "went back to", "falls back to"):
        check(f"I '{verb}' is a rollback",
              to.classify_target_outcome(f"Install failed and it {verb} 32.1.2", "32.1.2").vetoes,
              str(to.classify_target_outcome(f"Install failed and it {verb} 32.1.2", "32.1.2")))
    # But the -s is added only to MOTION verbs. stay/remain/stick depend on their subject: "I stay
    # on X" is a rollback, "the bug stays on X" is an affected report. Adding `stays` classified
    # that second sentence as a rollback target, i.e. deleted a real report.
    check("I 'the bug stays on X' is not a rollback (subject decides the meaning)",
          not to.classify_target_outcome("The bug stays on 32.1.2 too", "32.1.2").vetoes,
          str(to.classify_target_outcome("The bug stays on 32.1.2 too", "32.1.2")))
    check("I 'the crash remains on X' is not a rollback",
          not to.classify_target_outcome("The crash remains on 32.1.2", "32.1.2").vetoes,
          str(to.classify_target_outcome("The crash remains on 32.1.2", "32.1.2")))
    check("I first-person 'staying on X' is still a rollback",
          to.classify_target_outcome("I am staying on 32.1.2 until this is fixed", "32.1.2").vetoes,
          str(to.classify_target_outcome("I am staying on 32.1.2 until this is fixed", "32.1.2")))
    live = ("Windows Insider Build 26220.9022 Keeps Failing to Install and "
            "Rolls Back to 26200.9168")
    check("I the live Windows title: the rollback target is vetoed",
          to.classify_target_outcome(live, "26200.9168").vetoes,
          str(to.classify_target_outcome(live, "26200.9168")))
    check("I the live Windows title: the failing build is still affected",
          to.classify_target_outcome(live, "26220.9022").outcome == to.AFFECTED,
          str(to.classify_target_outcome(live, "26220.9022")))

    # ---------------- interrogative suppression ----------------
    # "Was this fixed in KB5121003?" ASKS whether the target is healthy; it does not claim it.
    # Read as an assertion it vetoes a legitimately affected row, and R3 cannot rescue it because a
    # question rarely carries a failure verb of its own. The sentence below appears verbatim in a
    # live Microsoft Q&A thread, so this is native phrasing rather than a constructed edge case.
    print(NEWLINE + "[Q] a question about the target is not a claim about it")
    for text, target in (
        ("Was this exact issue fixed in KB5121003 / build 26200.9168, even if it is not "
         "listed in the public release notes?", "KB5121003"),
        ("Is it fixed in 32.2.3?", "32.2.3"),
        ("Does anyone know if 32.1.2 works?", "32.1.2"),
        ("Has this been resolved in 32.2.1?", "32.2.1"),
    ):
        check(f"Q {text[:44]!r} does not veto",
              not to.classify_target_outcome(text, target).vetoes,
              str(to.classify_target_outcome(text, target)))
    for text, target in (("This was fixed in 32.2.3.", "32.2.3"),
                         ("It works in 32.1.2", "32.1.2"),
                         ("worked as intended on version 32.1.2", "32.1.2")):
        check(f"Q the ASSERTION {text[:38]!r} still vetoes",
              to.classify_target_outcome(text, target).vetoes,
              str(to.classify_target_outcome(text, target)))

    # ---------------- primitive-level guards ----------------
    print(NEWLINE + "[P] primitive behaviour")
    check("P a target absent from the text yields no outcome",
          to.classify_target_outcome("nothing here", "32.1.2").outcome == to.NONE)
    check("P R2: a cue may not bind across another identity",
          to.classify_target_outcome("fails in 32.2.0, works in 32.1.2", "32.2.0").outcome == to.AFFECTED,
          str(to.classify_target_outcome("fails in 32.2.0, works in 32.1.2", "32.2.0")))
    check("P 'workaround' is not a working claim",
          to.classify_target_outcome("32.1.2 workaround is to restart", "32.1.2").outcome != to.WORKING,
          str(to.classify_target_outcome("32.1.2 workaround is to restart", "32.1.2")))
    check("P a veto outcome reports the exact text that caused it",
          bool(to.classify_target_outcome("I reverted to 32.1.2", "32.1.2").excerpt),
          "no excerpt")
    check("P only working/rollback/fixed/reference veto",
          to.VETO_OUTCOMES == frozenset({to.WORKING, to.ROLLBACK, to.FIXED, to.REFERENCE}),
          str(sorted(to.VETO_OUTCOMES)))

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
        raise SystemExit(1)
