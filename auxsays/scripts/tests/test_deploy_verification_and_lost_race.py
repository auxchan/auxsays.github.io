#!/usr/bin/env python3
"""G91: a deployment is verified after material writeback, and a lost writeback race is re-run.

TWO GAPS, BOTH IN THE STEP AFTER THE EVIDENCE IS ALREADY CORRECT
-----------------------------------------------------------------
A. Every writer lane dispatched Pages after a material push and stopped there. `gh workflow run`
   returning 0 proves only that the DISPATCH was accepted; no lane ever looked at the build, so a
   Pages build that failed or never started left a correct commit undeployed with every lane green.
   The writeback already had an opt-in poll (`--pages-confirm-build`); no workflow passed it.
B. Run 44878227542 lost its whole collection cycle: a PR touching the evidence store merged while it
   ran, the writeback correctly refused to merge the two (`rebase_conflict`), pushed nothing and
   exited 1 -- and nothing re-ran the cycle. The writer-queue reaper repairs runs EVICTED from the
   queue, not runs that failed, so the next attempt was the next scheduled cycle, ~12 hours later.

WHAT IS PINNED, AND HOW
-----------------------
[A] the writeback's build confirmation, against a throwaway bare origin and a scripted run list:
    confirmed / failed / never appeared / never finished / unreadable, the outputs each sets, and that
    no outcome re-pushes or reverts the data commit. Also the no-change --deploy-recovery path.
[B] the `lost_race` classification: true for exactly the three race outcomes, false for a pushed run
    whatever its Pages build did, false for refused pushes while main did not move, false for a
    residual-file refusal that merely happened after main moved.
[C] the same contract through the BARE SCRIPT, the way every workflow runs it, reading the real
    $GITHUB_OUTPUT / $GITHUB_STEP_SUMMARY / annotations it writes.
[D] the workflow wiring, parsed: each writer's real argument list is fed to the writeback's own
    argparse parser (never matched as text); the confirm bound fits each job's budget; the outputs
    chain-ingest reads are the ones the writeback writes; a recovery run is still routine.
[E] the two recovery steps' shell, EXECUTED under bash against a fake `gh`, in every state that
    matters -- including a discriminating fake that reports a waiting writer run only to a query that
    asks about the `pending` state.

Deterministic, offline, writes nothing outside its temporary directories.
Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_deploy_verification_and_lost_race.py
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

from lib import automation_writeback as aw  # noqa: E402

WORKFLOWS = _REPO / ".github" / "workflows"
SCRIPT = _REPO / "auxsays" / "scripts" / "lib" / "automation_writeback.py"
EVIDENCE_WF = "obs-evidence-collection.yml"
INGEST_WF = "patch-ingest.yml"
WRITER_GROUP = "auxsays-main-writeback"
NEWLINE = "\n"

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


# --------------------------------------------------------------------------------------------------
# git fixtures (a bare origin and a working clone; no network)
# --------------------------------------------------------------------------------------------------
PY_OK = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
PY_FAIL = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
ALLOW = ["data/consensus_evidence.yml", "records/*.md"]


def g(repo: Path, *args: str, check_rc: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check_rc and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {p.returncode}: {p.stderr}")
    return p


def write(repo: Path, rel: str, content: str) -> None:
    fp = repo / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8", newline="\n")


def origin_head(origin: Path) -> str:
    return g(origin, "rev-parse", "main").stdout.strip()


def commit_count(origin: Path) -> int:
    return int(g(origin, "rev-list", "--count", "main").stdout.strip())


def setup(tmp: Path) -> tuple[Path, Path]:
    origin = tmp / "origin.git"
    g(tmp, "init", "--bare", "-b", "main", str(origin))
    seed = tmp / "seed"
    g(tmp, "clone", str(origin), str(seed))
    g(seed, "config", "user.name", "seed")
    g(seed, "config", "user.email", "seed@x")
    write(seed, "data/consensus_evidence.yml", "schema_version: 1\nevidence: []\n")
    write(seed, "records/rec-a.md", "a base\n")
    write(seed, "records/rec-shared.md", "line1\nline2\nline3\n")
    write(seed, "records/rec-other.md", "other base\n")
    g(seed, "add", "-A")
    g(seed, "commit", "-m", "seed")
    g(seed, "push", "origin", "main")
    work = tmp / "work"
    g(tmp, "clone", str(origin), str(work))
    return origin, work


def clone(tmp: Path, origin: Path, name: str) -> Path:
    dest = tmp / name
    g(tmp, "clone", str(origin), str(dest))
    g(dest, "config", "user.name", name)
    g(dest, "config", "user.email", f"{name}@x")
    return dest


def push_change(repo: Path, rel: str, content: str, msg: str) -> None:
    g(repo, "fetch", "origin", "main")
    g(repo, "reset", "--hard", "origin/main")
    write(repo, rel, content)
    g(repo, "add", "-A")
    g(repo, "commit", "-m", msg)
    g(repo, "push", "origin", "main")


def cfg(work: Path, **kw) -> aw.WritebackConfig:
    base = dict(repo=work, message="automation writeback", allow=list(ALLOW), validate=[PY_OK],
                max_retries=5, branch="main", remote="origin", sleep_fn=lambda _s: None)
    base.update(kw)
    return aw.WritebackConfig(**base)


class Sleeper:
    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, s) -> None:
        self.calls.append(s)


def marker_cmd(marker: Path) -> str:
    """A Pages dispatch stand-in that succeeds and records each invocation."""
    return f'"{sys.executable}" -c "open(r\'{marker.as_posix()}\',\'a\').write(\'x\')"'


# A `gh run list` stand-in: the first `pre_calls` calls print `pre` (the pre-dispatch snapshot; the
# no-change recovery path first asks whether main is deployed, so it takes two), every later call
# (the confirmation polls) prints `post`. A run whose headSha is "SELF" is rewritten to the live
# origin/main SHA, so the run belongs to exactly the revision the writeback pushed.
_SEQ_STATUS = r"""
import json, os, subprocess, sys
counter, origin, pre_tpl, post_tpl, pre_calls = sys.argv[1:6]
sha = subprocess.run(["git", "-C", origin, "rev-parse", "main"], capture_output=True, text=True).stdout.strip()
n = (int(open(counter).read()) if os.path.exists(counter) else 0) + 1
open(counter, "w").write(str(n))
runs = json.loads(open(pre_tpl if n <= int(pre_calls) else post_tpl).read())
for r in runs:
    if r.get("headSha") == "SELF":
        r["headSha"] = sha
