#!/usr/bin/env python3
"""G35-04: the deterministic verdict-reason producer, its one activation switch, and its integration.

lib/verdict_reason_producer derives reason candidates from STORED data only:
  * vendor_confirmed_serious -- OBS "Fixed ... in V" release-note bullets and the Microsoft
    release-health known-issue roll-up; exact version, verbatim stored statement, closed severity
    vocabulary, affected setup; minor lag / cosmetic / preference or profile reset / no exact version /
    no stored text / ambiguous scope fail closed;
  * user_corroborated_install_failure (Amendment A1) -- Windows rows naming the page's KB with install
    wording, Acrobat installer Exit Code 7 with a product check, the I11 independence gate, at least
    MIN_INDEPENDENT_REPORTERS reporters; TEST FIRST "when installing it", never WAIT.
PUBLIC_AUTO_ACTIVATION (TEMPORARY: OFF, owner approval pending) is the only way a candidate reaches
the decision authority.

SECTIONS. [V] the vendor class on frozen copies of the stored statements -- the 6 named pages
(VRP-V1..V7); review 1's probes: a scope must name a SETUP (V8, V9: "a small number of devices",
"if you use OBS" ... go to the review queue), review 2's hedged scopes are ambiguous too (V8b: "some
consumer devices", "certain conditions", the Q4 row), an OBS version counts only where the vendor names it as
the defective one (V9), the Windows minor-lag exclusion (V9), the vendor "other setups" line only on a
page with nothing else (V10). [I] the install class and its independence gate (VRP-I1..I6); review 1's
frozen negatives -- rows that deny an install failure, name only a build, report the update scan, a
rollback or another update's failure (I7) -- error codes from this update only (I8), and the two
DUPLICATES.md pairs the near-identical-text cue must collapse (I9); AUX-099: independence fails closed
(I10a, I10b, I14: a failure point or an OS version never separates two reports, a declared follow-up is a
copy), the install verb's subject and object (I11), strict grouping (I12), Acrobat rows -- this product,
not denied, grouped on the specific installer error (I13) -- and copy clusters (I15). [P] the corroboration
placeholder fails closed (VRP-P1). [N] purity: no network, no file, no clock, deterministic (VRP-N1,
N2). [S] the switch: ships OFF and changes nothing; ON, the projection, QA and the real gate carry the
candidates; the builder writes the git-ignored artifact (VRP-S0..S6). [C] the shipped corpus
(VRP-C1..C3). [X] mutants, one change each, each caught by a named check.

Needs ruby + the liquid gem for VRP-S3. Offline; writes only in a temp dir.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_verdict_reason_producer.py
"""
from __future__ import annotations

import ast
import contextlib
import copy
import io
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
sys.path.insert(0, str(_AUX / "scripts"))

import yaml  # noqa: E402

from lib import patch_decision as pd  # noqa: E402
from lib import verdict_projection as vp  # noqa: E402
from lib import verdict_reason_producer as vrp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402

PRODUCER_PATH = _AUX / "scripts" / "lib" / "verdict_reason_producer.py"
GATE_PATH = _AUX / "_includes" / "patch-verdict-gate.html"
WIN, OBS = "microsoft-windows-11", "obs-studio"
EM = "—"

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
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


@contextlib.contextmanager
def captured():
    global _PASS, _FAIL, _ERRORS
    saved = (_PASS, _FAIL, _ERRORS)
    _PASS, _FAIL, _ERRORS = 0, 0, []
    failures: list[str] = []
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield failures
    finally:
        failures.extend(_ERRORS)
        _PASS, _FAIL, _ERRORS = saved


# ------------------------------------------------------------------------ frozen stored statements
# Verbatim copies of what the records store today (OBS 31.1.2 / 32.0.4 / 33.0.0 captured notes; the
# 24H2 and 26H1 release-health roll-ups), frozen here so a lane rewriting a roll-up cannot move these
# checks. The corpus checks [C] run over the live records separately.

OBS_31_1_2_NOTES = "\r\n".join([
    "## OBS Studio 31.1.2 Hotfix Changes",
    "* Fixed an issue in OBS Studio 31.1.0 and 31.1.1 causing Multitrack Video to set the Maximum Video Tracks "
    "to 10 if the user had set it to \"Auto\" [dsaedtler]",
    "* Fixed an issue in OBS Studio 31.1.0 and 31.1.1 causing Browser Source hardware acceleration to fail in the "
    "Flatpak version [reitowo/tytan652]",
    "* Fixed an issue in OBS Studio 31.1.0 and 31.1.1 where progress bars were styled incorrectly [Warchamp7]",
    "* Fixed an issue in OBS Studio 31.1.0 and 31.1.1 where spacing around scrollbars was incorrect [Warchamp7]",
    "* Fixed an issue in OBS Studio 31.1.0 and 31.1.1 where Decklink Output did not work [CyBeRoni]",
    "* Fixed a freeze in OBS Studio 31.1.0 and 31.1.1 on Linux when using PipeWire capture with explicit sync [YaLTeR]",
    "* Fixed a crash in OBS Studio 31.0.2 when attempting to log info about a browser source crash [WizardCM]",
])
OBS_32_0_4_NOTES = "\r\n".join([
    "## OBS Studio 32.0.4 Hotfix Changes",
    "* Fixed an issue in 32.0.3 where deleting a scene does not remove its audio sources from the Audio Mixer "
    "[exeldro/Warchamp7]",
    "* Fixed an issue in 32.0.3 with audio device lag due to new deduplication logic [pkviet]",
])
OBS_33_0_0_NOTES = "\r\n".join([
    "## OBS Studio 33.0.0 Changes",
    "* Fixed a crash on macOS 27.2 when starting OBS Studio [PatTheMav]",
    "* Fixed profile import failing on paths with a trailing slash [Ushkalovk] "
    "([#13863](https://github.com/obsproject/obs-studio/pull/13863))",
])
HEADER_24H2 = ("Microsoft Release Health status (official) for Windows 11 24H2: 2 active known issue(s), 3 resolved, "
               "0 safeguard hold(s). Source: official Microsoft Windows release-health status page. This is "
               "vendor-published operational status, not user reports.")
RDP_24H2 = (f"- Active: Remote Desktop connections might fail for non-admin users with error 0xC000000D This issue "
            f"affects non-admin users connecting through Remote Desktop with Administrator protection enabled. {EM} "
            "status Mitigated; originating OS Build 26100.9550 KB5124010; last updated 2026-10-13 10:13 PT.")
AC3_24H2 = (f"- Resolved: Applications which require AC-3 audio decoding might close unexpectedly This issue is more "
            f"likely to occur in legacy applications, and unlikely for many modern applications. {EM} status Resolved "
            "KB5127648; originating OS Build 26100.9550 KB5124010; last updated 2026-10-13 10:13 PT; resolved by KB5127648.")
HEADER_26H1 = HEADER_24H2.replace("24H2", "26H1")
RDP_26H1 = (f"- Resolved: Remote Desktop connections might fail for non-admin users with error 0xC000000D This issue "
            f"affects non-admin users connecting through Remote Desktop with Administrator protection enabled. {EM} "
            "status Resolved KB5127653; originating OS Build 28000.3086 KB5124006; last updated 2026-10-28 22:02 PT; "
            "resolved by KB5127653.")
BLACK_26H1 = (f"- Resolved: Devices might experience a black screen or desktop loading issues after sign-in Microsoft "
              f"has received reports of this issue occurring in some virtual desktop environments. {EM} status Resolved "
              "KB5127646; originating OS Build 28000.2804 KB5120996; last updated 2026-10-13 10:13 PT; resolved by KB5127646.")
# Synthetic shapes for the refusals the corpus does not happen to contain today.
GENERIC_26H1 = (f"- Active: Devices might fail to boot after installing this update {EM} status Confirmed; "
                "originating OS Build 28000.2804 KB5120996; last updated 2026-10-14 10:13 PT.")
NA_26H1 = (f"- Resolved: Domain-joined devices might lose their secure trust relationship with the domain {EM} status "
           "Resolved KB5124010; originating N/A; last updated 2026-10-08 17:44 PT; resolved by KB5124010.")
COSMETIC_26H1 = (f"- Active: Taskbar icons might display incorrectly after sign-in {EM} status Confirmed; originating "
                 "OS Build 28000.2804 KB5120996; last updated 2026-10-14 10:13 PT.")
# Review 1's probes (tools/mut/mine.py R2..R4), verbatim, plus a Windows lag statement (LOW-1 / PM1d).
HEADER_25H2 = HEADER_24H2.replace("24H2", "25H2")
SMALL_NUMBER_25H2 = (f"- Active: Devices might fail to start after installing this update This issue affects a small "
                     f"number of devices. {EM} status Confirmed; originating OS Build 26200.8524 KB5089573; last updated "
                     "2026-10-30 10:00 PT.")
# The same generic description under a SPECIFIC subject: Microsoft's title names the setup, so it is used.
FALLBACK_25H2 = (f"- Active: USB audio devices might fail to start This issue affects a small number of devices. {EM} "
                 "status Confirmed; originating OS Build 26200.8524 KB5089573; last updated 2026-10-30 10:00 PT.")
LAG_25H2 = (f"- Active: Network shares might be unable to open without a long delay This issue affects devices "
            f"connecting to SMB shares over VPN. {EM} status Confirmed; originating OS Build 26200.8524 KB5089573; last "
            "updated 2026-10-30 10:00 PT.")
OBS_32_1_1_PROBE_NOTES = "\r\n".join([
    "## OBS Studio 32.1.1 Hotfix Changes",
    "* Fixed an issue in 32.1.0 where OBS would not start on some systems [probe]",
    "* Fixed a crash when loading scene collections created in 31.0.4 [probe]",
])
# The phrasings review 1 got through the first increment's grammar, each read as a scope.
SCOPES_NAMING_NOBODY = [
    ("if you use A small number of devices", WIN), ("for a limited number of devices", WIN),
    ("for devices that have installed this update", WIN), ("for all editions of Windows 11", WIN),
    ("if you use most devices", WIN), ("for only some users", WIN), ("if you use the update", WIN),
    ("if you use application", WIN), ("if you use program", WIN), ("if you use OBS", OBS),
    ("when starting OBS Studio", OBS), ("for a subset of Windows 11 devices", WIN), ("", WIN),
]
SCOPES_NAMING_A_SETUP = [
    ("if you use virtual desktop environments", WIN), ("if you use USB audio devices", WIN),
    ("if you use domain-joined devices", WIN), ("if you use applications which require AC-3 audio decoding", WIN),
    ("for non-admin users connecting through Remote Desktop with Administrator protection enabled", WIN),
    ("if you use Decklink Output", OBS), ("if you use Browser Source hardware acceleration in the Flatpak version", OBS),
    ("when using PipeWire capture with explicit sync on Linux", OBS), ("when opening source properties on Windows", OBS),
    ("if you use browser sources", OBS), ("if you use macOS 27.2", OBS),
]
# Review 2 (MAJOR-1, tools/mut/mine2.py Q4 and out/unit_probes.txt): scopes that name a setup only
# vaguely, each accepted by review 1's grammar. The first eight are the Q4 row's scope and the
# review's seven unit phrasings; the next three are the review's other accepted unit probes; the last
# four an "environment(s)" with no named type before it.
Q4_25H2 = (f"- Active: Devices might fail to start after installing this update This issue affects a small number of "
           f"devices in some environments. {EM} status Confirmed; originating OS Build 26200.8894 KB5121767; last "
           "updated 2026-10-30 10:00 PT.")
Q4_SCOPE = "for a small number of devices in some environments"
SCOPES_HEDGED = [
    (Q4_SCOPE, WIN), ("for some consumer devices", WIN), ("for devices that meet certain conditions", WIN),
    ("for some devices worldwide", WIN), ("for devices in some regions", WIN),
    ("for some customers in specific scenarios", WIN), ("for some devices under specific circumstances", WIN),
    ("for a limited number of commercial devices", WIN), ("for a small number of devices after restart", WIN),
    ("if you use some environments", WIN),
    ("for devices in these environments", WIN), ("for devices in enterprise environments", WIN),
    ("if you use such environments", WIN), ("when streaming in Windows environments", WIN),
]
# The corpus's two scopes taken from Microsoft's description text (not from a title subject).
CORPUS_DESCRIPTION_SCOPES = [
    ("for non-admin users connecting through Remote Desktop with Administrator protection enabled", WIN),
    ("if you use virtual desktop environments", WIN),
]


def obs(version, published, notes="", count=0, **over):
    r = {"update_entry": True, "product_id": OBS, "update_version": version, "update_published_at": published,
         "permalink": f"/updates/obs-project/obs-studio/{version.replace('.', '-')}/",
         "official_patch_notes_body": notes, "update_report_count": count,
         "official_patch_notes_source_url": f"https://github.com/obsproject/obs-studio/releases/tag/{version}"}
    r.update(over)
    return r


def win(line, build, kb, published, body="", update_type="2026-09 D", count=0, **over):
    r = {"update_entry": True, "product_id": WIN, "update_version": line, "target_build": build, "target_kb": kb,
         "target_feature_version": line, "update_type": update_type, "update_published_at": published,
         "permalink": f"/updates/microsoft/microsoft-windows-11/{line.lower()}/{build}/",
         "official_patch_notes_body": body, "update_report_count": count,
         "official_patch_notes_source_url": "https://learn.microsoft.com/en-us/windows/release-health/"}
    r.update(over)
    return r


def named_fixture() -> list[dict]:
    return [
        obs("31.1.0", "2025-07-07T00:00:00Z"), obs("31.1.1", "2025-07-12T00:00:00Z", count=1),
        obs("31.1.2", "2025-07-28T00:00:00Z", OBS_31_1_2_NOTES),
        obs("32.0.3", "2025-12-05T00:00:00Z"), obs("32.0.4", "2025-12-13T00:00:00Z", OBS_32_0_4_NOTES),
        obs("32.2.2", "2026-08-14T00:00:00Z", count=53), obs("33.0.0", "2026-10-23T00:00:00Z", OBS_33_0_0_NOTES),
        win("24H2", "26100.9550", "KB5124010", "2026-09-22T00:00:00Z"),
        win("24H2", "26100.9725", "KB5134133", "2026-10-26T00:00:00Z", "Base text.\n\n" + "\n".join(
            [HEADER_24H2, RDP_24H2, AC3_24H2]), update_type="2026-10 OOB"),
        win("26H1", "28000.2804", "KB5120996", "2026-08-27T00:00:00Z"),
        win("26H1", "28000.3086", "KB5124006", "2026-09-22T00:00:00Z"),
        win("26H1", "28000.3365", "KB5127653", "2026-10-28T00:00:00Z", "Base text.\n\n" + "\n".join(
            [HEADER_26H1, RDP_26H1, BLACK_26H1, GENERIC_26H1, NA_26H1, COSMETIC_26H1])),
    ]


def page_candidates(result, version, build=""):
    return sorted(((c["verdict"], c["scope"], c["severity_basis"]) for c in result.candidates
                   if c["update_version"] == version and c.get("target_build", "") == build))


def page_exclusions(result, version, build=""):
    return sorted(e["excluded"] for e in result.excluded
                  if e.get("update_version") == version and e.get("target_build", "") == build)


# ------------------------------------------------------------------------ [V] vendor_confirmed_serious

