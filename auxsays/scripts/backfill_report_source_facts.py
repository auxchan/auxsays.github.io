#!/usr/bin/env python3
"""Read each tracker's own record of the reports ALREADY stored as counted evidence rows, and store the facts
that record supplies in `_data/report_source_facts.yml` (lib/assessment_facts, AUX-137).

WHAT IT DOES. For every counted row whose report link is an issue of a tracker lib.assessment_facts has a
vocabulary for, it reads that one issue from the tracker's REST API (lib/github_api: api.github.com only, paced,
truthful User-Agent, stops at the first refusal) and stores its state, close reason, label names, the form's
operating-system family and version, and whether the form's crash-log field holds a link. It never collects a
report, never changes a row, a count or a record, and never stores a title, text or account.

BOUNDED AND RESUMABLE. One run sends at most --max-requests requests (default 60) and, with --max-seconds, stops
reading by itself once that much time has passed since it started (the workflow step that runs it has a hard cap;
a run that stops by itself still writes what it read). Order: reports with no entry
under the current rule first (by key), then the entries that are due, the one checked longest ago first. An OPEN
report is due one day after its last read (--open-max-age-days: a maintainer's label or close arrives on open
reports, and a new release's first days are when the page matters most); a CLOSED one after three days
(--max-age-days). Both are well inside lib.assessment_facts.STALE_AFTER_DAYS, after which the authority stops
using a record. The file is rewritten after the run with everything read so far, so the next run continues where
this one stopped, and a refusal mid-run loses nothing. Entries of reports that no longer count are dropped: the
file holds facts of the counted population and nothing else.

THE ONLY WRITER of that file (lib/single_writer: lock, no stale overwrite, atomic replace). Dry run by default.

Run by the scheduled evidence-collection lane, after collection and before the promotions that read the facts
(.github/workflows/obs-evidence-collection.yml, step "Refresh maintainer records of counted reports"):
    python auxsays/scripts/backfill_report_source_facts.py --write [--product-id obs-studio] [--max-requests 60]
Offline replay of issue objects fetched elsewhere, one file per issue named <owner>__<repository>__<number>.json
(tests, and a calibration read made with the `gh` client): add --replay-dir DIR; no request is sent then.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

# Run as a bare script by a workflow step: `lib` lives beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import assessment_facts, github_api, single_writer  # noqa: E402
from lib.report_counts import load_evidence_store, row_is_counted  # noqa: E402
from lib.source_segments import report_url_key  # noqa: E402

AUX = Path(__file__).resolve().parents[1]
ENDPOINT_FAMILY = "report_source_facts"
DEFAULT_MAX_REQUESTS = 60
DEFAULT_MAX_AGE_DAYS = 3
DEFAULT_OPEN_MAX_AGE_DAYS = 1


def counted_keys(rows, product_id: str = "") -> list[str]:
    """The report links of the counted rows this tool reads facts for, each once, sorted."""
    keys = set()
    for row in rows:
        if not row_is_counted(row):
            continue
        if product_id and str(row.get("product_id") or "").strip() != product_id:
            continue
        key = report_url_key(str(row.get("source_url") or ""))
        if assessment_facts.source_of(key):
            keys.add(key)
    return sorted(keys)


def plan(keys: list[str], existing: dict, today: str, max_age_days: int,
         open_max_age_days: int | None = None) -> list[str]:
    """Which reports this run reads, in order: no current entry first, then the entries that are due, oldest
    check first. A closed report is due `max_age_days` after its last read and an open one `open_max_age_days`
    after it (the same age when not given); never one read more recently than that."""
    missing = [k for k in keys if k not in existing]
    now = date.fromisoformat(today).toordinal()
    open_age = int(max_age_days if open_max_age_days is None else open_max_age_days)

    def due(key: str) -> bool:
        entry = existing[key]
        age = now - date.fromisoformat(entry["checked_at"]).toordinal()
        return age >= (open_age if entry.get("state") == "open" else int(max_age_days))

    stale = sorted((k for k in keys if k in existing and due(k)), key=lambda k: (existing[k]["checked_at"], k))
    return missing + stale


def api_url(key: str) -> str:
    source, number = key[len("https://"):].rsplit("/issues/", 1)
    return f"{github_api.API_ORIGIN}/repos/{source[len('github.com/'):]}/issues/{number}"


def replay_path(replay_dir: Path, key: str) -> Path:
    source, number = key[len("https://"):].rsplit("/issues/", 1)
    owner, repository = source[len("github.com/"):].split("/", 1)
    return replay_dir / f"{owner}__{repository}__{number}.json"


def read_issue(key: str, replay_dir: Path | None):
    """(issue object or None, problem). A replay never sends a request."""
    if replay_dir is not None:
        path = replay_path(replay_dir, key)
        if not path.is_file():
            return None, "no replay file"
        try:
            return json.loads(path.read_text(encoding="utf-8")), ""
        except ValueError:
            return None, "unreadable replay file"
    payload, _meta = github_api.get_json(api_url(key), endpoint_family=ENDPOINT_FAMILY)
    return payload, ""


def run(store_path: Path, facts_path: Path, *, product_id: str = "", max_requests: int = DEFAULT_MAX_REQUESTS,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS, open_max_age_days: int | None = None, today: str = "",
        replay_dir: Path | None = None, write: bool = False, max_seconds: float = 0,
        clock=time.monotonic) -> dict:
    started = clock()
    today = today or datetime.now(timezone.utc).date().isoformat()
    rows = load_evidence_store(store_path)
    all_keys = set(counted_keys(rows))
    keys = counted_keys(rows, product_id)
    baseline = single_writer.fingerprint(facts_path)
    existing = assessment_facts.load(facts_path)        # raises on a malformed file: never overwrite blindly
    entries = dict(existing)
    stats = {"counted_reports": len(keys), "current_entries": sum(1 for k in keys if k in existing),
             "read": 0, "written": 0, "unreadable": 0, "stopped": "", "dropped": 0, "remaining": 0}
    todo = plan(keys, existing, today, max_age_days,
                min(int(max_age_days), DEFAULT_OPEN_MAX_AGE_DAYS) if open_max_age_days is None
                else open_max_age_days)
    for position, key in enumerate(todo):
        if stats["read"] >= int(max_requests):
            stats["remaining"] = len(todo) - position
            break
        if max_seconds and clock() - started >= float(max_seconds):
            # The run's own time budget, measured from its start: stop READING, keep everything read so far.
            stats["stopped"] = "time_budget"
            stats["remaining"] = len(todo) - position
            break
        try:
            issue, problem = read_issue(key, replay_dir)
        except github_api.GitHubError as exc:
            stats["stopped"] = exc.reason
            stats["remaining"] = len(todo) - position
            break
        stats["read"] += 1
        entry = assessment_facts.entry_from_issue(key, issue, today) if issue is not None else None
        if entry is None or assessment_facts.entry_errors(entry):
            # Fail closed: an object that is not this issue, or a value outside the closed lists, leaves the
            # report WITHOUT a fact. An earlier entry is kept until a readable record replaces it.
            stats["unreadable"] += 1
            continue
        entries[key] = entry
        stats["written"] += 1
    kept = {k: v for k, v in entries.items() if k in all_keys}
    stats["dropped"] = len(entries) - len(kept)
    text = assessment_facts.render(kept.values())
    errors = assessment_facts.schema_errors({"schema_version": assessment_facts.SCHEMA_VERSION,
                                             "facts": list(kept.values())})
    if errors:
        raise SystemExit(f"refusing to write a malformed facts file: {errors[0]}")
    stats["entries"] = len(kept)
    stats["changed"] = (not facts_path.is_file()) or facts_path.read_text(encoding="utf-8") != text
    if write and stats["changed"]:
        single_writer.guarded_write(facts_path, text.encode("utf-8"), expected=baseline)
        assessment_facts.reset_stored()
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--store", type=Path, default=AUX / "_data" / "consensus_evidence.yml")
    parser.add_argument("--facts", type=Path, default=AUX / "_data" / assessment_facts.FACTS_NAME)
    parser.add_argument("--product-id", default="", help="read only this product's counted reports")
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS,
                        help="re-read a CLOSED report this many days after its last read")
    parser.add_argument("--open-max-age-days", type=int, default=None,
                        help=f"re-read an OPEN report this many days after its last read (default: "
                             f"{DEFAULT_OPEN_MAX_AGE_DAYS}, or --max-age-days when that is smaller)")
    parser.add_argument("--max-seconds", type=float, default=0,
                        help="stop reading this many seconds after the start and write what was read (0: no limit)")
    parser.add_argument("--today", default="", help="YYYY-MM-DD stored as checked_at (default: today, UTC)")
    parser.add_argument("--replay-dir", type=Path, default=None)
    parser.add_argument("--write", action="store_true", help="rewrite the facts file (default: dry run)")
    args = parser.parse_args(argv)
    if args.max_requests < 0 or args.max_age_days < 0 or (args.open_max_age_days or 0) < 0 or args.max_seconds < 0:
        parser.error("--max-requests, --max-seconds, --max-age-days and --open-max-age-days must not be negative")
    stats = run(args.store, args.facts, product_id=args.product_id.strip(), max_requests=args.max_requests,
                max_age_days=args.max_age_days, open_max_age_days=args.open_max_age_days,
                today=args.today.strip(), replay_dir=args.replay_dir, write=args.write,
                max_seconds=args.max_seconds)
    mode = "WRITE" if args.write else "DRY RUN"
    print(f"report source facts [{mode}]: " + ", ".join(f"{k}={v}" for k, v in stats.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
