#!/usr/bin/env python3
"""Close the loop on the official-record backfill queue.

    python auxsays/scripts/execute_backfill_queue.py --queue auxsays/_data/patch_backfill_queue.yml
    python auxsays/scripts/execute_backfill_queue.py --queue auxsays/_data/patch_backfill_queue.yml --write

`_data/patch_backfill_queue.yml` lists products whose official update history was to be ingested.
Nothing read it or wrote it: 36 rows said `queued` with `documented_update_count: 0` while the
official lane had already written 1,156 records for six of them (Figma 234, GitHub 472, Acrobat
Reader 199, Acrobat Pro 199, ComfyUI 50, Premiere Pro 2), and 29 others named a source that is
switched off and can never be reached by any run.

WHAT EXECUTES A ROW. The official ingest lane (`patch_ingest.py`, scheduled) is already the bounded,
resumable executor: per source it fetches the vendor listing, writes at most `record_limit` new
records per run and defers the rest to the next run. A row needs nothing else to execute it; what
was missing is the step that reads the result back. This is that step. It runs in the same lane,
after ingestion, and sets each row to what the repository's own facts say:

  complete   the product has generated records; `documented_update_count` is their number
  queued     the source is enabled and no record exists yet: the lane works on it every run.
             `backfill_blocker` says why it has produced nothing, when the lane's own health knows
             (`extraction_mismatch`, `source_failing`)
  blocked    no run can execute the row: the source is switched off (`source_disabled`), is
             watch-only with no automated adapter (`no_automated_source`), or is not configured
             (`no_source`). Switching a source on is an onboarding decision, not this step's.

Zero network. It never creates a record, never enables a source, and writes only the queue file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "_data" / "patch_backfill_queue.yml"
SOURCES_PATH = ROOT / "_data" / "patch_ingestion_sources.yml"
STATE_PATH = ROOT / "_data" / "patch_ingest_state.json"
GENERATED_DIR = ROOT / "updates" / "generated"

COMPLETE, QUEUED, BLOCKED = "complete", "queued", "blocked"
EXECUTOR = "official_ingest_lane"
BLOCKERS = ("extraction_mismatch", "source_failing", "source_disabled", "no_automated_source",
            "no_source")
# Derived fields this step owns. Every other key of a row is left exactly as it is.
OWNED = ("documented_update_count", "coverage_state", "backfill_status", "backfill_executor",
         "backfill_blocker")
_FM_PRODUCT = re.compile(r"^product_id:\s*(\S+)", re.M)


def record_counts(generated_dir: Path = GENERATED_DIR) -> dict[str, int]:
    """product_id -> number of generated records, read from each record's front matter."""
    counts: dict[str, int] = {}
    for path in sorted(Path(generated_dir).glob("*.md")):
        head = path.read_text(encoding="utf-8", errors="replace").split("\n---", 1)[0]
        match = _FM_PRODUCT.search(head)
        if match:
            product = match.group(1).strip("'\"")
            counts[product] = counts.get(product, 0) + 1
    return counts


def derive(row: dict[str, Any], *, records: int, source: dict[str, Any] | None,
           state: dict[str, Any] | None) -> dict[str, Any]:
    """The owned fields for one row, from facts only. Pure."""
    if records > 0:
        return {"documented_update_count": records, "coverage_state": "documented",
                "backfill_status": COMPLETE}
    out: dict[str, Any] = {"documented_update_count": 0,
                           "coverage_state": str(row.get("coverage_state") or "active_watch")}
    if out["coverage_state"] == "documented":
        out["coverage_state"] = "active_watch"          # it documents nothing any more
    ingestion = (source or {}).get("ingestion") or {}
    if source is None:
        out.update(backfill_status=BLOCKED, backfill_blocker="no_source")
    elif str(ingestion.get("adapter") or "") == "manual_watch":
        out.update(backfill_status=BLOCKED, backfill_blocker="no_automated_source")
    elif source.get("enabled") is not True:
        out.update(backfill_status=BLOCKED, backfill_blocker="source_disabled")
    else:
        out.update(backfill_status=QUEUED, backfill_executor=EXECUTOR)
        state = state or {}
        if state.get("extraction_mismatch") is True:
            out["backfill_blocker"] = "extraction_mismatch"
        elif int(state.get("consecutive_failures") or 0) > 0:
            out["backfill_blocker"] = "source_failing"
    return out


