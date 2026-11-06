from __future__ import annotations

import copy
import calendar
import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from .layoffs_bls_dol import (
    BlsDolLayoffsCollector,
    dol_source_freshness,
    load_layoffs_bls_dol_registry,
    parse_bls_api_response,
    parse_dol_national_xml,
    parse_dol_official_release_pdf,
)
from .layoffs_history import append_history, history_artifact, load_acceptance_ledger, promote_candidate_batch
from .layoffs_payroll_change import PayrollLevelObservation, calculate_total_nonfarm_payroll_change, load_payroll_change_methodology
from .raw import RawStore
from .production_integrity import validate_production_evidence


PRODUCTION_SCHEMA = "systems-monitor-production-1.0.0"
GOVERNANCE = {
    "acceptedStructuralRelationships": 0,
    "gateB": "OPEN",
    "forecastVintageObservations": 0,
    "materiality": "UNAUTHORIZED",
    "destinationImpact": "UNAVAILABLE",
    "phase5": "LOCKED",
    "forecasting": "LOCKED_UNAVAILABLE",
}
PHASE3_METRICS = {
    "CES0000000001": "US_LABOR_TOTAL_NONFARM_PAYROLLS",
    "LNS14000000": "US_LABOR_U3_UNEMPLOYMENT_RATE",
    "LNS11300000": "US_LABOR_FORCE_PARTICIPATION_RATE",
    "DOL-UI-SA-INITIAL": "US_LABOR_INITIAL_UI_CLAIMS",
    "JTS000000000000000JOL": "US_LABOR_JOB_OPENINGS",
    "JTS000000000000000HIL": "US_LABOR_HIRES",
}
SOURCE_INTERVAL_HOURS = {
    # One combined BLS request and bounded DOL retrieval per four-hour heartbeat.
    # Sparse release cadence must not delay detection by days or weeks.
    "dol-ui-claims": 4,
    "bls-jolts": 4,
    "bls-cps": 4,
    "bls-ces": 4,
    "bls-bed": 4,
}


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("production timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: dict[str, Any]) -> bool:
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, path)
    return True


def _due(source_id: str, existing: dict[str, Any] | None, now: datetime, force: bool, operational_checks: dict[str, Any] | None = None) -> bool:
    if force or not existing:
        return True
    check = existing.get("automation", {}).get("sourceChecks", {}).get(source_id, {})
    dates = [candidate.get("lastSuccessfulCheck") for candidate in (check, (operational_checks or {}).get(source_id, {}))]
    valid_dates = [value for value in dates if value and _utc(value) <= now]
    checked_at = max(valid_dates, key=_utc) if valid_dates else None
    if not checked_at:
        return True
    return (now - _utc(checked_at)).total_seconds() >= SOURCE_INTERVAL_HOURS[source_id] * 3600