def check_vendor() -> None:
    recs = named_fixture()
    res = vrp.produce(recs, {})
    want_3110 = [("WAIT", "if you use Browser Source hardware acceleration in the Flatpak version",
                  "substantial_workflow_breakage"),
                 ("WAIT", "if you use Decklink Output", "substantial_workflow_breakage"),
                 ("WAIT", "when using PipeWire capture with explicit sync on Linux", "substantial_workflow_breakage")]
    check("VRP-V1 OBS 31.1.0 (named page): OBS's 31.1.2 notes confirm three serious defects that START in 31.1.0 "
          "-- Decklink Output not working, Browser Source hardware acceleration failing in the Flatpak build, a "
          "PipeWire freeze on Linux -- each a scoped WAIT; the two cosmetic bullets and the Multitrack setting are "
          "refused",
          page_candidates(res, "31.1.0") == want_3110
          and page_exclusions(res, "31.1.0") == ["narrow_cosmetic", "narrow_cosmetic", "recoverable_preference_or_profile"],
          f"{page_candidates(res, '31.1.0')} {page_exclusions(res, '31.1.0')}")
    carried = page_candidates(res, "31.1.1")
    reasons_3111 = [c["reason"] for c in res.candidates if c["update_version"] == "31.1.1"]
    check("VRP-V2 the same defects on 31.1.1 are CARRIED OVER from 31.1.0, so they are TEST FIRST and never "
          "called new (a persistent problem is never a regression)",
          [v for v, _s, _b in carried] == ["TEST FIRST"] * 3
          and all("persists in OBS 31.1.1 (carried over from OBS 31.1.0)" in r for r in reasons_3111)
          and all(not c["new_in_this_version"] for c in res.candidates if c["update_version"] == "31.1.1"),
          f"{carried}")
    check("VRP-V3 OBS 32.0.3 (named page) does not qualify: its confirmed defects are an audio LAG (minor lag) and "
          "a stale mixer entry (no severity basis in the closed vocabulary)",
          page_candidates(res, "32.0.3") == [] and page_exclusions(res, "32.0.3") == ["minor_lag", "no_severity_basis"],
          f"{page_candidates(res, '32.0.3')} {page_exclusions(res, '32.0.3')}")
    profile = [e for e in res.excluded if "profile import failing" in e["source"].get("statement", "")]
    crash_no_version = [e for e in res.excluded if "macOS 27.2 when starting" in e["source"].get("statement", "")]
    check("VRP-V4 OBS 32.2.2 #13862 (named page) is EXCLUDED: OBS's profile-import fix names no affected version, "
          "and a profile import that fails is a recoverable profile problem anyway; a version-less crash note is "
          "never attributed to the release before it either",
          page_candidates(res, "32.2.2") == [] and len(profile) == 1
          and profile[0]["excluded"] == "no_exact_version" and profile[0].get("also") == "recoverable_preference_or_profile"
          and profile[0]["source"]["statement"] == "Fixed profile import failing on paths with a trailing slash"
          and len(crash_no_version) == 1 and crash_no_version[0]["excluded"] == "no_exact_version",
          f"{page_candidates(res, '32.2.2')} {profile} {crash_no_version}")
    w24 = page_candidates(res, "24H2", "26100.9550")
    w26 = page_candidates(res, "26H1", "28000.3086")
    b26 = page_candidates(res, "26H1", "28000.2804")
    check("VRP-V5 the three named Windows pages qualify from the stored release-health roll-up, each scoped to "
          "Microsoft's affected setup: 24H2 26100.9550 (Remote Desktop for non-admin users; AC-3 apps closing), "
          "26H1 28000.3086 (the same Remote Desktop issue), 26H1 28000.2804 (black screen in virtual desktop "
          "environments)",
          w24 == [("WAIT", "for non-admin users connecting through Remote Desktop with Administrator protection enabled",
                   "substantial_workflow_breakage"),
                  ("WAIT", "if you use applications which require AC-3 audio decoding", "crash_in_core_flow")]
          and w26 == [("WAIT", "for non-admin users connecting through Remote Desktop with Administrator protection "
                       "enabled", "substantial_workflow_breakage")]
          and b26 == [("WAIT", "if you use virtual desktop environments", "substantial_workflow_breakage")],
          f"{w24} {w26} {b26}")
    ex26 = sorted(e["excluded"] for e in res.excluded if e.get("update_version") == "26H1")
    queued = [q for q in res.review_queue if q.get("target_build") == "28000.2804"]
    check("VRP-V6 refusals that fail closed: a generic subject with no stated setup ('Devices might fail to boot') "
          "is an ambiguous scope and goes to the TEMPORARY review queue; an 'originating N/A' row has no exact "
          "version; a cosmetic issue is refused; a statement whose version has no record has no exact page",
          ex26 == ["ambiguous_scope", "narrow_cosmetic", "no_exact_version"] and len(queued) == 1
          and any(e["excluded"] == "no_exact_page" and e.get("update_version") == "31.0.2" for e in res.excluded),
          f"{ex26} {res.review_queue}")
    bodies = {r["permalink"]: str(r.get("official_patch_notes_body") or "") for r in recs}
    bad = []
    for c in res.candidates:
        cite = c["citation"]
        lines = bodies.get(cite.get("record"), "").replace("\r\n", "\n").split("\n")
        line = lines[cite["line"] - 1] if 0 < cite.get("line", 0) <= len(lines) else ""
        named = c["update_version"] if c["product_id"] == OBS else c.get("target_build", "")
        if (cite.get("statement", "")[:60] not in line or named not in cite.get("statement", "")
                or c["producer"]["version"] != vrp.PRODUCER_VERSION
                or c["producer"]["inputs"].get("body_sha256") != vrp._sha(bodies.get(cite["record"], ""))
                or c["severity_basis"] not in vrp.SEVERITY_BASES or not vr.SCOPE_RE.match(c["scope"])
                or not c.get("failure") or not c["reason"] or len(c["reason"]) > 320
                or (c["verdict"] == "WAIT") != bool(c["new_in_this_version"])):
            bad.append(c["id"])
    check(f"VRP-V7 every vendor candidate ({len(res.candidates)}) carries exact identity, a citation found verbatim "
          "at its stored line that NAMES this exact version or build, a closed-vocabulary severity basis, the "
          "affected setup, a recommendation (WAIT only when new), and provenance hashes of the stored text",
          len(res.candidates) == 10 and not bad, str(bad))


def probe_fixture() -> list[dict]:
    """Review 1's probe shapes on records of their own (tools/mut/mine.py R2..R4) + a lag statement."""
    return [
        obs("31.0.4", "2025-04-01T00:00:00Z"), obs("32.1.0", "2026-03-20T00:00:00Z"),
        obs("32.1.1", "2026-04-02T00:00:00Z", OBS_32_1_1_PROBE_NOTES),
        win("25H2", "26200.8524", "KB5089573", "2026-05-27T00:00:00Z"),
        win("25H2", "26200.9818", "KB5134140", "2026-10-28T00:00:00Z", "Base text.\n\n" + "\n".join(
            [HEADER_25H2, SMALL_NUMBER_25H2, FALLBACK_25H2, LAG_25H2])),
    ]


def check_vendor_scope() -> None:
    let_through = [s for s, p in SCOPES_NAMING_NOBODY if not vrp.scope_problem(s, p)]
    refused = [s for s, p in SCOPES_NAMING_A_SETUP if vrp.scope_problem(s, p)]
    install = {"verdict": "TEST FIRST", "scope": vrp.INSTALL_SCOPE, "reason": "x.", "product_id": OBS,
               "update_version": "9.0.0", "evidence": [], "citation": {"statement": "s", "record": "r"},
               "producer": {"class": vrp.VENDOR_CLASS}}
    check("VRP-V8 a scope must NAME A SETUP, not just read 'if / when / for ...': quantifier and population "
          "phrasings ('a small number of devices', 'all editions of Windows 11', 'only some users', 'devices that "
          "have installed this update'), the update itself, a bare 'application' / 'program' and the product "
          "('if you use OBS') are all refused; every scope the shipped corpus proposes still passes; 'when "
          "installing it' stands only for an installation failure",
          not let_through and not refused
          and not vrp.candidate_problems(dict(install, severity_basis="critical_install_failure"))
          and any("installation failure only" in p for p in vrp.candidate_problems(
              dict(install, severity_basis="crash_in_core_flow"))),
          f"let through={let_through} refused={refused}")
    hedged_through = [s for s, p in SCOPES_HEDGED if not vrp.scope_problem(s, p)]
    corpus_refused = [s for s, p in CORPUS_DESCRIPTION_SCOPES if vrp.scope_problem(s, p)]
    q4 = vrp.produce([win("25H2", "26200.8894", "KB5121767", "2026-09-23T00:00:00Z"),
                      win("25H2", "26200.9818", "KB5134140", "2026-10-28T00:00:00Z", "Base text.\n\n" + "\n".join(
                          [HEADER_25H2, Q4_25H2]))], {})
    q4_ex = [(e["excluded"], e.get("target_build")) for e in q4.excluded]
    q4_queue = [(q.get("update_version"), q.get("target_build")) for q in q4.review_queue]
    q4_info = vrp.classify_windows_issue(Q4_25H2[len("- Active: "):Q4_25H2.index(f" {EM} status")])
    check("VRP-V8b review 2's hedged scopes are AMBIGUOUS and go to the review queue: the Q4 row ('This issue "
          "affects a small number of devices in some environments', 25H2 26200.8894) gives no candidate, and its "
          "scope and the review's other unit phrasings ('some consumer devices', 'certain conditions', 'some "
          "devices worldwide', 'some regions', 'specific scenarios', 'specific circumstances', 'a limited number "
          "of commercial devices') and an 'environments' with no named type before it are all refused; the "
          "corpus's two scopes from Microsoft's description text still pass",
          not hedged_through and not corpus_refused and not q4.candidates
          and q4_ex == [("ambiguous_scope", "26200.8894")] and q4_queue == [("25H2", "26200.8894")]
          and q4_info.get("scope") == "" and q4_info.get("severity") == "substantial_workflow_breakage"
          and "vague" in vrp.scope_problem(Q4_SCOPE, WIN),
          f"let through={hedged_through} corpus refused={corpus_refused} q4 candidates="
          f"{[(c['verdict'], c['scope']) for c in q4.candidates]} excluded={q4_ex} queue={q4_queue} info={q4_info}")
    res = vrp.produce(probe_fixture(), {})
    fallback = [(c["verdict"], c["scope"]) for c in res.candidates if "USB audio devices might" in c["failure"]]
    res.candidates = [c for c in res.candidates if "USB audio devices might" not in c["failure"]]
    by_page = {(c["update_version"], c.get("target_build", "")) for c in res.candidates}
    small = [e for e in res.excluded if "Devices might fail to start after" in e["source"].get("statement", "")]
    lag = [e for e in res.excluded if "without a long delay" in e["source"].get("statement", "")]
    itself = [e for e in res.excluded if "where OBS would not start" in e["source"].get("statement", "")]
    created = [e for e in res.excluded if "created in 31.0.4" in e["source"].get("statement", "")]
    queued = sorted((q.get("update_version", ""), q.get("target_build", "")) for q in res.review_queue)
    check("VRP-V9 review 1's probes give NO candidate: Microsoft's 'This issue affects a small number of "
          "devices' under a generic subject and an OBS fix whose subject is OBS itself are ambiguous scopes, sent "
          "to the TEMPORARY review queue; 'scene collections created in 31.0.4' does not name 31.0.4 as defective "
          "(no exact version); a Windows issue that is a delay is a minor lag. The same generic description under "
          "a specific title subject takes the subject's setup",
          not res.candidates and not by_page and fallback == [("WAIT", "if you use USB audio devices")]
          and [e["excluded"] for e in small] == ["ambiguous_scope"] and [e["excluded"] for e in itself] == ["ambiguous_scope"]
          and [e["excluded"] for e in created] == ["no_exact_version"] and [e["excluded"] for e in lag] == ["minor_lag"]
          and queued == [("25H2", "26200.8524"), ("32.1.0", "")],
          f"candidates={sorted(by_page)} small={small[:1]} itself={itself[:1]} created={created[:1]} lag={lag[:1]} "
          f"queued={queued}")


def check_vendor_body() -> None:
    recs = named_fixture()
    res = vrp.produce(recs, {})
    page = dict(recs[7])  # 24H2 26100.9550: two vendor WAITs, no user report
    vendor = vrp.merge({}, res.candidates).get(vr.record_identity(page), [])
    install = {"id": "x:install", "verdict": "TEST FIRST", "scope": "when installing it", "reason_class":
               "corroborated_install_problem", "reason": "Two users independently report that this update fails "
               "to install."}
    alone = pd.public_body(pd.decide(page, valid_reasons=vendor), page, 0)
    with_reports = pd.public_body(pd.decide(dict(page, update_report_count=12), valid_reasons=vendor), page, 12)
    beside = pd.public_body(pd.decide(dict(page, update_report_count=2), valid_reasons=vendor + [install]), page, 2)
    vendor_line = pd.OTHER_SETUPS_BY_CLASS[vrp.VENDOR_CLASS]
    check("VRP-V10 the vendor 'Other setups: no problem is confirmed for them yet.' line prints only where the "
          "vendor reason stands alone on a page with no report; beside user reports, or beside an 'Also ... users "
          "independently report' reason, the page keeps the usual line that points at the reports",
          len(vendor) == 2 and alone.endswith(vendor_line) and with_reports.endswith(pd.OTHER_SETUPS)
          and beside.endswith(pd.OTHER_SETUPS) and "Also TEST FIRST when installing it" in beside
          and vendor_line not in with_reports + beside,
          f"alone={alone[-60:]!r} reports={with_reports[-60:]!r} beside={beside[-60:]!r}")


# G38 WS2 review (MAJOR-4, LOW-1; g38ws2rev1/out/ws2_unit_probes.txt P6a-g, P7a-e), each a fix bullet on 32.1.0.
P6_PERSISTENT = [
    "Fixed a crash in 32.1.0 when starting a recording that also occurred in earlier versions",
    "Fixed a crash in 32.1.0 (a regression in 31.0.0) when starting the virtual camera",
    "Fixed a crash in 32.1.0 when starting a stream, which existed in previous versions",
    "Fixed an issue in 32.1.0 where audio capture devices did not work, as in 32.0.4",
    "Fixed an issue in 32.1.0 (also seen in 31.1.2) where the replay buffer did not work",
    "Fixed a crash in 32.1.0 when switching scenes, first reported with 31.1.2",
    "Fixed a crash in 32.1.0, there ever since the first release, when switching scene collections",
]
P6_NEW = [
    "Fixed a crash in 32.1.0 when stopping a recording since the output was freed twice",
    "Fixed a crash in 32.1.0 on macOS 14.4.1 when starting the replay buffer",
]
P7_NOT_CORE = [
    "Fixed a freeze in 32.1.0 when closing the About dialog",
    "Fixed a hang in 32.1.0 when opening the Help menu",
    "Fixed a freeze in 32.1.0 when checking for updates",
]
P7_CORE = ["Fixed a freeze in 32.1.0 when starting a stream"]


