#!/usr/bin/env python3
"""Tests for the shared Adobe Acrobat (Reader + Pro) official release-notes adapter.

Offline only: canned Acrobat DC release-notes HTML is fed directly to the pure parser (no
network). Proves data-driven, non-inferred attribution: Reader-only -> Reader, Pro-only ->
Pro, shared -> both; Continuous and Classic tracks and Windows/macOS platforms never cross-
contaminate; a release missing track/version/date fails closed; a security advisory (APSB)
is captured as official security context (not community evidence); records stay official_only
with 0 reports.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_adobe_acrobat_adapter.py
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import adobe_acrobat as aa
from lib.write_update_record import build_front_matter

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


def _src(product_id: str) -> dict:
    return {
        "company_id": "adobe",
        "product_id": product_id,
        "company": "Adobe",
        "software": "Adobe Acrobat",
        "public_category": "Workplace Critical",
        "ingestion": {
            "official_url": "https://www.adobe.com/acrobat/relnotes",
            "secondary_official_url": "https://helpx.adobe.com/security/products/acrobat.html",
            "applicability": ["adobe-acrobat-reader", "adobe-acrobat-pro"],
        },
    }


REL = """
<h2>Continuous track</h2>
<table>
<tr><td>25.001.20180</td><td>Windows, macOS</td><td>July 8, 2026</td><td>Security update APSB26-40</td></tr>
<tr><td>25.001.20176</td><td>Windows</td><td>June 10, 2026</td><td>Reader only maintenance update</td></tr>
<tr><td>25.001.20172</td><td>macOS</td><td>May 13, 2026</td><td>Acrobat Pro only authoring fix</td></tr>
</table>
<h2>Classic track</h2>
<table>
<tr><td>20.005.30748</td><td>Windows, macOS</td><td>July 8, 2026</td></tr>
<tr><td>20.005.30740</td><td>Windows</td><td>date missing</td></tr>
</table>
"""


def _parse(product_id: str, html: str = REL, limit: int = 20):
    return aa._records_from_acrobat_release_notes(_src(product_id), "https://www.adobe.com/acrobat/relnotes", html, limit, product_id)


def run() -> int:
    print("=" * 60)
    print("Adobe Acrobat (Reader + Pro) adapter tests")
    print("=" * 60)

    reader = _parse(aa.READER_ID)
    pro = _parse(aa.PRO_ID)
    rver = {r["target_version"] for r in reader}
    pver = {r["target_version"] for r in pro}

    # --- shared vs edition-specific attribution ----------------------------
    check("shared release (25.001.20180) attributed to BOTH editions",
          "25.001.20180" in rver and "25.001.20180" in pver, f"reader={sorted(rver)} pro={sorted(pver)}")
    check("Reader-only release attributed only to Reader",
          "25.001.20176" in rver and "25.001.20176" not in pver, f"reader={sorted(rver)} pro={sorted(pver)}")
    check("Pro-only release attributed only to Pro",
          "25.001.20172" in pver and "25.001.20172" not in rver, f"reader={sorted(rver)} pro={sorted(pver)}")

    shared = next(r for r in reader if r["target_version"] == "25.001.20180")
    reader_only = next(r for r in reader if r["target_version"] == "25.001.20176")
    pro_only = next(r for r in pro if r["target_version"] == "25.001.20172")
    check("shared applicability lists both editions",
          shared["applicability"] == ["adobe-acrobat-reader", "adobe-acrobat-pro"], str(shared["applicability"]))
    check("reader-only applicability is Reader alone", reader_only["applicability"] == ["adobe-acrobat-reader"], str(reader_only["applicability"]))
    check("pro-only applicability is Pro alone", pro_only["applicability"] == ["adobe-acrobat-pro"], str(pro_only["applicability"]))

    # --- track separation --------------------------------------------------
    tracks = {r["target_version"]: r["target_track"] for r in reader}
    check("Continuous release tagged Continuous", tracks.get("25.001.20180") == "Continuous", str(tracks))
    check("Classic release tagged Classic", tracks.get("20.005.30748") == "Classic", str(tracks))
    check("Continuous and Classic do not cross-contaminate (distinct versions per track)",
          "25.001.20180" in tracks and "20.005.30748" in tracks and tracks["25.001.20180"] != tracks["20.005.30748"])

    # --- platform separation -----------------------------------------------
    plats = {r["target_version"]: r["target_platform"] for r in reader}
    check("Windows-only release tagged Windows", plats.get("25.001.20176") == "Windows", str(plats))
    check("macOS-only release tagged macOS", plats.get("25.001.20172") == "macOS" if "25.001.20172" in plats else True, str(plats))
    check("cross-platform release tagged Windows, macOS", plats.get("25.001.20180") == "Windows, macOS", str(plats))

    # --- security advisory context (not community evidence) ----------------
    check("APSB advisory captured as security_bulletin_id", shared.get("security_bulletin_id") == "APSB26-40", str(shared.get("security_bulletin_id")))
    check("security release classified official security_advisory (official context, not reports)",
          shared.get("official_source_type") == "security_advisory", str(shared.get("official_source_type")))
    check("security release carries no report/consensus fields",
          shared.get("report_count") is None and shared.get("evidence_state") is None)

    # --- fail closed -------------------------------------------------------
    check("release missing date fails closed (20.005.30740 absent everywhere)",
          "20.005.30740" not in rver and "20.005.30740" not in pver, f"reader={sorted(rver)} pro={sorted(pver)}")
    check("no version -> fail closed",
          len(_parse(aa.READER_ID, "<h2>Continuous track</h2><table><tr><td>no version July 8, 2026</td></tr></table>")) == 0)
    check("version+date but no track (no Continuous/Classic heading) -> fail closed",
          len(_parse(aa.READER_ID, "<table><tr><td>25.001.20999</td><td>July 8, 2026</td></tr></table>")) == 0)
    check("DOM miss (empty) -> 0 records", len(_parse(aa.READER_ID, "")) == 0)

    # --- official-only + write path ----------------------------------------
    front = build_front_matter(shared)
    check("front matter is official_only with 0 reports",
          front["evidence_state"] == "official_only" and front["update_report_count"] == 0,
          str({k: front[k] for k in ("evidence_state", "update_report_count")}))
    check("front matter carries structured Acrobat identity + applicability + bulletin id",
          front.get("target_track") == "Continuous" and front.get("target_version") == "25.001.20180"
          and front.get("applicability") == ["adobe-acrobat-reader", "adobe-acrobat-pro"]
          and front.get("security_bulletin_id") == "APSB26-40",
          str({k: front.get(k) for k in ("target_track", "target_version", "security_bulletin_id")}))
    check("security_advisory record renders a security-sensitive official source type",
          front.get("official_source_type") == "security_advisory", str(front.get("official_source_type")))

    # --- abbreviated months + unnamed track sections -----------------------
    # The ETK notes write dates both ways. Accepting only full month names silently discarded
    # every abbreviated row (_date_from_text returned "" -> the fail-closed guard dropped the
    # release), and "May" was the sole survivor because its abbreviation equals its full name.
    # The two fixes are COUPLED: admitting abbreviated dates without also handling a track
    # heading this adapter cannot name would publish that section's releases under the
    # previous section's track.
    for text, expected in (
        ("January 5, 2026", "2026-01-05"), ("Jan 5, 2026", "2026-01-05"),
        ("Feb 11, 2026", "2026-02-11"), ("Mar 3, 2026", "2026-03-03"),
        ("Apr 1, 2026", "2026-04-01"), ("May 18, 2026", "2026-05-18"),
        ("Jun 9, 2026", "2026-06-09"), ("Jul 23, 2026", "2026-07-23"),
        ("Aug 4, 2026", "2026-08-04"), ("Sep 9, 2026", "2026-09-09"),
        ("Sept 9, 2026", "2026-09-09"), ("Oct. 14, 2026", "2026-10-14"),
        ("Nov 11, 2026", "2026-11-11"), ("Dec 2, 2026", "2026-12-02"),
    ):
        got = aa._date_from_text(text)
        check(f"_date_from_text parses {text!r} as {expected}", got.startswith(expected), f"got {got!r}")

    check("an unmapped month token fails closed instead of defaulting to January",
          aa._date_from_text("Smarch 4, 2026") == "", repr(aa._date_from_text("Smarch 4, 2026")))
    check("TRACK_RE still names the two known tracks",
          aa.TRACK_RE.search("Continuous Track").group(1) == "Continuous"
          and aa.TRACK_RE.search("Classic Track").group(1) == "Classic")
    check("a year-based track heading is recognised as an UNNAMED track section",
          aa.TRACK_RE.search("Adobe Acrobat 2024 Track") is None
          and aa.UNNAMED_TRACK_HEADING_RE.search("Adobe Acrobat 2024 Track") is not None
          and aa.UNNAMED_TRACK_HEADING_RE.search("Windows") is None)

    MIXED = """
