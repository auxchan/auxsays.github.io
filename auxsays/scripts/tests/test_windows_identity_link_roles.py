#!/usr/bin/env python3
"""Windows acceptance: `identity_not_linked_to_issue` (AUX-076, the AUX-067 residual R1), the narrow rule.

Offline and deterministic, on SYNTHETIC text only. The rule refuses a build-only identity (title silent
on the build and the KB) only when EVERY body mention of the build is a pure statement of the
reporter's current state and the body has no word that could tie the build to the issue; anything else
fails open. The corpus shapes come from tests/fixtures/windows_link_roles/corpus_shapes.json:
paraphrases written for this suite, one per stored row the rule refuses (14) or keeps (10), each
reaching the same decision, the same per-occurrence roles and the same link words as its stored
original (checked once, outside CI, by diagnose_windows_link_roles.py --fixture-equivalence). The
second and third independent verifiers' probes are frozen as written in verifier2_probes.json and
verifier3_probes.json. Nothing here reads `_data`, a record or the evidence store, and no live total
is pinned: corpus growth cannot turn this suite red.

    A  scope guards and placement: a KB match, a title naming the build or KB, a build absent from
       the body and an empty build are never touched; every earlier, more specific reason keeps its
       reason; the rule runs after identity_not_the_subject
    B  preservation: every keep case of every earlier round and of all three independent
       verifications, each kept by the authority AND by the authority with the rule off
    C  negatives: the 14 refused corpus shapes, the earlier refusal cases the narrow rule still
       refuses, and one refusal per state marker, label, identity word and run character the stored
       shapes do not already pin. Every refusal is checked in the SAME check against the authority with
       the rule switched off, which must accept it, so the rule is the deciding gate
    D  mechanics: one keep witness per link word, per take-up word and per blocking word (deleting any
       one of them refuses the case it keeps), every occurrence must be a stated state, the build's
       sentence end, sentence and parenthesis masking, and the leading title copies
    E  declared limits, pinned as current behaviour and not claimed closed
    F  one authority for every Windows discovery method, and the consumers of the new reason
    G  the pinned refusal manifest (scripts/audit/r1_link_roles_refusals_2026-11-05.json)
    H  declared residual admissions R1N-01..R1N-03 (ledger AUX-076): earlier refusal cases and verifier
       refuse probes the narrow rule admits, each admitted by the authority on main too (rule off), so
       none is introduced by this change; pinned so that a later fix flips them on purpose

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_windows_identity_link_roles.py
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from lib import evidence_loss as el  # noqa: E402
from lib import report_counts as rc  # noqa: E402
from lib import tier2_evidence as t2  # noqa: E402
from patch_collectors import microsoft_windows as mw  # noqa: E402
from patch_collectors.base import PatchRecord, WINDOWS_PRODUCT_ID  # noqa: E402

FIX = _SCRIPTS / "tests" / "fixtures" / "windows_link_roles" / "corpus_shapes.json"
FIX_V2 = _SCRIPTS / "tests" / "fixtures" / "windows_link_roles" / "verifier2_probes.json"
FIX_V3 = _SCRIPTS / "tests" / "fixtures" / "windows_link_roles" / "verifier3_probes.json"
MANIFEST = _SCRIPTS / "audit" / "r1_link_roles_refusals_2026-11-05.json"
REASON = "identity_not_linked_to_issue"
CLASSES = ("R1N-01", "R1N-02", "R1N-03")
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


T7840 = {"target_feature_version": "25H2", "target_kb": "KB5077181", "target_os_build": "26200.7840",
         "target_release_date": "2026-02-10", "update_version": "25H2"}
T7623 = {"target_feature_version": "25H2", "target_kb": "KB5074109", "target_os_build": "26200.7623",
         "target_release_date": "2026-01-13", "update_version": "25H2"}
T9711 = {"target_feature_version": "26H2", "target_kb": "KB5127648", "target_os_build": "26300.9711",
         "target_release_date": "2026-10-13", "update_version": "26H2"}
T25 = {"target_feature_version": "25H2", "target_kb": "KB5127648", "target_os_build": "26200.9711",
       "target_release_date": "2026-10-13T00:00:00Z", "update_version": "25H2"}
URL = "https://learn.microsoft.com/en-us/answers/questions/99999/synthetic"
B = "26200.7840"
TAIL = "The printer shows offline since the update."


@contextmanager
def rule_off():
    """The authority with ONLY the link rule switched off."""
    original = mw.identity_not_linked_to_issue
    mw.identity_not_linked_to_issue = lambda *_a, **_k: False
    try:
        yield
    finally:
        mw.identity_not_linked_to_issue = original


def ids(target: dict, text: str) -> tuple[str, str, str]:
    kb = target["target_kb"] if mw._has_exact(text, target["target_kb"]) else ""
    build = target["target_os_build"] if mw._has_exact(text, target["target_os_build"]) else ""
    feature = target["target_feature_version"] if mw._has_exact(text, target["target_feature_version"]) else ""
    return kb, build, feature


def reason_of(target: dict, title: str, body: str, date: str = "2026-11-01") -> str | None:
    """The authority as `row_from_candidate` drives it: parent_title + report_title + body, identity
    matched on that joined text."""
    text = " ".join([title, title, body]).strip()
    return mw.windows_learn_qna_reason(target, URL, date, text, title, *ids(target, text))


def reason_live(target: dict, title: str, body: str) -> str | None:
    """The PRODUCTION construction: every Windows source builds report_text as title + body (Learn Q&A,
    Tech Community and the Windows 11 Forum alike), and row_from_candidate prepends parent_title and
    report_title, so the authority sees three leading copies of the title before the post's own text."""
    text = " ".join([title, title, title + " " + body]).strip()
    return mw.windows_learn_qna_reason(target, URL, "2026-11-01", text, title, *ids(target, text))


def reason_row(target: dict, title: str, body: str) -> str | None:
    """A Learn Q&A candidate through row_from_candidate, with report_text = clean_html(title + " " +
    body) exactly as the Learn source builds it (the verifiers' construction)."""
    rec = PatchRecord(WINDOWS_PRODUCT_ID, target["update_version"], Path("synthetic.md"), target["target_release_date"],
                      "current", "Windows 11", target["target_os_build"])
    cand = {"source_type": "microsoft_learn_qna", "source_name": "Microsoft Learn Q&A", "source_url": URL,
            "parent_title": title, "report_title": title,
            "report_text": mw.learn_qna.clean_html(" ".join([title, body]).strip()), "source_date": "2026-11-01"}
    return mw.row_from_candidate(rec, target, cand, "2026-11-05T00:00:00Z")["exclusion_reason"]


def both(target: dict, title: str, body: str, live: bool | str = False) -> tuple[str | None, str | None]:
    decide = reason_row if live == "row" else reason_live if live else reason_of
    got = decide(target, title, body)
    with rule_off():
        off = decide(target, title, body)
    return got, off


def roles(target: dict, title: str, body: str) -> list[tuple[str, str]]:
    text = " ".join([title, title, body]).strip()
    return [(r, k) for r, k, _s in mw.identity_link_details(text, title, target["target_os_build"])]


def only(target: dict, title: str, body: str) -> tuple[str, str] | None:
    r = roles(target, title, body)
    return r[0] if len(r) == 1 else None


def words(title: str, body: str) -> list[str]:
    return sorted({n for n, _w in mw.identity_link_words(" ".join([title, title, body]).strip(), title)})


def retained(case: dict) -> str:
    excerpt = case["report_text_excerpt"]
    if excerpt.endswith("..."):
        excerpt = excerpt[:-3]
    return " ".join([case["parent_title"], case["report_title"], excerpt]).strip()


def case_decision(case: dict) -> tuple[str | None, str | None, list[list[str]], list[str]]:
    text = retained(case)
    args = (case["target"], case["source_url"], case["source_date"], text, case["report_title"],
            case["matched_kb"], case["matched_os_build"], case["matched_feature_version"])
    got = mw.windows_learn_qna_reason(*args)
    with rule_off():
        off = mw.windows_learn_qna_reason(*args)
    det = [[r, k] for r, k, _s in mw.identity_link_details(text, case["report_title"], case["matched_os_build"])]
    lw = sorted({n for n, _w in mw.identity_link_words(text, case["report_title"])})
    return got, off, det, lw


def residual_class(target: dict, title: str, body: str, live: bool | str = False) -> str:
    """R1N-01 a mention that is not a stated state; R1N-02 a stated state continued, taken up or after a
    blocking word; R1N-03 every mention a stated state, but the body has a link word."""
    if live == "row":
        text = " ".join([title, title, mw.learn_qna.clean_html(" ".join([title, body]).strip())]).strip()
    else:
        text = " ".join([title, title, (title + " " + body) if live else body]).strip()
    found = [r for r, _k, _s in mw.identity_link_details(text, title, target["target_os_build"])]
    return "R1N-01" if "unlinked" in found else "R1N-02" if "linked" in found else "R1N-03"


KEEP = [
    ("K1", T7840, "Help please", "The 2026-02 update (26200.7840) fails to install with 0x800f0991."),
    ("K2", T7840, "Audio gone", "After installing 26200.7840 my audio stopped working."),
    ("K3", T7840, "Printer problem", "Since installing 26200.7840 my printer no longer prints."),
    ("K4", T7840, "Wi-Fi gone", "26200.7840 broke my Wi-Fi adapter after the update."),
    ("K5", T7840, "Taskbar freezes", "After updating to build 26200.7840, the taskbar freezes."),
    ("K6", T7840, "Cannot install", "Can't install 26200.7840, it rolls back at 100%."),
    ("K7", T7840, "Boot loop", "Build 26200.7840 installed and after the update the laptop is in a boot loop."),
    ("K8", T7840, "Search broken", "After the update to Windows 11 25H2 OS Build 26200.7840 the search box does not work."),
    ("K9", T7840, "Second monitor", "After Windows updated to 26200.7840 overnight the second monitor is not detected."),
    ("K10", T7840, "Drucker", "Nach dem Update auf 26200.7840 funktioniert der Drucker nicht mehr, error 0x00000709."),
    ("K11", T7840, "Two disks", "Before a recent Windows 11 update (build 26200.7840), I had one C: drive. After the update there are two."),
    ("K12", T7840, "Search gone", "Since I installed the latest update on Friday, I installed it (25H2; Build 26200.7840). After the restart search fails."),
    ("K13", T7840, "Printing", "After updating from 26200.7623 to 26200.7840 printing no longer works."),
    ("K14", T7840, "BSOD", "OS Build 26200.7840 causes a BSOD every boot after the update."),
    ("K15", T7840, "Explorer crashes", "I upgraded from Windows 10 to Windows 11 25H2 (26200.7840) and after the upgrade Explorer crashes."),
    ("K16", T7840, "Audio gone", "26200.7840 installed successfully but after the update my audio is gone."),
    ("K17", T7840, "Rollback", "The update to 26200.7840 failed to install and rolled back to 26200.7623."),
    ("K18", T7840, "Monitor flickers", "Since 26200.7840 was installed the second monitor flickers; the update broke it."),
    ("K19", T7840, "Search box", "On 26200.7840 since the update yesterday the search box is not working."),
    ("K20", T7840, "Explorer crashes", "I'm on 26200.7840 since the update and File Explorer crashes on launch."),
    ("K21", T7840, "Mic muted", "Windows 11 Pro (OS build 26200.7840) after the latest update my mic is muted."),
    ("K22", T7840, "Install fails", "26200.7840 fails to install without any error message, it just rolls back."),
    ("K23", T7840, "VPN drops", "After the 2026-02 Cumulative Update for Windows 11 Version 25H2 for x64-based Systems (KB5077999) (26200.7840) my VPN drops."),
    ("K24", T7840, "Explorer", "Ever since 26200.7840 File Explorer crashes after the update."),
    ("K25", T7840, "Printer stopped", "Since the update on 26200.7840 my printer stopped working. Uninstalling the update fixed it."),
    ("K26", T7840, "Calls drop", "Updated to 26200.7840 last night; since then calls drop after the update."),
    ("K27", T7840, "Install fails", "26200.7840 fails to install with 0x800f0922 and rolls back."),
    ("K28", T7840, "Camera fails", "After updating to Windows 11 Home Single Language 26200.7840 the camera fails."),
    ("P1", T7840, "Taskbar keeps crashing", "We are on 26200.7840 after last night's update and the taskbar keeps crashing every few minutes."),
    ("P2", T7840, "Printing broken", "I'm running 26200.7840 since yesterday's update and every printer shows offline."),
    ("P3", T7840, "Audio crackles", "Got 26200.7840 yesterday and now my audio crackles. The update broke my sound."),
    ("P4", T7840, "Wi-Fi drops", "My laptop moved to 26200.7840 overnight and Wi-Fi now drops every hour. It started right after the update."),
    ("P5", T7840, "Search box broken", "Windows Update put me on 26200.7840 today. Since the update the search box does not accept typing."),
    ("P6", T7840, "Explorer hangs", "I am currently on 26200.7840, which arrived with Patch Tuesday, and since installing it Explorer hangs."),
    ("P9", T7840, "Update rolled back", "26200.7840 rolled back twice during restart with error 0x800f0922."),
    ("P10", T7840, "Cannot sign in", "Since 26200.7840 I cannot sign in with Windows Hello. Uninstalling the update fixed it."),
]

