#!/usr/bin/env python3
"""Audit generated report counts against structured consensus evidence.

This script does not scrape public communities and does not modify generated
records. It compares report-bearing patch records with the manually curated
evidence dataset so stale or manually encoded counts are visible.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - used in lightweight local shells.
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
DEFAULT_STALE_DAYS = 7


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


def simple_yaml_mapping(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for line in text.splitlines():
        if not line or line.startswith((" ", "-")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    return data


def simple_consensus_evidence(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current:
                items.append(current)
            current = {}
            remainder = stripped[2:]
            if ":" in remainder:
                key, value = remainder.split(":", 1)
                current[key.strip()] = parse_scalar(value)
            continue
        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = parse_scalar(value)
    if current:
        items.append(current)
    return items


def load_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    if yaml is not None:
        data = yaml.safe_load(parts[1]) or {}
        return data if isinstance(data, dict) else {}
    return simple_yaml_mapping(parts[1])


def load_evidence(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        payload = yaml.safe_load(text) or {}
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            evidence = payload.get("evidence") or []
            return [item for item in evidence if isinstance(item, dict)]
        return []
    return simple_consensus_evidence(text)


def record_key(data: dict[str, Any]) -> tuple[str, str]:
    return (str(data.get("product_id") or "").strip(), str(data.get("update_version") or "").strip())


def report_count(data: dict[str, Any]) -> int:
    for key in ("confirmed_patch_specific_report_count", "update_report_count"):
        value = data.get(key)
        if value not in (None, ""):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip().strip("'\"")
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def latest_time(values: list[Any]) -> str | None:
    parsed = [item for item in (parse_time(value) for value in values) if item is not None]
    if not parsed:
        return None
    return max(parsed).isoformat().replace("+00:00", "Z")


def is_stale(value: Any, *, now: datetime, stale_days: int) -> bool:
    parsed = parse_time(value)
    if parsed is None:
        return True
    return (now - parsed).days >= stale_days


def audit(stale_days: int = DEFAULT_STALE_DAYS) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    evidence = load_evidence(EVIDENCE_PATH)
    evidence_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        product_id = str(item.get("product_id") or "").strip()
        version = str(item.get("update_version") or "").strip()
        if product_id and version:
            evidence_by_key[(product_id, version)].append(item)

    generated_records: list[dict[str, Any]] = []
    generated_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(GENERATED_DIR.glob("*.md")):
        data = load_front_matter(path)
        if not data.get("update_entry"):
            continue
        key = record_key(data)
        generated_count = report_count(data)
        item = {
            "path": str(path.relative_to(ROOT)),
            "title": data.get("title"),
            "product_id": key[0],
            "update_version": key[1],
            "generated_report_count": generated_count,
            "evidence_state": data.get("evidence_state"),
            "consensus_collection_status": data.get("consensus_collection_status"),
            "update_last_checked": data.get("update_last_checked"),
            "evidence_last_checked": data.get("evidence_last_checked") or data.get("consensus_last_checked"),
        }
        generated_records.append(item)
        if key[0] and key[1]:
            generated_by_key[key] = item

    records_with_reports = [item for item in generated_records if item["generated_report_count"] > 0]
    mismatches: list[dict[str, Any]] = []
    stale_records: list[dict[str, Any]] = []

    for item in records_with_reports:
        key = (item["product_id"], item["update_version"])
        evidence_rows = evidence_by_key.get(key, [])
        counted_rows = [row for row in evidence_rows if row.get("counted") is not False]
        latest_evidence_checked = latest_time([row.get("captured_at") for row in evidence_rows])
        item["structured_evidence_count"] = len(counted_rows)
        item["structured_evidence_exists"] = bool(evidence_rows)
        item["latest_structured_evidence_captured_at"] = latest_evidence_checked
        if not evidence_rows:
            mismatches.append({**item, "mismatch": "generated_reports_missing_structured_evidence"})
        elif len(counted_rows) != item["generated_report_count"]:
            mismatches.append({**item, "mismatch": "generated_report_count_differs_from_structured_evidence"})

        evidence_checked = item.get("evidence_last_checked")
        if not evidence_checked:
            stale_records.append({**item, "stale_reason": "missing_evidence_last_checked"})
        elif is_stale(evidence_checked, now=now, stale_days=stale_days):
            stale_records.append({**item, "stale_reason": "stale_evidence_last_checked"})

    for item in generated_records:
        if is_stale(item.get("update_last_checked"), now=now, stale_days=stale_days):
            stale_records.append({**item, "stale_reason": "stale_or_missing_update_last_checked"})

    evidence_without_matching_record: list[dict[str, Any]] = []
    evidence_count_mismatches: list[dict[str, Any]] = []
    for key, rows in sorted(evidence_by_key.items()):
        counted_rows = [row for row in rows if row.get("counted") is not False]
        generated = generated_by_key.get(key)
        if not generated:
            evidence_without_matching_record.append({
                "product_id": key[0],
                "update_version": key[1],
                "structured_evidence_count": len(counted_rows),
            })
            continue
        if generated["generated_report_count"] != len(counted_rows):
            evidence_count_mismatches.append({
                "path": generated["path"],
                "product_id": key[0],
                "update_version": key[1],
                "generated_report_count": generated["generated_report_count"],
                "structured_evidence_count": len(counted_rows),
            })

    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "mode": "audit_only_no_scraping_no_record_writes",
        "stale_after_days": stale_days,
        "generated_records_scanned": len(generated_records),
        "generated_records_with_reports": records_with_reports,
        "structured_evidence_groups": [
            {
                "product_id": product_id,
                "update_version": version,
                "structured_evidence_count": len([row for row in rows if row.get("counted") is not False]),
                "latest_structured_evidence_captured_at": latest_time([row.get("captured_at") for row in rows]),
            }
            for (product_id, version), rows in sorted(evidence_by_key.items())
        ],
        "mismatches": mismatches,
        "evidence_without_matching_record": evidence_without_matching_record,
        "evidence_count_mismatches": evidence_count_mismatches,
        "stale_records": stale_records,
    }


def print_text(result: dict[str, Any]) -> None:
    print("AUXSAYS consensus evidence audit")
    print(f"Mode: {result['mode']}")
    print(f"Generated records scanned: {result['generated_records_scanned']}")
    print(f"Generated records with reports: {len(result['generated_records_with_reports'])}")
    print(f"Structured evidence groups: {len(result['structured_evidence_groups'])}")
    print(f"Mismatches: {len(result['mismatches'])}")
    print(f"Stale/missing freshness findings: {len(result['stale_records'])}")
    if result["mismatches"]:
        print("\nMismatches:")
        for item in result["mismatches"]:
            print(
                "- {path}: {product_id} {update_version} claims {generated_report_count} reports; "
                "structured evidence count is {structured_evidence_count} ({mismatch}).".format(**item)
            )
    if result["evidence_without_matching_record"]:
        print("\nStructured evidence without matching generated record:")
        for item in result["evidence_without_matching_record"]:
            print(f"- {item['product_id']} {item['update_version']}: {item['structured_evidence_count']} rows")
    if result["stale_records"]:
        print("\nFreshness findings:")
        for item in result["stale_records"]:
            print(f"- {item['path']}: {item['stale_reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit generated report counts against structured consensus evidence.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS, help="Age threshold for stale checked dates.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when mismatches or stale freshness findings exist.")
    args = parser.parse_args()

    result = audit(stale_days=args.stale_days)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result)

    if args.strict and (result["mismatches"] or result["stale_records"] or result["evidence_without_matching_record"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
