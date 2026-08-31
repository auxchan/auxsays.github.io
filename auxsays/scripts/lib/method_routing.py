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
}

DEFAULT_PLAN: dict[str, Any] = {"primary": [], "fallback": [], "fallback_when": []}


def plan_methods(product_id: str) -> dict[str, Any]:
    plan = METHOD_PLANS.get(str(product_id or "").strip(), DEFAULT_PLAN)
    unknown = set(plan.get("fallback_when", [])) - FALLBACK_CONDITIONS
    if unknown:
        raise ValueError(f"unknown fallback conditions for {product_id}: {sorted(unknown)}")
    return {"primary": list(plan.get("primary", [])),
            "fallback": list(plan.get("fallback", [])),
            "fallback_when": list(plan.get("fallback_when", []))}


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
