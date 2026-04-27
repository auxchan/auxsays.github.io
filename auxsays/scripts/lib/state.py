"""State helpers for idempotent patch ingestion."""
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
