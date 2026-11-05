#!/usr/bin/env python3
"""Sharded CI must be the serial run, split -- never a smaller one.

ci-integrity.yml runs the governed suites as four parallel shard jobs and accepts the run only through
one `integrity` job that aggregates their receipts (AUX-070). Splitting one job into five creates new
ways for a green run to hide something the serial job could not: a suite that lands in no shard, a
shard whose failure is outvoted, a cancelled job that reads as passing, a receipt from another
commit. Each is asserted here against the real partitioner, the real runner (in real child
processes), the real aggregator and the real workflow file -- parsed, and its `run:` scalars
executed under bash, never grepped.

  [P] the partition: deterministic, disjoint, exhaustive, order-independent; hints only schedule
  [R] a shard runs every per-suite protection and writes an honest receipt outside the checkout
  [A] the aggregator rejects every failure mode, each by its named reason, and accepts only the whole
  [W] the workflow: names, matrix, `always()`, no continue-on-error, wiring between the steps
  [G] the merge authority still refuses unsuccessful, incomplete and cancelled runs

Offline: no network, no repo writes (every scratch repository lives in a temp directory).
"""
from __future__ import annotations

import copy
import fnmatch
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CI = REPO / "auxsays" / "scripts" / "ci"
RUNNER = CI / "run_integrity_tests.py"
AGGREGATOR = CI / "aggregate_integrity_receipts.py"
GATE = CI / "guarded_merge.py"
WORKFLOW = REPO / ".github" / "workflows" / "ci-integrity.yml"

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{str(detail)[:300]}]" if detail else ""))


def section(title: str) -> None:
    print()
    print("=" * 92)
    print(title)
    print("=" * 92)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod  # dataclasses (guarded_merge) resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


_LOADS = 0


def fresh_runner():
    """A private copy of the runner: its EXPECTED_CHECKS and paths are module globals."""
    global _LOADS
    _LOADS += 1
    return load(RUNNER, f"ci_runner_under_test_{_LOADS}")


def git(cwd: Path, *args: str) -> str:
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1")
    proc = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
                          cwd=cwd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout.strip()


# ==================================================================================================
# [P] the partition
# ==================================================================================================
def section_partition(runner) -> None:
    section("[P] the partition is deterministic, disjoint, exhaustive -- and hints only schedule")
    sections, problems = runner.load_manifest()
    population = [n for c in runner.EXECUTED for n in sections[c]]
    hints, default_ms = runner.load_duration_hints()
    check("P1 the shipped duration-hint table loads", isinstance(hints, dict) and default_ms > 0)

    for shards in (1, 2, 3, 4, 5, 7):
        buckets = runner.partition_suites(population, shards, hints, default_ms)
        flat = [n for b in buckets for n in b]
        check(f"P2 {shards} shard(s): disjoint and exhaustive over all {len(population)} suites",
              len(buckets) == shards and len(flat) == len(population) and set(flat) == set(population),
              f"{len(flat)} vs {len(population)}")

    a = runner.partition_suites(population, 4, hints, default_ms)
    b = runner.partition_suites(list(population), 4, dict(hints), default_ms)
    check("P3 the same manifest and hints give the same assignment", a == b)
    shuffled = list(reversed(population))
    c = runner.partition_suites(shuffled, 4, hints, default_ms)
    check("P4 a shard's SET of suites does not depend on manifest order",
          [set(x) for x in a] == [set(x) for x in c])
    position = {n: i for i, n in enumerate(population)}
    check("P5 within a shard, suites keep manifest order",
          all(x == sorted(x, key=position.__getitem__) for x in a))

    # A hint can move a suite, never remove it or add one.
    victim = population[0]
    no_hint = {k: v for k, v in hints.items() if k != victim}
    d = runner.partition_suites(population, 4, no_hint, default_ms)
    check("P6 a suite missing from the hint table is still assigned (default weight)",
          sum(x.count(victim) for x in d) == 1)
    ghost = "auxsays/scripts/tests/test_not_governed_anywhere.py"
    e = runner.partition_suites(population, 4, {**hints, ghost: 10_000_000}, default_ms)
    check("P7 a hint for a suite the manifest does not execute is ignored",
          all(ghost not in x for x in e) and e == a)
    zeroed = {k: 0 for k in hints}
    f = runner.partition_suites(population, 4, zeroed, default_ms)
    check("P8 zero weights still cover the population exactly once",
          sorted(n for x in f for n in x) == sorted(population))
    excluded = [n for c in runner.NOT_EXECUTED for n in sections[c]]
    check("P9 the partition never contains an excluded-category suite",
          not (set(excluded) & {n for x in a for n in x}), str(excluded[:3]))

    loads = [sum(hints.get(n, default_ms) for n in x) for x in a]
    heaviest = max(hints.get(n, default_ms) for n in population)
    check("P10 the shipped hints balance 4 shards within one suite's weight",
          max(loads) - min(loads) <= heaviest, f"loads(ms)={loads}")
    print(f"        balance: {[round(x / 1000, 1) for x in loads]} s, "
          f"{[len(x) for x in a]} suites")

    for bad in (0, -1, True, 2.0, "4"):
        try:
            runner.partition_suites(population, bad, hints, default_ms)
            ok = False
        except ValueError:
            ok = True
        check(f"P11 shard count {bad!r} is refused", ok)
    try:
        runner.partition_suites(population + population[:1], 4, hints, default_ms)
        ok = False
    except ValueError:
        ok = True
    check("P12 a population that names a suite twice is refused, not deduplicated", ok)

    for spec, want in (("1/4", (1, 4)), ("4/4", (4, 4)), ("1/1", (1, 1))):
        check(f"P13 --shard {spec} parses", runner.parse_shard(spec) == want)
    for spec in ("0/4", "5/4", "1/0", "a/b", "1/4/2", " 1/4", "1/4 ", "-1/4", "", "01/4", "1/04"):
        try:
            runner.parse_shard(spec)
            ok = False
        except ValueError:
            ok = True
        check(f"P14 --shard {spec!r} is refused", ok)

    with tempfile.TemporaryDirectory() as td:
        bad_tables = {
            "negative": {"default_seconds": 15, "seconds": {victim: -1}},
            "bool": {"default_seconds": 15, "seconds": {victim: True}},
            "string": {"default_seconds": 15, "seconds": {victim: "30"}},
            "zero default": {"default_seconds": 0, "seconds": {}},
            "no default": {"seconds": {}},
            "seconds not a map": {"default_seconds": 15, "seconds": [victim]},
            "top level a list": [],
        }
        for label, table in bad_tables.items():
            p = Path(td) / "hints.json"
            p.write_text(json.dumps(table), encoding="utf-8")
            try:
                runner.load_duration_hints(p)
                ok = False
            except ValueError:
                ok = True
            check(f"P15 a malformed hint table ({label}) is refused", ok)
        p = Path(td) / "nan.json"
        p.write_text('{"default_seconds": 15, "seconds": {"x": NaN}}', encoding="utf-8")
        try:
            runner.load_duration_hints(p)
            ok = False
        except ValueError:
            ok = True
        check("P15 a malformed hint table (NaN) is refused", ok)

    raw = json.loads(runner.HINTS.read_text(encoding="utf-8"))
    check("P16 the hint table holds seconds and nothing that could govern a suite",
          set(raw) <= {"about", "source", "default_seconds", "seconds"}
          and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                  for v in raw["seconds"].values()), str(sorted(raw)))