sys.stdout.write(json.dumps(runs))
"""


def seq_status(tmp: Path, origin: Path, pre: list, post: list, tag: str,
               pre_calls: int = 1) -> tuple[str, Path]:
    script = tmp / "seq_status.py"
    if not script.exists():
        script.write_text(_SEQ_STATUS, encoding="utf-8")
    pre_f = tmp / f"pre_{tag}.json"
    pre_f.write_text(json.dumps(pre), encoding="utf-8")
    post_f = tmp / f"post_{tag}.json"
    post_f.write_text(json.dumps(post), encoding="utf-8")
    counter = tmp / f"count_{tag}"
    return (f'"{sys.executable}" "{script.as_posix()}" "{counter.as_posix()}" "{origin.as_posix()}" '
            f'"{pre_f.as_posix()}" "{post_f.as_posix()}" {pre_calls}'), counter


def run(sha: str, status: str = "completed", conclusion: str | None = "success", db: int = 1) -> dict:
    return {"databaseId": db, "headSha": sha, "headBranch": "main", "status": status,
            "conclusion": conclusion}


class StepSummary:
    """Point $GITHUB_STEP_SUMMARY at a scratch file for one in-process call, then restore it, so the
    suite never appends to the summary of the CI job that is running it."""

    def __init__(self, tmp: Path, name: str) -> None:
        self.path = tmp / name
        self._old = None

    def __enter__(self) -> "StepSummary":
        self._old = os.environ.get("GITHUB_STEP_SUMMARY")
        os.environ["GITHUB_STEP_SUMMARY"] = str(self.path)
        return self

    def __exit__(self, *exc) -> None:
        if self._old is None:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        else:
            os.environ["GITHUB_STEP_SUMMARY"] = self._old

    def text(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else ""


# --------------------------------------------------------------------------------------------------
# [A] build confirmation
# --------------------------------------------------------------------------------------------------
def section_confirmation() -> None:
    print(NEWLINE + "[A] build confirmation: dispatched is not deployed")

    # A1 confirmed
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        status, _ = seq_status(tmp, origin, [], [run("SELF", db=200)], "a1")
        write(work, "records/rec-a.md", "A1\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, pages_confirm_build=True, pages_status_cmd=status,
                                 pages_confirm_attempts=4, pages_confirm_interval=30))
        check("A1 a build that succeeds is confirmed, and the run is ok",
              r.ok and r.pages_build_outcome == "confirmed" and not r.deployment_unverified
              and not r.deployment_pending, f"{r.pages_build_outcome} ok={r.ok}")

    # A2 failed
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        marker = tmp / "dispatches"
        status, _ = seq_status(tmp, origin, [], [run("SELF", conclusion="failure", db=200)], "a2")
        write(work, "records/rec-a.md", "A2 data\n")
        before = commit_count(origin)
        with StepSummary(tmp, "a2.md") as summ:
            r = aw.run_writeback(cfg(work, pages_cmd=marker_cmd(marker), pages_confirm_build=True,
                                     pages_status_cmd=status, pages_confirm_attempts=4,
                                     pages_confirm_interval=30))
        check("A2 a build that fails fails the run (ok False, deployment_pending)",
              not r.ok and r.deployment_pending and r.pages_build_outcome == "failed", r.outcome)
        check("A2 and is reported as unverified", r.deployment_unverified)
        check("A2 the data commit stays on main: pushed once, not reverted, not re-pushed",
              r.pushed and origin_head(origin) == r.pushed_sha and commit_count(origin) == before + 1
              and "A2 data" in g(origin, "show", "main:records/rec-a.md").stdout,
              f"commits {before}->{commit_count(origin)}")
        check("A2 Pages was dispatched exactly once (the poll is not a retry)",
              marker.exists() and marker.read_text() == "x",
              marker.read_text() if marker.exists() else "absent")
        check("A2 a failed build is never a lost race, so nothing re-runs the cycle", not r.lost_race)
        check("A2 the step summary names the failed build", "Deployment build failed" in summ.text())

    # A3 never appeared
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        slp = Sleeper()
        status, _ = seq_status(tmp, origin, [], [], "a3")
        write(work, "records/rec-a.md", "A3\n")
        with StepSummary(tmp, "a3.md") as summ:
            r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, pages_confirm_build=True, pages_status_cmd=status,
                                     pages_confirm_attempts=4, pages_confirm_interval=30, sleep_fn=slp))
        check("A3 a build that never appears is unverified, explicitly",
              r.pages_build_outcome == "unconfirmed" and r.deployment_unverified
              and aw.DEPLOYMENT_UNVERIFIED in r.outcomes, str(r.outcomes))
        check("A3 without failing the lane or claiming a pending dispatch",
              r.ok and r.pushed and not r.deployment_pending)
        check("A3 the wait is bounded: attempts-1 sleeps of the configured interval",
              slp.calls == [30, 30, 30], str(slp.calls))
        text = summ.text()
        check("A3 the step summary says the deployment is unverified, and why",
              "Deployment unverified" in text and "no Pages run for this revision appeared" in text
              and "90s" in text, text[:300])

    # A4 appeared but never finished
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        status, _ = seq_status(tmp, origin, [], [run("SELF", status="in_progress", conclusion=None, db=200)], "a4")
        write(work, "records/rec-a.md", "A4\n")
        with StepSummary(tmp, "a4.md") as summ:
            r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, pages_confirm_build=True, pages_status_cmd=status,
                                     pages_confirm_attempts=3, pages_confirm_interval=30))
        check("A4 a build still running at the deadline is unverified, not failed",
              r.ok and r.deployment_unverified and r.pages_build_outcome == "unconfirmed")
        check("A4 and the summary says it had not finished",
              "had not finished" in summ.text(), summ.text()[:300])

    # A5 the run list cannot be read
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        write(work, "records/rec-a.md", "A5\n")
        with StepSummary(tmp, "a5.md") as summ:
            r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, pages_confirm_build=True, pages_status_cmd=PY_FAIL,
                                     pages_confirm_attempts=2, pages_confirm_interval=30))
        check("A5 an unreadable run list is unverified, never confirmed",
              r.deployment_unverified and r.pages_build_outcome == "unconfirmed"
              and aw.PAGES_BUILD_CONFIRMED not in r.outcomes)
        check("A5 and the summary says the list could not be read",
              "could not be read" in summ.text(), summ.text()[:300])

    # A6 no-change deploy recovery, with confirmation on: still dispatches only for an undeployed
    # head, still never commits, and its own build is now confirmed too.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        pusher = clone(tmp, origin, "pusher")
        push_change(pusher, "records/rec-other.md", "site change\n", "Update automated patch evidence")
        head = origin_head(origin)
        marker = tmp / "dispatches"
        status, _ = seq_status(tmp, origin, [], [run("SELF", db=300)], "a6", pre_calls=2)
        r = aw.run_writeback(cfg(work, pages_cmd=marker_cmd(marker), pages_confirm_build=True,
                                 pages_status_cmd=status, pages_confirm_attempts=3, pages_confirm_interval=30,
                                 deploy_recovery=True, recovery_site_paths=["records/*.md"]))
        check("A6 deploy recovery still re-dispatches an undeployed head, and confirms its build",
              aw.DEPLOYMENT_MISSING in r.outcomes and marker.exists() and r.pages_build_outcome == "confirmed"
              and r.ok, str(r.outcomes))
        check("A6 and still never commits or pushes", not r.pushed and r.local_commit_sha == ""
              and origin_head(origin) == head)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        pusher = clone(tmp, origin, "pusher")
        push_change(pusher, "records/rec-other.md", "site change\n", "Update automated patch evidence")
        status, _ = seq_status(tmp, origin, [], [run("SELF", conclusion="failure", db=300)], "a6b", pre_calls=2)
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, pages_confirm_build=True, pages_status_cmd=status,
                                 pages_confirm_attempts=3, pages_confirm_interval=30,
                                 deploy_recovery=True, recovery_site_paths=["records/*.md"]))
        check("A6 a recovery build that fails fails the run", not r.ok and r.pages_build_outcome == "failed")


# --------------------------------------------------------------------------------------------------
# [B] lost-race classification
# --------------------------------------------------------------------------------------------------
_DRIFT = r"""
import subprocess, sys, uuid
other = sys.argv[1]
def g(*a): subprocess.run(["git", "-C", other, *a], check=True, capture_output=True)
g("fetch", "origin", "main"); g("reset", "--hard", "origin/main")
open(other + "/records/rec-other.md", "w").write("drift " + uuid.uuid4().hex + "\n")
g("add", "-A"); g("commit", "-m", "drift"); g("push", "origin", "main")
"""

_DRIFT_AND_STRAY = r"""
import subprocess, sys
work, other = sys.argv[1], sys.argv[2]
open(work + "/stray.txt", "w").write("not part of the candidate\n")
def g(*a): subprocess.run(["git", "-C", other, *a], check=True, capture_output=True)
g("fetch", "origin", "main"); g("reset", "--hard", "origin/main")
open(other + "/records/rec-other.md", "w").write("moved on\n")
g("add", "-A"); g("commit", "-m", "upstream"); g("push", "origin", "main")
"""


def section_lost_race() -> None:
    print(NEWLINE + "[B] lost_race: exactly the outcomes a fresh run can resolve")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        push_change(other, "records/rec-shared.md", "theirs\nline2\nline3\n", "upstream")
        write(work, "records/rec-shared.md", "mine\nline2\nline3\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK))
        check("B1 rebase_conflict after main moved is a lost race",
              r.outcome == aw.REBASE_CONFLICT and r.lost_race and not r.pushed, r.outcome)
        check("B1 and the summary dict carries it", r.as_dict().get("lost_race") is True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        push_change(other, "records/rec-other.md", "upstream\n", "upstream")
        write(work, "records/rec-a.md", "mine\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, validate=[PY_FAIL]))
        check("B2 validation failing after the rebase is a lost race",
              r.outcome == aw.VALIDATION_FAILED_AFTER_REBASE and r.lost_race, r.outcome)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        drift = tmp / "drift.py"
        drift.write_text(_DRIFT, encoding="utf-8")
        write(work, "records/rec-a.md", "mine\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, max_retries=2,
                                 test_hook_before_push=f'"{sys.executable}" "{drift.as_posix()}" "{other.as_posix()}"',
                                 test_hook_fires=99))
        check("B3 main moving until the retries run out is a lost race",
              r.outcome == aw.RETRY_EXHAUSTED and r.lost_race, r.outcome)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        push_change(other, "records/rec-other.md", "upstream\n", "upstream")
        write(work, "records/rec-a.md", "mine\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK))
        check("B4 a clean rebase that then pushes is not a lost race",
              r.outcome == aw.PUSH_SUCCESS_AFTER_RETRY and not r.lost_race, r.outcome)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        write(work, "secret.txt", "x\n")
        g(work, "add", "secret.txt")
        write(work, "records/rec-a.md", "mine\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK))
        check("B5 a refused path before any push is not a lost race",
              r.outcome == aw.UNEXPECTED_CHANGED_PATH and not r.lost_race, r.outcome)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        push_change(other, "records/rec-other.md", "upstream\n", "upstream")
        write(work, "records/rec-a.md", "mine\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_FAIL, pages_max_attempts=2))
        check("B6 a run that pushed after main moved but could not dispatch Pages is not a lost race",
              r.pushed and r.deployment_pending and not r.ok and not r.lost_race, r.outcome)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        hook = origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho refused >&2\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        write(work, "records/rec-a.md", "mine\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, max_retries=1))
        check("B7 pushes refused while main did NOT move are not a lost race",
              r.outcome == aw.RETRY_EXHAUSTED and aw.UPSTREAM_ADVANCED not in r.outcomes
              and not r.lost_race, f"{r.outcome} {r.outcomes}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        hook_py = tmp / "drift_stray.py"
        hook_py.write_text(_DRIFT_AND_STRAY, encoding="utf-8")
        write(work, "records/rec-a.md", "mine\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, test_hook_fires=1,
                                 test_hook_before_push=(f'"{sys.executable}" "{hook_py.as_posix()}" '
                                                        f'"{work.as_posix()}" "{other.as_posix()}"')))
        check("B8 a residual-file refusal after main moved is a defect, not a lost race",
              r.outcome == aw.UNSTAGED_CHANGED_PATH and aw.UPSTREAM_ADVANCED in r.outcomes
              and not r.lost_race, f"{r.outcome} {r.outcomes}")

    check("B9 the recoverable set is exactly the three race outcomes",
          aw.RECOVERABLE_LOST_RACE_OUTCOMES == {aw.REBASE_CONFLICT, aw.VALIDATION_FAILED_AFTER_REBASE,
                                                aw.RETRY_EXHAUSTED},
          str(sorted(aw.RECOVERABLE_LOST_RACE_OUTCOMES)))


# --------------------------------------------------------------------------------------------------
# [C] the bare script, the way every workflow runs it
# --------------------------------------------------------------------------------------------------
def run_script(tmp: Path, work: Path, extra: list[str], tag: str) -> tuple[int, dict, str, str]:
    """automation_writeback.py executed as a BARE SCRIPT, with $GITHUB_OUTPUT and
    $GITHUB_STEP_SUMMARY pointed at scratch files (never the CI job's own)."""
    out_f = tmp / f"out_{tag}"
    sum_f = tmp / f"sum_{tag}.md"
    cmd = [sys.executable, str(SCRIPT), "--repo", str(work), "--message", "Update automated patch evidence"]
    for a in ALLOW:
        cmd += ["--allow", a]
    cmd += ["--validate", PY_OK] + extra
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
               GITHUB_OUTPUT=str(out_f), GITHUB_STEP_SUMMARY=str(sum_f))
    env.pop("GITHUB_ENV", None)
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    outputs = {}
    if out_f.exists():
        for ln in out_f.read_text(encoding="utf-8").splitlines():
            if "=" in ln:
                k, v = ln.split("=", 1)
                outputs[k] = v
    summary = sum_f.read_text(encoding="utf-8") if sum_f.exists() else ""
    return p.returncode, outputs, p.stdout, summary


