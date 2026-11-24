#!/usr/bin/env python3
"""Re-identify stored DaVinci rows that are counted for a release line but name an exact release.

    python auxsays/scripts/migrate_davinci_release_line_identity.py            # report only
    python auxsays/scripts/migrate_davinci_release_line_identity.py --write    # apply

A bare DaVinci version ("21", "20") is the name of a whole release line, so its page collects every
report that names the line (lib/davinci_release_line.py). The collector now refuses, for the line
page, a report whose text names an exact point release. A producer fix does not touch rows already
stored, and the store is append-only for collectors, so this migration applies the SAME predicate to
the stored rows. Zero network; scoped to one product; idempotent.

FOR EACH counted row whose version is a bare line and whose own stored text names a point release
of that line (the predicate is `stated_point_releases`, the one the collector runs):

  * the line row is WITHDRAWN, audited: `counted: false`, `exclusion_reason:
    point_release_named_not_release_line`, the row kept (lib/evidence_loss.py);
  * when the stored text names exactly ONE tracked point release, and the store holds no row for
    that release and this report, the report is put to that release's own record through the
    collector's unchanged `row_from_candidate` (exact version, date, link, concrete problem), on
    the stored text only. If those gates accept it, the row is APPENDED there through the store's
    own append guard. If they refuse it, nothing is appended. Nothing is inferred from a date.

Selection is the shipped predicate over the whole store, never a list of ids. The receipt written
with `--write` records every row touched, the block hash of every row before and after, and proves
that no other row changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from lib import davinci_release_line as drl  # noqa: E402
from lib import version_attribution as va  # noqa: E402
from patch_collectors import davinci  # noqa: E402
from patch_collectors.base import (  # noqa: E402
    EVIDENCE_PATH, append_evidence_rows, atomic_write_text, generated_records, load_evidence,
)
from withdraw_acrobat_wrong_edition_rows import withdraw  # noqa: E402

PRODUCT_ID = drl.PRODUCT_ID
REASON = drl.REASON_POINT_RELEASE_NAMED
RECEIPT_DIR = Path(__file__).resolve().parent / "audit"
EOL = "\n"


def _blocks_by_id(text: str) -> dict[str, str]:
    """row id -> sha256 of that row's YAML block. Rows start at a line beginning "- id: "."""
    out: dict[str, str] = {}
    marker = EOL + "- id: "
    starts = []
    pos = text.find(marker)
    while pos != -1:
        starts.append(pos + 1)
        pos = text.find(marker, pos + 1)
    for index, lo in enumerate(starts):
        hi = starts[index + 1] if index + 1 < len(starts) else len(text)
        # Trailing blank lines are not part of a row: the store's append path separates a new
        # batch from the previous last row with one, and that must not read as a changed row.
        block = text[lo:hi].rstrip()
        row_id = block.split(EOL, 1)[0][len("- id: "):].strip().strip("'\"")
        out[row_id] = hashlib.sha256(block.encode("utf-8")).hexdigest()
    return out


def candidate_from_row(row: dict) -> dict:
    """The stored row as the collector's candidate shape. The stored excerpt is the only text."""
    return {
        "source_type": row.get("source_type"), "source_name": row.get("source_name"),
        "source_url": row.get("source_url"), "parent_title": row.get("parent_title"),
        "report_title": row.get("report_title"), "report_text": row.get("report_text_excerpt"),
        "source_date": row.get("source_date"),
    }


def plan(rows: list[dict]) -> list[dict]:
    """One entry per counted release-line row that names a point release, in store order."""
    records = {r.update_version: r for r in generated_records(PRODUCT_ID, include_archived=True)}
    held: dict[tuple[str, str], dict] = {}
    for row in rows:
        if row.get("product_id") == PRODUCT_ID and row.get("source_url"):
            held.setdefault((str(row.get("update_version")), str(row.get("source_url"))), row)
    entries: list[dict] = []
    for row in rows:
        if row.get("product_id") != PRODUCT_ID or row.get("counted") is not True:
            continue
        line = str(row.get("update_version") or "").strip()
        if not drl.is_bare_line(line):
            continue
        named = drl.stated_point_releases(va.stored_text(row), line, records)
        if not named:
            continue
        tracked = [p for p in named if p in records]
        url = str(row.get("source_url") or "")
        entry = {"id": row["id"], "line": line, "source_url": url, "named": named,
                 "tracked": tracked, "source_date": str(row.get("source_date") or ""),
                 "already_held_for": {p: bool(held[(p, url)].get("counted")) for p in tracked
                                      if (p, url) in held},
                 "append": None, "append_refused": ""}
        if len(tracked) == 1 and not entry["already_held_for"]:
            target = records[tracked[0]]
            gated = davinci.row_from_candidate(target, candidate_from_row(row),
                                               str(row.get("captured_at") or ""))
            if gated.get("counted") is True:
                entry["append"] = gated
            else:
                entry["append_refused"] = str(gated.get("exclusion_reason") or "not_counted")
        entries.append(entry)
    return entries


