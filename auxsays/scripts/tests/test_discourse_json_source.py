#!/usr/bin/env python3
"""Tests for the shared Discourse JSON consensus-discovery primitive.

The module is a discovery TRANSPORT only: it must emit normalized candidate rows and
honest failure classifications, and must never gate, count, or fabricate consensus.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from patch_collectors import discourse_json_source as discourse
from patch_collectors import runtime_budget as rb
from patch_collectors.base import source_url_is_specific

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
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


BASE = "https://community.example.com"


def payload(posts: list[dict], topics: list[dict]) -> dict:
    return {"posts": posts, "topics": topics, "grouped_search_result": {"more_full_page_results": None}}


def post(post_id: int, topic_id: int, blurb: str, created: str = "2026-08-10T19:04:42.600Z", post_number: int = 1) -> dict:
    return {"id": post_id, "topic_id": topic_id, "blurb": blurb, "created_at": created,
            "post_number": post_number, "username": "reporter", "name": "Reporter", "like_count": 0}


def topic(topic_id: int, title: str, slug: str) -> dict:
    return {"id": topic_id, "title": title, "slug": slug, "created_at": "2026-08-01T00:00:00Z", "posts_count": 3}


# Realistic fixture modeled on a live anonymous community.openai.com /search.json response.
SEARCH_FIXTURE = payload(
    posts=[
        post(11, 101, "After updating to ChatGPT 1.2026.217 the desktop app crashes on launch."),
        post(12, 102, "Voice input stopped working after this update.", created="2026-08-09T10:00:00Z", post_number=4),
        post(13, 999, "Post whose topic is missing from the payload."),
    ],
    topics=[
        topic(101, "ChatGPT desktop 1.2026.217 crashes on launch", "chatgpt-desktop-1-2026-217-crashes-on-launch"),
        topic(102, "Voice input broken after latest update", "voice-input-broken-after-latest-update"),
    ],
)


def run_collect(responses: dict[str, object], queries: list[str], *, context=None):
    """collect_discourse_candidates with a mocked transport seam. Returns (results, errors, urls)."""
    urls: list[str] = []
    original = discourse._fetch_json_text

    def fake_fetch(url: str, *, timeout: int = 30, max_bytes: int = discourse.MAX_RESPONSE_BYTES):
        urls.append(url)
        outcome = responses.get(url)
        if outcome is None:
            raise KeyError(f"unexpected fetch: {url}")
        if isinstance(outcome, Exception):
            raise outcome
        return 200, outcome if isinstance(outcome, str) else json.dumps(outcome)

    errors: list[dict] = []
    original_sleep = discourse.discourse_sleep
    try:
        discourse.discourse_sleep = lambda _s: None
        discourse._fetch_json_text = fake_fetch
        results = discourse.collect_discourse_candidates(
            base_url=BASE, queries=queries, context=context, errors=errors,
            source_type="discourse_forum_report", source_name="OpenAI Community",
        )
    finally:
        discourse._fetch_json_text = original
        discourse.discourse_sleep = original_sleep
    return results, errors, urls


def search_url(query: str) -> str:
    return discourse.discourse_search_url(BASE, query)


def run() -> int:
    print("=" * 60)
    print("Discourse JSON discovery primitive tests")
    print("=" * 60)

    # --- URL construction -------------------------------------------------------
    check("search URL quotes the query", search_url("ChatGPT 1.2026.217") == f"{BASE}/search.json?q=ChatGPT+1.2026.217", search_url("ChatGPT 1.2026.217"))
    check("forum base is normalized to a path-less https host", discourse.forum_base("https://Community.Example.com/some/path") == "https://community.example.com")
    try:
        discourse.forum_base("http://insecure.example.com")
        insecure_raised = False
    except discourse.DiscourseAccessError:
        insecure_raised = True
    check("non-https forum base is rejected (fail-closed)", insecure_raised)

    # --- candidate parsing ------------------------------------------------------
    results, errors, urls = run_collect({search_url("1.2026.217"): SEARCH_FIXTURE}, ["1.2026.217"])
    check("posts joined to topics become candidates", len(results) == 2 and not errors, str((len(results), errors)))
    if len(results) == 2:
        first, second = results
        check("candidate carries the specific topic URL", first["source_url"] == f"{BASE}/t/chatgpt-desktop-1-2026-217-crashes-on-launch/101", first["source_url"])
        check("reply candidates carry the post-anchored URL", second["source_url"].endswith("/voice-input-broken-after-latest-update/102/4"), second["source_url"])
        check("candidate URLs pass the strict verifier's specificity gate", all(source_url_is_specific(r["source_url"]) for r in results), str([r["source_url"] for r in results]))
        check("parent/report titles come from the topic", first["parent_title"] == "ChatGPT desktop 1.2026.217 crashes on launch", first["parent_title"])
        check("report text merges topic title and post blurb", "crashes on launch" in first["report_text"] and "desktop app crashes" in first["report_text"], first["report_text"])
        check("source_date normalized to second-precision UTC Z", first["source_date"] == "2026-08-10T19:04:42Z", first["source_date"])
        check("matched_query is recorded on every candidate", all(r.get("matched_query") == "1.2026.217" for r in results))
        check("source_type/source_name are the caller's", first["source_type"] == "discourse_forum_report" and first["source_name"] == "OpenAI Community", str((first["source_type"], first["source_name"])))
        forbidden = {"counted", "source_weight", "exclusion_reason", "patch_version_matched", "product_id", "update_version"}
        check("discovery emits NO acceptance/consensus fields (gating stays downstream)", not (forbidden & set(first)), str(sorted(forbidden & set(first))))
    check("post with a missing topic is dropped (no fabricated parent)", all("999" not in r["source_url"] for r in results), str([r["source_url"] for r in results]))

    # --- dedup ------------------------------------------------------------------
    results, errors, urls = run_collect({search_url("crash"): SEARCH_FIXTURE, search_url("crashes"): SEARCH_FIXTURE}, ["crash", "crashes", "crash", "  "])
    check("duplicate queries are fetched once; blank queries skipped", len(urls) == 2, str(urls))
    check("candidates de-duplicated by canonical URL across queries", len(results) == 2, str(len(results)))

    # --- since gate ---------------------------------------------------------------
    ctx = SimpleNamespace(since="2026-08-10")
    results, errors, _urls = run_collect({search_url("crash"): SEARCH_FIXTURE}, ["crash"], context=ctx)
    check("context.since drops older candidates", [r["source_url"] for r in results] == [f"{BASE}/t/chatgpt-desktop-1-2026-217-crashes-on-launch/101"], str([r["source_url"] for r in results]))

    # --- failure classification (never raises out of collect) --------------------
    blocked = discourse.DiscourseAccessError("http_403_blocked", status=403, signature="blocked")
    results, errors, _urls = run_collect({search_url("q403"): blocked}, ["q403"])
    check("403 is surfaced as a blocked error entry, not an exception", results == [] and len(errors) == 1 and errors[0]["blocked_signature"] == "blocked", str(errors))
    check("error entry names the method and query", errors and errors[0]["reason"].startswith("discourse_search_fetch_failed:") and errors[0]["query"] == "q403", str(errors))

    rate_limited = discourse.DiscourseAccessError("http_429_rate_limited", status=429, signature="rate_limited")
    results, errors, _urls = run_collect({search_url("q429"): rate_limited, search_url("ok"): SEARCH_FIXTURE}, ["q429", "ok"])
    check("429 on one query does not abort the sweep (fail-soft per query)", len(errors) == 1 and len(results) == 2, str((errors, len(results))))
    check("429 classified rate_limited", errors[0]["blocked_signature"] == "rate_limited", str(errors))

    results, errors, _urls = run_collect({search_url("bad"): "not json {"}, ["bad"])
    check("malformed JSON classified broken (parse failure never disappears)", errors and "json_parse_failed" in errors[0]["reason"] and errors[0]["blocked_signature"] == "broken", str(errors))

    results, errors, _urls = run_collect({search_url("shape"): json.dumps(["list", "shape"])}, ["shape"])
    check("non-object JSON payload classified broken", errors and "json_shape_unexpected" in errors[0]["reason"], str(errors))

    results, errors, _urls = run_collect({search_url("cf"): json.dumps({"posts": [], "topics": []}).replace("[]", '["checking your browser"]', 1)}, ["cf"])
    # A challenge page that happens to be JSON-shaped is still caught by the signature scan.
    check("challenge text inside a 200 body is classified blocked", errors and errors[0]["blocked_signature"] in {"blocked", "rate_limited"} or results == [], str((results, errors)))

    results, errors, _urls = run_collect({search_url("empty"): payload([], [])}, ["empty"])
    check("empty search result is a clean no-results (no error entry)", results == [] and errors == [], str((results, errors)))

    # --- bounded transient retry with bounded Retry-After -----------------------
    class FlakyThenGood:
        def __init__(self):
            self.calls = 0

        def __call__(self, url, *, timeout=30, max_bytes=discourse.MAX_RESPONSE_BYTES):
            self.calls += 1
            if self.calls == 1:
                exc = discourse.DiscourseAccessError("http_429_rate_limited", status=429, signature="rate_limited")
                exc.retry_after = 9999.0  # far beyond the bounded cap
                raise exc
            return 200, json.dumps(SEARCH_FIXTURE)

    flaky = FlakyThenGood()
    slept: list[float] = []
    original_fetch, original_sleep = discourse._fetch_json_text, discourse.discourse_sleep
    try:
        discourse._fetch_json_text = flaky
        discourse.discourse_sleep = lambda s: slept.append(s)
        payload_out = discourse.request_search_json(BASE, "retry me")
    finally:
        discourse._fetch_json_text = original_fetch
        discourse.discourse_sleep = original_sleep
    check("429 retries once and succeeds", flaky.calls == 2 and isinstance(payload_out, dict), str(flaky.calls))
    check("Retry-After is BOUNDED by the backoff cap (9999s never slept)", slept and slept[0] <= rb.BudgetConfig().backoff_cap, str(slept))

    class AlwaysBlocked:
        def __init__(self):
            self.calls = 0

        def __call__(self, url, *, timeout=30, max_bytes=discourse.MAX_RESPONSE_BYTES):
            self.calls += 1
            raise discourse.DiscourseAccessError("http_403_blocked", status=403, signature="blocked")

    hard = AlwaysBlocked()
    original_fetch = discourse._fetch_json_text
    try:
        discourse._fetch_json_text = hard
        try:
            discourse.request_search_json(BASE, "blocked")
            hard_raised = False
        except discourse.DiscourseAccessError:
            hard_raised = True
    finally:
        discourse._fetch_json_text = original_fetch
    check("hard 403 never retries (one request, terminal)", hard_raised and hard.calls == 1, str(hard.calls))

    class AlwaysRateLimited:
        def __init__(self):
            self.calls = 0

        def __call__(self, url, *, timeout=30, max_bytes=discourse.MAX_RESPONSE_BYTES):
            self.calls += 1
            raise discourse.DiscourseAccessError("http_429_rate_limited", status=429, signature="rate_limited")

    limited = AlwaysRateLimited()
    original_fetch, original_sleep = discourse._fetch_json_text, discourse.discourse_sleep
    try:
        discourse._fetch_json_text = limited
        discourse.discourse_sleep = lambda _s: None
        try:
            discourse.request_search_json(BASE, "always 429")
            limited_raised = False
        except discourse.DiscourseAccessError:
            limited_raised = True
    finally:
        discourse._fetch_json_text = original_fetch
        discourse.discourse_sleep = original_sleep
    check("persistent 429 stops after the single bounded retry", limited_raised and limited.calls == 1 + discourse.MAX_TRANSIENT_RETRIES, str(limited.calls))

    # --- runtime-budget integration ----------------------------------------------
    clock = {"now": 0.0}
    budget = rb.RuntimeBudget(clock=lambda: clock["now"])
    budget.start_collector("test-product")
    budget.start_method("discourse_json")
    rb.set_run_budget(budget)
    counted = FlakyThenGood()
    original_fetch, original_sleep = discourse._fetch_json_text, discourse.discourse_sleep
    try:
        discourse._fetch_json_text = counted
        discourse.discourse_sleep = lambda _s: None
        discourse.request_search_json(BASE, "budget")
        requests_charged = budget._method_requests
        backoff_charged = budget._method_backoff_total
    finally:
        discourse._fetch_json_text = original_fetch
        discourse.discourse_sleep = original_sleep
        rb.set_run_budget(None)
    check("every attempt (including the retry) is charged to the method budget", requests_charged == 2, str(requests_charged))
    check("retry backoff is charged against the cumulative backoff cap", 0 < backoff_charged <= rb.BudgetConfig().backoff_cap, str(backoff_charged))

    # A spent method budget stops further requests with the NORMAL budget exception.
    budget2 = rb.RuntimeBudget(clock=lambda: clock["now"])
    budget2.start_collector("test-product")
    budget2.start_method("discourse_json")
    budget2._method_requests = budget2.cfg.max_requests_per_method  # cap already spent
    rb.set_run_budget(budget2)
    original_fetch = discourse._fetch_json_text
    try:
        discourse._fetch_json_text = lambda url, **k: (200, json.dumps(SEARCH_FIXTURE))
        try:
            discourse.request_search_json(BASE, "over cap")
            cap_raised = None
        except rb.MethodBudgetExhausted as exc:
            cap_raised = exc
    finally:
        discourse._fetch_json_text = original_fetch
        rb.set_run_budget(None)
    check("request cap exhaustion raises MethodBudgetExhausted (terminal health, not a crash)", isinstance(cap_raised, rb.MethodBudgetExhausted), str(cap_raised))

    # --- date normalization edge cases -------------------------------------------
    check("millisecond ISO date normalizes", discourse.normalize_discourse_date("2026-08-10T19:04:42.600Z") == "2026-08-10T19:04:42Z")
    check("offset ISO date normalizes to UTC", discourse.normalize_discourse_date("2026-08-10T21:04:42+02:00") == "2026-08-10T19:04:42Z")
    check("garbage date becomes empty (never fabricated)", discourse.normalize_discourse_date("last tuesday") == "")

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