def section_bare_script() -> None:
    print(NEWLINE + "[C] the bare script writes the outputs the workflows read")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        push_change(other, "records/rec-shared.md", "theirs\nline2\nline3\n", "upstream")
        write(work, "records/rec-shared.md", "mine\nline2\nline3\n")
        rc, out, stdout, _ = run_script(tmp, work, ["--pages-cmd", PY_OK], "c1")
        check("C1 a lost race exits 1 and writes lost_race=true, pushed=false",
              rc == 1 and out.get("lost_race") == "true" and out.get("pushed") == "false"
              and out.get("outcome") == aw.REBASE_CONFLICT, f"rc={rc} {out}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        status, _ = seq_status(tmp, origin, [], [], "c2")
        write(work, "records/rec-a.md", "C2\n")
        rc, out, stdout, summary = run_script(tmp, work, [
            "--pages-cmd", PY_OK, "--pages-confirm-build", "--pages-confirm-attempts", "2",
            "--pages-confirm-interval", "0", "--pages-status-cmd", status], "c2")
        check("C2 an unverified deployment exits 0", rc == 0, f"rc={rc}")
        check("C2 and writes deployment_unverified=true", out.get("deployment_unverified") == "true", str(out))
        check("C2 and writes pages_build=unconfirmed", out.get("pages_build") == "unconfirmed", str(out))
        check("C2 and annotates the run", "::warning title=Deployment unverified::" in stdout, stdout[-400:])
        check("C2 and summarises it", "Deployment unverified" in summary, summary[:200])
        check("C2 and is not a lost race", out.get("lost_race") == "false", str(out))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        status, _ = seq_status(tmp, origin, [], [run("SELF", conclusion="failure", db=9)], "c3")
        write(work, "records/rec-a.md", "C3\n")
        rc, out, stdout, summary = run_script(tmp, work, [
            "--pages-cmd", PY_OK, "--pages-confirm-build", "--pages-confirm-attempts", "2",
            "--pages-confirm-interval", "0", "--pages-status-cmd", status], "c3")
        check("C3 a failed build exits 1 with deployment_pending and pages_build=failed",
              rc == 1 and out.get("deployment_pending") == "true" and out.get("pages_build") == "failed"
              and out.get("deployment_unverified") == "true", f"rc={rc} {out}")
        check("C3 and annotates the failure", "::error title=Pages build failed::" in stdout, stdout[-400:])
        check("C3 but is pushed and NOT a lost race, so no recovery re-runs it",
              out.get("pushed") == "true" and out.get("lost_race") == "false", str(out))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        status, _ = seq_status(tmp, origin, [], [run("SELF", db=9)], "c4")
        write(work, "records/rec-a.md", "C4\n")
        rc, out, stdout, _ = run_script(tmp, work, [
            "--pages-cmd", PY_OK, "--pages-confirm-build", "--pages-confirm-attempts", "2",
            "--pages-confirm-interval", "0", "--pages-status-cmd", status], "c4")
        check("C4 a confirmed build exits 0 with pages_build=confirmed, deployment_unverified=false",
              rc == 0 and out.get("pages_build") == "confirmed" and out.get("deployment_unverified") == "false",
              f"rc={rc} {out}")


# --------------------------------------------------------------------------------------------------
# [D] workflow wiring, parsed
# --------------------------------------------------------------------------------------------------
def load_wf(name: str) -> dict:
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8")) or {}
    if True in doc and "on" not in doc:
        doc["on"] = doc.pop(True)
    return doc


def strip_shell_comments(text: str) -> str:
    """Drop `#` comments, respecting quotes, so prose describing a flag can never satisfy a check."""
    out: list[str] = []
    for line in text.splitlines():
        buf: list[str] = []
        quote: str | None = None
        i = 0
        while i < len(line):
            ch = line[i]
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = None
                elif ch == "\\" and quote == '"' and i + 1 < len(line):
                    buf.append(line[i + 1])
                    i += 1
            elif ch in "'\"":
                quote = ch
                buf.append(ch)
            elif ch == "#" and (not buf or buf[-1].isspace()):
                break
            else:
                buf.append(ch)
            i += 1
        kept = "".join(buf).rstrip()
        if kept.strip():
            out.append(kept)
    return NEWLINE.join(out)


def writeback_invocations(doc: dict) -> list[tuple[str, dict, dict, list[str]]]:
    """(job name, job, step, argv) for every step whose executed shell runs automation_writeback.py.
    argv is the real argument list: comments stripped, continuations joined, shlex-split."""
    found = []
    for jname, job in (doc.get("jobs") or {}).items():
        for step in (job.get("steps") or []):
            body = step.get("run") if isinstance(step, dict) else None
            if not isinstance(body, str):
                continue
            joined = re.sub(r"\\\n\s*", " ", strip_shell_comments(body))
            for line in joined.splitlines():
                if "automation_writeback.py" not in line:
                    continue
                tokens = shlex.split(line)
                at = next(i for i, t in enumerate(tokens) if t.endswith("automation_writeback.py"))
                found.append((jname, job, step, tokens[at + 1:]))
    return found


def eval_ref(template: str, ctx: dict) -> str:
    """Resolve a `${{ dotted.path }}` value against ctx. Anything else raises, so an edit to these
    expressions fails loudly instead of being mis-evaluated."""
    m = re.fullmatch(r"\$\{\{\s*([A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)*)\s*\}\}", str(template).strip())
    if not m:
        raise ValueError(f"unsupported expression: {template!r}")
    cur = ctx
    for part in m.group(1).split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return "" if cur is None else str(cur)


class Expr:
    """A minimal evaluator for the `if:` grammar chain-ingest uses: always(), dotted context lookups,
    string literals, == / !=, &&, ||, !, parentheses. Unknown syntax raises. Equality follows GitHub's
    loose rule for the one case that matters here: a missing value equals ''."""

    TOKEN = re.compile(r"\s*(\$\{\{|\}\}|&&|\|\||==|!=|!|\(|\)|'[^']*'|[A-Za-z_][\w.-]*)")

    def __init__(self, text: str, ctx: dict) -> None:
        self.toks: list[str] = []
        pos = 0
        text = text.strip()
        while pos < len(text):
            m = self.TOKEN.match(text, pos)
            if not m:
                raise ValueError(f"cannot parse at {text[pos:pos + 20]!r}")
            self.toks.append(m.group(1))
            pos = m.end()
            while pos < len(text) and text[pos].isspace():
                pos += 1
        self.toks = [t for t in self.toks if t not in ("${{", "}}")]
        self.i = 0
        self.ctx = ctx

    def peek(self) -> str | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self) -> str:
        t = self.toks[self.i]
        self.i += 1
        return t

    def value(self):
        v = self.parse_or()
        if self.peek() is not None:
            raise ValueError(f"trailing tokens: {self.toks[self.i:]}")
        return v

    def parse_or(self):
        v = self.parse_and()
        while self.peek() == "||":
            self.take()
            rhs = self.parse_and()
            v = v or rhs
        return v

    def parse_and(self):
        v = self.parse_unary()
        while self.peek() == "&&":
            self.take()
            rhs = self.parse_unary()
            v = v and rhs
        return v

    def parse_unary(self):
        if self.peek() == "!":
            self.take()
            return not self.parse_unary()
        return self.parse_cmp()

    def parse_cmp(self):
        lhs = self.parse_atom()
        if self.peek() in ("==", "!="):
            op = self.take()
            rhs = self.parse_atom()
            a = "" if lhs is None else lhs
            b = "" if rhs is None else rhs
            return (a == b) if op == "==" else (a != b)
        return lhs

    def parse_atom(self):
        t = self.take()
        if t == "(":
            v = self.parse_or()
            if self.take() != ")":
                raise ValueError("unbalanced parenthesis")
            return v
        if t.startswith("'"):
            return t[1:-1]
        if t == "always" and self.peek() == "(":
            self.take()
            self.take()
            return True
        if re.fullmatch(r"[A-Za-z_][\w-]*(\.[A-Za-z_][\w-]*)*", t):
            cur = self.ctx
            for part in t.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
            return cur
        raise ValueError(f"unsupported token {t!r}")


