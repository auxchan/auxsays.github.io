from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any


ALGORITHMS = {"DIRECT_IDENTITY_V1", "DIFFERENCE_V1"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as error:
        raise ValueError("calculation input must be a finite decimal") from error


def calculate(algorithm_id: str, inputs: list[dict[str, Any]]) -> str:
    if algorithm_id not in ALGORITHMS:
        raise ValueError("algorithm is not allowlisted")
    if algorithm_id == "DIRECT_IDENTITY_V1":
        if len(inputs) != 1:
            raise ValueError("direct identity requires exactly one input")
        return str(_decimal(inputs[0]["value"]))
    if len(inputs) != 2:
        raise ValueError("difference requires current and baseline inputs")
    return str(_decimal(inputs[0]["value"]) - _decimal(inputs[1]["value"]))


def create_derivation(
    *,
    calculation_id: str,
    calculation_version: str,
    algorithm_id: str,
    configuration_version: str,
    source_snapshot_id: str,
    replay_mode: str,
    knowledge_cutoff: str,
    inputs: list[dict[str, Any]],
    output: dict[str, Any],
    baseline: dict[str, Any] | None,
    relationship_refs: list[str],
    propagation_profile: str | None = None,
    intermediate_contributions: list[dict[str, Any]] | None = None,
    stop_reasons: list[str] | None = None,
) -> dict[str, Any]:
    if not inputs or not all(row.get("stateId") and "value" in row for row in inputs):
        raise ValueError("complete input IDs and values are required")
    expected = calculate(algorithm_id, inputs)
    if str(output.get("value")) != expected:
        raise ValueError("derivation output does not reproduce")
    if not output.get("stateId") or not output.get("unit"):
        raise ValueError("derivation output identity and unit are required")
    if algorithm_id == "DIFFERENCE_V1" and not baseline:
        raise ValueError("difference calculation requires an explicit baseline")
    record: dict[str, Any] = {
        "schemaVersion": "phase4a-derivation-1.0.0",
        "calculationId": calculation_id,
        "calculationVersion": calculation_version,
        "algorithmId": algorithm_id,
        "configurationVersion": configuration_version,
        "sourceSnapshotId": source_snapshot_id,
        "replayMode": replay_mode,
        "knowledgeCutoff": knowledge_cutoff,
        "inputRecordIds": [row["stateId"] for row in inputs],
        "inputs": [{"stateId": row["stateId"], "value": str(row["value"]), "unit": row["unit"]} for row in inputs],
        "baseline": baseline or {"status": "NOT_APPLICABLE_DIRECT_STATE_MAPPING"},
        "transformations": [algorithm_id],
        "relationshipRefs": sorted(relationship_refs),
        "propagationProfile": propagation_profile,
        "intermediateContributions": intermediate_contributions or [],
        "stopReasons": sorted(stop_reasons or []),
        "evidenceClassification": "CALC_FROM_DIRECT_OFFICIAL_OBSERVATION",
        "output": {"stateId": output["stateId"], "value": expected, "unit": output["unit"]},
    }
    record["derivationId"] = stable_id("derivation", record)
    return record


def reproduce(record: dict[str, Any]) -> str:
    required = {
        "derivationId", "calculationId", "calculationVersion", "algorithmId",
        "configurationVersion", "sourceSnapshotId", "replayMode",
        "knowledgeCutoff", "inputs", "baseline", "output",
    }
    if not required.issubset(record):
        raise ValueError("incomplete derivation")
    copy = dict(record)
    identifier = copy.pop("derivationId")
    if identifier != stable_id("derivation", copy):
        raise ValueError("derivation identity mismatch")
    result = calculate(record["algorithmId"], record["inputs"])
    if result != str(record["output"]["value"]):
        raise ValueError("derivation result mismatch")
    return result
