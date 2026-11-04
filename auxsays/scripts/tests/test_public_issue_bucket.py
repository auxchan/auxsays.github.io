#!/usr/bin/env python3
"""The OBS public issue bucket reads words, not substrings, in both publication bucketers.

The public bucket is what a patch page prints ("Current reports mention <bucket>") and what each
accepted report's issue label says. Two copies compute it --
apply_consensus_to_records._public_issue_bucket (the record writer) and
build_consensus_from_evidence.public_issue_bucket (the reconcile builder) -- and both re-read the
stored theme, workflow area and report TITLE. After AUX-058/059 corrected the stored themes, the
OBS branch still matched two cues as substrings. Reproduced against the shipped functions, on
counted rows quoted verbatim:

    "Opening Image Source Properties or changing image file causes rendering lag ..."
                                       -> crash or stability problems   ("hang" in "changing")
    "VLC Source: Shuffle/Random option does not re-randomize ... on scene change"
                                       -> crash or stability problems   ("hang" in "change")
    "Windows: since 32.2.0, plugins whose dependencies are found via PATH no longer load"
                                       -> capture-source issues         ("window" in "Windows")

The OBS 31.1.2 page published "crash or stability problems" from the word "changing" alone.

WHY THE FIXTURES ARE FROZEN. The governed manifest compares this suite's total to an exact `= N`.
Every check below is over held-still text except E2, which is ONE check over the counted OBS
population: the two copies must agree on every row, which holds by construction for any store.
Offline: no network, no repo writes.
"""
from __future__ import annotations

import sys
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_consensus_to_records as writer                          # noqa: E402
import build_consensus_from_evidence as builder                      # noqa: E402
from lib import live_eligibility                                     # noqa: E402

OBS = "obs-studio"
CRASH = "crash or stability problems"
CAPTURE = "capture-source issues"
PLUGIN = "plugin or setup compatibility"
GENERAL = "general workflow reports"

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


def row(theme: str, area: str, title: str) -> dict:
    return {"product_id": OBS, "issue_theme": theme, "workflow_area": area, "report_title": title}


# --- verbatim fixtures (counted rows, stored fields as of AUX-059) -------------------------------

IMAGE_SOURCE_GH = row("unspecified issue", "general OBS workflow",
                      "Opening Image Source Properties or changing image file causes rendering lag and "
                      "skipped rendering frames on macOS (Apple Silicon)")
IMAGE_SOURCE_FORUM = row("unspecified issue", "general OBS workflow",
                         "Image Source causes rendering lag and dropped frames when opening Properties or "
                         "changing images on macOS")
VLC_13358 = row("unspecified issue", "general OBS workflow",
                "VLC Source: Shuffle/Random option does not re-randomize or update from disk on scene change")
WINDOWS_TAG_PLUGIN = row("plugin compatibility", "plugins",
                         "Windows: since 32.2.0, plugins whose dependencies are found via PATH no longer load")
WINDOWS_OS_AMF = row("unspecified issue", "general OBS workflow",
                     "AMF HEVC encoding on Windows is locked to Level 5.1 — cannot set Level 6.2 or High "
                     "Tier via FFmpeg options")
# The other two counted OBS 31.1.2 rows, so F1 regenerates that page's sentence from its population.
CAMERA_13989 = row("camera/source regression", "camera source workflow",
                   "Video Capture Device fails with DirectShow Run failed (0x80004005) starting with OBS "
                   "30.2.0-beta1")
CAMERA_13995 = row("camera/source regression", "camera source workflow",
                   'Virtual camera fails on macOS 26.7: "code signature invalid" - amfid finds no '
                   "provisioning profile for the camera extension")

# One verbatim row per bucket the fix must not move.
UNCHANGED = {
    CAPTURE: row("screen capture regression", "screen/window capture",
                 "Game Capture black screen with Tibia client.exe, but Streamlabs captures correctly."),
    "audio mixer or routing issues": row("audio mixer regression", "audio mixer UI",
                                         "macOS OBS Virtual Camera reports max 1920x1080 to Chrome/WebRTC "
                                         "despite AVFoundation capture working at 2560x1440"),
    CRASH: row("freeze / hang", "application stability",
               "Still processing video, even with no video input and no video output"),
    PLUGIN: row("plugin compatibility", "plugins", "32.1.1 crashes, I haven't updated because of it"),
    "keyboard shortcut regressions": row("hotkey regression", "keyboard shortcuts",
                                         "Pause/Unpause hotkeys actually start/stop recording"),
    "scene list workflow regressions": row("unspecified issue", "general OBS workflow",
                                           "Scene list type-to-select is laggy since 32.1.0 and no longer "
                                           "matches multi-letter input correctly"),
    "output or recording regressions": row("output configuration regression", "output settings",
                                           "Rescale output can be set to bad values and then prevents "
                                           "outputs from stopping"),
    GENERAL: row("unspecified issue", "general OBS workflow",
                 "OBS Version 32.0.0 removed --disable-shutdown-check"),
}

