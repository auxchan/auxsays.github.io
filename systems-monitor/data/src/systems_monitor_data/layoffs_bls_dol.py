from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from .retrieval import BoundedRetriever, RequestBudget, RetrievedArtifact, bls_request_body
from .raw import RawStore


_MONTHS = {f"M{month:02d}": month for month in range(1, 13)}
_QUARTERS = {f"Q{quarter:02d}": quarter for quarter in range(1, 5)}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class LayoffsSeriesSpec:
    canonical_factor: str
    source_id: str
    series_id: str
    label: str
    unit: str
    frequency: str
    seasonal_adjustment: str
    valid_time: str
    activation_state: str
    human_evidence_url: str
    methodology_url: str
    xml_path: str | None = None
    existing_acceptance_scope: str | None = None


@dataclass(frozen=True)
class SourceObservationCandidate:
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
    accepted_time: str | None
    publication_time_kind: str
    revision_status: str
    provenance_url: str
    evidence_url: str
    methodology_url: str


@dataclass(frozen=True)
class ParsedSourceBatch:
    observations: tuple[SourceObservationCandidate, ...]
    skipped_missing_values: int
    source_release_marker: str


def load_layoffs_bls_dol_registry(path: Path) -> tuple[dict[str, Any], tuple[LayoffsSeriesSpec, ...]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    specs = tuple(LayoffsSeriesSpec(**row) for row in document["series"])
    _validate_registry(document, specs)
    return document["acquisition"], specs


def _validate_registry(document: dict[str, Any], specs: tuple[LayoffsSeriesSpec, ...]) -> None:
    if document.get("schema_version") != "1.0.0" or len(specs) != 19:
        raise ValueError("layoffs BLS/DOL registry must contain the reviewed nineteen series")
    ids = [spec.series_id for spec in specs]
    if len(ids) != len(set(ids)):
        raise ValueError("source series IDs must be unique")
    profiles = document.get("source_profiles")
    if not isinstance(profiles, list) or {row.get("source_id") for row in profiles} != {"bls-jolts", "bls-cps", "bls-ces", "bls-bed", "dol-ui-claims"}:
        raise ValueError("all five BLS/DOL source families require cadence-aware profiles")
    for profile in profiles:
        required = {"publisher", "cadence", "expected_release_policy", "grace_period_hours", "retry_policy", "revision_behavior", "schema", "rights_policy", "health_policy"}
        if not required.issubset(profile):
            raise ValueError("source profile is incomplete")
    for spec in specs:
        if spec.activation_state not in {"ACCEPTED_EXISTING", "SOURCE_ENABLED_PENDING_ACCEPTANCE"}:
            raise ValueError("invalid source activation state")
        if not spec.human_evidence_url.startswith("https://") or not spec.methodology_url.startswith("https://"):
            raise ValueError("evidence and methodology URLs must use HTTPS")
        if spec.source_id == "dol-ui-claims" and not spec.xml_path:
            raise ValueError("DOL series requires an explicit XML path")
        if spec.source_id != "dol-ui-claims" and spec.xml_path is not None:
            raise ValueError("only DOL series may declare an XML path")


def parse_bls_api_response(
    payload: bytes,
    specs: Iterable[LayoffsSeriesSpec],
    *,
    release_id: str,
    artifact_sha256: str,
    retrieved_time: str,
    accepted_time: str | None,
    provenance_url: str,
    official_publication_time: str | None = None,
) -> ParsedSourceBatch:
    selected = tuple(specs)
    if not selected or any(spec.source_id == "dol-ui-claims" for spec in selected):
        raise ValueError("BLS parser requires one or more BLS series specs")
    _validate_common_inputs(release_id, artifact_sha256, retrieved_time, accepted_time)
    public_time, publication_time_kind = _publication_time(official_publication_time, retrieved_time)
    try:
        document = json.loads(payload)
        if document["status"] != "REQUEST_SUCCEEDED":
            raise ValueError("BLS request did not succeed")
        series_rows = document["Results"]["series"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("BLS schema drift or malformed response") from exc
    if not isinstance(series_rows, list):
        raise ValueError("BLS response series must be a list")

    by_id = {spec.series_id: spec for spec in selected}
    seen: set[str] = set()
    observations: list[SourceObservationCandidate] = []
    skipped = 0
    for series in series_rows:
        if not isinstance(series, dict):
            raise ValueError("BLS series row must be an object")
        series_id = series.get("seriesID")
        if series_id not in by_id:
            raise ValueError("BLS response returned an unrequested series")
        if series_id in seen:
            raise ValueError("BLS response duplicated a requested series")
        seen.add(series_id)
        rows = series.get("data")
        if not isinstance(rows, list) or not rows:
            raise ValueError("BLS series has no observation rows")
        spec = by_id[series_id]
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("BLS observation row must be an object")
            raw_value = str(row.get("value", "")).strip()
            if raw_value in {"", "-"}:
                skipped += 1
                continue
            period = _bls_period(row, spec.frequency)
            try:
                value = Decimal(raw_value.replace(",", ""))
            except InvalidOperation as exc:
                raise ValueError("BLS observation value is not numeric") from exc
            footnotes = row.get("footnotes", [])
            if not isinstance(footnotes, list):
                raise ValueError("BLS footnotes must be a list")
            preliminary = any(isinstance(note, dict) and note.get("code") == "P" for note in footnotes)
            observations.append(
                _candidate(
                    spec,
                    release_id=release_id,
                    artifact_sha256=artifact_sha256,
                    value=value,
                    observation_period=period,
                    public_time=public_time,
                    retrieved_time=retrieved_time,
                    accepted_time=accepted_time,
                    publication_time_kind=publication_time_kind,
                    revision_status="preliminary" if preliminary else "as_published",
                    provenance_url=provenance_url,
                )
            )
    if seen != set(by_id):
        raise ValueError("BLS response omitted a requested series")
    if not observations:
        raise ValueError("BLS response contained no usable observations")
    observations.sort(key=lambda row: (row.source_series_id, row.observation_period), reverse=True)
    return ParsedSourceBatch(tuple(observations), skipped, release_id)


def parse_dol_national_xml(
    payload: bytes,
    specs: Iterable[LayoffsSeriesSpec],
    *,
    release_id: str,
    artifact_sha256: str,
    retrieved_time: str,
    accepted_time: str | None,
    provenance_url: str,
    official_publication_time: str | None = None,
) -> ParsedSourceBatch:
    selected = tuple(specs)
    if not selected or any(spec.source_id != "dol-ui-claims" for spec in selected):
        raise ValueError("DOL parser requires one or more DOL UI series specs")
    _validate_common_inputs(release_id, artifact_sha256, retrieved_time, accepted_time)
    public_time, publication_time_kind = _publication_time(official_publication_time, retrieved_time)
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("DOL XML is malformed") from exc
    run_date = root.attrib.get("rundate", "").strip()
    if root.tag != "r539cyNational" or not run_date:
        raise ValueError("DOL national XML schema marker is missing")
    try:
        datetime.strptime(run_date, "%m/%d/%Y")
    except ValueError as exc:
        raise ValueError("DOL run date is malformed") from exc

    observations: list[SourceObservationCandidate] = []
    skipped = 0
    for week in root.findall("week"):
        raw_week = (week.findtext("weekEnded") or "").strip()
        try:
            observation_period = datetime.strptime(raw_week, "%m/%d/%Y").date().isoformat()
        except ValueError as exc:
            raise ValueError("DOL week-ending date is malformed") from exc
        for spec in selected:
            raw_value = (week.findtext(spec.xml_path or "") or "").replace("\u00a0", "").strip()
            if not raw_value:
                skipped += 1
                continue
            try:
                value = Decimal(raw_value.replace(",", ""))
            except InvalidOperation as exc:
                raise ValueError("DOL observation value is not numeric") from exc
            observations.append(
                _candidate(
                    spec,
                    release_id=release_id,
                    artifact_sha256=artifact_sha256,
                    value=value,
                    observation_period=observation_period,
                    public_time=public_time,
                    retrieved_time=retrieved_time,
                    accepted_time=accepted_time,
                    publication_time_kind=publication_time_kind,
                    revision_status="advance_or_revised_as_published",
                    provenance_url=provenance_url,
                )
            )
    if not observations:
        raise ValueError("DOL XML contained no usable national observations")
    observed_ids = {row.source_series_id for row in observations}
    missing_series = {spec.series_id for spec in selected} - observed_ids
    if missing_series:
        raise ValueError(f"DOL XML omitted populated data for requested series: {sorted(missing_series)}")
    observations.sort(key=lambda row: (row.source_series_id, row.observation_period), reverse=True)
    return ParsedSourceBatch(tuple(observations), skipped, f"{release_id}|rundate={run_date}")


class BlsDolLayoffsCollector:
    """Bounded source retrieval; raw capture, acceptance, and publication remain caller-owned."""

    def __init__(self, acquisition: dict[str, Any], *, retriever: BoundedRetriever | None = None):
        self.acquisition = acquisition
        self.retriever = retriever or BoundedRetriever()

    def retrieve_bls(self, specs: Iterable[LayoffsSeriesSpec], start_year: int, end_year: int) -> RetrievedArtifact:
        selected = tuple(specs)
        if not selected or any(spec.source_id == "dol-ui-claims" for spec in selected):
            raise ValueError("BLS retrieval requires BLS specs only")
        config = self.acquisition["bls"]
        body = bls_request_body([spec.series_id for spec in selected], start_year, end_year)
        RequestBudget(max_per_day=25, max_per_10_seconds=50).record()
        return self.retriever.fetch(
            config["endpoint"],
            method="POST",
            body=body,
            headers={"Content-Type": "application/json"},
            expected_types=("application/json",),
        )

    def retrieve_dol(self, year: int) -> RetrievedArtifact:
        config = self.acquisition["dol_ui"]
        body = urllib.parse.urlencode(
            {"level": "us", "strtdate": str(year), "enddate": str(year), "filetype": "xml", "submit": "Submit"}
        ).encode("ascii")
        RequestBudget(max_per_day=24, max_per_10_seconds=2).record()
        return self.retriever.fetch(
            config["endpoint"],
            method="POST",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            expected_types=("text/xml", "application/xml"),
        )


def collect_layoffs_bls_dol_candidates(
    *,
    registry_path: Path,
    raw_root: Path,
    candidate_path: Path,
    start_year: int | None = None,
    end_year: int | None = None,
    collector: BlsDolLayoffsCollector | None = None,
) -> dict[str, Any]:
    """Retrieve and persist an internal review batch without accepting or publishing it."""

    acquisition, specs = load_layoffs_bls_dol_registry(registry_path)
    active_collector = collector or BlsDolLayoffsCollector(acquisition)
    now = datetime.now(timezone.utc)
    final_year = now.year if end_year is None else end_year
    first_year = final_year - 1 if start_year is None else start_year
    if first_year > final_year:
        raise ValueError("start year cannot follow end year")
    run_id = str(uuid.uuid4())
    raw_store = RawStore(raw_root)

    bls_specs = tuple(spec for spec in specs if spec.source_id != "dol-ui-claims")
    dol_specs = tuple(spec for spec in specs if spec.source_id == "dol-ui-claims")
    bls_artifact = active_collector.retrieve_bls(bls_specs, first_year, final_year)
    bls_release = f"bls-api-retrieval-{bls_artifact.retrieved_time}"
    bls_raw = raw_store.capture(
        source_id="bls-layoffs-combined",
        run_id=run_id,
        request_identity=bls_artifact.final_url,
        retrieved_time=bls_artifact.retrieved_time,
        release_id=bls_release,
        content_type=bls_artifact.content_type,
        body=bls_artifact.body,
        parser_version=acquisition["bls"]["parser_version"],
        rights_result="ALLOW",
    )
    bls_batch = parse_bls_api_response(
        bls_artifact.body,
        bls_specs,
        release_id=bls_release,
        artifact_sha256=bls_raw.sha256,
        retrieved_time=bls_artifact.retrieved_time,
        accepted_time=None,
        provenance_url=bls_artifact.final_url,
    )

    dol_artifact = active_collector.retrieve_dol(final_year)
    dol_release = f"dol-ui-xml-retrieval-{dol_artifact.retrieved_time}"
    dol_raw = raw_store.capture(
        source_id="dol-ui-claims",
        run_id=run_id,
        request_identity=dol_artifact.final_url,
        retrieved_time=dol_artifact.retrieved_time,
        release_id=dol_release,
        content_type=dol_artifact.content_type,
        body=dol_artifact.body,
        parser_version=acquisition["dol_ui"]["parser_version"],
        rights_result="ALLOW",
    )
    dol_batch = parse_dol_national_xml(
        dol_artifact.body,
        dol_specs,
        release_id=dol_release,
        artifact_sha256=dol_raw.sha256,
        retrieved_time=dol_artifact.retrieved_time,
        accepted_time=None,
        provenance_url=dol_artifact.final_url,
    )

    by_series = {spec.series_id: spec for spec in specs}
    candidates = []
    for observation in (*bls_batch.observations, *dol_batch.observations):
        row = asdict(observation)
        row["value"] = str(observation.value)
        row["activation_state"] = "SOURCE_ENABLED_PENDING_ACCEPTANCE"
        row["publication_eligible"] = False
        row["registry_state_before_retrieval"] = by_series[observation.source_series_id].activation_state
        candidates.append(row)
    artifact = {
        "schemaVersion": "layoffs-source-candidate-batch-1.0.0",
        "artifactClass": "internal_source_candidate_batch",
        "activationStatus": "NOT_ACCEPTED_NOT_PUBLISHABLE",
        "runId": run_id,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requestedYears": {"start": first_year, "end": final_year},
        "rawArtifacts": [asdict(bls_raw), asdict(dol_raw)],
        "sourceDiagnostics": {
            "blsSkippedMissingValues": bls_batch.skipped_missing_values,
            "dolSkippedMissingValues": dol_batch.skipped_missing_values,
        },
        "candidates": candidates,
    }
    serialized = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    lowered = serialized.lower()
    if any(secret in lowered for secret in ("registrationkey", "api_key", "authorization")):
        raise ValueError("secret-shaped field cannot enter the candidate artifact")
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = candidate_path.with_suffix(candidate_path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    os.replace(temporary, candidate_path)
    return artifact


def _bls_period(row: dict[str, Any], frequency: str) -> str:
    try:
        year = int(row["year"])
        raw_period = row["period"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("BLS observation period is malformed") from exc
    if frequency == "monthly" and raw_period in _MONTHS:
        month = _MONTHS[raw_period]
        date(year, month, 1)
        return f"{year:04d}-{month:02d}"
    if frequency == "quarterly" and raw_period in _QUARTERS:
        return f"{year:04d}-Q{_QUARTERS[raw_period]}"
    raise ValueError("BLS observation frequency and period do not match")


def _candidate(
    spec: LayoffsSeriesSpec,
    *,
    release_id: str,
    artifact_sha256: str,
    value: Decimal,
    observation_period: str,
    public_time: str,
    retrieved_time: str,
    accepted_time: str | None,
    publication_time_kind: str,
    revision_status: str,
    provenance_url: str,
) -> SourceObservationCandidate:
    identity = hashlib.sha256(
        f"{spec.series_id}|{release_id}|{observation_period}".encode("utf-8")
    ).hexdigest()
    return SourceObservationCandidate(
        observation_id=identity,
        canonical_factor=spec.canonical_factor,
        source_id=spec.source_id,
        source_series_id=spec.series_id,
        release_id=release_id,
        artifact_sha256=artifact_sha256,
        value=value,
        unit=spec.unit,
        frequency=spec.frequency,
        geography="US",
        seasonal_adjustment=spec.seasonal_adjustment,
        observation_period=observation_period,
        public_time=public_time,
        retrieved_time=retrieved_time,
        accepted_time=accepted_time,
        publication_time_kind=publication_time_kind,
        revision_status=revision_status,
        provenance_url=provenance_url,
        evidence_url=spec.human_evidence_url,
        methodology_url=spec.methodology_url,
    )


def _validate_common_inputs(release_id: str, artifact_sha256: str, retrieved_time: str, accepted_time: str | None) -> None:
    if not release_id.strip() or not _SHA256.fullmatch(artifact_sha256):
        raise ValueError("release identity and artifact hash are required")
    retrieved = _utc(retrieved_time)
    if accepted_time is not None:
        accepted = _utc(accepted_time)
        if accepted < retrieved:
            raise ValueError("acceptance time cannot precede retrieval time")


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed


def _publication_time(official_publication_time: str | None, retrieved_time: str) -> tuple[str, str]:
    if official_publication_time is None:
        return retrieved_time, "conservative_retrieval_bound"
    if _utc(official_publication_time) > _utc(retrieved_time):
        raise ValueError("official publication time cannot follow retrieval time")
    return official_publication_time, "official"