def recovery_step_index(steps: list) -> int:
    """The patch-ingest recovery step, located STRUCTURALLY -- the step that reads the writeback's
    lost_race output through its env -- so a mutant that edits its shell cannot also hide it."""
    for i, s in enumerate(steps):
        env = (s.get("env") or {}) if isinstance(s, dict) else {}
        if "steps.commit.outputs.lost_race" in str(env.get("LOST_RACE", "")):
            return i
    return -1


def writer_group_members() -> set[str]:
    out = set()
    for path in WORKFLOWS.glob("*.yml"):
        c = load_wf(path.name).get("concurrency")
        group = c.get("group") if isinstance(c, dict) else c
        if group == WRITER_GROUP:
            out.add(path.name)
    return out


def section_wiring() -> None:
    print(NEWLINE + "[D] workflow wiring, parsed with the writeback's own argument parser")
    parser = aw.build_parser()
    lanes: dict[str, list] = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = load_wf(path.name)
        for jname, job, step, argv in writeback_invocations(doc):
            lanes.setdefault(path.name, []).append((jname, job, step, parser.parse_args(argv)))
    expected = {EVIDENCE_WF, INGEST_WF, "davinci-updates.yml", "promote-davinci-verified-reports.yml"}
    check("D0 every CLI writer lane is found (closed world)", set(lanes) == expected, str(sorted(lanes)))
    for name in sorted(expected):
        for jname, job, step, args in lanes.get(name, []) or [(None, {}, {}, None)]:
            if args is None:
                check(f"D1 {name} confirms its Pages build", False, "no writeback invocation")
                continue
            check(f"D1 {name} confirms its Pages build", bool(args.pages_cmd) and args.pages_confirm_build,
                  f"pages_cmd={args.pages_cmd!r} confirm={args.pages_confirm_build}")
            bound = max(args.pages_confirm_attempts - 1, 0) * args.pages_confirm_interval
            # Measured Pages runs take 237-612 s from creation; one may queue behind another build in
            # the `pages` concurrency group. 900 s covers that; 1500 s keeps the writer lane short.
            check(f"D2 {name} waits long enough for a queued build, and no longer than the lane can afford",
                  900 <= bound <= 1500 and args.pages_confirm_interval >= 15,
                  f"bound={bound}s interval={args.pages_confirm_interval}")
            check(f"D3 {name} keeps --deploy-recovery", args.deploy_recovery)
            job_timeout = float(job.get("timeout-minutes") or 360)
            capped = sum(float(s.get("timeout-minutes") or 0) for s in job.get("steps") or []
                         if isinstance(s, dict) and s is not step)
            headroom = job_timeout - capped - bound / 60.0
            check(f"D4 {name}/{jname} keeps at least 30 minutes of its job budget after the capped steps "
                  f"and the confirm wait", headroom >= 30, f"headroom={headroom:.1f} min")

    ev = load_wf(EVIDENCE_WF)
    collect = ev["jobs"]["collect"]
    wb_steps = [s for s in collect["steps"] if isinstance(s, dict)
                and "automation_writeback.py" in strip_shell_comments(str(s.get("run") or ""))]
    check("D5 the collect job's writeback step carries id `writeback`",
          len(wb_steps) == 1 and wb_steps[0].get("id") == "writeback", str([s.get("id") for s in wb_steps]))
    outputs = collect.get("outputs") or {}
    try:
        lost = eval_ref(outputs.get("writeback_lost_race", ""),
                        {"steps": {"writeback": {"outputs": {"lost_race": "SENTINEL"}}}})
    except ValueError as exc:
        lost = f"error: {exc}"
    check("D5 the collect job exports the writeback's lost_race output", lost == "SENTINEL", lost)

    chain = ev["jobs"]["chain-ingest"]
    step = (chain.get("steps") or [{}])[0]
    env = step.get("env") or {}
    ctx = {"needs": {"collect": {"outputs": {"writeback_lost_race": "NEEDS"}}},
           "github": {"event": {"inputs": {"recovery_of": "INPUT"}}, "run_id": "RUNID"}}
    try:
        resolved = {k: eval_ref(env.get(k, ""), ctx) for k in ("LOST_RACE", "RECOVERY_OF", "RUN_ID")}
    except ValueError as exc:
        resolved = {"error": str(exc)}
    check("D6 chain-ingest reads the collect job's lost_race, its own recovery_of input and run id",
          resolved == {"LOST_RACE": "NEEDS", "RECOVERY_OF": "INPUT", "RUN_ID": "RUNID"}, str(resolved))
    check("D6 and interpolates no expression into its shell", "${{" not in str(step.get("run")))
    check("D6 chain-ingest still needs the collect job", "collect" in (chain.get("needs") or []))

    for name in (EVIDENCE_WF, INGEST_WF):
        inputs = ((load_wf(name)["on"].get("workflow_dispatch") or {}).get("inputs") or {})
        spec = inputs.get("recovery_of") or {}
        check(f"D7 {name} declares an optional string input recovery_of",
              spec.get("type") == "string" and spec.get("required") is False and "default" not in spec, str(spec))

    chain_if = str(chain.get("if") or "")

    def gate(event: str, inputs: dict | None) -> bool:
        return bool(Expr(chain_if, {"github": {"event_name": event, "event": {"inputs": inputs}}}).value())

    routine = {"product_id": "", "update_version": "", "since": "", "dry_run": "false", "recovery_of": ""}
    recovery = dict(routine, recovery_of="44878227542")
    try:
        cases = {
            "schedule": gate("schedule", None) is True,
            "no-input dispatch (reaper)": gate("workflow_dispatch", routine) is True,
            "recovery dispatch": gate("workflow_dispatch", recovery) is True,
            "targeted dispatch": gate("workflow_dispatch", dict(routine, product_id="obs-studio")) is False,
            "dry run": gate("workflow_dispatch", dict(routine, dry_run="true")) is False,
        }
    except ValueError as exc:
        cases = {f"unparseable: {exc}": False}
    check("D8 a recovery run is still a routine cycle, so its own chain-ingest dispatches ingestion",
          all(cases.values()), str(cases))

    ing = load_wf(INGEST_WF)
    isteps = ing["jobs"]["ingest"]["steps"]
    names = [s.get("name") for s in isteps]
    commit_idx = next((i for i, s in enumerate(isteps) if s.get("id") == "commit"), -1)
    rec_idx = recovery_step_index(isteps)
    check("D9 patch-ingest has a recovery step after its writeback step",
          0 <= commit_idx < rec_idx, f"commit={commit_idx} recovery={rec_idx} names={names}")
    rec = isteps[rec_idx] if rec_idx >= 0 else {}
    rec_if = str(rec.get("if") or "")
    check("D9 it runs after a failed writeback (a status function other than success())",
          ("!cancelled()" in rec_if or "always()" in rec_if) and "success()" not in rec_if, rec_if)
    renv = rec.get("env") or {}
    rctx = {"steps": {"commit": {"outputs": {"lost_race": "STEP"}}},
            "github": {"event": {"inputs": {"recovery_of": "INPUT", "source": "SRC"}}, "run_id": "RUNID",
                       "repository": "REPO"}}
    try:
        rres = {k: eval_ref(renv.get(k, ""), rctx) for k in ("LOST_RACE", "RECOVERY_OF", "SOURCE", "RUN_ID")}
    except ValueError as exc:
        rres = {"error": str(exc)}
    check("D9 it reads the writeback's lost_race, recovery_of, source and run id",
          rres == {"LOST_RACE": "STEP", "RECOVERY_OF": "INPUT", "SOURCE": "SRC", "RUN_ID": "RUNID"}, str(rres))
    check("D9 and interpolates no expression into its shell", "${{" not in str(rec.get("run")))
    members = writer_group_members()
    check("D10 its GROUP_MEMBERS equals the parsed membership of the writer group",
          set(str(renv.get("GROUP_MEMBERS", "")).split()) == members and members,
          f"declared={sorted(str(renv.get('GROUP_MEMBERS', '')).split())} parsed={sorted(members)}")


