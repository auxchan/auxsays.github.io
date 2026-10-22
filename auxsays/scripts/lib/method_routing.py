#!/usr/bin/env python3
"""Configuration-driven discovery-method routing for the orchestration control plane.

A product DECLARES its methods and fallback conditions here instead of hardcoding routing through
the graph. The declaration is deliberately a Python literal in one module: deterministic, import-
checked, and internal (this is control-plane configuration, not site data, so it does not belong
under ``_data/`` where files are published to the Jekyll site).

Two hard rules:

  * DECLARATION IS NOT CAPABILITY. Listing a method in a plan never enables an unsupported
    method: each fallback still passes through its own production capability gate (for
    PowerPoint's Reddit fallback, the existing ``reddit_fallback_enabled`` env flag documenting
    the CI-blocked status from PR #23). A configured-but-incapable fallback is reported honestly
    as ``disabled``, never silently attempted.
  * FALLBACK NEVER WEAKENS ACCEPTANCE. Routing decides WHICH deterministic method runs next; the
    acceptance gates (exact build, channel, date, URL, concrete issue) are identical for every
    method and live in the collector authorities, not here.
"""
from __future__ import annotations

from typing import Any

# Canonical method-health statuses (must stay aligned with the collectors' emitted statuses).
HEALTH_STATUSES = frozenset({
    "success", "partial", "no_results", "blocked", "stale", "broken",
    "low_confidence", "disabled", "manual_review_needed",
})

# Conditions a product may cite for invoking a fallback method. Evaluated deterministically over
# the PRIMARY methods' health rows + accepted counts for the same patch target.
FALLBACK_CONDITIONS = frozenset({
    "no_accepted_reports",   # primary methods accepted zero reports for this patch
    "blocked",               # a primary method reported blocked
    "broken",                # a primary method reported broken
    "stale",                 # a primary method reported stale
    "low_confidence",        # a primary method reported low_confidence
})

# product_id -> declarative method plan. Products absent from this map get DEFAULT_PLAN, which
# has no orchestrated fallback -- their existing collectors keep their current behaviour.
METHOD_PLANS: dict[str, dict[str, Any]] = {
    "microsoft-powerpoint": {
        # Four primaries, run every cycle. They are independent corpora, not a retry chain: a
        # Super User question, a Microsoft Q&A thread and an OfficeDev issue are written by
        # different people in different places. Making the newer two conditional on Q&A failing
        # would suppress them exactly when Q&A is working.
        # learn_qna_powerpoint_tags shares the Q&A source FAMILY with learn_qna_search_rss but is a
        # genuinely different discovery path: one asks a search index for fixed phrasings, the
        # other walks the PowerPoint community inventories in recency order. A report worded in a
        # way no query anticipated is invisible to the first and ordinary to the second, so it is a
        # primary rather than a fallback.
        "primary": ["learn_qna_search_rss", "learn_qna_powerpoint_tags",
                    "stack_exchange_search", "github_officedev_issues",
                    "tech_community_discussions", "open_web_discovery"],
        "fallback": ["reddit_search"],
        "fallback_when": ["no_accepted_reports", "blocked", "broken", "stale", "low_confidence"],
    },
    "adobe-premiere-pro": {
        # ONE primary. Measured on current main over both live Premiere records, scheduled shape
        # (--since-days 45 --max-pages 5): the nine-method flat loop took 546.8s, of which
        # wayback_snapshot_recheck was 408.5s and reddit_search 92.3s -- 91.6% of the run spent
        # in two methods that returned 0 candidates and reported blocked/broken. Algolia took
        # 6.2s for 12 requests and produced every accepted row (4 for 26.2, 18 for 26.2.2).
        "primary": ["adobe_community_algolia_search"],
        # The recheck re-reads the specific report URLs already stored for this patch, so it is
        # the one method that can speak about evidence the collector already holds. It is a
        # fallback rather than a primary because it DISCOVERS nothing new -- a URL it returns is
        # already in the store and dies at URL dedupe -- and because it is itself currently
        # blocked on the same Adobe HTML surface (26.2 blocked, 26.2.2 no_results, 25 requests,
        # 0 candidates). Running it behind a healthy Algolia buys nothing and costs 20.3s.
        "fallback": ["adobe_community_known_url_recheck"],
        # Exactly the three conditions Algolia can actually produce. `stale` and
        # `low_confidence` are deliberately absent: adobe_community_method_status never returns
        # them, so declaring them would be configuration that can never fire.
        "fallback_when": ["no_accepted_reports", "blocked", "broken"],
        # Implemented and kept, never run by routine collection. Wayback is the single largest
        # cost in the whole collector (408.5s, 26 requests, ~15.7s per request against
        # web.archive.org) and it reached nothing: 0 candidates on both records, blocked on 26.2
        # and broken on 26.2.2. It also calls Brave itself, so it inherits the lapsed
        # subscription's HTTP 402. No automatic recovery trigger is declared because the
        # measurement gives none: the cycle where the primary fails is exactly the cycle that
        # must not also spend seven minutes on an archive that answered nothing.
        "probe_only": ["wayback_snapshot_recheck"],
        # Measured refused, every run, for months. Left implemented with their registry history
        # intact; they simply stop doing routine network work. Each still reports an honest
        # `disabled` row every cycle, because a method that stops emitting leaves its last
        # `blocked` row frozen in the telemetry and looking current (upsert_method_health keys on
        # (product, version, build, method) and retains what it is not given).
        "disabled": ["adobe_community_search", "adobe_community_bug_tab_index",
                     "reddit_search", "brave_search_api",
                     "creativecow_forum_index", "creativecow_brave_search"],
    },
}