def describe(entry: dict) -> str:
    if entry["append"] is not None:
        action = f"withdraw from {entry['line']}; append to {entry['tracked'][0]}"
    elif entry["already_held_for"]:
        held = ", ".join(f"{p} ({'counted' if c else 'held, not counted'})"
                         for p, c in entry["already_held_for"].items())
        action = f"withdraw from {entry['line']}; the report is already held for {held}"
    elif entry["append_refused"]:
        action = (f"withdraw from {entry['line']}; {entry['tracked'][0]}'s own gates refuse the "
                  f"stored text ({entry['append_refused']})")
    elif not entry["tracked"]:
        action = f"withdraw from {entry['line']}; names no tracked release"
    else:
        action = f"withdraw from {entry['line']}; names more than one tracked release"
    return f"{entry['line']} | {', '.join(entry['named'])} | {action} | {entry['source_url']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--write", action="store_true", help="apply; without it nothing is written")
    ap.add_argument("--evidence-path", default=str(EVIDENCE_PATH), help=argparse.SUPPRESS)
    ap.add_argument("--receipt", default="", help="where to write the receipt (with --write)")
    args = ap.parse_args(argv)

    path = Path(args.evidence_path)
    rows = load_evidence(path)
    entries = plan(rows)
    line_rows = [r for r in rows if r.get("product_id") == PRODUCT_ID and r.get("counted") is True
                 and drl.is_bare_line(r.get("update_version"))]
    print(f"{PRODUCT_ID}: {len(line_rows)} counted release-line rows examined, "
          f"{len(entries)} name a point release")
    for entry in entries:
        print("- " + describe(entry))
    if not entries:
        print("nothing to do")
        return 0
    if not args.write:
        print("report only (pass --write to apply)")
        return 0

    by_id = {row["id"]: row for row in rows}
    original = path.read_text(encoding="utf-8")
    text = original
    before = _blocks_by_id(text)
    for entry in entries:
        text, changed = withdraw(text, by_id[entry["id"]], REASON)
        entry["withdrawn"] = changed
    atomic_write_text(path, text)
    new_rows = [entry["append"] for entry in entries if entry["append"] is not None]
    added_rows: list[dict] = []
    if new_rows:
        append_evidence_rows(new_rows, path, out_added=added_rows)
    added_ids = {row["id"] for row in added_rows}
    after = _blocks_by_id(path.read_text(encoding="utf-8"))

    touched = {entry["id"] for entry in entries}
    drifted = sorted(i for i in before if i not in touched and after.get(i) != before[i])
    missing = sorted(i for i in before if i not in after)
    unexpected = sorted(i for i in after if i not in before and i not in added_ids)
    if drifted or missing or unexpected:
        atomic_write_text(path, original)               # all or nothing: put the store back
        raise SystemExit(f"refusing, store restored: scope proof failed (changed {drifted[:3]}, "
                         f"missing {missing[:3]}, unexpected {unexpected[:3]})")
    receipt = {
        "tool": Path(__file__).name, "product_id": PRODUCT_ID, "reason": REASON,
        "rows_before": len(before), "rows_after": len(after),
        "untouched_rows": len(before) - len(touched), "untouched_rows_identical": True,
        "withdrawn": [{"id": e["id"], "line": e["line"], "named": e["named"],
                       "source_url": e["source_url"], "block_sha256_before": before[e["id"]],
                       "block_sha256_after": after[e["id"]],
                       "already_held_for": e["already_held_for"],
                       "append_refused": e["append_refused"]} for e in entries],
        "appended": [{"id": row["id"], "update_version": row["update_version"],
                      "source_url": row["source_url"], "match_basis": row["match_basis"],
                      "from_line_row": next(e["id"] for e in entries
                                            if e["append"] is not None
                                            and e["append"]["id"] == row["id"]),
                      "block_sha256": after[row["id"]]} for row in added_rows],
    }
    target = Path(args.receipt) if args.receipt else RECEIPT_DIR / "davinci_release_line_identity.json"
    target.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"withdrawn {sum(1 for e in entries if e['withdrawn'])}, appended {len(added_rows)}, "
          f"{receipt['untouched_rows']} other rows byte-identical; receipt {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