def _candidate_rows(observations: Iterable[Any], specs_by_series: dict[str, Any], method_by_hash: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation in observations:
        row = asdict(observation)
        row["value"] = str(observation.value)
        row["activation_state"] = "SOURCE_ENABLED_PENDING_ACCEPTANCE"
        row["publication_eligible"] = False
        row["registry_state_before_retrieval"] = specs_by_series[observation.source_series_id].activation_state
        row["acquisition_method"] = method_by_hash[observation.artifact_sha256]
        rows.append(row)
    return rows


def _latest_by_series(history: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_period: dict[tuple[str, str], dict[str, Any]] = {}
    for row in history:
        key = (row["sourceSeriesId"], row["validTime"])
        prior = by_period.get(key)
        if not prior or (row["revisionNumber"], row["acceptedTime"]) > (prior["revisionNumber"], prior["acceptedTime"]):
            by_period[key] = row
    latest: dict[str, dict[str, Any]] = {}
    for row in by_period.values():
        prior = latest.get(row["sourceSeriesId"])
        if not prior or row["validTime"] > prior["validTime"]:
            latest[row["sourceSeriesId"]] = row
    return latest


def _format_value(value: str, unit: str) -> str:
    number = Decimal(value)
    rendered = f"{number:f}"
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if unit in {"claims", "thousands", "thousands of persons", "thousands of jobs"}:
        rendered = f"{int(number):,}" if number == number.to_integral() else f"{number:,f}".rstrip("0").rstrip(".")
    return f"{rendered} {unit}"


def _revision_evidence(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build one deterministic replay proof from accepted DOL revision history."""
    by_id = {row["observationId"]: row for row in history}
    revised = [
        row for row in history
        if row["sourceSeriesId"] == "DOL-UI-SA-INITIAL" and row.get("supersedesObservationId")
    ]
    if not revised:
        raise ValueError("production history lacks an accepted DOL revision chain")
    latest = max(revised, key=lambda row: (row["validTime"], row["revisionNumber"], row["acceptedTime"]))
    original = by_id.get(latest["supersedesObservationId"])
    if original is None or original["validTime"] != latest["validTime"]:
        raise ValueError("accepted DOL revision chain is incomplete")

    def release(row: dict[str, Any], label: str) -> dict[str, Any]:
        value = int(Decimal(row["value"]))
        return {
            "label": label,
            "releaseId": row["releaseId"],
            "publishedAt": row["publicTime"],
            "value": value,
            "displayValue": f"{value:,} claims",
            "evidenceUrl": row["evidenceUrl"],
            "artifactSha256": row["artifactSha256"],
        }

    first = release(original, "Accepted original release")
    current = release(latest, "Accepted revised release")
    return [{
        "id": f"dol-ui-initial-claims-{latest['validTime']}-revision-proof",
        "indicatorId": "US_LABOR_INITIAL_UI_CLAIMS",
        "sourceId": "dol-ui-claims",
        "seriesId": "DOL-UI-SA-INITIAL",
        "validTime": latest["validTime"],
        "label": f"Initial claims — week ending {latest['validTime']}",
        "releases": [first, current],
        "asKnown": {
            "cutoff": original["acceptedTime"],
            "value": first["value"],
            "displayValue": first["displayValue"],
        },
        "latestRevisedTruth": {
            "value": current["value"],
            "displayValue": current["displayValue"],
        },
    }]


def _production_snapshot(
    template: dict[str, Any],
    history: list[dict[str, Any]],
    source_checks: dict[str, Any],
    source_diagnostics: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    snapshot = copy.deepcopy(template)
    latest = _latest_by_series(history)
    metrics = snapshot["extensions"]["auxsays.phase2.metrics"]
    metric_series = {
        metric.get("sourceSeriesIds", [None])[0]: metric.get("id")
        for metric in metrics
        if len(metric.get("sourceSeriesIds", [])) == 1
    }
    if len(metrics) != len(PHASE3_METRICS) or metric_series != PHASE3_METRICS:
        raise ValueError("production snapshot metric identities differ from the exact governed Phase-3 set")
    provenance: dict[str, Any] = {}
    latest_source_rows: dict[str, list[dict[str, Any]]] = {}
    for metric in metrics:
        series_id = metric["sourceSeriesIds"][0]
        row = latest.get(series_id)
        if not row:
            raise ValueError(f"production history lacks accepted Phase-3 series {series_id}")
        numeric = Decimal(row["value"])
        value: int | float = int(numeric) if numeric == numeric.to_integral() else float(numeric)
        metric.update({
            "value": value,
            "displayValue": _format_value(row["value"], row["unit"]),
            "unit": row["unit"],
            "validTime": row["validTime"],
            "direction": "flat",
            "series": [{"displayPeriod": row["validTime"], "period": row["validTime"], "value": value}],
            "method": f"{row['seasonalAdjustment']}; accepted current-revised history; {row['releaseId']}; revision {row['revisionNumber']}",
        })
        provenance_id = f"prod-{row['observationId'][:24]}"
        metric["provenanceRefs"] = [provenance_id]
        provenance[provenance_id] = {
            "id": provenance_id,
            "sourceId": row["sourceId"],
            "seriesIds": [series_id],
            "seriesEvidenceUrls": {series_id: row["evidenceUrl"]},
            "vintageId": row["vintageId"],
            "revisionNumber": row["revisionNumber"],
            "publicationTimeKind": row["publicationTimeKind"],
            "publishedAt": row["publicTime"],
            "retrievedAt": row["retrievedTime"],
            "acceptedAt": row["acceptedTime"],
            "artifactSha256": row["artifactSha256"],
            "evidenceUrl": row["provenanceUrl"],
        }
        latest_source_rows.setdefault(row["sourceId"], []).append(row)
    snapshot["extensions"]["auxsays.phase3.provenance"] = provenance
    snapshot["extensions"]["auxsays.phase3.revisionEvidence"] = _revision_evidence(history)
    source_health: dict[str, Any] = {}
    for source_id, check in source_checks.items():
        dol_status = source_diagnostics.get("dolAcquisitionOverallStatus")
        primary_degraded = source_id == "dol-ui-claims" and dol_status in {
            "SUCCESS_WITH_PRIMARY_STALE",
            "SUCCESS_WITH_PRIMARY_FAILED",
        }
        source_health[source_id] = {
            "observationFreshness": check["health"].lower(),
            "observationFreshnessReason": check["reason"],
            "retrievalPathHealth": "stale" if primary_degraded else "current",
            "retrievalPathReason": (
                "The structured DOL XML path failed or was stale; the separately verified official PDF fallback is current."
                if primary_degraded else
                "The governed exact-series retrieval and validation path completed successfully."
            ),
        }
    snapshot["extensions"]["auxsays.phase3.sourceHealth"] = source_health
    for source_id, rows in latest_source_rows.items():
        source = snapshot["sources"][source_id]
        newest = max(rows, key=lambda row: row["validTime"])
        check = source_checks[source_id]
        source.update({
            "observationTime": newest["validTime"],
            "publishedAt": newest["publicTime"],
            "retrievedAt": newest["retrievedTime"],
            "freshnessEvaluatedAt": generated_at,
            "freshness": "current" if check["health"] == "CURRENT" else "stale",
            "freshnessReason": check["reason"],
            "revision": f"revision {newest['revisionNumber']}",
            "vintage": newest["vintageId"],
        })
    digest_basis = "|".join(f"{row['sourceSeriesId']}:{row['validTime']}:{row['value']}" for row in sorted(latest.values(), key=lambda item: item["sourceSeriesId"]))
    digest = hashlib.sha256(digest_basis.encode("utf-8")).hexdigest()[:12]
    snapshot["snapshot"].update({
        "id": f"factual-production-{generated_at.replace(':', '-').replace('.', '-')}-{digest}",
        "sourceSnapshotId": f"systems-monitor-production-{digest}",
        "asOf": generated_at,
        "evaluatedAt": generated_at,
        "generatedAt": generated_at,
        "publishedAt": generated_at,
        "publicationClass": "factual",
    })
    return snapshot


def _period_end_utc(period: str) -> datetime:
    if re_match := re.fullmatch(r"(20\d{2})-(\d{2})", period):
        year, month = (int(value) for value in re_match.groups())
        return datetime(year, month, calendar.monthrange(year, month)[1], tzinfo=timezone.utc)
    if re_match := re.fullmatch(r"(20\d{2})-Q([1-4])", period):
        year, quarter = (int(value) for value in re_match.groups())
        month = quarter * 3
        return datetime(year, month, calendar.monthrange(year, month)[1], tzinfo=timezone.utc)
    if re_match := re.fullmatch(r"20\d{2}-\d{2}-\d{2}", period):
        return datetime.fromisoformat(period).replace(tzinfo=timezone.utc)
    raise ValueError(f"unsupported production observation period: {period}")


def _bls_source_freshness(source_id: str, rows: list[dict[str, Any]], profile: dict[str, Any], now: datetime) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"{source_id} freshness requires at least one exact-series observation")
    stale_after = int(profile["health_policy"]["stale_after_hours"])
    latest_by_series: dict[str, str] = {}
    for row in rows:
        series_id = row.get("source_series_id", source_id)
        latest_by_series[series_id] = max(latest_by_series.get(series_id, ""), row["observation_period"])
    per_series = {}
    for series_id, period in sorted(latest_by_series.items()):
        age = (now - _period_end_utc(period)).total_seconds() / 3600
        if age < 0:
            raise ValueError(f"{source_id} newest observation cannot follow retrieval")
        per_series[series_id] = {"newestObservationPeriod": period, "observationAgeHours": round(age, 3), "status": "CURRENT" if age <= stale_after else "STALE"}
    newest_period = max(latest_by_series.values())
    status = "CURRENT" if all(row["status"] == "CURRENT" for row in per_series.values()) else "STALE"
    return {
        "status": status,
        "newestObservationPeriod": newest_period,
        "observationAgeHours": max(row["observationAgeHours"] for row in per_series.values()),
        "staleAfterHours": stale_after,
        "series": per_series,
        "freshnessBasis": "PER_SERIES_REFERENCE_AGE_NOT_RELEASE_CALENDAR",
    }


def _payroll_change(history: list[dict[str, Any]], methodology_path: Path) -> dict[str, Any]:
    rows = [row for row in history if row["sourceSeriesId"] == "CES0000000001"]
    by_period: dict[str, dict[str, Any]] = {}
    for row in rows:
        prior = by_period.get(row["validTime"])
        if not prior or row["revisionNumber"] > prior["revisionNumber"]:
            by_period[row["validTime"]] = row
    ordered = sorted(by_period.values(), key=lambda row: row["validTime"])
    if len(ordered) < 2:
        return {"methodologyVersion": "PAYROLL_CHANGE_V1", "status": "UNAVAILABLE_INCOMPLETE_OR_INCOMPATIBLE_INPUT", "publicValue": None, "acceptedProductionInputHistory": len(ordered)}

    def convert(row: dict[str, Any]) -> PayrollLevelObservation:
        return PayrollLevelObservation(
            observation_id=row["observationId"], valid_time=row["validTime"], value=Decimal(row["value"]),
            source_revision_status=row["sourceRevisionStatus"],
        )

    result = calculate_total_nonfarm_payroll_change(load_payroll_change_methodology(methodology_path), convert(ordered[-1]), convert(ordered[-2]))
    payload = asdict(result) if is_dataclass(result) else dict(result)
    payload = json.loads(json.dumps(payload, default=str))
    payload.update({"publicValue": None, "acceptedProductionInputHistory": len(ordered), "publicationBoundary": "CALC_OUTPUT_ACCEPTANCE_REQUIRED"})
    return payload


def _parity(history: list[dict[str, Any]], candidates: list[dict[str, Any]], accepted_series: set[str]) -> list[dict[str, Any]]:
    latest_history = _latest_by_series(history)
    current_by_period = {(row["source_series_id"], row["observation_period"]): row for row in candidates}
    result: list[dict[str, Any]] = []
    for series_id in sorted(accepted_series):
        accepted = latest_history.get(series_id)
        official_rows = [row for row in candidates if row["source_series_id"] == series_id]
        official = max(official_rows, key=lambda row: row["observation_period"]) if official_rows else None
        result.append({
            "sourceSeriesId": series_id,
            "officialLatestPeriod": None if official is None else official["observation_period"],
            "officialLatestValue": None if official is None else official["value"],
            "acceptedLatestPeriod": None if accepted is None else accepted["validTime"],
            "acceptedLatestValue": None if accepted is None else accepted["value"],
            "match": bool(official and accepted and official["observation_period"] == accepted["validTime"] and Decimal(official["value"]) == Decimal(accepted["value"])),
            "automationState": "AUTO_ACCEPT_EXACT_SERIES",
        })
    return result


def _historical_parity(history: list[dict[str, Any]], candidates: list[dict[str, Any]], accepted_series: set[str]) -> dict[str, Any]:
    """Compare deterministic history samples with the publisher's current revision view.

    The audit samples the newest, immediately prior, and oldest accepted period
    for every series, then adds every period that has an accepted revision chain.
    Multiple candidate retrieval paths (the DOL XML and official PDF fallback)
    are resolved by the newest official publication and retrieval timestamps.
    """
    accepted_by_series_period: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in history:
        if row["sourceSeriesId"] in accepted_series:
            accepted_by_series_period.setdefault((row["sourceSeriesId"], row["validTime"]), []).append(row)

    official_by_series_period: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["source_series_id"], row["observation_period"])
        prior = official_by_series_period.get(key)
        rank = (row["public_time"], row["retrieved_time"], row["release_id"], row["artifact_sha256"])
        if prior is None or rank > (prior["public_time"], prior["retrieved_time"], prior["release_id"], prior["artifact_sha256"]):
            official_by_series_period[key] = row

    samples: list[dict[str, Any]] = []
    for series_id in sorted(accepted_series):
        periods = sorted(period for candidate_series, period in accepted_by_series_period if candidate_series == series_id)
        roles_by_period: dict[str, set[str]] = {}
        if periods:
            roles_by_period.setdefault(periods[-1], set()).add("NEWEST")
            roles_by_period.setdefault(periods[0], set()).add("OLDER")
        if len(periods) >= 2:
            roles_by_period.setdefault(periods[-2], set()).add("PRIOR")
        for period in periods:
            if len(accepted_by_series_period[(series_id, period)]) > 1:
                roles_by_period.setdefault(period, set()).add("REVISION_CHAIN")

        for period in sorted(roles_by_period):
            accepted_rows = accepted_by_series_period[(series_id, period)]
            accepted = max(accepted_rows, key=lambda row: (row["revisionNumber"], row["acceptedTime"], row["observationId"]))
            official = official_by_series_period.get((series_id, period))
            matches = official is not None and Decimal(official["value"]) == Decimal(accepted["value"])
            samples.append({
                "sourceSeriesId": series_id,
                "period": period,
                "sampleRoles": sorted(roles_by_period[period]),
                "acceptedValue": accepted["value"],
                "acceptedRevisionNumber": accepted["revisionNumber"],
                "acceptedRevisionChainLength": len(accepted_rows),
                "officialCurrentValue": None if official is None else official["value"],
                "status": "MATCH_CURRENT_OFFICIAL" if matches else "OFFICIAL_WINDOW_NOT_RETRIEVED" if official is None else "ACCEPTED_HISTORY_STALE_REVISION",
            })

    return _historical_parity_document(samples, len(accepted_series))


def _historical_parity_document(samples: list[dict[str, Any]], series_count: int) -> dict[str, Any]:
    samples = sorted(samples, key=lambda row: (row["sourceSeriesId"], row["period"]))
    counts = {
        "seriesAudited": series_count,
        "samples": len(samples),
        "matches": sum(row["status"] == "MATCH_CURRENT_OFFICIAL" for row in samples),
        "officialWindowNotRetrieved": sum(row["status"] == "OFFICIAL_WINDOW_NOT_RETRIEVED" for row in samples),
        "staleAcceptedRevisions": sum(row["status"] == "ACCEPTED_HISTORY_STALE_REVISION" for row in samples),
        "revisionChainPeriods": sum("REVISION_CHAIN" in row["sampleRoles"] for row in samples),
    }
    return {
        "selectionPolicy": "NEWEST_PRIOR_OLDER_PLUS_EVERY_REVISION_CHAIN_PERIOD",
        "counts": counts,
        "samples": samples,
    }


def _merge_current_parity(
    existing: dict[str, Any] | None,
    fresh: list[dict[str, Any]],
    accepted_series: set[str],
    due_series: set[str],
) -> list[dict[str, Any]]:
    prior = {row["sourceSeriesId"]: row for row in (existing or {}).get("sourceParity", [])}
    current = {row["sourceSeriesId"]: row for row in fresh}
    merged: list[dict[str, Any]] = []
    for series_id in sorted(accepted_series):
        row = current.get(series_id) if series_id in due_series else prior.get(series_id)
        if row is None:
            raise ValueError(f"production parity state missing for governed series {series_id}")
        merged.append(row)
    return merged


def _merge_historical_parity(
    existing: dict[str, Any] | None,
    fresh: dict[str, Any],
    accepted_series: set[str],
    due_series: set[str],
) -> dict[str, Any]:
    prior_samples = (existing or {}).get("historicalParity", {}).get("samples", [])
    retained = [row for row in prior_samples if row["sourceSeriesId"] in accepted_series - due_series]
    return _historical_parity_document([*retained, *fresh["samples"]], len(accepted_series))


def _semantic_source_check(check: dict[str, Any] | None) -> dict[str, Any]:
    if not check:
        return {}
    return {key: value for key, value in check.items() if key != "lastSuccessfulCheck"}


def _semantic_diagnostics(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _semantic_diagnostics(item)
            for key, item in value.items()
            if key not in {"retrievedTime", "observationAgeHours"}
        }
    if isinstance(value, list):
        return [_semantic_diagnostics(item) for item in value]
    return value


def update_production(
    *,
    package_root: Path,
    runtime_root: Path,
    output_path: Path,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    generated_at = _iso(now)
    existing = _json(output_path) if output_path.exists() else None
    if existing is None:
        raise ValueError("the committed canonical production artifact is required as the fail-closed structural seed")
    validate_production_evidence(existing, output_path.parent / "raw")
    telemetry_path = output_path.parent / "source-checks.json"
    telemetry = _json(telemetry_path) if telemetry_path.exists() else {}
    operational_checks = telemetry.get("sourceChecks", {})
    registry_path = package_root / "config" / "layoffs" / "sources_bls_dol.json"
    registry_document = _json(registry_path)
    acquisition, specs = load_layoffs_bls_dol_registry(registry_path)
    source_profiles = {row["source_id"]: row for row in registry_document["source_profiles"]}
    rights = _json(package_root / "config" / "rights" / "rights.json")
    ledger = load_acceptance_ledger(package_root / "config" / "layoffs" / "history_acceptance.json", rights_registry=rights)
    accepted_series = {rule["sourceSeriesId"] for rule in ledger["rules"]}
    prior_history = existing["acceptedHistory"]["observations"]
    due_sources = {source_id for source_id in SOURCE_INTERVAL_HOURS if _due(source_id, existing, now, force, operational_checks)}
    if not due_sources:
        return {"status": "NO_SOURCES_DUE", "changed": False, "newlyAccepted": 0, "dueSources": []}

    run_id = str(uuid.uuid4())
    raw_store = RawStore(runtime_root / "raw")
    collector = BlsDolLayoffsCollector(acquisition)
    raw_records: list[Any] = []
    candidates: list[dict[str, Any]] = []
    method_by_hash: dict[str, str] = {}
    specs_by_series = {spec.series_id: spec for spec in specs}
    source_diagnostics: dict[str, Any] = {}

    bls_specs = tuple(
        spec for spec in specs
        if spec.source_id != "dol-ui-claims" and spec.source_id in due_sources and spec.series_id in accepted_series
    )
    if bls_specs:
        relevant_ids = {spec.series_id for spec in bls_specs}
        earliest_year = min(
            (int(row["validTime"][:4]) for row in prior_history if row["sourceSeriesId"] in relevant_ids),
            default=now.year - 1,
        )
        artifact = collector.retrieve_bls(bls_specs, max(now.year - 9, earliest_year), now.year)
        release_id = f"bls-api-retrieval-{artifact.retrieved_time}"
        raw = raw_store.capture(
            source_id="bls-layoffs-combined", run_id=run_id, request_identity=artifact.final_url,
            retrieved_time=artifact.retrieved_time, release_id=release_id, content_type=artifact.content_type,
            body=artifact.body, parser_version=acquisition["bls"]["parser_version"], rights_result="ALLOW",
        )
        parsed = parse_bls_api_response(
            artifact.body, bls_specs, release_id=release_id, artifact_sha256=raw.sha256,
            retrieved_time=artifact.retrieved_time, accepted_time=None, provenance_url=artifact.final_url,
        )
        raw_records.append(raw)
        method_by_hash[raw.sha256] = "bls_api_primary"
        candidates.extend(_candidate_rows(parsed.observations, specs_by_series, method_by_hash))

    dol_selected: list[Any] = []
    dol_freshness: dict[str, Any] | None = None
    dol_historical_parity_available = False
    if "dol-ui-claims" in due_sources:
        dol_specs = tuple(spec for spec in specs if spec.source_id == "dol-ui-claims")
        earliest_dol_year = min(
            (int(row["validTime"][:4]) for row in prior_history if row["sourceSeriesId"] == "DOL-UI-SA-INITIAL"),
            default=now.year,
        )
        primary_freshness: dict[str, Any] | None = None
        primary_failed = False
        try:
            primary = collector.retrieve_dol(earliest_dol_year, now.year)
            primary_release = f"dol-ui-xml-retrieval-{primary.retrieved_time}"
            primary_raw = raw_store.capture(
                source_id="dol-ui-claims", run_id=run_id, request_identity=primary.final_url,
                retrieved_time=primary.retrieved_time, release_id=primary_release, content_type=primary.content_type,
                body=primary.body, parser_version=acquisition["dol_ui"]["parser_version"], rights_result="ALLOW",
            )
            primary_batch = parse_dol_national_xml(
                primary.body, dol_specs, release_id=primary_release, artifact_sha256=primary_raw.sha256,
                retrieved_time=primary.retrieved_time, accepted_time=None, provenance_url=primary.final_url,
            )
            primary_freshness = dol_source_freshness(primary_batch.observations, retrieved_time=primary.retrieved_time, stale_after_hours=int(acquisition["dol_ui"]["stale_after_hours"]))
            raw_records.append(primary_raw)
            method_by_hash[primary_raw.sha256] = "dol_r539cyNational_xml_primary"
            dol_selected.extend(primary_batch.observations)
            dol_freshness = primary_freshness
            dol_historical_parity_available = True
            source_diagnostics["dolPrimaryFreshness"] = primary_freshness
            source_diagnostics.pop("dolPrimaryFailure", None)
        except (OSError, RuntimeError, ValueError) as error:
            primary_failed = True
            source_diagnostics["dolPrimaryFailure"] = {
                "errorType": type(error).__name__,
                "state": "PRIMARY_RETRIEVAL_OR_VALIDATION_FAILED",
            }
            source_diagnostics.pop("dolPrimaryFreshness", None)

        if primary_failed or primary_freshness is None or primary_freshness["status"] != "CURRENT":
            fallback = collector.retrieve_dol_official_release()
            fallback_release = f"dol-ui-official-release-retrieval-{fallback.retrieved_time}"
            fallback_raw = raw_store.capture(
                source_id="dol-ui-claims", run_id=run_id, request_identity=fallback.final_url,
                retrieved_time=fallback.retrieved_time, release_id=fallback_release, content_type=fallback.content_type,
                body=fallback.body, parser_version=acquisition["dol_ui"]["official_release_parser_version"], rights_result="ALLOW",
            )
            fallback_batch = parse_dol_official_release_pdf(
                fallback.body, dol_specs, artifact_sha256=fallback_raw.sha256,
                retrieved_time=fallback.retrieved_time, provenance_url=fallback.final_url,
            )
            fallback_freshness = dol_source_freshness(fallback_batch.observations, retrieved_time=fallback.retrieved_time, stale_after_hours=int(acquisition["dol_ui"]["stale_after_hours"]))
            if fallback_freshness["status"] != "CURRENT":
                raise ValueError("official DOL PDF fallback is stale")
            raw_records.append(fallback_raw)
            method_by_hash[fallback_raw.sha256] = "dol_official_release_pdf_fallback"
            dol_selected.extend(fallback_batch.observations)
            dol_freshness = fallback_freshness
            source_diagnostics["dolFallbackFreshness"] = fallback_freshness
            source_diagnostics["dolAcquisitionOverallStatus"] = (
                "SUCCESS_WITH_PRIMARY_FAILED" if primary_failed else "SUCCESS_WITH_PRIMARY_STALE"
            )
        else:
            source_diagnostics.pop("dolFallbackFreshness", None)
            source_diagnostics["dolAcquisitionOverallStatus"] = "SUCCESS"
        candidates.extend(_candidate_rows(dol_selected, specs_by_series, method_by_hash))
        source_diagnostics["dolFreshness"] = dol_freshness

    # Acceptance is a separate event after every retrieval.  Never reuse the
    # cadence-evaluation instant when network work can finish milliseconds later.
    latest_retrieval = max((_utc(row["retrieved_time"]) for row in candidates), default=now)
    generated_at = _iso(max(now, latest_retrieval, datetime.now(timezone.utc)))
    batch = {
        "schemaVersion": "layoffs-source-candidate-batch-1.0.0",
        "artifactClass": "internal_source_candidate_batch",
        "activationStatus": "NOT_ACCEPTED_NOT_PUBLISHABLE",
        "runId": run_id,
        "generatedAt": generated_at,
        "rawArtifacts": [asdict(record) for record in raw_records],
        "sourceDiagnostics": source_diagnostics,
        "candidates": candidates,
    }
    promoted = promote_candidate_batch(batch, ledger, accepted_at=generated_at, existing_history=prior_history)
    combined = append_history(prior_history, promoted)
    accepted_history = history_artifact(combined, generated_at=generated_at) if promoted else (existing["acceptedHistory"] if existing else history_artifact(combined, generated_at=generated_at))

    source_checks = copy.deepcopy(existing.get("automation", {}).get("sourceChecks", {}))
    source_diagnostics = {
        **copy.deepcopy(existing.get("automation", {}).get("sourceDiagnostics", {})),
        **source_diagnostics,
    }
    for source_id in sorted(due_sources):
        source_rows = [row for row in candidates if row["source_id"] == source_id]
        latest_period = max((row["observation_period"] for row in source_rows), default=None)
        health = "CURRENT"
        reason = "The scheduled exact-series source check completed and its latest governed observation was accepted or already present."
        if source_id == "dol-ui-claims" and dol_freshness:
            health = dol_freshness["status"]
            reason = (
                "Official DOL PDF fallback is current; the structured XML path failed or is stale and is separately reported."
                if source_diagnostics.get("dolAcquisitionOverallStatus") in {"SUCCESS_WITH_PRIMARY_STALE", "SUCCESS_WITH_PRIMARY_FAILED"}
                else "Official DOL structured data is current."
            )
        elif source_id.startswith("bls-"):
            freshness = _bls_source_freshness(source_id, source_rows, source_profiles[source_id], now)
            source_diagnostics.setdefault("blsFreshness", {})[source_id] = freshness
            health = freshness["status"]
            reason = (
                "Every retrieved governed series is within the configured source-age ceiling; this is not a release-calendar lateness check."
                if health == "CURRENT" else
                "At least one governed series exceeds the configured source-age ceiling; inspect per-series freshness."
            )
        source_checks[source_id] = {
            "lastSuccessfulCheck": generated_at,
            "health": health,
            "reason": reason,
            "latestOfficialPeriod": latest_period,
            "newerExpectedReleaseOverdue": health != "CURRENT",
            "minimumIntervalHours": SOURCE_INTERVAL_HOURS[source_id],
        }

    calculations = {
        "PAYROLL_CHANGE_V1": _payroll_change(combined, package_root / "config" / "layoffs" / "total_nonfarm_payroll_change_methodology.json"),
        "PAYROLL_CONTRACTION_BREADTH_V1": {"status": "UNAVAILABLE_ACCEPTED_INPUT_HISTORY_ZERO", "acceptedProductionInputHistory": 0, "publicValue": None, "requiredInputs": 10},
        "STATE_PAYROLL_GROWTH_BREADTH_V1": {"status": "UNAVAILABLE_ACCEPTED_INPUT_HISTORY_ZERO", "acceptedProductionInputHistory": 0, "publicValue": None, "requiredInputs": 51},
    }
    due_accepted_series = {
        spec.series_id for spec in specs
        if spec.source_id in due_sources and spec.series_id in accepted_series
    }
    current_parity = _merge_current_parity(
        existing, _parity(combined, candidates, due_accepted_series), accepted_series, due_accepted_series
    )
    historical_due_series = due_accepted_series - ({"DOL-UI-SA-INITIAL"} if "dol-ui-claims" in due_sources and not dol_historical_parity_available else set())
    historical_parity = _merge_historical_parity(
        existing,
        _historical_parity(combined, candidates, historical_due_series),
        accepted_series,
        historical_due_series,
    )
    if not all(row["match"] for row in current_parity):
        raise ValueError("current official-source parity failed for at least one governed exact series")
    if historical_parity["counts"]["staleAcceptedRevisions"]:
        raise ValueError("historical parity found an accepted value behind the publisher's current revision")

    prior_checks = existing.get("automation", {}).get("sourceChecks", {})
    source_state_changed = any(
        _semantic_source_check(source_checks.get(source_id)) != _semantic_source_check(prior_checks.get(source_id))
        for source_id in due_sources
    )
    prior_diagnostics = existing.get("automation", {}).get("sourceDiagnostics", {})
    semantic_diagnostics_changed = _semantic_diagnostics(source_diagnostics) != _semantic_diagnostics(prior_diagnostics)
    stable_generated_at = existing["generatedAt"]
    snapshot = _production_snapshot(
        existing["factualSnapshot"], combined, source_checks, source_diagnostics, stable_generated_at
    )
    material_change = bool(promoted) or source_state_changed or semantic_diagnostics_changed
    material_change = material_change or calculations != existing.get("calculations")
    material_change = material_change or current_parity != existing.get("sourceParity")
    material_change = material_change or historical_parity != existing.get("historicalParity")
    material_change = material_change or snapshot != existing.get("factualSnapshot")
    # A manually simulated cadence run must never strand production metadata in
    # the future.  Treat that invalid clock state as material so the next
    # real-clock run repairs every generated/freshness timestamp atomically.
    material_change = material_change or _utc(existing["generatedAt"]) > now
    if not material_change:
        _atomic_json(telemetry_path, {"schemaVersion": "production-source-checks-1.0.0", "sourceChecks": {**operational_checks, **{key: source_checks[key] for key in due_sources}}})
        return {
            "status": "UNCHANGED",
            "changed": False,
            "newlyAccepted": 0,
            "acceptedObservationCount": len(combined),
            "acceptedSeriesCount": len(accepted_series),
            "dueSources": sorted(due_sources),
            "sourceParityMatches": sum(1 for row in current_parity if row["match"]),
            "productionPath": str(output_path),
        }

    snapshot = _production_snapshot(
        existing["factualSnapshot"], combined, source_checks, source_diagnostics, generated_at
    )
    existing_raw = {row["sha256"]: row for row in existing.get("rawEvidence", [])}
    for record in raw_records:
        existing_raw[record.sha256] = {
            **asdict(record),
            "repositoryPath": f"systems-monitor/data/production/raw/{record.relative_path}",
        }

    artifact = {
        "schemaVersion": PRODUCTION_SCHEMA,
        "generatedAt": generated_at,
        "lineage": ["official source", "content-addressed raw evidence", "exact-series candidate validation", "governed acceptance", "immutable accepted history", "deterministic calculations", "production read model", "Vite bundle"],
        "governance": GOVERNANCE,
        "automation": {
            "heartbeat": "0 */4 * * *",
            "dueSources": sorted(due_sources),
            "sourceChecks": source_checks,
            "sourceDiagnostics": source_diagnostics,
            "lastRunId": run_id,
        },
        "rawEvidence": [existing_raw[key] for key in sorted(existing_raw)],
        "acceptedHistory": accepted_history,
        "calculations": calculations,
        "sourceParity": current_parity,
        "historicalParity": historical_parity,
        "factualSnapshot": snapshot,
    }
    artifact["payloadSha256"] = hashlib.sha256(json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

    production_raw = output_path.parent / "raw"
    for record in raw_records:
        source = runtime_root / "raw" / record.relative_path
        target = production_raw / record.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(source, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != record.sha256:
            raise RuntimeError("production raw evidence hash verification failed")
    validate_production_evidence(artifact, production_raw)
    changed = _atomic_json(output_path, artifact)
    _atomic_json(telemetry_path, {"schemaVersion": "production-source-checks-1.0.0", "sourceChecks": {**operational_checks, **{key: source_checks[key] for key in due_sources}}})
    return {
        "status": "UPDATED" if changed else "UNCHANGED",
        "changed": changed,
        "newlyAccepted": len(promoted),
        "acceptedObservationCount": len(combined),
        "acceptedSeriesCount": len(accepted_series),
        "dueSources": sorted(due_sources),
        "sourceParityMatches": sum(1 for row in artifact["sourceParity"] if row["match"]),
        "productionPath": str(output_path),
    }
