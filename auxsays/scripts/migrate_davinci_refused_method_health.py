#!/usr/bin/env python3
"""One-time, zero-network reclassification of DaVinci's frozen Blackmagic-forum health rows (AUX-117).

AUX-117 switched off `known_watchlist` and `vendor_forum_search` in the DaVinci collector, because the
Blackmagic Design forum refuses automated requests. From then on the collector writes a `disabled` row
for both methods on every record it walks. It cannot repair the rows of records it never walks: the
health store is an upsert that keeps whatever a run does not emit, and routine collection skips
ARCHIVED records (`base.generated_records`, AUX-065). So the 100 archived DaVinci records would keep
their last `blocked` rows, from the 2026-11-05 pass, forever.

A collector dispatch is the wrong tool for that: it discovers evidence (AUX-027). This script changes
method-health telemetry and nothing else. It makes no network request, runs no collector, reads no
candidate, and writes exactly one file. It is deterministic and idempotent.

Scope, exactly:
    product   blackmagic-davinci
    methods   known_watchlist, vendor_forum_search
    records   those whose generated record has `update_status: archived`
    rows      status `blocked` (a row already `disabled` is left exactly as it is)
    change    status -> disabled
              blocked_reason -> the collector's refusal reason
              notes -> the collector's refusal note, plus the time and diagnostic of the row's own
                       last attempt
    kept      every other field verbatim: identity, counters (all must already be 0), and last_run.

`last_run` is NOT restamped. These records were not checked by this migration, and their pages show
COLLECTION STALE because nothing has collected them since 2026-11-05. A new timestamp would claim a
check that never happened. A `disabled` row is not a usable source in the monitoring ladder, so the
page's freshness state cannot improve because of this script. It refuses, and writes nothing, if an
in-scope row is not in the shape it expects.

Run:  python auxsays/scripts/migrate_davinci_refused_method_health.py           (report only)
      python auxsays/scripts/migrate_davinci_refused_method_health.py --write
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch_collectors.base import (  # noqa: E402
    GENERATED_DIR, METHOD_HEALTH_PATH, load_front_matter_and_body, load_method_health,
    write_method_health_file,
)
from patch_collectors.davinci import (  # noqa: E402
    PRODUCT_ID, REFUSED_SOURCE_DISABLED_METHODS, REFUSED_SOURCE_DISABLED_NOTE,
    REFUSED_SOURCE_DISABLED_REASON,
)

COUNTER_FIELDS = ("candidates_found", "accepted_candidates", "duplicate_existing_evidence",
                  "evidence_rows_added", "public_counted_reports", "accepted_reports", "rejected_reports")
CHANGED_FIELDS = ("status", "blocked_reason", "notes")


class UnexpectedShape(RuntimeError):
    """An in-scope row is not a frozen `blocked` row with zero counters; nothing is written."""


def archived_versions(generated_dir: Path = GENERATED_DIR) -> set[str]:
    """Versions of the archived DaVinci records, read the way `base.generated_records` reads them."""
    versions: set[str] = set()
    for path in sorted(Path(generated_dir).glob("*.md")):
        data, _body = load_front_matter_and_body(path)
        if data.get("update_entry") is not True:
            continue
        if str(data.get("product_id") or "").strip() != PRODUCT_ID:
            continue
        if str(data.get("update_status") or "").strip() != "archived":
            continue
        version = str(data.get("update_version") or "").strip()
        if version:
            versions.add(version)
    return versions


def in_scope(row: dict[str, Any], archived: set[str]) -> bool:
    return (str(row.get("product_id") or "") == PRODUCT_ID
            and str(row.get("method_id") or "") in REFUSED_SOURCE_DISABLED_METHODS
            and str(row.get("update_version") or "") in archived)


def reclassified(row: dict[str, Any]) -> dict[str, Any]:
    """The row with exactly CHANGED_FIELDS replaced. Every other key is copied, not rebuilt."""
    out = dict(row)
    attempt = str(row.get("blocked_reason") or "").strip() or "no diagnostic recorded"
    out["status"] = "disabled"
    out["blocked_reason"] = REFUSED_SOURCE_DISABLED_REASON
    out["notes"] = (f"{REFUSED_SOURCE_DISABLED_NOTE} Reclassified by a zero-network migration (AUX-117). "
                    f"last_run is this method's last real attempt for this release, not a new check; "
                    f"that attempt was refused: {attempt}.")
    return out


def migrate(rows: list[dict[str, Any]], archived: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (new_rows, changed) without mutating the input rows. Raises UnexpectedShape."""
    out: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for row in rows:
        if not in_scope(row, archived):
            out.append(row)
            continue
        status = str(row.get("status") or "")
        if status == "disabled":
            out.append(row)  # idempotence: already reclassified, or written by the collector itself
            continue
        if status != "blocked":
            raise UnexpectedShape(f"{row.get('update_version')} {row.get('method_id')}: status {status!r}, "
                                  "expected 'blocked'")
        nonzero = [f for f in COUNTER_FIELDS if int(row.get(f) or 0) != 0]
        if nonzero:
            raise UnexpectedShape(f"{row.get('update_version')} {row.get('method_id')}: non-zero {nonzero}")
        if not str(row.get("last_run") or "").strip():
            raise UnexpectedShape(f"{row.get('update_version')} {row.get('method_id')}: no last_run")
        new = reclassified(row)
        changed.append(new)
        out.append(new)
    return out, changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reclassify DaVinci's frozen Blackmagic-forum health rows as disabled.")
    ap.add_argument("--path", default=str(METHOD_HEALTH_PATH), help="method-health store")
    ap.add_argument("--generated-dir", default=str(GENERATED_DIR), help="generated records (read only)")
    ap.add_argument("--write", action="store_true", help="write the store (default: report only)")
    args = ap.parse_args(argv)

    path = Path(args.path)
    rows = load_method_health(path)
    archived = archived_versions(Path(args.generated_dir))
    try:
        new_rows, changed = migrate(rows, archived)
    except UnexpectedShape as exc:
        print(f"REFUSED (nothing written): {exc}")
        return 2
    scope = [r for r in rows if in_scope(r, archived)]
    print(f"rows in store        : {len(rows)}")
    print(f"archived records     : {len(archived)}")
    print(f"rows in scope        : {len(scope)}")
    print(f"rows changed         : {len(changed)}")
    print(f"already disabled     : {sum(1 for r in scope if str(r.get('status')) == 'disabled')}")
    if args.write and changed:
        write_method_health_file(new_rows, path)
        print(f"written              : {path}")
    elif args.write:
        print("written              : nothing to do (idempotent)")
    else:
        print("report only; pass --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