# ==================================================================================================
# [R] the runner in shard mode, in real child processes, over a scratch repository
# ==================================================================================================
DRIVER = r'''
import importlib.util, os, sys
from pathlib import Path
runner_path, repo, *argv = sys.argv[1:]
spec = importlib.util.spec_from_file_location("ci_runner_driven", runner_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.REPO = Path(repo)
mod.TESTS = Path(repo) / "auxsays" / "scripts" / "tests"
mod.MANIFEST = Path(repo) / "auxsays" / "scripts" / "ci" / "integrity_suites.txt"
mod.HINTS = Path(repo) / "auxsays" / "scripts" / "ci" / "suite_duration_hints.json"
if os.environ.get("SCRATCH_SUITE_TIMEOUT"):
    mod.PER_TEST_TIMEOUT = float(os.environ["SCRATCH_SUITE_TIMEOUT"])
raise SystemExit(mod.main(argv))
'''

SUITES = {
    "ok_a": ("print('Results: 2/2 passed, 0 failed')\n", 2),
    "ok_b": ("print('Results: 3/3 passed, 0 failed')\n", 3),
    "ok_c": ("print('Results: 1/1 passed, 0 failed')\n", 1),
    "ok_d": ("print('Results: 4/4 passed, 0 failed')\n", 4),
}


class Scratch:
    """A throwaway git repository shaped like this one: suites, manifest, hints."""

    def __init__(self, suites: dict[str, tuple[str, int]], hints: dict[str, float] | None = None,
                 ignore: tuple[str, ...] = ()):
        self.root = Path(tempfile.mkdtemp(prefix="auxsays-shard-repo-"))
        self.out = Path(tempfile.mkdtemp(prefix="auxsays-shard-out-"))
        self.driver = self.out / "driver.py"
        self.driver.write_text(DRIVER, encoding="utf-8")
        tests = self.root / "auxsays" / "scripts" / "tests"
        ci = self.root / "auxsays" / "scripts" / "ci"
        tests.mkdir(parents=True)
        ci.mkdir(parents=True)
        lines = ["[blocking]"]
        self.paths = {}
        for key, (body, count) in suites.items():
            rel = f"auxsays/scripts/tests/test_scratch_{key}.py"
            (self.root / rel).write_text(body, encoding="utf-8")
            lines.append(f"{rel} = {count}")
            self.paths[key] = rel
        (ci / "integrity_suites.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        table = {"default_seconds": 5, "seconds": {self.paths[k]: v for k, v in (hints or {}).items()}}
        (ci / "suite_duration_hints.json").write_text(json.dumps(table), encoding="utf-8")
        if ignore:
            (self.root / ".gitignore").write_text("\n".join(ignore) + "\n", encoding="utf-8")
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "scratch")
        self.head = git(self.root, "rev-parse", "HEAD")

    def run(self, *args: str, receipt: str | None = "r.json", env: dict | None = None):
        path = (self.out / receipt) if receipt else None
        argv = [sys.executable, str(self.driver), str(RUNNER), str(self.root), *args]
        if path is not None:
            argv += ["--receipt", str(path)]
        full_env = dict(os.environ, GITHUB_RUN_ID="777", GITHUB_RUN_ATTEMPT="1",
                        PYTHONDONTWRITEBYTECODE="1", **(env or {}))
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=full_env, timeout=300)
        data = None
        if path is not None and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        return proc, data

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.out, ignore_errors=True)