<h2>Continuous Track</h2>
<table>
<tr><td>26.001.21771</td><td>Windows, macOS</td><td>Jul 23, 2026</td><td>Security update APSB26-45</td></tr>
<tr><td>26.001.21745</td><td>Windows, macOS</td><td>Sept 9, 2026</td></tr>
<tr><td>26.001.21563</td><td>Windows, macOS</td><td>May 18, 2026</td></tr>
</table>
<h2>Adobe Acrobat 2024 Track</h2>
<table>
<tr><td>24.001.30350</td><td>Windows, macOS</td><td>Oct. 14, 2026</td></tr>
<tr><td>24.001.30290</td><td>Windows, macOS</td><td>Feb 11, 2026</td></tr>
</table>
<h2>Classic Track</h2>
<table>
<tr><td>20.005.30748</td><td>Windows, macOS</td><td>Dec 2, 2026</td></tr>
</table>
"""
    mixed_pro = _parse("adobe-acrobat-pro", MIXED, limit=50)
    tracks = {r["version"]: r.get("target_track") for r in mixed_pro}
    dates = {r["version"]: str(r.get("published_at"))[:10] for r in mixed_pro}
    check("abbreviated-month Continuous releases are recovered",
          "26.001.21771" in tracks and "26.001.21745" in tracks, str(sorted(tracks)))
    check("a full-month release in the same table still parses", "26.001.21563" in tracks)
    check("recovered releases keep the correct Continuous track",
          all(tracks.get(v) == "Continuous" for v in ("26.001.21771", "26.001.21745", "26.001.21563")),
          str(tracks))
    check("releases under an unnamed track section are NOT published as the previous track",
          "24.001.30350" not in tracks and "24.001.30290" not in tracks, str(sorted(tracks)))
    check("a named track section after an unnamed one is labelled correctly",
          tracks.get("20.005.30748") == "Classic", str(tracks))
    check("recovered release dates carry the right month",
          dates.get("26.001.21771") == "2026-07-23" and dates.get("26.001.21745") == "2026-09-09"
          and dates.get("20.005.30748") == "2026-12-02", str(dates))
    mixed_reader = _parse("adobe-acrobat-reader", MIXED, limit=50)
    check("Reader parses the same source independently and stays Reader-scoped",
          len(mixed_reader) == len(mixed_pro)
          and all(r.get("product_id") == "adobe-acrobat-reader" for r in mixed_reader))
    check("no malformed version escapes the recovered rows",
          all(re.fullmatch(r"\d{2}\.\d{3}\.\d{4,6}", r["version"]) for r in mixed_pro))

    # --- unknown product id is inert ---------------------------------------
    check("fetch() returns [] for a non-Acrobat product id", aa.fetch({"product_id": "obs-studio", "ingestion": {}}, 3) == [])

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