def reconcile(queue: list[dict[str, Any]], *, counts: dict[str, int],
              sources: dict[str, dict[str, Any]], states: dict[str, dict[str, Any]]
              ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(the reconciled queue in its original order, one change entry per row that changed)."""
    out: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    for row in queue:
        product = str(row.get("product_id") or "")
        derived = derive(row, records=counts.get(product, 0), source=sources.get(product),
                         state=states.get(product))
        new = {key: value for key, value in row.items() if key not in OWNED}
        for key in OWNED:                                 # owned fields, in one stable order
            if key in derived:
                new[key] = derived[key]
        if new != row:
            changes.append({"product_id": product,
                            "from": {key: row.get(key) for key in OWNED if key in row},
                            "to": {key: new.get(key) for key in OWNED if key in new}})
        out.append(new)
    return out, changes


def dump(queue: list[dict[str, Any]]) -> str:
    return yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=1000)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--queue", default=str(QUEUE_PATH))
    ap.add_argument("--sources", default=str(SOURCES_PATH), help=argparse.SUPPRESS)
    ap.add_argument("--state", default=str(STATE_PATH), help=argparse.SUPPRESS)
    ap.add_argument("--generated-dir", default=str(GENERATED_DIR), help=argparse.SUPPRESS)
    ap.add_argument("--write", action="store_true", help="apply; without it nothing is written")
    ap.add_argument("--json", default="", help="write the result to this file")
    args = ap.parse_args(argv)

    queue_path = Path(args.queue)
    try:
        queue = yaml.safe_load(queue_path.read_text(encoding="utf-8"))
        sources_doc = yaml.safe_load(Path(args.sources).read_text(encoding="utf-8"))
        state_path = Path(args.state)
        state_doc = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"::error::backfill queue: an input could not be read: {exc}")
        return 2
    if not isinstance(queue, list) or not all(isinstance(r, dict) for r in queue) \
            or not isinstance(sources_doc, list):
        print("::error::backfill queue: the queue and the source config must each be a list of rows")
        return 2

    sources = {str(s.get("product_id")): s for s in sources_doc if isinstance(s, dict)}
    states = {str(k): v for k, v in (state_doc.get("sources") or {}).items() if isinstance(v, dict)}
    new_queue, changes = reconcile(queue, counts=record_counts(Path(args.generated_dir)),
                                   sources=sources, states=states)

    tally: dict[str, int] = {}
    for row in new_queue:
        key = row["backfill_status"] + (f" ({row['backfill_blocker']})" if row.get("backfill_blocker") else "")
        tally[key] = tally.get(key, 0) + 1
    print(f"backfill queue: {len(new_queue)} rows examined, {len(changes)} changed")
    for key in sorted(tally):
        print(f"  {key}: {tally[key]}")
    for change in changes:
        print(f"- {change['product_id']}: {change['from'].get('backfill_status')} "
              f"({change['from'].get('documented_update_count')}) -> "
              f"{change['to'].get('backfill_status')} ({change['to'].get('documented_update_count')})"
              + (f" [{change['to']['backfill_blocker']}]" if change["to"].get("backfill_blocker") else ""))
    if args.write and changes:
        queue_path.write_text(dump(new_queue), encoding="utf-8", newline="\n")
        print(f"wrote {queue_path}")
    elif not args.write:
        print("report only (pass --write to apply)")
    if args.json:
        Path(args.json).write_text(json.dumps({"examined": len(new_queue), "tally": tally,
                                               "changes": changes, "written": bool(args.write and changes)},
                                              indent=1, sort_keys=True) + "\n",
                                   encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