def section_runner(aggregator) -> None:
    section("[R] a shard runs every per-suite protection and writes an honest receipt")

    # --- R1: a clean 2-shard world, end to end through the real aggregator -----------------------
    progressive = textwrap.dedent("""
        import json, os
        r = json.load(open(os.environ["SCRATCH_RECEIPT"], encoding="utf-8"))
        ok = r["completion_state"] == "running" and len(r["suites"]) >= 1
        print("Results: %d/1 passed, %d failed" % (1 if ok else 0, 0 if ok else 1))
        raise SystemExit(0 if ok else 1)
        """)
    suites = dict(SUITES, progressive=(progressive, 1))
    world = Scratch(suites, hints={"ok_a": 30, "ok_b": 20, "ok_c": 10})  # ok_d, progressive unhinted
    try:
        rcpt = {}
        procs = {}
        for i in (1, 2):
            env = {"SCRATCH_RECEIPT": str(world.out / f"shard{i}.json")}
            procs[i], rcpt[i] = world.run("--suite", "all", "--shard", f"{i}/2",
                                          receipt=f"shard{i}.json", env=env)
        runner = fresh_runner()
        runner.REPO = world.root
        runner.MANIFEST = world.root / "auxsays/scripts/ci/integrity_suites.txt"
        runner.HINTS = world.root / "auxsays/scripts/ci/suite_duration_hints.json"
        sections, _ = runner.load_manifest()
        population = sections["blocking"]
        hints, default_ms = runner.load_duration_hints()
        expected = runner.partition_suites(population, 2, hints, default_ms)
        check("R1.1 both shards exit 0", all(procs[i].returncode == 0 for i in (1, 2)),
              {i: (procs[i].returncode, procs[i].stdout[-300:], procs[i].stderr[-300:]) for i in (1, 2)})
        check("R1.2 each receipt names its shard, total, commit, run and manifest digest",
              all(rcpt[i] and rcpt[i]["shard"] == {"index": i, "total": 2}
                  and rcpt[i]["commit"] == world.head and rcpt[i]["run_id"] == "777"
                  and rcpt[i]["manifest_digest"] == runner.file_digest(runner.MANIFEST)
                  and rcpt[i]["hints_digest"] == runner.file_digest(runner.HINTS) for i in (1, 2)))
        check("R1.3 each shard ran exactly its own slice of the partition",
              all([s["path"] for s in rcpt[i]["suites"]] == expected[i - 1]
                  and rcpt[i]["assigned"] == expected[i - 1] for i in (1, 2)),
              str([[s["path"][-14:] for s in rcpt[i]["suites"]] for i in (1, 2)]))
        union = [s["path"] for i in (1, 2) for s in rcpt[i]["suites"]]
        check("R1.4 the shards' union is the population, each suite exactly once",
              sorted(union) == sorted(population) and len(union) == len(set(union)))
        check("R1.5 a suite with no duration hint still ran",
              world.paths["ok_d"] in union and world.paths["progressive"] in union)
        recs = {s["path"]: s for i in (1, 2) for s in rcpt[i]["suites"]}
        check("R1.6 every suite record carries its governed count, totals and exit status",
              all(recs[world.paths[k]]["expected_checks"] == suites[k][1]
                  and recs[world.paths[k]]["total"] == suites[k][1]
                  and recs[world.paths[k]]["passed"] == suites[k][1]
                  and recs[world.paths[k]]["exit_status"] == 0
                  and recs[world.paths[k]]["verdict"] == "pass" for k in suites))
        check("R1.7 the receipt is complete, clean and records exit 0",
              all(rcpt[i]["completion_state"] == "complete" and rcpt[i]["mutation_check"] == "clean"
                  and rcpt[i]["exit_code"] == 0 and rcpt[i]["suites_failed"] == 0 for i in (1, 2)))
        check("R1.8 the receipt is rewritten after each suite (a later suite read it as `running`)",
              recs[world.paths["progressive"]]["verdict"] == "pass")
        check("R1.9 writing the receipt left the scratch checkout untouched",
              git(world.root, "status", "--porcelain", "-uall") == "")

        rdir = world.out / "receipts"
        for i in (1, 2):
            d = rdir / aggregator.artifact_name(i, 2)
            d.mkdir(parents=True)
            shutil.copy(world.out / f"shard{i}.json", d / "receipt.json")
        res = aggregator.aggregate(rdir, shards=2, needs_result="success", own_commit=world.head,
                                   expected_commit=world.head, run_id="777", runner=runner)
        check("R1.10 the real aggregator accepts the real runner's receipts",
              res["accepted"] and not res["reasons"], res["reasons"])
        check("R1.11 ... and its totals are the manifest's",
              res["population"] == len(population) and res["executed_once"] == len(population)
              and res["governed_checks"] == sum(c for _, c in suites.values())
              and res["observed_checks"] == res["governed_checks"])
        res = aggregator.aggregate(rdir, shards=2, needs_result="success", own_commit=world.head,
                                   run_id="778", runner=runner)
        check("R1.12 the same receipts are refused for a different run", not res["accepted"]
              and "WRONG_RUN" in {c for c, _ in res["reasons"]})

        proc, data = world.run("--suite", "all", "--shard", "1/2",
                               receipt=None, env={})
        check("R1.13 a shard without --receipt still runs (and writes nothing)",
              proc.returncode == 0 and not any(world.out.glob("*.partial")))
        inside = world.root / "receipt.json"
        argv = [sys.executable, str(world.driver), str(RUNNER), str(world.root), "--suite", "all",
                "--shard", "1/2", "--receipt", str(inside)]
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
        check("R1.14 a receipt path inside the checkout is refused before any suite runs",
              proc.returncode == 4 and not inside.exists() and "[ 1/" not in proc.stdout,
              f"rc={proc.returncode} {proc.stdout[-200:]} {proc.stderr[-200:]}")
        for spec in ("3/2", "0/2", "x"):
            proc, data = world.run("--suite", "all", "--shard", spec, receipt=f"bad{spec[0]}.json")
            check(f"R1.15 --shard {spec} exits 4 and writes no receipt",
                  proc.returncode == 4 and data is None, f"rc={proc.returncode}")
        proc, data = world.run("--suite", "all", "--shard", "6/6", receipt="empty.json")
        check("R1.16 a shard assigned no suites fails rather than passing empty",
              proc.returncode == 3 and data is None, f"rc={proc.returncode}")
        (world.root / "auxsays/scripts/ci/suite_duration_hints.json").write_text("{", encoding="utf-8")
        proc, data = world.run("--suite", "all", "--shard", "1/2", receipt="badhints.json")
        check("R1.17 a malformed hint table fails the shard (exit 3)",
              proc.returncode == 3 and data is None, f"rc={proc.returncode}")
    finally:
        world.close()

    # --- R2: every per-suite protection still decides each suite's verdict inside a shard ---------
    mixed = {
        "good": ("print('Results: 2/2 passed, 0 failed')\n", 2),
        "failing": ("print('  FAIL  a real assertion')\nprint('Results: 1/2 passed, 1 failed')\n"
                    "raise SystemExit(1)\n", 2),
        "drift": ("print('Results: 3/3 passed, 0 failed')\n", 5),
        "silent": ("print('nothing to see')\n", 1),
        "liar": ("print('  FAIL  hidden')\nprint('Results: 2/2 passed, 0 failed')\n", 2),
        "nonzero": ("print('Results: 1/1 passed, 0 failed')\nraise SystemExit(3)\n", 1),
        "hung": ("import time\ntime.sleep(20)\nprint('Results: 1/1 passed, 0 failed')\n", 1),
    }
    world = Scratch(mixed)
    try:
        proc, r = world.run("--suite", "all", "--shard", "1/1", env={"SCRATCH_SUITE_TIMEOUT": "2"})
        recs = {s["path"]: s for s in (r or {}).get("suites", [])}

        def rec(key: str) -> dict:
            return recs.get(world.paths[key], {})

        check("R2.1 a shard with failing suites exits 1 and its receipt says so",
              proc.returncode == 1 and r and r["exit_code"] == 1 and r["suites_failed"] == 6
              and r["completion_state"] == "complete", f"rc={proc.returncode}")
        check("R2.2 a clean suite still passes beside them", rec("good").get("verdict") == "pass")
        check("R2.3 a failing suite is recorded as failed with its counts",
              rec("failing").get("verdict") == "fail" and rec("failing").get("failed") == 1
              and rec("failing").get("exit_status") == 1)
        check("R2.4 governed check count: 3 checks against a declared 5 fails",
              rec("drift").get("verdict") == "fail" and rec("drift").get("total") == 3
              and rec("drift").get("expected_checks") == 5 and "DRIFT" in rec("drift").get("detail", ""))
        check("R2.5 required Results line: none printed is a failure with no total",
              rec("silent").get("verdict") == "fail" and rec("silent").get("total") is None
              and "NO RESULTS LINE" in rec("silent").get("detail", ""))
        check("R2.6 printed failure detection: FAIL lines beside '0 failed' fail",
              rec("liar").get("verdict") == "fail" and "INCONSISTENT" in rec("liar").get("detail", ""))
        check("R2.7 process exit status: a nonzero exit fails a clean summary",
              rec("nonzero").get("verdict") == "fail" and rec("nonzero").get("exit_status") == 3)
        check("R2.8 timeout handling: a hung suite times out, with no exit status",
              rec("hung").get("verdict") == "fail" and rec("hung").get("timed_out") is True
              and rec("hung").get("exit_status") is None)
    finally:
        world.close()

    # --- R3: the mutation guard, tracked and watched-ignored, inside a shard -----------------------
    writes_tracked = ("from pathlib import Path\n"
                      "Path('auxsays/scripts/tests/test_scratch_ok_a.py').write_text('x')\n"
                      "print('Results: 1/1 passed, 0 failed')\n")
    writes_ignored = ("from pathlib import Path\n"
                      "p = Path('auxsays/_data/qa_status.json'); p.parent.mkdir(parents=True, exist_ok=True)\n"
                      "p.write_text('{}')\n"
                      "print('Results: 1/1 passed, 0 failed')\n")
    for label, body in (("a tracked file", writes_tracked), ("a watched gitignored file", writes_ignored)):
        world = Scratch({"ok_a": SUITES["ok_a"], "writer": (body, 1)},
                        ignore=("auxsays/_data/qa_status.json",))
        try:
            proc, r = world.run("--suite", "all", "--shard", "1/1")
            check(f"R3 a suite that writes {label} makes the shard exit 2, receipt `mutated`",
                  proc.returncode == 2 and r and r["mutation_check"] == "mutated"
                  and r["exit_code"] == 2, f"rc={proc.returncode} {r and r['mutation_check']}")
        finally:
            world.close()