# --------------------------------------------------------------------------------------------------
# [E] the recovery shell, executed
# --------------------------------------------------------------------------------------------------
# Answers the pending-slot query with SIM_PENDING_N only when the query asks about `pending` AND
# names SIM_PENDING_WF, so a guard that forgets the pending state, or checks only its own workflow,
# sees a free lane and dispatches -- and fails the scenario.
FAKE_GH = r"""#!/usr/bin/env bash
echo "GH $*" >> "$SIM_LOG"
if [ "$1" = "workflow" ]; then
  echo "DISPATCH $*" >> "$SIM_LOG"
  exit "${SIM_DISPATCH_RC:-0}"
fi
if [ "$1" = "api" ]; then
  if [ "${SIM_API_RC:-0}" != "0" ]; then exit "${SIM_API_RC}"; fi
  case "$*" in
    *'.status == "pending"'*)
      case "$2" in
        *"/workflows/${SIM_PENDING_WF:-none}/"*) echo "${SIM_PENDING_N:-0}" ;;
        *) echo 0 ;;
      esac ;;
    *) echo 0 ;;
  esac
  exit 0
fi
exit 0
"""


def run_shell(script: str, env_decl: dict, sim_env: dict) -> tuple[int, list[list[str]], list[str], str]:
    """Run a step's `run:` scalar the way GitHub runs a step with no `shell:` (bash -e), with a fake
    gh first on PATH. Returns (exit code, dispatches as token lists, api queries, stdout)."""
    tmp = tempfile.mkdtemp()
    try:
        gh = Path(tmp, "gh")
        gh.write_text(FAKE_GH, newline="\n")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        sh = Path(tmp, "step.sh")
        sh.write_text(script, newline="\n")
        log = Path(tmp, "gh.log")
        log.write_text("", newline="\n")
        env = dict(os.environ)
        env.pop("GITHUB_OUTPUT", None)
        env.update({
            "PATH": tmp + os.pathsep + env.get("PATH", ""),
            "GITHUB_STEP_SUMMARY": str(Path(tmp, "summary.md")),
            "SIM_LOG": str(log),
            "REPO": "owner/repo",
            "GH_TOKEN": "fake",
        })
        if "GROUP_MEMBERS" in env_decl:
            env["GROUP_MEMBERS"] = " ".join(str(env_decl["GROUP_MEMBERS"]).split())
        env.update(sim_env)
        proc = subprocess.run([shutil.which("bash") or "bash", "--noprofile", "--norc", "-e", str(sh)],
                              capture_output=True, text=True, env=env)
        lines = log.read_text().splitlines()
        dispatches = [shlex.split(ln)[1:] for ln in lines if ln.startswith("DISPATCH ")]
        queries = [ln for ln in lines if ln.startswith("GH api ")]
        return proc.returncode, dispatches, queries, proc.stdout + proc.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def dispatch_summary(d: list[str]) -> tuple[str, dict]:
    """('workflow file', {input: value}) from a `workflow run <wf> ... -f k=v` token list."""
    wf = d[2] if len(d) > 2 else ""
    fields = {}
    for i, t in enumerate(d):
        if t in ("-f", "--field", "-F", "--raw-field") and i + 1 < len(d) and "=" in d[i + 1]:
            k, v = d[i + 1].split("=", 1)
            fields[k] = v
    return wf, fields