def check_vendor_persistence() -> None:
    """AUTH_V2_38 WS2 items 6 and 7 (review 2 LOW-1, LOW-2): persistence is never 'new'; OBS crash severity."""
    notes = "\r\n".join([
        "## OBS Studio 32.1.1 Hotfix Changes",
        "* Fixed an issue in 32.1.0 and earlier where audio monitoring devices did not work [probe]",   # review 2 Q2
        "* Fixed a rare crash in 32.1.0 when closing the About dialog [probe]",                         # review 2 Q5
        "* Fixed a crash in 32.1.0 when closing the About dialog [probe]",
        "* Fixed a crash in 32.1.0 when attempting to log info about a browser source crash [probe]",
        "* Fixed a crash in 32.1.0 when resizing the window [probe]",
        "* Fixed a crash in 32.1.0 when starting a recording with the replay buffer active [probe]",
        "* Fixed a possible crash in 32.1.0 on Windows when opening source properties [probe]",
        "* Fixed an issue in 32.1.0 where the virtual camera did not work since 31.0.0 [probe]",
    ] + [f"* {s} [probe]" for s in P6_PERSISTENT + P6_NEW + P7_NOT_CORE + P7_CORE])
    res = vrp.produce([obs("32.1.0", "2026-03-20T00:00:00Z"), obs("32.1.1", "2026-04-02T00:00:00Z", notes)], {})
    by = {}
    for c in res.candidates:
        by[c["failure"]] = (c["verdict"], c["severity_basis"], c["new_in_this_version"], c["reason"])
    ex = {e["source"]["statement"]: e["excluded"] for e in res.excluded}
    queued = sorted(q["source"]["statement"] for q in res.review_queue)
    q2 = by.get("Fixed an issue in 32.1.0 and earlier where audio monitoring devices did not work")
    since = by.get("Fixed an issue in 32.1.0 where the virtual camera did not work since 31.0.0")
    persist_reasons = [r for r in [q2, since] + [by.get(s) for s in P6_PERSISTENT] if r]
    new_ones = [by.get(s) for s in P6_NEW]
    win_notes = "Base text.\n\n" + "\n".join([HEADER_25H2, (
        f"- Active: USB audio devices might fail to start This issue also affects earlier updates of Windows 11. {EM} "
        "status Confirmed; originating OS Build 26200.8524 KB5089573; last updated 2026-10-30 10:00 PT.")])
    win_res = vrp.produce([win("25H2", "26200.8524", "KB5089573", "2026-05-27T00:00:00Z"),
                           win("25H2", "26200.9818", "KB5134140", "2026-10-28T00:00:00Z", win_notes)], {})
    wc = [(c["verdict"], c["new_in_this_version"], c["reason"]) for c in win_res.candidates]
    regression = by.get(P6_PERSISTENT[1])
    scopes = {c["failure"]: c["scope"] for c in res.candidates}
    history_kept_out = [scopes.get(s) for s in (P6_PERSISTENT[0], P6_PERSISTENT[2])]
    check("VRP-V11 a defect the vendor calls carried over is PERSISTENT, never new or caused: review 2's Q2 ('in "
          "32.1.0 and earlier'), 'did not work since 31.0.0', and the G38 WS2 review's phrasings -- 'that also "
          "occurred in earlier versions' (rendered S3), '(a regression in 31.0.0)', 'which existed in previous "
          "versions', 'as in 32.0.4', '(also seen in 31.1.2)', an older OBS version named anywhere ('first reported "
          "with 31.1.2'), 'ever since the first release' -- are TEST FIRST on 32.1.0 saying the problem persists, as "
          "is a Microsoft known issue that "
          "'also affects earlier updates'; none is WAIT and no reason says new, caused, introduced or originates. A "
          "causal 'since' ('since the output was freed twice') and a platform's version ('on macOS 14.4.1') are not "
          "carry-over: those stay WAIT, new in 32.1.0. The carry-over remark stays out of the scope ('when starting a "
          "recording', not '... that also occurred in earlier versions')",
          len(persist_reasons) == 2 + len(P6_PERSISTENT)
          and history_kept_out == ["when starting a recording", "when starting a stream"]
          and all(v == "TEST FIRST" and new is False and "persists" in reason for v, _s, new, reason in persist_reasons)
          and regression is not None and "carried over from OBS 31.0.0" in regression[3]
          and wc and all(v == "TEST FIRST" and new is False and "persists" in r for v, new, r in wc)
          and not any(re.search(r"\b(?:new|caus\w*|introduc\w*|originat\w*)\b", r, re.I)
                      for r in [x[3] for x in persist_reasons] + [x[2] for x in wc])
          and all(n is not None and n[0] == "WAIT" and n[2] is True for n in new_ones),
          f"q2={q2} since={since} persist={len(persist_reasons)} "
          f"{[(s[:40], by.get(s, ('-',))[0]) for s in P6_PERSISTENT]} new={new_ones} win={wc}")
    record = by.get("Fixed a crash in 32.1.0 when starting a recording with the replay buffer active")
    freeze = by.get(P7_CORE[0])
    check("VRP-V12 an OBS crash, freeze or hang is serious only on launch or in a core workflow: review 2's Q5 (a "
          "RARE crash when closing the About dialog) and a POSSIBLE crash in source properties go to the review queue, "
          "never to a page; a crash when closing the About dialog or while logging has no severity basis, nor has a "
          "freeze when closing the About dialog (rendered S4), a hang when opening the Help menu or a freeze when "
          "checking for updates; a crash when starting a recording is a core-flow crash, and a freeze when starting "
          "a stream substantial workflow breakage",
          record is not None and record[:2] == ("WAIT", "crash_in_core_flow")
          and freeze is not None and freeze[:2] == ("WAIT", "substantial_workflow_breakage")
          and all(ex.get(s) == "no_severity_basis" for s in P7_NOT_CORE)
          and ex.get("Fixed a rare crash in 32.1.0 when closing the About dialog") == "uncertain_severity"
          and ex.get("Fixed a possible crash in 32.1.0 on Windows when opening source properties") == "uncertain_severity"
          and ex.get("Fixed a crash in 32.1.0 when closing the About dialog") == "no_severity_basis"
          and ex.get("Fixed a crash in 32.1.0 when attempting to log info about a browser source crash") == "no_severity_basis"
          and ex.get("Fixed a crash in 32.1.0 when resizing the window") == "no_severity_basis"
          and queued == ["Fixed a possible crash in 32.1.0 on Windows when opening source properties",
                         "Fixed a rare crash in 32.1.0 when closing the About dialog"]
          and all(q["kind"] == "uncertain_severity" and q["queue_key"] for q in res.review_queue),
          f"record={record} freeze={freeze} ex={ex} queued={queued}")


# ------------------------------------------------------------------------ [I] install failures

def wrow(i, title, excerpt, date="2026-05-01", url=None, **over):
    r = {"id": f"w-{i}", "source_url": url or f"https://learn.test/q/{i}", "report_title": title,
         "report_text_excerpt": excerpt, "source_date": date, "applicability": None}
    r.update(over)
    return r


KBP = win("25H2", "26200.5000", "KB5099999", "2026-05-01T00:00:00Z", update_type="2026-05 D", count=3)
# Two reports of ONE problem (the same error code) whose details show two incidents: a Dell and an HP laptop.
R1 = wrow(1, "KB5099999 failed to install error 0x800f0991",
          "Update KB5099999 failed to install with error 0x800f0991 on my Dell laptop, tried twice.")
R2 = wrow(2, "KB5099999 Install error 0x800f0991 on a new HP laptop",
          "Installing KB5099999 fails with Install error - 0x800f0991 every time on my HP laptop, Windows 11 Home.",
          "2026-05-02")
R3 = wrow(3, "Start menu broken after KB5099999", "The Start menu does not open since the update.", "2026-05-03")
# The first increment's second row: another error code at a stage, and no detail that sets it apart.
R2_OTHER_CODE = wrow(4, "Cannot install the May preview KB5099999",
                     "Downloading KB5099999 keeps failing at 35 percent, download error 0x80070306, the troubleshooter "
                     "found nothing.", "2026-05-02")
INSTALL_REASON = "Two reports of separate incidents say that this update fails to install with error 0x800f0991."


def install_run(page, rows, **kw):
    return vrp.produce([page], {vr.record_identity(page): rows}, **kw)


def install_cands(result):
    return [x for x in result.candidates if x["producer"]["class"] == vrp.INSTALL_CLASS]


def check_install() -> None:
    res = install_run(KBP, [R1, R2, R3])
    c = install_cands(res)
    check("VRP-I1 Windows: two reports of ONE problem (the same error code) whose details show SEPARATE incidents "
          "(a Dell and an HP laptop) are TEST FIRST 'when installing it', naming the shared code; the unrelated "
          "Start-menu row is not cited",
          len(c) == 1 and (c[0]["verdict"], c[0]["scope"]) == ("TEST FIRST", "when installing it")
          and c[0]["reason"] == INSTALL_REASON and c[0]["problem_key"] == "error 0x800f0991"
          and c[0]["independence_basis"] == ["device"]
          and [e["id"] for e in c[0]["evidence"]] == ["w-1", "w-2"] and c[0]["new_in_this_version"] is False,
          str(c)[:300])
    other_kb = install_run(KBP, [wrow(1, "KB5088888 failed to install", "KB5088888 failed to install, error 0x800f0991."),
                                 wrow(2, "KB5088888 will not install", "KB5088888 will not install on two PCs.")])
    # Detection: each pair carries DIFFERENT source reporter ids (which alone would count as two), and one
    # copy cue -- so the cue is what removes the would-be second reporter.
    ids = lambda a, b: (dict(a, source_reporter_id="author-a"), dict(b, source_reporter_id="author-b"))  # noqa: E731
    plain = (dict(R1, report_text_excerpt="Update KB5099999 failed to install with error 0x800f0991, tried twice."),
             dict(R2, report_text_excerpt="Installing KB5099999 fails with Install error - 0x800f0991 every time."))
    xpost = install_run(KBP, list(ids(plain[0], dict(plain[1], report_text_excerpt=plain[1]["report_text_excerpt"]
                                                    + " I previously posted this on another forum."))))
    twins = install_run(KBP, list(ids(plain[0], dict(plain[0], id="w-9", source_url="https://answers.test/other/9"))))
    kbset = install_run(KBP, list(ids(
        dict(plain[0], report_text_excerpt="KB5099999 and KB5088888 failed to install, error 0x800f0991."),
        dict(plain[1], report_text_excerpt="Both KB5088888 and KB5099999 keep failing to install, install error "
                                           "0x800f0991."))))
    logs = install_run(KBP, list(ids(
        dict(plain[0], report_text_excerpt=plain[0]["report_text_excerpt"] + " log https://obsproject.com/logs/AbCd12"),
        dict(plain[1], report_text_excerpt=plain[1]["report_text_excerpt"] + " log https://obsproject.com/logs/AbCd12"))))
    two_ids = install_run(KBP, list(ids(*plain)))
    gate = {"other KB": other_kb, "declared cross-post": xpost, "same text at two URLs": twins,
            "same KB set": kbset, "same log URL": logs}
    check("VRP-I2 cross-post DETECTION only removes a would-be second reporter: two rows with different source "
          "reporter ids count as two, but a declared cross-post, the same text at a second URL, the same set of KB "
          "numbers or a shared log URL makes them ONE report (no candidate; queued for a person); rows naming "
          "another KB never qualify",
          all(not install_cands(r) for r in gate.values()) and len(install_cands(two_ids)) == 1
          and install_cands(two_ids)[0]["independence_basis"] == ["source_reporter_id"]
          and all(any(q["class"] == vrp.INSTALL_CLASS for q in r.review_queue) for n, r in gate.items() if n != "other KB"),
          str({n: [x["id"] for x in install_cands(r)] for n, r in gate.items()}))
    pro = {"update_entry": True, "product_id": "adobe-acrobat-pro", "update_version": "15.099.20001",
           "permalink": "/updates/adobe/adobe-acrobat-pro/15-099-20001/", "update_report_count": 2}
    reader = dict(pro, product_id="adobe-acrobat-reader", permalink="/updates/adobe/adobe-acrobat-reader/15-099-20001/")
    shared = "adobe-acrobat-reader,adobe-acrobat-pro"
    a1 = wrow(11, "Acrobat DC install fails on my Mac", "Acrobat DC install fails with Exit Code: 7 on El Capitan 10.11.3, "
              "the Creative Cloud app shows an error. ERROR: DW003", applicability=shared)
    a2 = wrow(12, "Cannot install Acrobat Pro DC on Windows 10", "Installer stops with Exit Code: 7 after the "
              "extraction step on a new Windows 10 machine. For example, ERROR: DW003", "2026-05-02", applicability=shared)
    a3 = wrow(13, "Acrobat DC will not install on my iMac", "Exit Code: 7 again on my iMac, Creative Cloud says the "
              "install failed. ERROR: DW003", "2026-05-03", applicability=shared)
    pro_res, reader_res = install_run(pro, [a1, a2]), install_run(reader, [a1, a2])
    reader_ok = install_run(reader, [dict(a1, report_text_excerpt=a1["report_text_excerpt"] + " Same with Reader."),
                                     dict(a2, report_text_excerpt=a2["report_text_excerpt"] + " Acrobat Reader too.")])
    two_macs = install_run(pro, [a1, a3])
    check("VRP-I3 Acrobat: two reports of the same specific installer error (DW003, under Exit Code 7) from a Mac and "
          "from Windows 10 (separate machines) fire on Pro; the same rows shared with Reader do NOT fire on the Reader "
          "page unless they name Reader (the calibration's P15/P16 refusal); two Mac reports are not shown to be "
          "separate machines (an OS version never separates two reports), so they do not fire",
          [x["reason"] for x in install_cands(pro_res)] == [
              "Two reports of separate incidents say that installing this version fails with installer error DW003 "
              "(Exit Code 7)."]
          and install_cands(pro_res)[0]["independence_basis"] == ["os"]
          and install_cands(pro_res)[0]["problem_key"] == "installer error DW003"
          and install_cands(reader_res) == [] and len(install_cands(reader_ok)) == 1 and install_cands(two_macs) == [],
          f"{[x['id'] for x in install_cands(pro_res)]} {[x['id'] for x in install_cands(reader_res)]} "
          f"{[x['independence_basis'] for x in install_cands(pro_res)]} {len(install_cands(two_macs))}")
    saved = vrp.MIN_INDEPENDENT_REPORTERS
    try:
        vrp.MIN_INDEPENDENT_REPORTERS = 3
        raised = install_run(KBP, [R1, R2, R3]).candidates
    finally:
        vrp.MIN_INDEPENDENT_REPORTERS = saved
    check("VRP-I4 the reporter threshold is ONE named constant, 2 (A1: at least 2 independent reporters remain); "
          "raising it to 3 stops the two-reporter page firing",
          vrp.MIN_INDEPENDENT_REPORTERS == 2 and raised == [], str(raised)[:200])
    entries = install_cands(res) + install_cands(pro_res)
    check("VRP-I5 an install candidate is never WAIT and never new: TEST FIRST 'when installing it' only, and a "
          "WAIT-shaped install entry is refused by the candidate schema",
          len(entries) == 2  # a mutant that loses them fails this check instead of crashing the suite
          and all(x["verdict"] == "TEST FIRST" and x["scope"] == "when installing it" for x in entries)
          and bool(vrp.candidate_problems(dict(entries[0], verdict="WAIT"))), f"{len(entries)} install entries")
    sec = dict(KBP, update_type="2026-05 B")
    merged = vrp.merge({}, install_run(sec, [R1, R2]).candidates)
    d = pd.decide(sec, valid_reasons=merged.get(vr.record_identity(sec), []))
    check("VRP-I6 on a monthly security update an install candidate never overrides SECURITY UPDATE: it adds the "
          "owner's 'installation issues reported' affected-configuration panel",
          d.verdict == "SECURITY UPDATE" and pd.PANEL_HEADING.get(d.panel_kind) == "Affected configuration"
          and pd.public_body(d, sec, 2).startswith("Security update - installation issues reported."),
          f"{d} {d.panel_kind}")


