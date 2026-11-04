#!/usr/bin/env python3
"""Teams derives platform, theme, area and severity from the reporter's text; the builder never turns
a missing severity into "low".

Before this change the Teams collector wrote `platform="Windows"` on every row (including rows it had
itself refused as Mac or VDI) and left theme, area and severity empty. The consensus builder's
`severity_summary` then counted a missing severity as "low", so a summary over rows with no severity
claimed they were all mildly severe.

THE LINE THIS SUITE HOLDS. Classification, sentiment and acceptance are three separate things:
  - platform/theme/area/severity come ONLY from what the reporter wrote;
  - with no supported theme the result stays unclassified (empty): a severity is never invented
    because a row is counted;
  - sentiment is FROZEN: "negative" on a counted row, empty on every other row, whatever the theme;
  - acceptance (counted / exclusion_reason) is identical with and without the theme table;
  - the three counting predicates that read `severity or "low"` are untouched (source-pinned below),
    because an empty severity being VALID is an acceptance decision, not a summary one.

Frozen fixtures, offline, no read of the evidence store: the governed manifest compares this suite's
total to an exact `= N`.
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_consensus_from_evidence as builder                      # noqa: E402
from lib import evidence_classification as ec                        # noqa: E402
from patch_collectors import base                                    # noqa: E402
from patch_collectors import microsoft_teams as teams                # noqa: E402

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
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


BUILD = "26198.304.4946.9672"
RECORD = base.PatchRecord(
    product_id="microsoft-teams", update_version=BUILD, path=Path("teams.md"),
    update_published_at="2026-08-03T00:00:00Z", update_status="current",
    update_product="Microsoft Teams")
URL = "https://learn.microsoft.com/en-us/answers/questions/5984300/teams-meeting-crash"


def judge(title: str, text: str, segment_type: str = "question") -> dict:
    return teams.evaluate_candidate(RECORD, {
        "source_type": teams.QNA_SOURCE_TYPE, "source_name": teams.QNA_SOURCE_NAME,
        "source_url": URL + ("" if segment_type == "question" else "#answer-1"),
        "parent_title": title, "report_title": title, "report_text": text,
        "source_date": "2026-09-01", "segment_type": segment_type,
    }, "2026-09-29T00:00:00Z")


def run_suite() -> int:
    print("=" * 92)
    print("Teams producer classification and the builder's missing-severity summary")
    print("=" * 92)

    # --- platform: the reporter's own text, never the product's release platform -------------
    no_os = judge("Teams crashes in meetings", f"Teams {BUILD} crashes every time I start a meeting.")
    check("P1 a report naming no operating system reads 'unknown', not 'Windows'",
          no_os["platform"] == "unknown", no_os["platform"])
    check("P2 the unknown report is still COUNTED: platform does not gate acceptance",
          no_os["counted"] is True and no_os["exclusion_reason"] is None)

    win = judge("Teams crashes in meetings", f"On Windows 11, Teams {BUILD} crashes whenever I join a meeting.")
    check("P3 a report that names Windows 11 reads 'windows' (lowercase vocabulary)",
          win["platform"] == "windows", win["platform"])

    mac = judge("Teams crashes on my Mac", f"On my Mac, Teams {BUILD} crashes whenever I join a meeting.")
    check("P4 a refused Mac report is no longer labelled Windows: it reads 'macos'",
          mac["platform"] == "macos" and mac["exclusion_reason"] == "platform_mac"
          and mac["counted"] is False, f"{mac['platform']} {mac['exclusion_reason']}")

    both = judge("Teams crashes", f"Windows 11 and macOS both crash on Teams {BUILD} when I join a meeting.")
    check("P5 two platforms named in one report read 'unknown'", both["platform"] == "unknown", both["platform"])

    ui_noun = judge("Teams windows freeze", f"Teams {BUILD}: the meeting windows and menus freeze.")
    check("P6 'windows' as a UI noun is not platform evidence", ui_noun["platform"] == "unknown", ui_noun["platform"])

    reply = judge("Teams crashes", f"On my MacBook the same build {BUILD} crashes.", segment_type="answer")
    check("P7 a reply-segment row is classified from its own text too ('macos', not 'Windows')",
          reply["platform"] == "macos" and reply["exclusion_reason"] == "reply_segment_not_counted_v1",
          f"{reply['platform']} {reply['exclusion_reason']}")

    check("P8 no row carries the old literal 'Windows'",
          all(row["platform"] != "Windows" for row in (no_os, win, mac, both, ui_noun, reply)))

    # --- theme / area / severity: a supported classification only ----------------------------
    cases = (
        ("T1 sign-in", "Teams sign in loop", "I am unable to sign in to Teams at all.",
         ("sign-in failure", "authentication", "high")),
        ("T2 crash", "Teams keeps crashing", "The desktop app crashes a minute into every meeting.",
         ("crash or hang", "system stability", "high")),
        ("T3 audio", "No audio in calls", "I hear no audio from other participants.",
         ("audio / video failure", "meeting audio and video", "medium")),
        ("T4 screen sharing", "Screen sharing broken", "Screen sharing shows a grey rectangle.",
         ("screen sharing failure", "screen sharing", "medium")),
        ("T5 join failure", "Teams meeting trouble", "I am unable to join any scheduled meeting.",
         ("meeting join / connection failure", "meetings", "high")),
        ("T6 launch failure", "New Teams won't launch", "The app won't launch after the update.",
         ("launch / open failure", "startup", "high")),
        ("T7 performance", "Teams is very slow", "Everything is slow and laggy.",
         ("performance regression", "performance", "medium")),
    )
    for label, title, text, expected in cases:
        got = teams.classify(title, text)
        check(f"{label} -> {expected[0]} / {expected[1]} / {expected[2]}",
              got[:2] == expected[:2] and got[3] == expected[2], str(got))

    sub = teams.classify("Teams chat settings changed", "My channel layout changed after the update.")
    check("T8 'hang' inside 'changed' is not a crash (word boundaries, not substrings)",
          sub[0] != "crash or hang", str(sub))

    denied = teams.classify("No crash after the update", "There is no crash at all, but the audio drops.")
    check("T9 a denied symptom does not theme the report: 'no crash' is not 'crash or hang'",
          denied[0] == "audio / video failure", str(denied))

    heading = teams.classify("Teams crashes on launch", "Also the camera preview is a little dark.")
    check("T10 the reporter's headline outweighs a passing body mention", heading[0] == "crash or hang", str(heading))

    # --- failure context is required (a plain mention establishes no malfunction) ---------------
    plain_signin = teams.classify("Teams crashes in meetings", "After I sign in each morning, Teams is fine until the call.")
    plain_signin_only = teams.classify("Question about Teams", "I sign in every morning and log in to my tenant.")
    check("T11 a plain mention of signing in is not a HIGH sign-in failure",
          plain_signin[0] != "sign-in failure" and plain_signin_only == ("", "", "unknown", ""),
          f"{plain_signin} {plain_signin_only}")
    signin_failures = ("Reset and sign-in failed.", "Teams sign in loop after the update.",
                       "I cannot log in to Teams.", "Stuck on the sign-in page.", "Authentication error 0xcaa20003.")
    check("T12 a failed sign-in, a loop, an error or inability to sign in is still a HIGH sign-in failure",
          all(teams.classify(text, "")[:2] + (teams.classify(text, "")[3],)
              == ("sign-in failure", "authentication", "high") for text in signin_failures),
          str([teams.classify(text, "") for text in signin_failures]))
    plain_chat = teams.classify("Teams chat", "I read my messages and notifications in the channel every day.")
    check("T13 a plain mention of chat, messages, notifications or channels establishes no malfunction",
          plain_chat == ("", "", "unknown", ""), str(plain_chat))
    chat_failures = ("Teams messages won't go through.", "I cannot send messages in a channel.",
                     "Notifications are not showing.", "Missing chat messages after the update.",
                     "Not receiving notifications.")
    check("T14 a message that cannot be sent, a missing chat or absent notification is still a chat problem",
          all(teams.classify(text, "")[0] == "chat or notification problem" for text in chat_failures),
          str([teams.classify(text, "")[0] for text in chat_failures]))
    plain_av = teams.classify("Teams", "I use my camera and video and audio every day.")
    check("T15 a plain mention of camera, video or audio establishes no A/V fault", plain_av[0] == "", str(plain_av))
    lag = teams.classify(
        "Teams desktop: system-wide lag when decoding incoming camera video, Video Codec engine at 70 % "
        "(AMD Radeon integrated GPU) - Microsoft Q&A",
        "In the Teams desktop app, my whole computer starts lagging as soon as another participant turns "
        "their camera on: audio becomes choppy, video drops to a")
    check("T16 the counted 'system-wide lag when decoding incoming camera video' report is performance",
          lag[:2] == ("performance regression", "performance") and lag[3] == "medium", str(lag))

    # --- no supported classification: unclassified, severity never invented -------------------
    unsupported = judge("Question about Teams", f"Teams {BUILD}: something is off and I do not know what.")
    check("U1 no supported theme -> empty theme, area and severity (nothing invented)",
          (unsupported["issue_theme"], unsupported["workflow_area"], unsupported["severity"]) == ("", "", ""),
          str((unsupported["issue_theme"], unsupported["workflow_area"], unsupported["severity"])))
    blank = teams.classify("", "")
    check("U2 empty text -> fully unclassified, platform 'unknown'", blank == ("", "", "unknown", ""), str(blank))

    counted_unclassified = judge("Teams is wrong", f"Teams {BUILD} throws an error and is broken since the update.")
    check("U3 a COUNTED row with no supported theme carries no severity",
          counted_unclassified["counted"] is True and counted_unclassified["severity"] == "",
          str(counted_unclassified))

    # --- the table itself -----------------------------------------------------------------------
    check("V1 every Teams rule severity is inside the shared vocabulary",
          all(rule.severity in ec.VALID_SEVERITIES for rule in teams._TEAMS_THEME_RULES))
    check("V2 no Teams theme text is empty or 'unspecified issue' (an empty/unspecified theme is the unclassified result)",
          all(rule.theme.strip() and rule.theme.lower() != "unspecified issue" for rule in teams._TEAMS_THEME_RULES))
    check("V3 classify returns four fields: it has no sentiment to return",
          len(teams.classify("a", "b")) == 4)
    check("V4 the same call twice gives the same answer (deterministic)",
          teams.classify("Teams crashes", "audio and sign in") == teams.classify("Teams crashes", "audio and sign in"))

    # --- sentiment is frozen -------------------------------------------------------------------------
    counted_rows = (no_os, win, counted_unclassified)
    check("S1 every counted row carries sentiment 'negative', whatever its theme",
          all(row["counted"] is True and row["sentiment"] == "negative" for row in counted_rows))
    rejected_rows = (mac, reply, judge("Teams chat", "No version here at all, the chat is broken."))
    check("S2 no rejected row carries a sentiment, whatever its theme",
          all(row["counted"] is False and row["sentiment"] == "" for row in rejected_rows),
          str([(r["counted"], r["sentiment"]) for r in rejected_rows]))
    check("S3 a themed counted row (crash) and an unthemed counted row share one sentiment",
          no_os["sentiment"] == counted_unclassified["sentiment"] == "negative")

    # --- acceptance is unchanged by classification ----------------------------------------------------
    check("A1 source identity, date, URL and weight are preserved on a counted row",
          win["source_url"] == URL and win["source_date"] == "2026-09-01"
          and win["source_weight"] == 1 and win["matched_version"] == BUILD)
    check("A2 a row without the exact build is refused for that reason, themed or not",
          judge("Teams crashes", "Teams crashes every time, no build given.")["exclusion_reason"]
          == "missing_exact_patch_version_match")

    # --- builder: a missing severity is never 'low' -------------------------------------------------
    rows = [{"severity": ""}, {"severity": None}, {}, {"severity": "high"}, {"severity": "HIGH"},
            {"severity": "low"}, {"severity": "   "}]
    keys = [builder.severity_summary_key(r) for r in rows]
    check("B1 a missing severity (empty, None, absent, blank) is 'unspecified', not 'low'",
          keys[0] == keys[1] == keys[2] == keys[6] == "unspecified", str(keys))
    check("B2 a stated severity is kept, lower-cased; a real 'low' stays 'low'",
          keys[3] == keys[4] == "high" and keys[5] == "low", str(keys))
    check("B3 'unspecified' is not a member of the severity vocabulary (it is a summary label only)",
          "unspecified" not in ec.VALID_SEVERITIES)

    builder_src = (SCRIPTS / "build_consensus_from_evidence.py").read_text(encoding="utf-8")
    check("B4 the builder no longer contains the `or \"low\"` fallback",
          'or "low"' not in builder_src and "or 'low'" not in builder_src)
    check("B5 the summary Counter is fed by the helper",
          "Counter(severity_summary_key(item) for item in items)" in builder_src)

    # --- the three COUNTING/VALIDITY predicates keep their fallback (acceptance, not summary) ----
    for label, rel in (("C1 apply_consensus_to_records", "apply_consensus_to_records.py"),
                       ("C2 qa_patch_records", "qa_patch_records.py"),
                       ("C3 lib.live_eligibility", "lib/live_eligibility.py")):
        text = (SCRIPTS / rel).read_text(encoding="utf-8")
        check(f"{label} still treats an empty severity as valid (`or \"low\"` untouched)",
              re.search(r'strip\(\)\.lower\(\) or "low"\)', text) is not None)

    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
