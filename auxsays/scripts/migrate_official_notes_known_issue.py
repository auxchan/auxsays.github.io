#!/usr/bin/env python3
"""One-time, zero-network sync of `official_notes_known_issue` with the GitHub release notes each record already stores (AUX-125).

The record writer now derives `official_notes_known_issue: declared` from a GitHub-release record's
stored body on create and on every refresh. It cannot reach a record whose body was refreshed before
that change and which the refresh window does not revisit: OBS Studio 33.0.2's notes gained a known-
issue notice after publication, the scheduled run stored the edited body, and the record kept no
field. This migration applies the SHIPPED parser, `lib.notes_known_issue`, to the body each record
already stores. It makes no network request, runs no adapter and no collector, and reads nothing but
generated records. It is deterministic and idempotent: a second run reports 0 changes.

Scope, exactly:
    records    those whose official source type is github-release
    action     add the line `official_notes_known_issue: declared` as the last front-matter line where
               the stored body declares a known issue for the record's own version and the field is
               absent; remove that line where the field is present and the stored body no longer
               declares one
Only records whose state actually changes are written, and only that one line changes in each: every
other byte of the record, including the body, is preserved and verified by re-parsing. A record the
edit cannot be applied to exactly is refused and reported, never rewritten through a serializer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from lib import notes_known_issue as nki  # noqa: E402
from lib.normalize import split_front_matter  # noqa: E402

AUX = Path(__file__).resolve().parents[1]
RECORDS = AUX / "updates" / "generated"
FIELD_LINE = f"{nki.FIELD}: {nki.DECLARED}\n"
_FIELD_LINE_RE = re.compile(rf"^{re.escape(nki.FIELD)}:.*\n", re.M)


def _front(text: str) -> tuple[dict, str] | None:
    fm, body = split_front_matter(text)
    if fm is None:
        return None
    data = yaml.safe_load(fm) or {}
    return (data, body) if isinstance(data, dict) else None


def _edit(text: str, wanted: str | None) -> str | None:
    """The record text with exactly the field line added or removed, or None if that cannot be done exactly."""
    if not text.startswith("---\n"):
        return None
    close = text.find("\n---\n", 3)
    if close < 0:
        return None
    head, tail = text[:close + 1], text[close + 1:]
    present = _FIELD_LINE_RE.findall(head)
    if wanted:
        if present:
            return None   # a present-but-different value is not this migration's to rewrite
        return head + FIELD_LINE + tail
    if present != [FIELD_LINE]:
        return None
    return _FIELD_LINE_RE.sub("", head, count=1) + tail


def plan(records_dir: Path) -> list[dict]:
    """One entry per GitHub-release record: its path, decision, reason, and new text when it changes."""
    entries: list[dict] = []
    for path in sorted(records_dir.glob("*.md")):
        text = path.read_bytes().decode("utf-8")
        parsed = _front(text)
        if parsed is None:
            continue
        front, body = parsed
        if not nki.is_github_release(front):
            continue
        assessment = nki.assess(front.get("official_patch_notes_body"), front.get("update_version"))
        wanted = nki.DECLARED if assessment.declared else None
        current = front.get(nki.FIELD)
        entry = {"path": path, "product_id": str(front.get("product_id") or ""),
                 "version": str(front.get("update_version") or ""),
                 "result": assessment.result, "reason": assessment.reason}
        if current == wanted:
            entry["decision"] = "unchanged"
        else:
            new_text = _edit(text, wanted)
            reparsed = _front(new_text) if new_text is not None else None
            expected = dict(front)
            if wanted:
                expected[nki.FIELD] = wanted
            else:
                expected.pop(nki.FIELD, None)
            if reparsed is None or reparsed[0] != expected or reparsed[1] != body:
                entry["decision"] = "refused"
            else:
                entry["decision"] = "set" if wanted else "removed"
                entry["text"] = new_text
        entries.append(entry)
    return entries


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default=str(RECORDS))
    ap.add_argument("--write", action="store_true", help="write the records (default: report only)")
    args = ap.parse_args(argv)

    records_dir = Path(args.records)
    entries = plan(records_dir)
    to_write = [e for e in entries if e["decision"] in {"set", "removed"}]
    refused = [e for e in entries if e["decision"] == "refused"]
    before = {p.name: _digest(p) for p in records_dir.glob("*.md")}
    if args.write and not refused:
        for entry in to_write:
            entry["path"].write_bytes(entry["text"].encode("utf-8"))
        # SCOPE PROOF: every file other than the changed ones is byte-identical.
        after = {p.name: _digest(p) for p in records_dir.glob("*.md")}
        touched = sorted(n for n in after if after[n] != before.get(n)) + sorted(set(before) - set(after))
        expected = sorted(e["path"].name for e in to_write)
        if touched != expected:
            print(json.dumps({"error": "scope_violation", "touched": touched, "expected": expected}))
            return 1
    print(json.dumps({
        "mode": "write" if args.write and not refused else "dry_run",
        "records_scanned": len(before),
        "github_release_records": len(entries),
        "manifest": [f"{e['path'].name}: {e['decision']}" for e in to_write],
        "refused": [f"{e['path'].name}: {e['reason']}" for e in refused],
        "results": {r: sum(1 for e in entries if e["result"] == r)
                    for r in (nki.DECLARED, nki.NOT_DECLARED, nki.UNKNOWN)},
    }, indent=2))
    return 2 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
