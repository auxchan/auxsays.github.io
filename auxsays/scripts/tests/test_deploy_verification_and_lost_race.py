#!/usr/bin/env python3
"""G91: a deployment is verified after material writeback, and a cycle that did not reach main is
re-run once -- with what stays broken made visible.

THE GAPS, ALL IN THE STEP AFTER THE EVIDENCE IS ALREADY CORRECT
----------------------------------------------------------------
A. Every writer lane dispatched Pages after a material push and stopped there. `gh workflow run`
   returning 0 proves only that the DISPATCH was accepted; no lane looked at the build. The writeback
   already had an opt-in poll (`--pages-confirm-build`); no workflow passed it, and the PowerPoint
   graph's Python binding could not. A run cancelled because a newer build superseded it in the
   one-deep `pages` concurrency group is NOT a failed build: the newer build deploys the content.
B. Run 44878227542 lost its whole collection cycle: a PR touching the evidence store merged while it
   ran, the writeback correctly refused to merge the two (`rebase_conflict`), pushed nothing and
   exited 1 -- and nothing re-ran it. The writer-queue reaper repaired runs EVICTED from the queue
   (zero jobs), not runs that ran and lost their cycle, and a recovery that was itself evicted came
   back with no record that it was a recovery. Nothing durable said when a cycle stayed lost.

WHAT IS PINNED, AND HOW
-----------------------
[A] the writeback's build confirmation, against a throwaway bare origin and a scripted run list:
    confirmed / failed / never appeared / never finished / unreadable / superseded (cancelled, then
    a same-SHA or descendant run) / a descendant that fails / an ancestor that must not count /
    a pre-dispatch snapshot that could not be read / a status query that hangs. No outcome
    re-pushes or reverts the data commit.
[B] the `lost_race` diagnostic (a hook's refusal after a clean rebase is not a race), and that a
    run whose checkout went stale never pushes a stale tree.
[C] the same contract through the BARE SCRIPT, the way every workflow runs it.
[D] the workflow wiring, parsed: each writer's real argument list is fed to the writeback's own
    argparse parser; the confirm bound fits each job's budget; the `Cycle reached main` steps and
    the run names are EVALUATED per context and cross-checked against the reaper module that reads
    them; the reaper's new step reads the eviction step's outputs and has the permissions it needs;
    every writer job of a re-run checks out main as it is when the job starts.
[E] shell EXECUTED under bash against a fake `gh`: chain-ingest dispatches ingestion only, on main;
    the reaper's eviction step re-dispatches on main, passes `recovery_of` on and reports whether
    the lane was free.
[F] writer_cycle_recovery's decisions over scripted run histories: reached / lost / loop guard /
    pause after a lost recovery / time limit vs operator cancel / one entrant per tick / Pages /
    a GREEN run whose cycle record was skipped (the PowerPoint graph's writeback lost its race).
[G] the same module as a BARE SCRIPT against a fake `gh` serving raw API JSON: the dispatch it
    issues, the writer states that hold it back, and the ONE tracking issue it opens, updates,
    closes or leaves alone.
[H] the PowerPoint graph's writeback binding confirms its build and writes its outputs.

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
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

from lib import automation_writeback as aw  # noqa: E402
import writer_cycle_recovery as wcr  # noqa: E402

WORKFLOWS = _REPO / ".github" / "workflows"
SCRIPT = _REPO / "auxsays" / "scripts" / "lib" / "automation_writeback.py"
RECOVERY_SCRIPT = _REPO / "auxsays" / "scripts" / "writer_cycle_recovery.py"
EVIDENCE_WF = "obs-evidence-collection.yml"
INGEST_WF = "patch-ingest.yml"
REAPER_WF = "writer-queue-reaper.yml"
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



# A scripted `gh run list`: call n prints responses[n-1] (the last one repeats) and "FAIL" exits 1.
# Placeholders: "SELF" -> origin/main at the time of the call; "PUSHED" -> the revision recorded by
# the advancing dispatch stand-in below before it moved main on (origin/main when none recorded);
# "ROOT" -> the first commit, an ANCESTOR of everything the writeback pushes.
_SCRIPTED_STATUS = r"""
import json, os, subprocess, sys
counter, origin, responses_f, pushed_f = sys.argv[1:5]
def rev(*a):
    return subprocess.run(["git", "-C", origin, *a], capture_output=True, text=True).stdout.strip()
main = rev("rev-parse", "main")
pushed = open(pushed_f).read().strip() if os.path.exists(pushed_f) else main
root = rev("rev-list", "--max-parents=0", "main").splitlines()[0]
n = (int(open(counter).read()) if os.path.exists(counter) else 0) + 1
open(counter, "w").write(str(n))
responses = json.load(open(responses_f))
resp = responses[min(n, len(responses)) - 1]
if resp == "FAIL":
    sys.exit(1)
names = {"SELF": main, "PUSHED": pushed, "ROOT": root}
for r in resp:
    r["headSha"] = names.get(r.get("headSha"), r.get("headSha"))
sys.stdout.write(json.dumps(resp))
"""


def scripted_status(tmp: Path, origin: Path, responses: list, tag: str) -> str:
    """responses[0] answers the pre-dispatch snapshot; responses[1:] answer the polls."""
    script = tmp / "scripted_status.py"
    if not script.exists():
        script.write_text(_SCRIPTED_STATUS, encoding="utf-8")
    resp_f = tmp / f"responses_{tag}.json"
    resp_f.write_text(json.dumps(responses), encoding="utf-8")
    return (f'"{sys.executable}" "{script.as_posix()}" "{(tmp / f"count_{tag}").as_posix()}" '
            f'"{origin.as_posix()}" "{resp_f.as_posix()}" "{(tmp / "pushed_sha").as_posix()}"')


# A Pages dispatch stand-in that succeeds AND lets another push land right after ours: it records the
# revision this run pushed, then pushes a later commit from another clone. The writeback's clone has
# never seen that later commit, so recognising its build as a descendant's needs a fetch.
_ADVANCE_DISPATCH = r"""
import subprocess, sys, uuid
origin, other, pushed_f = sys.argv[1:4]
sha = subprocess.run(["git", "-C", origin, "rev-parse", "main"], capture_output=True, text=True).stdout.strip()
open(pushed_f, "w").write(sha)
def g(*a): subprocess.run(["git", "-C", other, *a], check=True, capture_output=True)
g("fetch", "origin", "main"); g("reset", "--hard", "origin/main")
open(other + "/records/rec-other.md", "w").write("later " + uuid.uuid4().hex + "\n")
g("add", "-A"); g("commit", "-m", "a later push"); g("push", "origin", "main")
"""


# A `gh run list` stand-in that answers only after argv[2] seconds -- with a successful build of
# origin/main, so a caller that waited for it would confirm.
_SLOW_STATUS = r"""
import json, subprocess, sys, time
origin, delay = sys.argv[1], float(sys.argv[2])
time.sleep(delay)
sha = subprocess.run(["git", "-C", origin, "rev-parse", "main"], capture_output=True, text=True).stdout.strip()
sys.stdout.write(json.dumps([{"databaseId": 900, "headSha": sha, "headBranch": "main",
                              "status": "completed", "conclusion": "success"}]))
"""


def advance_dispatch(tmp: Path, origin: Path, other: Path) -> str:
    script = tmp / "advance_dispatch.py"
    script.write_text(_ADVANCE_DISPATCH, encoding="utf-8")
    return (f'"{sys.executable}" "{script.as_posix()}" "{origin.as_posix()}" "{other.as_posix()}" '
            f'"{(tmp / "pushed_sha").as_posix()}"')


def confirm_case(responses: list, tag: str, advance: bool = False, attempts: int = 4):
    """One material push with build confirmation on. Returns (result, summary text, origin head,
    the revision the run pushed as the dispatch saw it)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        pages_cmd = PY_OK
        if advance:
            pages_cmd = advance_dispatch(tmp, origin, clone(tmp, origin, "later"))
        status = scripted_status(tmp, origin, responses, tag)
        write(work, "records/rec-a.md", f"{tag}\n")
        with StepSummary(tmp, f"{tag}.md") as summ:
            r = aw.run_writeback(cfg(work, pages_cmd=pages_cmd, pages_confirm_build=True,
                                     pages_status_cmd=status, pages_confirm_attempts=attempts,
                                     pages_confirm_interval=30))
        pushed_f = tmp / "pushed_sha"
        recorded = pushed_f.read_text().strip() if pushed_f.exists() else ""
        return r, summ.text(), origin_head(origin), recorded

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

    # A15 a status query that hangs: each query is cut at pages_status_timeout and reads as
    # unreadable, so a hung `gh` can never stretch the bounded wait into the job's time limit. The
    # stand-in WOULD answer (a successful build of this very revision) if it were waited for.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        slow = tmp / "slow_status.py"
        slow.write_text(_SLOW_STATUS, encoding="utf-8")
        status = f'"{sys.executable}" "{slow.as_posix()}" "{origin.as_posix()}" 4'
        write(work, "records/rec-a.md", "A15\n")
        with StepSummary(tmp, "a15.md") as summ:
            r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, pages_confirm_build=True, pages_status_cmd=status,
                                     pages_status_timeout=1, pages_confirm_attempts=2, pages_confirm_interval=30))
        check("A15 a status query that does not answer within its timeout reads as unreadable: unverified, green",
              r.ok and r.pushed and r.deployment_unverified and r.pages_build_outcome == "unconfirmed"
              and aw.PAGES_BUILD_CONFIRMED not in r.outcomes and "could not be read" in summ.text(),
              f"{r.outcomes} {summ.text()[:200]}")