DEFAULT_PLAN: dict[str, Any] = {"primary": [], "fallback": [], "fallback_when": [],
                               "probe_only": [], "disabled": []}


def plan_methods(product_id: str) -> dict[str, Any]:
    plan = METHOD_PLANS.get(str(product_id or "").strip(), DEFAULT_PLAN)
    unknown = set(plan.get("fallback_when", [])) - FALLBACK_CONDITIONS
    if unknown:
        raise ValueError(f"unknown fallback conditions for {product_id}: {sorted(unknown)}")
    resolved = {"primary": list(plan.get("primary", [])),
                "fallback": list(plan.get("fallback", [])),
                "fallback_when": list(plan.get("fallback_when", [])),
                "probe_only": list(plan.get("probe_only", [])),
                "disabled": list(plan.get("disabled", []))}
    # One method, one role. A method listed twice is not a harmless duplicate: it would be
    # both executed and reported as intentionally not executed, and the health row written
    # second would overwrite the true one.
    seen: dict[str, str] = {}
    for role in ("primary", "fallback", "probe_only", "disabled"):
        for method_id in resolved[role]:
            if method_id in seen:
                raise ValueError(
                    f"{product_id}: {method_id} is declared both {seen[method_id]} and {role}")
            seen[method_id] = role
    return resolved


def fallback_justified(primary_health: list[dict[str, Any]], accepted_count: int,
                       conditions: list[str]) -> tuple[bool, str]:
    """Deterministic fallback decision for ONE patch target.

    Returns (justified, reason). Justification comes only from the declared conditions evaluated
    against the primary methods' canonical health statuses and the accepted count -- never from
    ambient guesswork. No conditions declared -> never justified."""
    statuses = {str(h.get("status") or "") for h in primary_health}
    bad = statuses - HEALTH_STATUSES - {""}
    if bad:
        raise ValueError(f"non-canonical health status from primary methods: {sorted(bad)}")
    for condition in conditions:
        if condition == "no_accepted_reports":
            if accepted_count == 0:
                return True, "no_accepted_reports"
        elif condition in statuses:
            return True, condition
    return False, ""