REFUSE = [
    ("R1", T7840, "Bluetooth stopped working after update",
     "Edition Windows 11 Pro Version 25H2 Installed on 2/14/2026 OS build 26200.7840 Experience Windows Feature Experience Pack."),
    ("R2", T7840, "Explorer crashes on launch", "I'm running 26200.7840. Since the update File Explorer crashes on launch."),
    ("R3", T7840, "Explorer crashes on launch", "I'm on 26200.7840 and since the update File Explorer crashes on launch."),
    ("R4", T7840, "Sudden BSODs", "Crashes started right after a windows app runtime update. Logs: Microsoft Windows 11 Home Version 25H2 (OS Build 26200.7840) ==== [SFC /ScanNow] Beginning system scan."),
    ("R5", T7840, "Feature update fails", "Upgrading from 26200.7840 to 26H2 fails with 0x800f0993."),
    ("R6", T7840, "Rollback", "Update rollback from Build 26200.7840 to Build 9168 every time, recurring update failure."),
    ("R7", T7840, "WSL install stuck", "System: Windows 11 Pro, Version 25H2, OS Build 26200.7840 Hardware: virtualization enabled. WSL install stuck at 14%."),
    ("R8", T7840, "Store error", "Running Windows 11 Pro, Version 25H2, OS Build 26200.7840, Windows Feature Experience Pack. Error 0x80070422 when installing apps."),
    ("R9", T7840, "Hello fails", "Environment: Windows 11 Enterprise 25H2 (build 26200.7840). After the update Windows Hello fails to load the container."),
    ("R10", T7840, "Disk Cleanup", "I am running Win11, v25H2, build 26200.7840, and ever since an update months ago Disk Cleanup shows 25mb."),
    ("R11", T7840, "Display", "Device Information: Model: Surface Laptop Processor: X1E OS: Windows 11 Pro, Version 25H2, Build 26200.7840 Issue Description: After the laptop was updated the display stays black."),
    ("R12", T7840, "GMKtec", "I have a GMKtec NucBox with Windows 11 Pro OS Build 26200.7840. Almost every month the update fails to install."),
    ("R13", T7840, "Windows Update fails with error 0x80070002",
     "Windows Update fails with error 0x80070002 Windows 11 25H2 (build 26200.7840), originally upgraded from 21H2. Problem: Settings shows an error."),
    ("R14", T7840, "Audio crackles", "I've got Windows 11 Pro 25H2 26200.7840 and since the update my audio crackles."),
    ("R15", T7840, "Search broke", "On 26200.7840 the search box is not working since the update yesterday."),
    ("R16", T7840, "Spotlight", "Windows 11 Pro 25H2 26200.7840 Spotlight fails to update lock screen images."),
    ("R17", T7840, "Wi-Fi", "Should I install 26200.7840? Since the January update my Wi-Fi breaks every day."),
    ("R18", T7840, "Printer offline", "I was running 26200.7840 fine until yesterday's update, now the printer is offline after the update."),
    ("R19", T7840, "Rollback", "The update to 26200.7922 failed to install and rolled back to 26200.7840 after the update."),
    ("R20", T7840, "Error 0x80070002", "Windows Update fails on 26200.7840 with 0x80070002 every night."),
    ("R21", T7840, "Printer bug", "Installing 26200.7840 to fix the printer bug, since the January update printing fails."),
    ("R22", T7840, "Store fails", "After a clean install, Windows 11 Pro 25H2 26200.7840, the Store fails with 0x80070005."),
    ("R23", T7840, "Driver install fails", "The Realtek audio driver update fails to install on my laptop running 26200.7840."),
    ("R24", T7840, "Next update", "26200.7840 went fine. The next update fails to install with 0x800f0922."),
    ("R25", T7840, "March update", "The March update on 26200.7840 fails to install with 0x800f0922."),
    ("R26", T7840, "Next update", "The next update on 26200.7840 fails to install with error 0x800f0922 every night."),
    ("R27", T7840, "2026-03 update", "I'm on 26200.7840. The 2026-03 update fails to install with 0x800f0922."),
    ("R28", T7840, "March update", "My laptop on 26200.7840 can't install the March update, error 0x800f0922."),
    ("R29", T7840, "Feature pack", "26200.7840 fails to install the Media Feature Pack, error 0x800F0991."),
    ("R30", T7840, "26H2 upgrade fails", "I was on 26200.7840 after the February update, then the 26H2 upgrade failed with 0xC1900101."),
    ("R32", T7840, "Defender definitions", "The Defender update KB2267602 fails to install on 26200.7840 since the February update."),
    ("R33", T7840, "Explorer crashes after the update", "26200.7840 here, Pro edition, and it happens every boot."),
    ("R34", T7840, "Network not working", "Network not working after Windows 11 25H2 update Windows Release OS: 26200.7840 What I've already tried: drivers."),
    ("R35", T7840, "Access denied", "Error 0x80070005 when connecting to 26200.7840 machines since the update."),
    ("N1", T7840, "26H2 upgrade fails at 35 percent", "Before upgrading to 26H2 I was on 26200.7840. The upgrade fails with error 0xC1900101 every time."),
    ("N2", T7840, "March update will not install", "I updated to 26200.7840 in February without problems. The March cumulative update fails to install with error 0x800f0922."),
    ("N3", T7840, "Defender definitions will not install", "The Defender update KB2267602 fails to install on 26200.7840 with error 0x80070643."),
    ("N6", T7840, "Screen flickers", "Update history: Successfully installed 26200.7840 on 2/11/2026. The screen started flickering after I bought a new monitor and installed its driver; error 0x80070005 in the log."),
    ("N7", T7840, "Wi-Fi drops", "Will installing 26200.7840 fix this? My Wi-Fi drops since the January update."),
    ("N9", T7840, "Store apps will not install", "Error 0x80070005 when installing any Store app. Windows 11 Pro 25H2 26200.7840 x64."),
    ("N10", T7840, "Feature update fails", "Trying to upgrade 26200.7840 machines to 26H2 fails with error 0xC1900101."),
    ("N11", T7840, "Media Feature Pack fails", "Installing the Media Feature Pack on 26200.7840 fails with error 0x800F0991."),
    ("N12", T7840, "Update stack package", "Update stack package 922.415 fails to install. winver shows 26200.7840."),
]

T24 = {"target_feature_version": "24H2", "target_kb": "KB5077181", "target_os_build": "26100.7840",
       "target_release_date": "2026-02-10", "update_version": "24H2"}

# Second round (the AUX-076 fix pass). "V-" cases are the independent verifier's probes, "M-" cases the
# implementer's own; every one is accepted by the authority with the rule off, so the rule decides it.
KEEP2 = [
    ("V-GK01", T7840, "Wi-Fi gone", "The 26200.7840 build broke my Wi-Fi. Rolling back the update fixed it."),
    ("V-GK03", T7840, "Printer error 0x00000709", "Since the February update on 26200.7840 my printer fails with error 0x00000709."),
    ("V-GK04", T7840, "Printer fails", "I'm having issues from the latest update (26200.7840): the printer fails after the update."),
    ("V-GK05", T7840, "Printer stopped", "Apart from that, after installing 26200.7840 the printer stopped working."),
    ("V-GK07", T7840, "Audio gone", "Successfully installed 26200.7840 yesterday, but since the update my audio is gone."),
    ("V-GK10", T7840, "Printer fails", "After the February 2026 update (OS Builds 26100.7840 and 26200.7840) my printer fails."),
    ("V-GK10b", T24, "Printer fails", "After the February 2026 update (OS Builds 26100.7840 and 26200.7840) my printer fails."),
    ("V-GK20", T7840, "Audio gone", "26200.7840 came through last night and my audio is gone. The update broke it."),
    ("V-GK32", T7840, "Bluetooth bug", "26200.7840 has a bug that breaks Bluetooth since I updated."),
    ("V-GK34", T7840, "Printer fixed by rollback", "Rolling back 26200.7840 fixed the printer after the update broke it."),
    ("V-GK02b", T7840, "Printer fixed by removal", "Uninstalling 26200.7840 fixed my printer. The update broke printing."),
    ("V-GK06b", T7840, "Bluetooth gone", "26200.7840 installed without any issues, but since the update Bluetooth is gone."),
    ("V-GK08b", T7840, "Printing broken", "The previous update, 26200.7840, broke printing after the update installed."),
    ("V-GK37", T7840, "Printer fails", "Problems from the 26200.7840 update: the printer fails after the update."),
    ("V-GK38", T7840, "Printer fails", "Since installing the update from Patch Tuesday (26200.7840) my printer fails."),
    ("V-A1", T7840, "Printer fails", "Since the 2026-02 update on 26200.7840 my printer fails."),
    ("V-A5", T7840, "Printer fails", "After the update from last week (build 26200.7840) my printer fails."),
    ("M-K01", T7840, "Printer fails", "After restoring my files, I updated to 26200.7840 and the printer fails."),
    ("M-K04", T7840, "Crashes", "26200.7840 keeps crashing after installing the update."),
    ("M-K05", T7840, "Crashes", "26200.7840 crashes when I open File Explorer since the update."),
    ("M-K06", T7840, "Issues", "Still having issues since installing 26200.7840: the printer fails."),
    ("M-K07", T7840, "BSOD", "I'm still getting BSODs since updating to 26200.7840."),
    ("M-K08", T7840, "Printer", "26200.7840 is still broken: the printer fails after the update."),
    ("M-K10", T7840, "Boot slow", "Since the update to 26200.7840, compared with before, boot is twice as slow."),
    ("M-K11", T7840, "Printer", "After the February update (26200.7840), my printer fails."),
    ("M-K16", T7840, "Install fails", "26200.7840 fails to install on my laptop with 0x800f0922."),
    ("M-K17", T7840, "Install fails", "26200.7840 can't install on our PCs, error 0x800f0922."),
    ("M-K20", T7840, "Printer", "Since 26200.7840 is installed, the printer fails."),
    ("M-K21", T7840, "Audio", "The 26200.7840 update restored my audio but broke printing."),
    ("M-K22", T7840, "Printer", "I uninstalled 26200.7840 and that fixed the printer after the update broke it."),
    ("M-K23", T7840, "Printer", "Removing 26200.7840 resolved the printer issue after the update."),
    ("M-K27", T7840, "Printer", "Updated to 26200.7840 last week with no issues, but now the printer fails after the update."),
    ("M-K30", T7840, "Printer", "Since the February 2026 update on 26200.7840 my printer fails."),
    ("M-K31", T7840, "Printer", "26200.7840 since the February update: my printer fails."),
    ("M-K32", T7840, "Printer", "Our PCs on 26200.7840 since the latest update cannot print."),
    ("M-K36", T7623, "Printer", "Since the January update on 26200.7623 my printer fails."),
    ("M-K37", T7840, "Printer", "After 26200.7840, the next morning my printer failed after the update."),
    # Entry pins: each is decided by one pattern alone, so deleting that pattern flips it (one fix per mutant).
    ("P-SRCFILLER", T7840, "Printer fails", "Since installing the update from Windows Update (26200.7840) my printer fails."),
    ("P-GAP", T7840, "Install fails", "26200.7840 failed to install and then I installed the March update manually."),
    ("P-XUPDATE", T7840, "Printer broken", "The 26200.7840 update broke my printer."),
    ("P-SINCEUPDATING", T7840, "Printer fails", "26200.7840 since updating: my printer fails after the update."),
]

