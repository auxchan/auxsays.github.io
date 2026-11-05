#!/usr/bin/env python3
"""Accept a sharded integrity run only as one complete, governed whole.

ci-integrity.yml runs the governed suites as N parallel shard jobs, and each shard writes a receipt
of exactly what it ran (run_integrity_tests.py --shard I/N --receipt PATH). This script is the only
place those receipts become a verdict, and it trusts none of them about what SHOULD have run:

  * it loads integrity_suites.txt from its own checkout, re-validates the closed world, and takes
    the governed population and every governed check count from there;
  * it recomputes the partition itself, so a shard that ran someone else's slice is caught even
    when the union happens to come out right;
  * it accepts only when the suites that individually passed every check are EXACTLY that
    population, each exactly once, with the governed number of checks -- a partial result is a
    rejection, never a smaller pass;
  * it is told the shard jobs' own result (`needs.shard.result`) and refuses anything but success,
    so a cancelled or failed job cannot be outvoted by receipts that happen to look clean.

Every refusal has a code in REASONS. The verdict is computed positively (complete coverage, one
valid receipt per shard, no reason recorded), so a check that is accidentally skipped cannot
produce an acceptance on its own.

Usage (the workflow passes all of these):
    python auxsays/scripts/ci/aggregate_integrity_receipts.py --receipts DIR --shards 4 \\
        --needs-result success [--expected-commit SHA] [--run-id ID]

DIR holds one sub-directory per artifact, `integrity-receipt-shard-<I>-of-<N>/receipt.json`, which
is how actions/download-artifact lays out several artifacts.

Exit codes: 0 accepted; 1 rejected; 2 this script failed (never a pass).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run_integrity_tests.py"
RECEIPT_FILE = "receipt.json"
ARTIFACT_RE = re.compile(r"integrity-receipt-shard-([0-9]+)-of-([0-9]+)")

ACCEPTED = 0
REJECTED = 1
ERROR = 2

# Every way this aggregator refuses. The suite test_ci_integrity_sharding.py drives a negative case
# for each code and requires the set of codes it reached to equal this set.
REASONS = {
    "MANIFEST_INVALID": "the manifest or duration-hint table in this checkout is not valid",
    "SHARD_JOB_NOT_SUCCESS": "the shard jobs did not all succeed (failed, cancelled or skipped)",
    "MISSING_ARTIFACT": "an expected shard artifact is absent",
    "UNEXPECTED_ARTIFACT": "something other than one receipt per shard artifact was delivered",
    "MISSING_RECEIPT": "a shard artifact holds no receipt",
    "MALFORMED_RECEIPT": "a receipt is not valid JSON of the receipt schema",
    "ARTIFACT_RECEIPT_MISMATCH": "an artifact holds the receipt of a different shard",
    "DUPLICATE_SHARD": "two receipts claim the same shard",
    "MISSING_SHARD": "a shard of 1..N has no receipt",
    "UNEXPECTED_SHARD": "a receipt or artifact names a shard outside 1..N of N",
    "WRONG_CATEGORY": "a receipt partitioned something other than the full executed population",
    "WRONG_COMMIT": "a receipt was produced on a different commit (or the commit is unknown)",
    "WRONG_RUN": "a receipt was produced by a different workflow run",
    "WRONG_MANIFEST_DIGEST": "a receipt was produced against a different manifest",
    "WRONG_HINTS_DIGEST": "a receipt was partitioned with a different duration-hint table",
    "SHARD_INCOMPLETE": "a shard did not finish (its receipt is still `running`)",
    "SHARD_FAILED": "a shard reported failing suites or a nonzero exit",
    "CHECKOUT_MUTATED": "a shard's repository-mutation check was not clean",
    "MISASSIGNED_SUITE": "a shard ran, or was assigned, a slice other than its own",
    "MISSING_SUITE": "a shard did not execute a suite assigned to it",
    "DUPLICATE_SUITE": "a suite was executed more than once",
    "EXTRA_SUITE": "a suite outside the governed population was executed",
    "COUNT_MISMATCH": "a suite's checks differ from its governed count",
    "SUITE_INCOMPLETE": "a suite timed out or printed no Results line",
    "SUITE_FAILED": "a suite failed checks, exited nonzero or was judged a failure",
    "INCOMPLETE_COVERAGE": "the suites that passed are not the whole governed population",
}

# The receipt schema, closed: a missing key, an extra key or a wrong type is MALFORMED_RECEIPT.
_STR, _INT, _BOOL, _NONE = (str,), (int,), (bool,), (type(None),)
TOP_FIELDS = {
    "schema": _STR, "shard": (dict,), "category": _STR, "commit": _STR + _NONE,
    "run_id": _STR + _NONE, "run_attempt": _STR + _NONE, "manifest_digest": _STR,
    "hints_digest": _STR + _NONE, "population": _INT, "assigned": (list,), "suites": (list,),
    "completion_state": _STR, "mutation_check": _STR, "suites_failed": _INT + _NONE,
    "exit_code": _INT + _NONE, "started_at": _STR, "finished_at": _STR + _NONE,
}
SHARD_FIELDS = {"index": _INT, "total": _INT}
SUITE_FIELDS = {
    "path": _STR, "expected_checks": _INT + _NONE, "verdict": _STR, "passed": _INT, "failed": _INT,
    "total": _INT + _NONE, "skipped": _INT, "exit_status": _INT + _NONE, "timed_out": _BOOL,
    "detail": _STR, "seconds": (int, float),
}


def artifact_name(index: int, total: int) -> str:
    return f"integrity-receipt-shard-{index}-of-{total}"


def load_runner():
    """The runner, loaded by path: this file runs as a bare script, so no package import."""
    spec = importlib.util.spec_from_file_location("auxsays_integrity_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {RUNNER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _typed(value, kinds: tuple) -> bool:
    # bool is an int subclass: True must never pass for a count or an exit status.
    if isinstance(value, bool) and bool not in kinds:
        return False
    return isinstance(value, kinds)


def _schema_errors(obj, fields: dict, where: str) -> list[str]:
    if not isinstance(obj, dict):
        return [f"{where} is not an object"]
    errors = [f"{where} lacks `{k}`" for k in fields if k not in obj]
    errors += [f"{where} has unexpected `{k}`" for k in obj if k not in fields]
    errors += [f"{where}.{k} has type {type(obj[k]).__name__}" for k, kinds in fields.items()
               if k in obj and not _typed(obj[k], kinds)]
    return errors


def _reject_constant(token: str):
    raise ValueError(f"non-finite number {token} in receipt")


def parse_receipt(raw: bytes, schema_id: str) -> tuple[dict | None, list[str]]:
    """(receipt, problems). Any problem means the receipt is not used at all."""
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        return None, [f"not valid JSON: {exc}"]
    problems = _schema_errors(data, TOP_FIELDS, "receipt")
    if problems:
        return None, problems
    problems = _schema_errors(data["shard"], SHARD_FIELDS, "receipt.shard")
    for i, suite in enumerate(data["suites"]):
        problems += _schema_errors(suite, SUITE_FIELDS, f"receipt.suites[{i}]")
    if not all(isinstance(p, str) for p in data["assigned"]):
        problems.append("receipt.assigned holds a non-string")
    if data["schema"] != schema_id:
        problems.append(f"receipt.schema is {data['schema']!r}, expected {schema_id!r}")
    return (None, problems) if problems else (data, [])


def aggregate(receipts_dir: Path, *, shards: int, needs_result: str, own_commit: str | None,
              expected_commit: str | None = None, run_id: str | None = None, runner=None) -> dict:
    """Pure apart from reading files. Returns the verdict and everything it was decided from."""
    runner = load_runner() if runner is None else runner
    reasons: list[tuple[str, str]] = []

    def reject(code: str, detail: str) -> None:
        if code not in REASONS:  # a typo here must fail loudly, never mint a silent no-op
            raise KeyError(code)
        reasons.append((code, detail))

    result = {"accepted": False, "reasons": reasons, "shards": [], "population": 0,
              "governed_checks": 0, "observed_checks": 0, "executed_once": 0}

    # 1. The authority: this checkout's manifest, never anything a receipt says about it.
    sections, problems = runner.load_manifest()
    errors = runner.validate_manifest(sections, problems)
    population = [n for cat in runner.EXECUTED for n in sections[cat]]
    governed = {n: runner.EXPECTED_CHECKS.get(n) for n in population}
    if errors or not population or any(v is None for v in governed.values()):
        reject("MANIFEST_INVALID", "; ".join(errors)[:400] or "no governed population")
        return result
    try:
        hints, default_ms = runner.load_duration_hints()
        assignment = runner.partition_suites(population, shards, hints, default_ms)
    except (OSError, ValueError, AssertionError) as exc:
        reject("MANIFEST_INVALID", f"duration hints / partition: {exc}")
        return result
    manifest_digest = runner.file_digest(runner.MANIFEST)
    hints_digest = runner.file_digest(runner.HINTS)
    result["population"] = len(population)
    result["governed_checks"] = sum(governed.values())
    pop_set = set(population)

    # 2. The jobs' own verdict. Receipts cannot outvote a failed or cancelled job.
    if needs_result != "success":
        reject("SHARD_JOB_NOT_SUCCESS", f"needs.shard.result is {needs_result!r}")

    # 3. The commit this checkout is, and the one the event says it should be.
    if not own_commit:
        reject("WRONG_COMMIT", "this checkout's commit could not be determined")
    elif expected_commit is not None and expected_commit != own_commit:
        reject("WRONG_COMMIT", f"checkout is {own_commit[:12]}, the event names {expected_commit[:12]}")

    # 4. Artifacts: exactly one directory per shard, each holding exactly one receipt.
    receipts: list[tuple[str, dict]] = []
    seen_artifacts: set[str] = set()
    if not receipts_dir.is_dir():
        reject("MISSING_ARTIFACT", f"receipts directory {receipts_dir} does not exist")
        entries = []
    else:
        entries = sorted(receipts_dir.iterdir(), key=lambda p: p.name)
    for entry in entries:
        match = ARTIFACT_RE.fullmatch(entry.name)
        if not entry.is_dir() or match is None:
            reject("UNEXPECTED_ARTIFACT", f"{entry.name} is not a shard receipt artifact")
            continue
        a_index, a_total = int(match.group(1)), int(match.group(2))
        if a_total != shards or not 1 <= a_index <= shards:
            reject("UNEXPECTED_SHARD", f"artifact {entry.name} is not one of the {shards} shards")
            continue
        seen_artifacts.add(entry.name)
        inside = sorted(p.name for p in entry.iterdir())
        if RECEIPT_FILE not in inside:
            reject("MISSING_RECEIPT", f"artifact {entry.name} holds no {RECEIPT_FILE}")
            continue
        if inside != [RECEIPT_FILE]:
            reject("UNEXPECTED_ARTIFACT", f"artifact {entry.name} holds {inside}")
        receipt_file = entry / RECEIPT_FILE
        if not receipt_file.is_file():
            reject("MALFORMED_RECEIPT", f"{entry.name}/{RECEIPT_FILE} is not a file")
            continue
        receipt, problems = parse_receipt(receipt_file.read_bytes(), runner.RECEIPT_SCHEMA)
        if receipt is None:
            reject("MALFORMED_RECEIPT", f"{entry.name}: " + "; ".join(problems)[:300])
            continue
        r_index, r_total = receipt["shard"]["index"], receipt["shard"]["total"]
        if (r_index, r_total) != (a_index, a_total):
            reject("ARTIFACT_RECEIPT_MISMATCH",
                   f"artifact {entry.name} holds the receipt of shard {r_index}/{r_total}")
        receipts.append((entry.name, receipt))
    for index in range(1, shards + 1):
        if artifact_name(index, shards) not in seen_artifacts:
            reject("MISSING_ARTIFACT", f"no artifact {artifact_name(index, shards)}")

    # 5. Shard identity, from what each receipt says it ran.
    by_index = Counter(r["shard"]["index"] for _, r in receipts)
    for index, count in sorted(by_index.items()):
        if count > 1:
            reject("DUPLICATE_SHARD", f"{count} receipts claim shard {index}")
    for index in range(1, shards + 1):
        if by_index.get(index, 0) == 0:
            reject("MISSING_SHARD", f"no receipt for shard {index}/{shards}")

    # 6. Each receipt on its own.
    executed_anywhere: Counter = Counter()   # every execution, wherever it happened
    shards_running: Counter = Counter()      # how many receipts ran each suite at all
    succeeded: Counter = Counter()
    observed_checks = 0
    unique_valid = 0
    for name, r in receipts:
        index, total = r["shard"]["index"], r["shard"]["total"]
        tag = f"shard {index}/{total}"
        before = len(reasons)
        if total != shards or not 1 <= index <= shards:
            reject("UNEXPECTED_SHARD", f"{name} claims {tag}, outside 1..{shards} of {shards}")
            continue
        own_slice = assignment[index - 1]
        if r["category"] != "all":
            reject("WRONG_CATEGORY", f"{tag} partitioned category {r['category']!r}, not 'all'")
        if r["commit"] != own_commit:
            reject("WRONG_COMMIT", f"{tag} ran on {str(r['commit'])[:12]}, checkout is "
                                   f"{str(own_commit)[:12]}")
        if run_id is not None and r["run_id"] != run_id:
            reject("WRONG_RUN", f"{tag} came from run {r['run_id']}, this is run {run_id}")
        if r["manifest_digest"] != manifest_digest:
            reject("WRONG_MANIFEST_DIGEST", f"{tag} used manifest {r['manifest_digest'][:19]}")
        if r["hints_digest"] != hints_digest:
            reject("WRONG_HINTS_DIGEST", f"{tag} used hints {str(r['hints_digest'])[:19]}")
        if r["completion_state"] != "complete":
            reject("SHARD_INCOMPLETE", f"{tag} completion_state is {r['completion_state']!r}")
        if r["exit_code"] != 0 or r["suites_failed"] != 0:
            reject("SHARD_FAILED", f"{tag} exit_code={r['exit_code']} "
                                   f"suites_failed={r['suites_failed']}")
        if r["mutation_check"] != "clean":
            reject("CHECKOUT_MUTATED", f"{tag} mutation_check is {r['mutation_check']!r}")
        if r["assigned"] != own_slice:
            reject("MISASSIGNED_SUITE", f"{tag} was assigned {len(r['assigned'])} suite(s) that "
                                        f"are not its slice of {len(own_slice)}")

        paths = [s["path"] for s in r["suites"]]
        shards_running.update(set(paths))
        for path, count in Counter(paths).items():
            if count > 1:
                reject("DUPLICATE_SUITE", f"{tag} ran {path} {count} times")
        slice_set = set(own_slice)
        for path in sorted(slice_set - set(paths)):
            reject("MISSING_SUITE", f"{tag} did not run {path}")

        for s in r["suites"]:
            path = s["path"]
            executed_anywhere[path] += 1
            if path not in pop_set:
                reject("EXTRA_SUITE", f"{tag} ran {path}, which is not governed")
                continue
            if path not in slice_set:
                reject("MISASSIGNED_SUITE", f"{tag} ran {path}, which belongs to another shard")
                continue
            ok = True
            want = governed[path]
            if s["expected_checks"] != want:
                reject("COUNT_MISMATCH", f"{path}: receipt expected {s['expected_checks']}, "
                                         f"manifest governs {want}")
                ok = False
            if s["timed_out"] or s["total"] is None:
                reject("SUITE_INCOMPLETE", f"{path}: " + ("timed out" if s["timed_out"]
                                                          else "no Results line"))
                ok = False
            else:
                if s["total"] != want:
                    reject("COUNT_MISMATCH", f"{path}: ran {s['total']} checks, governed {want}")
                    ok = False
                if (s["verdict"] != "pass" or s["failed"] != 0 or s["passed"] != s["total"]
                        or s["exit_status"] != 0):
                    reject("SUITE_FAILED", f"{path}: verdict={s['verdict']} passed={s['passed']} "
                                           f"failed={s['failed']} total={s['total']} "
                                           f"exit={s['exit_status']}")
                    ok = False
            if ok:
                succeeded[path] += 1
                observed_checks += s["total"]
        if len(reasons) == before and by_index[index] == 1:
            unique_valid += 1
        result["shards"].append({
            "index": index, "artifact": name, "suites": len(r["suites"]),
            "checks": sum(s["total"] or 0 for s in r["suites"]),
            "seconds": round(sum(float(s["seconds"]) for s in r["suites"]), 1),
            "state": r["completion_state"], "exit_code": r["exit_code"],
        })

    # 7. Across receipts: the union of passing suites must be the population, each exactly once.
    for path, count in sorted(shards_running.items()):
        if count > 1:
            reject("DUPLICATE_SUITE", f"{path} executed in {count} shards")
    uncovered = sorted(pop_set - set(succeeded))
    if uncovered:
        shown = ", ".join(uncovered[:8]) + (f" and {len(uncovered) - 8} more" if len(uncovered) > 8
                                            else "")
        reject("INCOMPLETE_COVERAGE", f"{len(uncovered)} of {len(pop_set)} governed suite(s) have "
                                      f"no passing receipt: {shown}")
    result["observed_checks"] = observed_checks
    result["executed_once"] = sum(1 for p in population if succeeded.get(p) == 1
                                  and executed_anywhere.get(p) == 1)

    # 8. The verdict, asserted positively rather than inferred from an empty reason list.
    complete = (set(succeeded) == pop_set
                and all(succeeded[p] == 1 and executed_anywhere[p] == 1 for p in population)
                and sum(executed_anywhere.values()) == len(population)
                and observed_checks == result["governed_checks"]
                and unique_valid == shards == len(receipts)
                and needs_result == "success")
    if not complete and not reasons:
        # Unreachable while every named check above holds; kept so that a weakened check can
        # never turn "not proven complete" into an acceptance with an empty reason list.
        reject("INCOMPLETE_COVERAGE", "the positive completeness test failed with no named reason")
    result["accepted"] = complete and not reasons
    return result


def render(result: dict, shards: int) -> list[str]:
    lines = ["AUXSAYS integrity aggregate -- " + str(shards) + " shard(s)", "=" * 84]
    for s in sorted(result["shards"], key=lambda x: (x["index"], x["artifact"])):
        lines.append(f"  shard {s['index']}/{shards}  {s['suites']:>3} suite(s)  {s['checks']:>5} "
                     f"checks  {s['seconds']:>7.1f}s  state={s['state']}  exit={s['exit_code']}")
    secs = [s["seconds"] for s in result["shards"]]
    lines.append("=" * 84)
    lines.append(f"governed suites    : {result['population']}")
    lines.append(f"executed once, pass: {result['executed_once']}")
    lines.append(f"governed checks    : {result['governed_checks']}")
    lines.append(f"passing checks     : {result['observed_checks']}")
    if secs:
        lines.append(f"shard suite time   : max {max(secs):.1f}s  min {min(secs):.1f}s  "
                     f"spread {max(secs) - min(secs):.1f}s  sum {sum(secs):.1f}s")
    if result["reasons"]:
        lines.append("")
        lines.append(f"REJECTED -- {len(result['reasons'])} reason(s):")
        for code, detail in result["reasons"]:
            lines.append(f"  {code}: {detail}")
    lines.append("")
    lines.append("AGGREGATE ACCEPTED" if result["accepted"] else "AGGREGATE REJECTED")
    return lines


def _write_step_summary(lines: list[str]) -> None:
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    try:
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("### CI integrity aggregate\n\n```\n" + "\n".join(lines) + "\n```\n")
    except OSError:
        pass  # presentation only; the exit code below is the verdict


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--receipts", required=True, type=Path,
                    help="directory holding one integrity-receipt-shard-<I>-of-<N>/ per artifact")
    ap.add_argument("--shards", required=True, type=int, help="how many shards the workflow ran")
    ap.add_argument("--needs-result", required=True,
                    help="needs.<shard job>.result from the workflow; anything but success rejects")
    ap.add_argument("--expected-commit", default=None,
                    help="the commit the event names (GITHUB_SHA); must equal this checkout")
    ap.add_argument("--run-id", default=None, help="this workflow run's id (GITHUB_RUN_ID)")
    args = ap.parse_args(argv)
    if args.shards < 1:
        print("--shards must be >= 1", file=sys.stderr)
        return ERROR

    runner = load_runner()
    result = aggregate(args.receipts, shards=args.shards, needs_result=args.needs_result,
                       own_commit=runner.head_commit(),
                       expected_commit=args.expected_commit or None,
                       run_id=args.run_id or None, runner=runner)
    lines = render(result, args.shards)
    print("\n".join(lines))
    _write_step_summary(lines)
    return ACCEPTED if result["accepted"] else REJECTED


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:  # a crash is never a pass
        import traceback
        traceback.print_exc()
        raise SystemExit(ERROR)
