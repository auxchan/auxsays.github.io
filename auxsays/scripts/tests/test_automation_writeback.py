#!/usr/bin/env python3
"""Deterministic tests for the conflict-safe automation writeback helper.

Each case builds a throwaway bare "origin" repo plus one or more clones, exercises
lib/automation_writeback.run_writeback against a real git remote, and asserts the outcome
tokens, the remote state, and that no forbidden git operation is ever used. No network.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_automation_writeback.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import automation_writeback as aw  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

PY_OK = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
PY_FAIL = f'"{sys.executable}" -c "import sys; sys.exit(1)"'

ALLOW = ["data/consensus_evidence.yml", "data/evidence_method_health.yml", "records/*.md"]


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def g(repo: Path, *args: str, check_rc: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check_rc and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {p.returncode}: {p.stderr}")
    return p


def write(repo: Path, rel: str, content: str) -> None:
    fp = repo / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")


def read_origin(origin: Path, rel: str) -> str:
    return g(origin, "show", f"main:{rel}", check_rc=False).stdout


def origin_head(origin: Path) -> str:
    return g(origin, "rev-parse", "main").stdout.strip()


def setup(tmp: Path) -> tuple[Path, Path]:
    """Create a bare origin seeded with baseline files, plus one working clone on main."""
    origin = tmp / "origin.git"
    g(tmp, "init", "--bare", "-b", "main", str(origin))
    seed = tmp / "seed"
    g(tmp, "clone", str(origin), str(seed))
    g(seed, "config", "user.name", "seed"); g(seed, "config", "user.email", "seed@x")
    write(seed, "data/consensus_evidence.yml", "schema_version: 1\nevidence: []\n")
    write(seed, "data/evidence_method_health.yml", "schema_version: 1\nmethods:\n  - a\n  - b\n  - c\n  - d\n  - e\n")
    write(seed, "records/rec-obs.md", "obs base\n")
    write(seed, "records/rec-acrobat.md", "acrobat base\n")
    write(seed, "records/rec-shared.md", "line1\nline2\nline3\nline4\nline5\n")
    write(seed, "records/rec-ingest.md", "ingest base\n")
    g(seed, "add", "-A"); g(seed, "commit", "-m", "seed")
    g(seed, "push", "origin", "main")
    work = tmp / "workA"
    g(tmp, "clone", str(origin), str(work))
    return origin, work


def clone(tmp: Path, origin: Path, name: str) -> Path:
    dest = tmp / name
    g(tmp, "clone", str(origin), str(dest))
    g(dest, "config", "user.name", name); g(dest, "config", "user.email", f"{name}@x")
    return dest


def push_change(repo: Path, rel: str, content: str, msg: str) -> None:
    """A concurrent writer pushes a change straight to origin/main (fast-forward)."""
    g(repo, "fetch", "origin", "main"); g(repo, "reset", "--hard", "origin/main")
    write(repo, rel, content)
    g(repo, "add", "-A"); g(repo, "commit", "-m", msg); g(repo, "push", "origin", "main")


def cfg(work: Path, **kw) -> aw.WritebackConfig:
    base = dict(repo=work, message="automation writeback", allow=list(ALLOW),
                validate=[PY_OK], max_retries=5, branch="main", remote="origin")
    base.update(kw)
    return aw.WritebackConfig(**base)


def run() -> int:
    print("=" * 64)
    print("Automation writeback helper tests")
    print("=" * 64)

    # 1. No material changes -> no commit, no push, no pages
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        before = origin_head(origin)
        marker = tmp / "pages1"
        r = aw.run_writeback(cfg(work, pages_cmd=f'"{sys.executable}" -c "open(r\'{marker.as_posix()}\',\'a\').write(\'x\')"'))
        check("1 no changes -> no_changes outcome", r.outcome == aw.NO_CHANGES, r.outcome)
        check("1 no commit created", r.local_commit_sha == "")
        check("1 remote unchanged", origin_head(origin) == before)
        check("1 pages NOT dispatched", not marker.exists() and not r.pages_dispatched)

    # 2. No upstream drift -> first push succeeds
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        write(work, "records/rec-acrobat.md", "acrobat NEW\n")
        r = aw.run_writeback(cfg(work))
        check("2 first push success", r.outcome == aw.PUSH_SUCCESS_FIRST_ATTEMPT, r.outcome)
        check("2 remote has the change", "acrobat NEW" in read_origin(origin, "records/rec-acrobat.md"))
        check("2 pushed_sha recorded", r.pushed_sha == origin_head(origin))

    # 3. Non-overlapping upstream commit -> rebase, revalidate, push, upstream preserved
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "workB")
        push_change(other, "records/rec-obs.md", "obs UPSTREAM\n", "upstream obs")  # different file
        write(work, "records/rec-acrobat.md", "acrobat MINE\n")
        r = aw.run_writeback(cfg(work))
        check("3 upstream_advanced detected", aw.UPSTREAM_ADVANCED in r.outcomes)
        check("3 rebase_success", aw.REBASE_SUCCESS in r.outcomes)
        check("3 validation reran after rebase", aw.VALIDATION_SUCCESS_AFTER_REBASE in r.outcomes)
        check("3 push succeeded after retry", r.outcome == aw.PUSH_SUCCESS_AFTER_RETRY, r.outcome)
        check("3 upstream change preserved", "obs UPSTREAM" in read_origin(origin, "records/rec-obs.md"))
        check("3 my change present", "acrobat MINE" in read_origin(origin, "records/rec-acrobat.md"))

    # 4. Upstream advances twice -> bounded second retry, push within limit
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "workB")
        drift = tmp / "drift.py"
        drift.write_text(_DRIFT_SCRIPT, encoding="utf-8")
        hook = f'"{sys.executable}" "{drift.as_posix()}" "{other.as_posix()}"'
        write(work, "records/rec-acrobat.md", "acrobat TWICE\n")
        r = aw.run_writeback(cfg(work, test_hook_before_push=hook, test_hook_fires=2, max_retries=5))
        check("4 push succeeded within retry limit", r.outcome == aw.PUSH_SUCCESS_AFTER_RETRY, r.outcome)
        check("4 required >=2 retries (bounded)", r.retry_number >= 2, f"retry={r.retry_number}")
        check("4 my change present", "acrobat TWICE" in read_origin(origin, "records/rec-acrobat.md"))

    # 5. Retry exhaustion -> clear failure, no force push, no pages
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "workB")
        drift = tmp / "drift.py"; drift.write_text(_DRIFT_SCRIPT, encoding="utf-8")
        hook = f'"{sys.executable}" "{drift.as_posix()}" "{other.as_posix()}"'
        marker = tmp / "pages5"
        write(work, "records/rec-acrobat.md", "acrobat EXHAUST\n")
        r = aw.run_writeback(cfg(work, test_hook_before_push=hook, test_hook_fires=99, max_retries=2,
                                  pages_cmd=f'"{sys.executable}" -c "open(r\'{marker.as_posix()}\',\'a\').write(\'x\')"'))
        check("5 retry exhausted", r.outcome == aw.RETRY_EXHAUSTED, r.outcome)
        check("5 my change NOT on remote", "acrobat EXHAUST" not in read_origin(origin, "records/rec-acrobat.md"))
        check("5 pages NOT dispatched", not marker.exists())

    # 6. Overlapping file conflict -> conflict detected, aborted, remote unchanged, path reported
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "workB")
        push_change(other, "records/rec-shared.md", "workB-line1\nline2\nline3\nline4\nline5\n", "upstream shared")
        upstream_head = origin_head(origin)
        write(work, "records/rec-shared.md", "workA-line1\nline2\nline3\nline4\nline5\n")  # same line
        r = aw.run_writeback(cfg(work))
        check("6 rebase_conflict", r.outcome == aw.REBASE_CONFLICT, r.outcome)
        check("6 conflicting path reported", "records/rec-shared.md" in r.conflicting_paths, str(r.conflicting_paths))
        check("6 remote main unchanged (not overwritten)", origin_head(origin) == upstream_head)
        check("6 upstream content intact", "workB-line1" in read_origin(origin, "records/rec-shared.md"))

    # 7a. Unexpected staged path via a broad allow that matches a forbidden path
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        before = origin_head(origin)
        write(work, "_site/index.html", "<html>\n")
        r = aw.run_writeback(cfg(work, allow=["_site/*", *ALLOW]))
        check("7a forbidden staged path refused", r.outcome == aw.UNEXPECTED_CHANGED_PATH, r.outcome)
        check("7a no commit / remote unchanged", origin_head(origin) == before and r.local_commit_sha == "")
    # 7b. Pre-staged path outside the allow-list is refused
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        before = origin_head(origin)
        write(work, "secret.txt", "nope\n")
        g(work, "add", "secret.txt")  # pre-staged, not in allow
        write(work, "records/rec-acrobat.md", "acrobat X\n")
        r = aw.run_writeback(cfg(work))
        check("7b pre-staged unexpected path refused", r.outcome == aw.UNEXPECTED_CHANGED_PATH, r.outcome)
        check("7b remote unchanged", origin_head(origin) == before)

    # 8. Validation failure after rebase -> push blocked, no pages, remote unchanged
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "workB")
        push_change(other, "records/rec-obs.md", "obs UP8\n", "upstream 8")
        upstream_head = origin_head(origin)
        marker = tmp / "pages8"
        write(work, "records/rec-acrobat.md", "acrobat 8\n")
        r = aw.run_writeback(cfg(work, validate=[PY_FAIL],
                                  pages_cmd=f'"{sys.executable}" -c "open(r\'{marker.as_posix()}\',\'a\').write(\'x\')"'))
        check("8 validation_failed_after_rebase", r.outcome == aw.VALIDATION_FAILED_AFTER_REBASE, r.outcome)
        check("8 remote unchanged (push blocked)", origin_head(origin) == upstream_head)
        check("8 pages NOT dispatched", not marker.exists())

    # 9. patch-ingest updates an unrelated generated record -> evidence commit rebases, preserves it
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "ingest")
        push_change(other, "records/rec-ingest.md", "ingest UPDATED\n", "patch-ingest record")
        write(work, "data/consensus_evidence.yml", "schema_version: 1\nevidence:\n  - id: e1\n")
        write(work, "records/rec-acrobat.md", "acrobat evidence\n")
        r = aw.run_writeback(cfg(work))
        check("9 evidence rebased over unrelated ingest record", r.ok and r.outcome == aw.PUSH_SUCCESS_AFTER_RETRY, r.outcome)
        check("9 ingest record preserved", "ingest UPDATED" in read_origin(origin, "records/rec-ingest.md"))
        check("9 evidence change present", "id: e1" in read_origin(origin, "data/consensus_evidence.yml"))

    # 10. Evidence + patch-ingest update the SAME shared health file -> not silently resolved
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "ingest")
        # upstream edits an EARLY line; workA edits a LATE line -> git would auto-merge cleanly
        push_change(other, "data/evidence_method_health.yml",
                    "schema_version: 1\nmethods:\n  - A_UP\n  - b\n  - c\n  - d\n  - e\n", "upstream health")
        upstream_head = origin_head(origin)
        write(work, "data/evidence_method_health.yml",
              "schema_version: 1\nmethods:\n  - a\n  - b\n  - c\n  - d\n  - e_MINE\n")
        r = aw.run_writeback(cfg(work))
        check("10 shared health-file conflict not silently resolved", r.outcome == aw.REBASE_CONFLICT, r.outcome)
        check("10 shared file reported", "data/evidence_method_health.yml" in r.conflicting_paths, str(r.conflicting_paths))
        check("10 remote unchanged", origin_head(origin) == upstream_head)

    # 11. Successful material push -> Pages dispatch requested exactly once
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        marker = tmp / "pages11"
        write(work, "records/rec-acrobat.md", "acrobat pages\n")
        r = aw.run_writeback(cfg(work, pages_cmd=f'"{sys.executable}" -c "open(r\'{marker.as_posix()}\',\'a\').write(\'1\')"'))
        check("11 push success", r.ok)
        check("11 pages dispatched exactly once", marker.exists() and marker.read_text() == "1", marker.read_text() if marker.exists() else "absent")
        check("11 pages_dispatch_success emitted", aw.PAGES_DISPATCH_SUCCESS in r.outcomes)

    # 12. No-op -> Pages dispatch not requested (and site-path gating: state-only change -> no pages)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        marker = tmp / "pages12"
        pages = f'"{sys.executable}" -c "open(r\'{marker.as_posix()}\',\'a\').write(\'1\')"'
        r = aw.run_writeback(cfg(work, pages_cmd=pages))  # no working-tree change
        check("12 no-op -> no pages", not marker.exists() and aw.PAGES_DISPATCH_SKIPPED_NO_CHANGES in r.outcomes)
        # site-path gating: change a NON-site allowed file only -> material push but no pages
        write(work, "data/evidence_method_health.yml", "schema_version: 1\nmethods:\n  - z\n")
        r2 = aw.run_writeback(cfg(work, pages_cmd=pages, site_paths=["records/*.md"]))
        check("12 state-only change pushes but does NOT dispatch pages",
              r2.ok and not r2.deploy_changed and not marker.exists(), f"deploy_changed={r2.deploy_changed}")

    # 13. Source inspection -> no force-push / ours-theirs USAGE (ignore the docstring/comments,
    # which legitimately document the prohibition).
    import ast
    src = (_REPO / "auxsays" / "scripts" / "lib" / "automation_writeback.py").read_text(encoding="utf-8")
    doc = ast.get_docstring(ast.parse(src), clean=False)
    code_only = src.replace(doc, "") if doc else src
    code_only = "\n".join(ln for ln in code_only.splitlines() if not ln.lstrip().startswith("#"))
    for banned in ("--force", "force-with-lease", "checkout --ours", "checkout --theirs",
                   "-X ours", "-X theirs", "-Xours", "-Xtheirs", '"--ours"', '"--theirs"'):
        check(f"13 helper code never uses '{banned}'", banned not in code_only)

    print()
    print("=" * 64)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 64)
    return 0 if _FAIL == 0 else 1


_DRIFT_SCRIPT = r"""
import os, subprocess, sys
work = sys.argv[1]
def g(*a):
    subprocess.run(["git", "-C", work, *a], check=True, capture_output=True)
cf = os.path.join(work, ".drift_counter")
n = (int(open(cf).read()) if os.path.exists(cf) else 0) + 1
open(cf, "w").write(str(n))
g("fetch", "origin", "main"); g("reset", "--hard", "origin/main")
g("config", "user.name", "drift"); g("config", "user.email", "drift@x")
p = os.path.join(work, "records", "rec-drift.md")
os.makedirs(os.path.dirname(p), exist_ok=True)
open(p, "a", encoding="utf-8").write("drift %d\n" % n)
g("add", "-A"); g("commit", "-m", "drift %d" % n); g("push", "origin", "main")
"""


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
