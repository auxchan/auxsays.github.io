#!/usr/bin/env python3
"""DaVinci, OBS and PowerPoint classify from what the report says, through the shared classifier.

`issue_theme` is published prose ("Current reports mention <theme>") and `platform` is stored on
every evidence row. These three collectors still ran the substring chains AUX-041 retired for
Adobe. Reproduced against the shipped functions, on text quoted verbatim from counted rows:

    OBS  "VLC Source: Shuffle/Random option does not re-randomize ... on scene change"
                                                         -> freeze / hang   ("hang" in "change")
    OBS  "starting OBS (flatpak) spawns numerous small windows", Other OS: Ubuntu 22.04
                                                         -> platform: windows (a UI noun)
    OBS  "Other OS: Arch Linux and Windows 10"           -> platform: windows (two platforms)
    DaVinci "[Linux] DaVinci Resolve can't open existing projects"
                                                         -> platform: windows
    DaVinci "... segfault at GPUDetect ..."              -> performance regression ("gpu")
    PowerPoint, any text                                 -> platform: windows (a literal)

WHY THE FIXTURES ARE FROZEN. The governed manifest compares this suite's total to an exact `= N`,
so a walk of the live store would make the count a function of the store. The texts below are held
still. Offline: no network, no repo writes, no read of the evidence store.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import collect_obs_reports as obs                                    # noqa: E402
from lib import evidence_classification as ec                        # noqa: E402
from patch_collectors import davinci                                 # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt             # noqa: E402

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


def obs_issue(title: str, body: str, labels: tuple[str, ...] = ()) -> dict:
    return {"title": title, "body": body, "labels": [{"name": name} for name in labels]}


# --- verbatim fixtures (counted rows) -----------------------------------------------------------

DV_LINUX_TAG = ("[Linux] DaVinci Resolve can't open existing projects",
                "[Linux] DaVinci Resolve can't open existing projects I'm currently trying to switch "
                "from Windows to Linux, so I'm also trying to get DaVinci Resolve to run on Linux. "
                "It's a bit shaky, but after a few attempts, I've gotten pretty decent results so far. "
                "I currently have Fedora...")
DV_SEGFAULT = ("DaVinci Resolve Studio 20.3.2 segfault on startup — RX 6700 XT, Linux Mint 22.2",
               "Sup gang, I keep getting a consistent segfault at GPUDetect on every time I launch which "
               "is preventing me to even get to the edit page.")
DV_SPECS = ("Audio doesn't work at all",
            "System specifications: Windows RTX 5060 8GB Ryzen 5 5500G DaVinci Resolve 21.0.1 Hello,")
DV_SPLINE = ("I cannot open my Spline window in Fusion",
             "Dual Screen doesn't work or just spawned new Spline windows whenever it felt like it and "
             "now I can't get the Spline window back")

OBS_TAHOE = obs_issue("[macOS 26 Tahoe] OBS crashes with EXC_BAD_ACCESS in libqcocoa.dylib", "")
OBS_FLATPAK = obs_issue("starting OBS (flatpak) spawns numerous small windows",
                        "### Operating System Info Other ### Other OS Ubuntu 22.04 ### OBS Studio Version "
                        "32.1.1 ### OBS Studio Version (Other) flatpak")
OBS_TWO_OS = obs_issue("OBS Dock size issue",
                       "Operating System Info Other ### Other OS Arch Linux and Windows 10 ### OBS Studio "
                       "Version 32.1.1")
OBS_SCENE_CHANGE = obs_issue(
    "VLC Source: Shuffle/Random option does not re-randomize or update from disk on scene change",
    "### Operating System Info Windows 11 ### Other OS _No response_ ### OBS Studio Version 32.1.1")
OBS_MONETIZATION = obs_issue(
    "Streaming stops after changing monetization settings on YouTube (OBS shows streaming, but no "
    "video received)", "")


def run_suite() -> int:
    print("[A] DaVinci platform: positive OS evidence, title tags kept")
    check("A1 a '[Linux]' title tag is the reporter's platform (was: windows)",
          davinci.classify(*DV_LINUX_TAG)[2] == "linux", str(davinci.classify(*DV_LINUX_TAG)))
    check("A2 'Linux Mint 22.2' in the title is linux",
          davinci.classify(*DV_SEGFAULT)[2] == "linux", str(davinci.classify(*DV_SEGFAULT)))
    check("A3 'System specifications: Windows' is OS evidence",
          davinci.classify(*DV_SPECS)[2] == "windows", str(davinci.classify(*DV_SPECS)))
    check("A4 Fusion's 'Spline windows' is a UI noun, not Windows",
          davinci.classify(*DV_SPLINE)[2] == "unknown", str(davinci.classify(*DV_SPLINE)))
    check("A5 'machine' does not read as macOS",
          davinci.classify("Resolve 20 render issue", "my machine renders it slowly")[2] == "unknown")

    print("[B] OBS platform")
    check("B1 a '[macOS 26 Tahoe]' title tag is macos (was: windows)",
          obs.classify(OBS_TAHOE)[2] == "macos", str(obs.classify(OBS_TAHOE)))
    check("B2 Flatpak on Ubuntu 22.04 is linux, its 'small windows' a UI noun (was: windows)",
          obs.classify(OBS_FLATPAK)[2] == "linux", str(obs.classify(OBS_FLATPAK)))
    check("B3 'Arch Linux and Windows 10' names two platforms: unknown (was: windows)",
          obs.classify(OBS_TWO_OS)[2] == "unknown", str(obs.classify(OBS_TWO_OS)))
    check("B4 a maintainer's platform/windows label is OS evidence",
          obs.classify(obs_issue("Hotkeys stop working", "", ("platform/windows",)))[2] == "windows")

    print("[C] PowerPoint platform: definitional, never asserted against the text")
    check("C1 no OS named: the Click-to-Run build establishes windows",
          ppt.classify("PowerPoint crashes when presenting", "since the update")[2] == "windows")
    check("C2 a report naming only macOS reads unknown, not windows",
          ppt.classify("Crash on Mac", "PowerPoint on macOS Sonoma crashes")[2] == "unknown")
    check("C3 a report naming Windows stays windows",
          ppt.classify("Eyedropper on windows cannot pick a color from a taskpane add-in", "")[2] == "windows")
    check("C4 the definitional platform is stated, not a literal on every branch",
          ppt.POWERPOINT_DEFINITIONAL_PLATFORM == "windows")

    print("[D] theme: word boundaries, the title weighted")
    check("D1 'scene change' is not a freeze (was: freeze / hang)",
          obs.classify(OBS_SCENE_CHANGE)[0] != "freeze / hang", str(obs.classify(OBS_SCENE_CHANGE)))
    check("D2 'changing monetization settings' is not a freeze (was: freeze / hang)",
          obs.classify(OBS_MONETIZATION)[0] != "freeze / hang", str(obs.classify(OBS_MONETIZATION)))
    check("D3 'GPUDetect' is not a GPU-performance report (was: performance regression)",
          davinci.classify(*DV_SEGFAULT)[0] != "performance regression", str(davinci.classify(*DV_SEGFAULT)))
    check("D4 PowerPoint: 'changed' is not a hang",
          ppt.classify("Unreliable Document Settings", "the settings I changed do not stick")[0]
          != "crash or hang")
    check("D5 a real OBS freeze still themes as one",
          obs.classify(obs_issue("GIFs from EmoteLab freeze every second", ""))[0] == "freeze / hang")
    check("D6 the title outweighs body mentions: an OBS camera title is a camera report",
          obs.classify(obs_issue("OBS Camera black screen but works fine in Windows Camera app", ""))[0]
          == "camera/source regression")

    print("[E] negation: a denied symptom does not score")
    check("E1 DaVinci 'no crash since 20.3' is not a crash report",
          davinci.classify("Timeline playback stutters", "there is no crash since 20.3, just stutter")[0]
          != "startup or application crash")
    check("E2 OBS 'no freeze' is not a freeze report",
          obs.classify(obs_issue("Preview stays black", "there is no freeze, the preview is just black"))[0]
          != "freeze / hang")

    print("[F] sentiment is exactly what the replaced chain returned")
    check("F1 OBS: a theme corrected to the fallback keeps the old chain's negative",
          obs.classify(OBS_SCENE_CHANGE)[0] == "unspecified issue"
          and obs.classify(OBS_SCENE_CHANGE)[4] == "negative", str(obs.classify(OBS_SCENE_CHANGE)))
    check("F2 DaVinci: the same, for 'GPUDetect'",
          davinci.classify(*DV_SEGFAULT)[4] == "negative", str(davinci.classify(*DV_SEGFAULT)))
    check("F3 DaVinci: no trigger at all is moderate, as before",
          davinci.classify("Use Tracker data independently", "how do I reuse tracker data")[4] == "moderate")
    check("F4 PowerPoint: the fallback is negative, as every old branch was",
          ppt.classify("Copilot Unable to Read Document Error", "")[4] == "negative")

    print("[G] vocabulary: the published themes, areas and severities are the old chains'")
    legacy_davinci = {("magic mask crash", "color grading / Magic Mask", "high"),
                      ("startup or application crash", "application stability", "high"),
                      ("render/export failure", "render/export", "medium"),
                      ("performance regression", "timeline / GPU performance", "medium"),
                      ("compatibility issue", "plugins / codecs", "medium"),
                      ("install issue", "installation", "medium")}
    legacy_obs = {("crash / stability", "application stability", "high"),
                  ("screen capture regression", "screen/window capture", "high"),
                  ("visual capture artifact", "display capture / HDR workflow", "medium"),
                  ("audio mixer regression", "audio mixer UI", "medium"),
                  ("hotkey regression", "keyboard shortcuts", "medium"),
                  ("camera/source regression", "camera source workflow", "medium"),
                  ("output configuration regression", "output settings", "medium"),
                  ("freeze / hang", "application stability", "high"),
                  ("plugin compatibility", "plugins", "medium")}
    legacy_ppt = {("file corruption / data loss", "file integrity", "critical"),
                  ("save failure", "save / storage", "high"), ("launch / open failure", "startup", "high"),
                  ("slideshow failure", "presenting", "high"), ("export failure", "export", "high"),
                  ("animation / transition regression", "animation", "medium"),
                  ("add-in incompatibility", "add-ins", "medium"),
                  ("rendering regression", "rendering", "medium"),
                  ("performance regression", "performance", "medium"),
                  ("install/update failure", "update", "high"),
                  ("crash or hang", "system stability", "high")}
    for name, rules, legacy in (("G1 DaVinci", davinci._DAVINCI_THEME_RULES, legacy_davinci),
                                ("G2 OBS", obs._OBS_THEME_RULES, legacy_obs),
                                ("G3 PowerPoint", ppt._POWERPOINT_THEME_RULES, legacy_ppt)):
        found = {(rule.theme, rule.area, rule.severity) for rule in rules}
        check(f"{name} table is exactly the old vocabulary, every severity valid",
              found == legacy and all(rule.severity in ec.VALID_SEVERITIES for rule in rules),
              str(found ^ legacy))

    print("[H] the shared resolver's heading is read unscrubbed; the body still is")
    check("H1 a bracketed title tag is platform evidence",
          ec.resolve_platform("", heading="[Linux] Resolve can't open projects").label == "linux")
    check("H2 the same bracket in a BODY is still an unfilled template",
          ec.resolve_platform("OS: [Linux]").label == "unknown")
    check("H3 DaVinci classify takes (heading, body): the one-blob call is refused",
          _single_argument_call_is_refused())
    check("H4 a title opening 'Windows:' is the platform (a counted OBS row)",
          obs.classify(obs_issue("Windows: since 32.2.0, plugins whose dependencies are found via PATH "
                                 "no longer load", ""))[2] == "windows")
    not_responding = davinci.classify(
        "Davinci not responding - Mac Studio M3 Ultra",
        "Since changing to a Mac Studio M3 Ultra, when starting up DR Studio 20.2.3 it is very slow and "
        "often not responding, also crashes sometimes.")
    check("H5 'not responding' asserts a failure: it does not deny the 'crashes' after it",
          not_responding[0] == "startup or application crash", str(not_responding))

    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


def _single_argument_call_is_refused() -> bool:
    try:
        davinci.classify("one concatenated blob")  # type: ignore[call-arg]
    except TypeError:
        return True
    return False


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
