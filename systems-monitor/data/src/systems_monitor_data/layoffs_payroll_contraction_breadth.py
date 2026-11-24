from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


METHOD_SCHEMA = "payroll-contraction-breadth-methodology-1.0.0"
EXPECTED_FACTOR = "factor:canonical:payroll-contraction-breadth"


@dataclass(frozen=True)
class CesInputObservation:
    observation_id: str
    series_id: str
    valid_time: str
    value: Decimal
    source_revision_status: str
    acceptance_state: str = "ACCEPTED"
    history_class: str = "CURRENT_REVISED_HISTORY"
    forecast_vintage_eligible: bool = False
    geography: str = "US_NATIONAL"
    industry_scope: str = "PRIVATE_INDUSTRY"
    measure: str = "ALL_EMPLOYEES_THOUSANDS"
    seasonal_adjustment: str = "SEASONALLY_ADJUSTED"
    frequency: str = "MONTHLY"


@dataclass(frozen=True)
class CalculationInputProvenance:
    series_id: str
    current_observation_id: str
    current_period: str
    current_revision_state: str
    current_value: str
    prior_observation_id: str
    prior_period: str
    prior_revision_state: str
    prior_value: str


@dataclass(frozen=True)
class PayrollBreadthCandidate:
    status: str
    observation_id: str
    canonical_factor_id: str
    valid_time: str
    value: Decimal
    unit: str
    contracted_member_count: int
    denominator: int
    methodology_version: str
    universe_version: str
    input_provenance: tuple[CalculationInputProvenance, ...]
    history_class: str
    forecast_vintage_eligible: bool
    public_statement: str


@dataclass(frozen=True)
class PayrollBreadthUnavailable:
    status: str
    missing_current_series: tuple[str, ...]
    missing_prior_series: tuple[str, ...]
    reasons: tuple[str, ...]
    value: None = None


def load_payroll_breadth_methodology(path: Path) -> dict[str, Any]:
    methodology = json.loads(path.read_text(encoding="utf-8"))
    validate_payroll_breadth_methodology(methodology)
    return methodology


def validate_payroll_breadth_methodology(methodology: dict[str, Any]) -> None:
    if methodology.get("schemaVersion") != METHOD_SCHEMA:
        raise ValueError("unsupported payroll contraction breadth methodology schema")
    if methodology.get("canonicalFactorId") != EXPECTED_FACTOR or methodology.get("claimClass") != "B_GOVERNED_CALC":
        raise ValueError("payroll contraction breadth must retain governed CALC identity")
    coverage = methodology.get("coveragePolicy", {})
    if coverage.get("requiredPercent") != 100 or coverage.get("requiredMemberCount") != 10 or coverage.get("denominator") != 10:
        raise ValueError("payroll contraction breadth requires fixed 10-of-10 coverage")
    if coverage.get("denominatorMayShrink") is not False or coverage.get("interpolationAllowed") is not False or coverage.get("carryForwardAllowed") is not False:
        raise ValueError("payroll contraction breadth coverage must fail closed")
    universe = methodology.get("universe", {})
    members = universe.get("members", [])
    selectors = [member.get("seriesId") for member in members]
    partitions = [member.get("exclusivePartition") for member in members]
    if len(members) != 10 or len(set(selectors)) != 10 or len(set(partitions)) != 10:
        raise ValueError("payroll contraction breadth universe must contain ten unique non-overlapping members")
    if universe.get("mutuallyExclusive") is not True or universe.get("nonOverlapping") is not True or universe.get("mixedParentChildAggregates") is not False:
        raise ValueError("payroll contraction breadth universe exclusivity is not proven")
    for member in members:
        if not str(member.get("seriesId", "")).startswith("CES") or not str(member.get("seriesId", "")).endswith("01"):
            raise ValueError("methodology member is not an exact CES all-employees selector")
        for field, expected in (
            ("geography", "US_NATIONAL"),
            ("industryScope", "PRIVATE_INDUSTRY"),
            ("measure", "ALL_EMPLOYEES_THOUSANDS"),
            ("seasonalAdjustment", "SEASONALLY_ADJUSTED"),
        ):
            if member.get(field) != expected:
                raise ValueError(f"methodology member has incompatible {field}")
    production = methodology.get("productionState", {})
    if production.get("acceptedCesInputHistoryDepth") != 0 or production.get("calculatedHistoryDepth") != 0:
        raise ValueError("methodology artifact cannot promote calibration data into accepted history")
    output = methodology.get("calculationOutputContract", {})
    if output.get("historyClass") != "CURRENT_REVISED_HISTORY" or output.get("forecastVintageEligible") is not False:
        raise ValueError("calculation output must remain current-revised and forecast-ineligible")


