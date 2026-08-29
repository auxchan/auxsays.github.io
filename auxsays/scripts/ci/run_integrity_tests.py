#!/usr/bin/env python3
"""Run the AUXSAYS test suites CI blocks on, and prove they changed nothing.

AUXSAYS protects exact-patch intelligence with standalone test scripts under auxsays/scripts/tests/.
Each prints a final `Results: N/M passed, K failed` line and exits nonzero on failure. Until this
runner existed, nothing executed them automatically -- a test that is never run is documentation,
not enforcement.

Three properties this runner exists to guarantee, each of which has been violated by hand before:

  * THE MANIFEST IS CLOSED-WORLD. Every test file on disk must be classified exactly once. A new
    test that nobody classified fails the run rather than silently bypassing CI; a manifest entry
    whose file is gone fails rather than silently shrinking coverage; a suite listed twice fails
    rather than quietly running twice or being counted in two categories.
  * NOTHING IS SILENTLY SKIPPED. A suite that cannot be imported, crashes, times out, or prints no
    parsable Results line is a FAILURE, never a skip. Green means every named suite really ran.
  * NOTHING IS SILENTLY WRITTEN. Several production scripts here write generated records even with
    no flags, and tests import them. Every tracked file is hashed before and after, so CI can never
    quietly mutate a checkout.

Usage:
    python auxsays/scripts/ci/run_integrity_tests.py --suite blocking
    python auxsays/scripts/ci/run_integrity_tests.py --suite diagnostic
    python auxsays/scripts/ci/run_integrity_tests.py --check-manifest
    python auxsays/scripts/ci/run_integrity_tests.py --list blocking

Exit codes: 0 green and tree unchanged; 1 a suite failed; 2 the working tree was mutated;
3 the manifest is not a valid closed-world classification.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TESTS = REPO / "auxsays" / "scripts" / "tests"
MANIFEST = Path(__file__).resolve().parent / "integrity_suites.txt"

RESULTS_RE = re.compile(r"^Results:\s*(\d+)\s*/\s*(\d+)\s+passed,\s*(\d+)\s+failed", re.M)
# A suite may SKIP individual assertions when an optional tool is missing. That is not a failure,
# but it MUST be visible: test_public_method_health_presentation silently dropped 51 of its 72
# checks on the Ubuntu runner (no Ruby `liquid` gem) while still reporting "21/21 passed", and the
# only way anyone noticed was diffing CI check totals against a local run.
SKIP_RE = re.compile(r"^\s*SKIP\s", re.M)
PER_TEST_TIMEOUT = 900

# Every category a test file may be classified into. `blocking` and `diagnostic` are executed;
# the rest are deliberately NOT run by CI, each for a stated reason.
EXECUTED = ("blocking", "diagnostic")
NOT_EXECUTED = ("network", "mutating", "environment_specific", "stale")
CATEGORIES = EXECUTED + NOT_EXECUTED

MANIFEST_ERROR = 3
MUTATION_ERROR = 2


def discovered_tests() -> set[str]:
    """Test files on disk. `__init__.py` is package plumbing, not a suite."""
    return {p.name for p in TESTS.glob("test_*.py") if p.is_file()}


def load_manifest() -> tuple[dict[str, list[str]], list[str]]:
    """Parse the manifest. Returns (category -> [names], problems)."""
    sections: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    problems: list[str] = []
    seen: dict[str, str] = {}
    current: str | None = None
    for lineno, raw in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            if current not in CATEGORIES:
                problems.append(f"line {lineno}: unknown category [{current}] "
                                f"(expected one of {', '.join(CATEGORIES)})")
            continue
        if current is None:
            problems.append(f"line {lineno}: entry before any [category]: {line!r}")
            continue
        if current not in sections:
            continue  # already reported as an unknown category
        if line in seen:
            problems.append(f"line {lineno}: {line} classified twice "
                            f"([{seen[line]}] and [{current}]) -- each suite belongs to exactly one")
            continue
        seen[line] = current
        sections[current].append(line)
    return sections, problems


def validate_manifest(sections: dict[str, list[str]], problems: list[str]) -> list[str]:
    """Closed-world check, in BOTH directions."""
    errors = list(problems)
    classified = {name for names in sections.values() for name in names}
    on_disk = discovered_tests()

    unclassified = sorted(on_disk - classified)
    if unclassified:
        errors.append(
            f"UNCLASSIFIED TEST SUITE: {len(unclassified)} test file(s) exist but are in no "
            f"category. A new test must be classified so it cannot silently bypass CI:\n"
            + "\n".join(f"    {n}" for n in unclassified))

    missing = sorted(classified - on_disk)
    if missing:
        errors.append(
            f"MANIFEST REFERENCES MISSING SUITE: {len(missing)} entr(y/ies) name a file that does "
            f"not exist. Coverage must not shrink silently:\n"
            + "\n".join(f"    {n}" for n in missing))
    return errors


# Paths that are GITIGNORED but must still never be written by CI. A guard built only on tracked
# files is blind to these: `qa_status.json` and `consensus_status.json` are produced by the very
# QA/consensus scripts the tests import, and `.gitignore` hides them, so a writer could clobber them
# with the tracked-file check still reporting "clean". Watched explicitly for that reason.
WATCHED_IGNORED = (
    "auxsays/_data/qa_status.json",
    "auxsays/_data/consensus_status.json",
    "auxsays/_data/patch_state.json",
    "auxsays/_site",
)


def _hash_path(path: Path) -> str:
    try:
        if path.is_dir():
            return "<dir>"
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return "<absent>"
    except OSError:
        return "<unreadable>"


def tracked_snapshot() -> dict[str, str] | None:
    """Hash of every tracked file plus the watched ignored paths, or None when git is unavailable.

    Tracked files catch a clobbered generated record; WATCHED_IGNORED catches a status snapshot that
    `.gitignore` would otherwise hide. An ignored __pycache__ stays noise and is not watched.
    """
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    snap: dict[str, str] = {}
    for raw in out.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        snap[rel] = _hash_path(REPO / rel)
    for rel in WATCHED_IGNORED:
        snap[f"[ignored] {rel}"] = _hash_path(REPO / rel)
    return snap


def diff_snapshots(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed = [f"{p} (modified)" for p in before if p in after and before[p] != after[p]]
    changed += [f"{p} (untracked/removed)" for p in before if p not in after]
    changed += [f"{p} (added to index)" for p in after if p not in before]
    return sorted(changed)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_one(name: str) -> tuple[bool, str, int, int, int, float]:
    """Run one suite. Returns (ok, detail, checks_passed, checks_failed, checks_skipped, seconds)."""
    path = TESTS / name
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, str(path)], cwd=REPO, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=PER_TEST_TIMEOUT, env=_env())
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {PER_TEST_TIMEOUT}s", 0, 0, 0, time.monotonic() - started
    elapsed = time.monotonic() - started
    blob = f"{proc.stdout}\n{proc.stderr}"

    match = None
    for match in RESULTS_RE.finditer(blob):
        pass  # the LAST Results line is the suite's own summary
    if match is None:
        # An import error, a crash, or malformed output. Never a skip, never a pass.
        tail = "\n".join(x for x in blob.strip().splitlines()[-8:] if x.strip())
        return False, f"NO RESULTS LINE (exit {proc.returncode})\n{tail}", 0, 0, 0, elapsed

    passed, total, failed = int(match.group(1)), int(match.group(2)), int(match.group(3))
    skipped = len(SKIP_RE.findall(blob))
    # Both conditions matter: a suite can print 0 failed and still exit nonzero (teardown, or a
    # crash after its summary), and a suite can exit 0 while reporting failures.
    if failed or proc.returncode != 0:
        failing = [x.strip() for x in blob.splitlines() if x.strip().startswith("FAIL")]
        detail = f"{failed} failed of {total} (exit {proc.returncode})"
        if failing:
            detail += "\n" + "\n".join("      " + x for x in failing[:12])
            if len(failing) > 12:
                detail += f"\n      ... and {len(failing) - 12} more"
        return False, detail, passed, failed, skipped, elapsed
    return True, f"{passed}/{total}" + (f" ({skipped} skipped)" if skipped else ""), passed, failed, skipped, elapsed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--suite", default="blocking", choices=(*EXECUTED, "all"),
                    help="'all' runs every executed category -- what CI uses")
    ap.add_argument("--list", dest="list_suite", choices=CATEGORIES,
                    help="print the category's suites and exit")
    ap.add_argument("--check-manifest", action="store_true",
                    help="validate the closed-world classification and exit")
    args = ap.parse_args(argv)

    sections, problems = load_manifest()
    errors = validate_manifest(sections, problems)
    if errors:
        print("MANIFEST INVALID -- CI cannot run against an open-world classification.\n",
              file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return MANIFEST_ERROR

    if args.check_manifest:
        total = sum(len(v) for v in sections.values())
        print(f"manifest OK: {total} test file(s), each classified exactly once")
        for cat in CATEGORIES:
            mark = "run by CI" if cat in EXECUTED else "not executed"
            print(f"  {cat:<22} {len(sections[cat]):>3}   ({mark})")
        return 0

    if args.list_suite:
        for name in sections[args.list_suite]:
            print(name)
        return 0

    names = ([n for cat in EXECUTED for n in sections[cat]]
             if args.suite == "all" else sections[args.suite])
    if not names:
        print(f"manifest classifies no suites as '{args.suite}'", file=sys.stderr)
        return MANIFEST_ERROR

    before = tracked_snapshot()
    print(f"AUXSAYS integrity runner -- category '{args.suite}': {len(names)} suite(s)")
    print(f"repo {REPO}  python {sys.version.split()[0]}  platform {sys.platform}")
    print("=" * 84)

    failures: list[tuple[str, str]] = []
    skipped_suites: list[tuple[str, int]] = []
    total_passed = total_failed = total_skipped = 0
    started = time.monotonic()
    for i, name in enumerate(names, 1):
        ok, detail, passed, failed, skipped, secs = run_one(name)
        total_passed += passed
        total_failed += failed
        total_skipped += skipped
        if skipped:
            skipped_suites.append((name, skipped))
        head, *rest = detail.splitlines() or [""]
        print(f"  [{i:>2}/{len(names)}] {'PASS' if ok else 'FAIL'}  {name:<52} {head}  ({secs:.1f}s)",
              flush=True)
        for line in rest:
            print(line, flush=True)
        if not ok:
            failures.append((name, detail))

    elapsed = time.monotonic() - started
    print("=" * 84)
    print(f"category       : {args.suite}")
    print(f"suites run     : {len(names)}")
    print(f"suites failed  : {len(failures)}")
    print(f"checks passed  : {total_passed}")
    print(f"checks failed  : {total_failed}")
    print(f"checks skipped : {total_skipped}")
    print(f"duration       : {elapsed:.1f}s")

    if skipped_suites:
        print("\nsuites that SKIPPED assertions (optional tooling absent -- coverage is reduced):")
        for name, n in skipped_suites:
            print(f"  - {name}: {n} skipped")

    exit_code = 1 if failures else 0
    if failures:
        print("\nfailing suites:")
        for name, detail in failures:
            print(f"  - {name}: {detail.splitlines()[0]}")

    if before is None:
        print("\nworking-tree check: SKIPPED (git unavailable)")
    else:
        moved = diff_snapshots(before, tracked_snapshot() or {})
        if moved:
            print(f"\nworking-tree check: FAILED -- {len(moved)} tracked file(s) changed")
            for p in moved[:25]:
                print(f"  {p}")
            if len(moved) > 25:
                print(f"  ... and {len(moved) - 25} more")
            print("A test mutated the checkout. CI must never write production files.")
            exit_code = max(exit_code, MUTATION_ERROR)
        else:
            print("\nworking-tree check: clean (no tracked file added, modified or removed)")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
