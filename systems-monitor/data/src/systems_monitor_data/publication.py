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


def validate_factual_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("publicationClass") != "factual":
        raise CandidateError("candidate must be factual")
    if candidate.get("activationStatus") != "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED":
        raise CandidateError("candidate activation boundary is missing")
    metrics = candidate.get("metrics")
    if not isinstance(metrics, list) or len(metrics) != 6:
        raise CandidateError("candidate must contain exactly six factual observations")
    prohibited = {"FCST", "SCEN"}
    if any(metric.get("stateType") in prohibited or metric.get("stateType") != "OBS" for metric in metrics):
        raise CandidateError("fixture or forecast state found in factual candidate")
    for metric in metrics:
        required = {"id", "label", "value", "unit", "observationPeriod", "sourceId", "sourceLabel", "publicTime", "retrievedTime", "acceptedTime", "sourceHealth", "provenanceUrl", "artifactSha256", "vintageId"}
        if not required.issubset(metric):
            raise CandidateError(f"incomplete factual metric: {metric.get('id')}")
        if metric.get("rightsState") != "ALLOW":
            raise CandidateError("non-allowed rights state")
        if not (parse_utc(metric["publicTime"]) <= parse_utc(metric["retrievedTime"]) <= parse_utc(metric["acceptedTime"])):
            raise CandidateError("impossible candidate temporal ordering")
        if any(secret in json.dumps(metric).lower() for secret in ("registrationkey", "api_key", "authorization")):
            raise CandidateError("secret-shaped field in candidate")
    if candidate.get("forecasts") or candidate.get("scenarios") or candidate.get("rankings") or candidate.get("events"):
        raise CandidateError("factual Phase-3 candidate cannot contain later-phase claims")
    if candidate.get("outlook", {}).get("status") != "unavailable_not_yet_supported":
        raise CandidateError("factual Outlook must be unavailable")


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
