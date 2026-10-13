from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
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
    source_report_run_date: str | None = None


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def load_layoffs_bls_dol_registry(path: Path) -> tuple[dict[str, Any], tuple[LayoffsSeriesSpec, ...]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    specs = tuple(LayoffsSeriesSpec(**row) for row in document["series"])
    _validate_registry(document, specs)
    return document["acquisition"], specs


def _validate_registry(document: dict[str, Any], specs: tuple[LayoffsSeriesSpec, ...]) -> None:
    if document.get("schema_version") != "1.0.0" or len(specs) != 20:
        raise ValueError("layoffs BLS/DOL registry must contain the reviewed twenty series")
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

    report_run_date = datetime.strptime(run_date, "%m/%d/%Y").date().isoformat()
    provisional_snapshot_id = "DOL-UI-r539cyNational-structured-snapshot"
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
                    release_id=provisional_snapshot_id,
                    artifact_sha256=artifact_sha256,
                    value=value,
                    observation_period=observation_period,
                    public_time=public_time,
                    retrieved_time=retrieved_time,
                    accepted_time=accepted_time,
                    publication_time_kind=publication_time_kind,
                    revision_status="as_published",
                    provenance_url=provenance_url,
                )
            )
    if not observations:
        raise ValueError("DOL XML contained no usable national observations")
    observed_ids = {row.source_series_id for row in observations}
    missing_series = {spec.series_id for spec in selected} - observed_ids
    if missing_series:
        raise ValueError(f"DOL XML omitted populated data for requested series: {sorted(missing_series)}")
    source_release_id = _dol_structured_snapshot_id(observations)
    observations = [
        replace(
            row,
            observation_id=_candidate_identity(
                row.source_series_id,
                _dol_structured_observation_id(row),
                row.observation_period,
            ),
            release_id=_dol_structured_observation_id(row),
            revision_status="current_revised_snapshot",
        )
        for row in observations
    ]
    observations.sort(key=lambda row: (row.source_series_id, row.observation_period), reverse=True)
    return ParsedSourceBatch(tuple(observations), skipped, source_release_id, report_run_date)


def parse_dol_official_release_html(
    payload: bytes,
    spec: LayoffsSeriesSpec,
    *,
    artifact_sha256: str,
    retrieved_time: str,
    provenance_url: str,
) -> ParsedSourceBatch:
    """Parse the bounded claims facts in an official USDOL distribution release.

    This is a deterministic text-layer parser. It intentionally recognizes only
    the seasonally adjusted initial-claims sentence and its explicit prior-week
    revision sentence; everything else in the release is ignored.
    """

    if spec.source_id != "dol-ui-claims" or spec.series_id != "DOL-UI-SA-INITIAL":
        raise ValueError("official DOL release fallback is bounded to seasonally adjusted initial claims")
    _validate_common_inputs("official-dol-release", artifact_sha256, retrieved_time, None)
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("official DOL release is not UTF-8 text") from exc
    parser = _VisibleTextParser()
    parser.feed(decoded)
    text = re.sub(r"\s+", " ", " ".join(parser.parts))
    if "United States Department of Labor" not in text or "Unemployment Insurance Weekly Claims Report" not in text:
        raise ValueError("official DOL release identity context is missing")
    publication_matches = re.findall(
        r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\s+(AM|PM)\s+(EDT|EST)",
        text,
    )
    if not publication_matches:
        raise ValueError("official DOL release publication time is missing")
    raw_date, raw_clock, meridiem, zone = publication_matches[-1]
    local = datetime.strptime(f"{raw_date} {raw_clock} {meridiem}", "%m/%d/%Y %I:%M %p")
    offset = timezone(timedelta(hours=-4 if zone == "EDT" else -5))
    published = local.replace(tzinfo=offset).astimezone(timezone.utc)
    publication_time = published.isoformat().replace("+00:00", "Z")
    if published > _utc(retrieved_time):
        raise ValueError("official DOL release publication time follows retrieval")

    advance = re.search(
        r"In the week ending ([A-Z][a-z]+ \d{1,2}), the advance figure for seasonally adjusted initial claims was ([\d,]+)",
        text,
    )
    if not advance:
        raise ValueError("official DOL release initial-claims sentence is missing")
    raw_period, raw_value = advance.groups()
    period = datetime.strptime(f"{raw_period} {published.year}", "%B %d %Y").date()
    if period > published.date() and (period - published.date()).days > 180:
        period = period.replace(year=period.year - 1)

    values: list[tuple[date, Decimal, str]] = [
        (period, Decimal(raw_value.replace(",", "")), "official_release_advance")
    ]
    revised = re.search(
        r"The previous week's level was revised (?:up|down) by [\d,]+ from [\d,]+ to ([\d,]+)",
        text,
    )
    if revised:
        values.append((period - timedelta(days=7), Decimal(revised.group(1).replace(",", "")), "official_release_revised"))

    observations = []
    for observation_period, value, revision_status in values:
        provisional = _candidate(
            spec,
            release_id="official-dol-release",
            artifact_sha256=artifact_sha256,
            value=value,
            observation_period=observation_period.isoformat(),
            public_time=publication_time,
            retrieved_time=retrieved_time,
            accepted_time=None,
            publication_time_kind="official",
            revision_status=revision_status,
            provenance_url=provenance_url,
        )
        semantic_release_id = _dol_structured_observation_id(provisional)
        observations.append(replace(
            provisional,
            observation_id=_candidate_identity(spec.series_id, semantic_release_id, observation_period.isoformat()),
            release_id=semantic_release_id,
        ))
    marker_digest = hashlib.sha256(
        "\n".join(f"{row.observation_period}|{row.value}" for row in observations).encode("utf-8")
    ).hexdigest()[:16]
    marker = f"DOL-UI-official-release-{published.date().isoformat()}-{marker_digest}"
    return ParsedSourceBatch(tuple(observations), 0, marker, published.date().isoformat())


