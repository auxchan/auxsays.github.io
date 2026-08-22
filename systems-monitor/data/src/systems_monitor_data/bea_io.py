from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import deque
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import time
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit, urlunsplit


BEA_API_ENDPOINT = "https://apps.bea.gov/api/data"
BEA_DATASET = "InputOutput"
BEA_ATTRIBUTION = (
    "This product uses the Bureau of Economic Analysis (BEA) Data API "
    "but is not endorsed or certified by BEA."
)
PARAMETER_METHOD = "GetParameterValues"
SECRET_QUERY_KEYS = {"userid", "user_id", "api_key", "key", "token"}
SAFE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")


class BeaApiError(ValueError):
    pass


class BeaRequestBudget:
    """In-process guard for BEA's published per-minute request/byte/error limits."""

    def __init__(self, *, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._requests: deque[float] = deque()
        self._bytes: deque[tuple[float, int]] = deque()
        self._errors: deque[float] = deque()

    def _prune(self, now: float) -> None:
        while self._requests and self._requests[0] <= now - 60:
            self._requests.popleft()
        while self._bytes and self._bytes[0][0] <= now - 60:
            self._bytes.popleft()
        while self._errors and self._errors[0] <= now - 60:
            self._errors.popleft()

    def begin_request(self) -> None:
        now = self._clock(); self._prune(now)
        if len(self._requests) >= 100:
            raise BeaApiError("BEA request-per-minute budget exhausted")
        self._requests.append(now)

    def record_result(self, byte_length: int, *, failed: bool = False) -> None:
        now = self._clock(); self._prune(now)
        if byte_length < 0:
            raise BeaApiError("BEA response byte count is invalid")
        if sum(size for _, size in self._bytes) + byte_length > 100 * 1024 * 1024:
            raise BeaApiError("BEA megabyte-per-minute budget exhausted")
        self._bytes.append((now, byte_length))
        if failed:
            if len(self._errors) >= 30:
                raise BeaApiError("BEA error-per-minute budget exhausted")
            self._errors.append(now)


@dataclass(frozen=True)
class BeaParameterValue:
    key: str
    description: str


@dataclass(frozen=True)
class BeaCell:
    row_code: str
    row_label: str
    column_code: str
    column_label: str
    value: str
    year: str
    table_id: str
    unit: str
    row_namespace: str = "COMMODITY"
    column_namespace: str = "INDUSTRY"

    @property
    def identity(self) -> str:
        core = f"{self.table_id}|{self.year}|{self.row_namespace}:{self.row_code}|{self.column_namespace}:{self.column_code}"
        return "bea-cell:" + hashlib.sha256(core.encode("utf-8")).hexdigest()

    def as_record(self) -> dict[str, Any]:
        return {**asdict(self), "cell_identity": self.identity}


def validate_user_id(user_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9-]{36}", user_id or ""):
        raise BeaApiError("BEA UserID must be supplied externally as 36 safe characters")


def redact_bea_url(url: str) -> str:
    parts = urlsplit(url)
    query = []
    for pair in parts.query.split("&"):
        if not pair:
            continue
        key = pair.split("=", 1)[0].lower()
        query.append(f"{pair.split('=', 1)[0]}=REDACTED" if key in SECRET_QUERY_KEYS else pair)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(query), parts.fragment))


