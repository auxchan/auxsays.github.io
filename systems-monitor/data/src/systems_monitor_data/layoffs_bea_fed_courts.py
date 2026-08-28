from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping


_BEA_CREDENTIAL = "AUXSAYS_BEA_USER_ID"
_SOURCE_IDS = {
    "bea-nipa",
    "bea-gdp-industry",
    "fed-g17",
    "fed-h15",
    "fed-sloos",
    "uscourts-f2",
}
_ALLOWED_HOSTS = {
    "apps.bea.gov",
    "www.bea.gov",
    "www.federalreserve.gov",
    "www.uscourts.gov",
    "uscourts.gov",
}
_SECRET_QUERY_KEYS = {"userid", "user_id", "api_key", "apikey", "key", "token", "authorization"}
_HASH = re.compile(r"^[0-9a-f]{64}$")
_COURTS_PERIOD = re.compile(r"/(20\d{2})/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/")
_G17_RELEASE = re.compile(r"(?:release|released|updated)[^\n]{0,80}(20\d{2})", re.IGNORECASE)


@dataclass(frozen=True)
class OfficialRequest:
    source_id: str
    endpoint: str
    public_identity: str
    query: tuple[tuple[str, str], ...] = ()
    _credential: str | None = field(default=None, repr=False, compare=False)

    def transport_url(self) -> str:
        query = list(self.query)
        if self.source_id.startswith("bea-"):
            if not self._credential:
                raise RuntimeError("BEA transport requires a credential")
            query.append(("UserID", self._credential))
        return self.endpoint if not query else f"{self.endpoint}?{urllib.parse.urlencode(query)}"

    def __str__(self) -> str:
        return self.public_identity


@dataclass(frozen=True)
class SourceIntakePlan:
    source_id: str
    activation_state: str
    health_status: str
    reason: str | None
    request: OfficialRequest | None


@dataclass(frozen=True)
class ExternalObservationCandidate:
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
    relationship_boundary: str | None = None


