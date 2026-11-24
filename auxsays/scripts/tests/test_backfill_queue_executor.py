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

    print("D. each row is derived from facts")
    d = q.derive(row, records=234, source=src(True), state={})
    check("D1 records on disk -> complete, with their number",
          d == {"documented_update_count": 234, "coverage_state": "documented",
                "backfill_status": "complete"}, str(d))
    d = q.derive(row, records=0, source=src(True), state={})
    check("D2 an enabled source with no record yet stays queued and names its executor",
          d["backfill_status"] == "queued" and d["backfill_executor"] == "official_ingest_lane"
          and "backfill_blocker" not in d, str(d))
    d = q.derive(row, records=0, source=src(True), state={"extraction_mismatch": True})
    check("D3 an extractor that maps nothing is named as the blocker",
          d["backfill_status"] == "queued" and d["backfill_blocker"] == "extraction_mismatch", str(d))
    d = q.derive(row, records=0, source=src(True), state={"consecutive_failures": 3})
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
    d = q.derive(row, records=5, source=src(False), state={"extraction_mismatch": True})
    check("D9 records decide: a row with records is complete whatever its source says",
          d["backfill_status"] == "complete", str(d))
    check("D10 every blocker the step can write is in the closed vocabulary",
          {"extraction_mismatch", "source_failing", "source_disabled", "no_automated_source", "no_source"}
          == set(q.BLOCKERS))

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
            {"sources": {"prod-b": {"extraction_mismatch": True}}}), encoding="utf-8")
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
