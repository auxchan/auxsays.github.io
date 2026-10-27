#!/usr/bin/env python3
"""One-time, zero-network labelling of platform-split records that the refresh window can never reach.

AUX-050 taught the Zendesk adapter to establish `official_notes_platform: windows_macos` from the
product's own installers, and the writer stores it on create and on refresh. It cannot reach records
created before that change and older than the adapter's refresh window: each run re-observes only the
newest records it sees, so an older record is never re-observed. On a product flagged
`official_notes_by_platform`, My Patch Stack compares a reader only with releases whose platform is
known, so a reader on one of those versions would see PLATFORM APPLICABILITY UNKNOWN forever.

This migration applies the SHIPPED classifier, `zendesk_help_center.joint_platform_downloads`, to the
notes each record already stores. It makes no network request, runs no adapter and no collector, and
reads nothing but generated records and the two catalogues. It is deterministic and idempotent: a
second run reports 0 changes.

Scope, exactly:
    products   those flagged official_notes_by_platform in patch_products.yml
    records    those with NO official_notes_platform
    action     add official_notes_platform: windows_macos and official_notes_platform_basis:
               installer_downloads, appended through the writer's own serializer
It never removes or changes a label, never touches a title or any other field, and labels nothing
the stored notes do not establish. A record whose notes establish nothing is reported, not guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from adapters import zendesk_help_center as zendesk  # noqa: E402
from lib import write_update_record as writer  # noqa: E402

AUX = Path(__file__).resolve().parents[1]
RECORDS = AUX / "updates" / "generated"
PRODUCTS = AUX / "_data" / "patch_products.yml"
SOURCES = AUX / "_data" / "patch_ingestion_sources.yml"


def flagged_products(products_path: Path = PRODUCTS) -> set[str]:
    products = yaml.safe_load(products_path.read_text(encoding="utf-8")) or []
    return {str(p.get("id")) for p in products if isinstance(p, dict) and p.get("official_notes_by_platform") is True}


def installer_names(sources_path: Path = SOURCES) -> dict[str, tuple[str, ...]]:
    sources = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or []
    return {str(s.get("product_id")): zendesk._installer_names(s) for s in sources if isinstance(s, dict)}


def plan(records_dir: Path, flagged: set[str], names: dict[str, tuple[str, ...]]) -> list[dict]:
    """One entry per in-scope record: its path, its decision, and the text it would be written as."""
    entries: list[dict] = []
    for path in sorted(records_dir.glob("*.md")):
        front, body = writer._front_matter(path)
        product_id = str(front.get("product_id") or "")
        if product_id not in flagged or "official_notes_platform" in front:
            continue
        version = str(front.get("update_version") or "")
        notes = " ".join(zendesk.strip_tags(str(front.get("official_patch_notes_body") or "")).split())
        joint, installers_seen = zendesk.joint_platform_downloads(notes, version, names.get(product_id, ()))
        entry = {"path": path, "product_id": product_id, "version": version,
                 "decision": "label" if joint else ("unverified" if installers_seen else "no_installers")}
        if joint:
            labelled = dict(front)
            labelled["official_notes_platform"] = joint
            labelled["official_notes_platform_basis"] = "installer_downloads"
            entry["text"] = writer._dump_record(labelled, body)
        entries.append(entry)
    return entries


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default=str(RECORDS))
    ap.add_argument("--products", default=str(PRODUCTS))
    ap.add_argument("--sources", default=str(SOURCES))
    ap.add_argument("--write", action="store_true", help="write the records (default: report only)")
    args = ap.parse_args(argv)

    records_dir = Path(args.records)
    entries = plan(records_dir, flagged_products(Path(args.products)), installer_names(Path(args.sources)))
    to_write = [e for e in entries if e["decision"] == "label"]
    before = {p.name: _digest(p) for p in records_dir.glob("*.md")}
    if args.write:
        for entry in to_write:
            entry["path"].write_bytes(entry["text"].encode("utf-8"))
        # SCOPE PROOF: every file other than the labelled ones is byte-identical.
        after = {p.name: _digest(p) for p in records_dir.glob("*.md")}
        touched = sorted(n for n in after if after[n] != before.get(n)) + sorted(set(before) - set(after))
        expected = sorted(e["path"].name for e in to_write)
        if touched != expected:
            print(json.dumps({"error": "scope_violation", "touched": touched, "expected": expected}))
            return 1
    print(json.dumps({
        "mode": "write" if args.write else "dry_run",
        "records_scanned": len(before),
        "in_scope": len(entries),
        "labelled": [f"{e['product_id']} {e['version']}" for e in to_write],
        "not_labelled": [f"{e['product_id']} {e['version']}: {e['decision']}" for e in entries if e["decision"] != "label"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
