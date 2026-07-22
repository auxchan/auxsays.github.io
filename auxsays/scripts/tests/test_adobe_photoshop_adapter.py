#!/usr/bin/env python3
"""Tests for the dedicated Adobe Photoshop (desktop) official release-notes adapter.

Offline only: canned Photoshop desktop release-notes HTML is fed directly to the pure
parser (no network). Proves the fail-closed contract:

- explicit desktop-Photoshop attribution (other Adobe products, Camera-Raw-only notes,
  and non-desktop Photoshop variants never produce a record);
- exact stable-version extraction (2X.Y / 2X.Y.Z), rejecting year-only, bare-major, and
  beta/prerelease builds;
- deterministic release date (full/ISO -> day precision, month+year -> month precision),
  with a body's exact day upgrading a heading's month;
- ambiguity fails closed (multi-version heading, undated release);
- deduplication by version; limit is honoured;
- records stay official_only with 0 reports and carry no consensus/community language.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_adobe_photoshop_adapter.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import adobe_photoshop as ap
from lib.write_update_record import build_front_matter

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

_URL = "https://helpx.adobe.com/photoshop/desktop/whats-new/photoshop-on-desktop-release-notes.html"


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


def _src() -> dict:
    return {
        "company_id": "adobe",
        "product_id": ap.PRODUCT_ID,
        "company": "Adobe",
        "software": "Photoshop",
        "public_category": "Design Workflow",
        "ingestion": {
            "official_url": _URL,
            "secondary_official_url": None,
        },
    }


def _parse(html: str, limit: int = 20):
    return ap._records_from_photoshop_release_notes(_src(), _URL, html, limit)


# A representative multi-release page: full-date, month-only, ISO-in-body, 2- and
# 3-component versions, a bundled Camera Raw mention (must not leak as a record).
PAGE = """
<h1>Photoshop desktop release notes</h1>
<p>Learn what's new in the latest releases of Photoshop on desktop.</p>

<h2>Photoshop 27.0 (October 2025 release)</h2>
<p>Release date: October 14, 2025.</p>
<h3>What's new</h3>
<ul><li>New Firefly-powered features. Camera Raw 17.0 is included. Premiere Pro 25.0 integration.</li></ul>

<h2>Photoshop 26.11 (September 2025 release)</h2>
<p>Released September 2025.</p>

<h2>Photoshop 26.10.1 (August 2025 release)</h2>
<ul><li>Maintenance build. Released on 2025-08-19.</li></ul>

