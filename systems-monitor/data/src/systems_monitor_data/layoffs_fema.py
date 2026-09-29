from __future__ import annotations

import hashlib
import json
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


_ALLOWED_HOSTS = {"www.fema.gov"}


@dataclass(frozen=True)
class FemaEventCandidate:
    event_id: str
    declaration_id: str
    source_record_id: str
    canonical_factor_id: str
    declaration_type: str
    incident_type: str
    title: str
    declaration_date: str
    incident_begin: str
    incident_end: str | None
    state: str
    designated_area: str
    fips_state_code: str | None
    fips_county_code: str | None
    retrieved_time: str
    last_refresh: str
    source_hash: str
    artifact_sha256: str
    provenance_url: str
    activation_state: str
    publication_eligible: bool
    relationship_boundary: str


def load_layoffs_fema_registry(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schemaVersion") != "layoffs-fema-source-1.0.0":
        raise ValueError("unsupported FEMA source registry schema")
    sources = document.get("sources")
    if not isinstance(sources, list) or len(sources) != 1:
        raise ValueError("FEMA registry must contain one bounded OpenFEMA source")
    source = sources[0]
    if source.get("sourceId") != "fema-openfema":
        raise ValueError("unexpected FEMA source identity")
    _validate_url(source["endpoint"])
    for field in ("evidenceUrl", "methodologyUrl", "rightsUrl"):
        _validate_url(source[field])
    if source.get("selectorStatus") != "VERIFIED_DATASET_AND_FIELDS":
        raise ValueError("FEMA event selector is not verified")
    if source.get("rightsPolicy") != "PENDING_REPOSITORY_RIGHTS_ACCEPTANCE":
        raise ValueError("FEMA rights posture must fail closed until accepted")
    return document


def plan_fema_request(source: Mapping[str, Any], *, declared_since: str, top: int = 1000) -> str:
    _iso(declared_since)
    if top < 1 or top > 1000:
        raise ValueError("OpenFEMA page size must be between 1 and 1000")
    query = urllib.parse.urlencode({
        "$filter": f"declarationDate ge '{declared_since}'",
        "$orderby": "declarationDate asc,id asc",
        "$top": str(top),
    })
    url = f"{source['endpoint']}?{query}"
    _validate_url(url)
    return url


def parse_fema_declarations(
    payload: bytes,
    source: Mapping[str, Any],
    *,
    artifact_sha256: str,
    retrieved_time: str,
    provenance_url: str,
) -> tuple[FemaEventCandidate, ...]:
    if not len(artifact_sha256) == 64 or any(character not in "0123456789abcdefABCDEF" for character in artifact_sha256):
        raise ValueError("FEMA artifact SHA-256 is invalid")
    _iso(retrieved_time)
    _validate_url(provenance_url)
    try:
        document = json.loads(payload)
        rows = document["DisasterDeclarationsSummaries"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("OpenFEMA schema drift or malformed response") from exc
    if not isinstance(rows, list):
        raise ValueError("OpenFEMA declarations must be a list")

    required = set(source["requiredFields"])
    events: list[FemaEventCandidate] = []
    identities: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not required.issubset(row):
            raise ValueError("OpenFEMA declaration omitted required fields")
        if any(row[field] in (None, "") for field in required):
            raise ValueError("OpenFEMA declaration has an empty required field")
        for field in ("declarationDate", "incidentBeginDate", "lastRefresh"):
            _iso(str(row[field]))
        incident_end = row.get("incidentEndDate")
        if incident_end:
            _iso(str(incident_end))
        declaration_id = str(row["femaDeclarationString"])
        record_id = str(row["id"])
        identity = f"fema:{declaration_id}:{record_id}"
        if identity in identities:
            raise ValueError("OpenFEMA response duplicated a source record")
        identities.add(identity)
        events.append(FemaEventCandidate(
            event_id=identity,
            declaration_id=declaration_id,
            source_record_id=record_id,
            canonical_factor_id=source["canonicalFactorId"],
            declaration_type=str(row["declarationType"]),
            incident_type=str(row["incidentType"]),
            title=str(row["declarationTitle"]),
            declaration_date=str(row["declarationDate"]),
            incident_begin=str(row["incidentBeginDate"]),
            incident_end=str(incident_end) if incident_end else None,
            state=str(row["state"]),
            designated_area=str(row["designatedArea"]),
            fips_state_code=str(row["fipsStateCode"]) if row.get("fipsStateCode") else None,
            fips_county_code=str(row["fipsCountyCode"]) if row.get("fipsCountyCode") else None,
            retrieved_time=retrieved_time,
            last_refresh=str(row["lastRefresh"]),
            source_hash=str(row["hash"]),
            artifact_sha256=artifact_sha256.lower(),
            provenance_url=provenance_url,
            activation_state="EVENT_SOURCE_IDENTIFIED_PENDING_ACCEPTANCE",
            publication_eligible=False,
            relationship_boundary=source["relationshipBoundary"],
        ))
    return tuple(events)


def event_revision_key(event: FemaEventCandidate) -> str:
    return hashlib.sha256(
        f"{event.source_record_id}|{event.last_refresh}|{event.source_hash}".encode("utf-8")
    ).hexdigest()


def _iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("OpenFEMA timestamps must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("OpenFEMA timestamps must include timezone")
    return parsed


def _validate_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in _ALLOWED_HOSTS or parts.port not in (None, 443) or parts.username or parts.password:
        raise ValueError("OpenFEMA URL is outside the reviewed host boundary")
    query_keys = {key.lower() for key, _ in urllib.parse.parse_qsl(parts.query)}
    if query_keys & {"key", "api_key", "token", "access_token"}:
        raise ValueError("OpenFEMA provenance URL cannot contain credentials")
