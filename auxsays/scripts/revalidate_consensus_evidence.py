#!/usr/bin/env python3
"""Dry-run classification harness for existing consensus evidence rows.

This script is intentionally fixture-only for now. It reads structured evidence
from an explicit input path, classifies rows for a product/version, and never
fetches source URLs or writes files.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - used in lightweight local shells.
    yaml = None


MODE = "dry_run_fixture_revalidation_no_fetch_no_write"
CLASSIFICATIONS = (
    "pending_source_adapter",
    "unsupported_source_type",
    "missing_url",
    "malformed_row",
    "candidate_for_revalidation",
)
CORE_FIELDS = ("product_id", "update_version", "source_type")
REVALIDATION_CANDIDATE_SOURCE_TYPES = {
    "github_issue",
}
PENDING_SOURCE_ADAPTER_TYPES = {
    "adobe_community_bug_report",
    "adobe_community_listing_card",
    "blackmagic_forum",
    "creativecow_forum_report",
    "creator_forum_report",
    "curated_watchlist",
    "reddit_community_report",
}


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def simple_evidence_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    saw_evidence_key = any(line.strip() == "evidence:" for line in text.splitlines())
    in_evidence = not saw_evidence_key

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        stripped = raw_line.strip()
        top_level = not raw_line.startswith((" ", "\t"))
        if top_level and stripped == "evidence:":
            in_evidence = True
            continue
        if top_level and saw_evidence_key and not stripped.startswith("- ") and stripped.endswith(":"):
            in_evidence = stripped == "evidence:"
            continue
        if stripped.startswith("- ") and in_evidence:
            if current:
                rows.append(current)
            current = {}
            remainder = stripped[2:]
            if ":" in remainder:
                key, value = remainder.split(":", 1)
                current[key.strip()] = parse_scalar(value)
            continue
        if current is not None and in_evidence and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = parse_scalar(value)
    if current:
        rows.append(current)
    return rows


def load_evidence_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        payload = yaml.safe_load(text) or {}
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            evidence = payload.get("evidence") or []
            return [item for item in evidence if isinstance(item, dict)]
        return []
    return simple_evidence_rows(text)


def is_counted(row: dict[str, Any]) -> bool:
    return row.get("counted") is True


def selected_rows(rows: list[dict[str, Any]], product_id: str, update_version: str) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("product_id") or "").strip() == product_id
        and str(row.get("update_version") or "").strip() == update_version
        and is_counted(row)
    ]


def classify_row(row: dict[str, Any]) -> tuple[str, str]:
    missing_core = [field for field in CORE_FIELDS if row.get(field) in (None, "")]
    if missing_core:
        return ("malformed_row", "missing core field(s): " + ", ".join(missing_core))
    if row.get("patch_version_matched") is not True:
        return ("malformed_row", "patch_version_matched is not true")
    source_url = str(row.get("source_url") or "").strip()
    if not source_url:
        return ("missing_url", "source_url is missing")
    source_type = str(row.get("source_type") or "").strip()
    if source_type in REVALIDATION_CANDIDATE_SOURCE_TYPES:
        return ("candidate_for_revalidation", "source type has a fixture-safe adapter contract")
    if source_type in PENDING_SOURCE_ADAPTER_TYPES:
        return ("pending_source_adapter", "source type is known but has no revalidation adapter in this harness")
    return ("unsupported_source_type", f"unsupported source_type: {source_type}")


def compact_row(row: dict[str, Any], classification: str, reason: str, index: int) -> dict[str, Any]:
    return {
        "row_index": index,
        "classification": classification,
        "reason": reason,
        "id": row.get("id"),
        "product_id": row.get("product_id"),
        "update_version": row.get("update_version"),
        "source_type": row.get("source_type"),
        "source_url": row.get("source_url"),
    }


def revalidate(evidence_file: Path, product_id: str, update_version: str) -> dict[str, Any]:
    rows = load_evidence_rows(evidence_file)
    selected = selected_rows(rows, product_id, update_version)
    classified: list[dict[str, Any]] = []
    counts = {name: 0 for name in CLASSIFICATIONS}
    for index, row in enumerate(selected, start=1):
        classification, reason = classify_row(row)
        counts[classification] += 1
        classified.append(compact_row(row, classification, reason, index))

    matching_rows = [
        row for row in rows
        if str(row.get("product_id") or "").strip() == product_id
        and str(row.get("update_version") or "").strip() == update_version
    ]
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": MODE,
        "fetches_urls": False,
        "writes_files": False,
        "evidence_file": str(evidence_file),
        "product_id": product_id,
        "update_version": update_version,
        "total_rows_loaded": len(rows),
        "matching_rows": len(matching_rows),
        "counted_rows_selected": len(selected),
        "non_counted_rows_skipped": len(matching_rows) - len(selected),
        "classification_counts": counts,
        "rows": classified,
    }


def print_summary(result: dict[str, Any]) -> None:
    print("AUXSAYS consensus evidence revalidation dry run")
    print(f"Mode: {result['mode']}")
    print(f"Evidence file: {result['evidence_file']}")
    print(f"Product/version: {result['product_id']} {result['update_version']}")
    print(f"Rows loaded: {result['total_rows_loaded']}")
    print(f"Matching rows: {result['matching_rows']}")
    print(f"Counted rows selected: {result['counted_rows_selected']}")
    print(f"Non-counted rows skipped: {result['non_counted_rows_skipped']}")
    print("Classification counts:")
    for name in CLASSIFICATIONS:
        label = name.replace("_", " ")
        print(f"- {label}: {result['classification_counts'].get(name, 0)}")
    print("No URLs fetched. No files written.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify fixture evidence rows for future revalidation.")
    parser.add_argument("--evidence-file", required=True, help="Fixture/input evidence YAML file.")
    parser.add_argument("--product", required=True, help="Product ID to select.")
    parser.add_argument("--version", required=True, help="Update version to select.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--summary", action="store_true", help="Print concise human-readable output.")
    output.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args(argv)

    result = revalidate(Path(args.evidence_file), args.product, args.version)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
