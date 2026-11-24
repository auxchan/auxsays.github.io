from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


METHOD_SCHEMA = "state-payroll-growth-breadth-methodology-1.0.0"
EXPECTED_FACTOR = "factor:canonical:state-level-payroll-growth-breadth"
STATE_SERIES = re.compile(r"^SMS\d{2}000000000000001$")


@dataclass(frozen=True)
class StatePayrollInputObservation:
    observation_id: str
    series_id: str
    jurisdiction: str
    valid_time: str
    value: Decimal
    source_revision_status: str
    acceptance_state: str = "ACCEPTED"
    unit: str = "thousands of persons"
    industry_scope: str = "TOTAL_NONFARM"
    measure: str = "ALL_EMPLOYEES_THOUSANDS"
    seasonal_adjustment: str = "SEASONALLY_ADJUSTED"
    frequency: str = "MONTHLY"
    geography_scope: str = "STATEWIDE"


@dataclass(frozen=True)
class StatePayrollInputProvenance:
    series_id: str
    jurisdiction: str
    current_observation_id: str
    current_period: str
    current_revision_state: str
    current_value: str
    prior_observation_id: str
    prior_period: str
    prior_revision_state: str
    prior_value: str


@dataclass(frozen=True)
class StatePayrollBreadthCandidate:
    status: str
    observation_id: str
    canonical_factor_id: str
    valid_time: str
    value: Decimal
    unit: str
    growing_member_count: int
    denominator: int
    methodology_version: str
    universe_version: str
    input_provenance: tuple[StatePayrollInputProvenance, ...]
    history_class: str
    forecast_vintage_eligible: bool


@dataclass(frozen=True)
class StatePayrollBreadthUnavailable:
    status: str
    missing_current_series: tuple[str, ...]
    missing_prior_series: tuple[str, ...]
    reasons: tuple[str, ...]
    value: None = None


def load_state_payroll_breadth_methodology(path: Path) -> dict[str, Any]:
    methodology = json.loads(path.read_text(encoding="utf-8"))
    validate_state_payroll_breadth_methodology(methodology)
    return methodology


def validate_state_payroll_breadth_methodology(methodology: dict[str, Any]) -> None:
    if methodology.get("schemaVersion") != METHOD_SCHEMA:
        raise ValueError("unsupported state payroll growth breadth methodology schema")
    if methodology.get("canonicalFactorId") != EXPECTED_FACTOR or methodology.get("claimClass") != "B_GOVERNED_CALC":
        raise ValueError("state payroll growth breadth must retain governed CALC identity")
    if methodology.get("methodologyVersion") != "STATE_PAYROLL_GROWTH_BREADTH_V1" or methodology.get("universeVersion") != "CES_STATE_TOTAL_NONFARM_V1":
        raise ValueError("state payroll breadth methodology or universe version is incorrect")
    coverage = methodology.get("coveragePolicy", {})
    if coverage.get("requiredPercent") != 100 or coverage.get("requiredMemberCount") != 51 or coverage.get("denominator") != 51:
        raise ValueError("state payroll breadth requires fixed 51-of-51 coverage")
    if coverage.get("denominatorMayShrink") is not False or coverage.get("interpolationAllowed") is not False or coverage.get("carryForwardAllowed") is not False:
        raise ValueError("state payroll breadth coverage must fail closed")
    universe = methodology.get("universe", {})
    members = universe.get("members", [])
    selectors = [row.get("seriesId") for row in members]
    fips = [row.get("fips") for row in members]
    postals = [row.get("postalCode") for row in members]
    if len(members) != 51 or len(set(selectors)) != 51 or len(set(fips)) != 51 or len(set(postals)) != 51:
        raise ValueError("state payroll universe must contain 51 unique jurisdictions and selectors")
    if universe.get("includesDistrictOfColumbia") is not True or universe.get("metropolitanSeriesAllowed") is not False or universe.get("mixedSeasonalAdjustmentAllowed") is not False:
        raise ValueError("state payroll universe boundaries are not exact")
    for member in members:
        expected = f"SMS{member['fips']}000000000000001"
        if member.get("seriesId") != expected or not STATE_SERIES.fullmatch(expected):
            raise ValueError("state payroll universe contains a non-statewide or malformed selector")
    production = methodology.get("productionState", {})
    if production.get("acceptedCesInputHistoryDepth") != 0 or production.get("calculatedHistoryDepth") != 0:
        raise ValueError("methodology artifact cannot promote calibration data into accepted history")


