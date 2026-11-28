#!/usr/bin/env python3
"""Recover, once, a scheduled cycle that GitHub never created; stand down a cycle that is already done.

Run by .github/workflows/missed-run-recovery.yml (`check`) and by the first job of
obs-evidence-collection.yml (`gate`). Standard library only, executed as a bare script.

THE GAP
-------
GitHub delivers each scheduled workflow here about twice a day, hours late, whatever its cron says
(11-12..11-26: the collection cron '17 */6' ran 32 times in 15 days, 0.4-5.5 h after its slot; the
import lane's 96 daily slots produced one run on 11-26). A run that was never created leaves nothing
behind: no cancelled run for the writer-queue reaper to re-dispatch, no lost run for G91 to re-run.
It can only be noticed from elapsed time against the last successful work.

THE ONE RULE
------------
A lane is DUE when no attempt of its routine work has started in the current designed window (its
cron period, anchored at its cron minute) and a grace has passed since the window opened. Recovery
dispatches ONE run, and a routine run that finds its window already done stands down. At most one
cycle per designed window is never more than the cron itself designs, and a missed window is
recovered once, never slot by slot. A dispatch is never taken as the work having happened.

LANE: import (assessment-import.yml, every 15 minutes by design)
  Upstream work = the committer date of the output repository's main. Successful work = the
  `run_started_at` of the newest successful import run (it fetched that main when it started).
  DUE when the output commit is newer than that start, at least IMPORT_GRACE old, no import run is
  active, none was created in the last IMPORT_CADENCE (the designed cadence), and fewer than
  IMPORT_FAILURE_CAP import runs failed since the output commit (otherwise HELD and reported; a new
  output commit or a success clears it). An unchanged output -- a commit older than the last success
  -- dispatches nothing, and the import itself commits nothing for an unchanged file.

LANE: collection (obs-evidence-collection.yml, '17 */6', a member of the writer group)
  DUE when no routine run (a cron run or one this repository's automation dispatched) was CREATED in
  the current window [hh:17, +6 h) in any state -- an evicted or lost run is the reaper's and G91's,
  which repair runs that exist -- at least COLLECTION_GRACE into the window, and the WHOLE writer
  group is free (any member pending, queued, in progress, waiting or requested = busy: the reaper's
  own free-lane rule, so this never adds a third entrant to the one-deep queue).
  `gate` is the in-run half: a cron run, a bot dispatch without `recovery_of`, or the reaper's
  re-dispatch of an EVICTED (zero-job) run stands down when an earlier routine run created in its own
  window COLLECTED, whatever its outcome (its `collect` job ran). It applies no rolling-24-h cap (that
  would stand down a window's first cycle when its cron is earlier than yesterday's); the check's own
  dispatches carry COLLECTION_DAILY_CAP. A lost cycle is repaired by G91's one re-run, which
  is never gated (nor is any operator dispatch); G91 judges a stood-down run as skipped, so the lost
  run before it stays the one it re-runs. Together: at most one routine collection per window and 4
  per aligned day (one per window; recovery dispatches also capped at 4 per rolling 24 h), plus G91's one re-run per lost cycle, exactly as before this change. Any doubt (an
  unreadable API) proceeds: the guard can only remove a duplicate, never a cycle.

Telemetry: one fixed line per lane, `FRESHNESS: lane=<lane> state=<state> ...`, in the log and the
job summary; `::warning` for a held or unreadable lane. Nothing here writes the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import writer_cycle_recovery as wcr

IMPORT_WORKFLOW = "assessment-import.yml"
# The public output-only repository the import lane reads (named in assessment-import.yml too).
OUTPUT_REPO = "auxchan/auxsays-assessment-output"
IMPORT_CADENCE = timedelta(minutes=15)
IMPORT_GRACE = timedelta(minutes=10)
IMPORT_FAILURE_CAP = 2
COLLECTION_WORKFLOW = "obs-evidence-collection.yml"
COLLECTION_PERIOD = timedelta(hours=6)
COLLECTION_OFFSET = timedelta(minutes=17)
COLLECTION_GRACE = timedelta(minutes=30)
# The cron's own daily cadence (24 h / 6 h): recovery never takes a rolling day above it.
COLLECTION_DAILY_CAP = 4
FAILED = frozenset({"failure", "timed_out", "startup_failure"})
# After a dispatch, wait until the new run is listed, so the next (serialised) check sees it active.
LISTED_WAIT_SECONDS = 90
LISTED_POLL_SECONDS = 5


def window_start(now: datetime, period: timedelta, offset: timedelta) -> datetime:
    """Start of the designed window containing `now`: windows begin at `offset` past midnight UTC
    and every `period` after it."""
    day = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    k = (now - day - offset) // period
    return day + offset + k * period


@dataclass
class Decision:
    lane: str
    state: str          # fresh | due | busy | held | cooldown | grace | unreadable (+ dispatched/dispatch_failed)
    reason: str
    dispatch: bool = False

    def line(self) -> str:
        return f"FRESHNESS: lane={self.lane} state={self.state} reason={self.reason}"


def _t(run: dict, key: str) -> datetime | None:
    return wcr.parse_time(run.get(key)) if run.get(key) else None


def decide_import(now: datetime, output_commit: datetime | None, runs: list[dict] | None) -> Decision:
    if output_commit is None or runs is None:
        return Decision("import", "unreadable", "output commit or import runs could not be read")
    if any(r.get("status") in wcr.ACTIVE_STATES for r in runs):
        return Decision("import", "busy", "an import run is already active")
    starts = [_t(r, "run_started_at") or _t(r, "created_at") for r in runs if r.get("conclusion") == "success"]
    starts = [s for s in starts if s is not None]
    last_success = max(starts) if starts else None
    if last_success is not None and output_commit <= last_success:
        return Decision("import", "fresh",
                        f"output {output_commit:%Y-%m-%dT%H:%M:%SZ} picked up by the run started {last_success:%Y-%m-%dT%H:%M:%SZ}")
    if now - output_commit < IMPORT_GRACE:
        return Decision("import", "grace", f"output committed {output_commit:%Y-%m-%dT%H:%M:%SZ}, inside the grace")
    # `cancelled` counts too: a job that hits its time limit ends the run `cancelled`, not `timed_out`
    # (writer_cycle_recovery.TIMEOUT_ANNOTATION), and a hanging import must not re-dispatch itself forever.
    failed = [r for r in runs if (r.get("conclusion") in FAILED or r.get("conclusion") == "cancelled")
              and (_t(r, "run_started_at") or _t(r, "created_at") or now) >= output_commit]
    if len(failed) >= IMPORT_FAILURE_CAP:
        return Decision("import", "held",
                        f"{len(failed)} import runs failed since the output commit; no further dispatch until a new output or a success")
    recent = [r for r in runs if (_t(r, "created_at") or datetime.min.replace(tzinfo=timezone.utc)) > now - IMPORT_CADENCE]
    if recent:
        return Decision("import", "cooldown", "an import run was created within the designed 15-minute cadence")
    since = f"since {last_success:%Y-%m-%dT%H:%M:%SZ}" if last_success else "with no successful run in view"
    return Decision("import", "due", f"output {output_commit:%Y-%m-%dT%H:%M:%SZ} not imported {since}", True)


def did_work(run: dict, jobs: dict | None) -> bool:
    """Whether a routine collection run collected (or may still): active runs and unreadable ones count,
    so doubt only ever withholds a recovery. A stood-down run (collect skipped) and an evicted run (no
    jobs) did not collect."""
    if run.get("status") != "completed" or jobs is None:
        return True
    js = jobs.get("jobs") or []
    if not js:
        return False
    collect = [j for j in js if j.get("name") == "collect"]
    if not collect:
        return run.get("conclusion") != "cancelled"     # a run from before the gate job existed
    return any(j.get("conclusion") != "skipped" for j in collect)


def worked_in_day(now: datetime, runs: list[dict], jobs_of) -> int:
    day_ago = now - timedelta(hours=24)
    n = 0
    for r in runs:
        created = _t(r, "created_at")
        if created is None or created <= day_ago or not wcr.is_routine(r):
            continue
        jobs = jobs_of(str(r.get("id"))) if r.get("status") == "completed" else None
        n += 1 if did_work(r, jobs) else 0
    return n


def decide_collection(now: datetime, runs: list[dict] | None, busy: int | None, worked_24h: int | None = 0) -> Decision:
    ws = window_start(now, COLLECTION_PERIOD, COLLECTION_OFFSET)
    if now - ws < COLLECTION_GRACE:
        return Decision("collection", "grace", f"window opened {ws:%Y-%m-%dT%H:%M:%SZ}, inside the grace")
    if runs is None:
        return Decision("collection", "unreadable", "collection runs could not be read")
    present = [r for r in runs if wcr.is_routine(r) and (_t(r, "created_at") or ws - timedelta(seconds=1)) >= ws]
    if present:
        r = present[0]
        return Decision("collection", "fresh",
                        f"window {ws:%Y-%m-%dT%H:%M:%SZ} has run {r.get('id')} ({r.get('status')}/{r.get('conclusion')})")
    if worked_24h is None:
        return Decision("collection", "unreadable", "the last 24 hours of collection runs could not be read")
    if worked_24h >= COLLECTION_DAILY_CAP:
        return Decision("collection", "capped",
                        f"{worked_24h} routine cycles collected in the last 24 h = the designed {COLLECTION_DAILY_CAP}")
    if busy is None:
        return Decision("collection", "unreadable", "the writer group's occupancy could not be read")
    if busy > 0:
        return Decision("collection", "busy", f"the writer group is occupied ({busy}); re-evaluated at the next check")
    return Decision("collection", "due", f"no routine run created in window {ws:%Y-%m-%dT%H:%M:%SZ}", True)


def gate_collection(event: str, actor: str, own_id: str, own_created: datetime, recovery_of: str,
                    runs: list[dict] | None, jobs_of) -> tuple[bool, str]:
    """(proceed, reason). `jobs_of(run_id)` returns the jobs document or None."""
    if event != "schedule" and actor != wcr.BOT_LOGIN:
        return True, "an operator dispatch is never gated"
    if recovery_of:
        jobs = jobs_of(recovery_of)
        if jobs is None:
            return True, f"the jobs of run {recovery_of} could not be read; proceeding"
        if (jobs.get("total_count") or len(jobs.get("jobs") or [])) != 0:
            return True, f"a re-run of run {recovery_of}, which started and lost its cycle, is never gated"
    if runs is None:
        return True, "collection runs could not be read; proceeding"
    ws = window_start(own_created, COLLECTION_PERIOD, COLLECTION_OFFSET)
    # No rolling-24-h cap here (review A2): windows do not line up with a rolling day, so a cap would stand
    # down the FIRST cycle of a window whose cron came a few minutes earlier than yesterday's, and nothing
    # would recover it. One routine collection per window already bounds the day to 4 aligned windows.
    for r in runs:
        created = _t(r, "created_at")
        if str(r.get("id")) == str(own_id) or created is None or not (ws <= created < own_created):
            continue
        if not wcr.is_routine(r) or r.get("status") != "completed":
            continue
        jobs = jobs_of(str(r.get("id")))
        if jobs is None or not did_work(r, jobs):      # unreadable: ignored (the guard fails open)
            continue
        # Whatever its outcome: a lost cycle is G91's one re-run (never gated), not a second routine
        # collection in the same window.
        return False, (f"run {r.get('id')} already collected in window {ws:%Y-%m-%dT%H:%M:%SZ} "
                       f"({r.get('conclusion')})")
    return True, f"no earlier routine run collected in window {ws:%Y-%m-%dT%H:%M:%SZ}"


# --------------------------------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------------------------------
class Api(wcr.Gh):
    def all_runs(self, workflow: str) -> list[dict] | None:
        data = self.get(f"repos/{self.repo}/actions/workflows/{workflow}/runs?per_page=50")
        return data.get("workflow_runs") if isinstance(data, dict) and isinstance(data.get("workflow_runs"), list) else None

    def run(self, run_id: str) -> dict | None:
        data = self.get(f"repos/{self.repo}/actions/runs/{run_id}")
        return data if isinstance(data, dict) else None

    def output_commit(self) -> datetime | None:
        data = self.get(f"repos/{OUTPUT_REPO}/commits/main")
        try:
            return wcr.parse_time(data["commit"]["committer"]["date"])
        except (TypeError, KeyError):
            return None

    def dispatch_routine(self, workflow: str) -> bool:
        # No inputs: exactly what a cron run of that workflow receives.
        return self.call(["workflow", "run", workflow, "--ref", "main", "--repo", self.repo])

    def wait_listed(self, workflow: str, known: set[str], sleep=time.sleep) -> bool:
        deadline = time.monotonic() + LISTED_WAIT_SECONDS
        while True:
            runs = self.all_runs(workflow) or []
            if any(str(r.get("id")) not in known for r in runs):
                return True
            if time.monotonic() >= deadline:
                return False
            sleep(LISTED_POLL_SECONDS)


def busy_count(api: Api, members: list[str]) -> int | None:
    total = 0
    for wf in members:
        n = api.active(wf)
        if n is None:
            return None
        total += n
    return total


def run_check(api: Api, lanes: list[str], members: list[str], now: datetime, sleep=time.sleep) -> list[Decision]:
    out = []
    for lane in lanes:
        if lane == "import":
            runs = api.all_runs(IMPORT_WORKFLOW)
            d, wf = decide_import(now, api.output_commit(), runs), IMPORT_WORKFLOW
        elif lane == "collection":
            runs = api.all_runs(COLLECTION_WORKFLOW)
            worked = worked_in_day(now, runs, api.jobs) if runs is not None else None
            d, wf = decide_collection(now, runs, busy_count(api, members), worked), COLLECTION_WORKFLOW
        else:
            out.append(Decision(lane, "unreadable", "unknown lane"))
            continue
        if d.dispatch:
            known = {str(r.get("id")) for r in runs or []}
            if api.dispatch_routine(wf):
                listed = api.wait_listed(wf, known, sleep)
                d = Decision(lane, "dispatched", d.reason + ("" if listed else "; the new run was not listed within 90 s"), True)
            else:
                d = Decision(lane, "dispatch_failed", d.reason, True)
        out.append(d)
    return out


def _summary(lines: list[str], title: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as h:
            h.write(f"### {title}\n\n" + "".join(f"- `{x}`\n" for x in lines))
    except OSError:
        pass


def _output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as h:
            h.write(f"{key}={value}\n")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["check", "gate"])
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--gh", nargs="+", default=["gh"], help="the GitHub CLI command (tests pass a fake)")
    ap.add_argument("--lanes", default="import,collection")
    ap.add_argument("--group-members", default="", help="every member of the writer concurrency group")
    ap.add_argument("--event", default="")
    ap.add_argument("--actor", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--recovery-of", default="")
    ap.add_argument("--now", default="", help="ISO time for tests; defaults to the clock")
    args = ap.parse_args(argv)
    now = wcr.parse_time(args.now) if args.now else datetime.now(timezone.utc)
    api = Api(list(args.gh), args.repo)

    if args.command == "gate":
        try:
            own = api.run(args.run_id) if args.run_id else None
            own_created = (wcr.parse_time(own.get("created_at")) if own and own.get("created_at") else None) or now
            proceed, reason = gate_collection(args.event, args.actor, args.run_id, own_created,
                                              args.recovery_of.strip(), api.all_runs(COLLECTION_WORKFLOW), api.jobs)
        except Exception as exc:  # the guard may only ever remove a duplicate, never a cycle
            proceed, reason = True, f"the guard failed ({type(exc).__name__}); proceeding"
        line = f"CYCLE_GATE: {'proceed' if proceed else 'stand_down'} reason={reason}"
        print(line, flush=True)
        _output("proceed", "true" if proceed else "false")
        _summary([line], "Collection window guard")
        return 0

    members = args.group_members.split()
    decisions = run_check(api, [x.strip() for x in args.lanes.split(",") if x.strip()], members, now)
    lines = [d.line() for d in decisions]
    for d, line in zip(decisions, lines):
        print(line, flush=True)
        if d.state in ("held", "unreadable", "dispatch_failed"):
            print(f"::warning title=Missed-run recovery::{line}")
    print("FRESHNESS_PLAN: " + json.dumps({d.lane: {"state": d.state, "dispatch": d.dispatch} for d in decisions}))
    _summary(lines, "Missed-run recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
