"""Rotating record coverage for the Acrobat community collector (R4-ACR).

THE DEFECT THIS CLOSES
----------------------
The collector walked its 199 records per edition newest-first and stopped on a 1200 s deadline after
about 10 of them. Measured on 12 scheduled runs (2026-11-20..26): Pro attempted 11.0 records a run on
average, Reader 10.1, always the same newest handful. On 2026-11-26 that left 202 of 398 Acrobat pages
reading COLLECTION STALE (last reached by a one-off dispatch in August-October) and 153 more that the
collector had NEVER attempted. A newest-first walk under a fixed budget is a ceiling on reach, not an
order: everything below the head is stranded for good.

WHAT THIS DOES INSTEAD
----------------------
It reallocates the SAME budget. Per edition and per untargeted run:

  1. Recent window: the `RECENT_WINDOW` newest records by release. Its `RECENT_SLOTS` least-recently-
     checked members go first, so each recent release is revisited every ceil(W / R) runs.
  2. Fill: every other record, least-recently-checked first.
  3. Cap: the walk stops after `max_records_per_run()` records (default 10, below the measured mean),
     so Adobe Community requests per run cannot rise: the method's per-record request count is fixed.

The walk state is the `last_run` the collector already writes on each record's
`adobe_community_algolia_search` row in `_data/evidence_method_health.yml`. No new file and no new
writer: the store the writeback already commits IS the rotation cursor.

DETERMINISM. Every order is a sort on (last check, release date, version) -- never on array position,
whose ties are arbitrary (memory array-position-is-not-chronology). A missing, unparseable or future
timestamp counts as "never checked", which sorts first: a record whose telemetry is unusable is the one
that most needs a visit, and a future stamp must not hide a record for ever.

Pure module: callers pass the records, the stored rows and `now`. Nothing here reads the network.
"""
from __future__ import annotations

import math
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from .patch_identity import patch_key

PRIMARY_METHOD = "adobe_community_algolia_search"
RECENT_WINDOW = 4
RECENT_SLOTS = 2
DEFAULT_MAX_RECORDS_PER_RUN = 10
MAX_RECORDS_ENV = "AUXSAYS_ACROBAT_MAX_RECORDS_PER_RUN"
# Scheduled runs GitHub actually delivered: 20 in 9.4 days (2026-11-17..26) = 2.1/day against a 4/day
# cron; rounded down. Used only to state the revisit bound in days against the freshness window.
DELIVERED_RUNS_PER_DAY = 2.0
# Requests one record can cost the primary method: 1 searchToken + up to MAX_ALGOLIA_QUERIES (3)
# Algolia queries + 1 getTopics batch. Stated here for the ceiling arithmetic; the collector's own
# constants are what bound it, and the replay test pins that the two agree.
MAX_REQUESTS_PER_RECORD = 5
NEVER = float("-inf")