# ==================================================================================================
# [A] the aggregator
# ==================================================================================================
OWN = "c" * 40


class ReceiptSet:
    """A valid receipt set for the REAL governed population, mutated one way per scenario."""

    def __init__(self, runner, aggregator, shards: int = 4):
        self.runner, self.agg, self.shards = runner, aggregator, shards
        sections, _ = runner.load_manifest()
        self.population = [n for c in runner.EXECUTED for n in sections[c]]
        self.excluded = [n for c in runner.NOT_EXECUTED for n in sections[c]]
        self.counts = {n: runner.EXPECTED_CHECKS[n] for n in self.population}
        hints, default_ms = runner.load_duration_hints()
        self.assignment = runner.partition_suites(self.population, shards, hints, default_ms)
        md, hd = runner.file_digest(runner.MANIFEST), runner.file_digest(runner.HINTS)
        self.receipts = {}
        for i, slice_ in enumerate(self.assignment, 1):
            self.receipts[aggregator.artifact_name(i, shards)] = {
                "schema": runner.RECEIPT_SCHEMA, "shard": {"index": i, "total": shards},
                "category": "all", "commit": OWN, "run_id": "4242", "run_attempt": "1",
                "manifest_digest": md, "hints_digest": hd, "population": len(self.population),
                "assigned": list(slice_), "suites": [self.record(n) for n in slice_],
                "completion_state": "complete", "mutation_check": "clean", "suites_failed": 0,
                "exit_code": 0, "started_at": "2026-11-05T00:00:00Z",
                "finished_at": "2026-11-05T00:08:00Z",
            }
        self.raw: dict[str, bytes] = {}       # artifact -> raw receipt bytes overriding the dict
        self.extra_files: dict[str, str] = {}  # relative path -> content

    def clone(self) -> "ReceiptSet":
        twin = copy.copy(self)
        twin.receipts = copy.deepcopy(self.receipts)
        twin.raw, twin.extra_files = {}, {}
        return twin

    def record(self, name: str) -> dict:
        n = self.counts.get(name, 7)
        return {"path": name, "expected_checks": n, "verdict": "pass", "passed": n, "failed": 0,
                "total": n, "skipped": 0, "exit_status": 0, "timed_out": False,
                "detail": f"{n}/{n}", "seconds": 1.5}

    def shard(self, i: int) -> dict:
        return self.receipts[self.agg.artifact_name(i, self.shards)]

    def write(self, root: Path) -> Path:
        rdir = root / "receipts"
        rdir.mkdir()
        for name, receipt in self.receipts.items():
            d = rdir / name
            d.mkdir()
            if receipt is None:
                continue
            data = self.raw.get(name) or (json.dumps(receipt, indent=1) + "\n").encode("utf-8")
            (d / "receipt.json").write_bytes(data)
        for rel, content in self.extra_files.items():
            p = rdir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return rdir


