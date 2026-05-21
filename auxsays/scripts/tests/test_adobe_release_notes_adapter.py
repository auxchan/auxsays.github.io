#!/usr/bin/env python3
"""Tests for Adobe official release-note ingestion."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import adobe_release_notes as adobe

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


def source() -> dict[str, object]:
    return {
        "company_id": "adobe",
        "product_id": "adobe-premiere-pro",
        "company": "Adobe",
        "software": "Premiere Pro",
        "public_category": "Video / Production",
        "ingestion": {
            "official_url": "https://helpx.adobe.com/premiere/desktop/whats-new/release-notes.html",
            "secondary_official_url": "https://community.adobe.com/announcements-727/what-s-new-in-adobe-premiere-26-2-2-may-2026-1560755",
        },
    }


RELEASE_NOTES_HTML = """
<html>
  <body>
    <h2>May 2026 (version 26.2.2)</h2>
    <p>Fixed a critical issue that impacted general stability and could cause Premiere to hang.</p>
    <h2>April 2026 (version 26.2)</h2>
    <p>New Film Impact-powered effects and transitions.</p>
  </body>
</html>
"""


def run() -> int:
    print("=" * 60)
    print("Adobe release notes adapter tests")
    print("=" * 60)

    records = adobe._records_from_version_headings(
        source(),
        "https://helpx.adobe.com/premiere/desktop/whats-new/release-notes.html",
        RELEASE_NOTES_HTML,
        2,
    )
    check("official HelpX headings produce two records", len(records) == 2, str(records))
    first = records[0]
    check("26.2.2 is detected as its own official update", first.get("version") == "26.2.2", str(first))
    check("26.2.2 uses May 2026 publish date", first.get("published_at") == "2026-05-01T00:00:00Z", str(first))
    check("26.2.2 remains official-only before community evidence", not first.get("report_count"), str(first))
    check("26.2.2 summary mentions critical stability hang fix", "critical general-stability issue" in str(first.get("official_summary")), str(first.get("official_summary")))
    check("26.2.2 body includes official fixed issue", "could cause Premiere Pro to hang" in str(first.get("body")), str(first.get("body")))
    check("26.2.2 official sources include matching announcement", any("26-2-2" in item.get("url", "") for item in first.get("official_sources", [])), str(first.get("official_sources")))

    second = records[1]
    check("26.2 record remains separate", second.get("version") == "26.2", str(second))

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
