from __future__ import annotations

import json
from typing import Any


UNSUPPORTED_DOMAINS = [
    "industry-structure", "occupation-demand", "production", "prices",
    "housing", "trade", "energy", "health", "education", "state-local",
]


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value).replace("\x00", "").replace("\r", " ").replace("\n", " ")
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    return text[:limit]


def build_master_read_model(
    *,
    state_run: dict[str, Any],
    calculated_states: list[dict[str, Any]],
    derivations: list[dict[str, Any]],
    accepted_relationships: list[dict[str, Any]],
    candidate_count: int,
    propagation_run: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    components = []
    for state in [*state_run["states"], *calculated_states]:
        components.append({
            "stateId": state["stateId"],
            "nodeId": state["nodeId"],
            "stateType": state["stateType"],
            "label": _safe_text(state["label"]),
            "value": state["value"],
            "unit": state["unit"],
            "observationPeriod": state.get("observationPeriod"),
            "freshness": state.get("freshness"),
            "auxsaysCalculation": state.get("auxsaysCalculation"),
            "derivationRef": state.get("derivationRef"),
        })
    relationship_summaries = [{
        "edgeId": edge["edgeId"],
        "version": edge["version"],
        "sourceNode": edge["sourceNode"],
        "targetNode": edge["targetNode"],
        "relationshipType": edge["relationshipType"],
        "evidenceClass": edge["evidenceClass"],
        "lifecycle": edge["lifecycle"],
    } for edge in accepted_relationships]
    model = {
        "schemaVersion": "phase4a-master-read-model-1.0.0",
        "artifactClass": "phase4a_master_read_model_candidate",
        "activationStatus": "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED",
        "domainId": "US_LABOR_ENGINE_PROOF",
        "stateRunId": state_run["stateRunId"],
        "evaluatedAt": state_run["evaluatedAt"],
        "knowledgeCutoff": state_run["knowledgeCutoff"],
        "replayMode": state_run["replayMode"],
        "structuralCoverageState": "LIMITED_ENGINE_PROOF",
        "coverageWarning": "This does not model the full economy and is not Gate-B evidence.",
        "supportedDomain": "six-indicator national labor engine proof only",
        "unsupportedDomains": UNSUPPORTED_DOMAINS,
        "stateComponents": components,
        "relationshipSummaries": relationship_summaries,
        "derivationRefs": sorted(row["derivationId"] for row in derivations),
        "sourceFreshness": [{"stateId": row["stateId"], "freshness": row["freshness"], "retrievalPathHealth": row["retrievalPathHealth"]} for row in state_run["states"]],
        "acceptedRelationshipCount": len(accepted_relationships),
        "candidateRelationshipCount": candidate_count,
        "evidenceMix": {"DIRECT": len(accepted_relationships), "AUTHORITATIVE_STRUCTURAL": 0, "TEST_FIXTURE": 0},
        "degradedState": "DEGRADED_SOURCE_PATH" if any(row["retrievalPathHealth"] == "stale" for row in state_run["states"]) else "NONE",
        "propagationSummary": {"runId": propagation_run["propagationRunId"], "traversalCount": propagation_run["traversalCount"], "stopReasons": propagation_run["stopReasons"]},
        "claimClassesPresent": ["OBS", "CALC"],
        "claimClassesAbsent": ["FCST", "SCEN"],
        "recurringInfrastructureCostUsd": profile["recurringInfrastructureCostUsd"],
    }
    serialized = json.dumps(model, sort_keys=True).lower()
    if any(secret in serialized for secret in ("api_key", "authorization", "password", "localpath", "sqlite")):
        raise ValueError("read model contains secret or storage-shaped content")
    if model["structuralCoverageState"] != "LIMITED_ENGINE_PROOF" or "FCST" not in model["claimClassesAbsent"]:
        raise ValueError("Phase-4A coverage or claim boundary is invalid")
    return model
