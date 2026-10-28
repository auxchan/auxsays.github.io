"""Live-consensus ELIGIBILITY: may this patch identity's community evidence be presented as live?

A stored live claim is a writer's statement, made when the writer last ran. The page is rendered
later, and between the two the pipeline behind the claim can stop: a method goes stale, a family
is blocked, a report is withdrawn. So the claim is never trusted on its own -- every surface renders
"Live consensus" only for an identity this module certifies at deploy time
(`build_live_eligibility_projection.py` -> `_data/live_eligibility.yml`). Anything else, including a
stored claim that no longer certifies, falls back to "Verified reports".

ALL of these are required, and each failure is named:

  a  the product is one whose projections the lane rebuilds and retracts
     (`report_counts.CONSENSUS_PROMOTION_PRODUCTS`); a live claim no lane maintains could only be
     corrected by hand
  b  at least `maturity.LIVE_MIN_ACCEPTED_REPORTS` counted reports for this exact identity -- the
     published High strength rung, not a new threshold
  c  at least that many distinct patch-specific report URLs not counted on another identity (any
     product). A thread counted for two versions is evidence about neither in particular, so it
     cannot carry a claim of mature consensus about one of them. This counts URLs; it says
     nothing about how many different PEOPLE wrote them
  d  `monitoring_health.certify_monitoring` (H0-H7) passes for this identity, judged over the
     families its counted reports actually came from

Pure: callers hand in the record, the WHOLE counted population, the method-health rows, `now` and
the thresholds. Reading them is `load_inputs`, kept separate so every decision is reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from patch_collectors.base import load_front_matter_and_body, normalize_url

from . import collector_ownership, maturity, monitoring_health
from .patch_identity import key_from
from .report_counts import (CONSENSUS_PROMOTION_PRODUCTS, counted_evidence_rows,
                            load_evidence_store, windows_targets_from_front_matter)

Key = tuple[str, str, str]


def _url(row: Mapping[str, Any]) -> str:
    return normalize_url(str(row.get("source_url") or ""))


def exclusive_url_counts(counted_groups: Mapping[Key, Iterable[Mapping[str, Any]]]) -> dict[Key, int]:
    """Per identity, the number of distinct patch-specific report URLs not counted on another
    identity. Computed over the whole population at once so a writer pays for it once per run.

    A row with no URL cannot be shown to belong to one identity only, so it never counts."""
    groups = {key: list(rows) for key, rows in counted_groups.items()}
    owners: dict[str, set[Key]] = {}
    for key, rows in groups.items():
        for row in rows:
            url = _url(row)
            if url:
                owners.setdefault(url, set()).add(key)
    return {key: sum(1 for url in {_url(row) for row in rows} if url and owners.get(url) == {key})
            for key, rows in groups.items()}


def evaluate(record: Mapping[str, Any], counted_groups: Mapping[Key, Iterable[Mapping[str, Any]]],
             *, emh_rows: Iterable[Mapping[str, Any]], now: datetime,
             thresholds: monitoring_health.Thresholds,
             exclusive: Mapping[Key, int] | None = None) -> maturity.LiveDecision:
    """Conditions a-d for one record. `counted_groups` is `report_counts.counted_evidence_rows`
    over EVERY product -- exclusivity is a property of the whole population, so a per-product slice
    would certify a URL another product also counts. `exclusive` is `exclusive_url_counts` of that
    same population, when the caller has already computed it.

    Every condition is evaluated even after one fails, so the run log names all of them."""
    reasons: list[str] = []
    product_id = str(record.get("product_id") or "").strip()
    key = key_from(record)
    rows = list(counted_groups.get(key, ()))

    if product_id not in CONSENSUS_PROMOTION_PRODUCTS:                         # a
        reasons.append("not_promotion_product")
    if len(rows) < maturity.LIVE_MIN_ACCEPTED_REPORTS:                         # b
        reasons.append(f"below_high_rung:{len(rows)}")
    if exclusive is None:
        exclusive = exclusive_url_counts(counted_groups)
    k = int(exclusive.get(key, 0))
    if k < maturity.LIVE_MIN_ACCEPTED_REPORTS:                                 # c
        reasons.append(f"exclusive_below_high_rung:{k}")
    health = monitoring_health.certify_monitoring(                            # d
        product_id, monitoring_health.rows_for(record, emh_rows),
        published_at=record.get("update_published_at"),
        contributing_families={str(row.get("source_type") or "") for row in rows},
        now=now, thresholds=thresholds,
        owned_methods=collector_ownership.ALLOWED_METHODS,
        manual_only_methods=collector_ownership.MANUAL_ONLY_METHODS)
    reasons.extend(f"monitoring:{reason}" for reason in health.reasons)
    return maturity.LiveDecision(live=not reasons, reasons=tuple(reasons))


@dataclass(frozen=True)
class Inputs:
    """Everything `evaluate` needs, read once from one site tree."""
    records: list[tuple[Path, dict[str, Any]]]
    counted_groups: dict[Key, list[dict[str, Any]]]
    emh_rows: list[dict[str, Any]]
    thresholds: monitoring_health.Thresholds


def load_inputs(aux_root: Path) -> Inputs:
    """The I/O half. Raises on a missing or malformed evidence store (`EvidenceStoreError`), a
    counted build-aware row with no build (`MissingBuildIdentity`), or unreadable telemetry or
    config -- never substitutes an empty population, which would read as "nothing is live" for the
    wrong reason. The caller decides what a refusal means."""
    aux_root = Path(aux_root)
    records = []
    for path in sorted((aux_root / "updates" / "generated").glob("*.md")):
        data, _body = load_front_matter_and_body(path)
        if isinstance(data, dict) and data.get("update_entry") is True:
            records.append((path, data))
    rows = load_evidence_store(aux_root / "_data" / "consensus_evidence.yml")
    groups = counted_evidence_rows(
        rows, windows_targets=windows_targets_from_front_matter(data for _p, data in records))
    return Inputs(
        records=records, counted_groups=groups,
        emh_rows=monitoring_health.load_method_health_rows(
            aux_root / "_data" / "evidence_method_health.yml"),
        thresholds=monitoring_health.load_thresholds(aux_root / "_config.yml"))