REFUSE2 = [
    ("V-GR01", T7840, "Update keeps failing", "I'm still on 26200.7840 after the update failed to install with 0x800f0922."),
    ("V-GR02", T7840, "Update keeps failing", "The update failed and returned me to 26200.7840, now it fails again with 0x800f0922."),
    ("V-GR03", T7840, "Update keeps failing", "Windows reverted itself to 26200.7840 after the update failed with 0x800f0922."),
    ("V-GR04", T7840, "Printing broke", "I restored my system to 26200.7840 after the March update broke printing."),
    ("V-GR05", T7840, "Printing broke", "Updated to 26200.7840 with no issues; the March update broke printing."),
    ("V-GR06", T7840, "Printing broke", "26200.7840 caused no problems for me, but the March update broke printing."),
    ("V-GR07", T7840, "Update stuck at 0%", "My PC on 26200.7840 is stuck installing the March update at 0%."),
    ("V-GR09", T7840, "Update fails 0x800f0922", "26200.7840 fails to install 26200.7922 with 0x800f0922."),
    ("V-GR10", T7840, "Feature update fails", "Machines on 26200.7840 fail to upgrade to 26H2 with 0xC1900101."),
    ("V-GR11", T7840, "Update fails 0x800f0922", "Trying to update 26200.7840 PCs with the March cumulative update fails with 0x800f0922."),
    ("V-GR12", T7840, "Slow boot", "After the update, compared to 26200.7840, boot takes twice as long."),
    ("V-GR13", T7840, "Update fails 0x800f0922",
     "Since 26200.7840 is the current build on all our machines, the March update fails with 0x800f0922 on every one."),
    ("V-GR14", T7840, "Next update fails", "After 26200.7840, the next update fails to install with 0x800f0922."),
    ("V-GR15", T7840, "Rollback loop", "26200.7840 keeps rolling back the March update."),
    ("V-GR17", T7840, "Printing fails", "On 26200.7840 everything worked. After updating to 26200.7922, printing fails."),
    ("V-GR18", T7840, "Printing broke", "Our fleet moved off 26200.7840 last month; the new build breaks printing after the update."),
    ("V-GR19", T7840, "Update fails", "My laptop came with 26200.7840 preinstalled and the March update fails."),
    ("V-GR20", T7840, "Update fails", "I can't get past 26200.7840; every newer update fails with 0x800f0922."),
    ("V-GR21", T7840, "Printer fails", "26200.7840 was the last build that worked; since the update my printer fails."),
    ("V-GR22", T7840, "Update keeps failing", "Still on 26200.7840 since the March update keeps failing to install."),
    ("V-GR23", T7840, "Update rolled back", "My PC is stuck on 26200.7840 after the update rolled back twice."),
    ("V-GR24", T7840, "Update failed", "The update failed and System Restore took me to 26200.7840."),
    ("V-GR25", T7840, "Update fails nightly", "26200.7840 fails to update to 26200.7922 every night."),
    ("V-GR26", T7840, "Update stuck at 0%", "26200.7840 stuck at 0% downloading KB5079473 after the update check."),
    ("V-GR27", T7840, "Update fails 0x800f0922", "26200.7840 can't install 26200.8037, error 0x800f0922."),
    ("V-GR28", T7840, "Feature update fails", "Upgrade of 26200.7840 fails with 0xC1900101 when going to 26H2."),
    ("V-GR29", T7840, "Printing broke", "Installed 26200.7840 with zero problems. The March update broke printing."),
    ("V-GR30", T7840, "Update stuck", "26200.7840 freezes at 35% while installing the next cumulative update."),
    ("V-GR31", T7840, "Update rolled back", "Windows restored 26200.7840 after the update rolled back."),
    ("V-GR32", T7840, "Update keeps failing", "I remain on 26200.7840 since the update keeps failing with 0x800f0922."),
    ("V-GR33", T7840, "Update keeps failing", "Stuck on 26200.7840 after the update failed again with 0x800f0922."),
    ("V-GR34", T7840, "Update keeps failing", "We are still running 26200.7840 after the latest update failed to install."),
    ("V-GR35", T7840, "Printing broke", "26200.7840 went in with no problems; the March update broke printing."),
    ("M-R01", T7840, "Update fails", "I'm stuck at 26200.7840 because the March update fails."),
    ("M-R02", T7840, "Update fails", "Still running 26200.7840 since the update keeps failing."),
    ("M-R03", T7840, "Update fails", "We stayed on 26200.7840 after the update failed."),
    ("M-R04", T7840, "Printing broke", "I rolled my PC back to 26200.7840 after the March update broke printing."),
    ("M-R05", T7840, "Update fails", "The update rolled back and left me on 26200.7840 with error 0x800f0922."),
    ("M-R06", T7840, "Printing broke", "26200.7840 with no problems at all; the March update broke printing."),
    ("M-R07", T7840, "Printing broke", "26200.7840 never caused any issues; the next update broke printing."),
    ("M-R08", T7840, "Update stuck", "26200.7840 stuck downloading the next update."),
    ("M-R09", T7840, "Update fails", "26200.7840 refuses to install KB5079473 since the update check."),
    ("M-R10", T7840, "Feature update fails", "26200.7840 fails to upgrade to Windows 11 26H2."),
    ("M-R11", T7840, "Update fails", "Devices on 26200.7840 fail to update to the latest version."),
    ("M-R13", T7840, "Update fails", "26200.7840 is our production build and the March update fails on it."),
    ("M-R14", T7840, "Update fails", "After 26200.7840 the 2026-03 update fails to install."),
    ("M-R15", T7840, "Update rolled back", "I'm on 26200.7840 after the update was rolled back."),
    ("M-R16", T7840, "Update failed", "A restore point brought me back to 26200.7840 after the update failed."),
    ("M-R17", T7840, "Printing broke", "Updated to 26200.7840 without problems, but the March update broke printing."),
    ("M-R18", T7840, "Update fails", "26200.7840 PCs with the 2026-03 update fail to boot."),
    ("M-R19", T7840, "Update fails", "26200.7840 keeps reverting the March cumulative update."),
    ("M-R20", T7840, "Printing fails", "Since the March update on 26200.7840 printing fails."),
    ("M-R21", T7840, "Printer", "26200.7840 since the March update: printing fails."),
    ("M-R22", T7840, "Printing", "Successfully installed 26200.7840. The March update broke printing."),
    ("M-R23", T7840, "Printing", "Updated to 26200.7840 with no issues, but the 2026-03 update broke printing."),
    ("M-R24", T7840, "Printing", "26200.7840 installed without problems, but after the next update printing fails."),
    ("M-R25", T7840, "Printing", "26200.7840 installed without problems, but KB5079473 broke printing."),
    ("M-R26", T7840, "Printing", "26200.7840 installed without problems, but after upgrading to 26H2 printing fails."),
    ("M-R27", T7840, "Printing", "26200.7840 installed without problems, but since the update to 26200.7922 printing fails."),
    ("M-R30", T7840, "Printer", "Rolling back 26200.7840 fixed nothing; the March update broke printing."),
    ("M-R31", T7840, "Printer", "Uninstalling 26200.7840 did not fix it; printing fails since the update."),
    ("M-R32", T7840, "Printer", "The update failed to install (26200.7840 to 26200.7922) and printing fails."),
    # Entry pins (see KEEP2).
    ("P-LASTGOOD", T7840, "Printer", "I reinstalled the last working build 26200.7840 since the update broke printing."),
    ("P-HISTORY", T7840, "Printer fails", "Update history shows 26200.7840 installed, and since the update my printer fails."),
    ("P-SHOULDFIX", T7840, "Printer fails", "I'm installing 26200.7840 which should fix the printer bug. Printing fails since the update."),
    ("P-SAFE", T7840, "Printer fails", "Is it safe to install 26200.7840? My printer fails since the update."),
    ("P-WAITING", T7840, "Printer fails", "Waiting for the 26200.7840 update; printing fails since the update."),
    ("P-WUFAILS", T7840, "Update fails", "Windows Update keeps failing on 26200.7840 after the latest update."),
]

# The production construction (three leading title copies): a body whose first clause begins with the
# title keeps that clause, and a body that is only the build beside the title stays unlinked.
LIVE_KEEP = [
    ("TP1", T7840, "Printer not working after update", "Printer not working after update to 26200.7840. It worked before."),
    ("TP2", T7840, "Audio stopped after installing", "Audio stopped after installing 26200.7840 yesterday."),
    ("TP3", T7840, "Explorer crashes since updating", "Explorer crashes since updating to build 26200.7840, every launch."),
]
LIVE_REFUSE = [
    ("R33-live", T7840, "Explorer crashes after the update", "26200.7840 here, Pro edition, and it happens every boot."),
]

