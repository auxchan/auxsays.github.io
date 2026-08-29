#!/usr/bin/env python3
"""The CI runner is policy, so it needs its own tests.

`run_integrity_tests.py` decides what CI blocks on. If its manifest check can be fooled, a new test
silently bypasses CI; if its result parser can be fooled, a failing suite reports green; if its
write guard can be fooled, CI quietly reverts a contributor's diff. Each of those is asserted here
against a real temporary manifest and real child processes -- not by inspecting the source.

Offline: no network, no repo writes.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "ci" / "run_integrity_tests.py"

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


def load_runner():
    spec = importlib.util.spec_from_file_location("ci_runner", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def write_suite(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def run_runner(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(RUNNER), *args], cwd=ROOT.parent,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def run() -> int:
    mod = load_runner()

    print("=" * 92)
    print("R1  the shipped manifest is a valid closed-world classification")
    print("=" * 92)
    sections, problems = mod.load_manifest()
    errors = mod.validate_manifest(sections, problems)
    check("R1.1 shipped manifest validates", not errors, "; ".join(errors)[:300])
    classified = {n for names in sections.values() for n in names}
    on_disk = mod.discovered_tests()
    check("R1.2 every test file on disk is classified", on_disk <= classified,
          str(sorted(on_disk - classified)))
    check("R1.3 no manifest entry lacks a file", classified <= on_disk,
          str(sorted(classified - on_disk)))
    check("R1.4 this very test file is classified", Path(__file__).name in classified)
    check("R1.5 categories are exactly the documented set",
          set(sections) == set(mod.CATEGORIES), str(sorted(sections)))
    counts = {c: len(sections[c]) for c in mod.CATEGORIES}
    check("R1.6 blocking is non-empty", counts["blocking"] > 0, str(counts))
    check("R1.7 excluded categories stay small and deliberate",
          sum(counts[c] for c in mod.NOT_EXECUTED) < len(on_disk) // 4, str(counts))

    print()
    print("=" * 92)
    print("R2  manifest validation rejects each way coverage could silently drift")
    print("=" * 92)
    base = {c: [] for c in mod.CATEGORIES}

    real = sorted(on_disk)[0]
    sections_a = {**{c: list(v) for c, v in base.items()}, "blocking": [real]}
    errs = mod.validate_manifest(sections_a, [])
    check("R2.1 unclassified files on disk are rejected",
          any("UNCLASSIFIED" in e for e in errs), str(errs)[:200])

    sections_b = {c: list(sections[c]) for c in mod.CATEGORIES}
    sections_b["blocking"] = sections_b["blocking"] + ["test_does_not_exist_anywhere.py"]
    errs = mod.validate_manifest(sections_b, [])
    check("R2.2 a manifest entry with no file is rejected",
          any("MISSING SUITE" in e for e in errs), str(errs)[:200])

    # A real duplicate, parsed from a real manifest file -- not an assertion about the source text.
    with tempfile.TemporaryDirectory() as td:
        dup = Path(td) / "dup_manifest.txt"
        dup.write_text(f"[blocking]\n{real}\n[diagnostic]\n{real}\n", encoding="utf-8")
        saved_manifest = mod.MANIFEST
        try:
            mod.MANIFEST = dup
            _sections, problems = mod.load_manifest()
        finally:
            mod.MANIFEST = saved_manifest
    check("R2.3 the same suite in two categories is rejected",
          any("classified twice" in p for p in problems), str(problems)[:200])

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad_category.txt"
        bad.write_text(f"[not_a_real_category]\n{real}\n", encoding="utf-8")
        saved_manifest = mod.MANIFEST
        try:
            mod.MANIFEST = bad
            _sections, problems = mod.load_manifest()
        finally:
            mod.MANIFEST = saved_manifest
    check("R2.4 an unknown category name is rejected",
          any("unknown category" in p for p in problems), str(problems)[:200])

    print()
    print("=" * 92)
    print("R3  a suite's outcome cannot be faked  (real child processes)")
    print("=" * 92)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        original_tests = mod.TESTS
        try:
            mod.TESTS = tmp
            write_suite(tmp, "test_ok.py", """
                print("Results: 3/3 passed, 0 failed")
                """)
            ok, detail, passed, failed, _ = mod.run_one("test_ok.py")
            check("R3.1 a clean suite passes", ok and passed == 3 and failed == 0, detail)

            write_suite(tmp, "test_reports_failure.py", """
                import sys
                print("  FAIL  something important")
                print("Results: 2/3 passed, 1 failed")
                sys.exit(1)
                """)
            ok, detail, _, failed, _ = mod.run_one("test_reports_failure.py")
            check("R3.2 a failing suite fails and its FAIL lines survive",
                  not ok and failed == 1 and "something important" in detail, detail[:160])

            # The dangerous case: a suite that claims success but exits nonzero.
            write_suite(tmp, "test_green_but_nonzero.py", """
                import sys
                print("Results: 5/5 passed, 0 failed")
                sys.exit(3)
                """)
            ok, detail, _, _, _ = mod.run_one("test_green_but_nonzero.py")
            check("R3.3 a nonzero exit fails even when the summary says 0 failed",
                  not ok, detail[:160])

            # The other dangerous case: crashes and malformed output must never look like a skip.
            write_suite(tmp, "test_import_error.py", """
                import a_module_that_does_not_exist  # noqa
                """)
            ok, detail, _, _, _ = mod.run_one("test_import_error.py")
            check("R3.4 an import error is a failure, not a skip",
                  not ok and "NO RESULTS LINE" in detail, detail[:160])

            write_suite(tmp, "test_silent.py", """
                pass
                """)
            ok, detail, _, _, _ = mod.run_one("test_silent.py")
            check("R3.5 a suite printing nothing is a failure, not a skip",
                  not ok and "NO RESULTS LINE" in detail, detail[:160])

            write_suite(tmp, "test_two_summaries.py", """
                print("Results: 9/9 passed, 0 failed")
                print("  FAIL  the real outcome")
                print("Results: 1/2 passed, 1 failed")
                """)
            ok, _, _, failed, _ = mod.run_one("test_two_summaries.py")
            check("R3.6 the LAST summary wins, so an early line cannot mask the real one",
                  not ok and failed == 1)

            write_suite(tmp, "test_slow.py", """
                import time
                time.sleep(30)
                print("Results: 1/1 passed, 0 failed")
                """)
            saved = mod.PER_TEST_TIMEOUT
            mod.PER_TEST_TIMEOUT = 2
            try:
                ok, detail, _, _, _ = mod.run_one("test_slow.py")
            finally:
                mod.PER_TEST_TIMEOUT = saved
            check("R3.7 a hung suite times out and fails", not ok and "TIMEOUT" in detail, detail[:120])
        finally:
            mod.TESTS = original_tests

    print()
    print("=" * 92)
    print("R4  the write guard sees what .gitignore hides")
    print("=" * 92)
    before = {"a.md": "1", "[ignored] auxsays/_data/qa_status.json": "x"}
    check("R4.1 a modified tracked file is detected",
          mod.diff_snapshots(before, {**before, "a.md": "2"}) == ["a.md (modified)"])
    check("R4.2 a removed tracked file is detected",
          "a.md (untracked/removed)" in mod.diff_snapshots(before, {k: v for k, v in before.items() if k != "a.md"}))
    check("R4.3 an added file is detected",
          "b.md (added to index)" in mod.diff_snapshots(before, {**before, "b.md": "9"}))
    check("R4.4 a gitignored status snapshot is watched, not invisible",
          mod.diff_snapshots(before, {**before, "[ignored] auxsays/_data/qa_status.json": "y"})
          == ["[ignored] auxsays/_data/qa_status.json (modified)"])
    for path in ("auxsays/_data/qa_status.json", "auxsays/_data/consensus_status.json"):
        check(f"R4.5 {path} is on the watch list", path in mod.WATCHED_IGNORED)
    check("R4.6 an unchanged tree reports no drift", mod.diff_snapshots(before, dict(before)) == [])

    print()
    print("=" * 92)
    print("R5  the CLI contract CI depends on")
    print("=" * 92)
    proc = run_runner("--check-manifest")
    check("R5.1 --check-manifest exits 0 on the shipped manifest",
          proc.returncode == 0, f"rc={proc.returncode} {proc.stderr[:160]}")
    proc = run_runner("--list", "blocking")
    listed = [x for x in proc.stdout.split() if x.endswith(".py")]
    check("R5.2 --list blocking prints exactly the blocking category",
          proc.returncode == 0 and listed == sections["blocking"], f"{len(listed)} vs {len(sections['blocking'])}")
    check("R5.3 exit codes are distinct and documented",
          mod.MANIFEST_ERROR == 3 and mod.MUTATION_ERROR == 2)
    check("R5.4 excluded categories are never executed by 'all'",
          all(n not in [x for c in mod.EXECUTED for x in sections[c]]
              for c in mod.NOT_EXECUTED for n in sections[c]))

    print()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
