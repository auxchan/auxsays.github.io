from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping
import uuid

from .bea_crosswalk import inspect_bea_concordance, validate_downstream_484_bridge
from .bea_io import (
    BEA_ATTRIBUTION,
    BeaInputOutputClient,
    BeaParameterValue,
    parse_input_output_data,
    redact_bea_url,
    resolve_table_id,
    resolve_year,
    sanitize_bea_response,
)
from .derivation import canonical_json, stable_id
from .phase4b import (
    BEA_CONCORDANCE_URL,
    build_phase4b_candidate,
    load_json,
    structural_artifact_as_of,
)
from .raw import RawStore
from .retrieval import BoundedRetriever
from .structural import (
    generate_structural_candidates,
    promote_structural_candidates,
    validate_product_roles,
)


LIVE_BLOCKED = "BLOCKED_LIVE_BEA_CREDENTIAL"
RIGHTS_STATE = "ALLOW_WITH_ATTRIBUTION_AND_TERMS_FINGERPRINT"
PARSER_VERSION = "bea-input-output-live-1.0.0"


class LiveBeaBlocked(RuntimeError):
    pass


class BoundedBeaHttpsTransport:
    def __init__(self, retriever: BoundedRetriever | None = None):
        self.retriever = retriever or BoundedRetriever(
            timeout_seconds=30,
            max_bytes=25_000_000,
            max_redirects=2,
            max_attempts=3,
        )

    def __call__(self, url: str) -> bytes:
        try:
            artifact = self.retriever.fetch(
                url,
                expected_types=("application/json", "text/json", "text/plain"),
            )
        except Exception:
            # The underlying URL contains the UserID. Never preserve an exception
            # chain that could echo that URL outside the request boundary.
            raise RuntimeError("bounded BEA HTTPS retrieval failed") from None
        return artifact.body


class RecordingTransport:
    def __init__(self, delegate: Callable[[str], bytes], now: Callable[[], str]):
        self.delegate = delegate
        self.now = now
        self.events: list[dict[str, Any]] = []

    def __call__(self, url: str) -> bytes:
        try:
            body = self.delegate(url)
        except Exception:
            raise RuntimeError("BEA request failed inside the redacted transport boundary") from None
        self.events.append({
            "requestIdentity": redact_bea_url(url),
            "retrievedTime": self.now(),
            "byteLength": len(body),
        })
        return body


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _schema_hash(body: bytes, result_key: str) -> str:
    try:
        rows = json.loads(body)["BEAAPI"]["Results"][result_key]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("BEA retained response schema is invalid") from error
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("BEA retained response rows are invalid")
    schema = sorted({key for row in rows for key in row})
    return "sha256:" + hashlib.sha256(canonical_json(schema).encode("utf-8")).hexdigest()


def _rights_fingerprint(data_root: Path) -> str:
    rights = load_json(data_root / "config" / "rights" / "rights.json")
    matches = [row for row in rights.get("policies", []) if row.get("source_id") == "bea-input-output"]
    if len(matches) != 1:
        raise ValueError("BEA rights policy is absent or ambiguous")
    policy = matches[0]
    decisions = policy.get("decisions", {})
    required = {
        "ingestion": "ALLOW",
        "raw_retention": "ALLOW",
        "transformation": "ALLOW",
        "internal_analytical_use": "ALLOW",
        "public_display": "ALLOW",
        "public_redistribution": "DENY",
    }
    if any(decisions.get(operation) != decision for operation, decision in required.items()):
        raise ValueError("BEA rights policy does not authorize the bounded operation")
    return "sha256:" + hashlib.sha256(canonical_json({"policy": policy, "attribution": BEA_ATTRIBUTION}).encode("utf-8")).hexdigest()


