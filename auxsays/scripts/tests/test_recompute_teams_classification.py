#!/usr/bin/env python3
"""The historical Teams reclassification consumes the shipped producer and writes nothing else.

Before the producer repair the Teams collector wrote the constant platform "Windows" on every row and
left theme, workflow area and severity empty. `recompute_teams_classification.py` re-derives those four
fields from the retained text. Its contract, pinned here on frozen rows:

  * it CONSUMES `microsoft_teams._classify_candidate` and carries no rule of its own;
  * platform is the resolver's answer for the text (windows / macos / unknown), never a default;
  * a theme, its workflow area and its severity are written together or not at all, and an
    unclassified row stays empty (nothing is invented because a row happens to be counted);
  * only a recognisably legacy Teams row is in scope: a row the repaired producer wrote, a row of any
    other product, and a row that already has a theme are never touched;
  * sentiment, counted status, exclusion reason, identity, URLs, dates and text are never written; the
    edit is block-scoped and addressed by position; a second run changes nothing; no network.

Offline: frozen rows and a temporary store only (plus one read of the checked-in store, at the end).
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import recompute_teams_classification as rt  # noqa: E402
from patch_collectors import microsoft_teams as teams  # noqa: E402

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


def row(rid: str, title: str, excerpt: str, *, counted: bool = False, pid: str = "microsoft-teams",
        platform: str = "Windows", theme: str = "", area: str = "", severity: str = "") -> dict:
    return {"id": rid, "product_id": pid, "update_version": "26213.1006.5014.9784",
            "source_url": f"https://example.org/{rid}", "parent_title": title, "report_title": title,
            "report_text_excerpt": excerpt, "captured_at": "2026-09-29T23:13:26Z", "source_date": "2026-09-24",
            "counted": counted, "exclusion_reason": None if counted else "ring_preview",
            "sentiment": "negative" if counted else "", "source_weight": 1,
            "issue_theme": theme, "workflow_area": area, "platform": platform, "severity": severity}


CHAT = row("chat", "Teams messages won't go through - desktop or online - Microsoft Q&A",
           "A couple days ago, I realised my messages on teams weren't going through - I found logging out "
           "and logging back into teams resolved it.", counted=True)
JOIN = row("join", "Dropped from meetings",
           "Using Teams v. 26213.1006.5014.9784 on Win 11 laptop fully updated. Dropped from meetings repeatedly.",
           counted=True)
SIGNIN = row("signin", "Teams desktop shows old email alias; web is correct. Reset and sign-in failed. - Microsoft Q&A",
             "I changed my email alias. Teams on the web displays it, but sign-in failed on desktop.", counted=True)
LAG = row("lag", "Teams desktop: system-wide lag when decoding incoming camera video",
          "my whole computer starts lagging as soon as another participant turns their camera on", counted=True)
NOTES = row("notes", "Missing Release Notes for Microsoft Teams - Microsoft Q&A",
            "Hello, as a Teams Administrator, I am facing an issue where many users can no longer end calls "
            "using headset buttons.", counted=True)
MAC = row("mac", "Teams on my MacBook Pro", "I use macOS Sonoma. I like the new layout.")
SHARE = row("share", "Screen sharing", "Cannot share my screen on a Mac in Teams, button is greyed out.")
FIXTURES = (CHAT, JOIN, SIGNIN, LAG, NOTES, MAC, SHARE)


def run_suite() -> int:
    print("[A] the shipped producer is consumed, not copied")
    got = {r["id"]: rt.decide(r)["write"] for r in (CHAT, JOIN, SIGNIN, LAG, NOTES)}
    check("A1 chat / join / sign-in / lag take the shipped theme, area and severity",
          (got["chat"].get("issue_theme"), got["chat"].get("severity"),
           got["join"].get("issue_theme"), got["join"].get("severity"),
           got["signin"].get("issue_theme"), got["signin"].get("severity"),
           got["lag"].get("issue_theme"), got["lag"].get("severity"))
          == ("chat or notification problem", "medium", "meeting join / connection failure", "high",
              "sign-in failure", "high", "performance regression", "medium"), str(got))
    original = teams._classify_candidate
    try:
        teams._classify_candidate = lambda parent, title, text: ("SENTINEL THEME", "SENTINEL AREA", "linux", "critical")
        sentinel = rt.decide(CHAT)["write"]
    finally:
        teams._classify_candidate = original
    check("A2 the migration follows the producer: a replaced producer changes what is written",
          sentinel == {"platform": "linux", "issue_theme": "SENTINEL THEME", "workflow_area": "SENTINEL AREA",
                       "severity": "critical"}, str(sentinel))
    tree = ast.parse(Path(rt.__file__).read_text(encoding="utf-8"))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names}
    imported |= {(node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    called = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    check("A3 no rule of its own: no regex, no ThemeRule, no pattern table; calls the producer",
          "re" not in imported and "ThemeRule" not in called and "compile" not in called
          and "_classify_candidate" in called, str(imported))

    print("[B] platform: the resolver's answer for the text, never a default")
    check("B1 no operating system named -> unknown, not the legacy 'Windows'",
          rt.decide(CHAT)["write"]["platform"] == "unknown")
    check("B2 'Win 11' -> windows; 'macOS Sonoma' -> macos",
          rt.decide(JOIN)["write"]["platform"] == "windows" and rt.decide(MAC)["write"]["platform"] == "macos")
    check("B3 every written platform is inside the vocabulary",
          all(rt.decide(r)["write"]["platform"] in rt.PLATFORM_VOCABULARY for r in FIXTURES))

    print("[C] theme: written as a unit, or left empty")
    d = rt.decide(NOTES)
    check("C1 no supported theme -> only platform is written; theme, area, severity stay empty",
          d["write"] == {"platform": "unknown"} and d["theme"] == "unclassified", str(d))
    d = rt.decide(SIGNIN)["write"]
    check("C2 a supported theme brings its area and a valid severity together",
          {"issue_theme", "workflow_area", "severity"} <= set(d) and d["severity"] in rt.ec.VALID_SEVERITIES, str(d))
    check("C3 a counted row without a theme gets no invented severity",
          "severity" not in rt.decide(NOTES)["write"] and NOTES["counted"])
    check("C4 a plain mention is not a failure: a macOS praise post is not given a theme",
          "issue_theme" not in rt.decide(MAC)["write"])

    print("[D] scope: only a recognisably legacy Teams row")
    check("D1 a row the repaired producer wrote (lowercase platform) is never re-judged",
          rt.decide(dict(CHAT, platform="unknown"))["write"] == {}
          and rt.decide(dict(CHAT, platform="unknown"))["basis"] == "skipped_not_legacy")
    check("D2 a row that already has a theme is never re-judged, even with the legacy platform",
          rt.decide(dict(CHAT, issue_theme="sign-in failure"))["write"] == {})
    check("D3 a stored severity alone also puts a row out of scope",
          rt.decide(dict(CHAT, severity="high"))["write"] == {})
    tmp_store = {"schema_version": 1, "evidence": [row("o1", CHAT["report_title"], CHAT["report_text_excerpt"],
                                                        pid="obs-studio")]}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "consensus_evidence.yml"
        path.write_text(yaml.safe_dump(tmp_store, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
        report = rt.run(path, write=True)
    check("D4 another product's row with the same shape is out of scope", report["rows_in_scope"] == 0
          and report["rows_changed"] == 0, str(report["rows_in_scope"]))

    print("[E] the write set")
    keys = set().union(*(rt.decide(r)["write"] for r in FIXTURES))
    check("E1 only platform / issue_theme / workflow_area / severity are ever written",
          keys and keys <= rt.WRITABLE, str(keys))
    check("E2 sentiment, counted and exclusion_reason are never in a decision",
          not any({"sentiment", "counted", "exclusion_reason"} & set(rt.decide(r)["write"]) for r in FIXTURES))
    try:
        rt.apply_writes("- id: a\n  sentiment: negative\n", ["a"], {0: {"sentiment": "moderate"}})
        refused = False
    except SystemExit:
        refused = True
    check("E3 the shared write site refuses a key outside the write set", refused)
    try:
        teams._classify_candidate = lambda parent, title, text: ("T", "A", "windows", "")
        rt.decide(CHAT)
        refused = False
    except SystemExit:
        refused = True
    finally:
        teams._classify_candidate = original
    check("E4 a producer answer with an unsupported severity is refused, not written", refused)

    print("[F] the store: block-scoped, identity by position, idempotent")
    rows = [dict(CHAT), dict(JOIN, id="chat"), dict(MAC), row("obs", "OBS crash", "crashes on quit", pid="obs-studio"),
            dict(NOTES)]
    store = {"schema_version": 1, "evidence": rows}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "consensus_evidence.yml"
        text = yaml.safe_dump(store, sort_keys=False, allow_unicode=True, width=1000)
        path.write_bytes(text.encode("utf-8"))
        dry = rt.run(path, write=False)
        check("F1 a dry run reports the work and changes no byte", path.read_bytes() == text.encode("utf-8")
              and dry["rows_changed"] == 4 and not dry["written"], str(dry["rows_changed"]))
        first = rt.run(path, write=True)
        after = yaml.safe_load(path.read_text(encoding="utf-8"))["evidence"]
        check("F2 two rows sharing an id are each edited in their own block",
              after[0]["issue_theme"] == "chat or notification problem"
              and after[1]["issue_theme"] == "meeting join / connection failure" and after[1]["platform"] == "windows",
              str(after[:2]))
        check("F3 every field outside the write set parses back unchanged",
              all(after[i][k] == rows[i][k] for i in range(len(rows)) for k in rows[i] if k not in rt.WRITABLE))
        check("F4 the other product's row is untouched, field for field", after[3] == rows[3])
        check("F5 sentiment, counted and exclusion reason survive on every row",
              [(r["sentiment"], r["counted"], r["exclusion_reason"]) for r in after]
              == [(r["sentiment"], r["counted"], r["exclusion_reason"]) for r in rows])
        changed_lines = sum(1 for a, b in zip(text.splitlines(), path.read_text(encoding="utf-8").splitlines())
                            if a != b)
        check("F6 the edit is block-scoped: only the decided field lines differ",
              changed_lines == sum(len(c) - 4 for c in first["changes"]), f"{changed_lines} lines")
        once = path.read_bytes()
        second = rt.run(path, write=True)
        check("F7 a second run changes nothing and writes nothing",
              second["rows_changed"] == 0 and not second["written"] and path.read_bytes() == once,
              str(second["rows_changed"]))
        audit = Path(tmp) / "audit.json"
        with contextlib.redirect_stdout(io.StringIO()):
            rt.main(["--store", str(path), "--audit", str(audit), "--parent-commit", "abc123"])
        manifest = json.loads(audit.read_text(encoding="utf-8"))
        check("F8 the manifest names the parent commit and hashes the classifier",
              manifest["parent_commit"] == "abc123" and set(manifest["classifier_sha256"]) == set(rt.CLASSIFIER_FILES)
              and all(len(h) == 64 for h in manifest["classifier_sha256"].values()))
        a = rt.run(Path(tmp) / "consensus_evidence.yml", write=False)["summary"]
        check("F9 the summary is deterministic across runs", a == rt.run(path, write=False)["summary"])

    print("[G] no network, one store write site")
    check("G1 imports no transport", not imported & {"urllib", "requests", "http", "socket", "httpx"}, str(imported))
    writes = [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
              and node.attr in ("write_bytes", "write_text")]
    check("G2 one store write site (write_bytes) and one manifest write", writes.count("write_bytes") == 1
          and writes.count("write_text") == 1, str(writes))

    print("[H] the checked-in store")
    live = rt.run(rt.STORE, write=False)
    check("H1 no legacy Teams row remains in the checked-in store", live["rows_changed"] == 0
          and live["summary"]["basis"].get("legacy", 0) == 0, str(live["summary"]["basis"]))
    stored = yaml.load(rt.STORE.read_bytes().decode("utf-8"), Loader=yaml.SafeLoader)["evidence"]
    teams_rows = [r for r in stored if r.get("product_id") == "microsoft-teams"]
    check("H2 every stored Teams platform is inside the vocabulary",
          teams_rows and all(r.get("platform") in rt.PLATFORM_VOCABULARY for r in teams_rows),
          str({r.get("platform") for r in teams_rows}))
    check("H3 every counted Teams row keeps sentiment 'negative'",
          all(r.get("sentiment") == "negative" for r in teams_rows if r.get("counted") is True))

    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        sys.exit(run_suite())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print(f"Results: {PASS}/{PASS + FAIL + 1} passed, {FAIL + 1} failed")
        sys.exit(1)
