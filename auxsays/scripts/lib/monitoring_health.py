"""Per-patch community monitoring health: one authority in Python.

Two things read `_data/evidence_method_health.yml` to judge whether the community collection for one
exact patch is healthy:

  * the public monitoring card, `_includes/monitoring-status.html`, a first-match ladder evaluated
    at build time; and
  * the live-consensus certifier, which must refuse to call a patch's consensus "live" unless the
    pipeline producing its evidence is actually running.

Until now only the card existed, and only in Liquid, so nothing in Python could ask the question and
nothing in PR CI checked the card (its render test needs Jekyll). This module is the Python authority
for both: `ladder` is a faithful port of the card, pinned to the same fixture table the render test
uses, and `certify_monitoring` is the stricter, fail-closed predicate (H0-H7) the certifier consults.

    H0  every row's method is one this product's collectors own -- nothing else is evidence of
        community monitoring (an official release-notes fetch never is)
    H7  every method the product owns has a row for this patch: a collector that silently stops
        emitting a failing method cannot leave a healthy-looking subset behind. A retired method
        satisfies this with its explicit `disabled` row.
    H1  at least one method is active (not disabled)
    H2  every active row has a valid, non-future timestamp
    H3  every active row ran after the patch was released and within `monitoring_max_age_days`
    H4  no active row is degraded (partial, blocked, broken, stale, low_confidence,
        manual_review_needed)
    H5  at least one active row is healthy (success or no_results)
    H6  every source family that contributed counted reports has a healthy active row, so disabling
        the method behind most of a patch's evidence cannot launder a pass on a side channel

A `disabled` row is neither healthy nor failing, as the ledger has always defined it. There is NO
minimum number of source families for live consensus: that is a coverage disclosure the card keeps
(INSUFFICIENT COVERAGE), not a reason a patch's own reports are invalid.

Pure: callers pass the rows, the record identity, `now` and the thresholds. Reading the files is
`load_method_health_rows` / `load_thresholds`, kept separate so every decision is reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from .patch_identity import key_from

DEGRADED_STATUSES = frozenset({"partial", "blocked", "broken", "stale", "low_confidence",
                               "manual_review_needed"})
BLOCKED_STATUSES = frozenset({"blocked", "broken"})
HEALTHY_STATUSES = frozenset({"success", "no_results"})
DISABLED = "disabled"

OFFICIAL_SOURCE_ONLY = "OFFICIAL SOURCE ONLY"
COLLECTION_STALE = "COLLECTION STALE"
NOT_YET_MONITORED = "NOT YET MONITORED"
COLLECTION_BLOCKED = "COLLECTION BLOCKED"
MONITORING_DEGRADED = "MONITORING DEGRADED"
INSUFFICIENT_COVERAGE = "INSUFFICIENT COVERAGE"
MONITORING_ACTIVE = "MONITORING ACTIVE"
NO_ACCEPTED_REPORTS = "NO ACCEPTED PATCH-SPECIFIC REPORTS"


@dataclass(frozen=True)
class Thresholds:
    """The two published monitoring thresholds, read from `_config.yml` -- never restated."""
    max_age_days: int
    min_healthy_families: int


def load_thresholds(config_path: Path) -> Thresholds:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    return Thresholds(max_age_days=int(config.get("monitoring_max_age_days") or 14),
                      min_healthy_families=int(config.get("monitoring_min_healthy_methods") or 2))


def load_method_health_rows(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rows = payload.get("methods") if isinstance(payload, dict) else payload
    return [row for row in rows or [] if isinstance(row, dict)]


def rows_for(identity: Mapping[str, Any], rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The method-health rows for one exact patch identity (product, version, build). The card joins
    on the same triple; a build-aware sibling's telemetry never answers for another build."""
    key = key_from(identity)
    return [row for row in rows if key_from(row) == key]


def _epoch(value: Any) -> float | None:
    """Seconds since the epoch the way the card's Liquid `date: '%s'` reads a value: None when the
    value is empty, 0 when it cannot be parsed (Liquid's `date` returns the input, which `plus: 0`
    turns into 0), otherwise the instant."""
    if isinstance(value, datetime):
        moment = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _status(row: Mapping[str, Any]) -> str:
    return str(row.get("status") or "").strip().lower()


def _family(row: Mapping[str, Any]) -> str:
    """A source FAMILY is the evidence source_type -- the identity the ownership manifest uses --
    falling back to the method id, exactly as the card does."""
    return str(row.get("source_type") or "") or str(row.get("method_id") or "")


