from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Protocol


_CENSUS_HOST = "api.census.gov"
_CREDENTIAL_NAME = "AUXSAYS_CENSUS_API_KEY"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_YEAR = re.compile(r"^\d{4}$")
_EITS_PERIOD = re.compile(r"^\d{4}(?:-(?:0[1-9]|1[0-2]))?$")
_MISSING = {"", "-", "(s)", "n", "na", "null", "x"}


@dataclass(frozen=True)
class CensusRequest:
    source_id: str
    endpoint: str
    public_identity: str
    query: tuple[tuple[str, str], ...]
    _credential: str = field(repr=False, compare=False)

    def sensitive_url_for_transport(self) -> str:
        """Build the ephemeral Census request URL. Never persist or log this value."""

        return f"{self.endpoint}?{urllib.parse.urlencode((*self.query, ('key', self._credential)))}"

    def __str__(self) -> str:
        return self.public_identity


@dataclass(frozen=True)
class CensusCollectionPlan:
    source_id: str
    activation_state: str
    health_status: str
    reason: str | None
    request: CensusRequest | None


@dataclass(frozen=True)
class CensusArtifact:
    body: bytes
    content_type: str
    public_request_identity: str
    retrieved_time: str


@dataclass(frozen=True)
class CensusObservationCandidate:
    observation_id: str
    canonical_factor: str
    source_id: str
    source_series_id: str
    release_id: str
    artifact_sha256: str
    value: Decimal
    unit: str
    frequency: str
    geography: str
    seasonal_adjustment: str
    observation_period: str
    public_time: str
    retrieved_time: str
    accepted_time: None
    publication_time_kind: str
    revision_status: str
    provenance_url: str
    evidence_url: str
    methodology_url: str
    activation_state: str
    publication_eligible: bool


@dataclass(frozen=True)
class CensusCollectionResult:
    source_id: str
    activation_state: str
    health_status: str
    reason: str | None
    artifact_sha256: str | None
    candidates: tuple[CensusObservationCandidate, ...]


class CensusTransport(Protocol):
    def fetch(self, request: CensusRequest) -> CensusArtifact: ...


