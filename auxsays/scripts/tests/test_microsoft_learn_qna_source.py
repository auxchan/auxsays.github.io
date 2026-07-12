#!/usr/bin/env python3
"""Tests for the Microsoft Learn Q&A search-RSS source module.

Offline only: the HTTP seam (_fetch_feed_text / request_learn_qna_feed) is monkeypatched
and every sleep is stubbed, so no live learn.microsoft.com request and no wall-clock delay
occur. Covers deterministic RSS parsing, specific-question-URL filtering, missing-field
resilience, and the blocked / broken / empty / partial health signals.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_microsoft_learn_qna_source.py
"""
from __future__ import annotations

import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import patch_collectors.microsoft_learn_qna_source as src
from patch_collectors.microsoft_learn_qna_source import LearnQnaAccessError

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


RSS_OK = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<title>Microsoft Learn Q&amp;A</title>
<item>
  <title>KB5095093 breaks printing on Windows 11 24H2</title>
  <link>https://learn.microsoft.com/en-us/answers/questions/2412345/kb5095093-breaks-printing</link>
  <pubDate>Tue, 30 Jun 2026 10:00:00 GMT</pubDate>
  <description>&lt;p&gt;After installing KB5095093 (OS Build 26100.8737) my printer stopped working.&lt;/p&gt;</description>
</item>
<item>
  <title>Windows 11 24H2 known issues (docs)</title>
  <link>https://learn.microsoft.com/en-us/windows/release-health/status-windows-11-24h2</link>
  <pubDate>Tue, 30 Jun 2026 09:00:00 GMT</pubDate>
  <description>Documentation page, not a Q&amp;A question.</description>
</item>
</channel></rss>"""

# An item with only a link (no title/description/pubDate) must not crash the parser.
RSS_MISSING_FIELDS = """<rss version="2.0"><channel>
<item><link>https://learn.microsoft.com/en-us/answers/questions/999888/x</link></item>
</channel></rss>"""

RSS_EMPTY = """<rss version="2.0"><channel><title>empty</title></channel></rss>"""
RSS_BROKEN = """<rss version="2.0"><channel><item><title>unclosed"""
BLOCK_PAGE = "<html><body>Access Denied. request blocked.</body></html>"


def run() -> int:
    print("=" * 60)
    print("Microsoft Learn Q&A source tests")
    print("=" * 60)
    src.learn_qna_sleep = lambda _d: None  # never wait on the clock

    # --- URL builder --------------------------------------------------------
    url = src.learn_qna_search_url("KB5095093")
    check("search URL targets the Learn search RSS API with the exact term", url.startswith("https://learn.microsoft.com/api/search/rss?") and "search=KB5095093" in url, url)
    check("search URL scopes to the QnA category facet", "category" in url and "QnA" in url.replace("%27", "'"), url)

    # --- pure RSS parse -----------------------------------------------------
    cands = src.parse_learn_qna_rss(RSS_OK)
    check("parses a valid Learn Q&A RSS entry", len(cands) == 1, str(len(cands)))
    if cands:
        c = cands[0]
        check("candidate URL is the specific question thread", c["source_url"] == "https://learn.microsoft.com/en-us/answers/questions/2412345/kb5095093-breaks-printing", c["source_url"])
        check("candidate carries title/text/date", "KB5095093" in c["report_title"] and "printer" in c["report_text"] and c["source_date"].startswith("2026-06-30"), str({k: c.get(k) for k in ("report_title", "source_date")}))
    check("ignores entries without a specific question URL (docs/category dropped)", all("/answers/questions/" in c["source_url"] for c in cands), str([c["source_url"] for c in cands]))

    missing = src.parse_learn_qna_rss(RSS_MISSING_FIELDS)
    check("handles missing title/body/date without crashing", isinstance(missing, list) and len(missing) == 1 and missing[0]["report_title"] == "" and missing[0]["source_date"] == "", str(missing))

    check("empty feed parses to zero candidates", src.parse_learn_qna_rss(RSS_EMPTY) == [])

    raised = False
    try:
        src.parse_learn_qna_rss(RSS_BROKEN)
    except ET.ParseError:
        raised = True
    check("malformed XML raises ET.ParseError (surfaced as broken)", raised)

    # --- request_learn_qna_feed via the _fetch_feed_text seam ---------------
    src._fetch_feed_text = lambda _url, **_k: (200, "application/rss+xml", RSS_OK)
    ok_cands = src.request_learn_qna_feed("KB5095093")
    check("request_learn_qna_feed returns parsed candidates on 200", len(ok_cands) == 1)

    src._fetch_feed_text = lambda _url, **_k: (200, "text/html", BLOCK_PAGE)
    blocked = False
    try:
        src.request_learn_qna_feed("KB5095093")
    except LearnQnaAccessError as exc:
        blocked = exc.signature == "blocked"
    check("blocked/access-denied response raises LearnQnaAccessError(blocked)", blocked)

    def _raise_429(_url, **_k):
        raise LearnQnaAccessError("http_429_rate_limited", status=429, signature="blocked")
    src._fetch_feed_text = _raise_429
    rate_blocked = False
    try:
        src.request_learn_qna_feed("KB5095093")
    except LearnQnaAccessError as exc:
        rate_blocked = exc.signature == "blocked" and exc.status == 429
    check("HTTP 429 rate-limit raises LearnQnaAccessError(blocked)", rate_blocked)

    src._fetch_feed_text = lambda _url, **_k: (200, "application/rss+xml", RSS_BROKEN)
    broke = False
    try:
        src.request_learn_qna_feed("KB5095093")
    except LearnQnaAccessError as exc:
        broke = exc.signature == "broken"
    check("parser/schema failure raises LearnQnaAccessError(broken)", broke)

    src._fetch_feed_text = lambda _url, **_k: (200, "application/rss+xml", RSS_EMPTY)
    check("reachable empty feed returns no candidates (-> no_results upstream)", src.request_learn_qna_feed("KB5095093") == [])

    # --- collect_learn_qna_candidates orchestration -------------------------
    original_request = src.request_learn_qna_feed
    try:
        src.request_learn_qna_feed = lambda q, **_k: src.parse_learn_qna_rss(RSS_OK)
        errors: list = []
        results = src.collect_learn_qna_candidates(queries=["KB5095093", "26100.8737"], context=SimpleNamespace(since=None), errors=errors)
        check("orchestration dedupes identical question URLs across queries", len(results) == 1 and errors == [], f"results={len(results)} errors={errors}")
        check("orchestration stamps the matched query term", results and results[0].get("matched_query") in ("KB5095093", "26100.8737"), str(results[0].get("matched_query") if results else None))

        def _partial(q, **_k):
            if q == "KB5095093":
                raise LearnQnaAccessError("blocked:rate_limited", status=429, signature="blocked")
            return src.parse_learn_qna_rss(RSS_OK)
        src.request_learn_qna_feed = _partial
        errors2: list = []
        results2 = src.collect_learn_qna_candidates(queries=["KB5095093", "26100.8737"], context=SimpleNamespace(since=None), errors=errors2)
        check("partial failure records the error but keeps the working search", len(results2) == 1 and len(errors2) == 1 and errors2[0].get("blocked_signature") == "blocked", f"results={len(results2)} errors={errors2}")
    finally:
        src.request_learn_qna_feed = original_request

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
