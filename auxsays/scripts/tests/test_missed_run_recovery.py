#!/usr/bin/env python3
"""Missed-run recovery: a scheduled cycle GitHub never created is recovered once; a done cycle stands down.

What is pinned (auxsays/scripts/missed_run_recovery.py, .github/workflows/missed-run-recovery.yml and the
`gate` job of obs-evidence-collection.yml):
  [1] the designed windows, derived from the real crons
  [2] import lane: stale data, unchanged output, delayed trigger (already active), grace, cooldown,
      persistent outage (held after 2 failures), successful publication (stops once fresh), unreadable
  [3] collection lane: missing trigger, delayed trigger present, evicted run left to the reaper, operator
      dispatch not counted, busy and unreadable writer group
  [4] the in-run window guard: a late cron after a cycle on main stands down; after a lost cycle it proceeds;
      G91 re-runs and operator dispatches are never gated; the reaper's re-dispatch of an evicted run is
  [5] EXECUTED: the bare script as a subprocess against a scripted fake `gh` -- two checks at once dispatch once
      per lane; the gate step's shell from the workflow YAML, run under bash, writes `proceed` (and its
      failure fallback proceeds)
  [6] simulated days: all crons missing -> recovered to exactly the designed 4 collection cycles per UTC day;
      late crons -> still 4; persistent failure -> 4, never more; import outage -> 2 dispatches then held
  [7] structure: concurrency, permissions, workflow_run names that exist, the writer-group list, the job
      conditions that skip collect / PowerPoint / chain-ingest on a stand-down
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "auxsays" / "scripts"
WF = REPO / ".github" / "workflows"
sys.path.insert(0, str(SCRIPTS))
import missed_run_recovery as mrr  # noqa: E402
import writer_cycle_recovery as wcr  # noqa: E402

_passed = 0
_failed = 0
BOT = {"login": "github-actions[bot]"}
OWNER = {"login": "owner"}
UTC = timezone.utc


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))


def T(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(i, created, status="completed", conclusion="success", event="schedule", actor=OWNER, started=None, title="x"):
    return {"id": i, "created_at": created, "run_started_at": started or created, "status": status,
            "conclusion": conclusion if status == "completed" else None, "event": event,
            "triggering_actor": actor, "display_title": title}


def load(name: str) -> dict:
    with open(WF / name, encoding="utf-8") as h:
        doc = yaml.safe_load(h)
    if True in doc and "on" not in doc:      # PyYAML reads the bare key `on` as True
        doc["on"] = doc.pop(True)
    return doc


def strip_comments(text: str) -> str:
    return "\n".join(line for line in str(text).splitlines() if not line.strip().startswith("#"))


# ------------------------------------------------------------------------------------------------
# A scripted fake `gh`: the same handler serves in-process calls and the subprocess fake.
# ------------------------------------------------------------------------------------------------
FAKE_SRC = r'''
import json, sys
def handle(argv, state):
    if state.get("fail"):
        return 1, ""
    if argv[:2] == ["workflow", "run"]:
        wf = argv[2]
        state["dispatches"].append(wf)
        state["next_id"] = state.get("next_id", 900000) + 1
        state["runs"].setdefault(wf, []).insert(0, {"id": state["next_id"], "created_at": state["now"],
            "run_started_at": state["now"], "status": "queued", "conclusion": None, "event": "workflow_dispatch",
            "triggering_actor": {"login": "github-actions[bot]"}, "display_title": "dispatched",
            "visible_after": state.get("lists", 0) + state.get("list_lag", 0)})
        return 0, ""
    if argv[0] != "api":
        return 1, ""
    path = argv[1]
    if path.endswith("/commits/main"):
        c = state.get("output_commit")
        return (0, json.dumps({"commit": {"committer": {"date": c}}})) if c else (1, "")
    if "/actions/workflows/" in path:
        wf = path.split("/actions/workflows/")[1].split("/")[0]
        if wf in state.get("unreadable", []):
            return 1, ""
        state["lists"] = state.get("lists", 0) + 1
        runs = sorted((r for r in state["runs"].get(wf, []) if r.get("visible_after", 0) < state["lists"]),
                      key=lambda r: r["created_at"], reverse=True)
        if "status=completed" in path:
            runs = [r for r in runs if r["status"] == "completed"]
        return 0, json.dumps({"workflow_runs": runs})
    if "/actions/runs/" in path:
        rid = path.split("/actions/runs/")[1].split("/")[0].split("?")[0]
        if path.split("?")[0].endswith("/jobs"):
            j = state.get("jobs", {}).get(rid)
            if j == "unreadable":
                return 1, ""
            return 0, json.dumps(j or {"total_count": 0, "jobs": []})
        for runs in state["runs"].values():
            for r in runs:
                if str(r["id"]) == rid:
                    return 0, json.dumps(r)
        return 1, ""
    return 1, ""
if __name__ == "__main__":
    p = __import__("os").environ["FAKE_GH_STATE"]
    st = json.load(open(p))
    rc, out = handle(sys.argv[1:], st)
    json.dump(st, open(p, "w"))
    sys.stdout.write(out)
    sys.exit(rc)
'''
_ns: dict = {}
exec(FAKE_SRC, _ns)
handle = _ns["handle"]


class FakeApi(mrr.Api):
    def __init__(self, state: dict):
        super().__init__(["gh"], "o/r")
        self.state = state

    def _run(self, args):
        rc, out = handle(args, self.state)
        return subprocess.CompletedProcess(args, rc, out, "")


def state(now, runs=None, output_commit=None, jobs=None, **kw):
    s = {"now": now, "runs": runs or {}, "output_commit": output_commit, "jobs": jobs or {}, "dispatches": []}
    s.update(kw)
    return s


MEMBERS = ["obs-evidence-collection.yml", "patch-ingest.yml", "davinci-updates.yml", "promote-davinci-verified-reports.yml"]
NOSLEEP = lambda s: None  # noqa: E731


def check_once(s, lanes=("import", "collection")):
    return {d.lane: d for d in mrr.run_check(FakeApi(s), list(lanes), MEMBERS, T(s["now"]), NOSLEEP)}


def main() -> int:
    print("[1] designed windows")
    six, off = mrr.COLLECTION_PERIOD, mrr.COLLECTION_OFFSET
    check("1a 00:05 belongs to the previous day's 18:17 window",
          mrr.window_start(T("2026-11-26T00:05:00Z"), six, off) == T("2026-11-25T18:17:00Z"))
    check("1b a window opens exactly at its slot",
          mrr.window_start(T("2026-11-26T06:17:00Z"), six, off) == T("2026-11-26T06:17:00Z"))
    check("1c 23:59 belongs to 18:17", mrr.window_start(T("2026-11-26T23:59:59Z"), six, off) == T("2026-11-26T18:17:00Z"))
    cron = load("obs-evidence-collection.yml")["on"]["schedule"][0]["cron"]
    m = re.fullmatch(r"(\d+) \*/(\d+) \* \* \*", cron)
    check("1d the collection window is the collection cron's own period and minute",
          bool(m) and timedelta(minutes=int(m.group(1))) == off and timedelta(hours=int(m.group(2))) == six, cron)
    icron = load("assessment-import.yml")["on"]["schedule"][0]["cron"]
    minutes = sorted(int(x) for x in icron.split()[0].split(","))
    gaps = {(b - a) for a, b in zip(minutes, minutes[1:] + [minutes[0] + 60])}
    check("1e the import cadence is the import cron's own spacing", gaps == {15} and mrr.IMPORT_CADENCE == timedelta(minutes=15), icron)
    out_env = load("assessment-import.yml")["jobs"]["import"]["env"]["OUTPUT_REPO"]
    check("1f the upstream read is the repository the import lane fetches", out_env == mrr.OUTPUT_REPO, out_env)

    print("\n[2] import lane")
    imp = "assessment-import.yml"
    live = [run(45844540577, "2026-11-26T14:59:39Z"), run(45770434245, "2026-11-26T06:45:40Z", event="workflow_dispatch")]
    d = mrr.decide_import(T("2026-11-26T22:12:21Z"), T("2026-11-26T17:07:30Z"), live)
    check("2a STALE DATA (the live 11-26 case): output 17:07:30 after the last successful import 14:59:39 -> due",
          d.state == "due" and d.dispatch, d.line())
    d = mrr.decide_import(T("2026-11-26T22:12:21Z"), T("2026-11-26T06:24:24Z"), live)
    check("2b UNCHANGED OUTPUT: an output older than the last success dispatches nothing", d.state == "fresh" and not d.dispatch, d.line())
    d = mrr.decide_import(T("2026-11-26T22:12:21Z"), T("2026-11-26T17:07:30Z"),
                          [run(1, "2026-11-26T22:10:00Z", status="queued")] + live)
    check("2c DELAYED TRIGGER: an import already queued (a late cron) -> busy, no dispatch", d.state == "busy" and not d.dispatch, d.line())
    d = mrr.decide_import(T("2026-11-26T17:12:00Z"), T("2026-11-26T17:07:30Z"), live)
    check("2d inside the 10-minute grace after the output commit -> no dispatch", d.state == "grace" and not d.dispatch, d.line())
    d = mrr.decide_import(T("2026-11-26T22:12:21Z"), T("2026-11-26T17:07:30Z"),
                          [run(2, "2026-11-26T22:05:00Z", conclusion="failure")] + live)
    check("2e COOLDOWN: a run created within the designed 15 minutes -> no dispatch", d.state == "cooldown" and not d.dispatch, d.line())
    two = [run(3, "2026-11-26T19:00:00Z", conclusion="failure"), run(2, "2026-11-26T18:00:00Z", conclusion="failure")] + live
    d = mrr.decide_import(T("2026-11-26T22:12:21Z"), T("2026-11-26T17:07:30Z"), two)
    check("2f PERSISTENT OUTAGE: 2 failures since the output commit -> held, no dispatch", d.state == "held" and not d.dispatch, d.line())
    d = mrr.decide_import(T("2026-11-26T22:12:21Z"), T("2026-11-26T17:07:30Z"), two[1:])
    check("2g one failure is retried once more (the cap is 2)", d.state == "due" and d.dispatch, d.line())
    d = mrr.decide_import(T("2026-11-26T23:30:00Z"), T("2026-11-26T23:00:00Z"), two)
    check("2h a NEW output commit clears the hold (failures before it do not count)", d.state == "due", d.line())
    d = mrr.decide_import(T("2026-11-26T22:30:00Z"), T("2026-11-26T17:07:30Z"),
                          [run(4, "2026-11-26T22:13:00Z", started="2026-11-26T22:13:05Z")] + live)
    check("2i SUCCESSFUL PUBLICATION: a success started after the output commit -> fresh, stops", d.state == "fresh" and not d.dispatch, d.line())
    check("2j unreadable output commit or run list -> no dispatch",
          mrr.decide_import(T("2026-11-26T22:12:21Z"), None, live).state == "unreadable"
          and mrr.decide_import(T("2026-11-26T22:12:21Z"), T("2026-11-26T17:07:30Z"), None).state == "unreadable")

    print("\n[3] collection lane")
    now = T("2026-11-26T19:00:00Z")
    d = mrr.decide_collection(now, [run(45781055842, "2026-11-26T08:11:20Z")], 0)
    check("3a MISSING TRIGGER: no routine run created in the 18:17 window, group free -> due", d.state == "due" and d.dispatch, d.line())
    d = mrr.decide_collection(T("2026-11-26T18:40:00Z"), [], 0)
    check("3b inside the 30-minute grace -> no dispatch", d.state == "grace" and not d.dispatch, d.line())
    d = mrr.decide_collection(T("2026-11-26T21:40:00Z"), [run(45898272536, "2026-11-26T21:27:30Z", status="in_progress")], 0)
    check("3c DELAYED TRIGGER: the window's cron arrived late (21:27) -> fresh", d.state == "fresh" and not d.dispatch, d.line())
    d = mrr.decide_collection(now, [run(7, "2026-11-26T18:20:00Z", conclusion="cancelled")], 0)
    check("3d an evicted run in the window is the reaper's, not a missing cycle -> no dispatch", d.state == "fresh", d.line())
    d = mrr.decide_collection(now, [run(8, "2026-11-26T18:30:00Z", event="workflow_dispatch", actor=OWNER)], 0)
    check("3e an operator dispatch does not count as the routine cycle -> due", d.state == "due", d.line())
    d = mrr.decide_collection(now, [run(9, "2026-11-26T18:30:00Z", event="workflow_dispatch", actor=BOT)], 0)
    check("3f a dispatch by this repository's automation counts -> fresh", d.state == "fresh", d.line())
    d = mrr.decide_collection(now, [], 1)
    check("3g a busy writer group (one pending entrant) -> no third entrant", d.state == "busy" and not d.dispatch, d.line())
    check("3h unreadable runs or occupancy -> no dispatch",
          mrr.decide_collection(now, None, 0).state == "unreadable" and mrr.decide_collection(now, [], None).state == "unreadable")
    d = mrr.decide_collection(now, [], 0, 4)
    check("3i DAILY CAP: 4 cycles collected in the last 24 h -> capped, never a 5th", d.state == "capped" and not d.dispatch, d.line())
    check("3j 3 cycles in 24 h still recovers; an unreadable day count does not",
          mrr.decide_collection(now, [], 0, 3).state == "due" and mrr.decide_collection(now, [], 0, None).state == "unreadable")

    print("\n[4] the in-run window guard")
    collect_ran = {"name": "collect", "conclusion": "success", "steps": [{"name": "Checkout", "conclusion": "success"}]}
    reached = {"total_count": 3, "jobs": [collect_ran, {"name": "chain-ingest", "steps": [{"name": wcr.CYCLE_MARKER_STEP, "conclusion": "success"}]}]}
    lost = {"total_count": 3, "jobs": [collect_ran, {"name": "chain-ingest", "steps": [{"name": wcr.CYCLE_MARKER_STEP, "conclusion": "skipped"}]}]}
    stood = {"total_count": 4, "jobs": [{"name": "gate", "conclusion": "success", "steps": [{"name": "x", "conclusion": "success"}]},
                                        {"name": "collect", "conclusion": "skipped", "steps": []},
                                        {"name": "chain-ingest", "conclusion": "skipped", "steps": []}]}
    rec = run(100, "2026-11-26T18:50:00Z", event="workflow_dispatch", actor=BOT)
    late = T("2026-11-26T21:27:30Z")

    def gate(jobs, event="schedule", actor=OWNER, recovery_of="", runs=None, created=late):
        rr = [rec] if runs is None else runs
        return mrr.gate_collection(event, actor["login"], "200", created, recovery_of, rr, lambda i: jobs.get(str(i)))

    p, why = gate({"100": reached})
    check("4a a late cron after the recovery put the window's cycle on main -> stands down", p is False, why)
    p, why = gate({"100": lost})
    check("4b A1/S1 a late cron after a recovery that LOST its cycle stands down too (the loss is G91's one re-run)",
          p is False, why)
    p, why = gate({"100": reached, "555": {"total_count": 3, "jobs": []}}, event="workflow_dispatch", actor=BOT, recovery_of="555")
    check("4c a G91 re-run of a run that started and lost is never gated", p is True, why)
    p, why = gate({"100": reached, "556": {"total_count": 0, "jobs": []}}, event="workflow_dispatch", actor=BOT, recovery_of="556")
    check("4d the reaper's re-dispatch of an EVICTED run is gated like the cron it replaces", p is False, why)
    p, why = gate({"100": reached}, event="workflow_dispatch", actor=OWNER)
    check("4e an operator dispatch is never gated", p is True, why)
    p, why = gate({"100": reached}, runs=[run(100, "2026-11-26T12:40:00Z", event="workflow_dispatch", actor=BOT)])
    check("4f a cycle from the PREVIOUS window does not stand this window down", p is True, why)
    p2, why2 = mrr.gate_collection("schedule", OWNER["login"], "200", late, "", None, lambda i: None)
    check("4g unreadable runs proceed (the guard only removes duplicates)", p2 is True, why2)
    p, why = gate({"101": stood}, runs=[run(101, "2026-11-26T19:00:00Z")])
    check("4h a stood-down run (it collected nothing) is not the window's cycle by itself", p is True, why)
    p, why = gate({"100": reached}, runs=[run(100, "2026-11-26T22:00:00Z", event="workflow_dispatch", actor=BOT)])
    check("4i a run created AFTER this one never stands it down", p is True, why)
    p, why = gate({"100": {"total_count": 0, "jobs": []}}, runs=[run(100, "2026-11-26T18:50:00Z", conclusion="cancelled")])
    check("4j an evicted earlier run (cancelled, no jobs) does not count", p is True, why)
    p, why = gate({"100": reached}, runs=[run(100, "2026-11-26T18:50:00Z", conclusion="cancelled")])
    check("4j2 A1/S1 an earlier run cancelled AFTER it collected (e.g. its time limit) counts as the window's cycle",
          p is False, why)
    day = [run(300 + i, iso(late - timedelta(hours=6 * i - 1)), event="workflow_dispatch", actor=BOT)
           for i in range(1, 5)]
    p, why = gate({str(300 + i): reached for i in range(1, 5)}, runs=day)
    check("4l A2 the gate applies NO rolling-24-h cap: 4 cycles in the previous 24 h (other windows) do not stand "
          "this window's first run down", p is True, why)
    p, why = gate({str(300 + i): reached for i in range(1, 4)}, runs=day[:3])
    check("4l2 three cycles in the previous 24 h and none in this window -> proceeds", p is True, why)
    # The reviewer's probe (A2): every cron within minutes of its slot; today's 18:17-window cron is 5 minutes
    # EARLIER in its window than yesterday's.
    probe = [run(1, "2026-11-26T18:25:00Z"), run(2, "2026-11-27T00:21:00Z"), run(3, "2026-11-27T06:19:00Z"),
             run(4, "2026-11-27T12:22:00Z")]
    pj = {str(i): reached for i in range(1, 5)}
    p, why = mrr.gate_collection("schedule", "auxchan", "99", T("2026-11-27T18:20:00Z"), "", probe, lambda i: pj.get(str(i)))
    check("4n A2 PROBE: a cron 5 min earlier in its window than yesterday's is the window's first cycle and proceeds",
          p is True, why)
    # Varied cron delays over consecutive days (earlier, later, the same): the first run of EVERY window proceeds and
    # a second run in the same window stands down.
    delays = [8, 3, 3, 12, 1, 40, 2, 2, 25, 0, 5, 59, 7, 7, 1, 30]          # minutes after each slot, 4 days
    hist, js, firsts, seconds = [], {}, [], []
    for k, dmin in enumerate(delays):
        slot = T("2026-11-27T00:17:00Z") + timedelta(hours=6 * k)
        first = run(500 + 2 * k, iso(slot + timedelta(minutes=dmin)))
        ok1, _ = mrr.gate_collection("schedule", "auxchan", str(first["id"]), T(first["created_at"]), "", list(hist),
                                     lambda i: js.get(str(i)))
        firsts.append(ok1)
        hist.insert(0, first)
        js[str(first["id"])] = reached
        dup = run(501 + 2 * k, iso(slot + timedelta(minutes=dmin + 90)))
        ok2, _ = mrr.gate_collection("schedule", "auxchan", str(dup["id"]), T(dup["created_at"]), "", list(hist),
                                     lambda i: js.get(str(i)))
        seconds.append(ok2)
        hist.insert(0, dup)
        js[str(dup["id"])] = stood
    check("4o A2 VARIED DELAYS over 4 days: the first run of every window proceeds", all(firsts), str(firsts))
    check("4p A2 VARIED DELAYS: a second run in the same window always stands down", not any(seconds), str(seconds))
    xl = run(401, "2026-11-26T18:50:00Z", conclusion="failure", event="workflow_dispatch", actor=BOT)
    xs = run(402, "2026-11-26T21:27:30Z")
    xr = run(400, "2026-11-26T12:40:00Z")
    g91 = {"401": lost, "402": stood, "400": reached}
    lane = wcr.decide_lane("obs-evidence-collection.yml", [xs, xl, xr], lambda i: g91.get(str(i)), lambda j: [],
                           T("2026-11-26T22:00:00Z"))
    check("4m A1/S1 G91 judges a stood-down run as skipped, so the lost run before it still gets its one re-run",
          wcr.judge(xs, lambda i: g91.get(str(i)), lambda j: []).state == "skip"
          and lane.dispatch_recovery_of == "401", f"{lane}")
    cr = {"name": "collect", "conclusion": "success"}
    check("4k did_work: a run whose collect ran counts; a stood-down or evicted one does not; doubt counts",
          mrr.did_work(run(1, "t"), {"jobs": [cr]}) and not mrr.did_work(run(1, "t"), stood)
          and not mrr.did_work(run(1, "t", conclusion="cancelled"), {"jobs": []})
          and mrr.did_work(run(1, "t"), None) and mrr.did_work(run(1, "t", status="in_progress"), {"jobs": []}))

    print("\n[5] executed: the bare script and the workflow's gate shell")
    tmp = Path(tempfile.mkdtemp(prefix="mrr-"))
    try:
        fake = tmp / "fake_gh.py"
        fake.write_text(FAKE_SRC, encoding="utf-8")
        sp = tmp / "state.json"
        st = state("2026-11-26T19:00:00Z",
                   runs={imp: live, "obs-evidence-collection.yml": [run(45781055842, "2026-11-26T08:11:20Z")]},
                   output_commit="2026-11-26T17:07:30Z")
        sp.write_text(json.dumps(st), encoding="utf-8")
        env = dict(os.environ, FAKE_GH_STATE=str(sp), PYTHONDONTWRITEBYTECODE="1")
        env.pop("GITHUB_STEP_SUMMARY", None)
        env.pop("GITHUB_OUTPUT", None)
        cmd = [sys.executable, str(SCRIPTS / "missed_run_recovery.py"), "check", "--repo", "o/r",
               "--lanes", "import,collection", "--group-members", " ".join(MEMBERS), "--now", "2026-11-26T19:00:00Z",
               "--gh", sys.executable, str(fake)]
        a = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(tmp))
        b = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(tmp))
        final = json.loads(sp.read_text(encoding="utf-8"))
        check("5a the bare script runs (sibling import resolves) and exits 0 twice", a.returncode == 0 and b.returncode == 0,
              (a.stderr + b.stderr)[-400:])
        check("5b CONCURRENT CHECKS: two checks back to back dispatch exactly once per lane",
              sorted(final["dispatches"]) == ["assessment-import.yml", "obs-evidence-collection.yml"], str(final["dispatches"]))
        check("5c the first reports dispatched, the second busy/fresh",
              "lane=import state=dispatched" in a.stdout and "lane=collection state=dispatched" in a.stdout
              and "lane=import state=busy" in b.stdout and "lane=collection state=fresh" in b.stdout, a.stdout + b.stdout)
        st["fail"] = True
        sp.write_text(json.dumps(st), encoding="utf-8")
        c = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(tmp))
        check("5d an unreachable API: no dispatch, a warning, exit 0",
              c.returncode == 0 and "::warning" in c.stdout and "state=dispatched" not in c.stdout, c.stdout[-300:])

        lag = state("2026-11-26T19:00:00Z", runs={imp: list(live)}, output_commit="2026-11-26T17:07:30Z", list_lag=3)
        polls = []
        mrr.run_check(FakeApi(lag), ["import"], MEMBERS, T(lag["now"]), polls.append)
        mrr.run_check(FakeApi(lag), ["import"], MEMBERS, T(lag["now"]), polls.append)
        check("5k a dispatched run the API lists only after a lag: the check waits for it, so the next check sees "
              "it and does not dispatch again", lag["dispatches"] == [imp] and len(polls) >= 1, f"{lag['dispatches']} polls={polls}")

        bash = shutil.which("bash")
        check("5e bash is available to execute the gate shell", bool(bash))
        step = [s for s in load("obs-evidence-collection.yml")["jobs"]["gate"]["steps"] if s.get("id") == "gate"][0]
        shell = str(step["run"])
        prefix = "python3 auxsays/scripts/missed_run_recovery.py gate"
        check("5f the gate shell calls the script's gate exactly once", shell.count(prefix) == 1, shell)
        exprs = {"${{ github.repository }}": "o/r", "${{ github.run_id }}": "200"}
        for k, v in exprs.items():
            shell = shell.replace(k, v)
        check("5g no unsubstituted expression is left in the shell", "${{" not in shell, shell)

        def run_gate(gstate, interpreter=None):
            sp.write_text(json.dumps(gstate), encoding="utf-8")
            outp = tmp / "out.txt"
            outp.write_text("", encoding="utf-8")
            sh = shell.replace(prefix, (interpreter or f'"{Path(sys.executable).as_posix()}" "{(SCRIPTS / "missed_run_recovery.py").as_posix()}" gate --gh "{Path(sys.executable).as_posix()}" "{fake.as_posix()}"'))
            genv = dict(env, GITHUB_OUTPUT=str(outp), EVENT="schedule", ACTOR="owner", RECOVERY_OF="")
            r = subprocess.run([bash, "-e", "-c", sh], capture_output=True, text=True, env=genv, cwd=str(tmp))
            return r, outp.read_text(encoding="utf-8")

        own = run(200, "2026-11-26T21:27:30Z", status="in_progress")
        g = state("2026-11-26T21:28:00Z", runs={"obs-evidence-collection.yml": [own, rec]}, jobs={"100": reached})
        r, out = run_gate(g)
        check("5h EXECUTED gate: a late cron after the window's cycle reached main writes proceed=false",
              r.returncode == 0 and out.strip() == "proceed=false", r.stdout + r.stderr + out)
        g["jobs"] = {"100": lost}
        r, out = run_gate(g)
        check("5i EXECUTED gate: after a LOST cycle in its window it also writes proceed=false (A1/S1)",
              r.returncode == 0 and out.strip() == "proceed=false", r.stdout + r.stderr + out)
        g["runs"]["obs-evidence-collection.yml"] = [own, run(100, "2026-11-26T12:50:00Z", event="workflow_dispatch", actor=BOT)]
        r, out = run_gate(g)
        check("5i2 EXECUTED gate: with only the previous window's cycle it writes proceed=true",
              r.returncode == 0 and out.strip() == "proceed=true", r.stdout + r.stderr + out)
        r, out = run_gate(g, interpreter="false")
        check("5j EXECUTED gate: a crashed guard still writes proceed=true and the step succeeds",
              r.returncode == 0 and "proceed=true" in out, r.stdout + r.stderr + out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n[6] simulated days (checks every 15 min, collection runs take 2 h)")

    def simulate(days, crons_at=(), cron_delay=None, conclusion="success", steady=False):
        """Returns per-UTC-day counts of collection runs that did the work (proceeded) and the dispatch
        count; records the per-window counts in `per_window`. `steady` starts with the previous window's
        cycle already on main (as in production) instead of a cold, empty history."""
        start = T("2026-11-27T00:00:00Z")
        prior = [run(800000, "2026-11-26T18:20:00Z")] if steady else []
        s = state(iso(start), runs={"obs-evidence-collection.yml": prior}, output_commit=None)
        jobs = {"800000": reached}
        s["jobs"] = jobs
        worked: dict[str, int] = {}
        per_window.clear()
        for k in range(days * 24 * 4):
            now = start + timedelta(minutes=15 * k)
            s["now"] = iso(now)
            runs = s["runs"]["obs-evidence-collection.yml"]
            for r in runs:                                   # finish: a run works for 2 h
                if r["status"] == "in_progress" and now - T(r["run_started_at"]) >= timedelta(hours=2):
                    r.update(status="completed", conclusion=conclusion)
                    jobs[str(r["id"])] = reached if conclusion == "success" else lost
            for r in sorted(runs, key=lambda x: x["created_at"]):   # start: the writer group runs one at a time
                if any(x["status"] == "in_progress" for x in runs):
                    break
                if r["status"] == "queued" and T(r["created_at"]) <= now:
                    proceed, _ = mrr.gate_collection(r["event"], r["triggering_actor"]["login"], str(r["id"]),
                                                     T(r["created_at"]), "", [x for x in runs if x is not r],
                                                     lambda i: jobs.get(str(i)))
                    if proceed:
                        r.update(status="in_progress", run_started_at=iso(now))
                        worked[now.strftime("%Y-%m-%d")] = worked.get(now.strftime("%Y-%m-%d"), 0) + 1
                        w = mrr.window_start(T(r["created_at"]), six, off)
                        per_window[w] = per_window.get(w, 0) + 1
                    else:
                        r.update(status="completed", conclusion="success")
                        jobs[str(r["id"])] = stood
            for slot in crons_at:                             # late crons arrive as schedule runs
                at = now.replace(hour=0, minute=0) + timedelta(hours=slot[0], minutes=slot[1]) + (cron_delay or timedelta(0))
                if now <= at < now + timedelta(minutes=15):
                    s["next_id"] = s.get("next_id", 900000) + 1
                    runs.insert(0, run(s["next_id"], iso(at), status="queued"))
            mrr.run_check(FakeApi(s), ["collection"], MEMBERS, now, NOSLEEP)
        return worked, len(s["dispatches"])

    per_window: dict = {}
    worked, n = simulate(3)
    check("6a ALL CRONS MISSING: recovery restores exactly the designed 4 cycles on every UTC day",
          set(worked.values()) == {4} and len(worked) == 3, str(worked))
    check("6a2 and never more than one cycle per designed window", max(per_window.values()) == 1, str(per_window))
    worked, n = simulate(3, crons_at=[(6, 17), (18, 17)], cron_delay=timedelta(hours=3, minutes=10), steady=True)
    check("6b LATE CRONS (3 h 10 min, as observed): still exactly 4 cycles per day, the late crons stand down",
          set(worked.values()) == {4} and max(per_window.values()) == 1, f"{worked} {per_window}")
    worked, n = simulate(3, conclusion="failure")
    check("6c PERSISTENT FAILURE: never more than 4 attempts per day (no retry storm)",
          max(worked.values()) <= 4 and n <= 12 and max(per_window.values()) == 1, f"{worked} dispatches={n}")
    for k_crons in ([(6, 17), (18, 17)], [(0, 17), (6, 17), (12, 17), (18, 17)]):
        worked, n = simulate(3, crons_at=k_crons, cron_delay=timedelta(hours=3, minutes=10), conclusion="failure",
                             steady=True)
        check(f"6c2 A1/S1 LATE CRONS + EVERY CYCLE LOST ({len(k_crons)} crons/day): one collection per window, "
              "never above 4 per day (G91's one re-run is the repair, not a second routine cycle)",
              max(worked.values()) <= 4 and max(per_window.values()) == 1, f"{worked} {per_window}")

    s = state("2026-11-26T17:20:00Z", runs={imp: list(live)}, output_commit="2026-11-26T17:07:30Z")
    dispatches_seen = 0
    for k in range(96):
        now = T("2026-11-26T17:20:00Z") + timedelta(minutes=15 * k)
        s["now"] = iso(now)
        for r in s["runs"][imp]:
            if r["status"] == "queued":
                r.update(status="completed", conclusion="failure")
        check_once(s, ["import"])
    check("6d IMPORT OUTAGE over 24 h: exactly 2 dispatches, then held", s["dispatches"].count(imp) == 2, str(s["dispatches"]))
    s = state("2026-11-26T17:20:00Z", runs={imp: list(live)}, output_commit="2026-11-26T17:07:30Z")
    for k in range(96):
        now = T("2026-11-26T17:20:00Z") + timedelta(minutes=15 * k)
        s["now"] = iso(now)
        for r in s["runs"][imp]:
            if r["status"] == "queued":
                r.update(status="completed", conclusion="cancelled")
        check_once(s, ["import"])
    check("6d2 A1/M1 HANGING IMPORT (each run hits its time limit, ends `cancelled`): 2 dispatches, then held",
          s["dispatches"].count(imp) == 2, str(s["dispatches"]))
    s = state("2026-11-26T22:12:21Z", runs={imp: list(live)}, output_commit="2026-11-26T17:07:30Z")
    for k in range(8):
        now = T("2026-11-26T22:12:21Z") + timedelta(minutes=15 * k)
        s["now"] = iso(now)
        for r in s["runs"][imp]:
            if r["status"] == "queued":
                r.update(status="completed", conclusion="success")
        dec = check_once(s, ["import"])
    check("6e SUCCESSFUL PUBLICATION: one dispatch, then fresh on every later check",
          s["dispatches"].count(imp) == 1 and dec["import"].state == "fresh", f"{s['dispatches']} {dec['import'].line()}")

    print("\n[7] structure")
    doc = load("missed-run-recovery.yml")
    conc = doc.get("concurrency") or {}
    check("7a the check serialises in its OWN group, never the writer group",
          conc.get("group") == "auxsays-missed-run-recovery" and conc.get("cancel-in-progress") is False, str(conc))
    check("7b it cannot write the repository (contents: read) and can dispatch (actions: write)",
          doc.get("permissions") == {"contents": "read", "actions": "write"}, str(doc.get("permissions")))
    names = {}
    for f in WF.glob("*.yml"):
        names[load(f.name).get("name")] = f.name
    wr = doc["on"]["workflow_run"]
    missing = [w for w in wr["workflows"] if w not in names]
    check("7c every workflow_run trigger names a workflow that exists (a typo would be silent)", not missing, str(missing))
    check("7d workflow_run is confined to main, on requested and completed runs",
          wr.get("branches") == ["main"] and wr.get("types") == ["requested", "completed"], str(wr))
    check("7e it never triggers on itself", doc.get("name") not in wr["workflows"])
    group = sorted(f.name for f in WF.glob("*.yml") if str((load(f.name).get("concurrency") or {}).get("group")) == "auxsays-main-writeback")
    mine = sorted(doc["jobs"]["check"]["env"]["GROUP_MEMBERS"].split())
    reaper = sorted(load("writer-queue-reaper.yml")["jobs"]["reap"]["env"]["GROUP_MEMBERS"].split())
    check("7f GROUP_MEMBERS equals the writer group and the reaper's list", mine == group == reaper, f"{mine} {group} {reaper}")
    run_text = strip_comments(doc["jobs"]["check"]["steps"][-1]["run"])
    check("7g the check runs both lanes with the group list",
          "missed_run_recovery.py check" in run_text and "--lanes import,collection" in run_text
          and '--group-members "${GROUP_MEMBERS}"' in run_text, run_text)
    ev = load("obs-evidence-collection.yml")["jobs"]
    check("7h collect needs the gate and runs unless it said false (or the run was cancelled)",
          ev["collect"].get("needs") == "gate"
          and ev["collect"].get("if") == "${{ !cancelled() && needs.gate.outputs.proceed != 'false' }}", str(ev["collect"].get("if")))
    check("7i the gate exports its step's proceed", ev["gate"].get("outputs") == {"proceed": "${{ steps.gate.outputs.proceed }}"})
    check("7j the PowerPoint job is skipped on a stand-down",
          ev["powerpoint-orchestrated"].get("if") == "${{ always() && needs.collect.result != 'cancelled' && needs.collect.result != 'skipped' }}",
          str(ev["powerpoint-orchestrated"].get("if")))
    check("7k chain-ingest dispatches no second ingestion on a stand-down",
          "always() && needs.collect.result != 'skipped' &&" in str(ev["chain-ingest"].get("if")), str(ev["chain-ingest"].get("if")))
    genv = (ev["gate"]["steps"][1].get("env") or {})
    check("7l the gate reads the event, the triggering actor and recovery_of",
          genv.get("EVENT") == "${{ github.event_name }}" and genv.get("ACTOR") == "${{ github.triggering_actor }}"
          and genv.get("RECOVERY_OF") == "${{ github.event.inputs.recovery_of }}", str(genv))
    check("7m the gate's fallback proceeds when the script fails",
          '|| echo "proceed=true" >> "$GITHUB_OUTPUT"' in strip_comments(ev["gate"]["steps"][1]["run"]))

    check("7n A1/S2 the gate job holds a read-only token (contents: read, actions: read)",
          ev["gate"].get("permissions") == {"contents": "read", "actions": "read"}, str(ev["gate"].get("permissions")))

    total = _passed + _failed
    print(f"\nResults: {_passed}/{total} passed, {_failed} failed")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
