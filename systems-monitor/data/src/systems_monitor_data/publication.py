from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import uuid

from .models import parse_utc


class CandidateError(ValueError):
    pass


def canonical_bytes(candidate: dict[str, Any]) -> bytes:
    return (json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _iso_time(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise CandidateError(f"{field} must be an ISO timestamp")
    try:
        parse_utc(value)
    except (TypeError, ValueError) as error:
        raise CandidateError(f"{field} must be an ISO timestamp") from error
    return value


def _secret_guard(value: Any) -> None:
    lowered = json.dumps(value, sort_keys=True).lower()
    if any(secret in lowered for secret in ("registrationkey", "api_key", "authorization")):
        raise CandidateError("secret-shaped field in candidate")


def validate_internal_review_model(candidate: dict[str, Any]) -> None:
    if candidate.get("schemaVersion") != "phase3-internal-review-model-1.0.0":
        raise CandidateError("unsupported internal review-model schema")
    if candidate.get("artifactClass") != "internal_factual_review_model":
        raise CandidateError("artifact must be explicitly classified as an internal review model")
    if candidate.get("activationStatus") != "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED":
        raise CandidateError("internal review-model activation boundary is missing")
    _iso_time(candidate.get("generatedAt"), "generatedAt")
    metrics = candidate.get("metrics")
    if not isinstance(metrics, list) or len(metrics) != 6:
        raise CandidateError("internal review model must contain exactly six factual observations")
    if any(metric.get("stateType") != "OBS" for metric in metrics):
        raise CandidateError("non-OBS state found in internal factual review model")
    for metric in metrics:
        required = {"id", "label", "value", "unit", "observationPeriod", "sourceId", "sourceSeriesId", "sourceLabel", "publicTime", "retrievedTime", "acceptedTime", "observationFreshness", "retrievalPathHealth", "provenanceUrl", "artifactSha256", "vintageId", "seasonalAdjustment"}
        if not required.issubset(metric):
            raise CandidateError(f"incomplete factual metric: {metric.get('id')}")
        if metric.get("rightsState") != "ALLOW":
            raise CandidateError("non-allowed rights state")
        if not (parse_utc(metric["publicTime"]) <= parse_utc(metric["retrievedTime"]) <= parse_utc(metric["acceptedTime"])):
            raise CandidateError("impossible candidate temporal ordering")
        if not isinstance(metric.get("sourceSeriesId"), str) or not metric["sourceSeriesId"]:
            raise CandidateError("source series ID is required")
    if candidate.get("forecasts") or candidate.get("scenarios") or candidate.get("rankings") or candidate.get("events"):
        raise CandidateError("internal Phase-3 review model cannot contain later-phase claims")
    if candidate.get("outlook", {}).get("status") != "unavailable_not_yet_supported":
        raise CandidateError("factual Outlook must be unavailable")
    _secret_guard(candidate)


def _validate_public_hierarchy(payload: dict[str, Any]) -> None:
    systems = payload.get("systems")
    extensions = payload.get("extensions")
    if not isinstance(systems, list) or not systems:
        raise CandidateError("public systems are required")
    if not isinstance(extensions, dict):
        raise CandidateError("extensions are required")
    registry = extensions.get("auxsays.phase2.navigationNodes")
    if not isinstance(registry, dict):
        raise CandidateError("public navigation-node registry is required")
    roots: dict[str, dict[str, Any]] = {}
    for node in systems:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise CandidateError("malformed public system node")
        if node["id"] in roots or node["id"] in registry:
            raise CandidateError("duplicate public navigation node ID")
        roots[node["id"]] = node
    for node_id, node in registry.items():
        if not isinstance(node, dict) or node.get("id") != node_id:
            raise CandidateError("malformed public navigation-node registry")
    all_nodes = {**roots, **registry}
    for node in all_nodes.values():
        if "children" in node:
            raise CandidateError("embedded public children are prohibited; use childRefs")
        refs = node.get("childRefs")
        if not isinstance(refs, list):
            raise CandidateError("public navigation node childRefs are required")
        if len(refs) != len(set(refs)):
            raise CandidateError("duplicate public child reference")
        if any(reference not in all_nodes for reference in refs):
            raise CandidateError("missing public child reference")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise CandidateError("cyclic public child reference")
        if node_id in visited:
            return
        visiting.add(node_id)
        for reference in all_nodes[node_id]["childRefs"]:
            visit(reference)
        visiting.remove(node_id)
        visited.add(node_id)

    for root_id in roots:
        visit(root_id)
    if set(registry) - visited:
        raise CandidateError("unreachable public navigation node")


def _validate_factual_payload(payload: dict[str, Any]) -> None:
    for collection in ("systems", "events"):
        if not isinstance(payload.get(collection), list):
            raise CandidateError(f"{collection} must be an array")
    if not isinstance(payload.get("sources"), dict) or not payload["sources"]:
        raise CandidateError("deduplicated sources are required")
    extensions = payload.get("extensions")
    if not isinstance(extensions, dict):
        raise CandidateError("extensions are required")
    metrics = extensions.get("auxsays.phase2.metrics")
    if not isinstance(metrics, list) or len(metrics) != 6:
        raise CandidateError("candidate must contain exactly six factual observations")
    if any(metric.get("stateType") != "OBS" for metric in metrics):
        raise CandidateError("factual first slice permits OBS only")
    provenance = extensions.get("auxsays.phase3.provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise CandidateError("deduplicated provenance registry is required")
    for source_id, source in payload["sources"].items():
        if not isinstance(source, dict) or source.get("sourceId") != source_id:
            raise CandidateError("malformed source reference")
        if source.get("publicDisplayAllowed") is not True:
            raise CandidateError("non-allowed source in public candidate")
        for field in ("observationTime", "publishedAt", "retrievedAt", "freshnessEvaluatedAt"):
            if field == "observationTime":
                if not isinstance(source.get(field), str) or not source[field]:
                    raise CandidateError("source observationTime is required")
            else:
                _iso_time(source.get(field), f"source.{field}")
    for metric in metrics:
        required = {"id", "stateType", "label", "value", "displayValue", "unit", "validTime", "sourceRefs", "provenanceRefs"}
        if not required.issubset(metric):
            raise CandidateError(f"incomplete PDI metric: {metric.get('id')}")
        if not isinstance(metric["sourceRefs"], list) or not metric["sourceRefs"]:
            raise CandidateError("metric sourceRefs are required")
        if not isinstance(metric["provenanceRefs"], list) or not metric["provenanceRefs"]:
            raise CandidateError("metric provenanceRefs are required")
        if any(reference not in payload["sources"] for reference in metric["sourceRefs"]):
            raise CandidateError("metric has malformed source reference")
        if any(reference not in provenance for reference in metric["provenanceRefs"]):
            raise CandidateError("metric has malformed provenance reference")
    for provenance_id, record in provenance.items():
        if not isinstance(record, dict) or record.get("id") != provenance_id:
            raise CandidateError("malformed provenance record")
        if record.get("sourceId") not in payload["sources"]:
            raise CandidateError("provenance source reference is invalid")
        if not isinstance(record.get("seriesIds"), list) or not record["seriesIds"]:
            raise CandidateError("provenance series IDs are required")
        for field in ("publishedAt", "retrievedAt", "acceptedAt"):
            _iso_time(record.get(field), f"provenance.{field}")
        if not (parse_utc(record["publishedAt"]) <= parse_utc(record["retrievedAt"]) <= parse_utc(record["acceptedAt"])):
            raise CandidateError("impossible provenance temporal ordering")
    if payload.get("events"):
        raise CandidateError("factual first slice cannot contain events")
    outlook = payload.get("outlook")
    if not isinstance(outlook, dict) or outlook.get("status") != "unavailable_not_yet_supported":
        raise CandidateError("factual Outlook must be explicitly unavailable")
    for field in ("forecasts", "industries", "occupations", "demandAllocation"):
        if outlook.get(field) != []:
            raise CandidateError("factual first slice cannot contain Outlook claims")
    _validate_public_hierarchy(payload)
    if "synthetic test" in json.dumps(payload).lower():
        raise CandidateError("fixture claim found in factual candidate")
    _secret_guard(payload)


def validate_publication_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("artifactType") != "PDI_PUBLICATION_CANDIDATE":
        raise CandidateError("artifact is not a pre-activation publication candidate")
    if "snapshot" in candidate or "publishedAt" in candidate:
        raise CandidateError("pre-activation candidate cannot claim active PDI metadata")
    metadata = candidate.get("candidate")
    if not isinstance(metadata, dict):
        raise CandidateError("candidate metadata is required")
    required = {"id", "targetSchemaVersion", "targetContractVersion", "evaluatedAt", "generatedAt", "asOf", "sourceSnapshotId", "publicationClass", "validationProfile", "payloadSha256"}
    if not required.issubset(metadata):
        raise CandidateError("candidate metadata is incomplete")
    if "publishedAt" in metadata:
        raise CandidateError("pre-activation candidate cannot contain publishedAt")
    if metadata.get("targetSchemaVersion") != "1.0.0":
        raise CandidateError("unsupported target schemaVersion")
    if metadata.get("targetContractVersion") != "1.0.0":
        raise CandidateError("unsupported target contractVersion")
    if metadata.get("publicationClass") != "factual":
        raise CandidateError("candidate publicationClass must be factual")
    if metadata.get("validationProfile") != "pdi-1.0.0-factual-pre-activation-v1":
        raise CandidateError("unsupported candidate validation profile")
    if not isinstance(metadata.get("sourceSnapshotId"), str) or not metadata["sourceSnapshotId"]:
        raise CandidateError("candidate sourceSnapshotId is required")
    for field in ("evaluatedAt", "generatedAt", "asOf"):
        _iso_time(metadata.get(field), f"candidate.{field}")
    payload = candidate.get("payload")
    if not isinstance(payload, dict):
        raise CandidateError("candidate payload is required")
    _validate_factual_payload(payload)
    expected_hash = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    if metadata.get("payloadSha256") != expected_hash:
        raise CandidateError("candidate payload hash mismatch")
    _secret_guard(candidate)


def validate_active_pdi_snapshot(snapshot_document: dict[str, Any]) -> None:
    if snapshot_document.get("schemaVersion") != "1.0.0":
        raise CandidateError("unsupported schemaVersion")
    if snapshot_document.get("contractVersion") != "1.0.0":
        raise CandidateError("missing or unsupported contractVersion")
    snapshot = snapshot_document.get("snapshot")
    if not isinstance(snapshot, dict):
        raise CandidateError("snapshot metadata is required")
    required_snapshot = {"id", "evaluatedAt", "generatedAt", "publishedAt", "asOf", "sourceSnapshotId", "publicationClass"}
    if not required_snapshot.issubset(snapshot):
        raise CandidateError("active PDI snapshot metadata is incomplete")
    if snapshot.get("publicationClass") != "factual":
        raise CandidateError("publicationClass must be factual")
    if not isinstance(snapshot.get("sourceSnapshotId"), str) or not snapshot["sourceSnapshotId"]:
        raise CandidateError("sourceSnapshotId is required")
    for field in ("evaluatedAt", "generatedAt", "publishedAt", "asOf"):
        _iso_time(snapshot.get(field), f"snapshot.{field}")
    if parse_utc(snapshot["publishedAt"]) < parse_utc(snapshot["generatedAt"]):
        raise CandidateError("publishedAt cannot precede snapshot generation")
    payload = {key: snapshot_document.get(key) for key in ("systems", "sources", "events", "outlook", "extensions")}
    _validate_factual_payload(payload)
    _secret_guard(snapshot_document)


SOURCE_PUBLIC_METADATA = {
    "bls-ces": {
        "provider": "U.S. Bureau of Labor Statistics",
        "dataset": "Current Employment Statistics",
        "authorityTier": "TIER_A_ORIGINAL_AUTHORITY",
        "methodologyUrl": "https://www.bls.gov/opub/hom/ces/home.htm",
        "nextExpectedReleaseAt": "See current BLS release calendar",
    },
    "bls-cps": {
        "provider": "U.S. Bureau of Labor Statistics",
        "dataset": "Current Population Survey labor-force statistics",
        "authorityTier": "TIER_A_ORIGINAL_AUTHORITY",
        "methodologyUrl": "https://www.bls.gov/opub/hom/cps/calculation.htm",
        "nextExpectedReleaseAt": "See current BLS release calendar",
    },
    "bls-jolts": {
        "provider": "U.S. Bureau of Labor Statistics",
        "dataset": "Job Openings and Labor Turnover Survey",
        "authorityTier": "TIER_A_ORIGINAL_AUTHORITY",
        "methodologyUrl": "https://www.bls.gov/opub/hom/jlt/presentation.htm",
        "nextExpectedReleaseAt": "See current BLS release calendar",
    },
    "dol-ui-claims": {
        "provider": "U.S. Department of Labor, Employment and Training Administration",
        "dataset": "Unemployment Insurance Weekly Claims",
        "authorityTier": "TIER_A_ORIGINAL_AUTHORITY",
        "methodologyUrl": "https://oui.doleta.gov/unemploy/claims.asp",
        "nextExpectedReleaseAt": "Thursday 08:30 ET",
    },
}


def export_publication_candidate(internal: dict[str, Any]) -> dict[str, Any]:
    """Build an immutable pre-activation artifact without claiming PDI activation."""
    validate_internal_review_model(internal)
    metrics: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}
    provenance: dict[str, dict[str, Any]] = {}
    for index, metric in enumerate(internal["metrics"]):
        source_id = metric["sourceId"]
        metadata = SOURCE_PUBLIC_METADATA.get(source_id)
        if metadata is None:
            raise CandidateError(f"unregistered public source: {source_id}")
        provenance_id = f"prov-{source_id}-{metric['vintageId']}"
        provenance_id = provenance_id.replace(":", "-").replace(".", "-")
        if provenance_id not in provenance:
            provenance[provenance_id] = {
                "id": provenance_id,
                "sourceId": source_id,
                "seriesIds": [],
                "evidenceUrl": metric["provenanceUrl"],
                "artifactSha256": metric["artifactSha256"],
                "publishedAt": metric["publicTime"],
                "retrievedAt": metric["retrievedTime"],
                "acceptedAt": metric["acceptedTime"],
                "publicationTimeKind": metric["publicationTimeKind"],
                "vintageId": metric["vintageId"],
                "revisionNumber": metric.get("revisionNumber", 0),
            }
        if metric["sourceSeriesId"] not in provenance[provenance_id]["seriesIds"]:
            provenance[provenance_id]["seriesIds"].append(metric["sourceSeriesId"])
        if source_id not in sources:
            sources[source_id] = {
                "sourceId": source_id,
                **metadata,
                "observationTime": metric["observationPeriod"],
                "publishedAt": metric["publicTime"],
                "retrievedAt": metric["retrievedTime"],
                "freshnessEvaluatedAt": internal["generatedAt"],
                "nextExpectedReleaseAt": metadata["nextExpectedReleaseAt"],
                "freshness": metric["observationFreshness"],
                "freshnessReason": metric["observationFreshnessReason"],
                "revision": f"revision {metric.get('revisionNumber', 0)}",
                "vintage": metric["vintageId"],
                "publicDisplayAllowed": True,
                "attributionRequired": True,
            }
        numeric_value = float(metric["value"])
        if numeric_value.is_integer():
            numeric_value = int(numeric_value)
        metrics.append({
            "id": metric["id"],
            "stateType": "OBS",
            "label": metric["label"],
            "value": numeric_value,
            "displayValue": f"{numeric_value:,} {metric['unit']}",
            "unit": metric["unit"],
            "validTime": metric["observationPeriod"],
            "sourceRefs": [source_id],
            "provenanceRefs": [provenance_id],
            "direction": "flat",
            "series": [{"period": metric["observationPeriod"], "displayPeriod": metric["observationPeriod"], "value": numeric_value}],
            "method": f"{metric['seasonalAdjustment']}; {metric['publicationTimeKind']}; vintage {metric['vintageId']}; revision {metric.get('revisionNumber', 0)}",
        })
    # Keep the most recent source-level times when a deduplicated source covers multiple series.
    for source_id, source in sources.items():
        source_metrics = [row for row in internal["metrics"] if row["sourceId"] == source_id]
        source["observationTime"] = max(row["observationPeriod"] for row in source_metrics)
        source["publishedAt"] = max(source_metrics, key=lambda row: parse_utc(row["publicTime"]))["publicTime"]
        source["retrievedAt"] = max(source_metrics, key=lambda row: parse_utc(row["retrievedTime"]))["retrievedTime"]
    navigation_nodes = {
        metric["id"]: {
            "id": metric["id"],
            "slug": metric["id"].lower().replace("_", "-"),
            "label": metric["label"],
            "rank": index + 1,
            "stateSummaryRefs": [metric["id"]],
            "childRefs": [],
            "availableViews": ["summary", "verified"],
        }
        for index, metric in enumerate(metrics)
    }
    payload = {
        "systems": [{
            "id": "us-labor",
            "slug": "us-labor",
            "label": "U.S. Labor System",
            "rank": 1,
            "stateSummaryRefs": [metric["id"] for metric in metrics],
            "childRefs": [metric["id"] for metric in metrics],
            "availableViews": ["summary", "verified", "outlook"],
        }],
        "sources": sources,
        "events": [],
        "outlook": {
            "status": "unavailable_not_yet_supported",
            "message": "Forecast unavailable / not yet supported",
            "horizons": [],
            "forecasts": [],
            "industries": [],
            "occupations": [],
            "demandAllocation": [],
        },
        "extensions": {
            "auxsays.phase2.metrics": metrics,
            "auxsays.phase2.trace": {"nodes": [], "edges": []},
            "auxsays.phase2.fixtureVariants": [],
            "auxsays.phase2.geographies": [{"id": "US", "label": "United States"}],
            "auxsays.phase2.ranges": [{"id": "latest", "label": "Latest available observation"}],
            "auxsays.phase2.navigationNodes": navigation_nodes,
            "auxsays.phase3.provenance": provenance,
            "auxsays.phase3.sourceHealth": {
                source_id: {
                    "observationFreshness": next(row["observationFreshness"] for row in internal["metrics"] if row["sourceId"] == source_id),
                    "observationFreshnessReason": next(row["observationFreshnessReason"] for row in internal["metrics"] if row["sourceId"] == source_id),
                    "retrievalPathHealth": next(row["retrievalPathHealth"] for row in internal["metrics"] if row["sourceId"] == source_id),
                    "retrievalPathReason": next(row["retrievalPathReason"] for row in internal["metrics"] if row["sourceId"] == source_id),
                }
                for source_id in sources
            },
        },
    }
    snapshot_time = internal["generatedAt"]
    candidate = {
        "artifactType": "PDI_PUBLICATION_CANDIDATE",
        "candidate": {
            "id": "factual-gate-a-candidate-2026-08-18",
            "targetSchemaVersion": "1.0.0",
            "targetContractVersion": "1.0.0",
            "evaluatedAt": snapshot_time,
            "generatedAt": snapshot_time,
            "asOf": max(metric["acceptedTime"] for metric in internal["metrics"]),
            "sourceSnapshotId": "phase3-normalized-six-indicator-2026-08-18",
            "publicationClass": "factual",
            "validationProfile": "pdi-1.0.0-factual-pre-activation-v1",
            "payloadSha256": hashlib.sha256(canonical_bytes(payload)).hexdigest(),
        },
        "payload": payload,
    }
    validate_publication_candidate(candidate)
    return candidate


def materialize_active_pdi_snapshot(candidate: dict[str, Any], *, activated_at: str) -> dict[str, Any]:
    validate_publication_candidate(candidate)
    _iso_time(activated_at, "activated_at")
    metadata = candidate["candidate"]
    if parse_utc(activated_at) < parse_utc(metadata["generatedAt"]):
        raise CandidateError("activation cannot precede candidate generation")
    snapshot_id = f"factual-active-{activated_at.replace(':', '-').replace('.', '-')}-{metadata['payloadSha256'][:12]}"
    document = {
        "schemaVersion": metadata["targetSchemaVersion"],
        "contractVersion": metadata["targetContractVersion"],
        "snapshot": {
            "id": snapshot_id,
            "evaluatedAt": metadata["evaluatedAt"],
            "generatedAt": metadata["generatedAt"],
            "publishedAt": activated_at,
            "asOf": metadata["asOf"],
            "sourceSnapshotId": metadata["sourceSnapshotId"],
            "publicationClass": metadata["publicationClass"],
        },
        **copy.deepcopy(candidate["payload"]),
    }
    validate_active_pdi_snapshot(document)
    return document


class AtomicPublisher:
    def __init__(self, root: Path):
        self.root = root
        self.candidates = root / "candidates"
        self.objects = root / "objects"
        self.pointer = root / "current.json"
        self.candidates.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write_immutable(path: Path, payload: bytes) -> None:
        if path.exists():
            return
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

    def stage(self, candidate: dict[str, Any]) -> tuple[str, Path]:
        validate_publication_candidate(candidate)
        payload = canonical_bytes(candidate)
        digest = hashlib.sha256(payload).hexdigest()
        path = self.candidates / f"{digest}.json"
        self._write_immutable(path, payload)
        return digest, path

    def activate_local(self, digest: str, *, rights_allowed: bool = True, activated_at: str | None = None) -> tuple[str, Path]:
        candidate_path = self.candidates / f"{digest}.json"
        if not candidate_path.exists():
            raise CandidateError("candidate object does not exist")
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        validate_publication_candidate(candidate)
        if not rights_allowed:
            raise CandidateError("current publication rights prohibit activation")
        activation_time = activated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        active_snapshot = materialize_active_pdi_snapshot(candidate, activated_at=activation_time)
        active_payload = canonical_bytes(active_snapshot)
        active_digest = hashlib.sha256(active_payload).hexdigest()
        active_path = self.objects / f"{active_digest}.json"
        self._write_immutable(active_path, active_payload)
        temporary = self.root / f".current.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        temporary.write_text(json.dumps({"sha256": active_digest, "relativePath": f"objects/{active_digest}.json"}, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.pointer)
        return active_digest, active_path

    def withdraw(self, cause: str) -> None:
        temporary = self.root / f".current.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        temporary.write_text(json.dumps({"status": "UNAVAILABLE", "cause": cause}, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.pointer)
