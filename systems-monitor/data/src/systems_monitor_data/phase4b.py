from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .bea_crosswalk import inspect_bea_concordance, validate_downstream_484_bridge
from .derivation import stable_id
from .eia_wpsr import parse_commercial_crude_stocks, parse_refinery_utilization
from .models import parse_utc
from .normalize import normalize_bls


BEA_CONCORDANCE_URL = "https://www.bea.gov/sites/default/files/2023-10/BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx"
BLS_484_EVIDENCE_URL = "https://data.bls.gov/timeseries/CES4348400001"
BLS_484_METHOD_URL = "https://www.bls.gov/ces/"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bls_484(payload: bytes, *, retrieved_time: str) -> dict[str, Any]:
    digest = hashlib.sha256(payload).hexdigest()
    observation = normalize_bls(
        payload,
        [{
            "indicator_id": "employment-truck-transportation",
            "source_id": "bls-ces",
            "source_series_id": "CES4348400001",
            "unit": "thousands",
        }],
        release_id="bls-ces-2026-08",
        artifact_sha256=digest,
        retrieved_time=retrieved_time,
        accepted_time=retrieved_time,
        provenance_url="https://api.bls.gov/publicAPI/v2/timeseries/data/",
    ).pop().as_record()
    return {
        "stateId": observation["observation_id"],
        "stateType": "OBS",
        "nodeId": "bls:industry-employment:484",
        "label": "Truck transportation employment",
        "value": observation["value"],
        "unit": observation["unit"],
        "observationPeriod": observation["valid_time"],
        "seriesId": observation["source_series_id"],
        "seasonalAdjustment": "seasonally_adjusted",
        "naicsCode": "484",
        "naicsVintage": "2022_NAICS",
        "acquisitionProvenanceUrl": observation["provenance_url"],
        "evidenceUrl": BLS_484_EVIDENCE_URL,
        "methodologyUrl": BLS_484_METHOD_URL,
        "artifactSha256": digest,
        "publicationClass": "PRELIMINARY",
    }


def structural_artifact_as_of(artifacts: list[dict[str, Any]], cutoff: str, replay_mode: str) -> dict[str, Any] | None:
    cutoff_time = parse_utc(cutoff)
    if replay_mode not in {"PUBLICLY_AVAILABLE_AS_OF", "OPERATIONALLY_KNOWN_AS_OF"}:
        raise ValueError("unsupported structural replay mode")
    field = "publicReleaseTime" if replay_mode == "PUBLICLY_AVAILABLE_AS_OF" else "acceptedTime"
    eligible = [row for row in artifacts if parse_utc(row[field]) <= cutoff_time]
    if replay_mode == "OPERATIONALLY_KNOWN_AS_OF":
        eligible = [row for row in eligible if parse_utc(row["retrievedTime"]) <= cutoff_time]
    return sorted(eligible, key=lambda row: (row[field], row.get("sourceArtifactId", "")))[-1] if eligible else None