def dol_source_freshness(
    observations: Iterable[SourceObservationCandidate],
    *,
    retrieved_time: str,
    stale_after_hours: int,
) -> dict[str, Any]:
    selected = tuple(row for row in observations if row.source_id == "dol-ui-claims")
    if not selected:
        raise ValueError("DOL freshness requires DOL observations")
    newest_period = max(row.observation_period for row in selected)
    newest_time = datetime.combine(date.fromisoformat(newest_period), datetime.min.time(), tzinfo=timezone.utc)
    age_hours = (_utc(retrieved_time) - newest_time).total_seconds() / 3600
    if age_hours < 0:
        raise ValueError("DOL newest observation cannot follow retrieval")
    return {
        "status": "CURRENT" if age_hours <= stale_after_hours else "STALE",
        "newestObservationPeriod": newest_period,
        "retrievedTime": retrieved_time,
        "observationAgeHours": round(age_hours, 3),
        "staleAfterHours": stale_after_hours,
    }


def repair_dol_candidate_batch(
    batch: dict[str, Any],
    *,
    registry_path: Path,
    raw_root: Path,
) -> dict[str, Any]:
    """Reparse the declared DOL evidence using source-stable release identity.

    The repair is deterministic and acceptance-neutral. It never changes a BLS
    candidate and it does not turn a candidate into accepted evidence.
    """

    if batch.get("activationStatus") != "NOT_ACCEPTED_NOT_PUBLISHABLE":
        raise ValueError("DOL repair requires a non-publishable candidate batch")
    acquisition, specs = load_layoffs_bls_dol_registry(registry_path)
    dol_specs = tuple(spec for spec in specs if spec.source_id == "dol-ui-claims")
    diagnostics = dict(batch.get("sourceDiagnostics", {}))
    fallback_current = (
        diagnostics.get("dolAcquisitionMethods", {})
        .get("officialReleaseFallback", {})
        .get("status") == "CURRENT"
    )
    raw_rows = [
        row for row in batch.get("rawArtifacts", [])
        if row.get("source_id") == "dol-ui-claims"
        and row.get("parser_version") == acquisition["dol_ui"]["parser_version"]
    ]
    if not raw_rows and fallback_current:
        return batch
    if len(raw_rows) != 1:
        raise ValueError("DOL repair requires exactly one declared raw artifact")
    raw = raw_rows[0]
    raw_path = raw_root / raw["relative_path"]
    payload = raw_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != raw.get("sha256"):
        raise ValueError("DOL raw artifact hash does not match its declaration")
    parsed = parse_dol_national_xml(
        payload,
        dol_specs,
        release_id=raw["release_id"],
        artifact_sha256=raw["sha256"],
        retrieved_time=raw["retrieved_time"],
        accepted_time=None,
        provenance_url=raw["request_identity"],
    )
    repaired_rows: list[dict[str, Any]] = []
    by_series = {spec.series_id: spec for spec in dol_specs}
    for observation in parsed.observations:
        row = asdict(observation)
        row["value"] = str(observation.value)
        row["activation_state"] = "SOURCE_ENABLED_PENDING_ACCEPTANCE"
        row["publication_eligible"] = False
        row["registry_state_before_retrieval"] = by_series[observation.source_series_id].activation_state
        row["acquisition_method"] = "dol_r539cyNational_xml_primary"
        repaired_rows.append(row)
    freshness = dol_source_freshness(
        parsed.observations,
        retrieved_time=raw["retrieved_time"],
        stale_after_hours=int(acquisition["dol_ui"].get("stale_after_hours", 336)),
    )
    if fallback_current:
        repaired_rows = [row for row in repaired_rows if row["source_series_id"] != "DOL-UI-SA-INITIAL"]
    preserved_rows = [
        row for row in batch.get("candidates", [])
        if row.get("source_id") != "dol-ui-claims"
        or row.get("acquisition_method") == "dol_official_release_fallback"
    ]
    diagnostics.update({
        "dolSkippedMissingValues": parsed.skipped_missing_values,
        "dolReportRunDate": parsed.source_report_run_date,
        "dolPrimaryFreshness": freshness,
    })
    if not fallback_current:
        diagnostics.update({
            "dolSourceReleaseMarker": parsed.source_release_marker,
            "dolFreshness": freshness,
        })
    repaired = dict(batch)
    repaired["sourceDiagnostics"] = diagnostics
    repaired["candidates"] = preserved_rows + repaired_rows
    return repaired


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

    def retrieve_dol_official_release(self, url: str | None = None) -> RetrievedArtifact:
        config = self.acquisition["dol_ui"]
        target = url or config["official_release_url"]
        RequestBudget(max_per_day=24, max_per_10_seconds=2).record()
        return self.retriever.fetch(target, expected_types=("text/html",))


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

    stale_after_hours = int(acquisition["dol_ui"].get("stale_after_hours", 336))
    raw_artifacts = [asdict(bls_raw)]
    acquisition_method_by_hash = {bls_raw.sha256: "bls_api_primary"}
    selected_dol_observations: tuple[CandidateObservation, ...] = ()
    selected_dol_marker: str | None = None
    dol_report_run_date: str | None = None
    dol_skipped_missing_values = 0
    try:
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
        primary_freshness = dol_source_freshness(
            dol_batch.observations,
            retrieved_time=dol_artifact.retrieved_time,
            stale_after_hours=stale_after_hours,
        )
        selected_dol_observations = tuple(dol_batch.observations)
        selected_dol_marker = dol_batch.source_release_marker
        dol_report_run_date = dol_batch.source_report_run_date
        dol_skipped_missing_values = dol_batch.skipped_missing_values
        raw_artifacts.append(asdict(dol_raw))
        acquisition_method_by_hash[dol_raw.sha256] = "dol_r539cyNational_xml_primary"
        primary_health = {
            "status": primary_freshness["status"],
            "url": dol_artifact.final_url,
            "releaseIdentity": dol_batch.source_release_marker,
            "rawSha256": dol_raw.sha256,
            "retrievedTime": dol_artifact.retrieved_time,
            "parserVersion": acquisition["dol_ui"]["parser_version"],
            "newestObservationPeriod": primary_freshness["newestObservationPeriod"],
        }
    except (RuntimeError, ValueError) as exc:
        primary_freshness = {
            "status": "BROKEN",
            "newestObservationPeriod": None,
            "staleAfterHours": stale_after_hours,
        }
        primary_health = {
            "status": "BROKEN",
            "url": acquisition["dol_ui"]["endpoint"],
            "errorClass": type(exc).__name__,
            "parserVersion": acquisition["dol_ui"]["parser_version"],
            "newestObservationPeriod": None,
        }
    method_health: dict[str, dict[str, Any]] = {
        "primaryXml": primary_health,
        "officialReleaseFallback": {"status": "NOT_TRIGGERED"},
        "officialArchive": {"status": "NOT_NEEDED"},
    }
    overall_status = "SUCCESS" if primary_freshness["status"] == "CURRENT" else "PARTIAL"
    selected_freshness = primary_freshness
    if primary_freshness["status"] in {"STALE", "PARTIAL", "BLOCKED", "BROKEN", "LOW_CONFIDENCE"}:
        try:
            fallback_artifact = active_collector.retrieve_dol_official_release()
            fallback_release = f"dol-ui-official-release-retrieval-{fallback_artifact.retrieved_time}"
            fallback_raw = raw_store.capture(
                source_id="dol-ui-claims",
                run_id=run_id,
                request_identity=fallback_artifact.final_url,
                retrieved_time=fallback_artifact.retrieved_time,
                release_id=fallback_release,
                content_type=fallback_artifact.content_type,
                body=fallback_artifact.body,
                parser_version=acquisition["dol_ui"]["official_release_parser_version"],
                rights_result="ALLOW",
            )
            initial_spec = next(spec for spec in dol_specs if spec.series_id == "DOL-UI-SA-INITIAL")
            fallback_batch = parse_dol_official_release_html(
                fallback_artifact.body,
                initial_spec,
                artifact_sha256=fallback_raw.sha256,
                retrieved_time=fallback_artifact.retrieved_time,
                provenance_url=fallback_artifact.final_url,
            )
            fallback_freshness = dol_source_freshness(
                fallback_batch.observations,
                retrieved_time=fallback_artifact.retrieved_time,
                stale_after_hours=stale_after_hours,
            )
            if fallback_freshness["status"] != "CURRENT":
                raise ValueError("official DOL release fallback is not current")
            selected_dol_observations = tuple(
                row for row in selected_dol_observations if row.source_series_id != "DOL-UI-SA-INITIAL"
            ) + fallback_batch.observations
            selected_dol_marker = fallback_batch.source_release_marker
            selected_freshness = fallback_freshness
            raw_artifacts.append(asdict(fallback_raw))
            acquisition_method_by_hash[fallback_raw.sha256] = "dol_official_release_fallback"
            method_health["officialReleaseFallback"] = {
                "status": "CURRENT",
                "url": fallback_artifact.final_url,
                "releaseIdentity": fallback_batch.source_release_marker,
                "rawSha256": fallback_raw.sha256,
                "publicationTime": fallback_batch.observations[0].public_time,
                "retrievedTime": fallback_artifact.retrieved_time,
                "parserVersion": acquisition["dol_ui"]["official_release_parser_version"],
                "newestObservationPeriod": fallback_freshness["newestObservationPeriod"],
            }
            overall_status = f"SUCCESS_WITH_PRIMARY_{primary_freshness['status']}"
        except (RuntimeError, ValueError) as exc:
            method_health["officialReleaseFallback"] = {
                "status": "BROKEN",
                "errorClass": type(exc).__name__,
                "url": acquisition["dol_ui"]["official_release_url"],
            }

    by_series = {spec.series_id: spec for spec in specs}
    candidates = []
    for observation in (*bls_batch.observations, *selected_dol_observations):
        row = asdict(observation)
        row["value"] = str(observation.value)
        row["activation_state"] = "SOURCE_ENABLED_PENDING_ACCEPTANCE"
        row["publication_eligible"] = False
        row["registry_state_before_retrieval"] = by_series[observation.source_series_id].activation_state
        row["acquisition_method"] = acquisition_method_by_hash[observation.artifact_sha256]
        candidates.append(row)
    artifact = {
        "schemaVersion": "layoffs-source-candidate-batch-1.0.0",
        "artifactClass": "internal_source_candidate_batch",
        "activationStatus": "NOT_ACCEPTED_NOT_PUBLISHABLE",
        "runId": run_id,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requestedYears": {"start": first_year, "end": final_year},
        "rawArtifacts": raw_artifacts,
        "sourceDiagnostics": {
            "blsSkippedMissingValues": bls_batch.skipped_missing_values,
            "dolSkippedMissingValues": dol_skipped_missing_values,
            "dolSourceReleaseMarker": selected_dol_marker,
            "dolReportRunDate": dol_report_run_date,
            "dolPrimaryFreshness": primary_freshness,
            "dolFreshness": selected_freshness,
            "dolAcquisitionOverallStatus": overall_status,
            "dolAcquisitionMethods": method_health,
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
    identity = _candidate_identity(spec.series_id, release_id, observation_period)
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


def _candidate_identity(series_id: str, release_id: str, observation_period: str) -> str:
    return hashlib.sha256(f"{series_id}|{release_id}|{observation_period}".encode("utf-8")).hexdigest()


def _dol_structured_snapshot_id(observations: Iterable[SourceObservationCandidate]) -> str:
    """Identify r539cy data content without treating daily report execution as a release.

    DOL's ``rundate`` changes when the report is executed even when the populated
    weekly observations do not. A canonical content identity prevents unchanged
    daily retrievals from manufacturing false releases or revisions.
    """

    selected = tuple(observations)
    if not selected:
        raise ValueError("DOL structured snapshot identity requires observations")
    newest_period = max(row.observation_period for row in selected)
    canonical = "\n".join(
        f"{row.source_series_id}|{row.observation_period}|{row.value}"
        for row in sorted(selected, key=lambda item: (item.source_series_id, item.observation_period))
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"DOL-UI-r539cyNational-data-through-{newest_period}-{digest}"


def _dol_structured_observation_id(observation: SourceObservationCandidate) -> str:
    semantic = f"{observation.source_series_id}|{observation.observation_period}|{observation.value}"
    digest = hashlib.sha256(semantic.encode("utf-8")).hexdigest()[:16]
    return f"DOL-UI-r539cyNational-observation-{observation.observation_period}-{digest}"


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