def _results(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        results = payload["BEAAPI"]["Results"]
    except (KeyError, TypeError) as error:
        raise BeaApiError("BEA response envelope is invalid") from error
    if not isinstance(results, dict):
        raise BeaApiError("BEA response results must be an object")
    error_rows = results.get("Error")
    if error_rows:
        raise BeaApiError("BEA returned an API error")
    return results


def parse_parameter_values(body: bytes, *, max_values: int = 2_000) -> list[BeaParameterValue]:
    if len(body) > 2_000_000:
        raise BeaApiError("BEA metadata response exceeds size bound")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BeaApiError("BEA metadata is not valid JSON") from error
    results = _results(payload)
    rows = results.get("ParamValue") or results.get("ParameterValues")
    if not isinstance(rows, list) or not 1 <= len(rows) <= max_values:
        raise BeaApiError("BEA parameter values are absent or exceed the bound")
    values = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise BeaApiError("BEA parameter value must be an object")
        key = str(row.get("Key") or row.get("key") or "").strip()
        description = str(row.get("Desc") or row.get("Description") or "").strip()
        if not key or not description or len(key) > 64 or len(description) > 500:
            raise BeaApiError("BEA parameter value is incomplete")
        if key in seen:
            raise BeaApiError("BEA parameter values contain a duplicate key")
        seen.add(key)
        values.append(BeaParameterValue(key, description))
    return values


def resolve_table_id(values: list[BeaParameterValue], required_title_terms: tuple[str, ...]) -> BeaParameterValue:
    terms = tuple(term.casefold() for term in required_title_terms)
    matches = [row for row in values if all(term in row.description.casefold() for term in terms)]
    if len(matches) != 1:
        raise BeaApiError("current BEA TableID could not be resolved uniquely from live metadata")
    if not matches[0].key.isdigit():
        raise BeaApiError("live BEA TableID is not an integer")
    return matches[0]


def resolve_year(values: list[BeaParameterValue], year: str) -> BeaParameterValue:
    matches = [row for row in values if row.key == year]
    if len(matches) != 1:
        raise BeaApiError("required BEA year is not available in live metadata")
    return matches[0]


def parse_input_output_data(
    body: bytes,
    *,
    expected_table_id: str,
    expected_year: str,
    expected_unit: str,
    max_rows: int = 20_000,
) -> list[BeaCell]:
    if not expected_table_id.isdigit() or not re.fullmatch(r"\d{4}", expected_year):
        raise BeaApiError("expected live table/year identity is invalid")
    if len(body) > 25_000_000:
        raise BeaApiError("BEA data response exceeds size bound")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BeaApiError("BEA data is not valid JSON") from error
    rows = _results(payload).get("Data")
    if not isinstance(rows, list) or not 1 <= len(rows) <= max_rows:
        raise BeaApiError("BEA data rows are absent or exceed the bound")
    cells = []
    identities = set()
    for row in rows:
        if not isinstance(row, dict):
            raise BeaApiError("BEA data row must be an object")
        row_code = str(row.get("RowCode") or "").strip()
        column_code = str(row.get("ColCode") or row.get("ColumnCode") or "").strip()
        row_label = str(row.get("RowDescr") or row.get("RowDescription") or "").strip()
        column_label = str(row.get("ColDescr") or row.get("ColumnDescription") or "").strip()
        table_id = str(row.get("TableID") or expected_table_id).strip()
        year = str(row.get("Year") or expected_year).strip()
        unit = str(row.get("Unit") or expected_unit).strip()
        raw_value = row.get("DataValue")
        if not SAFE_CODE.fullmatch(row_code) or not SAFE_CODE.fullmatch(column_code):
            raise BeaApiError("BEA row/column code is invalid")
        if not row_label or not column_label or len(row_label) > 500 or len(column_label) > 500:
            raise BeaApiError("BEA row/column label is invalid")
        if table_id != expected_table_id or year != expected_year or unit != expected_unit:
            raise BeaApiError("BEA table/year/unit identity drift")
        if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() in {"", "--", "(D)", "(NA)"}):
            continue
        try:
            value = Decimal(str(raw_value).replace(",", ""))
        except InvalidOperation as error:
            raise BeaApiError("BEA coefficient is not numeric") from error
        if not value.is_finite() or value < 0:
            raise BeaApiError("BEA coefficient is outside the accepted domain")
        cell = BeaCell(row_code, row_label, column_code, column_label, str(value), year, table_id, unit)
        if cell.identity in identities:
            raise BeaApiError("BEA data contains a duplicate source-cell identity")
        identities.add(cell.identity)
        cells.append(cell)
    if not cells:
        raise BeaApiError("BEA response has no usable cells; missing is not zero")
    return cells


class BeaInputOutputClient:
    def __init__(self, user_id: str, transport: Callable[[str], bytes], budget: BeaRequestBudget | None = None):
        validate_user_id(user_id)
        self._user_id = user_id
        self._transport = transport
        self._budget = budget or BeaRequestBudget()

    def _url(self, **parameters: str) -> str:
        query = {"UserID": self._user_id, "DataSetName": BEA_DATASET, **parameters}
        return f"{BEA_API_ENDPOINT}?{urlencode(query)}"

    def parameter_values(self, parameter_name: str) -> tuple[list[BeaParameterValue], str]:
        if parameter_name not in {"TableID", "Year"}:
            raise BeaApiError("InputOutput metadata discovery is limited to TableID and Year")
        url = self._url(method=PARAMETER_METHOD, ParameterName=parameter_name)
        body = self._fetch(url)
        return parse_parameter_values(body), redact_bea_url(url)

    def data(self, table_id: str, year: str) -> tuple[bytes, str]:
        if not table_id.isdigit() or not re.fullmatch(r"\d{4}", year):
            raise BeaApiError("BEA data request requires live integer TableID and four-digit year")
        url = self._url(method="GetData", TableID=table_id, Year=year)
        return self._fetch(url), redact_bea_url(url)

    def _fetch(self, url: str) -> bytes:
        self._budget.begin_request()
        try:
            body = self._transport(url)
        except Exception:
            self._budget.record_result(0, failed=True)
            raise
        self._budget.record_result(len(body))
        return body
