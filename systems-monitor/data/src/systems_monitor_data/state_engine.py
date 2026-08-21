from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from .derivation import stable_id
from .evidence import evidence_links
from .models import parse_utc


REPLAY_MODES = {"PUBLICLY_AVAILABLE_AS_OF", "OPERATIONALLY_KNOWN_AS_OF"}
AUTHORIZED_INDICATORS = {
    "US_LABOR_TOTAL_NONFARM_PAYROLLS": ("monthly", "employment_level"),
    "US_LABOR_U3_UNEMPLOYMENT_RATE": ("monthly", "unemployment_rate"),
    "US_LABOR_FORCE_PARTICIPATION_RATE": ("monthly", "participation_rate"),
    "US_LABOR_INITIAL_UI_CLAIMS": ("weekly", "claims"),
    "US_LABOR_JOB_OPENINGS": ("monthly", "job_openings"),
    "US_LABOR_HIRES": ("monthly", "hires"),
}


def _period_date(period: str) -> date:
    if len(period) == 7:
        year, month = (int(part) for part in period.split("-"))
        if month == 12:
            return date(year + 1, 1, 1)
        return date(year, month + 1, 1)
    return date.fromisoformat(period)


def _eligible(metric: dict[str, Any], mode: str, cutoff: str) -> bool:
    if metric.get("rightsState") != "ALLOW":
        return False
    cutoff_time = parse_utc(cutoff)
    field = "publicTime" if mode == "PUBLICLY_AVAILABLE_AS_OF" else "acceptedTime"
    return parse_utc(metric[field]) <= cutoff_time


def select_as_of(metrics: list[dict[str, Any]], mode: str, cutoff: str) -> list[dict[str, Any]]:
    if mode not in REPLAY_MODES:
        raise ValueError("unsupported replay mode")
    if any(row.get("id") not in AUTHORIZED_INDICATORS for row in metrics):
        raise ValueError("Phase-4A input is outside the six authorized indicators")
    by_indicator: dict[str, list[dict[str, Any]]] = {}
    for row in metrics:
        if _eligible(row, mode, cutoff):
            by_indicator.setdefault(row["id"], []).append(row)
    selected = []
    for indicator_id in sorted(by_indicator):
        rows = sorted(
            by_indicator[indicator_id],
            key=lambda row: (row["observationPeriod"], int(row.get("revisionNumber", 0)), row["publicTime"], row["acceptedTime"]),
        )
        selected.append(rows[-1])
    return selected


def previous_eligible(
    metrics: list[dict[str, Any]], indicator_id: str, current_period: str, mode: str, cutoff: str
) -> dict[str, Any] | None:
    candidates = [
        row for row in metrics
        if row.get("id") == indicator_id
        and row.get("observationPeriod", "") < current_period
        and _eligible(row, mode, cutoff)
    ]
    return sorted(candidates, key=lambda row: (row["observationPeriod"], int(row.get("revisionNumber", 0))))[-1] if candidates else None


class StateEngine:
    def __init__(self, profile: dict[str, Any]):
        self.profile = profile

    def run(
        self,
        metrics: list[dict[str, Any]],
        *,
        replay_mode: str,
        knowledge_cutoff: str,
        evaluated_at: str,
        source_snapshot_id: str,
    ) -> dict[str, Any]:
        parse_utc(knowledge_cutoff)
        evaluated = parse_utc(evaluated_at)
        selected = select_as_of(metrics, replay_mode, knowledge_cutoff)
        run_identity = {
            "engineVersion": self.profile["stateEngineVersion"],
            "configurationVersion": self.profile["configurationVersion"],
            "sourceSnapshotId": source_snapshot_id,
            "replayMode": replay_mode,
            "knowledgeCutoff": knowledge_cutoff,
            "evaluatedAt": evaluated_at,
            "geography": "US",
            "rightsDecisionSet": sorted({row.get("rightsState", "UNKNOWN") for row in selected}),
            "observationIdentities": [
                [row["id"], row["observationPeriod"], row.get("vintageId"), row.get("revisionNumber", 0)]
                for row in selected
            ],
        }
        observations = [self._observation_state(row, evaluated) for row in selected]
        return {
            **run_identity,
            "stateRunId": stable_id("state-run", run_identity),
            "states": observations,
            "missingIndicators": sorted(set(AUTHORIZED_INDICATORS) - {row["id"] for row in selected}),
        }

    def _observation_state(self, metric: dict[str, Any], evaluated: datetime) -> dict[str, Any]:
        frequency, state_family = AUTHORIZED_INDICATORS[metric["id"]]
        period_date = _period_date(metric["observationPeriod"])
        age_days = max(0, (evaluated.date() - period_date).days)
        max_age = self.profile["freshnessMaxAgeDays"][frequency]
        freshness = metric.get("observationFreshness") or ("stale" if age_days > max_age else "current")
        identity = {
            "indicatorId": metric["id"],
            "period": metric["observationPeriod"],
            "vintageId": metric.get("vintageId"),
            "revisionNumber": metric.get("revisionNumber", 0),
        }
        links = evidence_links(metric["sourceId"], metric["sourceSeriesId"], metric["provenanceUrl"])
        return {
            "stateId": stable_id("obs-state", identity),
            "nodeId": f"indicator:{metric['id']}",
            "stateType": "OBS",
            "auxsaysCalculation": "NONE",
            "label": metric["label"],
            "value": str(Decimal(str(metric["value"]))),
            "unit": metric["unit"],
            "stateFamily": state_family,
            "observationPeriod": metric["observationPeriod"],
            "publicTime": metric["publicTime"],
            "retrievedTime": metric["retrievedTime"],
            "acceptedTime": metric["acceptedTime"],
            "ageDays": age_days,
            "frequency": frequency,
            "freshness": freshness,
            "retrievalPathHealth": metric.get("retrievalPathHealth", "UNKNOWN"),
            "sourceId": metric["sourceId"],
            "sourceSeriesId": metric["sourceSeriesId"],
            "sourceLabel": metric["sourceLabel"],
            "seasonalAdjustment": metric["seasonalAdjustment"],
            "geography": "US",
            "rightsState": metric["rightsState"],
            **links,
            "artifactSha256": metric["artifactSha256"],
            "carriedForward": period_date < evaluated.date(),
        }
