from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_payroll_breadth_calibration(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schemaVersion") != "payroll-contraction-breadth-calibration-1.0.0":
        raise ValueError("unsupported payroll breadth calibration schema")
    if document.get("status") != "CALIBRATION_COMPLETE_METHOD_APPROVED_INPUT_HISTORY_PENDING":
        raise ValueError("payroll breadth calibration must remain separate from production history")
    decision = document.get("decision", {})
    if decision.get("approvedUniverse") != "OPTION_A" or decision.get("requiredCoveragePercent") != 100:
        raise ValueError("calibration decision must reflect the approved exact-ten universe and coverage")
    if decision.get("calibrationHistoryAcceptedForProduction") is not False:
        raise ValueError("calibration history cannot be accepted as production history")
    if document.get("recommendation", {}).get("authorization") != "REJECTED_SUPERSEDED_BY_TAYLOR_DECISION_2026_10_01":
        raise ValueError("the former 95 percent recommendation must remain explicitly rejected")
    for option in document.get("options", []):
        selectors = [member["seriesId"] for member in option["members"]]
        partitions = [member["exclusivePartition"] for member in option["members"]]
        if len(selectors) != len(set(selectors)) or len(partitions) != len(set(partitions)):
            raise ValueError("CES universe contains duplicate selectors or overlapping partitions")
        if not all(selector.startswith("CES") and selector.endswith("01") for selector in selectors):
            raise ValueError("CES universe must use exact all-employees selectors")
    return document


def load_state_payroll_growth_breadth_calibration(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schemaVersion") != "state-payroll-growth-breadth-calibration-1.0.0":
        raise ValueError("unsupported state payroll breadth calibration schema")
    if document.get("status") != "CALIBRATION_COMPLETE_METHOD_APPROVED_INPUT_HISTORY_PENDING":
        raise ValueError("state payroll breadth calibration must remain separate from production history")
    if document.get("methodologyVersion") != "STATE_PAYROLL_GROWTH_BREADTH_V1" or document.get("universeVersion") != "CES_STATE_TOTAL_NONFARM_V1":
        raise ValueError("state payroll breadth calibration versions are incorrect")
    selectors = document.get("selectors", [])
    if len(selectors) != 51 or len(set(selectors)) != 51:
        raise ValueError("state payroll breadth calibration requires 51 exact selectors")
    if document.get("coverage", {}).get("complete51Of51Periods") != 120:
        raise ValueError("state payroll breadth calibration does not prove the recorded 51-of-51 window")
    if document.get("calibrationHistoryAcceptedForProduction") is not False or document.get("publicationStatus") != "CALIBRATION_ONLY_NOT_ACCEPTED_NOT_PUBLISHABLE":
        raise ValueError("state payroll calibration rows cannot be production history")
    return document


def simulate_coverage(documents: Iterable[dict[str, Any]], selectors: Iterable[str]) -> dict[str, Any]:
    expected = tuple(selectors)
    by_series: dict[str, set[str]] = {}
    for document in documents:
        if document.get("status") != "REQUEST_SUCCEEDED":
            raise ValueError("BLS calibration response did not succeed")
        for series in document.get("Results", {}).get("series", []):
            series_id = series.get("seriesID")
            if series_id in by_series:
                raise ValueError("BLS calibration response duplicated a series")
            periods = {
                f"{row['year']}-{row['period'][1:]}"
                for row in series.get("data", [])
                if row.get("period", "").startswith("M") and row.get("period") != "M13" and row.get("value") not in (None, "", "-")
            }
            by_series[series_id] = periods
    if set(by_series) != set(expected):
        raise ValueError("BLS calibration response did not match the exact universe")
    all_periods = sorted(set().union(*by_series.values()))
    coverage = [sum(period in periods for periods in by_series.values()) / len(expected) * 100 for period in all_periods]
    return {
        "members": len(expected),
        "periods": len(all_periods),
        "firstPeriod": all_periods[0] if all_periods else None,
        "lastPeriod": all_periods[-1] if all_periods else None,
        "at100Percent": _share(coverage, 100),
        "atLeast95Percent": _share(coverage, 95),
        "atLeast90Percent": _share(coverage, 90),
        "atLeast80Percent": _share(coverage, 80),
        "missingBySeries": {series_id: len(all_periods) - len(periods) for series_id, periods in sorted(by_series.items())},
    }


def _share(values: list[float], threshold: float) -> float:
    return round(sum(value >= threshold for value in values) / len(values) * 100, 4) if values else 0.0