def section_aggregator(runner, aggregator) -> None:
    section("[A] the aggregator rejects every failure mode by name, and accepts only the whole")
    reached: set[str] = set()
    pristine = ReceiptSet(runner, aggregator, shards=4)

    def judge(mutate=None, *, needs="success", own=OWN, expected=None, run_id="4242", shards=4,
              agg_runner=None, before_write=None):
        rs = pristine.clone()
        if mutate:
            mutate(rs)
        with tempfile.TemporaryDirectory() as td:
            rdir = rs.write(Path(td))
            if before_write:
                before_write(rdir)
            return aggregator.aggregate(rdir, shards=shards, needs_result=needs, own_commit=own,
                                        expected_commit=expected, run_id=run_id,
                                        runner=agg_runner or runner)

    def refuses(label: str, code: str, mutate=None, **kw) -> None:
        res = judge(mutate, **kw)
        codes = {c for c, _ in res["reasons"]}
        reached.update(codes & {code})
        check(f"A {label} -> {code}", not res["accepted"] and code in codes,
              f"accepted={res['accepted']} codes={sorted(codes)}")

    base = judge()
    check("A0.1 a complete, valid receipt set is accepted", base["accepted"] and not base["reasons"],
          base["reasons"][:4])
    rs = pristine
    check("A0.2 ... covering the governed population with its governed totals",
          base["executed_once"] == base["population"] == len(rs.population)
          and base["observed_checks"] == base["governed_checks"] == sum(rs.counts.values()),
          f"{base['executed_once']}/{base['population']} {base['observed_checks']}/{base['governed_checks']}")
    res = judge(lambda r: r.shard(2)["suites"][0].update(skipped=3))
    check("A0.3 skipped assertions inside a passing suite are allowed (the runner surfaces them)",
          res["accepted"], res["reasons"][:3])
    res = judge(lambda r: [r.shard(i).update(run_id=None) for i in range(1, 5)], run_id=None)
    check("A0.4 run ids are not required when the caller names no run", res["accepted"])

    # -- the jobs' own verdict, and cancellation
    for needs in ("failure", "cancelled", "skipped", "", "Success"):
        refuses(f"needs.shard.result={needs!r} outvotes clean receipts", "SHARD_JOB_NOT_SUCCESS",
                needs=needs)

    # -- the manifest authority
    broken = fresh_runner()
    with tempfile.TemporaryDirectory() as td:
        dup = Path(td) / "integrity_suites.txt"
        first = rs.population[0]
        dup.write_text(runner.MANIFEST.read_text(encoding="utf-8") + f"\n[stale]\n{first}\n",
                       encoding="utf-8")
        broken.MANIFEST = dup
        refuses("a manifest that classifies a suite twice", "MANIFEST_INVALID", agg_runner=broken)
        bad_hints = fresh_runner()
        hp = Path(td) / "hints.json"
        hp.write_text('{"default_seconds": -1, "seconds": {}}', encoding="utf-8")
        bad_hints.HINTS = hp
        refuses("a malformed duration-hint table", "MANIFEST_INVALID", agg_runner=bad_hints)

    # -- artifacts and receipts
    refuses("a missing shard artifact", "MISSING_ARTIFACT",
            lambda r: r.receipts.pop(aggregator.artifact_name(3, 4)))
    refuses("an absent receipts directory", "MISSING_ARTIFACT",
            before_write=lambda d: shutil.rmtree(d))
    refuses("an artifact with no receipt in it", "MISSING_RECEIPT",
            lambda r: r.receipts.update({aggregator.artifact_name(2, 4): None}))
    refuses("a stray artifact beside the shards", "UNEXPECTED_ARTIFACT",
            lambda r: r.extra_files.update({"something-else/receipt.json": "{}"}))
    refuses("a stray file beside the receipt", "UNEXPECTED_ARTIFACT",
            lambda r: r.extra_files.update({aggregator.artifact_name(1, 4) + "/notes.txt": "x"}))
    refuses("a loose file in the receipts directory", "UNEXPECTED_ARTIFACT",
            lambda r: r.extra_files.update({"receipt.json": "{}"}))
    # download-artifact extracts flat, with no artifact directory, when exactly one artifact matches.
    flat = json.dumps(pristine.shard(1))
    refuses("one surviving artifact extracted flat by download-artifact", "UNEXPECTED_ARTIFACT",
            lambda r: (r.receipts.clear(), r.extra_files.update({"receipt.json": flat})))
    refuses("an artifact for shard 5 of 4", "UNEXPECTED_SHARD",
            lambda r: r.extra_files.update({"integrity-receipt-shard-5-of-4/receipt.json": "{}"}))
    refuses("an artifact from a 3-shard layout", "UNEXPECTED_SHARD",
            lambda r: r.extra_files.update({"integrity-receipt-shard-1-of-3/receipt.json": "{}"}))

    a2 = aggregator.artifact_name(2, 4)
    for label, raw in (("invalid JSON", b"{not json"), ("a JSON array", b"[]"),
                       ("non-UTF-8 bytes", b"\xff\xfe\x00"),
                       ("a NaN", None)):
        def mut(r, raw=raw, label=label):
            if raw is None:
                text = json.dumps(r.shard(2)).replace('"seconds": 1.5', '"seconds": NaN', 1)
                r.raw[a2] = text.encode("utf-8")
            else:
                r.raw[a2] = raw
        refuses(f"a receipt that is {label}", "MALFORMED_RECEIPT", mut)
    refuses("a receipt missing a field", "MALFORMED_RECEIPT", lambda r: r.shard(2).pop("exit_code"))
    refuses("a receipt with an unknown field", "MALFORMED_RECEIPT",
            lambda r: r.shard(2).update(verdict_override="pass"))
    refuses("a receipt with a boolean (false == 0) for an exit code", "MALFORMED_RECEIPT",
            lambda r: r.shard(2).update(exit_code=False))
    refuses("a suite record with a string count", "MALFORMED_RECEIPT",
            lambda r: r.shard(2)["suites"][0].update(total="12"))
    refuses("a suite record missing its exit status", "MALFORMED_RECEIPT",
            lambda r: r.shard(2)["suites"][0].pop("exit_status"))
    refuses("a receipt of another schema", "MALFORMED_RECEIPT",
            lambda r: r.shard(2).update(schema="auxsays-integrity-shard-receipt/0"))
    refuses("a receipt.json that is a directory", "MALFORMED_RECEIPT",
            lambda r: (r.receipts.update({a2: None}),
                       r.extra_files.update({a2 + "/receipt.json/x": "{}"})))

    def relabel(r):
        r.receipts[aggregator.artifact_name(3, 4)] = copy.deepcopy(r.shard(2))
    refuses("shard 3's artifact holding shard 2's receipt", "ARTIFACT_RECEIPT_MISMATCH", relabel)
    refuses("two receipts claiming shard 2", "DUPLICATE_SHARD", relabel)
    refuses("no receipt claiming shard 3", "MISSING_SHARD", relabel)
    refuses("a receipt claiming shard 2 of 5", "UNEXPECTED_SHARD",
            lambda r: r.shard(2)["shard"].update(total=5))

    # -- provenance
    refuses("a receipt from another commit", "WRONG_COMMIT",
            lambda r: r.shard(4).update(commit="d" * 40))
    refuses("a receipt with no commit", "WRONG_COMMIT", lambda r: r.shard(4).update(commit=None))
    refuses("a checkout whose commit is unknown", "WRONG_COMMIT", own=None)
    # Receipts that name no commit agree with a checkout that cannot name one: None == None. Only the
    # checkout-side check stands between that pair and an acceptance.
    refuses("an unknown checkout commit beside receipts that name none either", "WRONG_COMMIT",
            lambda r: [r.shard(i).update(commit=None) for i in range(1, 5)], own=None)
    refuses("a checkout that is not the commit the event names", "WRONG_COMMIT", expected="e" * 40)
    refuses("a receipt from another run", "WRONG_RUN", lambda r: r.shard(1).update(run_id="1"))
    refuses("a receipt against another manifest", "WRONG_MANIFEST_DIGEST",
            lambda r: r.shard(3).update(manifest_digest="sha256:" + "0" * 64))
    refuses("a receipt partitioned with other hints", "WRONG_HINTS_DIGEST",
            lambda r: r.shard(3).update(hints_digest="sha256:" + "0" * 64))
    refuses("a receipt that partitioned only the blocking category", "WRONG_CATEGORY",
            lambda r: r.shard(1).update(category="blocking"))

    # -- shard state
    def truncated(r):
        s = r.shard(2)
        s.update(completion_state="running", exit_code=None, suites_failed=None,
                 mutation_check="not_run", finished_at=None)
        s["suites"] = s["suites"][:3]
    refuses("a shard killed mid-run (receipt still `running`)", "SHARD_INCOMPLETE", truncated)
    refuses("a shard that exited 1", "SHARD_FAILED", lambda r: r.shard(1).update(exit_code=1))
    refuses("a shard reporting a failed suite with exit 0", "SHARD_FAILED",
            lambda r: r.shard(1).update(suites_failed=1))
    for state in ("mutated", "unavailable", "not_run"):
        refuses(f"a shard whose checkout check is {state!r}", "CHECKOUT_MUTATED",
                lambda r, state=state: r.shard(3).update(mutation_check=state))

    # -- the suites themselves: omitted, duplicated, reclassified, undercounted
    def drop(r):
        r.shard(2)["suites"].pop(1)
    refuses("a suite omitted from its shard", "MISSING_SUITE", drop)
    refuses("a suite omitted from its shard", "INCOMPLETE_COVERAGE", drop)

    def drop_everywhere(r):
        victim = r.shard(2)["assigned"][1]
        r.shard(2)["assigned"].remove(victim)
        r.shard(2)["suites"] = [s for s in r.shard(2)["suites"] if s["path"] != victim]
    refuses("a suite removed from both a shard's slice and its runs", "MISASSIGNED_SUITE",
            drop_everywhere)
    refuses("a suite removed from both a shard's slice and its runs", "INCOMPLETE_COVERAGE",
            drop_everywhere)

    def twice_in_shard(r):
        r.shard(1)["suites"].append(copy.deepcopy(r.shard(1)["suites"][0]))
    refuses("a suite run twice in one shard", "DUPLICATE_SUITE", twice_in_shard)

    def twice_across(r):
        r.shard(2)["suites"].append(copy.deepcopy(r.shard(1)["suites"][0]))
    refuses("a suite run in two shards", "DUPLICATE_SUITE", twice_across)
    refuses("a suite run in a shard it does not belong to", "MISASSIGNED_SUITE", twice_across)

    def swap(r):
        a, b = r.shard(1), r.shard(2)
        x, y = a["suites"].pop(0), b["suites"].pop(0)
        a["suites"].append(y)
        b["suites"].append(x)
        a["assigned"] = [s["path"] for s in a["suites"]]
        b["assigned"] = [s["path"] for s in b["suites"]]
    res = judge(swap)
    codes = {c for c, _ in res["reasons"]}
    check("A two shards that swapped a suite (the union of what ran is still complete) "
          "-> MISASSIGNED_SUITE", not res["accepted"] and "MISASSIGNED_SUITE" in codes, sorted(codes))
    reached.update(codes & {"MISASSIGNED_SUITE"})

    excluded = rs.excluded[0] if rs.excluded else "auxsays/scripts/tests/test_x.py"
    refuses("a suite from an excluded category reported as run", "EXTRA_SUITE",
            lambda r: r.shard(4)["suites"].append(r.record(excluded)))
    refuses("an invented suite reported as run", "EXTRA_SUITE",
            lambda r: r.shard(4)["suites"].append(r.record("auxsays/scripts/tests/test_invented.py")))

    def undercount(r):
        s = r.shard(3)["suites"][0]
        n = s["total"] - 1
        s.update(expected_checks=n, total=n, passed=n, detail=f"{n}/{n}")
    refuses("a receipt that lowered a suite's governed count to match", "COUNT_MISMATCH", undercount)

    def misstated(r):
        s = r.shard(3)["suites"][0]
        s.update(expected_checks=s["expected_checks"] - 1)  # ran the governed count, claims another
    refuses("a receipt that misstates a suite's governed count", "COUNT_MISMATCH", misstated)

    def ran_fewer(r):
        s = r.shard(3)["suites"][1]
        n = s["total"] - 2
        s.update(total=n, passed=n)
    refuses("a suite that ran fewer checks than governed", "COUNT_MISMATCH", ran_fewer)

    def ran_more(r):
        s = r.shard(3)["suites"][1]
        n = s["total"] + 2
        s.update(total=n, passed=n)
    refuses("a suite that ran more checks than governed", "COUNT_MISMATCH", ran_more)
    refuses("a suite that timed out", "SUITE_INCOMPLETE",
            lambda r: r.shard(1)["suites"][2].update(timed_out=True, exit_status=None))
    refuses("a suite with no Results line", "SUITE_INCOMPLETE",
            lambda r: r.shard(1)["suites"][2].update(total=None, passed=0))
    for label, change in (("judged a failure", {"verdict": "fail"}),
                          ("with a failed check", {"failed": 1}),
                          ("whose passes do not add up", {"passed": 0}),
                          ("that exited 1", {"exit_status": 1}),
                          ("with no exit status", {"exit_status": None})):
        refuses(f"a suite {label}", "SUITE_FAILED",
                lambda r, change=change: r.shard(4)["suites"][0].update(change))
    refuses("a failed suite leaves coverage incomplete", "INCOMPLETE_COVERAGE",
            lambda r: r.shard(4)["suites"][0].update(verdict="fail"))

    check("A9 every refusal code the aggregator defines was reached by a negative case above",
          reached == set(aggregator.REASONS), f"unreached={sorted(set(aggregator.REASONS) - reached)}")

    # The CLI, as a child process: a crash or bad argument is never a pass.
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run([sys.executable, str(AGGREGATOR), "--receipts", td, "--shards", "4"],
                              capture_output=True, text=True)
        check("A10 the CLI refuses to run without --needs-result", proc.returncode not in (0,),
              f"rc={proc.returncode}")
        proc = subprocess.run([sys.executable, str(AGGREGATOR), "--receipts", td, "--shards", "0",
                               "--needs-result", "success"], capture_output=True, text=True)
        check("A11 the CLI refuses --shards 0", proc.returncode == 2, f"rc={proc.returncode}")


