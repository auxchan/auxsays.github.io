#!/usr/bin/env python3
"""Re-derive the stored Microsoft Teams rows' classification through the shipped producer.

Before the Teams classification repair (#206) the collector wrote the constant platform "Windows"
(capitalised, off-vocabulary, and not read from the report) and never classified a row: theme, workflow
area and severity are "" on every row it wrote. Rows are append-only inside a collector run, so nothing
else will ever correct them.

THIS SCRIPT CONSUMES THE SHIPPED CLASSIFIER. It calls `microsoft_teams._classify_candidate` (the very
function the collector calls, so the heading is built the producer's way) on the retained text, and
copies no rule. A rule change there changes what this writes; nothing here has to follow it.

A ROW IS IN SCOPE ONLY WHEN IT IS RECOGNISABLY LEGACY: its platform is outside the producer's
vocabulary (windows / macos / linux / unknown) and its theme, workflow area and severity are all empty.
A row the repaired producer wrote carries a lowercase platform and was classified from the FULL report
text, which the truncated stored excerpt may no longer reproduce, so such a row is never re-judged.

  platform  legacy constant               -> the resolver's answer for the retained text
  theme     the producer finds a theme    -> theme, workflow area and severity, as one unit
            the producer finds none       -> left empty (no theme or severity is ever invented)

NEVER WRITTEN: sentiment (verdict-bearing), counted, exclusion_reason, identity, URLs, dates, weights,
version-match fields and the text itself. The shared block-scoped editor refuses any other key.

Zero network. Stored text only.

Run:  python auxsays/scripts/recompute_teams_classification.py            # dry run, JSON on stdout
      python auxsays/scripts/recompute_teams_classification.py --write    # in-place, block-scoped
      ... --audit PATH --parent-commit SHA                                  # also write the manifest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from lib import evidence_classification as ec  # noqa: E402
from patch_collectors import microsoft_teams as teams  # noqa: E402
from recompute_evidence_classification import WRITABLE, apply_writes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "_data" / "consensus_evidence.yml"
PRODUCT_ID = teams.TEAMS_PRODUCT_ID
PLATFORM_VOCABULARY = frozenset({"windows", "macos", "linux", ec.UNKNOWN_PLATFORM})
EMPTY_FIELDS = ("issue_theme", "workflow_area", "severity")
CLASSIFIER_FILES = (
    "scripts/patch_collectors/microsoft_teams.py",
    "scripts/lib/evidence_classification.py",
    "scripts/recompute_teams_classification.py",
)


def _s(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) or "")


def is_legacy(row: dict[str, Any]) -> bool:
    return _s(row, "platform") not in PLATFORM_VOCABULARY and not any(_s(row, f) for f in EMPTY_FIELDS)


def shipped(row: dict[str, Any]) -> tuple[str, str, str, str]:
    """(theme, workflow_area, platform, severity) from the producer, on the retained text."""
    return teams._classify_candidate(_s(row, "parent_title"), _s(row, "report_title"),
                                     _s(row, "report_text_excerpt"))


def decide(row: dict[str, Any]) -> dict[str, Any]:
    """The decision for one Teams row: the fields to write (possibly none) and why."""
    out: dict[str, Any] = {"id": row.get("id"), "counted": bool(row.get("counted")), "write": {},
                           "basis": "", "theme": ""}
    if not is_legacy(row):
        out["basis"] = "skipped_not_legacy"
        return out
    theme, area, platform, severity = shipped(row)
    if platform not in PLATFORM_VOCABULARY:
        raise SystemExit(f"refusing {row.get('id')}: producer platform {platform!r} is off-vocabulary")
    out["basis"] = "legacy"
    out["write"]["platform"] = platform
    if theme:
        if severity not in ec.VALID_SEVERITIES:
            raise SystemExit(f"refusing {row.get('id')}: severity {severity!r} is not a supported value")
        out["write"].update({"issue_theme": theme, "workflow_area": area, "severity": severity})
    out["theme"] = theme or "unclassified"
    return out


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(store: Path, write: bool) -> dict[str, Any]:
    raw = store.read_bytes().decode("utf-8")
    rows = yaml.load(raw, Loader=yaml.SafeLoader)["evidence"]
    decisions = [(index, decide(row)) for index, row in enumerate(rows) if _s(row, "product_id") == PRODUCT_ID]
    writes = {index: d["write"] for index, d in decisions if d["write"]}
    new_text = apply_writes(raw, [row.get("id") for row in rows], writes)
    after_rows = yaml.load(new_text, Loader=yaml.SafeLoader)["evidence"]
    # Prove the edit is exactly the decided one: every other field of every row is unchanged.
    if len(after_rows) != len(rows):
        raise SystemExit("refusing: the row count changed")
    for index, (old, new) in enumerate(zip(rows, after_rows)):
        if new != dict(old, **writes.get(index, {})):
            raise SystemExit(f"refusing row {index} ({old.get('id')}): the edit changed more than decided")
        if set(writes.get(index, {})) - WRITABLE:
            raise SystemExit(f"refusing row {index}: not writable")

    def tally(getter) -> dict[str, int]:
        counts: dict[str, int] = {}
        for index, d in decisions:
            key = getter(index, d) or '""'
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def after_value(field: str):
        return lambda index, _d: _s(after_rows[index], field)

    summary = {
        "platform_before": tally(lambda i, d: _s(rows[i], "platform")),
        "platform_after": tally(after_value("platform")),
        "issue_theme_after": tally(after_value("issue_theme")),
        "workflow_area_after": tally(after_value("workflow_area")),
        "severity_after": tally(after_value("severity")),
        "basis": tally(lambda i, d: d["basis"]),
        "counted_rows_changed": sum(1 for i, d in decisions if d["write"] and d["counted"]),
    }
    changes = [{"index": index, "id": rows[index].get("id"), "update_version": rows[index].get("update_version"),
                "counted": bool(rows[index].get("counted")),
                **{f: [_s(rows[index], f), v] for f, v in fields.items()}}
               for index, fields in sorted(writes.items())]
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "store_sha256_before": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "store_sha256_after": hashlib.sha256(new_text.encode("utf-8")).hexdigest(),
        "rows_in_scope": len(decisions), "rows_changed": len(writes),
        "fields_written": {f: sum(f in w for w in writes.values()) for f in sorted(WRITABLE)},
        "summary": summary, "changes": changes, "written": False,
    }
    if write and writes:
        store.write_bytes(new_text.encode("utf-8"))
        report["written"] = True
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--store", type=Path, default=STORE)
    parser.add_argument("--write", action="store_true", help="apply the decided edits in place")
    parser.add_argument("--audit", type=Path, help="also write the before/after manifest here")
    parser.add_argument("--parent-commit", default="", help="commit the store was read at (manifest only)")
    args = parser.parse_args(argv)
    report = run(args.store, args.write)
    if args.audit:
        base = Path(__file__).resolve().parents[1]
        audit = dict(report, parent_commit=args.parent_commit,
                     classifier_sha256={name: _sha(base / name) for name in CLASSIFIER_FILES})
        args.audit.write_text(json.dumps(audit, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "changes"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
