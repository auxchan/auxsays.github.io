#!/usr/bin/env python3
"""Windows acceptance: `identity_not_linked_to_issue` (AUX-076, the AUX-067 residual R1).

Offline and deterministic, on SYNTHETIC text only. The corpus shapes come from
tests/fixtures/windows_link_roles/corpus_shapes.json: paraphrases written for this suite, one per
stored row the rule refuses (14) or keeps (10), each reaching the same decision and the same
per-occurrence roles as its stored original (checked once, outside CI, by
diagnose_windows_link_roles.py --fixture-equivalence). Nothing here reads `_data`, a record or the
evidence store, and no live total is pinned: corpus growth cannot turn this suite red.

    A  scope guards and placement: a KB match, a title naming the build or KB, a build absent from
       the body and an empty build are never touched; every earlier, more specific reason keeps
       its reason; the rule runs after identity_not_the_subject
    B  preservation: synthetic linked phrasings, the 10 kept corpus shapes, and the second-round
       cases (the independent verifier's "V-" probes and the implementer's "M-" probes, each kept
       by the authority with the rule off, so the rule is what could wrongly refuse them)
    C  negatives: synthetic unlinked phrasings, the 14 refused corpus shapes and the second-round
       cases. Every refusal is checked in the SAME check against the authority with the rule
       switched off, which must accept it, so the rule is the deciding gate and not a passenger
       ("P-" cases pin one pattern each: deleting that pattern alone flips the case)
    D  role units: veto-before-link precedence, anchoring at the occurrence, the closed identity
       filler (no colon, no "on", no date, no other build), sentence and parenthesis masking,
       leading-title-copy stripping (at most the three copies the collectors add, whole words
       only), the record's own month against another month, the exceptions that keep a clean,
       successful-install or "previous" veto from swallowing a report that blames the build, and
       "any linked occurrence keeps the row"
    E  declared limits, pinned as current behaviour and not claimed closed
    F  one authority for every Windows discovery method, and the consumers of the new reason
    G  the pinned refusal manifest (scripts/audit/r1_link_roles_refusals_2026-11-05.json)

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
MANIFEST = _SCRIPTS / "audit" / "r1_link_roles_refusals_2026-11-05.json"
REASON = "identity_not_linked_to_issue"
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


def both(target: dict, title: str, body: str, live: bool = False) -> tuple[str | None, str | None]:
    decide = reason_live if live else reason_of
    got = decide(target, title, body)
    with rule_off():
        off = decide(target, title, body)
    return got, off


def roles(target: dict, title: str, body: str, date: str | None = None) -> list[tuple[str, str]]:
    text = " ".join([title, title, body]).strip()
    when = target["target_release_date"] if date is None else date
    return [(r, k) for r, k, _s in mw.identity_link_details(text, title, target["target_os_build"], when)]


def retained(case: dict) -> str:
    excerpt = case["report_text_excerpt"]
    if excerpt.endswith("..."):
        excerpt = excerpt[:-3]
    return " ".join([case["parent_title"], case["report_title"], excerpt]).strip()


def case_decision(case: dict) -> tuple[str | None, str | None, list[list[str]]]:
    text = retained(case)
    args = (case["target"], case["source_url"], case["source_date"], text, case["report_title"],
            case["matched_kb"], case["matched_os_build"], case["matched_feature_version"])
    got = mw.windows_learn_qna_reason(*args)
    with rule_off():
        off = mw.windows_learn_qna_reason(*args)
    det = [[r, k] for r, k, _s in mw.identity_link_details(text, case["report_title"], case["matched_os_build"],
                                                            case["target"]["target_release_date"])]
    return got, off, det


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


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Windows acceptance: identity_not_linked_to_issue (AUX-076)")
    print("=" * 78)

    # ---------------------------------------------------------------- A. scope guards and placement
    s1_title, s1_body = "Explorer crashes", "KB5077181 installed. Running Windows 11 Pro OS Build 26200.7840. Since the update File Explorer crashes."
    s1_text = " ".join([s1_title, s1_title, s1_body])
    check("A1 S1: a KB match with the build only in a running/spec line is kept, and the rule itself declines it",
          reason_of(T7840, s1_title, s1_body) is None
          and mw.identity_not_linked_to_issue(s1_text, s1_title, "KB5077181", "26200.7840", "KB5077181") is False
          and mw.identity_not_linked_to_issue(s1_text, s1_title, "", "26200.7840", "KB5077181") is True)
    s2_title = "26200.7840 printing broken"
    s2_body = "Running OS Build 26200.7840. Printing broken after the update."
    s2_text = " ".join([s2_title, s2_title, s2_body])
    check("A2 S2: a title naming the target build is kept, and the rule itself declines it",
          reason_of(T7840, s2_title, s2_body) is None
          and mw.identity_not_linked_to_issue(s2_text, s2_title, "", "26200.7840", "KB5077181") is False)
    check("A3 S3: a title naming the target KB is kept through the authority",
          reason_of(T7840, "KB5077181 breaks printing", "Running OS Build 26200.7840. Printing broken after the update.") is None)
    a4_title = "KB5077181 breaks printing"
    a4_text = " ".join([a4_title, a4_title, "Running OS Build 26200.7840. Printing broken after the update."])
    check("A4 the target KB in the title protects a build-only identity on its own (called with matched_kb empty)",
          mw.identity_not_linked_to_issue(a4_text, a4_title, "", "26200.7840", "KB5077181") is False
          and mw.identity_not_linked_to_issue(a4_text, "Printing broken", "", "26200.7840", "KB5077181") is True)
    # Retained-text shape: the build was matched on the full post, the stored excerpt no longer shows it.
    a5_title = "Printer broken after update"
    a5_text = " ".join([a5_title, a5_title, "Printing stopped after the update. Uninstalling the update fixed it."])
    a5 = mw.windows_learn_qna_reason(T7840, URL, "2026-11-01", a5_text, a5_title, "", "26200.7840", "25H2")
    check("A5 a build that is not in the body is never refused (no occurrence, no role, no decision)",
          a5 is None and mw.identity_link_details(a5_text, a5_title, "26200.7840") == []
          and mw.identity_not_linked_to_issue(a5_text, a5_title, "", "26200.7840", "KB5077181") is False, str(a5))
    a6_title, a6_body = "Printer broken", "KB5077181 installed. I'm on 25H2. Printing fails since the update."
    check("A6 an empty matched build is never refused: a KB + train identity counts as before",
          reason_of(T7840, a6_title, a6_body) is None
          and mw.identity_not_linked_to_issue(" ".join([a6_title, a6_body]), a6_title, "", "", "KB5077181") is False)
    a7_title = "Win11 26H2 (KB5121794) boot BSOD after update"
    a7_body = "Win11 Home 25H2 26200.9711 (current). Issue on 26H2 / KB5121794. Removing KB5121794 fixed it, BSOD gone."
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
    a9_title, a9_body = "Explorer crashes", "Explorer crashes randomly on 26200.7840 every morning."
    a9_text = " ".join([a9_title, a9_title, a9_body])
    check("A9 an unattributed report keeps missing_update_attribution, although this rule alone would refuse it",
          reason_of(T7840, a9_title, a9_body) == "missing_update_attribution"
          and mw.identity_not_linked_to_issue(a9_text, a9_title, "", "26200.7840", "KB5077181") is True,
          str(reason_of(T7840, a9_title, a9_body)))
    check("A10 the spam/meta rejection still answers first",
          reason_of(T7840, "Very strange Windows 11 MCT .ISO",
                    "This thread was rejected by the system as spam. I'm on 26200.7840 and the update fails.") == "meta_or_spam_report")
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

    # ---------------------------------------------------------------- B. preservation
    for name, target, title, body_text in KEEP:
        got = reason_of(target, title, body_text)
        check(f"B {name}: kept (the build itself is linked) -- {body_text[:60]}", got is None,
              f"{got} {roles(target, title, body_text)}")
    fixture = json.loads(FIX.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    keeps = [c for c in cases if c["kind"] == "keep"]
    refusals = [c for c in cases if c["kind"] == "refuse"]
    check("B0 the corpus-shape fixture holds 10 kept and 14 refused synthetic cases, each naming one original",
          len(keeps) == 10 and len(refusals) == 14 and len(cases) == 24
          and len({tuple(c["original"]) for c in cases}) == 24)
    for c in keeps:
        got, off, det = case_decision(c)
        check(f"B {c['case']} corpus shape {c['original'][1]} q{c['original'][2]}: kept with the original's roles {c['expected_roles']}",
              got is None and off is None and c["expected_reason"] is None and det == c["expected_roles"]
              and any(r == "affected" for r, _k in det), f"{got} {det}")
    for name, target, title, body_text in KEEP2:
        got, off = both(target, title, body_text)
        check(f"B {name}: kept, as the authority without the rule keeps it -- {body_text[:60]}",
              got is None and off is None, f"{got} / off {off} {roles(target, title, body_text)}")
    for name, target, title, body_text in LIVE_KEEP:
        got, off = both(target, title, body_text, live=True)
        check(f"B {name}: kept under the production construction (the body's own first clause starts with the title)",
              got is None and off is None, f"{got} / off {off}")

    # ---------------------------------------------------------------- C. negatives
    for name, target, title, body_text in REFUSE:
        got, off = both(target, title, body_text)
        check(f"C {name}: refused by this rule, and accepted with the rule off -- {body_text[:60]}",
              got == REASON and off is None, f"{got} / off {off} {roles(target, title, body_text)}")
    for name, target, title, body_text in REFUSE2:
        got, off = both(target, title, body_text)
        check(f"C {name}: refused by this rule, and accepted with the rule off -- {body_text[:60]}",
              got == REASON and off is None, f"{got} / off {off} {roles(target, title, body_text)}")
    for name, target, title, body_text in LIVE_REFUSE:
        got, off = both(target, title, body_text, live=True)
        check(f"C {name}: refused under the production construction (all three leading title copies are removed)",
              got == REASON and off is None, f"{got} / off {off}")
    n4 = reason_of(T7840, "Teams crashes on launch", "After installing the new Teams update on 26200.7840, Teams crashes on launch.")
    check("C N4: the foreign-product veto still answers first for another product's update", n4 == "foreign_product_subject_not_windows_patch", str(n4))
    for c in refusals:
        got, off, det = case_decision(c)
        tag = " [declared limit L4]" if c["declared_limit_l4"] else ""
        check(f"C {c['case']} corpus shape {c['original'][1]} q{c['original'][2]}: refused, accepted with the rule off, roles {c['expected_roles']}{tag}",
              got == REASON and off is None and c["expected_reason"] == REASON and det == c["expected_roles"]
              and det and not any(r == "affected" for r, _k in det), f"{got} / off {off} {det}")

    # ---------------------------------------------------------------- D. role units
    def only(target, title, body_text):
        r = roles(target, title, body_text)
        return r[0] if len(r) == 1 else ("<%d occurrences>" % len(r), "")
    check("D1 clean beats a named link: 'updated to X ... without problems' is clean, not affected (N2)",
          only(T7840, *REFUSE[[n for n, *_ in REFUSE].index("N2")][2:]) == ("clean", "clean:post"))
    check("D2 source beats a named link: 'upgrade X machines to 26H2' is source (N10)",
          only(T7840, "Feature update fails", "Trying to upgrade 26200.7840 machines to 26H2 fails with error 0xC1900101.")[0] == "source")
    check("D3 platform beats an attached update phrase (R32)",
          only(T7840, "Defender definitions", "The Defender update KB2267602 fails to install on 26200.7840 since the February update.")[0] == "platform")
    check("D4 baseline beats an attached update phrase (R30)",
          only(T7840, "26H2 upgrade fails", "I was on 26200.7840 after the February update, then the 26H2 upgrade failed with 0xC1900101.")[0] == "baseline")
    check("D5 an environment marker is a label, not a veto: 'We are on X after last night's update' is affected (P1)",
          only(T7840, "Taskbar keeps crashing", "We are on 26200.7840 after last night's update and the taskbar keeps crashing every few minutes.")
          == ("affected", "attached:post"))
    k13 = "After updating from 26200.7623 to 26200.7840 printing no longer works."
    check("D6 anchoring: in 'from A to X', X is the destination (kept on X) and A is the source (refused on A)",
          only(T7840, "Printing", k13) == ("affected", "destination:pre") and only(T7623, "Printing", k13)[0] == "source"
          and both(T7623, "Printing", k13) == (REASON, None))
    k17 = "The update to 26200.7840 failed to install and rolled back to 26200.7623."
    check("D7 the rollback target is a baseline: K17 is kept on X and refused on the build it rolled back to",
          reason_of(T7840, "Rollback", k17) is None and only(T7623, "Rollback", k17)[0] == "baseline"
          and both(T7623, "Rollback", k17) == (REASON, None))
    d8_title = "Updated to the new build"
    d8_body = "Yesterday all was fine. Updated to the new build 26200.7840 overnight and printing fails since the update."
    check("D8 only LEADING title copies are stripped: a title copy mid-body still links the build (and R33's leading copy does not)",
          reason_of(T7840, d8_title, d8_body) is None and only(T7840, d8_title, d8_body) == ("affected", "named:pre")
          and reason_of(T7840, "Explorer crashes after the update", "26200.7840 here, Pro edition, and it happens every boot.") == REASON)
    check("D9 no colon in the identity filler: 'update Windows Release OS: X' is a spec label (environment), not a named link (R34)",
          only(T7840, "Network not working", "Network not working after Windows 11 25H2 update Windows Release OS: 26200.7840 What I've already tried: drivers.")
          == ("environment", ""))
    check("D10 no date in the identity filler: 'Installed on 2/14/2026 OS build X' is environment, neither platform nor named (R1)",
          only(T7840, "Bluetooth stopped working after update",
               "Edition Windows 11 Pro Version 25H2 Installed on 2/14/2026 OS build 26200.7840 Experience Windows Feature Experience Pack.")
          == ("environment", ""))
    d11 = "Switched Windows 11 Pro on 26200.7840 to dark mode and since the update Explorer crashes."
    check("D11 no 'on' in the identity filler: 'Switched Windows 11 Pro on X' does not name the build as the change",
          only(T7840, "Explorer crashes", d11) == ("unlinked", "") and both(T7840, "Explorer crashes", d11) == (REASON, None),
          str(only(T7840, "Explorer crashes", d11)))
    d12 = "I updated to 26200.7623 (the 26200.7840 package never installed) and printing fails since the update."
    check("D12 no other build in the identity filler: 'updated to A (the X package never installed)' does not link X",
          only(T7840, "Printing fails", d12) == ("unlinked", "") and both(T7840, "Printing fails", d12) == (REASON, None),
          str(only(T7840, "Printing fails", d12)))
    k12 = "Since I installed the latest update on Friday, I installed it (25H2; Build 26200.7840). After the restart search fails."
    check("D13 a short parenthetical is one unit: '(25H2; Build X)' after 'installed it' is a named link (K12)",
          only(T7840, "Search gone", k12) == ("affected", "named:pre"))
    check("D14 a build token's own dot never ends a sentence: one mention is one occurrence, read whole",
          len(roles(T7840, "Audio gone", "After installing 26200.7840 my audio stopped working.")) == 1
          and only(T7840, "Audio gone", "After installing 26200.7840 my audio stopped working.") == ("affected", "named:pre"))
    d15 = "I'm on 26200.7840. After updating to 26200.7840 the printer fails."
    check("D15 one linked occurrence is enough: an environment mention beside a linked one keeps the row",
          roles(T7840, "Printer", d15) == [("environment", ""), ("affected", "named:pre")] and reason_of(T7840, "Printer", d15) is None)
    check("D16 possessive 'I've got X' is not a change (R14), while 'Got X yesterday' is (P3)",
          only(T7840, "Audio crackles", "I've got Windows 11 Pro 25H2 26200.7840 and since the update my audio crackles.")[0] != "affected"
          and only(T7840, "Audio crackles", "Got 26200.7840 yesterday and now my audio crackles. The update broke my sound.") == ("affected", "named:pre"))
    check("D17 'X fails to install <object>' makes X the platform (R29); 'X fails to install with <error>' is a failure of X (K27)",
          only(T7840, "Feature pack", "26200.7840 fails to install the Media Feature Pack, error 0x800F0991.")[0] != "affected"
          and only(T7840, "Install fails", "26200.7840 fails to install with 0x800f0922 and rolls back.") == ("affected", "direct:post"))
    check("D18 'X can't install <object>' makes X the platform; 'X can't install, <error>' is a failure of X",
          only(T7840, "March update", "My laptop on 26200.7840 can't install the March update, error 0x800f0922.")[0] != "affected"
          and only(T7840, "Install fails", "26200.7840 can't install, error 0x800f0922 since the update.") == ("affected", "direct:post"))
    check("D19 'to X' is a destination only after a change word: 'connecting to X machines' is not (R35)",
          only(T7840, "Access denied", "Error 0x80070005 when connecting to 26200.7840 machines since the update.")[0] != "affected")
    check("D20 a bare 'the update on X' names the build as the update (K25); a qualified one is the platform (R26)",
          only(T7840, "Printer stopped", "Since the update on 26200.7840 my printer stopped working. Uninstalling the update fixed it.")
          == ("affected", "named:pre")
          and only(T7840, "Next update", "The next update on 26200.7840 fails to install with error 0x800f0922 every night.")[0] == "platform")
    check("D21 history: 'Successfully installed X' in an update-history line is not a report on X (N6)",
          only(T7840, "Screen flickers", REFUSE[[n for n, *_ in REFUSE].index("N6")][3])[0] == "history")
    check("D22 prospective: 'Will installing X fix this?' names X as a remedy, not a cause (N7)",
          only(T7840, "Wi-Fi drops", "Will installing 26200.7840 fix this? My Wi-Fi drops since the January update.")[0] == "prospective")
    check("D23 each link role is reachable on its own: named, destination, attached, onset and direct",
          {only(T7840, "x", b)[1] for b in (
              "After installing 26200.7840 my audio stopped working.",
              "After updating from 26200.7623 to 26200.7840 printing no longer works.",
              "I'm on 26200.7840 since the update and File Explorer crashes on launch.",
              "Since 26200.7840 I cannot sign in with Windows Hello. Uninstalling the update fixed it.",
              "26200.7840 rolled back twice during restart with error 0x800f0922.")}
          == {"named:pre", "destination:pre", "attached:post", "onset:pre", "direct:post"})

    # Second round: each new or narrowed pattern, both directions.
    gk03 = "Since the February update on 26200.7840 my printer fails with error 0x00000709."
    check("D24 months: the record's own month names the build ('the February update on X' on a February record), another "
          "month is the platform, and with no release date every month counts as another month (fail closed)",
          only(T7840, "Printer", gk03) == ("affected", "named:pre")
          and only(T7840, "Printer", "Since the March update on 26200.7840 printing fails.") == ("platform", "platform:pre")
          and only(T7623, "Printer", "Since the January update on 26200.7623 my printer fails.") == ("affected", "named:pre")
          and roles(T7840, "Printer", gk03, date="") == [("platform", "platform:pre")]
          and roles(T7840, "Printer", gk03, date="2026-03-10") == [("platform", "platform:pre")])
    check("D25 an attached update phrase is month-aware: 'X since the February update' links, 'X since the March update' does not",
          only(T7840, "Printer", "26200.7840 since the February update: my printer fails.") == ("affected", "attached:post")
          and only(T7840, "Printer", "26200.7840 since the March update: printing fails.") == ("unlinked", ""))
    check("D26 an update phrase that failed does not attach: 'on X after last night's update' links, 'on X after the update was rolled back' does not",
          only(T7840, "Taskbar", "We are on 26200.7840 after last night's update and the taskbar keeps crashing every few minutes.")
          == ("affected", "attached:post")
          and only(T7840, "Update rolled back", "I'm on 26200.7840 after the update was rolled back.") == ("environment", ""))
    check("D27 the upgrade source is anchored at the build: 'Upgrading from X' is source, while an unrelated earlier 'from' and "
          "'issues from the latest update (X)' are not",
          only(T7840, "Feature update", "Upgrading from 26200.7840 fails with 0xC1900101 every time since the update.")
          == ("source", "source:pre")
          and only(T7840, "Printer", "Apart from that, after installing 26200.7840 the printer stopped working.") == ("affected", "named:pre")
          and only(T7840, "Printer", "I'm having issues from the latest update (26200.7840): the printer fails after the update.")
          == ("affected", "named:pre"))
    check("D28 a rollback or restore TARGET is a baseline, a removal that fixed it is a link, and a negated removal is neither",
          {only(T7840, "x", b)[0] for b in (
              "The update failed and returned me to 26200.7840, now it fails again with 0x800f0922.",
              "Windows reverted itself to 26200.7840 after the update failed with 0x800f0922.",
              "The update failed and System Restore took me to 26200.7840.",
              "Windows restored 26200.7840 after the update rolled back.")} == {"baseline"}
          and only(T7840, "x", "Rolling back 26200.7840 fixed the printer after the update broke it.") == ("affected", "remedy:mid")
          and only(T7840, "x", "Uninstalling 26200.7840 did not fix it; printing fails since the update.") == ("unlinked", "")
          and only(T7840, "x", "Rolling back 26200.7840 fixed nothing; the March update broke printing.") == ("unlinked", ""))
    check("D29 clean/successful-install exception: a contrast clause with an issue lifts the veto, unless it names another update "
          "(another month, KB, build or train)",
          only(T7840, "x", "26200.7840 installed without any issues, but since the update Bluetooth is gone.") == ("affected", "named:post")
          and only(T7840, "x", "Successfully installed 26200.7840 yesterday, but since the update my audio is gone.") == ("affected", "named:pre")
          and {only(T7840, "x", b)[0] for b in (
              "26200.7840 caused no problems for me, but the March update broke printing.",
              "26200.7840 installed without problems, but KB5079473 broke printing.",
              "26200.7840 installed without problems, but since the update to 26200.7922 printing fails.",
              "26200.7840 installed without problems, but after upgrading to 26H2 printing fails.")} == {"clean"}
          and only(T7840, "x", "Successfully installed 26200.7840. The March update broke printing.") == ("history", "history:pre"))
    check("D30 'previous' is a baseline unless the build itself is then blamed",
          only(T7840, "x", "The previous update, 26200.7840, broke printing after the update installed.") == ("affected", "named:pre")
          and only(T7840, "x", "Previously on 26200.7840 it worked, but since the update printing fails.") == ("baseline", "baseline:pre"))
    check("D31 the build as the SUBJECT that fails to install something else is the platform; failing itself is not",
          only(T7840, "x", "My PC on 26200.7840 is stuck installing the March update at 0%.") == ("platform", "platform:post")
          and only(T7840, "x", "26200.7840 fails to update to 26200.7922 every night.") == ("platform", "platform:post")
          and only(T7840, "x", "26200.7840 keeps crashing after installing the update.") == ("affected", "direct:post")
          and only(T7840, "x", "26200.7840 is stuck at 100% and rolls back.") == ("affected", "direct:post")
          and reason_of(T7840, "Rollback", "The update to 26200.7840 failed to install and rolled back to 26200.7623.") is None)
    check("D32 the build as the label of the machines another update is applied to is the platform",
          only(T7840, "x", "Trying to update 26200.7840 PCs with the March cumulative update fails with 0x800f0922.")
          == ("platform", "platform:post"))
    check("D33 a state statement ('X is the current build') and a following update ('After X, the next update') are baselines; "
          "a plain onset is not",
          only(T7840, "x", REFUSE2[[n for n, *_ in REFUSE2].index("V-GR13")][3]) == ("baseline", "baseline:post")
          and only(T7840, "x", "After 26200.7840, the next update fails to install with 0x800f0922.") == ("baseline", "baseline:post")
          and only(T7840, "x", "After 26200.7840, the next morning my printer failed after the update.") == ("affected", "onset:pre")
          and only(T7840, "x", "Since 26200.7840 is installed, the printer fails.") == ("affected", "onset:pre"))
    check("D34 a comparison point is a baseline: 'compared to X' (the destination link needs a change, not a comparison)",
          only(T7840, "x", "After the update, compared to 26200.7840, boot takes twice as long.") == ("baseline", "baseline:pre")
          and only(T7840, "x", "Since the update to 26200.7840, compared with before, boot is twice as slow.") == ("affected", "named:pre"))
    check("D35 where the reporter was left is a baseline ('still on X', 'stuck on X', 'left me on X'); 'still getting BSODs' is not",
          {only(T7840, "x", b)[0] for b in (
              "I'm still on 26200.7840 after the update failed to install with 0x800f0922.",
              "My PC is stuck on 26200.7840 after the update rolled back twice.",
              "The update rolled back and left me on 26200.7840 with error 0x800f0922.")} == {"baseline"}
          and only(T7840, "x", "I'm still getting BSODs since updating to 26200.7840.") == ("affected", "named:pre"))
    check("D36 an update noun with the build in a parenthesis that CLOSES at it names the build; an open one does not",
          only(T7840, "x", "After the update from last week (build 26200.7840) my printer fails.") == ("affected", "named:mid")
          and only(T24, "x", "After the February 2026 update (OS Builds 26100.7840 and 26200.7840) my printer fails.")
          == ("affected", "named:mid")
          and only(T7840, "x", "After the update from last week (build 26200.7840 here) my printer fails.") == ("unlinked", ""))
    tp1_title, tp1_body = "Printer not working after update", "Printer not working after update to 26200.7840. It worked before."
    check("D37 title copies: at most the three the collectors add are removed (a fourth is the post's own clause), and only "
          "whole-word copies",
          reason_live(T7840, tp1_title, tp1_body) is None
          and reason_live(T7840, "Explorer crashes after the update", "26200.7840 here, Pro edition, and it happens every boot.") == REASON
          and mw._r1_strip_title("Update Update Updated to 26200.7840 the printer fails.", "Update")
          == "Updated to 26200.7840 the printer fails."
          and reason_of(T7840, "Update", "Updated to 26200.7840 and the printer fails since the update.") is None)
    check("D38 the build as a named change also covers 'X build broke', 'X came through' and 'X has a bug'",
          {only(T7840, "x", b)[1] for b in (
              "The 26200.7840 build broke my Wi-Fi. Rolling back the update fixed it.",
              "26200.7840 has a bug that breaks Bluetooth since I updated.")} == {"direct:post"}
          and only(T7840, "x", "26200.7840 came through last night and my audio is gone. The update broke it.") == ("affected", "named:post"))

    # ---------------------------------------------------------------- E. declared limits (pinned, not closed)
    check("E1 [limit L1] an attached link plus a later sentence blaming an unnamed update still counts",
          reason_of(T7840, "Next update keeps failing",
                    "My system has been on 26200.7840 since the February update. Yesterday's update fails with error 0x800f0922.") is None)
    check("E2 [limit L2] onset and persistence are not covered: 'I have since updated to X and it still shuts down' counts",
          reason_of(T7840, "Shutdowns",
                    "This has been happening for a year. I have since updated to 26200.7840 and it still shuts down randomly after every update.") is None)
    check("E3 [limit L3] non-English link grammar is limited to the change-word prepositions: 'Seit X ...' is refused",
          both(T7840, "Explorer", "Seit 26200.7840 stuerzt der Explorer ab, error 0x80070005.") == (REASON, None))
    check("E4 [limit L4] a generic 'after today's update' beside a build stated only as the current state is refused (owner decision, default refuse)",
          both(T9711, "Defender offline scan boots into recovery",
               "26H2 26300.9711 Never seen this before. After todays update I ran a Defender Offline scan and it booted into recovery.")
          == (REASON, None))
    check("E5 [limit L4b] 'Build now: X' after a generic update sentence is refused",
          both(T7840, "Bluetooth gone", "Bluetooth vanished from Device Manager. This happened after the update. Build now: 26200.7840")
          == (REASON, None))
    check("E6 [limit L5] adjacency is the attachment proxy: 'On X the search box ... since the update' is refused while 'On X since the update ...' is kept",
          both(T7840, "Search broke", "On 26200.7840 the search box is not working since the update yesterday.") == (REASON, None)
          and reason_of(T7840, "Search box", "On 26200.7840 since the update yesterday the search box is not working.") is None)
    e7_title = "Update fails 0x800f0922"
    e7_body = "Hotfix list: KB5077181 KB5050021. OS Build 26200.7840. The update fails with 0x800f0922."
    check("E7 [limit L6] a KB match is out of scope even when the KB sits only in a hotfix list",
          reason_of(T7840, e7_title, e7_body) is None)
    check("E8 [limit L7] the filler is a closed list: an unlisted identity word between the change word and X fails closed",
          both(T7840, "Camera fails", "After updating to Windows 11 Pro Workstation Edition 26200.7840 the camera fails.") == (REASON, None))
    check("E9 [limit L5] 'X was successfully installed on <date>, but since then ...' is refused: 'installed on' is the Settings "
          "label and the onset is not adjacent",
          both(T7840, "Printer", "26200.7840 was successfully installed on 2/11, but since then my printer fails.") == (REASON, None))
    check("E10 [limit L8] the contrast exception lifts a clean veto for an issue it does not give to another NAMED update, so "
          "'... but the update fails' counts",
          reason_of(T7840, "Printer old", "26200.7840 installed without problems, but my printer is old and the update fails.") is None)
    check("E11 [limit L7] the closed filler spans an update noun and a parenthesis: 'Installing the update (X here) fails' counts",
          reason_of(T7840, "Install fails", "Installing the update (26200.7840 here) fails with 0x800f0922.") is None)
    check("E12 [limit L9] text built WITHOUT the source's own title prefix (two copies, as some older stored excerpts are) "
          "loses a first clause that begins with the title",
          both(T7840, tp1_title, tp1_body) == (REASON, None) and reason_live(T7840, tp1_title, tp1_body) is None)
    check("E13 [limit L10] 'X - Successfully installed on <date>' reads as an update-history line, even after a change phrase",
          both(T7840, "Printer", "After updating to 26200.7840 - Successfully installed on 2/11/2026 - the printer fails.")
          == (REASON, None))

    # ---------------------------------------------------------------- F. one authority, and the reason's consumers
    rec = PatchRecord(WINDOWS_PRODUCT_ID, "25H2", Path("synthetic-25h2.md"), "2026-02-10T00:00:00Z", "current", "Windows 11", "26200.7840")

    def cand(source_type: str, url: str, title: str, text: str) -> dict:
        return {"source_type": source_type, "source_name": source_type, "source_url": url, "parent_title": title,
                "report_title": title, "report_text": text, "source_date": "2026-02-20"}
    unlinked = "I'm on 26200.7840 and since the update File Explorer crashes on launch."
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