# Review 1, MAJOR-2: six REAL counted rows the first increment cited as "this update fails to install",
# frozen verbatim (stored title + excerpt), each with the page it was counted on.
LEARN = "https://learn.microsoft.com/en-us/answers/questions/"
FROZEN_NOT_INSTALL = [
    ("negated", win("25H2", "26200.7623", "KB5074109", "2026-01-13T00:00:00Z"), wrow(
        "q5754132", "2026-01 Security Update (KB5074109) (26200.7623) - Microsoft Q&A",
        "2026-01 Security Update (KB5074109) (26200.7623) - Microsoft Q&A The issue with the Security Update in "
        "December and now in January keeps coming up and eliciting responses that are not helpful. The issue is not "
        "that the update fails to install but that it does install and then...", "2026-02-02",
        url=LEARN + "5754132/2026-01-security-update-(kb5074109)-(26200-7623)"), "the row denies an install failure"),
    ("rollback target", win("25H2", "26200.9168", "KB5121003", "2026-08-12T00:00:00Z"), wrow(
        "q5976649", "Windows Insider Build 26220.9022 Keeps Failing to Install and Rolls Back to 26200.9168 - Microsoft Q&A",
        "Windows Insider Build 26220.9022 Keeps Failing to Install and Rolls Back to 26200.9168 - Microsoft Q&A Hello "
        "Windows Insider Team, I need help with a serious installation problem affecting my Windows 11 Pro Insider "
        "device. My current installed OS build is: Windows 11 Pro —...", "2026-08-16",
        url=LEARN + "5976649/windows-insider-build-26220-9022-keeps-failing-to"), "the row does not name this update"),
    ("update scan", win("25H2", "26200.8246", "KB5083769", "2026-04-14T00:00:00Z"), wrow(
        "q5864200", "Windows Update failed to check for updates with error 0x80240438. - Microsoft Q&A",
        "Windows Update failed to check for updates with error 0x80240438. - Microsoft Q&A This error code keeps coming "
        "up when checking for updates. Edition Windows 11 Home Version 25H2 Installed on ‎3/‎25/‎26 OS build "
        "26200.8246 Experience Windows Feature Experience Pack...", "2026-04-20",
        url=LEARN + "5864200/windows-update-failed-to-check-for-updates-with-er"), "the row does not name this update"),
    ("device build: programs", win("25H2", "26200.9457", "KB5129195", "2026-09-08T00:00:00Z"), wrow(
        "q6011494", "I'm having problems with Windows 11Pro 25H2 26200.9457/Pack 1000.26100.360.0 - Microsoft Q&A",
        "I'm having problems with Windows 11Pro 25H2 26200.9457/Pack 1000.26100.360.0 - Microsoft Q&A I'm having "
        "problems with Windows 11. Sometimes it won't install my programs, sometimes updates don't work, and now my "
        "laptop, which has Windows 11 installed, was showing my account...", "2026-09-22",
        url=LEARN + "6011494/im-having-problems-with-windows-11pro-25h2-26200-9"), "the row does not name this update"),
    ("device build: Settings", win("25H2", "26200.9457", "KB5129195", "2026-09-08T00:00:00Z"), wrow(
        "q6015696", "Windows Update fails with \"Something went wrong\" — UpdateOrchestrator event log missing even after "
        "in-place repair - Microsoft Q&A",
        "Windows Update fails with \"Something went wrong\" — UpdateOrchestrator event log missing even after in-place "
        "repair - Microsoft Q&A Windows 11 25H2 (build 26200.9457), originally upgraded from 21H2. Problem: Windows "
        "Update page in Settings shows \"Something went wrong. Try to...", "2026-09-27",
        url=LEARN + "6015696/windows-update-fails-with-something-went-wrong-upd"), "the row does not name this update"),
    ("another update's failure", win("24H2", "26100.7462", "KB5072033", "2025-12-09T00:00:00Z"), wrow(
        "q5680348", "windows update failed always since 3 months. - Microsoft Q&A",
        "windows update failed always since 3 months. - Microsoft Q&A Can not update the following : Cumulative Update "
        "for .NET Framework 3.5 and 4.8.1 for Windows 11, version 24H2 for x64 (KB5066131) (Install error - 0x800703f1) "
        "2.2025-12 Security Update (KB5072033) (26100.7462)", "2025-12-25",
        url=LEARN + "5680348/windows-update-failed-always-since-3-months"), "the install failure it reports is another update's"),
]
# DUPLICATES.md L1 (26200.7623, live) and N2 (26200.7922): one reporter each, kept apart by nothing but the URL.
L1 = [wrow("q5708079", "security updates are not installing - Microsoft Q&A",
           "security updates are not installing - Microsoft Q&A 2026-01 Security Update (KB5074109) (26200.7623) Install "
           "error - 0x80070306. I install this many times after successfully installation. this show an error and say "
           "retry", "2026-02-04", url=LEARN + "5708079/security-updates-are-not-installing"),
      wrow("q5769728", "Security Update (KB5074109) (26200.7623) Install error - Microsoft Q&A",
           "Security Update (KB5074109) (26200.7623) Install error - Microsoft Q&A 2026-01 Security Update (KB5074109) "
           "(26200.7623) Install error - 0x80070306. I install this many times after successful installation. this show "
           "an error and say retry", "2026-02-10", url=LEARN + "5769728/security-update-(kb5074109)-(26200-7623)-install-e")]
N2 = [wrow("q5794016", "2026 Preview update (KB5077241) (26200.7922) couldn't install - Microsoft Q&A",
           "2026 Preview update (KB5077241) (26200.7922) couldn't install - Microsoft Q&A I have an update that needs to be "
           "installed, and I have tried numerous times to complete it, but it keeps giving me the message to try again. "
           "It is 2026.02 Preview Update KB5077241 (26200.7922)", "2026-03-02",
           url=LEARN + "5794016/2026-preview-update-(kb5077241)-(26200-7922)-could"),
      wrow("q5791250", "How to fix an Windows update that will not install - Microsoft Q&A",
           "How to fix an Windows update that will not install - Microsoft Q&A I have an update that needs to be installed "
           "and I have tried numerous times to complete it and it keeps giving me the message to try again. It is "
           "2026.02 Preview Update KB5077241 (26200.7922) Does anyone have...", "2026-03-11",
           url=LEARN + "5791250/how-to-fix-an-windows-update-that-will-not-install")]


def check_install_rows() -> None:
    wrong = []
    for name, page, row, why in FROZEN_NOT_INSTALL:
        got = vrp.windows_install_row(row, page)
        if got["ok"] or not got["why"].startswith(why):
            wrong.append((name, got))
    probes = {  # review 1's probe R1 (two rows that deny it), a KB row about the update SCAN, and positives
        "did not fail": wrow(21, "KB5099999 Explorer no longer shows PDF previews", "After KB5099999 was installed on "
                             "January 24, 2026 (it did not fail to install, it installed fine), Windows Explorer no longer "
                             "displays PDF files."),
        "scan after the KB": wrow(22, "Windows Update failed to check for updates after KB5099999 - Microsoft Q&A",
                                  "Since the 2026-05 update KB5099999 Windows Update failed to check for updates with error "
                                  "0x80240438."),
    }
    refused = {n: vrp.windows_install_row(r, KBP) for n, r in probes.items()}
    upgrade = vrp.windows_install_row(wrow(23, "Why was the upgrade to 26200.5000 so massive?", "The upgrade to build "
                                           "26200.5000 has failed to install through Windows Update."), KBP)
    kept = [vrp.windows_install_row(r, KBP)["ok"] for r in (R1, R2)]
    denial = FROZEN_NOT_INSTALL[0][2]
    fires = install_run(KBP, [probes["did not fail"], dict(  # probe R1: two users who both say it INSTALLED
        denial, report_title=denial["report_title"].replace("KB5074109", "KB5099999"),
        report_text_excerpt=denial["report_text_excerpt"].replace("KB5074109", "KB5099999"))]).candidates
    check("VRP-I7 a row counts only when it reports THIS update failing to install: review 1's six real cited rows "
          "are refused -- one denies it ('not that the update fails to install'), four name only a build (a "
          "rollback target, the update scan, a device's current build twice), one reports the .NET update beside "
          "it failing -- and so are the probe's denials and a KB row about the update scan; the KB rows and an "
          "'upgrade to build <b> has failed to install' row still count",
          not wrong and not any(v["ok"] for v in refused.values()) and upgrade["ok"] and kept == [True, True]
          and not fires,
          f"wrong={wrong} refused={ {n: v['why'] for n, v in refused.items()} } upgrade={upgrade} kept={kept} "
          f"fires={[c['reason'] for c in fires]}")
    listing = wrow(24, "Updates fail - Microsoft Q&A", "2026-05 Security Update (KB5099999) (26200.5000) Install error - "
                   "0x800f0991 2026-05 .NET Framework Update (KB5088888) Install error - 0x800703f1 on my Dell laptop")
    codes = vrp.windows_install_row(listing, KBP)["codes"]
    reason = [c["reason"] for c in install_cands(install_run(KBP, [listing, R2]))]
    check("VRP-I8 error codes come only from THIS update: in a Windows Update listing the .NET update's "
          "0x800703f1 is not listed for this KB, so the reason names the page's own code",
          codes == ["0x800f0991"] and reason == [INSTALL_REASON], f"{codes} {reason}")
    pairs = {"L1": L1, "N2": N2}
    why = {n: vrp.same_reporter(*rows) for n, rows in pairs.items()}
    gate = {n: len(vrp.independent_reporters(rows)[0]) for n, rows in pairs.items()}
    check("VRP-I9 the independence gate collapses DUPLICATES.md's L1 (26200.7623, live) and N2 (26200.7922) -- the "
          "same misspelt sentences at two URLs -- to one reporter each, on the near-identical-text cue (I10)",
          all(w == "near-identical text once templates are stripped" for w in why.values())
          and gate == {"L1": 1, "N2": 1}, f"{why} {gate}")


# Review 1 LOW-2: L1's real row re-posted under a new title with one added sentence (Jaccard 0.32 then).
L1_REPOST = wrow("q5999001", "Can't get the January security update to install - Microsoft Q&A",
                 "2026-01 Security Update (KB5074109) (26200.7623) Install error - 0x80070306. I install this many times "
                 "after successfully installation. this show an error and say retry. Has anyone found a fix for this yet?",
                 "2026-02-20", url=LEARN + "5999001/cant-get-the-january-security-update-to-install")
# Review 2 Q3: one person's REWORDED re-post (Jaccard 0.231): no passage, no detail, nothing to tell it apart.
Q3_ORIGINAL = wrow(31, "KB5099999 fails to install and Outlook is broken",
                   "Windows Update cannot finish: KB5099999 fails to install with error 0x800f0991 each time. Outlook also "
                   "broke on May 2 and a repair did not help.")
Q3_REWORDED = wrow(32, "Can't install KB5099999, Outlook broken since May 2",
                   "Hi all, Windows Update will not complete on my PC and Outlook has problems too. The update KB5099999 "
                   "fails to install every time with error 0x800f0991. Outlook started misbehaving on May 2 so I tried a "
                   "repair.", "2026-05-04")


def check_independence() -> None:
    """AUTH_V2_37 correction 2 / AUTH_V2_38 WS2 items 1-3: independence fails closed; detection only removes."""
    same_code = [dict(R1, report_text_excerpt="Update KB5099999 failed to install with error 0x800f0991, tried twice."),
                 dict(R2, report_title="KB5099999 Install error 0x800f0991",
                      report_text_excerpt="Installing KB5099999 fails with Install error - 0x800f0991 every time.")]
    unknown = install_run(KBP, same_code)
    queued = [q for q in unknown.review_queue if q["class"] == vrp.INSTALL_CLASS]
    reworded = install_run(KBP, [Q3_ORIGINAL, Q3_REWORDED])
    repost = vrp.same_reporter(L1[0], L1_REPOST)
    l1_three = len(vrp.independent_reporters([L1[0], L1_REPOST, L1[1]])[0])
    # A cross-site re-post (two DIFFERENT source reporter ids, which alone would count as two) that keeps one
    # distinctive passage and rewords everything else: only the shared-passage cue sees it.
    passage = "I install this many times after successfully installation this show an error and say retry"
    first = wrow(33, "KB5099999 keeps failing to install", f"KB5099999 keeps failing to install with error 0x800f0991. "
                 f"{passage}.", source_reporter_id="site-a:1")
    second = wrow(34, "Help please, the May security update KB5099999 will not install, error 0x800f0991",
                  f"Hello everyone, hoping someone here knows this one: {passage}. Tried SFC, DISM, the "
                  "troubleshooter, a clean boot, resetting the Windows Update components and the catalog download of "
                  "KB5099999, error 0x800f0991 each time, nothing works.", "2026-05-06", source_reporter_id="site-b:7")
    cross_site = install_run(KBP, [first, second])
    cross_why = vrp.same_reporter(first, second)
    ta, tb = vrp._content_tokens(first), vrp._content_tokens(second)
    low_overlap = len(ta & tb) / len(ta | tb) < vrp.INDEPENDENCE_JACCARD
    check("VRP-I10a independence FAILS CLOSED: two rows of one problem at different URLs, with no stated detail and "
          "no source reporter id, are not two reporters -- no candidate, refused as not enough independent reports "
          "and queued for a person; review 2's reworded re-post (Q3) is never a second reporter; review 1's L1 "
          "re-post under a new title is DETECTED as one report and L1's three rows count once; a cross-site re-post "
          "under a different reporter id that rewords all but one distinctive passage is DETECTED by that passage "
          "and removed as a second reporter",
          not install_cands(unknown) and len(queued) == 1 and queued[0]["kind"] == "independence"
          and queued[0]["problem_key"] == "error 0x800f0991"
          and any(e["excluded"] == "not_enough_independent_reporters" for e in unknown.excluded)
          and not install_cands(reworded) and repost in ("a shared distinctive passage",
                                                         "near-identical text once templates are stripped")
          and l1_three == 1 and low_overlap and cross_why == "a shared distinctive passage"
          and not install_cands(cross_site),
          f"unknown={[c['id'] for c in install_cands(unknown)]} queued={queued} reworded="
          f"{[c['reason'] for c in install_cands(reworded)]} repost={repost!r} l1={l1_three} "
          f"cross={cross_why!r} low={low_overlap} cross_cands={len(install_cands(cross_site))}")
    # Conservative grouping: two near-identical Windows Update listings whose details conflict are TWO
    # incidents; a shared author with conflicting details is two incidents; a shared author otherwise one.
    tpl = "2026-05 Security Update (KB5099999) (26200.5000) Install error - 0x800f0991 on my {} laptop."
    dell, hp = (wrow(41, "Install error 0x800f0991", tpl.format("Dell")),
                wrow(42, "Install error 0x800f0991", tpl.format("HP"), "2026-05-02"))
    conflicting = install_run(KBP, [dell, hp])
    same_author = install_run(KBP, [dict(dell, source_reporter_id="a1"), dict(hp, source_reporter_id="a1")])
    one_author = install_run(KBP, [dict(same_code[0], source_reporter_id="a1"), dict(same_code[1], source_reporter_id="a1")])
    sim = vrp.same_reporter(dell, dict(dell, id="x", report_text_excerpt=tpl.format("Dell")))
    check("VRP-I10b conservative grouping: near-identical text whose details conflict (a Dell and an HP laptop) is "
          "NOT merged -- two incidents, a candidate; a shared source author with conflicting details is still two "
          "incidents; a shared author with nothing apart is one report; identical text with identical details is one",
          len(install_cands(conflicting)) == 1 and install_cands(conflicting)[0]["independence_basis"] == ["device"]
          and len(install_cands(same_author)) == 1 and not install_cands(one_author)
          and sim == "near-identical text once templates are stripped"
          and vrp.same_reporter(dell, hp) == "",
          f"conflicting={len(install_cands(conflicting))} same_author={len(install_cands(same_author))} "
          f"one_author={len(install_cands(one_author))} sim={sim!r} dell/hp={vrp.same_reporter(dell, hp)!r}")


