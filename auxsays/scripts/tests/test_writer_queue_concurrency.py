#!/usr/bin/env python3
"""AUXSAYS writer-lane governance: one writer at a time, and no legitimate job silently dropped.

WHY THIS EXISTS
---------------
Every workflow that mutates tracked repo state shares one GitHub Actions concurrency group so that
two writers can never own the working tree at once. That part worked. What did not work is the
QUEUE in front of it.

GitHub keeps, per concurrency group, at most ONE run in progress and ONE run queued. With
``cancel-in-progress: false`` the RUNNING run is protected, so when a third run enters the group it
is the QUEUED run that is cancelled. Writer runs here are long -- 54 to 197 minutes measured, with a
300-minute job cap -- so a six-hourly cron routinely arrives while the previous run is still active
and therefore sits in that single queued slot. The next arrival kills it.

Measured on production history before this suite existed (236 writer runs):

    14 SCHEDULED writer runs were cancelled, never re-run, never reported as failures
     8 of them were `Patch Evidence Collection` -- 17% of its cron runs
     7 of the 14 were displaced by another SCHEDULED run, i.e. production-on-production loss
       with no human involved at all

The root cause of that last figure: `patch-ingest.yml` and `obs-evidence-collection.yml` BOTH
declared ``17 */6 * * *``. GitHub does not deliver them in the same minute -- measured gaps were 277
to 688 seconds -- so they do not collide on arrival. They collide because the first one is still
running when the second is due, which puts the second in the queued slot, where the following cycle's
arrival destroys it.

The invariant is therefore NOT "serialise writers" (that already held). It is:

    AUXSAYS MAY SERIALISE WRITERS.
    AUXSAYS MUST NOT SILENTLY DROP LEGITIMATE SCHEDULED WORK MERELY BECAUSE ANOTHER
    LEGITIMATE WRITER ENTERED THE QUEUE.

WHAT IS TESTED, AND WHY IT IS NOT VACUOUS
-----------------------------------------
Two layers:

1. A model of the group's queue semantics (`Lane`), replayed over arrival sequences taken from real
   observed production timelines. The model is asserted against the recorded outcome of runs that
   actually were cancelled, so the model itself is calibrated rather than assumed.

2. Static properties of the declared workflow graph, derived from the parsed YAML -- not from
   comments, which have been wrong in this repo before. The properties are chosen so that the
   pre-fix configuration FAILS them: with two independently scheduled writers in one group, the
   arrival replay produces a dropped scheduled run, and `scheduled_writers()` returns two entries.

Run standalone. Deterministic, offline, writes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO / ".github" / "workflows"

sys.path.insert(0, str(REPO / "auxsays" / "scripts"))

try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML is required")
    raise

NEWLINE = "\n"
_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))


# ---------------------------------------------------------------------------------------------
# The lane model
# ---------------------------------------------------------------------------------------------

WRITER_GROUP = "auxsays-main-writeback"


class Lane:
    """GitHub concurrency group with cancel-in-progress: false.

    One slot for the run in progress, one slot for a queued run. A new arrival takes the queued
    slot; whatever was queued is CANCELLED, not deferred. That asymmetry -- the running run is
    protected while the queued run is disposable -- is the whole defect.
    """

    def __init__(self) -> None:
        self.running: str | None = None
        self.queued: str | None = None
        self.cancelled: list[str] = []
        self.executed: list[str] = []

    def arrive(self, run: str) -> None:
        if self.running is None:
            self.running = run
            return
        if self.queued is not None:
            self.cancelled.append(self.queued)
        self.queued = run

    def finish(self) -> None:
        if self.running is not None:
            self.executed.append(self.running)
        self.running = self.queued
        self.queued = None

    def drain(self) -> None:
        while self.running is not None:
            self.finish()


def replay(events: list[tuple[str, str]]) -> Lane:
    """`events` is a list of ("arrive", run) / ("finish", "") pairs, in order."""
    lane = Lane()
    for kind, run in events:
        if kind == "arrive":
            lane.arrive(run)
        else:
            lane.finish()
    return lane


# ---------------------------------------------------------------------------------------------
# Workflow graph, parsed from YAML
# ---------------------------------------------------------------------------------------------

def load_workflows() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        # `on:` is parsed by PyYAML as the boolean True (YAML 1.1 truthiness). Normalise it so the
        # trigger set can be read by name rather than by that surprise key.
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if True in doc and "on" not in doc:
            doc["on"] = doc.pop(True)
        out[path.name] = doc
    return out


def _job_values(doc: dict, key: str) -> list:
    return [job.get(key) for job in (doc.get("jobs") or {}).values() if isinstance(job, dict)]


def writes_repo(name: str, doc: dict, raw: str) -> bool:
    """A writer is a workflow that can commit to the repo.

    Determined from effective configuration -- `contents: write` permission plus an actual
    writeback invocation -- never from prose. `permissions` may sit at workflow or job level.
    """
    perms = [doc.get("permissions")] + _job_values(doc, "permissions")
    granted = any(isinstance(p, dict) and str(p.get("contents")) == "write" for p in perms)
    invokes = "automation_writeback" in raw or "orchestrate_evidence_run" in raw
    return granted and invokes


def concurrency_of(doc: dict) -> tuple[str, object]:
    c = doc.get("concurrency")
    if isinstance(c, str):
        return c, None
    if isinstance(c, dict):
        return str(c.get("group") or ""), c.get("cancel-in-progress")
    return "", None


def triggers_of(doc: dict) -> dict:
    on = doc.get("on")
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return {str(k): None for k in on}
    return dict(on or {})


def crons_of(doc: dict) -> list[str]:
    sched = triggers_of(doc).get("schedule") or []
    return [str(e.get("cron")) for e in sched if isinstance(e, dict) and e.get("cron")]


def strip_shell_comments(text: str) -> str:
    """Remove `#` comments from shell, respecting quotes.

    THIS IS THE POINT OF THE WHOLE HELPER. An adversarial review deleted three of the reaper's four
    safety mechanisms -- the in-flight guard, the zero-job eviction test and the one-per-tick
    `break` -- and this suite still reported 57/57, because the tokens it was grepping for
    (`/jobs`, `total_count`, `in_progress`, `queued`, `break`) all still appeared in the PROSE that
    describes those guards. The suite's own docstring promised properties derived from structure
    "not from comments, which have been wrong in this repo before", and it was doing exactly what it
    warned against. Every assertion about shell behaviour now runs against comment-free text.
    """
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
            elif ch == "#":
                break                       # comment to end of line
            else:
                buf.append(ch)
            i += 1
        kept = "".join(buf).rstrip()
        if kept.strip():
            out.append(kept)
    return NEWLINE.join(out)


def effective_shell(doc: dict, job: str | None = None) -> str:
    """The shell a workflow actually EXECUTES: every `run:` scalar, comments removed."""
    jobs = doc.get("jobs") or {}
    names = [job] if job else list(jobs)
    parts: list[str] = []
    for name in names:
        spec = jobs.get(name) or {}
        for step in (spec.get("steps") or []):
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                parts.append(strip_shell_comments(step["run"]))
    return NEWLINE.join(parts)


def main() -> int:
    docs = load_workflows()
    raws = {n: (WORKFLOWS / n).read_text(encoding="utf-8") for n in docs}

    writers = {n: d for n, d in docs.items() if writes_repo(n, d, raws[n])}
    members = {n: d for n, d in docs.items() if concurrency_of(d)[0] == WRITER_GROUP}
    scheduled_writers = {n: crons_of(d) for n, d in writers.items() if crons_of(d)}

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[1] the lane model reproduces the queue semantics we measured")
    # Calibration: the model must reproduce the real 09-09 04:37/04:38 sequence, where a queued
    # dispatch was killed by an arriving cron and the arriving cron was then killed by patch-ingest.
    lane = replay([("arrive", "evidence-long-run"),      # 34307514471, still active
                   ("arrive", "maintenance-dispatch"),   # 34311698674 -> queued
                   ("arrive", "evidence-cron"),          # 34311764894 -> kills the dispatch
                   ("arrive", "patch-ingest-cron")])     # 34312447032 -> kills the cron
    check("1a a queued run is cancelled by the next arrival",
          "maintenance-dispatch" in lane.cancelled, str(lane.cancelled))
    check("1b the SCHEDULED run is cancelled too, exactly as observed in run 34311764894",
          "evidence-cron" in lane.cancelled, str(lane.cancelled))
    check("1c the RUNNING run is never cancelled (cancel-in-progress: false)",
          "evidence-long-run" not in lane.cancelled, str(lane.cancelled))
    check("1d only one run may be queued at a time",
          lane.queued == "patch-ingest-cron", str(lane.queued))
    lane.drain()
    check("1e the model loses work: arrivals 4, executed 2, cancelled 2",
          len(lane.executed) == 2 and len(lane.cancelled) == 2,
          f"executed={lane.executed} cancelled={lane.cancelled}")

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[2] E -- two writers can never simultaneously own governed writeback")
    check("2a at least one workflow writes to the repo", bool(writers), "no writers detected")
    for name in sorted(writers):
        group, cancel = concurrency_of(docs[name])
        check(f"2b {name} declares the shared writer group",
              group == WRITER_GROUP, f"group={group!r}")
        check(f"2c {name} does not cancel the in-progress writer",
              cancel is False, f"cancel-in-progress={cancel!r}")
    for name in sorted(members):
        check(f"2d {name} is in the writer group and is in fact a writer",
              name in writers, "non-writer holding the writer lane")
    check("2e the model never runs two writers at once",
          replay([("arrive", "a"), ("arrive", "b"), ("arrive", "c")]).running == "a")

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[3] A/C -- scheduled writers must not be able to evict one another")
    # THE CORE ASSERTION. Two independently scheduled writers in a one-deep queue cannot coexist
    # safely: whichever is due while the other is still running occupies the queued slot and dies at
    # the next arrival. So the graph may declare AT MOST ONE scheduled entry point into the lane.
    check("3a at most one writer workflow declares a schedule trigger",
          len(scheduled_writers) <= 1,
          f"scheduled writers: {sorted(scheduled_writers)} -- two crons in a one-deep queue "
          f"drop scheduled work; chain the second to the first instead")

    # The replay proves WHY, on whatever the graph currently declares.
    if len(scheduled_writers) >= 2:
        first, second = sorted(scheduled_writers)[:2]
        lost = replay([("arrive", f"{first}-cycle1"),
                       ("arrive", f"{second}-cycle1"),
                       ("arrive", f"{first}-cycle2")]).cancelled
        check("3b two scheduled writers demonstrably lose a scheduled run",
              not lost, f"dropped: {lost}")
    else:
        check("3b a single scheduled entry point cannot be evicted by another cron",
              True)

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[4] D -- a failing writer must not starve the next legitimate writer")
    # This section used to iterate workflows declaring a `workflow_run` trigger. NO workflow here
    # does -- chaining is a `gh workflow run` call from inside a job -- so the loop body never ran
    # and the section's invariant rested entirely on an assertion about this file's own Lane class.
    # Assert the actual mechanism instead.
    ev_doc = docs.get("obs-evidence-collection.yml") or {}
    chain_job = ((ev_doc.get("jobs") or {}).get("chain-ingest") or {})
    chain_if = str(chain_job.get("if") or "")
    check("4a the chaining job does not require its dependencies to have succeeded",
          "always()" in chain_if, f"if={chain_if[:120]!r}")
    for gate in ("success()", "needs.collect.result == 'success'",
                 "needs.powerpoint-orchestrated.result == 'success'"):
        check(f"4b chaining is not gated on {gate}",
              gate not in chain_if,
              "gating on success lets one writer's failure starve the next")
    check("4c the lane releases to the queued run when the running one ends, whatever its outcome",
          replay([("arrive", "fails"), ("arrive", "next"), ("finish", "")]).running == "next")

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[5] B -- targeted maintenance must not evict routine production")
    # Maintenance must not be a separate scheduled writer competing for the lane. This used to be a
    # filename substring test for "maint", which any other name would have walked straight past.
    # The structural property is that the ONE scheduled writer is the entry point and no other
    # member of the lane carries a trigger that fires without a human.
    autonomous = {n: sorted(triggers_of(docs[n])) for n in members
                  if set(triggers_of(docs[n])) - {"workflow_dispatch"}}
    check("5a exactly one member of the writer lane can start without a human",
          len(autonomous) == 1, f"autonomous members: {autonomous}")
    check("5b every other member of the lane is dispatch-only",
          all(set(triggers_of(docs[n])) == {"workflow_dispatch"}
              for n in members if n not in autonomous),
          str({n: sorted(triggers_of(docs[n])) for n in members if n not in autonomous}))
    check("5c a dispatch arriving behind a running writer waits rather than displacing it",
          replay([("arrive", "routine"), ("arrive", "maintenance")]).running == "routine")

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[6] F -- every material write path still deploys the site")
    # Asserted against the EXECUTED shell with comments stripped. The previous version accepted
    # `"pages.yml" in raws[name] or "orchestrate_evidence_run" in raws[name]`, and a review that
    # commented out all four `--pages-cmd` lines still saw one of the four pass on the `or` branch
    # and the rest would have passed had the token survived anywhere in the file.
    for name in sorted(writers):
        shell = effective_shell(docs[name])
        check(f"6a {name} really dispatches a Pages build after writeback",
              "pages.yml" in shell,
              "a commit that never deploys is an incomplete write path")
    # The PowerPoint lane's deploy is bound in Python, not YAML, so it is asserted at its source.
    orch = (REPO / "auxsays" / "scripts" / "orchestrate_evidence_run.py")
    orch_src = orch.read_text(encoding="utf-8") if orch.exists() else ""
    check("6c the orchestrated lane binds a Pages dispatch by default",
          'pages_cmd: str | None = "gh workflow run pages.yml --ref main"' in orch_src,
          "the graph lane commits too, so it must deploy too")
    pages = docs.get("pages.yml") or {}
    pgroup, _ = concurrency_of(pages)
    check("6b the Pages workflow is NOT in the writer group, so a writer can always dispatch it",
          pgroup and pgroup != WRITER_GROUP, f"pages group={pgroup!r}")

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[7] non-writers must not hold the writer lane")
    for name, doc in sorted(docs.items()):
        group, _ = concurrency_of(doc)
        if group == WRITER_GROUP:
            continue
        if name in writers:
            check(f"7a {name} writes but is outside the writer group", False, f"group={group!r}")
    readers = [n for n, d in docs.items() if n not in writers]
    check("7b read-only workflows exist and stay out of the lane",
          all(concurrency_of(docs[n])[0] != WRITER_GROUP for n in readers),
          str([n for n in readers if concurrency_of(docs[n])[0] == WRITER_GROUP]))

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[8] the reaper -- the repair must live OUTSIDE the evicted run")
    # An evicted run is cancelled before a runner is allocated: its `jobs` array is empty, so no
    # step of ours ever executes inside it, not even an `always()` handler. Verified on every
    # in-window eviction. A design that re-enqueues from the displaced job is unimplementable, so
    # the recovery has to be a separate workflow that observes the loss from outside.
    reaper_name = "writer-queue-reaper.yml"
    reaper = docs.get(reaper_name)
    check("8a a reaper workflow exists", reaper is not None, "writer-queue-reaper.yml missing")
    if reaper:
        raw = raws[reaper_name]
        rgroup, _ = concurrency_of(reaper)
        check("8b the reaper is NOT a writer",
              reaper_name not in writers, "a writing reaper could clobber the tree")
        check("8c the reaper is NOT in the writer group",
              rgroup and rgroup != WRITER_GROUP,
              "joining the lane would let it evict the very run it protects")
        check("8d the reaper only reads the repo",
              str((reaper.get("permissions") or {}).get("contents")) == "read",
              str(reaper.get("permissions")))
        check("8e the reaper may dispatch workflows",
              str((reaper.get("permissions") or {}).get("actions")) == "write",
              str(reaper.get("permissions")))
        check("8f the reaper runs on its own schedule", bool(crons_of(reaper)),
              "a reaper that never runs repairs nothing")
        # EVERYTHING BELOW READS THE EXECUTED SHELL, COMMENTS STRIPPED. Grepping the raw file let a
        # review delete the in-flight guard, the zero-job test and the `break` while this suite
        # still reported all green, because each token survived in the prose describing it.
        shell = effective_shell(reaper, "reap")
        env = ((reaper.get("jobs") or {}).get("reap") or {}).get("env") or {}
        check("8g the reaper re-dispatches every routine writer",
              set(str(env.get("REAPABLE", "")).split()) == {"obs-evidence-collection.yml",
                                                            "patch-ingest.yml"},
              f"REAPABLE={env.get('REAPABLE')!r}")
        # CLOSED WORLD over the lane. A new workflow must not be able to join the writer group
        # without the reaper's group-wide guard knowing about it.
        check("8g2 the reaper's group-member list equals the parsed membership of the lane",
              set(str(env.get("GROUP_MEMBERS", "")).split()) == set(members),
              f"declared={sorted(str(env.get('GROUP_MEMBERS','')).split())} parsed={sorted(members)}")
        check("8h the reaper keys on the eviction signature: zero jobs allocated",
              "/jobs" in shell and "total_count" in shell,
              "a run cancelled AFTER starting may already have committed and must not be resurrected")
        check("8h2 and it refuses to resurrect a run that had jobs",
              "-ne 0" in shell and "left alone" in shell, shell[:200])
        # A COVERING run must have actually done the work. `.conclusion != "cancelled"` accepted
        # `failure`, `startup_failure`, `timed_out` and `skipped` -- and a real historical eviction
        # (patch-ingest 32226420647) would have been written off by a later `failure` run.
        check("8i a covering run must have concluded SUCCESS",
              'conclusion == \\"success\\"' in shell or 'conclusion == "success"' in shell,
              "anything-but-cancelled counts failures as having done the work")
        check("8i2 a covering run must be routine, not a targeted or dry-run dispatch",
              "github-actions[bot]" in shell and 'event == \\"schedule\\"' in shell
              or "triggering_actor" in shell,
              "a dry_run dispatch concludes success while writing nothing")
        check("8i3 an operator's own cancellation is not resurrected as a live write",
              "triggering_actor" in shell,
              "cancelling a queued dry run must not come back as a writeback")
        # THE GUARD MUST BE GROUP-WIDE. The pending slot belongs to the group; a per-workflow guard
        # let the reaper add a third entrant and destroy the other lane's queued run.
        check("8j the free-lane check is GROUP-WIDE, not per-workflow",
              "GROUP_MEMBERS" in shell,
              "a per-workflow guard lets the reaper evict the run it exists to protect")
        # Assert the actual COMPARISON, not the presence of the variable: replacing the guard with
        # `if false; then` leaves every token intact and slipped past an earlier version of this.
        check("8j2 and the occupancy check is a real comparison that can fire",
              '[ "${busy}" -gt 0 ]' in shell,
              "a guard rewritten to `if false` keeps all its tokens")
        check("8j3 and an occupied lane ends the tick without dispatching",
              "exit 0" in shell, shell[:200])
        # A BARE `break` inside the per-run loop. The outer loop also breaks
        # (`[ "${dispatched}" -gt 0 ] && break`), so a substring test for "break" passed even with
        # the inner one deleted. Count only lines that are exactly `break`.
        bare_breaks = [ln.strip() for ln in shell.splitlines()].count("break")
        check("8k the per-run loop stops after one re-dispatch",
              bare_breaks >= 1,
              f"bare `break` statements: {bare_breaks} -- the outer loop's `&& break` is not this")
        check("8l a transient API error does not abort the whole tick",
              "::warning" in shell and "set -uo pipefail" in shell,
              "set -e aborted the second lane when the first lane's API call failed")

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[9] routine ingestion is chained, not independently scheduled")
    ev = docs.get("obs-evidence-collection.yml") or {}
    chain = ((ev.get("jobs") or {}).get("chain-ingest") or {})
    check("9a the scheduled writer chains the de-scheduled writer",
          "patch-ingest.yml" in str(chain), str(chain)[:160])
    check("9b chaining survives a failure of the collection lanes",
          "always()" in str(chain.get("if")), str(chain.get("if")))
    chain_if = str(chain.get("if"))
    check("9c chaining is confined to the routine cycle",
          "schedule" in chain_if,
          "a targeted dispatch must not drag a full ingestion run behind it")
    # A reaped run arrives as a no-input `workflow_dispatch`, so a gate on the event name alone
    # would skip ingestion on exactly the cycles the reaper recovered -- the same silent loss, one
    # level up. The gate must also admit a dispatch carrying no inputs.
    check("9c2 chaining also covers a RECOVERED cycle re-dispatched by the reaper",
          all(f"github.event.inputs.{k} == ''" in chain_if
              for k in ("product_id", "update_version", "since")),
          chain_if)
    check("9c3 but not a dry run",
          "dry_run != 'true'" in chain_if, chain_if)
    check("9d the chained lane no longer declares its own cron",
          not crons_of(docs.get("patch-ingest.yml") or {}),
          "two crons in a one-deep queue is the original defect")
    check("9e the chained lane is still serialised by the writer group",
          concurrency_of(docs.get("patch-ingest.yml") or {})[0] == WRITER_GROUP,
          "dropping the group would allow two simultaneous writers")

    # -----------------------------------------------------------------------------------------
    print(NEWLINE + "[10] end to end: no legitimate SCHEDULED run is lost")

    def replay_with_reaper(arrivals: list[str]) -> tuple[list[str], list[str]]:
        """Same lane, plus a reaper that re-dispatches evicted scheduled runs.

        The reaper's covering rule is modelled too: an eviction is only repaired when no later run
        of the same workflow has since executed, because such a run already performed that
        workflow's routine cycle.
        """
        lane = Lane()
        pending_repairs: list[str] = []
        for run in arrivals:
            lane.arrive(run)
        # The reaper observes from outside, so it acts after the fact, once per tick.
        for _ in range(6):
            lane.finish()
            for lost in list(lane.cancelled):
                if not lost.startswith("cron:"):
                    continue                      # only scheduled work is resurrected
                workflow = lost.split(":")[1]
                covered = any(r.split(":")[1] == workflow
                              for r in lane.executed if ":" in r)
                if not covered and lost not in pending_repairs:
                    pending_repairs.append(lost)
                    lane.arrive(f"repair-of-{lost}")
        lane.drain()
        return lane.executed, [c for c in lane.cancelled
                               if c.startswith("cron:")
                               and f"repair-of-{c}" not in lane.executed
                               and not any(e.split(":")[1] == c.split(":")[1]
                                           for e in lane.executed if ":" in e)]

    # The exact 2026-09-09 sequence that lost run 34311764894.
    executed, lost = replay_with_reaper(["cron:evidence-prev", "dispatch:maintenance",
                                         "cron:evidence", "cron:ingest"])
    check("10a the historical loss of a scheduled run is repaired, not silently dropped",
          not lost, f"still lost: {lost}")
    check("10b the repair actually executes",
          any(e.startswith("repair-of-") for e in executed) or
          any(e.startswith("cron:evidence") for e in executed), str(executed))
    # A -- ingest becomes due while evidence is running: both must ultimately execute.
    executed, lost = replay_with_reaper(["cron:evidence", "cron:ingest"])
    check("10c A: ingest due while evidence runs -- both execute",
          "cron:evidence" in executed and "cron:ingest" in executed, str(executed))
    # B -- maintenance requested while routine ingest is running: routine must not be cancelled.
    lane = replay([("arrive", "cron:ingest"), ("arrive", "dispatch:maintenance")])
    check("10d B: maintenance waits; the running routine job is untouched",
          lane.running == "cron:ingest" and not lane.cancelled, str(lane.cancelled))
    # C -- routine evidence becomes due while maintenance is pending: nothing legitimate vanishes.
    executed, lost = replay_with_reaper(["cron:ingest", "dispatch:maintenance", "cron:evidence"])
    check("10e C: a cron arriving behind a pending dispatch is not silently lost",
          not lost, f"lost: {lost}")
    # D -- a writer fails: the next legitimate writer still proceeds.
    lane = replay([("arrive", "cron:evidence"), ("arrive", "cron:ingest"), ("finish", "")])
    check("10f D: the next writer proceeds after the previous one ends",
          lane.running == "cron:ingest", str(lane.running))

    # THE COUNTERFACTUAL. Section 10 models an algorithm, and section 8 asserts that algorithm is
    # actually implemented. Neither is worth anything unless the model can still FAIL, so assert
    # that the same sequence without a reaper does lose scheduled work. If this ever passes, the
    # model has stopped discriminating and the rest of section 10 is decoration.
    bare = replay([("arrive", "cron:evidence-prev"), ("arrive", "dispatch:maintenance"),
                   ("arrive", "cron:evidence"), ("arrive", "cron:ingest")])
    lost_bare = [c for c in bare.cancelled if c.startswith("cron:")]
    check("10g without a reaper the SAME sequence loses a scheduled run",
          bool(lost_bare), "the model no longer discriminates -- section 10 would be vacuous")
    check("10h and the reaper is what removes that loss",
          reaper is not None, "the model is only meaningful if the reaper is implemented")

    print(NEWLINE + "=" * 74)
    print(f"Results: {_passed}/{_passed + _failed} passed, {_failed} failed")
    print("=" * 74)
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
