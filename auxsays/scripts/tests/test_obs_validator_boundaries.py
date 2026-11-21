#!/usr/bin/env python3
"""AUX-129: a hoped-for outcome is not a working claim, and a stored row keeps its field boundaries.

THE RECORD. The audited-withdrawal tool (withdraw_obs_role_misattributed_rows.py) reported the
counted OBS Studio 32.1.2 row for GitHub issue #13518 as `version_reported_working`. The issue
reports that 32.1.2 cannot be installed on a newer Ubuntu: an install FAILURE. It stays counted.
Two validator defects produced the label, and each is fixed and pinned here:

  F1  The working cues built on the verb "work" (`target_works`, `works_on_target`) read a hoped-for,
      expected, conditional or requested outcome as a claim. The issue's Expected Behavior field
      hopes 32.1.2 "will work"; that is a hope, not a report.
  F2  The tool ran every stored field together with spaces. A cue could then bind across two
      fields, and R1 (a version the reporter DECLARED is never vetoed) could not apply, because the
      template's version answer is found by the line break after its heading. Stored OBS excerpts
      are whitespace-collapsed, so a row holding that heading without its line break is now
      UNDETERMINABLE from storage (never refused, never withdrawn), not refused.

Fixtures are in AUXSAYS's own words, apart from #13518's stored fields, which are read from the
live store (read only) so the pin is the real row. No acceptance threshold changes, and the suite
writes nothing outside a temporary directory.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_obs_validator_boundaries.py
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import collect_obs_reports as obs  # noqa: E402
import withdraw_obs_role_misattributed_rows as wd  # noqa: E402
from lib import target_outcome as to  # noqa: E402
from patch_collectors.base import EVIDENCE_PATH, load_evidence, write_evidence_file  # noqa: E402

NL = chr(10)
TOOL = SCRIPTS / "withdraw_obs_role_misattributed_rows.py"
ROW_13518 = "obs-studio-32-1-2-github-issue-13518"
V = "32.1.2"
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
        print(f"  FAIL  {label}" + (f"{NL}        {detail}" if detail else ""))


def outcome(text: str, target: str = V) -> to.Outcome:
    return to.classify_target_outcome(text, target)


def vetoes(text: str, target: str = V) -> bool:
    return outcome(text, target).vetoes


# The template headings, longest first so "(Other)" is never split from its own heading.
_HEADINGS = ("OBS Studio Version (Other)", "OBS Studio Version", "OBS Studio Crash Log URL",
             "OBS Studio Log URL", "Operating System Info", "Other OS", "Expected Behavior",
             "Current Behavior", "Steps to Reproduce", "Anything else we should know?")
_HEADING_RX = re.compile("### (" + "|".join(re.escape(h) for h in _HEADINGS) + ") ?")


def template_layout(flat: str) -> str:
    """Put the issue template's line breaks back into a whitespace-collapsed stored excerpt."""
    return _HEADING_RX.sub(lambda m: NL + NL + "### " + m.group(1) + NL + NL, flat).strip()


def row(rid: str, title: str, excerpt: str, *, version: str = V, url: str = "", counted: bool = True,
        reason=None, source_type: str = "github_issue", report_text: str = "") -> dict:
    out = {"id": rid, "product_id": "obs-studio", "update_version": version,
           "source_type": source_type, "source_name": "fixture",
           "source_url": url or ("https://example.invalid/" + rid),
           "parent_title": title, "report_title": title, "report_text_excerpt": excerpt,
           "captured_at": "2026-09-01T00:00:00Z", "patch_version_matched": True,
           "matched_version": version, "match_basis": "body", "counted": counted,
           "exclusion_reason": reason, "source_weight": 1}
    if report_text:
        out["report_text"] = report_text
    return out