def ladder(rows: Iterable[Mapping[str, Any]], *, published_at: Any, report_count: int,
           now: datetime, thresholds: Thresholds) -> str:
    """The public monitoring card's status for one patch: a faithful port of
    `_includes/monitoring-status.html`, first match wins.

      1  no rows                                     OFFICIAL SOURCE ONLY
      2  every row disabled                          OFFICIAL SOURCE ONLY
      3  no valid, non-future active timestamp       COLLECTION STALE
      4  nothing ran after release                   NOT YET MONITORED
      5  nothing fresh                               COLLECTION STALE
      6  no healthy family and a blocked/broken row  COLLECTION BLOCKED
      7  a degraded status or an invalid timestamp   MONITORING DEGRADED
      8  healthy families below the minimum          INSUFFICIENT COVERAGE
      9  accepted reports                            MONITORING ACTIVE
      10 otherwise                                   NO ACCEPTED PATCH-SPECIFIC REPORTS
    """
    now_s = now.timestamp()
    max_age_s = thresholds.max_age_days * 86400
    pub_s = _epoch(published_at) or 0.0
    total = disabled = fresh_usable = 0
    families: set[str] = set()
    has_valid = has_post = has_blocked = has_degraded = has_invalid = False
    for row in rows:
        total += 1
        status = _status(row)
        if status == DISABLED:
            disabled += 1
            continue
        if status in BLOCKED_STATUSES:
            has_blocked = True
        if status in DEGRADED_STATUSES:
            has_degraded = True
        run_s = _epoch(row.get("last_run"))
        if run_s is None or run_s > now_s:
            has_invalid = True
            continue
        has_valid = True
        if run_s < pub_s:
            continue
        has_post = True
        if now_s - run_s > max_age_s:
            continue
        fresh_usable += 1
        if status in HEALTHY_STATUSES:
            families.add(_family(row))
    if total == 0 or disabled == total:
        return OFFICIAL_SOURCE_ONLY
    if not has_valid:
        return COLLECTION_STALE
    if not has_post:
        return NOT_YET_MONITORED
    if fresh_usable == 0:
        return COLLECTION_STALE
    if not families and has_blocked:
        return COLLECTION_BLOCKED
    if has_degraded or has_invalid:
        return MONITORING_DEGRADED
    if len(families) < thresholds.min_healthy_families:
        return INSUFFICIENT_COVERAGE
    if int(report_count or 0) > 0:
        return MONITORING_ACTIVE
    return NO_ACCEPTED_REPORTS


@dataclass(frozen=True)
class HealthDecision:
    """Whether one patch's community monitoring is operationally healthy, and every reason it is not.
    The reasons are run diagnostics; they are never published."""
    healthy: bool
    reasons: tuple[str, ...]


def certify_monitoring(product_id: str, rows: Iterable[Mapping[str, Any]], *, published_at: Any,
                       contributing_families: Iterable[str], now: datetime, thresholds: Thresholds,
                       owned_methods: Mapping[str, Iterable[str]],
                       manual_only_methods: Iterable[str] = ()) -> HealthDecision:
    """H0-H7 for one exact patch. Fail closed: every reason found is returned, and any one refuses.

    `owned_methods` is the ownership manifest (`collector_ownership.ALLOWED_METHODS`).
    `manual_only_methods` are owned methods an operator runs by hand: their rows are recorded
    telemetry, but they are never expected (H7) and never count as a running pipeline."""
    owned = set(owned_methods.get(product_id, ()))
    manual = set(manual_only_methods)
    rows = [row for row in rows if str(row.get("method_id") or "") not in manual]
    reasons: list[str] = []

    seen = {str(row.get("method_id") or "") for row in rows}
    for method in sorted(seen - owned):                                         # H0
        reasons.append(f"unowned_method:{method}")
    for method in sorted((owned - manual) - seen):                              # H7
        reasons.append(f"missing_method_telemetry:{method}")

    active = [row for row in rows if _status(row) != DISABLED]
    if not active:                                                              # H1
        reasons.append("no_active_method")
    now_s = now.timestamp()
    pub_s = _epoch(published_at)
    if not pub_s:
        reasons.append("no_release_date")
    max_age_s = thresholds.max_age_days * 86400
    healthy_families: set[str] = set()
    for row in active:
        method = str(row.get("method_id") or "")
        status = _status(row)
        run_s = _epoch(row.get("last_run"))
        if not run_s or run_s > now_s:                                          # H2
            reasons.append(f"invalid_timestamp:{method}")
            continue
        if pub_s and run_s < pub_s:                                             # H3
            reasons.append(f"ran_before_release:{method}")
            continue
        if now_s - run_s > max_age_s:                                           # H3
            reasons.append(f"stale:{method}")
            continue
        if status in DEGRADED_STATUSES:                                         # H4
            reasons.append(f"degraded:{method}:{status}")
        elif status in HEALTHY_STATUSES:
            healthy_families.add(_family(row))
        else:
            reasons.append(f"unknown_status:{method}:{status}")
    if active and not healthy_families:                                         # H5
        reasons.append("no_healthy_method")
    for family in sorted(set(contributing_families) - healthy_families):        # H6
        reasons.append(f"contributing_family_unhealthy:{family}")
    return HealthDecision(healthy=not reasons, reasons=tuple(reasons))
