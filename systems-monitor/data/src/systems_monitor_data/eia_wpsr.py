from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import io
from typing import Any


class EiaWpsrError(ValueError):
    pass


@dataclass(frozen=True)
class EiaObservation:
    state_id: str
    state_type: str
    series_id: str
    label: str
    value: str
    unit: str
    geography: str
    valid_time: str
    public_time: str
    retrieved_time: str
    authority: str
    acquisition_provenance_url: str
    evidence_url: str
    methodology_url: str
    artifact_sha256: str
    assessment: str

    def as_record(self) -> dict[str, Any]:
        return asdict(self)


def _decode(payload: bytes) -> str:
    if not payload or len(payload) > 2_000_000:
        raise EiaWpsrError("EIA WPSR CSV is absent or exceeds the size bound")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise EiaWpsrError("EIA WPSR CSV encoding is not accepted")


def _decimal(raw: str) -> Decimal:
    try:
        value = Decimal(raw.replace(",", "").strip())
    except (AttributeError, InvalidOperation) as error:
        raise EiaWpsrError("EIA WPSR value is not numeric") from error
    if not value.is_finite() or value < 0:
        raise EiaWpsrError("EIA WPSR value is outside the accepted domain")
    return value


def _rows(payload: bytes, expected_columns: int) -> list[list[str]]:
    try:
        rows = list(csv.reader(io.StringIO(_decode(payload))))
    except csv.Error as error:
        raise EiaWpsrError("EIA WPSR CSV is malformed") from error
    if not 2 <= len(rows) <= 500 or len(rows[0]) != expected_columns:
        raise EiaWpsrError("EIA WPSR CSV schema drifted")
    if any(len(row) != expected_columns for row in rows):
        raise EiaWpsrError("EIA WPSR CSV has ragged rows")
    return rows


def _observation(
    *,
    payload: bytes,
    series_id: str,
    label: str,
    value: Decimal,
    unit: str,
    valid_time: str,
    public_time: str,
    retrieved_time: str,
    acquisition_url: str,
    evidence_url: str,
    assessment: str,
) -> EiaObservation:
    artifact_hash = hashlib.sha256(payload).hexdigest()
    identity = f"{series_id}|{valid_time}|{artifact_hash}"
    return EiaObservation(
        state_id="eia-obs:" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        state_type="OBS",
        series_id=series_id,
        label=label,
        value=str(value),
        unit=unit,
        geography="US",
        valid_time=valid_time,
        public_time=public_time,
        retrieved_time=retrieved_time,
        authority="U.S. Energy Information Administration",
        acquisition_provenance_url=acquisition_url,
        evidence_url=evidence_url,
        methodology_url="https://www.eia.gov/petroleum/supply/weekly/",
        artifact_sha256=artifact_hash,
        assessment=assessment,
    )


def parse_refinery_utilization(
    payload: bytes, *, public_time: str, retrieved_time: str
) -> EiaObservation:
    rows = _rows(payload, 12)
    header = rows[0]
    if header[:2] != ["STUB_1", "STUB_2"]:
        raise EiaWpsrError("EIA table 2 headers drifted")
    matches = [row for row in rows[1:] if row[0].strip() == "Refiner Inputs and Utilization" and row[1] == "Percent Utilization"]
    if len(matches) != 1:
        raise EiaWpsrError("EIA table 2 U.S. refinery utilization row is not unique")
    value = _decimal(matches[0][2])
    assessment = "HEADROOM_CONSTRAINED" if value >= Decimal("95") else "HEADROOM_AVAILABLE"
    return _observation(
        payload=payload,
        series_id="EIA_WPSR_TABLE2_US_PERCENT_OPERABLE_UTILIZATION",
        label="U.S. percent operable refinery utilization",
        value=value,
        unit="percent",
        valid_time=header[2],
        public_time=public_time,
        retrieved_time=retrieved_time,
        acquisition_url="https://ir.eia.gov/wpsr/table2.csv",
        evidence_url="https://www.eia.gov/dnav/pet/pet_pnp_wiup_dcu_nus_w.htm",
        assessment=assessment,
    )


def parse_commercial_crude_stocks(
    payload: bytes, *, public_time: str, retrieved_time: str
) -> EiaObservation:
    rows = _rows(payload, 8)
    header = rows[0]
    if header[0] != "STUB_1":
        raise EiaWpsrError("EIA table 4 headers drifted")
    matches = [row for row in rows[1:] if row[0] == "Commercial (Excluding SPR)"]
    if len(matches) != 1:
        raise EiaWpsrError("EIA table 4 commercial crude stocks row is not unique")
    value = _decimal(matches[0][1])
    prior = _decimal(matches[0][2])
    assessment = "BUFFER_AVAILABLE" if value >= prior else "BUFFER_CONSTRAINED"
    return _observation(
        payload=payload,
        series_id="EIA_WPSR_TABLE4_US_COMMERCIAL_CRUDE_EXCLUDING_SPR",
        label="U.S. commercial crude oil stocks excluding SPR",
        value=value,
        unit="million_barrels",
        valid_time=header[1],
        public_time=public_time,
        retrieved_time=retrieved_time,
        acquisition_url="https://ir.eia.gov/wpsr/table4.csv",
        evidence_url="https://www.eia.gov/dnav/pet/pet_stoc_wstk_dcu_nus_w.htm",
        assessment=assessment,
    )