def ids(pairs) -> list[str]:
    return [r["id"] for r, _ in pairs]


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("AUX-129 hypothetical success wording and stored-field boundaries")
    print("=" * 78)
    live_before = hashlib.sha256(EVIDENCE_PATH.read_bytes()).hexdigest()
    live_rows = load_evidence(EVIDENCE_PATH)
    live = next((r for r in live_rows if r.get("id") == ROW_13518), {})

    # ------------------------------------------------------------------ F1
    print(NL + "[F1] a hoped-for, expected, conditional or requested outcome is not a working claim")
    hope_13518 = str(live.get("report_text_excerpt") or "").split("### Expected Behavior")[-1].strip()
    check("F1.0 the live #13518 row still carries its Expected Behavior sentence (fixture is real)",
          V in hope_13518 and "hope" in hope_13518.lower(), hope_13518[:120])
    check("F1.1 #13518's stored Expected Behavior sentence is not a working claim for 32.1.2",
          not vetoes(hope_13518), str(outcome(hope_13518)))
    hypothetical = {
        "F1.2 hoped-for: 'I hope 32.1.2 will work'": "I hope 32.1.2 will work on my laptop",
        "F1.3 expected modal: '32.1.2 should work'": "32.1.2 should work with the new driver",
        "F1.4 question without a mark: 'would 32.1.2 work'": "Would OBS 32.1.2 work on Fedora 44",
        "F1.5 expectation: 'expecting 32.1.2 to work'": "I was expecting 32.1.2 to work out of the box",
        "F1.6 conditional: 'if 32.1.2 works'": "if 32.1.2 works I will roll it out to the studio",
        "F1.7 hoped-for, own words, #13518's shape": "I hope this release (obs 32.1.2) will work on my distro",
        "F1.8 requested: 'please make 32.1.2 work'": "Please make OBS 32.1.2 work on this distro",
        "F1.9 expectation: '32.1.2 is supposed to work'": "32.1.2 is supposed to work with PipeWire",
        "F1.10 mirror direction, modal: 'it should work on 32.1.2'": "it should work on 32.1.2 according to the notes",
        "F1.11 mirror direction, hope: 'I hope it works with 32.1.2'": "I hope it works with 32.1.2 this time",
        "F1.12 mirror direction, question: 'will it work with 32.1.2'": "will it work with 32.1.2 on older GPUs",
        "F1.13 mirror direction, conditional: 'if it works in 32.1.2'": "if it works in 32.1.2 we can drop the patch",
    }
    for label, text in hypothetical.items():
        check(label, not vetoes(text), str(outcome(text)))

    print(NL + "[F1] a genuine present or past working claim still vetoes")
    genuine = {
        "F1.20 '32.1.2 works fine'": ("32.1.2 works fine for me", to.WORKING),
        "F1.21 '32.1.2 worked for me'": ("32.1.2 worked for me all week", to.WORKING),
        "F1.22 'rolled back to 32.1.2 and it works'": ("I rolled back to 32.1.2 and it works", to.ROLLBACK),
        "F1.23 mirror direction: 'it works on 32.1.2'": ("it works on 32.1.2 without the plugin", to.WORKING),
    }
    for label, (text, want) in genuine.items():
        got = outcome(text)
        check(label, got.vetoes and got.outcome == want, str(got))

    print(NL + "[F1] inverse probes: a hypothetical word nearby does not cancel a genuine claim")
    inverse = {
        "F1.30 'if' governs a different clause": "If you need a stable build, 32.1.2 works fine.",
        "F1.31 'should' far from the target": "It should be noted that 32.1.2 works.",
        "F1.32 'as expected' then a claim": "As expected, 32.1.2 works.",
        "F1.33 'got 32.1.2 to work' is achieved, not hoped": "I finally got 32.1.2 to work.",
        "F1.34 'hopefully this helps' then a claim": "Hopefully this helps: 32.1.2 works for me.",
        "F1.35 a modal AFTER the claim": "32.1.2 works, so I would stay on it.",
        "F1.36 emphatic 'does work' is not a question": "it does work on 32.1.2",
        "F1.37 a lead word not followed by filler": "I hope you know 32.1.2 works fine",
        "F1.38 the hope governs a different verb": "I hoped 32.1.2 would fix it, and it works now",
        "F1.39 'if' clause ends before the claim": "If it helps, it works on 32.1.2",
        "F1.40 a condition AFTER the claim": "32.1.2 works if you disable the plugin",
        "F1.41 'did work' past emphatic": "it did work on 32.1.2",
    }
    for label, text in inverse.items():
        check(label, vetoes(text), str(outcome(text)))

    print(NL + "[F1] scope: only the two 'work' cues changed")
    check("F1.50 the hypothesis guard covers exactly target_works and works_on_target",
          to._HYPOTHESIS_SENSITIVE == frozenset({"target_works", "works_on_target"}),
          str(sorted(to._HYPOTHESIS_SENSITIVE)))
    check("F1.51 the polarity-sensitive set is unchanged",
          to._POLARITY_SENSITIVE == frozenset({"works_on_target", "target_works", "target_successful",
                                               "fixed_in_target"}), str(sorted(to._POLARITY_SENSITIVE)))
    roll = outcome("I hope to downgrade to 32.1.2 tonight")
    check("F1.52 the rollback cue is untouched, even under a hope (out of this fix's scope)",
          roll.outcome == to.ROLLBACK, str(roll))

    # ------------------------------------------------------------------ F2
    print(NL + "[F2] the stored #13518 row: an install failure, still counted, never refused")
    check("F2.0 the live #13518 row exists, is counted and has no exclusion reason",
          live.get("counted") is True and live.get("exclusion_reason") in (None, ""),
          f"counted={live.get('counted')} reason={live.get('exclusion_reason')}")
    refused, undeterminable = wd.assess_rows([live] if live else [])
    check("F2.1 the tool neither refuses nor marks undeterminable the stored #13518 row",
          refused == [] and undeterminable == [], f"{ids(refused)} {ids(undeterminable)}")
    layout = template_layout(str(live.get("report_text_excerpt") or ""))
    check("F2.2 #13518 in its issue-template layout declares 32.1.2 (R1 applies)",
          obs.declared_versions({"body": layout}) == {V}, str(obs.declared_versions({"body": layout})))
    check("F2.3 and the collector's own authority does not refuse it in that layout",
          obs.contradiction_reason({"title": live.get("report_title"), "body": layout}, V) is None,
          str(obs.contradiction_reason({"title": live.get("report_title"), "body": layout}, V)))
    as_text = dict(live, report_text=layout)
    r2, u2 = wd.assess_rows([as_text])
    check("F2.4 a stored row whose report text keeps the template layout is decidable and kept",
          r2 == [] and u2 == [] and not wd.declaration_lost(wd.stored_issue(as_text)),
          f"{ids(r2)} {ids(u2)}")

    print(NL + "[F2] field boundaries survive the rebuild")
    cross = row("obs-fixture-cross-field", "Everything works",
                "with 32.1.2 the preview drops frames after an hour", source_type="obs_forum_thread")
    spaced = " ".join(str(cross.get(k) or "") for k in
                      ("report_title", "parent_title", "report_text", "report_text_excerpt"))
    check("F2.10 control: run together with spaces, the title's verb binds to the excerpt's version",
          to.classify_target_outcome(spaced, V).outcome == to.WORKING,
          str(to.classify_target_outcome(spaced, V)))
    issue = wd.stored_issue(cross)
    check("F2.11 the rebuilt issue keeps the title and the body as separate fields",
          issue == {"title": "Everything works",
                    "body": "with 32.1.2 the preview drops frames after an hour"}, str(issue))
    check("F2.12 so the tool does not refuse the row on a cue that crosses the field boundary",
          wd.assess_rows([cross]) == ([], []), str(wd.assess_rows([cross])))
    two = row("obs-fixture-two-fields", "Title A", "body text", report_text="first line" + NL + "second line")
    two["parent_title"] = "Parent B"
    rebuilt = wd.stored_issue(two)
    check("F2.13 each distinct title is its own line, a repeated title appears once, and the body is "
          "the report text with its line breaks (the excerpt only without it)",
          rebuilt == {"title": "Title A" + NL + "Parent B", "body": "first line" + NL + "second line"}
          and wd.stored_issue(cross)["title"].count("Everything works") == 1, repr(rebuilt))

    print(NL + "[F2] a declaration the stored text lost: UNDETERMINABLE, never refused")
    flat = ("### Operating System Info Windows 11 ### OBS Studio Version 32.1.2 ### OBS Studio Version "
            "(Other) _No response_ ### Expected Behavior the audio meter works on 32.1.2 while the "
            "window is visible ### Current Behavior the meter freezes once minimised")
    lost = row("obs-fixture-lost-declaration", "Audio meter freezes when minimised", flat,
               url="https://example.invalid/lost")
    r3, u3 = wd.assess_rows([lost])
    check("F2.20 control: the role authority alone would refuse this flattened row",
          obs.contradiction_reason(wd.stored_issue(lost), V) == "version_reported_working",
          str(obs.contradiction_reason(wd.stored_issue(lost), V)))
    check("F2.21 the tool reports it UNDETERMINABLE, not refused",
          r3 == [] and ids(u3) == [lost["id"]], f"{ids(r3)} {ids(u3)}")
    check("F2.22 refused_rows (the T27 interface) never returns it",
          wd.refused_rows([lost]) == [], str(ids(wd.refused_rows([lost]))))
    lost_layout = dict(lost, report_text=template_layout(flat))
    check("F2.23 the same report with its line breaks is decided: declared, so R1 keeps it",
          wd.assess_rows([lost_layout]) == ([], []) and obs.declared_versions(
              {"body": lost_layout["report_text"]}) == {V}, str(wd.assess_rows([lost_layout])))
    check("F2.24 the heading counter agrees with the collector's field reader",
          wd.declaration_lost({"body": flat}) and not wd.declaration_lost({"body": template_layout(flat)}),
          f"{wd.declaration_lost({'body': flat})} {wd.declaration_lost({'body': template_layout(flat)})}")
    forum = row("obs-fixture-forum-rollback", "Recording stutters on 32.2.0",
                "Recording stutters on 32.2.0. I downgraded to 32.1.2 and it is smooth again.",
                url="https://example.invalid/forum", source_type="obs_forum_thread")
    r4, u4 = wd.assess_rows([forum])
    check("F2.25 a row with no template heading is still decidable and refused on its own words",
          ids(r4) == [forum["id"]] and u4 == [] and r4[0][1] == "version_is_rollback_target",
          f"{ids(r4)} {ids(u4)}")

    print(NL + "[F2] the CLI never withdraws an undeterminable row, even when named")
    with tempfile.TemporaryDirectory(prefix="aux129-") as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        write_evidence_file([lost, forum], store)
        original = store.read_bytes()
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        named = subprocess.run([sys.executable, str(TOOL), "--path", str(store), "--only-url", lost["source_url"],
                                "--write"], capture_output=True, text=True, encoding="utf-8", env=env,
                               cwd=str(SCRIPTS))
        check("F2.30 naming the undeterminable row moves nothing and writes nothing",
              named.returncode == 0 and store.read_bytes() == original
              and "rows moved to audited withdrawal: 0" in named.stdout
              and "rows UNDETERMINABLE from stored text" in named.stdout
              and "[undeterminable] 32.1.2  would be version_reported_working" in named.stdout,
              named.stdout[-600:] + named.stderr[-300:])
        control = subprocess.run([sys.executable, str(TOOL), "--path", str(store), "--only-url",
                                  forum["source_url"], "--write"], capture_output=True, text=True,
                                 encoding="utf-8", env=env, cwd=str(SCRIPTS))
        after = {r["id"]: r for r in load_evidence(store)}
        check("F2.31 control: naming the decidable row still withdraws exactly it, row kept",
              control.returncode == 0 and "rows moved to audited withdrawal: 1" in control.stdout
              and after[forum["id"]]["counted"] is False
              and after[forum["id"]]["exclusion_reason"] == "version_is_rollback_target"
              and after[lost["id"]]["counted"] is True and len(after) == 2,
              control.stdout[-600:] + control.stderr[-300:])

    print(NL + "[G] the live evidence store is read only")
    check("G1 the live evidence store is byte-identical after the suite",
          hashlib.sha256(EVIDENCE_PATH.read_bytes()).hexdigest() == live_before)
    # A corpus observation, not a check: rows a later collection adds must not turn this suite red
    # (the store changes after a pull request merges). At this change it is 0 and 0.
    live_refused, live_undet = wd.assess_rows(live_rows)
    print(f"  {'INFO' if not (live_refused or live_undet) else 'WARN'}  live store: tool refuses "
          f"{len(live_refused)} counted OBS row(s), {len(live_undet)} undeterminable "
          f"{ids(live_refused) + ids(live_undet)}")

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