def load_layoffs_census_registry(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1.0.0":
        raise ValueError("unsupported Census layoffs registry schema")
    if document.get("credential_environment_variable") != _CREDENTIAL_NAME:
        raise ValueError("Census credential environment contract changed")
    sources = document.get("sources")
    if not isinstance(sources, list) or {row.get("source_id") for row in sources} != {
        "census-bds",
        "census-bfs",
        "census-marts",
        "census-m3",
        "census-mtis",
        "census-ftd",
    }:
        raise ValueError("Census registry must contain the reviewed six programs")
    for source in sources:
        _validate_source(source)
    return document


def census_source(document: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    for source in document["sources"]:
        if source["source_id"] == source_id:
            return source
    raise KeyError(source_id)


def plan_census_collection(
    document: Mapping[str, Any],
    source_id: str,
    period: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> CensusCollectionPlan:
    source = census_source(document, source_id)
    env = os.environ if environment is None else environment
    credential = env.get(_CREDENTIAL_NAME, "").strip()
    if not credential:
        return CensusCollectionPlan(
            source_id,
            "SOURCE_IDENTIFIED",
            "blocked",
            f"credential_missing:{_CREDENTIAL_NAME}",
            None,
        )
    if not source["selector_status"].startswith("VERIFIED_") or not source["series"]:
        return CensusCollectionPlan(
            source_id,
            "SOURCE_IDENTIFIED",
            "blocked",
            "official_selector_unresolved",
            None,
        )

    query_mode = source["query_mode"]
    if query_mode == "BDS":
        if not _YEAR.fullmatch(period):
            raise ValueError("BDS period must be a four-digit reference year")
        query = (
            ("get", ",".join(source["query_fields"])),
            ("YEAR", period),
            ("for", source["geography"]),
        )
    elif query_mode == "EITS":
        if not _EITS_PERIOD.fullmatch(period):
            raise ValueError("EITS period must be YYYY or YYYY-MM")
        parts = [("get", ",".join(source["query_fields"])), ("time", period)]
        if source["geography"]:
            parts.append(("for", source["geography"]))
        query = tuple(parts)
    else:
        raise ValueError("unsupported Census query mode")

    public_identity = f"{source['endpoint']}?{urllib.parse.urlencode(query)}"
    request = CensusRequest(source_id, source["endpoint"], public_identity, query, credential)
    return CensusCollectionPlan(
        source_id,
        "SOURCE_ENABLED_PENDING_ACCEPTANCE",
        "success",
        None,
        request,
    )


class CensusHttpTransport:
    """Strict standard-library Census transport with bounded response size."""

    def __init__(self, *, timeout_seconds: float = 20, max_bytes: int = 8_000_000):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def fetch(self, request: CensusRequest) -> CensusArtifact:
        _validate_endpoint(request.endpoint)
        sensitive_url = request.sensitive_url_for_transport()
        http_request = urllib.request.Request(
            sensitive_url,
            headers={"User-Agent": "AUXSAYS-Systems-Monitor/0.1 (+https://auxsays.com)"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                _validate_endpoint(response.geturl().split("?", 1)[0])
                content_type = response.headers.get_content_type().lower()
                if content_type not in {"application/json", "text/json"}:
                    raise ValueError("Census response content type is not JSON")
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > self.max_bytes:
                    raise ValueError("Census response exceeds configured size bound")
                payload = response.read(self.max_bytes + 1)
                if len(payload) > self.max_bytes:
                    raise ValueError("Census response exceeds configured size bound")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"Census retrieval failed for {request.public_identity}: {type(exc).__name__}"
            ) from None
        return CensusArtifact(
            payload,
            content_type,
            request.public_identity,
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )


def collect_census_candidates(
    document: Mapping[str, Any],
    source_id: str,
    period: str,
    *,
    release_id: str,
    environment: Mapping[str, str] | None = None,
    transport: CensusTransport | None = None,
) -> CensusCollectionResult:
    plan = plan_census_collection(document, source_id, period, environment=environment)
    if plan.request is None:
        return CensusCollectionResult(source_id, plan.activation_state, plan.health_status, plan.reason, None, ())
    artifact = (transport or CensusHttpTransport()).fetch(plan.request)
    artifact_sha256 = hashlib.sha256(artifact.body).hexdigest()
    source = census_source(document, source_id)
    candidates = parse_census_payload(
        artifact.body,
        source,
        release_id=release_id,
        artifact_sha256=artifact_sha256,
        retrieved_time=artifact.retrieved_time,
        provenance_url=source["endpoint"],
    )
    return CensusCollectionResult(
        source_id,
        "SOURCE_ENABLED_PENDING_ACCEPTANCE",
        "success",
        None,
        artifact_sha256,
        candidates,
    )


def parse_census_payload(
    payload: bytes,
    source: Mapping[str, Any],
    *,
    release_id: str,
    artifact_sha256: str,
    retrieved_time: str,
    provenance_url: str,
) -> tuple[CensusObservationCandidate, ...]:
    _validate_batch_inputs(release_id, artifact_sha256, retrieved_time, provenance_url)
    try:
        rows = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Census response is not valid JSON") from exc
    if not isinstance(rows, list) or len(rows) < 2 or not isinstance(rows[0], list):
        raise ValueError("Census schema drift or empty response")
    header = rows[0]
    if not all(isinstance(value, str) for value in header) or len(header) != len(set(header)):
        raise ValueError("Census response header is malformed")
    records = []
    for row in rows[1:]:
        if not isinstance(row, list) or len(row) != len(header):
            raise ValueError("Census response row does not match its header")
        records.append(dict(zip(header, row)))
    if source["query_mode"] == "BDS":
        candidates = _parse_bds_records(records, header, source, release_id, artifact_sha256, retrieved_time, provenance_url)
    elif source["query_mode"] == "EITS":
        candidates = _parse_eits_records(records, header, source, release_id, artifact_sha256, retrieved_time, provenance_url)
    else:
        raise ValueError("unsupported Census query mode")
    if not candidates:
        raise ValueError("Census response contained no usable selected observations")
    return tuple(sorted(candidates, key=lambda row: (row.source_series_id, row.observation_period), reverse=True))


def _parse_bds_records(
    records: list[dict[str, Any]],
    header: list[str],
    source: Mapping[str, Any],
    release_id: str,
    artifact_sha256: str,
    retrieved_time: str,
    provenance_url: str,
) -> list[CensusObservationCandidate]:
    required = {"YEAR", "us", *(row["source_series_id"] for row in source["series"])}
    if not required.issubset(header):
        raise ValueError("BDS response omitted a requested variable or national geography")
    candidates = []
    for record in records:
        if record["us"] != "1" or not _YEAR.fullmatch(str(record["YEAR"])):
            raise ValueError("BDS response is not the requested U.S. annual geography")
        for series in source["series"]:
            value = _decimal_or_none(record[series["source_series_id"]])
            if value is None:
                continue
            candidates.append(
                _candidate(source, series, release_id, artifact_sha256, value, str(record["YEAR"]), retrieved_time, provenance_url)
            )
    return candidates


def _parse_eits_records(
    records: list[dict[str, Any]],
    header: list[str],
    source: Mapping[str, Any],
    release_id: str,
    artifact_sha256: str,
    retrieved_time: str,
    provenance_url: str,
) -> list[CensusObservationCandidate]:
    required = {"data_type_code", "category_code", "seasonally_adj", "cell_value", "time"}
    if not required.issubset(header):
        raise ValueError("EITS response omitted required dimensions")
    candidates = []
    seen: set[str] = set()
    for record in records:
        for series in source["series"]:
            selector = series["selector"]
            if not all(str(record.get(key)) == value for key, value in selector.items()):
                continue
            if "error_data" in record and str(record["error_data"]).lower() not in {"no", "false", "0"}:
                raise ValueError("EITS selected row is an error/uncertainty row, not an observation")
            value = _decimal_or_none(record["cell_value"])
            if value is None:
                continue
            period = str(record["time"])
            if not _EITS_PERIOD.fullmatch(period):
                raise ValueError("EITS represented period is malformed")
            identity = f"{series['source_series_id']}|{period}"
            if identity in seen:
                raise ValueError("EITS response duplicated a selected series period")
            seen.add(identity)
            candidates.append(
                _candidate(source, series, release_id, artifact_sha256, value, period, retrieved_time, provenance_url)
            )
    missing = {row["source_series_id"] for row in source["series"]} - {row.source_series_id for row in candidates}
    if missing:
        raise ValueError(f"EITS response omitted selected observations: {sorted(missing)}")
    return candidates


def _candidate(
    source: Mapping[str, Any],
    series: Mapping[str, Any],
    release_id: str,
    artifact_sha256: str,
    value: Decimal,
    observation_period: str,
    retrieved_time: str,
    provenance_url: str,
) -> CensusObservationCandidate:
    observation_id = hashlib.sha256(
        f"{series['source_series_id']}|{release_id}|{observation_period}".encode("utf-8")
    ).hexdigest()
    return CensusObservationCandidate(
        observation_id=observation_id,
        canonical_factor=series["canonical_factor"],
        source_id=source["source_id"],
        source_series_id=series["source_series_id"],
        release_id=release_id,
        artifact_sha256=artifact_sha256,
        value=value,
        unit=series["unit"],
        frequency="annual" if source["query_mode"] == "BDS" else "monthly",
        geography="US",
        seasonal_adjustment=series["seasonal_adjustment"],
        observation_period=observation_period,
        public_time=retrieved_time,
        retrieved_time=retrieved_time,
        accepted_time=None,
        publication_time_kind="conservative_retrieval_bound",
        revision_status="retrieved_vintage_subject_to_revision",
        provenance_url=provenance_url,
        evidence_url=source["evidence_url"],
        methodology_url=source["methodology_url"],
        activation_state="SOURCE_ENABLED_PENDING_ACCEPTANCE",
        publication_eligible=False,
    )


def _decimal_or_none(raw: Any) -> Decimal | None:
    text = "" if raw is None else str(raw).strip()
    if text.lower() in _MISSING:
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError("Census observation value is not numeric or a recognized missing marker") from exc


def _validate_source(source: Mapping[str, Any]) -> None:
    required = {
        "source_id",
        "program",
        "endpoint",
        "variables_url",
        "evidence_url",
        "methodology_url",
        "cadence",
        "expected_release_policy",
        "grace_period_hours",
        "revision_behavior",
        "rights_policy",
        "selector_status",
        "query_mode",
        "query_fields",
        "series",
    }
    if not required.issubset(source):
        raise ValueError("Census source profile is incomplete")
    _validate_endpoint(source["endpoint"])
    for field_name in ("variables_url", "evidence_url", "methodology_url"):
        if not str(source[field_name]).startswith("https://"):
            raise ValueError("Census evidence links must use HTTPS")
    ids = [series["source_series_id"] for series in source["series"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Census source series IDs must be unique within a program")
    if source["selector_status"].startswith("VERIFIED_") and not source["series"]:
        raise ValueError("verified Census sources require exact series selectors")
    if not source["selector_status"].startswith("VERIFIED_") and source["series"]:
        raise ValueError("unresolved Census sources cannot declare series selectors")


def _validate_endpoint(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if (
        parts.scheme != "https"
        or (parts.hostname or "").lower() != _CENSUS_HOST
        or parts.port not in (None, 443)
        or parts.username
        or parts.password
        or parts.query
        or not parts.path.startswith("/data/timeseries/")
    ):
        raise ValueError("Census endpoint is outside the reviewed API boundary")


def _validate_batch_inputs(release_id: str, artifact_sha256: str, retrieved_time: str, provenance_url: str) -> None:
    if not release_id.strip() or not _HASH.fullmatch(artifact_sha256):
        raise ValueError("release identity and artifact hash are required")
    try:
        instant = datetime.fromisoformat(retrieved_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("retrieval time must be ISO-8601") from exc
    if instant.tzinfo is None:
        raise ValueError("retrieval time must be timezone-aware")
    _validate_endpoint(provenance_url)