def create_structural_derivation(
    *,
    output: dict[str, Any],
    source_artifact: dict[str, Any],
    relationships: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    propagation: dict[str, Any],
    behavior: dict[str, Any],
    replay_mode: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    if output.get("stateType") != "CALC" or output.get("claim") not in {"CURRENT_EXPOSURE_ORDINAL", "AS_OF_EXPOSURE_ORDINAL"}:
        raise ValueError("structural derivation output must be a current/as-of ordinal CALC")
    if not relationships or not all(row.get("lifecycle") == "ACCEPTED" for row in relationships):
        raise ValueError("structural derivation requires accepted relationships")
    if not observations or not all(row.get("stateType") == "OBS" for row in observations):
        raise ValueError("structural derivation requires official OBS inputs")
    core = {
        "schemaVersion": "phase4b-structural-derivation-1.0.0",
        "algorithmId": "BOUNDED_STRUCTURAL_EXPOSURE_ORDINAL_V1",
        "sourceArtifactId": source_artifact["sourceArtifactId"],
        "sourceTableId": source_artifact["tableId"],
        "sourceProduct": source_artifact["productToken"],
        "economicYear": source_artifact["year"],
        "sourceRelease": source_artifact["publicReleaseTime"],
        "sourceCellIdentities": sorted(row["sourceCellIdentity"] for row in relationships),
        "relationshipRefs": sorted(f"{row['edgeId']}@{row['version']}" for row in relationships),
        "classificationVersion": source_artifact["classificationVersion"],
        "crosswalkVersion": source_artifact["crosswalkVersion"],
        "observationRefs": sorted(row["stateId"] for row in observations),
        "replayMode": replay_mode,
        "knowledgeCutoff": knowledge_cutoff,
        "propagationRunId": propagation["propagationRunId"],
        "propagationVersion": propagation["algorithmVersion"],
        "intermediateContributions": propagation["contributions"],
        "commonCauseReconciliation": propagation["reconciliation"],
        "behavior": behavior,
        "output": output,
        "warning": "Ordinal current exposure only; not jobs gained/lost and not a forecast.",
    }
    return {**core, "derivationId": stable_id("phase4b-derivation", core)}


def build_phase4b_candidate(*, data_root: Path, evaluated_at: str = "2026-08-21T17:00:00-07:00") -> dict[str, Any]:
    config_root = data_root / "config" / "phase4b"
    evidence_root = data_root / "evidence"
    source = load_json(config_root / "source.json")
    profile = load_json(config_root / "profile.json")
    bridge = load_json(config_root / "naics_bridge_484.json")

    concordance = inspect_bea_concordance(
        evidence_root / "bea" / "BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx",
        source_url=BEA_CONCORDANCE_URL,
        allowed_summary_codes={"211", "22", "324", "484", "486", "493"},
    )
    bridge_record = validate_downstream_484_bridge(concordance, bridge)
    bls_payload = (evidence_root / "bls" / "CES4348400001-2026-response.json").read_bytes()
    bls_obs = _bls_484(bls_payload, retrieved_time="2026-08-22T04:44:50Z")
    stocks = parse_commercial_crude_stocks(
        (evidence_root / "eia" / "WPSR-table4-2026-08-19.csv").read_bytes(),
        public_time="2026-08-19T14:30:00Z",
        retrieved_time="2026-08-22T04:47:28Z",
    ).as_record()
    capacity = parse_refinery_utilization(
        (evidence_root / "eia" / "WPSR-table2-2026-08-19.csv").read_bytes(),
        public_time="2026-08-19T14:30:00Z",
        retrieved_time="2026-08-22T04:47:28Z",
    ).as_record()
    credential_present = bool(os.environ.get(source["credentialEnvironmentVariable"]))
    gate_status = "BLOCKED_LIVE_BEA_CREDENTIAL" if not credential_present else "BLOCKED_LIVE_BEA_ACCEPTANCE_RUN_REQUIRED"
    model = {
        "schemaVersion": "phase4b-master-read-model-0.1.0",
        "artifactClass": "phase4b_bounded_structural_candidate",
        "activationStatus": "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED",
        "evaluatedAt": evaluated_at,
        "structuralCoverageState": "BOUNDED_STRUCTURAL_PROOF_PENDING_LIVE_ACCEPTANCE",
        "coverageWarning": "Only the approved energy/refining/utilities/transport slice is in scope; this is not a whole-economy model.",
        "coveredCodes": ["211", "22", "324", "484", "486", "493"],
        "downstreamTarget": {"beaSummaryCode": "484", "blsSeriesId": "CES4348400001"},
        "sourceHealth": {
            "beaInputOutput": gate_status,
            "beaConcordance": "VERIFIED_RETAINED_OFFICIAL_WORKBOOK",
            "eiaWpsr": "VERIFIED_RETAINED_OFFICIAL_CSV",
            "blsCes484": "VERIFIED_RETAINED_OFFICIAL_API_RESPONSE",
        },
        "currentObservations": [stocks, capacity, bls_obs],
        "behavioralEvidence": {
            "inventory": stocks["assessment"],
            "capacity": capacity["assessment"],
            "lag": "UNKNOWN_NOT_ZERO_PENDING_ACCEPTED_STRUCTURAL_RUN",
            "substitution": "NO_PROVEN_SUBSTITUTE",
            "numericAttenuation": None,
        },
        "acceptedRelationships": [],
        "rejectedRelationshipCount": 0,
        "structuralCalculations": [],
        "derivations": [],
        "claimClassesPresent": ["OBS"],
        "claimClassesAbsent": ["FCST", "SCEN"],
        "gateBStatus": gate_status,
        "humanPhase4bQa": "PENDING",
        "phase5Status": "LOCKED",
        "crosswalk": bridge_record,
        "recurringInfrastructureCostUsd": profile["recurringInfrastructureCostUsd"],
    }
    serialized = json.dumps(model, sort_keys=True).casefold()
    forbidden = ("api_key", "userid=", "authorization:", "password", "forecast value", "jobs lost", "jobs gained")
    if any(token in serialized for token in forbidden):
        raise ValueError("Phase-4B candidate contains a secret or unsupported claim")
    return {**model, "candidateId": stable_id("phase4b-candidate", model)}
