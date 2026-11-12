#!/usr/bin/env python3
"""Record one deploy's shadow observation of the verdict-reason producer (AUX-099).

pages.yml runs this right after build_verdict_projection.py, which wrote the producer's candidates and
review queue to the git-ignored `_data/verdict_reason_candidates.yml` (activation OFF: no page reads it).
This reads that artifact and a ledger of earlier deploys, tells each candidate and queue item seen for the
FIRST time apart from a REPEAT appearance (lib/producer_shadow), writes the ledger back, and appends a short
Markdown summary to the step summary.

WHERE THE LEDGER LIVES -- never a tracked file. `.producer-shadow/ledger.json` at the repository root,
outside the Jekyll source (it can never be rendered), restored from and saved to a GitHub Actions cache by
pages.yml (key `producer-shadow-v1-<run>-<attempt>`, restored by prefix: the newest wins; the deploys are
serialised by the workflow's `pages` concurrency group) and uploaded as a run artifact. No writeback lane
and no commit is involved, so it is not a second writer of tracked data. Retention: an Actions cache entry
lives until 7 days without access (the daily scheduled deploy restores the newest one, so it stays) or
eviction under the repository's 10 GB cache limit; each run artifact is kept 90 days. A lost cache is
re-established as a baseline and the summary says so (it under-counts prospective cases, never over).

PUBLIC-SAFE by construction: see lib/producer_shadow. Diagnostics only: this never fails a deploy (exit 0,
and the workflow step is continue-on-error), and it reads and writes nothing under auxsays/ except reading
the artifact.

Run:  python auxsays/scripts/producer_shadow.py --ledger .producer-shadow/ledger.json \
          [--candidates auxsays/_data/verdict_reason_candidates.yml] [--deploy-id ID] [--commit SHA] \
          [--observed-at ISO] [--summary FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Run as a bare script by pages.yml: `lib` lives beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from lib import producer_shadow  # noqa: E402

AUX = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = AUX / "_data" / "verdict_reason_candidates.yml"


def _read_ledger(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"unreadable": True}   # producer_shadow re-baselines it and counts a reset


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True, help="the shadow ledger (JSON), read and rewritten")
    ap.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES,
                    help="the producer artifact build_verdict_projection.py wrote")
    ap.add_argument("--deploy-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    ap.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""))
    ap.add_argument("--observed-at", default="")
    ap.add_argument("--summary", type=Path, default=None, help="append the Markdown summary here")
    args = ap.parse_args(argv)
    observed_at = args.observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z")
    try:
        artifact = yaml.safe_load(args.candidates.read_text(encoding="utf-8")) or {}
        if not isinstance(artifact, dict):
            raise ValueError("the producer artifact is not a mapping")
    except Exception as exc:  # noqa: BLE001 - diagnostics never fail a deploy
        artifact = {"error": f"{type(exc).__name__}: {exc}"}
    ledger, summary = producer_shadow.update(_read_ledger(args.ledger), artifact, deploy=args.deploy_id,
                                             commit=args.commit, observed_at=observed_at)
    _write_atomic(args.ledger, json.dumps(ledger, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
    text = producer_shadow.render_summary(ledger, summary)
    if args.summary:
        try:
            with open(args.summary, "a", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            print(f"::warning::could not write the shadow summary: {exc}")
    print(f"producer shadow: mode {summary.get('mode')}; {summary.get('candidates', 0)} candidate(s) and "
          f"{summary.get('queue', 0)} queue item(s) seen; first seen {summary.get('first_seen_candidates', 0)} / "
          f"{summary.get('first_seen_queue', 0)} ({summary.get('first_seen_origin', '-')}); repeats "
          f"{summary.get('repeat_candidates', 0)} / {summary.get('repeat_queue', 0)}; unique prospective so far "
          f"{ledger['totals'].get('prospective_candidate', 0)} / {ledger['totals'].get('prospective_queue', 0)}")
    for cls, row in producer_shadow.class_counts(ledger).items():
        print(f"  {cls}: " + ", ".join(f"{k} {v}" for k, v in row.items()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - diagnostics never fail a deploy
        print(f"::warning::producer shadow diagnostics failed: {type(exc).__name__}: {exc}")
        raise SystemExit(0) from None
