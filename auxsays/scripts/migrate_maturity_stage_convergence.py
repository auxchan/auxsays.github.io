#!/usr/bin/env python3
"""One-time, zero-network convergence of `intelligence_stage` onto the one maturity authority.

`lib.maturity` now owns all four stored maturity axes, and reconciliation writes all four. Before it
did, reconciliation wrote three of them and never `intelligence_stage`, and the writers disagreed on
the zero-report stage. 24 records were left holding a stage their other three axes contradict:

    13  official_only, 0 reports, stage `pilot`       demoted to zero; the stage stayed behind
     1  official_only, 0 reports, stage `manual_watch` the consensus writer's old zero-count literal
    10  official_only, 0 reports, no stage at all      created before the field existed

The `manual_watch` record is not a manual watch. Its history shows the consensus writer set the
stage when its one report was withdrawn (2026-10-09, "User report count updated to 0."); a
product-level manual watch is SOURCE configuration (`patch_ingestion_sources.yml` `type:
manual_watch`), a different field this migration does not read or touch.

It must land WITH the writer change. The 6-hourly evidence lane reconciles every product, so once
reconciliation writes the stage it would rewrite all 24 in the lane -- and 10 of them (comfyui,
figma, github) are outside that lane's writeback allow-list, so the writeback would refuse with
UNEXPECTED_CHANGED_PATH and discard the cycle's evidence for every product.

Scope, exactly:
    records  update entries whose ONLY maturity contradiction (`lib.maturity.contradictions`) is
             `intelligence_stage`
    action   set `intelligence_stage` to the canonical value for the record's count, as a one-line
             in-place edit (replace the line, or insert it after `evidence_state_label`)
It changes no count, verdict, label, state, status or any other field. A record whose other axes
also disagree is reported, never written. Deterministic and idempotent: a second run changes nothing.
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

from lib import maturity  # noqa: E402

AUX = Path(__file__).resolve().parents[1]
RECORDS = AUX / "updates" / "generated"
STAGE_LINE = re.compile(r"^intelligence_stage:[^\n]*$", re.M)
ANCHOR_LINE = re.compile(r"^evidence_state_label:[^\n]*\n", re.M)


def _split(text: str) -> tuple[str, str] | None:
    """(front matter text including its trailing newline, the rest) or None if not a record."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    return text[4:end + 1], text[end + 1:]


def _count(front: dict) -> int:
    try:
        return int(front.get("update_report_count") or front.get("confirmed_patch_specific_report_count") or 0)
    except (TypeError, ValueError):
        return 0


def converge_text(text: str) -> tuple[str, dict] | None:
    """The record rewritten with its canonical stage, and a description; None if out of scope."""
    parts = _split(text)
    if parts is None:
        return None
    front_text, rest = parts
    front = yaml.safe_load(front_text) or {}
    if not isinstance(front, dict) or front.get("update_entry") is not True:
        return None
    count = _count(front)
    differing = maturity.contradictions(front, count)
    if differing != ["intelligence_stage"]:
        return None
    stage = maturity.maturity_for(count).intelligence_stage
    line = f"intelligence_stage: {stage}"
    if STAGE_LINE.search(front_text):
        new_front = STAGE_LINE.sub(line, front_text, count=1)
    else:
        anchor = ANCHOR_LINE.search(front_text)
        if anchor is None:
            return None
        new_front = front_text[:anchor.end()] + line + "\n" + front_text[anchor.end():]
    # Prove the edit: the parsed front matter differs in exactly the one key, to the one value.
    after = yaml.safe_load(new_front) or {}
    if {k: v for k, v in after.items() if k != "intelligence_stage"} != \
            {k: v for k, v in front.items() if k != "intelligence_stage"} or after.get("intelligence_stage") != stage:
        raise RuntimeError("in-place stage edit changed more than intelligence_stage")
    return "---\n" + new_front + rest, {"product_id": front.get("product_id"),
                                        "version": str(front.get("update_version") or ""),
                                        "from": front.get("intelligence_stage"), "to": stage}


def plan(records_dir: Path) -> tuple[list[dict], list[str]]:
    """Records to converge, and records whose maturity disagrees on more than the stage (reported)."""
    entries: list[dict] = []
    other: list[str] = []
    for path in sorted(records_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        result = converge_text(text)
        if result is not None:
            new_text, detail = result
            entries.append({"path": path, "text": new_text, **detail})
            continue
        parts = _split(text)
        front = (yaml.safe_load(parts[0]) or {}) if parts else {}
        if isinstance(front, dict) and front.get("update_entry") is True:
            differing = maturity.contradictions(front, _count(front))
            if differing and differing != ["intelligence_stage"]:
                other.append(f"{path.name}: {', '.join(differing)}")
    return entries, other


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default=str(RECORDS))
    ap.add_argument("--write", action="store_true", help="write the records (default: report only)")
    args = ap.parse_args(argv)

    records_dir = Path(args.records)
    entries, other = plan(records_dir)
    before = {p.name: _digest(p) for p in records_dir.glob("*.md")}
    if args.write:
        for entry in entries:
            entry["path"].write_bytes(entry["text"].encode("utf-8"))
        # SCOPE PROOF: every file other than the converged ones is byte-identical.
        after = {p.name: _digest(p) for p in records_dir.glob("*.md")}
        touched = sorted(n for n in after if after[n] != before.get(n)) + sorted(set(before) - set(after))
        expected = sorted(e["path"].name for e in entries)
        if touched != expected:
            print(json.dumps({"error": "scope_violation", "touched": touched, "expected": expected}))
            return 1
    print(json.dumps({
        "mode": "write" if args.write else "dry_run",
        "records_scanned": len(before),
        "converged": [f"{e['product_id']} {e['version']}: {e['from']!r} -> {e['to']}" for e in entries],
        "not_converged_other_axes_disagree": other,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
