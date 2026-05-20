#!/usr/bin/env python3
"""Tests for Adobe Premiere Pro community evidence collection.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_adobe_premiere_collector.py

These tests use mocked/static Adobe Community HTML only. They must not perform
live Adobe Community requests.
"""
from __future__ import annotations

import os
import sys
import traceback
import types
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

# Local development environments may not have PyYAML installed. These tests do
# not perform YAML I/O, so provide an import shim before importing collectors.
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda *_args, **_kwargs: {}, safe_dump=lambda *_args, **_kwargs: ""))

from patch_collectors.base import CollectorContext, PatchRecord
import patch_collectors.adobe_premiere as premiere
from patch_collectors.adobe_premiere import (
    AdobeCommunityAccessError,
    adobe_community_bug_tab_candidates,
    adobe_community_known_url_candidates,
    adobe_community_method_status,
    adobe_community_search_candidates,
    adobe_report_url_is_specific,
    brave_search_api_candidates,
    extract_brave_report_links,
    evaluate_candidates,
    row_from_candidate,
)

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


SEARCH_HTML = """
<html>
  <body>
    <a href="/bug-reports-728/premiere-pro-26-2-export-crash-1559001">Premiere Pro 26.2 export crash</a>
    <a href="/bug-reports-728/premiere-pro-26-2-export-crash-1559001?tracking=1">Duplicate link</a>
    <a href="/announcements-727/welcome-to-premiere-26-2-1557825">Official announcement</a>
  </body>
</html>
"""

BUG_TAB_HTML = """
<html>
  <body>
    <a href="/bug-reports-728/premiere-pro-26-2-export-crash-1559001">Premiere Pro 26.2 export crash</a>
    <a href="/bug-reports-728/premiere-pro-26-2-export-crash-1559001?tracking=1">Duplicate bug-tab link</a>
    <a href="/t5/premiere-pro/ct-p/ct-premiere-pro?tabid=bugs">Premiere product bug tab</a>
    <a href="/t5/forums/searchpage/tab/message?q=Premiere%2026.2">Search results</a>
  </body>
</html>
"""

BUG_HTML = """
<html>
  <head>
    <meta property="og:title" content="Premiere Pro 26.2 export crash - Adobe Community">
  </head>
  <body>
    <article>
      <h1>Premiere Pro 26.2 export crash</h1>
      <time datetime="2026-05-02T10:00:00Z">May 2, 2026</time>
      <p>Adobe Premiere Pro 26.2 crashes every time I export my timeline on Windows.</p>
    </article>
  </body>
</html>
"""


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


def record() -> PatchRecord:
    return PatchRecord(
        product_id="adobe-premiere-pro",
        update_version="26.2",
        path=Path("auxsays/updates/generated/2026-04-30-premiere-pro-26-2.md"),
        update_published_at="2026-04-30T00:00:00Z",
        update_status="current",
        update_product="Premiere Pro",
    )


def candidate(**overrides: str) -> dict[str, str]:
    item = {
        "source_type": "adobe_community_bug_report",
        "source_name": "Adobe Community Bug Report",
        "source_url": "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001",
        "parent_title": "Premiere Pro 26.2 export crash",
        "report_title": "Premiere Pro 26.2 export crash",
        "report_text": "Adobe Premiere Pro 26.2 crashes every time I export my timeline on Windows.",
        "source_date": "2026-05-02",
    }
    item.update(overrides)
    return item