# ==================================================================================================
# [W] the workflow, parsed and executed
# ==================================================================================================
FAKE_PYTHON = r"""#!/usr/bin/env bash
printf '%s\n' "$@" > "$SIM_ARGS"
exit 0
"""


def eval_expr(text: str, ctx: dict) -> str:
    """`${{ a.b }}` lookups only; anything else raises, so a new expression fails loudly."""
    def one(match):
        expr = match.group(1).strip()
        if not re.fullmatch(r"[a-z_]+(\.[a-z_]+)+", expr):
            raise ValueError(f"unsupported expression: {expr}")
        cur = ctx
        for part in expr.split("."):
            cur = cur[part]
        return str(cur)
    return re.sub(r"\$\{\{(.*?)\}\}", one, text)


def bash_run(script: str, env: dict, cwd: Path, fake_python: bool = False) -> tuple[int, list[str], str]:
    tmp = Path(tempfile.mkdtemp(prefix="auxsays-wf-"))
    try:
        sh = tmp / "step.sh"
        sh.write_text(script, encoding="utf-8", newline="\n")
        args_file = tmp / "args.txt"
        full = dict(os.environ)
        full.update(env)
        full["SIM_ARGS"] = str(args_file)
        if fake_python:
            fp = tmp / "python"
            fp.write_text(FAKE_PYTHON, encoding="utf-8", newline="\n")
            fp.chmod(fp.stat().st_mode | stat.S_IEXEC)
            full["PATH"] = str(tmp) + os.pathsep + full.get("PATH", "")
        # Exactly how GitHub runs a `run:` step under `shell: bash`: errexit and pipefail on. W33 pins
        # that ci-integrity.yml declares that shell, so this is how CI really runs its steps.
        proc = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", str(sh)],
                              cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=full, timeout=300)
        args = args_file.read_text(encoding="utf-8").splitlines() if args_file.exists() else []
        return proc.returncode, args, proc.stdout + proc.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def walk_keys(node, key: str) -> int:
    if isinstance(node, dict):
        return sum((k == key) + walk_keys(v, key) for k, v in node.items())
    if isinstance(node, list):
        return sum(walk_keys(v, key) for v in node)
    return 0


