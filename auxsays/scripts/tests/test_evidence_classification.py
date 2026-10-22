#!/usr/bin/env python3
"""A published theme may not contradict the reporter, and a platform label must be earned.

`issue_theme` and `platform` are PUBLISHED PROSE -- the patch page prints "Current reports mention
<theme>" -- and two Adobe collectors produced them by guessing. Reproduced against the shipped
functions on the live corpus:

    "500 GB mSata (External - Cache & Render)"       -> export/render failure  (a disk label)
    "Premiere 26.2.2 unstable" / body opening
      "windows and menus freeze, rendering seems
       much slower"                                  -> export/render failure  (secondary clause)
                                                     -> platform: windows     (a UI noun)
    "OS: [Windows 11 Pro 24H2 / macOS version]"      -> platform: windows     (unfilled template)
    "There is no crash at all after the update"      -> application crash or hang

The last inverts its author. Acrobat had already repaired the THEME half for itself and recorded
the cost of the substring scan -- 59 of 63 counted rows whose own title said crash/freeze/hang
published a different theme -- but its PLATFORM half was still the same ordered membership scan,
so a stated macOS report was labelled `windows` whenever the word appeared anywhere.

WHY THE FIXTURES ARE FROZEN. The governed CI manifest compares this suite's reported total to an
exact `= N` in both directions, so a per-row walk of the live evidence store would make the count a
function of the store and go red on the next scheduled run. Every text below is quoted verbatim
from the row it came from and then held still.

WHAT THE THREE FIXES ARE, kept separable so each is pinned by its own named checks and can be
reverted independently:

  PART B   negation -- clause-local, symptom-scoped, bounded by word distance
  PART C   platform -- an allowlist of positive OS evidence, failing toward `unknown`
  PART A/E theme    -- scored word-boundary rules, the reporter's own title weighted above the body

Offline: no network, no repo writes, no read of the evidence store.
"""
from __future__ import annotations

import ast
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib import evidence_classification as ec                      # noqa: E402
from patch_collectors import adobe_acrobat_community as ac         # noqa: E402
from patch_collectors import adobe_premiere as ap                  # noqa: E402

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
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


# --- frozen fixtures ---------------------------------------------------------------------------
# Each entry is (heading, body) quoted verbatim from the stored row named in the comment.

# adobe-premiere-pro-26-2-2-...-does-not-transfer-audio-from-corresponding-video-clip
DISK_LABEL = (
    "Premiere Pro (26.2.2. B3) does not transfer audio from corresponding video clip when adding "
    "to an existing seq",
    "Dell XPS 17 9730 Win11 Ent (26200.8328) Intel Core i9-13900H 64 GB RAM 1TB SSD (Internal), "
    "4TB SanDisk SSD (External), 500 GB mSata (External - Cache & Render)",
)
# adobe-premiere-pro-26-2-2-...-premiere-26-2-2-unstable-1624607
UNSTABLE = (
    "Premiere 26.2.2 unstable",
    "Premiere Pro 26.2.2 still very unstable, windows and menus freeze or take forever to pop up, "
    "rendering seems much slower and still most of the same issues",
)
# The unfilled report template, live on two counted Premiere rows.
TEMPLATE = (
    "Performance / UI Responsiveness",
    "Category: Performance / UI Responsiveness OS: [Windows 11 Pro 24H2 / macOS version] "
    "CPU: [your CPU]",
)
# The same template naming only ONE platform. The live row happens to list both, so the two-
# platforms-named rule alone would refuse it and the placeholder scrubber would go unpinned --
# a mutation run proved exactly that. This fixture makes the scrubber the only thing standing
# between an unfilled form and a confident platform label.
TEMPLATE_ONE_OS = (
    "Performance issue after update",
    "Environment -- OS: [Windows 11 Pro 24H2] CPU: [your CPU] RAM: [amount]",
)
# A report whose only description of the failure lives under a reproduction heading.
REPRODUCE = (
    "Acrobat 26.001 problem",
    "Acrobat 26.001 problem. Steps to reproduce: open any PDF and it crashes immediately.",
)
# acrobat-18-011-20040-...-osx-10-13-4-acrobat-pro-not-working-1228160
NOT_WORKING = (
    "OSX 10.13.4 - Acrobat Pro NOT WORKING",
    "OSX 10.13.4 - Acrobat Pro NOT WORKING Hi, My Acrobat Pro won't start up on my MacBook Pro "
    '13" 2017 USB-C model. I run OSX 10.13.4 and Version 18.011.20040',
)
# A counted Acrobat row whose title carries the matched phrase AND a second symptom.
NOT_RESPONDING = (
    "Adobe Acrobat Pro Not Responding / Crashing",
    "Adobe Acrobat Pro Not Responding / Crashing Good morning, I am currently using Adobe Acrobat "
    "Pro on Windows 11",
)
# A counted Acrobat row naming Windows Server.
WINDOWS_SERVER = (
    "Reader 19.008.20080 causing IE to crash in Windows 2016 server Citrix XenApp environment",
    "Reader version 19.008.20080 causing IE to crash in Windows 2016 server Citrix XenApp "
    "environment",
)
# A counted Acrobat row whose platform is a parenthesised annotation.
ANNOTATED = (
    "Modal overlay blocks UI in Acrobat 26.001.21691 (Windows)",
    "Modal overlay blocks UI in Acrobat 26.001.21691 (Windows) - persists after repair, cache "
    "clear, DNS reset",
)
# The denial this guard exists for. Reproduced against the shipped Premiere classifier.
DENIED_CRASH = ("26.2.2 is fine for me", "There is no crash at all after the update.")

