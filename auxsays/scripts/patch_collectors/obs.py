"""OBS Studio evidence collector adapter.

OBS evidence comes from TWO independent source families, both judged by the same authority:

    github_issues  obsproject/obs-studio GitHub Issues   (the established family)
    obs_forum      obsproject.com support subforums      (added here)

"Independent" is by FAMILY, not by method count -- a second GitHub Issues query would have been
the same corpus behind a different name. These are different platforms with different authors,
and the forum is where a user who will never open a GitHub account goes.

Both families call collect_obs_reports.evaluate_issue and collect_obs_reports.evidence_row, so
neither can invent its own notion of what counts; a forum report and a GitHub issue differ in
where they were found, not in what counting them means. Both are written through one
write_evidence call, so a report discovered twice becomes duplicate telemetry, not a second row.
"""
from __future__ import annotations

import re
from typing import Any

import collect_obs_reports as legacy_obs
from lib import github_api

from .base import CollectorContext, ProductCollector, load_method_health, method_health_row, utc_now
from . import obs_forum_source as forum
from . import runtime_budget as rb

GITHUB_METHOD_ID = "github_issues"
FORUM_METHOD_ID = "obs_forum"

# WALK ORDER. Versions used to be walked in string order, oldest first, under a deadline that
# a normal run reaches after ~17 of 18 versions and a slow run after far fewer -- so the NEWEST
# release, the one a reader is deciding whether to install, was the one never refreshed: its rows
# sat frozen for days while still reading `success`. Now the newest few releases go first, and
# every other version follows least-recently-refreshed first, so the versions a run does not
# reach this time are the first ones the next run reaches. Deterministic for the same inputs.
NEWEST_FIRST = 3

_VERSION_PARTS_RE = re.compile(r"^(\d+(?:\.\d+){0,3})(?:([-+])(.*))?$")
_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def version_order_key(version: str) -> tuple:
    """Numeric release order: 33.10.0 after 33.9.0, and a pre-release before its release."""
    text = str(version or "").strip()
    match = _VERSION_PARTS_RE.match(text)
    if not match:
        return ((-1, -1, -1, -1), 0, "", text)
    numbers = tuple(int(part) for part in match.group(1).split("."))
    numbers = numbers + (0,) * (4 - len(numbers))
    rank = 0 if match.group(2) == "-" else 1
    return (numbers, rank, match.group(3) or "", text)


def _refresh_stamp(value: Any) -> str:
    """A comparable UTC second, or '' (never refreshed) for anything that is not one."""
    match = _STAMP_RE.match(str(value or "").strip())
    return match.group(0) if match else ""


def last_refreshed_by_version() -> dict[str, str]:
    """When each OBS version's monitoring rows were last written, from the committed health table.

    Both families are written together per version, so the OLDER of the two is used; a version
    missing either row has never been fully refreshed and reads as ''. Read-only. An unreadable
    table yields {} -- the order then falls back to newest-first throughout, still deterministic.
    """
    try:
        rows = load_method_health()
    except Exception:  # noqa: BLE001 -- ordering must never fail a collection run
        return {}
    stamps: dict[str, dict[str, str]] = {}
    for row in rows:
        if row.get("product_id") != legacy_obs.PRODUCT_ID:
            continue
        method = row.get("method_id")
        if method not in (GITHUB_METHOD_ID, FORUM_METHOD_ID):
            continue
        version = str(row.get("update_version") or "").strip()
        stamps.setdefault(version, {})[str(method)] = _refresh_stamp(row.get("last_run"))
    out: dict[str, str] = {}
    for version, by_method in stamps.items():
        if GITHUB_METHOD_ID in by_method and FORUM_METHOD_ID in by_method:
            out[version] = min(by_method[GITHUB_METHOD_ID], by_method[FORUM_METHOD_ID])
        else:
            out[version] = ""
    return out


def walk_order(versions, last_refreshed: dict[str, str]) -> list[str]:
    """The order a run processes versions in: newest NEWEST_FIRST first, then least recently refreshed.

    Ties among the rest (same stamp, or never refreshed) go newest first. A version is starved
    only if every run reaches no more than NEWEST_FIRST versions; any run that gets one further
    refreshes the stalest of the rest, which then moves to the back of the queue.
    """
    newest_first = sorted(set(versions), key=version_order_key, reverse=True)
    rank = {version: index for index, version in enumerate(newest_first)}
    head = newest_first[:NEWEST_FIRST]
    rest = sorted(newest_first[NEWEST_FIRST:],
                  key=lambda version: (_refresh_stamp(last_refreshed.get(version)), rank[version]))
    return head + rest


