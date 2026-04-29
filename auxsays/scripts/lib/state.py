"""State helpers for idempotent patch ingestion and source health.

The ingestion state is the operational ledger for AUXSAYS official-source
fetching. It should answer two separate questions:

1. Have we already written this specific patch record?
2. Is this source currently healthy, degraded, failing, disabled, or staged?
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def source_state(state: dict[str, Any], product_id: str) -> dict[str, Any]:
    sources = state.setdefault("sources", {})
    return sources.setdefault(product_id, {"seen": []})


def mark_seen(state: dict[str, Any], product_id: str, record_id: str) -> None:
    bucket = source_state(state, product_id)
    seen = bucket.setdefault("seen", [])
    if record_id not in seen:
        seen.insert(0, record_id)
        del seen[100:]


def is_seen(state: dict[str, Any], product_id: str, record_id: str) -> bool:
    return record_id in source_state(state, product_id).get("seen", [])


def classify_success(fetched: int, written: int, skipped: int) -> str:
    """Classify a successful adapter run without pretending every success is equal."""
    if fetched > 0:
        return "healthy"
    # A successful fetch with zero extracted records is not a transport failure,
    # but it may indicate either no new records or a parser/source mismatch.
    return "degraded"


def update_source_success(
    state: dict[str, Any],
    product_id: str,
    *,
    checked_at: str,
    duration_ms: int,
    adapter: str,
    fetched: int,
    written: int,
    skipped: int,
) -> None:
    bucket = source_state(state, product_id)
    previous_failures = int(bucket.get("consecutive_failures") or 0)
    status = classify_success(fetched, written, skipped)
    bucket.update({
        "status": status,
        "last_checked_at": checked_at,
        "last_success_at": checked_at,
        "last_error_at": "",
        "last_error": "",
        "last_error_type": "",
        "consecutive_failures": 0,
        "previous_consecutive_failures": previous_failures,
        "last_adapter": adapter,
        "last_records_fetched": int(fetched),
        "last_records_written": int(written),
        "last_records_skipped": int(skipped),
        "last_run_duration_ms": int(duration_ms),
    })
    if fetched == 0:
        bucket["last_health_note"] = "Fetch succeeded, but no records were extracted. This can mean no new updates or that the parser needs review."
    else:
        bucket["last_health_note"] = "Fetch succeeded."


def update_source_error(
    state: dict[str, Any],
    product_id: str,
    *,
    checked_at: str,
    duration_ms: int,
    adapter: str,
    error: str,
) -> None:
    bucket = source_state(state, product_id)
    failures = int(bucket.get("consecutive_failures") or 0) + 1
    bucket.update({
        "status": "failing" if failures >= 2 else "degraded",
        "last_checked_at": checked_at,
        "last_error_at": checked_at,
        "last_error": error,
        "last_error_type": classify_error(error),
        "consecutive_failures": failures,
        "last_adapter": adapter,
        "last_records_fetched": 0,
        "last_records_written": 0,
        "last_records_skipped": 0,
        "last_run_duration_ms": int(duration_ms),
        "last_health_note": "Fetch failed. Review source availability, adapter timeout, or parser behavior.",
    })


def classify_error(error: str) -> str:
    text = (error or "").lower()
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "403" in text or "forbidden" in text:
        return "blocked"
    if "404" in text or "not found" in text:
        return "not_found"
    if "ssl" in text or "certificate" in text:
        return "tls_error"
    if "parse" in text or "selector" in text:
        return "parser_error"
    if "connection" in text or "network" in text:
        return "network_error"
    return "error"
