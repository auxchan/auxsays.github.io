#!/usr/bin/env python3
"""The historical reclassification writes only what the retained text supports, and nothing else.

`recompute_evidence_classification.py` re-derives `platform` and `issue_theme` for stored rows the
replaced substring chains labelled. Its contract, pinned here on frozen rows:

  * a stored label is re-judged only when the classifier that PRODUCED it reproduces it from the
    retained text; otherwise it is kept (the evidence behind it is no longer stored);
  * platform is downgrade-only: never upgraded from unknown, and a different named OS is refused;
  * a theme is rewritten only when its own rule no longer hits the retained text, or the reporter's
    title names the new theme and never the stored one;
  * sentiment, counted status, identity, URLs, dates and text are never written, and the edit is
    block-scoped: every other field of every row parses back unchanged;
  * a second run changes nothing; the module touches no network and has one write site.

Offline: frozen rows and a temporary store only.
"""
from __future__ import annotations

import ast
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import recompute_evidence_classification as rc  # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []
BEFORE = "2026-09-01T00:00:00Z"    # captured before every collector's repair
AFTER = "9999-12-31T23:59:59Z"     # captured by the shipped classifier


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


def row(rid: str, pid: str, title: str, excerpt: str, *, theme: str, area: str, platform: str,
        severity: str = "medium", sentiment: str = "negative", captured: str = BEFORE) -> dict:
    return {"id": rid, "product_id": pid, "update_version": "1.0", "source_url": f"https://example.org/{rid}",
            "parent_title": title, "report_title": title, "report_text_excerpt": excerpt,
            "issue_theme": theme, "workflow_area": area, "platform": platform, "severity": severity,
            "sentiment": sentiment, "counted": True, "exclusion_reason": None, "captured_at": captured,
            "source_date": "2026-04-10"}


# Verbatim titles and excerpts from counted rows.
OBS_SCENE = row("obs-scene", "obs-studio",
                "VLC Source: Shuffle/Random option does not re-randomize or update from disk on scene change",
                "### Operating System Info Windows 11 ### Other OS _No response_ ### OBS Studio Version 32.1.1",
                theme="freeze / hang", area="application stability", platform="windows", severity="high")
OBS_TWO_OS = row("obs-two-os", "obs-studio", "OBS Dock size issue",
                 "Operating System Info Other ### Other OS Arch Linux and Windows 10 ### OBS Studio Version 32.1.1",
                 theme="unspecified issue", area="general OBS workflow", platform="windows", sentiment="moderate")
DV_LINUX = row("dv-linux", "blackmagic-davinci", "[Linux] DaVinci Resolve can't open existing projects",
               "[Linux] DaVinci Resolve can't open existing projects I'm currently trying to switch from Windows "
               "to Linux, so I'm also trying to get DaVinci Resolve to run on Linux.",
               theme="unspecified issue", area="general DaVinci Resolve workflow", platform="windows",
               sentiment="moderate")
PR_FREEZE = row("pr-freeze", "adobe-premiere-pro",
                "In 26.2.2, the app would freeze whenever I needed to open a drop-down menu",
                "In 26.2.2, the app would freeze whenever I needed to open a drop-down menu in the audio panel.",
                theme="media decode or audio/video issue", area="media playback", platform="unknown")
UPGRADE = row("upgrade", "obs-studio", "Preview flickers on macOS Sonoma", "Running macOS Sonoma 14.5.",
              theme="unspecified issue", area="general OBS workflow", platform="unknown", sentiment="moderate")
UNRETAINED = row("unretained", "obs-studio", "Settings reset", "Everything resets after restart.",
                 theme="audio mixer regression", area="audio mixer UI", platform="unknown")
SUPPORTED = row("supported", "obs-studio", "Audio desync after update", "My audio drifts behind the video.",
                theme="audio mixer regression", area="audio mixer UI", platform="unknown")
SHIPPED = dict(OBS_SCENE, id="shipped", captured_at=AFTER)


