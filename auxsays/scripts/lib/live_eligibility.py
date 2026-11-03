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

The same function decides what a WRITER stores. Every record writer holds a `RunContext` for its
run and `maturity.record_maturity` asks it, so a certifying identity is written live, and a live
record whose monitoring stops is written back to Verified reports, by whichever writer runs next --
there is no second eligibility rule for the lanes to drift from the projection's.

Pure: callers hand in the record, the WHOLE counted population, the method-health rows, `now` and
the thresholds. Reading them is `load_inputs` / `load_run_context`, kept separate so every decision
is reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from patch_collectors.base import load_front_matter_and_body, normalize_url

from . import collector_ownership, maturity, monitoring_health
from .evidence_classification import VALID_SENTIMENTS, VALID_SEVERITIES
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
    # (e) The population must be PUBLISHABLE as a live claim. The consensus writer refuses to project
    # a counted row with no URL, a failed source date, or a sentiment/severity outside its vocabulary
    # (gate_11/16/17), and QA requires a live claim's citations to be valid, distinct http(s) URLs.
    # Certifying an identity the writer cannot project turned a tolerated warning into QA errors that
    # discard a whole cycle's evidence -- so such an identity is simply not live until it is fixed.
    unprojectable = [row for row in rows if not _projectable(row)]
    if unprojectable:
        reasons.append(f"unprojectable_rows:{len(unprojectable)}")
    urls = [normalize_url(str(row.get("source_url") or "")) for row in rows]
    if len(set(urls)) != len(urls):
        reasons.append("duplicate_citation_urls")
    return maturity.LiveDecision(live=not reasons, reasons=tuple(reasons))


def _projectable(row: Mapping[str, Any]) -> bool:
    url = str(row.get("source_url") or "").strip().lower()
    return (url.startswith(("http://", "https://"))
            and row.get("source_date_pass") is not False
            and str(row.get("sentiment") or "").strip().lower() in VALID_SENTIMENTS
            and (str(row.get("severity") or "").strip().lower() or "low") in VALID_SEVERITIES)


@dataclass(frozen=True)
class RunContext:
    """One writer run's eligibility inputs: the WHOLE counted population (every product, so
    exclusivity is judged against everything), the method-health rows, the thresholds and ONE
    instant. `maturity.record_maturity` consults `decide`; a writer holding no context never promotes.

    `unavailable` names why the telemetry or config could not be read. A context carrying it declines
    every identity -- fail closed, and never a raise: a writer that crashed would discard the whole
    cycle's evidence to protect a label."""
    counted_groups: Mapping[Key, list[dict[str, Any]]]
    emh_rows: tuple[Mapping[str, Any], ...]
    thresholds: monitoring_health.Thresholds | None
    now: datetime
    unavailable: str = ""
    _exclusive: dict[Key, int] = field(init=False, repr=False, compare=False)
    _emh_by_key: dict[Key, list[Mapping[str, Any]]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Once per run, not once per record: a reconcile asks about every record in the tree.
        object.__setattr__(self, "_exclusive", exclusive_url_counts(self.counted_groups))
        by_key: dict[Key, list[Mapping[str, Any]]] = {}
        for row in self.emh_rows:
            try:
                by_key.setdefault(key_from(row), []).append(row)
            except Exception:  # noqa: BLE001 - an unkeyable telemetry row answers for no identity
                continue
        object.__setattr__(self, "_emh_by_key", by_key)

    def bind(self, counted_groups: Mapping[Key, list[dict[str, Any]]]) -> "RunContext":
        """This context over `counted_groups` -- the population the calling writer is counting, so
        its decisions and its counts can never come from two different readings of the store."""
        return replace(self, counted_groups=counted_groups)

    def bind_evidence(self, rows: Iterable[Mapping[str, Any]],
                      records: Iterable[Mapping[str, Any]]) -> "RunContext":
        """`bind` the authoritative counted population of `rows`, gated against `records` (full
        front matter). A store the authority refuses to group declines everything instead of raising."""
        try:
            groups = counted_evidence_rows(
                rows, windows_targets=windows_targets_from_front_matter(records))
        except Exception as exc:  # noqa: BLE001 - see the class docstring
            return replace(self, counted_groups={},
                           unavailable=f"population:{type(exc).__name__}")
        return self.bind(groups)

    def decide(self, record: Mapping[str, Any] | None,
               counted_rows: Iterable[Mapping[str, Any]] | None = None) -> maturity.LiveDecision:
        """`evaluate` for one record, from this run's population and instant. When the writer hands
        in the rows it is counting, a count that differs from this population's declines: a decision
        about one population must not be written beside a count from another."""
        if self.unavailable or self.thresholds is None:
            return maturity.LiveDecision(False, (f"context_unavailable:{self.unavailable or 'thresholds'}",))
        if not record:
            return maturity.LiveDecision(False, ("no_record",))
        try:
            key = key_from(record)
            if counted_rows is not None:
                mine, theirs = len(self.counted_groups.get(key, ())), len(list(counted_rows))
                if mine != theirs:
                    return maturity.LiveDecision(False, (f"population_mismatch:{theirs}!={mine}",))
            return evaluate(record, self.counted_groups, emh_rows=self._emh_by_key.get(key, ()),
                            now=self.now, thresholds=self.thresholds, exclusive=self._exclusive)
        except Exception as exc:  # noqa: BLE001 - see the class docstring
            return maturity.LiveDecision(False, (f"evaluation_failed:{type(exc).__name__}",))


def load_run_context(aux_root: Path, *, now: datetime,
                     counted_groups: Mapping[Key, list[dict[str, Any]]] | None = None) -> RunContext:
    """A writer's `RunContext`, reading `_data/evidence_method_health.yml` and `_config.yml` from
    the SAME site tree as the evidence store it counts. NEVER raises: unreadable telemetry or config
    returns a context that declines everything and names why (`unavailable`). The population is
    usually bound afterwards (`bind` / `bind_evidence`) from the rows the writer actually counts."""
    aux_root = Path(aux_root)
    groups = counted_groups if counted_groups is not None else {}
    try:
        emh_rows = tuple(monitoring_health.load_method_health_rows(
            aux_root / "_data" / "evidence_method_health.yml"))
        thresholds = monitoring_health.load_thresholds(aux_root / "_config.yml")
    except Exception as exc:  # noqa: BLE001 - see RunContext
        return RunContext(groups, (), None, now, unavailable=f"{type(exc).__name__}: {exc}"[:200])
    return RunContext(groups, emh_rows, thresholds, now)


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
