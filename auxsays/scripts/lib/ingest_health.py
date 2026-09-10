#!/usr/bin/env python3
"""Run-level ingestion health: what a green workflow is allowed to mean.

THE DEFECT THIS CLOSES
----------------------
`patch_ingest.py` returned 0 unless `--strict` was passed, and production never passed it. So an
enabled source could fail on every run and the GitHub Actions conclusion stayed **success**.
Measured on production run 34391487960: four enabled Elgato sources emitted
`HTTP 403 while fetching official source`, the job logged four `[ERROR]` lines, and the run
concluded `success`. A green ingestion lane was not evidence that official patch discovery worked.

A blanket `--strict` is NOT the repair, for two reasons. It exits non-zero when ANY enabled source
errors, which would leave the lane permanently red for as long as one vendor blocks us -- and it
also `break`s out of the source loop on the first error, discarding valid discovery from every
source that had not run yet. Trading silent-green for all-or-nothing is not an improvement.

WHAT THIS MODULE DOES INSTEAD
-----------------------------
Collect from every enabled source, persist honest per-source health, then classify the RUN:

  healthy   every enabled source that ran is healthy, or legitimately quiet (`no_results`).
  degraded  at least one enabled source is blocked / broken / failing, AND at least one produced
            trustworthy output. Exit 0 -- the healthy vendors' discovery is real and must not be
            thrown away -- but the run says so loudly, in an annotation and the step summary.
  failed    no enabled source produced trustworthy ingestion this run, or a critical invariant
            broke. Exit non-zero: there is nothing to trust.

The rule the directive asks for is that persisted telemetry and the workflow conclusion must not
contradict each other. `degraded` is the state GitHub cannot express natively, so it is expressed as
a visible warning annotation plus a summary table rather than as an undifferentiated green tick.

DISABLED SOURCES CANNOT POISON PRODUCTION HEALTH. Only sources that actually ran under the enabled
gate are scored; a `--all` dry-run probe of a staged source is reported but never changes the
verdict.

TWO BOUNDARIES THIS DELIBERATELY DOES NOT CLOSE, stated so nobody mistakes them for coverage:

* PARTIAL ROT IS INVISIBLE. `records_fetched` is `candidate_count` -- the rows an adapter parsed off
  a listing page -- not records written. An extractor that keeps matching one stale entry every run
  forever never advances the no-record streak, so a source that has half-rotted reads as healthy.
  Detecting that needs per-adapter instrumentation (the Elgato adapter already emits `parser_misses`
  and `no_matching_articles`; most do not), which is a wider change than this one.

* DEGRADED IS NOT ESCALATED BY AGE. A source that has failed for 73 consecutive runs produces the
  same `degraded` run verdict as one failing for the first time, and the run still exits 0 -- by
  design, because the healthy vendors' records in that same run are real. The escalation that does
  happen is on the PUBLIC surface: `source_health_snapshot.status_for` now publishes such a source
  as `Error` with the date it last extracted anything, instead of `Active / No new records`. If a
  time-based run-level escalation is wanted later, the streak needed for it is already persisted.
"""
from __future__ import annotations

import os
from typing import Any

RUN_HEALTHY = "healthy"
RUN_DEGRADED = "degraded"
RUN_FAILED = "failed"
# Nothing was in scope, so this run is not evidence of anything. It is NOT health, and it must never
# overwrite a real verdict: a `--source` typo used to persist `healthy` over a stored `failed` while
# the per-source buckets in the same file still read `failing, consecutive_failures: 13`.
RUN_NOT_EVALUATED = "not-evaluated"

# Per-source statuses that represent trustworthy output from this run.
TRUSTWORTHY = {"healthy", "no_results"}


def _bucket(state: dict[str, Any], product_id: str) -> dict[str, Any]:
    return ((state or {}).get("sources") or {}).get(product_id) or {}