# Third round (v3, the bounded fix pass after the second independent verification). "M3-" cases are the
# implementer's own; the second verifier's probes are in FIX_V2.
T8246 = {"target_feature_version": "25H2", "target_kb": "KB5083769", "target_os_build": "26200.8246",
         "target_release_date": "2026-04-14", "update_version": "25H2"}
KEEP3 = [
    ("M3K01", T8246, "Printer broke", "Windows 11 25H2 build 26200.8246 broke my printer after the update."),
    ("M3K02", T8246, "Printer broke", "26200.8246, my printer broke after the update."),
    ("M3K03", T8246, "Printer fails", "On Windows 11 25H2 26200.8246 my printer fails since the update."),
    ("M3K04", T8246, "Printer fails", "26200.8246 was installed on my PC and since then the printer fails."),
    ("M3K06", T8246, "Printer fails", "After installing 26200.8246 my printer fails; it had no trouble before."),
    ("M3K07", T8246, "Printer fails", "Every boot on 26200.8246 the printer is gone after the update."),
    ("M3K08", T8246, "Printer fails", "My laptop took 26200.8246 overnight and printing fails after the update."),
    ("M3K09", T8246, "Printer fails", "Compared to 25H2 26200.8037, 26200.8246 prints three times slower after the update."),
    ("M3K10", T8246, "Wi-Fi broke", "Did 26200.8246 break Wi-Fi for anyone? Mine stopped after the update."),
    ("M3K11", T8246, "Wi-Fi broke", "Rolled back from 26200.8246 to 26200.8037 because Wi-Fi broke after the update."),
    ("M3K12", T8246, "Wi-Fi broke", "I went back from 26200.8246 because Wi-Fi broke after the update."),
    ("M3K13", T8246, "Wi-Fi broke", "The problems come from 26200.8246, Wi-Fi broke after the update."),
    ("M3K14", T8246, "Printer drops", "26200.8246 is a stable build mostly, but since installing it the printer drops."),
    ("M3K15", T8246, "Spooler crash", "All 26200.8246 PCs with the April update crash the spooler after the update."),
    ("M3K16", T8246, "Install loop", "26200.8246 keeps failing to install every time with 0x800f0922."),
    ("M3K17", T8246, "Install loop", "26200.8246 rolls back the second time it reaches 100% after the update."),
    ("M3K19", T8246, "Printer fails", "I'm on 26200.8246 now. After installing 26200.8246 the printer fails."),
    ("M3K20", T8246, "Explorer", "Explorer crashes  after updating 26200.8246 every time I open it."),
    # Root-fix pins: no link at all, so only the veto's own fix keeps each of these.
    ("M3K21", T8246, "Start menu", "26200.8246 makes the Start menu not open, with no errors in Event Viewer, since the update."),
    ("M3K22", T8246, "Mouse", "On 26200.8246 the mouse is jerky in games after the update, no trouble before."),
    ("M3K23", T8246, "Wi-Fi", "Did 26200.8246 make Wi-Fi drop for anyone, any fix? It started after the update."),
    ("M3K24", T8246, "Boot slow", "Compared to 24H2 26200.8246 boots slower since the update."),
    ("M3K25", T8246, "Boot slow", "Compared to Windows 11, 26200.8246 boots slower since the update."),
    ("M3K26", T8246, "Printer", "26200.8246 - Successfully installed on 4/16/2026 - but since then the printer fails."),
    ("M3K27", T8246, "Boot", "It will not boot since installing 26200.8246, error 0xc000021a after the update."),
    ("M3K28", T8246, "Wi-Fi", "Why does 26200.8246 drop Wi-Fi every hour, is there a fix? It began after the update."),
    ("M3K29", T8246, "Printing", "26200.8246 installed without problems, but since the April update printing fails."),
    ("M3K30", T8246, "Printer", "Moving from a 26200.8246 machine to a new one fixed printing, which failed since the update."),
    ("M3K31", T8246, "Wi-Fi", "Why did 26200.8246 break Wi-Fi and how do I fix it? It began after the update."),
    ("M3K32", T8246, "Wi-Fi", "Did 26200.8246 drop Wi-Fi, and did a rollback fix it? It started after the update."),
    ("M3K33", T8246, "Wi-Fi", "Does 26200.8246 drop Wi-Fi for everyone or is there a fix? It began after the update."),
    ("M3K34", T8246, "Wi-Fi", "Downgraded from 26200.8246 to 24H2 because Wi-Fi broke after the update."),
    ("M3K35", T7840, "Printer", "Since February update on 26200.7840 my printer fails."),
    ("P3-SINCEUPDATING", T8246, "Printer", "I'm on 26200.8246 since updating and the printer fails."),
]
REFUSE3 = [
    ("M3R01", T8246, "Printer fails", "I'm running Windows 11 Pro 25H2, build 26200.8246. Since the update the printer fails."),
    ("M3R02", T8246, "Printer fails", "Windows 11 25H2 build 26200.8246. Since the update the printer fails."),
    ("M3R03", T8246, "Printer fails", "Windows 11 Pro 25H2 (build 26200.8246), clean install. Since the update the printer fails."),
    ("M3R04", T8246, "Printer fails", "25H2 26200.8246 Printing stopped since the update."),
    ("M3R05", T8246, "Printer fails",
     "Edition Windows 11 Pro Version 25H2 Installed on 4/16/2026 OS build 26200.8246. Printing fails since the update."),
    ("M3R06", T8246, "Printer fails", "OS: Windows 11 Pro 25H2 26200.8246 Printing fails since the update."),
    ("M3R07", T8246, "Printer fails", "Successfully installed 26200.8246. The May update broke printing."),
    ("M3R08", T8246, "Printer fails", "26200.8246 fails to install the May update with 0x800f0922."),
    ("M3R09", T8246, "Printer fails", "Should I install 26200.8246? Printing fails since the May update."),
    ("M3R10", T8246, "Printer fails", "The 26200.8246 upgrade to 26H2 fails with 0xC1900101."),
    ("M3R11", T8246, "Printer fails", "Update history: 26200.8246 installed 4/16/2026. The May update broke printing."),
    # Entry pins for vetoes whose earlier pin became a declared residual (a link on the other side now keeps
    # it): each of these carries no link, so the one veto decides it.
    ("P3-LASTGOOD", T8246, "Printer", "I reinstalled the last working build 26200.8246 and printing fails since the update."),
    ("P3-SHOULDFIX", T8246, "Printer", "The new 26200.8246 build should fix the printer bug; printing fails since the update."),
    ("P3-TOFIX", T8246, "Printer", "I'm told to get 26200.8246 to fix the printer bug; printing fails since the update."),
    ("P3-WAITING", T8246, "Printer", "Still waiting for 26200.8246; printing fails since the update."),
    ("P3-INSTALLON", T8246, "Feature pack", "Installing the Media Feature Pack on 26200.8246 never completes since the update."),
    ("P3-CLEANINSTALL", T8246, "Printer", "I'm running a clean install Windows 11 Pro 25H2 26200.8246 and printing fails since the update."),
]


# The earlier refusal cases (REFUSE, REFUSE2, REFUSE3, LIVE_REFUSE) the narrow rule still refuses: every one
# is a pure stated state with no link word.
STILL_REFUSED = ("R1", "R2", "R4", "R7", "R9", "R10", "R11", "R13", "R16", "R27", "R34",
                 "M3R01", "M3R02", "M3R03", "M3R04", "M3R05", "M3R06")
# The rest are declared residual admissions (ledger AUX-076; section H). The authority on main admits every
# one of them too, so none is introduced here:
#   R1N-01 a mention of the build is not a stated state (no state marker before it): the former veto shapes
#          (upgrade source, rollback target, history line, hoped-for fix, platform for another update,
#          clean install) and every unlisted phrasing;
#   R1N-02 a stated state that the sentence continues in lower case, takes up again (", which ...", ", since
#          ...") or that follows a blocking word ("Since I'm on X", "updated to Windows 11 OS Build X");
#   R1N-03 every mention a stated state, but the body has a link word, which may tie the issue to another
#          update rather than to the build.
RESIDUAL = {
    **{name: "R1N-01" for name in (
        "R5", "R6", "R14", "R15", "R17", "R18", "R19", "R20", "R21", "R22", "R23", "R24", "R25", "R26", "R28", "R29",
        "R30", "R32", "R33", "R35", "N1", "N2", "N3", "N6", "N7", "N10", "N11", "N12", "V-GR01", "V-GR02", "V-GR03",
        "V-GR04", "V-GR05", "V-GR06", "V-GR07", "V-GR09", "V-GR10", "V-GR11", "V-GR12", "V-GR13", "V-GR14", "V-GR15",
        "V-GR17", "V-GR18", "V-GR19", "V-GR20", "V-GR21", "V-GR22", "V-GR23", "V-GR24", "V-GR25", "V-GR26", "V-GR27",
        "V-GR28", "V-GR29", "V-GR30", "V-GR31", "V-GR32", "V-GR33", "V-GR34", "V-GR35", "M-R01", "M-R02", "M-R03",
        "M-R04", "M-R05", "M-R06", "M-R07", "M-R08", "M-R09", "M-R10", "M-R11", "M-R13", "M-R14", "M-R16", "M-R17",
        "M-R18", "M-R19", "M-R20", "M-R21", "M-R22", "M-R23", "M-R24", "M-R25", "M-R26", "M-R27", "M-R30", "M-R31",
        "M-R32", "P-LASTGOOD", "P-HISTORY", "P-SHOULDFIX", "P-SAFE", "P-WAITING", "P-WUFAILS", "M3R07", "M3R08",
        "M3R09", "M3R10", "M3R11", "P3-LASTGOOD", "P3-SHOULDFIX", "P3-TOFIX", "P3-WAITING", "P3-INSTALLON",
        "P3-CLEANINSTALL", "R33-live")},
    **{name: "R1N-02" for name in ("R3", "R12", "N9", "M-R15")},
    "R8": "R1N-03",
}