def _matrix_artifact(
    *,
    product: dict[str, Any],
    resolved: BeaParameterValue,
    safe_body: bytes,
    source: dict[str, Any],
    accepted_time: str,
    retrieved_time: str,
    rights_fingerprint: str,
    crosswalk_version: str,
    schema_hash: str,
) -> dict[str, Any]:
    core = {
        "dataset": source["dataset"],
        "tableId": resolved.key,
        "productToken": product["productToken"],
        "year": source["economicYear"],
        "contentHash": "sha256:" + _sha256(safe_body),
    }
    artifact_id = stable_id("bea-source-artifact", core)
    return {
        "sourceArtifactId": artifact_id,
        "authority": source["authority"],
        "dataset": source["dataset"],
        "tableId": resolved.key,
        "productToken": product["productToken"],
        "productTitle": resolved.description,
        "year": source["economicYear"],
        "aggregation": source["aggregation"],
        "redefinitionBasis": source["redefinitionBasis"],
        "priceBasis": source["priceBasis"],
        "unit": source["unit"],
        "metadataStatus": "VERIFIED_LIVE_GET_PARAMETER_VALUES",
        "classificationVersion": "BEA_SUMMARY_71_2017_NAICS",
        "crosswalkVersion": crosswalk_version,
        "publicReleaseTime": retrieved_time,
        "publicReleaseTimeKind": "CONSERVATIVE_RETRIEVAL_BOUND_NOT_OFFICIAL_RELEASE_TIME",
        "retrievedTime": retrieved_time,
        "acceptedTime": accepted_time,
        "sourceReleaseIdentity": stable_id("bea-release", core),
        "schemaHash": schema_hash,
        "contentHash": "sha256:" + _sha256(safe_body),
        "byteLength": len(safe_body),
        "rightsState": RIGHTS_STATE,
        "rightsFingerprint": rights_fingerprint,
        "attribution": BEA_ATTRIBUTION,
    }


