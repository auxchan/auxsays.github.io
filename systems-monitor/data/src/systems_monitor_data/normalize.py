from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .models import Observation

MONTHS = {f"M{number:02d}": number for number in range(1, 13)}


def normalize_bls(payload: bytes, indicators: list[dict], *, release_id: str, artifact_sha256: str, retrieved_time: str, accepted_time: str, provenance_url: str) -> list[Observation]:
    try:
        document = json.loads(payload)
        if document["status"] != "REQUEST_SUCCEEDED":
            raise ValueError("BLS request did not succeed")
        series_rows = document["Results"]["series"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("BLS schema drift or malformed response") from exc
    by_series = {row["source_series_id"]: row for row in indicators}
    result: list[Observation] = []
    seen: set[str] = set()
    for series in series_rows:
        series_id = series.get("seriesID")
        if series_id not in by_series or series_id in seen:
            raise ValueError("BLS series mismatch or duplicate series")
        seen.add(series_id)
        data = series.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("BLS series missing data")
        latest = next((row for row in data if row.get("period") in MONTHS), None)
        if latest is None:
            raise ValueError("BLS series has no monthly observation")
        try:
            month = MONTHS[latest["period"]]
            year = int(latest["year"])
            value = Decimal(latest["value"].replace(",", ""))
            date(year, month, 1)
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError("BLS malformed date or numeric value") from exc
        indicator = by_series[series_id]
        valid_time = f"{year:04d}-{month:02d}"
        observation_id = hashlib.sha256(f"{indicator['indicator_id']}|{release_id}|{valid_time}".encode()).hexdigest()
        observation = Observation(
            observation_id=observation_id,
            indicator_id=indicator["indicator_id"],
            source_id=indicator["source_id"],
            source_series_id=series_id,
            release_id=release_id,
            artifact_sha256=artifact_sha256,
            value=value,
            unit=indicator["unit"],
            geography="US",
            valid_time=valid_time,
            public_time=retrieved_time,
            retrieved_time=retrieved_time,
            accepted_time=accepted_time,
            vintage_id=release_id,
            revision_number=0,
            supersedes_observation_id=None,
            publication_time_kind="conservative_retrieval_bound",
            provenance_url=provenance_url,
        )
        observation.validate()
        result.append(observation)
    if seen != set(by_series):
        raise ValueError("BLS response omitted a requested series")
    return result


def normalize_dol_release(record: dict) -> Observation:
    required = {"indicator_id", "source_id", "source_series_id", "release_id", "artifact_sha256", "value", "unit", "geography", "valid_time", "public_time", "retrieved_time", "accepted_time", "vintage_id", "revision_number", "supersedes_observation_id", "provenance_url"}
    if not required.issubset(record):
        raise ValueError("DOL release record missing required fields")
    observation_id = hashlib.sha256(f"{record['indicator_id']}|{record['release_id']}|{record['valid_time']}".encode()).hexdigest()
    try:
        observation = Observation(observation_id=observation_id, value=Decimal(str(record["value"])), publication_time_kind="official", rights_state="ALLOW", **{key: record[key] for key in required if key not in {"value"}})
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("DOL invalid numeric value") from exc
    if observation.unit != "claims" or observation.geography != "US":
        raise ValueError("DOL unit or geography mismatch")
    observation.validate()
    return observation


def normalize_dol_xml(payload: bytes, indicator: dict, *, release_id: str, artifact_sha256: str, retrieved_time: str, accepted_time: str, provenance_url: str) -> Observation:
    try:
        root = ET.fromstring(payload)
        if root.tag != "r539cyNational" or not root.attrib.get("rundate"):
            raise ValueError("unexpected DOL root schema")
        available = []
        for week in root.findall("week"):
            raw_value = (week.findtext("InitialClaims/SA") or "").replace("\u00a0", "").strip()
            if raw_value:
                available.append((week, raw_value))
        if not available:
            raise ValueError("DOL response has no national SA initial claims")
        week, raw_value = available[-1]
        valid_time = datetime.strptime(week.findtext("weekEnded"), "%m/%d/%Y").date().isoformat()
        value = Decimal(raw_value.replace(",", ""))
    except (AttributeError, ET.ParseError, InvalidOperation, ValueError) as exc:
        raise ValueError("DOL XML schema drift or malformed value") from exc
    observation_id = hashlib.sha256(f"{indicator['indicator_id']}|{release_id}|{valid_time}".encode()).hexdigest()
    observation = Observation(
        observation_id=observation_id,
        indicator_id=indicator["indicator_id"],
        source_id=indicator["source_id"],
        source_series_id=indicator["source_series_id"],
        release_id=release_id,
        artifact_sha256=artifact_sha256,
        value=value,
        unit=indicator["unit"],
        geography="US",
        valid_time=valid_time,
        public_time=retrieved_time,
        retrieved_time=retrieved_time,
        accepted_time=accepted_time,
        vintage_id=f"eta-query-{root.attrib['rundate']}",
        revision_number=0,
        supersedes_observation_id=None,
        publication_time_kind="conservative_retrieval_bound",
        provenance_url=provenance_url,
    )
    observation.validate()
    return observation
