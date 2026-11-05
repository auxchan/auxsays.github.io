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


# --- underfilled-evidence enrichment (B3 / L1) ----------------------------------------------------
#
# WHY A SEPARATE TABLE. `FALLBACK_CONDITIONS` are four failure statuses plus "no accepted reports".
# None of them can fire for a patch whose primary methods are HEALTHY and accepted something -- which
# is exactly the patch that is short of the live rung by a few reports. An underfill plan names the
# extra, bounded work a product may do for such a patch. It is a separate table, not a fourth role in
# METHOD_PLANS, so `plan_methods` and every caller of it are untouched.
#
# DECLARATION IS NOT CAPABILITY, here too. A plan entry is read only by a collector that implements
# the named adapter, and only behind that collector's own default-off flag. An entry here never
# enables a request on its own.
#
# THE TRIGGER IS THE CERTIFIER'S OWN VERDICT. "Underfilled" means exactly: the shipped
# `live_eligibility.evaluate` refused the identity, and EVERY reason it gave is a count reason. Any
# other reason (degraded or missing telemetry, an unprojectable row, not a promotion product, ...)
# means more reports would not make it live, so nothing is fetched for it. There is no new threshold.
#
# NO REPORT BECOMES VALID BECAUSE ITS PATCH IS INSIDE THE WINDOW. The window only decides which
# patches receive discovery attention; every hydrated report still goes through the product's
# unchanged acceptance authority.
UNDERFILL_ROLES = frozenset({"enrichment"})

# Hard ceiling on the recency window. A plan may choose a smaller window; it may not choose a larger
# one, because an older patch's shortfall cannot be closed by a recency-bounded discovery anyway.
UNDERFILL_MAX_WINDOW_DAYS = 90

# The only excerpt-time rejections an opening-post hydration may re-judge: the two a 280-character
# excerpt can explain by leaving text out. A veto (wrong KB, wrong train, cross-patch duplicate, build
# only in system specs, foreign product, official note, announcement, tenant, account, date before
# release, stale after rollover, a question that is not a regression) is never re-judged. Widening
# this set is a code change with its own dry-run evidence, never a plan edit.
UNDERFILL_ENRICHABLE_REASONS = frozenset({"missing_kb_or_build", "missing_update_attribution"})

# The `evaluate` reason prefixes that mean "short of reports" and nothing else
# (live_eligibility.evaluate conditions b and c). Anything else is certifier_unreachable.
UNDERFILL_COUNT_PREFIXES = ("below_high_rung:", "exclusive_below_high_rung:")

UNDERFILL_PLANS: dict[str, dict[str, Any]] = {
    "microsoft-windows-11": {
        # Opening-post hydration of the Learn Q&A threads THIS RUN's search-RSS discovery found and
        # rejected on its excerpt. Enrichment inside learn_qna_search_rss: it owns no health row,
        # adds no source_type, and its failures never enter that method's status.
        "adapters": ["learn_qna_question_hydration"],
        "role": "enrichment",
        # 90 days (AUTH v2.16 D3): 60 would drop 25H2 26200.9457, the nearest certification, on
        # 2026-11-13; 90 keeps it until 2026-12-13 and keeps 26H2 26300.9711 to its own boundary.
        "window_days": 90,
        "enrichable_reasons": ["missing_kb_or_build", "missing_update_attribution"],
        "max_fetches_per_run": 45,
        "max_fetches_per_identity": 30,
        # D3: "Do not spend all 45 hydrations repeatedly on older records while current Windows
        # patches receive none." The first `recency_reserve` fetches of every run go to the newest
        # underfilled patches, before the closable-first priority spends the rest.
        "recency_reserve": 5,
    },
}