# The five canonical Acrobat theme texts, frozen here as a preservation fixture. They are the same
# strings the Acrobat collector suite asserts, repeated deliberately: that suite proves the
# collector still behaves, this one proves the SHARED library did not change the behaviour it
# inherited. If these ever disagree, the generalisation is what broke.
ACROBAT_PRESERVED = (
    ("Acrobat keeps crashing immediately upon opening", "crash or launch failure"),
    ("Document Freezing After Clicking Save. We use a Topaz Signature pad.",
     "crash or launch failure"),
    ("Acrobat breaks printing on macOS - jobs never reach print queue", "printing regression"),
    ("PDF Keeps Crashing. Workaround: open it through Edge and print using Microsoft Print to PDF",
     "crash or launch failure"),
    ("Acrobat crashes when I open a design document", "crash or launch failure"),
)

CRASH_RULE = next(r for r in ap._PREMIERE_THEME_RULES if r.key == "crash")
AC_CRASH_RULE = next(r for r in ac._THEME_RULES if r.key == "crash")


def premiere_theme(heading: str, body: str) -> str:
    return ap.classify(heading, body)[0]


def premiere_platform(heading: str, body: str) -> str:
    return ap.classify(heading, body)[2]


def constant_from_source(path: Path, name: str) -> set[str]:
    """Read a top-level `name = {...}` set literal out of a script WITHOUT importing it.

    `build_consensus_from_evidence.py` is a top-level script, and the collectors that depend on
    this library run as bare scripts in production, so a test that imports one to read a constant
    would be testing a different import graph than the one that ships.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError(f"{name} not found in {path.name}")


def run_suite() -> int:
    print("=" * 92)
    print("PART A  the five reproduced defects")
    print("=" * 92)

    check("Part A: a disk label does not set the published theme to export/render",
          premiere_theme(*DISK_LABEL) == "media decode or audio/video issue",
          premiere_theme(*DISK_LABEL))
    check("Part A: a UI noun is not an operating-system claim",
          premiere_platform(*UNSTABLE) == "unknown", premiere_platform(*UNSTABLE))
    check("Part A: the theme comes from the symptom, not a secondary clause",
          premiere_theme(*UNSTABLE) == "application crash or hang", premiere_theme(*UNSTABLE))
    check("Part A: an unfilled template is not platform evidence",
          premiere_platform(*TEMPLATE) == "unknown", premiere_platform(*TEMPLATE))
    check("Part A: an explicitly denied crash is not evidence of a crash",
          premiere_theme(*DENIED_CRASH) == "unspecified issue", premiere_theme(*DENIED_CRASH))
    check("Part A: a stated macOS launch failure keeps both its theme and its platform",
          ac.acrobat_classify(NOT_WORKING[1], title=NOT_WORKING[0])[:3]
          == ("crash or launch failure", "application stability", "macos"),
          str(ac.acrobat_classify(NOT_WORKING[1], title=NOT_WORKING[0])[:3]))

    print()
    print("=" * 92)
    print("PART B  negation: each class judged independently")
    print("=" * 92)

    counted, suppressed = ec.count_hits("Premiere crashes on launch every time",
                                        CRASH_RULE.pattern, negatable=True)
    check("Part B: an ordinary positive statement is counted",
          (counted, suppressed) == (1, 0), f"counted={counted} suppressed={suppressed}")
    counted, suppressed = ec.count_hits(DENIED_CRASH[1], CRASH_RULE.pattern, negatable=True)
    check("Part B: a plain denial is suppressed",
          (counted, suppressed) == (0, 1), f"counted={counted} suppressed={suppressed}")
    contrast = "It doesn't crash, but the timeline freezes every few minutes."
    counted, suppressed = ec.count_hits(contrast, CRASH_RULE.pattern, negatable=True)
    check("Part B: a contrast suppresses only the denied clause",
          (counted, suppressed) == (1, 1), f"counted={counted} suppressed={suppressed}")
    check("Part B: and the other symptom in that sentence stays classifiable",
          premiere_theme("26.2.2 report", contrast) == "timeline crash or hang",
          premiere_theme("26.2.2 report", contrast))
    check("Part B: an inability modal is a failure report, not a denial",
          premiere_theme("I can't export anything since 26.2", "") == "export/render failure",
          premiere_theme("I can't export anything since 26.2", ""))
    counted, _ = ec.count_hits("Acrobat won't launch after the update",
                               AC_CRASH_RULE.pattern, negatable=True)
    check("Part B: an inability modal MATCHED BY the pattern is still counted",
          counted == 1, f"counted={counted}")
    counted, suppressed = ec.count_hits(NOT_RESPONDING[0], AC_CRASH_RULE.pattern, negatable=True)
    check("Part B: a negation inside a matched phrase does not negate a later symptom",
          (counted, suppressed) == (2, 0), f"counted={counted} suppressed={suppressed}")
    counted, suppressed = ec.count_hits(NOT_WORKING[1], AC_CRASH_RULE.pattern, negatable=True)
    check("Part B: a denial five words away is out of range",
          suppressed == 0 and counted >= 1, f"counted={counted} suppressed={suppressed}")
    counted, suppressed = ec.count_hits(
        "I can't even hit the report button, without Premiere freezing.",
        CRASH_RULE.pattern, negatable=True)
    check("Part B: the ambiguous 'without' is NOT treated as a denial (deferred, pinned)",
          (counted, suppressed) == (1, 0), f"counted={counted} suppressed={suppressed}")
    check("Part B: a denied crash is not an Acrobat crash either",
          ac.acrobat_classify(DENIED_CRASH[1])[0] == "unspecified Acrobat issue",
          ac.acrobat_classify(DENIED_CRASH[1])[0])
    check("Part B: negation is scoped to rules that opt in, so a capability rule is unaffected",
          not any(r.negatable for r in ap._PREMIERE_THEME_RULES if r.key == "export"))
    check("Part B: exactly one Premiere rule and one Acrobat rule opt in",
          sum(r.negatable for r in ap._PREMIERE_THEME_RULES) == 1
          and sum(r.negatable for r in ac._THEME_RULES) == 1)

    print()
    print("=" * 92)
    print("PART C  platform: positive evidence only, failing toward unknown")
    print("=" * 92)

    for text, want, label in (
        ("Dell XPS 17 9730 Win11 Ent", "windows", "an abbreviated build token"),
        ("running Windows 11 24H2", "windows", "a version"),
        ("my Windows PC crashed", "windows", "a device noun"),
        (WINDOWS_SERVER[1], "windows", "Windows Server by year"),
        (ANNOTATED[1], "windows", "a parenthesised annotation"),
        ("The upgrade patch cannot be installed by the windows installer service", "windows",
         "the Windows Installer component"),
        ("windows and menus freeze", "unknown", "a UI noun"),
        ("too many windows open at once", "unknown", "a bare plural"),
        ("macOS Sequoia 15.2", "macos", "a macOS release name"),
        ("MacBook Pro M3", "macos", "Apple hardware"),
        ("Ubuntu 24.04", "linux", "a Linux distribution"),
        ("Works on Windows but fails on macOS", "unknown", "two platforms named"),
        ("> I am on Windows 11", "unknown", "a quoted reply"),
        ("Premiere is slow lately", "unknown", "nothing stated"),
    ):
        got = ec.resolve_platform(text)
        check(f"Part C: {label} -> {want}", got.label == want, f"{got.label} ({got.basis})")

    check("Part C: a placeholder naming only one platform is still not evidence",
          premiere_platform(*TEMPLATE_ONE_OS) == "unknown",
          premiere_platform(*TEMPLATE_ONE_OS))
    signed = "Acrobat crashes.\n--\nSent from my Windows 11 desktop"
    check("Part C: a signature block is not platform evidence",
          ec.resolve_platform(signed).label == "unknown",
          ec.resolve_platform(signed).basis)
    definitional = ec.resolve_platform("no OS named anywhere", definitional="windows")
    check("Part C: a definitional product keeps its platform without naming it",
          definitional.label == "windows"
          and definitional.basis == "definitional_product_platform", str(definitional))
    check("Part C: the UI-noun case records WHY it was refused",
          "windows_without_os_context" in ec.resolve_platform("windows and menus freeze").suppressed)
    bases = {ec.resolve_platform(t).basis for t in (
        "Windows 11", "windows and menus", "Windows and macOS", "nothing", "> on Windows 11")}
    check("Part C: every basis returned is in the closed vocabulary",
          bases <= ec.PLATFORM_BASES, str(bases - ec.PLATFORM_BASES))

    print()
    print("=" * 92)
    print("PART D  vocabulary and structural guards")
    print("=" * 92)

    consumer = SCRIPTS / "build_consensus_from_evidence.py"
    check("Part D: the mirrored severity vocabulary still equals the consumer's",
          ec.VALID_SEVERITIES == constant_from_source(consumer, "VALID_SEVERITIES"),
          str(ec.VALID_SEVERITIES ^ constant_from_source(consumer, "VALID_SEVERITIES")))
    check("Part D: the mirrored sentiment vocabulary still equals the consumer's",
          ec.VALID_SENTIMENTS == constant_from_source(consumer, "VALID_SENTIMENTS"),
          str(ec.VALID_SENTIMENTS ^ constant_from_source(consumer, "VALID_SENTIMENTS")))
    check("Part D: the library cannot return sentiment at all",
          "sentiment" not in ec.ThemeVerdict.__dataclass_fields__
          and "sentiment" not in ec.ThemeRule.__dataclass_fields__)
    try:
        ec.validate_rules((ec.ThemeRule("t", "a", "catastrophic", "k", re.compile("x")),))
        refused_severity = False
    except ValueError:
        refused_severity = True
    check("Part D: an out-of-vocabulary severity is refused, not silently un-counted",
          refused_severity)
    try:
        ec.validate_rules((ec.ThemeRule("t", "a", "high", "k", re.compile("x")),
                           ec.ThemeRule("u", "b", "high", "k", re.compile("y"))))
        refused_duplicate = False
    except ValueError:
        refused_duplicate = True
    check("Part D: a duplicate rule key is refused", refused_duplicate)
    check("Part D: both shipped Adobe theme tables validate",
          ec.validate_rules(ap._PREMIERE_THEME_RULES) is None
          and ec.validate_rules(ac._THEME_RULES) is None)
    premiere_themes = {r.theme for r in ap._PREMIERE_THEME_RULES}
    check("Part D: the Premiere fallback is not a scored rule, so it cannot win",
          "unspecified issue" not in premiere_themes
          and ap.classify("", "")[0] == "unspecified issue")
    check("Part D: the Acrobat fallback is not a scored rule either",
          "unspecified Acrobat issue" not in {r.theme for r in ac._THEME_RULES})
    tree = ast.parse((SCRIPTS / "lib" / "evidence_classification.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    check("Part D: the library imports no transport and no writer",
          imported <= {"__future__", "re", "dataclasses"}, str(imported))

    print()
    print("=" * 92)
    print("PART E  the collectors the library now serves")
    print("=" * 92)

    for text, want in ACROBAT_PRESERVED:
        got = ac.acrobat_classify(text)[0]
        check(f"Part E: preserved -- {text[:52]!r}", got == want, got)
    check("Part E: Premiere classification takes the title and the body separately",
          _single_argument_call_is_refused())
    check("Part E: Premiere sentiment is negative when a theme matched",
          ap.classify(*DISK_LABEL)[4] == "negative")
    check("Part E: Premiere sentiment is moderate only on the fallback, exactly as before",
          ap.classify("", "")[4] == "moderate")
    check("Part E: Acrobat sentiment is negative on both paths, exactly as before",
          ac.acrobat_classify("Acrobat crashes")[4] == "negative"
          and ac.acrobat_classify("a report with no symptom words")[4] == "negative")
    check("Part E: the reporter's own title outweighs the body",
          ec.HEADING_WEIGHT == 5
          and premiere_theme("Premiere crashes constantly",
                             "rendering rendering rendering rendering") ==
          "application crash or hang")
    check("Part E: evidence inside 'steps to reproduce' is not truncated away",
          ac.acrobat_classify(REPRODUCE[1], title=REPRODUCE[0])[0] == "crash or launch failure",
          ac.acrobat_classify(REPRODUCE[1], title=REPRODUCE[0])[0])
    check("Part E: a workaround the reporter already tried is still truncated away",
          bool(ac._TRIED_SPLIT_RE.search("Workaround: print through Edge")))

    print()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


def _single_argument_call_is_refused() -> bool:
    """The old signature took one concatenated blob, which made title weighting inexpressible."""
    try:
        ap.classify("one concatenated blob")  # type: ignore[call-arg]
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
