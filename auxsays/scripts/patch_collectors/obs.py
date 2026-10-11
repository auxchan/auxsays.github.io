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

from typing import Any

import collect_obs_reports as legacy_obs

from .base import CollectorContext, ProductCollector, method_health_row, utc_now
from . import obs_forum_source as forum
from . import runtime_budget as rb

GITHUB_METHOD_ID = "github_issues"
FORUM_METHOD_ID = "obs_forum"


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
        return "broken", str(result.get("github_error") or result.get("error") or "")
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
    if (stats.get("listings_failed", 0) or stats.get("threads_failed", 0)
            or stats.get("threads_unparsed", 0) or stats.get("threads_bodyless", 0)):
        return "partial"
    if accepted > 0:
        return "success"
    return "no_results"


class ObsCollector(ProductCollector):
    product_id = legacy_obs.PRODUCT_ID

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        records_by_version = {version: path for version, path in legacy_obs.active_obs_records()}
        if context.target_versions:
            versions = sorted(context.target_versions)
        else:
            versions = sorted(records_by_version)

        # ONE pool for the whole run. A thread is fetched once and evaluated against every
        # version offline; per-version fetching would multiply forum requests by the version count.
        forum.reset_pool()
        pool, pool_stats, pool_error = forum.get_pool()

        results: list[dict[str, Any]] = []
        for version in versions:
            _b = rb.get_run_budget()
            if _b is not None and _b.collector_finalize_expired():
                rb.emit("collector_budget_stop", product_id=self.product_id, reason="collector_finalize")
                break
            if not legacy_obs.valid_update_version(version):
                results.append({
                    "product_id": self.product_id,
                    "version": version,
                    "status": "invalid_version",
                    "accepted_count": 0,
                    "rejected_count": 0,
                })
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
                    notes="obsproject/obs-studio GitHub Issues, exact version matching.",
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
        return results
