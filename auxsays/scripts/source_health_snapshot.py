#!/usr/bin/env python3
"""Generate a static source-health snapshot for AUXSAYS.

This script is intentionally static-site compatible. It does not require a
backend, database, or long-running service. It combines:

- patch_ingestion_sources.yml: what AUXSAYS intends to track
- patch_ingest_state.json: what happened during the latest official ingestion

The output is render-ready Jekyll data for methodology/source audit pages.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "_data" / "patch_ingestion_sources.yml"
STATE_PATH = ROOT / "_data" / "patch_ingest_state.json"
OUTPUT_PATH = ROOT / "_data" / "source_health.yml"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else []


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def friendly_error(error: str) -> str:
    text = (error or "").strip()
    lower = text.lower()
    if not text:
        return "None"
    if "timed out" in lower or "timeout" in lower:
        return "Timeout during last check"
    if "403" in lower or "forbidden" in lower:
        return "Blocked or forbidden by source"
    if "404" in lower or "not found" in lower:
        return "Source page not found"
    if "parse" in lower or "selector" in lower:
        return "Parser needs review"
    if "ssl" in lower or "certificate" in lower:
        return "TLS/certificate error"
    if len(text) > 110:
        return text[:107].rstrip() + "..."
    return text


def status_for(source: dict[str, Any], source_state: dict[str, Any], last_error: str) -> tuple[str, str]:
    ingestion = source.get("ingestion") or {}
    adapter = ingestion.get("adapter") or ingestion.get("type") or ""
    enabled = bool(source.get("enabled"))
    recommended = str(source.get("recommended_priority") or "").lower()

    if not enabled:
        if adapter == "manual_watch" or "manual" in recommended:
            return "Manual watch", "Manual watch active"
        if "staged" in recommended or "build later" in recommended or "p2" in recommended or "p3" in recommended:
            return "Staged", "Staged"
        return "Disabled", "Disabled"

    explicit = str(source_state.get("status") or "").lower()
    failures = int(source_state.get("consecutive_failures") or 0)
    fetched = int(source_state.get("last_records_fetched") or 0)

    if last_error or failures:
        # If an enabled source has never successfully completed, treat the
        # operational signal as failing immediately. A first-time timeout is
        # not merely degraded because there is no known-good baseline yet.
        if not source_state.get("last_success_at") or failures >= 2 or explicit == "failing":
            return "Failing", "Failing"
        return "Degraded", "Degraded"

    checked = bool(source_state.get("last_checked_at"))
    written = int(source_state.get("last_records_written") or 0)

    if checked and fetched == 0 and written == 0:
        # A successful run with no extracted/written records is not a degraded
        # source. It means the source was reachable but no eligible new update
        # record was found during that run.
        return "Idle healthy", "No new records"

    if explicit == "degraded":
        return "Degraded", "Degraded"
    if source_state.get("last_success_at"):
        return "Healthy", "Healthy"
    return "Enabled", "Pending first check"


def capability_summary(extractable: dict[str, Any]) -> dict[str, Any]:
    def yes(key: str) -> bool:
        return bool(extractable.get(key))

    return {
        "release_notes": yes("release_note_body") or yes("title") or yes("archived_release_history"),
        "version": yes("version"),
        "release_date": yes("release_date"),
        "download_url": yes("download_url"),
        "file_size": yes("file_size"),
        "checksum": yes("checksum"),
        "known_issues": yes("known_issues"),
        "release_assets": yes("platform_specific_installers"),
    }


def main() -> int:
    sources = load_yaml(CONFIG_PATH)
    state = load_json(STATE_PATH)
    state_sources = state.get("sources") or {}

    error_map: dict[str, str] = {}
    for item in state.get("last_errors") or []:
        product_id = item.get("product_id")
        if product_id:
            error_map[product_id] = item.get("error") or ""

    rows: list[dict[str, Any]] = []
    for source in sources:
        ingestion = source.get("ingestion") or {}
        product_id = source.get("product_id") or source.get("source_id") or source.get("software")
        source_state = state_sources.get(product_id, {}) if isinstance(state_sources, dict) else {}
        enabled = bool(source.get("enabled"))
        # Disabled/staged sources should not keep showing stale errors from an
        # older enabled test run. Their current operational state is staged,
        # not actively failing.
        last_error = (error_map.get(product_id) or source_state.get("last_error") or "") if enabled else ""
        status, status_detail = status_for(source, source_state, last_error)
        extractable = ingestion.get("extractable_fields") or {}
        capabilities = capability_summary(extractable)
        health_note = source.get("source_health_note") or source_state.get("last_health_note") or ""
        if not enabled and status == "Staged" and not health_note:
            health_note = "Source configured but intentionally staged until adapter reliability is proven."

        rows.append({
            "source_id": product_id,
            "company_id": source.get("company_id"),
            "product_id": product_id,
            "company": source.get("company"),
            "software": source.get("software"),
            "public_category": source.get("public_category"),
            "adapter_type": ingestion.get("adapter") or ingestion.get("type"),
            "enabled": bool(source.get("enabled")),
            "status": status,
            "status_detail": status_detail,
            "polling_frequency": ingestion.get("polling_frequency") or source.get("polling_frequency") or "",
            "last_success": source_state.get("last_success_at") or source_state.get("last_success") or "",
            "last_error": last_error,
            "last_error_display": friendly_error(last_error),
            "last_error_type": source_state.get("last_error_type") or "",
            "consecutive_failures": int(source_state.get("consecutive_failures") or (1 if last_error else 0)),
            "last_checked": source_state.get("last_checked_at") or source_state.get("last_checked") or state.get("last_run_finished_at") or "",
            "last_records_fetched": int(source_state.get("last_records_fetched") or 0),
            "last_records_written": int(source_state.get("last_records_written") or 0),
            "last_records_skipped": int(source_state.get("last_records_skipped") or 0),
            "last_run_duration_ms": int(source_state.get("last_run_duration_ms") or 0),
            "last_health_note": health_note,
            "capabilities": capabilities,
            "raw_extractable_fields": extractable,
        })

    # Status order first, then alpha. Healthy/degraded enabled sources should be easy to audit.
    status_order = {"Failing": 0, "Degraded": 1, "Enabled": 2, "Healthy": 3, "Idle healthy": 4, "Staged": 5, "Manual watch": 6, "Disabled": 7}
    rows.sort(key=lambda row: (status_order.get(row.get("status"), 9), (row.get("company") or "").lower(), (row.get("software") or "").lower()))
    OUTPUT_PATH.write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8")
    print(f"Wrote {len(rows)} source-health rows to {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
