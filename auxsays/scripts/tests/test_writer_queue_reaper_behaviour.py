#!/usr/bin/env python3
"""The writer-queue reaper, EXECUTED -- not grepped.

WHY THIS FILE EXISTS SEPARATELY FROM test_writer_queue_concurrency.py
--------------------------------------------------------------------
The first version of that suite asserted the reaper's safety mechanisms by searching the workflow
file for tokens. An adversarial review then deleted three of the four mechanisms -- the in-flight
guard, the zero-job eviction test and the one-per-tick `break` -- and the suite still reported all
green, because every token it looked for survived in the PROSE that described the guard it had just
removed. That is the third time this repo has been bitten by the same shape (a Liquid `blank`
comparison that always fired, a CSS declaration that lost the cascade, and now this).

The structural suite was repaired to read `run:` scalars with comments stripped, which catches
deletion. It still cannot answer the question that actually matters: given a particular state of the
Actions API, WHAT DOES THE REAPER DO? So this file extracts the real shell from the workflow and
runs it against a scripted fake `gh`, asserting the decision it reaches in each state that matters.

Nothing here mocks the reaper's own logic -- only the API it reads. The `run:` scalar under test is
never retyped; it is loaded from the YAML, so it cannot drift from what CI executes.

REQUIRES: `bash`. Present on ubuntu-latest and on this repo's Windows dev setup via Git Bash. If
bash is missing the suite reports that and fails loudly rather than passing vacuously.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "writer-queue-reaper.yml"

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


# A fake `gh` that answers each query class from the environment, so a scenario is fully described
# by a handful of variables. It dispatches on the jq expression because that is what distinguishes
# the reaper's queries from one another.
FAKE_GH = r"""#!/usr/bin/env bash
q="$*"
if [ "$1" = "workflow" ]; then
  echo "DISPATCHED $3" >> "$SIM_DISPATCH_LOG"
  exit 0
fi
case "$q" in
  # Answer the occupancy query DIFFERENTLY depending on whether it asks about `pending`. A
  # concurrency-blocked run reports `status: "pending"`, so a query that omits that state is blind
  # to exactly the run the guard protects. Returning "occupied" only to a pending-aware query makes
  # the scenario discriminate: a blind reaper sees a free lane and dispatches.
  *'.status == "pending"'*)      echo "$SIM_INFLIGHT_PENDING" ;;
  *'select(.status =='*)         echo "$SIM_INFLIGHT" ;;
  *'.conclusion == \"success\"'*|*'conclusion == "success"'*)  echo "$SIM_COVERING" ;;
  *'conclusion == \"cancelled\"'*|*'conclusion == "cancelled"'*)
      case "$q" in
        *obs-evidence-collection*) echo "$SIM_EVICTED_OBS" ;;
        *patch-ingest*)            echo "$SIM_EVICTED_ING" ;;
      esac ;;
  */jobs*)                                                     echo "$SIM_JOBS" ;;
