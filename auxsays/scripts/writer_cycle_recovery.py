#!/usr/bin/env python3
"""Re-run, once, a routine writer cycle that ran but never reached main; report what stays lost.

Run by the Writer Queue Reaper (.github/workflows/writer-queue-reaper.yml) after its eviction step,
every two hours. Standard library only, executed as a bare script.

THE GAP (G91)
-------------
Run 44878227542 collected a whole evidence cycle, lost its writeback race to a pull request merged
mid-run (`upstream_advanced`, `rebase_conflict`), pushed nothing and failed. The reaper's eviction
repair keys on a run cancelled with ZERO jobs, so it left that run alone, and the next attempt was
the next scheduled cycle. The same silence covered every other way a routine run can end without
its cycle on main: a refused writeback, a failed QA after collection, a job that hit its time limit.

WHAT COUNTS AS "REACHED MAIN"
-----------------------------
Read from the run itself, never inferred from the conclusion alone. Each routine writer run
executes a step named exactly CYCLE_MARKER_STEP only when every writeback in it pushed or had
nothing to push (obs-evidence-collection.yml: its chain-ingest job, over both writer jobs;
patch-ingest.yml: its ingest job); when it did not, the step is listed as `skipped`. So:
  * marker step succeeded, any conclusion         -> reached (a run that failed AFTER main had the
                                                      cycle, e.g. a failed Pages build, is never
                                                      re-run, so a deployment problem can never make
                                                      a cycle run twice);
  * marker step listed but not succeeded          -> LOST, even when the run concluded `success`:
                                                      the PowerPoint graph's step takes `tee`'s exit
                                                      status, and its writeback can lose a race or
                                                      the graph can stop before writing back while
                                                      the run stays green;
  * no marker step at all, conclusion `success`   -> reached: a run from before the record existed
                                                      (its every step, the writeback included,
                                                      succeeded);
  * no marker step, any other conclusion          -> LOST;
  * `cancelled` with zero jobs                    -> an eviction: the reaper's first step owns it;
  * `cancelled` with jobs                         -> an operator's cancel is LEFT ALONE, exactly as
                                                      the eviction step does; a job that hit its
                                                      `timeout-minutes` also ends `cancelled`, and
                                                      only its annotation ("The job has exceeded the
                                                      maximum execution time ...") tells the two
                                                      apart, so a timed-out run is judged by its
                                                      marker like any other.
Only routine runs are considered: a cron run, or one this repository's own automation dispatched
(github-actions[bot]). An operator's dispatch is the operator's to repeat.

THE DECISION, PER LANE
----------------------
Walk that lane's completed routine runs newest first, skipping cancellations. The newest is HEAD.
Each run's jobs are read, a green one's too, because the record decides (above).
  * HEAD reached main                      -> nothing to do.
  * HEAD is lost and is itself a recovery  -> never re-run (the loop guard). Its title carries
    ("... (recovery of run N)", from the workflow's run-name) so the record survives an eviction.
  * HEAD is lost, and walking further back finds a recovery run that ALSO lost before any run that
    reached main -> the lane is persistently broken: re-runs pause until a run reaches main again.
    No retry storm, however long a source stays broken.
  * HEAD is lost and older than DISPATCH_WINDOW -> reported, not re-run.
  * otherwise -> dispatch the workflow once on main with `recovery_of=<HEAD id>`.
A dispatch happens only when the reaper's first step found the whole writer group free (no run
pending, queued or in progress in ANY member) and dispatched nothing itself, AND the same
group-wide check, repeated immediately before the dispatch, still finds it free: one entrant per
tick, into a lane with no queued writer to cancel. (The re-check and the dispatch are two API calls;
a writer that arrives in the moment between them is the one exposure left, and a run it evicts is
the eviction step's to re-dispatch.) The writer group's own concurrency keeps two writers from ever
running at once. The re-run
checks out main when it starts, and its writeback fetches main again before every push, rebases
its single commit, re-validates the rebased tree and refuses any path both sides touched -- so a
recovered run can never push a stale tree. Nothing here merges evidence.

WHAT STAYS VISIBLE
------------------
A lost recovery, a paused lane, a lost cycle too old to re-run, or a latest Pages build on main
that genuinely failed is a PROBLEM. Problems go into ONE tracking issue (ISSUE_TITLE), opened by
this step, its body rewritten when the problems change, and closed when every lane's latest routine
run reached main and the latest Pages build succeeded. The issue carries run ids, workflow file
names, conclusions and failed step names only: no secrets, no findings, no evidence text. The
reaper's own concurrency group serialises ticks, so two ticks can never open two issues.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

# The step every routine writer run executes only when its cycle reached main. The writer workflows
# name a step with exactly this text; test_deploy_verification_and_lost_race.py asserts both.
CYCLE_MARKER_STEP = "Cycle reached main"
# What the writer workflows' `run-name` appends when `recovery_of` is set.
RECOVERY_TITLE_RE = re.compile(r"\(recovery of run (\d+)\)\s*$")
BOT_LOGIN = "github-actions[bot]"
# GitHub's own annotation on a job cancelled by its `timeout-minutes` (observed verbatim on runs
# 33810979002 and 33753609648: "The job has exceeded the maximum execution time of 1h30m0s").
TIMEOUT_ANNOTATION = "exceeded the maximum execution time"
ISSUE_TITLE = "Automated writer recovery needs attention"
PAGES_WORKFLOW = "pages.yml"
# A Pages run that ended in one of these failed. `cancelled` is a superseded run in the one-deep
# `pages` concurrency group, not a failure.
PAGES_FAILURES = frozenset({"failure", "timed_out", "startup_failure"})
# Every status GitHub reports for a run that has not completed. The same list the eviction step's
# group-wide occupancy check uses.
ACTIVE_STATES = frozenset({"pending", "queued", "in_progress", "waiting", "requested"})
# A lost run newer than this is re-run; the eviction step uses the same 14-hour window.
DISPATCH_WINDOW = timedelta(hours=14)
# How far back the walk looks for a recovery that already lost (the pause rule).
WALK_WINDOW = timedelta(hours=72)
MAX_FAILED_STEPS = 3


def parse_time(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def is_routine(run: dict) -> bool:
    actor = (run.get("triggering_actor") or {}).get("login")
    return run.get("event") == "schedule" or actor == BOT_LOGIN


def recovery_of(run: dict) -> str:
    """The id of the run this run re-ran, from its display title; "" when it is not a recovery."""
    m = RECOVERY_TITLE_RE.search(str(run.get("display_title") or ""))
    return m.group(1) if m else ""


def marker_reached(jobs: dict) -> bool:
    return any(step.get("name") == CYCLE_MARKER_STEP and step.get("conclusion") == "success"
               for job in jobs.get("jobs") or [] for step in job.get("steps") or [])


def marker_listed(jobs: dict) -> bool:
    """True when the run carries the cycle record at all, run or skipped. Runs from before the
    record existed do not, and only for them is a `success` conclusion taken as the record."""
    return any(step.get("name") == CYCLE_MARKER_STEP
               for job in jobs.get("jobs") or [] for step in job.get("steps") or [])


def failed_steps(jobs: dict) -> list[str]:
    out = []
    for job in jobs.get("jobs") or []:
        for step in job.get("steps") or []:
            if step.get("conclusion") in ("failure", "cancelled", "timed_out"):
                out.append(f"{job.get('name')} / {step.get('name')} ({step.get('conclusion')})")
    return out[:MAX_FAILED_STEPS]


@dataclass
class Judged:
    run: dict
    state: str                  # reached | lost | skip
    detail: str = ""            # outcome codes for the issue / summary


@dataclass
class LaneDecision:
    workflow: str
    dispatch_recovery_of: str = ""   # dispatch the workflow once with this recovery_of
    problem: str = ""                # a line for the tracking issue
    note: str = ""                   # a line for the step summary
    decided: bool = True             # False when the API could not be read


def judge(run: dict, jobs_for: Callable[[str], dict | None],
          annotations_for: Callable[[str], list | None]) -> Judged | None:
    """One completed routine run. None when the API could not be read for it."""
    conclusion = str(run.get("conclusion") or "")
    jobs = jobs_for(str(run.get("id")))
    if jobs is None:
        return None
    if conclusion == "success":
        if marker_reached(jobs) or not marker_listed(jobs):
            return Judged(run, "reached")
        # Green, but a writer job's writeback did not reach main (see the module docstring).
        return Judged(run, "lost", f"`success`, but `{CYCLE_MARKER_STEP}` was skipped: a writer job's "
                                   "writeback did not reach main")
    if conclusion == "cancelled":
        if int(jobs.get("total_count") or 0) == 0:
            return Judged(run, "skip", "evicted")          # the eviction step's case
        timed_out = False
        for job in jobs.get("jobs") or []:
            if job.get("conclusion") != "cancelled":
                continue
            notes = annotations_for(str(job.get("id")))
            if notes is None:
                return None
            if any(TIMEOUT_ANNOTATION in str(n.get("message") or "") for n in notes):
                timed_out = True
        if not timed_out:
            return Judged(run, "skip", "cancelled after it started (left alone)")
        conclusion = "cancelled: job time limit"
    steps = failed_steps(jobs)
    detail = f"`{conclusion}`" + (f"; failed steps: {', '.join(f'`{s}`' for s in steps)}" if steps else "")
    return Judged(run, "reached" if marker_reached(jobs) else "lost", detail)


def _link(run: dict) -> str:
    url = str(run.get("html_url") or "")
    return f"run [{run.get('id')}]({url})" if url else f"run {run.get('id')}"


def decide_lane(workflow: str, runs: list[dict], jobs_for: Callable[[str], dict | None],
                annotations_for: Callable[[str], list | None], now: datetime) -> LaneDecision:
    walk_from = now - WALK_WINDOW
    candidates = [r for r in runs if r.get("status") == "completed" and is_routine(r)
                  and (parse_time(r.get("created_at")) or now) >= walk_from]
    candidates.sort(key=lambda r: (str(r.get("created_at") or ""), int(r.get("id") or 0)), reverse=True)
    head: Judged | None = None
    # Runs some recovery already attempted that an operator then cancelled after it started: that
    # was the one re-run, and an operator's cancel is never resurrected.
    cancelled_recoveries: set[str] = set()
    for run in candidates:
        judged = judge(run, jobs_for, annotations_for)
        if judged is None:
            return LaneDecision(workflow, decided=False,
                                note=f"could not read run {run.get('id')}; nothing decided this tick")
        if judged.state == "skip":
            if judged.detail != "evicted" and recovery_of(run):
                cancelled_recoveries.add(recovery_of(run))
            continue
        if head is None:
            if judged.state == "reached":
                return LaneDecision(workflow, note=f"latest routine run {run.get('id')} reached main")
            head = judged
            of = recovery_of(run)
            if of:
                return LaneDecision(workflow, problem=(
                    f"`{workflow}`: recovery {_link(run)} (re-run of run {of}) ended {judged.detail} and its "
                    "cycle did not reach main. It is not re-run again: one automatic re-run per lost cycle."),
                    note=f"recovery run {run.get('id')} of run {of} lost its cycle too; not re-run (loop guard)")
            continue
        if judged.state == "reached":
            break
        of = recovery_of(run)
        if of:
            return LaneDecision(workflow, problem=(
                f"`{workflow}`: {_link(head.run)} ended {head.detail} and its cycle did not reach main. "
                f"Automatic re-runs are paused for this lane: recovery run {run.get('id')} (of run {of}) "
                "also lost its cycle, and no routine run has reached main since."),
                note=f"run {head.run.get('id')} lost its cycle; re-runs paused (recovery run {run.get('id')} lost too)")
    if head is None:
        return LaneDecision(workflow, note="no completed routine run in the window")
    if str(head.run.get("id")) in cancelled_recoveries:
        return LaneDecision(workflow, note=(
            f"run {head.run.get('id')} lost its cycle; its recovery run was cancelled after it started "
            "(an operator's cancel is left alone)"))
    created = parse_time(head.run.get("created_at")) or now
    if created < now - DISPATCH_WINDOW:
        return LaneDecision(workflow, problem=(
            f"`{workflow}`: {_link(head.run)} ended {head.detail} and its cycle did not reach main more "
            f"than {int(DISPATCH_WINDOW.total_seconds() // 3600)} hours ago; it was not re-run automatically."),
            note=f"run {head.run.get('id')} lost its cycle outside the re-run window")
    return LaneDecision(workflow, dispatch_recovery_of=str(head.run.get("id")),
                        note=f"run {head.run.get('id')} ended {head.detail} without its cycle reaching main")


def pages_problem(runs: list[dict] | None, branch: str = "main") -> tuple[bool, str]:
    """(readable, problem line). The latest completed Pages run on `branch` that was not cancelled
    or skipped decides: a genuine failure is a problem; anything else is healthy."""
    if runs is None:
        return False, ""
    done = [r for r in runs if r.get("status") == "completed" and r.get("head_branch") == branch
            and r.get("conclusion") not in ("cancelled", "skipped")]
    if not done:
        return True, ""
    done.sort(key=lambda r: (str(r.get("created_at") or ""), int(r.get("id") or 0)), reverse=True)
    latest = done[0]
    if latest.get("conclusion") in PAGES_FAILURES:
        return True, (f"Pages: the latest completed build on `{branch}`, {_link(latest)} for commit "
                      f"`{str(latest.get('head_sha') or '')[:7]}`, ended `{latest.get('conclusion')}`; "
                      "the site is not showing the newest revision.")
    return True, ""


def issue_body(problems: list[str]) -> str:
    lines = [
        "This issue is kept by the Writer Queue Reaper (`.github/workflows/writer-queue-reaper.yml`). "
        "It carries run ids, workflow names and outcome codes only.",
        "",
        "Current problems:",
        "",
    ]
    lines += [f"- {p}" for p in problems]
    lines += [
        "",
        "The reaper closes this issue when every routine writer lane's latest run reached main and "
        "the latest Pages build on `main` succeeded.",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------------------
# I/O: the GitHub CLI
# --------------------------------------------------------------------------------------------------
class Gh:
    def __init__(self, argv: list[str], repo: str) -> None:
        self.argv = argv
        self.repo = repo

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(self.argv + args, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")

    def get(self, path: str):
        proc = self._run(["api", path])
        if proc.returncode != 0:
            return None
        try:
            return json.loads(proc.stdout or "null")
        except json.JSONDecodeError:
            return None

    def call(self, args: list[str]) -> bool:
        proc = self._run(args)
        if proc.returncode != 0:
            sys.stderr.write(f"gh {' '.join(args[:4])} failed rc={proc.returncode}: {proc.stderr.strip()[:300]}\n")
        return proc.returncode == 0

    # reads
    def runs(self, workflow: str) -> list[dict] | None:
        data = self.get(f"repos/{self.repo}/actions/workflows/{workflow}/runs?status=completed&per_page=50")
        return data.get("workflow_runs") if isinstance(data, dict) and isinstance(data.get("workflow_runs"), list) else None

    def jobs(self, run_id: str) -> dict | None:
        data = self.get(f"repos/{self.repo}/actions/runs/{run_id}/jobs?per_page=100")
        return data if isinstance(data, dict) and isinstance(data.get("jobs"), list) else None

    def annotations(self, job_id: str) -> list | None:
        data = self.get(f"repos/{self.repo}/check-runs/{job_id}/annotations?per_page=100")
        return data if isinstance(data, list) else None

    def active(self, workflow: str) -> int | None:
        """Runs of `workflow` not yet completed, in every state GitHub reports before completion.
        `pending` above all: a run held back by a concurrency group reports `pending`, not `queued`
        (writer-queue-depth-one). None when the list cannot be read."""
        data = self.get(f"repos/{self.repo}/actions/workflows/{workflow}/runs?per_page=20")
        if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
            return None
        return sum(1 for r in data["workflow_runs"] if r.get("status") in ACTIVE_STATES)

    def pages_runs(self) -> list[dict] | None:
        data = self.get(f"repos/{self.repo}/actions/workflows/{PAGES_WORKFLOW}/runs?branch=main&status=completed&per_page=30")
        return data.get("workflow_runs") if isinstance(data, dict) and isinstance(data.get("workflow_runs"), list) else None

    def open_issue(self) -> tuple[bool, dict | None]:
        data = self.get(f"repos/{self.repo}/issues?state=open&per_page=100")
        if not isinstance(data, list):
            return False, None
        mine = [i for i in data if isinstance(i, dict) and "pull_request" not in i
                and i.get("title") == ISSUE_TITLE and (i.get("user") or {}).get("login") == BOT_LOGIN]
        mine.sort(key=lambda i: int(i.get("number") or 0))
        return True, (mine[0] if mine else None)

    # writes
    def dispatch(self, workflow: str, of: str) -> bool:
        return self.call(["workflow", "run", workflow, "--ref", "main", "--repo", self.repo,
                          "-f", f"recovery_of={of}"])

    def create_issue(self, body: str) -> bool:
        return self.call(["api", "-X", "POST", f"repos/{self.repo}/issues",
                          "-f", f"title={ISSUE_TITLE}", "-f", f"body={body}"])

    def update_issue(self, number: int, body: str) -> bool:
        return self.call(["api", "-X", "PATCH", f"repos/{self.repo}/issues/{number}", "-f", f"body={body}"])

    def close_issue(self, number: int) -> bool:
        # The comment says why; the close is what matters, so only the close decides the result.
        self.call(["api", "-X", "POST", f"repos/{self.repo}/issues/{number}/comments", "-f",
                   "body=Resolved: every routine writer lane's latest run reached main and the "
                   "latest Pages build on main succeeded."])
        return self.call(["api", "-X", "PATCH", f"repos/{self.repo}/issues/{number}",
                          "-f", "state=closed", "-f", "state_reason=completed"])


def lane_free(busy: str, dispatched: str) -> bool:
    """True only when the reaper's first step positively reported a free lane and no dispatch of
    its own. Anything missing or unreadable counts as occupied."""
    return busy.strip() == "0" and dispatched.strip() == "0"


@dataclass
class Plan:
    decisions: list[LaneDecision] = field(default_factory=list)
    dispatch: tuple[str, str] | None = None      # (workflow, recovery_of)
    held: tuple[str, str] | None = None          # a dispatch the pre-dispatch re-check held back
    problems: list[str] = field(default_factory=list)
    all_decided: bool = True


def occupied_now(gh: Gh, members: list[str]) -> bool:
    """The group-wide occupancy check again, immediately before a dispatch. The eviction step
    checked it first, but checkout and setup ran since; a writer that arrived meanwhile must not get
    a recovery queued behind it. Unreadable, or no members named, counts as occupied."""
    if not members:
        return True
    for wf in members:
        n = gh.active(wf)
        if n is None or n > 0:
            return True
    return False


def plan_tick(gh: Gh, reapable: list[str], busy: str, dispatched: str, now: datetime,
              members: list[str] | None = None) -> Plan:
    plan = Plan()
    for wf in reapable:
        runs = gh.runs(wf)
        if runs is None:
            decision = LaneDecision(wf, decided=False, note="could not read its runs; nothing decided this tick")
        else:
            decision = decide_lane(wf, runs, gh.jobs, gh.annotations, now)
        plan.decisions.append(decision)
        plan.all_decided = plan.all_decided and decision.decided
        if decision.problem:
            plan.problems.append(decision.problem)
        if decision.dispatch_recovery_of and plan.dispatch is None and lane_free(busy, dispatched):
            plan.dispatch = (wf, decision.dispatch_recovery_of)
    if plan.dispatch and occupied_now(gh, list(members or [])):
        plan.held = plan.dispatch
        plan.dispatch = None
    readable, pages = pages_problem(gh.pages_runs())
    plan.all_decided = plan.all_decided and readable
    if pages:
        plan.problems.append(pages)
    return plan


def keep_issue(gh: Gh, plan: Plan, dry_run: bool) -> str:
    readable, issue = gh.open_issue()
    if not readable:
        print("::warning title=Reaper::could not read the open issues; the tracking issue is left as it is")
        return "issues unreadable; tracking issue left as it is"
    if plan.problems:
        body = issue_body(plan.problems)
        if issue is None:
            if not dry_run and gh.create_issue(body):
                return "opened the tracking issue"
            return "would open the tracking issue" if dry_run else "could not open the tracking issue"
        if str(issue.get("body") or "").strip() == body.strip():
            return f"tracking issue #{issue.get('number')} already lists these problems"
        if not dry_run and gh.update_issue(int(issue["number"]), body):
            return f"updated tracking issue #{issue.get('number')}"
        return f"would update tracking issue #{issue.get('number')}" if dry_run else "could not update the tracking issue"
    if issue is None:
        return "no problems; no tracking issue open"
    if not plan.all_decided:
        return f"tracking issue #{issue.get('number')} left open: part of the state could not be read"
    if not dry_run and gh.close_issue(int(issue["number"])):
        return f"closed tracking issue #{issue.get('number')}"
    return f"would close tracking issue #{issue.get('number')}" if dry_run else "could not close the tracking issue"


def build_parser() -> argparse.ArgumentParser:
    """Separate from main() so a test parses the reaper step's real argument list with this parser."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("REPO", ""))
    parser.add_argument("--reapable", default=os.environ.get("REAPABLE", ""))
    parser.add_argument("--group-members", default=os.environ.get("GROUP_MEMBERS", ""),
                        help="every workflow in the writer concurrency group (re-checked before a dispatch)")
    parser.add_argument("--lane-busy", default="", help="the eviction step's `busy` output")
    parser.add_argument("--dispatched", default="", help="the eviction step's `dispatched` output")
    parser.add_argument("--dry-run", action="store_true", help="decide and report; dispatch nothing, write no issue")
    parser.add_argument("--gh-argv", default='["gh"]', help=argparse.SUPPRESS)
    parser.add_argument("--now", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.repo or not args.reapable.split():
        parser.error("--repo and --reapable (or REPO and REAPABLE) are required")
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    gh = Gh(json.loads(args.gh_argv), args.repo)

    plan = plan_tick(gh, args.reapable.split(), args.lane_busy, args.dispatched, now,
                     args.group_members.split())
    lines = []
    for d in plan.decisions:
        lines.append(f"- `{d.workflow}`: {d.note}")
        if not d.decided:
            print(f"::warning title=Reaper::{d.workflow}: {d.note}")
    dispatched = ""
    if plan.dispatch:
        wf, of = plan.dispatch
        if args.dry_run:
            dispatched = f"would re-dispatch `{wf}` once (recovery of run {of})"
        elif gh.dispatch(wf, of):
            dispatched = f"re-dispatched `{wf}` once (recovery of run {of})"
        else:
            dispatched = f"re-dispatch of `{wf}` failed"
            print(f"::warning title=Reaper::re-dispatch of {wf} (recovery of run {of}) failed")
    elif plan.held:
        dispatched = (f"a lost cycle waits: a writer entered the lane after the eviction step's check "
                      f"(`{plan.held[0]}`, run {plan.held[1]}); the next tick re-decides")
    elif any(d.dispatch_recovery_of for d in plan.decisions):
        dispatched = "a lost cycle waits: the lane is occupied or this tick already added an entrant"
    for p in plan.problems:
        print(f"::warning title=Writer cycle or deployment needs attention::{p}")
    issue = keep_issue(gh, plan, args.dry_run)
    print("REAPER_PLAN: " + json.dumps({
        "dispatch": list(plan.dispatch) if plan.dispatch else None,
        "problems": plan.problems, "issue": issue,
        "lanes": {d.workflow: {"decided": d.decided, "recovery_of": d.dispatch_recovery_of,
                               "problem": bool(d.problem)} for d in plan.decisions},
    }), flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as h:
                h.write("### Cycles that did not reach main\n\n" + "\n".join(lines) + "\n")
                if dispatched:
                    h.write(f"- {dispatched}\n")
                h.write(f"- tracking issue: {issue}\n")
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