def observed_status(result: dict[str, Any] | None, error: dict[str, Any] | None,
                    prior: dict[str, Any], *, tolerance: int | None = None) -> str:
    """The status THIS run observed, independent of whether the run was allowed to persist it.

    THIS IS THE FIX FOR THE WORST BUG IN THE FIRST VERSION OF THIS MODULE. Health used to be read
    straight out of the persisted bucket -- but `update_source_success` / `update_source_error` are
    both gated on `if not args.dry_run`, so a DRY RUN graded this run's sources against the previous
    production run's telemetry. Reproduced: one enabled source whose adapter always raises
    `HTTP 403`, with a state file saying `healthy`, produced

        [ERROR] alpha: HTTP 403 while fetching official source
        "run_health": "healthy"                 exit 0
        step summary: "All enabled official sources are collecting normally."

    which is the original silent-green defect upgraded into an affirmative false claim. Deriving the
    status from what the run actually saw makes a dry run as truthful as a write run, and leaves the
    write path's behaviour identical because it observes exactly what it persists.
    """
    from lib.state import DEFAULT_EMPTY_EXTRACTION_TOLERANCE, classify_error, classify_success
    if error is not None:
        # Two consecutive failures is `failing`; a first is `degraded`. Either way, impaired.
        return "failing" if int(prior.get("consecutive_failures") or 0) >= 1 else "degraded"
    if result is None:
        return "unknown"
    fetched = int(result.get("candidate_count") or 0)
    streak = 0 if fetched > 0 else int(prior.get("consecutive_empty_extractions") or 0) + 1
    return classify_success(
        fetched, 0, 0, consecutive_empty=streak,
        tolerance=DEFAULT_EMPTY_EXTRACTION_TOLERANCE if tolerance is None else int(tolerance),
        ever_extracted=bool(prior.get("last_extraction_at")))