def check_install_subject() -> None:
    """AUTH_V2_38 WS2 item 4 (review 2 LOW-3, F7): the install verb's subject is this update; install-context codes."""
    base = "The Start menu stopped opening after the May update."
    q1a = wrow(51, "Start menu broken after KB5099999", base + " After installing KB5099999 my Nvidia graphics "
               "driver will not install anymore.")
    q1b = wrow(52, "Start menu broken after KB5099999", base + " Since KB5099999 the HP Smart printer app fails to "
               "install from the Store.", "2026-05-02")
    printer = wrow(53, "KB5099999 then a printer problem", "KB5099999 installed but my printer driver fails to install, "
                   "error 0x80070643.")
    crash = wrow(54, "KB5099999 fails to install", "KB5099999 fails to install with error 0x800f0922 and the PC then "
                 "crashed with HYPERVISOR_ERROR 0x20001.")
    glued = wrow(55, "Install error - 0x800f09912026-05 Preview Update (KB5099999)", "Install error - "
                 "0x800f09912026-05 Preview Update (KB5099999) (26200.5000) every day.")
    follow = wrow(56, "2026-05 update KB5099999 won't install", "2026-05 update KB5099999 won't install. Get error "
                  "code 0x800f0991")
    italian = wrow(57, "Aggiornamento della sicurezza (KB5099999) Errore di installazione - 0x80070002",
                   "ENG: I've been trying for days. Can't install it.")
    both = wrow(58, "KB5099999 and KB5088888 failed to install", "KB5099999 and KB5088888 failed to install, error "
                "0x800f0991.")
    # G38 WS2 review, MAJOR-2 (P4a-c, rendered S2): the install verb's OBJECT is other software, the update named
    # after it ("since KB...", "after KB...") or before it ("Since KB... I can't install the ... driver").
    p4a = wrow(63, "Can't install Realtek driver", "I can't install the new Realtek audio driver since KB5099999, error "
               "0x80070103 every time.")
    p4b = wrow(64, "Office won't install", "Unable to install Office 365 after KB5099999 on my Dell laptop, error "
               "0x80070103.", "2026-05-02")
    p4c = wrow(65, "Nvidia", "Cannot install the Nvidia driver after KB5099999 on my HP laptop, error 0x80070103.",
               "2026-05-03")
    p4kb = wrow(66, "KB5099999 and drivers", "Since KB5099999 I can't install the new Realtek audio driver, error "
                "0x80070103.")
    s2a = wrow(67, "Start menu broken after KB5099999", base + " Separately, I can't install the new Realtek audio "
               "driver since KB5099999 on my Dell laptop, error 0x80070103 every time.")
    s2b = wrow(68, "Taskbar broken after KB5099999", "The taskbar is empty since the May update. Also unable to install "
               "Office after KB5099999 on my HP laptop, error 0x80070103.", "2026-05-02")
    kept = wrow(69, "KB5099999 failed", "Unable to install KB5099999 on my Dell laptop, error 0x80070103; the Realtek "
                "driver is fine.")
    got = {n: vrp.windows_install_row(r, KBP) for n, r in (("q1a", q1a), ("q1b", q1b), ("printer", printer),
                                                           ("crash", crash), ("glued", glued), ("follow", follow),
                                                           ("italian", italian), ("both", both), ("p4a", p4a),
                                                           ("p4b", p4b), ("p4c", p4c), ("p4kb", p4kb), ("s2a", s2a),
                                                           ("s2b", s2b), ("kept", kept))}
    fires = install_cands(install_run(KBP, [q1a, q1b]))
    fires_p4 =install_cands(install_run(KBP, [p4b, p4c])) + install_cands(install_run(KBP, [s2a, s2b]))
    check("VRP-I11 the install verb's subject must be THIS update: review 2's Q1 rows ('After installing KB... my "
          "Nvidia graphics driver will not install', 'Since KB... the HP Smart printer app fails to install') and a "
          "printer driver failing after the update are refused, so Q1 fires nothing; so is install wording whose "
          "OBJECT is other software, the update named after it or before it ('I can't install the new Realtek driver "
          "since KB...', 'unable to install Office after KB...', 'Since KB... I can't install the ... driver'), so the "
          "Dell / HP pair and the rendered S2 pair fire nothing; codes come only from install-error context -- never "
          "a bugcheck (HYPERVISOR_ERROR 0x20001) -- and are read when glued to the next word, in the sentence after "
          "the failure, under a localized 'install error' label; updates named together share the failure",
          not got["q1a"]["ok"] and not got["q1b"]["ok"] and not got["printer"]["ok"] and not fires
          and not any(got[n]["ok"] for n in ("p4a", "p4b", "p4c", "p4kb", "s2a", "s2b")) and not fires_p4
          and got["kept"]["ok"] and got["kept"]["codes"] == ["0x80070103"]
          and got["crash"]["codes"] == ["0x800f0922"] and got["glued"]["codes"] == ["0x800f0991"]
          and got["follow"]["codes"] == ["0x800f0991"] and got["italian"]["codes"] == ["0x80070002"]
          and got["both"]["ok"] and got["both"]["codes"] == ["0x800f0991"],
          str({n: (v["ok"], v["codes"], v["why"][:40]) for n, v in got.items()}) + f" fires_p4={len(fires_p4)}")


def check_install_grouping() -> None:
    """AUTH_V2_38 WS2 item 5 (Amendment A3): a specific shared characteristic; different codes alone are not one problem."""
    other = dict(R2, report_text_excerpt=R2["report_text_excerpt"].replace("0x800f0991", "0x80073712"),
                 report_title=R2["report_title"].replace("0x800f0991", "0x80073712"))
    strict = install_run(KBP, [R1, other])
    lenient = install_run(KBP, [R1, other], install_grouping="lenient")
    rollback = install_run(KBP, [dict(R1, report_text_excerpt=R1["report_text_excerpt"] + " It rolls back after the "
                                      "restart."),
                                 dict(other, report_text_excerpt=other["report_text_excerpt"] + " Each time it rolls "
                                      "back after restarting.")])
    rb = install_cands(rollback)
    check("VRP-I12 strict install grouping is the default (A3): two separate incidents with DIFFERENT error codes are "
          "not one problem -- no candidate, refused as sharing no characteristic and queued; the same two sharing a "
          "named stage (it rolls back) are one problem; A1's lenient reading exists only to be measured",
          vrp.INSTALL_GROUPING == "strict" and not install_cands(strict)
          and any(e["excluded"] == "no_shared_failure_characteristic" for e in strict.excluded)
          and any(q["class"] == vrp.INSTALL_CLASS for q in strict.review_queue)
          and len(install_cands(lenient)) == 1 and len(rb) == 1 and rb[0]["problem_key"] == "rolls back"
          and rb[0]["reason"].endswith("fails to install: it rolls back instead of completing."),
          f"strict={len(install_cands(strict))} lenient={len(install_cands(lenient))} rollback={[c['reason'] for c in rb]}")


# G38 WS2 review (round 1 of AUX-099): the Acrobat rows. Probe shapes from g38ws2rev1/tools/py/ws2_unit_probes.py.
ACRO_PRO = {"update_entry": True, "product_id": "adobe-acrobat-pro", "update_version": "15.099.20001",
            "permalink": "/updates/adobe/adobe-acrobat-pro/15-099-20001/", "update_report_count": 2}
ACRO_TAIL = " Exit Code: 7 Please see specific errors below for troubleshooting. For example, ERROR: "


def check_acrobat_rows() -> None:
    """AUTH_V2_38 WS2 items 4 and 5 for Acrobat (review MAJOR-2, MAJOR-3): this product failing; one SPECIFIC error."""
    other_product = [  # P4d: Exit Code 7 of ANOTHER Adobe product, on rows counted for Acrobat Pro
        wrow(71, "Photoshop fails, Acrobat fine", "Acrobat Pro DC 15.099.20001 works on my Mac, but Photoshop CC fails "
             "with" + ACRO_TAIL + "DW003"),
        wrow(72, "Illustrator install error on Windows 10", "Windows 10: Acrobat Pro DC is up to date (15.099.20001) and "
             "works; Illustrator will not install," + ACRO_TAIL + "DW003", "2026-05-02")]
    denied = [  # P4e: the rows say this version installed
        wrow(73, "Fixed!", "Exit Code: 7 is gone: Acrobat Pro DC 15.099.20001 installed fine on my Mac today. DW003"),
        wrow(74, "Works now", "On Windows 10 the old Exit Code: 7 error is gone, 15.099.20001 installed successfully.",
             "2026-05-02")]
    # P5a: the SPECIFIC installer errors differ (DW003/DW006 on a Mac, DW071 on Windows 10); only the generic Exit
    # Code 7 is shared. P5b: the same specific error on both (a control: one problem).
    p5a = [wrow(75, "Install fails on Mac", "Acrobat Pro DC will not install on my Mac." + ACRO_TAIL + "DW003, DW006"),
           wrow(76, "Installation failed error DW071", "Windows 10 clean install, Acrobat DC fails installation:"
                + ACRO_TAIL + "DW071", "2026-05-02")]
    p5b = [p5a[0], dict(p5a[1], report_title="Installation failed error DW003",
                        report_text_excerpt=p5a[1]["report_text_excerpt"].replace("DW071", "DW003"))]
    no_code = [wrow(77, "Acrobat Pro DC fails on my Mac", "Acrobat Pro DC fails to install on my Mac, Exit Code: 7."),
               wrow(78, "Acrobat Pro DC fails on Windows 10", "Windows 10: Acrobat Pro DC fails with Exit Code: 7.",
                    "2026-05-02")]
    rows = {n: [vrp.acrobat_install_row(r, ACRO_PRO["product_id"]) for r in rs]
            for n, rs in (("other", other_product), ("denied", denied), ("p5a", p5a), ("no_code", no_code))}
    runs = {n: install_run(ACRO_PRO, rs) for n, rs in (("other", other_product), ("denied", denied), ("p5a", p5a),
                                                       ("p5b", p5b), ("no_code", no_code))}
    queued = {n: [q["problem_key"] for q in r.review_queue if q["class"] == vrp.INSTALL_CLASS] for n, r in runs.items()}
    p5b_c = install_cands(runs["p5b"])
    check("VRP-I13 Acrobat rows count only when THIS product fails to install, grouped on the SPECIFIC installer "
          "error: Exit Code 7 that is another Adobe product's ('Acrobat works, but Photoshop fails with Exit Code: "
          "7', 'Illustrator will not install, Exit Code: 7') and rows saying the version installed or the error is "
          "gone are refused (P4d, P4e); reports whose specific errors differ (DW003/DW006 vs DW071) share "
          "only the generic Exit Code 7 every failure prints, so they are not one problem -- no candidate, queued "
          "(P5a), as are rows with no specific error; the same specific error on a Mac and on Windows 10 is one "
          "problem (TEST FIRST naming it)",
          [i["why"] for i in rows["other"]] == ["the Exit Code 7 it reports is another Adobe product's"] * 2
          and [i["why"] for i in rows["denied"]] == ["the row denies an install failure"] * 2
          and [i["codes"] for i in rows["p5a"]] == [["DW003", "DW006"], ["DW071"]]
          and [i["ok"] for i in rows["no_code"]] == [True, True] and [i["codes"] for i in rows["no_code"]] == [[], []]
          and not any(install_cands(runs[n]) for n in ("other", "denied", "p5a", "no_code"))
          and queued["p5a"] == ["no shared characteristic"] and queued["no_code"] == ["no shared characteristic"]
          and len(p5b_c) == 1 and p5b_c[0]["problem_key"] == "installer error DW003"
          and p5b_c[0]["independence_basis"] == ["os"],
          f"rows={ {n: [(i['ok'], i['why'][:30], i['codes']) for i in v] for n, v in rows.items()} } "
          f"queued={queued} p5b={[c['reason'] for c in p5b_c]}")


def check_one_machine() -> None:
    """AUTH_V2_38 WS2 items 1 and 3 (review MAJOR-1): what one person on one machine shows twice is one report."""
    p3a = [wrow(81, "KB5099999 won't install", "KB5099999 fails to install on my PC with error 0x800f0922. The progress "
                "bar gets stuck at 35% and then it gives up. I already ran the troubleshooter."),
           wrow(82, "Still cannot get the May cumulative update on", "Tried again this morning: KB5099999 failed to "
                "install, error 0x800f0922 again, this time it stopped at 61% before giving up. Any ideas what to try "
                "next?", "2026-05-03")]
    p3b = [wrow(83, "KB5099999 fails", "KB5099999 fails to install with error 0x800f0922, my CPU sits at 100% the whole "
                "time while Windows Update spins."),
           wrow(84, "Update error", "KB5099999 failed to install with 0x800f0922. It goes to 20% and then errors out.",
                "2026-05-04")]
    p3c = [wrow(85, "Acrobat DC install fails on Sierra", "Acrobat Pro DC will not install on my Mac running Sierra "
                "10.12.6." + ACRO_TAIL + "DF012"),
           wrow(86, "Still failing after upgrading to High Sierra", "I upgraded to High Sierra 10.13 hoping it would "
                "help, but the Acrobat Pro DC installer still ends with" + ACRO_TAIL + "DF012", "2026-05-08")]
    # Rendered S1's shape: two rows of one code, one adds a stall point, the other the SAME author's declared
    # follow-up with another stall point.
    s1 = [wrow(87, "KB5099999 install error 0x800f0991", "KB5099999 failed to install with error 0x800f0991. The "
               "progress bar stops at 35% each time."),
          wrow(88, "KB5099999 install error 0x800f0991 again", "Install error - 0x800f0991 on KB5099999. Following up on "
               "my question from last week: tried again today and this time it stopped at 61%.", "2026-05-09")]
    runs = {"p3a": install_run(KBP, p3a), "p3b": install_run(KBP, p3b), "p3c": install_run(ACRO_PRO, p3c),
            "s1": install_run(KBP, s1)}
    details = [vrp.incident_details(r) for r in p3a] + [vrp.incident_details(r, "adobe-acrobat-pro") for r in p3c]
    s1_dropped = vrp.independent_reporters(s1)[1]
    same_stall = vrp.same_reporter(
        wrow(89, "x", "KB5099999 fails to install on my Dell XPS laptop, it stops at 35% every time."),
        wrow(90, "y", "Windows Update halts at 35% while installing KB5099999 on this XPS from Dell; tried SFC, DISM "
             "and a clean boot without luck."))
    check("VRP-I14 what ONE person on ONE machine shows twice is never a second incident: a retry that stops at "
          "another percentage (P3a), a CPU at 100% beside an install at 20% (P3b), the same Mac before and after an "
          "upgrade from Sierra 10.12.6 to High Sierra 10.13 (P3c) -- each no candidate, queued for a person; a declared "
          "follow-up ('Following up on my question from last week', rendered S1) is a copy and never counts; failure "
          "points and OS versions are still read, as copy-detection cues only (the same stall point and computer on "
          "two rows is one report)",
          not any(install_cands(r) for r in runs.values())
          and all(any(e["excluded"] == "not_enough_independent_reporters" for e in r.excluded)
                  for n, r in runs.items() if n != "s1")
          and [d.get("failure_point") for d in details[:2]] == [frozenset({"35%"}), frozenset({"61%"})]
          and [d.get("os_version") for d in details[2:]] == [frozenset({"macos-10.12"}), frozenset({"macos-10.13"})]
          and [d["why"] for d in s1_dropped] == ["a declared cross-post"]
          and same_stall == "the same incident details",
          f"cands={ {n: [c['independence_basis'] for c in install_cands(r)] for n, r in runs.items()} } "
          f"s1_dropped={s1_dropped} same_stall={same_stall!r}")


