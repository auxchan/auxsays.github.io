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

ADAPTIVE ROUTING (the second half of this module). Three things are derived from the health rows
the collectors already store, and nothing else -- no model, no separate learning store, no clock
other than the one the caller passes:

  * ORDER. `order_methods` sorts a role's methods by measured history: a method whose latest run
    was refused goes last, then the most recently productive first, then the more productive, then
    the cheaper, and the DECLARED order breaks every tie. With no history it returns the declared
    order unchanged. It never drops a method and never adds one.
  * BOUNDED FALLBACKS. A plan may declare at most MAX_FALLBACK_METHODS fallbacks; `plan_methods`
    refuses a longer chain at import time, so "try one more source" cannot grow without limit.
  * RETURN TO SERVICE. `effective_plan` moves a switched-off method that the re-probe step found
    answering again (`reprobe_methods.py`) back into the plan as a FALLBACK, for the one run the
    step GRANTED a request budget to. `advance_service` settles each granted run from the
    method's own rows: an answered run advances a ramp, a refused run is a RELAPSE (out again,
    cooldown restarted with a longer back-off, a new probe needed). `due_reprobes` says which
    switched-off methods may be probed now: only those the registry's policy allows, only after
    their cooldown, only within a hard per-run request cap.

All three change WHICH method is tried and WHEN. None of them can change what is ACCEPTED: the
candidates of every method, whatever its position or role, pass the same collector authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

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
    # NVIDIA driver families: ONE primary, the forum's default views, shared by both families in
    # one cycle per run. Declared here so the method can be switched off the same day without a
    # code change to the collector: moving it to "disabled" for BOTH families stops every forum
    # request and reports an honest `disabled` row (nothing stored is removed). No fallback, by
    # design: the other public NVIDIA communities were measured unusable (G44/G45).
    "nvidia-geforce-game-ready": {"primary": ["nvidia_forum_default_views"]},
    "nvidia-studio-driver": {"primary": ["nvidia_forum_default_views"]},
    # DaVinci Resolve. ONE method still answers: the Creative COW board walk. The other four are
    # off, each for its own reason, and each still writes an honest `disabled` row every cycle:
    #   reddit_search        access policy (no written permission) -- never re-probed
    #   known_watchlist      a hand-kept URL list, half of it Reddit -- never re-probed
    #   web_search           a placeholder with no provider -- never re-probed
    #   vendor_forum_search  the Blackmagic forum refuses automated requests (AWS WAF). This is a
    #                        technical refusal, not a rights decision, so it is the one method the
    #                        re-probe step re-tests (weekly at most, two requests at most). If the
    #                        forum answers again, `effective_plan` returns it as a fallback for each
    #                        run the step grants, under the request budget the registry declares;
    #                        a run the forum refuses is a relapse and needs a new probe.
    "blackmagic-davinci": {
        "primary": ["creative_cow_forum_search"],
        "fallback_when": ["no_accepted_reports", "blocked", "broken"],
        "disabled": ["known_watchlist", "reddit_search", "vendor_forum_search", "web_search"],
    },
}

# A fallback chain is bounded by declaration. Three is already more than any plan uses (the longest
# has one); the number exists so that a fourth is a decision, not an accident.
MAX_FALLBACK_METHODS = 3

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
    if len(resolved["fallback"]) > MAX_FALLBACK_METHODS:
        raise ValueError(f"{product_id}: {len(resolved['fallback'])} fallbacks declared; "
                         f"the bound is {MAX_FALLBACK_METHODS}")
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


# =================================================================================================
# ADAPTIVE ROUTING: order from measured history, bounded re-probe of switched-off methods.
# Pure functions over the stored health rows and probe records. No I/O, no network, no globals.
# =================================================================================================

RESPONDING_STATUSES = frozenset({"success", "partial", "no_results", "low_confidence"})
FAILING_STATUSES = frozenset({"blocked", "stale", "broken"})

# Rows of one method whose `last_run` falls within this window of the method's newest row belong
# to the same collection pass. A pass is bounded by the 240-minute collect step.
RUN_WINDOW = timedelta(hours=4)