# Constructed controls: the genuine words must still match.
GENUINE_HANG = [row("unspecified issue", "general OBS workflow", title) for title in (
    "OBS hang when stopping the stream", "OBS hangs when stopping the stream",
    "OBS keeps hanging when stopping the stream", "OBS hanged when stopping the stream")]
GENUINE_WINDOW = row("unspecified issue", "general OBS workflow",
                     "Window source shows the wrong application after alt-tab")


def both(item: dict) -> tuple[str, str]:
    return writer._public_issue_bucket(OBS, item), builder.public_issue_bucket(OBS, item)


def run_suite() -> int:
    print("=" * 92)
    print("OBS public issue bucket: word-bounded 'hang' and 'window' in both publication bucketers")
    print("=" * 92)

    for tag, item in (("A1", IMAGE_SOURCE_GH), ("A3", IMAGE_SOURCE_FORUM), ("A5", VLC_13358)):
        w, b = both(item)
        check(f"{tag} writer: 'chang(e|ing)' is not a hang -> {item['report_title'][:48]!r}", w == GENERAL, w)
        check(f"{tag[0]}{int(tag[1]) + 1} builder: 'chang(e|ing)' is not a hang -> {item['report_title'][:48]!r}",
              b == GENERAL, b)

    w, b = both(WINDOWS_TAG_PLUGIN)
    check("B1 writer: a 'Windows:' OS tag is not window capture; the plugin cue decides", w == PLUGIN, w)
    check("B2 builder: a 'Windows:' OS tag is not window capture; the plugin cue decides", b == PLUGIN, b)
    w, b = both(WINDOWS_OS_AMF)
    check("B3 writer: 'encoding on Windows' is not window capture", w == GENERAL, w)
    check("B4 builder: 'encoding on Windows' is not window capture", b == GENERAL, b)

    results = [both(item) for item in GENUINE_HANG]
    check("C1 writer: hang / hangs / hanging / hanged still read as stability",
          all(w == CRASH for w, _ in results), str(results))
    check("C2 builder: hang / hangs / hanging / hanged still read as stability",
          all(b == CRASH for _, b in results), str(results))
    w, b = both(GENUINE_WINDOW)
    check("C3 writer: a standalone 'window' still reads as capture", w == CAPTURE, w)
    check("C4 builder: a standalone 'window' still reads as capture", b == CAPTURE, b)

    moved_w = {k: writer._public_issue_bucket(OBS, v) for k, v in UNCHANGED.items()
               if writer._public_issue_bucket(OBS, v) != k}
    moved_b = {k: builder.public_issue_bucket(OBS, v) for k, v in UNCHANGED.items()
               if builder.public_issue_bucket(OBS, v) != k}
    check(f"D1 writer: all {len(UNCHANGED)} previously valid OBS buckets keep their verbatim rows",
          not moved_w, str(moved_w))
    check(f"D2 builder: all {len(UNCHANGED)} previously valid OBS buckets keep their verbatim rows",
          not moved_b, str(moved_b))

    fixtures = ([IMAGE_SOURCE_GH, IMAGE_SOURCE_FORUM, VLC_13358, WINDOWS_TAG_PLUGIN, WINDOWS_OS_AMF,
                 CAMERA_13989, CAMERA_13995, GENUINE_WINDOW] + GENUINE_HANG + list(UNCHANGED.values()))
    split = [(item["report_title"][:40], *both(item)) for item in fixtures if len(set(both(item))) > 1]
    check(f"E1 the two bucketers agree on all {len(fixtures)} frozen OBS fixtures", not split, str(split))

    inputs = live_eligibility.load_inputs(ROOT)
    obs_rows = other_split = 0
    obs_split: list[tuple] = []
    other = Counter()
    for (pid, ver, *_rest), rows in inputs.counted_groups.items():
        for item in rows:
            w, b = writer._public_issue_bucket(pid, item), builder.public_issue_bucket(pid, item)
            if pid == OBS:
                obs_rows += 1
                if w != b:
                    obs_split.append((ver, item.get("id"), w, b))
            elif w != b:
                other_split += 1
                other[(pid, w, b)] += 1
    check(f"E2 the two bucketers agree on every counted OBS row in the store ({obs_rows} rows)",
          obs_rows > 0 and not obs_split, str(obs_split[:5]))
    # Reported, not gated: pre-existing differences outside OBS are out of this fix's scope.
    print(f"  INFO  non-OBS bucketer differences (pre-existing, not gated): {other_split} {dict(other)}")

    sentence = writer._issue_cluster_sentence(writer._issue_counter(
        OBS, [IMAGE_SOURCE_GH, CAMERA_13989, CAMERA_13995, IMAGE_SOURCE_FORUM]))
    check("F1 OBS 31.1.2's regenerated sentence names only what its reports establish",
          sentence == "Current reports mention capture source issues.", sentence)
    labels = (writer._public_sample_issue(OBS, VLC_13358), writer._public_sample_issue(OBS, WINDOWS_TAG_PLUGIN))
    check("F2 accepted-report issue labels follow the corrected buckets",
          labels == (GENERAL, f"{PLUGIN} in plugins"), str(labels))

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