def section_workflow(runner, aggregator, gate) -> None:
    import yaml

    section("[W] the workflow: names, matrix, always(), and the wiring between steps -- executed")
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = wf.get("jobs") or {}
    shard, final = jobs.get("shard") or {}, jobs.get("integrity") or {}
    rel = WORKFLOW.relative_to(REPO).as_posix()
    check("W1 workflow name and path are the ones guarded_merge.py governs",
          wf.get("name") == "CI integrity" and rel == gate.GOVERNED_WORKFLOW_PATH, f"{wf.get('name')} {rel}")
    triggers = wf.get(True) or wf.get("on") or {}
    check("W2 it still runs on pull_request", "pull_request" in triggers, str(triggers))
    check("W3 exactly two jobs: the shards and the aggregate", sorted(jobs) == ["integrity", "shard"],
          str(sorted(jobs)))
    check("W4 the final job keeps the stable check name `integrity`", final.get("name") == "integrity")
    needs = final.get("needs")
    check("W5 the final job needs the shard job", needs in ("shard", ["shard"]), str(needs))
    cond = str(final.get("if", "")).replace("${{", "").replace("}}", "").strip()
    check("W6 the final job runs under always(), so it can never be skipped green", cond == "always()",
          repr(final.get("if")))
    check("W7 nothing in the workflow uses continue-on-error", walk_keys(wf, "continue-on-error") == 0)
    strategy = shard.get("strategy") or {}
    matrix = strategy.get("matrix") or {}
    values = matrix.get("shard") or []
    n = len(values)
    check("W8 the matrix is exactly shard: [1..N] -- no include/exclude", set(matrix) == {"shard"}
          and values == list(range(1, n + 1)) and n == 4, str(matrix))
    check("W9 fail-fast is off, so every shard reaches its own verdict",
          strategy.get("fail-fast") is False)
    names = [eval_expr(str(shard.get("name", "")), {"matrix": {"shard": i}}) for i in values]
    check("W10 no shard job can take the name `integrity`",
          all(x != "integrity" and x for x in names) and len(set(names)) == n, str(names))
    check("W11 both jobs are time-bounded",
          isinstance(shard.get("timeout-minutes"), int) and isinstance(final.get("timeout-minutes"), int))

    ssteps = {s.get("name"): s for s in shard.get("steps", [])}
    fsteps = [s.get("name") for s in final.get("steps", [])]
    fmap = {s.get("name"): s for s in final.get("steps", [])}
    sorder = [s.get("name") for s in shard.get("steps", [])]
    manifest_run = "python auxsays/scripts/ci/run_integrity_tests.py --check-manifest"
    check("W12 both jobs run the closed-world manifest check",
          ssteps.get("Verify the test manifest is closed-world", {}).get("run") == manifest_run
          and fmap.get("Verify the test manifest is closed-world", {}).get("run") == manifest_run)
    run_step = ssteps.get("Run integrity suites (this shard)", {})
    upload = ssteps.get("Upload the shard receipt", {})
    check("W13 a shard checks the manifest, runs, proves its checkout, then uploads -- in that order",
          sorder.index("Verify the test manifest is closed-world")
          < sorder.index("Run integrity suites (this shard)")
          < sorder.index("Prove the checkout was not modified")
          < sorder.index("Upload the shard receipt") if "Upload the shard receipt" in sorder else False,
          str(sorder))
    check("W14 the shard index reaches the shell through env, not interpolation",
          (run_step.get("env") or {}).get("SHARD") == "${{ matrix.shard }}"
          and "${{" not in str(run_step.get("run", "")))

    # Execute the shard step against a fake python and read back exactly what it was asked to run.
    temp = "/runner/temp"
    passed_args = []
    for i in values:
        rc, args, out = bash_run(str(run_step.get("run", "")),
                                 {"SHARD": str(i), "RUNNER_TEMP": temp}, REPO, fake_python=True)
        passed_args.append((rc, args))
    want = [["auxsays/scripts/ci/run_integrity_tests.py", "--suite", "all", "--shard", f"{i}/{n}",
             "--receipt", f"{temp}/integrity-receipt/receipt.json"] for i in values]
    check("W15 executed: each shard runs `--suite all --shard I/N --receipt <runner temp>`",
          [a for _, a in passed_args] == want and all(rc == 0 for rc, _ in passed_args),
          str(passed_args[:1]))
    receipt_path = f"{temp}/integrity-receipt/receipt.json"
    up = upload.get("with") or {}
    ctx = {"runner": {"temp": temp}}
    check("W16 the upload always runs and ships exactly the receipt the runner wrote",
          str(upload.get("if", "")).strip() == "always()"
          and str(upload.get("uses", "")).startswith("actions/upload-artifact@")
          and eval_expr(str(up.get("path", "")), ctx) == receipt_path
          and up.get("if-no-files-found") == "error", str(upload))
    art = [eval_expr(str(up.get("name", "")), {"matrix": {"shard": i}}) for i in values]
    check("W17 one uniquely named artifact per shard, the names the aggregator expects",
          art == [aggregator.artifact_name(i, n) for i in values] and len(set(art)) == n, str(art))
    check("W18 the receipt is written outside the checkout (runner temp, never the workspace)",
          "$RUNNER_TEMP/" in str(run_step.get("run", "")) and "GITHUB_WORKSPACE" not in str(run_step))

    download = fmap.get("Download the shard receipts", {})
    dwith = download.get("with") or {}
    dl_path = eval_expr(str(dwith.get("path", "")), ctx)
    check("W19 the download fetches every shard artifact into runner temp, one directory each",
          str(download.get("uses", "")).startswith("actions/download-artifact@")
          and all(fnmatch.fnmatchcase(a, str(dwith.get("pattern", ""))) for a in art)
          and not dwith.get("merge-multiple") and "name" not in dwith
          and dl_path.startswith(temp + "/"), str(dwith))
    agg = fmap.get("Aggregate the shard receipts", {})
    check("W20 the aggregate reads needs.shard.result through env",
          (agg.get("env") or {}).get("SHARD_RESULT") == "${{ needs.shard.result }}"
          and "${{" not in str(agg.get("run", "")))
    rc, args, out = bash_run(str(agg.get("run", "")),
                             {"RUNNER_TEMP": temp, "SHARD_RESULT": "success", "GITHUB_SHA": "a" * 40,
                              "GITHUB_RUN_ID": "99"}, REPO, fake_python=True)

    def arg(flag: str):
        return args[args.index(flag) + 1] if flag in args else None
    check("W21 executed: the aggregate gets the download dir, N, the needs result, commit and run",
          args[:1] == ["auxsays/scripts/ci/aggregate_integrity_receipts.py"]
          and arg("--receipts") == dl_path and arg("--shards") == str(n)
          and arg("--needs-result") == "success" and arg("--expected-commit") == "a" * 40
          and arg("--run-id") == "99", str(args))

    downstream = ["Audit consensus evidence", "Validate generated records (read-only)",
                  "Validate ingestion sources", "Validate evidence method health",
                  "Refuse unexplained evidence loss", "Prove the checkout was not modified"]
    present = all(d in fsteps for d in downstream)
    check("W22 every downstream gate runs in the final job, after aggregation, in its original order",
          present and fsteps.index("Download the shard receipts") < fsteps.index("Aggregate the shard receipts")
          < fsteps.index(downstream[0])
          and [fsteps.index(d) for d in downstream] == sorted(fsteps.index(d) for d in downstream),
          str(fsteps))
    check("W23 no downstream gate carries an `if:` that could skip it",
          present and all("if" not in fmap[d] for d in downstream))
    check("W24 the downstream gates' commands are unchanged",
          fmap.get("Audit consensus evidence", {}).get("run")
          == "python auxsays/scripts/audit_consensus_evidence.py"
          and fmap.get("Validate generated records (read-only)", {}).get("run")
          == "python auxsays/scripts/qa_patch_records.py --read-only --publish-strict"
          and fmap.get("Validate ingestion sources", {}).get("run")
          == "python auxsays/scripts/validate_ingestion_sources.py"
          and fmap.get("Validate evidence method health", {}).get("run")
          == "python auxsays/scripts/validate_evidence_method_health.py"
          and "check_evidence_loss.py --base \"$BASE\"" in
          str(fmap.get("Refuse unexplained evidence loss", {}).get("run")))
    last = final.get("steps", [{}])[-1]
    check("W25 the last step re-checks needs.shard.result under always()",
          last.get("name") == "Require every shard job to have succeeded"
          and str(last.get("if", "")).strip() == "always()"
          and (last.get("env") or {}).get("SHARD_RESULT") == "${{ needs.shard.result }}")
    outcomes = {}
    for result in ("success", "failure", "cancelled", "skipped", ""):
        rc, _, _ = bash_run(str(last.get("run", "")), {"SHARD_RESULT": result}, REPO)
        outcomes[result] = rc
    check("W26 executed: that step passes only for `success` -- a cancelled run cannot end green",
          outcomes["success"] == 0 and all(outcomes[r] != 0 for r in outcomes if r != "success"),
          str(outcomes))
    # bash_run executes every step under -eo pipefail. That is what CI does only if the workflow
    # names the shell: with none named, GitHub runs `bash -e`, without pipefail.
    check("W33 every step runs under bash -eo pipefail, as bash_run simulates: defaults.run.shell is bash "
          "and no job or step overrides it",
          (wf.get("defaults") or {}).get("run") == {"shell": "bash"}
          and all("defaults" not in job for job in jobs.values())
          and walk_keys(wf, "shell") == 1, str(wf.get("defaults")))

    # The aggregate step, executed with the REAL python and aggregator, against receipts built for
    # this checkout's real HEAD.
    head = runner.head_commit()
    check("W27 this checkout's commit is readable (the aggregate needs it)", head is not None)
    if head is None:
        return
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        rs = ReceiptSet(runner, aggregator)
        for r in rs.receipts.values():
            r["commit"] = head
            r["run_id"] = "99"
        rdir = rs.write(tdp)
        os.replace(rdir, tdp / "integrity-receipts")
        summary = tdp / "summary.md"
        base_env = {"RUNNER_TEMP": tdp.as_posix(), "GITHUB_SHA": head, "GITHUB_RUN_ID": "99",
                    "GITHUB_STEP_SUMMARY": str(summary)}
        rc_ok, _, out_ok = bash_run(str(agg.get("run", "")), {**base_env, "SHARD_RESULT": "success"}, REPO)
        check("W28 executed for real: a complete receipt set for this commit is accepted",
              rc_ok == 0 and "AGGREGATE ACCEPTED" in out_ok, out_ok[-400:])
        check("W29 ... and the governed totals land in the step summary",
              summary.exists() and "AGGREGATE ACCEPTED" in summary.read_text(encoding="utf-8"))
        rc, _, out = bash_run(str(agg.get("run", "")), {**base_env, "SHARD_RESULT": "cancelled"}, REPO)
        check("W30 executed for real: the same receipts with a cancelled shard job are rejected",
              rc == 1 and "SHARD_JOB_NOT_SUCCESS" in out, f"rc={rc}")
        rc, _, out = bash_run(str(agg.get("run", "")),
                              {**base_env, "SHARD_RESULT": "success", "GITHUB_SHA": "f" * 40}, REPO)
        check("W31 executed for real: receipts for a commit the event does not name are rejected",
              rc == 1 and "WRONG_COMMIT" in out, f"rc={rc}")
        shutil.rmtree(tdp / "integrity-receipts" / aggregator.artifact_name(4, n))
        rc, _, out = bash_run(str(agg.get("run", "")), {**base_env, "SHARD_RESULT": "success"}, REPO)
        check("W32 executed for real: a missing shard artifact is rejected",
              rc == 1 and "MISSING_ARTIFACT" in out, f"rc={rc}")