def _topology_check(accepted: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = {(row["sourceNode"], row["targetNode"]): row["sourceCellIdentity"] for row in accepted}
    required = [
        ("bea:commodity:211", "bea:industry:324"),
        ("bea:commodity:211", "bea:industry:22"),
        ("bea:commodity:324", "bea:industry:484"),
        ("bea:commodity:22", "bea:industry:484"),
    ]
    direct_cells = [{"sourceNode": source, "targetNode": target, "sourceCellIdentity": pairs.get((source, target))} for source, target in required]
    direct_supported = all(row["sourceCellIdentity"] for row in direct_cells)
    return {
        "proposedDirectCellsSupported": direct_supported,
        "directCells": direct_cells,
        "industryCommodityHandoff": "NOT_ACCEPTED_NO_MAKE_OR_MARKET_SHARE_RULE",
        "pathAExecutable": False,
        "pathBExecutable": False,
        "commonCauseProofStatus": "BLOCKED_HANDOFF_UNPROVEN",
        "explanation": "Commodity and industry namespaces remain distinct; matching numeric codes do not create a traversable handoff.",
    }


def _benchmark_summary(direct_cells: list, total_cells: list, topology_artifact: dict, benchmark_artifact: dict) -> dict[str, Any]:
    direct_pairs = {(row.row_code, row.column_code) for row in direct_cells}
    total_transposed_pairs = {(row.column_code, row.row_code) for row in total_cells}
    return {
        "directProduct": topology_artifact["productToken"],
        "directTableId": topology_artifact["tableId"],
        "totalProduct": benchmark_artifact["productToken"],
        "totalTableId": benchmark_artifact["tableId"],
        "totalRole": "NON_RECURSIVE_BENCHMARK_ONLY",
        "includedInPropagation": False,
        "overlappingBoundedCodePairs": len(direct_pairs & total_transposed_pairs),
        "numericComparison": "NOT_APPLIED_NO_APPROVED_COMPATIBILITY_TOLERANCE",
    }


def _attach_current_observations(observations: list[dict[str, Any]], attachment_config: dict[str, Any], accepted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = {node for edge in accepted for node in (edge["sourceNode"], edge["targetNode"])}
    by_series = {str(row.get("seriesId") or row.get("series_id")): row for row in observations}
    attachments = []
    for rule in attachment_config.get("attachments", []):
        observation = by_series.get(rule["seriesId"])
        if observation is None:
            raise ValueError("approved current-state attachment observation is absent")
        if rule.get("propagationSeed") is not False:
            raise ValueError("current companion OBS cannot become a propagation seed")
        compatible = [node_id for node_id in rule["nodeIds"] if node_id in nodes]
        unavailable = [node_id for node_id in rule["nodeIds"] if node_id not in nodes]
        attachments.append({
            "seriesId": rule["seriesId"],
            "stateId": observation.get("stateId") or observation.get("state_id"),
            "nodeIds": compatible,
            "unavailableNodeIds": unavailable,
            "role": rule["role"],
            "propagationSeed": False,
            "status": "ATTACHED_CONTEXT_ONLY" if compatible else "NOT_ATTACHED_NO_COMPATIBLE_ACCEPTED_NODE",
        })
    return attachments


def _replay_proof(artifacts: list[dict[str, Any]], accepted_time: str) -> dict[str, Any]:
    accepted_at = datetime.fromisoformat(accepted_time.replace("Z", "+00:00"))
    earliest_public = min(datetime.fromisoformat(row["publicReleaseTime"].replace("Z", "+00:00")) for row in artifacts)
    public_before = (earliest_public - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    operational_before = (accepted_at - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    public_at = structural_artifact_as_of(artifacts, accepted_time, "PUBLICLY_AVAILABLE_AS_OF")
    operational_at = structural_artifact_as_of(artifacts, accepted_time, "OPERATIONALLY_KNOWN_AS_OF")
    return {
        "publicBeforeCutoff": public_before,
        "publicBefore": structural_artifact_as_of(artifacts, public_before, "PUBLICLY_AVAILABLE_AS_OF"),
        "operationalBeforeCutoff": operational_before,
        "operationalBefore": structural_artifact_as_of(artifacts, operational_before, "OPERATIONALLY_KNOWN_AS_OF"),
        "acceptedCutoff": accepted_time,
        "publicAtArtifactId": public_at["sourceArtifactId"] if public_at else None,
        "operationalAtArtifactId": operational_at["sourceArtifactId"] if operational_at else None,
        "publicReleaseTimeKind": "CONSERVATIVE_RETRIEVAL_BOUND_NOT_OFFICIAL_RELEASE_TIME",
    }


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    temporary.write_bytes(payload)
    os.replace(temporary, path)


class LiveBeaAcceptanceRunner:
    def __init__(
        self,
        *,
        data_root: Path,
        review_root: Path,
        environment: Mapping[str, str] | None = None,
        transport: Callable[[str], bytes] | None = None,
        now: Callable[[], str] = utc_now,
    ):
        self.data_root = data_root
        self.review_root = review_root
        self.environment = os.environ if environment is None else environment
        self.transport = transport
        self.now = now

    def run(self) -> dict[str, Any]:
        started = time.monotonic()
        source = load_json(self.data_root / "config" / "phase4b" / "source.json")
        credential_name = source["credentialEnvironmentVariable"]
        user_id = self.environment.get(credential_name)
        if not user_id:
            raise LiveBeaBlocked(LIVE_BLOCKED)

        profile = load_json(self.data_root / "config" / "phase4b" / "profile.json")
        rule = load_json(self.data_root / "config" / "phase4b" / "acceptance_rule.json")
        bridge = load_json(self.data_root / "config" / "phase4b" / "naics_bridge_484.json")
        attachments_config = load_json(self.data_root / "config" / "phase4b" / "current_state_attachments.json")
        validate_product_roles({
            "topologyProduct": source["topology"]["productToken"],
            "totalRequirementsProduct": source["benchmark"]["productToken"],
            "totalRequirementsRole": source["benchmark"]["role"],
            "includeTotalInPropagation": False,
        })
        rights_fingerprint = _rights_fingerprint(self.data_root)
        concordance = inspect_bea_concordance(
            self.data_root / "evidence" / "bea" / "BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx",
            source_url=BEA_CONCORDANCE_URL,
            allowed_summary_codes=set(rule["allowedCodes"]),
        )
        bridge_record = validate_downstream_484_bridge(concordance, bridge)

        recording = RecordingTransport(self.transport or BoundedBeaHttpsTransport(), self.now)
        client = BeaInputOutputClient(user_id, recording)
        table_values, table_wire, table_url = client.parameter_values_artifact("TableID")
        year_values, year_wire, year_url = client.parameter_values_artifact("Year")
        table_safe = sanitize_bea_response(table_wire)
        year_safe = sanitize_bea_response(year_wire)
        topology_value = resolve_table_id(table_values, tuple(source["topology"]["requiredTitleTerms"]))
        benchmark_value = resolve_table_id(table_values, tuple(source["benchmark"]["requiredTitleTerms"]))
        resolve_year(year_values, source["economicYear"])

        topology_wire, topology_url = client.data(topology_value.key, source["economicYear"])
        benchmark_wire, benchmark_url = client.data(benchmark_value.key, source["economicYear"])
        topology_safe = sanitize_bea_response(topology_wire)
        benchmark_safe = sanitize_bea_response(benchmark_wire)
        accepted_time = self.now()

        topology_cells = parse_input_output_data(
            topology_safe,
            expected_table_id=topology_value.key,
            expected_year=source["economicYear"],
            expected_unit=source["unit"],
            row_namespace="COMMODITY",
            column_namespace="INDUSTRY",
        )
        benchmark_cells = parse_input_output_data(
            benchmark_safe,
            expected_table_id=benchmark_value.key,
            expected_year=source["economicYear"],
            expected_unit=source["unit"],
            row_namespace="INDUSTRY",
            column_namespace="COMMODITY",
        )
        topology_artifact = _matrix_artifact(
            product=source["topology"], resolved=topology_value,
            safe_body=topology_safe, source=source, accepted_time=accepted_time,
            retrieved_time=recording.events[2]["retrievedTime"],
            rights_fingerprint=rights_fingerprint,
            crosswalk_version=bridge_record["bridgeVersion"],
            schema_hash=_schema_hash(topology_safe, "Data"),
        )
        benchmark_artifact = _matrix_artifact(
            product=source["benchmark"], resolved=benchmark_value,
            safe_body=benchmark_safe, source=source, accepted_time=accepted_time,
            retrieved_time=recording.events[3]["retrievedTime"],
            rights_fingerprint=rights_fingerprint,
            crosswalk_version=bridge_record["bridgeVersion"],
            schema_hash=_schema_hash(benchmark_safe, "Data"),
        )
        candidates, rejected = generate_structural_candidates(
            topology_cells,
            artifact=topology_artifact,
            rule=rule,
            allowed_codes=set(rule["allowedCodes"]),
        )
        accepted, lifecycle_events = promote_structural_candidates(candidates, rule)
        topology_check = _topology_check(accepted)
        benchmark = _benchmark_summary(topology_cells, benchmark_cells, topology_artifact, benchmark_artifact)
        gate_status = (
            "BLOCKED_STRUCTURAL_HANDOFF_UNPROVEN"
            if topology_check["proposedDirectCellsSupported"]
            else "BLOCKED_PROPOSED_DIRECT_TOPOLOGY_UNSUPPORTED"
        )
        base_candidate = build_phase4b_candidate(data_root=self.data_root, evaluated_at=accepted_time)
        current_attachments = _attach_current_observations(base_candidate["currentObservations"], attachments_config, accepted)
        replay = _replay_proof([topology_artifact, benchmark_artifact], accepted_time)
        retained_bytes = sum(len(body) for body in (table_safe, year_safe, topology_safe, benchmark_safe))

        run_core = {
            "schemaVersion": "phase4b-live-bea-run-1.0.0",
            "status": "LIVE_BEA_STRUCTURAL_RELATIONSHIPS_ACCEPTED_GATE_B_REMAINS_BLOCKED",
            "acceptedTime": accepted_time,
            "metadataMethod": "GetParameterValues",
            "economicYear": source["economicYear"],
            "resolvedProducts": [
                {"productToken": source["topology"]["productToken"], "tableId": topology_value.key, "title": topology_value.description},
                {"productToken": source["benchmark"]["productToken"], "tableId": benchmark_value.key, "title": benchmark_value.description},
            ],
            "sourceArtifacts": [topology_artifact, benchmark_artifact],
            "acceptedRelationships": accepted,
            "relationshipLifecycleEvents": lifecycle_events,
            "rejectedRelationships": rejected,
            "nodeCount": len({node for edge in accepted for node in (edge["sourceNode"], edge["targetNode"])}),
            "topologyCheck": topology_check,
            "directTotalBenchmark": benchmark,
            "currentObservations": base_candidate["currentObservations"],
            "currentStateAttachments": current_attachments,
            "behavioralEvidence": base_candidate["behavioralEvidence"],
            "commonCauseResult": {
                "status": topology_check["commonCauseProofStatus"],
                "reconciliation": None,
                "reason": "No accepted industry-to-commodity handoff exists; synthetic reconciliation is not substituted.",
            },
            "structuralEmploymentExposure": {
                "status": "NOT_GENERATED",
                "reason": "No accepted executable path and no approved OBS-to-structural-pressure transformation.",
                "claimClass": "CALC_ABSENT",
            },
            "replay": replay,
            "crosswalk": bridge_record,
            "requestMetrics": {
                "requestCount": len(recording.events),
                "wireBytes": sum(row["byteLength"] for row in recording.events),
                "requests": recording.events,
            },
            "recurringInfrastructureCostUsd": profile["recurringInfrastructureCostUsd"],
            "humanPhase4bQa": "PENDING",
            "gateBStatus": gate_status,
            "phase5Status": "LOCKED",
            "performance": {
                "elapsedMsBeforePersistence": round((time.monotonic() - started) * 1000),
                "retainedEvidenceBytes": retained_bytes,
                "requestCount": len(recording.events),
                "recurringInfrastructureCostUsd": profile["recurringInfrastructureCostUsd"],
            },
        }
        run_id = stable_id("phase4b-live-run", run_core)

        raw_store = RawStore(self.data_root / "evidence" / "bea" / "live" / "raw")
        captures = []
        for label, body, safe_url, retrieved_time in (
            ("tableid-metadata", table_safe, table_url, recording.events[0]["retrievedTime"]),
            ("year-metadata", year_safe, year_url, recording.events[1]["retrievedTime"]),
            (source["topology"]["productToken"], topology_safe, topology_url, recording.events[2]["retrievedTime"]),
            (source["benchmark"]["productToken"], benchmark_safe, benchmark_url, recording.events[3]["retrievedTime"]),
        ):
            captures.append(asdict(raw_store.capture(
                source_id=source["sourceId"],
                run_id=run_id,
                request_identity=safe_url,
                retrieved_time=retrieved_time,
                release_id=f"{label}-{source['economicYear']}",
                content_type="application/json",
                body=body,
                parser_version=PARSER_VERSION,
                rights_result=RIGHTS_STATE,
            )))

        run_record = {**run_core, "runId": run_id, "immutableCaptures": captures}
        run_path = self.review_root / "live-runs" / f"{run_id.split(':', 1)[1]}.json"
        _write_atomic(run_path, (json.dumps(run_record, indent=2, sort_keys=True) + "\n").encode("utf-8"))

        candidate = base_candidate
        candidate.pop("candidateId", None)
        candidate.update({
            "structuralCoverageState": "BOUNDED_STRUCTURAL_PROOF",
            "sourceHealth": {**candidate["sourceHealth"], "beaInputOutput": "VERIFIED_LIVE_ACCEPTED_RELATIONSHIPS"},
            "acceptedRelationships": accepted,
            "rejectedRelationshipCount": len(rejected),
            "structuralCalculations": [],
            "derivations": [],
            "claimClassesPresent": ["OBS"],
            "claimClassesAbsent": ["FCST", "SCEN"],
            "liveBeaRunRef": run_id,
            "sourceArtifacts": [topology_artifact, benchmark_artifact],
            "topologyCheck": topology_check,
            "directTotalBenchmark": benchmark,
            "currentStateAttachments": current_attachments,
            "behavioralEvidence": base_candidate["behavioralEvidence"],
            "commonCauseResult": run_core["commonCauseResult"],
            "structuralEmploymentExposure": run_core["structuralEmploymentExposure"],
            "replay": replay,
            "gateBStatus": gate_status,
            "humanPhase4bQa": "PENDING",
            "phase5Status": "LOCKED",
        })
        candidate["candidateId"] = stable_id("phase4b-candidate", candidate)
        candidate_path = self.review_root / "phase4b-read-model-candidate.json"
        _write_atomic(candidate_path, (json.dumps(candidate, indent=2, sort_keys=True) + "\n").encode("utf-8"))

        return {
            "status": run_record["status"],
            "runId": run_id,
            "runRecordPath": str(run_path),
            "candidatePath": str(candidate_path),
            "resolvedProducts": run_record["resolvedProducts"],
            "sourceArtifacts": [
                {key: row[key] for key in ("sourceArtifactId", "tableId", "productToken", "productTitle", "year", "contentHash", "byteLength", "schemaHash")}
                for row in run_record["sourceArtifacts"]
            ],
            "acceptedRelationshipCount": len(accepted),
            "rejectedRelationshipCount": len(rejected),
            "nodeCount": run_record["nodeCount"],
            "topologyCheck": topology_check,
            "directTotalBenchmark": benchmark,
            "currentStateAttachments": current_attachments,
            "behavioralEvidence": run_core["behavioralEvidence"],
            "commonCauseResult": run_core["commonCauseResult"],
            "structuralEmploymentExposure": run_core["structuralEmploymentExposure"],
            "replay": replay,
            "requestMetrics": run_record["requestMetrics"],
            "structuralCalculationCount": 0,
            "humanPhase4bQa": "PENDING",
            "gateBStatus": gate_status,
            "phase5Status": "LOCKED",
            "recurringInfrastructureCostUsd": profile["recurringInfrastructureCostUsd"],
            "performance": run_core["performance"],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AUXSAYS bounded Phase-4B live BEA acceptance runner")
    parser.add_argument("--data-root", type=Path, default=Path("systems-monitor/data"))
    parser.add_argument("--review-root", type=Path, default=Path("systems-monitor/state/review"))
    args = parser.parse_args(argv)
    started = time.monotonic()
    try:
        result = LiveBeaAcceptanceRunner(data_root=args.data_root, review_root=args.review_root).run()
    except LiveBeaBlocked:
        print(json.dumps({"status": LIVE_BLOCKED}, sort_keys=True))
        return 2
    except Exception as error:
        print(json.dumps({"status": "FAILED_CLOSED", "errorType": type(error).__name__}, sort_keys=True))
        return 1
    result["elapsedMs"] = round((time.monotonic() - started) * 1000)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