def section_superseded() -> None:
    print(NEWLINE + "[A'] a superseded Pages run is not a failed build; only a genuine failure is")
    # pages.yml: group `pages`, cancel-in-progress false. A run WAITING in that group is cancelled the
    # moment a newer run enters it, and the newer run builds a later commit -- this content included.

    # A7 the reviewers' reproduction: our run cancelled, a same-SHA run (e.g. the daily cron, or a
    # deploy-recovery dispatch) waiting behind it -- then that run succeeds.
    r, text, _, _ = confirm_case([[], [run("SELF", conclusion="cancelled", db=200),
                                       run("SELF", status="queued", conclusion=None, db=201)],
                                  [run("SELF", conclusion="cancelled", db=200), run("SELF", db=201)]], "a7")
    check("A7 a run cancelled by a newer one is not a failed build: the poll waits for the run that "
          "superseded it, which confirms", r.ok and r.pages_build_outcome == "confirmed"
          and not r.deployment_pending and aw.PAGES_BUILD_FAILED not in r.outcomes, f"{r.outcomes}")
    r, text, _, _ = confirm_case([[], [run("SELF", conclusion="cancelled", db=200),
                                       run("SELF", status="queued", conclusion=None, db=201)]], "a7b")
    check("A7 and when that run has not finished by the deadline: unverified, the lane stays green",
          r.ok and r.deployment_unverified and r.pages_build_outcome == "unconfirmed"
          and not r.deployment_pending and "the Pages run for this revision had not finished" in text,
          f"{r.outcomes} {text[:200]}")

    # A8 cancelled, and no other run for this revision or a later one ever shows up
    r, text, _, _ = confirm_case([[], [run("SELF", conclusion="cancelled", db=200)]], "a8")
    check("A8 a cancelled run with no successor in view is unverified (superseded), never failed",
          r.ok and r.deployment_unverified and not r.deployment_pending
          and aw.PAGES_BUILD_FAILED not in r.outcomes and "superseded" in text, f"{r.outcomes} {text[:200]}")

    # A9 another push lands right after ours; our run is cancelled and the LATER commit's run succeeds
    r, text, head, pushed = confirm_case([[], [run("PUSHED", conclusion="cancelled", db=200),
                                               run("SELF", db=300)]], "a9", advance=True)
    check("A9 the fixture is real: main moved past the pushed revision before the poll",
          bool(pushed) and head != pushed and r.pushed_sha == pushed, f"pushed={pushed} head={head}")
    check("A9 a later commit's successful build deploys this revision: confirmed",
          r.ok and r.pages_build_outcome == "confirmed" and not r.deployment_unverified, f"{r.outcomes}")

    r, text, _, _ = confirm_case([[], [run("PUSHED", conclusion="cancelled", db=200),
                                       run("SELF", status="in_progress", conclusion=None, db=300)]],
                                 "a10", advance=True)
    check("A10 superseded, and the later build has not finished: unverified, and the summary says so",
          r.ok and r.deployment_unverified and "newer build had not finished" in text, text[:300])

    r, text, _, _ = confirm_case([[], [run("PUSHED", conclusion="cancelled", db=200),
                                       run("SELF", conclusion="failure", db=300)]], "a11", advance=True)
    check("A11 superseded, and the LATER commit's build failed: unverified, not this lane's failed build",
          r.ok and r.deployment_unverified and not r.deployment_pending
          and r.pages_build_outcome == "unconfirmed" and "newer build that would deploy it failed" in text,
          f"{r.outcomes} {text[:300]}")

    # A12 the genuine failure conclusions other than `failure` (A2 pins `failure`)
    for conclusion in ("timed_out", "startup_failure"):
        r, text, _, _ = confirm_case([[], [run("SELF", conclusion=conclusion, db=200)]], f"a12{conclusion}")
        check(f"A12 a build of this revision that ended `{conclusion}` fails the lane",
              not r.ok and r.deployment_pending and r.pages_build_outcome == "failed", f"{r.outcomes}")

    # A13 direction matters: an ANCESTOR's successful build does not deploy this revision
    r, text, _, _ = confirm_case([[], [run("ROOT", db=50)]], "a13")
    check("A13 an older commit's successful build is never taken for this revision's deployment",
          r.pages_build_outcome == "unconfirmed" and aw.PAGES_BUILD_CONFIRMED not in r.outcomes, f"{r.outcomes}")

    # A14 the pre-dispatch snapshot could not be read (N2): a failed run for this revision cannot be
    # attributed to this dispatch -- it may be the stale build the dispatch replaces
    r, text, _, _ = confirm_case(["FAIL", [run("SELF", conclusion="failure", db=100)]], "a14")
    check("A14 with no readable snapshot a failed run for this SHA is not attributed: unverified, green",
          r.ok and r.deployment_unverified and not r.deployment_pending
          and aw.PAGES_BUILD_FAILED not in r.outcomes and "could not be attributed" in text,
          f"{r.outcomes} {text[:300]}")
    r, text, _, _ = confirm_case(["FAIL", [run("SELF", db=100)]], "a14b")
    check("A14 while a successful run for this SHA still confirms", r.ok and r.pages_build_outcome == "confirmed")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        unreadable = aw._run_ids_for_sha(cfg(work, pages_status_cmd=PY_FAIL), "abc")
        readable = aw._run_ids_for_sha(cfg(work, pages_status_cmd=scripted_status(
            tmp, origin, [[run("SELF", db=7)]], "a14c")), origin_head(origin))
    check("A14 an unreadable snapshot is None, never an empty set that claims no run existed",
          unreadable is None and readable == {"7"}, f"{unreadable!r} {readable!r}")

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

    # B7b (review NIT): main moved ONCE, the rebase was clean, and every push after it was refused by
    # a hook. upstream_advanced is in the outcomes, but the retries ran out on a refusal, not a race.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        push_change(other, "records/rec-other.md", "upstream B7b\n", "upstream")
        hook = origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho refused >&2\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        write(work, "records/rec-a.md", "mine B7b\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK, max_retries=1))
        check("B7b a clean rebase followed by pushes a hook refused is not a lost race",
              r.outcome == aw.RETRY_EXHAUSTED and aw.UPSTREAM_ADVANCED in r.outcomes
              and aw.REBASE_SUCCESS in r.outcomes and not r.pushed and not r.lost_race,
              f"{r.outcome} {r.outcomes}")

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




def section_stale_tree() -> None:
    print(NEWLINE + "[B'] a re-run starts from main, and no run ever pushes a stale tree")
    # A recovery is dispatched with `--ref main` and checks out main when its job starts (pinned in
    # [D]). If main moves again while it runs, the same writeback protects it as any run: it fetches
    # main before every push, rebases its single commit, re-validates the rebased tree, and refuses
    # any path both sides touched (B1).
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        other = clone(tmp, origin, "other")
        push_change(other, "records/rec-other.md", "upstream B10\n", "upstream")
        upstream_tip = origin_head(origin)
        write(work, "records/rec-a.md", "mine B10\n")
        r = aw.run_writeback(cfg(work, pages_cmd=PY_OK))
        parent = g(origin, "rev-parse", "main^").stdout.strip()
        check("B10 a run whose checkout went stale pushes its commit rebased onto the NEW main, "
              "re-validated, carrying both changes -- never its stale tree",
              r.pushed and parent == upstream_tip and aw.VALIDATION_SUCCESS_AFTER_REBASE in r.outcomes
              and "upstream B10" in g(origin, "show", "main:records/rec-other.md").stdout
              and "mine B10" in g(origin, "show", "main:records/rec-a.md").stdout,
              f"{r.outcomes} parent={parent} upstream={upstream_tip}")
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



def section_bare_script_superseded() -> None:
    print(NEWLINE + "[C'] the bare script reports a superseded run as unverified, not failed")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup(tmp)
        status = scripted_status(tmp, origin, [[], [run("SELF", conclusion="cancelled", db=9)]], "c5")
        write(work, "records/rec-a.md", "C5\n")
        rc, out, stdout, summary = run_script(tmp, work, [
            "--pages-cmd", PY_OK, "--pages-confirm-build", "--pages-confirm-attempts", "2",
            "--pages-confirm-interval", "0", "--pages-status-cmd", status], "c5")
        check("C5 a cancelled (superseded) Pages run exits 0 with deployment_unverified=true and no error",
              rc == 0 and out.get("deployment_unverified") == "true" and out.get("pages_build") == "unconfirmed"
              and out.get("deployment_pending") == "false" and out.get("pushed") == "true"
              and "::error" not in stdout and "::warning title=Deployment unverified::" in stdout,
              f"rc={rc} {out} {stdout[-300:]}")


# --------------------------------------------------------------------------------------------------
# [D] workflow wiring, parsed and evaluated
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


def script_invocations(doc: dict, script: str) -> list[tuple[str, dict, dict, list[str]]]:
    """(job name, job, step, argv) for every step whose executed shell runs `script`. argv is the
    real argument list: comments stripped, continuations joined, shlex-split."""
    found = []
    for jname, job in (doc.get("jobs") or {}).items():
        for step in (job.get("steps") or []):
            body = step.get("run") if isinstance(step, dict) else None
            if not isinstance(body, str):
                continue
            joined = re.sub(r"\\\n\s*", " ", strip_shell_comments(body))
            for line in joined.splitlines():
                if script not in line:
                    continue
                tokens = shlex.split(line)
                at = next(i for i, t in enumerate(tokens) if t.endswith(script))
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
    """A minimal evaluator for the expression grammar these workflows use: always(), cancelled(),
    format(), dotted context lookups, string literals, == / !=, &&, ||, !, parentheses. Unknown
    syntax raises. && and || return an operand, as GitHub's do, and equality follows GitHub's loose
    rule for the one case that matters here: a missing value equals ''."""

    TOKEN = re.compile(r"\s*(\$\{\{|\}\}|&&|\|\||==|!=|!|\(|\)|,|'[^']*'|[A-Za-z_][\w.-]*)")

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
        if t in ("always", "cancelled") and self.peek() == "(":
            self.take()
            self.take()
            return True if t == "always" else bool(self.ctx.get("__cancelled__", False))
        if t == "format" and self.peek() == "(":
            self.take()
            args = [self.parse_or()]
            while self.peek() == ",":
                self.take()
                args.append(self.parse_or())
            if self.take() != ")":
                raise ValueError("unbalanced format()")
            out = str(args[0])
            for n, a in enumerate(args[1:]):
                out = out.replace("{" + str(n) + "}", "" if a is None else str(a))
            return out
        if re.fullmatch(r"[A-Za-z_][\w-]*(\.[A-Za-z_][\w-]*)*", t):
            cur = self.ctx
            for part in t.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
            return cur
        raise ValueError(f"unsupported token {t!r}")


def evaluate(text: str, ctx: dict):
    try:
        return Expr(str(text), ctx).value()
    except ValueError as exc:
        return f"unparseable: {exc}"


def writer_group_members() -> set[str]:
    out = set()
    for path in WORKFLOWS.glob("*.yml"):
        c = load_wf(path.name).get("concurrency")
        group = c.get("group") if isinstance(c, dict) else c
        if group == WRITER_GROUP:
            out.add(path.name)
    return out


def marker_step(steps: list, reads: str) -> tuple[int, dict]:
    """The `Cycle reached main` step, located STRUCTURALLY -- the step whose `if` reads `reads` --
    so a mutant that renames it is caught by the name check rather than hidden from it."""
    for i, s in enumerate(steps):
        if isinstance(s, dict) and reads in str(s.get("if") or ""):
            return i, s
    return -1, {}


# Measured, not assumed (G91 round 2): the slowest post-collect tail of the collect job over the last
# 60 runs (run 44939561794, 25.3 min) and the slowest PowerPoint job outside one outlier (59.1 min).
MEASURED_POST_COLLECT_MIN = 25.3
MEASURED_PPT_JOB_MIN = 59.1


def section_wiring() -> None:
    print(NEWLINE + "[D] workflow wiring, parsed with the writeback's own argument parser")
    parser = aw.build_parser()
    lanes: dict[str, list] = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = load_wf(path.name)
        for jname, job, step, argv in script_invocations(doc, "automation_writeback.py"):
            lanes.setdefault(path.name, []).append((jname, job, step, parser.parse_args(argv)))
    expected = {EVIDENCE_WF, INGEST_WF, "davinci-updates.yml", "promote-davinci-verified-reports.yml"}
    check("D0 every CLI writer lane is found (closed world)", set(lanes) == expected, str(sorted(lanes)))
    collect_args = None
    for name in sorted(expected):
        for jname, job, step, args in lanes.get(name, []) or [(None, {}, {}, None)]:
            if args is None:
                check(f"D1 {name} confirms its Pages build", False, "no writeback invocation")
                continue
            if name == EVIDENCE_WF:
                collect_args = args
            check(f"D1 {name} confirms its Pages build", bool(args.pages_cmd) and args.pages_confirm_build,
                  f"pages_cmd={args.pages_cmd!r} confirm={args.pages_confirm_build}")
            bound = max(args.pages_confirm_attempts - 1, 0) * args.pages_confirm_interval
            # The last 100 Pages runs took 237-612 s from creation; one may queue behind another build
            # in the `pages` concurrency group. 900 s covers that; 1500 s keeps the writer lane short.
            check(f"D2 {name} waits long enough for a queued build, and no longer than the lane can afford",
                  900 <= bound <= 1500 and args.pages_confirm_interval >= 15,
                  f"bound={bound}s interval={args.pages_confirm_interval}")
            check(f"D3 {name} keeps --deploy-recovery", args.deploy_recovery)
            job_timeout = float(job.get("timeout-minutes") or 360)
            capped = sum(float(s.get("timeout-minutes") or 0) for s in job.get("steps") or []
                         if isinstance(s, dict) and s is not step)
            tail = MEASURED_POST_COLLECT_MIN if (name == EVIDENCE_WF and jname == "collect") else 0.0
            headroom = job_timeout - capped - tail - bound / 60.0
            check(f"D4 {name}/{jname} keeps at least 10 minutes of its job budget after its capped steps, "
                  f"the measured uncapped tail and the confirm wait", headroom >= 10,
                  f"headroom={headroom:.1f} min (timeout {job_timeout}, capped {capped}, tail {tail})")

    ev = load_wf(EVIDENCE_WF)
    jobs = ev["jobs"]
    collect, ppt, chain = jobs["collect"], jobs["powerpoint-orchestrated"], jobs["chain-ingest"]
    wb_steps = [s for s in collect["steps"] if isinstance(s, dict)
                and "automation_writeback.py" in strip_shell_comments(str(s.get("run") or ""))]
    check("D5 the collect job's writeback step carries id `writeback`",
          len(wb_steps) == 1 and wb_steps[0].get("id") == "writeback", str([s.get("id") for s in wb_steps]))
    sentinel = {"steps": {"writeback": {"outputs": {"pushed": "PUSHED", "outcome": "OUTCOME"}},
                          "graph": {"outputs": {"pushed": "GPUSHED", "outcome": "GOUTCOME"}}}}
    try:
        exported = {k: eval_ref((collect.get("outputs") or {}).get(k, ""), sentinel)
                    for k in ("writeback_pushed", "writeback_outcome")}
        gexported = {k: eval_ref((ppt.get("outputs") or {}).get(k, ""), sentinel)
                     for k in ("writeback_pushed", "writeback_outcome")}
    except ValueError as exc:
        exported = gexported = {"error": str(exc)}
    check("D5 the collect job exports its writeback's pushed and outcome",
          exported == {"writeback_pushed": "PUSHED", "writeback_outcome": "OUTCOME"}, str(exported))
    check("D5 the PowerPoint job exports its graph writeback's pushed and outcome",
          gexported == {"writeback_pushed": "GPUSHED", "writeback_outcome": "GOUTCOME"}, str(gexported))

    # D6 chain-ingest's `Cycle reached main`: first step, evaluated over every outcome pair that matters
    csteps = chain.get("steps") or []
    first = csteps[0] if csteps else {}
    check("D6 chain-ingest's FIRST step is the cycle record, named exactly as the reaper reads it",
          first.get("name") == wcr.CYCLE_MARKER_STEP and "run" in first, str(first.get("name")))

    def reached(c_pushed, c_outcome, p_pushed, p_outcome):
        return evaluate(first.get("if", ""), {"needs": {
            "collect": {"outputs": {"writeback_pushed": c_pushed, "writeback_outcome": c_outcome}},
            "powerpoint-orchestrated": {"outputs": {"writeback_pushed": p_pushed, "writeback_outcome": p_outcome}}}})

    cases = {
        "both pushed": (("true", "push_success_first_attempt", "true", "push_success_after_retry"), True),
        "collect had nothing to push": (("false", "no_changes", "true", "push_success_first_attempt"), True),
        "PowerPoint had nothing to push": (("true", "push_success_first_attempt", "false", "no_changes"), True),
        "collect lost its race": (("false", "rebase_conflict", "true", "push_success_first_attempt"), False),
        "collect writeback skipped (failure/time limit earlier)": (("", "", "true", "no_changes"), False),
        "PowerPoint graph never wrote back": (("true", "push_success_first_attempt", "", ""), False),
        "PowerPoint validation refused": (("true", "push_success_first_attempt", "false",
                                           "validation_failed_pre_commit"), False),
    }
    got = {k: reached(*v[0]) is v[1] for k, v in cases.items()}
    check("D6 it runs exactly when BOTH writer jobs' cycles reached main", all(got.values()), str(got))
    disp = csteps[1:] if len(csteps) > 1 else []
    check("D6 chain-ingest still dispatches ingestion after it, and dispatches nothing else",
          len(disp) == 1 and "patch-ingest.yml" in strip_shell_comments(str(disp[0].get("run")))
          and EVIDENCE_WF not in strip_shell_comments(str(disp[0].get("run"))), str([s.get("name") for s in disp]))
    check("D6 chain-ingest still needs both writer jobs", set(chain.get("needs") or []) ==
          {"collect", "powerpoint-orchestrated"}, str(chain.get("needs")))

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
        gcases = {
            "schedule": gate("schedule", None) is True,
            "no-input dispatch (reaper)": gate("workflow_dispatch", routine) is True,
            "recovery dispatch": gate("workflow_dispatch", recovery) is True,
            "targeted dispatch": gate("workflow_dispatch", dict(routine, product_id="obs-studio")) is False,
            "dry run": gate("workflow_dispatch", dict(routine, dry_run="true")) is False,
        }
    except ValueError as exc:
        gcases = {f"unparseable: {exc}": False}
    check("D8 a recovery run is still a routine cycle: it records its cycle and dispatches ingestion",
          all(gcases.values()), str(gcases))

    # D9 patch-ingest's `Cycle reached main`
    isteps = load_wf(INGEST_WF)["jobs"]["ingest"]["steps"]
    commit_idx = next((i for i, s in enumerate(isteps) if s.get("id") == "commit"), -1)
    m_idx, mstep = marker_step(isteps, "steps.commit.outputs.pushed")
    check("D9 patch-ingest records its cycle in a step after its writeback, named exactly as the reaper reads it",
          0 <= commit_idx < m_idx and mstep.get("name") == wcr.CYCLE_MARKER_STEP, f"{commit_idx} {m_idx} {mstep.get('name')}")

    def ingest_reached(pushed, outcome):
        return evaluate(mstep.get("if", ""), {"steps": {"commit": {"outputs": {"pushed": pushed, "outcome": outcome}}}})

    icases = {
        "pushed": (("true", "push_success_first_attempt"), True),
        "nothing to push": (("false", "no_changes"), True),
        "access refusal committed, job still failed": (("true", "push_success_after_retry"), True),
        "lost its race": (("false", "rebase_conflict"), False),
        "writeback skipped (ingestion failed)": (("", ""), False),
    }
    igot = {k: (ingest_reached(*v[0]) is v[1]) for k, v in icases.items()}
    check("D9 it runs exactly when the writeback reached main", all(igot.values()), str(igot))
    check("D9 and it is recorded even when a later step fails or the run is cancelled (always())",
          "always()" in str(mstep.get("if")), str(mstep.get("if")))
    check("D9 patch-ingest no longer re-dispatches itself (recovery is the reaper's, from outside)",
          not any("patch-ingest.yml" in strip_shell_comments(str(s.get("run") or "")) for s in isteps),
          "a step of patch-ingest names its own workflow")

    # D10 run names: evaluated per context, and parsed back by the reaper's module
    for name, wfname in ((EVIDENCE_WF, "Patch Evidence Collection"), (INGEST_WF, "AUXSAYS Patch Ingestion")):
        expr = str(load_wf(name).get("run-name") or "")
        rec = evaluate(expr, {"inputs": {"recovery_of": "44878227542"}})
        plain = evaluate(expr, {"inputs": {"recovery_of": ""}})
        sched = evaluate(expr, {"inputs": {}})
        check(f"D10 {name}: a recovery run is titled with the run it re-runs, every other run keeps the name",
              rec == f"{wfname} (recovery of run 44878227542)" and plain == wfname and sched == wfname,
              f"{rec!r} {plain!r} {sched!r}")
        check(f"D10 {name}: the reaper's module reads that title back, and only that title",
              wcr.recovery_of({"display_title": rec}) == "44878227542"
              and wcr.recovery_of({"display_title": plain}) == "", f"{rec!r}")

    # D11 the reaper: eviction step first, then the lost-cycle step wired to its outputs
    reaper = load_wf(REAPER_WF)
    rjob = reaper["jobs"]["reap"]
    rsteps = rjob.get("steps") or []
    check("D11 the reaper's FIRST step is still the eviction repair (test_writer_queue_reaper_behaviour "
          "executes steps[0])", bool(rsteps) and rsteps[0].get("id") == "reap", str(rsteps[0].get("id") if rsteps else None))
    inv = script_invocations(reaper, "writer_cycle_recovery.py")
    check("D11 one later step runs writer_cycle_recovery.py", len(inv) == 1, str(len(inv)))
    if inv:
        _, _, rstep, rargv = inv[0]
        rargs = wcr.build_parser().parse_args(rargv)
        renv = rstep.get("env") or {}
        ctx = {"steps": {"reap": {"outputs": {"busy": "BUSY", "dispatched": "DISP"}}}}
        try:
            resolved = {"LANE_BUSY": eval_ref(renv.get("LANE_BUSY", ""), ctx),
                        "DISPATCHED": eval_ref(renv.get("DISPATCHED", ""), ctx)}
        except ValueError as exc:
            resolved = {"error": str(exc)}
        check("D11 it passes the eviction step's `busy` and `dispatched` outputs, through env",
              rargs.lane_busy == "${LANE_BUSY}" and rargs.dispatched == "${DISPATCHED}"
              and resolved == {"LANE_BUSY": "BUSY", "DISPATCHED": "DISP"}, f"{rargs} {resolved}")
        idx = rsteps.index(rstep)
        runs_after_fail = evaluate(rstep.get("if", ""), {"__cancelled__": False})
        check("D11 it runs after the eviction step whatever that step did, but not on cancellation",
              idx > 0 and runs_after_fail is True and evaluate(rstep.get("if", ""), {"__cancelled__": True}) is False,
              str(rstep.get("if")))
        checkouts = [s for s in rsteps[:idx] if "actions/checkout" in str(s.get("uses"))]
        check("D11 the scripts are checked out before it runs",
              any("auxsays/scripts" in str((s.get("with") or {}).get("sparse-checkout")) for s in checkouts),
              str(checkouts))
    jenv = rjob.get("env") or {}
    check("D11 the reaper job provides REPO, REAPABLE, GROUP_MEMBERS and a token to that step",
          {"REPO", "REAPABLE", "GROUP_MEMBERS", "GH_TOKEN"} <= set(jenv)
          and set(str(jenv.get("REAPABLE")).split()) == {EVIDENCE_WF, INGEST_WF}
          and set(str(jenv.get("GROUP_MEMBERS")).split()) == writer_group_members(), str(sorted(jenv)))
    perms = reaper.get("permissions") or {}
    check("D11 the reaper may keep the tracking issue and read job annotations, and still only reads code",
          perms.get("issues") == "write" and perms.get("checks") == "read" and perms.get("contents") == "read"
          and perms.get("actions") == "write", str(perms))

    # D12 the PowerPoint lane: its deployment is confirmed, and a failed one turns the lane red
    psteps = ppt.get("steps") or []
    f_idx, fstep = marker_step(psteps, "steps.graph.outputs.deployment_pending")
    g_idx = next((i for i, s in enumerate(psteps) if s.get("id") == "graph"), -1)
    fires = {v: evaluate(fstep.get("if", ""), {"steps": {"graph": {"outputs": {"deployment_pending": v}}}})
             for v in ("true", "false", "")}
    check("D12 a step after the graph fails the PowerPoint lane exactly when its deployment failed",
          0 <= g_idx < f_idx and fires == {"true": True, "false": False, "": False}, f"{g_idx} {f_idx} {fires}")
    import orchestrate_evidence_run as orch
    ppt_bound = max(0, orch.PAGES_CONFIRM_ATTEMPTS - 1) * orch.PAGES_CONFIRM_INTERVAL / 60.0
    ppt_headroom = float(ppt.get("timeout-minutes") or 360) - MEASURED_PPT_JOB_MIN - ppt_bound
    check("D12 the PowerPoint job's time limit leaves 30 minutes after its slowest measured run and the "
          "confirm wait", ppt_headroom >= 30, f"headroom={ppt_headroom:.1f} (bound {ppt_bound:.1f} min)")
    if collect_args is not None:
        check("D12 the graph confirms with the same bound as the command-line collect lane",
              (orch.PAGES_CONFIRM_ATTEMPTS, orch.PAGES_CONFIRM_INTERVAL)
              == (collect_args.pages_confirm_attempts, collect_args.pages_confirm_interval),
              f"{orch.PAGES_CONFIRM_ATTEMPTS}/{orch.PAGES_CONFIRM_INTERVAL}")

    # D13 (amendment A1.2) a re-run starts from main as it is when its job STARTS. A recovery is
    # dispatched with `--ref main` (E1, E2, G1), so github.ref is refs/heads/main while github.sha is
    # the tip at dispatch time, which a run waiting in the writer queue can be far behind. Every writer
    # job checks out the REF, resolved when the checkout runs -- never the dispatch-time SHA.
    recovery_ctx = {"github": {"ref": "refs/heads/main", "sha": "0000000stale-dispatch-time-tip"}}
    refs = {}
    for name, jname in ((EVIDENCE_WF, "collect"), (EVIDENCE_WF, "powerpoint-orchestrated"), (INGEST_WF, "ingest")):
        cos = [s for s in (load_wf(name)["jobs"][jname].get("steps") or [])
               if isinstance(s, dict) and str(s.get("uses") or "").startswith("actions/checkout@")]
        try:
            refs[f"{name}/{jname}"] = [eval_ref((c.get("with") or {}).get("ref", ""), recovery_ctx) for c in cos]
        except ValueError as exc:
            refs[f"{name}/{jname}"] = [f"unsupported: {exc}"]
    check("D13 every writer job of a re-run checks out main as it is when the job starts, not the dispatch-time SHA",
          all(v == ["refs/heads/main"] for v in refs.values()), str(refs))


# --------------------------------------------------------------------------------------------------
# [E] shell, executed
# --------------------------------------------------------------------------------------------------
# chain-ingest's dispatch and the PowerPoint failure step: a fake gh that logs every dispatch.
FAKE_GH = r"""#!/usr/bin/env bash
echo "GH $*" >> "$SIM_LOG"
if [ "$1" = "workflow" ]; then
  echo "DISPATCH $*" >> "$SIM_LOG"
  exit "${SIM_DISPATCH_RC:-0}"
fi
q="$*"
case "$q" in
  # the reaper's eviction step: occupancy, covering run, evicted runs (with titles), jobs
  *'.status == "pending"'*) echo "${SIM_BUSY:-0}" ;;
  *'conclusion == "success"'*) echo "${SIM_COVERING:-}" ;;
  *'conclusion == "cancelled"'*)
    case "$q" in
      *obs-evidence-collection*) printf '%b' "${SIM_EVICTED_OBS:-}" ;;
      *patch-ingest*) printf '%b' "${SIM_EVICTED_ING:-}" ;;
    esac ;;
  */jobs*) echo "${SIM_JOBS:-0}" ;;
  *) echo 0 ;;
esac
exit 0
"""


def run_shell(script: str, sim_env: dict) -> tuple[int, list[list[str]], str, str]:
    """Run a step's `run:` scalar the way GitHub runs a step with no `shell:` (bash -e), with a fake
    gh first on PATH. Returns (exit code, dispatches as token lists, stdout+stderr, $GITHUB_OUTPUT)."""
    tmp = tempfile.mkdtemp()
    try:
        gh = Path(tmp, "gh")
        gh.write_text(FAKE_GH, newline="\n")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        sh = Path(tmp, "step.sh")
        sh.write_text(script, newline="\n")
        log = Path(tmp, "gh.log")
        log.write_text("", newline="\n")
        out_f = Path(tmp, "output")
        env = dict(os.environ)
        env.update({
            "PATH": tmp + os.pathsep + env.get("PATH", ""),
            "GITHUB_STEP_SUMMARY": str(Path(tmp, "summary.md")),
            "GITHUB_OUTPUT": str(out_f),
            "SIM_LOG": str(log),
            "REPO": "owner/repo",
            "GH_TOKEN": "fake",
        })
        env.update(sim_env)
        proc = subprocess.run([shutil.which("bash") or "bash", "--noprofile", "--norc", "-e", str(sh)],
                              capture_output=True, text=True, env=env)
        lines = log.read_text().splitlines()
        dispatches = [shlex.split(ln)[1:] for ln in lines if ln.startswith("DISPATCH ")]
        output = out_f.read_text() if out_f.exists() else ""
        return proc.returncode, dispatches, proc.stdout + proc.stderr, output
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


def on_main(d: list[str]) -> bool:
    """A `workflow run` token list targets exactly `--ref main`, once."""
    refs = [d[i + 1] for i, t in enumerate(d) if t == "--ref" and i + 1 < len(d)]
    return refs == ["main"]


def declared_inputs(name: str) -> set[str]:
    return set(((load_wf(name)["on"].get("workflow_dispatch") or {}).get("inputs") or {}).keys())


def section_executed() -> None:
    print(NEWLINE + "[E] shell executed under bash against a fake gh")
    if shutil.which("bash") is None:
        check("E bash is available to execute the workflow shell", False, "bash not found")
        return

    chain = load_wf(EVIDENCE_WF)["jobs"]["chain-ingest"]["steps"]
    body = str(chain[1].get("run") if len(chain) > 1 else "").replace("${{ github.repository }}", "owner/repo")
    check("E1 the dispatch step interpolates nothing else", "${{" not in body)
    rc, ds, out, _ = run_shell(body, {})
    summ = [dispatch_summary(d) for d in ds]
    check("E1 chain-ingest dispatches routine ingestion once, with no inputs, and nothing else",
          rc == 0 and summ == [(INGEST_WF, {})], f"rc={rc} {summ} {out[-300:]}")
    check("E1 and on main", len(ds) == 1 and on_main(ds[0]), str(ds))

    reaper = load_wf(REAPER_WF)["jobs"]["reap"]
    step0 = reaper["steps"][0]["run"]
    renv = reaper.get("env") or {}
    base = {"GROUP_MEMBERS": " ".join(str(renv.get("GROUP_MEMBERS", "")).split()),
            "REAPABLE": str(renv.get("REAPABLE", ""))}

    rc, ds, out, output = run_shell(step0, dict(base, SIM_EVICTED_OBS=(
        "101 2026-11-22T03:00:00Z Patch Evidence Collection (recovery of run 99)\\n")))
    summ = [dispatch_summary(d) for d in ds]
    check("E2 an evicted RECOVERY run is re-dispatched carrying the SAME recovery_of (finding 4: the "
          "loop guard survives an eviction)", rc == 0 and summ == [(EVIDENCE_WF, {"recovery_of": "99"})],
          f"rc={rc} {summ} {out[-300:]}")
    check("E2 and on main (amendment A1.2: a re-run starts from main)", len(ds) == 1 and on_main(ds[0]), str(ds))
    rc, ds, out, output = run_shell(step0, dict(base, SIM_EVICTED_ING=(
        "201 2026-11-22T03:00:00Z AUXSAYS Patch Ingestion\\n")))
    summ = [dispatch_summary(d) for d in ds]
    check("E2 an evicted routine run is re-dispatched as the recovery of ITSELF",
          rc == 0 and summ == [(INGEST_WF, {"recovery_of": "201"})], f"rc={rc} {summ}")
    check("E2 every input it passes is declared by the workflow it dispatches",
          all(set(f) <= declared_inputs(wf) for wf, f in summ if wf), str(summ))
    outs = dict(ln.split("=", 1) for ln in output.splitlines() if "=" in ln)
    check("E2 and it tells the next step the lane was free and that it added the tick's one entrant",
          outs.get("busy") == "0" and outs.get("dispatched") == "1", str(outs))
    rc, ds, out, output = run_shell(step0, dict(base, SIM_BUSY="1", SIM_EVICTED_OBS=(
        "101 2026-11-22T03:00:00Z Patch Evidence Collection\\n")))
    outs = dict(ln.split("=", 1) for ln in output.splitlines() if "=" in ln)
    check("E2 an occupied lane: nothing dispatched, and the next step is told so",
          rc == 0 and ds == [] and int(outs.get("busy") or 0) > 0 and outs.get("dispatched") == "0", f"{ds} {outs}")
    rc, ds, out, output = run_shell(step0, dict(base))
    outs = dict(ln.split("=", 1) for ln in output.splitlines() if "=" in ln)
    check("E2 a quiet tick reports a free lane and no entrant", rc == 0 and ds == []
          and outs.get("busy") == "0" and outs.get("dispatched") == "0", str(outs))

    ppt = load_wf(EVIDENCE_WF)["jobs"]["powerpoint-orchestrated"]["steps"]
    _, fstep = marker_step(ppt, "steps.graph.outputs.deployment_pending")
    rc, ds, out, _ = run_shell(str(fstep.get("run") or "exit 0"), {"PAGES_BUILD": "failed"})
    check("E3 the PowerPoint failure step fails the lane and says why", rc != 0 and "::error" in out, f"rc={rc}")


# --------------------------------------------------------------------------------------------------
# [F] writer_cycle_recovery's decisions
# --------------------------------------------------------------------------------------------------
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
BOT = "github-actions[bot]"
WRITEBACK_STEP = "Commit material evidence changes (conflict-safe writeback)"


def at(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def wrun(rid: int, hours_ago: float, conclusion: str = "success", event: str = "schedule",
         actor: str = "auxchan", of: str = "", name: str = "Patch Evidence Collection") -> dict:
    return {"id": rid, "created_at": at(hours_ago), "status": "completed", "conclusion": conclusion,
            "event": event, "triggering_actor": {"login": actor},
            "display_title": name + (f" (recovery of run {of})" if of else ""),
            "html_url": f"https://github.com/o/r/actions/runs/{rid}"}


def recovery_run(rid: int, hours_ago: float, of: str, conclusion: str = "failure", **kw) -> dict:
    return wrun(rid, hours_ago, conclusion, event="workflow_dispatch", actor=BOT, of=of, **kw)


def jobs_of(marker: bool = False, failed: bool = True, cancelled_job: int | None = None,
            evicted: bool = False) -> dict:
    if evicted:
        return {"total_count": 0, "jobs": []}
    js = [{"id": 1, "name": "collect", "conclusion": "failure" if failed else "success",
           "steps": [{"name": WRITEBACK_STEP, "conclusion": "failure" if failed else "success"}]},
          {"id": 3, "name": "chain-ingest", "conclusion": "success",
           "steps": [{"name": wcr.CYCLE_MARKER_STEP, "conclusion": "success" if marker else "skipped"}]}]
    if cancelled_job is not None:
        js.append({"id": cancelled_job, "name": "powerpoint-orchestrated", "conclusion": "cancelled",
                   "steps": [{"name": "Run the PowerPoint evidence graph", "conclusion": "cancelled"}]})
    return {"total_count": len(js), "jobs": js}


TIMEOUT_NOTES = [{"annotation_level": "failure",
                  "message": "The job has exceeded the maximum execution time of 1h30m0s"},
                 {"annotation_level": "failure", "message": "The operation was canceled."}]
CANCEL_NOTES = [{"annotation_level": "failure", "message": "The operation was canceled."}]


def legacy_jobs() -> dict:
    """A green run from before the cycle record existed: no `Cycle reached main` step at all."""
    return {"total_count": 2, "jobs": [
        {"id": 1, "name": "collect", "conclusion": "success",
         "steps": [{"name": WRITEBACK_STEP, "conclusion": "success"}]},
        {"id": 3, "name": "chain-ingest", "conclusion": "success",
         "steps": [{"name": "Dispatch routine patch ingestion", "conclusion": "success"}]}]}


def with_green_jobs(runs, jobs: dict | None) -> dict:
    """`jobs`, plus a successful cycle record for every green run the test gave none: the module
    reads the record of a green run too, and most scenarios are about the runs that are not green."""
    out = dict(jobs or {})
    lists = runs.values() if isinstance(runs, dict) else [runs]
    for lst in lists:
        for r in lst if isinstance(lst, list) else []:
            if r.get("conclusion") == "success" and str(r.get("id")) not in out:
                out[str(r.get("id"))] = jobs_of(marker=True, failed=False)
    return out


def decide(runs: list, jobs: dict | None = None, notes: dict | None = None, wf: str = EVIDENCE_WF):
    jobs = with_green_jobs(runs, jobs)
    notes = notes or {}
    return wcr.decide_lane(wf, runs, lambda rid: jobs.get(str(rid)), lambda jid: notes.get(str(jid)), NOW)


class FakeGhObj:
    """plan_tick's view of the API, from dicts. A missing entry reads as unreadable."""

    def __init__(self, runs: dict, jobs: dict | None = None, notes: dict | None = None,
                 pages: list | None = None, active: dict | None = None) -> None:
        self._runs, self._jobs, self._notes = runs, with_green_jobs(runs, jobs), notes or {}
        self._pages = [] if pages is None else pages
        self._active = active or {}

    def active(self, wf):
        return self._active.get(wf, 0)

    def runs(self, wf):
        return self._runs.get(wf)

    def jobs(self, rid):
        return self._jobs.get(str(rid))

    def annotations(self, jid):
        return self._notes.get(str(jid))

    def pages_runs(self):
        return self._pages


def prun(rid: int, hours_ago: float, conclusion: str = "success", branch: str = "main") -> dict:
    return {"id": rid, "created_at": at(hours_ago), "status": "completed", "conclusion": conclusion,
            "head_branch": branch, "head_sha": f"{rid:07d}abcdef", "html_url": f"https://github.com/o/r/actions/runs/{rid}"}


def section_decisions() -> None:
    print(NEWLINE + "[F] writer_cycle_recovery: which cycle is re-run, which is reported")
    d = decide([wrun(5, 2), wrun(4, 8, "failure")])
    check("F1 the latest routine run reached main: nothing re-run, nothing reported",
          d.decided and not d.dispatch_recovery_of and not d.problem, d.note)
    d = decide([wrun(5, 2, "failure"), wrun(4, 8)], {"5": jobs_of()})
    check("F2 the latest routine run ended without its cycle on main: re-run once, as its recovery",
          d.dispatch_recovery_of == "5" and not d.problem, d.note)
    d = decide([wrun(5, 2, "failure"), wrun(4, 8)], {"5": jobs_of(marker=True)})
    check("F3 a run that failed AFTER its cycle reached main (e.g. its Pages build) is never re-run",
          not d.dispatch_recovery_of and not d.problem, d.note)
    d = decide([recovery_run(6, 1, of="5"), wrun(5, 6, "failure")], {"6": jobs_of(), "5": jobs_of()})
    check("F4 a recovery that lost its cycle too is not re-run, and is reported with both run ids",
          not d.dispatch_recovery_of and "6" in d.problem and "re-run of run 5" in d.problem, d.problem)
    d = decide([wrun(7, 1, "failure"), recovery_run(6, 6, of="5"), wrun(5, 10, "failure")],
               {"7": jobs_of(), "6": jobs_of(), "5": jobs_of()})
    check("F5 after a recovery lost, later lost cycles pause until a run reaches main (no retry storm)",
          not d.dispatch_recovery_of and "paused" in d.problem and "recovery run 6" in d.problem, d.problem)
    d = decide([wrun(9, 1, "failure"), wrun(8, 5), recovery_run(6, 20, of="5")],
               {"9": jobs_of(), "6": jobs_of()})
    check("F6 a run that reached main since then lifts the pause: the new loss is re-run",
          d.dispatch_recovery_of == "9" and not d.problem, d.note)
    d = decide([wrun(5, 20, "failure")], {"5": jobs_of()})
    check("F7 a lost cycle older than the re-run window is reported, not re-run",
          not d.dispatch_recovery_of and "not re-run automatically" in d.problem, d.problem)
    d = decide([wrun(5, 2, "cancelled"), wrun(4, 8)], {"5": jobs_of(failed=False, cancelled_job=77)},
               {"77": TIMEOUT_NOTES})
    check("F8 a run whose job hit its time limit (cancelled, with GitHub's timeout annotation) is lost: re-run",
          d.dispatch_recovery_of == "5", d.note)
    d = decide([wrun(5, 2, "cancelled"), wrun(4, 8)], {"5": jobs_of(marker=True, failed=False, cancelled_job=77)},
               {"77": TIMEOUT_NOTES})
    check("F8 unless its cycle had already reached main", not d.dispatch_recovery_of and not d.problem, d.note)
    d = decide([wrun(5, 2, "cancelled"), wrun(4, 8)], {"5": jobs_of(failed=False, cancelled_job=77)},
               {"77": CANCEL_NOTES})
    check("F9 an operator's cancel of a started run is left alone, as the eviction step leaves it",
          not d.dispatch_recovery_of and not d.problem and d.decided, d.note)
    d = decide([wrun(5, 1, "cancelled"), wrun(4, 4, "failure")],
               {"5": jobs_of(failed=False, cancelled_job=77), "4": jobs_of()}, {"77": CANCEL_NOTES})
    check("F9 and does not hide an older lost cycle behind it", d.dispatch_recovery_of == "4", d.note)
    d = decide([wrun(5, 1, "cancelled"), wrun(4, 6)], {"5": jobs_of(evicted=True)})
    check("F10 an eviction (zero jobs) is the eviction step's, not this step's",
          not d.dispatch_recovery_of and not d.problem, d.note)
    d = decide([wrun(5, 1, "failure", event="workflow_dispatch", actor="auxchan"), wrun(4, 6)])
    check("F11 an operator's own dispatch is never re-run (and is not even read)",
          d.decided and not d.dispatch_recovery_of and not d.problem, d.note)
    d = decide([wrun(5, 1, "failure")], {})
    check("F12 a run that cannot be read decides nothing: no re-run, no report",
          not d.decided and not d.dispatch_recovery_of and not d.problem, d.note)
    d = decide([wrun(5, 1, "cancelled")], {"5": jobs_of(failed=False, cancelled_job=77)}, {})
    check("F12 nor do unreadable annotations", not d.decided and not d.dispatch_recovery_of, d.note)
    d = decide([recovery_run(6, 1, of="5", conclusion="cancelled"), wrun(5, 4, "failure")],
               {"6": jobs_of(failed=False, cancelled_job=78), "5": jobs_of()}, {"78": CANCEL_NOTES})
    check("F13 a recovery an operator cancelled after it started is not attempted again",
          not d.dispatch_recovery_of and not d.problem, d.note)
    frees = {(b, x): wcr.lane_free(b, x) for b, x in (("0", "0"), ("", "0"), ("0", ""), ("1", "0"),
                                                       ("0", "1"), ("x", "0"))}
    check("F14 only a positively free lane with no entrant this tick may take one; anything else is occupied",
          frees == {("0", "0"): True, ("", "0"): False, ("0", ""): False, ("1", "0"): False,
                    ("0", "1"): False, ("x", "0"): False}, str(frees))
    both_lost = {EVIDENCE_WF: [wrun(5, 2, "failure")], INGEST_WF: [wrun(15, 1, "failure", name="AUXSAYS Patch Ingestion")]}
    lost_jobs = {"5": jobs_of(), "15": jobs_of()}
    members = sorted(writer_group_members())
    plan = wcr.plan_tick(FakeGhObj(both_lost, lost_jobs), [EVIDENCE_WF, INGEST_WF], "0", "0", NOW, members)
    check("F15 two lanes with lost cycles still get exactly one entrant per tick, group-wide",
          plan.dispatch == (EVIDENCE_WF, "5"), str(plan.dispatch))
    plan = wcr.plan_tick(FakeGhObj({EVIDENCE_WF: [recovery_run(6, 1, of="5")], INGEST_WF: [wrun(15, 1, "failure")]},
                                   {"6": jobs_of(), "15": jobs_of()}), [EVIDENCE_WF, INGEST_WF], "2", "0", NOW, members)
    check("F15 an occupied lane gets no entrant, but persistent failures are still reported",
          plan.dispatch is None and len(plan.problems) == 1 and EVIDENCE_WF in plan.problems[0], str(plan.problems))
    held = {}
    for label, active in (("a member's run is now pending", {"davinci-updates.yml": 1}),
                          ("a member's runs cannot be read", {"promote-davinci-verified-reports.yml": None})):
        p2 = wcr.plan_tick(FakeGhObj(both_lost, lost_jobs, active=active), [EVIDENCE_WF, INGEST_WF], "0", "0",
                           NOW, members)
        held[label] = p2.dispatch is None and p2.held == (EVIDENCE_WF, "5")
    p3 = wcr.plan_tick(FakeGhObj(both_lost, lost_jobs), [EVIDENCE_WF, INGEST_WF], "0", "0", NOW, [])
    held["no group members named"] = p3.dispatch is None
    check("F18 the group-wide check is repeated right before the dispatch: a writer that entered since, "
          "an unreadable member or an unnamed group holds it back", all(held.values()), str(held))
    pages = {
        "latest failed": ([prun(3, 1, "failure"), prun(2, 5)], True),
        "latest timed out": ([prun(3, 1, "timed_out")], True),
        "latest cancelled, the one before succeeded": ([prun(3, 1, "cancelled"), prun(2, 5)], False),
        "latest cancelled, the one before failed": ([prun(3, 1, "cancelled"), prun(2, 5, "failure")], True),
        "latest succeeded after a failure": ([prun(3, 1), prun(2, 5, "failure")], False),
        "another branch failed": ([prun(3, 1, "failure", branch="feature"), prun(2, 5)], False),
    }
    pgot = {k: (bool(wcr.pages_problem(v)[1]) is want and wcr.pages_problem(v)[0]) for k, (v, want) in pages.items()}
    check("F16 Pages: the latest completed, non-cancelled build on main decides; only a genuine failure is a problem",
          all(pgot.values()) and wcr.pages_problem(None) == (False, ""), str(pgot))
    check("F17 the module reads a recovery title from either writer workflow, and nothing else",
          wcr.recovery_of({"display_title": "Patch Evidence Collection (recovery of run 123)"}) == "123"
          and wcr.recovery_of({"display_title": "AUXSAYS Patch Ingestion (recovery of run 9)"}) == "9"
          and wcr.recovery_of({"display_title": "Patch Evidence Collection"}) == ""
          and wcr.recovery_of({"display_title": "recovery of run 7 (manual)"}) == "")
    # F19-F21: a GREEN run is judged by its record too. The PowerPoint graph's step takes `tee`'s exit
    # status, so its writeback can lose a race (or the graph can stop before writing back) while the
    # whole run concludes `success` -- with chain-ingest's `Cycle reached main` skipped.
    d = decide([wrun(5, 2), wrun(4, 8)], {"5": jobs_of(marker=False, failed=False)})
    check("F19 a green run whose cycle record was skipped (the PowerPoint writeback lost its race) is lost: re-run",
          d.dispatch_recovery_of == "5" and not d.problem and "`success`" in d.note, d.note)
    d = decide([wrun(5, 2), wrun(4, 8, "failure")], {"5": legacy_jobs()})
    check("F20 a green run from before the record existed (no such step at all) reached main: nothing re-run",
          d.decided and not d.dispatch_recovery_of and not d.problem, d.note)
    d = decide([wrun(5, 2)], {"5": None})
    check("F21 a green run whose jobs cannot be read decides nothing (its record is unknown)",
          not d.decided and not d.dispatch_recovery_of and not d.problem, d.note)


# --------------------------------------------------------------------------------------------------
# [G] writer_cycle_recovery as a bare script, against a fake gh serving raw API JSON
# --------------------------------------------------------------------------------------------------
FAKE_GH_PY = r'''
import json, os, re, sys
args = sys.argv[1:]
scn = json.load(open(os.environ["FAKE_GH_SCENARIO"], encoding="utf-8"))
log = open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8")
def out(obj):
    sys.stdout.write(json.dumps(obj))
if args[:2] == ["workflow", "run"]:
    log.write(json.dumps({"kind": "dispatch", "args": args}) + "\n")
    sys.exit(scn.get("write_rc", 0))
if args and args[0] == "api":
    if "-X" in args:
        i = args.index("-X")
        method = args[i + 1]
        rest = [a for j, a in enumerate(args) if j not in (0, i, i + 1)]
        fields = {}
        for j, a in enumerate(rest):
            if a == "-f":
                k, v = rest[j + 1].split("=", 1)
                fields[k] = v
        log.write(json.dumps({"kind": "write", "method": method, "path": rest[0], "fields": fields}) + "\n")
        out({})
        sys.exit(scn.get("write_rc", 0))
    path = args[1]
    log.write(json.dumps({"kind": "read", "path": path}) + "\n")
    def serve(v, wrap=None):
        if v is None or v == "FAIL":
            sys.exit(1)
        out({wrap: v} if wrap else v)
        sys.exit(0)
    m = re.match(r"repos/[^/]+/[^/]+/actions/workflows/([^/?]+)/runs", path)
    if m and m.group(1) == "pages.yml":
        serve(scn.get("pages", []), "workflow_runs")
    if m:
        serve(scn.get("runs", {}).get(m.group(1), []), "workflow_runs")
    m = re.match(r"repos/[^/]+/[^/]+/actions/runs/(\d+)/jobs", path)
    if m:
        serve(scn.get("jobs", {}).get(m.group(1)))
    m = re.match(r"repos/[^/]+/[^/]+/check-runs/(\d+)/annotations", path)
    if m:
        serve(scn.get("annotations", {}).get(m.group(1)))
    if re.match(r"repos/[^/]+/[^/]+/issues\?", path):
        serve(scn.get("issues", []))
sys.exit(2)
'''


def run_cli(scn: dict, busy: str = "0", dispatched: str = "0", dry: bool = False):
    tmp = tempfile.mkdtemp()
    try:
        fake = Path(tmp, "fake_gh.py")
        fake.write_text(FAKE_GH_PY, encoding="utf-8")
        scn = dict(scn)
        if isinstance(scn.get("runs"), dict):
            scn["jobs"] = with_green_jobs(scn["runs"], scn.get("jobs"))
        scn_f = Path(tmp, "scenario.json")
        scn_f.write_text(json.dumps(scn), encoding="utf-8")
        log = Path(tmp, "log.jsonl")
        log.write_text("", encoding="utf-8")
        env = dict(os.environ, FAKE_GH_SCENARIO=str(scn_f), FAKE_GH_LOG=str(log),
                   GITHUB_STEP_SUMMARY=str(Path(tmp, "summary.md")), PYTHONIOENCODING="utf-8",
                   PYTHONDONTWRITEBYTECODE="1")
        env.pop("GITHUB_OUTPUT", None)
        cmd = [sys.executable, str(RECOVERY_SCRIPT), "--repo", "o/r", "--reapable", f"{EVIDENCE_WF} {INGEST_WF}",
               "--group-members", " ".join(sorted(writer_group_members())),
               "--lane-busy", busy, "--dispatched", dispatched, "--now", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "--gh-argv", json.dumps([sys.executable, str(fake)])] + (["--dry-run"] if dry else [])
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
        entries = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        summary = Path(tmp, "summary.md").read_text(encoding="utf-8") if Path(tmp, "summary.md").exists() else ""
        return p.returncode, p.stdout + p.stderr, entries, summary
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def writes(entries: list) -> list:
    return [e for e in entries if e["kind"] in ("dispatch", "write")]


def section_cli() -> None:
    print(NEWLINE + "[G] writer_cycle_recovery as a bare script: its dispatch and its one tracking issue")
    healthy = {"runs": {EVIDENCE_WF: [wrun(5, 2)], INGEST_WF: [wrun(15, 1, name="AUXSAYS Patch Ingestion")]},
               "pages": [prun(3, 1)], "issues": []}
    rc, out, entries, summary = run_cli(healthy)
    job_reads = sorted(e["path"] for e in entries if "/jobs" in e.get("path", ""))
    check("G0 a healthy tick writes nothing, reads only each lane's newest run's record, and exits 0",
          rc == 0 and writes(entries) == [] and job_reads == ["repos/o/r/actions/runs/15/jobs?per_page=100",
                                                              "repos/o/r/actions/runs/5/jobs?per_page=100"],
          f"rc={rc} {writes(entries)} {job_reads} {out[-300:]}")
    rc, out, entries, _ = run_cli(dict(healthy, jobs={"5": jobs_of(marker=False, failed=False)}))
    w = writes(entries)
    check("G12 a green run whose cycle record was skipped is re-run once, as its recovery",
          rc == 0 and [e.get("args") for e in w] == [["workflow", "run", EVIDENCE_WF, "--ref", "main", "--repo",
                                                        "o/r", "-f", "recovery_of=5"]], f"rc={rc} {w} {out[-300:]}")
    lost = dict(healthy, runs={EVIDENCE_WF: [wrun(5, 2, "failure")], INGEST_WF: healthy["runs"][INGEST_WF]},
                jobs={"5": jobs_of()})
    rc, out, entries, summary = run_cli(lost)
    w = writes(entries)
    check("G1 a lost cycle and a free lane: exactly one dispatch, on main, carrying recovery_of",
          rc == 0 and [e.get("args") for e in w] == [["workflow", "run", EVIDENCE_WF, "--ref", "main", "--repo",
                                                        "o/r", "-f", "recovery_of=5"]], f"rc={rc} {w} {out[-300:]}")
    summ = [dispatch_summary(e["args"]) for e in w if e["kind"] == "dispatch"]
    check("G1 every input it passes is declared by the workflow it dispatches",
          bool(summ) and all(set(f) <= declared_inputs(wf) for wf, f in summ), str(summ))
    for busy, dispatched, label in (("", "0", "the eviction step's outputs are missing"),
                                    ("1", "0", "the lane is occupied"),
                                    ("0", "1", "the eviction step already added this tick's entrant")):
        rc, out, entries, _ = run_cli(lost, busy=busy, dispatched=dispatched)
        check(f"G2 no dispatch when {label}", rc == 0 and writes(entries) == [], str(writes(entries)))
    held_by = {}
    for state in ("pending", "queued", "in_progress", "waiting", "requested"):
        arrived = dict(lost, runs=dict(lost["runs"], **{"davinci-updates.yml": [
            {"id": 900, "status": state, "conclusion": None, "created_at": at(0.1), "event": "workflow_dispatch",
             "triggering_actor": {"login": "auxchan"}, "display_title": "DaVinci"}]}))
        rc, out, entries, summary = run_cli(arrived)
        held_by[state] = rc == 0 and writes(entries) == [] and "waits" in summary
    check("G11 a writer that entered the lane after the eviction step's check holds the dispatch back, "
          "in every state a run reports before it completes", all(held_by.values()), str(held_by))

    persistent = dict(healthy, runs={EVIDENCE_WF: [recovery_run(6, 1, of="5"), wrun(5, 6, "failure")],
                                     INGEST_WF: healthy["runs"][INGEST_WF]},
                      jobs={"6": jobs_of(), "5": jobs_of()})
    rc, out, entries, _ = run_cli(persistent)
    w = writes(entries)
    created = [e for e in w if e["kind"] == "write" and e["method"] == "POST" and e["path"] == "repos/o/r/issues"]
    body = created[0]["fields"].get("body", "") if created else ""
    check("G3 a recovery that lost too: not re-run; ONE tracking issue opened, titled as the module says",
          rc == 0 and not any(e["kind"] == "dispatch" for e in w) and len(created) == 1
          and created[0]["fields"].get("title") == wcr.ISSUE_TITLE, f"{w}")
    check("G3 the issue names the lane, the run ids and the outcome code",
          EVIDENCE_WF in body and "6" in body and "re-run of run 5" in body and "`failure`" in body
          and WRITEBACK_STEP in body, body[:400])
    problem = decide(persistent["runs"][EVIDENCE_WF], persistent["jobs"]).problem
    same = dict(persistent, issues=[{"number": 12, "title": wcr.ISSUE_TITLE, "user": {"login": BOT},
                                     "body": wcr.issue_body([problem])}])
    rc, out, entries, _ = run_cli(same)
    check("G4 the same problems already listed: no duplicate, no edit", writes(entries) == [], str(writes(entries)))
    stale = dict(same, issues=[dict(same["issues"][0], body="older problems\n")])
    rc, out, entries, _ = run_cli(stale)
    w = writes(entries)
    check("G4 different problems: the one open issue's body is rewritten, nothing else",
          [(e["method"], e["path"]) for e in w] == [("PATCH", "repos/o/r/issues/12")] and "body" in w[0]["fields"], str(w))
    clear = dict(healthy, issues=same["issues"])
    rc, out, entries, _ = run_cli(clear)
    w = writes(entries)
    check("G5 everything healthy again: the issue is commented on and closed",
          [(e["method"], e["path"]) for e in w] == [("POST", "repos/o/r/issues/12/comments"),
                                                     ("PATCH", "repos/o/r/issues/12")]
          and w[-1]["fields"].get("state") == "closed", str(w))
    half = dict(clear, runs={EVIDENCE_WF: [wrun(5, 2)], INGEST_WF: "FAIL"})
    rc, out, entries, _ = run_cli(half)
    check("G6 a lane that could not be read keeps the issue open: closing needs the whole state",
          writes(entries) == [] and "::warning" in out, str(writes(entries)))
    rc, out, entries, _ = run_cli(dict(persistent, issues="FAIL"))
    check("G7 unreadable issues: nothing opened blindly (no duplicate), and it says so",
          writes(entries) == [] and "::warning" in out, str(writes(entries)))
    rc, out, entries, _ = run_cli(dict(lost, runs={EVIDENCE_WF: lost["runs"][EVIDENCE_WF],
                                                   INGEST_WF: persistent["runs"][EVIDENCE_WF]},
                                       jobs={"5": jobs_of(), "6": jobs_of()}), dry=True)
    check("G8 a dry run dispatches nothing and writes no issue", writes(entries) == [] and rc == 0,
          str(writes(entries)))
    human = dict(healthy, issues=[{"number": 3, "title": wcr.ISSUE_TITLE, "user": {"login": "someone"}, "body": "x"}])
    rc, out, entries, _ = run_cli(human)
    check("G9 an issue a person opened with the same title is never edited or closed",
          writes(entries) == [], str(writes(entries)))
    rc, out, entries, _ = run_cli(dict(healthy, pages=[prun(3, 1, "failure"), prun(2, 5)]))
    w = writes(entries)
    check("G10 a failing Pages build on main opens the tracking issue too",
          len(w) == 1 and w[0]["method"] == "POST" and "Pages" in w[0]["fields"].get("body", "")
          and "`failure`" in w[0]["fields"].get("body", ""), str(w))


# --------------------------------------------------------------------------------------------------
# [H] the PowerPoint graph's writeback binding
# --------------------------------------------------------------------------------------------------
def section_powerpoint_binding() -> None:
    print(NEWLINE + "[H] the PowerPoint graph confirms its build and reports its writeback")
    import orchestrate_evidence_run as orch
    seen: list = []
    real = aw.run_writeback
    tmp = Path(tempfile.mkdtemp())
    out_f = tmp / "github_output"
    old = os.environ.get("GITHUB_OUTPUT")
    try:
        aw.run_writeback = lambda c: (seen.append(c), aw.WritebackResult(
            outcome=aw.PUSH_SUCCESS_FIRST_ATTEMPT, pushed=True, deployment_pending=True,
            pages_build_outcome="failed", ok=False))[1]
        os.environ["GITHUB_OUTPUT"] = str(out_f)
        orch.default_writeback(_REPO, orch.POWERPOINT_ALLOW, message="m")()
        silent = out_f.exists()
        orch.default_writeback(_REPO, orch.POWERPOINT_ALLOW, message="m", github_output=True)()
        outs = dict(ln.split("=", 1) for ln in out_f.read_text().splitlines() if "=" in ln) if out_f.exists() else {}
    finally:
        aw.run_writeback = real
        if old is None:
            os.environ.pop("GITHUB_OUTPUT", None)
        else:
            os.environ["GITHUB_OUTPUT"] = old
        shutil.rmtree(tmp, ignore_errors=True)
    c = seen[0] if seen else None
    check("H1 the graph's writeback confirms its Pages build with the lanes' bound",
          c is not None and c.pages_confirm_build is True and (c.pages_confirm_attempts, c.pages_confirm_interval)
          == (orch.PAGES_CONFIRM_ATTEMPTS, orch.PAGES_CONFIRM_INTERVAL) == (40, 30),
          str(c and (c.pages_confirm_build, c.pages_confirm_attempts, c.pages_confirm_interval)))
    check("H2 by default the binding writes no step output (a test never touches the CI job's file)", not silent)
    check("H3 with github_output it writes the outputs the workflow reads",
          outs.get("pushed") == "true" and outs.get("outcome") == aw.PUSH_SUCCESS_FIRST_ATTEMPT
          and outs.get("deployment_pending") == "true" and outs.get("pages_build") == "failed", str(outs))

    captured: dict = {}

    class _Pipeline:
        def __init__(self, *a, **kw) -> None:
            pass

        def run(self, resume_run_id=None):
            from lib.orchestration import DONE, OrchestrationState
            s = OrchestrationState(run_id="t", trigger="t", product_ids=["microsoft-powerpoint"])
            s.terminal = DONE
            return s

    saved = (orch.default_writeback, orch.Pipeline, orch.default_context_fetch)
    ck = Path(tempfile.mkdtemp())
    try:
        orch.default_writeback = lambda *a, **kw: (captured.update(kw), (lambda: {}))[1]
        orch.Pipeline = _Pipeline
        orch.default_context_fetch = lambda: None
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            rc = orch.main(["--write", "--checkpoint-dir", str(ck)])
    finally:
        orch.default_writeback, orch.Pipeline, orch.default_context_fetch = saved
        shutil.rmtree(ck, ignore_errors=True)
    check("H4 the production CLI binds the writeback with github_output on",
          rc == 0 and captured.get("github_output") is True, str(captured))


def main() -> int:
    print("=" * 74)
    print("G91 deployment verification and lost-cycle recovery")
    print("=" * 74)
    section_confirmation()
    section_superseded()
    section_lost_race()
    section_stale_tree()
    section_bare_script()
    section_bare_script_superseded()
    section_wiring()
    section_executed()
    section_decisions()
    section_cli()
    section_powerpoint_binding()
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