def coverage_fields(order: list[str], processed: list[str], skipped: list[str],
                    pool_stats: dict[str, int]) -> dict[str, Any]:
    """Which versions a run processed and skipped, plus the pool's fetched/parsed/failed/skipped counts.

    A skipped version gets no result and so no health row: its committed rows keep their old
    last_run, and the existing staleness rule decides when that stops counting as monitored. This
    makes the incomplete coverage diagnosable; it does not invent a status for it.
    """
    return {
        "versions_total": len(order),
        "versions_processed": len(processed),
        "versions_skipped": len(skipped),
        "processed": ",".join(processed),
        "skipped": ",".join(skipped),
        "threads_fetched": int(pool_stats.get("threads_requested") or 0),
        "threads_parsed": int(pool_stats.get("threads_in_pool") or 0),
        "threads_failed": int(pool_stats.get("threads_failed") or 0) + int(pool_stats.get("threads_unparsed") or 0),
        "threads_skipped": int(pool_stats.get("threads_skipped") or 0),
    }


def forum_candidates(version: str, pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Threads that name this version, using the acceptance authority's OWN matcher.

    GitHub gets this narrowing for free from a server-side version query. The forum has no
    queryable search (robots disallows /forum/search/), so the pool is narrowed locally -- and
    it is narrowed with `match_basis` rather than a hand-rolled containment test, because a
    second version predicate is a second authority waiting to drift.

    A thread that never names the version is not a REJECTED candidate, it was never a candidate:
    counting 180 threads as rejections for every version would make the telemetry meaningless.
    """
    return [post for post in pool if legacy_obs.match_basis(post, version)]


def evaluate_forum_candidates(version: str, release_date, candidates: list[dict[str, Any]],
                              captured_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the shared OBS authority over forum candidates. This judges nothing of its own."""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for post in candidates:
        basis, reason = legacy_obs.evaluate_issue(post, version, release_date)
        if reason:
            rejected.append({"source_url": post.get("source_url"), "reason": reason})
            continue
        identity = forum.row_identity(version, post, legacy_obs.slug)
        if identity is None:
            # No resolvable thread id, so the row could not be matched back to its thread and two
            # URL shapes for one thread could not be recognised as the same report. Refused rather
            # than stored under an invented identity.
            rejected.append({"source_url": post.get("source_url"),
                             "reason": "unresolvable_thread_identity"})
            continue
        accepted.append(legacy_obs.evidence_row(
            post, version, basis, captured_at, identity=identity,
        ))
    return accepted, rejected


def github_health(collector_status: int, result: dict[str, Any]) -> tuple[str, str]:
    """GitHub method health from the GITHUB outcome alone, as (status, blocked_reason).

    Before the second family existed, the collector's overall status WAS the GitHub status.
    Now it is not: a run where GitHub 502s and the forum returns three reports still exits 0.
    Deriving this from the merged result would report that outage as success -- the exact
    shape of silent rot, where adding a source makes the failure of another invisible.
    """
    failed = collector_status != 0 or result.get("github_status") == "failed"
    if failed:
        reason = str(result.get("github_error") or result.get("error") or "")
        # GitHub refused (rate limit, access denial, other 403) and the transport stopped the run:
        # the source is refusing us, which is `blocked`, not a defect of ours.
        return ("blocked" if github_api.is_stop(reason) else "broken"), reason
    if int(result.get("github_accepted_count") or 0) > 0:
        return "success", ""
    return "no_results", ""


def retired_watchlist_row(product_id: str, version: str, last_run: str) -> dict[str, Any]:
    """The retired known_watchlist slot, emitted on EVERY run.

    It never discovered a candidate, and obs_forum is the real second family. It is emitted
    rather than deleted because a method that simply stops emitting keeps its last status
    forever -- silence would freeze its old row in the health table instead of retiring it.
    Zero candidates and `disabled` are what keep it from reading as coverage.
    """
    return method_health_row(
        product_id=product_id,
        update_version=version,
        method_id="known_watchlist",
        source_type="curated_watchlist",
        status="disabled",
        candidates_found=0,
        accepted_reports=0,
        rejected_reports=0,
        blocked_reason="retired_superseded_by_obs_forum",
        last_run=last_run,
        notes="Retired. Reserved slot that never discovered a candidate; superseded by obs_forum.",
    )


def forum_status(pool_error: str | None, stats: dict[str, int], accepted: int) -> str:
    """Truthful health for the forum method.

    Ordered worst-first on purpose. `broken` is reported when pages WERE fetched and the
    extractor mapped none of them -- a source whose extractor maps nothing is impaired
    immediately, and letting that read as `no_results` is how silent rot survives a green run.
    """
    if pool_error:
        return "blocked"
    if stats.get("threads_requested", 0) > 0 and stats.get("threads_in_pool", 0) == 0:
        return "broken"
    # threads_bodyless counts only the empty bodies that point at OUR failure -- a missing wrapper,
    # an extraction failure, an unexplained empty wrapper -- so any count still degrades. A
    # legitimately textless post (images/embeds only, or quote only) degrades only when such posts
    # are a material share of the pool, which is what a site-wide markup change looks like.
    if (stats.get("listings_failed", 0) or stats.get("threads_failed", 0)
            or stats.get("threads_unparsed", 0) or stats.get("threads_bodyless", 0)
            or forum.empty_body_collapse(stats)):
        return "partial"
    if accepted > 0:
        return "success"
    return "no_results"


class ObsCollector(ProductCollector):
    product_id = legacy_obs.PRODUCT_ID

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        records_by_version = {version: path for version, path in legacy_obs.active_obs_records()}
        if context.target_versions:
            versions = list(context.target_versions)
        else:
            versions = list(records_by_version)
        order = walk_order(versions, last_refreshed_by_version())

        # ONE pool for the whole run. A thread is fetched once and evaluated against every
        # version offline; per-version fetching would multiply forum requests by the version count.
        forum.reset_pool()
        pool, pool_stats, pool_error = forum.get_pool()

        results: list[dict[str, Any]] = []
        processed: list[str] = []
        skipped: list[str] = []
        for index, version in enumerate(order):
            _b = rb.get_run_budget()
            if _b is not None and _b.collector_finalize_expired():
                # Every version from here on gets NO result and so no health row -- never a fresh
                # or successful one. The stop names them, with the pool's own counts.
                skipped = order[index:]
                rb.emit("collector_budget_stop", product_id=self.product_id, reason="collector_finalize",
                        **coverage_fields(order, processed, skipped, pool_stats))
                break
            if not legacy_obs.valid_update_version(version):
                results.append({
                    "product_id": self.product_id,
                    "version": version,
                    "status": "invalid_version",
                    "accepted_count": 0,
                    "rejected_count": 0,
                })
                processed.append(version)
                continue

            record_path = records_by_version.get(version)
            release_date = legacy_obs.release_date_for_record(record_path)
            candidates = forum_candidates(version, pool)
            forum_accepted, forum_rejected = evaluate_forum_candidates(
                version, release_date, candidates, legacy_obs.utc_now())

            status, result = legacy_obs.collect_one(
                version=version,
                record_path=record_path,
                since=context.since,
                max_pages=context.max_pages,
                write=context.write,
                extra_accepted=forum_accepted,
                extra_rejected=forum_rejected,
            )
            last_run = utc_now()
            result["product_id"] = self.product_id
            result["collector_status"] = status
            result["forum_pool_stats"] = dict(pool_stats)
            result["forum_candidates"] = len(candidates)
            result["forum_accepted_count"] = len(forum_accepted)
            result["forum_rejected_count"] = len(forum_rejected)

            added_by_type = result.get("added_rows_by_source_type") or {}
            github_added = int(added_by_type.get("github_issue") or 0)
            forum_added = int(added_by_type.get(forum.SOURCE_TYPE) or 0)

            github_accepted = int(result.get("github_accepted_count") or 0)
            github_rejected = int(result.get("github_rejected_count") or 0)
            github_status, github_reason = github_health(status, result)

            forum_note = ("obsproject.com Windows/Mac/Linux support subforums, opening posts only; "
                          "pool of %d threads." % int(pool_stats.get("threads_in_pool") or 0))

            result["method_health"] = [
                method_health_row(
                    product_id=self.product_id,
                    update_version=version,
                    method_id=GITHUB_METHOD_ID,
                    source_type="github_issue",
                    status=github_status,
                    candidates_found=github_accepted + github_rejected,
                    accepted_reports=github_accepted,
                    rejected_reports=github_rejected,
                    evidence_rows_added=github_added,
                    duplicate_existing_evidence=max(0, github_accepted - github_added),
                    blocked_reason=github_reason,
                    last_run=last_run,
                    notes="obsproject/obs-studio GitHub Issues, exact version matching."
                          + (f" {github_api.stop_note()}" if github_status == "blocked" else ""),
                ),
                method_health_row(
                    product_id=self.product_id,
                    update_version=version,
                    method_id=FORUM_METHOD_ID,
                    source_type=forum.SOURCE_TYPE,
                    status=forum_status(pool_error, pool_stats, len(forum_accepted)),
                    candidates_found=len(candidates),
                    accepted_reports=len(forum_accepted),
                    rejected_reports=len(forum_rejected),
                    evidence_rows_added=forum_added,
                    duplicate_existing_evidence=max(0, len(forum_accepted) - forum_added),
                    blocked_reason=pool_error or "",
                    last_run=last_run,
                    notes=forum_note,
                ),
            ]

            result["method_health"].append(
                retired_watchlist_row(self.product_id, version, last_run))

            if record_path:
                result["record_path"] = str(record_path.relative_to(legacy_obs.ROOT))
            results.append(result)
            processed.append(version)
        # Every run says what it covered, budget stop or not, so a run that reaches only part of
        # the walk is diagnosable from its own log.
        rb.emit("obs_version_walk", product_id=self.product_id, order=",".join(order),
                budget_stopped=bool(skipped), **coverage_fields(order, processed, skipped, pool_stats))
        return results
