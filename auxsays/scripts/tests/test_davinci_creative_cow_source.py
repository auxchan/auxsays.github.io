#!/usr/bin/env python3
"""Tests for Creative COW DaVinci evidence collection.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_creative_cow_source.py

These tests use mocked/static HTML only. They must not perform live Creative
COW HTTP requests.
"""
from __future__ import annotations

import sys
import traceback
import types
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

# Local development environments may not have PyYAML installed. The DaVinci
# gate functions exercised here do not need YAML I/O, so provide an import shim.
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda *_args, **_kwargs: {}, safe_dump=lambda *_args, **_kwargs: ""))

from patch_collectors.base import CollectorContext, PatchRecord, source_url_is_specific
import patch_collectors.davinci as davinci
from patch_collectors.davinci import (
    creative_cow_forum_search_candidates,
    creative_cow_method_status,
    creative_cow_thread_candidate,
    method_status,
    row_from_candidate,
)

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


LISTING_HTML = """
<html>
  <body>
    <a href="https://creativecow.net/forums/thread/davinci-resolve-21-render-crash/">DaVinci Resolve 21 render crash</a>
    <a href="/forums/forum/davinci-resolve/">DaVinci Resolve forum</a>
  </body>
</html>
"""

THREAD_HTML = """
<html>
  <head>
    <meta property="og:title" content="DaVinci Resolve 21 render crash - Creative COW">
  </head>
  <body>
    <nav>Forums / DaVinci Resolve</nav>
    <article>
      <h1>DaVinci Resolve 21 render crash</h1>
      <p>Posted by Taylor on <time datetime="2026-04-15T16:10:00Z">April 15, 2026</time></p>
      <div class="post">
        DaVinci Resolve 21 crashed every time I tried to render a timeline on Windows.
      </div>
      <div class="reply">I saw the same export failure after updating to Resolve Studio 21.</div>
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


def stable_record() -> PatchRecord:
    return PatchRecord(
        product_id="blackmagic-davinci",
        update_version="21",
        path=Path("auxsays/updates/generated/2026-04-14-davinci-resolve-21.md"),
        update_published_at="2026-04-14",
        update_status="current",
        update_product="DaVinci Resolve",
    )


def beta_record() -> PatchRecord:
    return PatchRecord(
        product_id="blackmagic-davinci",
        update_version="21 Public Beta 1",
        path=Path("auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md"),
        update_published_at="2026-04-14",
        update_status="current",
        update_product="DaVinci Resolve",
    )


def creative_candidate(**overrides: str) -> dict[str, str]:
    candidate = {
        "source_type": "creator_forum_report",
        "source_name": "Creative COW DaVinci Resolve",
        "source_url": "https://creativecow.net/forums/thread/davinci-resolve-21-render-crash/",
        "parent_title": "DaVinci Resolve 21 render crash",
        "report_title": "DaVinci Resolve 21 render crash",
        "report_text": "DaVinci Resolve 21 crashed every time I tried to render a timeline on Windows.",
        "source_date": "2026-04-15",
    }
    candidate.update(overrides)
    return candidate


def run() -> int:
    print("=" * 60)
    print("DaVinci Creative COW source tests")
    print("=" * 60)

    parsed = creative_cow_thread_candidate(
        "https://creativecow.net/forums/thread/davinci-resolve-21-render-crash/?utm_source=test",
        THREAD_HTML,
    )
    check("parses valid Creative COW thread candidate", isinstance(parsed, dict), f"candidate={parsed!r}")
    if parsed:
        check("candidate source_type is creator forum", parsed.get("source_type") == "creator_forum_report", str(parsed))
        check("candidate source_name is Creative COW DaVinci Resolve", parsed.get("source_name") == "Creative COW DaVinci Resolve", str(parsed))
        check(
            "candidate canonical source_url is specific thread URL",
            parsed.get("source_url") == "https://creativecow.net/forums/thread/davinci-resolve-21-render-crash/",
            str(parsed),
        )
        check("candidate parent_title is thread title", parsed.get("parent_title") == "DaVinci Resolve 21 render crash", str(parsed))
        check("candidate source_date parsed from time element", parsed.get("source_date") == "2026-04-15", str(parsed))

    check(
        "Creative COW forum/category URL is not a specific report",
        source_url_is_specific("https://creativecow.net/forums/forum/davinci-resolve/") is False,
    )
    check(
        "Creative COW thread URL is a specific report",
        source_url_is_specific("https://creativecow.net/forums/thread/davinci-resolve-21-render-crash/") is True,
    )

    valid_row = row_from_candidate(stable_record(), creative_candidate(), "2026-05-14T00:00:00Z")
    check("valid Creative COW stable 21 candidate counts", valid_row.get("counted") is True, f"reason={valid_row.get('exclusion_reason')!r}")
    check("valid Creative COW candidate has equal source weight", valid_row.get("source_weight") == 1, str(valid_row))

    category_url_row = row_from_candidate(
        stable_record(),
        creative_candidate(source_url="https://creativecow.net/forums/forum/davinci-resolve/"),
        "2026-05-14T00:00:00Z",
    )
    check(
        "category/list source_url is rejected",
        category_url_row.get("counted") is False and category_url_row.get("exclusion_reason") == "source_url_not_specific_report",
        f"reason={category_url_row.get('exclusion_reason')!r}",
    )

    no_version_row = row_from_candidate(
        stable_record(),
        creative_candidate(
            parent_title="DaVinci Resolve render crash",
            report_title="DaVinci Resolve render crash",
            report_text="DaVinci Resolve crashed every time I tried to render a timeline.",
        ),
        "2026-05-14T00:00:00Z",
    )
    check(
        "missing exact version is rejected",
        no_version_row.get("counted") is False and no_version_row.get("exclusion_reason") == "missing_exact_patch_version_match",
        f"reason={no_version_row.get('exclusion_reason')!r}",
    )

    no_product_row = row_from_candidate(
        stable_record(),
        creative_candidate(parent_title="21 render crash", report_title="21 render crash", report_text="21 crashed every time I tried to render."),
        "2026-05-14T00:00:00Z",
    )
    check(
        "missing DaVinci product context is rejected",
        no_product_row.get("counted") is False and no_product_row.get("exclusion_reason") == "missing_davinci_product_context",
        f"reason={no_product_row.get('exclusion_reason')!r}",
    )

    how_to_row = row_from_candidate(
        stable_record(),
        creative_candidate(
            parent_title="How do I add subtitles in DaVinci Resolve 21?",
            report_title="How do I add subtitles in DaVinci Resolve 21?",
            report_text="I am learning DaVinci Resolve 21 and want to add subtitles to a clip.",
        ),
        "2026-05-14T00:00:00Z",
    )
    check(
        "non-issue/how-to content is rejected",
        how_to_row.get("counted") is False and how_to_row.get("exclusion_reason") == "not_a_real_issue_report",
        f"reason={how_to_row.get('exclusion_reason')!r}",
    )

    beta_for_stable_row = row_from_candidate(
        stable_record(),
        creative_candidate(
            source_url="https://creativecow.net/forums/thread/davinci-resolve-21-public-beta-1-crash/",
            parent_title="DaVinci Resolve 21 Public Beta 1 render crash",
            report_title="DaVinci Resolve 21 Public Beta 1 render crash",
            report_text="DaVinci Resolve 21.0 Public Beta 1 crashed during render.",
        ),
        "2026-05-14T00:00:00Z",
    )
    check(
        "stable 21 rejects Public Beta 1 context",
        beta_for_stable_row.get("counted") is False and beta_for_stable_row.get("exclusion_reason") == "beta_context_for_stable_record",
        f"reason={beta_for_stable_row.get('exclusion_reason')!r}",
    )

    stable_for_beta_row = row_from_candidate(
        beta_record(),
        creative_candidate(
            parent_title="DaVinci Resolve 21 render crash",
            report_title="DaVinci Resolve 21 render crash",
            report_text="DaVinci Resolve 21 crashed during render.",
        ),
        "2026-05-14T00:00:00Z",
    )
    check(
        "Beta 1 rejects stable 21 wording",
        stable_for_beta_row.get("counted") is False and stable_for_beta_row.get("exclusion_reason") == "missing_exact_patch_version_match",
        f"reason={stable_for_beta_row.get('exclusion_reason')!r}",
    )

    beta_row = row_from_candidate(
        beta_record(),
        creative_candidate(
            source_url="https://creativecow.net/forums/thread/davinci-resolve-21-public-beta-1-render-crash/",
            parent_title="DaVinci Resolve 21 Public Beta 1 render crash",
            report_title="DaVinci Resolve 21 Public Beta 1 render crash",
            report_text="DaVinci Resolve 21.0 Public Beta 1 crashed during render.",
        ),
        "2026-05-14T00:00:00Z",
    )
    check("Beta 1 exact Creative COW candidate counts", beta_row.get("counted") is True, f"reason={beta_row.get('exclusion_reason')!r}")

    original_request_text = davinci.request_text
    try:
        pages = {
            "https://creativecow.net/forums/forum/davinci-resolve/": LISTING_HTML,
            "https://creativecow.net/forums/thread/davinci-resolve-21-render-crash/": THREAD_HTML,
        }
        davinci.request_text = lambda url: pages[url]
        errors: list[dict[str, str]] = []
        candidates = creative_cow_forum_search_candidates(
            stable_record(),
            CollectorContext(write=False, since=None, max_pages=1),
            errors,
        )
    finally:
        davinci.request_text = original_request_text
    check("Creative COW method discovers mocked thread candidate", len(candidates) == 1, f"candidates={candidates!r}, errors={errors!r}")
    check("Creative COW method has no errors for mocked success", errors == [], f"errors={errors!r}")

    check("Creative COW health success when candidates are evaluated", creative_cow_method_status(candidates, [], [valid_row], []) == "success")
    check("Creative COW health no_results when no candidates are found", creative_cow_method_status([], [], [], []) == "no_results")
    check("generic method health success status", method_status(candidates, [valid_row], [], []) == "success")
    check(
        "Creative COW health blocked status",
        creative_cow_method_status([], [], [], [{"reason": "creative_cow_listing_fetch_failed:http_403_Blocked"}]) == "blocked",
    )

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
