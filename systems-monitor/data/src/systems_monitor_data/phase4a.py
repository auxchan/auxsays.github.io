from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from .derivation import create_derivation, stable_id
from .propagation import PropagationEngine
from .read_model import build_master_read_model
from .relationships import promote_relationships
from .state_engine import StateEngine


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_phase4a_candidate(
    *,
    review_model_path: Path,
    config_root: Path,
    replay_mode: str = "OPERATIONALLY_KNOWN_AS_OF",
    knowledge_cutoff: str = "2026-08-19T00:00:00Z",
    evaluated_at: str = "2026-08-19T00:00:00Z",
) -> dict[str, Any]:
    source_bytes = review_model_path.read_bytes()
    source_snapshot_id = f"sha256:{hashlib.sha256(source_bytes).hexdigest()}"
    review_model = json.loads(source_bytes)
    profile = load_json(config_root / "phase4a" / "profile.json")
    definitions = load_json(config_root / "phase4a" / "relationships.json")
    rules = load_json(config_root / "phase4a" / "acceptance_rules.json")
    accepted, lifecycle_events = promote_relationships(definitions, rules)
    state_run = StateEngine(profile).run(
        review_model["metrics"],
        replay_mode=replay_mode,
        knowledge_cutoff=knowledge_cutoff,
        evaluated_at=evaluated_at,
        source_snapshot_id=source_snapshot_id,
    )
    by_node = {row["nodeId"]: row for row in state_run["states"]}
    calculated_states = []
    derivations = []
    for edge in accepted:
        source = by_node[edge["sourceNode"]]
        state_identity = {"sourceStateId": source["stateId"], "edgeId": edge["edgeId"], "edgeVersion": edge["version"], "configurationVersion": profile["configurationVersion"]}
        result = {
            "stateId": stable_id("calc-state", state_identity),
            "nodeId": edge["targetNode"],
            "stateType": "CALC",
            "auxsaysCalculation": "DIRECT_IDENTITY_V1",
            "label": edge["targetNode"].split(":", 1)[1].replace("-", " ").title(),
            "value": source["value"],
            "unit": edge["targetUnit"],
            "stateFamily": edge["stateFamily"],
            "observationPeriod": source["observationPeriod"],
            "freshness": source["freshness"],
            "evidenceClassification": "DIRECT_SEMANTIC_MAPPING_NOT_CAUSAL",
        }
        derivation = create_derivation(
            calculation_id=f"{edge['edgeId']}-DIRECT-STATE",
            calculation_version=profile["derivationVersion"],
            algorithm_id="DIRECT_IDENTITY_V1",
            configuration_version=profile["configurationVersion"],
            source_snapshot_id=source_snapshot_id,
            replay_mode=replay_mode,
            knowledge_cutoff=knowledge_cutoff,
            inputs=[source],
            output=result,
            baseline=None,
            relationship_refs=[f"{edge['edgeId']}@{edge['version']}"],
            propagation_profile=profile["configurationVersion"],
        )
        result["derivationRef"] = derivation["derivationId"]
        calculated_states.append(result)
        derivations.append(derivation)
    propagation = PropagationEngine(profile).run(
        state_run["states"],
        accepted,
        replay_mode=replay_mode,
        knowledge_cutoff=knowledge_cutoff,
        source_snapshot_id=source_snapshot_id,
    )
    read_model = build_master_read_model(
        state_run=state_run,
        calculated_states=calculated_states,
        derivations=derivations,
        accepted_relationships=accepted,
        candidate_count=0,
        propagation_run=propagation,
        profile=profile,
    )
    candidate = {
        "schemaVersion": "phase4a-review-candidate-1.0.0",
        "artifactClass": "phase4a_engine_proof_candidate",
        "activationStatus": "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED",
        "structuralCoverageState": "LIMITED_ENGINE_PROOF",
        "gateBStatus": "OPEN_PHASE4B_REQUIRED",
        "sourceSnapshotId": source_snapshot_id,
        "profile": deepcopy(profile),
        "stateRun": state_run,
        "calculatedStates": calculated_states,
        "derivations": derivations,
        "acceptedRelationships": accepted,
        "relationshipLifecycleEvents": lifecycle_events,
        "propagationRun": propagation,
        "masterReadModel": read_model,
        "forecasts": [],
        "scenarios": [],
    }
    candidate["candidateId"] = stable_id("phase4a-candidate", candidate)
    return candidate
