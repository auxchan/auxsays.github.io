#!/usr/bin/env python3
"""Tests for the hardened DaVinci Reddit evidence discovery (davinci.py).

Offline only: transport is monkeypatched and every sleep is stubbed, so no live
Reddit request and no wall-clock delay occur. Covers (A) bounded retry/backoff for
transient 429/5xx (and no-retry for hard 403 blocks), (B) honest method-health
classification (429/rate-limit -> blocked/partial, not broken), and (C) that the
existing strict acceptance gates are preserved for Reddit candidates.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_reddit_source.py
"""
from __future__ import annotations

import sys
import traceback
import types
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

# Local/CI environments may lack PyYAML; the gate + transport helpers here need no YAML I/O.
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda *_a, **_k: {}, safe_dump=lambda *_a, **_k: ""))

from patch_collectors.base import CollectorContext, PatchRecord
import patch_collectors.davinci as davinci
from patch_collectors.davinci import (
    SourceAccessError,
    evaluate_candidates,
    method_status,
    reddit_backoff_delay,
    reddit_candidate,
    reddit_feed_candidates,
    request_with_backoff,
    row_from_candidate,
)

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


def stable_record() -> PatchRecord:
    return PatchRecord(
        product_id="blackmagic-davinci",
        update_version="21",
        path=Path("auxsays/updates/generated/2026-04-14-davinci-resolve-21.md"),
        update_published_at="2026-04-14",
        update_status="current",
        update_product="DaVinci Resolve",
    )


def epoch(y, m, d, h=12) -> float:
    return datetime(y, m, d, h, tzinfo=timezone.utc).timestamp()


def rc(title, selftext, created_utc, slug="dr21_issue") -> dict:
    """Build a Reddit candidate via the production reddit_candidate() mapper."""
    return reddit_candidate({
        "title": title,
        "selftext": selftext,
        "created_utc": created_utc,
        "permalink": f"/r/davinciresolve/comments/abc123/{slug}/",
    })


CAP = "2026-04-20T00:00:00Z"

RSS_OK = """<?xml version="1.0"?><rss><channel>
<item><title>DaVinci Resolve 21 render crash on export</title>
<link>https://www.reddit.com/r/davinciresolve/comments/xyz789/dr21_render_crash/</link>
<pubDate>Mon, 20 Apr 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""

# An Atom entry missing link/updated fields — must not crash the parser.
ATOM_PARTIAL = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>DaVinci Resolve 21 crash</title></entry>
</feed>"""


def with_stubbed_sleep(fn):
    """Run fn() with davinci.reddit_sleep stubbed to a recorder; return (result_or_exc, delays)."""
    delays: list[float] = []
    original = davinci.reddit_sleep
    davinci.reddit_sleep = lambda d: delays.append(d)
    try:
        try:
            return ("ok", fn(), delays)
        except SourceAccessError as exc:
            return ("raised", exc, delays)
    finally:
        davinci.reddit_sleep = original