def source_rows(state: dict[str, Any], attempted: list[dict[str, Any]],
                results: list[dict[str, Any]] | None = None,
                errors: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """One structured health row per source that ran, scored on THIS RUN'S observation.

    Persisted state supplies only the history a single run cannot see for itself -- the no-record
    streak and the last real extraction. The status, the error and the counts come from what just
    happened, so a dry run cannot inherit yesterday's verdict.

    Every field exists to make a failure diagnosable without opening a log: which source, what kind
    of source, when it ran, what the transport did, what the extractor did, and how long it has been
    since the source last actually produced a record -- which is NOT the same question as when the
    fetch last succeeded, and conflating the two is what let Netlify look current for months.
    """
    by_result = {str(r.get("product_id") or ""): r for r in (results or [])}
    by_error = {str(e.get("product_id") or ""): e for e in (errors or [])}
    rows: list[dict[str, Any]] = []
    for source in attempted:
        pid = str(source.get("product_id") or "")
        ing = source.get("ingestion") or {}
        b = _bucket(state, pid)
        res, err = by_result.get(pid), by_error.get(pid)
        status = observed_status(res, err, b, tolerance=ing.get("empty_extraction_tolerance"))
        fetched = int((res or {}).get("candidate_count") or 0)
        streak = 0 if fetched > 0 else int(b.get("consecutive_empty_extractions") or 0) + (
            0 if res is None and err is None else 1)
        rows.append({
            "source_id": pid,
            "product_id": pid,
            "company_id": str(source.get("company_id") or ""),
            "source_type": str(ing.get("type") or ing.get("adapter") or "unknown"),
            "adapter": str((res or {}).get("adapter") or b.get("last_adapter") or ing.get("adapter") or ""),
            "enabled": bool(source.get("enabled")),
            "checked_at": str(b.get("last_checked_at") or ""),
            "status": status,
            "error_type": str((err or {}).get("error_type") or b.get("last_error_type") or ""),
            "error": str((err or {}).get("error") or ""),
            "records_fetched": fetched,
            "records_written": int(len((res or {}).get("written") or []) or 0),
            "consecutive_failures": int(b.get("consecutive_failures") or 0) + (1 if err else 0),
            "consecutive_empty_extractions": streak,
            "last_success_at": str(b.get("last_success_at") or ""),
            "last_extraction_at": str(b.get("last_extraction_at") or ""),
            "health_note": str(b.get("last_health_note") or ""),
        })
    return rows


def classify_run(rows: list[dict[str, Any]]) -> str:
    """The run verdict, from the per-source rows of the sources that were ENABLED and ran."""
    scored = [r for r in rows if r.get("enabled")]
    if not scored:
        return RUN_NOT_EVALUATED
    impaired = [r for r in scored if r["status"] not in TRUSTWORTHY]
    produced = any(int(r.get("records_fetched") or 0) > 0 for r in scored)
    if not impaired:
        # Everything either delivered or was legitimately quiet. A fleet that is simply quiet today
        # is healthy; silence is only alarming once a source's own streak says so, and that is
        # already decided per source.
        return RUN_HEALTHY
    if not produced:
        # Something is impaired AND the whole run produced no record at all. `no_results` is not
        # output: an earlier version counted it as trustworthy, so a fleet where 15 of 16 sources
        # hard-failed and one returned an empty page exited 0 as "degraded".
        return RUN_FAILED
    return RUN_DEGRADED


def summarise(rows: list[dict[str, Any]], verdict: str) -> str:
    """A human-readable summary for the workflow step summary. Plain language, no raw enums."""
    scored = [r for r in rows if r.get("enabled")]
    ok = [r for r in scored if r["status"] in TRUSTWORTHY]
    bad = [r for r in scored if r["status"] not in TRUSTWORTHY]
    headline = {
        RUN_HEALTHY: "All enabled official sources are collecting normally.",
        RUN_DEGRADED: (f"{len(bad)} of {len(scored)} enabled official sources are not collecting. "
                       f"The other {len(ok)} completed normally and their records were kept."),
        RUN_FAILED: "No enabled official source produced usable output on this run.",
        RUN_NOT_EVALUATED: ("No enabled official source was in scope for this run, so it says "
                            "nothing about collection health either way."),
    }.get(verdict, f"Unrecognised run verdict: {verdict}.")
    lines = [f"### Official source collection: {verdict.upper()}", "", headline, ""]
    if scored:
        lines += ["| Source | Type | Status | Fetched | Last extraction | Detail |",
                  "| --- | --- | --- | ---: | --- | --- |"]
        for r in sorted(scored, key=lambda x: (x["status"] in TRUSTWORTHY, x["source_id"])):
            detail = r["error"] or r["health_note"] or ""
            lines.append(
                f"| `{r['source_id']}` | {r['source_type']} | {r['status']} | {r['records_fetched']} "
                f"| {r['last_extraction_at'] or 'never'} | {detail[:120]} |")
    return "\n".join(lines) + "\n"


def annotate(rows: list[dict[str, Any]], verdict: str, *, emit=print) -> None:
    """GitHub annotations, so a degraded run is visible on the run page and not only in a file."""
    for r in sorted(rows, key=lambda x: x["source_id"]):
        if not r.get("enabled") or r["status"] in TRUSTWORTHY:
            continue
        why = r["error"] or r["health_note"] or r["status"]
        emit(f"::warning title=Ingestion source {r['status']}::{r['source_id']}: {why[:180]}")
    if verdict == RUN_FAILED:
        emit("::error title=Ingestion failed::No enabled official source produced usable output.")
    elif verdict == RUN_DEGRADED:
        bad = [r["source_id"] for r in rows if r.get("enabled") and r["status"] not in TRUSTWORTHY]
        emit(f"::warning title=Ingestion degraded::{len(bad)} enabled source(s) not collecting: "
             f"{', '.join(sorted(bad))}")


def write_step_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)