def run_suite() -> int:
    print("[A] platform: downgrade only, and only from evidence in hand")
    d = rc.decide(OBS_TWO_OS)
    check("A1 two platforms named: the stored windows is written unknown",
          d["write"] == {"platform": "unknown"} and d["platform"] == "downgraded_unsupported", str(d))
    d = rc.decide(DV_LINUX)
    check("A2 a different named OS is refused, not swapped: unknown, never linux",
          d["write"].get("platform") == "unknown" and d["platform"] == "downgraded_swap_refused", str(d))
    d = rc.decide(UPGRADE)
    check("A3 a stored unknown is never upgraded", "platform" not in d["write"]
          and d["platform"] == "upgrade_withheld", str(d))

    print("[B] theme: rewritten only when unsupported or outranked by the reporter's title")
    d = rc.decide(OBS_SCENE)
    check("B1 'hang' only inside 'change': rewritten to the shipped answer",
          d["theme"] == "rewritten_unsupported" and d["write"].get("issue_theme") == "unspecified issue"
          and d["write"].get("severity") == "medium", str(d))
    d = rc.decide(PR_FREEZE)
    check("B2 the title says freeze, never media: rewritten (outranked by title)",
          d["theme"] == "rewritten_outranked_by_title"
          and d["write"].get("issue_theme") == "application crash or hang", str(d))
    d = rc.decide(UNRETAINED)
    check("B3 a label the retained text cannot reproduce is kept",
          d["theme"] == "not_reproducible_from_retained_text" and not d["write"], str(d))
    d = rc.decide(SUPPORTED)
    check("B4 a stored theme its own rule still supports is kept",
          d["theme"] == "confirmed" and not d["write"], str(d))
    d = rc.decide(SHIPPED)
    check("B5 a row the shipped classifier wrote is judged by it, not the old chain",
          d["theme"] in ("confirmed", "not_reproducible_from_retained_text"), str(d))

    print("[C] the write set")
    fixtures = (OBS_SCENE, OBS_TWO_OS, DV_LINUX, PR_FREEZE, UPGRADE, UNRETAINED, SUPPORTED, SHIPPED)
    keys = set().union(*(rc.decide(f)["write"] for f in fixtures))
    check("C1 only platform / issue_theme / workflow_area / severity are ever written",
          keys and keys <= rc.WRITABLE, str(keys))
    check("C2 sentiment is never written, even when a theme moves to the fallback",
          "sentiment" not in rc.decide(OBS_SCENE)["write"])
    try:
        rc.apply_writes("- id: a\n  sentiment: negative\n", ["a"], {0: {"sentiment": "moderate"}})
        refused = False
    except SystemExit:
        refused = True
    check("C3 the write site refuses a key outside the write set", refused)

    print("[D] the store: block-scoped, identity by position, idempotent")
    store = {"schema_version": 1, "evidence": [OBS_SCENE, dict(OBS_TWO_OS, id="obs-scene"), SUPPORTED]}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "consensus_evidence.yml"
        text = yaml.safe_dump(store, sort_keys=False, allow_unicode=True, width=1000)
        path.write_bytes(text.encode("utf-8"))
        first = rc.run(path, write=True)
        after = yaml.safe_load(path.read_text(encoding="utf-8"))["evidence"]
        check("D1 two rows sharing an id are each edited in their own block",
              after[0]["issue_theme"] == "unspecified issue" and after[1]["platform"] == "unknown"
              and after[1]["issue_theme"] == "unspecified issue", str(after[:2]))
        untouched = all(after[i][k] == store["evidence"][i][k] for i in range(3)
                        for k in store["evidence"][i] if k not in rc.WRITABLE)
        check("D2 every field outside the write set parses back unchanged", untouched)
        check("D3 sentiment and counted are unchanged on every row",
              [r["sentiment"] for r in after] == [r["sentiment"] for r in store["evidence"]]
              and all(r["counted"] for r in after))
        changed_lines = sum(1 for a, b in zip(text.splitlines(), path.read_text(encoding="utf-8").splitlines())
                            if a != b)
        check("D4 the edit is block-scoped: only the decided field lines differ",
              changed_lines == sum(len(c) - 6 for c in first["changes"]), f"{changed_lines} lines")
        second = rc.run(path, write=True)
        check("D5 a second run changes nothing", second["rows_changed"] == 0 and not second["written"],
              str(second["rows_changed"]))

    print("[E] no network, one write site")
    tree = ast.parse(Path(rc.__file__).read_text(encoding="utf-8"))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names}
    imported |= {(node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    check("E1 imports no transport", not imported & {"urllib", "requests", "http", "socket", "httpx"},
          str(imported))
    writes = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute)
              and node.attr in ("write_bytes", "write_text")]
    check("E2 exactly one write site", len(writes) == 1, str(len(writes)))

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