def run() -> int:
    print("=" * 60)
    print("DaVinci Reddit hardening tests")
    print("=" * 60)
    record = stable_record()

    # --- A. bounded retry/backoff -------------------------------------------
    calls = {"n": 0}
    def fetch_429_then_ok():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise SourceAccessError("http_429_Too Many Requests", status=429, blocked_signature="rate_limited")
        return "PAYLOAD"
    kind, result, delays = with_stubbed_sleep(lambda: request_with_backoff(fetch_429_then_ok))
    check("429 retried then succeeds within bounded retries", kind == "ok" and result == "PAYLOAD" and len(delays) == 2, f"{kind} {result} delays={delays}")
    check("backoff is deterministic increasing (1.5, 3.0)", delays == [1.5, 3.0], str(delays))

    def fetch_503_always():
        raise SourceAccessError("http_503_Service Unavailable", status=503)
    kind, result, delays = with_stubbed_sleep(lambda: request_with_backoff(fetch_503_always))
    check("transient 5xx retried then raises after exhausting retries", kind == "raised" and len(delays) == 2, f"{kind} delays={delays}")

    def fetch_403():
        raise SourceAccessError("http_403_Blocked", status=403, blocked_signature="blocked")
    kind, result, delays = with_stubbed_sleep(lambda: request_with_backoff(fetch_403))
    check("hard 403 block is NOT retried (fails fast, no sleep)", kind == "raised" and delays == [], f"{kind} delays={delays}")

    check("Retry-After honored (capped)", reddit_backoff_delay(SourceAccessError("http_429", status=429, retry_after=5.0), 0) == 5.0)
    check("Retry-After above cap is clamped", reddit_backoff_delay(SourceAccessError("http_429", status=429, retry_after=999.0), 0) == 20.0)
    check("no Retry-After -> exponential backoff", reddit_backoff_delay(SourceAccessError("http_429", status=429), 1) == 3.0)
    check("429 classified transient", davinci.is_transient_reddit_error(SourceAccessError("http_429", status=429)) is True)
    check("403 classified non-transient", davinci.is_transient_reddit_error(SourceAccessError("http_403", status=403, blocked_signature="blocked")) is False)

    # --- B. honest method-health classification -----------------------------
    check("pure 429 outcome -> blocked (not broken)", method_status([], [], [], [{"reason": "reddit_search_feed_fetch_failed:http_429_Too Many Requests"}]) == "blocked")
    check("rate_limited signature -> blocked", method_status([], [], [], [{"reason": "reddit_listing_fetch_failed:all_reddit_endpoint_attempts_failed[reddit_listing_www_json=http_429:rate_limited]"}]) == "blocked")
    check("403 blocked outcome -> blocked", method_status([], [], [], [{"reason": "reddit_search_fetch_failed:http_403_Blocked:blocked"}]) == "blocked")
    accepted_stub = [{"counted": True}]
    check("mixed accepted + 429 -> partial", method_status([{"x": 1}], accepted_stub, [], [{"reason": "http_429 too many requests"}]) == "partial")
    check("candidates found but all rejected -> no_results", method_status([{"x": 1}], [], [{"counted": False}], []) == "no_results")
    check("empty (source reached, nothing relevant) -> no_results", method_status([], [], [], []) == "no_results")
    check("parser/decode error (not a block) -> broken", method_status([], [], [], [{"reason": "reddit_search_fetch_failed:json_decode_failed:JSONDecodeError"}]) == "broken")

    # --- C. acceptance gates preserved (Reddit candidates) ------------------
    concrete = rc("DaVinci Resolve 21 render crash on export", "Every render crashes after updating to DaVinci Resolve 21 on Windows.", epoch(2026, 4, 20))
    row = row_from_candidate(record, concrete, CAP)
    check("exact-version concrete DaVinci crash accepted", row.get("counted") is True and row.get("exclusion_reason") in (None, ""), str(row.get("exclusion_reason")))
    check("accepted row carries required evidence fields", all(row.get(k) for k in ("source_url", "source_type", "source_name", "report_title", "report_text_excerpt", "source_date", "match_basis", "issue_theme", "workflow_area")) and row.get("source_url").startswith("https://www.reddit.com/r/davinciresolve/comments/"), str({k: row.get(k) for k in ("source_url", "match_basis", "issue_theme")}))

    generic = rc("DaVinci Resolve 21 — should I update?", "Thinking about updating to 21. Is it safe? Anyone recommend it?", epoch(2026, 4, 20), slug="should_i_update")
    grow = row_from_candidate(record, generic, CAP)
    check("generic 'should I update / anyone' rejected", grow.get("counted") is False and grow.get("exclusion_reason") == "not_a_real_issue_report", str(grow.get("exclusion_reason")))

    pre = rc("DaVinci Resolve 21 crash on launch", "Resolve 21 crashes on launch every time.", epoch(2026, 4, 10), slug="pre_release_crash")
    prow = row_from_candidate(record, pre, CAP)
    check("report dated before release rejected", prow.get("counted") is False and prow.get("exclusion_reason") == "source_date_before_or_unverified_against_release", str(prow.get("exclusion_reason")))

    latest = rc("DaVinci Resolve latest version keeps crashing", "The newest DaVinci Resolve crashes constantly.", epoch(2026, 4, 20), slug="latest_crash")
    lrow = row_from_candidate(record, latest, CAP)
    check("'latest version' with no exact patch rejected", lrow.get("counted") is False and lrow.get("exclusion_reason") == "missing_exact_patch_version_match", str(lrow.get("exclusion_reason")))

    official = rc("DaVinci Resolve 21 released!", "Version 21 is now available for download. New features and improvements.", epoch(2026, 4, 20), slug="release_announcement")
    orow = row_from_candidate(record, official, CAP)
    check("official/announcement post (no concrete issue) not counted", orow.get("counted") is False and orow.get("exclusion_reason") == "not_a_real_issue_report", str(orow.get("exclusion_reason")))

    dup_a = rc("DaVinci Resolve 21 render crash", "Render crashes in DaVinci Resolve 21.", epoch(2026, 4, 20), slug="dup_crash")
    dup_b = rc("DaVinci Resolve 21 render crash (repost)", "Render crashes in DaVinci Resolve 21.", epoch(2026, 4, 21), slug="dup_crash")  # same permalink slug -> same URL
    acc, rej = evaluate_candidates(record, [dup_a, dup_b], CAP, set())
    check("duplicate Reddit URL is deduped (one accepted)", len(acc) == 1, f"accepted={len(acc)} rejected={len(rej)}")

    # --- RSS/Atom parsing ----------------------------------------------------
    check("well-formed RSS parses to a candidate", len(reddit_feed_candidates(RSS_OK)) == 1, str(reddit_feed_candidates(RSS_OK)))
    check("partial/missing Atom fields do not crash the parser", isinstance(reddit_feed_candidates(ATOM_PARTIAL), list))

    # --- end-to-end reddit_search_candidates (transport monkeypatched) ------
    post = {"title": "DaVinci Resolve 21 render crash", "selftext": "crash on render", "created_utc": epoch(2026, 4, 20), "permalink": "/r/davinciresolve/comments/ee1/dr21_crash/"}
    orig_json = davinci.request_reddit_json_with_fallback
    orig_feed_disc = davinci.reddit_feed_discovery_candidates
    try:
        davinci.request_reddit_json_with_fallback = lambda attempts: {"data": {"children": [{"data": post}], "after": None}}
        davinci.reddit_feed_discovery_candidates = lambda rec, ctx, errs: []
        errors: list = []
        cands = davinci.reddit_search_candidates(record, CollectorContext(write=False, since=None, max_pages=1), errors)
        check("Reddit JSON success path yields candidates with no errors", len(cands) >= 1 and errors == [], f"cands={len(cands)} errors={errors}")

        def blocked_json(attempts):
            raise SourceAccessError("http_403_Blocked", status=403, blocked_signature="blocked")
        davinci.request_reddit_json_with_fallback = blocked_json
        davinci.reddit_feed_discovery_candidates = lambda rec, ctx, errs: [rc("DaVinci Resolve 21 crash from feed", "crash", epoch(2026, 4, 20), slug="feed_crash")]
        errors2: list = []
        cands2 = davinci.reddit_search_candidates(record, CollectorContext(write=False, since=None, max_pages=1), errors2)
        check("RSS/feed fallback yields candidates when JSON is blocked, and errors are recorded honestly", len(cands2) >= 1 and len(errors2) >= 1, f"cands={len(cands2)} errors={len(errors2)}")
    finally:
        davinci.request_reddit_json_with_fallback = orig_json
        davinci.reddit_feed_discovery_candidates = orig_feed_disc

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