def load_layoffs_bea_fed_courts_registry(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1.0.0":
        raise ValueError("unsupported BEA/Federal Reserve/Courts registry schema")
    if document.get("credential_environment_variables", {}).get("bea") != _BEA_CREDENTIAL:
        raise ValueError("BEA credential environment contract changed")
    sources = document.get("sources")
    if not isinstance(sources, list) or {source.get("source_id") for source in sources} != _SOURCE_IDS:
        raise ValueError("registry must contain the reviewed six official source products")
    for source in sources:
        _validate_source(source)
    return document


def official_source(document: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    for source in document["sources"]:
        if source["source_id"] == source_id:
            return source
    raise KeyError(source_id)


def plan_official_intake(
    document: Mapping[str, Any],
    source_id: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> SourceIntakePlan:
    source = official_source(document, source_id)
    selector_status = source["selector_status"]
    env = os.environ if environment is None else environment

    if source_id.startswith("bea-"):
        credential = env.get(_BEA_CREDENTIAL, "").strip()
        if not credential:
            return SourceIntakePlan(
                source_id,
                "SOURCE_IDENTIFIED",
                "blocked",
                f"credential_missing:{_BEA_CREDENTIAL}",
                None,
            )
        if not selector_status.startswith("VERIFIED_") or not source["series"]:
            return SourceIntakePlan(
                source_id,
                "SOURCE_IDENTIFIED",
                "blocked",
                "exact_table_line_or_crosswalk_unresolved",
                None,
            )
        query = _bea_query(source["series"][0])
        public_identity = f"{source['endpoint']}?{urllib.parse.urlencode(query)}"
        return SourceIntakePlan(
            source_id,
            "SOURCE_ENABLED_PENDING_ACCEPTANCE",
            "source_identified",
            None,
            OfficialRequest(source_id, source["endpoint"], public_identity, query, credential),
        )

    if source_id == "fed-g17":
        return SourceIntakePlan(
            source_id,
            "RAW_REVIEW_ONLY_PENDING_RIGHTS_AND_SELECTOR_ACCEPTANCE",
            "source_identified",
            source.get("blocked_reason"),
            OfficialRequest(source_id, source["endpoint"], source["endpoint"]),
        )
    if source_id == "uscourts-f2":
        return SourceIntakePlan(
            source_id,
            "RAW_REVIEW_ONLY_PENDING_RIGHTS_AND_SCHEMA_ACCEPTANCE",
            "source_identified",
            source.get("blocked_reason"),
            OfficialRequest(source_id, source["endpoint"], source["endpoint"]),
        )

    return SourceIntakePlan(
        source_id,
        "SOURCE_IDENTIFIED",
        "blocked",
        "exact_series_or_question_binding_unresolved",
        None,
    )


def parse_bea_api_response(
    payload: bytes,
    source: Mapping[str, Any],
    *,
    release_id: str,
    artifact_sha256: str,
    retrieved_time: str,
    provenance_url: str,
) -> tuple[ExternalObservationCandidate, ...]:
    """Parse only registry-approved BEA table/line selectors.

    The shipped registry deliberately has no approved BEA selectors yet. This
    parser is ready for the narrow table/line amendment without treating API
    discovery results as accepted observations.
    """

    _validate_batch(release_id, artifact_sha256, retrieved_time, provenance_url)
    series = source.get("series", [])
    if not source.get("selector_status", "").startswith("VERIFIED_") or not series:
        raise ValueError("BEA exact table/line selector is not verified")
    try:
        document = json.loads(payload)
        results = document["BEAAPI"]["Results"]
        if "Error" in results:
            raise ValueError("BEA API returned an error")
        rows = results["Data"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("BEA schema drift or malformed response") from exc
    if not isinstance(rows, list):
        raise ValueError("BEA data payload must be a list")

    candidates: list[ExternalObservationCandidate] = []
    matched: set[tuple[str, str]] = set()
    for spec in series:
        for row in rows:
            if str(row.get("TableName")) != spec["table_name"] or str(row.get("LineNumber")) != str(spec["line_number"]):
                continue
            period = str(row.get("TimePeriod", "")).strip()
            raw_value = str(row.get("DataValue", "")).replace(",", "").strip()
            if not period or raw_value in {"", "--", "(NA)"}:
                continue
            try:
                value = Decimal(raw_value)
            except InvalidOperation as exc:
                raise ValueError("BEA selected value is not numeric") from exc
            key = (spec["source_series_id"], period)
            if key in matched:
                raise ValueError("BEA response duplicated a selected series period")
            matched.add(key)
            candidates.append(
                _candidate(
                    source,
                    spec,
                    release_id,
                    artifact_sha256,
                    value,
                    period,
                    retrieved_time,
                    provenance_url,
                    frequency=spec["frequency"],
                    seasonal_adjustment=spec["seasonal_adjustment"],
                )
            )
    if not candidates:
        raise ValueError("BEA response contained no approved table/line observations")
    return tuple(sorted(candidates, key=lambda row: (row.source_series_id, row.observation_period), reverse=True))


def validate_g17_alltables_payload(payload: bytes) -> str:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = payload.decode("latin-1")
    normalized = " ".join(text.split()).lower()
    required = ("industrial production", "capacity utilization", "g.17")
    if not all(marker in normalized for marker in required):
        raise ValueError("G.17 all-tables schema marker is missing")
    release = _G17_RELEASE.search(text)
    return f"g17-raw-review|year={release.group(1) if release else 'unresolved'}"


def parse_fed_ddp_csv(
    payload: bytes,
    source: Mapping[str, Any],
    *,
    release_id: str,
    artifact_sha256: str,
    retrieved_time: str,
    provenance_url: str,
) -> tuple[ExternalObservationCandidate, ...]:
    _validate_batch(release_id, artifact_sha256, retrieved_time, provenance_url)
    series = source.get("series", [])
    if not source.get("selector_status", "").startswith("VERIFIED_") or not series:
        raise ValueError("Federal Reserve exact DDP series selection is not verified")
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        rows = list(reader)
    except UnicodeDecodeError as exc:
        raise ValueError("Federal Reserve DDP payload is not UTF-8 CSV") from exc
    if not reader.fieldnames:
        raise ValueError("Federal Reserve DDP CSV has no header")
    candidates: list[ExternalObservationCandidate] = []
    for spec in series:
        required = {spec["period_column"], spec["value_column"]}
        if not required.issubset(reader.fieldnames):
            raise ValueError("Federal Reserve DDP CSV omitted an approved column")
        for row in rows:
            period = str(row[spec["period_column"]]).strip()
            raw_value = str(row[spec["value_column"]]).strip()
            if not period or raw_value in {"", "ND", "NA"}:
                continue
            try:
                value = Decimal(raw_value)
            except InvalidOperation as exc:
                raise ValueError("Federal Reserve selected value is not numeric") from exc
            candidates.append(
                _candidate(
                    source,
                    spec,
                    release_id,
                    artifact_sha256,
                    value,
                    period,
                    retrieved_time,
                    provenance_url,
                    frequency=spec["frequency"],
                    seasonal_adjustment=spec["seasonal_adjustment"],
                )
            )
    if not candidates:
        raise ValueError("Federal Reserve DDP response contained no approved observations")
    return tuple(candidates)


def validate_sloos_payload(payload: bytes, source: Mapping[str, Any]) -> tuple[str, ...]:
    text = payload.decode("utf-8-sig", errors="strict")
    normalized = " ".join(text.split()).lower()
    if "senior loan officer opinion survey" not in normalized:
        raise ValueError("SLOOS release marker is missing")
    series = source.get("series", [])
    if not source.get("selector_status", "").startswith("VERIFIED_") or not series:
        raise ValueError("SLOOS question identifiers and respondent universes are not verified")
    missing = [spec["question_id"] for spec in series if spec["question_id"] not in text]
    if missing:
        raise ValueError(f"SLOOS payload omitted approved question identifiers: {missing}")
    return tuple(spec["question_id"] for spec in series)


def discover_courts_f2_xlsx_url(page_payload: bytes, dated_page_url: str) -> str:
    _validate_url(dated_page_url)
    parser = _LinkCollector()
    try:
        parser.feed(page_payload.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValueError("U.S. Courts F-2 page is not UTF-8 HTML") from exc
    candidates: list[str] = []
    for href, label in parser.links:
        absolute = urllib.parse.urljoin(dated_page_url, href)
        clean = absolute.split("#", 1)[0]
        if urllib.parse.urlsplit(clean).path.lower().endswith(".xlsx") and ("f-2" in label.lower() or "f-2" in clean.lower() or "f2" in clean.lower()):
            _validate_url(clean)
            candidates.append(clean)
    unique = sorted(set(candidates))
    if len(unique) != 1:
        raise ValueError(f"expected one official F-2 XLSX link, found {len(unique)}")
    return unique[0]


def parse_courts_f2_xlsx(
    payload: bytes,
    source: Mapping[str, Any],
    *,
    release_id: str,
    artifact_sha256: str,
    retrieved_time: str,
    dated_page_url: str,
) -> tuple[ExternalObservationCandidate, ...]:
    _validate_batch(release_id, artifact_sha256, retrieved_time, dated_page_url)
    if source.get("source_id") != "uscourts-f2" or not source.get("series"):
        raise ValueError("U.S. Courts F-2 registry binding is missing")
    period_match = _COURTS_PERIOD.search(dated_page_url)
    if not period_match:
        raise ValueError("dated F-2 page URL does not encode the reporting date")
    observation_period = "-".join(period_match.groups())
    rows = _xlsx_rows(payload)
    header_index, headers = _find_f2_headers(rows)
    total_row = _find_national_total(rows[header_index + 1 :])

    candidates: list[ExternalObservationCandidate] = []
    for spec in source["series"]:
        column = _find_business_column(headers, spec["chapter_header"])
        raw_value = total_row[column] if column < len(total_row) else ""
        try:
            value = Decimal(str(raw_value).replace(",", "").strip())
        except InvalidOperation as exc:
            raise ValueError(f"F-2 {spec['chapter_header']} total is not numeric") from exc
        if value < 0 or value != value.to_integral_value():
            raise ValueError("F-2 filing counts must be nonnegative integers")
        candidates.append(
            _candidate(
                source,
                spec,
                release_id,
                artifact_sha256,
                value,
                observation_period,
                retrieved_time,
                dated_page_url,
                frequency="quarterly rolling 12 months",
                seasonal_adjustment="not seasonally adjusted",
                relationship_boundary=source["relationship_boundary"],
            )
        )
    return tuple(candidates)


def _bea_query(spec: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return (
        ("method", "GetData"),
        ("datasetname", spec["dataset_name"]),
        ("TableName", spec["table_name"]),
        ("Frequency", spec["frequency_code"]),
        ("Year", spec.get("year", "X")),
        ("ResultFormat", "JSON"),
    )


def _candidate(
    source: Mapping[str, Any],
    spec: Mapping[str, Any],
    release_id: str,
    artifact_sha256: str,
    value: Decimal,
    observation_period: str,
    retrieved_time: str,
    provenance_url: str,
    *,
    frequency: str,
    seasonal_adjustment: str,
    relationship_boundary: str | None = None,
) -> ExternalObservationCandidate:
    identity = hashlib.sha256(
        f"{spec['source_series_id']}|{release_id}|{observation_period}".encode("utf-8")
    ).hexdigest()
    return ExternalObservationCandidate(
        observation_id=identity,
        canonical_factor=spec["canonical_factor"],
        source_id=source["source_id"],
        source_series_id=spec["source_series_id"],
        release_id=release_id,
        artifact_sha256=artifact_sha256,
        value=value,
        unit=spec["unit"],
        frequency=frequency,
        geography="US",
        seasonal_adjustment=seasonal_adjustment,
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
        relationship_boundary=relationship_boundary,
    )


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._label: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._label = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._label.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._label)))
            self._href = None
            self._label = []


def _xlsx_rows(payload: bytes) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValueError("U.S. Courts workbook is not a valid XLSX archive") from exc
    with archive:
        names = set(archive.namelist())
        sheets = sorted(name for name in names if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
        if not sheets:
            raise ValueError("U.S. Courts workbook has no worksheet XML")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.itertext()) for node in root.findall("{*}si")]
        rows: list[list[str]] = []
        for sheet in sheets:
            root = ET.fromstring(archive.read(sheet))
            for row in root.findall(".//{*}row"):
                cells: dict[int, str] = {}
                for cell in row.findall("{*}c"):
                    ref = cell.attrib.get("r", "")
                    column = _column_number(ref)
                    kind = cell.attrib.get("t")
                    if kind == "inlineStr":
                        value = "".join(cell.find("{*}is").itertext()) if cell.find("{*}is") is not None else ""
                    else:
                        raw = cell.findtext("{*}v", default="")
                        if kind == "s" and raw:
                            try:
                                value = shared[int(raw)]
                            except (IndexError, ValueError) as exc:
                                raise ValueError("U.S. Courts XLSX shared-string index is invalid") from exc
                        else:
                            value = raw
                    cells[column] = value.strip()
                if cells:
                    width = max(cells) + 1
                    rows.append([cells.get(index, "") for index in range(width)])
        if not rows:
            raise ValueError("U.S. Courts workbook contained no worksheet rows")
        return rows


def _column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        raise ValueError("XLSX cell reference is malformed")
    number = 0
    for character in letters.group(0):
        number = number * 26 + ord(character) - 64
    return number - 1


def _find_f2_headers(rows: list[list[str]]) -> tuple[int, list[str]]:
    for index in range(len(rows) - 1):
        first = [value.strip() for value in rows[index]]
        second = [value.strip() for value in rows[index + 1]]
        if any(value.lower() == "business" for value in first) and any("chapter 7" in value.lower() for value in second):
            width = max(len(first), len(second))
            group = ""
            headers = []
            for column in range(width):
                top = first[column] if column < len(first) else ""
                bottom = second[column] if column < len(second) else ""
                if top:
                    group = top
                headers.append(" ".join(part for part in (group, bottom) if part).strip())
            return index + 1, headers
    raise ValueError("U.S. Courts F-2 business/chapter header schema was not found")


def _find_national_total(rows: list[list[str]]) -> list[str]:
    for row in rows:
        jurisdiction_cells = [value.strip().lower() for value in row[:3]]
        if any(value in {"total", "united states", "total united states", "u.s. total"} for value in jurisdiction_cells):
            return row
    raise ValueError("U.S. Courts F-2 national total row was not found")


def _find_business_column(headers: list[str], chapter: str) -> int:
    target = f"business {chapter}".lower()
    matches = [index for index, header in enumerate(headers) if "nonbusiness" not in header.lower() and target in header.lower()]
    if len(matches) != 1:
        raise ValueError(f"U.S. Courts F-2 expected one Business {chapter} column")
    return matches[0]


def _validate_source(source: Mapping[str, Any]) -> None:
    required = {
        "source_id",
        "publisher",
        "product",
        "endpoint",
        "evidence_url",
        "methodology_url",
        "cadence",
        "expected_release_policy",
        "grace_period_hours",
        "revision_behavior",
        "rights_policy",
        "selector_status",
        "extraction_mode",
        "series",
    }
    if not required.issubset(source):
        raise ValueError("official source profile is incomplete")
    for field_name in ("endpoint", "evidence_url", "methodology_url"):
        _validate_url(str(source[field_name]))
    series = source["series"]
    if not isinstance(series, list):
        raise ValueError("source series must be a list")
    ids = [row["source_series_id"] for row in series]
    if len(ids) != len(set(ids)):
        raise ValueError("source series IDs must be unique")
    if source["selector_status"].startswith("VERIFIED_") and not series:
        raise ValueError("verified selectors require exact source series")
    if source["selector_status"].startswith("UNRESOLVED_") and series:
        raise ValueError("unresolved selectors cannot emit source series")


def _validate_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if (
        parts.scheme != "https"
        or (parts.hostname or "").lower() not in _ALLOWED_HOSTS
        or parts.port not in (None, 443)
        or parts.username
        or parts.password
    ):
        raise ValueError("official source URL is outside the reviewed host boundary")


def _validate_batch(release_id: str, artifact_sha256: str, retrieved_time: str, provenance_url: str) -> None:
    if not release_id.strip() or not _HASH.fullmatch(artifact_sha256):
        raise ValueError("release identity and artifact hash are required")
    try:
        instant = datetime.fromisoformat(retrieved_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("retrieval time must be ISO-8601") from exc
    if instant.tzinfo is None:
        raise ValueError("retrieval time must be timezone-aware")
    _validate_url(provenance_url)
    query_keys = {key.lower() for key, _ in urllib.parse.parse_qsl(urllib.parse.urlsplit(provenance_url).query)}
    if query_keys & _SECRET_QUERY_KEYS:
        raise ValueError("persisted provenance URL cannot contain credential parameters")