# A chain of copies: A (site-a author) and B share one passage, B and C (site-b author) another; A and C share none.
CHAIN_P1 = "the cumulative package downloads fully then reverts every change after the second reboot screen"
CHAIN_P2 = "servicing stack repair through dism restorehealth finished cleanly yet nothing changed afterwards"


def check_copy_clusters() -> None:
    """AUTH_V2_38 WS2 items 1 and 2 over clusters (review P2b; reviewer mutants RM5, RM6, RM7)."""
    common = ("Something didn't go as planned. No need to worry, undoing changes. Please keep your computer on. "
              "We couldn't complete the updates, undoing changes, don't turn off your computer.")
    dell = wrow(91, "KB5099999 fails on Dell XPS", "My Dell XPS 13 cannot install KB5099999, error 0x800f0922. " + common)
    lenovo = wrow(92, "KB5099999 fails on ThinkPad", "ThinkPad T14 here. KB5099999 failed to install, 0x800f0922. "
                  + common, "2026-05-02")
    bridge = wrow(93, "Same", "KB5099999 failed to install, 0x800f0922. " + common, "2026-05-03")
    bridged = vrp.independent_reporters([dell, lenovo, bridge])
    # One row names a Dell, the other a Dell AND an HP: they can be one machine (overlap is not a conflict).
    overlap = install_run(KBP, [wrow(94, "KB5099999 install error 0x800f0991", "KB5099999 failed to install with error "
                                     "0x800f0991 on my Dell laptop."),
                                wrow(95, "Install error 0x800f0991 everywhere", "Install error - 0x800f0991 for KB5099999 "
                                     "on my Dell laptop and on my HP laptop too.", "2026-05-02")])
    chain = [wrow(96, "KB5099999 will not install", f"KB5099999 will not install, error 0x800f0991: {CHAIN_P1}.",
                  source_reporter_id="site-a:1"),
             wrow(97, "Help with KB5099999", f"Error 0x800f0991 on KB5099999. {CHAIN_P1}. Then {CHAIN_P2}.",
                  "2026-05-02"),
             wrow(98, "Any fix for May update", f"Hello, the May update keeps failing with 0x800f0991 for KB5099999 and "
                  f"{CHAIN_P2}.", "2026-05-03", source_reporter_id="site-b:7")]
    chain_kept = vrp.independent_reporters(chain)[0]
    direct = (vrp.same_reporter(R1, dict(R2, report_text_excerpt=R2["report_text_excerpt"] + " Cross-posted from the "
                                         "Windows forum.")),
              vrp.same_reporter(R1, dict(R2, report_text_excerpt=R2["report_text_excerpt"] + " Reposting since nobody "
                                         "replied.")))
    check("VRP-I15 copy detection and conservative grouping over CLUSTERS: a detail-less third row quoting the same "
          "error text never bridges a Dell and a ThinkPad incident into one report (P2b: two stay two); rows whose "
          "computers overlap ('my Dell' / 'my Dell and my HP') can be one machine, so they are not two; a copy of a "
          "copy is one report -- a chain A~B~C whose ends carry different reporter ids and share nothing directly "
          "counts once; a declared cross-post or re-post is one report even when the rows are compared directly",
          len(bridged[0]) == 2 and {r["id"] for r in bridged[0]} == {"w-91", "w-92"}
          and not install_cands(overlap) and len(chain_kept) == 1
          and not vrp._passages(chain[0]) & vrp._passages(chain[2])
          and direct == ("a declared cross-post", "a declared cross-post"),
          f"bridged={[r['id'] for r in bridged[0]]} overlap={len(install_cands(overlap))} "
          f"chain={[r['id'] for r in chain_kept]} direct={direct}")


# ------------------------------------------------------------------------ [P] placeholder

def check_placeholder() -> None:
    a = {"id": "a", "source_url": "https://one.test/1", "report_title": "Crash on export", "report_text_excerpt": "x"}
    b = dict(a, id="b", source_url="https://two.test/2")
    verdicts = {"independent": True, "uncertain": False, "not_independent": False}
    check("VRP-P1 the non-install corroboration placeholder fails closed: it proposes nothing, two rows at "
          "different URLs are NOT independent without a verifier, and only a verifier's 'independent' counts",
          vrp.corroboration_candidates(obs("9.0.0", "2026-01-01"), [a, b]) == []
          and vrp.corroboration_candidates(obs("9.0.0", "2026-01-01"), [a, b],
                                           incident_independence=lambda x, y: "independent") == []
          and vrp.rows_are_independent(a, b) is False
          and all(vrp.rows_are_independent(a, b, incident_independence=lambda x, y, v=v: v) is want
                  for v, want in verdicts.items()))


# ------------------------------------------------------------------------ [N] purity

ALLOWED_IMPORTS = {"__future__", "hashlib", "json", "re", "typing", "verdict_reasons"}


def check_purity() -> None:
    tree = ast.parse(PRODUCER_PATH.read_text(encoding="utf-8"))
    imported, calls = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported |= {node.module.split(".")[0]} if node.module else {a.name for a in node.names}
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node, ast.Attribute) and node.attr in ("environ", "argv", "now", "today", "time"):
            calls.add(node.attr)
    attempts: list = []
    real = (socket.getaddrinfo, socket.socket.connect, socket.create_connection)

    def gai(*a, **k):
        attempts.append(("getaddrinfo", a[:1]))
        raise OSError("network refused by VRP-N1")

    def connect(self, address):
        attempts.append(("connect", address))
        raise OSError("network refused by VRP-N1")

    def create_connection(address, *a, **k):
        attempts.append(("create_connection", address))
        raise OSError("network refused by VRP-N1")
    socket.getaddrinfo, socket.socket.connect, socket.create_connection = gai, connect, create_connection
    try:
        first = json.dumps(vrp.produce(named_fixture(), {}).as_dict(), sort_keys=True)
        second = json.dumps(vrp.produce(named_fixture(), {}).as_dict(), sort_keys=True)
        third = json.dumps(vrp.produce(list(reversed(named_fixture())), {}).as_dict(), sort_keys=True)
    finally:
        socket.getaddrinfo, socket.socket.connect, socket.create_connection = real
    check("VRP-N1 the producer is a pure function of its arguments: it imports only the standard regex/hash/json "
          "modules and lib.verdict_reasons, opens no file, reads no environment, argv or clock, and a run makes "
          "zero network attempts",
          imported <= ALLOWED_IMPORTS and "open" not in calls and not ({"environ", "argv", "now", "today", "time"} & calls)
          and not attempts, f"imports={sorted(imported - ALLOWED_IMPORTS)} calls={sorted(calls & {'open', 'environ', 'argv'})} "
                           f"attempts={attempts[:2]}")
    check("VRP-N2 deterministic: two runs are byte-identical, and the record order does not change the result",
          first == second == third)


# ------------------------------------------------------------------------ corpus (shared)

_CORPUS: dict = {}


def corpus() -> dict:
    if not _CORPUS:
        records, groups = vp.load_inputs(_AUX)
        reasons, lifecycle, problems = vp.load_fact_files(_AUX)
        _CORPUS.update(records=records, groups=groups, reasons=reasons, lifecycle=lifecycle, problems=problems,
                       produced=vrp.produce(records, groups))
    return _CORPUS


@contextlib.contextmanager
def switch(on: bool):
    saved = vrp.PUBLIC_AUTO_ACTIVATION
    vrp.PUBLIC_AUTO_ACTIVATION = on
    try:
        yield
    finally:
        vrp.PUBLIC_AUTO_ACTIVATION = saved


def reviewed_only_projection(c) -> dict:
    """The projection decide gives with the reviewed entries alone (the producer not consulted at all)."""
    by_ident = {vr.record_identity(r): r for r in c["records"]}
    valid, _u = vr.valid_reasons_by_identity(c["reasons"], c["groups"], by_ident)
    pages = {}
    for rec in c["records"]:
        d = pd.decide(dict(rec), valid_reasons=valid.get(vr.record_identity(rec), []), lifecycle=c["lifecycle"])
        if d.verdict != pd.INSUFFICIENT_DATA:
            pages[vp.page_key(rec)] = vp.row_for(d, rec)
    return {"schema_version": vp.SCHEMA_VERSION, "pages": dict(sorted(pages.items()))}


# ------------------------------------------------------------------------ [S] the switch

def check_switch(tmp: Path) -> None:
    text = PRODUCER_PATH.read_text(encoding="utf-8")
    assigns = re.findall(r"^PUBLIC_AUTO_ACTIVATION\s*=\s*(.+)$", text, re.M)
    check("VRP-S0 the ONE activation switch ships OFF, as a literal module constant labelled TEMPORARY (no "
          "environment variable, argument or file can turn it on)",
          vrp.PUBLIC_AUTO_ACTIVATION is False and assigns == ["False"]
          and "TEMPORARY" in text.split("PUBLIC_AUTO_ACTIVATION = False")[0][-400:], str(assigns))
    c = corpus()
    shipped = vp.project(c["records"], c["groups"], c["reasons"], c["lifecycle"])[0]
    reviewed = reviewed_only_projection(c)
    check(f"VRP-S1 switch OFF: the shipped projection is byte-identical to the reviewed-entries-only projection "
          f"({len(reviewed['pages'])} rows) although the producer proposes {len(c['produced'].candidates)} "
          "candidates over the same corpus -- nothing published changes",
          vp.render(shipped) == vp.render(reviewed) and len(c["produced"].candidates) > 0
          and vp.supported_reasons(c["records"], c["groups"], c["reasons"])[0]
          == vr.valid_reasons_by_identity(c["reasons"], c["groups"],
                                          {vr.record_identity(r): r for r in c["records"]})[0])
    with switch(True):
        on = vp.project(c["records"], c["groups"], c["reasons"], c["lifecycle"])[0]
        valid_on, _u = vp.supported_reasons(c["records"], c["groups"], c["reasons"])
    changed = sorted(k for k in set(on["pages"]) | set(reviewed["pages"]) if on["pages"].get(k) != reviewed["pages"].get(k))
    cand_pages = {"|".join(vr.reason_identity(x)) for x in c["produced"].candidates}
    by_key = {vp.page_key(r): r for r in c["records"]}
    rows_are_decide = all(on["pages"][k] == vp.row_for(pd.decide(dict(by_key[k]), valid_reasons=valid_on.get(
        vr.record_identity(by_key[k]), []), lifecycle=c["lifecycle"]), by_key[k]) for k in changed if k in on["pages"])
    kept_reviewed = all(set(reviewed["pages"][k]["reasons"]) <= set(on["pages"][k]["reasons"])
                        for k in reviewed["pages"] if reviewed["pages"][k]["reasons"])
    check(f"VRP-S2 switch ON: the projection changes on candidate pages only ({len(changed)} rows), every changed "
          "row is exactly decide's over the merged reasons, and every reviewed entry stays on its page",
          changed and set(changed) <= cand_pages and rows_are_decide and kept_reviewed,
          f"{len(changed)} {sorted(set(changed) - cand_pages)[:3]}")
    check_render_switch_on()
    check_qa_switch(tmp / "qa")
    check_builder(tmp / "builder")
    check_writers(tmp / "writers")


def check_writers(tmp: Path) -> None:
    """AUTH_V2_38 WS2 item 8: the record writers gather a page's reasons exactly as the projection does, so
    with the switch ON the prose they store is the page's verdict and verdict_policy_drift clears."""
    import apply_consensus_to_records as acr  # noqa: PLC0415 - the writer itself, offline
    import build_consensus_from_evidence as bce  # noqa: PLC0415
    recs = named_fixture()
    gen = tmp / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(recs):
        (gen / f"r{i:02d}.md").write_text("---\n" + yaml.safe_dump(r, allow_unicode=True) + "---\nbody\n",
                                          encoding="utf-8")
    index = {(r["product_id"], r["update_version"], r.get("target_build", "")): r for r in recs}
    page = recs[0]   # OBS 31.1.0: three vendor WAITs, no report
    got = {}
    saved_dir, saved_cache = acr.GENERATED_DIR, list(acr._ALL_ENTRY_RECORDS)
    try:
        acr.GENERATED_DIR = gen
        for on in (False, True):
            acr._ALL_ENTRY_RECORDS.clear()
            with switch(on):
                a = acr._policy_decision(OBS, "31.1.0", "", [], dict(page))[0]
                b = bce.policy_decision(OBS, "31.1.0", "", [], dict(page), index)[0]
                valid, _u = vp.supported_reasons(recs, {}, [])
                want = pd.decide(dict(page), valid_reasons=valid.get(vr.record_identity(page), []))
            got[on] = ((a.verdict, a.scope), (b.verdict, b.scope), (want.verdict, want.scope))
    finally:
        acr.GENERATED_DIR = saved_dir
        acr._ALL_ENTRY_RECORDS[:] = saved_cache
    check("VRP-S6 the record writers (apply_consensus_to_records, build_consensus_from_evidence) gather a page's "
          "reasons as the projection does: switch OFF they store INSUFFICIENT DATA for OBS 31.1.0, exactly as before; "
          "switch ON they store decide's verdict over the producer's candidates, so the stored prose never lags the "
          "page (the drift that never cleared)",
          got[False] == (("INSUFFICIENT DATA", ""),) * 3 and got[True][0] == got[True][1] == got[True][2]
          and got[True][0][0] == "WAIT", str(got))