# Witnesses, one per alternative of the narrow rule, so that deleting that alternative ALONE flips the case.
# Keep witnesses (each kept, and accepted with the rule off):
#   LINK   "Running Windows 11 Pro OS Build <B>. <s>. " + TAIL           a link word in a sentence of its own
#   TAKEN  "Running Windows 11 Pro OS Build <B>, <s>. " + TAIL           the build taken up after its comma
#   BLOCK  "<s> Windows 11 Pro OS Build <B>, the printer ... update."    a blocking word right before the run
# Refuse witnesses (each refused, and accepted with the rule off):
#   STATE  "<s> <B>. " + TAIL                                            a marker, label, identity word or run
#                                                                        character the stored shapes do not pin
W_LINK = [
    ("cause:caused", "Something caused the printer to drop"),
    ("cause:causes", "The update causes the outage"),
    ("cause:causing", "The update is causing the outage"),
    ("cause:the cause of", "Nobody knows the cause of the outage"),
    ("cause:due to", "The outage is due to the update"),
    ("cause:because of", "Printing stopped because of the update"),
    ("cause:thanks to", "Printing stopped thanks to the update"),
    ("cause:introduc", "The update introduced a spooler bug"),
    ("cause:trigger", "The update triggered a spooler crash"),
    ("cause:culprit", "The update is the culprit"),
    ("cause:responsib", "The update is responsible for the outage"),
    ("cause:blam", "I blame the update for the outage"),
    ("cause:fault", "The update is at fault here"),
    ("cause:regression", "It looks like a regression in the update"),
    ("blame:broke", "The update broke the printer"),
    ("blame:breaks", "The update breaks printing"),
    ("blame:breaking", "The update is breaking printing"),
    ("blame:broken", "Printing is broken"),
    ("blame:wreck", "The update wrecked printing"),
    ("blame:knock", "The update knocked the printer offline"),
    ("blame:kill", "The update killed printing"),
    ("blame:ruin", "The update ruined printing"),
    ("blame:messed", "The update messed up printing"),
    ("blame:brick", "The update bricked the print server"),
    ("blame:wiped", "The update wiped the printer settings"),
    ("blame:nuked", "The update nuked the printer driver"),
    ("blame:trashed", "The update trashed the printer driver"),
    ("blame:screwed", "The update screwed up printing"),
    ("brought:came with", "The bug came with the update"),
    ("brought:comes with", "The bug comes with the update"),
    ("brought:come with", "Such bugs come with the update"),
    ("brought:shipped with", "The bug shipped with the update"),
    ("brought:arrived with", "The bug arrived with the update"),
    ("brought:brought", "The update brought a spooler bug"),
    ("brought:made", "The update made printing fail"),
    ("brought:makes", "The update makes printing fail"),
    ("anaphor:this", "This build is bad"),
    ("anaphor:that", "That build is bad"),
    ("anaphor:these", "These builds are bad"),
    ("anaphor:those", "Those builds are bad"),
    ("anaphor:said", "Said build is bad"),
    ("anaphor:same", "The same build is bad on my laptop"),
    ("anaphor:version", "This version is bad"),
    ("anaphor:release", "This release is bad"),
    ("anaphor:update", "This update is bad"),
    ("anaphor:upgrade", "This upgrade is bad"),
    ("anaphor:patch", "This patch is bad"),
    ("anaphor:cu", "This CU is bad"),
    ("anaphor:lcu", "This LCU is bad"),
    ("anaphor:one", "This one is bad"),
    ("anaphor:the build", "The build is bad"),
    ("anaphor:the version", "The version is bad"),
    ("anaphor:the release", "The release is bad"),
    ("anaphor:itself", "Windows itself shows nothing"),
    ("it_changed:it", "It installed on Saturday"),
    ("it_changed:which", "The patch, which installed on Saturday, is bad"),
    ("it_changed:was", "It was installed on Saturday"),
    ("it_changed:got", "It got installed on Saturday"),
    ("it_changed:has been", "It has been installed for a week"),
    ("it_changed:had been", "It had been installed on Saturday"),
    ("it_changed:just", "It just installed on Saturday"),
    ("it_changed:finally", "It finally installed on Saturday"),
    ("it_changed:updated", "It updated on Saturday"),
    ("it_changed:upgraded", "It upgraded on Saturday"),
    ("it_changed:arrived", "It arrived on Saturday"),
    ("it_changed:landed", "It landed on Saturday"),
    ("it_changed:came", "It came on Saturday"),
    ("it_changed:downloaded", "It downloaded on Saturday"),
    ("it_changed:applied", "It applied on Saturday"),
    ("since_then:since then", "Since then the spooler crashes"),
    ("since_then:after that", "After that the spooler crashes"),
    ("since_then:following it", "Following it the spooler crashes"),
    ("since_then:with it", "With it the spooler crashes"),
    ("since_then:before that", "Before that the spooler worked"),
    ("since_then:until then", "Until then the spooler worked"),
    ("since_then:since$", "The spooler has crashed ever since"),
    ("since_installing:since installing", "Since installing, the spooler crashes"),
    ("since_installing:after updating", "After updating, the spooler crashes"),
    ("since_installing:following upgrading", "Following upgrading, the spooler crashes"),
    ("since_installing:when applying", "When applying patches the spooler crashes"),
    ("since_installing:once getting", "Once getting patches the spooler crashes"),
    ("since_installing:receiving", "Since receiving patches the spooler crashes"),
    ("since_installing:downloading", "Since downloading patches the spooler crashes"),
    ("removal:uninstall", "Uninstalling the patch stops the crashes"),
    ("removal:rolled back", "I rolled back and printing works"),
    ("removal:rolled it back", "I rolled it back and printing works"),
    ("removal:rolling back", "Rolling back lets me print"),
    ("removal:rolls back", "Windows rolls back and printing works"),
    ("removal:revert", "I reverted and printing works"),
    ("removal:reverting", "Reverting lets me print"),
    ("removal:reverts", "Windows reverts and printing works"),
    ("removal:downgrad", "I downgraded and printing works"),
    ("removal:removing it", "Removing it lets me print"),
    ("removal:remove", "I had to remove it to print"),
    ("removal:removed", "I removed it and printing works"),
    ("removal:removes", "Windows removes it and printing works"),
    ("removal:removing this", "Removing this lets me print"),
    ("removal:removing that", "Removing that lets me print"),
    ("removal:removing the update", "Removing the update lets me print"),
]
W_TAKEN = [
    ("pronoun:which", "which I put on last week"),
    ("pronoun:that", "that is what winver shows"),
    ("pronoun:it", "it shows that in winver"),
    ("pronoun:its", "its print queue is empty"),
    ("pronoun:it's", "it's what winver shows"),  # read by "it": the apostrophe is a word boundary
    ("pronoun:this", "this is what winver shows"),
    ("pronoun:who", "who knows how"),
    ("pronoun:and", "and it shows that in winver"),
    ("pronoun:but", "but it shows that in winver"),
    ("pronoun:so", "so it shows that in winver"),
    ("onset:since", "since the update the printer is offline"),
    ("onset:after", "after the update the printer is offline"),
    ("onset:following", "following the update the printer is offline"),
    ("onset:because", "because the update went in the printer is offline"),
    ("onset:with", "with the update the printer is offline"),
    ("onset:via", "via Windows Update, and the printer is offline"),
    ("onset:through", "through Windows Update, and the printer is offline"),
    ("onset:from", "from Windows Update, and the printer is offline"),
    ("onset:until", "until the update the printer was fine"),
    ("onset:when", "when the update went in the printer went offline"),
    ("onset:once", "once the update went in the printer went offline"),
    ("onset:ever", "ever since the update the printer is offline"),
    ("predicate:installed", "installed last week"),
    ("predicate:updated", "updated last week"),
    ("predicate:upgraded", "upgraded last week"),
    ("predicate:arrived", "arrived last week"),
    ("predicate:landed", "landed last week"),
    ("predicate:came", "came last week"),
    ("predicate:got", "got here last week"),
    ("predicate:downloaded", "downloaded last week"),
    ("predicate:rolled", "rolled out last week"),
    ("predicate:was", "was fine before the update"),
    ("predicate:is", "is the one on this PC"),
    ("predicate:has", "has the problem"),
    ("predicate:had", "had the problem"),
    ("predicate:keeps", "keeps dropping the printer"),
    ("predicate:kept", "kept dropping the printer"),
    ("predicate:just", "just like the other PC"),
    ("predicate:also", "also on the laptop"),
    ("predicate:then", "then the printer went offline"),
    ("predicate:now", "now the printer is offline"),
    ("predicate:still", "still shows the printer offline"),
    ("predicate:fail", "failing at printing"),
    ("predicate:crash", "crashing the spooler"),
    ("predicate:froze", "froze twice"),
    ("predicate:freez", "freezing twice"),
    ("predicate:hang", "hanging at boot"),
    ("predicate:stuck", "stuck at boot"),
]
W_BLOCK = [
    ("block:since", "Since"), ("block:after", "After"), ("block:following", "Following"), ("block:because", "Because"),
    ("block:when", "When"), ("block:once", "Once"), ("block:to", "Moved to"), ("block:onto", "Moved onto"),
    ("block:into", "Moved into"), ("block:from", "Coming from"), ("block:on", "On"), ("block:with", "With"),
    ("block:install", "Installed"), ("block:updat", "Updated"), ("block:upgrad", "Upgraded"), ("block:patch", "Patched"),
    ("block:download", "Downloaded"), ("block:got", "Got"), ("block:get", "We get"), ("block:getting", "Getting"),
    ("block:received", "Received"), ("block:the", "The"), ("block:this", "This"), ("block:that", "That"),
    ("block:latest", "The latest"), ("block:new", "The new"), ("block:newest", "The newest"),
    ("block:recent", "The recent"), ("block:current", "The current"),
]
W_STATE = [
    ("label:system", "System: Windows 11 Pro 25H2 build"),
    ("label:platform", "Platform: Windows 11 Pro 25H2 build"),
    ("label:configuration", "Configuration: Windows 11 Pro 25H2 build"),
    ("label:product", "Product: Windows 11 Pro 25H2 build"),
    ("label:version", "Version: Windows 11 Pro 25H2 build"),
    ("label:edition", "Edition: Windows 11 Pro 25H2 build"),
    ("running:i'm", "I'm on 25H2 build"),
    ("running:i’m", "I’m on 25H2 build"),
    ("running:we are", "We are using 25H2 build"),
    ("running:currently", "I am currently running 25H2 build"),
    ("running_windows:using", "Using Windows 11 Pro build"),
    ("opens:win", "Running Win 11 Pro build"),
    ("opens:win11", "Running Win11 Pro build"),
    ("word:home+single+language+x64", "Running Windows 11 Home Single Language 25H2 x64 build"),
    ("word:iot+enterprise+ltsc+ver", "Running Windows 11 IoT Enterprise LTSC ver 25H2 build"),
    ("word:education+n+arm64", "Running Windows 11 Education N arm64 build"),
    ("word:insider+beta+channel", "Running Windows 11 Insider Beta Channel build"),
    ("word:dev", "Running Windows 11 Insider Dev Channel build"),
    ("word:canary", "Running Windows 11 Insider Canary Channel build"),
    ("word:edition", "Running Windows 11 Pro Edition build"),
    ("word:for+workstations", "Running Windows 11 Pro for Workstations build"),
    ("word:edu", "Running Windows 11 Edu build"),
    ("word:v", "Running Windows 11 Pro v 25H2 build"),
    ("word:10", "Running Windows 10 build"),
    ("run:)", "Windows 11 (25H2) build"),
    ("run:[]", "Windows 11 [25H2] build"),
    ("run:/", "Windows 11 Pro / 25H2 / build"),
    ("run:-", "Windows 11 Pro - 25H2 - build"),
    ("run:–", "Windows 11 Pro – 25H2 – build"),
    ("run:—", "Windows 11 Pro — 25H2 — build"),
]
STATE_LINE = f"Running Windows 11 Pro OS Build {B}"


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Windows acceptance: identity_not_linked_to_issue (AUX-076, the narrow rule)")
    print("=" * 78)

    # ---------------------------------------------------------------- A. scope guards and placement
    s1_title, s1_body = "Explorer crashes", "KB5077181 installed. Running Windows 11 Pro OS Build 26200.7840. Since the update File Explorer crashes."
    s1_text = " ".join([s1_title, s1_title, s1_body])
    check("A1 S1: a KB match with the build only in a running/spec line is kept, and the rule itself declines it",
          reason_of(T7840, s1_title, s1_body) is None
          and mw.identity_not_linked_to_issue(s1_text, s1_title, "KB5077181", "26200.7840", "KB5077181") is False
          and mw.identity_not_linked_to_issue(s1_text, s1_title, "", "26200.7840", "KB5077181") is True)
    s2_title = "26200.7840 printing stopped"
    s2_body = "Running OS Build 26200.7840. Printing stopped after the update."
    s2_text = " ".join([s2_title, s2_title, s2_body])
    check("A2 S2: a title naming the target build is kept, and the rule itself declines it",
          reason_of(T7840, s2_title, s2_body) is None
          and mw.identity_not_linked_to_issue(s2_text, s2_title, "", "26200.7840", "KB5077181") is False
          and mw.identity_not_linked_to_issue(" ".join(["Printing stopped", "Printing stopped", s2_body]), "Printing stopped", "",
                                              "26200.7840", "KB5077181") is True)
    check("A3 S3: a title naming the target KB is kept through the authority",
          reason_of(T7840, "KB5077181 stops printing", "Running OS Build 26200.7840. Printing stopped after the update.") is None)
    a4_title = "KB5077181 stops printing"
    a4_text = " ".join([a4_title, a4_title, "Running OS Build 26200.7840. Printing stopped after the update."])
    check("A4 the target KB in the title protects a build-only identity on its own (called with matched_kb empty)",
          mw.identity_not_linked_to_issue(a4_text, a4_title, "", "26200.7840", "KB5077181") is False
          and mw.identity_not_linked_to_issue(a4_text, "Printing stopped", "", "26200.7840", "KB5077181") is True)
    # Retained-text shape: the build was matched on the full post, the stored excerpt no longer shows it.
    a5_title = "Printer offline after update"
    a5_text = " ".join([a5_title, a5_title, "Printing stopped after the update. The printer shows offline."])
    a5 = mw.windows_learn_qna_reason(T7840, URL, "2026-11-01", a5_text, a5_title, "", "26200.7840", "25H2")
    check("A5 a build that is not in the body is never refused (no occurrence, no role, no decision)",
          a5 is None and mw.identity_link_details(a5_text, a5_title, "26200.7840") == []
          and mw.identity_not_linked_to_issue(a5_text, a5_title, "", "26200.7840", "KB5077181") is False, str(a5))
    a6_title, a6_body = "Printer offline", "KB5077181 installed. I'm on 25H2. Printing fails since the update."
    check("A6 an empty matched build is never refused: a KB + train identity counts as before",
          reason_of(T7840, a6_title, a6_body) is None
          and mw.identity_not_linked_to_issue(" ".join([a6_title, a6_body]), a6_title, "", "", "KB5077181") is False)
    a7_title = "Win11 26H2 (KB5121794) boot BSOD after update"
    a7_body = "Win11 Home 25H2 26200.9711 (current). Issue on 26H2 / KB5121794. Removing KB5121794 cleared the BSOD."
    a7_text = " ".join([a7_title, a7_title, a7_body])
    check("A7 an AUX-067 row keeps identity_not_the_subject, although this rule alone would refuse it too",
          reason_of(T25, a7_title, a7_body) == "identity_not_the_subject"
          and mw.identity_not_linked_to_issue(a7_text, a7_title, "", "26200.9711", "KB5127648") is True,
          str(reason_of(T25, a7_title, a7_body)))
    a8_title, a8_body = "My PC crashes randomly", "My PC crashes randomly. OS Build 26200.7840."
    a8_text = " ".join([a8_title, a8_title, a8_body])
    check("A8 a system-spec rejection keeps build_only_in_system_specs, although this rule alone would refuse it",
          reason_of(T7840, a8_title, a8_body) == "build_only_in_system_specs"
          and mw.identity_not_linked_to_issue(a8_text, a8_title, "", "26200.7840", "KB5077181") is True,
          str(reason_of(T7840, a8_title, a8_body)))
    a9_title, a9_body = "Explorer crashes", "I'm running 26200.7840. Explorer crashes randomly every morning."
    a9_text = " ".join([a9_title, a9_title, a9_body])
    check("A9 an unattributed report keeps missing_update_attribution, although this rule alone would refuse it",
          reason_of(T7840, a9_title, a9_body) == "missing_update_attribution"
          and mw.identity_not_linked_to_issue(a9_text, a9_title, "", "26200.7840", "KB5077181") is True,
          str(reason_of(T7840, a9_title, a9_body)))
    check("A10 the spam/meta rejection still answers first",
          reason_of(T7840, "Very strange Windows 11 MCT .ISO",
                    "This thread was rejected by the system as spam. I'm on 26200.7840. The update fails.") == "meta_or_spam_report")
    src = (_SCRIPTS / "patch_collectors" / "microsoft_windows.py").read_text(encoding="utf-8")
    body = src.split("def windows_learn_qna_reason(", 1)[1].split("def row_from_candidate(", 1)[0]
    intent_at = body.find("reason = windows_intent_reason(report_text")
    subject_at = body.find("    if identity_not_the_subject(target, report_title, matched_kb, matched_os_build):")
    rule_at = body.find("    if identity_not_linked_to_issue(report_text, report_title, matched_kb, matched_os_build,")
    ret_at = body.find('        return "identity_not_linked_to_issue"')
    check("A11 placement: the rule is the last statement before `return None`, after the intent filter and after identity_not_the_subject",
          0 <= intent_at < subject_at < rule_at < ret_at and body.count("identity_not_linked_to_issue(") == 1
          and body[ret_at:].split("\n", 2)[1].strip() == "return None",
          f"intent {intent_at}, subject {subject_at}, rule {rule_at}, return {ret_at}")
    intent_src = src.split("def windows_intent_reason(", 1)[1].split("def identity_basis(", 1)[0]
    check("A12 the rule is not consulted by the intent filter (no existing reason can be relabelled)",
          "identity_not_linked_to_issue" not in intent_src and "identity_link" not in intent_src)
    check("A13 the rule reads no month: the same post is decided alike for any release date",
          len({mw.identity_not_linked_to_issue(" ".join(["x", "x", f"Running Windows 11 Pro OS Build {B}. {TAIL}"]), "x", "", B,
                                               "KB5077181", d) for d in ("", "2026-02-10", "2026-07-14T00:00:00Z")}) == 1
          and mw.identity_link_details(f"x x OS: {B}.", "x", B, "2026-02-10") == mw.identity_link_details(f"x x OS: {B}.", "x", B))

    # ---------------------------------------------------------------- B. preservation
    for name, target, title, body_text in KEEP + KEEP2 + KEEP3:
        got, off = both(target, title, body_text)
        check(f"B {name}: kept, as the authority without the rule keeps it -- {body_text[:60]}",
              got is None and off is None, f"{got} / off {off} {roles(target, title, body_text)}")
    for name, target, title, body_text in LIVE_KEEP:
        got, off = both(target, title, body_text, live=True)
        check(f"B {name}: kept under the production construction (the body's own first clause starts with the title)",
              got is None and off is None, f"{got} / off {off}")
    fixture = json.loads(FIX.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    keeps = [c for c in cases if c["kind"] == "keep"]
    refusals = [c for c in cases if c["kind"] == "refuse"]
    check("B0 the corpus-shape fixture holds 10 kept and 14 refused synthetic cases, each naming one original",
          len(keeps) == 10 and len(refusals) == 14 and len(cases) == 24
          and len({tuple(c["original"]) for c in cases}) == 24)
    for c in keeps:
        got, off, det, lw = case_decision(c)
        check(f"B {c['case']} corpus shape {c['original'][1]} q{c['original'][2]}: kept with the original's roles {c['expected_roles']}",
              got is None and off is None and c["expected_reason"] is None and det == c["expected_roles"]
              and lw == c["expected_link_words"] and not all(r == "environment" for r, _k in det), f"{got} {det} {lw}")
    v2 = json.loads(FIX_V2.read_text(encoding="utf-8"))["cases"]
    v2_keep = [c for c in v2 if c["kind"] == "keep"]
    v2_refuse = [c for c in v2 if c["kind"] == "refuse"]
    check("B00 the second verifier's fixture holds its 53 probes (27 keep, 26 refuse), each named once, every keep expected kept",
          len(v2) == 53 and len(v2_keep) == 27 and len(v2_refuse) == 26 and len({c["case"] for c in v2}) == 53
          and all(c["expected"] == "kept" for c in v2_keep))
    for c in v2_keep:
        got, off = both(c["target"], c["title"], c["body"], live="row")
        check(f"B {c['case']} (second verifier): kept, as the authority without the rule keeps it -- {c['body'][:60]}",
              got is None and off is None, f"{got} / off {off}")
    v3 = json.loads(FIX_V3.read_text(encoding="utf-8"))["cases"]
    v3_keep = [c for c in v3 if c["kind"] == "keep"]
    v3_refuse = [c for c in v3 if c["kind"] == "refuse"]
    check("B000 the third verifier's fixture holds its 77 fresh probes (42 keep, 35 refuse), each named once; every keep the "
          "authority without the rule counts is expected kept, and the one it does not (V3-K37) keeps that earlier reason",
          len(v3) == 77 and len(v3_keep) == 42 and len(v3_refuse) == 35 and len({c["case"] for c in v3}) == 77
          and all(c["expected"] == "kept" for c in v3_keep if c["case"] != "V3-K37")
          and [c["expected"] for c in v3_keep if c["case"] == "V3-K37"] == ["missing_update_attribution"])
    for c in v3_keep:
        got, off = both(c["target"], c["title"], c["body"], live="row")
        want = None if c["expected"] == "kept" else c["expected"]
        check(f"B {c['case']} (third verifier): {c['expected']}, as the authority without the rule decides -- {c['body'][:60]}",
              got == want and off == want, f"{got} / off {off} {c['note']}")

    # ---------------------------------------------------------------- C. negatives
    earlier = {name: (target, title, body_text, live) for live, rows in ((False, REFUSE + REFUSE2 + REFUSE3), (True, LIVE_REFUSE))
               for name, target, title, body_text in rows}
    check("C0 every earlier refusal case is either still refused or a declared residual, never both, and the lists name no "
          "unknown case", set(STILL_REFUSED) | set(RESIDUAL) == set(earlier) and not set(STILL_REFUSED) & set(RESIDUAL)
          and len(earlier) == len(REFUSE) + len(REFUSE2) + len(REFUSE3) + len(LIVE_REFUSE))
    for name in STILL_REFUSED:
        target, title, body_text, live = earlier[name]
        got, off = both(target, title, body_text, live=live)
        check(f"C {name}: refused by this rule, and accepted with the rule off -- {body_text[:60]}",
              got == REASON and off is None, f"{got} / off {off} {roles(target, title, body_text)}")
    for c in refusals:
        got, off, det, lw = case_decision(c)
        tag = " [declared limit L1]" if c["declared_limit_l4"] else ""
        check(f"C {c['case']} corpus shape {c['original'][1]} q{c['original'][2]}: refused, accepted with the rule off, every "
              f"mention a stated state, no link word{tag}",
              got == REASON and off is None and c["expected_reason"] == REASON and det == c["expected_roles"]
              and det and all(r == "environment" for r, _k in det) and lw == [] == c["expected_link_words"],
              f"{got} / off {off} {det} {lw}")
    for c in v3_refuse:
        if c["expected"] != "refused":
            continue  # an earlier reason (as on main) or section H
        got, off = both(c["target"], c["title"], c["body"], live="row")
        check(f"C {c['case']} (third verifier): refused by this rule, and accepted with the rule off -- {c['body'][:60]}",
              got == REASON and off is None, f"{got} / off {off}")
    n4 = reason_of(T7840, "Teams crashes on launch", "After installing the new Teams update on 26200.7840, Teams crashes on launch.")
    check("C N4: the foreign-product veto still answers first for another product's update", n4 == "foreign_product_subject_not_windows_patch", str(n4))
    for wid, part in W_STATE:
        body_text = f"{part} {B}. {TAIL}"
        got, off = both(T7840, "Printer offline", body_text)
        check(f"C state[{wid}]: a stated state is refused, and accepted with the rule off -- {body_text[:60]}",
              got == REASON and off is None and only(T7840, "Printer offline", body_text) == ("environment", ""),
              f"{got} / off {off} {roles(T7840, 'Printer offline', body_text)}")
    base_body = f"{STATE_LINE}. {TAIL}"
    check("C control: the witness base (a stated state and a generic cue) is refused, and accepted with the rule off",
          both(T7840, "Printer offline", base_body) == (REASON, None) and words("Printer offline", base_body) == [])
    check("C end: the build's sentence may close, or go on with a comma, a parenthesis or a capitalised word",
          all(both(T7840, "Printer offline", f"{STATE_LINE}{tail} {TAIL}") == (REASON, None)
              for tail in (".", ", Windows Feature Experience Pack.", " (clean install).", " Experience Pack.")))
    check("C split: a semicolon, a question mark, an exclamation mark and a line break each end the build's sentence",
          all(both(T7840, "Printer offline", f"{STATE_LINE}{sep} the printer shows offline since the update.") == (REASON, None)
              for sep in (";", "?", "!", NEWLINE)))

    # ---------------------------------------------------------------- D. mechanics: one witness per alternative
    for wid, part in W_LINK:
        body_text = f"{STATE_LINE}. {part}. {TAIL}"
        got, off = both(T7840, "Printer offline", body_text)
        check(f"D link[{wid}]: a link word anywhere in the body keeps the stated state -- {part}",
              got is None and off is None and only(T7840, "Printer offline", body_text) == ("environment", "")
              and len(words("Printer offline", body_text)) == 1, f"{got} / off {off} {words('Printer offline', body_text)}")
    for wid, part in W_TAKEN:
        body_text = f"{STATE_LINE}, {part}. {TAIL}"
        got, off = both(T7840, "Printer offline", body_text)
        check(f"D taken[{wid}]: the build taken up after its comma keeps the row -- {part}",
              got is None and off is None and only(T7840, "Printer offline", body_text) == ("linked", "taken_up:" + wid.split(":")[0])
              and words("Printer offline", body_text) == [], f"{got} / off {off} {roles(T7840, 'Printer offline', body_text)}")
    for wid, part in W_BLOCK:
        body_text = f"{part} Windows 11 Pro OS Build {B}, the printer shows offline since the update."
        got, off = both(T7840, "Printer offline", body_text)
        check(f"D block[{wid}]: a blocking word right before the state keeps the row -- {part} Windows 11 Pro OS Build X",
              got is None and off is None and (only(T7840, "Printer offline", body_text) or ("", ""))[0] == "linked"
              and (only(T7840, "Printer offline", body_text) or ("", ""))[1].startswith("blocked:")
              and words("Printer offline", body_text) == [], f"{got} / off {off} {roles(T7840, 'Printer offline', body_text)}")
    for tail in (", [installed last week]", "), which I put on last week", " (installed last week)"):
        pre = "Windows 11 Pro (OS Build" if tail.startswith(")") else "Running Windows 11 Pro OS Build"
        body_text = f"{pre} {B}{tail}. {TAIL}"
        got, off = both(T7840, "Printer offline", body_text)
        check(f"D taken[skip {tail.strip()[:2]}]: punctuation before the take-up word is skipped -- {body_text[:60]}",
              got is None and off is None and (only(T7840, "Printer offline", body_text) or ("", ""))[0] == "linked",
              f"{got} / off {off} {roles(T7840, 'Printer offline', body_text)}")
    d1 = f"I'm on {B} and since the update the printer shows offline."
    check("D1 a stated state that the sentence continues in lower case is linked ('continued') and kept",
          only(T7840, "Printer offline", d1) == ("linked", "continued") and both(T7840, "Printer offline", d1) == (None, None))
    d2 = f"{STATE_LINE}. Since {B} the printer shows offline after the update."
    check("D2 refusal needs EVERY occurrence to be a stated state: a second mention that is not one keeps the row",
          [r for r, _k in roles(T7840, "Printer offline", d2)] == ["environment", "unlinked"]
          and both(T7840, "Printer offline", d2) == (None, None)
          and both(T7840, "Printer offline", f"{STATE_LINE}. OS: {B}. {TAIL}") == (REASON, None))
    d3 = "Running 25H2 build 26200.7840 for two days, the printer shows offline. It started after the update."
    check("D3 a bare 'running' / 'using' marks a state only before Windows: 'running 25H2 build X' is not a stated state",
          only(T7840, "Printer offline", "After two days of running 25H2 build 26200.7840, the printer shows offline.") == ("unlinked", "")
          and both(T7840, "Printer offline",
                   "After two days of running 25H2 build 26200.7840, the printer shows offline. It started after the update.")
          == (None, None) and roles(T7840, "Printer offline", d3) == [("unlinked", "")])
    check("D4 the identity run holds no update noun, no determiner, no date and no other build: each breaks the state",
          all(only(T7840, "Printer offline", f"{lead} {B}. {TAIL}") == ("unlinked", "") for lead in (
              "Running Windows 11 update", "I'm on the", "Running Windows 11 Pro 5/14/2026", "I'm on 26200.7623,"))
          and all(both(T7840, "Printer offline", f"{lead} {B}. {TAIL}") == (None, None) for lead in (
              "Running Windows 11 update", "I'm on the", "Running Windows 11 Pro 5/14/2026", "I'm on 26200.7623,")))
    check("D5 the Settings copy without its 'OS build' label is not a stated state ('Installed on <date> X', third verifier W1)",
          both(T7840, "Printer offline", f"Edition Windows 11 Pro Installed on 5/14/2026 {B} Experience Pack 1000. {TAIL}")
          == (None, None))
    check("D6 an identity line must OPEN the sentence: an identity run after other words is not a stated state",
          only(T7840, "Printer offline", f"My laptop Windows 11 25H2 build {B}. {TAIL}") == ("unlinked", "")
          and both(T7840, "Printer offline", f"My laptop Windows 11 25H2 build {B}. {TAIL}") == (None, None))
    d7 = f"Windows 11 25H2 (build {B}; since the update the printer shows offline)."
    check("D7 a short parenthetical is one unit: its semicolon does not end the build's sentence, so the take-up inside counts",
          only(T7840, "Printer offline", d7) == ("linked", "continued") and both(T7840, "Printer offline", d7) == (None, None))
    check("D8 a build token's own dot never ends a sentence: one mention is one occurrence, read whole",
          [r for r, _k, s in mw.identity_link_details(f"x x OS: {B}. {TAIL}", "x", B)] == ["environment"])
    t_live, b_live = "Printer broken", f"{STATE_LINE}. {TAIL}"
    check("D9 title copies: the three leading copies the collectors add are removed, so a link word in the TITLE is not read",
          reason_live(T7840, t_live, b_live) == REASON and both(T7840, t_live, b_live) == (REASON, None)
          and words(t_live, b_live) == [])
    check("D10 ... but a fourth copy is the post's own first clause and is read",
          reason_live(T7840, t_live, f"Printer broken. {b_live}") is None)
    check("D11 ... and only whole-word copies: a title that is the start of the first word does not cut it",
          both(T7840, "Win", f"Windows 11 25H2 build {B}. {TAIL}") == (REASON, None)
          and mw._r1_strip_title(f"Win Win Windows 11 25H2 build {B}.", "Win") == f"Windows 11 25H2 build {B}.")
    q_title = "Printer &amp; scanner  broken"
    check("D12 the title is matched as stored AND after clean_html, so the cleaned copy inside report_text is removed too",
          both(T7840, q_title, b_live, live="row") == (REASON, None)
          and mw._r1_strip_title(" ".join([q_title, q_title, mw.learn_qna.clean_html(q_title + " " + b_live)]), q_title) == b_live)
    check("D13 the link words are read on the body without the title copies, and anywhere in it (another sentence too)",
          mw.identity_link_words(" ".join([t_live, t_live, b_live]), t_live) == []
          and [n for n, _w in mw.identity_link_words(f"x x {b_live} Since then it drops.", "x")] == ["since_then"])
    d15 = f"{STATE_LINE}. The printer has been offline after the update ever since"
    check("D15 'since' that closes the post (no punctuation after it) is a link word too",
          both(T7840, "Printer offline", d15) == (None, None) and words("Printer offline", d15) == ["since_then"]
          and both(T7840, "Printer offline", f"{STATE_LINE}. The printer has been offline after the update.") == (REASON, None))
    check("D14 each mention's role is exactly one of environment, linked or unlinked, and a linked role names why",
          {r for r, _k in roles(T7840, "x", f"{STATE_LINE}. Since {B} it fails. Since I'm on {B}, it fails. {STATE_LINE}, which hurts.")}
          == {"environment", "unlinked", "linked"}
          and {k for _r, k in roles(T7840, "x", f"Since I'm on {B}, it fails. {STATE_LINE}, which hurts. I'm on {B} and so on.")}
          == {"blocked:since", "taken_up:pronoun", "continued"})

    # ---------------------------------------------------------------- E. declared limits (pinned, not closed)
    check("E1 [limit L1] a generic 'after today's update' beside a build stated only as the current state is refused (owner decision, default refuse)",
          both(T9711, "Defender offline scan boots into recovery",
               "26H2 26300.9711 Never seen this before. After todays update I ran a Defender Offline scan and it booted into recovery.")
          == (REASON, None))
    check("E2 [limit L2] the link words are a closed English list: a link to the build phrased outside it, in a sentence of its "
          "own after a stated state, is not read and the post is refused",
          both(T7840, "Wi-Fi drops", f"{STATE_LINE}. Wi-Fi drops every hour from the moment it went on, after the update.")
          == (REASON, None))
    check("E3 [limit L3] punctuation stands in for attachment: 'I'm on X and since the update ...' is kept (continued), while "
          "'I'm on X, and since the update ...' is refused (the comma closes the state)",
          both(T7840, "Explorer crashes on launch", "I'm on 26200.7840 and since the update File Explorer crashes on launch.")
          == (None, None)
          and both(T7840, "Explorer crashes on launch", "I'm on 26200.7840, and since the update File Explorer crashes on launch.")
          == (REASON, None))
    check("E4 [limit L4] non-English link words are not read: 'OS: X. Seit diesem Build ...' is refused like any stated state",
          both(T7840, "Drucker offline", "OS: 26200.7840. Seit diesem Build ist der Drucker offline, since the update.")
          == (REASON, None))
    check("E5 [limit L5] a state label the rule does not list ('Build now: X') fails open: kept",
          both(T7840, "Bluetooth gone", "Bluetooth vanished from Device Manager. This happened after the update. Build now: 26200.7840")
          == (None, None))
    e6_title = "Update fails 0x800f0922"
    e6_body = "Hotfix list: KB5077181 KB5050021. OS Build 26200.7840. The update fails with 0x800f0922."
    check("E6 [limit L6] a KB match is out of scope even when the KB sits only in a hotfix list",
          reason_of(T7840, e6_title, e6_body) is None)

    # ---------------------------------------------------------------- F. one authority, and the reason's consumers
    rec = PatchRecord(WINDOWS_PRODUCT_ID, "25H2", Path("synthetic-25h2.md"), "2026-02-10T00:00:00Z", "current", "Windows 11", "26200.7840")

    def cand(source_type: str, url: str, title: str, text: str) -> dict:
        return {"source_type": source_type, "source_name": source_type, "source_url": url, "parent_title": title,
                "report_title": title, "report_text": text, "source_date": "2026-02-20"}
    unlinked = "I'm on 26200.7840. Since the update File Explorer crashes on launch."
    linked = "After installing 26200.7840 File Explorer crashes on launch."
    learn = [cand("microsoft_learn_qna", "https://learn.microsoft.com/en-us/answers/questions/7000001/a", "Explorer crashes", unlinked),
             cand("microsoft_learn_qna", "https://learn.microsoft.com/en-us/answers/questions/7000002/b", "Explorer crashes", linked)]
    tc = mw.TechCommunityPool(candidates=[
        cand(mw.TECHCOMMUNITY_SOURCE_TYPE, "https://techcommunity.microsoft.com/discussions/windows11/explorer/7000003", "Explorer crashes", unlinked),
        cand(mw.TECHCOMMUNITY_SOURCE_TYPE, "https://techcommunity.microsoft.com/discussions/windows11/explorer2/7000004", "Explorer crashes", linked)],
        telemetry={}, errors=[])
    ef_pool = mw.ElevenForumPool(candidates=[
        cand(mw.ELEVENFORUM_SOURCE_TYPE, "https://www.elevenforum.com/t/explorer.7000005", "Explorer crashes", unlinked),
        cand(mw.ELEVENFORUM_SOURCE_TYPE, "https://www.elevenforum.com/t/explorer2.7000006", "Explorer crashes", linked)],
        telemetry={}, errors=[], unparseable=[])
    saved = (mw.learn_qna.collect_learn_qna_candidates, mw.record_target)
    try:
        mw.learn_qna.collect_learn_qna_candidates = lambda **_k: list(learn)
        mw.record_target = lambda _r: dict(T7840)
        accepted, rejected, health = mw.collect_for_record(rec, object(), {}, tc, ef_pool)
    finally:
        mw.learn_qna.collect_learn_qna_candidates, mw.record_target = saved
    by_type_rej = {r["source_type"]: r for r in rejected}
    by_type_acc = {r["source_type"]: r for r in accepted}
    types = {"microsoft_learn_qna", mw.TECHCOMMUNITY_SOURCE_TYPE, mw.ELEVENFORUM_SOURCE_TYPE}
    check("F1 one authority for every discovery method: the same unlinked report is refused by Learn, Tech Community AND the Windows 11 Forum",
          set(by_type_rej) == types and all(r["exclusion_reason"] == REASON for r in rejected) and len(rejected) == 3,
          str([(r["source_type"], r["exclusion_reason"]) for r in rejected]))
    check("F2 ... and the linked twin is accepted by each of the three, on the record's build",
          set(by_type_acc) == types and len(accepted) == 3 and all(r["target_build"] == "26200.7840" for r in accepted)
          and len(health) == 3)
    row = by_type_rej.get("microsoft_learn_qna", {})
    check("F3 the refused row is stored uncounted with the reason, no target_build, and its matched build kept for diagnosis",
          row.get("counted") is False and row.get("evidence_valid_for_current_patch") is False
          and row.get("exclusion_reason") == REASON and row.get("target_build") == ""
          and row.get("matched_os_build") == "26200.7840" and not row.get("matched_kb"))
    calls = [m.start() for m in re.finditer(r"windows_learn_qna_reason\(", src)]
    rfc = src.split("def row_from_candidate(", 1)[1].split("\ndef ", 1)[0]
    check("F4 windows_learn_qna_reason is called in exactly one place, row_from_candidate, and row_from_candidate only by evaluate_candidates",
          len(calls) == 2 and "windows_learn_qna_reason(target, str(candidate.get(\"source_url\")" in rfc
          and len(re.findall(r"(?<!def )row_from_candidate\(record, target", src)) == 1
          and "row = row_from_candidate(record, target, {**candidate" in src.split("def evaluate_candidates(", 1)[1].split("\ndef ", 1)[0])
    outside = []
    for path in sorted(_SCRIPTS.rglob("*.py")):
        if "tests" in path.relative_to(_SCRIPTS).parts or path.name in ("microsoft_windows.py", "diagnose_windows_link_roles.py"):
            continue
        if "windows_learn_qna_reason(" in path.read_text(encoding="utf-8", errors="replace"):
            outside.append(str(path.relative_to(_SCRIPTS)))
    check("F5 no production module outside the collector calls the Windows reason function directly (only the read-only diagnostic)",
          outside == [], str(outside))
    base_row = {"product_id": WINDOWS_PRODUCT_ID, "update_version": "25H2", "id": "w-1", "source_url": "https://x/1",
                "counted": True, "patch_version_matched": True, "target_build": "26200.7840"}
    withdrawn = {**base_row, "counted": False, "exclusion_reason": REASON, "evidence_valid_for_current_patch": False}
    check("F6 the evidence-loss guard reads a counted row withdrawn with this reason as an AUDITED withdrawal",
          el.find_unexplained_losses([base_row], [withdrawn]) == []
          and el.find_unexplained_losses([base_row], [{**withdrawn, "exclusion_reason": ""}]) != [])
    check("F7 the count predicate does not count a refused row and does not crash on its empty build",
          rc.counted_evidence_rows([row, withdrawn], windows_targets={}) == {})
    check("F8 the reason is never promotable to a lower evidence tier (it is a role refusal, not a missing identity)",
          REASON not in t2.PROMOTABLE_REJECTIONS
          and t2.tier2_row_from_rejection({**row, "tier2_full_text": unlinked}, windows=[], captured_at="2026-11-05T00:00:00Z") is None)
    check("F9 method-health telemetry counts the reason by name",
          mw.rejection_counts(rejected).get(REASON) == 3
          and f"{REASON}=1" in mw.build_notes(T7840, learn, [by_type_acc.get("microsoft_learn_qna", {})], [row], [],
                                              ["KB5077181", "26200.7840"]))

    # ---------------------------------------------------------------- G. the pinned refusal manifest
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = man["entries"]
    five = [tuple(e[f] for f in man["selector"]) for e in entries]
    check("G1 the manifest pins 14 distinct five-field identities, all Windows, all refused for this reason, with its provenance",
          len(entries) == 14 and len(set(five)) == 14 and man["selector"] == ["product_id", "update_version", "target_build", "id", "source_url"]
          and all(e["product_id"] == WINDOWS_PRODUCT_ID and e["reason_with_rule"] == REASON and e["reason_parent"] is None for e in entries)
          and man["exclusion_reason"] == REASON and len(man["parent_commit"]) == 40
          and all(len(man[k]) == 64 for k in ("authority_sha256_parent", "authority_sha256", "store_sha256"))
          and man["replay"]["changed"] == 14 and man["replay"]["changed_to_another_reason"] == 0)
    check("G2 every pinned row is build-only on its own record's build, with a block hash",
          all(e["matched_kb"] == "" and e["matched_os_build"] == e["target_build"] == e["target_os_build"]
              and len(e["block_sha256"]) == 64 and f"/questions/{e['question_id']}/" in e["source_url"] for e in entries))
    pinned = {(e["update_version"], e["target_build"], e["question_id"]): e for e in entries}
    check("G3 the 14 refused corpus shapes are exactly the 14 pinned rows, one to one",
          {tuple(c["original"]) for c in refusals} == set(pinned))
    check("G4 the declared-limit L4 flags agree between the manifest and the fixture (4 generic-cue rows)",
          all(pinned[tuple(c["original"])]["declared_limit_l4"] == c["declared_limit_l4"] for c in refusals)
          and sum(e["declared_limit_l4"] for e in entries) == 4)
    check("G5 the pinned roles are the fixture's roles: no stored refusal was paraphrased into a different role",
          all(pinned[tuple(c["original"])]["occurrence_roles"] == c["expected_roles"] for c in refusals))
    check("G6 the manifest's authority hash is a 64-hex digest distinct from its parent's, and its store hash is the replayed store",
          re.fullmatch(r"[0-9a-f]{64}", man["authority_sha256"]) is not None
          and man["authority_sha256"] != man["authority_sha256_parent"]
          and man["store_sha256"] == "050f8125d92c34f6a3312e0915cdd677af3f03542bf022ab836722b9e2749947")

    # ---------------------------------------------------------------- H. declared residual admissions (main admits them too)
    check("H0 the declared residual classes are exactly R1N-01..R1N-03, across the suite and both verifier fixtures",
          set(RESIDUAL.values()) | {c["expected"] for c in v2_refuse} | {c["expected"] for c in v3_refuse if c["expected"].startswith("R1N")}
          == set(CLASSES) and all(c["expected"] in CLASSES for c in v2_refuse))
    for name, cls in RESIDUAL.items():
        target, title, body_text, live = earlier[name]
        got, off = both(target, title, body_text, live=live)
        check(f"H {name} [{cls}]: admitted, and admitted with the rule off as on main (declared residual, not introduced) "
              f"-- {body_text[:50]}", got is None and off is None and residual_class(target, title, body_text, live) == cls,
              f"{got} / off {off} {roles(target, title, body_text)}")
    for c in v2_refuse + [c for c in v3_refuse if c["expected"].startswith("R1N")]:
        got, off = both(c["target"], c["title"], c["body"], live="row")
        check(f"H {c['case']} (verifier) [{c['expected']}]: admitted, and admitted with the rule off as on main "
              f"(declared residual, not introduced) -- {c['body'][:50]}",
              got is None and off is None and residual_class(c["target"], c["title"], c["body"], live="row") == c["expected"],
              f"{got} / off {off}")
    for c in v3_refuse:
        if c["expected"] == "refused" or c["expected"].startswith("R1N"):
            continue
        got, off = both(c["target"], c["title"], c["body"], live="row")
        check(f"H {c['case']} (third verifier): an earlier reason answers first, here and on main alike ({c['expected']})",
              got == off == c["expected"], f"{got} / off {off}")

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
