#!/usr/bin/env python3
"""Deterministic tests for the conflict-safe automation writeback helper.

Each case builds a throwaway bare "origin" repo plus one or more clones, exercises
lib/automation_writeback.run_writeback against a real git remote, and asserts the outcome
tokens, the remote state, and that no forbidden git operation is ever used. No network.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_automation_writeback.py
"""
from __future__ import annotations

import json
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


class Sleeper:
    """Records requested backoff delays instead of sleeping."""
    def __init__(self): self.calls: list = []
    def __call__(self, s): self.calls.append(s)


_PAGES_MOCK = r"""
import os, sys
counter, fail_until, marker = sys.argv[1], int(sys.argv[2]), sys.argv[3]
n = (int(open(counter).read()) if os.path.exists(counter) else 0) + 1
open(counter, "w").write(str(n))
if n <= fail_until:
    sys.exit(1)          # simulate a Pages dispatch (or auth) failure
open(marker, "a").write("x"); sys.exit(0)
"""


def pages_env(tmp: Path):
    """Return (make_pages_cmd, counter, marker). make_pages_cmd(fail_until) yields a shell
    command that fails the first `fail_until` invocations then succeeds and touches marker."""
    script = tmp / "pages_mock.py"; script.write_text(_PAGES_MOCK, encoding="utf-8")
    counter = tmp / "pages_counter"; marker = tmp / "pages_marker"
    def make(fail_until: int) -> str:
        return f'"{sys.executable}" "{script.as_posix()}" "{counter.as_posix()}" {fail_until} "{marker.as_posix()}"'
    return make, counter, marker


def status_cmd(tmp: Path, runs: list) -> str:
    """A mocked `gh run list` that prints the given pages-run records as JSON."""
    n = len(list(tmp.glob("status_*.json")))
    f = tmp / f"status_{n}.json"; f.write_text(json.dumps(runs), encoding="utf-8")
    return f'"{sys.executable}" -c "import sys;sys.stdout.write(open(r\'{f.as_posix()}\').read())"'


def dep_run(sha, branch="main", status="completed", conclusion="success"):
    return {"databaseId": 1, "headSha": sha, "headBranch": branch, "status": status, "conclusion": conclusion}


