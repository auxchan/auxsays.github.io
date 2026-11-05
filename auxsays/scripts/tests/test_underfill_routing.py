#!/usr/bin/env python3
"""Underfilled-evidence routing (B3 §12, AUX-073): the plan table and its three pure functions.

Offline, deterministic, no file or network access beyond importing the modules.

    P  plan_underfill       Windows declares exactly one enrichment adapter; every other product
                            declares none; every malformed plan is refused, not repaired
    U  underfill_justified  the trigger is the shipped certifier's own verdict: count reasons only,
                            inside the window; anything else fails closed. Prefixes are COMPUTED from
                            `live_eligibility.evaluate` on a fixture, not restated
    O  underfill_order      deterministic for any input order; recency reserve first (AUTH v2.16 D3:
                            the current patch is never starved by older ones), then closable-first;
                            caps apply to real GETs after ordering; a shared URL is fetched once

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_underfill_routing.py
"""
from __future__ import annotations

import itertools
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import live_eligibility as le  # noqa: E402
from lib import maturity  # noqa: E402
from lib import method_routing as mr  # noqa: E402
from lib import monitoring_health as mh  # noqa: E402
from lib.report_counts import CONSENSUS_PROMOTION_PRODUCTS  # noqa: E402

NEWLINE = chr(10)
_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


def refused(product_id: str, plan: dict) -> str:
    """The ValueError text plan_underfill raises for `plan`, or '' when it accepts it."""
    try:
        mr.plan_underfill(product_id, plans={product_id: plan})
    except ValueError as exc:
        return str(exc) or "refused"
    return ""


WIN = "microsoft-windows-11"
NOW = datetime(2026, 11, 5, 2, 54, 57, tzinfo=timezone.utc)
THRESHOLDS = mh.Thresholds(max_age_days=14, min_healthy_families=2)


def record(build: str, published: str = "2026-09-14T00:00:00Z") -> dict:
    return {"product_id": WIN, "update_version": "25H2", "target_build": build,
            "update_published_at": published, "update_entry": True}


def health(build: str, status: str = "success", method: str = "learn_qna_search_rss",
           source_type: str = "microsoft_learn_qna") -> dict:
    return {"product_id": WIN, "update_version": "25H2", "target_build": build, "method_id": method,
            "source_type": source_type, "status": status, "last_run": "2026-11-05T01:00:00Z"}


def counted(build: str, n: int) -> list[dict]:
    return [{"product_id": WIN, "update_version": "25H2", "target_build": build,
             "source_type": "microsoft_learn_qna", "counted": True, "patch_version_matched": True,
             "source_url": f"https://learn.microsoft.com/en-us/answers/questions/{9_000_000 + i}/r",
             "source_date_pass": True, "sentiment": "negative", "severity": "high"} for i in range(n)]


def ev(build: str, n: int, rows: list[dict]) -> maturity.LiveDecision:
    key = (WIN, "25H2", build)
    return le.evaluate(record(build), {key: counted(build, n)}, emh_rows=rows, now=NOW,
                       thresholds=THRESHOLDS)


