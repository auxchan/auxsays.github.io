from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import parse_utc

HEALTH_STATES = {"current", "delayed", "stale", "unavailable", "schema_format_changed", "validation_failed", "rights_blocked"}


def evaluate_health(policy: dict, *, now: str, last_retrieval: str | None, last_validation: str | None, failure: str | None = None, rights_allowed: bool = True) -> str:
    if not rights_allowed:
        return "rights_blocked"
    if failure in {"schema_format_changed", "validation_failed", "unavailable"}:
        return failure
    if not last_retrieval or not last_validation:
        return "unavailable"
    instant = parse_utc(now)
    validated = parse_utc(last_validation)
    age = instant - validated
    if age <= timedelta(hours=policy["expected_interval_hours"] + policy["delay_grace_hours"]):
        return "current"
    if age <= timedelta(hours=policy["stale_after_hours"]):
        return "delayed"
    return "stale"


def heartbeat_due(last_evaluation: str | None, now: str, window_hours: int = 4) -> bool:
    if last_evaluation is None:
        return True
    return parse_utc(now) - parse_utc(last_evaluation) >= timedelta(hours=window_hours)


def source_work_due(policy: dict, *, last_success: str | None, now: str) -> bool:
    if last_success is None:
        return True
    return parse_utc(now) - parse_utc(last_success) >= timedelta(hours=policy["expected_interval_hours"])