def parse_time(value: Any) -> datetime | None:
    """A stored timestamp as an aware UTC datetime, or None. Accepts the forms the collectors write
    (`2026-11-24T00:40:44Z`, with or without seconds/offset) and a bare date."""
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def format_time(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def method_history(rows: Iterable[dict[str, Any]], product_id: str) -> dict[str, dict[str, Any]]:
    """Per-method measured history for one product, from its stored health rows.

    Each stored row is the method's LATEST attempt on one patch, plus the history the writer
    carried on it. The summary is therefore: how many patches it has a row for, how many
    candidates and accepted rows those latest attempts hold, when it last answered and last
    accepted anything, what its newest collection pass looked like, and what an attempt costs."""
    pid = str(product_id or "").strip()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows or ():
        if isinstance(row, dict) and str(row.get("product_id") or "").strip() == pid:
            grouped.setdefault(str(row.get("method_id") or "").strip(), []).append(row)
    history: dict[str, dict[str, Any]] = {}
    for method_id, method_rows in grouped.items():
        if not method_id:
            continue
        attempted = [r for r in method_rows if str(r.get("status") or "") != "disabled"]
        runs = [t for t in (parse_time(r.get("last_run")) for r in attempted) if t is not None]
        newest = max(runs) if runs else None
        latest = [r for r in attempted
                  if newest is not None and (parse_time(r.get("last_run")) or newest) >= newest - RUN_WINDOW
                  and parse_time(r.get("last_run")) is not None]
        latest_status = [str(r.get("status") or "") for r in latest]

        def _latest_time(field: str, fallback_ok) -> datetime | None:
            times = []
            for r in method_rows:
                stamp = parse_time(r.get(field))
                if stamp is None and fallback_ok(r):
                    stamp = parse_time(r.get("last_run"))
                if stamp is not None:
                    times.append(stamp)
            return max(times) if times else None

        durations = sorted(int(r["duration_ms"]) for r in attempted
                           if isinstance(r.get("duration_ms"), int) and not isinstance(r.get("duration_ms"), bool))
        reasons: dict[str, int] = {}
        for r in attempted:
            for code, count in (r.get("rejection_reasons") or {}).items():
                reasons[str(code)] = reasons.get(str(code), 0) + int(count or 0)
        history[method_id] = {
            "rows": len(method_rows),
            "attempted_rows": len(attempted),
            "attempts": sum(int(r.get("attempts") or 1) for r in attempted),
            "candidates": sum(int(r.get("candidates_found") or 0) for r in attempted),
            "accepted": sum(int(r.get("accepted_candidates") or 0) for r in attempted),
            "last_run": format_time(newest) if newest else "",
            "last_good_at": _fmt(_latest_time(
                "last_good_at", lambda r: str(r.get("status") or "") in RESPONDING_STATUSES)),
            "last_accepted_at": _fmt(_latest_time(
                "last_accepted_at", lambda r: int(r.get("accepted_candidates") or 0) > 0
                and str(r.get("status") or "") != "disabled")),
            "latest_rows": len(latest),
            "latest_failing": sum(1 for s in latest_status if s in FAILING_STATUSES),
            "latest_responding": sum(1 for s in latest_status if s in RESPONDING_STATUSES),
            "median_duration_ms": durations[len(durations) // 2] if durations else None,
            "rejection_reasons": dict(sorted(reasons.items())),
        }
    return history


def _fmt(moment: datetime | None) -> str:
    return format_time(moment) if moment else ""


def latest_pass_failed(summary: dict[str, Any] | None) -> bool:
    """True when the method's newest collection pass had rows and NONE of them answered."""
    if not summary:
        return False
    return bool(summary.get("latest_rows")) and not summary.get("latest_responding") \
        and bool(summary.get("latest_failing"))


def order_methods(methods: Iterable[str], history: dict[str, dict[str, Any]] | None) -> list[str]:
    """The same methods, in the order measured history says to try them. Deterministic.

    Sort key, most significant first:
      1. a method whose newest pass was entirely refused goes after every method that answered;
      2. the method that most recently ACCEPTED a report goes first (never-accepted last);
      3. more accepted rows first;
      4. the cheaper method first, when both costs were measured;
      5. the declared position -- so with no history, or equal history, nothing moves.
    Output is always a permutation of the input: nothing is dropped, nothing is added, and a
    duplicate in the input is kept once at its first position."""
    declared: list[str] = []
    for method_id in methods or ():
        if method_id not in declared:
            declared.append(method_id)
    history = history or {}

    def key(item: tuple[int, str]) -> tuple:
        position, method_id = item
        summary = history.get(method_id) or {}
        accepted_at = parse_time(summary.get("last_accepted_at"))
        cost = summary.get("median_duration_ms")
        return (
            1 if latest_pass_failed(summary) else 0,
            -(accepted_at.timestamp()) if accepted_at else float("inf"),
            -int(summary.get("accepted") or 0),
            cost if isinstance(cost, int) else float("inf"),
            position,
        )

    return [method_id for _pos, method_id in sorted(enumerate(declared), key=key)]


# --- re-probe scheduling -------------------------------------------------------------------------
# Hard caps. A scheduled run may spend at most this many requests on probes, whatever is due.
MAX_REPROBE_REQUESTS_PER_RUN = 4
MAX_REPROBE_METHODS_PER_RUN = 2

# A GRANT is the re-probe step's permission for ONE collection run to use a returned method, with a
# request budget. It serves the run that wrote it and no later one: the lane runs every 6 hours and
# its collect step is capped at 240 minutes, so a grant older than this belongs to a run whose
# re-probe step did not run (or crashed), and the method stays off.
SERVICE_GRANT_TTL = timedelta(hours=5)
# Granted runs in a row that left no row of the method behind (a lost writeback, a product that was
# not collected). The outcome is unknown, and unknown is not answered: after this many the recovery
# is withdrawn and a new probe is needed.
MAX_UNSETTLED_SERVICE_RUNS = 2
_CLOCK_SKEW = timedelta(minutes=10)


def probe_cooldown_hours(base_hours: int, consecutive_refusals: int, max_hours: int) -> int:
    """Exponential back-off: base, 2x, 4x ... capped. A source that keeps refusing is asked less."""
    doublings = max(0, int(consecutive_refusals or 0) - 1)
    return int(min(max_hours, base_hours * (2 ** min(doublings, 10))))


def backoff_steps(probe: dict[str, Any] | None) -> int:
    """How many refusals the back-off counts: refused probes in a row PLUS relapses. A relapse is a
    recovery the real run then refused; the next answered probe does not forgive it, so a source
    that flaps (listing answers, search refuses) is asked less each time, not weekly for ever."""
    probe = probe or {}
    return int(probe.get("consecutive_refusals") or 0) + int(probe.get("relapses") or 0)


def _probe_index(probes: Iterable[dict[str, Any]] | None) -> dict[tuple[str, str], dict[str, Any]]:
    return {(str(p.get("product_id") or ""), str(p.get("method_id") or "")): p
            for p in (probes or ()) if isinstance(p, dict)}


def recovered_in_service(product_id: str, method_id: str, rows: Iterable[dict[str, Any]] | None,
                         probes: Iterable[dict[str, Any]] | None, *, now: datetime | None = None) -> bool:
    """Is a switched-off method back in service for THIS run? Only when its probe record says
    `recovered` AND the re-probe step granted this run a request budget.

    The state is explicit, in the probe record, and has one writer (the re-probe step). It is NOT
    derived from the absence of failing rows: the method's rows are overwritten every cycle (a
    `blocked` row becomes `disabled` the cycle after), so "no failing row since the probe" used to
    read as "in service" again every second cycle. A record that was refused real work says
    `relapsed`, and only a new probe can change that. `rows` is accepted for signature
    compatibility and is not consulted."""
    probe = _probe_index(probes).get((str(product_id), str(method_id)))
    if not probe or probe.get("result") != "recovered":
        return False
    now = now or datetime.now(timezone.utc)
    probed_at = parse_time(probe.get("probed_at"))
    granted_at = parse_time(probe.get("granted_at"))
    if probed_at is None or granted_at is None:
        return False
    if probed_at > now + _CLOCK_SKEW or granted_at > now + _CLOCK_SKEW:
        return False                      # a record from the future proves nothing
    if granted_at < probed_at or now - granted_at > SERVICE_GRANT_TTL:
        return False                      # no grant for this run: the method stays off
    return int(probe.get("grant_requests") or 0) > 0


def service_budget(service: dict[str, Any], service_runs: int) -> int:
    """The request budget of the next run of a returned method: the declared ramp step for a method
    that has answered `service_runs` real runs since its recovery, then the declared steady cap."""
    ramp = [int(n) for n in (service.get("ramp_requests") or [])]
    steady = int(service.get("max_requests_per_run") or 0)
    step = int(service_runs or 0)
    return max(0, min(steady, ramp[step] if step < len(ramp) else steady))


def advance_service(probe: dict[str, Any], rows: Iterable[dict[str, Any]] | None, now: datetime,
                    *, service: dict[str, Any], cooldown_hours: int, max_cooldown_hours: int
                    ) -> tuple[dict[str, Any], str]:
    """Settle the run a `recovered` record last granted, then grant the next one. Pure.

    Returns (record, event); event is '' (not in service), `granted` (first grant), `answered`,
    `unsettled`, `relapsed_refused` or `relapsed_unsettled`.

      * rows of the method newer than the grant, at least one answering -> the run counted:
        `service_runs` + 1 (the ramp advances); once the ramp is complete the relapse count is
        forgiven.
      * rows newer than the grant, none answering -> RELAPSE: the record becomes `relapsed`, the
        relapse count grows, the cooldown restarts from now with the grown back-off, and the
        method is out until a NEW probe answers.
      * no row newer than the grant -> the run is unsettled (the cycle was lost, or the product
        was not collected). One is tolerated and re-granted at the same ramp step; at
        MAX_UNSETTLED_SERVICE_RUNS the recovery is withdrawn (cooldown restarts, no relapse
        counted: the source did not refuse, it was never seen answering)."""
    record = dict(probe)
    if record.get("result") != "recovered":
        return record, ""
    pid, mid = str(record.get("product_id") or ""), str(record.get("method_id") or "")
    granted_at = parse_time(record.get("granted_at"))
    event = "granted"
    if granted_at is not None:
        since = [str(r.get("status") or "") for r in rows or ()
                 if isinstance(r, dict) and str(r.get("product_id") or "") == pid
                 and str(r.get("method_id") or "") == mid
                 and str(r.get("status") or "") != "disabled"
                 and (parse_time(r.get("last_run")) or granted_at) > granted_at]
        if not since:
            record["unsettled_runs"] = int(record.get("unsettled_runs") or 0) + 1
            event = "unsettled"
            if record["unsettled_runs"] >= MAX_UNSETTLED_SERVICE_RUNS:
                event = "relapsed_unsettled"
        elif any(status in RESPONDING_STATUSES for status in since):
            record["service_runs"] = int(record.get("service_runs") or 0) + 1
            record["unsettled_runs"] = 0
            event = "answered"
            if record["service_runs"] >= len(service.get("ramp_requests") or []):
                record["relapses"] = 0    # it has carried the full ramp: the flapping is over
        else:
            record["relapses"] = int(record.get("relapses") or 0) + 1
            event = "relapsed_refused"
    if event.startswith("relapsed"):
        hours = probe_cooldown_hours(int(cooldown_hours), max(1, backoff_steps(record)),
                                     int(max_cooldown_hours))
        record.update(result="relapsed", next_probe_after=format_time(now + timedelta(hours=hours)),
                      reason="service_run_refused" if event == "relapsed_refused" else "service_run_unsettled",
                      service_runs=0, unsettled_runs=0, granted_at="", grant_requests=0,
                      state_at=format_time(now))
        return record, event
    record.update(granted_at=format_time(now), state_at=format_time(now),
                  grant_requests=service_budget(service, int(record.get("service_runs") or 0)))
    return record, event


def effective_plan(product_id: str, rows: Iterable[dict[str, Any]] | None = None,
                   probes: Iterable[dict[str, Any]] | None = None,
                   *, reprobe_refusal=None, now: datetime | None = None) -> dict[str, Any]:
    """The declared plan with history applied: roles ordered, recovered methods returned to service.

    `reprobe_refusal` is `lib.acquisition_methods.reprobe_refusal` (passed in, because that module
    imports this one). A switched-off method returns ONLY as a fallback, only while
    `recovered_in_service` holds, and only if the registry's policy allows it to be re-probed at
    all -- so a probe record for a policy-closed method, however it got into the file, moves
    nothing. Without rows and probes this is exactly `plan_methods`.

    A CALLER THAT PASSES `reprobe_refusal` MUST ENFORCE THE DECLARED SERVICE BOUNDS (the granted
    request budget, the spacing, robots.txt for the paths it requests). Only the DaVinci collector
    does; the orchestration graph has no per-run request budget and therefore does not pass it."""
    plan = plan_methods(product_id)
    rows = [r for r in (rows or ()) if isinstance(r, dict)]
    history = method_history(rows, product_id)
    returned: list[str] = []
    if reprobe_refusal is not None:
        for role in ("disabled", "probe_only"):
            for method_id in list(plan[role]):
                if reprobe_refusal(method_id):
                    continue
                if recovered_in_service(product_id, method_id, rows, probes, now=now):
                    plan[role].remove(method_id)
                    returned.append(method_id)
    room = max(0, MAX_FALLBACK_METHODS - len(plan["fallback"]))
    for method_id in returned[room:]:
        plan["disabled"].append(method_id)          # no room in the bounded chain: stays off
    returned = returned[:room]
    plan["fallback"] = order_methods(plan["fallback"] + returned, history)
    plan["primary"] = order_methods(plan["primary"], history)
    if returned and not plan["fallback_when"]:
        plan["fallback_when"] = ["no_accepted_reports", "blocked", "broken"]
    plan["returned_to_service"] = returned
    return plan


def due_reprobes(rows: Iterable[dict[str, Any]] | None, probes: Iterable[dict[str, Any]] | None,
                 now: datetime, *, reprobe_refusal, reprobe_spec,
                 max_requests: int = MAX_REPROBE_REQUESTS_PER_RUN,
                 max_methods: int = MAX_REPROBE_METHODS_PER_RUN) -> list[dict[str, Any]]:
    """Which switched-off methods may be probed NOW, oldest probe first, within the run's caps.

    A method is a candidate when a plan lists it `disabled` or `probe_only`. It is skipped when the
    registry's policy refuses it (Reddit, Microsoft Learn Q&A, Adobe, paid search, or simply not
    declared), when its record says `recovered` (it is in service, or waiting for its next grant;
    a new probe would be a wasted request), or when its cooldown has not expired. The returned
    list never needs more than `max_requests` requests in total."""
    index = _probe_index(probes)
    candidates: list[dict[str, Any]] = []
    for product_id in sorted(METHOD_PLANS):
        plan = plan_methods(product_id)
        for method_id in plan["disabled"] + plan["probe_only"]:
            refusal = reprobe_refusal(method_id)
            entry = {"product_id": product_id, "method_id": method_id}
            if refusal:
                candidates.append({**entry, "due": False, "skip": refusal})
                continue
            spec = reprobe_spec(method_id) or {}
            probe = index.get((product_id, method_id)) or {}
            if probe.get("result") == "recovered":
                candidates.append({**entry, "due": False, "skip": "in_service"})
                continue
            after = parse_time(probe.get("next_probe_after"))
            if after is not None and now < after:
                candidates.append({**entry, "due": False, "skip": "cooldown",
                                   "next_probe_after": probe.get("next_probe_after")})
                continue
            candidates.append({**entry, "due": True, "spec": spec, "prior": dict(probe),
                               "last_probed_at": str(probe.get("probed_at") or ""),
                               "consecutive_refusals": int(probe.get("consecutive_refusals") or 0),
                               "relapses": int(probe.get("relapses") or 0),
                               "total_requests": int(probe.get("total_requests") or 0)})
    due = sorted((c for c in candidates if c["due"]),
                 key=lambda c: (c["last_probed_at"], c["product_id"], c["method_id"]))
    budget = max(0, int(max_requests))
    selected: list[dict[str, Any]] = []
    for item in due:
        need = int(item["spec"].get("max_requests") or 1)
        if len(selected) >= max_methods or need > budget:
            item["due"] = False
            item["skip"] = "run_cap"
            continue
        budget -= need
        selected.append(item)
    return selected + [c for c in candidates if not c["due"]]


# --- robots.txt ----------------------------------------------------------------------------------
# One evaluator for the probe and for the collector that serves a returned method, so both read the
# source's crawl rules the same way: for the user-agent token the request will really carry and
# for the exact URL it will really ask. Pure text in, verdict out.
#
# Semantics (RFC 9309): the group whose user-agent token is the longest one contained in ours
# applies, else the `*` group; within it the longest matching path pattern wins and Allow wins a
# tie; `*` matches any run of characters and a trailing `$` anchors the end. No group, or no
# matching rule, allows. A body that is not a robots file at all (an HTML page served at 200) is
# NOT read as "nothing is disallowed": it is `unreadable`, and the caller must not proceed.
def parse_robots(text: str, agent: str) -> dict[str, Any]:
    """{readable, rules: [(allow: bool, pattern)], crawl_delay: float | None} for `agent`."""
    body = str(text or "")
    head = body.lstrip()[:400].lower()
    if head.startswith("<") or "<html" in head or "<!doctype" in head:
        return {"readable": False, "rules": [], "crawl_delay": None}
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_agents = False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if current is None or not in_agents:
                current = {"agents": [], "rules": [], "crawl_delay": None}
                groups.append(current)
            current["agents"].append(value.lower())
            in_agents = True
            continue
        in_agents = False
        if current is None:
            continue
        if field in ("allow", "disallow"):
            if value:
                current["rules"].append((field == "allow", value))
        elif field == "crawl-delay":
            try:
                current["crawl_delay"] = max(0.0, float(value))
            except ValueError:
                pass
    token = str(agent or "").lower()
    best: tuple[int, dict[str, Any]] | None = None
    for group in groups:
        for name in group["agents"]:
            if name != "*" and name and name in token and (best is None or len(name) > best[0]):
                best = (len(name), group)
    if best is None:
        merged = {"rules": [], "crawl_delay": None}
        for group in groups:
            if "*" in group["agents"]:
                merged["rules"].extend(group["rules"])
                if group["crawl_delay"] is not None:
                    merged["crawl_delay"] = group["crawl_delay"]
        chosen = merged
    else:
        chosen = best[1]
    return {"readable": True, "rules": list(chosen["rules"]), "crawl_delay": chosen["crawl_delay"]}


def _robots_pattern_matches(pattern: str, target: str) -> bool:
    import re                           # stdlib; local so the module's import block stays as it was
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = ".*".join(re.escape(part) for part in body.split("*")) + ("$" if anchored else "")
    return re.match(regex, target) is not None


def robots_allows(robots: dict[str, Any], url: str) -> bool:
    """May `url` be requested under the parsed rules? False for an unreadable robots file."""
    if not robots.get("readable"):
        return False
    from urllib.parse import urlsplit   # stdlib; local so the module's import block stays as it was
    parts = urlsplit(str(url or ""))
    target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    verdict, length = True, -1
    for allow, pattern in robots.get("rules") or ():
        if _robots_pattern_matches(pattern, target):
            size = len(pattern)
            if size > length or (size == length and allow):
                verdict, length = allow, size
    return verdict