def entry(key: tuple, release: str, shortfall: int, urls: list[str], date: str = "2026-10-20") -> dict:
    return {"key": key, "release_date": release, "shortfall": shortfall,
            "queue": [{"url": u, "date": date} for u in urls]}


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Underfilled-evidence routing (B3 §12, AUX-073)")
    print("=" * 78)

    # ------------------------------------------------------------------ P. plan_underfill
    print(NEWLINE + "[P] plan_underfill")
    try:
        plan = mr.plan_underfill(WIN)
    except ValueError as exc:  # the SHIPPED plan must validate; a refusal is this check failing
        plan, plan_error = None, str(exc)
    else:
        plan_error = ""
    check("P1 Windows declares learn_qna_question_hydration as its one ENRICHMENT adapter, 90 days, "
          "45/run, 30/identity, the two excerpt-explainable reasons",
          plan is not None and plan["adapters"] == ["learn_qna_question_hydration"]
          and plan["role"] == "enrichment" and plan["window_days"] == 90
          and plan["max_fetches_per_run"] == 45 and plan["max_fetches_per_identity"] == 30
          and sorted(plan["enrichable_reasons"]) == ["missing_kb_or_build", "missing_update_attribution"]
          and 0 < plan["recency_reserve"] < plan["max_fetches_per_run"], str(plan) if plan else plan_error)
    others = sorted((set(CONSENSUS_PROMOTION_PRODUCTS) | set(mr.METHOD_PLANS) | {"adobe-photoshop"}) - {WIN})
    check("P2 every other product resolves to NO underfill plan (v1 is Windows only)",
          len(others) >= 6 and all(mr.plan_underfill(p) is None for p in others), str(others))
    base = dict(mr.UNDERFILL_PLANS[WIN])
    check("P3 an unknown role is refused", bool(refused(WIN, {**base, "role": "fallback"}))
          and bool(refused(WIN, {**base, "role": "underfill"})))
    check("P4 window_days above UNDERFILL_MAX_WINDOW_DAYS (90) is refused; 90 itself is accepted",
          mr.UNDERFILL_MAX_WINDOW_DAYS == 90 and bool(refused(WIN, {**base, "window_days": 91}))
          and not refused(WIN, {**base, "window_days": 90}) and not refused(WIN, {**base, "window_days": 60}))
    check("P5 window_days <= 0 (and a bool) is refused",
          all(refused(WIN, {**base, "window_days": v}) for v in (0, -1, True, "90")))
    check("P6 a product whose projections no lane rebuilds is refused",
          "adobe-photoshop" not in CONSENSUS_PROMOTION_PRODUCTS
          and "promotion product" in refused("adobe-photoshop", base))
    check("P7 a method that is already in a METHOD_PLANS role is refused (one method, one role)",
          "declared both" in refused("microsoft-powerpoint", {**base, "adapters": ["learn_qna_search_rss"]})
          and "declared both" in refused("adobe-premiere-pro", {**base, "adapters": ["reddit_search"]}))
    check("P8 a method listed twice in the adapters is refused",
          "declared both" in refused(WIN, {**base, "adapters": ["learn_qna_question_hydration"] * 2}))
    check("P9 a veto is never re-judged: an enrichable reason outside the two is refused",
          all(refused(WIN, {**base, "enrichable_reasons": [*base["enrichable_reasons"], extra]})
              for extra in ("wrong_kb_for_current_patch", "generic_support_request", "vague_latest_update",
                            "cross_patch_duplicate", "date_before_release"))
          and bool(refused(WIN, {**base, "enrichable_reasons": []})))
    check("P10 caps are validated: non-positive, inverted, or a reserve above the run cap",
          bool(refused(WIN, {**base, "max_fetches_per_run": 0}))
          and bool(refused(WIN, {**base, "max_fetches_per_identity": 46}))
          and bool(refused(WIN, {**base, "recency_reserve": 46}))
          and bool(refused(WIN, {**base, "recency_reserve": -1})))
    check("P11 METHOD_PLANS and plan_methods are untouched: Windows still routes through DEFAULT_PLAN",
          set(mr.METHOD_PLANS) == {"microsoft-powerpoint", "adobe-premiere-pro"}
          and mr.plan_methods(WIN) == {k: [] for k in ("primary", "fallback", "fallback_when",
                                                       "probe_only", "disabled")})

    # ------------------------------------------------------------------ U. underfill_justified
    print(NEWLINE + "[U] underfill_justified, judged on the shipped evaluate's own reasons")
    b = "26200.9457"
    healthy = [health(b), health(b, "no_results", "techcommunity_windows_sitemap", "microsoft_tech_community")]
    short = ev(b, 27, healthy)
    ok, why = mr.underfill_justified(short.live, short.reasons, release_age_days=52.1, window_days=90)
    check("U1 a healthy patch short of the rung is justified (reasons computed by evaluate)",
          ok and why == "underfilled" and not short.live and short.reasons
          and all(r.startswith(mr.UNDERFILL_COUNT_PREFIXES) for r in short.reasons), str(short.reasons))
    live = ev(b, 35, healthy)
    check("U2 a live patch is never justified",
          live.live and mr.underfill_justified(live.live, live.reasons, release_age_days=10,
                                               window_days=90) == (False, "live"), str(live.reasons))
    degraded = ev(b, 27, [health(b, "partial"), healthy[1]])
    missing = ev(b, 27, [healthy[1]])
    check("U3 a degraded or missing primary row is certifier_unreachable: nothing is fetched for it",
          any(r.startswith("monitoring:") for r in degraded.reasons)
          and mr.underfill_justified(degraded.live, degraded.reasons, release_age_days=10,
                                     window_days=90) == (False, "certifier_unreachable")
          and mr.underfill_justified(missing.live, missing.reasons, release_age_days=10,
                                     window_days=90) == (False, "certifier_unreachable"),
          f"{degraded.reasons} / {missing.reasons}")
    check("U4 the window is inclusive at its edge and closed beyond it; an undated release is outside",
          mr.underfill_justified(False, short.reasons, release_age_days=90.0, window_days=90)[0]
          and mr.underfill_justified(False, short.reasons, release_age_days=90.01, window_days=90)
          == (False, "outside_recency_window")
          and mr.underfill_justified(False, short.reasons, release_age_days=None, window_days=90)
          == (False, "outside_recency_window"))
    zero = ev(b, 0, healthy)
    emitted = {p for p in mr.UNDERFILL_COUNT_PREFIXES if any(r.startswith(p) for r in zero.reasons)}
    check("U5 every prefix the trigger keys on is one the shipped evaluate actually emits",
          emitted == set(mr.UNDERFILL_COUNT_PREFIXES) and len(emitted) == 2, str(zero.reasons))
    check("U6 an unknown reason fails closed, as does a refusal that names no reason",
          mr.underfill_justified(False, ("below_high_rung:3", "a_future_reason:1"), release_age_days=5,
                                 window_days=90) == (False, "certifier_unreachable")
          and mr.underfill_justified(False, (), release_age_days=5, window_days=90)
          == (False, "certifier_unreachable"))
    try:
        mr.underfill_justified(False, short.reasons, release_age_days=5, window_days=91)
        window_guard = False
    except ValueError:
        window_guard = True
    check("U7 the function itself refuses a window above the hard cap", window_guard)

    # ------------------------------------------------------------------ O. underfill_order
    print(NEWLINE + "[O] underfill_order")
    k_new = (WIN, "26H2", "26300.9818")       # newest, not closable
    k_mid = (WIN, "26H2", "26300.9711")       # closable
    k_mid_s = (WIN, "25H2", "26200.9711")     # same release, larger shortfall
    k_old = (WIN, "25H2", "26200.9457")       # older, closable
    entries = [
        entry(k_new, "2026-10-28T00:00:00Z", 20, ["n1", "n2", "n3"]),
        entry(k_mid, "2026-10-13T00:00:00Z", 2, ["m1", "m2", "shared"]),
        entry(k_mid_s, "2026-10-13T00:00:00Z", 24, ["shared", "s1"]),
        entry(k_old, "2026-09-14T00:00:00Z", 1, ["o1", "o2"]),
    ]
    caps = {"max_fetches_per_run": 45, "max_fetches_per_identity": 30}
    reference = mr.underfill_order(entries, recency_reserve=2, **caps)
    check("O1 the plan is identical for every permutation of the input (24 orders)",
          all(mr.underfill_order(list(p), recency_reserve=2, **caps) == reference
              for p in itertools.permutations(entries)))
    check("O2 reserve to the NEWEST patch first, then closable-first by newest release, then the rest",
          reference["fetch"] == ["n1", "n2", "m1", "m2", "shared", "o1", "o2", "n3", "s1"],
          str(reference["fetch"]))
    check("O3 a URL two siblings queued is fetched once, charged to the first, and served to both",
          reference["fetch"].count("shared") == 1 and reference["charged"]["shared"] == k_mid
          and "shared" in reference["served"][k_mid_s] and "shared" in reference["served"][k_mid])
    tie = mr.underfill_order([entry((WIN, "25H2", "26200.1"), "2026-10-13", 5, ["a"]),
                              entry((WIN, "26H2", "26300.1"), "2026-10-13", 5, ["b"])],
                             recency_reserve=0, **caps)
    check("O4 equal release and shortfall: ties break on version then build, newest first (as the walk)",
          tie["fetch"] == ["b", "a"], str(tie["fetch"]))
    capped = mr.underfill_order(entries, recency_reserve=2, max_fetches_per_run=4, max_fetches_per_identity=2)
    check("O5 the caps apply to real GETs AFTER ordering: the run cap truncates, the identity cap skips",
          capped["fetch"] == ["n1", "n2", "m1", "m2"]
          and mr.underfill_order(entries, recency_reserve=0, max_fetches_per_run=45,
                                 max_fetches_per_identity=1)["fetch"] == ["m1", "o1", "n1", "s1"]
          and capped["not_reached"][k_old] == ["o1", "o2"], f"{capped['fetch']}")
    dated = mr.underfill_order([entry(k_old, "2026-09-14", 1, [])
                                | {"queue": [{"url": "late", "date": "2026-10-30"},
                                             {"url": "early", "date": "2026-09-20"},
                                             {"url": "late2", "date": "2026-10-30"}]}],
                               recency_reserve=0, **caps)
    check("O6 within one identity: newest discovery date first, then URL",
          dated["fetch"] == ["late", "late2", "early"], str(dated["fetch"]))

    # D3 PIN. Older patches that could each absorb the whole per-run budget must not take every fetch
    # while the current patch gets none. Without the reserve they do; with it, the newest is served.
    old_a = (WIN, "25H2", "26200.9000")
    old_b = (WIN, "24H2", "26100.9000")
    current = (WIN, "26H2", "26300.9818")
    starve = [entry(old_a, "2026-08-11", 5, [f"a{i:02d}" for i in range(30)]),
              entry(old_b, "2026-08-11", 6, [f"b{i:02d}" for i in range(30)]),
              entry(current, "2026-10-28", 33, [f"c{i}" for i in range(8)])]
    without = mr.underfill_order(starve, recency_reserve=0, **caps)
    reserve = mr.UNDERFILL_PLANS[WIN]["recency_reserve"]
    with_plan = mr.underfill_order(starve, recency_reserve=reserve, **caps)
    got_current = sum(1 for u in with_plan["fetch"] if with_plan["charged"][u] == current)
    check("O7 D3: with the shipped reserve the CURRENT patch is fetched even when older closable "
          "patches could take all 45; without a reserve it would get none",
          not any(without["charged"][u] == current for u in without["fetch"])
          and got_current == min(8, reserve) and len(with_plan["fetch"]) == 45
          and with_plan["fetch"][:reserve] == [f"c{i}" for i in range(reserve)],
          f"current got {got_current}, reserve {reserve}")
    # The measured run-1 shape (B3 pool.json, L1 §9): the reserve costs the closable patches at most
    # its own size and leaves both of them reached in the same run.
    measured = [entry((WIN, "26H2", "26300.9818"), "2026-10-28", 20, [f"x{i}" for i in range(5)]),
                entry((WIN, "26H2", "26300.9711"), "2026-10-13", 13, [f"y{i:02d}" for i in range(26)]),
                entry((WIN, "25H2", "26200.9457"), "2026-09-14", 6, [f"z{i:02d}" for i in range(15)]),
                entry((WIN, "25H2", "26200.9550"), "2026-09-22", 21, [f"w{i:02d}" for i in range(16)])]
    m = mr.underfill_order(measured, recency_reserve=reserve, **caps)
    per = {e["key"][2]: sum(1 for u in m["fetch"] if m["charged"][u] == e["key"]) for e in measured}
    check("O8 the measured run-1 shape: newest patch served, 26H2 9711 fully reached, 25H2 9457 "
          "reached for all but the reserve's cost, the non-closable older patch not before them",
          per["26300.9818"] == 5 and per["26300.9711"] == 26 and per["26200.9457"] == 14
          and per["26200.9550"] == 0 and len(m["fetch"]) == 45, str(per))

    print()
    print("=" * 78)
    for err in _ERRORS:
        print(f"  - {err}")
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