def plan_underfill(product_id: str, *,
                   plans: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The validated underfill plan for one product, or None when it declares none.

    Refuses (ValueError) an unknown role, a window outside 1..UNDERFILL_MAX_WINDOW_DAYS, a product
    whose projections no lane rebuilds (``report_counts.CONSENSUS_PROMOTION_PRODUCTS``), a re-judged
    reason outside UNDERFILL_ENRICHABLE_REASONS, non-positive or inverted fetch caps, and a method
    that is declared twice -- inside the adapters, or in any role of the product's METHOD_PLANS entry
    (one method, one role, exactly as ``plan_methods`` enforces it among its own roles)."""
    table = UNDERFILL_PLANS if plans is None else plans
    product = str(product_id or "").strip()
    plan = table.get(product)
    if plan is None:
        return None
    from lib.report_counts import CONSENSUS_PROMOTION_PRODUCTS  # noqa: PLC0415 - keeps routing light
    if product not in CONSENSUS_PROMOTION_PRODUCTS:
        raise ValueError(f"{product}: underfill needs a promotion product (its counts are rebuilt "
                         "and retracted by a lane)")
    role = plan.get("role")
    if role not in UNDERFILL_ROLES:
        raise ValueError(f"{product}: unknown underfill role {role!r}")
    window = plan.get("window_days")
    if not isinstance(window, int) or isinstance(window, bool) \
            or not 0 < window <= UNDERFILL_MAX_WINDOW_DAYS:
        raise ValueError(f"{product}: window_days must be 1..{UNDERFILL_MAX_WINDOW_DAYS}, got {window!r}")
    adapters = [str(m) for m in plan.get("adapters") or []]
    if not adapters:
        raise ValueError(f"{product}: an underfill plan names at least one adapter")
    reasons = [str(r) for r in plan.get("enrichable_reasons") or []]
    if not reasons or set(reasons) - UNDERFILL_ENRICHABLE_REASONS:
        raise ValueError(f"{product}: enrichable_reasons must be a non-empty subset of "
                         f"{sorted(UNDERFILL_ENRICHABLE_REASONS)}, got {reasons}")
    caps = {}
    for name in ("max_fetches_per_run", "max_fetches_per_identity"):
        value = plan.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{product}: {name} must be a positive integer, got {value!r}")
        caps[name] = value
    if caps["max_fetches_per_identity"] > caps["max_fetches_per_run"]:
        raise ValueError(f"{product}: max_fetches_per_identity exceeds max_fetches_per_run")
    reserve = plan.get("recency_reserve", 0)
    if not isinstance(reserve, int) or isinstance(reserve, bool) \
            or not 0 <= reserve <= caps["max_fetches_per_run"]:
        raise ValueError(f"{product}: recency_reserve must be 0..max_fetches_per_run, got {reserve!r}")
    seen: dict[str, str] = {}
    for role_name, methods in plan_methods(product).items():
        if role_name == "fallback_when":
            continue
        for method_id in methods:
            seen[method_id] = role_name
    for method_id in adapters:
        if method_id in seen:
            raise ValueError(f"{product}: {method_id} is declared both {seen[method_id]} and {role}")
        seen[method_id] = role
    return {"adapters": adapters, "role": role, "window_days": window,
            "enrichable_reasons": reasons, "recency_reserve": reserve, **caps}


def underfill_justified(live: bool, reasons: tuple[str, ...] | list[str], *,
                        release_age_days: float | None, window_days: int) -> tuple[bool, str]:
    """Deterministic underfill decision for ONE patch, from the certifier's own decision.

    Returns (justified, decision). ``decision`` is one of ``underfilled``, ``live``,
    ``certifier_unreachable``, ``not_count_limited`` or ``outside_recency_window``. Fail closed: a
    reason this function does not recognise is certifier_unreachable, never "probably a count"."""
    if not isinstance(window_days, int) or isinstance(window_days, bool) \
            or not 0 < window_days <= UNDERFILL_MAX_WINDOW_DAYS:
        raise ValueError(f"window_days must be 1..{UNDERFILL_MAX_WINDOW_DAYS}, got {window_days!r}")
    if live:
        return False, "live"
    reasons = tuple(str(r) for r in reasons or ())
    if not reasons:
        return False, "certifier_unreachable"
    if any(not r.startswith(UNDERFILL_COUNT_PREFIXES) for r in reasons):
        return False, "certifier_unreachable"
    if release_age_days is None or release_age_days < 0 or release_age_days > window_days:
        return False, "outside_recency_window"
    return True, "underfilled"


def _ordered(entries: list[dict[str, Any]], *, recency: bool) -> list[dict[str, Any]]:
    """Total, input-order-independent identity order. Python's sort is stable, so the keys are
    applied least significant first. Ties end on version then build, newest first, exactly as the
    Windows collector's `_newest_first` walk breaks them."""
    out = sorted(entries, key=lambda e: tuple(str(p) for p in e["key"]))
    out.sort(key=lambda e: (str(e["key"][1]), str(e["key"][2])), reverse=True)
    out.sort(key=lambda e: int(e["shortfall"]))
    out.sort(key=lambda e: str(e["release_date"]), reverse=True)
    if not recency:
        out.sort(key=lambda e: 0 if e["closable"] else 1)
    return out


def underfill_order(entries: list[dict[str, Any]], *, max_fetches_per_run: int,
                    max_fetches_per_identity: int, recency_reserve: int = 0) -> dict[str, Any]:
    """Which queued URLs one run hydrates, in GET order. Pure and deterministic.

    ``entries``: one per underfilled identity -- ``key`` (product, version, build),
    ``release_date`` (ISO, sortable), ``shortfall`` (reports still missing for the live rung) and
    ``queue`` (``[{"url", "date"}]``, the identity's eligible rejected URLs).

    Order:
      1. RECENCY RESERVE. The first ``recency_reserve`` GETs go to the newest identities (release
         date, newest first; then smallest shortfall). This is what stops a run from spending every
         fetch on older patches while the current patch receives none (AUTH v2.16 D3).
      2. PRIORITY. The rest go to "closable" identities first (queue at least as long as the
         shortfall), then newest release, then smallest shortfall.
    Within an identity: newest discovery date first, then URL. A URL is fetched at most once per run;
    a second identity that queued it is served from that one fetch and is charged nothing. The caps
    apply to real GETs and only after ordering.

    Returns ``{"fetch": [url, ...], "charged": {url: key}, "served": {key: [url, ...]},
    "not_reached": {key: [url, ...]}}`` -- ``charged`` names the identity whose cap paid for each GET.
    """
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        urls: dict[str, str] = {}
        for item in entry.get("queue") or []:
            url = str(item.get("url") or "")
            if url and url not in urls:
                urls[url] = str(item.get("date") or "")
        queue = sorted(urls, key=lambda u: u)
        queue.sort(key=lambda u: urls[u], reverse=True)
        shortfall = max(0, int(entry.get("shortfall") or 0))
        normalized.append({"key": tuple(entry["key"]), "release_date": str(entry.get("release_date") or ""),
                           "shortfall": shortfall, "queue": queue,
                           "closable": shortfall > 0 and len(queue) >= shortfall})

    fetched: list[str] = []
    charged: dict[str, tuple] = {}
    per_identity: dict[tuple, int] = {}

    def walk(order: list[dict[str, Any]], run_limit: int) -> None:
        for entry in order:
            for url in entry["queue"]:
                if len(fetched) >= run_limit:
                    return
                if url in charged:
                    continue
                if per_identity.get(entry["key"], 0) >= max_fetches_per_identity:
                    break
                fetched.append(url)
                charged[url] = entry["key"]
                per_identity[entry["key"]] = per_identity.get(entry["key"], 0) + 1

    walk(_ordered(normalized, recency=True), min(max(0, recency_reserve), max_fetches_per_run))
    walk(_ordered(normalized, recency=False), max_fetches_per_run)
    served = {e["key"]: [u for u in e["queue"] if u in charged] for e in normalized}
    not_reached = {e["key"]: [u for u in e["queue"] if u not in charged] for e in normalized}
    return {"fetch": fetched, "charged": charged, "served": served, "not_reached": not_reached}