def max_records_per_run(env: Mapping[str, str] | None = None) -> int:
    """The per-edition, per-run record cap. Invalid or non-positive values fall back to the default:
    a typo must not silently remove the bound that keeps Adobe requests from rising."""
    raw = str((os.environ if env is None else env).get(MAX_RECORDS_ENV) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_RECORDS_PER_RUN
    return value if 0 < value <= DEFAULT_MAX_RECORDS_PER_RUN else DEFAULT_MAX_RECORDS_PER_RUN


def _epoch(value: Any, now: datetime) -> float:
    raw = str(value or "").strip()
    if not raw:
        return NEVER
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return NEVER
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    stamp = moment.timestamp()
    return NEVER if stamp > now.timestamp() else stamp


def last_checked(product_id: str, rows: Iterable[Mapping[str, Any]], now: datetime) -> dict[tuple[str, str, str], float]:
    """{patch key: epoch of the latest usable primary-method attempt} for one edition."""
    out: dict[tuple[str, str, str], float] = {}
    for row in rows:
        if str(row.get("product_id") or "") != product_id or row.get("method_id") != PRIMARY_METHOD:
            continue
        key = patch_key(product_id, row.get("update_version"), row.get("target_build"))
        stamp = _epoch(row.get("last_run"), now)
        if stamp > out.get(key, NEVER):
            out[key] = stamp
    return out


def _key(record: Any) -> tuple[str, str, str]:
    return patch_key(record.product_id, record.update_version, getattr(record, "target_build", ""))


def _release_desc(record: Any) -> tuple[str, str]:
    return (str(getattr(record, "update_published_at", "") or ""), str(record.update_version or ""))


def _lru_sorted(records: Sequence[Any], checked: Mapping[tuple[str, str, str], float]) -> list[Any]:
    # Release date and version DESCENDING inside a timestamp tie, done as two stable sorts so no
    # string has to be negated: first newest-first, then (stable) by last check ascending.
    by_release = sorted(records, key=_release_desc, reverse=True)
    return sorted(by_release, key=lambda r: checked.get(_key(r), NEVER))


def recent_slots_for(cap: int | None, slots: int = RECENT_SLOTS) -> int:
    """Recent-window picks a run can afford while leaving at least ONE slot for the rest of the corpus.

    A lowered cap (the documented way to shed Adobe load) must not hand every slot to the newest
    records: at cap 1 or 2 with two recent picks the fill got nothing and 195 of 199 records were never
    reached again. So the recent window keeps at most cap - 1 picks; at cap 1 it gets none and the
    whole corpus is one least-recently-checked pool, the newest included, so nothing starves."""
    if cap is None:
        return max(0, slots)
    return max(0, min(slots, cap - 1))


def rotation_order(records: Sequence[Any], rows: Iterable[Mapping[str, Any]], now: datetime, *,
                   window: int = RECENT_WINDOW, slots: int = RECENT_SLOTS,
                   cap: int | None = None) -> list[Any]:
    """Every record exactly once: recent picks, then the least-recently-checked fill, then the
    recent-window members not picked this run. The caller's cap decides how far the walk gets; passing
    it here also keeps at least one fill slot (see `recent_slots_for`).

    A FAILED attempt counts as a check. The collector stamps `last_run` on a blocked/broken row as on a
    successful one, and the rotation does not move failed records to the front: a failure here is
    almost always the source refusing or an outage, and re-trying the same records first would spend a
    capped budget against a refusing source while the tail stalls. The failed row stays visible as
    broken/blocked, and the record is retried within one revisit bound."""
    if not records:
        return []
    product_id = records[0].product_id
    checked = last_checked(product_id, rows, now)
    picks_n = recent_slots_for(cap, slots)
    if picks_n == 0 and cap is not None:
        return _lru_sorted(list(records), checked)
    newest = sorted(records, key=_release_desc, reverse=True)
    recent = newest[:max(0, window)]
    recent_ids = {id(r) for r in recent}
    recent_lru = _lru_sorted(recent, checked)
    picks, held = recent_lru[:picks_n], recent_lru[picks_n:]
    fill = _lru_sorted([r for r in records if id(r) not in recent_ids], checked)
    return picks + fill + held


def revisit_bound_runs(total: int, cap: int, *, window: int = RECENT_WINDOW,
                       slots: int = RECENT_SLOTS) -> int:
    """Worst case, in runs, before a record outside the recent window is attempted again, when every
    run attempts `cap` records. Always finite for cap >= 1 (see `recent_slots_for`)."""
    cap = max(1, int(cap))
    recent = min(window, total)
    picks = min(recent_slots_for(cap, slots), recent)
    if picks == 0:
        return math.ceil(total / cap) if total else 0
    fill_population = total - recent
    if fill_population <= 0:
        return math.ceil(recent / picks)
    return math.ceil(fill_population / (cap - picks))


def revisit_bound_days(bound_runs: int, runs_per_day: float) -> float:
    return round(bound_runs / runs_per_day, 1) if runs_per_day > 0 else float("inf")


def coverage_state(records: Sequence[Any], rows: Iterable[Mapping[str, Any]], now: datetime,
                   thresholds: Any) -> dict[str, Any]:
    """Stale / never-attempted counts for one edition, by the repo's own monitoring ladder."""
    from . import monitoring_health as mh  # noqa: PLC0415
    rows = list(rows)
    states: Counter[str] = Counter()
    never = 0
    oldest = None
    if records:
        checked = last_checked(records[0].product_id, rows, now)
    else:
        checked = {}
    for record in records:
        ident = {"product_id": record.product_id, "update_version": record.update_version,
                 "target_build": getattr(record, "target_build", "")}
        states[mh.ladder(mh.rows_for(ident, rows), published_at=record.update_published_at,
                         report_count=0, now=now, thresholds=thresholds)] += 1
        stamp = checked.get(_key(record), NEVER)
        if stamp == NEVER:
            never += 1
        elif oldest is None or stamp < oldest:
            oldest = stamp
    return {
        "records_total": len(records),
        "stale_remaining": states.get(mh.COLLECTION_STALE, 0),
        "never_attempted_remaining": never,
        "oldest_last_checked": (datetime.fromtimestamp(oldest, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                                if oldest is not None else ""),
    }


def coverage_summary(product_id: str, rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """The latest run's telemetry for one edition, recomputed from the PERSISTED primary-method rows
    (those carrying the newest `last_run`). This is what makes the stored rows the telemetry: a run
    summary can be rebuilt from the committed store without the run's log."""
    primary = [r for r in rows if str(r.get("product_id") or "") == product_id
               and r.get("method_id") == PRIMARY_METHOD]
    if not primary:
        return {"product_id": product_id, "last_run": "", "records_attempted": 0}
    latest = max(str(r.get("last_run") or "") for r in primary)
    run = [r for r in primary if str(r.get("last_run") or "") == latest]
    reasons: Counter[str] = Counter()
    for r in run:
        reasons.update({str(k): int(v) for k, v in (r.get("rejection_reasons") or {}).items()})
    measured = [r for r in run if r.get("requests") is not None]
    return {
        "product_id": product_id,
        "last_run": latest,
        "records_attempted": len(run),
        "successful_searches": sum(1 for r in run if str(r.get("status") or "") in
                                   {"success", "no_results", "partial", "low_confidence"}),
        "accepted_reports": sum(int(r.get("accepted_reports") or 0) for r in run),
        "rejection_reasons": dict(sorted(reasons.items())),
        # None, not 0, when no row of the run measured requests: an unmeasured cost is not a free one.
        "requests": sum(int(r["requests"]) for r in measured) if measured else None,
    }