def push_material(tmp: Path, origin: Path, rel: str, content: str, msg: str) -> str:
    """A concurrent writer pushes a site-affecting commit to origin/main; returns its SHA."""
    d = clone(tmp, origin, f"pusher_{rel.replace('/','_')}_{msg.replace(' ','_')}")
    write(d, rel, content); g(d, "add", "-A"); g(d, "commit", "-m", msg); g(d, "push", "origin", "main")
    return g(origin, "rev-parse", "main").stdout.strip()


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

    # ===== Part H: bounded Pages dispatch + no-change deployment recovery ==================

    # H1/H2: material push; first dispatch fails, second succeeds (deterministic backoff recorded)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        mk, counter, marker = pages_env(tmp); slp = Sleeper()
        write(work, "records/rec-acrobat.md", "H2\n")
        r = aw.run_writeback(cfg(work, pages_cmd=mk(1), sleep_fn=slp))
        check("H2 push ok + Pages succeeded on retry", r.ok and r.pages_dispatched and aw.PAGES_DISPATCH_SUCCESS in r.outcomes)
        check("H2 exactly 2 dispatch attempts", r.pages_attempts == 2, str(r.pages_attempts))
        check("H2 backoff applied deterministically [5]", r.pages_backoff_applied == [5] and slp.calls == [5], str(r.pages_backoff_applied))
        check("H2 push not repeated (single commit on main)", origin_head(origin) == r.pushed_sha)

    # H3/H5/H19/H21/H22: material push; all dispatch attempts fail -> deployment_pending, fail visibly
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        mk, counter, marker = pages_env(tmp); slp = Sleeper()
        write(work, "records/rec-acrobat.md", "H3\n")
        r = aw.run_writeback(cfg(work, pages_cmd=mk(99), sleep_fn=slp, pages_max_attempts=3))
        check("H3 push succeeded (not claimed as push failure)", r.pushed and r.pushed_sha == origin_head(origin))
        check("H3 deployment_pending set, overall fails visibly", r.deployment_pending and not r.ok)
        check("H3 pages_dispatch_failed emitted, never success", aw.PAGES_DISPATCH_FAILED in r.outcomes and aw.PAGES_DISPATCH_SUCCESS not in r.outcomes)
        check("H21 dispatch attempts bounded to max (3)", r.pages_attempts == 3, str(r.pages_attempts))
        check("H22 backoff sequence deterministic [5,15]", r.pages_backoff_applied == [5, 15] and slp.calls == [5, 15])
        check("H4 git push not repeated on dispatch failure", origin_head(origin) == r.pushed_sha)

    # H6/H23: later no-change run detects a missing deployment for the current main SHA -> dispatch
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        M = push_material(tmp, origin, "records/rec-a.md", "site change\n", "Update automated patch evidence")
        mk, counter, marker = pages_env(tmp)
        r = aw.run_writeback(cfg(work, pages_cmd=mk(0), deploy_recovery=True,
                                  recovery_site_paths=["records/*.md"], pages_status_cmd=status_cmd(tmp, [])))
        check("H6 no_changes + deployment_missing + dispatch success", aw.NO_CHANGES in r.outcomes and aw.DEPLOYMENT_MISSING in r.outcomes and r.pages_dispatched)
        check("H6 recovery did NOT push or fabricate a commit", not r.pushed and not r.changed and r.local_commit_sha == "")
        check("H23 recovery targeted current origin/main SHA", r.origin_sha_latest == M, r.origin_sha_latest)
        check("H6 pages actually invoked (marker written)", marker.exists())

    # H7: later no-change run sees the current main SHA already deployed -> skip dispatch
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        M = push_material(tmp, origin, "records/rec-a.md", "site change\n", "Update automated patch evidence")
        mk, counter, marker = pages_env(tmp)
        r = aw.run_writeback(cfg(work, pages_cmd=mk(0), deploy_recovery=True, recovery_site_paths=["records/*.md"],
                                  pages_status_cmd=status_cmd(tmp, [dep_run(M)])))
        check("H7 deployment_current, no dispatch", aw.DEPLOYMENT_CURRENT in r.outcomes and aw.DEPLOYMENT_MISSING not in r.outcomes)
        check("H7 pages NOT invoked", not marker.exists() and not r.pages_dispatched and r.ok)

    # H8-H11: insufficient deployment evidence for the exact current SHA -> recovery dispatches
    insufficient = {
        "H8 older successful SHA": lambda M: [dep_run("deadbeef" * 5)],
        "H9 success on another branch": lambda M: [dep_run(M, branch="feature/x")],
        "H10 queued/in-progress run": lambda M: [dep_run(M, status="in_progress", conclusion=None), dep_run(M, status="queued", conclusion=None)],
        "H11 failed/cancelled run": lambda M: [dep_run(M, conclusion="failure"), dep_run(M, conclusion="cancelled")],
    }
    for label, mk_runs in insufficient.items():
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td); origin, work = setup(tmp)
            M = push_material(tmp, origin, "records/rec-a.md", "s\n", "Update automated patch evidence")
            mk, counter, marker = pages_env(tmp)
            r = aw.run_writeback(cfg(work, pages_cmd=mk(0), deploy_recovery=True, recovery_site_paths=["records/*.md"],
                                      pages_status_cmd=status_cmd(tmp, mk_runs(M))))
            check(f"{label} is insufficient -> recovery dispatches", aw.DEPLOYMENT_MISSING in r.outcomes and marker.exists())

    # H18: a no-change patch-ingest run does NOT assume site responsibility for a non-owned commit
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        M = push_material(tmp, origin, "records/rec-a.md", "s\n", "Update automated patch evidence")  # evidence, not ingest
        mk, counter, marker = pages_env(tmp)
        r = aw.run_writeback(cfg(work, pages_cmd=mk(0), deploy_recovery=True, recovery_site_paths=["records/*.md"],
                                  recovery_commit_grep="Ingest official patch records",
                                  pages_status_cmd=status_cmd(tmp, [])))
        check("H18 patch-ingest abstains from a non-ingest commit (no dispatch)",
              aw.DEPLOYMENT_MISSING not in r.outcomes and not marker.exists() and aw.DEPLOYMENT_CURRENT in r.outcomes)

    # H16/H17: patch-ingest site-responsibility distinction (state-only vs generated record)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        mk, counter, marker = pages_env(tmp)
        write(work, "data/consensus_evidence.yml", "evidence:\n  - x\n")  # non-site (state-like)
        r = aw.run_writeback(cfg(work, pages_cmd=mk(0), site_paths=["records/*.md"]))
        check("H16 state-only push: changed=true deploy_changed=false no Pages",
              r.changed and not r.deploy_changed and not marker.exists() and aw.PAGES_DISPATCH_SKIPPED_NO_CHANGES in r.outcomes)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        mk, counter, marker = pages_env(tmp)
        write(work, "records/rec-acrobat.md", "record\n")  # site-affecting
        r = aw.run_writeback(cfg(work, pages_cmd=mk(0), site_paths=["records/*.md"]))
        check("H17 generated-record push: changed=true deploy_changed=true Pages dispatched",
              r.changed and r.deploy_changed and marker.exists() and r.pages_dispatched)

    # H13/H14: failure paths never dispatch Pages (with a real pages_cmd present)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "wc"); push_change(other, "records/rec-shared.md", "wb\nline2\nline3\nline4\nline5\n", "up")
        mk, counter, marker = pages_env(tmp)
        write(work, "records/rec-shared.md", "wa\nline2\nline3\nline4\nline5\n")
        r = aw.run_writeback(cfg(work, pages_cmd=mk(0)))
        check("H13 rebase conflict never dispatches Pages", r.outcome == aw.REBASE_CONFLICT and not marker.exists())
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        other = clone(tmp, origin, "wc"); push_change(other, "records/rec-b.md", "up\n", "up")
        mk, counter, marker = pages_env(tmp)
        write(work, "records/rec-acrobat.md", "x\n")
        r = aw.run_writeback(cfg(work, pages_cmd=mk(0), validate=[PY_FAIL]))
        check("H14 validation failure never dispatches Pages", r.outcome == aw.VALIDATION_FAILED_AFTER_REBASE and not marker.exists())

    # H24: output-contract fields exist and are consistent
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = setup(tmp)
        mk, counter, marker = pages_env(tmp)
        write(work, "records/rec-acrobat.md", "out\n")
        r = aw.run_writeback(cfg(work, pages_cmd=mk(0)))
        d = r.as_dict()
        check("H24 output contract keys present", all(k in d for k in ("changed", "deploy_changed", "pushed", "pushed_sha", "deployment_pending")))
        check("H24 push success -> changed/pushed true, deployment_pending false", d["changed"] and d["pushed"] and not d["deployment_pending"])
        r2 = aw.run_writeback(cfg(work, pages_cmd=mk(0)))  # now a genuine no-op (no recovery configured)
        check("H24 no_changes does not set changed=true", r2.outcome == aw.NO_CHANGES and not r2.changed and not r2.pushed)

    # ===== Part S: staged-tree equivalence -- VALIDATED TREE == COMMITTED TREE ============
    # `git add -- <allow>` builds the candidate in the INDEX, but validators are ordinary
    # subprocesses reading the WORKING TREE. Anything the tree holds and the candidate does not
    # can therefore make a validator pass on state git will never publish. These cases pin the
    # fail-closed gate that removes that gap, and pin the transients that must still be tolerated.

    def s_setup(tmp: Path):
        """Origin + work seeded with a COHERENT pair (evidence_count 0 / record_count 0) and a
        .gitignore, mirroring the real lanes where every transient artefact is ignored."""
        origin, work = setup(tmp)
        g(work, "config", "user.name", "bot"); g(work, "config", "user.email", "bot@x")
        seedS = clone(tmp, origin, "seedS")
        write(seedS, "data/consensus_evidence.yml", "evidence_count: 0\n")
        write(seedS, "records/rec-obs.md", "record_count: 0\n")
        write(seedS, ".gitignore", "qa_status.json\nconsensus_status.json\n")
        g(seedS, "add", "-A"); g(seedS, "commit", "-m", "coherent pair"); g(seedS, "push", "origin", "main")
        g(work, "fetch", "origin", "main"); g(work, "reset", "--hard", "origin/main")
        return origin, work

    def coherence(tmp: Path, target: Path) -> str:
        """A stand-in for qa_patch_records.scan_evidence_count_alignment: passes only when the
        evidence count and the generated-record count agree in whatever tree it is pointed at."""
        v = tmp / "coherence.py"
        if not v.exists():
            v.write_text(_COHERENCE_SCRIPT, encoding="utf-8")
        return f'"{sys.executable}" "{v.as_posix()}" "{target.as_posix()}"'

    # S1. THE DEFECT: allowed evidence staged + an UNALLOWED record modified in the working tree.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        vcmd = coherence(tmp, work)
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")   # allowed -> staged
        write(work, "records/rec-obs.md", "record_count: 1\n")              # NOT allowed
        pre = subprocess.run(vcmd, shell=True, capture_output=True)
        check("S1 the working tree is coherent, so the validator passes when run there",
              pre.returncode == 0)
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml"],
                                 validate=[vcmd], validate_before_commit=True, pages_cmd=None))
        check("S1 REFUSED with unstaged_changed_path", r.outcome == aw.UNSTAGED_CHANGED_PATH, r.outcome)
        check("S1 the unallowed record is named in the outcome",
              "records/rec-obs.md" in r.conflicting_paths, str(r.conflicting_paths))
        check("S1 validation was NOT executed", r.validation == [], str(r.validation))
        check("S1 no commit was created", g(work, "rev-parse", "HEAD").stdout.strip() == before)
        check("S1 nothing pushed", r.pushed is False)
        check("S1 origin byte-identical", origin_head(origin) == before)
        check("S1 index reset -- nothing left staged",
              g(work, "diff", "--cached", "--name-only").stdout.strip() == "")
        check("S1 the mutation is NOT discarded (left visible for diagnosis, never stashed)",
              "record_count: 1" in (work / "records" / "rec-obs.md").read_text(encoding="utf-8"))
        # Demonstrate the defect itself: committing only the allowed half yields a revision the
        # very same validator rejects -- which is what main received before this gate existed.
        g(work, "add", "--", "data/consensus_evidence.yml")
        g(work, "commit", "-m", "allowed half only (defect demonstration)")
        ver = tmp / "verifyS1"; g(tmp, "clone", "-q", str(work), str(ver))
        post = subprocess.run(coherence(tmp, ver), shell=True, capture_output=True)
        check("S1 DEFECT PROVEN: committing only the allowed half yields an INCOHERENT revision",
              post.returncode != 0)

    # S2. Allowed material only, clean remainder -> validation runs and the commit lands.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        vcmd = coherence(tmp, work)
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")
        write(work, "records/rec-obs.md", "record_count: 1\n")
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml", "records/*.md"],
                                 validate=[vcmd], validate_before_commit=True, pages_cmd=None))
        check("S2 normal writeback still succeeds when the candidate covers the mutation",
              r.pushed is True, r.outcome)
        check("S2 origin advanced", origin_head(origin) != before)
        check("S2 validation actually ran", len(r.validation) == 1, str(r.validation))
        ver = tmp / "verifyS2"; g(tmp, "clone", "-q", str(origin), str(ver))
        check("S2 the COMMITTED revision is coherent",
              subprocess.run(coherence(tmp, ver), shell=True, capture_output=True).returncode == 0)

    # S3. Unallowed tracked DELETION -> refused (the real lanes' `rm -f` of tracked _data files).
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")
        (work / "records" / "rec-obs.md").unlink()
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml"], pages_cmd=None))
        check("S3 unallowed tracked DELETION is refused", r.outcome == aw.UNSTAGED_CHANGED_PATH, r.outcome)
        check("S3 the deleted path is named", "records/rec-obs.md" in r.conflicting_paths,
              str(r.conflicting_paths))
        check("S3 origin unchanged", origin_head(origin) == before)

    # S4. Unallowed NON-IGNORED UNTRACKED file -> refused. This is the sharpest case: a brand-new
    # generated record for a product outside --allow is readable by QA and never committed.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")
        write(work, "records/rec-newproduct.md", "record_count: 1\n")
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml"], pages_cmd=None))
        check("S4 unallowed untracked file is refused", r.outcome == aw.UNSTAGED_CHANGED_PATH, r.outcome)
        check("S4 the untracked path is named", "records/rec-newproduct.md" in r.conflicting_paths,
              str(r.conflicting_paths))
        check("S4 origin unchanged", origin_head(origin) == before)

    # S5. IGNORED untracked transients must NOT refuse -- every real lane produces these.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")
        write(work, "records/rec-obs.md", "record_count: 1\n")
        write(work, "qa_status.json", '{"status":"transient"}\n')
        write(work, "consensus_status.json", '{"status":"transient"}\n')
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml", "records/*.md"],
                                 pages_cmd=None))
        check("S5 gitignored transients do NOT trigger a refusal", r.pushed is True, r.outcome)
        check("S5 origin advanced", origin_head(origin) != before)

    # S6. Validator failure still blocks the commit (pre-existing gate intact).
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml"],
                                 validate=[PY_FAIL], validate_before_commit=True, pages_cmd=None))
        check("S6 validator failure -> validation_failed_pre_commit",
              r.outcome == aw.VALIDATION_FAILED_PRE_COMMIT, r.outcome)
        check("S6 no commit reached origin", origin_head(origin) == before)

    # S7. PRECEDENCE: a forbidden path that actually reaches the index still reports the existing
    # staged-path outcome, not the new one -- the old protection is unchanged.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        write(work, "_site/index.html", "<html></html>\n")
        r = aw.run_writeback(cfg(work, allow=["_site/*"], pages_cmd=None))
        check("S7 forbidden STAGED path keeps unexpected_changed_path (precedence preserved)",
              r.outcome == aw.UNEXPECTED_CHANGED_PATH, r.outcome)

    # S8. An allowed NEW file is staged by the pathspec and must NOT read as residual untracked.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        before = origin_head(origin)
        write(work, "records/rec-brandnew.md", "record_count: 0\n")
        r = aw.run_writeback(cfg(work, allow=["records/*.md"], pages_cmd=None))
        check("S8 an allowed NEW file commits normally (not mistaken for residual)",
              r.pushed is True, r.outcome)
        check("S8 the new file reached origin",
              "record_count" in read_origin(origin, "records/rec-brandnew.md"))
        check("S8 origin advanced", origin_head(origin) != before)

    # S9. Multiple allowed paths -> all validated and all committed together.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        vcmd = coherence(tmp, work)
        write(work, "data/consensus_evidence.yml", "evidence_count: 2\n")
        write(work, "records/rec-obs.md", "record_count: 2\n")
        write(work, "data/evidence_method_health.yml", "schema_version: 1\nmethods:\n  - z\n")
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml", "records/*.md",
                                              "data/evidence_method_health.yml"],
                                 validate=[vcmd], validate_before_commit=True, pages_cmd=None))
        check("S9 multiple allowed paths commit together", r.pushed is True, r.outcome)
        committed = set(g(origin, "show", "--name-only", "--pretty=format:", "main").stdout.split())
        check("S9 every allowed mutation is in the commit",
              {"data/consensus_evidence.yml", "records/rec-obs.md",
               "data/evidence_method_health.yml"} <= committed, str(sorted(committed)))
        ver = tmp / "verifyS9"; g(tmp, "clone", "-q", str(origin), str(ver))
        check("S9 the committed revision is coherent",
              subprocess.run(coherence(tmp, ver), shell=True, capture_output=True).returncode == 0)

    # S10. THE RETRY PATH IS LOAD-BEARING. Residual appearing after the first gate must still be
    # caught on the post-rebase revalidation -- an untracked file survives a clean rebase.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        other = clone(tmp, origin, "workB")
        hook_script = tmp / "residual_drift.py"
        hook_script.write_text(_RESIDUAL_DRIFT_SCRIPT, encoding="utf-8")
        hook = (f'"{sys.executable}" "{hook_script.as_posix()}" '
                f'"{other.as_posix()}" "{work.as_posix()}"')
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml"],
                                 test_hook_before_push=hook, test_hook_fires=1,
                                 max_retries=5, pages_cmd=None))
        check("S10 post-rebase residual is refused on the retry path",
              r.outcome == aw.UNSTAGED_CHANGED_PATH, r.outcome)
        check("S10 the late untracked path is named",
              any("rec-late" in p for p in r.conflicting_paths), str(r.conflicting_paths))
        check("S10 nothing was pushed by this run", r.pushed is False)
        check("S10 only the concurrent writer's commit is on origin",
              origin_head(origin) != before and
              "evidence_count: 1" not in read_origin(origin, "data/consensus_evidence.yml"))

    # S11. No-change deployment recovery is unchanged by the gate.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        make_pages, _counter, marker = pages_env(tmp)
        sha = origin_head(origin)
        g(work, "fetch", "origin", "main"); g(work, "reset", "--hard", "origin/main")
        r = aw.run_writeback(cfg(work, allow=["records/*.md"], pages_cmd=make_pages(0),
                                 deploy_recovery=True, recovery_site_paths=["records/*.md"],
                                 pages_status_cmd=status_cmd(tmp, [dep_run(sha, conclusion="failure")]),
                                 sleep_fn=Sleeper()))
        check("S11 clean no-change run still reports no_changes", r.outcome == aw.NO_CHANGES, r.outcome)
        check("S11 deployment recovery still dispatched Pages", marker.exists())

    # S12. Pages dispatch on a normal material push is unchanged.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        make_pages, counter, marker = pages_env(tmp)
        write(work, "records/rec-obs.md", "record_count: 0\npages\n")
        r = aw.run_writeback(cfg(work, allow=["records/*.md"], site_paths=["records/*.md"],
                                 pages_cmd=make_pages(0), sleep_fn=Sleeper()))
        check("S12 material push still dispatches Pages exactly once",
              r.pushed is True and r.pages_dispatched is True and counter.read_text().strip() == "1",
              f"{r.outcome} attempts={r.pages_attempts}")

    # S13. The measured PowerPoint half-promotion is now unreachable: evidence + health allowed,
    # the product's generated record NOT allowed -- exactly the production --allow list shape.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        vcmd = coherence(tmp, work)
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")          # allowed
        write(work, "data/evidence_method_health.yml", "schema_version: 1\nmethods:\n  - ppt\n")
        write(work, "records/rec-obs.md", "record_count: 1\n")                     # NOT allowed
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml",
                                              "data/evidence_method_health.yml"],
                                 validate=[vcmd], validate_before_commit=True, pages_cmd=None))
        check("S13 half-promotion refused: evidence+health cannot land without the record",
              r.outcome == aw.UNSTAGED_CHANGED_PATH, r.outcome)
        check("S13 origin never received the evidence half", origin_head(origin) == before)
        check("S13 no half-promoted revision exists",
              "evidence_count: 1" not in read_origin(origin, "data/consensus_evidence.yml"))

    # S14. The measured real-lane residue -- two TRACKED files deleted by the cleanup step and
    # absent from every --allow list -- is refused, which is why the caller cleanup had to change
    # from `rm -f` to a restore. Without that caller fix these lanes would refuse every run.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        seedT = clone(tmp, origin, "seedT")
        write(seedT, "data/source_health.yml", "generated: telemetry\n")
        write(seedT, "data/patch_ingest_state.json", '{"sources":{}}\n')
        g(seedT, "add", "-A"); g(seedT, "commit", "-m", "tracked transients"); g(seedT, "push", "origin", "main")
        g(work, "fetch", "origin", "main"); g(work, "reset", "--hard", "origin/main")
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")
        (work / "data" / "source_health.yml").unlink()          # the old `rm -f`
        (work / "data" / "patch_ingest_state.json").unlink()    # the old `rm -f`
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml"], pages_cmd=None))
        check("S14 the old `rm -f` of tracked files would refuse the run",
              r.outcome == aw.UNSTAGED_CHANGED_PATH, r.outcome)
        check("S14 both deleted tracked files are named",
              {"data/source_health.yml", "data/patch_ingest_state.json"} <= set(r.conflicting_paths),
              str(r.conflicting_paths))
        # the replacement cleanup restores them instead, and the run proceeds normally
        g(work, "checkout", "--", "data/source_health.yml", "data/patch_ingest_state.json")
        r2 = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml"], pages_cmd=None))
        check("S14 restoring them instead lets the writeback proceed", r2.pushed is True, r2.outcome)

    # S15. The complete refusal contract, with a REAL pages_cmd present: residual paths reported,
    # validation not executed, no commit, no push, no Pages dispatch, and ok=False so the CLI
    # exits non-zero and the workflow step fails visibly rather than passing quietly.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td); origin, work = s_setup(tmp)
        make_pages, counter, marker = pages_env(tmp)
        before = origin_head(origin)
        write(work, "data/consensus_evidence.yml", "evidence_count: 1\n")   # allowed
        write(work, "records/rec-obs.md", "record_count: 1\n")              # NOT allowed
        r = aw.run_writeback(cfg(work, allow=["data/consensus_evidence.yml"],
                                 site_paths=["data/consensus_evidence.yml"],
                                 validate=[PY_OK], validate_before_commit=True,
                                 pages_cmd=make_pages(0), sleep_fn=Sleeper()))
        check("S15 outcome is unstaged_changed_path", r.outcome == aw.UNSTAGED_CHANGED_PATH, r.outcome)
        check("S15 residual paths are reported for diagnosis", r.conflicting_paths == ["records/rec-obs.md"],
              str(r.conflicting_paths))
        check("S15 validation not executed", r.validation == [])
        check("S15 commit not created", g(work, "rev-parse", "HEAD").stdout.strip() == before)
        check("S15 push not attempted", r.pushed is False and r.pushed_sha == "")
        check("S15 origin unchanged", origin_head(origin) == before)
        check("S15 Pages NOT dispatched", not marker.exists() and r.pages_dispatched is False
              and r.pages_attempts == 0)
        check("S15 ok=False -> CLI exits non-zero (step fails visibly)", r.ok is False)
        check("S15 the summary payload carries the residual paths",
              bool(r.as_dict().get("conflicting_paths")))
        check("S15 no silent cleanup: the mutation is still on disk",
              "record_count: 1" in (work / "records" / "rec-obs.md").read_text(encoding="utf-8"))
        check("S15 no unallowed path was auto-added to the index",
              g(work, "diff", "--cached", "--name-only").stdout.strip() == "")

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


_COHERENCE_SCRIPT = r"""
import re, sys, pathlib
repo = pathlib.Path(sys.argv[1])
def count(rel, key):
    fp = repo / rel
    if not fp.exists():
        return 0
    m = re.search(key + r":\s*(\d+)", fp.read_text(encoding="utf-8"))
    return int(m.group(1)) if m else 0
# Stand-in for qa_patch_records.scan_evidence_count_alignment: the evidence count and the
# generated-record count must agree in whichever tree this is pointed at.
sys.exit(0 if count("data/consensus_evidence.yml", "evidence_count")
              == count("records/rec-obs.md", "record_count") else 1)
"""

_RESIDUAL_DRIFT_SCRIPT = r"""
import os, subprocess, sys
other, work = sys.argv[1], sys.argv[2]
def g(repo, *a):
    subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True)
# A concurrent writer advances origin so the next attempt must rebase...
g(other, "fetch", "origin", "main"); g(other, "reset", "--hard", "origin/main")
g(other, "config", "user.name", "drift"); g(other, "config", "user.email", "drift@x")
p = os.path.join(other, "records", "rec-drift.md")
os.makedirs(os.path.dirname(p), exist_ok=True)
open(p, "a", encoding="utf-8").write("drift\n")
g(other, "add", "-A"); g(other, "commit", "-m", "concurrent drift"); g(other, "push", "origin", "main")
# ...and a late, non-ignored UNTRACKED file appears in the bot's tree AFTER the first gate.
# An untracked file does not block `git rebase`, so only the post-rebase gate can catch it.
late = os.path.join(work, "records", "rec-late.md")
open(late, "w", encoding="utf-8").write("record_count: 99\n")
"""


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
