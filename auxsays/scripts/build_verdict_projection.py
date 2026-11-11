#!/usr/bin/env python3
"""Write lib/patch_decision.decide's verdicts for the Liquid gate, at deploy time.

`_includes/patch-verdict-gate.html` publishes EVERY verdict -- AVOID, SECURITY UPDATE (with a
security page's warning panel), WAIT and TEST FIRST -- ONLY from `_data/verdict_projection.yml`, the
file this writes: per page, the verdict, scope, line, panel and recommendations Python decided from
the lifecycle record, the stored release type, the counted evidence and the reviewed reason
entries. The gate never evaluates an entry or an official fact itself (GROWTH-3 review 1, D2: a
Liquid copy of the support rule published verdicts `decide` refused; review 2, LOW-1: its own
reading of the lifecycle file and the release type parted from Python's). See lib/verdict_projection
for the contract.

POSITION IS LOAD-BEARING. pages.yml runs this after the inputs are final and BEFORE
`qa_patch_records.py --publish-strict` (which compares the file with `decide` and errors on any
difference) and BEFORE `jekyll build` (which renders it).

FAILURE. An unreadable evidence store, or any failure while deciding, writes an EMPTY projection
carrying the error and exits 0 with a ::warning::. Rendered, that is fail closed: no page publishes
any verdict. It is not silent: QA then reports every page the authority would have given one as an
ERROR, so a deploy cannot quietly drop them.

THE REASON PRODUCER RUNS HERE TOO (G35-04). lib/verdict_reason_producer derives reason candidates
from the same records and counted rows and this writes them, with its refusals and its TEMPORARY
review queue, to `_data/verdict_reason_candidates.yml` beside the projection. Running it here, at
deploy, into a derived git-ignored file, is what keeps it from ever being a second writer of
tracked data. Its PUBLIC_AUTO_ACTIVATION switch is OFF (TEMPORARY, pending the owner's approval), so
the projection above does not read the candidates and nothing published changes; ON, the projection
carries them. A producer failure writes the error into the candidates file and never touches the
projection.

GENERATED AT DEPLOY, NEVER COMMITTED (both files are git-ignored).

Run:  python auxsays/scripts/build_verdict_projection.py [--root DIR] [--output FILE] [--candidates-output FILE]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run as a bare script by pages.yml: `lib` and `patch_collectors` live beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from lib import verdict_projection, verdict_reason_producer  # noqa: E402
from patch_collectors.base import atomic_write_text  # noqa: E402

AUX = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=AUX,
                    help="the site tree to read (default: this repository's auxsays/)")
    ap.add_argument("--output", type=Path, default=None,
                    help=f"where to write (default: <root>/_data/{verdict_projection.PROJECTION_NAME})")
    ap.add_argument("--candidates-output", type=Path, default=None,
                    help=f"where the reason producer's candidates go (default: {verdict_reason_producer.ARTIFACT_NAME} "
                         "beside the projection)")
    args = ap.parse_args(argv)
    output = args.output or (args.root / "_data" / verdict_projection.PROJECTION_NAME)
    candidates_output = args.candidates_output or (output.parent / verdict_reason_producer.ARTIFACT_NAME)
    records, groups = None, None
    try:
        records, groups = verdict_projection.load_inputs(args.root)
        reasons, lifecycle, problems = verdict_projection.load_fact_files(args.root)
        projection, unsupported = verdict_projection.project(records, groups, reasons, lifecycle)
    except Exception as exc:  # noqa: BLE001 - deliberately broad; see FAILURE above
        print(f"::warning::verdict projection is EMPTY, so no page publishes a verdict: "
              f"{type(exc).__name__}: {exc}")
        projection = {"schema_version": verdict_projection.SCHEMA_VERSION, "pages": {},
                      "error": f"{type(exc).__name__}: {exc}"}
        unsupported, problems = {}, []
    for problem in problems:
        print(f"::warning::verdict fact file refused, it supports nothing: {problem}")
    for reason_id, why in sorted(unsupported.items()):
        print(f"{reason_id}: not supported ({'; '.join(why)})")
    atomic_write_text(output, verdict_projection.render(projection))
    pages = projection.get("pages") or {}
    print(f"Wrote {output}: {len(pages)} page(s) with a verdict, "
          f"{len(unsupported)} entr{'y' if len(unsupported) == 1 else 'ies'} unsupported")
    for key, row in pages.items():
        print(f"  {row.get('url') or key}: {verdict_projection.phrase(row.get('verdict', ''), row.get('scope', ''))}")
    write_candidates(candidates_output, records, groups)
    return 0


def write_candidates(path: Path, records, groups) -> None:
    """The reason producer's run over the same inputs, to the git-ignored candidates artifact (G35-04).
    Its own failure never touches the projection above: it writes the error instead."""
    try:
        if records is None:
            raise RuntimeError("the projection inputs could not be read")
        payload = verdict_reason_producer.artifact(verdict_reason_producer.produce(records, groups))
    except Exception as exc:  # noqa: BLE001 - the artifact is advisory; record the error, never raise
        payload = {"schema_version": 1, "producer_version": verdict_reason_producer.PRODUCER_VERSION,
                   "error": f"{type(exc).__name__}: {exc}", "candidates": [], "excluded": [], "review_queue": []}
    atomic_write_text(path, verdict_reason_producer.ARTIFACT_HEADER
                      + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100))
    state = "ON" if verdict_reason_producer.PUBLIC_AUTO_ACTIVATION else "OFF (temporary, pending owner approval)"
    print(f"Wrote {path}: {len(payload.get('candidates') or [])} reason candidate(s), "
          f"{len(payload.get('review_queue') or [])} queued for review; public auto-activation {state}")


if __name__ == "__main__":
    raise SystemExit(main())
