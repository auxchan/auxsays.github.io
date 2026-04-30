#!/usr/bin/env python3
"""Build a dry-run consensus status file from manually curated evidence.

This does not scrape communities and does not modify generated update records.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
OUT_PATH = ROOT / "_data" / "consensus_status.json"
VALID_SENTIMENTS = {"positive", "moderate", "negative"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def load_evidence() -> list[dict[str, Any]]:
    if not EVIDENCE_PATH.exists():
        return []
    payload = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        evidence = payload.get("evidence") or []
        return [item for item in evidence if isinstance(item, dict)]
    return []


def is_patch_specific(item: dict[str, Any]) -> bool:
    if item.get("patch_version_matched") is True:
        return True
    version = str(item.get("update_version") or "").strip().lower()
    text = " ".join([
        str(item.get("parent_title") or ""),
        str(item.get("report_title") or ""),
        str(item.get("report_text_excerpt") or ""),
    ]).lower()
    return bool(version and version in text)


def consensus_label(counts: Counter[str]) -> str:
    total = sum(counts.values())
    if total <= 0:
        return "Insufficient data"
    negative_ratio = counts["negative"] / total
    positive_ratio = counts["positive"] / total
    if negative_ratio >= 0.55:
        return "Negative"
    if positive_ratio >= 0.55 and counts["negative"] == 0:
        return "Positive"
    return "Moderate"


def confidence(total: int) -> str:
    if total >= 25:
        return "Medium"
    if total >= 8:
        return "Low-Medium"
    if total > 0:
        return "Low"
    return "Insufficient"


def main() -> int:
    evidence = load_evidence()
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    excluded: list[dict[str, Any]] = []

    for item in evidence:
        product_id = str(item.get("product_id") or "").strip()
        version = str(item.get("update_version") or "").strip()
        sentiment = str(item.get("sentiment") or "").strip().lower()
        severity = str(item.get("severity") or "").strip().lower()
        if not product_id or not version:
            item["exclusion_reason"] = item.get("exclusion_reason") or "missing_product_or_version"
            excluded.append(item)
            continue
        if sentiment not in VALID_SENTIMENTS:
            item["exclusion_reason"] = item.get("exclusion_reason") or "invalid_sentiment"
            excluded.append(item)
            continue
        if severity and severity not in VALID_SEVERITIES:
            item["exclusion_reason"] = item.get("exclusion_reason") or "invalid_severity"
            excluded.append(item)
            continue
        if item.get("counted") is False or not is_patch_specific(item):
            item["exclusion_reason"] = item.get("exclusion_reason") or "not_confirmed_patch_specific"
            excluded.append(item)
            continue
        groups[(product_id, version)].append(item)

    aggregate = []
    for (product_id, version), items in sorted(groups.items()):
        sentiments = Counter(str(item.get("sentiment")).lower() for item in items)
        severities = Counter(str(item.get("severity") or "low").lower() for item in items)
        themes = Counter(str(item.get("issue_theme") or "unspecified") for item in items)
        aggregate.append({
            "product_id": product_id,
            "update_version": version,
            "report_count": len(items),
            "positive_count": sentiments["positive"],
            "moderate_count": sentiments["moderate"],
            "negative_count": sentiments["negative"],
            "issue_themes": dict(themes.most_common()),
            "severity_summary": dict(severities.most_common()),
            "consensus_label": consensus_label(sentiments),
            "confidence": confidence(len(items)),
            "evidence_state": "pilot_sample",
        })

    OUT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "dry_run_manual_evidence_only",
        "evidence_items_read": len(evidence),
        "aggregate_count": len(aggregate),
        "excluded_count": len(excluded),
        "aggregates": aggregate,
        "excluded": excluded,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Consensus dry run read {len(evidence)} evidence items; built {len(aggregate)} aggregate rows; excluded {len(excluded)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
