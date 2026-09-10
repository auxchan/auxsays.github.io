"""State helpers for idempotent patch ingestion and source health.

The ingestion state is the operational ledger for AUXSAYS official-source
fetching. It should answer two separate questions:

1. Have we already written this specific patch record?
2. Is this source currently healthy, degraded, failing, disabled, or staged?
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Seen-history retention per source. This MUST be at least as large as the widest
# candidate scan window any enabled source can use, so that no record identity that
# is still inside an active scan window is evicted from `seen` and then re-ingested
# on the next run (which would burn the per-run write budget and churn files).
#
# The default scan window is patch_ingest.BACKFILL_SCAN_LIMIT (200); a source may
# only NARROW it via ingestion.scan_limit (validated to be <= this value), so 200
# covers every permitted window. Kept as an explicit constant here (rather than
# imported from patch_ingest) to avoid a circular import; patch_ingest asserts
# BACKFILL_SCAN_LIMIT <= SEEN_RETENTION so the two cannot silently drift apart.
SEEN_RETENTION = 200


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" so Python's text layer does not translate "\n" to the platform separator. This is
    # a TRACKED data file, and `test_teams_record_cleanup` requires it to be LF-only; an ingestion
    # run on Windows rewrote all 2034 line endings as CRLF and turned that suite red, with a diff
    # touching every line of the file. Production runs on Linux, where the bug is invisible.
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="")


def source_state(state: dict[str, Any], product_id: str) -> dict[str, Any]:
    sources = state.setdefault("sources", {})
    return sources.setdefault(product_id, {"seen": []})


def mark_seen(state: dict[str, Any], product_id: str, record_id: str) -> None:
    bucket = source_state(state, product_id)
    seen = bucket.setdefault("seen", [])
    if record_id not in seen:
        seen.insert(0, record_id)
        del seen[SEEN_RETENTION:]


def is_seen(state: dict[str, Any], product_id: str, record_id: str) -> bool:
    return record_id in source_state(state, product_id).get("seen", [])


# How many consecutive checks a source may produce NO RECORD on before that silence is treated as
# rot rather than as a quiet period. This is not a release-cadence threshold and must not be read as
# one: it counts CHECKS, not days, so it means "this source has been asked N times in a row and
# produced nothing". A source may override it when its own publishing rhythm makes a longer silence
# normal (`ingestion.empty_extraction_tolerance`).
#
# A FAILED FETCH COUNTS TOO. The question this counter answers is "how long since this source last
# gave us a record", and a 403 answers it just as much as an empty parse does. Counting only the
# empty parses would restart the clock whenever a source changed failure mode -- which is exactly
# what the four Elgato sources did: they served HTTP 403 for 13 consecutive runs, then recovered
# transport and began fetching 30 articles and extracting 0 from them. Nothing about that sequence
# is a source that has been quiet for one check.
#
# 12 is deliberately generous. Ingestion runs on a 6-hourly chain, so 12 consecutive empties is
# roughly three days of a source returning a page that yields no record at all. Netlify has been in
# that state since 2026-04-29.
DEFAULT_EMPTY_EXTRACTION_TOLERANCE = 12


def classify_success(fetched: int, written: int, skipped: int,
                     *, consecutive_empty: int = 0,
                     tolerance: int = DEFAULT_EMPTY_EXTRACTION_TOLERANCE,
                     ever_extracted: bool = False) -> str:
    """Classify a successful adapter run without pretending every success is equal.

    A FETCH that succeeds is not an EXTRACTION that succeeded, and the difference is the whole
    point of this function. Four outcomes, where there used to be two:

      healthy     records came back.
      no_results  the fetch worked and produced nothing, and that is still plausibly normal --
                  the source simply has not published since the last check.
      stale       it USED to extract records and has now produced nothing `tolerance` times in a
                  row. Something changed after it was working.
      broken      it has produced nothing `tolerance` times in a row and has NEVER extracted a
                  record. That is not a quiet period; the extractor has never matched this source.

    `stale` and `broken` are separated on purpose. They need different repairs -- one is a source
    that moved, the other is an extractor that never fitted -- and collapsing them would hide which
    of the two you are looking at.

    THIS DISTINCTION IS THE DEFECT THIS FUNCTION EXISTS TO CLOSE. It used to return `degraded` for
    every zero-extraction run, with a note that said the state "can mean no new updates or that the
    parser needs review" -- i.e. it recorded that it could not tell the two apart, and then let the
    run report success anyway. Measured on Netlify at 3a47e1f8: `www.netlify.com/changelog/` returns
    HTTP 200 and 152 KB containing 41 `/changelog/` links, and `NETLIFY_DETAIL_RE` in
    `adapters/html_changelog.py` requires `/changelog/YYYY/M/D/slug/`. Zero of the 41 match, because
    the site moved to slug-only URLs. The fetch is perfect, the extractor matches nothing, and every
    run since has reported `status: "success"`.
    """
    if fetched > 0:
        return "healthy"
    if consecutive_empty > max(0, int(tolerance)):
        return "stale" if ever_extracted else "broken"
    return "no_results"


def update_source_success(
    state: dict[str, Any],
    product_id: str,
    *,
    checked_at: str,
    duration_ms: int,
    adapter: str,
    fetched: int,
    written: int,
    skipped: int,
    tolerance: int = DEFAULT_EMPTY_EXTRACTION_TOLERANCE,
) -> None:
    bucket = source_state(state, product_id)
    previous_failures = int(bucket.get("consecutive_failures") or 0)
    consecutive_empty = 0 if fetched > 0 else int(bucket.get("consecutive_empty_extractions") or 0) + 1
    status = classify_success(fetched, written, skipped,
                              consecutive_empty=consecutive_empty, tolerance=tolerance,
                              ever_extracted=bool(bucket.get("last_extraction_at")))
    bucket.update({
        "status": status,
        "last_checked_at": checked_at,
        # `last_success_at` means the FETCH succeeded. It deliberately no longer carries the weight
        # of "this source is working": Netlify's fetch has succeeded on every run for months while
        # extracting nothing, so a reader looking only at this field saw a source that was healthy
        # as of today. `last_extraction_at` below is the field that answers "when did this source
        # last actually produce a record".
        "last_success_at": checked_at,
        "last_error_at": "",
        "last_error": "",
        "last_error_type": "",
        "consecutive_failures": 0,
        "previous_consecutive_failures": previous_failures,
        "consecutive_empty_extractions": consecutive_empty,
        "last_adapter": adapter,
        "last_records_fetched": int(fetched),
        "last_records_written": int(written),
        "last_records_skipped": int(skipped),
        "last_run_duration_ms": int(duration_ms),
    })
    if fetched > 0:
        bucket["last_extraction_at"] = checked_at
        bucket["last_extraction_records"] = int(fetched)
        bucket["last_health_note"] = "Fetch succeeded."
    elif status in ("broken", "stale"):
        ever = "has never extracted a record" if status == "broken" else (
            f"last extracted a record at {bucket.get('last_extraction_at')}")
        bucket["last_health_note"] = (
            f"Fetch succeeded but extracted no records on {consecutive_empty} consecutive checks, "
            f"and this source {ever}. The page is reachable and the extractor is matching nothing "
            "in it, which points at a changed page structure rather than a quiet period.")
    else:
        bucket["last_health_note"] = (
            "Fetch succeeded and extracted no records. Still within the tolerated quiet window for "
            "this source.")


def update_source_error(
    state: dict[str, Any],
    product_id: str,
    *,
    checked_at: str,
    duration_ms: int,
    adapter: str,
    error: str,
) -> None:
    bucket = source_state(state, product_id)
    failures = int(bucket.get("consecutive_failures") or 0) + 1
    # A failed fetch produced no record, so it advances the no-record streak as well. Resetting it
    # only on a real extraction is what keeps a mode-change (blocked -> fetches-but-parses-nothing)
    # from looking like a fresh, quiet source.
    empty_streak = int(bucket.get("consecutive_empty_extractions") or 0) + 1
    bucket.update({
        "consecutive_empty_extractions": empty_streak,
        "status": "failing" if failures >= 2 else "degraded",
        "last_checked_at": checked_at,
        "last_error_at": checked_at,
        "last_error": error,
        "last_error_type": classify_error(error),
        "consecutive_failures": failures,
        "last_adapter": adapter,
        "last_records_fetched": 0,
        "last_records_written": 0,
        "last_records_skipped": 0,
        "last_run_duration_ms": int(duration_ms),
        "last_health_note": "Fetch failed. Review source availability, adapter timeout, or parser behavior.",
    })


def classify_error(error: str) -> str:
    text = (error or "").lower()
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "403" in text or "forbidden" in text:
        return "blocked"
    if "404" in text or "not found" in text:
        return "not_found"
    if "ssl" in text or "certificate" in text:
        return "tls_error"
    if "parse" in text or "selector" in text:
        return "parser_error"
    if "connection" in text or "network" in text:
        return "network_error"
    return "error"
