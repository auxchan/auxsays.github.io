#!/usr/bin/env python3
"""One-time, zero-network repair of generated-record text that a local run once decoded as cp1252 (G39).

WHAT HAPPENED. On 2026-05-02 a local, one-off pass over generated records (commit a02573fd, "Add file
size status to generated records") read UTF-8 files with the Windows default code page and wrote them
back as UTF-8. Every curly quote and dash in the text it touched became three characters: "agent's"
with a curly apostrophe was stored as "agent" + "â€™" + "s". The collectors were never at fault -- the
same items were first written correctly (bfa5cf73), and a later official refresh re-captured one body
correctly -- and that pass is not part of the repository, so no producer reproduces it. What it left
behind is frozen: a refresh never rewrites a stored title, and the ingestion lane re-observes only the
newest records of each source, so these records are never seen again. This is the situation
migrate_official_notes_platform_backlog.py was written for, and this follows it.

WHAT THIS DOES. For every generated record, each TOP-LEVEL text field is repaired only when undoing
the misreading is exact: the stored text must contain the misreading's signature, must encode back to
cp1252 without loss, and those bytes must be valid UTF-8. Anything else is left alone, and a field that
carries the signature but cannot be repaired exactly is REPORTED, never guessed at. Nested values are
never touched: under a record they are copies of evidence rows (accepted_report_sources), and the
evidence store is not this migration's to change.

It makes no network request, runs no adapter and no collector, and reads nothing but generated records.
It writes through the writer's own serializer (lib/write_update_record._dump_record), proves its scope
by hashing every record before and after, and is idempotent: a second run reports 0 changes.

Run:  python auxsays/scripts/migrate_repair_transcoded_text.py [--records DIR] [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import write_update_record as writer  # noqa: E402

AUX = Path(__file__).resolve().parents[1]
RECORDS = AUX / "updates" / "generated"

# The misreading's signature: a UTF-8 lead byte shown as its cp1252 character -- 0xE2 (typographic
# punctuation: curly quotes, dashes, ellipsis, euro, trade mark) followed by two continuation bytes, or
# 0xC2/0xC3 (no-break space, Latin-1 letters) followed by one -- each continuation byte 0x80-0xBF also
# shown as its cp1252 character. Built from byte values so no editor can decode it into what it matches.
_CONT = "[" + re.escape(bytes(range(0x80, 0xC0)).decode("cp1252", errors="ignore")) + "]"
SIGNATURE = re.compile(chr(0xE2) + _CONT + _CONT + "|[" + chr(0xC2) + chr(0xC3) + "]" + _CONT)


def repair_text(value: str) -> str | None:
    """The text before it was misread, or None when the value does not carry the misreading or cannot be
    repaired exactly (the caller then leaves it alone)."""
    if not SIGNATURE.search(value):
        return None
    try:
        fixed = value.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return None
    return fixed if fixed != value and not SIGNATURE.search(fixed) else None


def plan(records_dir: Path) -> list[dict]:
    """One entry per record that carries the signature: its repaired fields, its unrepairable ones, and
    (when anything is repaired) the text it would be written as."""
    entries: list[dict] = []
    for path in sorted(records_dir.glob("*.md")):
        if not SIGNATURE.search(path.read_text(encoding="utf-8")):
            continue
        front, body = writer._front_matter(path)
        repaired = dict(front)
        fields: list[str] = []
        suspect: list[str] = []
        for key, value in front.items():
            if not isinstance(value, str) or not SIGNATURE.search(value):
                continue
            fixed = repair_text(value)
            if fixed is None:
                suspect.append(key)
            else:
                repaired[key] = fixed
                fields.append(key)
        if not fields and not suspect:
            continue  # the signature is only in nested evidence copies
        entry = {"path": path, "product_id": str(front.get("product_id") or ""),
                 "fields": fields, "suspect": suspect}
        if fields:
            entry["text"] = writer._dump_record(repaired, body)
            entry["repaired"] = {k: repaired[k] for k in fields}
            entry["front"] = front
        entries.append(entry)
    return entries


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--records", default=str(RECORDS))
    ap.add_argument("--write", action="store_true", help="write the records (default: report only)")
    args = ap.parse_args(argv)

    records_dir = Path(args.records)
    entries = plan(records_dir)
    to_write = [e for e in entries if e["fields"]]
    before = {p.name: _digest(p) for p in records_dir.glob("*.md")}
    if args.write:
        for entry in to_write:
            entry["path"].write_bytes(entry["text"].encode("utf-8"))
        # SCOPE PROOF: every file other than the repaired ones is byte-identical, and in a repaired one
        # every field other than the repaired ones reads back unchanged.
        after = {p.name: _digest(p) for p in records_dir.glob("*.md")}
        touched = sorted(n for n in after if after[n] != before.get(n)) + sorted(set(before) - set(after))
        expected = sorted(e["path"].name for e in to_write)
        moved = []
        for entry in to_write:
            front, _ = writer._front_matter(entry["path"])
            want = {**entry["front"], **entry["repaired"]}
            moved += [f"{entry['path'].name}:{key}" for key in sorted(set(front) | set(want))
                      if front.get(key) != want.get(key)]
        if touched != expected or moved:
            print(json.dumps({"error": "scope_violation", "touched": touched, "expected": expected,
                              "moved": moved}))
            return 1
    print(json.dumps({
        "mode": "write" if args.write else "dry_run",
        "records_scanned": len(before),
        "repaired": {e["path"].name: e["fields"] for e in to_write},
        "not_repaired": {e["path"].name: e["suspect"] for e in entries if e["suspect"]},
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
