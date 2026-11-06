#!/usr/bin/env python3
"""READ-ONLY, WARN-ONLY diagnostic: Microsoft Learn Q&A reports counted more than once (AUX-078).

A Learn Q&A question URL carries a title slug that follows the title, so before AUX-078 the same
report could be stored and counted twice on one patch under two slugs. The producers now dedup on
the canonical report identity (``lib.source_segments.learn_report_key``: question id + anchored
segment), which stops NEW duplicates. It cannot see the ones already stored -- a producer fix proves
"this cannot be produced", never "this is not present" -- so this replays the store and names them.

What it prints (no third-party text: question ids and store positions only, never titles or slugs):
  * class (a): within ONE patch identity's authoritative counted population
    (``report_counts.counted_evidence_rows``, Windows gate included), two or more counted rows that
    share one canonical Learn report identity. Each is one report counted N times.
  * store-wide, any counted state: rows on one (product, version, build) that share a canonical
    identity under a different spelling -- what the canonical append guard would now refuse.

It never writes, never fails a build and never decides anything: exit 0 whatever it finds (WARN
lines), exit 2 only when the store or records cannot be read. Withdrawing a stored duplicate is an
audited, separate correction; this only reports.

Usage: python auxsays/scripts/audit_learn_report_identity.py [--root <auxsays dir>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.patch_identity import key_from  # noqa: E402
from lib.report_counts import (  # noqa: E402
    EvidenceStoreError, counted_evidence_rows, load_evidence_store,
    windows_targets_from_front_matter,
)
from lib.source_segments import learn_report_key  # noqa: E402
from patch_collectors.base import load_front_matter_and_body  # noqa: E402

AUX = SCRIPT_DIR.parent


def _records(aux_root: Path) -> list[dict]:
    out = []
    for path in sorted((aux_root / "updates" / "generated").glob("*.md")):
        data, _body = load_front_matter_and_body(path)
        if isinstance(data, dict) and data.get("update_entry") is True:
            out.append(data)
    return out


def class_a_groups(rows: list[dict], records: list[dict]) -> list[dict]:
    """Counted duplicates: per identity of the authoritative population, canonical Learn identities
    held by more than one counted row. Sorted, so the output is reproducible."""
    position = {id(row): index for index, row in enumerate(rows)}
    groups = counted_evidence_rows(rows, windows_targets=windows_targets_from_front_matter(records))
    found = []
    for identity in sorted(groups):
        buckets: dict[str, list[int]] = {}
        for row in groups[identity]:
            key = learn_report_key(str(row.get("source_url") or ""))
            if key:
                buckets.setdefault(key, []).append(position.get(id(row), -1))
        for key in sorted(buckets):
            if len(buckets[key]) > 1:
                found.append({"identity": identity, "report_key": key,
                              "store_rows": sorted(buckets[key])})
    return found


def stored_spelling_groups(rows: list[dict]) -> list[dict]:
    """Any counted state: one (product, version, build) holding one canonical Learn identity under
    more than one distinct spelling. The first row is what the append guard keeps; the rest are
    what it would now refuse."""
    buckets: dict[tuple, list[tuple[int, str]]] = {}
    for index, row in enumerate(rows):
        url = str(row.get("source_url") or "")
        key = learn_report_key(url)
        if not key:
            continue
        try:
            identity = key_from(row)
        except Exception:  # noqa: BLE001 - an unkeyable row belongs to no identity
            continue
        buckets.setdefault((identity, key), []).append((index, url.strip().rstrip("/").lower()))
    found = []
    for (identity, key), members in sorted(buckets.items()):
        if len({spelling for _i, spelling in members}) > 1:
            found.append({"identity": identity, "report_key": key,
                          "store_rows": [i for i, _s in members]})
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", type=Path, default=AUX,
                        help="the site tree to read (default: this repository's auxsays/)")
    args = parser.parse_args(argv)
    aux_root = args.root.resolve()
    store = aux_root / "_data" / "consensus_evidence.yml"
    try:
        rows = load_evidence_store(store)
        records = _records(aux_root)
        class_a = class_a_groups(rows, records)
    except (EvidenceStoreError, OSError) as exc:
        print(f"learn_report_identity: cannot read inputs: {exc}")
        return 2
    spellings = stored_spelling_groups(rows)
    learn_rows = sum(1 for row in rows if learn_report_key(str(row.get("source_url") or "")))
    print("learn_report_identity: read-only diagnostic (AUX-078); WARN-only, exit 0 whatever it finds")
    print(f"store rows={len(rows)} learn_qna_rows={learn_rows}")
    print(f"class (a) counted duplicate groups: {len(class_a)} "
          f"(excess counted rows: {sum(len(g['store_rows']) - 1 for g in class_a)})")
    for group in class_a:
        product, version, build = group["identity"]
        print(f"WARN class_a product={product} version={version} build={build or '-'} "
              f"report={group['report_key']} counted_rows={len(group['store_rows'])} "
              f"store_rows={group['store_rows']}")
    refused = sum(len(g["store_rows"]) - 1 for g in spellings)
    print(f"store-wide identities held under more than one spelling (any counted state): "
          f"{len(spellings)} groups, {refused} rows the canonical guard would now refuse")
    for group in spellings:
        product, version, build = group["identity"]
        print(f"INFO spelling product={product} version={version} build={build or '-'} "
              f"report={group['report_key']} store_rows={group['store_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
