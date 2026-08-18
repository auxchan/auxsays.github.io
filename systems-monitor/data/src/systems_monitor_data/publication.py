from __future__ import annotations

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


def validate_factual_candidate(candidate: dict[str, Any]) -> None:
    """Validate the immutable public-interface candidate, not the internal review model."""
    if candidate.get("schemaVersion") != "1.0.0":
        raise CandidateError("unsupported schemaVersion")
    if candidate.get("contractVersion") != "1.0.0":
        raise CandidateError("missing or unsupported contractVersion")
    snapshot = candidate.get("snapshot")
    if not isinstance(snapshot, dict):
        raise CandidateError("snapshot metadata is required")
    required_snapshot = {"id", "evaluatedAt", "generatedAt", "publishedAt", "asOf", "sourceSnapshotId", "publicationClass"}
    if not required_snapshot.issubset(snapshot):
        raise CandidateError("snapshot metadata is incomplete")
    if snapshot.get("publicationClass") != "factual":
        raise CandidateError("publicationClass must be factual")
    if not isinstance(snapshot.get("sourceSnapshotId"), str) or not snapshot["sourceSnapshotId"]:
        raise CandidateError("sourceSnapshotId is required")
    for field in ("evaluatedAt", "generatedAt", "publishedAt", "asOf"):
        _iso_time(snapshot.get(field), f"snapshot.{field}")
    for collection in ("systems", "events"):
        if not isinstance(candidate.get(collection), list):
            raise CandidateError(f"{collection} must be an array")
    if not isinstance(candidate.get("sources"), dict) or not candidate["sources"]:
        raise CandidateError("deduplicated sources are required")
    extensions = candidate.get("extensions")
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
    for source_id, source in candidate["sources"].items():
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
        if any(reference not in candidate["sources"] for reference in metric["sourceRefs"]):
            raise CandidateError("metric has malformed source reference")
        if any(reference not in provenance for reference in metric["provenanceRefs"]):
            raise CandidateError("metric has malformed provenance reference")
    for provenance_id, record in provenance.items():
        if not isinstance(record, dict) or record.get("id") != provenance_id:
            raise CandidateError("malformed provenance record")
        if record.get("sourceId") not in candidate["sources"]:
            raise CandidateError("provenance source reference is invalid")
        if not isinstance(record.get("seriesIds"), list) or not record["seriesIds"]:
            raise CandidateError("provenance series IDs are required")
        for field in ("publishedAt", "retrievedAt", "acceptedAt"):
            _iso_time(record.get(field), f"provenance.{field}")
        if not (parse_utc(record["publishedAt"]) <= parse_utc(record["retrievedAt"]) <= parse_utc(record["acceptedAt"])):
            raise CandidateError("impossible provenance temporal ordering")
    if candidate.get("events"):
        raise CandidateError("factual first slice cannot contain events")
    outlook = candidate.get("outlook")
    if not isinstance(outlook, dict) or outlook.get("status") != "unavailable_not_yet_supported":
        raise CandidateError("factual Outlook must be explicitly unavailable")
    for field in ("forecasts", "industries", "occupations", "demandAllocation"):
        if outlook.get(field) != []:
            raise CandidateError("factual first slice cannot contain Outlook claims")
    if "synthetic test" in json.dumps(candidate).lower():
        raise CandidateError("fixture claim found in factual candidate")
    _secret_guard(candidate)


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


def export_public_pdi_candidate(internal: dict[str, Any]) -> dict[str, Any]:
    """Explicit boundary from normalized review evidence to the BINDING PDI."""
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
    snapshot_time = internal["generatedAt"]
    candidate = {
        "schemaVersion": "1.0.0",
        "contractVersion": "1.0.0",
        "snapshot": {
            "id": "factual-gate-a-candidate-2026-08-18",
            "evaluatedAt": snapshot_time,
            "generatedAt": snapshot_time,
            "publishedAt": snapshot_time,
            "asOf": max(metric["acceptedTime"] for metric in internal["metrics"]),
            "sourceSnapshotId": "phase3-normalized-six-indicator-2026-08-18",
            "publicationClass": "factual",
        },
        "systems": [{
            "id": "us-labor",
            "slug": "us-labor",
            "label": "U.S. Labor System",
            "rank": 1,
            "stateSummaryRefs": [metric["id"] for metric in metrics],
            "availableViews": ["summary", "verified", "outlook"],
            "children": [{
                "id": metric["id"],
                "slug": metric["id"].lower().replace("_", "-"),
                "label": metric["label"],
                "rank": index + 1,
                "stateSummaryRefs": [metric["id"]],
                "availableViews": ["summary", "verified"],
            } for index, metric in enumerate(metrics)],
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
            "auxsays.phase3.activation": {"status": "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED"},
        },
    }
    validate_factual_candidate(candidate)
    return candidate


class AtomicPublisher:
    def __init__(self, root: Path):
        self.root = root
        self.objects = root / "objects"
        self.pointer = root / "current.json"
        self.objects.mkdir(parents=True, exist_ok=True)

    def stage(self, candidate: dict[str, Any]) -> tuple[str, Path]:
        validate_factual_candidate(candidate)
        payload = canonical_bytes(candidate)
        digest = hashlib.sha256(payload).hexdigest()
        path = self.objects / f"{digest}.json"
        if not path.exists():
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        return digest, path

    def activate_local(self, digest: str, *, rights_allowed: bool = True) -> None:
        candidate_path = self.objects / f"{digest}.json"
        if not candidate_path.exists():
            raise CandidateError("candidate object does not exist")
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        validate_factual_candidate(candidate)
        if not rights_allowed:
            raise CandidateError("current publication rights prohibit activation")
        temporary = self.root / f".current.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        temporary.write_text(json.dumps({"sha256": digest, "relativePath": f"objects/{digest}.json"}, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.pointer)

    def withdraw(self, cause: str) -> None:
        temporary = self.root / f".current.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        temporary.write_text(json.dumps({"status": "UNAVAILABLE", "cause": cause}, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.pointer)