<h2>Photoshop 26.0 (October 2024 release)</h2>
<p>Release date: October 15, 2024.</p>
"""


def run() -> int:
    print("=" * 60)
    print("Adobe Photoshop (desktop) adapter tests")
    print("=" * 60)

    recs = _parse(PAGE)
    versions = [r["target_version"] for r in recs]
    by_ver = {r["target_version"]: r for r in recs}

    # --- 1-4: clean multi-release extraction, order, and count -------------
    check("1. four clean desktop releases extracted", len(recs) == 4, f"versions={versions}")
    check("2. newest-first order preserved (27.0, 26.11, 26.10.1, 26.0)",
          versions == ["27.0", "26.11", "26.10.1", "26.0"], f"versions={versions}")
    check("3. two-component version 27.0 accepted", "27.0" in by_ver)
    check("4. three-component version 26.10.1 accepted", "26.10.1" in by_ver)

    # --- 5-7: date extraction + precision ----------------------------------
    check("5. full date in body upgrades heading month -> exact day (27.0 = 2025-10-14)",
          by_ver["27.0"]["published_at"] == "2025-10-14T00:00:00Z"
          and by_ver["27.0"]["date_precision"] == "day",
          str((by_ver["27.0"]["published_at"], by_ver["27.0"]["date_precision"])))
    check("6. month-only heading yields month precision (26.11 = 2025-09-01, month)",
          by_ver["26.11"]["published_at"] == "2025-09-01T00:00:00Z"
          and by_ver["26.11"]["date_precision"] == "month",
          str((by_ver["26.11"]["published_at"], by_ver["26.11"]["date_precision"])))
    check("7. ISO date in body completes an otherwise month heading (26.10.1 = 2025-08-19, day)",
          by_ver["26.10.1"]["published_at"] == "2025-08-19T00:00:00Z"
          and by_ver["26.10.1"]["date_precision"] == "day",
          str((by_ver["26.10.1"]["published_at"], by_ver["26.10.1"]["date_precision"])))

    # --- 8: no cross-product version contamination -------------------------
    check("8. bundled Camera Raw 17.0 / Premiere 25.0 in body never become records",
          "17.0" not in versions and "25.0" not in versions, f"versions={versions}")
    check("8b. body month phrasing is honest (26.11 summary says 'released September 2025', not a day)",
          "September 2025" in by_ver["26.11"]["official_summary"]
          and "September 1" not in by_ver["26.11"]["official_summary"],
          by_ver["26.11"]["official_summary"])

    # --- 9-13: attribution rejection (other products / non-desktop) --------
    check("9. Premiere Pro heading -> no record",
          len(_parse("<h2>Premiere Pro 25.0 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0)
    check("10. Camera-Raw-only heading -> no record",
          len(_parse("<h2>Camera Raw 17.0 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0)
    check("11. Lightroom / Illustrator / Acrobat / Firefly headings -> no records",
          all(len(_parse(f"<h2>{p} 27.0 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0
              for p in ("Lightroom Classic", "Illustrator", "Acrobat", "Firefly")))
    check("12. 'Photoshop on the web' -> no record",
          len(_parse("<h2>Photoshop on the web 27.0 (October 2025)</h2><p>October 14, 2025.</p>")) == 0)
    check("13. 'Photoshop on iPad' -> no record",
          len(_parse("<h2>Photoshop on iPad 6.0 (October 2025)</h2><p>October 14, 2025.</p>")) == 0)
    check("13b. generic Creative Cloud desktop heading -> no record",
          len(_parse("<h2>Creative Cloud desktop app 6.0 (October 2025)</h2><p>October 14, 2025.</p>")) == 0)

    # --- 14-15: stable-only (reject beta/prerelease) -----------------------
    check("14. beta heading -> no record",
          len(_parse("<h2>Photoshop 27.0 beta (October 2025)</h2><p>October 14, 2025.</p>")) == 0)
    check("15. prerelease / technology preview headings -> no records",
          len(_parse("<h2>Photoshop 27.0 (Prerelease)</h2><p>October 14, 2025.</p>")) == 0
          and len(_parse("<h2>Photoshop 27.0 Technology Preview</h2><p>October 14, 2025.</p>")) == 0)

    # --- 16-18: version validity -------------------------------------------
    check("16. year-only 'Photoshop 2025' -> no record",
          len(_parse("<h2>Photoshop 2025 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0)
    check("17. bare-major 'Photoshop 26' -> no record",
          len(_parse("<h2>Photoshop 26 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0)
    check("18. multi-version heading is ambiguous -> no record",
          len(_parse("<h2>Photoshop 27.0 and 26.11 (October 2025)</h2><p>October 14, 2025.</p>")) == 0)

    # --- 19-20: date fail-closed + dedup -----------------------------------
    check("19. undated release fails closed (heading + no date anywhere)",
          len(_parse("<h2>Photoshop 27.0</h2><h3>What's new</h3><ul><li>Features.</li></ul>")) == 0)
    dup = _parse("<h2>Photoshop 27.0 (October 2025 release)</h2><p>October 14, 2025.</p>"
                 "<h2>Photoshop 27.0 (October 2025 release)</h2><p>October 14, 2025.</p>")
    check("20. duplicate version deduped to a single record", len(dup) == 1, f"count={len(dup)}")

    # --- 21: limit honoured ------------------------------------------------
    limited = _parse(PAGE, limit=2)
    check("21. limit honoured (limit=2 -> 2 newest records)",
          [r["target_version"] for r in limited] == ["27.0", "26.11"],
          str([r["target_version"] for r in limited]))

    # --- 22: DOM-miss + inert fetch for wrong product ----------------------
    check("22. empty / non-release DOM -> 0 records",
          _parse("") == [] and _parse("<p>No releases here.</p>") == [])
    check("22b. fetch() returns [] for a non-Photoshop product id",
          ap.fetch({"product_id": "obs-studio", "ingestion": {}}, 3) == [])

    # --- 23-25: official-only write path, structured identity, no consensus -
    rec = by_ver["27.0"]
    front = build_front_matter(rec)
    check("23. front matter is official_only with 0 reports",
          front["evidence_state"] == "official_only" and front["update_report_count"] == 0,
          str({k: front[k] for k in ("evidence_state", "update_report_count")}))
    check("24. structured Photoshop identity: version, applicability, platform",
          front.get("target_version") == "27.0"
          and rec.get("applicability") == ["adobe-photoshop"]
          and rec.get("target_platform") == "Windows, macOS",
          str({"tv": front.get("target_version"), "app": rec.get("applicability")}))
    blob = " ".join(str(rec.get(k, "")) for k in ("body", "official_summary", "title", "capture_status")).lower()
    check("25. record carries no consensus/community/report language",
          not any(term in blob for term in ("consensus", "report", "users say", "community", "complaint", "verified reports")),
          blob)
    check("25b. record emits no report/consensus fields (pipeline derives official_only)",
          rec.get("report_count") is None and rec.get("evidence_state") is None
          and rec.get("update_report_count") is None and rec.get("consensus_label") is None)

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
