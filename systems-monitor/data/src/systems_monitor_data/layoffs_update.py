from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTIVATION_STATES = {"SOURCE_IDENTIFIED", "SOURCE_ENABLED_PENDING_ACCEPTANCE", "ACCEPTED", "BLOCKED"}
HEALTH_STATES = {"success", "partial", "no_results", "blocked", "stale", "broken", "low_confidence", "disabled", "manual_review_needed"}


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def redact(value: str, secret_values: list[str]) -> str:
    result = value
    for secret in secret_values:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


def source_due(source: dict[str, Any], now: str, last_attempt_at: str | None) -> bool:
    if not last_attempt_at:
        return True
    elapsed = (parse_utc(now) - parse_utc(last_attempt_at)).total_seconds() / 3600
    return elapsed >= float(source["minimumIntervalHours"])


def credential_state(source: dict[str, Any], environment: dict[str, str] | None = None) -> dict[str, str] | None:
    name = source.get("credentialEnv")
    if not name:
        return None
    values = environment if environment is not None else os.environ
    if values.get(name):
        return None
    return {"activationState": "BLOCKED", "health": "blocked", "reasonCode": f"MISSING_{name}"}


def content_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def atomic_activate(candidate: dict[str, Any], active_path: Path) -> dict[str, Any]:
    validate_snapshot(candidate)
    existing = json.loads(active_path.read_text(encoding="utf-8")) if active_path.exists() else None
    if existing and existing.get("payloadSha256") == candidate.get("payloadSha256"):
        return {"changed": False, "snapshotId": existing["snapshotId"], "reason": "CONTENT_UNCHANGED"}
    active_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = active_path.with_suffix(active_path.suffix + ".tmp")
    temporary.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(active_path)
    return {"changed": True, "snapshotId": candidate["snapshotId"], "reason": "ACTIVATED_ATOMICALLY"}


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    required = {"schemaVersion", "snapshotId", "publicationClass", "activationStatus", "generatedAt", "payloadSha256", "factors", "relationships", "sourceHealth"}
    if not required.issubset(snapshot):
        raise ValueError("layoffs snapshot is incomplete")
    if snapshot["publicationClass"] != "fixture" or snapshot["activationStatus"] != "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED":
        raise ValueError("layoffs review snapshot crossed its publication boundary")
    for factor in snapshot["factors"]:
        if factor.get("activationState") not in ACTIVATION_STATES:
            raise ValueError("factor activation state is invalid")
        if factor.get("activationState") != "ACCEPTED" and "displayValue" in factor:
            raise ValueError("unaccepted factor cannot display a value")
        if factor.get("activationState") == "ACCEPTED":
            accepted = {"displayValue", "unit", "period", "publisher", "dataset", "seriesId", "evidenceUrl", "acceptedAt", "snapshotId"}
            if not accepted.issubset(factor):
                raise ValueError("accepted factor lacks publication evidence")
            if factor["snapshotId"] != snapshot["snapshotId"]:
                raise ValueError("mixed snapshot identity")
    for state in snapshot["sourceHealth"].values():
        if state.get("health") not in HEALTH_STATES:
            raise ValueError("source health state is invalid")


def build_review_snapshot(*, taxonomy: dict[str, Any], source_states: list[dict[str, Any]], relationships: list[dict[str, Any]], generated_at: str, source_health: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    canonical: dict[str, dict[str, Any]] = {}
    placements: list[dict[str, Any]] = []
    for group in taxonomy["groups"]:
        canonical.setdefault(group["canonicalFactorId"], {"canonicalFactorId": group["canonicalFactorId"], "label": group["label"], "activationState": "SOURCE_IDENTIFIED"})
        for placement in group["placements"]:
            canonical.setdefault(placement["canonicalFactorId"], {"canonicalFactorId": placement["canonicalFactorId"], "label": placement["label"], "activationState": "SOURCE_IDENTIFIED"})
            placements.append({"placementId": placement["placementId"], "canonicalFactorId": placement["canonicalFactorId"], "parentPlacementId": group["placementId"], "order": placement["order"]})
    source_by_factor = {row["canonicalFactorId"]: row for row in source_states}
    for factor_id, source in source_by_factor.items():
        if factor_id in canonical:
            canonical[factor_id] = {**canonical[factor_id], **source}
    health = source_health or {row["sourceId"]: {"health": row["health"], "activationState": row["activationState"], "reasonCode": row.get("reasonCode")} for row in source_states}
    payload = {"factors": sorted(canonical.values(), key=lambda row: row["canonicalFactorId"]), "placements": placements, "relationships": relationships, "sourceHealth": health, "acceptedObservationRefs": ["US_LABOR_INITIAL_UI_CLAIMS"]}
    digest = content_hash(payload)
    snapshot_id = f"layoffs-review-{digest[:16].lower()}"
    for factor in payload["factors"]:
        if factor.get("activationState") == "ACCEPTED":
            factor["snapshotId"] = snapshot_id
    snapshot = {
        "schemaVersion": "layoffs-live-branch-review-1.0.0",
        "snapshotId": snapshot_id,
        "publicationClass": "fixture",
        "activationStatus": "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED",
        "generatedAt": generated_at,
        "payloadSha256": content_hash(payload),
        "factors": payload["factors"],
        "placements": payload["placements"],
        "relationships": payload["relationships"],
        "sourceHealth": payload["sourceHealth"],
        "acceptedObservationRefs": payload["acceptedObservationRefs"],
        "coverage": {"level2": 10, "level3Placements": 100, "canonicalFactors": len(canonical), "acceptedFactorCount": sum(row.get("activationState") == "ACCEPTED" for row in canonical.values())},
    }
    validate_snapshot(snapshot)
    return snapshot
