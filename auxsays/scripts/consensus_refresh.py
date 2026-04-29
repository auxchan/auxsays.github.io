#!/usr/bin/env python3
"""AUXSAYS consensus refresh scaffold.

This script intentionally does not scrape public communities yet. It codifies and audits
AUXSAYS' global consensus rule so future collectors cannot count vague reports.

Global rule:
- Count only confirmed patch-specific reports.
- A report is confirmed when the exact patch/version is named in the report itself
  or in the parent discussion/thread title.
- Replies inside a patch-specific parent thread count unless the reply explicitly
  shifts to another version or unrelated issue.
- Every confirmed report is counted equally.
- Low-context mentions are excluded, not downweighted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"
RULES_PATH = ROOT / "_data" / "consensus_rules.yml"
POLICY_ID = "confirmed_patch_specific_reports_v1"


def load_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def classify_record(front: dict[str, Any]) -> dict[str, Any]:
    count = int(front.get("update_report_count") or 0)
    policy = front.get("consensus_match_policy")
    status = front.get("consensus_collection_status") or "unknown"
    warnings: list[str] = []
    if policy != POLICY_ID:
        warnings.append("missing_or_legacy_consensus_policy")
    if front.get("consensus_low_context_policy") not in ("excluded", None):
        warnings.append("low_context_policy_not_excluded")
    if front.get("consensus_report_weighting") not in ("equal_per_confirmed_report", None):
        warnings.append("report_weighting_not_equal")
    if count > 0 and status in ("deferred_official_only", "unknown"):
        warnings.append("record_has_reports_but_collection_status_not_static_or_live")
    return {
        "title": front.get("title"),
        "product_id": front.get("product_id"),
        "version": front.get("update_version"),
        "report_count": count,
        "consensus_label": front.get("update_consensus_label"),
        "collection_status": status,
        "policy": policy,
        "warnings": warnings,
    }


def audit() -> dict[str, Any]:
    rules = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) if RULES_PATH.exists() else {}
    records = []
    for path in sorted(GENERATED_DIR.glob("*.md")):
        front = load_front_matter(path)
        if not front.get("update_entry"):
            continue
        item = classify_record(front)
        item["path"] = str(path.relative_to(ROOT))
        records.append(item)
    return {
        "policy_id": rules.get("policy_id") or POLICY_ID,
        "match_required": rules.get("match_required", True),
        "exclude_low_context": rules.get("exclude_low_context", True),
        "equal_weight_reports": rules.get("equal_weight_reports", True),
        "record_count": len(records),
        "records_with_reports": sum(1 for item in records if item["report_count"] > 0),
        "total_confirmed_patch_specific_reports": sum(item["report_count"] for item in records),
        "warnings": [item for item in records if item["warnings"]],
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit AUXSAYS global consensus policy metadata.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()
    result = audit()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Policy: {result['policy_id']}")
        print(f"Records: {result['record_count']}")
        print(f"Records with confirmed patch-specific reports: {result['records_with_reports']}")
        print(f"Total confirmed patch-specific reports: {result['total_confirmed_patch_specific_reports']}")
        if result["warnings"]:
            print("Warnings:")
            for item in result["warnings"]:
                print(f"- {item['path']}: {', '.join(item['warnings'])}")
        else:
            print("Consensus metadata audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