_RENDER_RB = r"""
require 'liquid'
require 'json'
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
tpl = Liquid::Template.parse(payload["template"])
out = {}
payload["cases"].each do |name, c|
  out[name] = tpl.render!({ "rec" => c["rec"], "cnt" => c["cnt"], "site" => payload["site"] })
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""
PROBE = "@@{{ gate_label }}|{{ gate_scope }}|{{ gate_body }}|{{ gate_panel_heading }}|{{ gate_panel_text }}@@"
TEMPLATE_OVERRIDE: str | None = None


def render_gate(cases: dict, projection: dict) -> dict | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    text = TEMPLATE_OVERRIDE if TEMPLATE_OVERRIDE is not None else GATE_PATH.read_text(encoding="utf-8")
    template = text.replace("include.record", "rec").replace("include.count", "cnt") + PROBE
    with tempfile.TemporaryDirectory() as td:
        script, payload, out = Path(td) / "g.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload.write_text(json.dumps({"template": template, "site": {"data": {"verdict_projection": projection}},
                                       "cases": cases}, default=str), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-300:]}
        return json.loads(out.read_text(encoding="utf-8"))


def check_render_switch_on() -> None:
    recs = named_fixture() + [dict(KBP, update_type="2026-05 B")]
    counted = {vr.record_identity(recs[-1]): [R1, R2]}
    with switch(True):
        projection = vp.project(recs, counted, [], [])[0]
        valid, _u = vp.supported_reasons(recs, counted, [])
    targets = {"obs 31.1.0": recs[0], "obs 31.1.1": recs[1], "win 26100.9550": recs[7], "win 28000.2804": recs[9],
               "security install": recs[-1], "obs 32.0.3": recs[3]}
    cases = {k: {"rec": {f: r.get(f) for f in ("product_id", "update_version", "target_build")},
                 "cnt": int(r.get("update_report_count") or 0)} for k, r in targets.items()}
    out = render_gate(cases, projection)
    if out is None or "__error__" in out:
        check("VRP-S3 the real gate renders the switch-ON candidates", False, str(out)[:300])
        return
    got = {}
    for k in targets:
        m = re.search(r"@@(.*?)\|(.*?)\|(.*?)\|(.*?)\|(.*?)@@", out[k], re.S)
        got[k] = tuple(s.strip() for s in m.groups()) if m else None
    want = {}
    for k, r in targets.items():
        d = pd.decide(dict(r), valid_reasons=valid.get(vr.record_identity(r), []))
        want[k] = (d.verdict, d.scope, pd.public_body(d, r, int(r.get("update_report_count") or 0)),
                   pd.PANEL_HEADING.get(d.panel_kind, ""), pd.panel_text(d))
    check("VRP-S3 switch ON, the REAL gate prints each candidate's scoped verdict exactly as decide gives it: OBS "
          "31.1.0 WAIT, 31.1.1 TEST FIRST, the two named Windows pages WAIT, a security update keeps SECURITY "
          "UPDATE with the affected-configuration panel, and OBS 32.0.3 stays INSUFFICIENT DATA",
          got == want and [got[k][0] for k in targets] == ["WAIT", "TEST FIRST", "WAIT", "WAIT", "SECURITY UPDATE",
                                                           "INSUFFICIENT DATA"]
          and got["security install"][3] == "Affected configuration"
          and "Other setups: no problem is confirmed for them yet." in got["obs 31.1.0"][2],
          str({k: (got[k] or ("",))[:2] for k in targets})[:400])


def _write_tree(root: Path, recs: list, rows: list) -> None:
    gen = root / "updates" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(recs):
        (gen / f"r{i:02d}.md").write_text("---\n" + yaml.safe_dump(r, allow_unicode=True) + "---\nbody\n", encoding="utf-8")
    data = root / "_data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "consensus_evidence.yml").write_text(yaml.safe_dump({"schema_version": 1, "evidence": rows}), encoding="utf-8")
    (data / "verdict_reasons.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    (data / "patch_lifecycle.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")


def check_qa_switch(tmp: Path) -> None:
    import qa_patch_records as qa
    recs = named_fixture()
    tmp.mkdir(parents=True, exist_ok=True)
    _write_tree(tmp, recs, [])
    files = sorted((tmp / "updates" / "generated").glob("*.md"))
    saved = (qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH)
    proj_path = tmp / "_data" / vp.PROJECTION_NAME

    def scan():
        qa.REASONS_PATH = tmp / "_data" / "verdict_reasons.yml"
        qa.LIFECYCLE_PATH = tmp / "_data" / "patch_lifecycle.yml"
        qa.EVIDENCE_PATH = tmp / "_data" / "consensus_evidence.yml"
        qa.PROJECTION_PATH = proj_path
        try:
            return qa.scan_verdict_policy(files)
        finally:
            qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH = saved
    codes = lambda es: {e["code"] for e in es}  # noqa: E731
    off_projection = vp.project(recs, {}, [], [])[0]
    with switch(True):
        on_projection = vp.project(recs, {}, [], [])[0]
        proj_path.write_text(vp.render(on_projection), encoding="utf-8")
        e_on, _w = scan()
        proj_path.write_text(vp.render(off_projection), encoding="utf-8")
        e_stale, _w = scan()
    proj_path.write_text(vp.render(on_projection), encoding="utf-8")
    e_forged, _w = scan()
    proj_path.write_text(vp.render(off_projection), encoding="utf-8")
    e_off, _w = scan()
    check("VRP-S4 QA reads the same switch: ON, the deploy's candidate projection is clean and a projection built "
          "without the candidates is an ERROR; OFF, a projection carrying candidates is an ERROR (a forged or "
          "stale activation cannot publish) and the reviewed-only one is clean",
          on_projection["pages"] and not off_projection["pages"]
          and "verdict_render_disagrees" not in codes(e_on) and "verdict_render_disagrees" in codes(e_stale)
          and "verdict_render_disagrees" in codes(e_forged) and "verdict_render_disagrees" not in codes(e_off),
          f"on={codes(e_on)} stale={codes(e_stale)} forged={codes(e_forged)} off={codes(e_off)}")


def check_builder(tmp: Path) -> None:
    tree = tmp / "auxsays"
    _write_tree(tree, named_fixture(), [])
    out = tmp / "out" / vp.PROJECTION_NAME
    script = _AUX / "scripts" / "build_verdict_projection.py"
    proc = subprocess.run([sys.executable, str(script), "--root", str(tree), "--output", str(out)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    artifact = out.parent / vrp.ARTIFACT_NAME
    data = yaml.safe_load(artifact.read_text(encoding="utf-8")) if artifact.exists() else {}
    projection = yaml.safe_load(out.read_text(encoding="utf-8")) if out.exists() else {}
    ignored = (_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    check("VRP-S5 the deploy builder runs the producer where the projection is built and writes its candidates, "
          "refusals and review queue to the git-ignored artifact beside the projection (never a tracked file); "
          "with the switch OFF the projection beside it carries none of them",
          proc.returncode == 0 and data.get("public_auto_activation") is False
          and len(data.get("candidates") or []) == 10 and data.get("review_queue")
          and projection.get("pages") == {} and "auxsays/_data/verdict_reason_candidates.yml" in ignored
          and not (tree / "_data" / vrp.ARTIFACT_NAME).exists(),
          f"rc={proc.returncode} {proc.stdout[-300:]} {proc.stderr[-300:]}")


# ------------------------------------------------------------------------ [C] corpus

def check_corpus() -> None:
    c = corpus()
    res = c["produced"]
    recs = {r.get("permalink"): r for r in c["records"]}
    bad = []
    for x in res.candidates:
        rec = recs.get(x["page"])
        if rec is None or vr.record_identity(rec) != vr.reason_identity(x) or vrp.candidate_problems(x):
            bad.append(x["id"])
            continue
        if x["producer"]["class"] == vrp.VENDOR_CLASS:
            src = recs.get(x["citation"]["record"]) or {}
            body = re.sub(r"\s+", " ", str(src.get("official_patch_notes_body") or ""))
            if re.sub(r"\s+", " ", x["citation"]["statement"]) not in body:
                bad.append(x["id"])
        else:
            counted = {r.get("id") for r in c["groups"].get(vr.record_identity(rec), [])}
            if not {e["id"] for e in x["evidence"]} <= counted:
                bad.append(x["id"])
    check(f"VRP-C1 over the shipped corpus every candidate ({len(res.candidates)}) names a real page by its exact "
          "identity, passes its own schema, and rests on a statement stored verbatim on the cited record or on "
          "rows counted on that very page", res.candidates and not bad, str(bad[:3]))
    install_only = vrp.ProducerResult()
    install_only.candidates = [x for x in res.candidates if x["producer"]["class"] == vrp.INSTALL_CLASS]
    agree = vrp.agreement_with_reviewed(install_only, c["reasons"])
    install = [a for a in agree if a["reason_class"] == "corroborated_install_problem"]
    refused_pages = {(e.get("product_id"), e.get("update_version"), e.get("target_build", ""))
                     for e in res.excluded if e["class"] == vrp.INSTALL_CLASS}
    install_c = [x for x in res.candidates if x["producer"]["class"] == vrp.INSTALL_CLASS]
    # Every page the install class had to judge (>= 2 counted rows reporting THIS update failing) ends as a
    # candidate or a recorded refusal: the corpus check cannot pass vacuously with no candidate.
    judged = set()
    for rec_ in c["records"]:
        pid = rec_.get("product_id")
        rows_ = c["groups"].get(vr.record_identity(rec_), [])
        if rec_.get("update_entry", True) is False:
            continue
        if pid == WIN and rec_.get("target_kb") and rec_.get("target_build"):
            n_ok = sum(vrp.windows_install_row(r, rec_)["ok"] for r in rows_)
        elif pid in vrp.ACROBAT:
            n_ok = sum(vrp.acrobat_install_row(r, pid)["ok"] for r in rows_)
        else:
            continue
        if n_ok >= vrp.MIN_INDEPENDENT_REPORTERS:
            judged.add(vr.record_identity(rec_))
    outcome = {vr.reason_identity(x) for x in install_c} | refused_pages
    reviewed_by_id = {r.get("id"): r for r in c["reasons"]}
    reviewed_ident = {a["entry"]: vr.reason_identity(reviewed_by_id[a["entry"]]) for a in install}
    reviewed_judged = [e for e, ident in reviewed_ident.items() if ident in judged]
    unexplained = [a["entry"] for a in install if a["producer"] == "abstains"
                   and reviewed_ident[a["entry"]] in judged and reviewed_ident[a["entry"]] not in refused_pages]
    check("VRP-C2 against the reviewed install entries the producer agrees or abstains, never contradicts, and "
          f"proposes no other install verdict or scope on any reviewed page; on each of the {len(reviewed_judged)} "
          "reviewed pages with two or more install rows to judge, an abstention carries a recorded install refusal "
          "(not enough independent reports, or no shared specific error), never silence. With independence resting "
          "on identity details only and Acrobat grouped on the specific installer error it reproduces none of the 4 "
          "today; the calibration's 3/4 was the lenient, assumed-independent reading",
          not any(a["producer"] == "differs" for a in agree) and len(install) == 4 and reviewed_judged
          and not unexplained, f"unexplained={unexplained} judged={reviewed_judged} {str(agree)[:300]}")
    unproven = []
    for x in install_c:
        rows = {r.get("id"): r for r in c["groups"].get(vr.reason_identity(x), [])}
        cited = [rows[e["id"]] for e in x["evidence"] if e["id"] in rows]
        pairs = [(a, b) for i, a in enumerate(cited) for b in cited[i + 1:]]
        if len(cited) < 2 or not x["independence_basis"] or not x["problem_key"] or not all(
                vrp.distinct_incident({"details": vrp.incident_details(a, x["product_id"]),
                                       "reporter_ids": vrp._reporter_ids(a)},
                                      {"details": vrp.incident_details(b, x["product_id"]),
                                       "reporter_ids": vrp._reporter_ids(b)}) for a, b in pairs):
            unproven.append(x["id"])
    vendor_waits = [x for x in res.candidates if x["verdict"] == "WAIT"]
    check(f"VRP-C3 over the shipped corpus every install candidate ({len(install_c)}) rests on reports of ONE "
          "problem (a shared characteristic) whose every pair the source shows to be separate machines, never on "
          f"an assumed second reporter, and every one of the {len(judged)} pages with two or more rows reporting "
          "their update failing to install ends as a candidate or a recorded refusal; every WAIT is a "
          "vendor-confirmed defect new in that version",
          not unproven and judged and judged == outcome
          and all(x["producer"]["class"] == vrp.VENDOR_CLASS and x["new_in_this_version"] for x in vendor_waits),
          f"unproven={unproven[:3]} judged-only={sorted(judged - outcome)[:3]} "
          f"outcome-only={sorted(outcome - judged)[:3]}")


# ------------------------------------------------------------------------ [X] mutants

def run_mutant(label: str, body, mutants: list, *, mutate, restore) -> None:
    try:
        with captured() as baseline:
            body()
    except Exception as exc:  # noqa: BLE001
        mutants.append((label, [], f"baseline raised {type(exc).__name__}: {exc}"))
        return
    mutate()
    try:
        with captured() as failures:
            body()
    except Exception as exc:  # noqa: BLE001
        mutants.append((label, [], f"{type(exc).__name__}: {exc}"))
        return
    finally:
        restore()
    mutants.append((label, [f for f in failures if f not in set(baseline)], ""))


def swap(owner, name, replacement):
    original = getattr(owner, name)
    return (lambda: setattr(owner, name, replacement)), (lambda: setattr(owner, name, original))


NEVER = re.compile(r"(?!x)x")  # a pattern that matches nothing: a check switched off


def head_class_other_setups(real):
    """The first increment's rule: the vendor line whenever the HEAD reason is a vendor one."""
    def mutated(decision, record, report_count):
        body = real(decision, record, report_count)
        head = decision.reasons[0] if decision.reasons else {}
        vendor_line = pd.OTHER_SETUPS_BY_CLASS.get(str(head.get("reason_class") or ""))
        if vendor_line and body.endswith(pd.OTHER_SETUPS):
            body = body[: -len(pd.OTHER_SETUPS)] + vendor_line
        return body
    return mutated


def build_alone_mentions(real):
    """The first increment's rule: the page's build anywhere in the row names the update."""
    def mutated(text, page):
        build = str(page.get("target_build") or "")
        extra = [(m.start(), m.end()) for m in re.finditer(re.escape(build), text)] if build else []
        return sorted(set(real(text, page)) | set(extra))
    return mutated


def all_codes(real):
    """The first increment's rule: every 0x code in a qualifying row is this update's."""
    def mutated(row, page):
        got = real(row, page)
        if got["ok"]:
            got = dict(got, codes=sorted({c for c in vrp._CODE_RX.findall(vrp._txt(row)) if c[2:].lstrip("0")}))
        return got
    return mutated


def similarity_ignores_conflicts(real):
    """Before AUX-099: text similarity merged two rows whatever their details said."""
    def mutated(a, b, product_id=""):
        why = real(a, b, product_id)
        if why:
            return why
        ta, tb = vrp._content_tokens(a), vrp._content_tokens(b)
        if ta | tb and len(ta & tb) / len(ta | tb) >= vrp.INDEPENDENCE_JACCARD:
            return "near-identical text once templates are stripped"
        return ""
    return mutated


def uncertain_drafted(real):
    """Before AUX-099: 'a possible crash' was drafted like any other."""
    def mutated(statement):
        got = real(statement)
        if got.get("excluded") == "uncertain_severity" and got.get("severity"):
            return {k: v for k, v in got.items() if k not in ("excluded", "note")}
        return got
    return mutated


def freeze_needs_no_core_flow(real):
    """Before the G38 WS2 review (LOW-1): every freeze or hang was substantial workflow breakage."""
    def mutated(statement):
        got = real(statement)
        head = vrp._OBS_HEAD_RE.match(re.sub(r"\s+", " ", statement).strip())
        if got.get("excluded") == "no_severity_basis" and head and head.group("kind").lower() in ("freeze", "hang"):
            when = vrp._WHEN_RE.search(statement)
            return {"severity": "substantial_workflow_breakage", "failure_kind": head.group("kind").lower(),
                    "scope": f"when {when.group(1).strip()}" if when else ""}
        return got
    return mutated


