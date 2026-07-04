#!/usr/bin/env python3
"""Tests for the shared, product-agnostic reddit_source helper.

These tests are fully offline: the Reddit transport functions are replaced with
in-memory fakes. No live Reddit requests are made. They cover candidate mapping,
usable-URL/canonicalization, feed (Atom/RSS) parsing, the search->listing->feed
orchestration, and graceful blocked handling (errors populated, no crash).
"""
from __future__ import annotations

import sys
import traceback
import types
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

# base.py imports PyYAML at module load; provide a shim if it is unavailable.
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda *_a, **_k: {}, safe_dump=lambda *_a, **_k: ""))

import patch_collectors.reddit_source as rs

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


def ctx(max_pages: int = 1, since: str | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(max_pages=max_pages, since=since)


POST = {
    "title": "Premiere Pro 26.2 export crash",
    "selftext": "Adobe Premiere Pro 26.2 crashes every time I export on Windows.",
    "permalink": "/r/premierepro/comments/abc123/premiere_pro_262_export_crash/",
    "created_utc": 1746441600,
}

ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Premiere Pro 26.2 export crash</title>
    <link rel="alternate" href="https://www.reddit.com/r/premierepro/comments/atom01/premiere_pro_262_export_crash/"/>
    <summary>Adobe Premiere Pro 26.2 crashes on export.</summary>
    <published>2026-05-05T10:00:00Z</published>
  </entry>
</feed>
"""

RSS_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Premiere Pro 26.2 export crash</title>
    <link>https://www.reddit.com/r/premierepro/comments/rss01/premiere_pro_262_export_crash/</link>
    <description>Adobe Premiere Pro 26.2 crashes on export.</description>
    <pubDate>Mon, 05 May 2026 10:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


def run() -> int:
    print("=" * 60)
    print("Shared reddit_source helper tests")
    print("=" * 60)

    # 1. Candidate mapping from a Reddit JSON post.
    cand = rs.reddit_candidate(POST, source_type="reddit_community_report", source_name="r/premierepro")
    check("reddit_candidate maps title/selftext/permalink", (
        cand["source_type"] == "reddit_community_report"
        and cand["source_name"] == "r/premierepro"
        and cand["source_url"] == "https://www.reddit.com/r/premierepro/comments/abc123/premiere_pro_262_export_crash/"
        and "crashes" in cand["report_text"].lower()
        and "T" in cand["source_date"] and cand["source_date"].endswith("Z")
    ), f"cand={cand!r}")

    # 2. Usable-URL + canonicalization.
    check("reddit comments URL is usable", rs.reddit_source_url_is_usable("https://www.reddit.com/r/premierepro/comments/x/y/") is True)
    check("reddit subreddit index URL is not usable", rs.reddit_source_url_is_usable("https://www.reddit.com/r/premierepro/") is False)
    check("canonical_reddit_url drops query/fragment", rs.canonical_reddit_url("https://old.reddit.com/r/premierepro/comments/x/y/?utm=1#c") == "https://www.reddit.com/r/premierepro/comments/x/y/")

    # 3. Feed parsing (Atom + RSS).
    atom = rs.reddit_feed_candidates(ATOM_FEED, source_type="reddit_community_report", source_name="r/premierepro")
    check("Atom feed parses one usable candidate", len(atom) == 1 and "/comments/atom01/" in atom[0]["source_url"], f"atom={atom!r}")
    rss = rs.reddit_feed_candidates(RSS_FEED, source_type="reddit_community_report", source_name="r/premierepro")
    check("RSS feed parses one usable candidate", len(rss) == 1 and "/comments/rss01/" in rss[0]["source_url"], f"rss={rss!r}")

    original_json = rs.request_reddit_json_with_fallback
    original_feed = rs.request_reddit_feed
    try:
        # 4. Orchestration with successful JSON transport.
        rs.request_reddit_json_with_fallback = lambda attempts: {"data": {"children": [{"data": POST}], "after": None}}
        rs.request_reddit_feed = lambda url, **kwargs: []
        errors: list[dict[str, object]] = []
        candidates = rs.collect_reddit_candidates(
            subreddits=["premierepro"],
            queries=['"Premiere Pro 26.2"'],
            context=ctx(),
            errors=errors,
            source_type="reddit_community_report",
        )
        check(
            "collect_reddit_candidates returns mapped, de-duped candidates",
            len(candidates) == 1
            and candidates[0]["source_type"] == "reddit_community_report"
            and candidates[0]["source_name"] == "r/premierepro"
            and "/comments/abc123/" in candidates[0]["source_url"],
            f"candidates={candidates!r} errors={errors!r}",
        )

        # 5. Graceful blocked handling — every transport raises.
        def blocked(*_args: object, **_kwargs: object):
            raise rs.SourceAccessError("http_403_blocked", status=403, blocked_signature="blocked")

        rs.request_reddit_json_with_fallback = blocked
        rs.request_reddit_feed = blocked
        blocked_errors: list[dict[str, object]] = []
        blocked_candidates = rs.collect_reddit_candidates(
            subreddits=["premierepro"],
            queries=['"Premiere Pro 26.2"'],
            context=ctx(),
            errors=blocked_errors,
            source_type="reddit_community_report",
        )
        check(
            "collect_reddit_candidates degrades to empty + errors when blocked (no crash)",
            blocked_candidates == [] and len(blocked_errors) > 0 and any("403" in str(e.get("reason")) for e in blocked_errors),
            f"candidates={blocked_candidates!r} errors={blocked_errors!r}",
        )
    finally:
        rs.request_reddit_json_with_fallback = original_json
        rs.request_reddit_feed = original_feed

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