def declared_inputs(name: str) -> set[str]:
    return set(((load_wf(name)["on"].get("workflow_dispatch") or {}).get("inputs") or {}).keys())


def section_executed() -> None:
    print(NEWLINE + "[E] the recovery shell, executed under bash against a fake gh")
    if shutil.which("bash") is None:
        check("E bash is available to execute the workflow shell", False, "bash not found")
        return

    chain = load_wf(EVIDENCE_WF)["jobs"]["chain-ingest"]["steps"][0]
    cscript, cenv = chain["run"], chain.get("env") or {}
    base = {"RUN_ID": "777", "LOST_RACE": "", "RECOVERY_OF": ""}

    rc, ds, _, out = run_shell(cscript, cenv, dict(base, LOST_RACE="true"))
    summ = [dispatch_summary(d) for d in ds]
    check("E1 a lost race re-dispatches THIS workflow once, carrying recovery_of, and nothing else",
          rc == 0 and summ == [(EVIDENCE_WF, {"recovery_of": "777"})], f"rc={rc} {summ} {out[-300:]}")
    check("E1 every input it passes is declared by the workflow it dispatches",
          all(set(f) <= declared_inputs(wf) for wf, f in summ if wf), str(summ))
    rc, ds, _, out = run_shell(cscript, cenv, dict(base, LOST_RACE="true", RECOVERY_OF="555"))
    summ = [dispatch_summary(d) for d in ds]
    check("E2 a recovery run that loses again is NOT re-dispatched; ingestion still follows",
          rc == 0 and summ == [(INGEST_WF, {})] and "::warning" in out, f"rc={rc} {summ}")
    rc, ds, _, out = run_shell(cscript, cenv, dict(base, LOST_RACE="false"))
    summ = [dispatch_summary(d) for d in ds]
    check("E3 no lost race: routine ingestion only", rc == 0 and summ == [(INGEST_WF, {})], f"rc={rc} {summ}")
    rc, ds, _, out = run_shell(cscript, cenv, dict(base))
    summ = [dispatch_summary(d) for d in ds]
    check("E4 no writeback output at all (collect failed earlier): routine ingestion only",
          rc == 0 and summ == [(INGEST_WF, {})], f"rc={rc} {summ}")
    check("E4 the ingestion dispatch passes only inputs patch-ingest declares",
          all(set(f) <= declared_inputs(wf) for wf, f in summ if wf), str(summ))

    ing = load_wf(INGEST_WF)["jobs"]["ingest"]["steps"]
    idx = recovery_step_index(ing)
    rec = ing[idx] if idx >= 0 else None
    if rec is None:
        check("E patch-ingest has a recovery step to execute", False)
        return
    rscript, renv = rec["run"], rec.get("env") or {}
    rbase = {"RUN_ID": "888", "LOST_RACE": "true", "RECOVERY_OF": "", "SOURCE": ""}

    rc, ds, qs, out = run_shell(rscript, renv, rbase)
    summ = [dispatch_summary(d) for d in ds]
    check("E5 a lost race with a free lane re-dispatches patch-ingest once, carrying recovery_of",
          rc == 0 and summ == [(INGEST_WF, {"recovery_of": "888"})], f"rc={rc} {summ} {out[-300:]}")
    check("E5 every input it passes is declared by patch-ingest",
          all(set(f) <= declared_inputs(wf) for wf, f in summ if wf), str(summ))
    check("E5 the free-lane check reads every member of the writer group",
          {m for m in writer_group_members() if any(f"/workflows/{m}/" in q for q in qs)} == writer_group_members(),
          f"{len(qs)} queries")
    rc, ds, _, out = run_shell(rscript, renv, dict(rbase, SIM_PENDING_WF="davinci-updates.yml",
                                                   SIM_PENDING_N="1"))
    check("E6 a writer run waiting in the pending slot (any lane) blocks the re-dispatch",
          rc == 0 and ds == [] and "::warning" in out, f"rc={rc} {ds}")
    rc, ds, _, out = run_shell(rscript, renv, dict(rbase, RECOVERY_OF="666"))
    check("E7 a recovery run that loses again is not re-dispatched (loop guard)",
          rc == 0 and ds == [] and "::warning" in out, f"rc={rc} {ds}")
    rc, ds, _, out = run_shell(rscript, renv, dict(rbase, SOURCE="obs-studio"))
    check("E8 a dispatch scoped to one source is not re-run automatically",
          rc == 0 and ds == [], f"rc={rc} {ds}")
    rc, ds, qs, out = run_shell(rscript, renv, dict(rbase, LOST_RACE="false"))
    check("E9 no lost race: nothing dispatched and the API is not even read",
          rc == 0 and ds == [] and qs == [], f"rc={rc} {ds} {qs}")
    rc, ds, qs, out = run_shell(rscript, renv, dict(rbase, LOST_RACE=""))
    check("E9 a skipped writeback (dry run, earlier failure): nothing dispatched", rc == 0 and ds == [],
          f"rc={rc} {ds}")
    rc, ds, _, out = run_shell(rscript, renv, dict(rbase, SIM_API_RC="1"))
    check("E10 an unreadable run list fails SAFE: treated as occupied, nothing dispatched",
          rc == 0 and ds == [] and "::warning" in out, f"rc={rc} {ds}")
    rc, ds, _, out = run_shell(rscript, renv, dict(rbase, SIM_DISPATCH_RC="1"))
    check("E11 a re-dispatch that fails is not silent: the step fails", rc != 0 and "::error" in out,
          f"rc={rc}")


def main() -> int:
    print("=" * 74)
    print("G91 deployment verification and lost-race recovery")
    print("=" * 74)
    section_confirmation()
    section_lost_race()
    section_bare_script()
    section_wiring()
    section_executed()
    print(NEWLINE + "=" * 74)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 74)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