def calculate_payroll_contraction_breadth(
    methodology: dict[str, Any],
    current_inputs: Iterable[CesInputObservation],
    prior_inputs: Iterable[CesInputObservation],
) -> PayrollBreadthCandidate | PayrollBreadthUnavailable:
    validate_payroll_breadth_methodology(methodology)
    expected = tuple(member["seriesId"] for member in methodology["universe"]["members"])
    current = _index_inputs(current_inputs)
    prior = _index_inputs(prior_inputs)
    missing_current = tuple(series_id for series_id in expected if series_id not in current)
    missing_prior = tuple(series_id for series_id in expected if series_id not in prior)
    reasons: list[str] = []
    extra_current = sorted(set(current) - set(expected))
    extra_prior = sorted(set(prior) - set(expected))
    if missing_current or missing_prior:
        reasons.append("INCOMPLETE_10_OF_10_COVERAGE")
    if extra_current or extra_prior:
        reasons.append("UNEXPECTED_SERIES_OUTSIDE_GOVERNED_UNIVERSE")
    if reasons:
        return PayrollBreadthUnavailable(
            status="UNAVAILABLE_INCOMPLETE_OR_INCOMPATIBLE_INPUT",
            missing_current_series=missing_current,
            missing_prior_series=missing_prior,
            reasons=tuple(reasons),
        )

    for series_id in expected:
        for observation in (current[series_id], prior[series_id]):
            incompatibility = _input_incompatibility(observation)
            if incompatibility:
                reasons.append(f"{series_id}:{incompatibility}")
    current_periods = {row.valid_time for row in current.values()}
    prior_periods = {row.valid_time for row in prior.values()}
    if len(current_periods) != 1 or len(prior_periods) != 1:
        reasons.append("INPUT_PERIODS_NOT_ALIGNED")
    elif not _is_previous_month(next(iter(prior_periods)), next(iter(current_periods))):
        reasons.append("INPUT_PERIODS_NOT_PREVIOUS_COMPATIBLE_MONTHS")
    if reasons:
        return PayrollBreadthUnavailable(
            status="UNAVAILABLE_INCOMPLETE_OR_INCOMPATIBLE_INPUT",
            missing_current_series=(),
            missing_prior_series=(),
            reasons=tuple(reasons),
        )

    period = next(iter(current_periods))
    contracted = sum(current[series_id].value < prior[series_id].value for series_id in expected)
    value = Decimal(contracted * 10)
    provenance = tuple(
        CalculationInputProvenance(
            series_id=series_id,
            current_observation_id=current[series_id].observation_id,
            current_period=current[series_id].valid_time,
            current_revision_state=current[series_id].source_revision_status,
            current_value=str(current[series_id].value),
            prior_observation_id=prior[series_id].observation_id,
            prior_period=prior[series_id].valid_time,
            prior_revision_state=prior[series_id].source_revision_status,
            prior_value=str(prior[series_id].value),
        )
        for series_id in expected
    )
    identity = {
        "factor": EXPECTED_FACTOR,
        "methodologyVersion": methodology["methodologyVersion"],
        "universeVersion": methodology["universeVersion"],
        "period": period,
        "value": str(value),
        "inputs": [row.__dict__ for row in provenance],
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
    return PayrollBreadthCandidate(
        status="CALC_CANDIDATE_PENDING_ACCEPTANCE",
        observation_id=f"calc:payroll-contraction-breadth:{period}:{digest}",
        canonical_factor_id=EXPECTED_FACTOR,
        valid_time=period,
        value=value,
        unit="percent",
        contracted_member_count=contracted,
        denominator=10,
        methodology_version=methodology["methodologyVersion"],
        universe_version=methodology["universeVersion"],
        input_provenance=provenance,
        history_class="CURRENT_REVISED_HISTORY",
        forecast_vintage_eligible=False,
        public_statement=f"{value}% of tracked private-industry supersectors contracted payrolls from the previous month.",
    )


def _index_inputs(inputs: Iterable[CesInputObservation]) -> dict[str, CesInputObservation]:
    indexed: dict[str, CesInputObservation] = {}
    for observation in inputs:
        if observation.series_id in indexed:
            raise ValueError(f"duplicate CES input observation for {observation.series_id}")
        indexed[observation.series_id] = observation
    return indexed


def _input_incompatibility(observation: CesInputObservation) -> str | None:
    if not observation.observation_id or not observation.source_revision_status:
        return "INPUT_IDENTITY_OR_REVISION_STATE_MISSING"
    if not observation.value.is_finite():
        return "INVALID_NUMERIC_INPUT"
    expected = (
        (observation.acceptance_state, "ACCEPTED", "INPUT_NOT_ACCEPTED"),
        (observation.history_class, "CURRENT_REVISED_HISTORY", "NOT_CURRENT_REVISED_HISTORY"),
        (observation.forecast_vintage_eligible, False, "FORECAST_VINTAGE_INPUT_NOT_ALLOWED"),
        (observation.geography, "US_NATIONAL", "NON_NATIONAL_INPUT"),
        (observation.industry_scope, "PRIVATE_INDUSTRY", "NON_PRIVATE_INDUSTRY_INPUT"),
        (observation.measure, "ALL_EMPLOYEES_THOUSANDS", "NON_PAYROLL_EMPLOYMENT_INPUT"),
        (observation.seasonal_adjustment, "SEASONALLY_ADJUSTED", "SEASONALLY_INCOMPATIBLE_INPUT"),
        (observation.frequency, "MONTHLY", "NON_MONTHLY_INPUT"),
    )
    return next((reason for actual, required, reason in expected if actual != required), None)


def _is_previous_month(prior: str, current: str) -> bool:
    try:
        prior_year, prior_month = (int(value) for value in prior.split("-"))
        current_year, current_month = (int(value) for value in current.split("-"))
    except (ValueError, AttributeError):
        return False
    if not (1 <= prior_month <= 12 and 1 <= current_month <= 12):
        return False
    next_year = prior_year + (1 if prior_month == 12 else 0)
    next_month = 1 if prior_month == 12 else prior_month + 1
    return (current_year, current_month) == (next_year, next_month)
