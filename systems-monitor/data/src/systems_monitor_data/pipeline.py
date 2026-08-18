from __future__ import annotations

import hashlib
import json
import uuid
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from .normalize import normalize_bls, normalize_dol_xml
from .publication import canonical_bytes, validate_factual_candidate
from .raw import RawStore
from .registry import Registry
from .retrieval import BoundedRetriever, RequestBudget, bls_request_body
from .rights import RightsEngine
from .storage import ObservationStore


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class FirstSlicePipeline:
    def __init__(self, package_root: Path, local_root: Path):
        self.package_root = package_root
        self.local_root = local_root
        self.registry = Registry(package_root / "config")
        self.rights = RightsEngine(self.registry.rights)
        self.retriever = BoundedRetriever()
        self.raw = RawStore(local_root / "raw")
        self.store = ObservationStore(local_root / "systems-monitor.sqlite")

    def collect_bls(self, year: int) -> list:
        endpoint = self.registry.source("bls-ces")["endpoint"]
        indicators = [row for row in self.registry.enabled_indicators() if row["source_id"].startswith("bls-")]
        for source_id in {row["source_id"] for row in indicators}:
            self.rights.require(source_id, "ingestion")
            self.rights.require(source_id, "raw_retention")
        request_body = bls_request_body([row["source_series_id"] for row in indicators], year, year)
        limits = self.registry.source("bls-ces")["operational_limits"]
        RequestBudget(max_per_day=limits["queries_per_day"], max_per_10_seconds=limits["requests_per_10_seconds"]).record()
        retrieved = self.retriever.fetch(endpoint, method="POST", body=request_body, headers={"Content-Type": "application/json"}, expected_types=("application/json",))
        run_id = str(uuid.uuid4())
        release_id = f"bls-retrieval-{retrieved.retrieved_time}"
        raw = self.raw.capture(source_id="bls-combined-request", run_id=run_id, request_identity=retrieved.final_url, retrieved_time=retrieved.retrieved_time, release_id=release_id, content_type=retrieved.content_type, body=retrieved.body, parser_version="bls-json-v1", rights_result="ALLOW")
        accepted = now_utc()
        observations = normalize_bls(retrieved.body, indicators, release_id=release_id, artifact_sha256=raw.sha256, retrieved_time=retrieved.retrieved_time, accepted_time=accepted, provenance_url=endpoint)
        for observation in observations:
            self.store.add(observation)
        return observations

    def collect_dol(self, year: int):
        source = self.registry.source("dol-ui-claims")
        self.rights.require("dol-ui-claims", "ingestion")
        self.rights.require("dol-ui-claims", "raw_retention")
        request_body = urllib.parse.urlencode({"level": "us", "strtdate": str(year), "enddate": str(year), "filetype": "xml", "submit": "Submit"}).encode()
        limits = source["operational_limits"]
        RequestBudget(max_per_day=limits["queries_per_day"], max_per_10_seconds=limits["requests_per_10_seconds"]).record()
        retrieved = self.retriever.fetch(source["endpoint"], method="POST", body=request_body, headers={"Content-Type": "application/x-www-form-urlencoded"}, expected_types=("text/xml", "application/xml"))
        run_id = str(uuid.uuid4())
        release_id = f"dol-query-{retrieved.retrieved_time}"
        raw = self.raw.capture(source_id="dol-ui-claims", run_id=run_id, request_identity=retrieved.final_url, retrieved_time=retrieved.retrieved_time, release_id=release_id, content_type=retrieved.content_type, body=retrieved.body, parser_version="dol-weekly-claims-xml-v1", rights_result="ALLOW")
        indicator = next(row for row in self.registry.enabled_indicators() if row["source_id"] == "dol-ui-claims")
        observation = normalize_dol_xml(retrieved.body, indicator, release_id=release_id, artifact_sha256=raw.sha256, retrieved_time=retrieved.retrieved_time, accepted_time=now_utc(), provenance_url=source["endpoint"])
        self.store.add(observation)
        return observation


def candidate_from_observations(observations: list, *, generated_at: str) -> dict:
    metrics = []
    for observation in observations:
        source_health = "current"
        if observation.source_id == "dol-ui-claims":
            observation_date = datetime.fromisoformat(observation.valid_time).replace(tzinfo=timezone.utc)
            generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            if (generated - observation_date).days > 14:
                source_health = "stale"
        metrics.append({
            "id": observation.indicator_id,
            "label": observation.indicator_id.replace("US_LABOR_", "").replace("_", " ").title(),
            "stateType": "OBS",
            "value": str(observation.value),
            "unit": observation.unit,
            "observationPeriod": observation.valid_time,
            "sourceId": observation.source_id,
            "sourceLabel": observation.source_id,
            "publicTime": observation.public_time,
            "retrievedTime": observation.retrieved_time,
            "acceptedTime": observation.accepted_time,
            "publicationTimeKind": observation.publication_time_kind,
            "vintageId": observation.vintage_id,
            "revisionNumber": observation.revision_number,
            "sourceHealth": source_health,
            "rightsState": observation.rights_state,
            "provenanceUrl": observation.provenance_url,
            "artifactSha256": observation.artifact_sha256,
        })
    candidate = {
        "schemaVersion": "phase3-factual-candidate-1.0.0",
        "publicationClass": "factual",
        "activationStatus": "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED",
        "generatedAt": generated_at,
        "geography": "US",
        "metrics": metrics,
        "forecasts": [],
        "scenarios": [],
        "rankings": [],
        "events": [],
        "outlook": {"status": "unavailable_not_yet_supported", "message": "Forecast unavailable / not yet supported"},
    }
    validate_factual_candidate(candidate)
    return candidate


def write_review_candidate(path: Path, candidate: dict) -> str:
    payload = canonical_bytes(candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()