def calculate_state_payroll_growth_breadth(
    methodology: dict[str, Any],
    current_inputs: Iterable[StatePayrollInputObservation],
    prior_inputs: Iterable[StatePayrollInputObservation],
) -> StatePayrollBreadthCandidate | StatePayrollBreadthUnavailable:
    validate_state_payroll_breadth_methodology(methodology)
    members = tuple(methodology["universe"]["members"])
    expected = tuple(row["seriesId"] for row in members)
    jurisdiction_by_series = {row["seriesId"]: row["postalCode"] for row in members}
    current = _index(current_inputs)
    prior = _index(prior_inputs)
    missing_current = tuple(series_id for series_id in expected if series_id not in current)
    missing_prior = tuple(series_id for series_id in expected if series_id not in prior)
    reasons: list[str] = []
    if missing_current or missing_prior:
        reasons.append("INCOMPLETE_51_OF_51_COVERAGE")
    if set(current) - set(expected) or set(prior) - set(expected):
        reasons.append("UNEXPECTED_SERIES_OUTSIDE_GOVERNED_UNIVERSE")
    if reasons:
        return StatePayrollBreadthUnavailable("UNAVAILABLE_INCOMPLETE_OR_INCOMPATIBLE_INPUT", missing_current, missing_prior, tuple(reasons))

    for series_id in expected:
        for label, row in (("CURRENT", current[series_id]), ("PRIOR", prior[series_id])):
            reason = _incompatibility(row, jurisdiction_by_series[series_id])
            if reason:
                reasons.append(f"{series_id}:{label}_{reason}")
    current_periods = {row.valid_time for row in current.values()}
    prior_periods = {row.valid_time for row in prior.values()}
    if len(current_periods) != 1 or len(prior_periods) != 1:
        reasons.append("INPUT_PERIODS_NOT_ALIGNED")
    elif not _is_previous_month(next(iter(prior_periods)), next(iter(current_periods))):
        reasons.append("INPUT_PERIODS_NOT_PREVIOUS_COMPATIBLE_MONTHS")
    if reasons:
        return StatePayrollBreadthUnavailable("UNAVAILABLE_INCOMPLETE_OR_INCOMPATIBLE_INPUT", (), (), tuple(reasons))

    period = next(iter(current_periods))
    growing = sum(current[series_id].value > prior[series_id].value for series_id in expected)
    value = (Decimal(growing) * Decimal(100) / Decimal(51)).quantize(Decimal("0.0001"))
    provenance = tuple(
        StatePayrollInputProvenance(
            series_id=series_id,
            jurisdiction=jurisdiction_by_series[series_id],
            current_observation_id=current[series_id].observation_id,
            current_period=current[series_id].valid_time,
            current_revision_state=current[series_id].source_revision_status,
            current_value=str(current[series_id].value),
            prior_observation_id=prior[series_id].observation_id,
            prior_period=prior[series_id].valid_time,
            prior_revision_state=prior[series_id].source_revision_status,
            prior_value=str(prior[series_id].value),
        ) for series_id in expected
    )
    identity = {"factor": EXPECTED_FACTOR, "methodologyVersion": methodology["methodologyVersion"], "universeVersion": methodology["universeVersion"], "period": period, "value": str(value), "inputs": [row.__dict__ for row in provenance]}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
    return StatePayrollBreadthCandidate(
        status="CALC_CANDIDATE_PENDING_ACCEPTANCE",
        observation_id=f"calc:state-payroll-growth-breadth:{period}:{digest}",
        canonical_factor_id=EXPECTED_FACTOR,
        valid_time=period,
        value=value,
        unit="percent",
        growing_member_count=growing,
        denominator=51,
        methodology_version=methodology["methodologyVersion"],
        universe_version=methodology["universeVersion"],
        input_provenance=provenance,
        history_class="CURRENT_REVISED_HISTORY",
        forecast_vintage_eligible=False,
    )


def _index(inputs: Iterable[StatePayrollInputObservation]) -> dict[str, StatePayrollInputObservation]:
    indexed: dict[str, StatePayrollInputObservation] = {}
    for row in inputs:
        if row.series_id in indexed:
            raise ValueError(f"duplicate state CES input observation for {row.series_id}")
        indexed[row.series_id] = row
    return indexed


def _incompatibility(row: StatePayrollInputObservation, expected_jurisdiction: str) -> str | None:
    if not row.observation_id or not row.source_revision_status:
        return "INPUT_IDENTITY_OR_REVISION_STATE_MISSING"
    if not row.value.is_finite():
        return "INVALID_NUMERIC_INPUT"
    required = (
        (row.acceptance_state, "ACCEPTED", "INPUT_NOT_ACCEPTED"),
        (row.jurisdiction, expected_jurisdiction, "JURISDICTION_MISMATCH"),
        (row.unit, "thousands of persons", "INCOMPATIBLE_UNIT"),
        (row.industry_scope, "TOTAL_NONFARM", "NON_TOTAL_NONFARM_INPUT"),
        (row.measure, "ALL_EMPLOYEES_THOUSANDS", "NON_ALL_EMPLOYEES_INPUT"),
        (row.seasonal_adjustment, "SEASONALLY_ADJUSTED", "SEASONALLY_INCOMPATIBLE_INPUT"),
        (row.frequency, "MONTHLY", "NON_MONTHLY_INPUT"),
        (row.geography_scope, "STATEWIDE", "METROPOLITAN_OR_NON_STATEWIDE_INPUT"),
    )
    return next((reason for actual, expected, reason in required if actual != expected), None)


def _is_previous_month(prior: str, current: str) -> bool:
    try:
        prior_year, prior_month = (int(value) for value in prior.split("-"))
        current_year, current_month = (int(value) for value in current.split("-"))
    except (ValueError, AttributeError):
        return False
    if not (1 <= prior_month <= 12 and 1 <= current_month <= 12):
        return False
    return (current_year, current_month) == (prior_year + (prior_month == 12), 1 if prior_month == 12 else prior_month + 1)
