from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


METHOD_SCHEMA = "total-nonfarm-payroll-change-methodology-1.0.0"
EXPECTED_FACTOR = "factor:canonical:total-nonfarm-payroll-change"
EXPECTED_SERIES = "CES0000000001"
EXPECTED_CANONICAL_SERIES = "US_LABOR_TOTAL_NONFARM_PAYROLLS"


@dataclass(frozen=True)
class PayrollLevelObservation:
    observation_id: str
    valid_time: str
    value: Decimal
    source_revision_status: str
    series_id: str = EXPECTED_SERIES
    canonical_series_id: str = EXPECTED_CANONICAL_SERIES
    acceptance_state: str = "ACCEPTED"
    unit: str = "thousands of persons"
    geography: str = "US_NATIONAL"
    seasonal_adjustment: str = "SEASONALLY_ADJUSTED"
    frequency: str = "MONTHLY"


@dataclass(frozen=True)
class PayrollChangeCandidate:
    status: str
    observation_id: str
    canonical_factor_id: str
    valid_time: str
    value: Decimal
    unit: str
    methodology_version: str
    current_input_observation_id: str
    prior_input_observation_id: str
    current_revision_state: str
    prior_revision_state: str
    history_class: str
    forecast_vintage_eligible: bool


@dataclass(frozen=True)
class PayrollChangeUnavailable:
    status: str
    reasons: tuple[str, ...]
    value: None = None


def load_payroll_change_methodology(path: Path) -> dict[str, Any]:
    methodology = json.loads(path.read_text(encoding="utf-8"))
    validate_payroll_change_methodology(methodology)
    return methodology


def validate_payroll_change_methodology(methodology: dict[str, Any]) -> None:
    if methodology.get("schemaVersion") != METHOD_SCHEMA:
        raise ValueError("unsupported total nonfarm payroll change methodology schema")
    if methodology.get("canonicalFactorId") != EXPECTED_FACTOR or methodology.get("claimClass") != "B_GOVERNED_CALC":
        raise ValueError("total nonfarm payroll change must retain governed CALC identity")
    if methodology.get("methodologyVersion") != "PAYROLL_CHANGE_V1" or methodology.get("formula") != "delta_t = E_t - E_t-1":
        raise ValueError("PAYROLL_CHANGE_V1 formula is not exact")
    contract = methodology.get("inputContract", {})
    expected = {
        "seriesId": EXPECTED_SERIES,
        "canonicalSeriesId": EXPECTED_CANONICAL_SERIES,
        "geography": "US_NATIONAL",
        "measure": "ALL_EMPLOYEES_THOUSANDS",
        "sourceUnit": "thousands of persons",
        "seasonalAdjustment": "SEASONALLY_ADJUSTED",
        "frequency": "MONTHLY",
        "comparison": "PREVIOUS_COMPATIBLE_MONTH",
        "requiredAcceptedInputs": 2,
    }
    if any(contract.get(field) != value for field, value in expected.items()):
        raise ValueError("PAYROLL_CHANGE_V1 input contract is incompatible")
    rules = methodology.get("calculationRules", {})
    prohibited = ("percentChangeAllowed", "annualizationAllowed", "smoothingAllowed", "interpolationAllowed", "carryForwardAllowed")
    if any(rules.get(field) is not False for field in prohibited):
        raise ValueError("PAYROLL_CHANGE_V1 must prohibit transformations and imputation")
    production = methodology.get("productionState", {})
    if production.get("acceptedInputHistoryDepth") != 0 or production.get("calculatedHistoryDepth") != 0:
        raise ValueError("methodology artifact cannot promote unaccepted payroll history")


def calculate_total_nonfarm_payroll_change(
    methodology: dict[str, Any],
    current: PayrollLevelObservation | None,
    prior: PayrollLevelObservation | None,
) -> PayrollChangeCandidate | PayrollChangeUnavailable:
    validate_payroll_change_methodology(methodology)
    if current is None or prior is None:
        missing = tuple(label for label, row in (("CURRENT_INPUT_MISSING", current), ("PRIOR_INPUT_MISSING", prior)) if row is None)
        return PayrollChangeUnavailable("UNAVAILABLE_INCOMPLETE_OR_INCOMPATIBLE_INPUT", missing)

    reasons: list[str] = []
    for label, row in (("CURRENT", current), ("PRIOR", prior)):
        if not row.observation_id or not row.source_revision_status:
            reasons.append(f"{label}_INPUT_IDENTITY_OR_REVISION_STATE_MISSING")
        if not row.value.is_finite():
            reasons.append(f"{label}_INVALID_NUMERIC_INPUT")
        required = (
            (row.acceptance_state, "ACCEPTED", "INPUT_NOT_ACCEPTED"),
            (row.series_id, EXPECTED_SERIES, "WRONG_SOURCE_SERIES"),
            (row.canonical_series_id, EXPECTED_CANONICAL_SERIES, "WRONG_CANONICAL_SERIES"),
            (row.unit, "thousands of persons", "INCOMPATIBLE_UNIT"),
            (row.geography, "US_NATIONAL", "NON_NATIONAL_INPUT"),
            (row.seasonal_adjustment, "SEASONALLY_ADJUSTED", "SEASONALLY_INCOMPATIBLE_INPUT"),
            (row.frequency, "MONTHLY", "NON_MONTHLY_INPUT"),
        )
        reasons.extend(f"{label}_{reason}" for actual, expected, reason in required if actual != expected)
    if current.series_id != prior.series_id or current.canonical_series_id != prior.canonical_series_id:
        reasons.append("INPUT_SERIES_IDENTITY_MISMATCH")
    if current.unit != prior.unit:
        reasons.append("INPUT_UNITS_MISMATCH")
    if current.seasonal_adjustment != prior.seasonal_adjustment:
        reasons.append("INPUT_SEASONAL_ADJUSTMENT_MISMATCH")
    if not _is_previous_month(prior.valid_time, current.valid_time):
        reasons.append("INPUT_PERIODS_NOT_PREVIOUS_COMPATIBLE_MONTHS")
    if reasons:
        return PayrollChangeUnavailable("UNAVAILABLE_INCOMPLETE_OR_INCOMPATIBLE_INPUT", tuple(reasons))

    value = current.value - prior.value
    identity = {
        "factor": EXPECTED_FACTOR,
        "methodologyVersion": methodology["methodologyVersion"],
        "period": current.valid_time,
        "value": str(value),
        "current": current.__dict__,
        "prior": prior.__dict__,
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:24]
    return PayrollChangeCandidate(
        status="CALC_CANDIDATE_PENDING_ACCEPTANCE",
        observation_id=f"calc:total-nonfarm-payroll-change:{current.valid_time}:{digest}",
        canonical_factor_id=EXPECTED_FACTOR,
        valid_time=current.valid_time,
        value=value,
        unit="thousands of jobs",
        methodology_version=methodology["methodologyVersion"],
        current_input_observation_id=current.observation_id,
        prior_input_observation_id=prior.observation_id,
        current_revision_state=current.source_revision_status,
        prior_revision_state=prior.source_revision_status,
        history_class="CURRENT_REVISED_HISTORY",
        forecast_vintage_eligible=False,
    )


def _is_previous_month(prior: str, current: str) -> bool:
    try:
        prior_year, prior_month = (int(value) for value in prior.split("-"))
        current_year, current_month = (int(value) for value in current.split("-"))
    except (ValueError, AttributeError):
        return False
    if not (1 <= prior_month <= 12 and 1 <= current_month <= 12):
        return False
    return (current_year, current_month) == (prior_year + (prior_month == 12), 1 if prior_month == 12 else prior_month + 1)
