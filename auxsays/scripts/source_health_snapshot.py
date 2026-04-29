#!/usr/bin/env python3
"""Generate a lightweight static source-health snapshot for AUXSAYS.

This is not a backend monitor. It combines the current ingestion config with the
last local state file so Jekyll can render a transparent source-health table.
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
        last_error = error_map.get(product_id) or source_state.get("last_error") or ""
        rows.append({
            "source_id": product_id,
            "company_id": source.get("company_id"),
            "product_id": product_id,
            "company": source.get("company"),
            "software": source.get("software"),
            "adapter_type": ingestion.get("adapter") or ingestion.get("type"),
            "enabled": bool(source.get("enabled")),
            "last_success": source_state.get("last_success") or source_state.get("last_success_at") or "",
            "last_error": last_error,
            "consecutive_failures": source_state.get("consecutive_failures") or (1 if last_error else 0),
            "last_checked": source_state.get("last_checked") or state.get("last_run_finished_at") or "",
        })

    rows.sort(key=lambda row: ((row.get("company") or "").lower(), (row.get("software") or "").lower()))
    OUTPUT_PATH.write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    print(f"Wrote {len(rows)} source-health rows to {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