def run() -> int:
    print("=" * 60)
    print("Adobe Premiere Pro collector tests")
    print("=" * 60)

    valid = row_from_candidate(record(), candidate(), "2026-05-20T00:00:00Z")
    check("specific 26.2 crash report counts", valid.get("counted") is True, f"reason={valid.get('exclusion_reason')!r}")
    check("accepted row uses equal source weight", valid.get("source_weight") == 1, str(valid))
    check("accepted row uses Premiere product id", valid.get("product_id") == "adobe-premiere-pro", str(valid))

    missing_version = row_from_candidate(
        record(),
        candidate(
            parent_title="Premiere Pro export crash",
            report_title="Premiere Pro export crash",
            report_text="Adobe Premiere Pro crashes every time I export my timeline after the latest update.",
        ),
        "2026-05-20T00:00:00Z",
    )
    check(
        "missing exact version is rejected",
        missing_version.get("counted") is False and missing_version.get("exclusion_reason") == "missing_exact_patch_version_match",
        f"reason={missing_version.get('exclusion_reason')!r}",
    )

    category_url = row_from_candidate(
        record(),
        candidate(source_url="https://community.adobe.com/bug-reports-728"),
        "2026-05-20T00:00:00Z",
    )
    check(
        "generic category/search URL is rejected",
        category_url.get("counted") is False and category_url.get("exclusion_reason") == "source_url_not_specific_report",
        f"reason={category_url.get('exclusion_reason')!r}",
    )
    check("Adobe bug report URL is specific", adobe_report_url_is_specific(candidate()["source_url"]) is True)
    check("Adobe category URL is not specific", adobe_report_url_is_specific("https://community.adobe.com/bug-reports-728") is False)

    official = row_from_candidate(
        record(),
        candidate(
            source_url="https://community.adobe.com/announcements-727/welcome-to-premiere-26-2-1557825",
            parent_title="Welcome to Premiere Pro 26.2",
            report_title="Welcome to Premiere Pro 26.2",
            report_text="Official announcement and release notes for Premiere Pro 26.2.",
        ),
        "2026-05-20T00:00:00Z",
    )
    check("official announcement/release note is rejected", official.get("counted") is False, f"reason={official.get('exclusion_reason')!r}")

    how_to = row_from_candidate(
        record(),
        candidate(
            parent_title="How do I use captions in Premiere Pro 26.2?",
            report_title="How do I use captions in Premiere Pro 26.2?",
            report_text="How do I use captions in Adobe Premiere Pro 26.2? I am learning the workflow.",
        ),
        "2026-05-20T00:00:00Z",
    )
    check(
        "how-to/support question without regression is rejected",
        how_to.get("counted") is False and how_to.get("exclusion_reason") == "not_a_real_issue_report",
        f"reason={how_to.get('exclusion_reason')!r}",
    )

    build_without_context = row_from_candidate(
        record(),
        candidate(
            parent_title="Build 65 export crash",
            report_title="Build 65 export crash",
            report_text="Build 65 crashes during export on Windows.",
        ),
        "2026-05-20T00:00:00Z",
    )
    check(
        "Build 65 without Premiere Pro 26.2 context is rejected",
        build_without_context.get("counted") is False,
        f"reason={build_without_context.get('exclusion_reason')!r}",
    )

    build_with_context = row_from_candidate(
        record(),
        candidate(
            parent_title="Premiere Pro 26.2 Build 65 UI lag",
            report_title="Premiere Pro 26.2 Build 65 UI lag",
            report_text="Adobe Premiere Pro 26.2 Build 65 has severe UI lag and freezes when editing the timeline.",
        ),
        "2026-05-20T00:00:00Z",
    )
    check("Build 65 with clear Premiere Pro 26.2 context counts", build_with_context.get("counted") is True, f"reason={build_with_context.get('exclusion_reason')!r}")

    accepted, rejected = evaluate_candidates(record(), [candidate(), candidate(source_url=candidate()["source_url"] + "?utm=duplicate")], "2026-05-20T00:00:00Z")
    check("duplicate canonical URL only produces one accepted row", len(accepted) == 1 and len(rejected) == 0, f"accepted={accepted!r}, rejected={rejected!r}")

    original_request_text = premiere.request_text
    try:
        pages = {
            premiere.search_url('"Premiere Pro 26.2" crash', 1): SEARCH_HTML,
            "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001": BUG_HTML,
        }

        def fake_request(url: str, *_args: object, **_kwargs: object) -> str:
            if url in pages:
                return pages[url]
            return "<html><body>No results</body></html>"

        premiere.request_text = fake_request
        errors: list[dict[str, str]] = []
        discovered = adobe_community_search_candidates(record(), CollectorContext(write=False, since=None, max_pages=1), errors)
    finally:
        premiere.request_text = original_request_text
    check("mocked Adobe Community search discovers specific report URL", len(discovered) == 1, f"candidates={discovered!r}, errors={errors!r}")
    check("mocked Adobe Community search has no errors", errors == [], f"errors={errors!r}")

    original_request_text = premiere.request_text
    try:
        pages = {
            premiere.bug_tab_url(1): BUG_TAB_HTML,
            "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001": BUG_HTML,
        }

        def fake_request(url: str, *_args: object, **_kwargs: object) -> str:
            if url in pages:
                return pages[url]
            return "<html><body>No results</body></html>"

        premiere.request_text = fake_request
        errors = []
        bug_tab_candidates = adobe_community_bug_tab_candidates(record(), CollectorContext(write=False, since=None, max_pages=1), errors)
    finally:
        premiere.request_text = original_request_text
    check("bug-tab listing discovers specific report URL", len(bug_tab_candidates) == 1, f"candidates={bug_tab_candidates!r}, errors={errors!r}")
    check("bug-tab listing ignores category/search links", errors == [], f"errors={errors!r}")

    check("Adobe product landing URL is not specific", adobe_report_url_is_specific("https://community.adobe.com/t5/premiere-pro/ct-p/ct-premiere-pro?tabid=bugs") is False)
    check("Adobe search page URL is not specific", adobe_report_url_is_specific("https://community.adobe.com/t5/forums/searchpage/tab/message?q=Premiere%2026.2") is False)

    original_request_text = premiere.request_text
    original_load_evidence = premiere.load_evidence
    try:
        def fake_request(url: str, *_args: object, **_kwargs: object) -> str:
            if url == "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001":
                return BUG_HTML
            return "<html><body>No results</body></html>"

        def fake_load_evidence() -> list[dict[str, object]]:
            return [{
                "product_id": "adobe-premiere-pro",
                "update_version": "26.2",
                "source_url": "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001?utm=old",
            }]

        premiere.request_text = fake_request
        premiere.load_evidence = fake_load_evidence
        errors = []
        known_candidates = adobe_community_known_url_candidates(record(), CollectorContext(write=False, since=None, max_pages=1), errors)
    finally:
        premiere.request_text = original_request_text
        premiere.load_evidence = original_load_evidence
    check("known URL recheck refetches and validates specific URLs", len(known_candidates) == 1, f"candidates={known_candidates!r}, errors={errors!r}")

    original_request_text = premiere.request_text
    try:
        calls: list[str] = []

        def fake_request(url: str, *_args: object, **_kwargs: object) -> str:
            calls.append(url)
            if url.startswith(premiere.ADOBE_SEARCH_URL):
                raise AdobeCommunityAccessError("rate_limited")
            if url == premiere.bug_tab_url(1):
                return BUG_TAB_HTML
            if url == "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001":
                return BUG_HTML
            return "<html><body>No results</body></html>"

        premiere.request_text = fake_request
        accepted_rows, rejected_rows, health = premiere.collect_for_record(record(), CollectorContext(write=False, since=None, max_pages=1))
    finally:
        premiere.request_text = original_request_text
    health_by_id = {row.get("method_id"): row for row in health}
    check("search rate limit does not stop fallback bug-tab method", len(accepted_rows) == 1, f"accepted={accepted_rows!r}, rejected={rejected_rows!r}, health={health!r}")
    check("method health records search as blocked", health_by_id.get("adobe_community_search", {}).get("status") == "blocked", f"health={health!r}")
    check("method health records bug-tab separately", health_by_id.get("adobe_community_bug_tab_index", {}).get("status") == "success", f"health={health!r}")
    check("blocked search endpoint is not retried six times", sum(1 for url in calls if url.startswith(premiere.ADOBE_SEARCH_URL)) <= 1, f"calls={calls!r}")


    original_request_text = premiere.request_text
    original_request_brave_search = premiere.request_brave_search
    original_env = os.environ.get(premiere.BRAVE_API_KEY_ENV)
    try:
        os.environ.pop(premiere.BRAVE_API_KEY_ENV, None)
        errors = []
        brave_missing = brave_search_api_candidates(record(), CollectorContext(write=False, since=None, max_pages=1), errors)
    finally:
        if original_env is not None:
            os.environ[premiere.BRAVE_API_KEY_ENV] = original_env
    check("Brave method disables cleanly when API key is missing", brave_missing == [] and errors and errors[0]["reason"] == "missing_BRAVE_SEARCH_API_KEY", f"candidates={brave_missing!r}, errors={errors!r}")
    check("method health disabled when Brave key is missing", adobe_community_method_status([], [], [], errors) == "disabled", f"errors={errors!r}")

    brave_payload = {
        "web": {
            "results": [
                {"url": "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001?tracking=brave"},
                {"url": "https://community.adobe.com/t5/premiere-pro/ct-p/ct-premiere-pro"},
                {"url": "https://example.com/not-adobe"},
            ]
        }
    }
    brave_links = extract_brave_report_links(brave_payload)
    check("Brave response extracts only specific Adobe bug-report URLs", brave_links == ["https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001"], f"links={brave_links!r}")

    try:
        os.environ[premiere.BRAVE_API_KEY_ENV] = "test-token"

        def fake_brave_search(query: str, api_key: str, *_args: object, **_kwargs: object) -> dict[str, object]:
            check("Brave token is read from env and passed to request helper", api_key == "test-token")
            return brave_payload

        def fake_request(url: str, *_args: object, **_kwargs: object) -> str:
            if url == "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-export-crash-1559001":
                return BUG_HTML
            return "<html><body>No results</body></html>"

        premiere.request_brave_search = fake_brave_search
        premiere.request_text = fake_request
        errors = []
        brave_candidates = brave_search_api_candidates(record(), CollectorContext(write=False, since=None, max_pages=1), errors)
    finally:
        premiere.request_text = original_request_text
        premiere.request_brave_search = original_request_brave_search
        if original_env is None:
            os.environ.pop(premiere.BRAVE_API_KEY_ENV, None)
        else:
            os.environ[premiere.BRAVE_API_KEY_ENV] = original_env
    check("Brave candidate URL is fetched and converted to candidate", len(brave_candidates) == 1 and errors == [], f"candidates={brave_candidates!r}, errors={errors!r}")

    original_request_brave_search = premiere.request_brave_search
    original_env = os.environ.get(premiere.BRAVE_API_KEY_ENV)
    try:
        os.environ[premiere.BRAVE_API_KEY_ENV] = "test-token"

        def fake_brave_blocked(query: str, api_key: str, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AdobeCommunityAccessError("brave_rate_limited")

        premiere.request_brave_search = fake_brave_blocked
        errors = []
        blocked_brave = brave_search_api_candidates(record(), CollectorContext(write=False, since=None, max_pages=1), errors)
    finally:
        premiere.request_brave_search = original_request_brave_search
        if original_env is None:
            os.environ.pop(premiere.BRAVE_API_KEY_ENV, None)
        else:
            os.environ[premiere.BRAVE_API_KEY_ENV] = original_env
    check("Brave API rate limit records blocked diagnostics without crashing", blocked_brave == [] and errors and "brave_rate_limited" in errors[0]["reason"], f"candidates={blocked_brave!r}, errors={errors!r}")

    check("method health success when accepted rows exist", adobe_community_method_status(discovered, [valid], [], []) == "success")
    check("method health no_results when search returns nothing", adobe_community_method_status([], [], [], []) == "no_results")
    check(
        "method health blocked when fetch is blocked",
        adobe_community_method_status([], [], [], [{"reason": "adobe_community_search_fetch_failed:http_403_blocked"}]) == "blocked",
    )
    try:
        raise AdobeCommunityAccessError("blocked")
    except AdobeCommunityAccessError:
        check("AdobeCommunityAccessError is available for fetch diagnostics", True)

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
