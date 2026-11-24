#!/usr/bin/env python3
"""The official-record backfill queue is read back from what the official lane actually did.

`_data/patch_backfill_queue.yml` held 36 `queued` rows that nothing read or wrote. Measured at
12d207ba: 6 of them already had 1,156 records between them, 1 was an enabled source whose extractor
had matched nothing for 244 runs (Netlify), and 29 named a source that is switched off.
`execute_backfill_queue.py` runs in the ingest lane after ingestion and sets each row from facts:
complete (records exist), queued (enabled source, the lane works on it every run) or blocked (no
run can execute it), with a closed blocker vocabulary. It also pins the Netlify extractor repair
that makes the one executable row execute.

Offline: temporary fixtures, and read-only invariants over the shipped files that hold for any
commit a scheduled lane can make.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import assess_coverage  # noqa: E402
import execute_backfill_queue as q  # noqa: E402
from adapters import html_changelog as HC  # noqa: E402

PASS = 0
FAIL = 0
TOOL = str(SCRIPTS / "execute_backfill_queue.py")


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


def src(enabled: bool, adapter: str = "rss_feed") -> dict:
    return {"enabled": enabled, "ingestion": {"adapter": adapter}}


def run_suite() -> int:
    row = {"product_id": "p", "coverage_state": "active_watch", "documented_update_count": 0,
           "backfill_status": "queued"}

    # What the ingest lane records for a source whose last run was a whole pass against its
    # primary official source: the state entry, and that run's result entry.
    ok = {"last_success_at": "2026-11-24T03:01:36Z", "consecutive_failures": 0,
          "extraction_mismatch": False}
    whole = {"product_id": "p", "deferred_count": 0, "extraction_mismatch": False}

    print("D. each row is derived from facts")
    d = q.derive(row, records=234, source=src(True), state=ok, result=whole)
    check("D1 a whole pass against a reachable source, with records -> complete, with their number",
          d == {"documented_update_count": 234, "coverage_state": "documented",
                "backfill_status": "complete"}, str(d))
    d = q.derive(row, records=0, source=src(True), state=ok, result=whole)
    check("D2 an enabled source with no record yet stays queued and names its executor",
          d["backfill_status"] == "queued" and d["backfill_executor"] == "official_ingest_lane"
          and "backfill_blocker" not in d, str(d))
    d = q.derive(row, records=0, source=src(True), state={**ok, "extraction_mismatch": True}, result=whole)
    check("D3 an extractor that maps nothing is named as the blocker",
          d["backfill_status"] == "queued" and d["backfill_blocker"] == "extraction_mismatch", str(d))
    d = q.derive(row, records=0, source=src(True), state={**ok, "consecutive_failures": 3}, result=whole)
    check("D4 a failing source is named as the blocker", d.get("backfill_blocker") == "source_failing", str(d))
    d = q.derive(row, records=0, source=src(False), state={})
    check("D5 a switched-off source is blocked, not queued",
          d["backfill_status"] == "blocked" and d["backfill_blocker"] == "source_disabled"
          and "backfill_executor" not in d, str(d))
    d = q.derive(row, records=0, source=src(False, "manual_watch"), state={})
    check("D6 a watch-only source has no automated executor",
          d["backfill_status"] == "blocked" and d["backfill_blocker"] == "no_automated_source", str(d))
    d = q.derive(row, records=0, source=None, state={})
    check("D7 a product with no source is blocked", d.get("backfill_blocker") == "no_source", str(d))
    d = q.derive({**row, "coverage_state": "documented", "backfill_status": "complete"}, records=0,
                 source=src(True), state={})
    check("D8 a 'complete' row whose records are gone is queued again, never left complete",
          d["backfill_status"] == "queued" and d["coverage_state"] == "active_watch", str(d))
    # REVIEW S1. "A record exists" is not "the backfill ran": Premiere Pro had 2 records while the
    # same state recorded its official source as blocked, and read `complete`.
    premiere = {**ok, "status": "partial", "primary_last_success_at": "",
                "primary_source_error": "HTTP 403 while fetching official Adobe source",
                "primary_source_error_type": "blocked"}
    d = q.derive(row, records=2, source=src(True), state=premiere,
                 result={**whole, "primary_source_error": "HTTP 403"})
    check("D9 records with a blocked primary source are NOT complete; the count is still reported",
          d["backfill_status"] == "queued" and d["backfill_blocker"] == "primary_source_blocked"
          and d["documented_update_count"] == 2 and d["coverage_state"] == "documented", str(d))
    check("D10 every blocker the step can write is in the closed vocabulary",
          {"extraction_mismatch", "source_failing", "source_disabled", "no_automated_source", "no_source",
           "not_run", "primary_source_blocked", "no_run_result", "records_deferred"} == set(q.BLOCKERS))
    d = q.derive(row, records=2, source=src(True), state=ok, result={**whole, "deferred_count": 7})
    check("D11 a bounded run that deferred records is in progress, not complete (Netlify: 2 of 9)",
          d["backfill_status"] == "queued" and d["backfill_blocker"] == "records_deferred", str(d))
    d = q.derive(row, records=5, source=src(False), state=ok, result=whole)
    check("D12 records never make a switched-off source complete",
          d["backfill_status"] == "blocked" and d["backfill_blocker"] == "source_disabled"
          and d["documented_update_count"] == 5, str(d))
    d = q.derive(row, records=5, source=src(True), state={}, result=whole)
    check("D13 no successful run on record is not complete", d.get("backfill_blocker") == "not_run", str(d))
    d = q.derive(row, records=5, source=src(True), state=ok, result=None)
    check("D14 a row with no history and no result from this run is named, not passed",
          d["backfill_status"] == "queued" and d.get("backfill_blocker") == "no_run_result", str(d))
    d = q.derive({**row, "backfill_blocker": "records_deferred"}, records=5, source=src(True), state=ok,
                 result=None)
    check("D14b ...and a row still working through its listing stays in progress",
          d["backfill_status"] == "queued" and d.get("backfill_blocker") == "records_deferred", str(d))
    d = q.derive({**row, "backfill_status": "complete"}, records=5, source=src(True), state=ok, result=None)
    check("D15 a one-source run does not un-complete the rows it did not touch",
          d["backfill_status"] == "complete", str(d))
    d = q.derive({**row, "backfill_status": "complete"}, records=5, source=src(True), state=premiere,
                 result=None)
    check("D16 ...but a state-level fault still does", d.get("backfill_blocker") == "primary_source_blocked",
          str(d))
    # REVIEW S5. A value that is not a number must not crash the step before the writeback.
    try:
        d = q.derive(row, records=5, source=src(True), state={**ok, "consecutive_failures": "n/a"},
                     result={**whole, "deferred_count": "many"})
        soft = d["backfill_status"] == "queued" and d["backfill_blocker"] == "source_failing"
    except Exception as exc:                                  # noqa: BLE001
        soft, d = False, repr(exc)
    check("D17 a non-numeric state value fails closed and does not raise", soft, str(d))

    print("R. the command, on temporary files")
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "gen").mkdir()
        for i in range(3):
            (t / "gen" / f"2026-01-0{i + 1}-a-{i}.md").write_text(
                "---\ntitle: x\nproduct_id: prod-a\nupdate_version: '1'\n---\nbody\n", encoding="utf-8")
        queue = [{"product_id": "prod-a", "product_name": "A", "coverage_state": "active_watch",
                  "documented_update_count": 0, "backfill_status": "queued", "note": "kept"},
                 {"product_id": "prod-b", "product_name": "B", "coverage_state": "active_watch",
                  "documented_update_count": 0, "backfill_status": "queued"},
                 {"product_id": "prod-c", "product_name": "C", "coverage_state": "active_watch",
                  "documented_update_count": 0, "backfill_status": "queued"}]
        (t / "queue.yml").write_text(q.dump(queue), encoding="utf-8", newline="\n")
        (t / "sources.yml").write_text(yaml.safe_dump([
            {"product_id": "prod-a", **src(True)}, {"product_id": "prod-b", **src(True)},
            {"product_id": "prod-c", **src(False)}]), encoding="utf-8")
        (t / "state.json").write_text(json.dumps(
            {"sources": {"prod-a": ok, "prod-b": {**ok, "extraction_mismatch": True}},
             "last_results": [{**whole, "product_id": "prod-a"},
                              {**whole, "product_id": "prod-b", "extraction_mismatch": True}]}),
            encoding="utf-8")
        args = [sys.executable, TOOL, "--queue", str(t / "queue.yml"), "--sources", str(t / "sources.yml"),
                "--state", str(t / "state.json"), "--generated-dir", str(t / "gen")]
        before = (t / "queue.yml").read_bytes()
        dry = subprocess.run(args, capture_output=True, text=True)
        check("R1 without --write nothing is written",
              dry.returncode == 0 and (t / "queue.yml").read_bytes() == before, dry.stdout + dry.stderr)
        done = subprocess.run([*args, "--write"], capture_output=True, text=True)
        after = {r["product_id"]: r for r in yaml.safe_load((t / "queue.yml").read_text(encoding="utf-8"))}
        check("R2 --write records what the lane did",
              done.returncode == 0 and after["prod-a"]["backfill_status"] == "complete"
              and after["prod-a"]["documented_update_count"] == 3
              and after["prod-b"]["backfill_blocker"] == "extraction_mismatch"
              and after["prod-c"]["backfill_status"] == "blocked", done.stdout + done.stderr)
        check("R3 a row's other keys are kept and the row order is unchanged",
              after["prod-a"].get("note") == "kept" and list(after) == ["prod-a", "prod-b", "prod-c"])
        fixed = (t / "queue.yml").read_bytes()
        again = subprocess.run([*args, "--write"], capture_output=True, text=True)
        check("R4 a second run changes nothing",
              again.returncode == 0 and "0 changed" in again.stdout and (t / "queue.yml").read_bytes() == fixed)
        # The next run of the lane writes the first record for prod-b: the row completes by itself.
        (t / "gen" / "2026-02-01-b-0.md").write_text(
            "---\nproduct_id: prod-b\nupdate_version: '1'\n---\n", encoding="utf-8")
        (t / "state.json").write_text(json.dumps(
            {"sources": {"prod-a": ok, "prod-b": ok},
             "last_results": [{**whole, "product_id": "prod-a"}, {**whole, "product_id": "prod-b"}]}),
            encoding="utf-8")
        subprocess.run([*args, "--write"], capture_output=True, text=True)
        after = {r["product_id"]: r for r in yaml.safe_load((t / "queue.yml").read_text(encoding="utf-8"))}
        check("R5 a queued row completes when the lane writes its first record, with no other step",
              after["prod-b"]["backfill_status"] == "complete" and "backfill_blocker" not in after["prod-b"]
              and "backfill_executor" not in after["prod-b"], str(after["prod-b"]))
        (t / "queue.yml").write_text("not: a list\n", encoding="utf-8")
        bad = subprocess.run([*args, "--write"], capture_output=True, text=True)
        check("R6 a malformed queue is exit 2 and is not rewritten",
              bad.returncode == 2 and (t / "queue.yml").read_text(encoding="utf-8") == "not: a list\n",
              str(bad.returncode))
        # REVIEW S5. In the lane the step runs with --fail-soft: the same failure is reported in
        # the log, the job summary and the step output, the file is untouched, and the exit is 0.
        summary, output = t / "summary.md", t / "output.txt"
        env = {**os.environ, "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_OUTPUT": str(output)}
        softly = subprocess.run([*args, "--write", "--fail-soft"], capture_output=True, text=True, env=env)
        check("R7 --fail-soft: the failure does not fail the step, and the file is not rewritten",
              softly.returncode == 0 and (t / "queue.yml").read_text(encoding="utf-8") == "not: a list\n",
              str(softly.returncode) + softly.stdout[-200:])
        check("R8 --fail-soft: the failure is in the log, the job summary and the step output",
              "::error title=Backfill queue read-back failed" in softly.stdout
              and summary.exists() and "FAILED (fail-soft)" in summary.read_text(encoding="utf-8")
              and output.exists() and "status=failed" in output.read_text(encoding="utf-8"),
              softly.stdout[-300:])
        (t / "queue.yml").write_bytes(fixed)
        (t / "state.json").write_text("[1, 2]", encoding="utf-8")
        crash = subprocess.run([*args, "--write", "--fail-soft"], capture_output=True, text=True, env=env)
        check("R9 --fail-soft: a state file of the wrong shape is reported, never a traceback exit",
              crash.returncode == 0 and "::error" in crash.stdout
              and (t / "queue.yml").read_bytes() == fixed, str(crash.returncode) + crash.stdout[-200:])

    print("N. the one executable row: Netlify's extractor maps the entries its page publishes")
    base = "https://www.netlify.com/changelog/"
    netlify = {"product_id": "netlify", "company_id": "netlify",
               "ingestion": {"parser_profile": "netlify_changelog"}}
    listing = ("<a href='/changelog/2026-11-23-agent-runners-pull-request-improvements/'>A</a>"
               "<a href='/changelog/gemini-4-neon-ai-gateway-agent-runners/'>B</a>"
               "<a href='/changelog/2026/9/11/old-dated-entry/'>C</a>"
               "<a href='/changelog/tag/security/'>tag</a><a href='/changelog/page/2'>older</a>"
               "<a href='/changelog/feed.xml'>RSS</a><a href='/changelog.md'>md</a>"
               "<a href='/changelog/'>all</a><a href='https://evil.example/changelog/a-b/'>x</a>")
    links = HC._candidate_links(netlify, base, listing)
    check("N1 dated-slug, slug-only and old dated-folder entries are mapped; nothing else is",
          links == [base + "2026-11-23-agent-runners-pull-request-improvements/",
                    base + "gemini-4-neon-ai-gateway-agent-runners/",
                    base + "2026/9/11/old-dated-entry/"], str(links))
    check("N2 the listing no longer reads as an extraction mismatch",
          HC.changelog_probe(netlify, base, listing, links)["extraction_mismatch"] is False)
    check("N3 an entry's date is the one its URL states",
          HC._date_from_entry_url(links[0]) == "2026-11-23T00:00:00Z"
          and HC._date_from_entry_url(links[1]) == "", HC._date_from_entry_url(links[0]))

    print("L. the shipped files (read only)")
    queue = yaml.safe_load(q.QUEUE_PATH.read_text(encoding="utf-8"))
    sources = {str(s.get("product_id")): s
               for s in yaml.safe_load(q.SOURCES_PATH.read_text(encoding="utf-8"))}
    check("L1 every row has one of the three statuses",
          all(r.get("backfill_status") in ("complete", "queued", "blocked") for r in queue))
    stranded = [r["product_id"] for r in queue if r.get("backfill_status") == "queued"
                and not (sources.get(r["product_id"], {}).get("enabled") is True
                         and r.get("backfill_executor") == "official_ingest_lane")]
    check("L2 no row is queued without an enabled source that executes it", not stranded, str(stranded))
    unnamed = [r["product_id"] for r in queue if r.get("backfill_status") == "blocked"
               and r.get("backfill_blocker") not in q.BLOCKERS]
    check("L3 every blocked row names its blocker", not unnamed, str(unnamed))
    check("L4 the ingest workflow runs the step, so coverage no longer reports an unexecuted queue",
          assess_coverage.backfill_has_executor() is True)
    # REVIEW S1: the alarm must not go quiet for rows no run can execute.
    report = assess_coverage.assess(now=datetime.now(timezone.utc), backfill=[
        {"product_id": "off", "backfill_status": "blocked", "backfill_blocker": "source_disabled"},
        {"product_id": "stuck", "backfill_status": "queued", "backfill_blocker": "primary_source_blocked"},
        {"product_id": "busy", "backfill_status": "queued", "backfill_blocker": "records_deferred"},
        {"product_id": "done", "backfill_status": "complete"}], backfill_executor=True)
    named = sorted(p for f in report["flags"] if f["code"] == "backfill_queued" for p in f["products"])
    check("L6 with an executor, coverage still reports blocked rows and stalled rows, and only those",
          named == ["off", "stuck"], str(named))
    lane = yaml.safe_load((REPO / ".github" / "workflows" / "patch-ingest.yml").read_text(encoding="utf-8"))
    steps = [s for job in lane["jobs"].values() for s in job.get("steps", [])
             if "execute_backfill_queue.py" in str(s.get("run") or "")]
    check("L7 the lane runs the read-back fail-soft, in front of its writeback",
          len(steps) == 1 and "--fail-soft" in steps[0]["run"].split("#", 1)[0]
          and "--write" in steps[0]["run"], str([s.get("run") for s in steps]))
    # Review 2 item a: the step's status=failed is read by a step AFTER the writeback that fails the job.
    ingest = lane["jobs"]["ingest"]["steps"]
    names = [str(s.get("name") or "") for s in ingest]
    gate = [s for s in ingest if s.get("name") == "Fail the run when a fail-soft step failed"]
    check("L8 a failed read-back is the run's conclusion, read after the writeback and the cycle record",
          len(steps) == 1 and steps[0].get("id") == "backfill_queue" and len(gate) == 1
          and "always()" in str(gate[0].get("if"))
          and "steps.backfill_queue.outputs.status == 'failed'" in str(gate[0].get("if"))
          and "exit 1" in str(gate[0].get("run"))
          and names.index(gate[0]["name"]) > names.index("Cycle reached main")
          > names.index("Commit generated patch records (conflict-safe writeback)"), str(gate))
    wf = (REPO / ".github" / "workflows" / "patch-ingest.yml").read_text(encoding="utf-8")
    check("L5 the lane may commit the queue file it rewrites",
          "--allow auxsays/_data/patch_backfill_queue.yml" in wf)

    print("=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
