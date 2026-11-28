#!/usr/bin/env python3
"""Re-identify stored DaVinci rows that are counted for a release line but name an exact release.

    python auxsays/scripts/migrate_davinci_release_line_identity.py            # report only
    python auxsays/scripts/migrate_davinci_release_line_identity.py --write    # apply

A bare DaVinci version ("21", "20") is the name of a whole release line, so its page collects every
report that names the line (lib/davinci_release_line.py). The collector now refuses, for the line
page, a report whose text names an exact point release. A producer fix does not touch rows already
stored, and the store is append-only for collectors, so this migration applies the SAME predicate to
the stored rows. Zero network; scoped to one product; idempotent.

FOR EACH counted row whose version is a bare line and which names a point release of that line.
Two stored facts establish that, and nothing else does:

  (a) the row's own stored text names one (the predicate is `stated_point_releases`, the one the
      collector runs on the full text);
  (b) the SAME report (same source URL) is counted on a point release of that line. That count was
      made on the report's full text by the exact-version gate, so the store records that the
      report names the point release even though this row's 280-character excerpt stops before
      it. Measured at 57f65455: 8 line rows (21: 5, 20: 2, 19: 1), each counted on two pages.

For each such row:

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


def _blocks(text: str) -> list[tuple[str, str]]:
    """(row id, sha256 of that row's YAML block) for EVERY row, in store order.

    A list, not a mapping by id: 67 ids are shared by 137 rows (one report counted for several
    builds), and a mapping kept one block per id, so its "untouched rows identical" covered less
    than it said. Rows start at a line beginning "- id: ".
    """
    out: list[tuple[str, str]] = []
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
        out.append((row_id, hashlib.sha256(block.encode("utf-8")).hexdigest()))
    return out


def close_append_gap(path: Path) -> None:
    """Remove any blank line directly before a row (a safety net since R4-FIX2).

    `append_evidence_rows` used to join the existing text and the new rows with a newline even on a
    store that already ended in one, leaving an empty line between two rows; it no longer does, but a
    store written before the fix (or by another writer) can still hold one. The stored format has none, and
    the text between two rows is read as the earlier row's facts. Only a blank line directly before
    a row is removed; no row changes.
    """
    text = path.read_text(encoding="utf-8")
    closed = text.replace("\n\n- id: ", "\n- id: ")
    if closed != text:
        atomic_write_text(path, closed)


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
    counted_for: dict[str, set[str]] = {}
    for row in rows:
        if row.get("product_id") == PRODUCT_ID and row.get("source_url"):
            held.setdefault((str(row.get("update_version")), str(row.get("source_url"))), row)
            if row.get("counted") is True:
                counted_for.setdefault(str(row.get("source_url")), set()).add(
                    str(row.get("update_version") or "").strip())
    entries: list[dict] = []
    for row in rows:
        if row.get("product_id") != PRODUCT_ID or row.get("counted") is not True:
            continue
        line = str(row.get("update_version") or "").strip()
        if not drl.is_bare_line(line):
            continue
        url = str(row.get("source_url") or "")
        named = drl.stated_point_releases(va.stored_text(row), line, records)
        basis = "stored_text"
        if not named:
            # (b): the store counts this same report on a point release of the line.
            named = drl.counted_point_releases(line, counted_for.get(url, ()))
            basis = "counted_on_point_release"
        if not named:
            continue
        tracked = [p for p in named if p in records]
        entry = {"id": row["id"], "line": line, "source_url": url, "named": named, "basis": basis,
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
    return (f"{entry['line']} | {', '.join(entry['named'])} ({entry['basis']}) | {action} | "
            f"{entry['source_url']}")


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

    original = path.read_text(encoding="utf-8")
    text = original
    before = _blocks(text)
    rows_by_identity = {(str(r.get("update_version")), str(r.get("source_url") or "")): r for r in rows
                        if r.get("product_id") == PRODUCT_ID}
    for entry in entries:
        # By (version, URL), never by id: an id can be shared, and `withdraw` refuses unless
        # exactly one block matches the product, the version and the URL.
        text, changed = withdraw(text, rows_by_identity[(entry["line"], entry["source_url"])], REASON)
        entry["withdrawn"] = changed
    atomic_write_text(path, text)
    new_rows = [entry["append"] for entry in entries if entry["append"] is not None]
    added_rows: list[dict] = []
    if new_rows:
        append_evidence_rows(new_rows, path, out_added=added_rows)
        close_append_gap(path)
    added_ids = {row["id"] for row in added_rows}
    after = _blocks(path.read_text(encoding="utf-8"))

    # THE SCOPE PROOF, block by block in store order. A withdrawal edits a row in place and an
    # append adds rows at the end, so: every block before is still at its position; the blocks
    # that changed are exactly the withdrawn rows, one each; everything after them is an append.
    touched_ids = [entry["id"] for entry in entries if entry["withdrawn"]]
    changed_at = [i for i, pair in enumerate(before) if i >= len(after) or after[i] != pair]
    changed_ids = sorted(before[i][0] for i in changed_at)
    missing = [before[i][0] for i in changed_at if i >= len(after) or after[i][0] != before[i][0]]
    unexpected = sorted(row_id for row_id, _sha in after[len(before):] if row_id not in added_ids)
    if changed_ids != sorted(touched_ids) or missing or unexpected \
            or len(after) != len(before) + len(added_rows):
        atomic_write_text(path, original)               # all or nothing: put the store back
        raise SystemExit(f"refusing, store restored: scope proof failed (changed {changed_ids[:3]}, "
                         f"expected {sorted(touched_ids)[:3]}, missing {missing[:3]}, "
                         f"unexpected {unexpected[:3]})")
    sha_before = {before[i][0]: before[i][1] for i in changed_at}
    sha_after = {after[i][0]: after[i][1] for i in changed_at}
    appended_sha = dict(after[len(before):])
    receipt = {
        "tool": Path(__file__).name, "product_id": PRODUCT_ID, "reason": REASON,
        "rows_before": len(before), "rows_after": len(after),
        "untouched_rows": len(before) - len(changed_at), "untouched_rows_identical": True,
        "proof": "every block compared by position in store order; ids are not unique",
        "withdrawn": [{"id": e["id"], "line": e["line"], "named": e["named"], "basis": e["basis"],
                       "source_url": e["source_url"],
                       "block_sha256_before": sha_before.get(e["id"], ""),
                       "block_sha256_after": sha_after.get(e["id"], ""),
                       "already_held_for": e["already_held_for"],
                       "append_refused": e["append_refused"]} for e in entries],
        "appended": [{"id": row["id"], "update_version": row["update_version"],
                      "source_url": row["source_url"], "match_basis": row["match_basis"],
                      "from_line_row": next(e["id"] for e in entries
                                            if e["append"] is not None
                                            and e["append"]["id"] == row["id"]),
                      "block_sha256": appended_sha.get(row["id"], "")} for row in added_rows],
    }
    target = Path(args.receipt) if args.receipt else RECEIPT_DIR / "davinci_release_line_identity.json"
    target.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"withdrawn {sum(1 for e in entries if e['withdrawn'])}, appended {len(added_rows)}, "
          f"{receipt['untouched_rows']} other rows byte-identical; receipt {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