# ==================================================================================================
# [G] the merge authority
# ==================================================================================================
def section_gate(gate) -> None:
    section("[G] guarded_merge.py still refuses unsuccessful, incomplete and cancelled runs")
    head = "b" * 40
    pr = {"state": "open", "draft": False, "base": {"ref": "main"}, "mergeable": True,
          "mergeable_state": "clean", "head": {"sha": head}}

    def run(conclusion, status="completed", event="pull_request", rid=1):
        return {"id": rid, "path": gate.GOVERNED_WORKFLOW_PATH, "head_sha": head, "event": event,
                "status": status, "conclusion": conclusion, "pull_requests": [{"number": 9}]}

    def verdict(runs):
        return gate.decide(pr, head, runs, number=9)

    v = verdict([run("success")])
    check("G1 a successful pull_request run of ci-integrity.yml is accepted", v.allowed, v.render())
    for conclusion in ("cancelled", "failure", "timed_out", "skipped", "startup_failure", "neutral"):
        v = verdict([run(conclusion)])
        check(f"G2 a {conclusion} run is refused", not v.allowed and v.code == "run_not_success",
              v.render())
    v = verdict([run(None, status="in_progress")])
    check("G3 a run still in progress (shards running) is refused", not v.allowed
          and v.code == "run_incomplete", v.render())
    v = verdict([run(None, status="queued")])
    check("G4 a queued run is refused", not v.allowed and v.code == "run_incomplete", v.render())
    v = verdict([])
    check("G5 no run at all is refused", not v.allowed and v.code == "no_required_run", v.render())
    v = verdict([run("success", rid=2), run("failure", event="workflow_dispatch", rid=3)])
    check("G6 a failing run of the same commit vetoes a green one", not v.allowed, v.render())
    v = verdict([run("success", event="workflow_dispatch")])
    check("G7 a green that is not this PR's pull_request run is refused", not v.allowed, v.render())


def main() -> int:
    runner = fresh_runner()
    aggregator = load(AGGREGATOR, "ci_aggregator_under_test")
    gate = load(GATE, "ci_guarded_merge_under_test")
    for fn, args in ((section_partition, (runner,)),
                     (section_runner, (aggregator,)),
                     (section_aggregator, (runner, aggregator)),
                     (section_workflow, (runner, aggregator, gate)),
                     (section_gate, (gate,))):
        try:
            fn(*args)
        except Exception:  # a crashed section is a failure, reported, and the rest still run
            check(f"{fn.__name__} ran to completion", False, traceback.format_exc()[-600:])
    print()
    if FAILURES:
        print("Failed: " + "; ".join(FAILURES)[:2000])
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