esac
exit 0
"""


def load_step() -> tuple[str, dict]:
    import yaml
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["reap"]
    return job["steps"][0]["run"], (job.get("env") or {})


def run_scenario(script: str, env_decl: dict, **sim) -> tuple[int, str, list[str]]:
    tmp = tempfile.mkdtemp()
    try:
        gh = Path(tmp, "gh")
        gh.write_text(FAKE_GH, newline="\n")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        sh = Path(tmp, "run.sh")
        sh.write_text("#!/usr/bin/env bash\n" + script, newline="\n")
        log = Path(tmp, "dispatch.log")
        log.write_text("", newline="\n")
        env = dict(os.environ)
        env.update({
            "PATH": tmp + os.pathsep + env.get("PATH", ""),
            "GITHUB_STEP_SUMMARY": str(Path(tmp, "summary.md")),
            "REPO": "auxchan/auxsays.github.io",
            "GROUP_MEMBERS": " ".join(str(env_decl.get("GROUP_MEMBERS", "")).split()),
            "REAPABLE": str(env_decl.get("REAPABLE", "")),
            "SIM_INFLIGHT": sim.get("inflight", "0"),
            # Defaults to the plain occupancy answer so every other scenario is unaffected; the
            # pending-blindness scenario overrides it to make the two queries disagree.
            "SIM_INFLIGHT_PENDING": sim.get("inflight_pending", sim.get("inflight", "0")),
            "SIM_COVERING": sim.get("covering", ""),
            "SIM_EVICTED_OBS": sim.get("evicted_obs", ""),
            "SIM_EVICTED_ING": sim.get("evicted_ing", ""),
            "SIM_JOBS": sim.get("jobs", "0"),
            "SIM_DISPATCH_LOG": str(log),
        })
        proc = subprocess.run(["bash", str(sh)], capture_output=True, text=True, env=env)
        dispatched = [ln.split()[1] for ln in log.read_text().splitlines()
                      if ln.startswith("DISPATCHED")]
        return proc.returncode, proc.stdout, dispatched
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


OBS = "obs-evidence-collection.yml"
ING = "patch-ingest.yml"

SCENARIOS = [
    # label, sim state, expected dispatches, why it matters
    ("a quiet lane with nothing lost dispatches nothing",
     {}, []),
    ("a routine eviction with zero jobs and no covering run is REPAIRED",
     {"evicted_obs": "101 2026-09-09T03:00:00Z"}, [OBS]),
    ("the same eviction is NOT repaired while the lane is occupied -- the pending slot "
     "belongs to the group, so adding an entrant would destroy someone else's queued run",
     {"inflight": "1", "evicted_obs": "101 2026-09-09T03:00:00Z"}, []),
    # DISCRIMINATING: the lane looks FREE to a query that omits `pending` and OCCUPIED to one that
    # includes it. A reaper blind to `pending` therefore dispatches here and fails this scenario.
    # This is a real production defect, not a hypothetical: the first live tick reported
    # "1 run(s) queued or in progress" while run 34333264915 sat pending in the very slot the guard
    # exists to protect, because `pending` was missing from the state list.
    ("a run held PENDING by the concurrency group occupies the lane",
     {"inflight": "0", "inflight_pending": "1",
      "evicted_obs": "101 2026-09-09T03:00:00Z"}, []),
    ("a cancelled run that HAD jobs is never resurrected -- it may already have committed",
     {"evicted_obs": "101 2026-09-09T03:00:00Z", "jobs": "2"}, []),
    ("a later SUCCESSFUL routine run covers the loss, so no duplicate cycle is queued",
     {"evicted_obs": "101 2026-09-09T03:00:00Z", "covering": "2026-09-09T05:00:00Z"}, []),
    ("a covering run OLDER than the eviction does not cover it",
     {"evicted_obs": "101 2026-09-09T03:00:00Z", "covering": "2026-09-09T01:00:00Z"}, [OBS]),
    ("two evictions in one window still produce exactly one entrant",
     {"evicted_obs": "101 2026-09-09T01:00:00Z\n102 2026-09-09T03:00:00Z"}, [OBS]),
    ("a loss in the ingest lane is repaired in the ingest lane",
     {"evicted_ing": "201 2026-09-09T03:00:00Z"}, [ING]),
    ("losses in BOTH lanes still produce exactly one entrant, group-wide",
     {"evicted_obs": "101 2026-09-09T03:00:00Z",
      "evicted_ing": "201 2026-09-09T03:00:00Z"}, [OBS]),
]


def main() -> int:
    if shutil.which("bash") is None:
        print("  FAIL  bash is required to execute the reaper's shell")
        print(NEWLINE + "Results: 0/1 passed, 1 failed")
        return 1
    script, env_decl = load_step()

    print(NEWLINE + "[R] the reaper's real shell, executed against a scripted Actions API")
    for label, sim, expected in SCENARIOS:
        rc, out, dispatched = run_scenario(script, env_decl, **sim)
        check(f"R {label}", dispatched == expected,
              f"dispatched={dispatched} expected={expected}{NEWLINE}{out.strip()[:400]}")
        check(f"R   ...and the step exits 0 while doing it", rc == 0,
              f"exit={rc} -- a routine tick must not report as a failure")

    print(NEWLINE + "[Q] a quiet tick is the normal case and must never fail the job")
    # `set -e` is deliberately not in force so one lane's API error cannot abort the other. That
    # makes the script's exit status the status of its LAST command, which is easy to get wrong:
    # an `[ -n "$notes" ] && printf ...` tail returned 1 on every tick that had nothing to report.
    rc, out, dispatched = run_scenario(script, env_decl)
    check("Q1 exit status is 0 with nothing to report", rc == 0, f"exit={rc}")
    check("Q2 and nothing was dispatched", dispatched == [], str(dispatched))

    print(NEWLINE + "[F] an unreadable API fails SAFE -- it must not dispatch blindly")
    # The fake gh emits nothing for the in-flight count, which is what a failed call looks like.
    rc, out, dispatched = run_scenario(script, env_decl, inflight="",
                                       evicted_obs="101 2026-09-09T03:00:00Z")
    check("F1 an unreadable in-flight count is treated as an occupied lane",
          dispatched == [], f"dispatched={dispatched}")
    check("F2 and it says so rather than failing silently",
          "::warning" in out, out.strip()[:300])
    check("F3 and still exits 0", rc == 0, f"exit={rc}")

    print(NEWLINE + "=" * 74)
    print(f"Results: {_passed}/{_passed + _failed} passed, {_failed} failed")
    print("=" * 74)
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
