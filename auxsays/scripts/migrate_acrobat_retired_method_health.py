#!/usr/bin/env python3
"""One-time, zero-network repair of the FROZEN Acrobat retired-method health rows.

AUX-026 fixed the producer: a retired Acrobat method now reports `disabled` every time its record is
walked. It could not fix the rows already in the store, because the health store is an upsert that
retains what a run does not emit -- so 286 rows stayed at `blocked`, last_run 2026-08-07/09-01, for
methods nobody runs.

The obvious way to clear them was a targeted collector dispatch. That was tried once and it was the
WRONG MECHANISM: a full collector dispatch discovers evidence. Workflow run 37871206618 wrote commit
de8ccb21, which besides health added five counted Reader evidence rows, rewrote three generated
records and touched the Tier-2 store -- one of those rows was an explicitly "Acrobat DC Pro" report
published on a Reader page. Clearing telemetry must not be able to move evidence.

So this migration touches method health and nothing else. It makes no network request, reads no
candidate, runs no collector and writes exactly one file. It is deterministic and idempotent: run it
twice and the second run reports 0 changes.

Scope, exactly:
    products   adobe-acrobat-reader, adobe-acrobat-pro
    methods    adobe_community_search, reddit_search
    action     status -> disabled, counters -> not-run, blocked_reason -> empty, notes -> truthful,
               last_run -> the stamp passed in; identity fields preserved verbatim
It will not touch an Algolia row, another product, or any row outside that product x method set.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from patch_collectors.base import (  # noqa: E402
    METHOD_HEALTH_PATH, load_method_health, method_health_row, write_method_health_file,
)

PRODUCTS = ("adobe-acrobat-reader", "adobe-acrobat-pro")
# Each retired method keeps its OWN family. Collapsing them would file a Reddit row under the family
# the ACTIVE method shares, which is the family used to attribute stored evidence.
SOURCE_TYPES = {
    "adobe_community_search": "adobe_community_bug_report",
    "reddit_search": "reddit_community_report",
}
NOTES = (
    "Not run. This source refused every request it was given over a sustained period, so AUXSAYS "
    "deliberately stopped calling it rather than spending each cycle timing out against it. The "
    "method is retained and can be restored if the source starts answering again. "
    "(acrobat community collector; edition={product_id})"
)


def migrate(rows: list[dict], *, last_run: str) -> tuple[list[dict], list[dict]]:
    """Return (new_rows, changed) without mutating the input rows."""
    out: list[dict] = []
    changed: list[dict] = []
    for row in rows:
        product_id = str(row.get("product_id") or "")
        method_id = str(row.get("method_id") or "")
        if product_id not in PRODUCTS or method_id not in SOURCE_TYPES:
            out.append(row)
            continue
        # IDEMPOTENCE. A row already in the target shape is left exactly as it is, including its
        # own last_run. Re-stamping it would make every run report changes and would overwrite the
        # real timestamp of the run that legitimately wrote it.
        already = _target_shape(row, product_id, method_id, str(row.get("last_run") or ""))
        if already == row:
            out.append(row)
            continue
        repaired = _target_shape(row, product_id, method_id, last_run)
        changed.append(repaired)
        out.append(repaired)
    return out, changed


def _target_shape(row: dict, product_id: str, method_id: str, last_run: str) -> dict:
    return method_health_row(
            product_id=product_id,
            update_version=str(row.get("update_version") or ""),
            method_id=method_id,
            # Preserved verbatim. Acrobat is not build-aware so this is "" today, but the identity
            # is copied rather than assumed, so a future build-aware Acrobat cannot be silently
            # re-keyed onto the wrong patch.
            target_build=str(row.get("target_build") or ""),
            source_type=SOURCE_TYPES[method_id],
            status="disabled",
            candidates_found=0,
            accepted_reports=0,
            rejected_reports=0,
            blocked_reason=None,
            last_run=last_run,
            notes=NOTES.format(product_id=product_id),
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--last-run", required=True,
                    help="ISO timestamp to stamp on the repaired rows")
    ap.add_argument("--path", default=str(METHOD_HEALTH_PATH))
    ap.add_argument("--write", action="store_true",
                    help="write the file (default: report what would change)")
    args = ap.parse_args(argv)

    path = Path(args.path)
    rows = load_method_health(path)
    new_rows, changed = migrate(rows, last_run=args.last_run)

    print(f"rows in store      : {len(rows)}")
    print(f"in scope           : "
          f"{sum(1 for r in rows if str(r.get('product_id')) in PRODUCTS and str(r.get('method_id')) in SOURCE_TYPES)}")
    print(f"rows changed       : {len(changed)}")
    if args.write and changed:
        write_method_health_file(new_rows, path)
        print(f"written            : {path}")
    elif args.write:
        print("written            : nothing to do (idempotent)")
    else:
        print("dry run; pass --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