def exit7_grouping(real):
    """Before the G38 WS2 review (MAJOR-3): Acrobat rows grouped on the generic installer Exit Code 7."""
    def mutated(rows, mode=""):
        groups = real(rows, mode)
        acrobat = [r for r, info in rows if info.get("acrobat")]
        if acrobat and (mode or vrp.INSTALL_GROUPING) == "strict":
            groups["installer exit code 7"] = acrobat
        return groups
    return mutated


# The persistence and declared-copy patterns as round 1 of AUX-099 shipped them (the phrase lists the review broke).
OLD_PERSISTENT_RE = re.compile(
    r"\b(?:and (?:earlier|older|prior|before)|or (?:earlier|older)|(?:and|or) (?:all )?(?:previous|prior|older|earlier) "
    r"(?:versions?|releases?|builds?|updates?)|since\b|regression (?:from|since)|also affect\w*|still (?:present|"
    r"occur\w*|happen\w*)|persist\w*|carried over|long-?standing|pre-?existing)", re.I)
OLD_XPOST_RX = re.compile(r"(previously posted|also posted|cross-?post|posted (?:this|it) (?:on|in)|i recently posted|"
                          r"part 2|part two)")


def check_mutations(tmp: Path) -> None:
    real_obs, real_win = vrp.classify_obs_statement, vrp.classify_windows_issue
    real_statements, real_produce = vrp._obs_statements, vrp.produce
    real_problems = vrp.candidate_problems
    gated = {"minor_lag", "narrow_cosmetic", "recoverable_preference_or_profile", "no_severity_basis"}

    def acrobat_exit7_only(row, pid):
        """The Acrobat row check reduced to 'Exit Code 7 is shown' (no product, negation or other-product check)."""
        text = vrp._txt(row)
        return {"ok": bool(vrp._EXIT7_RX.search(text)), "why": "",
                "codes": sorted({c.upper() for c in vrp._ADOBE_INSTALLER_CODE_RX.findall(text)})}

    def no_severity_gate(fn):
        def mutated(text):
            r = fn(text)
            if r.get("excluded") in gated:
                return {"severity": "substantial_workflow_breakage", "failure_kind": "x", "title": r.get("title", text),
                        "scope": "if you use the Audio Mixer"}
            return r
        return mutated

    def version_inferred(records):
        """The exact-version check removed: a bullet that names no version is attributed to the release
        just before the one whose notes carry it -- the inference the rule forbids."""
        out = real_statements(records)
        order = sorted((r for r in records if r.get("product_id") == OBS),
                       key=lambda r: str(r.get("update_published_at") or ""))
        versions = [str(r.get("update_version")) for r in order]
        for st in out:
            if not st["named"] and st["fixed_in"] in versions and versions.index(st["fixed_in"]) > 0:
                st["named"] = [versions[versions.index(st["fixed_in"]) - 1]]
        return out

    def with_network(records, counted):
        import urllib.request  # noqa: PLC0415 - the mutant's whole point
        try:
            # An IP literal from TEST-NET-1 (RFC 5737): no DNS lookup; VRP-N1's guard refuses the connect.
            urllib.request.urlopen("http://192.0.2.1/known-issues", timeout=2)
        except Exception:  # noqa: BLE001
            pass
        return real_produce(records, counted)

    cases = [
        ("VX1 the severity gate removed (lag, cosmetic, preference and unrecognised defects pass)", check_vendor,
         [swap(vrp, "classify_obs_statement", no_severity_gate(real_obs)),
          swap(vrp, "classify_windows_issue", no_severity_gate(real_win))]),
        ("VX2 the exact-version check removed (a version-less bullet is attributed to the release before)",
         check_vendor, [swap(vrp, "_obs_statements", version_inferred)]),
        ("VX3 the scope requirement dropped (an unscoped candidate is proposed)", check_vendor,
         [swap(vrp, "_scope_ok", lambda scope, product_id="": True)]),
        ("VX4 the activation switch default flipped to ON", lambda: check_switch(tmp / f"x4"),
         [swap(vrp, "PUBLIC_AUTO_ACTIVATION", True)]),
        ("VX5 a network call added to the producer", check_purity, [swap(vrp, "produce", with_network)]),
        ("VX6 the independence gate removed (every qualifying row is a reporter)", check_install,
         [swap(vrp, "independent_reporters", lambda rows, product_id="": (sorted(rows, key=lambda r: str(r.get("id"))),
                                                                          []))]),
        ("VX7 the reporter threshold lowered to one", check_install, [swap(vrp, "MIN_INDEPENDENT_REPORTERS", 1)]),
        ("VX8 the Acrobat product check removed (a Pro row counts on the Reader page)", check_install,
         [swap(vrp, "acrobat_install_row", acrobat_exit7_only)]),
        ("VX9 an install failure may be WAIT", check_install,
         [swap(vrp, "candidate_problems", lambda e: [p for p in real_problems(e) if not p.startswith("WAIT")])]),
        ("VX10 the placeholder counts two different URLs as independent", check_placeholder,
         [swap(vrp, "rows_are_independent", lambda a, b, incident_independence=None:
               a.get("source_url") != b.get("source_url"))]),
        # Review 1: one mutant per fix half.
        ("VX11 the setup-word requirement removed (any 'if / when / for ...' phrase is a setup)", check_vendor_scope,
         [swap(vrp, "_SCOPE_GENERIC_WORDS", frozenset())]),
        ("VX12 the product's own name counts as a setup ('if you use OBS')", check_vendor_scope,
         [swap(vrp, "_PRODUCT_WORDS", {})]),
        ("VX13 an OBS version anywhere in a fix note names the defective version ('created in V')", check_vendor_scope,
         [swap(vrp, "_OBS_NAMED_RE", re.compile(
             r"\b(?:in|present in) (?:OBS Studio )?(\d+\.\d+\.\d+)((?:(?:,|,? and) (?:OBS Studio )?\d+\.\d+\.\d+)*)"
             r"|(?!x)x(\d)(\d)", re.ASCII))]),
        ("VX14 the Windows minor-lag exclusion removed", check_vendor_scope,
         [swap(vrp, "_WIN_LAG_RE", NEVER)]),
        ("VX15 the vendor 'other setups' line beside user reports (the first increment's head-class rule)",
         check_vendor_body, [swap(pd, "public_body", head_class_other_setups(pd.public_body))]),
        ("VX16 the install-denial guard removed", check_install_rows, [swap(vrp, "_INSTALL_NEGATION_RX", NEVER)]),
        ("VX17 a build alone names the update again", check_install_rows,
         [swap(vrp, "_page_mentions", build_alone_mentions(vrp._page_mentions))]),
        ("VX18 'check for updates' / 'rolls back to' read as install failures again", check_install_rows,
         [swap(vrp, "_NOT_AN_INSTALL_RX", NEVER)]),
        ("VX19 install wording beside ANOTHER update counts for this one", check_install_rows,
         [swap(vrp, "_owner_is_page", lambda span, page_spans, other_spans: True)]),
        ("VX20 every error code in the row is listed for this update", check_install_rows,
         [swap(vrp, "windows_install_row", all_codes(vrp.windows_install_row))]),
        ("VX21 the near-identical-text cue (I10) disabled", check_install_rows,
         [swap(vrp, "INDEPENDENCE_JACCARD", 0.99)]),
        # Review 2 (MAJOR-1): one mutant per half of the hedge rule.
        ("VX22 a hedge word ('some', 'certain', 'specific', 'regions' ...) no longer makes a scope vague",
         check_vendor_scope, [swap(vrp, "_SCOPE_HEDGE_WORDS", frozenset())]),
        ("VX23 'a small / limited number of ...' no longer makes a scope vague", check_vendor_scope,
         [swap(vrp, "_SCOPE_HEDGE_PHRASE_RE", NEVER)]),
        ("VX24 'environments' counts as a setup whatever stands before it", check_vendor_scope,
         [swap(vrp, "_names_environment_type", lambda word, generic: True)]),
        ("VX25 'environments' is vague even after a named type ('virtual desktop environments')", check_vendor_scope,
         [swap(vrp, "_names_environment_type", lambda word, generic: False)]),
        # AUTH_V2_38 WS2 (AUX-099): one mutant per fix half.
        ("VX26 (item 3) an unknown second reporter counts: independence is assumed, not established",
         check_independence, [swap(vrp, "distinct_incident", lambda a, b, product_id="": "assumed")]),
        ("VX27 (item 2) similarity collapses incidents whose details conflict (conservative grouping off)",
         check_independence, [swap(vrp, "same_reporter", similarity_ignores_conflicts(vrp.same_reporter))]),
        ("VX28 (item 1) the shared-distinctive-passage cue disabled (a reworded re-post goes undetected)",
         check_independence, [swap(vrp, "SHARED_PASSAGE_WORDS", 10 ** 6)]),
        ("VX29 (item 4) the install verb's subject is not checked (another program failing counts)",
         check_install_subject, [swap(vrp, "_install_subject", lambda text, span, refs, page_spans, other_spans:
                                      vrp._owner_is_page(span, page_spans, other_spans))]),
        ("VX30 (item 4) a crash or bugcheck code is read as an install error", check_install_subject,
         [swap(vrp, "_CRASH_CONTEXT_RX", NEVER)]),
        ("VX31 (item 4) updates named together: only the nearest one counts", check_install_subject,
         [swap(vrp, "_coordinated", lambda text, refs, i, step: refs[i][2])]),
        ("VX32 (item 5) lenient grouping by default: different error codes are one problem again",
         check_install_grouping, [swap(vrp, "INSTALL_GROUPING", "lenient")]),
        ("VX33 (item 6) an OBS defect 'in V and earlier' / 'since' is new in V again", check_vendor_persistence,
         [swap(vrp, "_PERSISTENT_RE", NEVER)]),
        ("VX34 (item 6) a Microsoft issue that also affects earlier updates originates in this one again",
         check_vendor_persistence, [swap(vrp, "_WIN_PERSISTENT_RE", NEVER)]),
        ("VX35 (item 7) an OBS crash needs no core-workflow cue", check_vendor_persistence,
         [swap(vrp, "_OBS_CORE_FLOW_RE", re.compile(""))]),
        ("VX36 (item 7) a crash while logging or in a dialog counts as a core-flow crash", check_vendor_persistence,
         [swap(vrp, "_OBS_NOT_CORE_RE", NEVER)]),
        ("VX37 (item 7) a possible / rare crash is drafted instead of queued", check_vendor_persistence,
         [swap(vrp, "classify_obs_statement", uncertain_drafted(vrp.classify_obs_statement))]),
        ("VX38 (item 3) a different source reporter id is not a different reporter", check_install,
         [swap(vrp, "_reporter_ids", lambda row: frozenset())]),
        ("VX39 (item 8) the record writers read reviewed reasons only again (the drift never clears)",
         lambda: check_writers(tmp / "x39"),
         [swap(vp, "page_supported_reasons", lambda page, rows, reviewed_valid, records=():
               [dict(e) for e in reviewed_valid])]),
        # G38 WS2 review of AUX-099 (round 2): one mutant per fix.
        ("VX40 (items 1/3, MAJOR-1) a failure point or an OS version separates two reports again",
         check_one_machine, [swap(vrp, "IDENTITY_DETAIL_KINDS",
                                  vrp.IDENTITY_DETAIL_KINDS + vrp.COPY_ONLY_DETAIL_KINDS)]),
        ("VX41 (item 1, MAJOR-1) a declared follow-up or re-post is not a declared copy (round 1's cue list)",
         check_one_machine, [swap(vrp, "_XPOST_RX", OLD_XPOST_RX)]),
        ("VX42 (item 2, P2b) a detail-less third row bridges two machines into one report",
         check_copy_clusters, [swap(vrp, "_may_join", lambda why, a, b: True)]),
        ("VX43 (item 2) overlapping identity details ('my Dell' / 'my Dell and my HP') count as two machines",
         check_copy_clusters, [swap(vrp, "_conflicting", lambda a, b: [
             k for k in vrp.IDENTITY_DETAIL_KINDS if a.get(k) and b.get(k) and a[k] != b[k]])]),
        ("VX44 (item 4, MAJOR-2) the install verb's OBJECT is not read (other software failing counts)",
         check_install_subject, [swap(vrp, "_FOREIGN_OBJECT_RX", NEVER)]),
        ("VX45 (item 4, MAJOR-2) an Acrobat row saying the version installed counts", check_acrobat_rows,
         [swap(vrp, "_ACROBAT_NEGATION_RX", NEVER)]),
        ("VX46 (item 4, MAJOR-2) another Adobe product's Exit Code 7 counts for Acrobat", check_acrobat_rows,
         [swap(vrp, "_ADOBE_OTHER_PRODUCT_RX", NEVER)]),
        ("VX47 (item 5, MAJOR-3) Acrobat rows group on the generic Exit Code 7 again", check_acrobat_rows,
         [swap(vrp, "install_groups", exit7_grouping(vrp.install_groups))]),
        ("VX48 (item 6, MAJOR-4) an older OBS version named anywhere in a bullet is not carry-over",
         check_vendor_persistence, [swap(vrp, "_ANY_VERSION_RE", NEVER)]),
        ("VX49 (item 6, MAJOR-4) persistence is round 1's phrase list ('earlier' / 'previous' anywhere is new)",
         check_vendor_persistence, [swap(vrp, "_PERSISTENT_RE", OLD_PERSISTENT_RE)]),
        ("VX50 (item 6) a causal 'since' reads as carry-over", check_vendor_persistence,
         [swap(vrp, "_PERSISTENT_RE", re.compile(vrp._PERSISTENT_RE.pattern + r"|\bsince\b", re.I))]),
        ("VX51 (item 7, LOW-1) a freeze or hang needs no core-workflow cue", check_vendor_persistence,
         [swap(vrp, "classify_obs_statement", freeze_needs_no_core_flow(vrp.classify_obs_statement))]),
    ]
    mutants: list = []
    for label, body, swaps in cases:
        run_mutant(label, body, mutants, mutate=lambda s=swaps: [m() for m, _r in s],
                   restore=lambda s=swaps: [r() for _m, r in s])
    for label, failures, crash in mutants:
        check(f"{label} -> caught", bool(failures),
              f"mutant crashed instead of being caught: {crash}" if crash else "no NAMED check failed")
        if failures:
            print(f"        caught by: {', '.join(sorted(failures)[:3])}")


# ------------------------------------------------------------------------ the suite

def run() -> int:
    print("=" * 78)
    print("G35-04 VERDICT-REASON PRODUCER")
    print("=" * 78)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print("\n[V] vendor_confirmed_serious, on frozen copies of the stored statements")
        check_vendor()
        check_vendor_scope()
        check_vendor_body()
        check_vendor_persistence()
        print("\n[I] user-corroborated install failures and the independence gate")
        check_install()
        check_install_rows()
        check_independence()
        check_install_subject()
        check_install_grouping()
        check_acrobat_rows()
        check_one_machine()
        check_copy_clusters()
        print("\n[P] the corroboration placeholder")
        check_placeholder()
        print("\n[N] purity")
        check_purity()
        print("\n[S] the activation switch and the integration")
        check_switch(tmp / "s")
        print("\n[C] the shipped corpus")
        check_corpus()
        print("\n[X] mutants, each caught by a named check")
        check_mutations(tmp)
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
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
